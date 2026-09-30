"""Gruppe `tail_fins`: gepfeilte Heckflossen mit NACA-Tropfenprofil (Kap. 7)."""
from __future__ import annotations

import math

from build123d import Axis, Face, Line, Part, ThreePointArc, Wire, revolve

from ..features import Feature
from ..geom import arm_section_face, ruled_loft
from ..profiles import lerp, teardrop_outline
from ..skeleton import Skeleton

GROUP = "tail_fins"
CLIP_HEIGHT = 500.0


def bottom_z(sk: Skeleton, g) -> float:
    return sk.body_bottom_z + g.bottom_offset


def leading_edge_z(sk: Skeleton, g, s: float) -> float:
    return bottom_z(sk, g) + g.tip_chord + (g.span_radius - s) * math.tan(math.radians(g.sweep_angle))


def section_outline(sk: Skeleton, g, s: float) -> list[tuple[float, float]]:
    lam = (s - sk.joint_radius) / (g.span_radius - sk.joint_radius)
    thickness = lerp(g.thickness_root, g.thickness_tip, lam)
    z_le = leading_edge_z(sk, g, s)
    return [(q, z_le + dz) for q, dz in teardrop_outline(g.profile_chord, thickness, g.max_thickness_pos)]


def planform_clip(sk: Skeleton, g) -> Part:
    """Rotationskörper: ρ ≤ span_radius, z ≥ Unterkante, Ecke mit corner_radius gerundet."""
    zb, rs, rc = bottom_z(sk, g), g.span_radius, g.corner_radius
    top = zb + CLIP_HEIGHT
    p = lambda r, z: (r, 0, z)  # noqa: E731 – Punkt in der XZ-Ebene
    if rc > 0:
        c45 = 1 - math.sqrt(0.5)
        edges = [Line(p(0, zb), p(rs - rc, zb)),
                 ThreePointArc(p(rs - rc, zb), p(rs - rc * c45, zb + rc * c45), p(rs, zb + rc)),
                 Line(p(rs, zb + rc), p(rs, top))]
    else:
        edges = [Line(p(0, zb), p(rs, zb)), Line(p(rs, zb), p(rs, top))]
    edges += [Line(p(rs, top), p(0, top)), Line(p(0, top), p(0, zb))]
    return revolve(Face(Wire(edges)), Axis.Z, 360)


def tail_fin(sk: Skeleton, g, angle: float, clip: Part) -> Part:
    faces = [arm_section_face(angle, s, section_outline(sk, g, s)) for s in (0.0, g.span_radius + 5)]
    return ruled_loft(*faces) & clip


def build_tail_fins(sk: Skeleton, g) -> list[Feature]:
    clip = planform_clip(sk, g)
    return [Feature(f"tail_fin_{i}", "lower", "add", tail_fin(sk, g, a, clip), GROUP)
            for i, a in enumerate(sk.arm_angles())]
