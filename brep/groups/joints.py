"""Gruppe `joints`: Schlitz/Lasche Nase↔Oberteil, Kerbe/Lasche Oberteil↔Unterteil (Kap. 9).

Laschenmasse sind abgeleitet (Schlitz − Spiel) und keine freien Parameter.
"""
from __future__ import annotations

import math

from build123d import Box, Part, Pos, Rot

from ..features import Feature
from ..geom import ring, sector
from ..skeleton import Skeleton

GROUP = "joints"


def derived(sk: Skeleton, g) -> dict[str, float]:
    """Abgeleitete Masse (werden im Bericht/der Zeichnung ausgegeben)."""
    r_mid = sk.joint_radius - g.upper_tab_thickness / 2
    return {
        "nose_tab_width": g.nose_slot_width - 2 * g.clearance,
        "nose_tab_height": g.nose_slot_depth - g.clearance,
        "upper_tab_half_angle": g.rim_notch_half_angle - math.degrees(g.clearance / r_mid),
        "upper_tab_height": g.rim_notch_depth - g.clearance,
    }


def nose_angles(g) -> list[float]:
    return [g.nose_tab_angle + k * 360.0 / g.nose_tab_count for k in range(int(g.nose_tab_count))]


def nose_slot(sk: Skeleton, g, angle: float) -> Part:
    r0 = sk.nose_joint_radius - g.nose_tab_thickness - g.clearance
    z0 = sk.nose_joint_z - g.nose_slot_depth
    length = 20.0
    box = Pos(r0 + length / 2, 0, z0 + 10) * Box(length, g.nose_slot_width, 20)
    return Rot(0, 0, angle) * box


def nose_tab(sk: Skeleton, g, angle: float) -> Part:
    d = derived(sk, g)
    z1 = sk.nose_joint_z
    z0 = z1 - d["nose_tab_height"]
    r_out, r_in = sk.nose_joint_radius, sk.nose_joint_radius - g.nose_tab_thickness
    band = Rot(0, 0, angle) * (Pos(r_out / 2 + 1, 0, (z0 + z1) / 2) * Box(r_out + 2, d["nose_tab_width"], z1 - z0))
    return band & ring(r_out, r_in, z0, z1)


def rim_notch(sk: Skeleton, g, angle: float) -> Part:
    z0 = sk.split_z - g.rim_notch_depth
    return sector(angle, g.rim_notch_half_angle, sk.joint_radius + g.rim_notch_margin, z0, sk.split_z + 5)


def upper_tab(sk: Skeleton, g, angle: float) -> Part:
    d = derived(sk, g)
    return sector(angle, d["upper_tab_half_angle"], sk.joint_radius, sk.split_z - d["upper_tab_height"], sk.split_z,
                  r_in=sk.joint_radius - g.upper_tab_thickness)


def build_joints(sk: Skeleton, g) -> list[Feature]:
    feats = []
    for k, a in enumerate(nose_angles(g)):
        feats.append(Feature(f"nose_slot_{k}", "upper", "cut", nose_slot(sk, g, a), GROUP))
        feats.append(Feature(f"nose_tab_{k}", "nose", "attach", nose_tab(sk, g, a), GROUP))
    for i, a in enumerate(sk.nominal_angles()):
        feats.append(Feature(f"rim_notch_{i}", "lower", "cut", rim_notch(sk, g, a), GROUP))
        if g.upper_tab_enabled:
            feats.append(Feature(f"upper_tab_{i}", "upper", "attach", upper_tab(sk, g, a), GROUP))
    return feats
