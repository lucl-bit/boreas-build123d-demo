"""Benchmark-Runner B-rep (build123d) vs. Voxel (PicoGK).

Aufruf (im Repo-Root):
    python -m bench.run_benchmark [--tools brep,voxel] [--tasks B01,B02,...|all]
                                  [--voxel-sizes 2.0,1.0,0.5,0.25] [--run-id ID] [--timeout 1800]
                                  [--tool-cmd brep="python -m bench._fake_tool --mode brep"] ...

Ablauf je Aufgabe und Werkzeug: CLI im Subprozess (Timeout, Wandzeit, Spitzen-RAM des Prozessbaums, Logs)
-> result.json des Tools einlesen -> werkzeugneutrale Metriken aus den STL-Dateien -> erweitertes
result.json nach bench/results/<run_id>/<task>/<tool>/. Sonderlaeufe: B03 (Gruppenvariation),
B07 (Voxelgroessen-Sweep), B10 (Wiederholungen). Danach Report und Kopie nach bench/results/latest/.
Nicht vorhandene CLIs werden als status "not_run" mit Grund festgehalten.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import math
import os
import platform
import re
import shlex
import shutil
import statistics
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np

from bench import metrics as M
from bench.procmeasure import run_measured

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "bench" / "results"

TASK_TITLES = {
    "B01": "Referenz importieren und abgleichen", "B02": "Parametrisches Gesamtmodell",
    "B03": "Gruppen-Variation", "B04": "Tropfenprofil (Fins, Gondeln)", "B05": "Wandstaerke / Schale",
    "B06": "Uebergaenge / Verrundungen", "B07": "Masseneigenschaften und Genauigkeit", "B08": "Mesh-Export und Druckbarkeit",
    "B09": "Aero-Vorbereitung", "B10": "Performance und Skalierung",
    "V01": "Gitter-Infill (Lattice)", "V02": "Konforme Kuehlluftkanaele", "V03": "Mesh-Booleans, Feld-Wandstaerke", "V04": "Slices fuer den Druck",
    "R01": "Bemasste technische Zeichnung", "R02": "STEP-Export, Kanten-/Flaechen-Selektoren", "R03": "Constraints, Skelett, Joints, URDF",
    "R04": "Exakte Masse, Toleranzen, Passungen",
}
SECTION_OF = {"B": "common", "V": "voxel_only", "R": "brep_only"}
ALL_TASKS = list(TASK_TITLES)
# Aufgaben, bei denen das Ergebnis mit der Referenz-Geometrie (STEP) verglichen wird (Ganzmodell)
REF_TASKS = {"B01", "B02", "B07"}
# Annahme, welche Teile sich bei einer Gruppenaenderung aendern duerfen (fuer die Unabhaengigkeitspruefung B03)
EXPECTED_PARTS = {
    # laut docs/geometrie_definition.md Kap. 1: Fins sitzen am Oberteil, die Gruppe nose baut auch den Einsatz,
    # arms baut Stege (Oberteil) und Kiele (Unterteil)
    "skeleton": ["upper", "lower", "nose", "nose_insert"], "upper_body": ["upper"], "arms": ["upper", "lower"],
    "motor_pods": ["upper"], "lower_body": ["lower"], "body_fins": ["upper"], "tail_fins": ["lower"],
    "nose": ["nose", "nose_insert"], "joints": ["upper", "lower", "nose"], "details": ["upper", "lower"],
}


# --------------------------------------------------------------------------- Hilfsfunktionen

def clean(o):
    """JSON-tauglich machen: numpy -> Python, NaN/inf -> None."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if math.isfinite(f) else None
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(obj), indent=1, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def find_dotnet() -> str | None:
    d = shutil.which("dotnet")
    if d:
        return d
    for c in (r"C:\Program Files\dotnet\dotnet.exe", r"C:\Program Files (x86)\dotnet\dotnet.exe"):
        if os.path.exists(c):
            return c
    return None


def split_cmd(s: str) -> list[str]:
    parts = shlex.split(s, posix=(os.name != "nt"))
    parts = [p[1:-1] if len(p) > 1 and p[0] == p[-1] and p[0] in "\"'" else p for p in parts]
    if parts and parts[0].lower() in ("python", "python3", "py"):
        parts[0] = sys.executable
    return parts


