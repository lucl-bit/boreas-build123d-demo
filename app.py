"""Lokaler Web-Server für die Boreas-build123d-Demo.  Start:  python app.py  →  http://localhost:8123"""
from __future__ import annotations

import json
import mimetypes
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import webbrowser
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import boreas_upper as bu
import pipeline
import tour

ROOT = Path(__file__).parent
GUI = ROOT / "gui"
OUT = ROOT / "out"
STEP_FILE = ROOT / "Mohammed_0.1 Full Shell.step"
MOCK = json.loads((ROOT / "mock_data.json").read_text(encoding="utf-8"))
PORT = int(os.environ.get("PORT", 8123))

# OCCT ist nicht thread-sicher → alle CAD-Operationen serialisieren
CAD_LOCK = threading.Lock()
_cache: dict = {}


def material(name: str) -> dict:
    return MOCK["materials"].get(name) or MOCK["materials"]["PETG"]


def build_payload(body: dict) -> dict:
    p = bu.Params.from_dict(body.get("params", {}))
    req = body["req"]
    mat = material(body.get("material", "PETG"))
    t0 = time.perf_counter()
    res = bu.build(p)
    full = res["parts"]
    parts = bu.section_cut(full) if body.get("section") else full
    build_ms = res["build_ms"]
    t1 = time.perf_counter()
    meshes = {name: {**bu.mesh(part), "color": bu.PART_STYLE[name]} for name, part in parts.items()}
    mesh_ms = (time.perf_counter() - t1) * 1000
    props = bu.mass_properties(full, mat["density"])
    checks = bu.check_constraints(p, req, mat, MOCK["limits"], props["mass_g"])
    return {
        "params": asdict(p), "derived": bu.derived(p), "meshes": meshes, "props": props, "checks": checks,
        "timing": {"build_ms": build_ms, "mesh_ms": mesh_ms, "total_ms": (time.perf_counter() - t0) * 1000,
                   "cached": build_ms < 100},
        "valid": {name: part.is_valid for name, part in parts.items()},
    }


def original_payload() -> dict:
    if "original" not in _cache:
        local = tour.original_local(STEP_FILE)
        _cache["original"] = {k: bu.mesh(v, 0.3, 0.4, with_edges=False) for k, v in local.items() if k != "Innenschale"}
    return _cache["original"]


def batch_payload() -> list:
    rows = []
    for name, preset in MOCK["presets"].items():
        mat = material(preset["material"])
        p = bu.autosize(preset["req"], mat, MOCK["limits"])
        t0 = time.perf_counter()
        parts = bu.build(p)["parts"]
        props = bu.mass_properties(parts, mat["density"])
        checks = bu.check_constraints(p, preset["req"], mat, MOCK["limits"], props["mass_g"])
        rows.append({
            "name": name, "material": preset["material"], "params": asdict(p), "props": props,
            "ok": sum(c["ok"] for c in checks), "n_checks": len(checks),
            "failed": [c["name"] for c in checks if not c["ok"]],
            "twr": next((c["value"] for c in checks if c["name"].startswith("Schub")), None),
            "ms": (time.perf_counter() - t0) * 1000,
        })
    return rows


def export_file(body: dict) -> tuple[bytes, str]:
    fmt = body["format"]
    p = bu.Params.from_dict(body["params"])
    mat = material(body.get("material", "PETG"))
    parts = bu.build(p)["parts"]
    meta = {"material": mat["label"], "variant": body.get("preset") or "Parametrische Variante",
            "mass_body": f"{parts['Rumpf'].volume * mat['density'] / 1000:.0f} g"}
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, f"boreas_oberteil.{fmt}")
        bu.export(parts, fmt, path, p, meta)
        return Path(path).read_bytes(), fmt


def tour_payload(body: dict) -> dict:
    ctx = tour.Ctx(p=bu.Params.from_dict(body.get("params", {})), req=body["req"],
                   mat=material(body.get("material", "PETG")), mat_key=body.get("material", "PETG"),
                   cfg=MOCK, opts=body.get("opts", {}), root=ROOT)
    return tour.run_step(body["id"], ctx)


EXPORT_MIME = {
    "step": "application/step", "stl": "model/stl", "3mf": "model/3mf",
    "glb": "model/gltf-binary", "dxf": "image/vnd.dxf", "svg": "image/svg+xml",
}


def _safe(base: Path, rel: str) -> Path | None:
    path = (base / unquote(rel)).resolve()
    return path if path.is_file() and path.is_relative_to(base.resolve()) else None


