"""Parametrisches Oberteil (Rumpf + Ausleger + Gondeln + Nasenkappe), nachgebaut aus
'Mohammed_0.1 Full Shell.step'. Einheiten: mm, N, g. Ursprung = Rohrachse / Rohrunterkante."""
from __future__ import annotations

import copy
import math
import time
from dataclasses import asdict, dataclass, fields, replace

from build123d import (
    Align, Axis, Bezier, Box, BuildLine, BuildSketch, Circle, Color, Compound, Cylinder, Ellipse,
    EllipticalCenterArc, ExportDXF, ExportSVG, Face, GeomType, GridLocations, Line, LineType, Location,
    Mesher, Plane, PolarLocations, Polyline, Pos, RevoluteJoint, RigidJoint, Rot, SlotCenterToCenter,
    Spline, Text, Unit, export_gltf, export_step, export_stl, extrude, fillet, loft, make_face, offset,
    revolve, scale, sweep,
)

MIN = (Align.CENTER, Align.CENTER, Align.MIN)


@dataclass
class Params:
    body_radius: float = 33.0
    body_height: float = 117.0
    wall: float = 2.0
    slot_count: int = 2
    slot_width: float = 12.0
    slot_depth: float = 8.5
    fit_clearance: float = 0.3
    arm_count: int = 4
    arm_angle: float = 45.0
    arm_reach: float = 110.0
    arm_width: float = 13.0
    arm_thickness: float = 3.0
    gusset_height: float = 35.0
    gusset_length: float = 25.0
    pod_radius: float = 12.0
    pod_height: float = 28.0
    nose_length: float = 93.0
    nose_shape: float = 0.5
    edge_fillet: float = 1.0
    lightening_slots: int = 2
    pod_wall: float = 1.2
    cable_hole_d: float = 6.0
    engrave: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> "Params":
        out = cls()
        for f in fields(cls):
            if f.name in d and d[f.name] is not None:
                setattr(out, f.name, int(round(float(d[f.name]))) if f.type == "int" else float(d[f.name]))
        return out


# group, label, unit, min, max, step
PARAM_SPEC = {
    "body_radius":      ("Rumpf", "Rohr-Radius", "mm", 20, 70, 0.5),
    "body_height":      ("Rumpf", "Rohr-Höhe", "mm", 60, 220, 1),
    "wall":             ("Rumpf", "Wandstärke", "mm", 0.8, 5, 0.1),
    "slot_count":       ("Steckverbindung", "Anzahl Schlitze/Laschen", "", 1, 6, 1),
    "slot_width":       ("Steckverbindung", "Schlitzbreite", "mm", 4, 30, 0.5),
    "slot_depth":       ("Steckverbindung", "Schlitztiefe", "mm", 3, 20, 0.5),
    "fit_clearance":    ("Steckverbindung", "Passungsspiel", "mm", 0, 1, 0.05),
    "arm_count":        ("Ausleger", "Anzahl Ausleger", "", 3, 8, 1),
    "arm_angle":        ("Ausleger", "Winkel-Offset", "°", 0, 90, 1),
    "arm_reach":        ("Ausleger", "Reichweite (Achse→Motor)", "mm", 60, 260, 1),
    "arm_width":        ("Ausleger", "Auslegerbreite", "mm", 6, 30, 0.5),
    "arm_thickness":    ("Ausleger", "Auslegerstärke", "mm", 1.5, 12, 0.5),
    "gusset_height":    ("Ausleger", "Knotenblech Höhe", "mm", 0, 60, 1),
    "gusset_length":    ("Ausleger", "Knotenblech Länge", "mm", 0, 50, 1),
    "pod_radius":       ("Gondeln", "Gondel-Radius", "mm", 6, 30, 0.5),
    "pod_height":       ("Gondeln", "Gondel-Höhe", "mm", 10, 70, 1),
    "nose_length":      ("Nasenkappe", "Nasenlänge", "mm", 30, 200, 1),
    "nose_shape":       ("Nasenkappe", "Form-Exponent (0.5 Ogive … 1 Kegel)", "", 0.3, 1.0, 0.05),
    "edge_fillet":      ("Detail-Features", "Verrundung Motorplatten (0 = aus)", "mm", 0, 3, 0.1),
    "lightening_slots": ("Detail-Features", "Erleichterungs-Langlöcher je Arm", "", 0, 5, 1),
    "pod_wall":         ("Detail-Features", "Gondel-Wand (Shell, 0 = massiv)", "mm", 0, 4, 0.1),
    "cable_hole_d":     ("Detail-Features", "Kabeldurchführung Ø (0 = aus)", "mm", 0, 12, 0.5),
    "engrave":          ("Detail-Features", "Gravur „BOREAS“ (0/1)", "", 0, 1, 1),
}


