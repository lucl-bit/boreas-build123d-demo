"""Analysen & vereinfachte Simulationen, die direkt auf der build123d-Geometrie aufsetzen.
Alle Modelle sind bewusst einfach gehalten (Demo) und mit Mock-Daten parametriert."""
from __future__ import annotations

import base64
import io
import math
import os
from dataclasses import replace

import numpy as np
from build123d import Compound, Cylinder, Face, Plane, Pos, export_stl
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from PIL import Image, ImageDraw

import boreas_upper as bu

G = 9.81


# ---------------------------------------------------------------- Hilfen

def _np_mesh(shape, tol=0.2, ang=0.3):
    v, t = bu._tessellate(shape, tol, ang)
    return np.array([(p.X, p.Y, p.Z) for p in v], float), np.array(t, int).reshape(-1, 3)


def colormap(x: np.ndarray) -> np.ndarray:
    """0..1 → blau-cyan-grün-gelb-rot."""
    stops = np.array([[0.19, 0.30, 0.85], [0.10, 0.75, 0.90], [0.25, 0.80, 0.35], [0.98, 0.85, 0.15], [0.90, 0.20, 0.15]])
    x = np.clip(x, 0, 1) * (len(stops) - 1)
    i = np.minimum(x.astype(int), len(stops) - 2)
    f = (x - i)[:, None]
    return stops[i] * (1 - f) + stops[i + 1] * f


def motor_positions(p: bu.Params) -> list[tuple[float, float]]:
    return [(p.arm_reach * math.cos(math.radians(a)), p.arm_reach * math.sin(math.radians(a))) for a in bu.arm_angles(p)]


# ---------------------------------------------------------------- 1. Masse & Trägheit

def _gprops(shape, density_g_mm3: float):
    gp = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape.wrapped, gp)
    m = gp.Mass() * density_g_mm3
    c = gp.CentreOfMass()
    mat = gp.MatrixOfInertia()
    inertia = np.array([[mat.Value(i, j) for j in (1, 2, 3)] for i in (1, 2, 3)]) * density_g_mm3
    return m, np.array([c.X(), c.Y(), c.Z()]), inertia


def _cyl_inertia(m, r, h):
    ixx = m * (3 * r * r + h * h) / 12
    return np.diag([ixx, ixx, m * r * r / 2])


def vehicle_components(p: bu.Params, parts: dict, req: dict, mat: dict, cfg: dict, with_payload=True) -> list:
    """Masse, Schwerpunkt und Trägheit aller Komponenten (g, mm, g·mm²)."""
    comps = []
    for name, part in parts.items():
        m, c, inertia = _gprops(part, mat["density"] / 1000)
        comps.append({"name": f"{name} (CAD)", "m": m, "c": c, "I": inertia, "src": "build123d"})
    z_motor = p.arm_thickness + 0.5 * p.pod_height
    for i, (x, y) in enumerate(motor_positions(p)):
        comps.append({"name": f"Motor {i + 1}", "m": req["motor_mass"], "c": np.array([x, y, z_motor]),
                      "I": _cyl_inertia(req["motor_mass"], req["motor_diameter"] / 2, 0.8 * req["motor_diameter"]), "src": "Mock"})
    if with_payload:
        comps.append({"name": "Nutzlast", "m": req["payload_mass"], "c": np.array([0, 0, 2 + req["payload_length"] / 2]),
                      "I": _cyl_inertia(req["payload_mass"], req["payload_diameter"] / 2, req["payload_length"]), "src": "Mock"})
    fl = cfg["flight"]
    comps.append({"name": "Akku (Unterteil)", "m": req["battery_mass"], "c": np.array([0, 0, fl["battery_position_z_mm"]]),
                  "I": _cyl_inertia(req["battery_mass"], fl["battery_radius_mm"], fl["battery_length_mm"]), "src": "Mock"})
    return comps