# ====================================================================== Modus ④ Vergleich (B-rep vs. Voxel)
BENCH = ROOT / "bench" / "results"
SPEC_DIR = ROOT / "spec"
MOCK_DIR = BENCH / "mock"
TOOL_IDS = ("brep", "voxel")
SECTION_OF = {"B": "common", "R": "brep_only", "V": "voxel_only", "A": "api"}
RUN_LOCK = threading.Lock()   # Neu-Rechnen läuft als eigener Prozess → eigener Lock statt CAD_LOCK (blockiert ①–③ nicht)
_TOKEN = re.compile(r"^[A-Za-z0-9_][\w.\-]*$")
_SET_ARG = re.compile(r"^[A-Za-z_]\w*\.[A-Za-z_]\w*=[\w.+\-]+$")
IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
BENCH_MIME = {
    ".stl": "model/stl", ".step": "application/step", ".stp": "application/step", ".3mf": "model/3mf", ".svg": "image/svg+xml",
    ".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
    ".webp": "image/webp", ".json": "application/json; charset=utf-8", ".dxf": "image/vnd.dxf", ".urdf": "application/xml",
    ".txt": "text/plain; charset=utf-8", ".md": "text/plain; charset=utf-8", ".csv": "text/csv; charset=utf-8",
}


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _tok(v: str | None) -> str | None:
    return v if v and _TOKEN.match(v) else None


def _run_label(name: str) -> str:
    m = re.match(r"^(\d{4})(\d{2})(\d{2})[_-](\d{2})(\d{2})", name)
    base = f"{m[3]}.{m[2]}.{m[1]} {m[4]}:{m[5]}" if m else name
    if name.endswith("_selftest"):
        return f"Selbsttest {name[:-9]}"
    return {"latest": "latest (letzter Lauf)", "mock": "Mock-Daten", "live": "live (neu gerechnet)"}.get(name, base)


def list_runs() -> list[dict]:
    if not BENCH.is_dir():
        return []
    # Layout: <run>/<task>/<tool>/result.json (Runner) oder <run>/<task>/result.json (Selbsttests eines einzelnen Tools)
    names = [d.name for d in BENCH.iterdir() if d.is_dir() and _TOKEN.match(d.name)
             and (any(d.glob("*/*/result.json")) or any(d.glob("*/result.json")))]
    rest = sorted((n for n in names if n not in ("latest", "live", "mock") and not n.endswith("_selftest")), reverse=True)
    tests = sorted(n for n in names if n.endswith("_selftest"))
    order = [n for n in ("latest", "live") if n in names] + rest + tests + (["mock"] if "mock" in names else [])
    return [{"id": n, "label": _run_label(n), "mock": n == "mock"} for n in order]


def default_run(runs: list[dict]) -> str | None:
    ids = [r["id"] for r in runs]
    if "latest" in ids:
        return "latest"
    # echte Läufe vor Fake-/Selbsttest-/Live-Läufen; ohne solche die Mock-Daten
    real = [i for i in ids if i != "mock" and not i.startswith("fake_") and not i.endswith("_selftest") and i != "live"]
    return real[0] if real else ("mock" if "mock" in ids else (ids[0] if ids else None))


def find_result(run: str, task: str, tool: str, fill: bool = True):
    """→ (dict, run_used, reldir) | (None, None, None). Fehlt das Ergebnis im Lauf, springt es (fill) auf die Mock-Daten."""
    for r in ([run] + (["mock"] if fill and run != "mock" else [])):
        p = BENCH / r / task / tool / "result.json"
        if p.is_file():
            d = _read_json(p)
            if isinstance(d, dict):
                return d, r, f"{r}/{task}/{tool}"
        flat = BENCH / r / task / "result.json"      # Selbsttests: ein Tool pro Ordner, ohne Tool-Unterordner
        if flat.is_file():
            d = _read_json(flat)
            if isinstance(d, dict) and (d.get("tool") == tool or (d.get("tool") is None and r.startswith(tool))):
                return d, r, f"{r}/{task}"
    return None, None, None