def derived(p: Params) -> dict:
    """Abgeleitete (getriebene) Maße – diese sind keine freien Parameter."""
    return {
        "tab_width": p.slot_width - 2 * p.fit_clearance,
        "tab_height": p.slot_depth - p.fit_clearance,
        "spigot_outer_radius": p.body_radius - p.wall - p.fit_clearance,
        "nose_base_radius": p.body_radius,
        "pad_radius": p.pod_radius + 2.0,
        "inner_diameter": 2 * (p.body_radius - p.wall),
        "span": 2 * (p.arm_reach + p.pod_radius + 2.0),
        "total_height": p.body_height + p.nose_length,
    }


def arm_angles(p: Params) -> list[float]:
    return [p.arm_angle + i * 360 / p.arm_count for i in range(p.arm_count)]


# ---------------------------------------------------------------- Geometrie

def _snap(hist, title, op, code, shape, part="Rumpf"):
    if hist is not None:
        # Kopie: Joints verschieben das Originalobjekt später (connect_to), die Historie soll das nicht sehen
        hist.append({"title": title, "op": op, "code": code, "shape": copy.copy(shape), "part": part})


def _ring(r_out: float, r_in: float, h: float, z0: float):
    return Pos(0, 0, z0) * (Cylinder(r_out, h, align=MIN) - Cylinder(r_in, h, align=MIN))


def gusset_face(p: Params) -> Face:
    r0, t = p.body_radius - p.wall / 2, p.arm_thickness
    gh, gl = p.gusset_height, p.gusset_length
    a, b, c = (r0, 0, t), (r0, 0, t + gh), (r0 + gl, 0, t)
    return make_face([Line(a, b), Bezier(b, (r0 + 0.12 * gl, 0, t + 0.12 * gh), c), Line(c, a)])


def pod_profile(r: float, h: float):
    hc = 0.3 * h
    with BuildSketch(Plane.XZ) as sk:
        with BuildLine():
            Polyline((0, 0), (r, 0), (r, hc))
            EllipticalCenterArc((0, hc), r, h - hc, 0, arc_size=90)
            Line((0, h), (0, 0))
        make_face()
    return sk.sketch


def _pod(r: float, h: float):
    return revolve(pod_profile(r, h), Axis.Z)


def nose_profile(rb: float, length: float, k: float, ext: float = 0.0):
    pts = []
    for i in range(41):
        x = length * (i / 40) ** 2  # Abstand von der Spitze, dicht an der Spitze
        pts.append((rb * (x / length) ** k, length - x))
    with BuildSketch(Plane.XZ) as sk:
        with BuildLine():
            Spline(*pts)
            if ext > 0:
                Polyline((rb, 0), (rb, -ext), (0, -ext), (0, length))
            else:
                Polyline((rb, 0), (0, 0), (0, length))
        make_face()
    return sk.sketch


def lightening_slot_sketch(p: Params):
    """Langlöcher entlang eines Arms (lokal: Arm liegt auf +X)."""
    pad_r = derived(p)["pad_radius"]
    x0 = p.body_radius + (p.gusset_length if p.gusset_height >= 1 else 0) + 4
    x1 = p.arm_reach - pad_r - 3
    n = p.lightening_slots
    h = 0.45 * p.arm_width
    pitch = (x1 - x0) / max(n, 1)
    if n < 1 or pitch - 3 < h + 2:
        return None
    slots = [Pos((x0 + x1) / 2, 0) * loc * SlotCenterToCenter(pitch - 3 - h, h)
             for loc in GridLocations(pitch, 1, n, 1)]
    return slots


def engrave_angle(p: Params) -> float:
    step = 360 / p.arm_count
    mids = [p.arm_angle + (k + 0.5) * step for k in range(p.arm_count)]
    return min(mids, key=lambda a: abs(((a - 270) + 180) % 360 - 180))


