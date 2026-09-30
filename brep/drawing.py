"""Bemasste A3-Zeichnung des Gesamtmodells (Ober-, Unterteil, Nase) – Aufgabe R01.

Geometrie aus dem Modell (Hidden-Line-Removal), Maszahlen aus der Spec. Nutzt die Blatt-Helfer der
bestehenden Demo-Zeichnung (`drawing.py`: View, Sheet, Layer-Setup).
"""
from __future__ import annotations

import math

from build123d import Compound, ExportSVG, LineType, Plane, Unit, section

from drawing import SHEET_H, Sheet, View, _choose_scale, n

from .assembly import build_features
from .skeleton import Skeleton
from .spec import Spec


def _layers(svg: ExportSVG) -> None:
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


def drawing_svg(spec: Spec, parts: dict, path: str) -> None:
    sk = Skeleton.from_params(spec.group("skeleton"))
    nose, fins, tail = spec.group("nose"), spec.group("body_fins"), spec.group("tail_fins")
    body = Compound([parts[k] for k in ("upper", "lower", "nose") if k in parts])

    svg = ExportSVG(unit=Unit.MM, margin=5)
    _layers(svg)
    v_front = View(body, (0, -1, 0), (0, 0, 1), (-205, -20, -118, 128), "Vorderansicht")
    v_top = View(body, (0, 0, 1), (0, 1, 0), (-15, 205, -10, 128), "Draufsicht")
    s = _choose_scale([v_front, v_top])
    sh = Sheet(svg, 0.0)
    for v in (v_front, v_top):
        v.place(s)
        sh.draw_view(v, hidden=False)

    # --- Vorderansicht: Höhen und Durchmesser
    f = v_front.pt
    z_tip = sk.nose_joint_z + nose.length
    x_l = -sk.motor_radius - 20
    sh.center_line(f((0, 0, sk.body_bottom_z)), f((0, 0, z_tip)))
    sh.lin(f((x_l, 0, sk.body_bottom_z)), f((x_l, 0, z_tip)), (-14, 0), n(z_tip - sk.body_bottom_z),
           direction=(0, 1, 0))
    sh.lin(f((x_l, 0, sk.body_bottom_z)), f((x_l, 0, sk.split_z)), (-4, 0), n(sk.split_z - sk.body_bottom_z),
           direction=(0, 1, 0))
    sh.lin(f((x_l, 0, sk.nose_joint_z)), f((x_l, 0, z_tip)), (-4, 0), n(nose.length), direction=(0, 1, 0))
    sh.lin(f((-sk.joint_radius, 0, sk.split_z)), f((sk.joint_radius, 0, sk.split_z)), (0, -6),
           "Ø" + n(2 * sk.joint_radius))
    sh.lin(f((-sk.nose_joint_radius, 0, sk.nose_joint_z)), f((sk.nose_joint_radius, 0, sk.nose_joint_z)), (0, 8),
           "Ø" + n(2 * sk.nose_joint_radius))

    # --- Draufsicht: Motorlage
    tp = v_top.pt
    m = sk.motor_positions()
    sh.lin(tp((m[1].X, m[1].Y, 0)), tp((m[0].X, m[0].Y, 0)), (0, 14), n(abs(m[0].X - m[1].X)), direction=(1, 0, 0))
    sh.lin(tp((m[0].X, m[3].Y, 0)), tp((m[0].X, m[0].Y, 0)), (14, 0), n(abs(m[0].Y - m[3].Y)), direction=(0, 1, 0))
    for p in m:
        c = tp((p.X, p.Y, 0))
        sh.center_line((c[0] - 5, c[1]), (c[0] + 5, c[1]), 1)
        sh.center_line((c[0], c[1] - 5), (c[0], c[1] + 5), 1)
    tgt = tp((m[0].X, m[0].Y, 0))
    sh.leader(tgt, (tgt[0] + 10, tgt[1] - 18), f"{sk.arm_count}× Motor auf R{n(sk.motor_radius)}")

    # --- Schnitt A–A: Fin-Profil bei halber Spannweite (Massstab 2:1)
    a = math.radians(sk.arm_angles()[0])
    fin = next(f.shape for f in build_features(spec) if f.group == "body_fins")
    s_mid = (sk.joint_radius + sk.motor_radius) / 2
    cut = section(fin, Plane(origin=(s_mid * math.cos(a), s_mid * math.sin(a), 0),
                             z_dir=(math.cos(a), math.sin(a), 0)))
    v_fin = View(cut, (math.cos(a), math.sin(a), 0), (0, 0, 1), (-15, 60, -118, -20), "Schnitt A–A  Fin-Profil (2:1)")
    v_fin.place(2.0)
    sh.draw_view(v_fin, hidden=False)
    fp = v_fin.pt
    bb = cut.bounding_box()
    q = (-math.sin(a), math.cos(a), 0)
    ctr = (bb.center().X, bb.center().Y)
    lo = (ctr[0], ctr[1], bb.min.Z)
    hi = (ctr[0], ctr[1], bb.max.Z)
    sh.lin(fp(lo), fp(hi), (-10, 0), f"Sehne {n(fins.profile_chord)}", direction=(0, 1, 0))
    lam = (s_mid - sk.joint_radius) / (sk.motor_radius - sk.joint_radius)
    t_mid = fins.thickness_root + (fins.thickness_tip - fins.thickness_root) * lam
    z_max = bb.max.Z - fins.max_thickness_pos * fins.profile_chord
    left = (ctr[0] - q[0] * t_mid / 2, ctr[1] - q[1] * t_mid / 2, z_max)
    right = (ctr[0] + q[0] * t_mid / 2, ctr[1] + q[1] * t_mid / 2, z_max)
    sh.lin(fp(left), fp(right), (0, -8), n(t_mid), direction=(1, 0, 0))

    # --- Beschriftung
    sh.text((65, -40), f"Tropfenprofil NACA-00xx, max. Dicke bei {n(100 * fins.max_thickness_pos)} % Sehne", 3.2)
    sh.text((65, -48), f"Fin: Dicke {n(fins.thickness_root)} → {n(fins.thickness_tip)} mm, Pfeilung aus Vorderkante", 3.2)
    sh.text((65, -56), f"Heckflosse: Sehne {n(tail.profile_chord)}, Spannweite R{n(tail.span_radius)}", 3.2)
    sh.text((65, -64), "Alle Masse aus spec/boreas_spec.json – Zeichnung regeneriert mit dem Modell.", 3.2)
    sh.frame(title="Boreas – Gesamtmodell (B-rep)", sub_title="Ober-, Unterteil, Nase", drawing_number="BR-R01",
             sheet_number=1, drawing_scale=s)
    svg.write(path)


__all__ = ["drawing_svg", "SHEET_H"]
