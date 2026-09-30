"""Selbsttest der Metriken gegen analytische Werte. Aufruf: python -m bench.test_metrics

Erzeugt Quader/Kugel/Zylinder mit build123d, exportiert als STL (wie ein echtes Tool) und
vergleicht Volumen, Flaeche, Schwerpunkt, Traegheit, Stirnflaeche, Abweichung, ICP.
Schreibt bench/results/metrics_selftest.json.
"""
from __future__ import annotations

import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

from bench import metrics as M

ROOT = Path(__file__).resolve().parent
RESULTS: list[dict] = []


def check(name: str, value: float, expected: float, rel_tol: float, unit: str = ""):
    err = abs(value - expected) / max(abs(expected), 1e-12)
    ok = err <= rel_tol
    RESULTS.append({"test": name, "value": value, "expected": expected, "rel_error": err,
                    "rel_tol": rel_tol, "unit": unit, "ok": bool(ok)})
    print(f"[{'OK ' if ok else 'FAIL'}] {name:52s} {value:14.4f} vs {expected:14.4f}  rel.Fehler {err:.2e} (Tol {rel_tol:.0e})")
    return ok


def main() -> int:
    from build123d import Box, Cylinder, Pos, Rot, Sphere, export_stl

    tmp = Path(tempfile.mkdtemp(prefix="bench_selftest_"))
    ok = True

    # ---------------- Quader 20 x 30 x 40 (exakt, 12 Dreiecke) mit Versatz
    a, b, c = 20.0, 30.0, 40.0
    box = Pos(100, -50, 200) * Box(a, b, c)
    p = tmp / "box.stl"
    export_stl(box, str(p))
    m = M.analyze_file(p)
    V = a * b * c
    ok &= check("Quader Volumen", m["volume_mm3"], V, 1e-6, "mm3")
    ok &= check("Quader Flaeche", m["area_mm2"], 2 * (a * b + b * c + a * c), 1e-6, "mm2")
    ok &= check("Quader Schwerpunkt X", m["centroid_mm"][0], 100.0, 1e-6)
    ok &= check("Quader Schwerpunkt Z", m["centroid_mm"][2], 200.0, 1e-6)
    I = np.array(m["inertia_tensor_mm5"])
    ok &= check("Quader Ixx (Schwerpunkt, rho=1)", I[0, 0], V * (b * b + c * c) / 12, 1e-6, "mm5")
    ok &= check("Quader Iyy", I[1, 1], V * (a * a + c * c) / 12, 1e-6, "mm5")
    ok &= check("Quader Izz", I[2, 2], V * (a * a + b * b) / 12, 1e-6, "mm5")
    ok &= abs(I[0, 1]) < 1e-3 * I[0, 0]
    ok &= bool(m["topology"]["watertight"]) and m["topology"]["closed_and_oriented"]
    print("       Topologie:", {k: m["topology"][k] for k in ("watertight", "open_edges", "non_manifold_edges", "components", "euler_characteristic")})
    fa_z = M.projected_area(M.read_stl(p), "z")
    fa_x = M.projected_area(M.read_stl(p), "x")
    ok &= check("Quader Stirnflaeche Z (a*b)", fa_z["area_mm2"], a * b, 5e-3, "mm2")
    ok &= check("Quader Stirnflaeche X (b*c)", fa_x["area_mm2"], b * c, 5e-3, "mm2")

    # ---------------- Kugel r = 25 (tesselliert, analytischer Wert mit Toleranz durch Facettierung)
    r = 25.0
    sph = Pos(10, 20, 30) * Sphere(r)
    p = tmp / "sphere.stl"
    export_stl(sph, str(p), tolerance=0.01, angular_tolerance=0.05)
    ts = M.read_stl(p)
    m = M.mesh_metrics(ts, p)
    ok &= check("Kugel Volumen", m["volume_mm3"], 4 / 3 * math.pi * r ** 3, 2e-3, "mm3")
    ok &= check("Kugel Flaeche", m["area_mm2"], 4 * math.pi * r * r, 2e-3, "mm2")
    I = np.array(m["inertia_tensor_mm5"])
    ok &= check("Kugel I (2/5 V r^2)", I[0, 0], 0.4 * 4 / 3 * math.pi * r ** 3 * r * r, 3e-3, "mm5")
    ok &= check("Kugel Schwerpunkt Y", m["centroid_mm"][1], 20.0, 1e-4)
    ok &= bool(m["topology"]["watertight"])
    for ax in "xyz":
        fa = M.projected_area(ts, ax)
        ok &= check(f"Kugel Stirnflaeche {ax.upper()} (pi r^2), Pixel {fa['pixel_mm']:.3f} mm", fa["area_mm2"], math.pi * r * r, 6e-3, "mm2")
    # Kugel gegen Kugel r+0.5: mittlere Abweichung 0.5
    sph2 = Pos(10, 20, 30) * Sphere(r + 0.5)
    p2 = tmp / "sphere2.stl"
    export_stl(sph2, str(p2), tolerance=0.01, angular_tolerance=0.05)
    dev = M.deviation(ts, M.read_stl(p2), n_query=50_000, n_index=200_000)
    ok &= check("Abweichung Kugel r=25 vs r=25.5 (Mittel a->b)", dev["a_to_b_mm"]["mean"], 0.5, 1e-2, "mm")
    ok &= check("Abweichung ... Mittel b->a", dev["b_to_a_mm"]["mean"], 0.5, 1e-2, "mm")
    ok &= check("Abweichung ... p95", dev["symmetric_p95_mm"], 0.5, 1.5e-2, "mm")

    # ---------------- Zylinder r=10 h=40
    rc, hc = 10.0, 40.0
    cyl = Cylinder(rc, hc)
    p = tmp / "cyl.stl"
    export_stl(cyl, str(p), tolerance=0.005, angular_tolerance=0.05)
    tc = M.read_stl(p)
    m = M.mesh_metrics(tc, p)
    Vc = math.pi * rc * rc * hc
    ok &= check("Zylinder Volumen", m["volume_mm3"], Vc, 1e-3, "mm3")
    ok &= check("Zylinder Flaeche", m["area_mm2"], 2 * math.pi * rc * (rc + hc), 1e-3, "mm2")
    I = np.array(m["inertia_tensor_mm5"])
    ok &= check("Zylinder Izz (V r^2/2)", I[2, 2], Vc * rc * rc / 2, 2e-3, "mm5")
    ok &= check("Zylinder Ixx (V(3r^2+h^2)/12)", I[0, 0], Vc * (3 * rc * rc + hc * hc) / 12, 2e-3, "mm5")
    ok &= check("Zylinder Stirnflaeche Z", M.projected_area(tc, "z")["area_mm2"], math.pi * rc * rc, 6e-3, "mm2")
    ok &= check("Zylinder Stirnflaeche X", M.projected_area(tc, "x")["area_mm2"], 2 * rc * hc, 6e-3, "mm2")

    # ---------------- Defekte Meshes muessen erkannt werden
    tb = M.read_stl(tmp / "box.stl")
    holed = tb[2:]  # zwei Dreiecke entfernt -> offen
    tp = M.topology(holed)
    RESULTS.append({"test": "offenes Mesh erkannt", "open_edges": tp["open_edges"], "ok": tp["open_edges"] > 0 and not tp["watertight"]})
    print("[%s] offenes Mesh erkannt: open_edges=%d watertight=%s" % ("OK " if tp["open_edges"] > 0 else "FAIL", tp["open_edges"], tp["watertight"]))
    ok &= tp["open_edges"] > 0 and not tp["watertight"]
    # nicht-mannigfaltig: dreifache Kante durch ein zusaetzliches Dreieck
    extra = np.concatenate([tb, np.array([[tb[0][0], tb[0][1], tb[0][0] + [0, 0, 7.0]]])])
    tp = M.topology(extra)
    RESULTS.append({"test": "nicht-mannigfaltige Kante erkannt", "non_manifold_edges": tp["non_manifold_edges"], "ok": tp["non_manifold_edges"] > 0})
    print("[%s] nicht-mannigfaltige Kante erkannt: %d" % ("OK " if tp["non_manifold_edges"] > 0 else "FAIL", tp["non_manifold_edges"]))
    ok &= tp["non_manifold_edges"] > 0
    # zwei getrennte Koerper
    two = np.concatenate([tb, tb + [500, 0, 0]])
    tp = M.topology(two)
    RESULTS.append({"test": "2 Komponenten", "components": tp["components"], "ok": tp["components"] == 2})
    print("[%s] Komponenten = %d (erwartet 2)" % ("OK " if tp["components"] == 2 else "FAIL", tp["components"]))
    ok &= tp["components"] == 2
    # ASCII-STL lesbar
    txt = tmp / "box_ascii.stl"
    with open(txt, "w") as fh:
        fh.write("solid t\n")
        for t in tb:
            fh.write("facet normal 0 0 0\n outer loop\n")
            for v in t:
                fh.write("  vertex %.6f %.6f %.6f\n" % tuple(v))
            fh.write(" endloop\nendfacet\n")
        fh.write("endsolid t\n")
    ok &= check("ASCII-STL Volumen", M.mesh_metrics(M.read_stl(txt))["volume_mm3"], V, 1e-6, "mm3")

    # ---------------- ICP: Zylinder mit Nase (asymmetrisch) um 3 Grad / 2 mm verschieben
    from build123d import Box as B2
    shape = Cylinder(10, 40) + Pos(12, 0, 8) * B2(10, 6, 12)
    p = tmp / "asym.stl"
    export_stl(shape, str(p), tolerance=0.01, angular_tolerance=0.05)
    ta = M.read_stl(p)
    ang = math.radians(3.0)
    Rz = np.array([[math.cos(ang), -math.sin(ang), 0], [math.sin(ang), math.cos(ang), 0], [0, 0, 1]])
    moved = M.apply_transform(ta, Rz, [2.0, -1.0, 0.5])
    res = M.icp(moved, ta, iters=60, trim=1.0)
    print("       ICP:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in res.items() if k != "R"})
    ok &= check("ICP Rueckdrehung Winkel", res["rotation_deg"], 3.0, 0.02, "deg")
    good = res["trimmed_rms_last_mm"] < 0.02
    RESULTS.append({"test": "ICP Restfehler < 0.02 mm", "value": res["trimmed_rms_last_mm"], "ok": bool(good)})
    print("[%s] ICP Restfehler %.4f mm (< 0.02)" % ("OK " if good else "FAIL", res["trimmed_rms_last_mm"]))
    ok &= good

    out = {"ok": bool(ok), "n_tests": len(RESULTS), "n_failed": sum(1 for r in RESULTS if not r["ok"]), "tests": RESULTS}
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "metrics_selftest.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("\nGESAMT:", "ALLE OK" if ok else "FEHLER", f"({out['n_failed']} fehlgeschlagen von {out['n_tests']})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