def build_arm(p: Params, hist: list | None = None):
    """Ein einzelner Arm (lokal auf +X). Details werden hier auf einfacher Geometrie modelliert – schnell."""
    R, w, t = p.body_radius, p.wall, p.arm_thickness
    pad_r = derived(p)["pad_radius"]
    x0 = R - w / 2  # Arm beginnt in der Rohrwand, die Bohrung muss ihn nicht mehr schneiden
    arm = Pos((x0 + p.arm_reach) / 2, 0, t / 2) * Box(p.arm_reach - x0, p.arm_width, t)
    arm += Pos(p.arm_reach, 0, 0) * Cylinder(pad_r, t, align=MIN)
    _snap(hist, "Arm + Motorplatte", "Box ∪ Cylinder",
          "arm = Pos(...) * Box(L, b, t)\narm += Pos(L, 0, 0) * Cylinder(r_pad, t, align=MIN)", arm, "Arm")

    if p.edge_fillet > 0:
        edges = (arm.edges().filter_by(GeomType.CIRCLE)
                 .filter_by_position(Axis.Z, t - 0.01, t + 0.01)
                 .filter_by(lambda e: abs(e.radius - pad_r) < 0.01))
        try:
            arm = fillet(edges, min(p.edge_fillet, 0.9 * t))
            _snap(hist, "Verrundung Motorplatte", "Selektor → fillet",
                  "edges = arm.edges().filter_by(GeomType.CIRCLE)\n"
                  "    .filter_by_position(Axis.Z, t, t)\n    .filter_by(lambda e: e.radius == r_pad)\n"
                  "arm = fillet(edges, radius)", arm, "Arm")
        except Exception:
            pass

    if p.gusset_height >= 1 and p.gusset_length >= 1:
        arm += extrude(gusset_face(p), amount=p.arm_width / 2, both=True)
        _snap(hist, "Knotenblech", "Skizze (Bezier) → extrude",
              "face = make_face([Line(a, b), Bezier(b, ctrl, c), Line(c, a)])\n"
              "arm += extrude(face, amount=b/2, both=True)", arm, "Arm")

    slots = lightening_slot_sketch(p)
    if slots:
        arm = arm.cut(*[extrude(Pos(0, 0, -1) * s, amount=t + 2) for s in slots])
        _snap(hist, "Erleichterungs-Langlöcher", "SlotCenterToCenter + GridLocations → Cut",
              "slots = [loc * SlotCenterToCenter(l, h) for loc in GridLocations(pitch, 1, n, 1)]\n"
              "arm = arm.cut(*[extrude(s, amount=t) for s in slots])", arm, "Arm")
    return arm


def build_tube(p: Params, hist: list | None = None):
    R, H, w, t = p.body_radius, p.body_height, p.wall, p.arm_thickness
    tube = Cylinder(R, H, align=MIN) - Pos(0, 0, -1) * Cylinder(R - w, H + 2, align=MIN)
    _snap(hist, "Rohr (hohl)", "Cylinder − Cylinder", "tube = Cylinder(R, H) - Pos(0,0,-1) * Cylinder(R - wall, H + 2)", tube)

    slot = Pos(R, 0, H - p.slot_depth / 2 + 0.5) * Box(4 * w + 2, p.slot_width, p.slot_depth + 1)
    tube = tube.cut(*[loc * slot for loc in PolarLocations(0, p.slot_count).locations])
    _snap(hist, "Steckschlitze", "Boolean Cut + Muster",
          "tube = tube.cut(*[loc * slot for loc in PolarLocations(0, n_slots)])", tube)

    if p.cable_hole_d > 0:
        zh = t + (p.gusset_height if p.gusset_height >= 1 else 0) + p.cable_hole_d / 2 + 3
        hole = Pos(R, 0, zh) * Rot(0, 90, 0) * Cylinder(p.cable_hole_d / 2, 4 * w + 2)
        tube = tube.cut(*[loc * hole for loc in PolarLocations(0, p.arm_count, start_angle=p.arm_angle).locations])
        _snap(hist, "Kabeldurchführungen", "Boolean Cut (radiale Bohrung)",
              "hole = Pos(R, 0, z) * Rot(0, 90, 0) * Cylinder(d/2, 4*wall)\n"
              "tube = tube.cut(*[loc * hole for loc in PolarLocations(0, n, 45)])", tube)

    if p.engrave:
        depth = min(0.6, 0.4 * w)
        fs = min(0.12 * H, 0.42 * R)
        a = math.radians(engrave_angle(p))
        direction = (math.cos(a), math.sin(a), 0)
        plane = Plane(origin=(direction[0] * (R + 1), direction[1] * (R + 1), 0.55 * H),
                      x_dir=(-math.sin(a), math.cos(a), 0), z_dir=direction)
        txt = extrude(plane * Text("BOREAS", font_size=fs, rotation=90), amount=-(depth + 4))
        tube -= txt & (Cylinder(R + 2, H, align=MIN) - Cylinder(R - depth, H, align=MIN))
        _snap(hist, "Gravur", "Text → extrude → ∩ Ring → Cut",
              "txt = extrude(plane * Text('BOREAS', font_size=fs, rotation=90), amount=-4)\n"
              "tube -= txt & (Cylinder(R+2, H) - Cylinder(R-depth, H))", tube)
    return tube


