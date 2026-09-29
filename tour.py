"""Geführte Feature-Tour: jeder Schritt zeigt eine build123d-Fähigkeit am Boreas-Oberteil."""
from __future__ import annotations

import inspect
import math
import os
import shutil
import time
from collections import Counter
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np
from build123d import (
    Align, Axis, BuildPart, Compound, CounterBoreHole, Cylinder, GeomType, Hole, Locations, Plane,
    PolarLocations, Pos, Rot, SortBy, Text, chamfer, import_step,
)

import analysis as an
import boreas_upper as bu
from payload import C, chart, ds, f, ghost, item, lines, marker, parts_items, polyline, triad

ORIG_AXIS = (679.75, 23.2, 1303.0)   # Rohrachse und Rohrunterkante im STEP
ORIG_NOSE_DROP = 90.0                # Nasenkappe liegt im STEP 90 mm „explodiert“ über dem Rohr


@dataclass
class Ctx:
    p: bu.Params
    req: dict
    mat: dict
    mat_key: str
    cfg: dict
    opts: dict
    root: Path


_CACHE: dict = {}


def _key(p: bu.Params) -> tuple:
    return tuple(asdict(p).items())


def src(*fns) -> dict:
    return {"lang": "python", "text": "\n\n".join(inspect.getsource(fn).rstrip() for fn in fns)}


def code(text: str, lang: str = "python") -> dict:
    return {"lang": lang, "text": inspect.cleandoc(text) if lang == "python" else text}


def load_original(step_path: Path):
    if "orig" not in _CACHE:
        t0 = time.perf_counter()
        shape = import_step(str(step_path))
        _CACHE["orig"] = (shape, (time.perf_counter() - t0) * 1000)
    return _CACHE["orig"]


def original_local(step_path: Path) -> dict:
    """Original-Teile ins lokale Koordinatensystem (Rohrachse = Z, Rohrunterkante = 0)."""
    shape, _ = load_original(step_path)
    lower, upper = shape.children
    nose, inner, body = upper.shells()
    to_local = Pos(-ORIG_AXIS[0], -ORIG_AXIS[1], -ORIG_AXIS[2])
    drop = Pos(0, 0, -ORIG_NOSE_DROP)
    return {"Rumpf": to_local * body, "Innenschale": drop * (to_local * inner),
            "Nasenkappe": drop * (to_local * nose), "Unterteil": to_local * lower}


def build(ctx: Ctx, p: bu.Params | None = None, accessories: bool = False) -> dict:
    p = p or ctx.p
    return bu.build(p, accessories={"prop_diameter": ctx.req["prop_diameter"]} if accessories else None)


# ================================================================== Kapitel 1 · Daten rein

TYPE_COLORS = {"PLANE": C["blue"], "CYLINDER": C["green"], "BSPLINE": C["orange"], "TORUS": C["violet"],
               "CONE": C["yellow"], "SPHERE": C["pink"]}


def s_import(ctx: Ctx) -> dict:
    shape, ms = load_original(ctx.root / "Mohammed_0.1 Full Shell.step")
    local = original_local(ctx.root / "Mohammed_0.1 Full Shell.step")
    groups: dict = {}
    for name, sh in local.items():
        for face in sh.faces():
            groups.setdefault(face.geom_type.name, []).append(face)
    items = [item(f"type:{t}", Compound(fs), TYPE_COLORS.get(t, C["grey"]), edges=False, tol=0.25)
             for t, fs in groups.items()]
    lower, upper = shape.children
    rows = []
    for label, obj in [("Boreal_first_step (Unterteil)", lower), ("COMPOUND (Oberteil)", upper)]:
        rows.append([label, type(obj).__name__, len(obj.solids()), len(obj.shells()), len(obj.faces()),
                     len(obj.edges()), "Volumenkörper" if obj.solids() else "nur Flächen"])
    counts = Counter(fc.geom_type.name for fc in shape.faces())
    return {
        "items": items,
        "legend": [[t.title(), TYPE_COLORS.get(t, C["grey"])] for t in groups],
        "stats": [["Importzeit", f(ms, 0, "ms")], ["Flächen gesamt", str(len(shape.faces()))],
                  ["Kanten", str(len(shape.edges()))], ["Volumenkörper", str(len(shape.solids()))]],
        "table": {"head": ["Teil", "Typ", "Solids", "Shells", "Flächen", "Kanten", "Art"], "rows": rows},
        "charts": [chart("Flächentypen im STEP", "", "Anzahl",
                         [ds("Flächen", range(len(counts)), counts.values(), C["cyan"])], kind="bar")
                   | {"labels": [k.title() for k in counts]}],
        "notes": ["Das Oberteil ist ein reines Flächenmodell (0 Solids): Volumen, Masse oder FEM sind daraus "
                  "nicht direkt ableitbar – genau deshalb wird es in den nächsten Schritten parametrisch als "
                  "Volumenmodell neu aufgebaut."],
        "code": code("""
            shape = import_step("Mohammed_0.1 Full Shell.step")
            lower, upper = shape.children              # Baugruppenstruktur aus dem STEP
            print(len(upper.solids()), len(upper.faces()))   # 0 Solids, 268 Flächen → Flächenmodell
            planes = upper.faces().filter_by(GeomType.PLANE)
            by_type = Counter(face.geom_type for face in shape.faces())
        """),
    }


# ================================================================== Kapitel 2 · Modellieren