def combine_inertia(comps: list) -> dict:
    m = sum(c["m"] for c in comps)
    com = sum(c["m"] * c["c"] for c in comps) / m
    total = np.zeros((3, 3))
    for c in comps:
        d = c["c"] - com
        total += c["I"] + c["m"] * (d @ d * np.eye(3) - np.outer(d, d))
    principal = np.linalg.eigvalsh(total)
    return {"mass_g": m, "com_mm": com, "I_gmm2": total, "I_kgm2": total * 1e-9, "principal_kgm2": principal * 1e-9}


def inertia_report(p, parts, req, mat, cfg) -> dict:
    comps = vehicle_components(p, parts, req, mat, cfg)
    tot = combine_inertia(comps)
    rows = [[c["name"], f"{c['m']:.1f}", f"{c['c'][0]:.1f}", f"{c['c'][1]:.1f}", f"{c['c'][2]:.1f}", c["src"]] for c in comps]
    return {"components": comps, "total": tot, "rows": rows}


# ---------------------------------------------------------------- 2. Kollision

def clash_check(p: bu.Params, parts: dict, accessories: dict, req: dict) -> dict:
    z_disc = p.arm_thickness + p.pod_height + 1
    discs = [Pos(x, y, z_disc - 1.5) * Cylinder(req["prop_diameter"] / 2, 3, align=bu.MIN) for x, y in motor_positions(p)]
    pairs = [(f"Propellerkreis {i + 1}", d, name, part) for i, d in enumerate(discs)
             for name, part in parts.items() if name != "Gondeln"]
    n = len(discs)
    pairs += [(f"Propellerkreis {i + 1}", discs[i], f"Propellerkreis {(i + 1) % n + 1}", discs[(i + 1) % n]) for i in range(n)]
    if "Kabel" in accessories:
        pairs.append(("Kabel", accessories["Kabel"], "Rumpf", parts["Rumpf"]))
    rows, hits = [], []
    for a_name, a, b_name, b in pairs:
        dist = a.distance_to(b)
        vol = 0.0
        if dist < 1e-6:
            inter = a & b
            vol = inter.volume if inter is not None else 0.0
            if vol > 1e-3:
                hits.append(inter)
        rows.append({"a": a_name, "b": b_name, "distance": dist, "overlap_mm3": vol, "ok": vol <= 1e-3})
    return {"rows": rows, "hits": hits, "discs": discs}


# ---------------------------------------------------------------- 3. FEM Ausleger

def arm_sections(p: bu.Params, body, n_stations: int = 60) -> dict:
    a = math.radians(p.arm_angle)
    d = np.array([math.cos(a), math.sin(a), 0.0])
    e = np.array([-math.sin(a), math.cos(a), 0.0])
    pad_r = bu.derived(p)["pad_radius"]
    gh = p.gusset_height if p.gusset_height >= 1 else 0
    width = max(p.arm_width, 2 * pad_r) + 4
    height = p.arm_thickness + gh + 8
    zc = (p.arm_thickness + gh) / 2
    s0 = p.body_radius + 0.3
    stations = np.linspace(s0, p.arm_reach, n_stations)
    rows = []
    for s in stations:
        o = s * d
        rect = Face.make_rect(width, height, Plane(origin=(o[0], o[1], zc), x_dir=tuple(e), z_dir=tuple(d)))
        sec = body.intersect(rect)
        faces = sec.faces() if sec is not None else []
        if not faces:
            rows.append((s, 0.0, 0.0, 0.0))
            continue
        gp = GProp_GProps()
        for f in faces:
            fp = GProp_GProps()
            BRepGProp.SurfaceProperties_s(f.wrapped, fp)
            gp.Add(fp)
        area = gp.Mass()
        m = gp.MatrixOfInertia()
        inertia = sum(e[i] * e[j] * m.Value(i + 1, j + 1) for i in range(3) for j in range(3))
        cz = gp.CentreOfMass().Z()
        bb = Compound(faces).bounding_box()
        c = max(bb.max.Z - cz, cz - bb.min.Z)
        rows.append((s, area, inertia, c))
    arr = np.array(rows)
    return {"s": arr[:, 0], "A": arr[:, 1], "I": arr[:, 2], "c": arr[:, 3]}


