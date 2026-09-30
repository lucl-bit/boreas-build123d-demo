"""Mehransichten-Render (matplotlib, headless) für STL-Dateien.

python tools/render_views.py out.png teil1.stl[:farbe] teil2.stl[:farbe] ... [--views iso,front,top] [--alpha 0.5]
Farben als Hex ohne #, z. B. model.stl:1f5fa8 ref.stl:d9731a.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bench.metrics import read_stl  # noqa: E402

VIEWS = {"iso": (25, -60), "iso2": (25, 30), "front": (0, -90), "side": (0, 0), "top": (90, -90), "bottom": (-90, -90)}
PALETTE = ["1f5fa8", "d9731a", "3a9a5b", "b03a48", "7a52a8"]


def _decimate(t: np.ndarray, max_tris: int) -> np.ndarray:
    if len(t) <= max_tris:
        return t
    idx = np.random.default_rng(0).choice(len(t), max_tris, replace=False)
    return t[np.sort(idx)]


def render(out: str, meshes: list[tuple[np.ndarray, str]], views=("iso", "iso2", "front", "top"), alpha=1.0,
           max_tris=120_000, title: str | None = None, dpi=80) -> None:
    cols = min(len(views), 3)
    rows = (len(views) + cols - 1) // cols
    fig = plt.figure(figsize=(6 * cols, 5.5 * rows))
    allp = np.vstack([m.reshape(-1, 3) for m, _ in meshes])
    c = (allp.max(0) + allp.min(0)) / 2
    r = (allp.max(0) - allp.min(0)).max() / 2
    for k, v in enumerate(views):
        el, az = VIEWS[v]
        ax = fig.add_subplot(rows, cols, k + 1, projection="3d")
        e, a = np.radians(el), np.radians(az)
        light = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
        for tris, col in meshes:
            t = _decimate(tris, max_tris // len(meshes))
            n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
            n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
            rgb = np.array([int(col[i:i + 2], 16) / 255 for i in (0, 2, 4)])
            fc = np.clip((0.35 + 0.65 * np.abs(n @ light))[:, None] * rgb, 0, 1)
            fc = np.hstack([fc, np.full((len(fc), 1), alpha)])
            ax.add_collection3d(Poly3DCollection(t, facecolors=fc, edgecolors="none"))
        ax.set_xlim(c[0] - r, c[0] + r)
        ax.set_ylim(c[1] - r, c[1] + r)
        ax.set_zlim(c[2] - r, c[2] + r)
        ax.view_init(el, az)
        ax.set_box_aspect((1, 1, 1))
        ax.set_axis_off()
        ax.set_title(v)
    if title:
        fig.suptitle(title)
    plt.tight_layout()
    plt.savefig(out, dpi=dpi)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("stl", nargs="+")
    ap.add_argument("--views", default="iso,iso2,front,top")
    ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--title")
    a = ap.parse_args()
    meshes = []
    for i, s in enumerate(a.stl):
        path, _, col = s.partition(":") if not s[1:3] == ":\\" else (s, "", "")
        if s[1:3] == ":\\" or s[1:3] == ":/":
            head, _, col = s[2:].partition(":")
            path = s[:2] + head
        meshes.append((read_stl(path), col or PALETTE[i % len(PALETTE)]))
    render(a.out, meshes, a.views.split(","), a.alpha, title=a.title)


if __name__ == "__main__":
    main()
