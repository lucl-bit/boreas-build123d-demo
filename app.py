"""Lokaler Web-Server für die Boreas-build123d-Demo.  Start:  python app.py  →  http://localhost:8123"""
from __future__ import annotations

import json
import mimetypes
import os
import sys
import tempfile
import threading
import time
import traceback
import webbrowser
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

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
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, default=float).encode("utf-8"), "application/json; charset=utf-8")

    def _file(self, path: Path | None, download: bool = False):
        if path is None:
            return self._send(404, b"not found", "text/plain")
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix == ".js":
            ctype = "text/javascript; charset=utf-8"
        extra = {"Content-Disposition": f'attachment; filename="{path.name}"'} if download else None
        self._send(200, path.read_bytes(), ctype, extra)

    def do_GET(self):
        try:
            route = self.path.split("?")[0]
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