class Ctx:
    """Laufkontext: Argumente, Ordner, Werkzeug-Kommandos."""

    def __init__(self, args):
        self.args = args
        self.run_id = args.run_id
        self.run_dir = RESULTS / self.run_id
        self.spec = args.spec
        self.timeout = args.timeout
        self.tool_cmd: dict[str, list[str]] = {}
        for item in args.tool_cmd or []:
            k, v = item.split("=", 1)
            self.tool_cmd[k.strip()] = split_cmd(v)
        self.overridden = bool(self.tool_cmd)
        self.voxel_build: dict | None = None
        self.notes: list[str] = []

    # -- Werkzeug-Verfuegbarkeit ---------------------------------------------------------------
    def availability(self, tool: str) -> tuple[bool, str, list[str]]:
        if tool in self.tool_cmd:
            return True, "Kommando per --tool-cmd ueberschrieben", self.tool_cmd[tool]
        if tool == "brep":
            if not (ROOT / "brep" / "cli.py").exists():
                return False, "brep/cli.py existiert (noch) nicht", []
            return True, "", [sys.executable, "-m", "brep.cli"]
        if tool == "voxel":
            dn = find_dotnet()
            if not (ROOT / "voxel").exists() or not list((ROOT / "voxel").glob("*.csproj")):
                return False, "voxel/*.csproj existiert (noch) nicht", []
            if not dn:
                return False, "dotnet ist nicht installiert (weder im PATH noch unter C:\\Program Files\\dotnet)", []
            if self.voxel_build is None:
                self.voxel_build = self._build_voxel(dn)
            if not self.voxel_build["ok"]:
                return False, "dotnet build fehlgeschlagen (siehe run_meta.json / build_voxel.log)", []
            return True, "", [dn, "run", "--project", "voxel", "-c", "Release", "--no-build", "--"]
        return False, f"unbekanntes Werkzeug {tool}", []

    def _build_voxel(self, dn: str) -> dict:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        log("dotnet build voxel -c Release ...")
        r = run_measured([dn, "build", "voxel", "-c", "Release"], str(ROOT), 1800,
                         self.run_dir / "build_voxel.stdout.log", self.run_dir / "build_voxel.stderr.log")
        r["ok"] = r.get("exit_code") == 0
        r["note"] = "Build einmalig vorab; Laeufe danach mit --no-build (Laufzeit ohne Compile)."
        return r


# --------------------------------------------------------------------------- Werkzeugaufruf

def build_args(ctx: Ctx, task: str, out_dir: Path, sets=(), voxel=None) -> list[str]:
    a = ["--spec", ctx.spec, "--task", task, "--out", str(out_dir)]
    for s in sets:
        a += ["--set", s]
    if voxel is not None:
        a += ["--voxel", str(voxel)]
    return a


def not_run_result(task: str, tool: str, out_dir: Path, reason: str) -> dict:
    res = {"task": task, "tool": tool, "status": "not_run", "notes": reason,
           "runner": {"status": "not_run", "reason": reason}}
    write_json(out_dir / "result.json", res)
    return res


def run_tool(ctx: Ctx, tool: str, task: str, out_dir: Path, sets=(), voxel=None, timeout=None) -> dict:
    """Ein Aufruf des Tool-CLIs mit Messung. Rueckgabe: result-Dict (Tool-Ergebnis + runner-Block, noch ohne neutral)."""
    ok, why, base = ctx.availability(tool)
    if out_dir.exists():
        shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not ok:
        return not_run_result(task, tool, out_dir, why)
    cmd = base + build_args(ctx, task, out_dir, sets, voxel)
    r = run_measured(cmd, str(ROOT), timeout or ctx.timeout, out_dir / "stdout.log", out_dir / "stderr.log")
    runner = {
        "status": None, "wall_s": r.get("wall_s"), "peak_ram_mb": r.get("peak_ram_mb"),
        "peak_ram_root_mb": r.get("peak_ram_root_mb"), "peak_ram_max_child_mb": r.get("peak_ram_max_child_mb"),
        "ram_method": r.get("ram_method"), "exit_code": r.get("exit_code"), "timed_out": r.get("timed_out"),
        "cmd": [str(c) for c in cmd], "stdout_log": "stdout.log", "stderr_log": "stderr.log",
        "started": dt.datetime.now().isoformat(timespec="seconds"),
    }
    if r.get("error"):
        runner["error"] = r["error"]
    rj = out_dir / "result.json"
    res: dict
    if rj.exists():
        try:
            res = read_json(rj)
            shutil.copyfile(rj, out_dir / "result_raw.json")
        except Exception as e:
            res = {"task": task, "tool": tool, "status": "failed", "notes": f"result.json unlesbar: {e}"}
    else:
        tail = ""
        try:
            tail = (out_dir / "stderr.log").read_text(errors="ignore")[-600:]
        except Exception:
            pass
        res = {"task": task, "tool": tool, "status": "failed",
               "notes": "Kein result.json geschrieben (Exit-Code %s%s). stderr-Ende: %s" % (
                   r.get("exit_code"), ", Timeout" if r.get("timed_out") else "", tail.strip()[-400:])}
    runner["status"] = "timeout" if r.get("timed_out") else ("ok" if r.get("exit_code") == 0 else "exit_nonzero")
    if runner["status"] == "exit_nonzero" and res.get("status") in (None, "ok"):
        res["status"] = "failed"
        res["notes"] = (res.get("notes") or "") + f" [Runner: Exit-Code {r.get('exit_code')}]"
    if runner["status"] == "timeout":
        res["status"] = "failed"
    res["runner"] = runner
    res.setdefault("task", task)
    res.setdefault("tool", tool)
    return res


