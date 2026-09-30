"""Gruppe `arms`: Steg unter dem Fin (Oberteil) und V-Kiel mit gestufter Oberseite (Unterteil). Kap. 3."""
from __future__ import annotations

import math

from build123d import Box, Cylinder, Part, Pos, Rot

from ..features import Feature
from ..geom import arm_section_face, ring, ruled_loft
from ..skeleton import Skeleton

GROUP = "arms"


def _arm_box(angle: float, s0: float, s1: float, width: float, z0: float, z1: float) -> Part:
    """Quader im Armsystem: s0…s1 (Spannweite), |q| ≤ width/2, z0…z1."""
    box = Pos((s0 + s1) / 2, 0, (z0 + z1) / 2) * Box(s1 - s0, width, z1 - z0)
    return Rot(0, 0, angle) * box


def web(sk: Skeleton, g, angle: float) -> Part:
    r_end = sk.motor_radius - g.web_end_offset
    z0 = sk.split_z
    bar = _arm_box(angle, g.web_start - 5, r_end + 5, g.web_width, z0 - g.web_depth, z0)
    return bar & ring(r_end, g.web_start, z0 - g.web_depth - 1, z0 + 1)


def keel_apex_height(sk: Skeleton, g, s: float) -> float:
    """H_k(s): Höhe Kiel-Grundoberkante → V-Spitze (linear in s)."""
    s_end = sk.motor_radius - g.keel_end_radius
    t = (s - sk.joint_radius) / (s_end - sk.joint_radius)
    return g.keel_height_root + (g.keel_height_tip - g.keel_height_root) * t


def keel(sk: Skeleton, g, angle: float, motor) -> Part:
    z_k = sk.split_z - g.keel_top_offset
    has_pad = g.pad_length > 0 and g.pad_height > 0
    z_top = z_k + (g.pad_height if has_pad else 0.0)
    tan_a = math.tan(math.radians(g.keel_half_angle))

    def triangle(s: float):
        z_ap = z_k - keel_apex_height(sk, g, s)
        hw = (z_top - z_ap) * tan_a
        return arm_section_face(angle, s, [(-hw, z_top), (0.0, z_ap), (hw, z_top)], spline=False)

    body = ruled_loft(triangle(0.0), triangle(sk.motor_radius))
    pad_end = g.pad_start + g.pad_length
    if has_pad:
        body -= _arm_box(angle, -10, g.pad_start, 200, z_k, z_top + 5)
        body -= _arm_box(angle, pad_end, sk.motor_radius + 10, 200, z_k - g.tip_drop, z_top + 5)
    elif g.tip_drop > 0:
        body -= _arm_box(angle, pad_end, sk.motor_radius + 10, 200, z_k - g.tip_drop, z_top + 5)
    body -= Pos(motor.X, motor.Y, z_k - 50) * Cylinder(g.keel_end_radius, 120)
    return body


def build_arms(sk: Skeleton, g) -> list[Feature]:
    feats = []
    for i, (a, m) in enumerate(zip(sk.arm_angles(), sk.motor_positions())):
        if g.web_depth > 0:
            feats.append(Feature(f"web_{i}", "upper", "add", web(sk, g, a), GROUP))
        feats.append(Feature(f"keel_{i}", "lower", "add", keel(sk, g, a, m), GROUP))
    return feats
