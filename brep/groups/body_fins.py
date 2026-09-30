"""Gruppe `body_fins`: geneigter Aero-Fin Rumpf → Motor mit NACA-Tropfenprofil (Kap. 5).

Der Querschnitt (Vorderkante oben) wird entlang der geneigten Vorderkante verschoben; Dicke und
Vorderkantenhöhe sind linear in der Spannweite s, darum ist der Loft zwischen s = 0 und s = R_M exakt.
"""
from __future__ import annotations

from build123d import Part

from ..features import Feature
from ..geom import arm_section_face, halfspace_above, ruled_loft
from ..profiles import lerp, teardrop_outline
from ..skeleton import Skeleton

GROUP = "body_fins"


def span_fraction(sk: Skeleton, s: float) -> float:
    """λ(s) = 0 bei joint_radius, 1 bei motor_radius."""
    return (s - sk.joint_radius) / (sk.motor_radius - sk.joint_radius)


def section_outline(sk: Skeleton, g, s: float) -> list[tuple[float, float]]:
    lam = span_fraction(sk, s)
    z_le = sk.split_z + lerp(g.le_height_root, g.le_height_tip, lam)
    thickness = lerp(g.thickness_root, g.thickness_tip, lam)
    return [(q, z_le + dz) for q, dz in teardrop_outline(g.profile_chord, thickness, g.max_thickness_pos)]


def fin(sk: Skeleton, g, angle: float) -> Part:
    faces = [arm_section_face(angle, s, section_outline(sk, g, s), cant_deg=g.cant_angle, cant_z=sk.split_z)
             for s in (0.0, sk.motor_radius)]
    return ruled_loft(*faces) & halfspace_above(sk.split_z)


def sweep_angle_deg(sk: Skeleton, g) -> float:
    """Abgeleitete Pfeilung der Vorderkante (nur Anzeige)."""
    import math
    return math.degrees(math.atan2(g.le_height_root - g.le_height_tip, sk.motor_radius - sk.joint_radius))


def build_body_fins(sk: Skeleton, g) -> list[Feature]:
    return [Feature(f"fin_{i}", "upper", "add", fin(sk, g, a), GROUP) for i, a in enumerate(sk.arm_angles())]