# --------------------------------------------------------------------------- Neutrale Metriken

def load_parts(out_dir: Path, res: dict) -> tuple[np.ndarray | None, dict[str, np.ndarray]]:
    files = res.get("files") or {}
    mesh = None
    parts: dict[str, np.ndarray] = {}
    mp = files.get("mesh")
    if mp and (out_dir / mp).exists():
        mesh = M.read_stl(out_dir / mp)
    for name, rel in (files.get("parts") or {}).items():
        if isinstance(rel, str) and rel.lower().endswith(".stl") and (out_dir / rel).exists():
            parts[name] = M.read_stl(out_dir / rel)
    if mesh is None and parts:
        mesh = np.concatenate(list(parts.values()))
    return mesh, parts


def neutral_metrics(out_dir: Path, res: dict, ref_compare: bool = False, icp: bool = True,
                    frontal: bool = True) -> dict:
    """Werkzeugneutrale Metriken aus den STL-Dateien des Tool-Ergebnisses."""
    t0 = time.time()
    nm: dict = {"errors": []}
    try:
        mesh, parts = load_parts(out_dir, res)
    except Exception as e:
        nm["errors"].append(f"STL lesen: {e}")
        return nm
    if mesh is None:
        nm["note"] = "keine STL-Ausgabe"
        return nm
    files = res.get("files") or {}
    try:
        m = M.mesh_metrics(mesh, out_dir / files["mesh"] if files.get("mesh") else None)
        if frontal:
            m["frontal_area_z"] = M.projected_area(mesh, "z")
            m["frontal_area_x"] = M.projected_area(mesh, "x")
        if not files.get("mesh"):
            m["note"] = "Gesamt-Mesh aus Teilen zusammengesetzt (Volumen/Topologie nur eingeschraenkt aussagekraeftig)"
        nm["mesh"] = m
    except Exception as e:
        nm["errors"].append(f"mesh_metrics: {e}\n{traceback.format_exc(limit=2)}")
    nm["parts"] = {}
    for name, t in parts.items():
        try:
            pm = M.mesh_metrics(t, out_dir / files["parts"][name])
            nm["parts"][name] = pm
        except Exception as e:
            nm["errors"].append(f"parts.{name}: {e}")
    # Selbstauskunft vs. neutral
    try:
        rep = res.get("metrics") or {}
        chk = {}
        for k, nk in (("volume_mm3", "volume_mm3"), ("area_mm2", "area_mm2")):
            if rep.get(k) is not None and nm.get("mesh", {}).get(nk):
                chk[k] = {"reported": rep[k], "neutral": nm["mesh"][nk],
                          "rel_diff": (nm["mesh"][nk] - rep[k]) / rep[k] if rep[k] else None}
        if rep.get("bbox_mm") and nm.get("mesh", {}).get("bbox_mm"):
            chk["bbox_mm_max_abs_diff"] = float(np.max(np.abs(np.array(rep["bbox_mm"]) - np.array(nm["mesh"]["bbox_mm"])))) \
                if len(rep["bbox_mm"]) == 6 else None
        nm["self_report_check"] = chk
    except Exception as e:
        nm["errors"].append(f"self_report_check: {e}")
    # Koordinatensystem-Plausibilitaet
    bb = nm.get("mesh", {}).get("bbox_mm")
    if bb:
        cx, cy = (bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2
        if abs(cx) > 150 or abs(cy) > 150:
            nm["frame_warning"] = f"Mesh-Mitte XY=({cx:.0f},{cy:.0f}) mm weicht stark vom PLAN.md-Ursprung ab (Achse=0) - Datei-KS?"
    if ref_compare and parts:
        try:
            from bench import reference as R
            nm["reference_deviation"] = {}
            for name, t in parts.items():
                if name in ("upper", "lower", "nose"):
                    nm["reference_deviation"][name] = R.compare_to_reference(t, name, do_icp=icp)
        except Exception as e:
            nm["errors"].append(f"reference_deviation: {e}\n{traceback.format_exc(limit=3)}")
    nm["neutral_seconds"] = round(time.time() - t0, 2)
    if not nm["errors"]:
        del nm["errors"]
    return nm


def finalize(out_dir: Path, res: dict, task: str, ref_compare: bool = False, icp: bool = True) -> dict:
    if res.get("status") not in ("not_run",):
        try:
            res["neutral_metrics"] = neutral_metrics(out_dir, res, ref_compare=ref_compare, icp=icp)
        except Exception as e:
            res["neutral_metrics"] = {"errors": [f"{e}\n{traceback.format_exc(limit=3)}"]}
    write_json(out_dir / "result.json", res)
    return res


def brief(res: dict) -> str:
    r = res.get("runner", {})
    if res.get("status") == "not_run":
        return "not_run: " + str(r.get("reason"))
    return "%s wall=%ss ram=%sMB" % (res.get("status"), r.get("wall_s"), r.get("peak_ram_mb"))


# --------------------------------------------------------------------------- Standardaufgabe

def run_standard(ctx: Ctx, tool: str, task: str, voxel=None) -> dict:
    out = ctx.run_dir / task / tool
    log(f"{task} / {tool} ...")
    res = run_tool(ctx, tool, task, out, voxel=voxel)
    finalize(out, res, task, ref_compare=(task in REF_TASKS), icp=True)
    log(f"   -> {brief(res)}")
    return res


# --------------------------------------------------------------------------- B03 Gruppenvariation

def load_spec(ctx: Ctx):
    p = Path(ctx.spec)
    if not p.is_absolute():
        p = ROOT / p
    if not p.exists():
        return None
    return read_json(p)


def pick_variation(group: dict) -> tuple[str, float, float] | None:
    """(param, alter Wert, neuer Wert): erster numerischer Parameter, Mittelwert von min/max (auf step gerundet)."""
    for name, p in (group.get("params") or {}).items():
        try:
            lo, hi, v0 = float(p["min"]), float(p["max"]), float(p["value"])
        except (KeyError, TypeError, ValueError):
            continue
        if hi <= lo:
            continue
        step = float(p.get("step") or 0) or None
        new = (lo + hi) / 2.0
        if abs(new - v0) < 1e-9 or abs(new - v0) < 0.05 * (hi - lo):
            new = v0 + (hi - v0) * 0.5 if hi - v0 >= v0 - lo else v0 - (v0 - lo) * 0.5
        if step:
            new = lo + round((new - lo) / step) * step
        new = min(max(new, lo), hi)
        if isinstance(p.get("value"), int) and (step or 1) >= 1:
            new = int(round(new))
        if abs(new - v0) < 1e-12:
            new = hi if abs(hi - v0) > abs(lo - v0) else lo
        return name, v0, float(new)
    return None


def run_b03(ctx: Ctx, tool: str) -> dict:
    task = "B03"
    root_out = ctx.run_dir / task / tool
    ok, why, _ = ctx.availability(tool)
    if not ok:
        return not_run_result(task, tool, root_out, why)
    spec = load_spec(ctx)
    if spec is None:
        return not_run_result(task, tool, root_out, f"Spec {ctx.spec} nicht gefunden - Gruppenvariation nicht moeglich")
    log(f"B03 / {tool}: Baseline + {len(spec['groups'])} Gruppen")
    base_dir = root_out / "baseline"
    base = run_tool(ctx, tool, task, base_dir)
    finalize(base_dir, base, task, ref_compare=False)
    log(f"   baseline -> {brief(base)}")
    _, bparts = load_parts(base_dir, base) if base.get("status") not in ("not_run", "failed", "unsupported") else (None, {})
    variations = []
    for g, gd in spec["groups"].items():
        pv = pick_variation(gd)
        if pv is None:
            variations.append({"group": g, "status": "skipped", "reason": "kein numerischer Parameter mit min/max"})
            continue
        pname, v0, v1 = pv
        setstr = f"{g}.{pname}={v1:g}"
        vdir = root_out / f"var_{g}"
        vr = run_tool(ctx, tool, task, vdir, sets=[setstr])
        _, vparts = load_parts(vdir, vr) if vr.get("status") not in ("not_run", "failed", "unsupported") else (None, {})
        entry = {"group": g, "label": gd.get("label"), "param": f"{g}.{pname}", "baseline_value": v0, "new_value": v1,
                 "override": setstr, "status": vr.get("status"), "dir": f"var_{g}",
                 "wall_s": vr["runner"].get("wall_s"), "runtime_s_reported": vr.get("runtime_s"),
                 "peak_ram_mb": vr["runner"].get("peak_ram_mb"), "parts": {}}
        changed = []
        for pn in sorted(set(bparts) | set(vparts)):
            if pn in bparts and pn in vparts:
                d = M.meshes_differ(bparts[pn], vparts[pn])
            else:
                d = {"changed": True, "reason": "Teil fehlt in einem der Laeufe"}
            entry["parts"][pn] = d
            if d.get("changed"):
                changed.append(pn)
        exp = EXPECTED_PARTS.get(g, ["upper", "lower", "nose"])
        entry["changed_parts"] = changed
        entry["expected_parts"] = exp
        entry["unexpected_changes"] = [c for c in changed if c not in exp]
        entry["independent"] = (len(entry["unexpected_changes"]) == 0) if bparts and vparts else None
        # Nicht betroffene Teile bitgleich?
        entry["untouched_identical"] = all(entry["parts"][p].get("identical") for p in entry["parts"] if p not in changed) \
            if bparts and vparts else None
        variations.append(entry)
        log(f"   {g}: {setstr} -> {vr.get('status')} wall={entry['wall_s']}s geaendert={changed}")
        finalize(vdir, vr, task)
    walls = [v["wall_s"] for v in variations if v.get("wall_s")]
    res = {
        "task": task, "tool": tool, "tool_version": base.get("tool_version"),
        "status": base.get("status") if base.get("status") in ("failed", "unsupported", "not_run") else
        ("ok" if all(v.get("status") in ("ok", "partial", "skipped") for v in variations) else "partial"),
        "params": base.get("params"), "notes": (base.get("notes") or ""),
        "files": {"baseline": "baseline/result.json"},
        "metrics": {"baseline_wall_s": base["runner"].get("wall_s"),
                    "mean_regen_wall_s": statistics.mean(walls) if walls else None,
                    "max_regen_wall_s": max(walls) if walls else None},
        "variations": variations,
        "runner": {"status": "ok", "wall_s": round(statistics.mean(walls), 3) if walls else None,
                   "wall_s_meaning": "Mittelwert der Regenerationszeit je Gruppenvariation", "total_wall_s": round(sum(walls) + (base["runner"].get("wall_s") or 0), 3),
                   "peak_ram_mb": max([base["runner"].get("peak_ram_mb") or 0] + [v.get("peak_ram_mb") or 0 for v in variations]) or None},
        "neutral_metrics": {"group_independence": {
            "expected_parts_assumption": EXPECTED_PARTS,
            "note": "Geaendert = Hausdorff-Naeherung > 0.02 mm oder Volumen > 1e-4 relativ. 'expected' ist eine Annahme aus dem Gruppenschluessel.",
            "groups_tested": sum(1 for v in variations if v.get("independent") is not None),
            "groups_independent": sum(1 for v in variations if v.get("independent") is True),
        }},
    }
    write_json(root_out / "result.json", res)
    return res


# --------------------------------------------------------------------------- B07 Voxel-Sweep

def _find_brep_meshes(ctx: Ctx):
    """Sucht das B-rep-Modell (B07/B02) im aktuellen Lauf, sonst in latest, fuer die Genauigkeits-Kurve."""
    for base in (ctx.run_dir, RESULTS / "latest"):
        for t in ("B07", "B02"):
            d = base / t / "brep"
            rj = d / "result.json"
            if rj.exists():
                try:
                    r = read_json(rj)
                    if r.get("status") in ("ok", "partial"):
                        mesh, parts = load_parts(d, r)
                        if mesh is not None:
                            return r, mesh, parts, str(d)
                except Exception:
                    continue
    return None, None, {}, None


def run_b07(ctx: Ctx, tool: str) -> dict:
    task = "B07"
    root_out = ctx.run_dir / task / tool
    if tool != "voxel":
        return run_standard(ctx, tool, task)
    ok, why, _ = ctx.availability(tool)
    if not ok:
        return not_run_result(task, tool, root_out, why)
    sizes = [float(s) for s in ctx.args.voxel_sizes.split(",") if s.strip()]
    brep_res, brep_mesh, brep_parts, brep_src = _find_brep_meshes(ctx)
    idx_brep = M.SurfaceIndex(brep_mesh, 500_000) if brep_mesh is not None else None
    log(f"B07 / voxel: Sweep {sizes} (Vergleichsmodell: {brep_src})")
    base = run_standard(ctx, tool, task)  # Standard-Voxelgroesse des Tools
    sweep = []
    for s in sizes:
        d = root_out / "sweep" / f"v{s:g}"
        log(f"   B07 voxel {s} mm ...")
        r = run_tool(ctx, tool, task, d, voxel=s)
        r = finalize(d, r, task, ref_compare=True, icp=False)
        entry = {"voxel_mm": s, "dir": f"sweep/v{s:g}", "status": r.get("status"),
                 "wall_s": r["runner"].get("wall_s"), "peak_ram_mb": r["runner"].get("peak_ram_mb"),
                 "runtime_s_reported": r.get("runtime_s")}
        nm = r.get("neutral_metrics", {})
        mm = nm.get("mesh", {})
        entry.update({"triangles": mm.get("triangles"), "file_size_bytes": mm.get("file_size_bytes"),
                      "volume_mm3": mm.get("volume_mm3"), "area_mm2": mm.get("area_mm2"),
                      "watertight": (mm.get("topology") or {}).get("watertight"),
                      "frontal_area_z_mm2": (mm.get("frontal_area_z") or {}).get("area_mm2"),
                      "frontal_area_x_mm2": (mm.get("frontal_area_x") or {}).get("area_mm2")})
        entry["reference_deviation"] = {p: {"mean_mm": (v.get("offset_only") or {}).get("symmetric_mean_mm"),
                                            "p95_mm": (v.get("offset_only") or {}).get("symmetric_p95_mm"),
                                            "max_mm": (v.get("offset_only") or {}).get("hausdorff_mm")}
                                        for p, v in (nm.get("reference_deviation") or {}).items()}
        if idx_brep is not None and r.get("status") in ("ok", "partial"):
            try:
                mesh, _ = load_parts(d, r)[0], None
                dev = M.deviation(mesh, brep_mesh, n_query=100_000, n_index=500_000, index_b=idx_brep)
                bm = M.mesh_metrics(brep_mesh)
                Ib, Iv = np.array(bm["inertia_tensor_mm5"]), np.array(mm["inertia_tensor_mm5"])
                entry["vs_brep_inertia_rel_err"] = float(np.linalg.norm(Iv - Ib) / np.linalg.norm(Ib))
                entry["vs_brep"] = {
                    "source": brep_src,
                    "volume_rel_err": (mm.get("volume_mm3") - bm["volume_mm3"]) / bm["volume_mm3"] if mm.get("volume_mm3") else None,
                    "area_rel_err": (mm.get("area_mm2") - bm["area_mm2"]) / bm["area_mm2"] if mm.get("area_mm2") else None,
                    "centroid_shift_mm": float(np.linalg.norm(np.array(mm["centroid_mm"]) - np.array(bm["centroid_mm"]))) if mm.get("centroid_mm") else None,
                    "mean_mm": dev["symmetric_mean_mm"], "p95_mm": dev["symmetric_p95_mm"], "max_mm": dev["hausdorff_mm"],
                }
            except Exception as e:
                entry["vs_brep_error"] = str(e)
        sweep.append(entry)
        log(f"      -> {brief(r)} tri={entry['triangles']}")
    base["sweep"] = sweep
    # Konvergenzordnung: Steigung log(mittlere Abweichung) ueber log(Voxelgroesse)
    pts = [(math.log(e["voxel_mm"]), math.log(e["vs_brep"]["mean_mm"])) for e in sweep
           if (e.get("vs_brep") or {}).get("mean_mm") and e["vs_brep"]["mean_mm"] > 0]
    if len(pts) >= 3:
        x, y = np.array(pts).T
        base["sweep_convergence_order_mean_dev"] = float(np.polyfit(x, y, 1)[0])
    pv = [(math.log(e["voxel_mm"]), math.log(abs(e["vs_brep"]["volume_rel_err"]))) for e in sweep
          if (e.get("vs_brep") or {}).get("volume_rel_err")]
    if len(pv) >= 3:
        x, y = np.array(pv).T
        base["sweep_convergence_order_volume_err"] = float(np.polyfit(x, y, 1)[0])
    base["sweep_note"] = ("Genauigkeit relativ zum B-rep-Modell desselben Laufs (vs_brep) und zur STEP-Referenz (reference_deviation, nur Offset). "
                          "Das B-rep-Volumen ist ein exakter OCC-Wert, das Voxel-Volumen kommt aus dem Mesh.")
    write_json(root_out / "result.json", base)
    return base


# --------------------------------------------------------------------------- B10 Wiederholungen

def run_b10(ctx: Ctx, tool: str) -> dict:
    task = "B10"
    out = ctx.run_dir / task / tool
    n = max(1, ctx.args.repeats)
    log(f"B10 / {tool}: {n} Wiederholungen")
    walls, rams, reps = [], [], []
    res = None
    for i in range(n):
        res = run_tool(ctx, tool, task, out)
        if res.get("status") in ("not_run", "unsupported", "failed"):
            break
        walls.append(res["runner"]["wall_s"])
        if res["runner"].get("peak_ram_mb"):
            rams.append(res["runner"]["peak_ram_mb"])
        reps.append(res.get("runtime_s"))
    if res is None:
        return {}
    finalize(out, res, task)
    if walls:
        res["runner"]["repeats"] = {"n": len(walls), "wall_s": walls, "wall_median_s": statistics.median(walls),
                                    "wall_min_s": min(walls), "wall_max_s": max(walls), "peak_ram_mb": rams,
                                    "runtime_s_reported": reps,
                                    "note": "Wiederholung 1 = kalt (Import/JIT), weitere = warm; jeweils frischer Prozess."}
        write_json(out / "result.json", res)
    log(f"   -> {brief(res)}")
    if res.get("status") in ("ok", "partial") and not ctx.args.no_b10_scaling:
        res["scaling"] = b10_scaling(ctx, tool, out)
        write_json(out / "result.json", res)
    return res


def b10_scaling(ctx: Ctx, tool: str, out: Path) -> list[dict]:
    """Skalierung nach benchmark_tasks.json/B10: B02 mit Armzahl 3/4/6/8, Fillets aus, Voxel: Groessen des Sweeps."""
    spec = load_spec(ctx) or {}
    groups = spec.get("groups", {})
    steps: list[tuple[str, list[str], float | None]] = []
    if "arm_count" in (groups.get("skeleton", {}).get("params") or {}):
        steps += [(f"arms{n}", [f"skeleton.arm_count={n}"], None) for n in (3, 4, 6, 8)]
    fil = [k for k, v in (groups.get("details", {}).get("params") or {}).items() if "fillet" in k and float(v.get("min", 0)) <= 0]
    if fil:
        steps.append(("no_fillets", [f"details.{k}=0" for k in fil], None))
    if tool == "voxel":
        steps += [(f"voxel{float(x):g}", [], float(x)) for x in ctx.args.voxel_sizes.split(",") if x.strip()]
    rows = []
    for label, sets, vox in steps:
        d = out / f"scale_{label}"
        log(f"   B10 Skalierung {label} ...")
        r = run_tool(ctx, tool, "B02", d, sets=sets, voxel=vox)
        try:
            nm = neutral_metrics(d, r, frontal=False) if r.get("status") in ("ok", "partial") else {}
        except Exception as e:
            nm = {"errors": [str(e)]}
        r["neutral_metrics"] = nm
        write_json(d / "result.json", r)
        mm = nm.get("mesh", {})
        rows.append({"label": label, "sets": sets, "voxel_mm": vox, "status": r.get("status"), "dir": f"scale_{label}",
                     "wall_s": r["runner"].get("wall_s"), "peak_ram_mb": r["runner"].get("peak_ram_mb"),
                     "triangles": mm.get("triangles"), "file_size_bytes": mm.get("file_size_bytes"),
                     "step_size_bytes": _step_size(d, r), "watertight": (mm.get("topology") or {}).get("watertight")})
    return rows


def _step_size(d: Path, r: dict):
    st = (r.get("files") or {}).get("step")
    return (d / st).stat().st_size if st and (d / st).exists() else None


# --------------------------------------------------------------------------- Hauptprogramm

def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Boreas-Benchmark B-rep vs. Voxel")
    ap.add_argument("--tools", default="brep,voxel")
    ap.add_argument("--tasks", default="all", help="B01,B02,... oder all (B*, V*, R*)")
    ap.add_argument("--voxel-sizes", default="2.0,1.0,0.5,0.25", help="Sweep fuer B07 und B10-Skalierung Voxel (mm)")
    ap.add_argument("--voxel-default", type=float, default=None, help="Voxelgroesse fuer alle Nicht-B07-Aufgaben (sonst Tool-Standard)")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--spec", default="spec/boreas_spec.json")
    ap.add_argument("--timeout", type=float, default=1800.0, help="Sekunden je Tool-Aufruf")
    ap.add_argument("--repeats", type=int, default=3, help="Wiederholungen fuer B10")
    ap.add_argument("--tool-cmd", action="append", metavar='NAME="CMD"',
                    help='Kommando eines Tools ueberschreiben, z. B. brep="python -m bench._fake_tool --mode brep"; '
                         "Standard-Argumente (--spec --task --out ...) werden angehaengt. Solche Laeufe aktualisieren 'latest' nicht.")
    ap.add_argument("--update-latest", action="store_true", help="latest auch bei --tool-cmd-Lauf ueberschreiben")
    ap.add_argument("--no-b10-scaling", action="store_true", help="B10: nur die Wiederholungen, keine Skalierungsstufen (Armzahl, Fillets, Voxelgroesse)")
    ap.add_argument("--no-latest", action="store_true")
    ap.add_argument("--no-report", action="store_true")
    a = ap.parse_args(argv)
    if not a.run_id:
        a.run_id = ("fake_" if a.tool_cmd else "") + time.strftime("%Y%m%d_%H%M%S")
    return a


def expand_tasks(s: str) -> list[str]:
    if s.strip().lower() == "all":
        return ALL_TASKS
    out = [t.strip().upper() for t in s.split(",") if t.strip()]
    bad = [t for t in out if t not in TASK_TITLES]
    if bad:
        raise SystemExit(f"Unbekannte Aufgaben: {bad}")
    return out


def load_task_titles():
    p = ROOT / "spec" / "benchmark_tasks.json"
    if not p.exists():
        return
    try:
        d = read_json(p)
        items = d.get("tasks", d) if isinstance(d, dict) else d
        if isinstance(items, dict):
            items = [{"id": k, **(v if isinstance(v, dict) else {"title": v})} for k, v in items.items()]
        for it in items:
            tid = it.get("id")
            title = it.get("title") or it.get("name") or it.get("label")
            if tid and title and tid in TASK_TITLES:
                TASK_TITLES[tid] = title
    except Exception:
        pass


def main(argv=None) -> int:
    args = parse_args(argv)
    load_task_titles()
    ctx = Ctx(args)
    tools = [t.strip() for t in args.tools.split(",") if t.strip()]
    tasks = expand_tasks(args.tasks)
    ctx.run_dir.mkdir(parents=True, exist_ok=True)
    log(f"Run {ctx.run_id}: Tools {tools}, Aufgaben {tasks}")
    meta = {
        "run_id": ctx.run_id, "started": dt.datetime.now().isoformat(timespec="seconds"),
        "args": vars(args), "tools": tools, "tasks": tasks, "fake": ctx.overridden,
        "host": {"platform": platform.platform(), "python": sys.version.split()[0], "cpu_count": os.cpu_count(),
                 "machine": platform.machine()},
        "availability": {}, "task_titles": {t: TASK_TITLES[t] for t in tasks},
    }
    try:
        import build123d
        meta["host"]["build123d"] = getattr(build123d, "__version__", "?")
    except Exception:
        pass
    try:
        from bench import reference as R
        rm = R.reference_meta()
        meta["reference"] = {"alignment": rm["alignment"], "coverage": {k: v.get("coverage_area_fraction") for k, v in rm["shells"].items()}}
    except Exception as e:
        meta["reference_error"] = str(e)
    for t in tools:
        ok, why, cmd = ctx.availability(t)
        meta["availability"][t] = {"available": ok, "reason": why, "cmd": cmd}
        log(f"Werkzeug {t}: {'verfuegbar' if ok else 'NICHT verfuegbar - ' + why}")
    if ctx.voxel_build:
        meta["voxel_build"] = {k: v for k, v in ctx.voxel_build.items() if k != "cmd"}
    write_json(ctx.run_dir / "run_meta.json", meta)

    t_all = time.time()
    for task in tasks:
        for tool in tools:
            try:
                if task == "B03":
                    run_b03(ctx, tool)
                elif task == "B07":
                    run_b07(ctx, tool)
                elif task == "B10":
                    run_b10(ctx, tool)
                else:
                    run_standard(ctx, tool, task, voxel=(args.voxel_default if tool == "voxel" else None))
            except Exception as e:  # ein Fehler darf den Gesamtlauf nicht abbrechen
                out = ctx.run_dir / task / tool
                log(f"   FEHLER im Runner bei {task}/{tool}: {e}")
                write_json(out / "result.json", {"task": task, "tool": tool, "status": "failed",
                                                  "notes": f"Runner-Ausnahme: {e}", "runner": {"status": "runner_error",
                                                  "traceback": traceback.format_exc()}})
    meta["finished"] = dt.datetime.now().isoformat(timespec="seconds")
    meta["total_s"] = round(time.time() - t_all, 1)
    write_json(ctx.run_dir / "run_meta.json", meta)

    if not args.no_report:
        try:
            from bench import report
            report.build_report(ctx.run_dir)
            log("Report geschrieben: summary.md / summary.json / charts/")
        except Exception as e:
            log(f"Report fehlgeschlagen: {e}\n{traceback.format_exc()}")

    if not args.no_latest and (not ctx.overridden or args.update_latest):
        latest = RESULTS / "latest"
        if latest.exists():
            shutil.rmtree(latest, ignore_errors=True)
        shutil.copytree(ctx.run_dir, latest)
        log(f"Kopiert nach {latest}")
    else:
        log("latest NICHT aktualisiert (Fake-/Override-Lauf oder --no-latest)")
    log(f"Fertig in {meta['total_s']} s: {ctx.run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