def build_body(p: Params, hist: list | None = None):
    tube = build_tube(p, hist)
    arm = build_arm(p, hist)
    body = tube.fuse(*[loc * arm for loc in PolarLocations(0, p.arm_count, start_angle=p.arm_angle).locations])
    _snap(hist, "Arme verteilen & verschmelzen", "PolarLocations → fuse",
          "body = tube.fuse(*[loc * arm for loc in PolarLocations(0, n, start_angle=45)])", body)
    return body


def build_pods(p: Params, hist: list | None = None):
    pod = _pod(p.pod_radius, p.pod_height)
    _snap(hist, "Gondel-Profil drehen", "Skizze → revolve", "pod = revolve(profile_sketch, Axis.Z)", pod, "Gondeln")
    if p.pod_wall > 0:
        pod = offset(pod, amount=-p.pod_wall, openings=pod.faces().sort_by(Axis.Z)[0])
        _snap(hist, "Gondel aushöhlen", "offset/shell mit Öffnung",
              "pod = offset(pod, amount=-wall, openings=pod.faces().sort_by(Axis.Z)[0])", pod, "Gondeln")
    pods = None
    for loc in PolarLocations(p.arm_reach, p.arm_count, start_angle=p.arm_angle):
        placed = loc * Pos(0, 0, p.arm_thickness) * pod
        pods = placed if pods is None else pods + placed
    _snap(hist, "Gondeln verteilen", "PolarLocations",
          "for loc in PolarLocations(L, n, start_angle=45):\n    pods += loc * Pos(0,0,t) * pod", pods, "Gondeln")
    return pods


def build_nose(p: Params, hist: list | None = None):
    """Nasenkappe im eigenen Koordinatensystem (Basis bei z=0) – platziert wird per Joint."""
    d = derived(p)
    R, w = p.body_radius, p.wall
    outer = revolve(nose_profile(R, p.nose_length, p.nose_shape), Axis.Z)
    _snap(hist, "Nasenkappe: Spline-Profil drehen", "Spline → revolve",
          "outer = revolve(nose_profile(R, L, k), Axis.Z)", outer, "Nasenkappe")
    nose = outer - revolve(nose_profile(R - w, p.nose_length - w, p.nose_shape, ext=1), Axis.Z)
    _snap(hist, "Nasenkappe aushöhlen", "Boolean Cut", "nose = outer - revolve(inner_profile, Axis.Z)", nose, "Nasenkappe")
    r_sp = d["spigot_outer_radius"]
    spigot_h = d["tab_height"] + 4
    nose += _ring(R - w / 2, r_sp - w, w, 0)            # Bund, verbindet Kappe mit Zentrierring
    nose += _ring(r_sp, r_sp - w, spigot_h, -spigot_h)  # Zentrierring (sitzt im Rohr)
    _snap(hist, "Zentrierring", "Union", "nose += ring(r_spigot, r_spigot - wall, h)", nose, "Nasenkappe")
    th = d["tab_height"]
    ri = r_sp - w
    for loc in PolarLocations(0, p.slot_count):
        tab = Pos((R + ri) / 2, 0, -th / 2) * Box(R - ri, d["tab_width"], th)
        tab &= Pos(0, 0, -th) * Cylinder(R, th, align=MIN)
        nose += loc * tab
    _snap(hist, "Laschen (passend zu Schlitzen)", "Box ∩ Zylinder → Union",
          "tab = Box(...) & Cylinder(R, th)   # Laschenbreite = Schlitz − 2·Spiel\nnose += loc * tab", nose, "Nasenkappe")
    return nose


