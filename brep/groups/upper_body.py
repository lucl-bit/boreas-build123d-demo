"""Gruppe `upper_body`: fassförmiges Oberteil-Rohr + NACA-Kühlluft-Einlässe (Definition Kap. 2)."""
from __future__ import annotations

from build123d import Part, extrude

from ..features import Feature
from ..geom import arm_point, poly_face, revolve_rz
from ..profiles import barrel_radius, cosine_stations
from ..skeleton import Skeleton

GROUP = "upper_body"


def outer_radius(sk: Skeleton, g, z: float) -> float:
    """r_o(z) – Aussenkontur des Rohrs."""
    zeta = (z - sk.split_z) / sk.tube_height
    return barrel_radius(zeta, sk.joint_radius, sk.nose_joint_radius, g.bulge, g.bulge_pos)


def _tube_outline(sk: Skeleton, g, offset: float, z_ext: float) -> list[tuple[float, float]]:
    """Kontur (ρ, z) für revolve: Achse unten → Kontur (Spline) → Achse oben."""
    z0, z1 = sk.split_z, sk.nose_joint_z
    pts = [(outer_radius(sk, g, z0 + t * (z1 - z0)) - offset, z0 + t * (z1 - z0)) for t in cosine_stations(30)]
    if z_ext > 0:
        pts = [(pts[0][0], z0 - z_ext)] + pts + [(pts[-1][0], z1 + z_ext)]
    return [(0.0, pts[0][1])] + pts + [(0.0, pts[-1][1])]


def tube_outer(sk: Skeleton, g) -> Part:
    outline = _tube_outline(sk, g, 0.0, 0.0)
    return revolve_rz(outline, spline_from=1, spline_to=len(outline) - 2)


def tube_cavity(sk: Skeleton, g) -> Part:
    outline = _tube_outline(sk, g, g.wall, 1.0)
    return revolve_rz(outline, spline_from=2, spline_to=len(outline) - 3)


def intake(sk: Skeleton, g, angle: float) -> Part:
    """Ein NACA-Einlass: Prisma (Draufsicht-Trapez) ∩ Prisma (Seitenansicht mit ebener Rampe)."""
    z_t = sk.nose_joint_z - g.intake_top_offset
    z_l = z_t - g.intake_length
    u_top = outer_radius(sk, g, z_t)
    u_lip = outer_radius(sk, g, z_l) - g.intake_depth
    u_far = max(outer_radius(sk, g, z) for z in (z_l, z_t, sk.split_z + sk.tube_height * g.bulge_pos)) + 10
    b_lip, b_top = g.intake_width / 2, g.intake_width_top / 2
    side = poly_face([arm_point(angle, u_lip, 0, z_l), arm_point(angle, u_far, 0, z_l),
                      arm_point(angle, u_far, 0, z_t), arm_point(angle, u_top, 0, z_t)])
    side_prism = extrude(side, amount=max(b_lip, b_top) + 1, both=True)
    plan = poly_face([arm_point(angle, 0, -b_lip, z_l), arm_point(angle, 0, b_lip, z_l),
                      arm_point(angle, 0, b_top, z_t), arm_point(angle, 0, -b_top, z_t)])
    direction = arm_point(angle, 1, 0, 0)
    plan_prism = extrude(plan, amount=u_far + 5, dir=(direction.X, direction.Y, 0))
    return side_prism & plan_prism


def build_upper_body(sk: Skeleton, g) -> list[Feature]:
    feats = [Feature("tube_outer", "upper", "base", tube_outer(sk, g), GROUP),
             Feature("tube_cavity", "upper", "cavity", tube_cavity(sk, g), GROUP)]
    if g.intake_enabled:
        for i, a in enumerate(sk.mid_angles()):
            feats.append(Feature(f"intake_{i}", "upper", "cut", intake(sk, g, a), GROUP))
    return feats
