"""Gruppe `lower_body`: hohler Kegelrumpf mit Kragen (Kap. 6)."""
from __future__ import annotations

from build123d import Part

from ..features import Feature
from ..geom import revolve_rz
from ..skeleton import Skeleton

GROUP = "lower_body"


def outer_points(sk: Skeleton, g) -> tuple[tuple[float, float], ...]:
    """A (Trennebene), B (Kragen-Knick), C (Unterkante) als (ρ, z)."""
    a = (sk.joint_radius, sk.split_z)
    b = (sk.joint_radius - g.collar_taper, sk.split_z - g.collar_length)
    c = (g.bottom_radius, sk.body_bottom_z)
    return a, b, c


def cone_line(sk: Skeleton, g, z: float) -> float:
    """r_BC(z): Gerade durch B und C, auch oberhalb von B fortgesetzt."""
    _, (rb, zb), (rc, zc) = outer_points(sk, g)
    return rb + (rc - rb) * (z - zb) / (zc - zb)


def cone_outer(sk: Skeleton, g) -> Part:
    a, b, c = outer_points(sk, g)
    return revolve_rz([(0.0, a[1]), a, b, c, (0.0, c[1])])


def cone_cavity(sk: Skeleton, g) -> Part:
    """r_in(z) = min(Bohrung, r_BC(z) − wall) über [z_B − 1, z₀ + 1]."""
    bore = sk.joint_radius - g.collar_wall
    z_top, z_bot = sk.split_z + 1, sk.body_bottom_z - 1
    _, (rb, zb), (rc, zc) = outer_points(sk, g)
    slope = (rc - rb) / (zc - zb)                      # dρ/dz der Kegelflanke
    z_x = zb + (bore + g.wall - rb) / slope            # hier schneidet die versetzte Flanke die Bohrung
    r_bot = cone_line(sk, g, z_bot) - g.wall
    if z_x >= z_top:                                    # Flanke überall enger als die Bohrung
        pts = [(0.0, z_top), (cone_line(sk, g, z_top) - g.wall, z_top), (r_bot, z_bot), (0.0, z_bot)]
    else:
        pts = [(0.0, z_top), (bore, z_top), (bore, z_x), (r_bot, z_bot), (0.0, z_bot)]
    return revolve_rz(pts)


def build_lower_body(sk: Skeleton, g) -> list[Feature]:
    return [Feature("cone_outer", "lower", "base", cone_outer(sk, g), GROUP),
            Feature("cone_cavity", "lower", "cavity", cone_cavity(sk, g), GROUP)]