def beam_fem(p: bu.Params, body, req: dict, mat: dict, parts: dict | None = None) -> dict:
    """1D-Euler-Bernoulli-FE, Steifigkeit aus echten CAD-Querschnitten. Kragarm an der Rohrwand, Schub an der Spitze."""
    sec = arm_sections(p, body)
    s, inertia, c = sec["s"], np.maximum(sec["I"], 1e-3), sec["c"]
    E, F = mat["E"], req["thrust_per_motor"]
    n = len(s)
    K = np.zeros((2 * n, 2 * n))
    for k in range(n - 1):
        L = s[k + 1] - s[k]
        EI = E * 0.5 * (inertia[k] + inertia[k + 1])
        ke = EI / L ** 3 * np.array([[12, 6 * L, -12, 6 * L], [6 * L, 4 * L * L, -6 * L, 2 * L * L],
                                     [-12, -6 * L, 12, -6 * L], [6 * L, 2 * L * L, -6 * L, 4 * L * L]])
        idx = [2 * k, 2 * k + 1, 2 * k + 2, 2 * k + 3]
        K[np.ix_(idx, idx)] += ke
    f = np.zeros(2 * n)
    f[-2] = F
    free = np.arange(2, 2 * n)
    u = np.zeros(2 * n)
    u[free] = np.linalg.solve(K[np.ix_(free, free)], f[free])
    w = u[0::2]
    moment = F * (p.arm_reach - s)
    stress = moment * c / inertia
    max_i = int(np.argmax(stress))
    analytic = bu.arm_deflection(p, F, E)
    k_tip = F / max(w[-1], 1e-9) * 1000
    arm_mass = float(np.trapezoid(sec["A"], s)) * mat["density"] / 1000
    pod_mass = parts["Gondeln"].volume * mat["density"] / 1000 / p.arm_count if parts else 0
    m_eff = (req["motor_mass"] + pod_mass + 0.24 * arm_mass) / 1000
    f1 = math.sqrt(k_tip / m_eff) / (2 * math.pi)
    return {
        "s": s, "w": w, "stress": stress, "A": sec["A"], "I": inertia,
        "tip_deflection": float(w[-1]), "analytic_deflection": analytic,
        "max_stress": float(stress[max_i]), "max_stress_at": float(s[max_i]),
        "safety_factor": mat["yield"] / max(float(stress[max_i]), 1e-9),
        "f1_hz": f1, "k_tip_n_per_m": k_tip,
    }


def stress_colors(p: bu.Params, mesh_vertices: list, fem: dict) -> list:
    v = np.array(mesh_vertices, float).reshape(-1, 3)
    pad_r = bu.derived(p)["pad_radius"]
    out = np.tile([0.62, 0.66, 0.70], (len(v), 1))
    smax = max(float(fem["stress"].max()), 1e-9)
    for a in bu.arm_angles(p):
        r = math.radians(a)
        d, e = np.array([math.cos(r), math.sin(r), 0]), np.array([-math.sin(r), math.cos(r), 0])
        s, lat = v @ d, np.abs(v @ e)
        z_top = p.arm_thickness + (p.gusset_height if p.gusset_height >= 1 else 0) + 0.5
        mask = ((s >= p.body_radius - 0.2) & (lat <= pad_r + 0.5) & (s <= p.arm_reach + pad_r + 0.5)
                & (v[:, 2] <= z_top))
        sig = np.interp(s[mask], fem["s"], fem["stress"])
        out[mask] = colormap(sig / smax)
    return [round(x, 3) for x in out.ravel()]


# ---------------------------------------------------------------- 4. Aerodynamik

