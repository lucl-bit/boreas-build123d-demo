"""Gruppe `motor_pods`: Tropfen-Gondel = Zylinder-Sockel + Potenz-Ogive (Kap. 4)."""
from __future__ import annotations

from build123d import Axis, Cylinder, Part, Pos, offset

from ..features import Feature
from ..geom import revolve_rz
from ..profiles import ogive_stations, power_ogive
from ..skeleton import Skeleton

GROUP = "motor_pods"


def pod_outline(g, z0: float) -> list[tuple[float, float]]:
    """Meridian (ρ′, z) einer Gondel, Achse unten → Sockel → Ogive (Spline) → Spitze auf der Achse."""
    zb = z0 + g.base_height
    dome = [(power_ogive(t, g.radius, 1.0, g.tip_exponent), zb + t * g.dome_height) for t in ogive_stations(50)]
    dome[-1] = (0.0, zb + g.dome_height)
    return [(0.0, z0), (g.radius, z0)] + dome


SHELL_FALLBACKS: list[float] = []


def _inner_outline(g, z0: float) -> list[tuple[float, float]]:
    """Innenkontur für die Schale: Radius − Wand, Kuppel um die Wand niedriger, unten offen (Näherung des Offsets)."""
    r, zb, hd = g.radius - g.wall, z0 + g.base_height, g.dome_height - g.wall
    dome = [(power_ogive(t, r, 1.0, g.tip_exponent), zb + t * hd) for t in ogive_stations(50)]
    dome[-1] = (0.0, zb + hd)
    return [(0.0, z0 - 1), (r, z0 - 1)] + dome


def pod(sk: Skeleton, g) -> Part:
    outline = pod_outline(g, sk.split_z)
    solid = revolve_rz(outline, spline_from=2, spline_to=len(outline) - 1)
    if g.wall > 0:
        bottom = solid.faces().sort_by(Axis.Z)[0]
        try:
            solid = offset(solid, amount=-g.wall, openings=bottom)
        except Exception:  # OCCT-Offset scheitert bei manchen Wandstärken (StdFail_NotDone) → analytische Innenkontur
            SHELL_FALLBACKS.append(g.wall)
            solid = solid - revolve_rz(_inner_outline(g, sk.split_z), spline_from=2, spline_to=None)
    if g.cable_hole_d > 0:
        solid -= Pos(0, 0, sk.split_z - 10) * Cylinder(g.cable_hole_d / 2, 2 * (g.base_height + 10))
    return solid


def build_motor_pods(sk: Skeleton, g) -> list[Feature]:
    base = pod(sk, g)
    return [Feature(f"pod_{i}", "upper", "add", Pos(m.X, m.Y, 0) * base, GROUP)
            for i, m in enumerate(sk.motor_positions())]