def _file_entry(key: str, val: str, reldir: str) -> dict | None:
    rel = posixpath.normpath(f"{reldir}/{val.replace(chr(92), '/')}")
    if rel.startswith("..") or rel.startswith("/") or ":" in rel:
        return None
    full = _bench_file(rel)
    ext = posixpath.splitext(rel)[1].lower()
    kind = "mesh" if ext == ".stl" else "image" if ext in IMG_EXT else "pdf" if ext == ".pdf" else "file"
    e = {"key": key, "path": val, "name": posixpath.basename(rel), "ext": ext, "kind": kind, "exists": full is not None,
         "url": "/bench/" + quote(rel), "size": None, "tris": None}
    if full is not None:
        e["size"] = full.stat().st_size
        if ext == ".stl":
            try:
                with open(full, "rb") as f:
                    head = f.read(84)
                n = int.from_bytes(head[80:84], "little")
                e["tris"] = n if len(head) == 84 and 84 + 50 * n == e["size"] else None
            except OSError:
                pass
    return e


def enrich_result(d: dict, run_used: str, requested: str, reldir: str) -> dict:
    """Ergänzt result.json um _meta (Herkunft, Mock-Flag, aufgelöste Dateiliste mit URLs, Grössen, Dreiecksanzahl)."""
    out = dict(d)
    files: list[dict] = []

    def walk(key: str, v):
        if isinstance(v, str) and v:
            if (e := _file_entry(key, v, reldir)):
                files.append(e)
        elif isinstance(v, (list, tuple)):
            for i, x in enumerate(v):
                walk(f"{key}[{i + 1}]", x)
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(f"{key}.{k}" if key else str(k), x)

    walk("", d.get("files") or {})
    out["_meta"] = {"run": run_used, "requested_run": requested, "mock": run_used == "mock", "filled": run_used != requested, "files": files}
    return out


def _norm_task(t: dict, mock: bool) -> dict:
    t = dict(t)
    t["id"] = str(t.get("id", "")).strip()
    t["section_key"] = SECTION_OF.get(t["id"][:1].upper(), "other")
    t["_mock"] = mock
    return t


def _task_list(data) -> list[dict]:
    if isinstance(data, dict):
        data = data.get("tasks", data)
    if isinstance(data, dict):
        data = [{"id": k, **v} for k, v in data.items() if isinstance(v, dict)]
    return [t for t in (data or []) if isinstance(t, dict) and t.get("id")]


def load_tasks() -> tuple[list[dict], str]:
    """spec/benchmark_tasks.json hat Vorrang; fehlende IDs werden aus der Mock-Kopie ergänzt."""
    mock = {t["id"]: _norm_task(t, True) for t in _task_list(_read_json(MOCK_DIR / "benchmark_tasks.json"))}
    spec = {t["id"]: _norm_task(t, False) for t in _task_list(_read_json(SPEC_DIR / "benchmark_tasks.json"))}
    merged = {**mock, **spec}
    order = {"B": 0, "R": 1, "V": 2, "A": 3}
    tasks = sorted(merged.values(), key=lambda t: (order.get(t["id"][:1].upper(), 9), t["id"]))
    src = "spec" if spec and not any(t["_mock"] for t in tasks) else "spec+mock" if spec else "mock" if mock else "none"
    return tasks, src


def _dotnet() -> str | None:
    """dotnet aus PATH, sonst Standard-Installationsort (der Server-Prozess kennt einen frischen PATH evtl. nicht)."""
    found = shutil.which("dotnet")
    if found:
        return found
    for cand in (r"C:\Program Files\dotnet\dotnet.exe", r"C:\Program Files (x86)\dotnet\dotnet.exe"):
        if Path(cand).is_file():
            return cand
    return None


def tool_availability() -> dict:
    spec = (SPEC_DIR / "boreas_spec.json").is_file()
    brep_cli = (ROOT / "brep" / "cli.py").is_file()
    dotnet = _dotnet()
    vox = ROOT / "voxel"
    has_proj = vox.is_dir() and any(vox.glob("*.csproj"))
    return {
        "brep": {"available": brep_cli and spec,
                 "reason": "" if brep_cli and spec else ("brep/cli.py fehlt" if not brep_cli else "spec/boreas_spec.json fehlt")},
        "voxel": {"available": bool(dotnet) and has_proj and spec,
                  "reason": "" if dotnet and has_proj and spec else (
                      "dotnet ist nicht installiert" if not dotnet else "voxel/-Projekt fehlt" if not has_proj else "spec/boreas_spec.json fehlt")},
    }