def _silhouette(v: np.ndarray, t: np.ndarray, axes: tuple[int, int], res: float = 0.4):
    uv = v[:, axes]
    lo = uv.min(0) - 2
    size = np.ceil((uv.max(0) + 2 - lo) / res).astype(int)
    img = Image.new("L", (int(size[0]), int(size[1])), 0)
    draw = ImageDraw.Draw(img)
    px = (uv - lo) / res
    px[:, 1] = size[1] - px[:, 1]
    for tri in t:
        draw.polygon([tuple(px[i]) for i in tri], fill=255)
    area = (np.asarray(img) > 0).sum() * res * res
    thumb = img.copy()
    thumb.thumbnail((360, 360))
    rgba = Image.new("RGBA", thumb.size, (0, 0, 0, 0))
    rgba.paste((111, 207, 151, 255), mask=thumb)
    buf = io.BytesIO()
    rgba.save(buf, "PNG")
    return area, "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def aero(p: bu.Params, parts: dict, mass_g: float, req: dict, cfg: dict) -> dict:
    v, t = _np_mesh(Compound(list(parts.values())))
    a_front, img_front = _silhouette(v, t, (1, 2))
    a_top, img_top = _silhouette(v, t, (0, 1))
    ac = cfg["aero"]
    m = mass_g / 1000
    t_max = p.arm_count * req["thrust_per_motor"]
    tilt_lim = math.degrees(math.acos(min(1.0, m * G / t_max))) if t_max > m * G else 0.0
    tilt_max = min(tilt_lim, ac["max_tilt_deg"])
    tilts = np.linspace(0.5, max(tilt_max, 1), 40)
    cda = ac["cd_front"] * a_front * 1e-6 * np.cos(np.radians(tilts)) + ac["cd_top"] * a_top * 1e-6 * np.sin(np.radians(tilts))
    speed = np.sqrt(2 * m * G * np.tan(np.radians(tilts)) / (ac["rho"] * cda))
    drag = 0.5 * ac["rho"] * speed ** 2 * cda
    return {
        "A_front_mm2": a_front, "A_top_mm2": a_top, "img_front": img_front, "img_top": img_top,
        "tilt": tilts, "speed": speed, "drag": drag, "power_w": drag * speed,
        "v_max": float(speed[-1]) if tilt_max > 0 else 0.0, "tilt_max": tilt_max,
        "fineness": p.nose_length / (2 * p.body_radius),
    }


# ---------------------------------------------------------------- 5. Flugdynamik

def roll_step(p: bu.Params, inertia_kgm2: np.ndarray, mass_g: float, req: dict, cfg: dict) -> dict:
    fl = cfg["flight"]
    ixx = float(inertia_kgm2[0, 0])
    n = p.arm_count
    t_max = req["thrust_per_motor"]
    t_hover = mass_g / 1000 * G / n
    dt_max = max(0.0, min(t_max - t_hover, t_hover))
    lever = sum(abs(y) for _, y in motor_positions(p)) / 1000
    tau_max = dt_max * lever
    wn, zeta, tm = fl["omega_n"], fl["zeta"], fl["motor_time_constant_s"]
    # Regler ist fest auf die Referenzdrohne abgestimmt → andere Trägheit = anderes Verhalten
    i_ref = fl["ref_Ixx_kgm2"]
    kp, kd = i_ref * wn ** 2, 2 * zeta * wn * i_ref
    target = math.radians(fl["step_deg"])
    dt, T = 0.0005, 1.2
    th = om = tau = 0.0
    ts, ths, taus = [], [], []
    for k in range(int(T / dt)):
        cmd = max(-tau_max, min(tau_max, kp * (target - th) - kd * om))
        tau += (cmd - tau) * dt / tm
        om += tau / ixx * dt
        th += om * dt
        if k % 10 == 0:
            ts.append(k * dt)
            ths.append(math.degrees(th))
            taus.append(tau)
    ths_a = np.array(ths)
    step = fl["step_deg"]
    try:
        t10 = ts[int(np.argmax(ths_a >= 0.1 * step))]
        t90 = ts[int(np.argmax(ths_a >= 0.9 * step))]
        rise = t90 - t10 if ths_a.max() >= 0.9 * step else float("nan")
    except IndexError:
        rise = float("nan")
    return {
        "t": ts, "theta": ths, "tau": taus, "Ixx": ixx, "tau_max": tau_max, "alpha_max": tau_max / ixx,
        "hover_throttle": t_hover / t_max, "rise_time": rise, "overshoot": max(0.0, (ths_a.max() - step) / step * 100),
    }