def propeller_sections(diameter: float) -> list:
    """Blatt-Querschnitte: Ellipsen, nach außen schmaler und flacher angestellt (Radius, Sehne, Anstellwinkel)."""
    r_tip = diameter / 2
    stations = [(4.0, 0.16, 32), (0.35 * r_tip, 0.22, 22), (0.7 * r_tip, 0.17, 14), (0.97 * r_tip, 0.08, 9)]
    sections = []
    for r, chord_f, pitch in stations:
        plane = Plane(origin=(r, 0, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0))
        # Dicke skaliert mit: zu flache Ellipsen (Seitenverhältnis > ~40) lassen den Loft scheitern
        sections.append(plane * Rot(0, 0, pitch) * Ellipse(chord_f * r_tip / 2, 0.9 * diameter / 127))
    return sections


def build_propeller(diameter: float):
    """Zweiblatt-Propeller: Blatt als Loft durch die verdrehten Querschnitte."""
    blade = loft(propeller_sections(diameter))
    return Pos(0, 0, -3) * Cylinder(4.5, 6, align=MIN) + blade + Rot(0, 0, 180) * blade


def cable_path(p: Params):
    R, w, t = p.body_radius, p.wall, p.arm_thickness
    pad_r = derived(p)["pad_radius"]
    gh = p.gusset_height if p.gusset_height >= 1 else 0
    gl = p.gusset_length if gh else 0
    zh = t + gh + p.cable_hole_d / 2 + 3
    r0 = R - w / 2
    pts = [(0.25 * R, 0, max(zh - 25, 4)), (R - w - 5, 0, zh), (R + 3, 0, zh)]
    if gh:
        # Bezier-Knotenblech verläuft bei u=0.5 durch (r0 + 0.31·gl, t + 0.31·gh) → Kabel mit Abstand darüber
        pts += [(r0 + 0.31 * gl + 3, 0, t + 0.31 * gh + 5), (r0 + gl + 3, 0, t + 3.5)]
    x_on, x_off = pts[-1][0] + 5, p.arm_reach - pad_r - 2
    if x_off > x_on:
        # dichte Stützpunkte, damit der Spline flach auf dem Arm liegt und nicht durchhängt
        k = max(2, int((x_off - x_on) / 8))
        pts += [(x_on + (x_off - x_on) * i / k, 0, t + 2.6) for i in range(k + 1)]
    pts.append((p.arm_reach - p.pod_radius - 1.5, 0, t + min(6, 0.3 * p.pod_height)))
    return Spline(*pts)


def build_cables(p: Params):
    path = cable_path(p)
    cable = sweep(Plane(origin=path @ 0, z_dir=path % 0) * Circle(min(1.6, p.cable_hole_d / 2 - 0.5)), path)
    cables = None
    for loc in PolarLocations(0, p.arm_count, start_angle=p.arm_angle):
        c = loc * cable
        cables = c if cables is None else cables + c
    return cables


PART_STYLE = {
    "Rumpf": (0.30, 0.72, 0.42),
    "Gondeln": (0.20, 0.55, 0.85),
    "Nasenkappe": (0.95, 0.52, 0.18),
    "Propeller": (0.85, 0.87, 0.90),
    "Kabel": (0.90, 0.25, 0.25),
}


_BODY_KEYS = ("body_radius", "body_height", "wall", "slot_count", "slot_width", "slot_depth", "arm_count", "arm_angle",
              "arm_reach", "arm_width", "arm_thickness", "gusset_height", "gusset_length", "pod_radius",
              "edge_fillet", "lightening_slots", "cable_hole_d", "engrave")
_POD_KEYS = ("pod_radius", "pod_height", "pod_wall", "arm_reach", "arm_count", "arm_angle", "arm_thickness")
_NOSE_KEYS = ("body_radius", "wall", "slot_count", "slot_width", "slot_depth", "fit_clearance", "nose_length", "nose_shape")
_MEMO: dict = {}


def _cached(fn, p: Params, keys: tuple, hist):
    """Nur neu bauen, was sich geändert hat (mit Bauhistorie wird immer frisch gebaut)."""
    if hist is not None:
        return fn(p, hist)
    key = (fn.__name__,) + tuple(getattr(p, k) for k in keys)
    if key not in _MEMO:
        if len(_MEMO) > 60:
            _MEMO.clear()
        _MEMO[key] = fn(p)
    return copy.copy(_MEMO[key])


