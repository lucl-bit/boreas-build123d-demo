"""Bemaßte Werkstattzeichnungen (2 × A3) aus dem parametrischen Modell.
Alle Maßzahlen stammen aus den Modellparametern, die Geometrie aus der HLR-Projektion der echten Körper."""
from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
from build123d import (
    Align, Arrow, Box, CenterArc, Compound, Draft, DimensionLine, Edge, ExportSVG, ExtensionLine, LineType,
    PageSize, Pos, Rot, TechnicalDrawing, Text, Unit, scale,
)

import boreas_upper as bu

SHEET_H = 297.0
DRAFT = Draft(font_size=3.2, arrow_length=2.5, line_width=0.18, pad_around_text=1.0, extension_gap=1.0,
              decimal_precision=1, display_units=False)
FS = 3.0
SCALES = (1.0, 0.5, 0.4, 0.25, 0.2, 0.1)


def n(v: float) -> str:
    return f"{v:.0f}" if abs(v - round(v)) < 1e-6 else f"{v:.1f}".rstrip("0").rstrip(".")


def _unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


class View:
    def __init__(self, shape, view_dir, up, cell, title, section_faces=None):
        self.z = _unit(view_dir)
        self.x = _unit(np.cross(up, self.z))
        self.y = np.cross(self.z, self.x)
        c = shape.bounding_box(optimal=False).center()
        self.vis, self.hid = bu.fast_projection(shape, tuple(np.array([c.X, c.Y, c.Z]) + 2000 * self.z), tuple(up), (c.X, c.Y, c.Z))
        bb = Compound(self.vis).bounding_box(optimal=False)
        self.u0, self.u1, self.v0, self.v1 = bb.min.X, bb.max.X, bb.min.Y, bb.max.Y
        self.cell, self.title, self.section_faces = cell, title, section_faces or []

    def fits(self, s, margin=20):
        x0, x1, y0, y1 = self.cell
        return (self.u1 - self.u0) * s + 2 * margin <= x1 - x0 and (self.v1 - self.v0) * s + 2 * margin <= y1 - y0

    def place(self, s, dy_sheet=0.0):
        x0, x1, y0, y1 = self.cell
        self.s = s
        self.sx = (x0 + x1) / 2 - s * (self.u0 + self.u1) / 2
        self.sy = (y0 + y1) / 2 - s * (self.v0 + self.v1) / 2 + dy_sheet

    def pt(self, p):
        p = np.asarray(p, float)
        return (float(self.s * p @ self.x + self.sx), float(self.s * p @ self.y + self.sy), 0.0)

    def geom(self, edges):
        return Pos(self.sx, self.sy) * scale(Compound(edges), by=self.s)

    def box(self):
        return (self.s * self.u0 + self.sx, self.s * self.u1 + self.sx, self.s * self.v0 + self.sy, self.s * self.v1 + self.sy)