def compare_index(run: str | None, fill: bool) -> dict:
    runs = list_runs()
    run = run if run in [r["id"] for r in runs] else default_run(runs)
    tasks, tsrc = load_tasks()
    summary = {}
    for t in tasks:
        row = {}
        for tool in TOOL_IDS:
            d, used, _ = find_result(run, t["id"], tool, fill) if run else (None, None, None)
            row[tool] = {"status": d.get("status", "failed") if d else "not_run", "runtime_s": d.get("runtime_s") if d else None,
                         "mock": used == "mock"}
        summary[t["id"]] = row
    return {
        "runs": runs, "run": run, "tasks": tasks, "tasks_source": tsrc, "summary": summary,
        "matrix_source": "spec" if (SPEC_DIR / "feature_matrix.json").is_file() else "mock" if (MOCK_DIR / "feature_matrix.json").is_file() else "none",
        "tools": tool_availability(),
    }


def compare_matrix() -> dict:
    for p, src in ((SPEC_DIR / "feature_matrix.json", "spec"), (MOCK_DIR / "feature_matrix.json", "mock")):
        d = _read_json(p)
        if isinstance(d, dict) and d.get("features"):
            return {**d, "_source": src, "_mock": src == "mock" or bool(d.get("_mock"))}
    return {"features": [], "categories": [], "legend": {}, "_source": "none", "_mock": False}


def _bench_roots() -> list[Path]:
    base = BENCH.resolve()
    return [base] + [d.resolve() for d in BENCH.iterdir() if d.is_dir()]   # "latest" darf ein Link/Junction sein


def _bench_file(rel: str) -> Path | None:
    """Sicherer Zugriff unterhalb bench/results (kein Path-Traversal, keine absoluten Pfade)."""
    if not BENCH.is_dir() or "\\" in rel or rel.startswith("/") or ":" in rel or "\0" in rel:
        return None
    if any(seg in ("", ".", "..") for seg in rel.split("/")):
        return None
    try:
        cand = (BENCH / rel).resolve()
        if cand.is_file() and any(cand.is_relative_to(r) for r in _bench_roots()):
            return cand
    except (OSError, ValueError):
        pass
    return None