def build(p: Params, hist: list | None = None, accessories: dict | None = None) -> dict:
    """accessories={'prop_diameter': 127, 'prop_angle': 0} baut zusätzlich Propeller (per Joint) und Kabel."""
    t0 = time.perf_counter()
    body = _cached(build_body, p, _BODY_KEYS, hist)
    pods = _cached(build_pods, p, _POD_KEYS, hist)
    nose = _cached(build_nose, p, _NOSE_KEYS, hist)

    RigidJoint("nose_seat", body, Location((0, 0, p.body_height)))
    RigidJoint("base", nose, Location((0, 0, 0)))
    body.joints["nose_seat"].connect_to(nose.joints["base"])

    parts = {"Rumpf": body, "Gondeln": pods, "Nasenkappe": nose}
    extra = {}
    if accessories:
        z_top = p.arm_thickness + p.pod_height + 1
        prop = build_propeller(accessories["prop_diameter"])
        props = []
        for i, a in enumerate(arm_angles(p)):
            c = (p.arm_reach * math.cos(math.radians(a)), p.arm_reach * math.sin(math.radians(a)), z_top)
            RevoluteJoint(f"motor{i}", body, axis=Axis(c, (0, 0, 1)))
            blade = copy.copy(prop)
            RigidJoint("hub", blade, Location((0, 0, 0)))
            body.joints[f"motor{i}"].connect_to(blade.joints["hub"], angle=(accessories.get("prop_angle", 0) + 90 * i) % 360)
            props.append(blade)
        extra["Propeller"] = Compound(children=props)
        if p.cable_hole_d > 0:
            extra["Kabel"] = build_cables(p)
    for name, part in {**parts, **extra}.items():
        part.label = name
        part.color = Color(*PART_STYLE[name])
    return {"parts": parts, "accessories": extra, "build_ms": (time.perf_counter() - t0) * 1000}


def section_cut(parts: dict) -> dict:
    cutter = Pos(0, -1000, 0) * Box(4000, 2000, 4000)
    return {k: v - cutter for k, v in parts.items()}


# ---------------------------------------------------------------- Analyse

def mass_properties(parts: dict, density_g_cm3: float) -> dict:
    out, tot_m, mom = {}, 0.0, [0.0, 0.0, 0.0]
    for name, part in parts.items():
        v = part.volume
        m = v / 1000 * density_g_cm3
        c = part.center()
        out[name] = {"volume_cm3": v / 1000, "mass_g": m, "area_cm2": part.area / 100}
        tot_m += m
        mom = [mom[0] + m * c.X, mom[1] + m * c.Y, mom[2] + m * c.Z]
    bb = Compound(list(parts.values())).bounding_box()
    return {
        "parts": out,
        "mass_g": tot_m,
        "cog": [x / tot_m for x in mom] if tot_m else [0, 0, 0],
        "bbox": [bb.size.X, bb.size.Y, bb.size.Z],
    }


def arm_deflection(p: Params, thrust_n: float, e_mpa: float) -> float:
    """Kragbalken: δ = F·L³ / (3·E·I), I = b·t³/12, freie Länge ab Rohrwand."""
    L = max(p.arm_reach - p.body_radius, 1.0)
    inertia = p.arm_width * p.arm_thickness ** 3 / 12
    return thrust_n * L ** 3 / (3 * e_mpa * inertia)