class Sheet:
    def __init__(self, svg: ExportSVG, dy: float):
        self.svg, self.dy = svg, dy

    def add(self, shape, layer):
        if shape is not None:
            self.svg.add_shape(shape, layer=layer)

    def lin(self, a, b, off, label, direction=None):
        """Längenmaß zwischen zwei Blattpunkten; off = Versatzvektor der Maßlinie."""
        kw = {"measurement_direction": direction} if direction else {}
        self.add(ExtensionLine([a, b], offset=off, draft=DRAFT, label=label, **kw), "Maße")

    def dim(self, a, b, label, arrows=(True, True)):
        self.add(DimensionLine([a, b], draft=DRAFT, label=label, arrows=arrows), "Maße")

    def radius(self, center, r_sheet, angle_deg, label):
        a = math.radians(angle_deg)
        tip = (center[0] + r_sheet * math.cos(a), center[1] + r_sheet * math.sin(a), 0)
        if r_sheet >= 9:
            self.dim(center, tip, label, arrows=(False, True))
        else:
            self.leader(tip, (tip[0] + 9 * math.cos(a), tip[1] + 9 * math.sin(a)), label)

    def angle(self, center, r_sheet, a0, a1, label):
        self.add(DimensionLine(Pos(center[0], center[1]) * CenterArc((0, 0), r_sheet, a0, a1 - a0), draft=DRAFT, label=label), "Maße")

    def leader(self, target, knee, label, right=None):
        right = knee[0] >= target[0] if right is None else right
        end = (knee[0] + (1.5 if right else -1.5), knee[1], 0)
        self.add(Arrow(2.2, Edge.make_line((knee[0], knee[1], 0), target), 0.18, head_at_start=False), "Maße")
        self.add(Edge.make_line((knee[0], knee[1], 0), end), "Maßlinien")
        self.add(Pos(end[0] + (0.8 if right else -0.8), end[1] + 0.6) *
                 Text(label, FS, align=(Align.MIN if right else Align.MAX, Align.MIN)), "Text")

    def center_line(self, a, b, ext=4.0):
        a, b = np.array(a[:2]), np.array(b[:2])
        d = (b - a) / max(np.linalg.norm(b - a), 1e-9) * ext
        self.add(Edge.make_line((*(a - d), 0), (*(b + d), 0)), "Mittellinien")

    def text(self, pos, s, size=FS, align=(Align.MIN, Align.MIN)):
        self.add(Pos(pos[0], pos[1] + self.dy) * Text(s, size, align=align), "Text")

    def draw_view(self, v: View, hidden=True):
        self.add(v.geom(v.vis), "Sichtbar")
        if hidden and v.hid:
            self.add(v.geom(v.hid), "Verdeckt")
        for face in v.section_faces:
            placed = Pos(v.sx, v.sy) * scale(Rot(-90, 0, 0) * face, by=v.s)
            self.add(placed, "Schnitt")
            self.add(_hatch(placed), "Schraffur")
        x0, x1, y0, y1 = v.box()
        self.add(Pos((x0 + x1) / 2, y1 + 17) * Text(v.title, 3.5, align=(Align.CENTER, Align.MIN)), "Text")

    def frame(self, **kw):
        self.add(Pos(0, self.dy) * TechnicalDrawing(designed_by="build123d", page_size=PageSize.A3, nominal_text_size=8, **kw), "Rahmen")


def _hatch(face, spacing=1.6):
    bb = face.bounding_box(optimal=False)
    lines = []
    span = bb.size.X + bb.size.Y
    k = bb.min.X - bb.size.Y
    while k < bb.max.X:
        a, b = (k, bb.min.Y, 0), (k + span, bb.min.Y + span, 0)
        seg = face & Edge.make_line(a, b)
        if seg is not None:
            lines += list(seg.edges())
        k += spacing
    return Compound(lines) if lines else None


def _half_section(part):
    cut = part - Pos(0, -1000, 0) * Box(4000, 2000, 4000)
    faces = [fc for fc in cut.faces() if abs(fc.center().Y) < 1e-6 and fc.geom_type.name == "PLANE"
             and abs(abs(fc.normal_at().Y) - 1) < 1e-6]
    return cut, faces


def _choose_scale(views):
    for s in SCALES:
        if all(v.fits(s) for v in views):
            return s
    return SCALES[-1]


# ------------------------------------------------------------------ Blatt 1: Rumpf

