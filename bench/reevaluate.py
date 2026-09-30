"""Auswertung eines Laufs neu rechnen, ohne die Werkzeuge erneut zu starten.

python -m bench.reevaluate bench/results/run1 [bench/results/latest]

Rechnet die Referenz-Abweichung (B01, B02, B07 inkl. Voxel-Sweep) und die Gruppen-Unabhängigkeit (B03) mit dem
aktuellen Code neu und schreibt danach Report und Diagramme neu. Nützlich, wenn sich Auswertungsregeln geändert haben.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from bench import metrics as M
from bench import reference as R
from bench.report import build_report
from bench.run_benchmark import EXPECTED_PARTS, REF_TASKS, load_parts


def _read(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _write(p: Path, d: dict) -> None:
    p.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")


def ref_dev(d: Path, res: dict) -> dict:
    _, parts = load_parts(d, res)
    return {n: R.compare_to_reference(t, n, do_icp=False) for n, t in parts.items() if n in ("upper", "lower", "nose")}


def reevaluate(run: Path) -> None:
    for task in sorted(REF_TASKS):
        for tool in ("brep", "voxel"):
            p = run / task / tool / "result.json"
            if not p.exists():
                continue
            res = _read(p)
            if res.get("status") in ("ok", "partial"):
                res.setdefault("neutral_metrics", {})["reference_deviation"] = ref_dev(p.parent, res)
                _write(p, res)
                print(task, tool, {k: round(v["offset_only"]["symmetric_mean_mm"], 3)
                                   for k, v in res["neutral_metrics"]["reference_deviation"].items()})
            for e in res.get("sweep", []):
                sp = p.parent / e["dir"] / "result.json"
                if sp.exists():
                    sr = _read(sp)
                    rd = ref_dev(sp.parent, sr)
                    sr.setdefault("neutral_metrics", {})["reference_deviation"] = rd
                    _write(sp, sr)
                    e["reference_deviation"] = {k: {"mean_mm": v["offset_only"]["symmetric_mean_mm"],
                                                    "p95_mm": v["offset_only"]["symmetric_p95_mm"],
                                                    "max_mm": v["offset_only"]["hausdorff_mm"]} for k, v in rd.items()}
            if res.get("sweep"):
                _write(p, res)
    for tool in ("brep", "voxel"):
        p = run / "B03" / tool / "result.json"
        if not p.exists():
            continue
        res = _read(p)
        for v in res.get("variations", []):
            exp = EXPECTED_PARTS.get(v["group"], ["upper", "lower", "nose"])
            v["expected_parts"] = exp
            v["unexpected_changes"] = [c for c in v.get("changed_parts", []) if c not in exp]
            v["independent"] = len(v["unexpected_changes"]) == 0
        gi = res.setdefault("neutral_metrics", {}).setdefault("group_independence", {})
        gi["expected_parts_assumption"] = EXPECTED_PARTS
        gi["groups_tested"] = sum(1 for v in res.get("variations", []) if v.get("independent") is not None)
        gi["groups_independent"] = sum(1 for v in res.get("variations", []) if v.get("independent"))
        _write(p, res)
        print("B03", tool, gi["groups_independent"], "/", gi["groups_tested"])
    build_report(run)


if __name__ == "__main__":
    for arg in sys.argv[1:] or ["bench/results/latest"]:
        print("==", arg)
        reevaluate(Path(arg))
