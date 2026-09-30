# -*- coding: utf-8 -*-
"""Erzeugt die Erklaer-Diagramme fuer die Praesentation (SVG, selbsttragend).

Aufruf: python presentation/gen_figures.py
Umfaerben: nur den Farbblock unter den Imports (BREP*, VOX*, INK, GREY*, FONT) aendern und neu ausfuehren.
"""
import math, os
from xml.sax.saxutils import escape

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)

BREP, BREP_L, BREP_M = "#1f5fa8", "#dbe8f6", "#8fb3dc"
VOX, VOX_L, VOX_M = "#d9731a", "#fbe6d2", "#eeb27d"
INK, GREY, GREY_L, GREY_M = "#0d192f", "#565e6d", "#e8e2d6", "#b9b3a8"
HALO = 'paint-order="stroke" stroke="#f2ede3" stroke-width="6" stroke-linejoin="round"'
FONT = "'Outfit', 'Segoe UI', Arial, sans-serif"


def wrap(name, title, desc, body, w=1280, h=720):
    s = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
         f'role="img" aria-labelledby="t d" font-family="{FONT}">\n'
         f'<title id="t">{escape(title)}</title>\n<desc id="d">{escape(desc)}</desc>\n'
         '<defs>\n'
         f'<marker id="arrK" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker>\n'
         f'<marker id="arrG" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{GREY}"/></marker>\n'
         f'<marker id="arrB" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{BREP}"/></marker>\n'
         f'<marker id="arrO" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{VOX}"/></marker>\n'
         '</defs>\n'
         f'<rect width="{w}" height="{h}" fill="#f2ede3"/>\n{body}\n</svg>\n')
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(s)
    print("ok", name, len(s) // 1024, "KB")


def T(x, y, s, size=22, weight="400", fill=INK, anchor="start", style="", extra=""):
    st = f' font-style="{style}"' if style else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}"{st} {extra}>{escape(s)}</text>')


def TL(x, y, lines, size=22, lh=None, **kw):
    lh = lh or size * 1.3
    return "\n".join(T(x, y + i * lh, l, size, **kw) for i, l in enumerate(lines))


def R(x, y, w, h, fill="none", stroke=INK, sw=2, rx=8, dash=""):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"{d}/>')


def L(x1, y1, x2, y2, stroke=INK, sw=2, dash="", marker=""):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    m = f' marker-end="url(#{marker})"' if marker else ""
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{sw}"{d}{m}/>'


def P(pts, fill="none", stroke=INK, sw=2, close=True, dash=""):
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + (" Z" if close else "")
    da = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"{da}/>'


def C(x, y, r, fill=INK, stroke="none", sw=0):
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def title(s, sub=None):
    out = T(40, 58, s, 34, "700")
    if sub:
        out += "\n" + T(40, 96, sub, 22, fill=GREY)
    return out


# ------------------------------------------------------------------ Profil
def yt(x, t):
    """NACA-00xx Dickenverteilung (halbe Dicke, Sehne = 1)."""
    if x < 0 or x > 1:
        return None
    return 5 * t * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1015 * x ** 4)


def inside(u, v, t):
    """Punkt (u,v) in Sehnen-Einheiten im Profil?"""
    h = yt(u, t)
    return h is not None and abs(v) <= h


def profile_pts(t, n=240):
    up = []
    for i in range(n + 1):
        # cosine spacing fuer runde Nase
        x = 0.5 * (1 - math.cos(math.pi * i / n))
        up.append((x, yt(x, t)))
    return up + [(x, -y) for x, y in reversed(up)]


def runs(t, chord, cell, x0, cy, xmin=-0.05, xmax=1.05, ymax=0.5):
    """Rasterisiert das Profil in Zellen der Kantenlaenge 'cell' (px); liefert Zeilenlaeufe in px (relativ zu x0, cy)."""
    out = []
    ny = int(math.ceil(ymax * chord / cell))
    nx0 = int(math.floor(xmin * chord / cell))
    nx1 = int(math.ceil(xmax * chord / cell))
    for j in range(-ny, ny):
        v = -(j + 0.5) * cell / chord  # Zeile j (nach unten positiv)
        # Achtung: Zeile j deckt v-Bereich ab; Zentrum-Test
        start = None
        for i in range(nx0, nx1 + 1):
            u = (i + 0.5) * cell / chord
            f = inside(u, v, t) if i < nx1 else False
            if f and start is None:
                start = i
            if (not f) and start is not None:
                out.append((start * cell, j * cell, (i - start) * cell, cell))
                start = None
    return out


# ------------------------------------------------------------------ Kuben
def cube_faces(x0, y0, s, d):
    front = [(x0, y0), (x0 + s, y0), (x0 + s, y0 + s), (x0, y0 + s)]
    top = [(x0, y0), (x0 + d, y0 - d), (x0 + s + d, y0 - d), (x0 + s, y0)]
    right = [(x0 + s, y0), (x0 + s + d, y0 - d), (x0 + s + d, y0 + s - d), (x0 + s, y0 + s)]
    return front, top, right