def s_sketch(ctx: Ctx) -> dict:
    p = ctx.p
    parts = build(ctx)["parts"]
    a = p.arm_angle
    items = ghost(parts, 0.1)
    sketches = [
        ("Knotenblech (Bezier)", Rot(0, 0, a) * bu.gusset_face(p), C["orange"]),
        ("Nasenprofil (Spline)", Pos(0, 0, p.body_height) * bu.nose_profile(p.body_radius, p.nose_length, p.nose_shape), C["yellow"]),
        ("Gondelprofil (Ellipsenbogen)", Rot(0, 0, a) * Pos(p.arm_reach, 0, p.arm_thickness) * bu.pod_profile(p.pod_radius, p.pod_height), C["cyan"]),
    ]
    slots = bu.lightening_slot_sketch(p) or []
    if slots:
        sketches.append(("Langlöcher (SlotCenterToCenter)", Rot(0, 0, a) * Pos(0, 0, p.arm_thickness + 0.1) * Compound(slots), C["pink"]))
    ang = math.radians(bu.engrave_angle(p))
    d = (math.cos(ang), math.sin(ang), 0)
    plane = Plane(origin=(d[0] * (p.body_radius + 1), d[1] * (p.body_radius + 1), 0.55 * p.body_height),
                  x_dir=(-math.sin(ang), math.cos(ang), 0), z_dir=d)
    sketches.append(("Text", plane * Text("BOREAS", font_size=min(0.12 * p.body_height, 0.42 * p.body_radius), rotation=90), C["violet"]))
    for label, sk, col in sketches:
        items.append(item(f"sk:{label}", sk, col, 0.55, edges=False))
        items.append(lines(f"skl:{label}", sk.edges(), col, 2.5))
    return {
        "items": items,
        "legend": [[lbl, col] for lbl, _, col in sketches],
        "stats": [["Skizzen", str(len(sketches))], ["Spline-Stützpunkte Nase", "41"]],
        "code": src(bu.gusset_face, bu.nose_profile, bu.lightening_slot_sketch),
    }


PLACE_TITLES_POD = ("Gondel-Profil drehen", "Gondel aushöhlen")


def _history(ctx: Ctx) -> list:
    k = ("hist",) + _key(ctx.p)
    if k not in _CACHE:
        h: list = []
        bu.build(ctx.p, hist=h)
        _CACHE[k] = h
    return _CACHE[k]


def _display(p: bu.Params, snap: dict):
    s, part = snap["shape"], snap["part"]
    if part == "Arm":
        return Rot(0, 0, p.arm_angle) * s
    if part == "Gondeln" and snap["title"] in PLACE_TITLES_POD:
        return Rot(0, 0, p.arm_angle) * Pos(p.arm_reach, 0, p.arm_thickness) * s
    if part == "Nasenkappe":
        return Pos(0, 0, p.body_height) * s
    return s


def s_history(ctx: Ctx) -> dict:
    p, hist = ctx.p, _history(ctx)
    k = int(min(max(int(ctx.opts.get("index", len(hist) - 1)), 0), len(hist) - 1))
    snap = hist[k]
    cur = _display(p, snap)
    color = bu.PART_STYLE.get(snap["part"], C["green"])
    items = []
    latest = {}
    for s in hist[:k]:
        latest[s["part"]] = s
    for part, s in latest.items():
        if part == snap["part"] or (part == "Arm" and snap["part"] != "Arm"):
            continue
        items += [item(f"ctx:{part}", _display(p, s), bu.PART_STYLE.get(part, C["grey"]), 0.18, edges=False, tol=0.3)]
    prev = latest.get(snap["part"])
    notes = []
    dk = ("diff",) + _key(p) + (k,)
    if prev is not None and "verteilen" not in snap["title"]:
        if dk not in _CACHE:
            a, b = _display(p, prev), cur
            _CACHE[dk] = (b - a, a - b)
        added, removed = _CACHE[dk]
        items.append(item("cur", cur, color, 0.45))
        if added is not None and added.volume > 1e-6:
            items.append(item("added", added, C["yellow"], 1.0, edges=False))
            notes.append(f"Gelb = hinzugefügt ({f(added.volume / 1000, 2, 'cm³')})")
        if removed is not None and removed.volume > 1e-6:
            items.append(item("removed", removed, C["red"], 0.9, edges=False))
            notes.append(f"Rot = entfernt ({f(removed.volume / 1000, 2, 'cm³')})")
    else:
        items.append(item("cur", cur, color, 1.0))
    return {
        "items": items,
        "slider": {"key": "index", "min": 0, "max": len(hist) - 1, "value": k,
                   "labels": [f"{i + 1}. {s['title']}" for i, s in enumerate(hist)]},
        "stats": [["Schritt", f"{k + 1} / {len(hist)}"], ["Operation", snap["op"]], ["Bauteil", snap["part"]],
                  ["Flächen", str(len(cur.faces()))], ["Volumen", f(cur.volume / 1000, 2, "cm³")]],
        "notes": notes,
        "code": code(snap["code"]),
    }


def s_loft_sweep(ctx: Ctx) -> dict:
    p = ctx.p
    parts = build(ctx)["parts"]
    a = p.arm_angle
    at_motor = Rot(0, 0, a) * Pos(p.arm_reach, 0, p.arm_thickness + p.pod_height + 1)
    prop = at_motor * bu.build_propeller(ctx.req["prop_diameter"])
    sections = [at_motor * s for s in bu.propeller_sections(ctx.req["prop_diameter"])]
    items = ghost(parts, 0.15) + [item("Propeller", prop, C["white"], 0.55)]
    for i, s in enumerate(sections):
        items.append(lines(f"sec{i}", s.edges(), C["yellow"], 3))
    extra = []
    if p.cable_hole_d > 0:
        path = Rot(0, 0, a) * bu.cable_path(p)
        cable = Rot(0, 0, a) * bu.build_cables(replace(p, arm_count=1, arm_angle=0))
        items += [item("Kabel", cable, C["red"], 0.85, edges=False), lines("pfad", [path], C["cyan"], 3)]
        extra = [["Kabelpfad (Spline)", f(path.length, 1, "mm")]]
    return {
        "items": items,
        "legend": [["Loft-Querschnitte", C["yellow"]], ["Propeller (Loft)", C["white"]],
                   ["Sweep-Pfad", C["cyan"]], ["Kabel (Sweep)", C["red"]]],
        "stats": [["Loft-Querschnitte", str(len(sections))], ["Propeller-Volumen", f(prop.volume / 1000, 2, "cm³")]] + extra,
        "code": src(bu.propeller_sections, bu.build_propeller, bu.build_cables),
    }


def motor_mount_builder(r=16.0, t=4.0, bolt_circle=9.5):
    with BuildPart() as mount:
        Cylinder(r, t, align=(Align.CENTER, Align.CENTER, Align.MIN))
        with Locations((0, 0, t)):
            with PolarLocations(bolt_circle, 4):
                CounterBoreHole(radius=1.6, counter_bore_radius=2.9, counter_bore_depth=1.5)
            Hole(radius=4)
        top = mount.edges().group_by(Axis.Z)[-1].filter_by(GeomType.CIRCLE).sort_by(SortBy.RADIUS)[-1]
        chamfer(top, 0.8)
    return mount.part