def compare_run(body: dict) -> dict:
    """Neu rechnen: ruft die Tool-CLI als Subprozess auf und schreibt nach bench/results/live/<task>/<tool>/."""
    task, tool = _tok(body.get("task")), body.get("tool")
    if not task or tool not in TOOL_IDS:
        raise ValueError("task/tool ungültig")
    avail = tool_availability()[tool]
    if not avail["available"]:
        raise RuntimeError(f"{tool}-CLI nicht verfügbar: {avail['reason']}")
    sets = [s.strip() for s in body.get("sets", []) if isinstance(s, str) and s.strip()]
    for s in sets:
        if not _SET_ARG.match(s):
            raise ValueError(f"Überschreibung ungültig (erwartet gruppe.param=wert): {s}")
    out = BENCH / "live" / task / tool
    if not RUN_LOCK.acquire(blocking=False):
        raise RuntimeError("Es läuft bereits eine Berechnung.")
    try:
        out.mkdir(parents=True, exist_ok=True)
        (out / "result.json").unlink(missing_ok=True)
        spec = str(SPEC_DIR / "boreas_spec.json")
        if tool == "brep":
            cmd = [sys.executable, "-m", "brep.cli", "--spec", spec, "--task", task, "--out", str(out)]
        else:
            cmd = [_dotnet(), "run", "--project", str(ROOT / "voxel"), "-c", "Release", "--", "--spec", spec, "--task", task, "--out", str(out)]
            if body.get("voxel"):
                vs = float(body["voxel"])
                if not 0.01 <= vs <= 50:
                    raise ValueError("Voxelgrösse ausserhalb 0.01 … 50 mm")
                cmd += ["--voxel", str(vs)]
        for s in sets:
            cmd += ["--set", s]
        t0 = time.perf_counter()
        try:
            cp = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
            rc, so, se = cp.returncode, cp.stdout, cp.stderr
        except subprocess.TimeoutExpired:
            rc, so, se = -1, "", "Zeitüberschreitung nach 900 s"
        return {"returncode": rc, "seconds": time.perf_counter() - t0, "stdout": so[-1500:], "stderr": se[-1500:],
                "cmd": " ".join(cmd), "run": "live", "has_result": (out / "result.json").is_file()}
    finally:
        RUN_LOCK.release()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code: int, data: bytes, ctype: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        try:
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass    # Client hat abgebrochen (z. B. beim Schrittwechsel während eines grossen STL)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, default=float).encode("utf-8"), "application/json; charset=utf-8")

    def _file(self, path: Path | None, download: bool = False, bench: bool = False):
        if path is None:
            return self._send(404, b"not found", "text/plain")
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix == ".js":
            ctype = "text/javascript; charset=utf-8"
        if bench:
            ctype = BENCH_MIME.get(path.suffix.lower(), "application/octet-stream")
        extra = {"Content-Disposition": f'attachment; filename="{path.name}"'} if download else {}
        if path.suffix.lower() == ".svg":     # SVG aus Ergebnisordnern darf beim direkten Öffnen keine Skripte ausführen
            extra["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
        self._send(200, path.read_bytes(), ctype, extra or None)

    def do_GET(self):
        try:
            url = urlparse(self.path)
            route, qs = url.path, {k: v[0] for k, v in parse_qs(url.query).items()}
            if route in ("/", "/index.html"):
                self._file(GUI / "index.html")
            elif route.startswith("/gui/"):
                self._file(_safe(GUI, route[5:]))
            elif route.startswith("/out/"):
                self._file(_safe(OUT, route[5:]), download=True)
            elif route == "/api/config":
                self._json({"spec": bu.PARAM_SPEC, "defaults": asdict(bu.Params()), "tour": tour.step_list(),
                            "stages": [{"id": s[0], "name": s[1], "tool": s[2], "desc": s[3]} for s in pipeline.STAGES],
                            "loop": pipeline.LOOP_BACK, **MOCK})
            elif route == "/api/original":
                with CAD_LOCK:
                    self._json(original_payload())
            elif route == "/api/compare/index":
                self._json(compare_index(_tok(qs.get("run")), qs.get("fill", "1") != "0"))
            elif route == "/api/compare/matrix":
                self._json(compare_matrix())
            elif route == "/api/compare/result":
                run, task, tool = _tok(qs.get("run")), _tok(qs.get("task")), qs.get("tool")
                if not (run and task and tool in TOOL_IDS):
                    return self._json({"error": "run/task/tool ungültig"}, 400)
                d, used, reldir = find_result(run, task, tool, qs.get("fill", "1") != "0")
                self._json(enrich_result(d, used, run, reldir) if d else
                           {"task": task, "tool": tool, "status": "not_run", "notes": "", "metrics": {}, "files": {},
                            "_meta": {"run": run, "requested_run": run, "mock": False, "filled": False, "files": []}})
            elif route.startswith("/bench/"):
                self._file(_bench_file(unquote(route[7:])), download=qs.get("dl") == "1", bench=True)
            elif route == "/api/source":
                self._send(200, (ROOT / "boreas_upper.py").read_bytes(), "text/plain; charset=utf-8")
            else:
                self._send(404, b"not found", "text/plain")
        except Exception as exc:
            traceback.print_exc()
            self._json({"error": str(exc)}, 500)

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if self.path == "/api/compare/run":
                try:
                    return self._json(compare_run(body))
                except ValueError as exc:
                    return self._json({"error": str(exc)}, 400)
                except RuntimeError as exc:
                    return self._json({"error": str(exc)}, 409)
            with CAD_LOCK:
                if self.path == "/api/build":
                    self._json(build_payload(body))
                elif self.path == "/api/autosize":
                    p = bu.autosize(body["req"], material(body.get("material", "PETG")), MOCK["limits"],
                                    bu.Params.from_dict(body.get("params", {})))
                    self._json({"params": asdict(p)})
                elif self.path == "/api/batch":
                    self._json(batch_payload())
                elif self.path == "/api/tour":
                    self._json(tour_payload(body))
                elif self.path == "/api/pipeline":
                    res = pipeline.run_pipeline(body["req"], body.get("material", "PETG"), body.get("params"),
                                                name=body.get("name", "variante"), optimize=body.get("optimize", True),
                                                with_meshes=True)
                    self._json(res)
                elif self.path == "/api/export":
                    data, fmt = export_file(body)
                    self._send(200, data, EXPORT_MIME[fmt],
                               {"Content-Disposition": f'attachment; filename="boreas_oberteil.{fmt}"'})
                else:
                    self._send(404, b"not found", "text/plain")
        except Exception as exc:
            traceback.print_exc()
            self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)


def _warmup():
    """Font-Scan (Text/Zeichnung) und STEP-Import einmalig im Hintergrund vorwegnehmen."""
    with CAD_LOCK:
        try:
            from build123d import Text
            Text("warmup", 3)
            tour.load_original(STEP_FILE)
        except Exception:
            traceback.print_exc()


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"Boreas build123d Demo läuft auf {url}  (Strg+C zum Beenden)")
    threading.Thread(target=_warmup, daemon=True).start()
    if "--no-browser" not in sys.argv:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    server.serve_forever()