def check_constraints(p: Params, req: dict, mat: dict, limits: dict, structure_mass_g: float | None) -> list:
    d = derived(p)
    n = p.arm_count
    checks = []

    def add(name, value, limit, ok, unit="mm", hint=""):
        checks.append({"name": name, "value": value, "limit": limit, "ok": bool(ok), "unit": unit, "hint": hint})

    gap_body = p.arm_reach - d["pad_radius"] - p.body_radius
    add("Gondel ↔ Rumpf Abstand", gap_body, f"≥ {limits['min_margin']}", gap_body >= limits["min_margin"],
        hint="Reichweite erhöhen oder Gondel-Radius senken")
    prop = req["prop_diameter"]
    pp = round(2 * p.arm_reach * math.sin(math.pi / n) - prop, 6)  # sin(π/6)·2 ≠ 1 exakt in float
    add("Propeller ↔ Propeller", pp, f"≥ {limits['prop_gap']}", pp >= limits["prop_gap"],
        hint="Reichweite erhöhen oder weniger Ausleger")
    pb = p.arm_reach - prop / 2 - p.body_radius
    add("Propeller ↔ Rumpf", pb, f"≥ {limits['min_margin']}", pb >= limits["min_margin"], hint="Reichweite erhöhen")
    pd = d["inner_diameter"] - req["payload_diameter"]
    add("Nutzlast Ø passt ins Rohr", pd, "≥ 2", pd >= 2, hint="Rohr-Radius erhöhen / Wand dünner")
    pl = p.body_height - req["payload_length"]
    add("Nutzlast-Länge passt", pl, "≥ 5", pl >= 5, hint="Rohr-Höhe erhöhen")
    usage = p.slot_count * p.slot_width / (2 * math.pi * p.body_radius) * 100
    add("Schlitze belegen Umfang", usage, "≤ 35", usage <= 35, unit="%", hint="weniger/schmalere Schlitze")
    add("Laschenbreite (abgeleitet)", d["tab_width"], "≥ 4", d["tab_width"] >= 4, hint="Schlitz breiter oder weniger Spiel")
    add("Wandstärke druckbar", p.wall, f"≥ {limits['min_wall']}", p.wall >= limits["min_wall"])
    gus_end = p.body_radius + p.gusset_length
    free = p.arm_reach - d["pad_radius"] - gus_end
    add("Knotenblech ↔ Motorplatte", free, "≥ 2", free >= 2 or p.gusset_height < 1, hint="Knotenblech kürzer")
    delta = round(arm_deflection(p, req["thrust_per_motor"], mat["E"]), 6)
    add("Ausleger-Durchbiegung @ Vollschub", delta, f"≤ {limits['max_deflection']}", delta <= limits["max_deflection"],
        hint="Ausleger dicker/breiter oder steiferes Material")
    if structure_mass_g is not None:
        total = structure_mass_g + req["payload_mass"] + req["battery_mass"] + n * req["motor_mass"]
        twr = n * req["thrust_per_motor"] / (total * 9.81 / 1000)
        add("Schub/Gewicht (TWR)", twr, f"≥ {limits['min_twr']}", twr >= limits["min_twr"], unit="",
            hint=f"Abflugmasse {total:.0f} g")
    return checks


def _ceil(x: float, step: float) -> float:
    return math.ceil(x / step - 1e-9) * step


def autosize(req: dict, mat: dict, limits: dict, base: Params | None = None) -> Params:
    """Leitet einen gültigen Parametersatz aus den Anforderungen ab (einfacher, geschlossener 'Solver')."""
    p = replace(base or Params())
    n = int(req["arm_count"])
    p.arm_count = n
    p.body_radius = _ceil(req["payload_diameter"] / 2 + 1.0 + p.wall, 0.5)
    p.body_height = _ceil(req["payload_length"] + 7, 1)
    p.pod_radius = _ceil(req["motor_diameter"] / 2 + 1.5, 0.5)
    p.pod_height = _ceil(p.pod_radius * 2.3, 1)
    pad_r = p.pod_radius + 2
    s = math.sin(math.pi / n)
    p.arm_reach = _ceil(max(
        (req["prop_diameter"] + limits["prop_gap"]) / (2 * s),
        p.body_radius + req["prop_diameter"] / 2 + limits["min_margin"],
        p.body_radius + pad_r + limits["min_margin"],
    ), 1)
    p.arm_width = max(p.arm_width, _ceil(p.pod_radius * 1.1, 0.5))
    L = p.arm_reach - p.body_radius
    t = (4 * req["thrust_per_motor"] * L ** 3 / (mat["E"] * p.arm_width * limits["max_deflection"])) ** (1 / 3)
    p.arm_thickness = min(max(_ceil(t, 0.5), 2.0), 12.0)
    p.gusset_height = min(35.0, _ceil(0.3 * p.body_height, 1))
    p.gusset_length = max(0.0, min(25.0, math.floor(p.arm_reach - pad_r - p.body_radius - 4)))
    p.slot_width = min(p.slot_width, math.floor(0.3 * 2 * math.pi * p.body_radius / p.slot_count))
    p.nose_length = _ceil(2.8 * p.body_radius, 1)
    return p


# ---------------------------------------------------------------- Mesh / Export

def _tessellate(shape, tol: float, ang: float):
    try:
        return shape.tessellate(tol, ang)
    except AttributeError:
        # Importierte Flächenmodelle enthalten teils Flächen ohne Triangulierung → einzeln, defekte überspringen
        verts, tris = [], []
        for face in shape.faces():
            try:
                v, t = face.tessellate(tol, ang)
            except AttributeError:
                continue
            off = len(verts)
            verts += v
            tris += [(a + off, b + off, c + off) for a, b, c in t]
        return verts, tris