def motor_mount_algebra(r=16.0, t=4.0, bolt_circle=9.5):
    top = (Align.CENTER, Align.CENTER, Align.MAX)
    mount = Cylinder(r, t, align=(Align.CENTER, Align.CENTER, Align.MIN))
    bolt = Pos(0, 0, t) * (Cylinder(1.6, t, align=top) + Cylinder(2.9, 1.5, align=top))
    mount = mount.cut(*[loc * bolt for loc in PolarLocations(bolt_circle, 4)], Cylinder(4, t, align=(Align.CENTER, Align.CENTER, Align.MIN)))
    edge = mount.edges().group_by(Axis.Z)[-1].filter_by(GeomType.CIRCLE).sort_by(SortBy.RADIUS)[-1]
    return chamfer(edge, 0.8)


def s_modes(ctx: Ctx) -> dict:
    t0 = time.perf_counter()
    a = motor_mount_builder()
    ta = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    b = motor_mount_algebra()
    tb = (time.perf_counter() - t0) * 1000
    same = abs(a.volume - b.volume) < 1e-6 * max(a.volume, 1)
    return {
        "items": [item("builder", Pos(-22, 0, 0) * a, C["blue"]), item("algebra", Pos(22, 0, 0) * b, C["green"])],
        "legend": [["Builder-Modus (links)", C["blue"]], ["Algebra-Modus (rechts)", C["green"]]],
        "stats": [["Volumen Builder", f(a.volume, 2, "mm³")], ["Volumen Algebra", f(b.volume, 2, "mm³")],
                  ["Identisch", "✔ ja" if same else "✘ nein"], ["Flächen", f"{len(a.faces())} / {len(b.faces())}"],
                  ["Bauzeit", f"{ta:.0f} / {tb:.0f} ms"]],
        "notes": ["Beide Varianten erzeugen dieselbe Geometrie. Builder-Modus liest sich wie ein CAD-Feature-Baum "
                  "(Kontext-Manager, Hole-Features); Algebra-Modus ist reines Python mit Operatoren (+ − & *) – "
                  "ideal für Funktionen, Schleifen und Optimierung."],
        "code": src(motor_mount_builder, motor_mount_algebra),
    }


SELECTORS = {
    "cyl": ("Alle Zylinderflächen", "Rumpf", "part.faces().filter_by(GeomType.CYLINDER)"),
    "top": ("Oberste Flächengruppe (group_by Z)", "Rumpf", "part.faces().group_by(Axis.Z)[-1]"),
    "bspline": ("Freiformflächen (Knotenblech-Bezier)", "Rumpf", "part.faces().filter_by(GeomType.BSPLINE)"),
    "armtop": ("Planflächen auf Armhöhe (Position)", "Rumpf",
               "part.faces().filter_by(GeomType.PLANE).filter_by_position(Axis.Z, t - 0.01, t + 0.01)"),
    "vertical": ("Senkrechte Kanten", "Rumpf", "part.edges().filter_by(Axis.Z)"),
    "padcircle": ("Kreiskanten mit Radius der Motorplatte", "Rumpf",
                  "part.edges().filter_by(GeomType.CIRCLE).filter_by(lambda e: abs(e.radius - r_pad) < 0.01)"),
    "largest": ("Die 5 größten Flächen", "Rumpf", "part.faces().sort_by(SortBy.AREA)[-5:]"),
    "slotedges": ("Kanten der Steckschlitze (Position)", "Rumpf",
                  "part.edges().filter_by(Axis.Z).filter_by_position(Axis.Z, H - d, H)"),
    "nose": ("Nasenkappe: größte Fläche", "Nasenkappe", "part.faces().sort_by(SortBy.AREA)[-1:]"),
}


def s_selectors(ctx: Ctx) -> dict:
    p = ctx.p
    parts = build(ctx)["parts"]
    key = ctx.opts.get("sel", "cyl")
    label, target, expr = SELECTORS.get(key, SELECTORS["cyl"])
    ns = {"part": parts[target], "Axis": Axis, "GeomType": GeomType, "SortBy": SortBy, "t": p.arm_thickness,
          "r_pad": bu.derived(p)["pad_radius"], "H": p.body_height, "d": p.slot_depth}
    sel = eval(expr, {"__builtins__": {"abs": abs}}, ns)  # nur serverseitig definierte Ausdrücke
    items = ghost(parts, 0.16)
    is_faces = expr.startswith("part.faces")
    if is_faces:
        items.append(item("sel", Compound(list(sel)), C["yellow"], 1.0, edges=False))
        measure = ["Fläche gesamt", f(sum(x.area for x in sel) / 100, 2, "cm²")]
    else:
        items.append(lines("sel", list(sel), C["yellow"], 4))
        measure = ["Länge gesamt", f(sum(x.length for x in sel), 1, "mm")]
    return {
        "items": items, "legend": [[label, C["yellow"]]],
        "stats": [["Treffer", str(len(sel))], measure, ["Objekt", target]],
        "code": code(f'part = parts["{target}"]\nauswahl = {expr}\nprint(len(auswahl))'),
    }


DETAIL_KEYS = [("fillet", "Verrundung Motorplatten"), ("slots", "Erleichterungs-Langlöcher"),
               ("shell", "Hohle Gondeln (offset)"), ("cable", "Kabeldurchführung"), ("engrave", "Gravur (Text) – teuer!")]


def _detail_params(p: bu.Params, o: dict) -> bu.Params:
    return replace(p, edge_fillet=(p.edge_fillet or 1.0) if o.get("fillet", True) else 0,
                   lightening_slots=(p.lightening_slots or 2) if o.get("slots", True) else 0,
                   pod_wall=(p.pod_wall or 1.2) if o.get("shell", True) else 0,
                   cable_hole_d=(p.cable_hole_d or 6) if o.get("cable", True) else 0,
                   engrave=1 if o.get("engrave", True) else 0)