def cube(x0, y0, s, d, fills, stroke, sw=2):
    f, t, r = cube_faces(x0, y0, s, d)
    return "\n".join([P(f, fills[0], stroke, sw), P(t, fills[1], stroke, sw), P(r, fills[2], stroke, sw)])


# ================================================================== Abb. 1
def fig01():
    body = [title("Vektorgrafik und Pixelbild: derselbe Unterschied existiert in 3D")]
    chord, t = 220, 0.36
    cols = [(40, BREP, BREP_L, "Vektor: gespeichert ist ein Rezept", "Kurve + Formel, glatt bei jeder Vergrösserung"),
            (660, VOX, VOX_L, "Pixel: gespeichert ist ein Raster", "Feste Auflösung, beim Vergrössern sichtbar")]
    cell = 2.5
    Z = 5.0
    u0 = -3.0
    bw, bh = 250, 190
    vh = bh / Z / 2
    for ci, (cx, col, colL, head, sub) in enumerate(cols):
        body.append(R(cx, 120, 580, 310, "#ffffff", col, 3, 12))
        body.append(T(cx + 20, 158, head, 25, "700", col))
        body.append(T(cx + 20, 188, sub, 19, fill=GREY))
        x0, cy = cx + 40, 320
        if ci == 0:
            pts = [(x0 + u * chord, cy - v * chord) for u, v in profile_pts(t)]
            body.append(P(pts, colL, col, 3))
        else:
            for (rx, ry, rw, rh) in runs(t, chord, cell, x0, cy):
                body.append(f'<rect x="{x0 + rx:.2f}" y="{cy + ry:.2f}" width="{rw:.2f}" height="{rh:.2f}" fill="{col}" stroke="{col}" stroke-width="0.4"/>')
        body.append(R(x0 + u0, cy - vh, bw / Z, 2 * vh, "none", INK, 2, 0, "5,3"))
        body.append(T(x0 + 110, 405, "Originalgrösse", 19, fill=GREY, anchor="middle"))
        bx, by = cx + 300, 205
        cid = f"clip{ci}"
        body.append(f'<clipPath id="{cid}"><rect x="{bx}" y="{by}" width="{bw}" height="{bh}"/></clipPath>')
        body.append(R(bx, by, bw, bh, "#ffffff", INK, 2, 0))
        ycen = by + bh / 2
        g = [f'<g clip-path="url(#{cid})">']
        if ci == 0:
            pts = [(bx + (u * chord - u0) * Z, ycen - v * chord * Z) for u, v in profile_pts(t, 400)]
            g.append(P(pts, colL, col, 4))
        else:
            for (rx, ry, rw, rh) in runs(t, chord, cell, 0, 0):
                n = int(round(rw / cell))
                for k in range(n):
                    if not (bx - cell * Z <= bx + (rx + k * cell - u0) * Z <= bx + bw):
                        continue
                    g.append(f'<rect x="{bx + (rx + k * cell - u0) * Z:.1f}" y="{ycen + ry * Z:.1f}" width="{cell * Z:.1f}" height="{rh * Z:.1f}" fill="{col}" stroke="#ffffff" stroke-width="1"/>')
        g.append("</g>")
        body.append("\n".join(g))
        body.append(T(bx + bw / 2, by + bh + 24, "5-fach vergrössert", 19, fill=GREY, anchor="middle"))
        body.append(L(x0 + u0 + bw / Z, cy - vh, bx - 1, by, INK, 1.5, "4,3"))
        body.append(L(x0 + u0 + bw / Z, cy + vh, bx - 1, by + bh, INK, 1.5, "4,3"))
    body.append(T(640, 462, "In 3D heisst das:", 24, "700", GREY, "middle"))
    body.append(L(330, 470, 330, 494, GREY, 3, marker="arrG"))
    body.append(L(950, 470, 950, 494, GREY, 3, marker="arrG"))
    body.append(R(40, 504, 580, 200, BREP_L, BREP, 3, 12))
    body.append(cube(90, 610, 90, 36, [BREP_M, "#c4d8ee", "#6f9bcc"], BREP, 3))
    body.append(T(230, 554, "B-rep", 28, "700", BREP))
    body.append(TL(230, 588, ["Körper = Flächen, Kanten,", "Ecken: exakte Formeln.", "Eine Rundung ist ein", "echter Kreisbogen."], 21, 27))
    body.append(R(660, 504, 580, 200, VOX_L, VOX, 3, 12))
    s_, d = 22, 9
    H = [[1, 2, 2, 1], [2, 3, 3, 2], [2, 3, 3, 2], [1, 2, 2, 1]]
    ox, oy = 700, 676
    for z in range(3, -1, -1):
        for i in range(4):
            for k in range(H[z][i]):
                X = ox + i * s_ + z * d
                Y = oy - (k + 1) * s_ - z * d
                body.append(cube(X, Y, s_, d, [VOX_M, "#f6d2b0", "#c9682a"], "#ffffff", 1.2))
    body.append(T(850, 554, "Voxel", 28, "700", VOX))
    body.append(TL(850, 588, ["Körper = Würfelzellen in", "einem 3D-Raster. Eine", "Rundung ist eine Treppe,", "fein oder grob."], 21, 27))
    wrap("fig01_vektor_vs_pixel.svg", "Vektor und Pixel als Analogie zu B-rep und Voxel",
         "Links: Vektorgrafik bleibt beim Vergrössern glatt (Analogie B-rep). Rechts: Pixelbild zeigt Treppen (Analogie Voxel).",
         "\n".join(body))


