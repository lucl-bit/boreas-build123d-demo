"""Gruppe `details`: Nachbearbeitung auf Teil-Ebene (Kap. 10) – Verrundungen und Gravur.

Anders als die übrigen Gruppen erzeugt `details` keine Rohkörper, sondern verändert fertige Teile. Die Kanten
werden rein geometrisch über Selektoren gefunden (Skelett + Topologie), nicht über fremde Parameter.
Misslingt eine Operation (typisch bei Fillets), bleibt das Teil unverändert und es gibt eine Notiz.
"""
from __future__ import annotations

import math

from build123d import Face, GeomType, Part, Plane, Text, extrude, fillet

from ..skeleton import Skeleton

GROUP = "details"


def pod_junction_edges(sk: Skeleton, upper: Part):
    """Je Motorachse die Kreiskanten mit dem grössten Radius oberhalb der Trennebene (= Sockel/Ogive)."""
    circles = upper.edges().filter_by(GeomType.CIRCLE)
    out = []
    for m in sk.motor_positions():
        on_axis = [e for e in circles
                   if math.hypot(e.arc_center.X - m.X, e.arc_center.Y - m.Y) < 1e-3 and e.arc_center.Z > sk.split_z + 0.01]
        if on_axis:
            r_max = max(e.radius for e in on_axis)
            out += [e for e in on_axis if abs(e.radius - r_max) < 1e-6]
    return out


def main_cone_face(lower: Part) -> Face | None:
    cones = lower.faces().filter_by(GeomType.CONE)
    return max(cones, key=lambda f: f.area) if cones else None


def tail_root_edges(lower: Part):
    """Schnittkanten Heckflosse/Kegel: Kanten (keine Kreise/Geraden), die ganz auf der grössten Kegelfläche liegen."""
    cone = main_cone_face(lower)
    if cone is None:
        return []
    out = []
    for e in lower.edges():
        if e.geom_type in (GeomType.CIRCLE, GeomType.LINE):
            continue
        if all(cone.distance_to(e @ t) < 1e-3 for t in (0.0, 0.25, 0.5, 0.75, 1.0)):
            out.append(e)
    return out


def _safe_fillet(part: Part, edges, radius: float, label: str) -> tuple[Part, str]:
    if not edges:
        return part, f"{label}: keine passenden Kanten gefunden"
    try:
        out = fillet(edges, radius)
    except Exception as exc:  # OCCT wirft StdFail_NotDone u. ä.
        return part, f"{label} r={radius} fehlgeschlagen ({type(exc).__name__}, {len(edges)} Kanten)"
    if not out.is_valid:
        return part, f"{label} r={radius}: Ergebnis ungültig, verworfen"
    return out, f"{label} r={radius} an {len(edges)} Kanten"


def engrave(sk: Skeleton, lower: Part, depth: float = 0.6) -> Part:
    """Schriftzug BOREAS auf der Kegelflanke zwischen zwei Heckflossen (Tiefe ab Kegelfläche)."""
    angle = math.radians(sk.arm_angle_offset + 180.0 / sk.arm_count)
    z_mid = sk.split_z + (sk.body_bottom_z - sk.split_z) * 0.45
    d = (math.cos(angle), math.sin(angle), 0.0)
    cone = main_cone_face(lower)
    probe = (d[0] * 200, d[1] * 200, z_mid)
    r = math.hypot(*cone.find_intersection_points if False else (0, 0)) if False else None
    # Radius der Kegelfläche in dieser Richtung: nächster Punkt der Kegelfläche zum Fernpunkt
    near = cone.closest_points(probe)[0] if hasattr(cone, "closest_points") else None
    r = math.hypot(near.X, near.Y) if near is not None else 20.0
    plane = Plane(origin=(d[0] * (r + 2), d[1] * (r + 2), z_mid), x_dir=(-d[1], d[0], 0), z_dir=d)
    text = extrude(plane * Text("BOREAS", font_size=8, rotation=90), amount=-(2 + depth))
    return lower - text


def apply_details(sk: Skeleton, g, parts: dict) -> tuple[dict, list[str]]:
    notes: list[str] = []
    parts = dict(parts)
    if g.pod_fillet > 0 and "upper" in parts:
        parts["upper"], note = _safe_fillet(parts["upper"], pod_junction_edges(sk, parts["upper"]), g.pod_fillet,
                                            "Gondel-Verrundung")
        notes.append(note)
    if g.tail_root_fillet > 0 and "lower" in parts:
        parts["lower"], note = _safe_fillet(parts["lower"], tail_root_edges(parts["lower"]), g.tail_root_fillet,
                                            "Heckflossen-Wurzel")
        notes.append(note)
    if g.engrave and "lower" in parts:
        try:
            parts["lower"] = engrave(sk, parts["lower"])
            notes.append("Gravur BOREAS")
        except Exception as exc:
            notes.append(f"Gravur fehlgeschlagen ({type(exc).__name__})")
    return parts, notes