def s_details(ctx: Ctx) -> dict:
    q = _detail_params(ctx.p, ctx.opts)
    base = _detail_params(ctx.p, {k: False for k, _ in DETAIL_KEYS})
    t0 = time.perf_counter()
    bu.build_body(q)
    body_ms = (time.perf_counter() - t0) * 1000
    parts = build(ctx, q)["parts"]
    base_parts = build(ctx, base)["parts"]
    if ctx.opts.get("section"):
        parts = bu.section_cut(parts)
    dens = ctx.mat["density"] / 1000
    m = sum(x.volume for x in build(ctx, q)["parts"].values()) * dens
    m0 = sum(x.volume for x in base_parts.values()) * dens
    return {
        "items": parts_items(parts),
        "stats": [["Strukturmasse", f(m, 1, "g")], ["ohne Details", f(m0, 1, "g")], ["Differenz", f(m - m0, 1, "g")],
                  ["Rumpf neu gebaut in", f(body_ms, 0, "ms")], ["Flächen Rumpf", str(len(parts["Rumpf"].faces()))]],
        "notes": ["Die Gravur erzeugt hunderte Flächen – jede spätere Boolesche Operation wird dadurch teurer. "
                  "Deshalb modelliert das Modell Rohr und einen Arm getrennt und verschmilzt erst am Schluss."],
        "code": src(bu.build_arm),
    }


def s_joints(ctx: Ctx) -> dict:
    p = ctx.p
    res = build(ctx, accessories=True)
    parts, acc = res["parts"], res["accessories"]
    items = parts_items(parts)
    for i, rotor in enumerate(acc["Propeller"].children if acc.get("Propeller") else []):
        x, y = an.motor_positions(p)[i]
        items.append(item(f"rotor{i}", rotor, C["white"], 0.95, edges=False,
                          spin={"center": [x, y, 0], "axis": [0, 0, 1], "dir": 1 if i % 2 == 0 else -1}))
    if acc.get("Kabel") is not None:
        items.append(item("Kabel", acc["Kabel"], C["red"], 1.0, edges=False))
    body = parts["Rumpf"]
    frames = []
    for name, j in body.joints.items():
        loc = j.location
        m = loc.wrapped.Transformation()
        rot = np.array([[m.Value(r, c) for c in (1, 2, 3)] for r in (1, 2, 3)])
        frames += triad(f"joint:{name}", tuple(loc.position), 14, rot.T)
    items += frames
    return {
        "items": items, "explode": True,
        "legend": [["Joint-Achse X", C["red"]], ["Y", C["green"]], ["Z (Drehachse)", C["blue"]]],
        "stats": [["Joints am Rumpf", str(len(body.joints))], ["davon RevoluteJoint", str(p.arm_count)],
                  ["RigidJoint", "1 (Nasenkappe)"]],
        "controls_client": [{"type": "toggle", "key": "spin", "label": "Propeller drehen (Animation)", "value": True}],
        "code": code("""
            RigidJoint("nose_seat", body, Location((0, 0, H)))       # Sitz der Nasenkappe am Rohr
            RigidJoint("base", nose, Location((0, 0, 0)))            # Bezugspunkt an der Kappe
            body.joints["nose_seat"].connect_to(nose.joints["base"])  # → Kappe wird platziert

            for i, (x, y) in enumerate(motor_positions):
                RevoluteJoint(f"motor{i}", body, axis=Axis((x, y, z_top), (0, 0, 1)))
                rotor = copy.copy(propeller)
                RigidJoint("hub", rotor, Location((0, 0, 0)))
                body.joints[f"motor{i}"].connect_to(rotor.joints["hub"], angle=30)
        """),
    }


# ================================================================== Kapitel 3 · Parametrik

def s_params(ctx: Ctx) -> dict:
    p = ctx.p
    parts = build(ctx)["parts"]
    mass = sum(x.volume for x in parts.values()) * ctx.mat["density"] / 1000
    checks = bu.check_constraints(p, ctx.req, ctx.mat, ctx.cfg["limits"], mass)
    d = bu.derived(p)
    return {
        "items": parts_items(parts),
        "table": {"head": ["Constraint", "Wert", "Grenze", ""],
                  "rows": [[c["name"], f(c["value"], 2 if c["unit"] == "" else 1, c["unit"]), c["limit"], "✔" if c["ok"] else "✘"]
                           for c in checks]},
        "stats": [["Freie Parameter", str(len(bu.PARAM_SPEC))], ["Getriebene Maße", str(len(d))],
                  ["Constraints erfüllt", f"{sum(c['ok'] for c in checks)} / {len(checks)}"]],
        "actions": [{"label": "▶ In der Werkbank ausprobieren", "mode": "werkbank"}],
        "code": src(bu.derived),
    }


def s_variants(ctx: Ctx) -> dict:
    items, rows, masses, names = [], [], [], []
    x = 0.0
    for name, pre in ctx.cfg["presets"].items():
        mat = ctx.cfg["materials"][pre["material"]]
        p = bu.autosize(pre["req"], mat, ctx.cfg["limits"])
        parts = bu.build(p)["parts"]
        span = bu.derived(p)["span"]
        x += span / 2
        placed = {k: Pos(x, 0, 0) * v for k, v in parts.items()}
        items += parts_items(placed, prefix=f"{name}:", edges=False, tol=0.25)
        x += span / 2 + 40
        mass = sum(v.volume for v in parts.values()) * mat["density"] / 1000
        checks = bu.check_constraints(p, pre["req"], mat, ctx.cfg["limits"], mass)
        rows.append([name, pre["material"], p.arm_count, f(2 * p.body_radius, 0), f(span, 0), f(mass, 0, "g"),
                     f"{sum(c['ok'] for c in checks)}/{len(checks)}"])
        masses.append(mass)
        names.append(name)
    return {
        "items": items,
        "table": {"head": ["Variante", "Material", "n", "Ø Rohr", "Spannweite", "Masse", "✔"], "rows": rows},
        "charts": [chart("Strukturmasse je Variante", "", "g", [ds("Masse", range(len(masses)), masses, C["green"])], "bar")
                   | {"labels": names}],
        "notes": ["Alle Varianten entstehen aus demselben Code – nur die Anforderungen (Mock-Daten) unterscheiden sich."],
        "code": src(bu.autosize),
    }


# ================================================================== Kapitel 4 · Simulation