# ---------------------------------------------------------------- 6. Fertigung

def manufacturing(parts: dict, mat: dict, cfg: dict) -> dict:
    mf = cfg["manufacturing"]
    cos_lim = math.cos(math.radians(mf["overhang_angle_deg"]))
    out = {}
    for name, part in parts.items():
        v, t = _np_mesh(part, 0.15, 0.25)
        p0, p1, p2 = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
        cr = np.cross(p1 - p0, p2 - p0)
        area = np.linalg.norm(cr, axis=1) / 2
        nz = cr[:, 2] / np.maximum(np.linalg.norm(cr, axis=1), 1e-12)
        zmin = v[:, 2].min()
        on_bed = np.minimum(np.minimum(p0[:, 2], p1[:, 2]), p2[:, 2]) < zmin + 0.3
        over = (nz < -cos_lim) & ~on_bed
        vflag = np.zeros(len(v), bool)
        vflag[t[over].ravel()] = True
        base = np.array(bu.PART_STYLE[name]) * 0.35 + 0.45
        colors = np.where(vflag[:, None], [0.93, 0.25, 0.25], base)
        bb = part.bounding_box()
        dims = sorted([bb.size.X, bb.size.Y])
        fits = {pr: (dims[0] <= min(xy[:2]) and dims[1] <= max(xy[:2]) and bb.size.Z <= xy[2])
                for pr, xy in cfg["printers"].items()}
        vol = part.volume / 1000
        over_pct = float(area[over].sum() / area.sum() * 100)
        hours = vol * (1 + 0.5 * over_pct / 100) / mf["flow_cm3_per_h"]
        mass = vol * mat["density"]
        out[name] = {
            "vertices": [round(x, 3) for x in v.ravel()], "triangles": t.ravel().tolist(),
            "colors": [round(x, 3) for x in colors.ravel()],
            "overhang_pct": over_pct, "overhang_cm2": float(area[over].sum() / 100),
            "size": [bb.size.X, bb.size.Y, bb.size.Z], "fits": fits,
            "print_h": hours, "mass_g": mass,
            "cost": mass / 1000 * mat["price_kg"] + hours * mf["machine_rate_per_h"],
        }
    return out


# ---------------------------------------------------------------- 7. Design-Optimierung

def design_sweep(p: bu.Params, req: dict, mat: dict, limits: dict, base_mass_g: float,
                 thicknesses=None, widths=None) -> dict:
    """CAD im Loop: für jede Kombination wird der Arm mit build123d gebaut und sein Volumen gemessen."""
    thicknesses = thicknesses or [2, 3, 4, 5, 6, 8, 10]
    widths = widths or [8, 11, 14, 18, 22]
    arm0 = bu.build_arm(p).volume
    L = p.arm_reach - p.body_radius
    F = req["thrust_per_motor"]
    pts = []
    combos = [(t, w) for t in thicknesses for w in widths]
    if (p.arm_thickness, p.arm_width) not in combos:
        combos.append((p.arm_thickness, p.arm_width))  # aktuelles Design immer mitbewerten
    for t, w in combos:
        q = replace(p, arm_thickness=float(t), arm_width=float(w), lightening_slots=0 if w < 10 else p.lightening_slots)
        vol = bu.build_arm(q).volume
        mass = base_mass_g + p.arm_count * (vol - arm0) / 1000 * mat["density"]
        inertia = w * t ** 3 / 12
        defl = F * L ** 3 / (3 * mat["E"] * inertia)
        stress = F * L * (t / 2) / inertia
        ok = defl <= limits["max_deflection"] and stress <= mat["yield"] / limits["min_safety_factor"]
        pts.append({"t": t, "w": w, "mass": mass, "defl": defl, "stress": stress, "ok": ok,
                    "current": (t, w) == (p.arm_thickness, p.arm_width)})
    pareto = []
    for a in sorted(pts, key=lambda r: r["mass"]):
        if not pareto or a["defl"] < pareto[-1]["defl"]:
            pareto.append(a)
    feasible = [r for r in pts if r["ok"]]
    best = min(feasible, key=lambda r: r["mass"]) if feasible else None
    return {"points": pts, "pareto": pareto, "best": best, "n_cad": len(pts)}