def edge_segments(edges) -> list:
    seg = []
    for e in edges:
        n = 1 if e.geom_type.name == "LINE" else max(8, min(48, int(e.length / 2)))
        pts = e.positions([i / n for i in range(n + 1)])
        for a, b in zip(pts[:-1], pts[1:]):
            seg += [round(a.X, 3), round(a.Y, 3), round(a.Z, 3), round(b.X, 3), round(b.Y, 3), round(b.Z, 3)]
    return seg


def mesh(shape, tol: float = 0.08, ang: float = 0.15, with_edges: bool = True) -> dict:
    verts, tris = _tessellate(shape, tol, ang)
    out = {
        "vertices": [round(c, 3) for v in verts for c in (v.X, v.Y, v.Z)],
        "triangles": [i for t in tris for i in t],
    }
    if with_edges:
        out["edges"] = edge_segments(shape.edges())
    return out


def assembly(parts: dict) -> Compound:
    c = Compound(children=list(parts.values()))
    c.label = "Boreas_Oberteil_Variante"
    return c


def export(parts: dict, fmt: str, path: str, p: Params | None = None, meta: dict | None = None) -> None:
    asm = assembly(parts)
    if fmt == "step":
        export_step(asm, path)
    elif fmt == "stl":
        export_stl(asm, path, tolerance=0.05, angular_tolerance=0.2)
    elif fmt == "glb":
        export_gltf(asm, path, binary=True)
    elif fmt == "3mf":
        m = Mesher()
        for part in parts.values():
            m.add_shape(part, linear_deflection=0.05, angular_deflection=0.2)
        m.write(path)
    elif fmt == "dxf":
        p_body = parts["Rumpf"]
        z = p_body.bounding_box().min.Z + 0.5
        sec = p_body.intersect(Face.make_rect(4000, 4000, Plane.XY.offset(z)))
        sec = sec if isinstance(sec, (list, tuple)) else [sec]
        dxf = ExportDXF(unit=Unit.MM)
        dxf.add_layer("Kontur")
        dxf.add_shape([Pos(0, 0, -z) * e for s in sec for e in s.edges()], layer="Kontur")
        dxf.write(path)
    elif fmt == "svg":
        import drawing
        drawing.drawing_svg(p or Params(), path, meta)
    else:
        raise ValueError(fmt)


def fast_projection(shape, origin, up, look_at, tol: float = 0.05):
    """Polygonales Hidden-Line-Removal (OCCT HLRBRep_PolyAlgo). Das exakte Verfahren hinter
    project_to_viewport braucht bei Zylinder-Zylinder-Verschneidungen (Kabelbohrungen) >10 s."""
    import numpy as np
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.HLRBRep import HLRBRep_PolyAlgo, HLRBRep_PolyHLRToShape

    z = np.subtract(origin, look_at).astype(float)
    z /= np.linalg.norm(z)
    x = np.cross(up, z)
    x /= np.linalg.norm(x)
    BRepMesh_IncrementalMesh(shape.wrapped, tol, False, 0.2, True)
    algo = HLRBRep_PolyAlgo()
    algo.Load(shape.wrapped)
    algo.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(*look_at), gp_Dir(*z), gp_Dir(*x))))
    algo.Update()
    hlr = HLRBRep_PolyHLRToShape()
    hlr.Update(algo)

    from OCP.BRepLib import BRepLib

    def edges(*compounds):
        out = []
        for c in compounds:
            if c is None or c.IsNull():
                continue
            BRepLib.BuildCurves3d_s(c)
            out += [e for e in Compound(c).edges() if e.length > 1e-6]
        return out

    visible = edges(hlr.VCompound(), hlr.OutLineVCompound(), hlr.Rg1LineVCompound())
    hidden = edges(hlr.HCompound(), hlr.OutLineHCompound())
    return visible, hidden


if __name__ == "__main__":
    prm = Params()
    h: list = []
    res = build(prm, hist=h, accessories={"prop_diameter": 127})
    for k, v in {**res["parts"], **res["accessories"]}.items():
        print(k, "valid", v.is_valid, "vol cm³", round(v.volume / 1000, 2))
    print("build ms", round(res["build_ms"]), "history steps", [s["title"] for s in h])