def s_inertia(ctx: Ctx) -> dict:
    p = ctx.p
    parts = build(ctx)["parts"]
    rep = an.inertia_report(p, parts, ctx.req, ctx.mat, ctx.cfg)
    tot = rep["total"]
    markers = []
    for c in rep["components"]:
        if c["src"] == "Mock":
            markers.append(marker(c["c"], 3 + 0.25 * c["m"] ** 0.5, C["violet"], c["name"]))
    markers.append(marker(tot["com_mm"], 5, C["yellow"], "Gesamtschwerpunkt"))
    w, vecs = np.linalg.eigh(tot["I_gmm2"])
    items = parts_items(parts, 0.35, edges=False)
    for k in range(3):
        v = vecs[:, k] * 60
        items.append(polyline(f"pa{k}", [tot["com_mm"] - v, tot["com_mm"] + v], [C["red"], C["green"], C["cyan"]][k], 2))
    ik = tot["I_kgm2"]
    return {
        "items": items, "markers": markers,
        "legend": [["Mock-Komponenten (Motoren, Nutzlast, Akku)", C["violet"]], ["Gesamtschwerpunkt", C["yellow"]],
                   ["Hauptträgheitsachsen", C["cyan"]]],
        "stats": [["Abflugmasse", f(tot["mass_g"], 1, "g")],
                  ["Schwerpunkt z", f(tot["com_mm"][2], 1, "mm")],
                  ["Ixx", f"{ik[0, 0]:.3e} kg·m²"], ["Iyy", f"{ik[1, 1]:.3e} kg·m²"], ["Izz", f"{ik[2, 2]:.3e} kg·m²"]],
        "table": {"head": ["Komponente", "Masse g", "x", "y", "z", "Quelle"], "rows": rep["rows"]},
        "code": src(an._gprops, an.combine_inertia),
    }


def s_clash(ctx: Ctx) -> dict:
    p = replace(ctx.p, arm_reach=float(ctx.opts.get("reach") or ctx.p.arm_reach))
    req = dict(ctx.req, prop_diameter=float(ctx.opts.get("prop") or ctx.req["prop_diameter"]))
    res = bu.build(p, accessories={"prop_diameter": req["prop_diameter"]})
    parts, acc = res["parts"], res["accessories"]
    cc = an.clash_check(p, parts, acc, req)
    bad_discs = {r["a"] for r in cc["rows"] if not r["ok"]} | {r["b"] for r in cc["rows"] if not r["ok"]}
    items = parts_items(parts, 0.9, edges=False)
    for i, dsc in enumerate(cc["discs"]):
        items.append(item(f"disc{i}", dsc, C["red"] if f"Propellerkreis {i + 1}" in bad_discs else C["cyan"], 0.25, edges=False))
    if acc.get("Kabel") is not None:
        items.append(item("Kabel", acc["Kabel"], C["orange"], 1.0, edges=False))
    for i, h in enumerate(cc["hits"]):
        items.append(item(f"hit{i}", h, C["red"], 1.0, edges=False))
    n_bad = sum(not r["ok"] for r in cc["rows"])
    return {
        "items": items,
        "legend": [["Propellerkreis frei", C["cyan"]], ["Kollision", C["red"]], ["Kabel", C["orange"]]],
        "stats": [["Geprüfte Paare", str(len(cc["rows"]))], ["Kollisionen", str(n_bad)],
                  ["Min. Abstand", f(min(r["distance"] for r in cc["rows"]), 2, "mm")]],
        "table": {"head": ["Objekt A", "Objekt B", "Abstand", "Überlappung", ""],
                  "rows": [[r["a"], r["b"], f(r["distance"], 2, "mm"), f(r["overlap_mm3"], 1, "mm³"), "✔" if r["ok"] else "✘"]
                           for r in cc["rows"]]},
        "controls_dynamic": [
            {"type": "range", "key": "reach", "label": "Reichweite testen", "unit": "mm", "min": 50, "max": 260, "step": 1, "value": p.arm_reach},
            {"type": "range", "key": "prop", "label": "Propeller Ø testen", "unit": "mm", "min": 50, "max": 260, "step": 1, "value": req["prop_diameter"]},
        ],
        "code": code("""
            gap = disc.distance_to(body)              # minimaler Abstand zweier Körper
            if gap == 0:
                overlap = (disc & body).volume        # Durchdringungsvolumen per Boolean
        """),
    }


def s_fem(ctx: Ctx) -> dict:
    p = ctx.p
    parts = build(ctx)["parts"]
    fem = an.beam_fem(p, parts["Rumpf"], ctx.req, ctx.mat, parts)
    body_item = item("Rumpf", parts["Rumpf"], C["grey"])
    body_item["colors"] = an.stress_colors(p, body_item["vertices"], fem)
    s = fem["s"] - p.body_radius
    L = p.arm_reach - p.body_radius
    inertia = p.arm_width * p.arm_thickness ** 3 / 12
    x = np.linspace(0, L, 40)
    w_an = ctx.req["thrust_per_motor"] * x ** 2 * (3 * L - x) / (6 * ctx.mat["E"] * inertia)
    allow = ctx.mat["yield"] / ctx.cfg["limits"]["min_safety_factor"]
    diff = (1 - fem["tip_deflection"] / fem["analytic_deflection"]) * 100
    return {
        "items": [body_item] + ghost({k: v for k, v in parts.items() if k != "Rumpf"}, 0.25),
        "colorbar": {"min": 0, "max": float(fem["stress"].max()), "unit": "MPa", "label": "Biegespannung Ausleger"},
        "stats": [["Spitzen-Durchbiegung FEM", f(fem["tip_deflection"], 3, "mm")],
                  ["Handformel (Rechteckbalken)", f(fem["analytic_deflection"], 3, "mm")],
                  ["Max. Spannung", f(fem["max_stress"], 1, "MPa")], ["Sicherheit gegen Fließen", f(fem["safety_factor"], 1)],
                  ["1. Biege-Eigenfrequenz", f(fem["f1_hz"], 0, "Hz")]],
        "charts": [
            chart("Durchbiegung entlang des Arms", "Abstand von Rohrwand [mm]", "w [mm]",
                  [ds("FEM (CAD-Querschnitte)", s, fem["w"], C["green"]), ds("Handformel", x, w_an, C["grey"], dashed=True)]),
            chart("Biegespannung", "Abstand von Rohrwand [mm]", "σ [MPa]",
                  [ds("σ(s)", s, fem["stress"], C["orange"], fill=True), ds("zulässig (Fließgrenze / SF)", [s[0], s[-1]], [allow, allow], C["red"], dashed=True)]),
            chart("Flächenträgheitsmoment aus CAD-Schnitten", "Abstand von Rohrwand [mm]", "I [mm⁴]",
                  [ds("I(s)", s, fem["I"], C["cyan"])]),
        ],
        "notes": [f"Die FEM ist {diff:.0f} % steifer als die Handformel, weil sie Knotenblech, Langlöcher und "
                  "Motorplatte über echte Querschnitte aus dem CAD berücksichtigt.",
                  "Modell: 1D-Euler-Bernoulli-Balken (60 Schnitte), eingespannt an der Rohrwand, Vollschub an der Spitze."],
        "code": src(an.arm_sections),
    }


