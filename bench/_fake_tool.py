"""ATTRAPPE (FAKE) - nur zum Testen der Benchmark-Pipeline, KEIN echtes Ergebnis!

Haelt den CLI-Vertrag aus PLAN.md ein, baut aber nur das alte Oberteil aus boreas_upper.py.
  --mode brep   : STL direkt aus build123d (Unterteil fehlt -> status partial)
  --mode voxel  : "Voxel-Simulation": Vertices des Meshes werden auf das Voxelgitter --voxel gerundet
                  (nur um Pipeline, B07-Kurven und Report zu testen; kein echtes Voxelmodell)
Aufruf wie die echten CLIs:
  python -m bench._fake_tool --mode brep --spec bench/_fake_spec.json --task B02 --out DIR [--set g.p=v] [--voxel 0.5]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# gruppe.parameter -> Feld in boreas_upper.Params (nur die, die das alte Modell kennt)
FIELD = {
    "skeleton.arm_count": "arm_count", "upper_body.body_height": "body_height", "upper_body.wall": "wall",
    "arms.arm_width": "arm_width", "arms.arm_thickness": "arm_thickness", "motor_pods.pod_radius": "pod_radius",
    "motor_pods.pod_height": "pod_height", "nose.nose_length": "nose_length", "joints.fit_clearance": "fit_clearance",
    "details.edge_fillet": "edge_fillet",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="brep", choices=["brep", "voxel"])
    ap.add_argument("--spec")
    ap.add_argument("--task", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--voxel", type=float, default=None)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    res = {"task": a.task, "tool": a.mode, "tool_version": "FAKE (bench/_fake_tool.py, boreas_upper.py)",
           "status": "ok", "params": {"voxel_size_mm": a.voxel if a.mode == "voxel" else None, "overrides": {}},
           "metrics": {}, "files": {}, "code_loc": 0,
           "notes": "ATTRAPPE: nur altes Oberteil + Nase, kein Unterteil. Nur zum Test der Pipeline."}
    if a.task not in ("B01", "B02", "B03", "B07", "B10"):
        res.update(status="unsupported", runtime_s=0.0, notes="FAKE-Tool implementiert diese Aufgabe nicht.")
        (out / "result.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
        return 0

    import numpy as np
    from build123d import Compound, export_stl
    import boreas_upper as bu
    from bench import metrics as M

    p = bu.Params()
    for s in a.set:
        k, v = s.split("=", 1)
        res["params"]["overrides"][k] = float(v)
        if k in FIELD:
            setattr(p, FIELD[k], int(round(float(v))) if isinstance(getattr(p, FIELD[k]), int) else float(v))
    built = bu.build(p)["parts"]
    parts = {"upper": Compound(children=[built["Rumpf"], built["Gondeln"]]), "nose": built["Nasenkappe"]}
    files = {"parts": {}}
    tris = {}
    for name, shp in parts.items():
        f = out / f"{name}.stl"
        export_stl(shp, str(f), tolerance=0.05, angular_tolerance=0.2)
        t = M.read_stl(f)
        if a.mode == "voxel":
            s = a.voxel or 1.0
            t = np.round(t / s) * s
            time.sleep(0.02 / s)  # simuliert Skalierung der Laufzeit mit feiner werdendem Gitter
            M.write_stl(f, t)
        tris[name] = t
        files["parts"][name] = f.name
    allt = np.concatenate(list(tris.values()))
    M.write_stl(out / "model.stl", allt)
    files["mesh"] = "model.stl"
    mm = M.mesh_metrics(allt)
    res["metrics"] = {"volume_mm3": mm["volume_mm3"], "area_mm2": mm["area_mm2"], "bbox_mm": mm["bbox_mm"],
                      "parts": {n: {"volume_mm3": M.mass_properties(t)["volume_mm3"]} for n, t in tris.items()}}
    res["files"] = files
    res["status"] = "partial"
    res["runtime_s"] = round(time.perf_counter() - t0, 3)
    (out / "result.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
