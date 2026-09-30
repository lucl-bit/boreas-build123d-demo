"""Reine Mathematik der Profile (ohne CAD): identisch zu docs/geometrie_definition.md, Kapitel 0.

Diese Funktionen sind die „Single Source of Truth“ der Formen; das B-rep-Modell legt Splines durch
ihre Stützpunkte, der Voxel-Nachbau kann sie direkt als Abstandsfunktion auswerten.
"""
from __future__ import annotations

import math

NACA_AT_MAX = 0.2969 * math.sqrt(0.3) - 0.1260 * 0.3 - 0.3516 * 0.09 + 0.2843 * 0.027 - 0.1015 * 0.0081


def naca_n(x: float) -> float:
    """NACA-4-Ziffern-Dickenverteilung ohne Vorfaktor (x = 0…1)."""
    x = min(max(x, 0.0), 1.0)
    return 0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1015 * x ** 4


def warp(x: float, p: float) -> float:
    """Verschiebt das Dickenmaximum von x = 0.3 nach x = p (stückweise linear, C¹ bei p)."""
    return 0.3 * x / p if x <= p else 0.3 + 0.7 * (x - p) / (1.0 - p)


def teardrop_half_thickness(depth: float, chord: float, thickness: float, max_pos: float) -> float:
    """Halbe Dicke h(δ) des Tropfenprofils in der Tiefe δ unter der Vorderkante."""
    return 0.5 * thickness * naca_n(warp(depth / chord, max_pos)) / NACA_AT_MAX


def cosine_stations(count: int) -> list[float]:
    """0…1, dicht an beiden Enden (für Profil-Stützpunkte)."""
    return [0.5 * (1.0 - math.cos(math.pi * k / count)) for k in range(count + 1)]


def teardrop_outline(chord: float, thickness: float, max_pos: float, stations: int = 40) -> list[tuple[float, float]]:
    """Geschlossene Kontur (q, −δ) von der Hinterkante links über die Vorderkante zur Hinterkante rechts."""
    half = [(teardrop_half_thickness(chord * t, chord, thickness, max_pos), -chord * t) for t in cosine_stations(stations)]
    left = [(-h, z) for h, z in reversed(half)]
    right = [(h, z) for h, z in half[1:]]
    return left + right


def power_ogive(zeta: float, radius: float, m: float, k: float) -> float:
    """ρ(ζ) = R·(1 − ζ^m)^k, ζ ∈ [0, 1] (Nase: m, k frei; Gondel: m = 1)."""
    zeta = min(max(zeta, 0.0), 1.0)
    return radius * max(1.0 - zeta ** m, 0.0) ** k


def ogive_stations(count: int = 60) -> list[float]:
    """ζ-Stützstellen, dicht an der Spitze (ζ → 1)."""
    return [1.0 - (1.0 - j / count) ** 2 for j in range(count + 1)]


def barrel_radius(zeta: float, r_bottom: float, r_top: float, bulge: float, bulge_pos: float) -> float:
    """Fassform des Oberteil-Rohrs: Gerade + bulge·sin(π·ζ^q), Maximum bei ζ = bulge_pos."""
    q = math.log(0.5) / math.log(bulge_pos)
    zeta = min(max(zeta, 0.0), 1.0)
    return r_bottom + (r_top - r_bottom) * zeta + bulge * math.sin(math.pi * zeta ** q)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