# ================================================================== Abb. 2
def fig02():
    body = [title("B-rep: ein Körper besteht aus Flächen, Kanten und Ecken")]
    s, d = 120, 50
    panels = [(40, "1  Körper", "(Solid)"), (340, "2  Flächen", "(Faces)"), (640, "3  Kanten", "(Edges)"), (940, "4  Ecken", "(Vertices)")]
    for (px, h1, h2) in panels:
        body.append(R(px, 90, 290, 350, "#ffffff", GREY_M, 2, 12))
        body.append(T(px + 145, 130, h1, 27, "700", BREP, "middle"))
        body.append(T(px + 145, 158, h2, 19, fill=GREY, anchor="middle"))
    # 1 Solid
    x0, y0 = 40 + 70, 270
    body.append(cube(x0, y0, s, d, [BREP_M, "#c4d8ee", "#6f9bcc"], BREP, 3))
    body.append(T(40 + 145, 425, "der ganze geschlossene Körper", 19, fill=GREY, anchor="middle"))
    # 2 Faces exploded
    px = 340
    f, t, r = cube_faces(px + 60, 285, 100, 42)
    off = [(-8, 10), (-8, -14), (22, 4)]
    fills = [BREP_M, "#c4d8ee", "#6f9bcc"]
    for face, (dx, dy), fl in zip((f, t, r), off, fills):
        body.append(P([(x + dx, y + dy) for x, y in face], fl, BREP, 3))
    body.append(T(px + 145, 425, "jede Fläche = eine Formel", 19, fill=GREY, anchor="middle"))
    # 3 Edges
    px = 640
    x0, y0 = px + 70, 270
    f, t, r = cube_faces(x0, y0, s, d)
    hid = [((x0 + d, y0 - d), (x0 + d, y0 + s - d)), ((x0 + d, y0 + s - d), (x0 + s + d, y0 + s - d)), ((x0, y0 + s), (x0 + d, y0 + s - d))]
    for a, b in hid:
        body.append(L(a[0], a[1], b[0], b[1], BREP, 2.5, "7,5"))
    vis = [(f[0], f[1]), (f[1], f[2]), (f[2], f[3]), (f[3], f[0]), (t[0], t[1]), (t[1], t[2]), (t[2], t[3]), (r[1], r[2]), (r[2], r[3])]
    for a, b in vis:
        body.append(L(a[0], a[1], b[0], b[1], BREP, 5))
    body.append(T(px + 145, 425, "Kante = Naht zweier Flächen", 19, fill=GREY, anchor="middle"))
    # 4 Vertices
    px = 940
    x0, y0 = px + 70, 270
    f, t, r = cube_faces(x0, y0, s, d)
    body.append(P(f, "none", GREY_M, 2))
    body.append(P(t, "none", GREY_M, 2))
    body.append(P(r, "none", GREY_M, 2))
    for pa, pb in [((x0 + d, y0 - d), (x0 + d, y0 + s - d)), ((x0 + d, y0 + s - d), (x0 + s + d, y0 + s - d)), ((x0, y0 + s), (x0 + d, y0 + s - d))]:
        body.append(L(pa[0], pa[1], pb[0], pb[1], GREY_M, 2, "7,5"))
    vs = {f[0], f[1], f[2], f[3], t[1], t[2], r[2], (x0 + d, y0 + s - d)}
    for (x, y) in vs:
        body.append(C(x, y, 9, BREP, "#ffffff", 2))
    body.append(T(px + 145, 425, "Ecke = ein Punkt im Raum", 19, fill=GREY, anchor="middle"))
    # Flaechentypen
    body.append(T(40, 484, "Eine Fläche muss nicht eben sein. Typische Flächentypen:", 24, "700"))
    types = [("Ebene", "flat", ["z. B.", "Stirnfläche"]), ("Zylinder", "cyl", ["z. B. Rohr,", "Bohrung"]),
             ("Kegel", "cone", ["z. B. konischer", "Rumpf"]), ("Freiform (NURBS)", "nurbs", ["z. B.", "Tropfenprofil"])]
    for i, (name, kind, ex) in enumerate(types):
        cx = 40 + i * 305
        body.append(R(cx, 508, 285, 150, BREP_L, BREP, 2, 10))
        body.append(T(cx + 142, 542, name, 23, "700", BREP, "middle"))
        gx, gy = cx + 20, 558
        if kind == "flat":
            body.append(P([(gx, gy + 70), (gx + 40, gy + 15), (gx + 110, gy + 15), (gx + 70, gy + 70)], "#ffffff", BREP, 3))
        elif kind == "cyl":
            body.append(f'<path d="M{gx+5},{gy+20} L{gx+5},{gy+70} A45,14 0 0 0 {gx+95},{gy+70} L{gx+95},{gy+20} A45,14 0 0 0 {gx+5},{gy+20} Z" fill="#ffffff" stroke="{BREP}" stroke-width="3"/>')
            body.append(f'<ellipse cx="{gx+50}" cy="{gy+20}" rx="45" ry="14" fill="{BREP_M}" stroke="{BREP}" stroke-width="3"/>')
        elif kind == "cone":
            body.append(f'<path d="M{gx+50},{gy+8} L{gx+5},{gy+70} A45,14 0 0 0 {gx+95},{gy+70} Z" fill="#ffffff" stroke="{BREP}" stroke-width="3"/>')
        else:
            body.append(f'<path d="M{gx},{gy+45} C{gx+25},{gy-5} {gx+55},{gy+85} {gx+110},{gy+20} L{gx+110},{gy+50} C{gx+60},{gy+100} {gx+25},{gy+30} {gx},{gy+75} Z" fill="#ffffff" stroke="{BREP}" stroke-width="3"/>')
        body.append(TL(cx + 140, 598, ex, 19, 25, fill=GREY))
    body.append(T(40, 696, "Genauigkeit: nur durch die Zahlenrechnung begrenzt (Toleranz im Bereich 1e-7 mm), nicht durch ein Raster.", 21, fill=INK))
    wrap("fig02_brep_anatomie.svg", "Anatomie eines B-rep-Körpers",
         "Ein Würfel als Beispiel: Körper, Flächen, Kanten, Ecken. Darunter die Flächentypen Ebene, Zylinder, Kegel und Freiform.",
         "\n".join(body))


