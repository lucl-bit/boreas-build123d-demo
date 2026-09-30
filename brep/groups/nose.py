"""Gruppe `nose`: hohle Potenz-Ogive + Einsatz in der Spitze (Kap. 8)."""
from __future__ import annotations

from build123d import Cylinder, Part, Pos

from ..features import Feature
from ..geom import revolve_rz
from ..profiles import ogive_stations, power_ogive
from ..skeleton import Skeleton

GROUP = "nose"


def ogive_outline(z_base: float, radius: float, length: float, m: float, k: float,
                  z_start: float | None = None) -> list[tuple[float, float]]:
    """Meridian (ρ, z) einer Potenz-Ogive ab z_base; optional unten bis z_start verlängert (zylindrisch)."""
    pts = [(power_ogive(t, radius, m, k), z_base + t * length) for t in ogive_stations(60)]
    pts[-1] = (0.0, z_base + length)
    head = [(0.0, z_base)] if z_start is None else [(0.0, z_start), (radius, z_start)]
    return head + pts


def ogive_outer(sk: Skeleton, g) -> Part:
    outline = ogive_outline(sk.nose_joint_z, sk.nose_joint_radius, g.length, g.shape_m, g.shape_n)
    return revolve_rz(outline, spline_from=1, spline_to=len(outline) - 1)


def ogive_inner(sk: Skeleton, g) -> Part:
    outline = ogive_outline(sk.nose_joint_z, sk.nose_joint_radius - g.wall, g.length - g.tip_wall,
                            g.shape_m, g.shape_n, z_start=sk.nose_joint_z - 1)
    return revolve_rz(outline, spline_from=2, spline_to=len(outline) - 1)


def insert(sk: Skeleton, g, cavity: Part) -> Part:
    z0 = sk.nose_joint_z + g.insert_z
    return cavity & (Pos(0, 0, z0 + g.length / 2) * Cylinder(g.insert_radius, g.length))


def build_nose(sk: Skeleton, g) -> list[Feature]:
    cavity = ogive_inner(sk, g)
    feats = [Feature("ogive_outer", "nose", "base", ogive_outer(sk, g), GROUP),
             Feature("ogive_inner", "nose", "cavity", cavity, GROUP)]
    if g.insert_enabled:
        feats.append(Feature("insert", "nose_insert", "base", insert(sk, g, cavity), GROUP))
    return feats
