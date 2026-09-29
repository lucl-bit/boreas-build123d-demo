"""Einheitliches Szenen-/Ergebnisformat für die GUI (Tour und Pipeline benutzen es gleichermaßen)."""
from __future__ import annotations

import numpy as np

import boreas_upper as bu

C = {
    "green": (0.30, 0.72, 0.42), "blue": (0.20, 0.55, 0.85), "orange": (0.95, 0.52, 0.18), "red": (0.93, 0.27, 0.27),
    "yellow": (1.0, 0.85, 0.2), "cyan": (0.45, 0.85, 1.0), "violet": (0.70, 0.55, 1.0), "grey": (0.62, 0.66, 0.72),
    "white": (0.92, 0.94, 0.97), "pink": (0.95, 0.45, 0.75),
}


def item(id_: str, shape, color=None, opacity: float = 1.0, edges: bool = True, tol: float = 0.1, **extra) -> dict:
    m = bu.mesh(shape, tol, 0.2, with_edges=edges)
    return {"id": id_, "color": color or C["grey"], "opacity": opacity, **m, **extra}


def parts_items(parts: dict, opacity: float = 1.0, edges: bool = True, prefix: str = "", tol: float = 0.1) -> list:
    return [item(prefix + name, part, bu.PART_STYLE.get(name, C["grey"]), opacity, edges, tol) for name, part in parts.items()]


def ghost(parts: dict, opacity: float = 0.12) -> list:
    return parts_items(parts, opacity, edges=False, prefix="ghost:", tol=0.3)


def lines(id_: str, edges, color, width: float = 2.0) -> dict:
    return {"id": id_, "segments": bu.edge_segments(edges), "color": color, "width": width}


def polyline(id_: str, pts, color, width: float = 2.0) -> dict:
    seg = []
    for a, b in zip(pts[:-1], pts[1:]):
        seg += [*map(float, a), *map(float, b)]
    return {"id": id_, "segments": seg, "color": color, "width": width}


def triad(id_: str, origin, size: float = 15.0, axes=None) -> list:
    axes = axes if axes is not None else np.eye(3)
    o = np.array(origin, float)
    cols = [C["red"], C["green"], C["blue"]]
    return [polyline(f"{id_}:{k}", [o, o + size * np.asarray(axes[k], float)], cols[k], 3) for k in range(3)]


def marker(pos, radius: float, color, label: str = "") -> dict:
    return {"pos": [float(x) for x in pos], "radius": radius, "color": color, "label": label}


def ds(label: str, xs, ys, color, dashed: bool = False, points: bool = False, fill: bool = False) -> dict:
    return {"label": label, "data": [[float(x), float(y)] for x, y in zip(xs, ys)], "color": color,
            "dashed": dashed, "points": points, "fill": fill}


def chart(title: str, xlabel: str, ylabel: str, datasets: list, kind: str = "line") -> dict:
    return {"title": title, "xlabel": xlabel, "ylabel": ylabel, "datasets": datasets, "type": kind}


def hexcol(c) -> str:
    return "#%02x%02x%02x" % tuple(int(round(v * 255)) for v in c)


def f(v, d: int = 1, unit: str = "") -> str:
    s = f"{v:,.{d}f}".replace(",", "'")
    return f"{s} {unit}".strip()