def s_aero(ctx: Ctx) -> dict:
    p = ctx.p
    parts = build(ctx)["parts"]
    tot = an.inertia_report(p, parts, ctx.req, ctx.mat, ctx.cfg)["total"]
    ae = an.aero(p, parts, tot["mass_g"], ctx.req, ctx.cfg)
    arrows = [polyline(f"flow{i}", [(-250, y, z), (-150, y, z)], C["cyan"], 2)
              for i, (y, z) in enumerate([(-40, 20), (0, 60), (40, 100), (0, 150), (-60, 40), (60, 40)])]
    return {
        "items": parts_items(parts) + arrows,
        "images": [{"title": "Stirnfläche (Anströmung in +X)", "src": ae["img_front"]},
                   {"title": "Draufsicht (Sinkflug)", "src": ae["img_top"]}],
        "stats": [["Stirnfläche", f(ae["A_front_mm2"] / 100, 1, "cm²")], ["Draufsichtfläche", f(ae["A_top_mm2"] / 100, 1, "cm²")],
                  ["Max. Geschwindigkeit", f(ae["v_max"], 1, "m/s") + f" ({ae['v_max'] * 3.6:.0f} km/h)"],
                  ["bei Neigung", f(ae["tilt_max"], 0, "°")], ["Feinheit Nase L/D", f(ae["fineness"], 2)]],
        "charts": [
            chart("Geschwindigkeit vs. Neigungswinkel", "Neigung [°]", "v [m/s]", [ds("v(θ)", ae["tilt"], ae["speed"], C["cyan"])]),
            chart("Widerstandsleistung", "v [m/s]", "P [W]", [ds("P = D·v", ae["speed"], ae["power_w"], C["orange"])]),
        ],
        "notes": ["Flächen werden aus der build123d-Tessellierung gerastert (0,4 mm Pixel). Cw-Werte sind Mock-Annahmen."],
        "code": src(an._silhouette),
    }


def s_flight(ctx: Ctx) -> dict:
    p = ctx.p
    parts = build(ctx)["parts"]
    full = an.combine_inertia(an.vehicle_components(p, parts, ctx.req, ctx.mat, ctx.cfg, True))
    empty = an.combine_inertia(an.vehicle_components(p, parts, ctx.req, ctx.mat, ctx.cfg, False))
    a = an.roll_step(p, full["I_kgm2"], full["mass_g"], ctx.req, ctx.cfg)
    b = an.roll_step(p, empty["I_kgm2"], empty["mass_g"], ctx.req, ctx.cfg)
    step = ctx.cfg["flight"]["step_deg"]
    return {
        "items": parts_items(parts),
        "stats": [["Ixx mit Nutzlast", f"{a['Ixx']:.3e} kg·m²"], ["Max. Rollmoment", f(a["tau_max"], 3, "N·m")],
                  ["Max. Winkelbeschleunigung", f(math.degrees(a["alpha_max"]), 0, "°/s²")],
                  ["Anstiegszeit 10→90 %", f(a["rise_time"] * 1000, 0, "ms")], ["Überschwingen", f(a["overshoot"], 1, "%")],
                  ["Schwebe-Gas", f(a["hover_throttle"] * 100, 0, "%")]],
        "charts": [
            chart(f"Roll-Sprungantwort auf {step}°", "t [s]", "Rollwinkel [°]",
                  [ds("mit Nutzlast", a["t"], a["theta"], C["green"]), ds("ohne Nutzlast", b["t"], b["theta"], C["cyan"], dashed=True),
                   ds("Soll", [0, a["t"][-1]], [step, step], C["grey"], dashed=True)]),
            chart("Stellmoment", "t [s]", "τ [N·m]", [ds("mit Nutzlast", a["t"], a["tau"], C["orange"])]),
        ],
        "notes": ["Trägheitstensor kommt direkt aus der CAD-Geometrie (+ Mock-Komponenten). PD-Regler mit Motorzeitkonstante "
                  "und Momentensättigung – ändert man Reichweite oder Material, ändert sich das Flugverhalten."],
        "code": src(an.roll_step),
    }


def s_optimize(ctx: Ctx) -> dict:
    p = ctx.p
    parts = build(ctx)["parts"]
    base = sum(x.volume for x in parts.values()) * ctx.mat["density"] / 1000
    sw = an.design_sweep(p, ctx.req, ctx.mat, ctx.cfg["limits"], base)
    ok = [r for r in sw["points"] if r["ok"]]
    nok = [r for r in sw["points"] if not r["ok"]]
    best = sw["best"]
    datasets = [ds("zulässig", [r["mass"] for r in ok], [r["defl"] for r in ok], C["green"], points=True),
                ds("unzulässig", [r["mass"] for r in nok], [r["defl"] for r in nok], C["grey"], points=True),
                ds("Pareto-Front", [r["mass"] for r in sw["pareto"]], [r["defl"] for r in sw["pareto"]], C["cyan"]),
                ds("aktuell", [base], [bu.arm_deflection(p, ctx.req["thrust_per_motor"], ctx.mat["E"])], C["orange"], points=True)]
    actions, items = [], parts_items(parts, 0.3, edges=False)
    if best:
        datasets.append(ds("Optimum", [best["mass"]], [best["defl"]], C["yellow"], points=True))
        q = replace(p, arm_thickness=float(best["t"]), arm_width=float(best["w"]))
        items = parts_items(bu.build(q)["parts"])
        actions.append({"label": f"✔ Optimum übernehmen (t={best['t']} mm, b={best['w']} mm)",
                        "apply": {"arm_thickness": best["t"], "arm_width": best["w"]}})
    top = sorted(ok, key=lambda r: r["mass"])[:6]
    return {
        "items": items, "actions": actions,
        "charts": [chart("Designraum: Masse vs. Durchbiegung (log)", "Strukturmasse [g]", "Durchbiegung [mm]", datasets, "scatter") | {"ylog": True}],
        "table": {"head": ["Stärke t", "Breite b", "Masse", "Durchbiegung", "Spannung"],
                  "rows": [[f(r["t"], 1, "mm"), f(r["w"], 0, "mm"), f(r["mass"], 1, "g"), f(r["defl"], 2, "mm"), f(r["stress"], 1, "MPa")] for r in top]},
        "stats": [["CAD-Neubauten im Loop", str(sw["n_cad"])], ["zulässige Designs", f"{len(ok)} / {len(sw['points'])}"],
                  ["Optimum", f"t={best['t']} mm · b={best['w']} mm · {best['mass']:.1f} g" if best else "keins"]],
        "code": src(an.design_sweep),
    }