# ---------------------------------------------------------------- 8. Simulator-Export (URDF)

URDF_TMPL = """<?xml version="1.0"?>
<!-- Automatisch erzeugt aus build123d (Boreas-Demo). Masse/Trägheit aus CAD + Mock-Komponenten. -->
<robot name="boreas_{name}">
  <link name="base_link">
    <inertial>
      <origin xyz="{cx:.5f} {cy:.5f} {cz:.5f}" rpy="0 0 0"/>
      <mass value="{m:.5f}"/>
      <inertia ixx="{ixx:.6e}" ixy="{ixy:.6e}" ixz="{ixz:.6e}" iyy="{iyy:.6e}" iyz="{iyz:.6e}" izz="{izz:.6e}"/>
    </inertial>
    <visual><geometry><mesh filename="meshes/base.stl" scale="0.001 0.001 0.001"/></geometry></visual>
    <collision><geometry><mesh filename="meshes/base.stl" scale="0.001 0.001 0.001"/></geometry></collision>
  </link>
{rotors}
</robot>
"""

ROTOR_TMPL = """  <link name="rotor_{i}">
    <inertial><mass value="{m:.5f}"/><inertia ixx="{ixx:.3e}" ixy="0" ixz="0" iyy="{ixx:.3e}" iyz="0" izz="{izz:.3e}"/></inertial>
    <visual><geometry><mesh filename="meshes/rotor.stl" scale="0.001 0.001 0.001"/></geometry></visual>
  </link>
  <joint name="rotor_{i}_joint" type="continuous">
    <parent link="base_link"/><child link="rotor_{i}"/>
    <origin xyz="{x:.5f} {y:.5f} {z:.5f}" rpy="0 0 0"/><axis xyz="0 0 {dir}"/>
  </joint>"""


def export_urdf(p: bu.Params, parts: dict, inertia_total: dict, req: dict, out_dir: str, name="variante") -> dict:
    os.makedirs(os.path.join(out_dir, "meshes"), exist_ok=True)
    export_stl(Compound(list(parts.values())), os.path.join(out_dir, "meshes", "base.stl"), tolerance=0.1)
    prop = bu.build_propeller(req["prop_diameter"])
    export_stl(prop, os.path.join(out_dir, "meshes", "rotor.stl"), tolerance=0.1)
    m_rot = prop.volume * 1.2e-6  # kg, Mock-Dichte Kunststoff
    r = req["prop_diameter"] / 2000
    rotors = "\n".join(ROTOR_TMPL.format(i=i, m=m_rot, ixx=m_rot * r * r / 12, izz=m_rot * r * r / 3,
                                         x=x / 1000, y=y / 1000, z=(p.arm_thickness + p.pod_height + 1) / 1000,
                                         dir=1 if i % 2 == 0 else -1)
                       for i, (x, y) in enumerate(motor_positions(p)))
    inertia = inertia_total["I_kgm2"]
    com = inertia_total["com_mm"] / 1000
    text = URDF_TMPL.format(name=name, cx=com[0], cy=com[1], cz=com[2], m=inertia_total["mass_g"] / 1000,
                            ixx=inertia[0, 0], ixy=inertia[0, 1], ixz=inertia[0, 2], iyy=inertia[1, 1],
                            iyz=inertia[1, 2], izz=inertia[2, 2], rotors=rotors)
    path = os.path.join(out_dir, "boreas.urdf")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return {"path": path, "text": text}
