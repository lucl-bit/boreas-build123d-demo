"""Skelett (Master-Geometrie): die Schnittstellenmasse, die alle Gruppen gemeinsam nutzen.

Siehe docs/geometrie_definition.md, Kapitel 0. Das Skelett kennt nur die Gruppe `skeleton` der Spec.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from build123d import Location, Plane, Vector


@dataclass(frozen=True)
class Skeleton:
    arm_count: int
    arm_angle_offset: float
    arm_splay: float
    motor_radius: float
    split_z: float
    joint_radius: float
    nose_joint_z: float
    nose_joint_radius: float
    body_bottom_z: float

    @classmethod
    def from_params(cls, g) -> "Skeleton":
        """`g` = GroupParams der Gruppe 'skeleton'."""
        return cls(int(g.arm_count), g.arm_angle_offset, g.arm_splay, g.motor_radius, g.split_z,
                   g.joint_radius, g.nose_joint_z, g.nose_joint_radius, g.body_bottom_z)

    # ---------------------------------------------------------------- abgeleitete Grössen
    @property
    def tube_height(self) -> float:
        """Höhe des Oberteil-Rohrs (Trennebene → Nasen-Anschluss)."""
        return self.nose_joint_z - self.split_z

    @property
    def lower_length(self) -> float:
        return self.split_z - self.body_bottom_z

    def nominal_angles(self) -> list[float]:
        """ψᵢ – ungespreizte Teilung (Kerben/Laschen Oberteil↔Unterteil)."""
        return [self.arm_angle_offset + i * 360.0 / self.arm_count for i in range(self.arm_count)]

    def arm_angles(self) -> list[float]:
        """θᵢ – gespreizte Armwinkel (Motoren, Fins, Kiele, Heckflossen)."""
        return [a + (-1) ** i * self.arm_splay for i, a in enumerate(self.nominal_angles())]

    def mid_angles(self) -> list[float]:
        """φᵢ – Winkel zwischen zwei Armen (Kühlluft-Einlässe)."""
        return [self.arm_angle_offset + (i + 0.5) * 360.0 / self.arm_count for i in range(self.arm_count)]

    def motor_positions(self) -> list[Vector]:
        return [Vector(self.motor_radius * math.cos(math.radians(a)), self.motor_radius * math.sin(math.radians(a)),
                       self.split_z) for a in self.arm_angles()]

    @staticmethod
    def radial_location(angle_deg: float, radius: float = 0.0, z: float = 0.0) -> Location:
        """Lokales System mit X = radial (Winkel), Y = quer, Z = oben."""
        a = math.radians(angle_deg)
        return Location(Plane(origin=(radius * math.cos(a), radius * math.sin(a), z),
                              x_dir=(math.cos(a), math.sin(a), 0), z_dir=(0, 0, 1)))

    def arm_locations(self) -> list[Location]:
        """Armsystem je Arm: X = Spannweite s, Y = quer q, Z = z (Ursprung auf der Rumpfachse, z = 0)."""
        return [self.radial_location(a) for a in self.arm_angles()]