# ================================================================== Kapitel 5 · Daten raus

def s_manufacturing(ctx: Ctx) -> dict:
    parts = build(ctx)["parts"]
    mf = an.manufacturing(parts, ctx.mat, ctx.cfg)
    items = [{"id": f"mf:{k}", "color": C["grey"], "opacity": 1.0, "vertices": v["vertices"], "triangles": v["triangles"],
              "colors": v["colors"]} for k, v in mf.items()]
    rows = [[k, f(v["overhang_pct"], 1, "%"), " · ".join(("✔ " if ok else "✘ ") + pr for pr, ok in v["fits"].items()),
             f(v["print_h"], 1, "h"), f(v["cost"], 2, "€")] for k, v in mf.items()]
    proc = ctx.mat["process"]
    return {
        "items": items, "explode": True,
        "legend": [["Überhang > 45° (braucht Stützstruktur)", C["red"]]],
        "stats": [["Druckzeit gesamt", f(sum(v["print_h"] for v in mf.values()), 1, "h")],
                  ["Kosten gesamt (Mock)", f(sum(v["cost"] for v in mf.values()), 2, "€")],
                  ["Verfahren laut Material", proc]],
        "table": {"head": ["Teil", "Überhang", "Passt auf Drucker", "Zeit", "Kosten"], "rows": rows},
        "notes": ([] if proc == "FDM" else [f"{ctx.mat['label']} wird nicht gedruckt ({proc}) – Zeiten/Kosten gelten nur als FDM-Vergleich."]),
        "code": src(an.manufacturing),
    }


def s_exports(ctx: Ctx) -> dict:
    parts = build(ctx)["parts"]
    fmts = [("step", "STEP (CAD-Austausch)"), ("stl", "STL (Slicer/CFD)"), ("3mf", "3MF (Druck mit Farben)"),
            ("glb", "glTF/GLB (Web, Unity, Blender)"), ("dxf", "DXF-Schnitt (Laser/CNC)"), ("svg", "SVG-Zeichnung")]
    return {
        "items": parts_items(parts),
        "actions": [{"label": f"⬇ {lbl}", "export": k} for k, lbl in fmts] + [{"label": "📐 Technische Zeichnung ansehen", "drawing": True}],
        "stats": [["Formate", str(len(fmts))], ["Zeichnung", "2 × A3, voll bemaßt"],
                  ["Maßarten", "Längen, Ø, R, Winkel, Teilkreis, Hinweislinien"],
                  ["Schnitte", "Halbschnitte mit Schraffur"]],
        "notes": ["Die Zeichnung ist komplett parametrisch: Ansichten per Hidden-Line-Removal aus den echten Körpern, "
                  "alle Maßzahlen aus den Modellparametern – jede Variante bekommt automatisch ihre eigene Werkstattzeichnung."],
        "code": code("""
            export_step(assembly, "boreas.step")                 # mit Namen & Farben je Teil
            export_stl(assembly, "boreas.stl", tolerance=0.05)
            Mesher().add_shape(part).write("boreas.3mf")
            export_gltf(assembly, "boreas.glb", binary=True)

            # Zeichnung: Projektion + Bemaßung (drawing.py)
            visible, hidden = fast_projection(body, origin, up, look_at)        # Hidden-Line-Removal
            ExtensionLine([p1, p2], offset=(0, 10), draft=DRAFT, label="Ø66")    # Längen-/Durchmessermaß
            DimensionLine([center, rim], draft=DRAFT, label="R14", arrows=(False, True))   # Radius
            DimensionLine(CenterArc(c, r, 45, 90), draft=DRAFT, label="90°")    # Winkelmaß
            TechnicalDrawing(page_size=PageSize.A3, title="Boreas Oberteil – Rumpf", drawing_scale="2")
        """),
    }


def s_urdf(ctx: Ctx) -> dict:
    p = ctx.p
    parts = build(ctx)["parts"]
    tot = an.inertia_report(p, parts, ctx.req, ctx.mat, ctx.cfg)["total"]
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = ctx.root / "out" / f"urdf_{stamp}"
    res = an.export_urdf(p, parts, tot, ctx.req, str(out))
    zip_path = shutil.make_archive(str(out), "zip", out)
    items = parts_items(parts, 0.6, edges=False)
    z = p.arm_thickness + p.pod_height + 1
    for i, (x, y) in enumerate(an.motor_positions(p)):
        items += triad(f"rotor{i}", (x, y, z), 18)
    items += triad("base_link", tot["com_mm"], 30)
    return {
        "items": items, "markers": [marker(tot["com_mm"], 5, C["yellow"], "base_link inertial")],
        "legend": [["Frames (rot=X, grün=Y, blau=Z)", C["blue"]], ["Schwerpunkt base_link", C["yellow"]]],
        "stats": [["Links", str(1 + p.arm_count)], ["Joints (continuous)", str(p.arm_count)],
                  ["Masse", f(tot["mass_g"] / 1000, 3, "kg")]],
        "downloads": [{"label": "⬇ URDF-Paket (.zip)", "url": "/out/" + os.path.basename(zip_path)}],
        "notes": ["Direkt nutzbar in ROS/Gazebo, PX4-SITL oder NVIDIA Isaac Sim – Masse und Trägheit stammen aus dem CAD."],
        "code": code(res["text"], "xml"),
    }


def s_pipeline(ctx: Ctx) -> dict:
    return {
        "items": parts_items(build(ctx)["parts"]),
        "actions": [{"label": "▶ Pipeline-Ansicht öffnen", "mode": "pipeline"}],
        "code": code("""
            # Headless / CI – ohne GUI:
            #   python pipeline.py --preset "Kamera-Gimbal"
            #   python pipeline.py --all
            from pipeline import run_pipeline
            result = run_pipeline(req, material="PA12-CF", optimize=True)
            for stage in result["stages"]:
                print(stage["name"], stage["ms"], stage["summary"])
        """),
    }


