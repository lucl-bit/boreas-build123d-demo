"""Kleine build123d-Bausteine, die mehrere Gruppen brauchen (kein Zugriff auf Parameter)."""
from __future__ import annotations

import math
from collections.abc import Sequence

from build123d import (
    Axis, Box, Compound, Cylinder, Edge, Face, Line, Location, Part, Plane, Polyline, Pos, Solid, Spline, Vector,
    Wire, extrude, loft, revolve,
)

BIG = 1000.0  # mm, "unendlich" für Halbräume


def _face_from(points3d: Sequence[Vector], spline: bool) -> Face:
    """Geschlossene ebene Fläche: Spline (oder Polylinie) durch alle Punkte + gerade Schlusslinie."""
    if spline:
        edges = [Spline(*points3d), Line(points3d[-1], points3d[0])]
        return Face(Wire(edges))
    return Face(Wire(Polyline(*points3d, close=True).edges()))


def poly_face(points3d: Sequence[Vector]) -> Face:
    """Ebene Fläche aus einem geschlossenen Polygon."""
    return _face_from(points3d, spline=False)


def revolve_rz(outline: Sequence[tuple[float, float]], spline_from: int | None = None,
               spline_to: int | None = None) -> Solid:
    """Rotationskörper um die Z-Achse aus einer Kontur (ρ, z).

    `outline` ist ein offener Zug (erster und letzter Punkt liegen auf der Achse, ρ = 0). Die Punkte
    `spline_from…spline_to` (inkl.) werden als Spline verbunden, der Rest als Geraden.
    """
    pts = [Vector(r, 0, z) for r, z in outline]
    edges: list[Edge] = []
    i = 0
    n = len(pts)
    while i < n - 1:
        if spline_from is not None and i == spline_from:
            end = n - 1 if spline_to is None else spline_to
            edges.append(Spline(*pts[spline_from:end + 1]))
            i = end
        else:
            edges.append(Line(pts[i], pts[i + 1]))
            i += 1
    if (pts[-1] - pts[0]).length > 1e-9:
        edges.append(Line(pts[-1], pts[0]))
    return revolve(Face(Wire(edges)), Axis.Z, 360)


def profile_curve_rz(f, z_a: float, z_b: float, stations: Sequence[float]) -> list[tuple[float, float]]:
    """Stützpunkte (f(z), z) für z = z_a + t·(z_b − z_a)."""
    return [(f(z_a + t * (z_b - z_a)), z_a + t * (z_b - z_a)) for t in stations]


def arm_point(angle_deg: float, s: float, q: float, z: float) -> Vector:
    """Punkt im Armsystem (s = Spannweite, q = quer, z) → global."""
    a = math.radians(angle_deg)
    return Vector(s * math.cos(a) - q * math.sin(a), s * math.sin(a) + q * math.cos(a), z)


def arm_section_face(angle_deg: float, s: float, outline_qz: Sequence[tuple[float, float]], spline: bool = True,
                     cant_deg: float = 0.0, cant_z: float = 0.0) -> Face:
    """Querschnitt in der Ebene s = const des Arms mit Winkel `angle_deg`.

    `outline_qz` in (q, z) absolut; optional um die Achse (q = 0, z = cant_z) um `cant_deg` gedreht
    (positiv: Oberseite Richtung +q).
    """
    c, sn = math.cos(math.radians(cant_deg)), math.sin(math.radians(cant_deg))
    pts = []
    for q, z in outline_qz:
        dz = z - cant_z
        pts.append(arm_point(angle_deg, s, q * c + dz * sn, -q * sn + dz * c + cant_z))
    return _face_from(pts, spline)


def ruled_loft(face_a: Face, face_b: Face) -> Part:
    """Regelfläche zwischen zwei Querschnitten gleicher Parametrisierung (exakt bei linearer Interpolation)."""
    return loft([face_a, face_b], ruled=True)


def halfspace_above(z: float) -> Part:
    return Pos(0, 0, z + BIG / 2) * Box(BIG, BIG, BIG)


def halfspace_below(z: float) -> Part:
    return Pos(0, 0, z - BIG / 2) * Box(BIG, BIG, BIG)


def z_slab(z0: float, z1: float, size: float = BIG) -> Part:
    return Pos(0, 0, (z0 + z1) / 2) * Box(size, size, z1 - z0)


def ring(r_out: float, r_in: float, z0: float, z1: float) -> Part:
    body = Pos(0, 0, (z0 + z1) / 2) * Cylinder(r_out, z1 - z0)
    return body - Pos(0, 0, (z0 + z1) / 2) * Cylinder(r_in, z1 - z0 + 2) if r_in > 0 else body


def wedge(center_deg: float, half_angle_deg: float, z0: float, z1: float, reach: float = 300.0) -> Part:
    """Keil (Winkelbereich) um die Z-Achse, Spitze auf der Achse, z0…z1 (für Sektoren, half_angle < 89°)."""
    a0, a1 = math.radians(center_deg - half_angle_deg), math.radians(center_deg + half_angle_deg)
    am = math.radians(center_deg)
    far = reach / max(math.cos(math.radians(half_angle_deg)), 0.05)
    pts = [Vector(0, 0, z0), Vector(far * math.cos(a0), far * math.sin(a0), z0),
           Vector(far * math.cos(am), far * math.sin(am), z0), Vector(far * math.cos(a1), far * math.sin(a1), z0)]
    return extrude(Face(Wire(Polyline(*pts, close=True).edges())), amount=z1 - z0)


def sector(center_deg: float, half_angle_deg: float, r_out: float, z0: float, z1: float, r_in: float = 0.0) -> Part:
    """Ring- bzw. Kreissektor um die Rumpfachse."""
    return ring(r_out, r_in, z0, z1) & wedge(center_deg, half_angle_deg, z0 - 1, z1 + 1, reach=r_out + 10)


def fuse_all(parts: Sequence[Part]) -> Part:
    parts = [p for p in parts if p is not None]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return parts[0].fuse(*parts[1:])


def compound(parts: Sequence[Part]) -> Compound:
    return Compound([p for p in parts if p is not None])
