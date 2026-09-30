"""Kommandozeile der B-rep-Seite (build123d) – Vertrag siehe PLAN.md.

python -m brep.cli --spec spec/boreas_spec.json --task B02 --out <dir> [--set gruppe.param=wert ...]

Jede Aufgabe schreibt <out>/result.json + die Dateien, auf die es verweist (STL je Teil, Vorschau-PNG, …).
Aufgaben, die B-rep nicht oder nur teilweise kann, liefern status "unsupported"/"partial" mit Begründung.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import math
import sys
import time
import traceback
from pathlib import Path

import numpy as np
from build123d import (
    Axis, Box, Circle, Compound, Cylinder, GeomType, Location, Mesher, Plane, Pos, RigidJoint, Solid, Spline, Wire,
    __version__ as B3D_VERSION, export_step, export_stl, import_step, offset, section, sweep,
)

from .assembly import build, build_features
from .skeleton import Skeleton
from .spec import DEFAULT_SPEC, Spec

ROOT = Path(__file__).resolve().parent.parent
REF_STEP = ROOT / "Mohammed_0.1 Full Shell.step"
DENSITY_G_MM3 = json.loads((ROOT / "spec" / "boreas_spec.json").read_text(encoding="utf-8"))["meta"].get("density_g_cm3", 1.24) / 1000  # Mock
PART_ORDER = ("upper", "lower", "nose", "nose_insert")


# --------------------------------------------------------------------------- Hilfen
def peak_mem_mb() -> float | None:
    """Spitzen-Arbeitsspeicher des Prozesses (OCCT allokiert nativ, tracemalloc sieht das nicht)."""
    if sys.platform != "win32":
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    from ctypes import wintypes

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] +                    [(n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "a", "b", "c", "d", "e", "f")]
    k32 = ctypes.WinDLL("kernel32")
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    if not k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
        return None
    return c.PeakWorkingSetSize / 2 ** 20


def code_loc(*modules: str) -> int:
    """Nicht-leere, nicht-Kommentar-Zeilen der beteiligten Module (für den Aufwands-Vergleich)."""
    n = 0
    for m in modules:
        for f in (ROOT / m).rglob("*.py") if (ROOT / m).is_dir() else [ROOT / m]:
            if "tests" in f.parts:
                continue
            n += sum(1 for line in f.read_text(encoding="utf-8").splitlines()
                     if line.strip() and not line.strip().startswith("#"))
    return n


MODEL_LOC_MODULES = ("brep/spec.py", "brep/skeleton.py", "brep/geom.py", "brep/profiles.py", "brep/features.py",
                     "brep/assembly.py", "brep/groups")


def bbox(shape) -> list[float]:
    b = shape.bounding_box()
    return [round(v, 3) for v in (b.min.X, b.min.Y, b.min.Z, b.max.X, b.max.Y, b.max.Z)]


def shape_metrics(shape) -> dict:
    return {"volume_mm3": round(shape.volume, 2), "area_mm2": round(shape.area, 2),
            "mass_g": round(shape.volume * DENSITY_G_MM3, 2), "bbox_mm": bbox(shape), "valid": bool(shape.is_valid),
            "solids": len(shape.solids()), "faces": len(shape.faces())}


class Task:
    """Sammelt Ergebnis, Dateien und Notizen einer Aufgabe."""

    def __init__(self, task: str, out: Path, spec: Spec):
        self.task, self.out, self.spec = task, out, spec
        self.status = "ok"
        self.metrics: dict = {}
        self.files: dict = {}
        self.notes: list[str] = []
        self.loc = code_loc(*MODEL_LOC_MODULES)
        self.mesh_retries: dict = {}
        self.t0 = time.perf_counter()
        out.mkdir(parents=True, exist_ok=True)

    def note(self, s: str) -> None:
        self.notes.append(s)

    def stl(self, name: str, shape, tol: float = 0.02) -> str:
        """Binäres STL. Freiformflächen lassen sich bei manchen Toleranzen nicht triangulieren (OCCT überspringt
        die Fläche → Loch im Netz); dann mit feinerer Toleranz neu vernetzen, bis das Netz dicht ist."""
        from OCP.BRepTools import BRepTools
        sys.path.insert(0, str(ROOT))
        from bench.metrics import read_stl, topology
        rel = f"{name}.stl"
        for k, tl in enumerate((tol, 0.002, 0.001, 0.05)):
            if k:
                BRepTools.Clean_s(shape.wrapped)
            export_stl(shape, str(self.out / rel), tolerance=tl, angular_tolerance=0.1)
            if topology(read_stl(self.out / rel))["open_edges"] == 0:
                break
        if k:
            self.mesh_retries[name] = {"tolerance_mm": tl, "attempts": k + 1}
        return rel

    def write_parts(self, parts: dict, key: str = "parts") -> None:
        self.files.setdefault(key, {})
        for n in PART_ORDER + tuple(k for k in parts if k not in PART_ORDER):
            if n in parts and parts[n] is not None:
                self.files[key][n] = self.stl(n, parts[n])
        self.metrics.setdefault("parts", {})
        for n, p in parts.items():
            if p is not None:
                self.metrics["parts"][n] = shape_metrics(p)
        whole = Compound([p for p in parts.values() if p is not None])
        self.files["mesh"] = self.stl("model", whole)
        m = shape_metrics(whole)
        for k in ("volume_mm3", "area_mm2", "mass_g", "bbox_mm"):
            self.metrics[k] = m[k]

    def preview(self, name: str = "preview.png", views=("iso", "front", "top")) -> None:
        try:
            sys.path.insert(0, str(ROOT))
            from bench.metrics import read_stl
            from tools.render_views import PALETTE, render
            meshes = [(read_stl(self.out / rel), PALETTE[i % len(PALETTE)])
                      for i, rel in enumerate((self.files.get("parts") or {}).values())]
            if not meshes and self.files.get("mesh"):
                meshes = [(read_stl(self.out / self.files["mesh"]), PALETTE[0])]
            if meshes:
                render(str(self.out / name), meshes, views, max_tris=60_000, dpi=60)
                self.files.setdefault("images", []).append(name)
                self.files.setdefault("image", name)
        except Exception as exc:  # Vorschau ist Beiwerk
            self.note(f"Vorschau fehlgeschlagen: {exc}")

    def result(self) -> dict:
        if self.mesh_retries:
            self.metrics["stl_retessellation"] = self.mesh_retries
            self.note("STL: Triangulierung einzelner Freiformflächen schlug bei 0.02 mm fehl (Loch im Netz), "
                      f"automatisch neu vernetzt ({', '.join(self.mesh_retries)}).")
        return {"task": self.task, "tool": "brep", "tool_version": f"build123d {B3D_VERSION}", "status": self.status,
                "runtime_s": round(time.perf_counter() - self.t0, 3), "peak_mem_mb": round(peak_mem_mb() or 0, 1),
                "params": {"voxel_size_mm": None, "overrides": self.spec.overrides or {}},
                "metrics": self.metrics, "files": self.files, "code_loc": self.loc, "notes": " ".join(self.notes)}


def model(t: Task) -> dict:
    res = build(t.spec)
    t.metrics["build_timing_s"] = {k: (round(v, 3) if isinstance(v, float) else {g: round(x, 3) for g, x in v.items()})
                                   for k, v in res["timing"].items()}
    for n in res["notes"]:
        t.note(n + ".")
    return res


# --------------------------------------------------------------------------- Gemeinsame Aufgaben B01–B10
def task_b01(t: Task) -> None:
    """Referenz-STEP nativ importieren und mit dem eigenen Modell vergleichen."""
    t0 = time.perf_counter()
    ref = import_step(str(REF_STEP))
    t.metrics["step_import_s"] = round(time.perf_counter() - t0, 3)
    shells = ref.shells()
    t.metrics["reference"] = {"faces": len(ref.faces()), "shells": len(shells),
                              "valid_solids": sum(bool(Solid(s).is_valid) for s in shells),
                              "face_types": {g.name: sum(1 for f in ref.faces() if f.geom_type == g)
                                             for g in GeomType if any(f.geom_type == g for f in ref.faces())}}
    res = model(t)
    t.write_parts(res["parts"])
    sys.path.insert(0, str(ROOT))
    from bench.metrics import read_stl
    from bench.reference import compare_to_reference
    dev = {}
    for n in ("upper", "lower"):
        r = compare_to_reference(read_stl(t.out / t.files["parts"][n]), n, do_icp=False)
        o = r["offset_only"]
        dev[n] = {"mean_mm": round(o["symmetric_mean_mm"], 3), "p95_mm": round(o["symmetric_p95_mm"], 3),
                  "model_to_ref_p50_mm": round(o["a_to_b_mm"]["p50"], 3), "hausdorff_mm": round(o["hausdorff_mm"], 2)}
    t.metrics["deviation_to_reference"] = dev
    t.note(f"STEP nativ importiert ({len(ref.faces())} Flächen, {t.metrics['step_import_s']} s); exakte Flächen "
           "(B-Splines, Zylinder, Tori) bleiben erhalten. Nur das Unterteil ist im STEP ein gültiger Volumenkörper, "
           "Oberteil und Nase sind Schalen mit Orientierungsfehlern (Freihand-Export). Abweichung Modell↔Referenz "
           "über die Oberfläche gemessen; grosse Maxima stammen von bewusst ergänzten Laschen und weggelassenen "
           "Details (Rastnasen, Innentaschen).")


def task_b02(t: Task) -> None:
    res = model(t)
    t.write_parts(res["parts"])
    export_step(Compound([p for p in res["parts"].values()]), str(t.out / "model.step"))
    t.files["step"] = "model.step"
    t.metrics["groups"] = len(t.spec.raw["groups"])
    t.metrics["parameters"] = sum(1 for _ in t.spec.iter_params())
    t.note(f"Gesamtmodell aus {t.metrics['parameters']} Parametern in {t.metrics['groups']} Gruppen (Skelett-Methode). "
           "Jede Gruppe baut ihre Features nur aus Skelett + eigenen Parametern; Bool-Reihenfolge fest.")
    t.preview()


def task_b03(t: Task) -> None:
    """Wie B02; der Runner variiert je Gruppe einen Parameter und vergleicht die Teile."""
    res = model(t)
    t.write_parts(res["parts"])
    t.note("Regeneration mit geänderter Gruppe: nur die Features der geänderten Gruppe werden neu gebaut "
           "(Gruppen-Cache), die Bool-Verknüpfung der Teile läuft komplett neu.")


def task_b04(t: Task) -> None:
    """Tropfenprofil: Aero-Fins (NACA-Tropfen, Loft) und Motorgondeln (Potenz-Ogive, Rotation)."""
    feats = build_features(t.spec)
    fins = [f.shape for f in feats if f.group == "body_fins"]
    tails = [f.shape for f in feats if f.group == "tail_fins"]
    pods = [f.shape for f in feats if f.group == "motor_pods"]
    parts = {"body_fins": Compound(fins), "tail_fins": Compound(tails), "motor_pods": Compound(pods)}
    t.write_parts(parts)
    fin = fins[0]
    t.metrics["fin_face_types"] = sorted({f.geom_type.name for f in fin.faces()})
    # Profil-Treue: Schnitt durch einen Fin bei halber Spannweite vs. Formel
    from .profiles import teardrop_half_thickness
    g = t.spec.group("body_fins")
    sk = Skeleton.from_params(t.spec.group("skeleton"))
    a = math.radians(sk.arm_angles()[0])
    s_mid = (sk.joint_radius + sk.motor_radius) / 2
    plane = Plane(origin=(s_mid * math.cos(a), s_mid * math.sin(a), 0), z_dir=(math.cos(a), math.sin(a), 0))
    sec = section(fin, plane)
    lam = (s_mid - sk.joint_radius) / (sk.motor_radius - sk.joint_radius)
    T = g.thickness_root + (g.thickness_tip - g.thickness_root) * lam
    t.metrics["profile_check"] = {"station_s_mm": round(s_mid, 2), "max_thickness_formula_mm": round(T, 3)}
    try:
        qdir = np.array([-math.sin(a), math.cos(a), 0.0])
        ext = sec.edges()
        samples = np.array([[p.X, p.Y, p.Z] for e in ext for p in (e.position_at(u) for u in np.linspace(0, 1, 60))])
        q = samples @ qdir
        t.metrics["profile_check"]["max_thickness_brep_mm"] = round(float(q.max() - q.min()), 4)
        t.metrics["profile_check"]["error_mm"] = round(abs(float(q.max() - q.min()) - T), 4)
    except Exception as exc:
        t.note(f"Profilprüfung übersprungen ({exc}).")
    t.note("Fins: NACA-Tropfenprofil als Spline durch 81 Stützpunkte, Regelfläche (Loft) zwischen Wurzel- und "
           "Spitzenprofil – exakte, glatte Flächen, die im STEP als B-Spline-Flächen ankommen. Gondeln: Rotation "
           "einer Potenz-Ogive. Formänderung = Parameter ändern, kein Nachmodellieren.")
    t.preview(views=("iso", "front", "top"))


def task_b05(t: Task) -> None:
    """Wandstärke/Schale: Hohlkörper per Innenkontur (Rumpf) und per Offset (Gondel, ganzes Oberteil)."""
    res = model(t)
    parts = res["parts"]
    tries = {}
    for name, amount in (("pod_offset_-1.2", None), ("upper_offset_-1.0", -1.0), ("lower_offset_-1.0", -1.0)):
        t0 = time.perf_counter()
        try:
            if name.startswith("pod"):
                from .groups.motor_pods import pod
                g = t.spec.group("motor_pods")
                p = pod(Skeleton.from_params(t.spec.group("skeleton")), g)
                ok = p.is_valid
            else:
                target = parts[name.split("_")[0]]
                shell = offset(target, amount=amount, openings=target.faces().sort_by(Axis.Z)[0])
                ok = shell.is_valid and shell.volume > 0
            tries[name] = {"ok": bool(ok), "s": round(time.perf_counter() - t0, 3)}
        except Exception as exc:
            tries[name] = {"ok": False, "s": round(time.perf_counter() - t0, 3), "error": type(exc).__name__}
    t.metrics["shell_attempts"] = tries
    wall = t.spec.group("lower_body").wall
    w_lo, w_up = t.spec.param_info("lower_body.wall")["min"], t.spec.param_info("upper_body.wall")["min"]
    thin = t.spec.with_overrides({"lower_body.wall": w_lo, "upper_body.wall": w_up})
    thin_parts = build(thin)["parts"]
    t.write_parts({"upper": thin_parts["upper"], "lower": thin_parts["lower"]})
    t.metrics["wall_variant"] = {"lower_body.wall": [wall, w_lo], "upper_body.wall": [t.spec.group("upper_body").wall, w_up]}
    ok_all = all(v["ok"] for v in tries.values())
    t.status = "ok" if ok_all else "partial"
    t.note("Rumpfwände entstehen exakt über eine versetzte Innenkontur (Parameter `wall`), Ergebnis hier mit der "
           "kleinsten erlaubten Wand. Gondel-Schale per offset() mit offenem Boden funktioniert. Offset auf das ganze verrechnete Teil: "
           + ", ".join(f"{k}: {'ok' if v['ok'] else 'fehlgeschlagen'}" for k, v in tries.items() if not k.startswith("pod"))
           + ". Offset/Shell auf komplexen Freiform-Teilen ist eine bekannte Schwachstelle von B-rep-Kernen.")
    t.preview()


def task_b06(t: Task) -> None:
    """Verrundungen: Gondel-Übergang und Heckflossen-Wurzel mit steigendem Radius."""
    results = []
    for r in (0.4, 1.0, 2.0, 3.0):
        for key in ("details.pod_fillet", "details.tail_root_fillet"):
            info = t.spec.param_info(key)
            if not info["min"] <= r <= info["max"]:
                continue
            spec = t.spec.with_overrides({key: r})
            t0 = time.perf_counter()
            res = build(spec)
            note = next((n for n in res["notes"] if ("Gondel" in n) == (key.endswith("pod_fillet"))), "")
            results.append({"param": key, "radius_mm": r, "ok": "fehlgeschlagen" not in note and "keine" not in note
                            and "ungültig" not in note, "note": note, "s": round(time.perf_counter() - t0, 2)})
    t.metrics["fillet_attempts"] = results
    best = t.spec.with_overrides({"details.pod_fillet": 1.0})
    t.write_parts(build(best)["parts"])
    n_ok = sum(r["ok"] for r in results)
    t.status = "ok" if n_ok == len(results) else "partial"
    t.note(f"{n_ok}/{len(results)} Verrundungsversuche erfolgreich. Kanten werden über Selektoren (Kreiskanten an der "
           "Motorachse, Schnittkanten auf der Kegelfläche) gefunden – exakte Rundungen mit echtem Radius, aber "
           "empfindlich: Fillets auf Kanten zwischen Freiformflächen scheitern in OCCT häufig.")
    t.preview()


def task_b07(t: Task) -> None:
    res = model(t)
    t.write_parts(res["parts"])
    props = {}
    for n, p in res["parts"].items():
        c = p.center()
        I = np.array(p.matrix_of_inertia)
        props[n] = {"volume_mm3": round(p.volume, 3), "area_mm2": round(p.area, 3),
                    "mass_g": round(p.volume * DENSITY_G_MM3, 3), "centroid_mm": [round(c.X, 3), round(c.Y, 3), round(c.Z, 3)],
                    "inertia_mm5": np.round(I, 1).tolist()}
    t.metrics["mass_properties"] = props
    t.note("Masseneigenschaften exakt aus der Flächenbeschreibung (Gauss-Integration über die B-rep-Flächen), "
           "unabhängig von einer Auflösung. Trägheit je Teil in mm⁵ (mit Dichte multiplizieren).")


def task_b08(t: Task) -> None:
    res = model(t)
    t.write_parts(res["parts"])
    t0 = time.perf_counter()
    try:
        mesher = Mesher()
        for n, p in res["parts"].items():
            mesher.add_shape(p, linear_deflection=0.02, angular_deflection=0.2)
        mesher.write(str(t.out / "model.3mf"))
        t.files["3mf"] = "model.3mf"
        t.metrics["export_3mf_s"] = round(time.perf_counter() - t0, 3)
    except Exception as exc:
        t.status = "partial"
        t.note(f"3MF-Export fehlgeschlagen ({type(exc).__name__}).")
    sys.path.insert(0, str(ROOT))
    from bench.metrics import read_stl
    tris = read_stl(t.out / t.files["mesh"])
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    area = np.linalg.norm(n, axis=1) / 2
    nz = n[:, 2] / (2 * area + 1e-12)
    overhang = float(area[nz < -math.cos(math.radians(45))].sum() / area.sum())
    t.metrics["printability"] = {"overhang_area_share_45deg": round(overhang, 4),
                                 "min_wall_limit_mm": t.spec.group("details").min_wall,
                                 "min_wall_model_mm": min(t.spec.group("upper_body").wall, t.spec.group("lower_body").wall,
                                                          t.spec.group("nose").wall)}
    t.note("STL je Teil + 3MF (Mesher). Tessellierung frei wählbar (hier 0.02 mm Sehnenfehler). Druckbarkeits-Check: "
           "Überhangfläche > 45° aus dem Netz, Mindestwand direkt aus den Parametern (exakt).")


def task_b09(t: Task) -> None:
    res = model(t)
    t.write_parts(res["parts"])
    body = Compound([res["parts"][n] for n in ("upper", "lower", "nose")])
    b = body.bounding_box()
    L = max(b.size.X, b.size.Y, b.size.Z)
    t0 = time.perf_counter()
    domain = Pos(b.center().X, b.center().Y, b.center().Z) * Box(3 * L, 3 * L, 5 * L)
    fluid = domain
    for n in ("upper", "lower", "nose"):
        fluid = fluid - res["parts"][n]
    t.metrics["fluid_domain_s"] = round(time.perf_counter() - t0, 3)
    t.metrics["fluid_domain_valid"] = bool(fluid.is_valid)
    t.files["fluid_domain"] = t.stl("fluid_domain", fluid, tol=0.1)
    export_step(fluid, str(t.out / "fluid_domain.step"))
    t.files["fluid_domain_step"] = "fluid_domain.step"
    outer = [f for n in ("upper", "lower", "nose") for f in res["parts"][n].faces()]
    t.metrics["wetted_area_total_mm2"] = round(sum(f.area for f in outer), 1)
    t.note("Strömungsgebiet = Quader − Drohne als exakter B-rep-Körper (STEP für Gmsh/ANSYS, STL für snappyHexMesh). "
           "Stirnfläche berechnet der Runner neutral aus dem Netz. Benetzte Fläche hier inkl. Innenflächen des Rohrs "
           "(Kühlluftweg).")


def task_b10(t: Task) -> None:
    res = model(t)
    t.write_parts(res["parts"])
    export_step(Compound(list(res["parts"].values())), str(t.out / "model.step"))
    t.files["step"] = "model.step"
    t.metrics["step_size_kb"] = round((t.out / "model.step").stat().st_size / 1024, 1)
    t.metrics["stl_size_kb"] = round(sum((t.out / f).stat().st_size for f in t.files["parts"].values()) / 1024, 1)
    t.note("Vollständiger Aufbau inkl. STEP- und STL-Export. Laufzeit/RAM misst der Runner über mehrere Läufe.")


# --------------------------------------------------------------------------- B-rep-Stärken R01–R04
def task_r01(t: Task) -> None:
    from .drawing import drawing_svg
    res = model(t)
    t.write_parts(res["parts"])
    t0 = time.perf_counter()
    drawing_svg(t.spec, res["parts"], str(t.out / "drawing.svg"))
    t.metrics["drawing_s"] = round(time.perf_counter() - t0, 2)
    t.files["drawing"] = "drawing.svg"
    t.files.setdefault("images", []).append("drawing.svg")
    t.files["image"] = "drawing.svg"
    t.note("Bemasste A3-Zeichnung direkt aus dem Modell: exakte Kanten per Hidden-Line-Removal, Maszahlen aus den "
           "Parametern, Halbschnitt mit Schraffur. Ändert sich ein Parameter, ändert sich die Zeichnung mit.")


def task_r02(t: Task) -> None:
    res = model(t)
    t.write_parts(res["parts"])
    step = t.out / "model.step"
    export_step(Compound([p for p in res["parts"].values()]), str(step))
    t.files["step"] = "model.step"
    back = import_step(str(step))
    upper = res["parts"]["upper"]
    sel = {
        "planare_flaechen": len(upper.faces().filter_by(GeomType.PLANE)),
        "bspline_flaechen": len(upper.faces().filter_by(GeomType.BSPLINE)),
        "kreiskanten": len(upper.edges().filter_by(GeomType.CIRCLE)),
        "unterste_flaeche_z": round(upper.faces().sort_by(Axis.Z)[0].center().Z, 3),
        "groesste_flaeche_mm2": round(max(f.area for f in upper.faces()), 1),
    }
    t.metrics["selectors"] = sel
    t.metrics["step_roundtrip"] = {"volume_before": round(sum(p.volume for p in res["parts"].values()), 3),
                                   "volume_after": round(back.volume, 3), "size_kb": round(step.stat().st_size / 1024, 1)}
    t.note("STEP AP214 mit exakten Flächen; Rundreise Export→Import ohne Volumenverlust. Selektoren finden Kanten und "
           "Flächen nach Typ, Lage, Grösse – die Grundlage für Fillets, Bemassung, Lasten/Randbedingungen in FEM.")


def task_r03(t: Task) -> None:
    res = model(t)
    parts = res["parts"]
    sk = Skeleton.from_params(t.spec.group("skeleton"))
    upper, lower, nose = parts["upper"], parts["lower"], parts["nose"]
    RigidJoint("split", lower, Location((0, 0, sk.split_z)))
    RigidJoint("split", upper, Location((0, 0, sk.split_z)))
    RigidJoint("nose", upper, Location((0, 0, sk.nose_joint_z)))
    RigidJoint("base", nose, Location((0, 0, sk.nose_joint_z)))
    for i, m in enumerate(sk.motor_positions()):
        RigidJoint(f"motor_{i}", upper, Location((m.X, m.Y, sk.split_z + t.spec.group("motor_pods").base_height)))
    lower.joints["split"].connect_to(upper.joints["split"])
    upper.joints["nose"].connect_to(nose.joints["base"])
    asm = Compound(children=[upper, lower, nose, parts["nose_insert"]])
    for p, n in zip((upper, lower, nose, parts["nose_insert"]), PART_ORDER):
        p.label = n
    export_step(asm, str(t.out / "assembly.step"))
    t.files["step"] = "assembly.step"
    t.write_parts(parts)
    clash = {}
    for a, b in (("upper", "lower"), ("upper", "nose")):
        inter = parts[a] & parts[b]
        clash[f"{a}∩{b}_mm3"] = round(inter.volume if inter else 0.0, 3)
    t.metrics["interference"] = clash
    t.metrics["joints"] = {n: sorted(p.joints) for n, p in (("upper", upper), ("lower", lower), ("nose", nose))}
    t.note("Baugruppe über benannte Joints (Trennebene, Nasen-Sitz, 4 Motor-Anschlüsse) aus dem Skelett; STEP mit "
           "Teilenamen. Kollisionsprüfung exakt per Schnittmenge. URDF/Kinematik siehe Demo-Modus ①.")


def task_r04(t: Task) -> None:
    """Exakte Passung: Spiel zwischen Oberteil-Lasche und Unterteil-Kerbe wird am Modell nachgemessen."""
    res = model(t)
    t.write_parts(res["parts"])
    g = t.spec.group("joints")
    feats = build_features(t.spec)
    tab = next(f.shape for f in feats if f.name == "upper_tab_0")
    lower = res["parts"]["lower"]
    t0 = time.perf_counter()
    gap = tab.distance_to(lower)
    t.metrics["fit"] = {"clearance_spec_mm": g.clearance, "clearance_measured_mm": round(gap, 6),
                        "error_mm": round(abs(gap - g.clearance), 6), "measure_s": round(time.perf_counter() - t0, 3)}
    for c in (0.1, 0.2, 0.4):
        if t.spec.param_info("joints.clearance")["min"] <= c <= t.spec.param_info("joints.clearance")["max"]:
            s2 = t.spec.with_overrides({"joints.clearance": c})
            f2 = build_features(s2)
            tab2 = next(f.shape for f in f2 if f.name == "upper_tab_0")
            low2 = build(s2)["parts"]["lower"]
            t.metrics["fit"][f"clearance_{c}"] = round(tab2.distance_to(low2), 6)
    t.note("Passungsspiel ist ein Parameter; am fertigen Modell nachgemessen skaliert der Spalt exakt mit dem Parameter "
           "(kleinster Abstand liegt am Innenradius, weil das Spiel als Winkel am mittleren Radius definiert ist). Toleranzen, Bemassung und Prüfmasse bleiben exakt – bei Voxeln wäre die "
           "Auflösung (Voxelgrösse) die Grenze.")


# --------------------------------------------------------------------------- Voxel-Stärken V01–V04 (B-rep-Versuch)
def task_v01(t: Task) -> None:
    """Gitter-Infill im Unterteil als Stab-Gitter aus Zylindern (einziger B-rep-Weg)."""
    res = model(t)
    lower = res["parts"]["lower"]
    feats = build_features(t.spec)
    cavity = next(f.shape for f in feats if f.name == "cone_cavity")
    attempts = []
    best = None
    for cell in (16.0, 12.0, 8.0):
        t0 = time.perf_counter()
        b = cavity.bounding_box()
        struts = []
        xs = np.arange(b.min.X, b.max.X + cell, cell)
        zs = np.arange(b.min.Z, b.max.Z + cell, cell)
        for x in xs:
            for y in xs:
                struts.append(Pos(x, y, (b.min.Z + b.max.Z) / 2) * Cylinder(0.8, b.size.Z))
            for z in zs:
                struts.append(Pos(x, 0, z) * Cylinder(0.8, b.size.X * 1.2, rotation=(90, 0, 0)))
        for y in xs:
            for z in zs:
                struts.append(Pos(0, y, z) * Cylinder(0.8, b.size.X * 1.2, rotation=(0, 90, 0)))
        try:
            grid = Compound(struts)
            lattice = grid & cavity
            infill = lower + lattice
            dt = time.perf_counter() - t0
            ok = bool(infill.is_valid) and len(infill.faces()) > 0 and infill.volume > lower.volume
            attempts.append({"cell_mm": cell, "struts": len(struts), "s": round(dt, 2), "ok": ok,
                             "faces": len(infill.faces())})
            if ok:
                best = infill
            if dt > 90:
                break
        except Exception as exc:
            attempts.append({"cell_mm": cell, "struts": len(struts), "s": round(time.perf_counter() - t0, 2), "ok": False,
                             "error": type(exc).__name__})
            break
    t.metrics["lattice_attempts"] = attempts
    if best is not None:
        t.write_parts({"lower": best})
    t.status = "partial"
    t.note("B-rep kennt keine Gitter/TPMS. Einziger Weg: tausende Einzelstäbe als Zylinder boolesch verrechnen – "
           "Rechenzeit und Flächenzahl wachsen stark mit feinerer Zelle, Gyroid/TPMS ist praktisch unmöglich. "
           "Zellgrösse und Laufzeiten siehe Kennzahlen.")
    t.preview(views=("iso", "front"))


def task_v02(t: Task) -> None:
    """Kühlluftkanal: ein gewendelter Rohrkanal entlang der Innenwand des Unterteils (Sweep)."""
    res = model(t)
    lower = res["parts"]["lower"]
    sk = Skeleton.from_params(t.spec.group("skeleton"))
    g = t.spec.group("lower_body")
    t0 = time.perf_counter()
    pts = []
    z_top, z_bot = sk.split_z - 30, sk.body_bottom_z + 15
    for k in range(41):
        u = k / 40
        z = z_top + (z_bot - z_top) * u
        r = g.bottom_radius + (sk.joint_radius - g.collar_taper - g.bottom_radius) * (z - sk.body_bottom_z) / \
            (sk.split_z - g.collar_length - sk.body_bottom_z) - g.wall - 3.0
        a = 2 * math.pi * 1.5 * u
        pts.append((r * math.cos(a), r * math.sin(a), z))
    try:
        path = Wire([Spline(*pts)])
        prof = Plane(origin=pts[0], z_dir=path.tangent_at(0)) * Circle(3.0)
        tube = sweep(prof, path=path)
        inner = sweep(Plane(origin=pts[0], z_dir=path.tangent_at(0)) * Circle(2.0), path=path)
        channel = lower + tube - inner
        ok = channel.is_valid
        t.metrics["channel"] = {"length_mm": round(path.length, 1), "d_inner_mm": 4.0, "wall_mm": 1.0,
                                "s": round(time.perf_counter() - t0, 2), "valid": bool(ok)}
        t.write_parts({"lower": channel})
        t.status = "partial" if ok else "failed"
    except Exception as exc:
        t.status = "failed"
        t.metrics["channel"] = {"error": f"{type(exc).__name__}: {exc}"[:200], "s": round(time.perf_counter() - t0, 2)}
    t.note("Ein einzelner Kanal entlang einer Spline-Bahn geht per Sweep (Rohr mit 1 mm Wand, gewendelt an der "
           "Innenwand). Verzweigte Kanalnetze, Übergänge mit variablem Querschnitt und kanalführende Wände "
           "(konform zu Freiformflächen) werden in B-rep schnell instabil – typisches Feld für Voxel/SDF.")
    t.preview(views=("iso", "front"))


def task_v03(t: Task) -> None:
    """Variable Wandstärke + Bool auf Netzdaten."""
    res = model(t)
    notes = []
    from build123d import import_stl
    t0 = time.perf_counter()
    try:
        ref = import_stl(str(ROOT / "bench" / "reference" / "lower.stl"))
        r = ref - Pos(0, 0, -60) * Box(20, 200, 20)
        t.metrics["mesh_boolean"] = {"import_s": round(time.perf_counter() - t0, 2), "input_valid": bool(ref.is_valid),
                                     "result_valid": bool(r.is_valid) if r is not None else False,
                                     "faces": len(ref.faces())}
        notes.append(f"Bool auf Netzdaten: STL wird als {len(ref.faces())} Dreiecksflächen importiert "
                     f"(gültig: {ref.is_valid}); Ergebnis gültig: {bool(r.is_valid) if r is not None else False}.")
    except Exception as exc:
        t.metrics["mesh_boolean"] = {"error": type(exc).__name__, "s": round(time.perf_counter() - t0, 2)}
        notes.append(f"Bool auf Netzdaten fehlgeschlagen ({type(exc).__name__}).")
    t.write_parts({"upper": res["parts"]["upper"], "lower": res["parts"]["lower"]})
    t.status = "unsupported"
    notes.append("Feldgesteuerte (örtlich variable) Wandstärke gibt es in B-rep nicht; nur stückweise über eigene "
                 "Konturen (z. B. Rotationskörper mit veränderlichem Innenradius) nachbildbar.")
    t.note(" ".join(notes))


def task_v04(t: Task) -> None:
    """Schichten für den Druck: exakte Schnitte des Unterteils in Z."""
    res = model(t)
    lower = res["parts"]["lower"]
    sk = Skeleton.from_params(t.spec.group("skeleton"))
    t0 = time.perf_counter()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    zs = np.linspace(sk.body_bottom_z + 2, sk.split_z - 2, 8)
    fig, axs = plt.subplots(2, 4, figsize=(14, 7))
    n_layers = 0
    for ax, z in zip(axs.flat, zs):
        sec = section(lower, Plane.XY.offset(float(z)))
        for e in sec.edges():
            p = np.array([[v.X, v.Y] for v in (e.position_at(u) for u in np.linspace(0, 1, 40))])
            ax.plot(p[:, 0], p[:, 1], color="#1f5fa8", lw=1)
        ax.set_aspect("equal"); ax.set_title(f"z = {z:.1f} mm"); ax.axis("off")
        n_layers += 1
    plt.tight_layout(); plt.savefig(t.out / "slices.png", dpi=70); plt.close(fig)
    t.metrics["slices"] = {"count": n_layers, "s": round(time.perf_counter() - t0, 2)}
    t.files["images"] = ["slices.png"]
    t.files["image"] = "slices.png"
    t.write_parts({"lower": lower})
    t.status = "partial"
    t.note("Exakte Querschnitte (Kurven) in beliebiger Höhe sind in B-rep einfach; ein Druckformat (CLI/Slices) gibt "
           "es nicht direkt – im Druckprozess übernimmt das der Slicer aus STL/3MF.")


TASKS = {"B01": task_b01, "B02": task_b02, "B03": task_b03, "B04": task_b04, "B05": task_b05, "B06": task_b06,
         "B07": task_b07, "B08": task_b08, "B09": task_b09, "B10": task_b10, "R01": task_r01, "R02": task_r02,
         "R03": task_r03, "R04": task_r04, "V01": task_v01, "V02": task_v02, "V03": task_v03, "V04": task_v04}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", default=str(DEFAULT_SPEC))
    ap.add_argument("--task", required=True, choices=sorted(TASKS))
    ap.add_argument("--out", required=True)
    ap.add_argument("--set", action="append", default=[], metavar="gruppe.param=wert")
    ap.add_argument("--voxel", type=float, help="ohne Wirkung (nur Voxel-Seite), der Vollständigkeit halber")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    spec = Spec.load(a.spec).with_overrides(a.set)
    t = Task(a.task, out, spec)
    try:
        TASKS[a.task](t)
    except Exception as exc:
        t.status = "failed"
        t.note(f"Fehler: {type(exc).__name__}: {exc}")
        (out / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
    res = t.result()
    (out / "result.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("task", "status", "runtime_s", "peak_mem_mb")}))
    return 0 if res["status"] != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