# ================================================================== Abb. 3
def fig03():
    body = [title("Ein Tropfenprofil: exakte Kurve gegenüber Voxel-Treppe",
                  "Aero-Fin, Sehne 40 mm, Dicke 24 % (9.6 mm); beispielhaftes Schema")]
    t, chord = 0.24, 350
    specs = [(20, "B-rep", BREP, BREP_L, None, "Kurve = Formel", ["Jede Vergrösserung bleibt glatt,", "die Hinterkante bleibt scharf."]),
             (440, "Voxel 3 mm", VOX, VOX_L, 3.0, "13 Zellen über die Sehne", ["Dünne Hinterkante fällt aus dem", "Raster, Nase und Dicke verrundet."]),
             (860, "Voxel 1 mm", VOX, VOX_L, 1.0, "40 Zellen über die Sehne", ["Treppe kaum sichtbar, aber 3-fach", "feiner = 27-fach mehr Zellen (dicht)."])]
    U0, U1 = 0.70, 1.0
    zb_w, zb_h = 350, 150
    Z = zb_w / ((U1 - U0) * chord)
    for k, (cx, head, col, colL, cellmm, sub, notes) in enumerate(specs):
        body.append(R(cx, 116, 400, 500, "#ffffff", col, 3, 12))
        body.append(T(cx + 20, 156, head, 28, "700", col))
        body.append(T(cx + 20, 188, sub, 20, fill=GREY))
        x0, cy = cx + 25, 262
        cell_px = None if cellmm is None else cellmm * chord / 40.0
        prof = [(u, v) for u, v in profile_pts(t)]
        if cell_px is None:
            body.append(P([(x0 + u * chord, cy - v * chord) for u, v in prof], colL, col, 3))
        else:
            for (rx, ry, rw, rh) in runs(t, chord, cell_px, 0, 0):
                n = int(round(rw / cell_px))
                for q in range(n):
                    body.append(f'<rect x="{x0 + rx + q * cell_px:.2f}" y="{cy + ry:.2f}" width="{cell_px:.2f}" height="{rh:.2f}" fill="{VOX_M}" stroke="{VOX}" stroke-width="{1.2 if cellmm > 2 else 0.4}"/>')
            body.append(P([(x0 + u * chord, cy - v * chord) for u, v in prof], "none", INK, 2, True, "6,4"))
        body.append(R(x0 + U0 * chord, cy - 0.075 * chord, (U1 - U0) * chord + 6, 0.15 * chord, "none", INK, 2, 0, "5,3"))
        body.append(T(cx + 20, 342, "Hinterkante, 3.8-fach vergrössert", 19, fill=GREY))
        bx, by = cx + 25, 356
        cid = f"clipf{k}"
        body.append(f'<clipPath id="{cid}"><rect x="{bx}" y="{by}" width="{zb_w}" height="{zb_h}"/></clipPath>')
        body.append(R(bx, by, zb_w, zb_h, "#ffffff", INK, 2, 0))
        yc = by + zb_h / 2
        g = [f'<g clip-path="url(#{cid})">']
        if cell_px is None:
            g.append(P([(bx + (u * chord - U0 * chord) * Z, yc - v * chord * Z) for u, v in prof], colL, col, 3))
        else:
            for (rx, ry, rw, rh) in runs(t, chord, cell_px, 0, 0):
                n = int(round(rw / cell_px))
                for q in range(n):
                    if not (bx - cell_px * Z <= bx + (rx + q * cell_px - U0 * chord) * Z <= bx + zb_w):
                        continue
                    g.append(f'<rect x="{bx + (rx + q * cell_px - U0 * chord) * Z:.1f}" y="{yc + ry * Z:.1f}" width="{cell_px * Z:.1f}" height="{rh * Z:.1f}" fill="{VOX_M}" stroke="{VOX}" stroke-width="{2 if cellmm > 2 else 0.8}"/>')
            g.append(P([(bx + (u * chord - U0 * chord) * Z, yc - v * chord * Z) for u, v in prof], "none", INK, 2.5, True, "7,4"))
        g.append("</g>")
        body.append("\n".join(g))
        body.append(TL(cx + 20, 548, notes, 20, 27, fill=INK))
    body.append(T(640, 650, "Gestrichelte Linie = exakte Sollform. Der Abstand dazu ist der Fehler der Voxel-Darstellung.", 21, fill=INK, anchor="middle"))
    body.append(T(640, 688, "Je dünner das Detail (Fin-Hinterkante, Wand), desto feiner muss das Raster sein.", 22, "700", fill=INK, anchor="middle"))
    wrap("fig03_fin_kurve_vs_voxel.svg", "Tropfenprofil als exakte Kurve und als Voxel-Treppe",
         "Dasselbe symmetrische Tropfenprofil als B-rep-Kurve, als grobes Voxelraster (3 mm) und als feines Voxelraster (1 mm), jeweils mit vergrösserter Hinterkante.",
         "\n".join(body))


