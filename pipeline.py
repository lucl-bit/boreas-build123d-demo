"""Headless-Pipeline: Anforderungen → build123d-CAD → Simulationen → Optimierung → Exporte → Report.

    python pipeline.py --preset "Kamera-Gimbal"
    python pipeline.py --all
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import time
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

import analysis as an
import boreas_upper as bu
from payload import C, chart, ds, f, parts_items

ROOT = Path(__file__).parent
MOCK = json.loads((ROOT / "mock_data.json").read_text(encoding="utf-8"))

# id, Name, Werkzeug, Beschreibung
STAGES = [
    ("req", "Anforderungen", "JSON (Mock-Daten)", "Nutzlast, Propeller, Motoren, Material"),
    ("size", "Auto-Auslegung", "Python-Constraint-Solver", "Anforderungen → Parameter"),
    ("cad", "CAD-Aufbau", "build123d", "Volumenmodell aus Parametern"),
    ("check", "Constraint-Check", "Python", "Geometrische & physikalische Regeln"),
    ("mass", "Masse & Trägheit", "build123d / OCCT GProp", "Volumen, Schwerpunkt, Trägheitstensor"),
    ("clash", "Kollision", "build123d distance/Boolean", "Propeller ↔ Struktur ↔ Kabel"),
    ("fem", "FEM Ausleger", "build123d-Schnitte + NumPy-FE", "Durchbiegung, Spannung, Eigenfrequenz"),
    ("opt", "Optimierung", "build123d im Loop", "leichtester zulässiger Arm → Neuaufbau"),
    ("aero", "Aerodynamik", "Tessellierung + Raster", "Stirnfläche → Widerstand → v_max"),
    ("flight", "Flugdynamik", "NumPy-Zeitsimulation", "Roll-Sprungantwort mit Regler"),
    ("mfg", "Fertigung", "NumPy auf Mesh", "Überhänge, Druckbett, Zeit/Kosten"),
    ("export", "Export", "build123d export_*", "STEP · STL · 3MF · GLB · DXF · SVG · URDF"),
    ("report", "Report", "JSON", "Kennzahlen aller Stufen"),
]
LOOP_BACK = ("opt", "cad")  # Optimierung speist zurück in den CAD-Aufbau


def _slug(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()


def run_pipeline(req: dict, material: str, params: dict | None = None, name: str = "variante",
                 optimize: bool = True, with_meshes: bool = False, out_root: Path | None = None) -> dict:
    mat = MOCK["materials"][material]
    limits = MOCK["limits"]
    out_dir = (out_root or ROOT / "out") / f"{time.strftime('%Y%m%d_%H%M%S')}_{_slug(name)}"
    out_dir.mkdir(parents=True, exist_ok=True)
    stages, ctx = [], {}

    def stage(sid, fn):
        meta = next(s for s in STAGES if s[0] == sid)
        t0 = time.perf_counter()
        res = fn() or {}
        stages.append({"id": sid, "name": meta[1], "tool": meta[2], "desc": meta[3],
                       "ms": (time.perf_counter() - t0) * 1000, "status": res.pop("status", "ok"), **res})

    def s_req():
        return {"summary": f"{req['arm_count']} Motoren · Nutzlast Ø{req['payload_diameter']} mm · {material}",
                "table": {"head": ["Anforderung", "Wert"],
                          "rows": [[MOCK["requirement_fields"][k][0], f"{v} {MOCK['requirement_fields'][k][1]}"] for k, v in req.items()]}}

    def s_size():
        p = bu.Params.from_dict(params) if params else bu.autosize(req, mat, limits)
        ctx["p"] = p
        d = asdict(p)
        return {"summary": f"Reichweite {p.arm_reach:.0f} mm · Rohr Ø{2 * p.body_radius:.0f} mm · Arm {p.arm_thickness} mm",
                "table": {"head": ["Parameter", "Wert"], "rows": [[bu.PARAM_SPEC[k][1], f"{v:g} {bu.PARAM_SPEC[k][2]}"] for k, v in d.items()]},
                "params": d}

    def s_cad():
        res = bu.build(ctx["p"], accessories={"prop_diameter": req["prop_diameter"]})
        ctx["parts"], ctx["acc"] = res["parts"], res["accessories"]
        vol = sum(x.volume for x in res["parts"].values()) / 1000
        out = {"summary": f"{len(res['parts'])} Bauteile · {vol:.1f} cm³ · {sum(len(x.faces()) for x in res['parts'].values())} Flächen",
               "stats": [["Volumen", f(vol, 1, "cm³")], ["BRep gültig", "✔" if all(x.is_valid for x in res["parts"].values()) else "✘"]]}
        if with_meshes:
            out["items"] = parts_items(res["parts"], tol=0.15)
        return out

    def s_check():
        mass = sum(x.volume for x in ctx["parts"].values()) * mat["density"] / 1000
        checks = bu.check_constraints(ctx["p"], req, mat, limits, mass)
        n_ok = sum(c["ok"] for c in checks)
        ctx["checks"] = checks
        return {"summary": f"{n_ok}/{len(checks)} Constraints erfüllt", "status": "ok" if n_ok == len(checks) else "warn",
                "table": {"head": ["Constraint", "Wert", "Grenze", ""],
                          "rows": [[c["name"], f(c["value"], 2), c["limit"], "✔" if c["ok"] else "✘"] for c in checks]}}

    def s_mass():
        rep = an.inertia_report(ctx["p"], ctx["parts"], req, mat, MOCK)
        tot = ctx["inertia"] = rep["total"]
        ik = tot["I_kgm2"]
        return {"summary": f"{tot['mass_g']:.0f} g · Ixx {ik[0, 0]:.2e} kg·m²",
                "stats": [["Abflugmasse", f(tot["mass_g"], 1, "g")], ["Schwerpunkt z", f(tot["com_mm"][2], 1, "mm")],
                          ["Ixx / Iyy / Izz", f"{ik[0, 0]:.2e} / {ik[1, 1]:.2e} / {ik[2, 2]:.2e}"]],
                "table": {"head": ["Komponente", "Masse g", "x", "y", "z", "Quelle"], "rows": rep["rows"]}}

    def s_clash():
        cc = an.clash_check(ctx["p"], ctx["parts"], ctx["acc"], req)
        bad = [r for r in cc["rows"] if not r["ok"]]
        return {"summary": f"{len(cc['rows'])} Paare · {len(bad)} Kollisionen · min. {min(r['distance'] for r in cc['rows']):.1f} mm",
                "status": "ok" if not bad else "warn",
                "table": {"head": ["A", "B", "Abstand", ""], "rows": [[r["a"], r["b"], f(r["distance"], 2, "mm"), "✔" if r["ok"] else "✘"] for r in cc["rows"]]}}

    def s_fem():
        fem = ctx["fem"] = an.beam_fem(ctx["p"], ctx["parts"]["Rumpf"], req, mat, ctx["parts"])
        s = fem["s"] - ctx["p"].body_radius
        ok = fem["safety_factor"] >= limits["min_safety_factor"]
        return {"summary": f"δ {fem['tip_deflection']:.2f} mm · σmax {fem['max_stress']:.1f} MPa · SF {fem['safety_factor']:.1f} · f₁ {fem['f1_hz']:.0f} Hz",
                "status": "ok" if ok else "warn",
                "charts": [chart("Durchbiegung", "s [mm]", "w [mm]", [ds("FEM", s, fem["w"], C["green"])]),
                           chart("Biegespannung", "s [mm]", "σ [MPa]", [ds("σ", s, fem["stress"], C["orange"], fill=True)])]}

    def s_opt():
        if not optimize:
            return {"summary": "übersprungen", "status": "skip"}
        base = sum(x.volume for x in ctx["parts"].values()) * mat["density"] / 1000
        sw = an.design_sweep(ctx["p"], req, mat, limits, base)
        best = sw["best"]
        if not best:
            return {"summary": "kein zulässiges Design gefunden", "status": "warn"}
        if best.get("current"):
            return {"summary": f"{sw['n_cad']} CAD-Varianten · aktuelles Design ist bereits das leichteste zulässige", "loop": True}
        before = base
        ctx["p"] = replace(ctx["p"], arm_thickness=float(best["t"]), arm_width=float(best["w"]))
        res = bu.build(ctx["p"], accessories={"prop_diameter": req["prop_diameter"]})
        ctx["parts"], ctx["acc"] = res["parts"], res["accessories"]
        ctx["inertia"] = an.inertia_report(ctx["p"], ctx["parts"], req, mat, MOCK)["total"]
        ctx["fem"] = an.beam_fem(ctx["p"], ctx["parts"]["Rumpf"], req, mat, ctx["parts"])
        after = sum(x.volume for x in ctx["parts"].values()) * mat["density"] / 1000
        ok = [r for r in sw["points"] if r["ok"]]
        out = {"summary": f"{sw['n_cad']} CAD-Varianten · Arm {best['t']}×{best['w']} mm · {before:.0f} → {after:.0f} g",
               "loop": True,
               "stats": [["Masse vorher", f(before, 1, "g")], ["Masse nachher", f(after, 1, "g")],
                         ["Durchbiegung neu (FEM)", f(ctx["fem"]["tip_deflection"], 2, "mm")]],
               "charts": [chart("Designraum", "Masse [g]", "Durchbiegung [mm]",
                                [ds("zulässig", [r["mass"] for r in ok], [r["defl"] for r in ok], C["green"], points=True),
                                 ds("Pareto", [r["mass"] for r in sw["pareto"]], [r["defl"] for r in sw["pareto"]], C["cyan"]),
                                 ds("Optimum", [best["mass"]], [best["defl"]], C["yellow"], points=True)], "scatter") | {"ylog": True}]}
        if with_meshes:
            out["items"] = parts_items(ctx["parts"], tol=0.15)
        return out

    def s_aero():
        ae = an.aero(ctx["p"], ctx["parts"], ctx["inertia"]["mass_g"], req, MOCK)
        ctx["aero"] = ae
        return {"summary": f"A_front {ae['A_front_mm2'] / 100:.0f} cm² · v_max {ae['v_max']:.1f} m/s",
                "images": [{"title": "Stirnfläche", "src": ae["img_front"]}, {"title": "Draufsicht", "src": ae["img_top"]}],
                "charts": [chart("v vs. Neigung", "θ [°]", "v [m/s]", [ds("v", ae["tilt"], ae["speed"], C["cyan"])])]}

    def s_flight():
        fl = ctx["flight"] = an.roll_step(ctx["p"], ctx["inertia"]["I_kgm2"], ctx["inertia"]["mass_g"], req, MOCK)
        return {"summary": f"Anstieg {fl['rise_time'] * 1000:.0f} ms · Überschwingen {fl['overshoot']:.0f} % · Schwebe-Gas {fl['hover_throttle'] * 100:.0f} %",
                "charts": [chart("Roll-Sprungantwort", "t [s]", "θ [°]", [ds("θ", fl["t"], fl["theta"], C["green"])])]}

    def s_mfg():
        mf = ctx["mfg"] = an.manufacturing(ctx["parts"], mat, MOCK)
        out = {"summary": f"{sum(v['print_h'] for v in mf.values()):.1f} h Druck · {sum(v['cost'] for v in mf.values()):.2f} € (Mock)",
               "table": {"head": ["Teil", "Überhang", "Zeit", "Kosten"],
                         "rows": [[k, f(v["overhang_pct"], 1, "%"), f(v["print_h"], 1, "h"), f(v["cost"], 2, "€")] for k, v in mf.items()]}}
        if with_meshes:
            out["items"] = [{"id": f"mf:{k}", "color": C["grey"], "opacity": 1, "vertices": v["vertices"],
                             "triangles": v["triangles"], "colors": v["colors"]} for k, v in mf.items()]
        return out

    def s_export():
        files = []
        for fmt in ("step", "stl", "3mf", "glb", "dxf", "svg"):
            path = out_dir / f"boreas_oberteil.{fmt}"
            bu.export(ctx["parts"], fmt, str(path), ctx["p"],
                      {"material": mat["label"], "variant": name,
                       "mass_body": f"{ctx['parts']['Rumpf'].volume * mat['density'] / 1000:.0f} g"})
            files.append(path)
        an.export_urdf(ctx["p"], ctx["parts"], ctx["inertia"], req, str(out_dir / "urdf"))
        files.append(Path(shutil.make_archive(str(out_dir / "urdf"), "zip", out_dir / "urdf")))
        ctx["files"] = files
        rel = lambda fp: "/out/" + fp.relative_to(ROOT / "out").as_posix()
        return {"summary": f"{len(files)} Dateien in out/{out_dir.name}",
                "downloads": [{"label": f"⬇ {fp.name} ({fp.stat().st_size / 1024:.0f} kB)", "url": rel(fp)} for fp in files]}

    def s_report():
        rep = {
            "name": name, "material": material, "requirements": req, "params": asdict(ctx["p"]),
            "constraints": [{k: c[k] for k in ("name", "value", "limit", "ok")} for c in ctx["checks"]],
            "mass_g": ctx["inertia"]["mass_g"], "inertia_kgm2": np.asarray(ctx["inertia"]["I_kgm2"]).tolist(),
            "fem": {k: ctx["fem"][k] for k in ("tip_deflection", "max_stress", "safety_factor", "f1_hz")},
            "aero": {k: ctx["aero"][k] for k in ("A_front_mm2", "A_top_mm2", "v_max", "tilt_max")},
            "flight": {k: ctx["flight"][k] for k in ("rise_time", "overshoot", "hover_throttle", "tau_max")},
            "manufacturing": {k: {kk: v[kk] for kk in ("overhang_pct", "print_h", "cost", "fits")} for k, v in ctx["mfg"].items()},
            "stages": [{"id": s["id"], "ms": s["ms"], "status": s["status"], "summary": s.get("summary", "")} for s in stages],
            "files": [fp.name for fp in ctx["files"]],
        }
        path = out_dir / "report.json"
        path.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
        return {"summary": f"report.json · Gesamt {sum(s['ms'] for s in stages) / 1000:.1f} s",
                "downloads": [{"label": "⬇ report.json", "url": "/out/" + path.relative_to(ROOT / "out").as_posix()}]}

    for sid, fn in [("req", s_req), ("size", s_size), ("cad", s_cad), ("check", s_check), ("mass", s_mass),
                    ("clash", s_clash), ("fem", s_fem), ("opt", s_opt), ("aero", s_aero), ("flight", s_flight),
                    ("mfg", s_mfg), ("export", s_export), ("report", s_report)]:
        stage(sid, fn)
    return {"stages": stages, "out_dir": str(out_dir), "total_ms": sum(s["ms"] for s in stages)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preset", default="Boreas Referenz (≈ STEP)")
    ap.add_argument("--all", action="store_true", help="alle Mock-Datensätze nacheinander")
    ap.add_argument("--no-opt", action="store_true", help="Optimierungsstufe überspringen")
    args = ap.parse_args()
    names = list(MOCK["presets"]) if args.all else [args.preset]
    for name in names:
        pre = MOCK["presets"][name]
        print(f"\n=== {name} ({pre['material']}) ===")
        res = run_pipeline(pre["req"], pre["material"], name=name, optimize=not args.no_opt)
        for s in res["stages"]:
            print(f"  {s['status']:4s} {s['name']:18s} {s['ms']:7.0f} ms  {s.get('summary', '')}")
        print(f"  → {res['out_dir']}  ({res['total_ms'] / 1000:.1f} s)")


if __name__ == "__main__":
    main()