# ================================================================== Registry

STEPS = [
    ("import", "1 · Daten rein", "STEP-Import & Topologie", s_import,
     "build123d liest das vorhandene STEP mit Baugruppenstruktur ein und macht die Topologie (Solids, Shells, Flächen, Kanten) "
     "direkt in Python abfragbar. Die Farben zeigen die Flächentypen.", []),
    ("sketch", "2 · Modellieren", "2D-Skizzen & Profile", s_sketch,
     "Jedes Feature beginnt mit einer Skizze: Linien, Bezier-Kurven, Splines, Ellipsenbögen, Langlöcher und Text – "
     "platziert auf beliebigen Ebenen im Raum.", []),
    ("history", "2 · Modellieren", "Bauhistorie Schritt für Schritt", s_history,
     "Der komplette Feature-Baum des Modells. Mit dem Regler durch alle Schritte scrubben – gelb ist, was der Schritt "
     "hinzufügt, rot, was er entfernt.", []),
    ("loft", "2 · Modellieren", "Loft & Sweep", s_loft_sweep,
     "Freiformkörper: Der Propeller entsteht als Loft durch verdrehte Ellipsen-Querschnitte, das Kabel als Sweep eines "
     "Kreises entlang eines 3D-Splines.", []),
    ("modes", "2 · Modellieren", "Builder- vs. Algebra-Modus", s_modes,
     "build123d kennt zwei Schreibweisen für dasselbe Ergebnis. Beispiel: ein Motorhalter mit Senkbohrungen.", []),
    ("selectors", "2 · Modellieren", "Topologie-Selektoren", s_selectors,
     "Statt Kanten anzuklicken, wählt man sie per Regel aus: nach Typ, Position, Richtung, Größe oder eigener Bedingung. "
     "Das macht Fillets & Co. robust gegenüber Parameteränderungen.",
     [{"type": "select", "key": "sel", "label": "Selektor", "value": "cyl", "options": [[k, v[0]] for k, v in SELECTORS.items()]}]),
    ("details", "2 · Modellieren", "Detail-Features", s_details,
     "Verrundungen, Langloch-Muster, Schalenkörper (offset), Bohrungen und Gravur – einzeln zu- und abschaltbar.",
     [{"type": "toggle", "key": k, "label": lbl, "value": True} for k, lbl in DETAIL_KEYS]
     + [{"type": "toggle", "key": "section", "label": "Schnittansicht", "value": False}]),
    ("joints", "2 · Modellieren", "Baugruppe & Joints", s_joints,
     "Teile werden über Joints verbunden statt über feste Koordinaten: RigidJoint für die Nasenkappe, RevoluteJoint "
     "(Drehachse) für jeden Propeller.", []),
    ("params", "3 · Parametrik", "Parameter & Constraints", s_params,
     "23 freie Parameter treiben das Modell; abhängige Maße werden berechnet, 11 Constraints prüfen die Auslegung.", []),
    ("variants", "3 · Parametrik", "Varianten aus Mock-Anforderungen", s_variants,
     "Aus fünf Mock-Datensätzen legt der Code automatisch fünf gültige Varianten aus und baut sie.", []),
    ("inertia", "4 · Simulation", "Masse, Schwerpunkt, Trägheit", s_inertia,
     "Exakte Volumeneigenschaften aus der BRep-Geometrie plus Mock-Komponenten (Motoren, Nutzlast, Akku) → "
     "Trägheitstensor für die Flugdynamik.", []),
    ("clash", "4 · Simulation", "Kollisions- & Abstandsprüfung", s_clash,
     "Propellerkreise, Struktur und Kabel werden paarweise auf Abstand und Durchdringung geprüft. Mit den Reglern eine "
     "Kollision provozieren!", []),
    ("fem", "4 · Simulation", "FEM Ausleger", s_fem,
     "60 Schnitte durch den CAD-Arm liefern Fläche und Trägheitsmoment → 1D-Balken-FE → Durchbiegung, Spannung, "
     "Eigenfrequenz. Farbkarte = Biegespannung.", []),
    ("aero", "4 · Simulation", "Aerodynamik", s_aero,
     "Projizierte Flächen aus der Geometrie → Luftwiderstand → erreichbare Geschwindigkeit.", []),
    ("flight", "4 · Simulation", "Flugdynamik", s_flight,
     "Trägheit aus dem CAD geht in eine Roll-Regelkreis-Simulation: Wie schnell kippt die Drohne mit/ohne Nutzlast?", []),
    ("optimize", "4 · Simulation", "Design-Optimierung", s_optimize,
     "CAD im Loop: 35 Arm-Varianten werden gebaut und bewertet. Das leichteste zulässige Design kann übernommen werden.", []),
    ("manufacturing", "5 · Daten raus", "Fertigung & Druckbarkeit", s_manufacturing,
     "Überhang-Analyse auf der Tessellierung, Druckbett-Check und Zeit-/Kostenschätzung je Teil.", []),
    ("exports", "5 · Daten raus", "Exporte & Zeichnung", s_exports,
     "Ein Modell, alle Formate: für CAD, Druck, Web, Laser/CNC und Dokumentation.", []),
    ("urdf", "5 · Daten raus", "Simulator-Export (URDF)", s_urdf,
     "Robotik-/Flugsimulatoren brauchen Geometrie + Masse + Trägheit + Gelenke. build123d liefert alles davon.", []),
    ("pipeline", "5 · Daten raus", "Automatisierte Pipeline", s_pipeline,
     "Alles zusammen als eine Kette, die ohne GUI läuft: Anforderungen → CAD → Simulationen → Optimierung → Exporte → Report.", []),
]

STEP_FN = {s[0]: s[3] for s in STEPS}


def step_list() -> list:
    return [{"id": sid, "chapter": ch, "title": title, "lead": lead, "controls": controls}
            for sid, ch, title, _, lead, controls in STEPS]


def run_step(step_id: str, ctx: Ctx) -> dict:
    t0 = time.perf_counter()
    out = STEP_FN[step_id](ctx)
    out["ms"] = (time.perf_counter() - t0) * 1000
    return out