# ================================================================== Abb. 4
def fig04():
    body = [title("Voxel und Distanzfeld: jede Zelle merkt sich den Abstand zur Oberfläche",
                  "2D-Schnitt durch einen runden Körper; Zahlen = Abstand in Zelleneinheiten")]
    cs = 62
    nx, ny = 11, 8
    gx, gy = 40, 128
    ccx, ccy, rad = 5.5, 4.0, 2.7
    for j in range(ny):
        for i in range(nx):
            dx, dy = (i + 0.5) - ccx, (j + 0.5) - ccy
            dist = math.hypot(dx, dy) - rad
            if dist < 0:
                a = min(1.0, 0.25 + 0.35 * (-dist))
                fill = f"rgb({int(255 - a * (255 - 0xd9))},{int(255 - a * (255 - 0x73))},{int(255 - a * (255 - 0x1a))})"
                fill = VOX_L if -dist < 1.0 else (VOX_M if -dist < 1.8 else "#e59a55")
            else:
                fill = "#ffffff" if dist > 0.6 else "#f4f4f4"
            body.append(R(gx + i * cs, gy + j * cs, cs, cs, fill, "#cccccc", 1, 0))
            lab = "0.0" if abs(dist) < 0.05 else f"{dist:+.1f}".replace("-", "\u2212")
            body.append(T(gx + i * cs + cs / 2, gy + j * cs + cs / 2 + 7, lab, 19, fill=INK if abs(dist) > 0.35 else "#000", weight="700" if abs(dist) < 0.5 else "400", anchor="middle", extra='paint-order="stroke" stroke="#ffffff" stroke-width="5" stroke-linejoin="round"'))
    # exakte Nulllinie
    body.append(f'<circle cx="{gx + ccx * cs}" cy="{gy + ccy * cs}" r="{rad * cs}" fill="none" stroke="{INK}" stroke-width="3" stroke-dasharray="10,6"/>')
    body.append(T(gx, gy + ny * cs + 34, "gestrichelt = Oberfläche (Abstand 0)", 21, fill=INK))
    # Rechts: Erklaerung
    rx = 770
    body.append(R(rx, 128, 470, 130, VOX_L, VOX, 3, 12))
    body.append(TL(rx + 20, 165, ["Negativ = innen  (orange)", "Null = Oberfläche", "Positiv = aussen  (weiss)"], 23, 32, weight="700"))
    body.append(T(rx, 300, "Formen kombinieren = rechnen", 25, "700", VOX))
    ops = [("Vereinigen", "min(a, b)"), ("Schneiden", "max(a, b)"), ("Abziehen", "max(a, \u2212b)"), ("Wand der Dicke w", "|d| \u2264 w/2")]
    for i, (n, f) in enumerate(ops):
        yy = 335 + i * 46
        body.append(T(rx, yy, n, 23))
        body.append(T(rx + 460, yy, f, 23, "700", VOX, "end", extra='font-family="Consolas, monospace"'))
        body.append(L(rx, yy + 12, rx + 460, yy + 12, GREY_M, 1))
    body.append(TL(rx, 560, ["Keine Flächen, keine Topologie:", "Booleans gelingen fast immer.", "Der Preis: nur so genau wie das Raster."], 21, 29, fill=INK))
    wrap("fig04_sdf_2d.svg", "Signed Distance Field in 2D",
         "Ein Kreis als Raster; jede Zelle speichert den vorzeichenbehafteten Abstand zur Oberfläche. Booleans sind min und max.",
         "\n".join(body))


