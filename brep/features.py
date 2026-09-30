"""Feature = ein Rohkörper einer Gruppe mit Ziel-Teil und Rolle in der Bool-Reihenfolge.

Rollen (Reihenfolge in `assembly.combine`):
    base   – Grundkörper (vereinigt)
    add    – wird vereinigt
    cavity – wird danach abgezogen (Hohlräume, auch Teile anderer Features darin verschwinden)
    attach – wird nach den Hohlräumen vereinigt (z. B. Laschen, die in einen Hohlraum ragen dürfen)
    cut    – wird zuletzt abgezogen (Einlässe, Schlitze, Kerben)
"""
from __future__ import annotations

from dataclasses import dataclass

from build123d import Part

ROLES = ("base", "add", "cavity", "attach", "cut")
PARTS = ("upper", "lower", "nose", "nose_insert")


@dataclass
class Feature:
    name: str
    part: str
    role: str
    shape: Part
    group: str = ""

    def __post_init__(self):
        if self.part not in PARTS:
            raise ValueError(f"Feature {self.name}: unbekanntes Teil '{self.part}'")
        if self.role not in ROLES:
            raise ValueError(f"Feature {self.name}: unbekannte Rolle '{self.role}'")