def sheet_body(svg, p: bu.Params, dy: float, meta: dict):
    R, H, w, t = p.body_radius, p.body_height, p.wall, p.arm_thickness
    d = bu.derived(p)
    pad_r, L = d["pad_radius"], p.arm_reach
    gh = p.gusset_height if p.gusset_height >= 1 else 0
    gl = p.gusset_length if gh else 0
    a = math.radians(p.arm_angle)

    body = bu.build_body(p)
    local = replace(p, arm_angle=0.0)
    single = bu.build_tube(local).fuse(bu.build_arm(local))

    v_front = View(body, (0, -1, 0), (0, 0, 1), (-200, -68, -68, 135), "Vorderansicht")
    v_arm = View(single, (0, -1, 0), (0, 0, 1), (-64, 56, -68, 135), "Ansicht B – Arm in wahrer Länge")
    v_top = View(body, (0, 0, 1), (0, 1, 0), (60, 200, -68, 135), "Draufsicht")
    s = _choose_scale([v_front, v_arm, v_top])
    sh = Sheet(svg, dy)
    for v in (v_front, v_arm, v_top):
        v.place(s, dy)
        sh.draw_view(v)

    # --- Vorderansicht
    f = v_front.pt
    sh.center_line(f((0, 0, 0)), f((0, 0, H)))
    sh.lin(f((-R, 0, 0)), f((-R, 0, H)), (-12, 0), n(H))
    sh.lin(f((-R, 0, H)), f((R, 0, H)), (0, 10), "Ø" + n(2 * R))
    zi = 0.78 * H
    sh.dim(f((-(R - w), 0, zi)), f((R - w, 0, zi)), "Ø" + n(2 * (R - w)))
    if p.slot_count >= 1:
        sh.lin(f((R, 0, H - p.slot_depth)), f((R, 0, H)), (9, 0), n(p.slot_depth))

    # --- Ansicht B (lokal: Arm entlang +X)
    b = v_arm.pt
    sh.center_line(b((0, 0, 0)), b((0, 0, H)))
    sh.center_line(b((L, 0, 0)), b((L, 0, t + 6)))
    sh.lin(b((0, 0, 0)), b((L, 0, 0)), (0, -16), n(L))
    if gl:
        sh.lin(b((R - w / 2, 0, 0)), b((R - w / 2 + gl, 0, 0)), (0, -7), n(gl))
    x_r = L + pad_r
    sh.lin(b((x_r, 0, 0)), b((x_r, 0, t)), (8, 0), n(t))
    if gh:
        sh.lin(b((x_r, 0, 0)), b((R - w / 2, 0, t + gh)), (18, 0), n(t + gh), direction=(0, 1, 0))
    if p.cable_hole_d > 0:
        zh = t + gh + p.cable_hole_d / 2 + 3
        sh.lin(b((x_r, 0, 0)), b((R, 0, zh)), (28, 0), n(zh), direction=(0, 1, 0))
        rh = p.cable_hole_d / 2
        facing = any(abs((k * 360 / p.arm_count - 270) % 360) < 1e-6 for k in range(p.arm_count))
        if facing:  # eine Bohrung zeigt zum Betrachter → echter Kreis in Rohrmitte
            tgt = b((rh * 0.707, 0, zh + rh * 0.707))
            sh.center_line(b((-rh - 2, 0, zh)), b((rh + 2, 0, zh)), 1)
        else:
            tgt = b((R + 0.5, 0, zh + rh))
        sh.leader(tgt, (tgt[0] + 12, tgt[1] + 12), f"Ø{n(p.cable_hole_d)} Kabeldurchführung ({p.arm_count}×)")
    if p.edge_fillet > 0:
        tgt = b((L - pad_r * 0.7, 0, t))
        sh.leader(tgt, (tgt[0] - 6, tgt[1] + 12), f"R{n(min(p.edge_fillet, 0.9 * t))}")

    # --- Draufsicht
    tp = v_top.pt
    c = tp((0, 0, 0))
    sh.center_line(tp((-L - pad_r, 0, 0)), tp((L + pad_r, 0, 0)))
    sh.center_line(tp((0, -L - pad_r, 0)), tp((0, L + pad_r, 0)))
    sh.add(Pos(c[0], c[1]) * CenterArc((0, 0), L * s, 0, 360), "Mittellinien")
    angles = bu.arm_angles(p)
    for ang in angles:
        r_ = math.radians(ang)
        sh.center_line(c, tp((L * math.cos(r_), L * math.sin(r_), 0)), 2)
    # Teilkreis-Durchmesser entlang eines Arms
    a2 = math.radians(angles[len(angles) // 2]) if len(angles) % 2 == 0 else a + math.pi
    ends = sorted([tp((L * math.cos(a), L * math.sin(a), 0)), tp((L * math.cos(a2), L * math.sin(a2), 0))])
    sh.dim(ends[0], ends[1], "Ø" + n(2 * L))  # von links nach rechts → Text lesbar
    if p.arm_angle > 1:
        sh.angle(c, 0.85 * L * s, 0, p.arm_angle, n(p.arm_angle) + "°")
    sh.angle(c, 0.62 * L * s, p.arm_angle, p.arm_angle + 360 / p.arm_count, n(360 / p.arm_count) + "°")
    pc = tp((L * math.cos(a), L * math.sin(a), 0))
    sh.radius(pc, pad_r * s, p.arm_angle + 90, "R" + n(pad_r))
    # Armbreite am gegenüberliegenden Arm
    r2 = math.radians(angles[1] if len(angles) > 1 else p.arm_angle)
    dd, ee = np.array([math.cos(r2), math.sin(r2), 0]), np.array([-math.sin(r2), math.cos(r2), 0])
    m = dd * (L - pad_r - 4)
    sh.lin(tp(m - ee * p.arm_width / 2), tp(m + ee * p.arm_width / 2), tuple(dd[:2] * (pad_r * 2 * s + 6)), n(p.arm_width))
    if p.slot_count % 2 == 0:  # Schlitz bei 180° bemaßen, weg vom Winkelmaß
        sh.lin(tp((-R, -p.slot_width / 2, 0)), tp((-R, p.slot_width / 2, 0)), (-10, 0), n(p.slot_width))
    elif p.slot_count >= 1:
        sh.lin(tp((R, -p.slot_width / 2, 0)), tp((R, p.slot_width / 2, 0)), (10, 0), n(p.slot_width))
    slots = bu.lightening_slot_sketch(p)
    if slots:
        x0 = R + gl + 4
        x1 = L - pad_r - 3
        pitch = (x1 - x0) / p.lightening_slots
        hs = 0.45 * p.arm_width
        e0 = np.array([-math.sin(a), math.cos(a), 0])
        d0 = np.array([math.cos(a), math.sin(a), 0])
        tgt = tp(d0 * (x0 + pitch / 2) + e0 * hs / 2)
        sh.leader(tgt, (tgt[0] - 14, tgt[1] + 16),
                  f"{p.lightening_slots}× Langloch {n(pitch - 3)}×{n(hs)} (R{n(hs / 2)})")

    notes = [f"Maße in mm · Allgemeintoleranzen ISO 2768-m · Maßstab 1:{n(1 / s)}",
             f"Werkstoff: {meta.get('material', '–')} · Masse Rumpf: {meta.get('mass_body', '–')}",
             f"Wandstärke Rohr {n(w)} · Knotenblech-Kontur: quadr. Bezier",
             "Alle Maße parametrisch aus boreas_upper.Params (build123d)"]
    for i, line in enumerate(notes):
        sh.text((-196, -92 - 6 * i), line)
    sh.frame(title="Boreas Oberteil – Rumpf", sub_title=meta.get("variant", "Parametrische Variante"),
             drawing_number="BOR-UP-001", sheet_number=1, drawing_scale=n(1 / s))


# ------------------------------------------------------------------ Blatt 2: Nasenkappe & Gondel

def sheet_nose_pod(svg, p: bu.Params, dy: float, meta: dict):
    R, w = p.body_radius, p.wall
    d = bu.derived(p)
    nose = bu.build_nose(p)
    nose_cut, nose_faces = _half_section(nose)
    pod = bu._pod(p.pod_radius, p.pod_height)
    if p.pod_wall > 0:
        from build123d import Axis, offset
        pod = offset(pod, amount=-p.pod_wall, openings=pod.faces().sort_by(Axis.Z)[0])
    pod_cut, pod_faces = _half_section(pod)

    v_ns = View(nose_cut, (0, -1, 0), (0, 0, 1), (-200, -68, -68, 135), "Halbschnitt A–A Nasenkappe", nose_faces)
    v_nside = View(nose, (1, 0, 0), (0, 0, 1), (-64, 56, -68, 135), "Nasenkappe Seitenansicht (Lasche)")
    v_pod = View(pod_cut, (0, -1, 0), (0, 0, 1), (60, 200, -68, 135), "Halbschnitt B–B Gondel", pod_faces)
    s = _choose_scale([v_ns, v_nside, v_pod])
    sh = Sheet(svg, dy)
    for v in (v_ns, v_nside, v_pod):
        v.place(s, dy)
        sh.draw_view(v, hidden=v is v_nside)

    th, sp_h = d["tab_height"], d["tab_height"] + 4
    r_sp = d["spigot_outer_radius"]
    q = v_ns.pt
    sh.center_line(q((0, 0, -sp_h)), q((0, 0, p.nose_length)))
    sh.lin(q((R, 0, 0)), q((0, 0, p.nose_length)), (16, 0), n(p.nose_length), direction=(0, 1, 0))
    sh.lin(q((-R, 0, 0)), q((R, 0, 0)), (0, -(sp_h * s + 16)), "Ø" + n(2 * R))
    sh.lin(q((-r_sp, 0, -sp_h)), q((r_sp, 0, -sp_h)), (0, -7), f"Ø{n(2 * r_sp)} (Spiel {n(p.fit_clearance)})")
    sh.lin(q((-r_sp, 0, -sp_h)), q((-r_sp, 0, 0)), (-(R - r_sp) * s - 8, 0), n(sp_h))
    if p.slot_count >= 1:
        sh.lin(q((R, 0, -th)), q((R, 0, 0)), (7, 0), n(th))
    zw = 0.35 * p.nose_length
    r_out = R * ((p.nose_length - zw) / p.nose_length) ** p.nose_shape
    tgt = q((-(r_out - w / 2), 0, zw))
    sh.leader(tgt, (tgt[0] - 10, tgt[1] + 12), f"Wand {n(w)}", right=False)
    sh.text((v_ns.box()[0] - 2, v_ns.cell[2] + 2), f"Kontur: r(z) = {n(R)}·((L−z)/L)^{n(p.nose_shape)}", 2.4)

    if p.slot_count >= 1:
        g = v_nside.pt
        tw = d["tab_width"]
        sh.lin(g((0, -tw / 2, -th)), g((0, tw / 2, -th)), (0, -8), n(tw))
        sh.center_line(g((0, 0, -sp_h)), g((0, 0, p.nose_length)))

    r_p, h_p = p.pod_radius, p.pod_height
    k = v_pod.pt
    sh.center_line(k((0, 0, 0)), k((0, 0, h_p)))
    sh.lin(k((-r_p, 0, 0)), k((r_p, 0, 0)), (0, -9), "Ø" + n(2 * r_p))
    sh.lin(k((r_p, 0, 0)), k((0, 0, h_p)), (12, 0), n(h_p), direction=(0, 1, 0))
    sh.lin(k((-r_p, 0, 0)), k((-r_p, 0, 0.3 * h_p)), (-8, 0), n(0.3 * h_p))
    if p.pod_wall > 0:
        tgt = k((-(r_p - p.pod_wall / 2), 0, 0.15 * h_p))
        sh.leader(tgt, (tgt[0] - 8, tgt[1] - 10), f"Wand {n(p.pod_wall)}", right=False)
    tgt = k((r_p * 0.7, 0, 0.3 * h_p + (h_p - 0.3 * h_p) * math.sqrt(1 - 0.49)))
    sh.leader(tgt, (tgt[0] + 8, tgt[1] + 10), f"Kuppel: Ellipse a={n(r_p)}, b={n(0.7 * h_p)}")

    notes = [f"Maße in mm · Allgemeintoleranzen ISO 2768-m · Maßstab 1:{n(1 / s)}",
             f"Werkstoff: {meta.get('material', '–')} · Laschenbreite = Schlitzbreite − 2 × Spiel",
             f"Gondeln: {p.arm_count} Stück · Nasenkappe: 1 Stück"]
    for i, line in enumerate(notes):
        sh.text((-196, -92 - 6 * i), line)
    sh.frame(title="Boreas Oberteil – Nasenkappe & Gondel", sub_title=meta.get("variant", "Parametrische Variante"),
             drawing_number="BOR-UP-002", sheet_number=2, drawing_scale=n(1 / s))


def drawing_svg(p: bu.Params, path: str, meta: dict | None = None) -> None:
    meta = meta or {}
    svg = ExportSVG(unit=Unit.MM, margin=5)
    grey = (0.45, 0.45, 0.45)
    svg.add_layer("Rahmen", line_weight=0.5)
    svg.add_layer("Sichtbar", line_weight=0.35)
    svg.add_layer("Verdeckt", line_color=grey, line_weight=0.18, line_type=LineType.ISO_DASH)
    svg.add_layer("Mittellinien", line_color=(0.2, 0.35, 0.6), line_weight=0.18, line_type=LineType.ISO_DASH_DOT)
    svg.add_layer("Schnitt", fill_color=(0.93, 0.93, 0.93), line_weight=0.35)
    svg.add_layer("Schraffur", line_color=grey, line_weight=0.13)
    svg.add_layer("Maße", fill_color=(0.0, 0.0, 0.0), line_weight=0.18)
    svg.add_layer("Maßlinien", line_weight=0.18)
    svg.add_layer("Text", fill_color=(0.0, 0.0, 0.0), line_weight=0.05)
    sheet_body(svg, p, 0.0, meta)
    sheet_nose_pod(svg, p, -(SHEET_H + 12), meta)
    svg.write(path)