# ================================================================== Abb. 5
def fig05():
    body = [title("Skelett-Methode: eine Gruppe ändern, der Rest bleibt stabil")]
    cx0, cy0 = 640, 362
    groups = [("nose", "Nasenkappe"), ("upper_body", "Oberteil-Rumpf"), ("arms", "Ausleger"), ("motor_pods", "Motorgondeln"),
              ("body_fins", "Aero-Fins"), ("lower_body", "Unterteil-Rumpf"), ("tail_fins", "Heckflossen"), ("joints", "Steckverbindungen"),
              ("details", "Detail / Fertigung")]
    rx, ry, bw, bh = 470, 200, 232, 70
    pos = []
    for i, (k, lab) in enumerate(groups):
        a = math.radians(i * 40)
        pos.append((cx0 + rx * math.sin(a), cy0 - ry * math.cos(a)))
    # Linien zuerst
    for (x, y), (k, lab) in zip(pos, groups):
        hot = k == "body_fins"
        body.append(L(cx0, cy0, x, y, INK if hot else GREY_M, 4 if hot else 2.5, marker="" ))
    # Skelett
    body.append(R(cx0 - 150, cy0 - 52, 300, 104, "#ffffff", INK, 4, 14))
    body.append(T(cx0, cy0 - 8, "Skelett (Master)", 27, "700", INK, "middle"))
    body.append(TL(cx0, cy0 + 20, ["Arme, Motorposition, Trennebene,", "Anschlussradien"], 18, 21, fill=GREY, anchor="middle"))
    for (x, y), (k, lab) in zip(pos, groups):
        hot = k == "body_fins"
        body.append(R(x - bw / 2, y - bh / 2, bw, bh, INK if hot else GREY_L, INK if hot else GREY, 3 if hot else 2, 12))
        body.append(T(x, y - 4, lab, 23, "700", "#ffffff" if hot else INK, "middle"))
        body.append(T(x, y + 22, k, 18, fill="#dddddd" if hot else GREY, anchor="middle", extra='font-family="Consolas, monospace"'))
    # Callout
    hx, hy = pos[4]
    body.append(T(hx + 130, hy - 6, "body_fins.chord = 40", 21, "700", INK, "start", extra='font-family="Consolas, monospace"'))
    body.append(T(hx + 130, hy + 20, "einziger geänderter Parameter", 18, fill=GREY, anchor="start"))
    # Legende unten
    body.append(R(40, 650, 1200, 50, "#ffffff", GREY_M, 2, 10))
    body.append(T(60, 683, "Regel: Jede Gruppe liest nur sich selbst und das Skelett, nie eine andere Gruppe.", 22, "700"))
    body.append(T(1220, 683, "Linie = liest Mass", 20, fill=GREY, anchor="end"))
    body.append(T(40, 100, "Test: Geometrie der übrigen Gruppen bleibt identisch (gleicher Geometrie-Hash).", 22, fill=GREY))
    wrap("fig05_parametergruppen_skelett.svg", "Parametergruppen und Skelett-Methode",
         "Das Skelett in der Mitte enthält die gemeinsamen Schnittstellenmasse. Neun Gruppen lesen nur ihre eigenen Parameter und das Skelett. Beispiel: nur body_fins.chord wird geändert.",
         "\n".join(body))


# ================================================================== Abb. 6
def fig06():
    body = [title("Design-Automation-Pipeline: wo welches Werkzeug seine Stärke hat",
                  "Einordnung nach Erwartung; der Benchmark bestätigt oder widerlegt sie")]
    cw, gap, x0 = 236, 12, 26
    stages = ["Anforderungen", "CAD-Geometrie", "Simulation", "Optimierung", "Fertigung"]
    brep = [None, ["Parametrik, Skelett,", "Baugruppen-Joints,", "Constraints"], ["Masse, Trägheit exakt,", "Balken-FEM,", "Projektionsflächen"],
            ["Parameter-Sweep:", "je Variante neu", "bauen"], ["STEP, bemasste", "Zeichnung,", "Toleranzen"]]
    vox = [None, ["Freiformen, Gitter,", "Kühlkanäle,", "Feldsteuerung"], ["Raster = Gitter für", "Strömung (LBM)", "und Wärme"],
           ["Feldbasiert:", "Wandstärke und", "Gitter variabel"], ["Slices, STL,", "Gitter-Infill", "für 3D-Druck"]]
    for i, s in enumerate(stages):
        x = x0 + i * (cw + gap)
        pts = [(x, 190), (x + cw - 22, 190), (x + cw, 225), (x + cw - 22, 260), (x, 260)]
        if i > 0:
            pts.append((x + 22, 225))
        body.append(P(pts, GREY_L, INK, 2.5))
        body.append(T(x + cw / 2 + (8 if i else 0), 234, s, 22, "700", INK, "middle"))
        if i == 0:
            body.append(R(x, 280, cw, 274, "#ffffff", GREY, 2.5, 10))
            body.append(TL(x + 16, 318, ["Eingaben:", "", "Nutzlast", "Zielgeschwindigkeit", "Bauraum, Material", "", "als Parameterdatei", "(JSON)"], 20, 28))
        else:
            body.append(R(x, 280, cw, 130, BREP_L, BREP, 3, 10))
            body.append(T(x + 14, 306, "B-rep", 19, "700", BREP))
            body.append(TL(x + 14, 336, brep[i], 20, 26))
            body.append(R(x, 424, cw, 130, VOX_L, VOX, 3, 10))
            body.append(T(x + 14, 450, "Voxel", 19, "700", VOX))
            body.append(TL(x + 14, 480, vox[i], 20, 26))
    # Schleife
    lx1 = x0 + 3 * (cw + gap) + cw / 2 + 8
    lx2 = x0 + 1 * (cw + gap) + cw / 2 + 8
    body.append(f'<path d="M{lx1},186 C{lx1},128 {lx2},128 {lx2},184" fill="none" stroke="{INK}" stroke-width="3" marker-end="url(#arrK)"/>')
    body.append(T((lx1 + lx2) / 2, 134, "Schleife: Agent ändert eine Gruppe, Pipeline läuft neu", 20, "700", INK, "middle"))
    # Unteres Band
    body.append(R(26, 578, 1228, 120, "#ffffff", INK, 2.5, 10))
    body.append(T(46, 614, "Schnittstelle zum KI-Agenten in allen Stufen:", 23, "700"))
    body.append(TL(46, 648, ["Code statt Klicks  ·  Parameter als JSON  ·  Aufruf ohne Oberfläche (headless)  ·  Ergebnis als Datei plus Kennzahlen"], 21))
    body.append(T(46, 680, "Das Raster (Voxel) ist ein Vorteil, wenn die Simulation selbst ein Raster braucht; B-rep, wenn Masse und Zeichnung zählen.", 19, fill=GREY))
    wrap("fig06_pipeline_einordnung.svg", "Design-Automation-Pipeline mit Einordnung beider Werkzeuge",
         "Fünf Stufen von Anforderungen bis Fertigung. Pro Stufe eine typische Stärke von B-rep und Voxel. Rückkopplungsschleife von Optimierung zu CAD.",
         "\n".join(body))


# ================================================================== Abb. 7
def fig07():
    body = [title("Genauigkeit gegen Rechenaufwand: die Voxelgrösse ist der Regler",
                  "Qualitatives Schema, keine Messwerte")]
    pl, pr, top, bot = 100, 590, 180, 555
    sizes = ["4", "2", "1", "0.5", "0.25"]

    def xs(px0, idx):
        return px0 + 30 + idx * (pr - pl - 60) / 4.0

    # linkes Panel: Fehler
    px0 = pl
    body.append(T(px0, 150, "Abweichung von der exakten Form", 25, "700"))
    body.append(L(px0, top, px0, bot, INK, 2.5))
    body.append(L(px0, bot, pr, bot, INK, 2.5))
    body.append(T(px0 - 14, top + 6, "gross", 18, fill=GREY, anchor="end"))
    body.append(T(px0 - 14, bot, "klein", 18, fill=GREY, anchor="end"))
    for i, s in enumerate(sizes):
        body.append(L(xs(px0, i), bot, xs(px0, i), bot + 8, INK, 2))
        body.append(T(xs(px0, i), bot + 34, s, 20, anchor="middle"))
    body.append(T((px0 + pr) / 2, bot + 66, "Voxelgrösse in mm  (grob \u2192 fein)", 21, "700", anchor="middle"))
    vals = [1, .5, .25, .125, .0625]
    ypt = lambda v: bot - 12 - v * (bot - top - 30)
    pts = [(xs(px0, i), ypt(v)) for i, v in enumerate(vals)]
    body.append(P(pts, "none", VOX, 5, False))
    for x, y in pts:
        body.append(C(x, y, 7, VOX))
    body.append(L(px0, bot - 10, pr, bot - 10, BREP, 5))
    body.append(T(px0 + 20, bot - 26, "B-rep: nur Zahlengenauigkeit", 21, "700", BREP))
    body.append(T(xs(px0, 0) + 70, ypt(1) + 12, "Voxel: Fehler ~ Zellgrösse", 21, "700", VOX))
    # Toleranz-Linie
    tol = 0.2
    body.append(L(px0, ypt(tol), pr, ypt(tol), GREY, 2.5, "8,5"))
    body.append(T(px0 + 20, ypt(tol) - 10, "geforderte Toleranz", 21, fill=GREY))
    idx_x = 2.4
    xc = xs(px0, idx_x)
    body.append(L(xc, ypt(tol), xc, bot, INK, 2, "4,4"))
    # rechtes Panel: Speicher
    qx0, qr = 700, 1200
    xs2 = lambda idx: qx0 + 30 + idx * (qr - qx0 - 60) / 4.0
    body.append(T(qx0, 150, "Speicher und Rechenzeit (relativ, log. Skala)", 25, "700"))
    body.append(L(qx0, top, qx0, bot, INK, 2.5))
    body.append(L(qx0, bot, qr, bot, INK, 2.5))
    for i, s in enumerate(sizes):
        body.append(L(xs2(i), bot, xs2(i), bot + 8, INK, 2))
        body.append(T(xs2(i), bot + 34, s, 20, anchor="middle"))
    body.append(T((qx0 + qr) / 2, bot + 66, "Voxelgrösse in mm  (grob \u2192 fein)", 21, "700", anchor="middle"))
    ylog = lambda v: bot - 12 - math.log10(v) / 3.7 * (bot - top - 30)
    dense = [1, 8, 64, 512, 4096]
    sparse = [1, 4, 16, 64, 256]
    pd = [(xs2(i), ylog(v)) for i, v in enumerate(dense)]
    ps = [(xs2(i), ylog(v)) for i, v in enumerate(sparse)]
    body.append(P(pd, "none", VOX, 5, False))
    body.append(P(ps, "none", VOX_M, 5, False, "10,6"))
    for x, y in pd:
        body.append(C(x, y, 7, VOX))
    for x, y in ps:
        body.append(C(x, y, 6, VOX_M, VOX, 1.5))
    body.append(L(qx0, ylog(1.6), qr, ylog(1.6), BREP, 5))
    body.append(T(qr, ylog(1.6) - 14, "B-rep: hängt an Feature-Zahl, nicht an Auflösung", 21, "700", BREP, "end", extra=HALO))
    body.append(T(qx0 + 20, top + 36, "dichtes Raster: \u00d78 je Halbierung", 21, "700", VOX, extra=HALO))
    body.append(T(qr, ylog(256) + 44, "dünnbesetzt (nur Oberflächennähe): \u00d74", 21, "700", VOX, "end", extra=HALO))
    xc2 = xs2(idx_x)
    body.append(L(xc2, top + 60, xc2, bot, INK, 2, "4,4"))
    body.append(T(xc2 + 10, bot - 80, "Arbeitspunkt", 21, "700", extra=HALO))
    body.append(T(640, 704, "Erwartung. Messwerte folgen aus  [[ERGEBNIS: B07 Genauigkeit vs. Voxelgrösse]]  und  [[ERGEBNIS: B10 Laufzeit/RAM]].", 19, fill=GREY, anchor="middle", style="italic"))
    wrap("fig07_genauigkeit_vs_voxelgroesse.svg", "Genauigkeit gegen Voxelgrösse und Speicher",
         "Links: Fehler wächst mit der Zellgrösse; B-rep bleibt bei nahezu null. Rechts: Speicher wächst bei feinerem Raster um Faktor 8 (dicht) oder 4 (dünnbesetzt) je Halbierung. Qualitatives Schema.",
         "\n".join(body))


# ================================================================== Abb. 8
def fig08():
    body = [title("Hybrid-Workflow: B-rep für das Bemassbare, Voxel für das Gitterartige")]
    # A
    body.append(R(40, 240, 300, 190, BREP_L, BREP, 3, 14))
    body.append(T(60, 282, "build123d (B-rep)", 26, "700", BREP))
    body.append(TL(60, 320, ["Skelett + Bauteile", "parametrisch, Gruppen,", "Constraints"], 21, 28))
    # B (oben rechts)
    body.append(R(500, 100, 340, 130, "#ffffff", BREP, 3, 14))
    body.append(T(520, 142, "Exakte Ausgabe", 24, "700", BREP))
    body.append(TL(520, 176, ["STEP, Zeichnung, Toleranzen", "für Freigabe, CNC, Doku"], 20, 27))
    # D (unten Mitte)
    body.append(R(500, 380, 340, 200, VOX_L, VOX, 3, 14))
    body.append(T(520, 422, "PicoGK (Voxel)", 26, "700", VOX))
    body.append(TL(520, 460, ["Gitter-Infill, Kühlkanäle,", "variable Wandstärke,", "Glättung der Übergänge"], 21, 28))
    # E
    body.append(R(940, 380, 300, 200, "#ffffff", VOX, 3, 14))
    body.append(T(960, 422, "3D-Druck", 26, "700", VOX))
    body.append(TL(960, 460, ["Slices / STL", "Druckbarkeits-Check", "aus dem Raster"], 21, 28))
    # Pfeile
    body.append(L(340, 300, 500, 180, BREP, 4, marker="arrB"))
    body.append(T(360, 236, "exakt", 20, "700", BREP))
    body.append(L(340, 370, 500, 450, VOX, 4, marker="arrO"))
    body.append(T(356, 462, "Mesh (STL)", 20, "700", VOX))
    body.append(T(356, 486, "+ Voxelgrösse wählen", 19, fill=VOX))
    body.append(L(840, 480, 940, 480, VOX, 4, marker="arrO"))
    body.append(f'<path d="M500,545 C400,620 260,620 190,438" fill="none" stroke="{GREY}" stroke-width="3" stroke-dasharray="9,6" marker-end="url(#arrG)"/>')
    body.append(T(320, 636, "Rückweg nur als Mesh:", 20, "700", GREY, "middle"))
    body.append(T(320, 660, "keine bemassbaren Flächen mehr", 20, fill=GREY, anchor="middle"))
    body.append(R(880, 100, 360, 130, GREY_L, GREY_M, 2, 14))
    body.append(TL(898, 138, ["Wahrheitsquelle bleibt", "das Parametermodell", "(Spec + Skript)."], 20, 27))
    body.append(T(640, 704, "Faustregel: was bemasst, toleriert oder gezeichnet wird \u2192 B-rep.  Was Gitter, Kanal oder Feld ist \u2192 Voxel.", 21, "700", anchor="middle"))
    wrap("fig08_hybrid_workflow.svg", "Hybrid-Workflow aus B-rep und Voxel",
         "build123d erzeugt exakte Ausgaben (STEP, Zeichnung) und ein Mesh, PicoGK ergänzt Gitter, Kühlkanäle und variable Wandstärken für den 3D-Druck. Rückweg nur als Mesh.",
         "\n".join(body))


for f in (fig01, fig02, fig03, fig04, fig05, fig06, fig07, fig08):
    f()
