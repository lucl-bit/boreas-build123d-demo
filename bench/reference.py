"""Referenzgeometrie (Mohammed_0.1 Full Shell.step): Tessellierung, Cache, Ausrichtung ins Modell-KS.

Aufruf:  python -m bench.reference [--force]

Erzeugt in bench/reference/:
    upper/lower/nose/nose_cap/nose_insert/full .stl   Tessellierung im PLAN.md-Koordinatensystem
                         (Datei-KS = Modell-KS - offset_to_model), reference_transform.json dokumentiert das
    reference_meta.json  Offset, Abdeckung, exakte OCC-Kennwerte, Mesh-Metriken, Stirnflaechen
Teile: upper = Shell 3, lower = Shell 0, nose = Shell 1+2 (nose_cap = 1, nose_insert = 2).

Koordinatensystem (PLAN.md): mm, Z oben, Ursprung auf der Rumpfachse in der Trennebene Oberteil/Unterteil.
Der Offset wird aus der Geometrie bestimmt (nicht hartkodiert):
  Achse (X,Y) = Kreisfit-Mittel ueber Schichten von Nasenkappe und Oberteil-Rohr,
  Trennebene Z = kleinste Z-Koordinate des Oberteils (Shell 3).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from bench import metrics as M

HERE = Path(__file__).resolve().parent
REF_DIR = HERE / "reference"
STEP = HERE.parent / "Mohammed_0.1 Full Shell.step"
META = REF_DIR / "reference_meta.json"
SHELL_OF = {"lower": [0], "nose_cap": [1], "nose_insert": [2], "upper": [3]}
PARTS = ("upper", "lower", "nose")  # Teile, die mit den Tool-Ausgaben verglichen werden
LIN_TOL, ANG_TOL = 0.05, 0.1


def _tessellate_shell(shell):
    """Ganze Schale vermaschen (gemeinsame Kanten), Flaechen ohne Triangulierung ueberspringen.

    Rueckgabe (tris (N,3,3), Liste der Flaechen ohne Netz mit Flaeche in mm2)."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_REVERSED
    from OCP.TopLoc import TopLoc_Location

    BRepMesh_IncrementalMesh(shell.wrapped, LIN_TOL, False, ANG_TOL, True)
    tris, failed = [], []
    for f in shell.faces():
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(f.wrapped, loc)
        if tri is None or tri.NbTriangles() == 0:
            failed.append(float(f.area))
            continue
        tr = loc.Transformation()
        nodes = [tri.Node(k).Transformed(tr) for k in range(1, tri.NbNodes() + 1)]
        V = np.array([[p.X(), p.Y(), p.Z()] for p in nodes])
        T = np.array([[tri.Triangle(k).Value(1), tri.Triangle(k).Value(2), tri.Triangle(k).Value(3)]
                      for k in range(1, tri.NbTriangles() + 1)]) - 1
        if f.wrapped.Orientation() == TopAbs_REVERSED:
            T = T[:, [0, 2, 1]]
        tris.append(V[T])
    return (np.concatenate(tris) if tris else np.zeros((0, 3, 3))), failed


def _fit_circle(P):
    A = np.c_[2 * P[:, 0], 2 * P[:, 1], np.ones(len(P))]
    b = (P ** 2).sum(1)
    x = np.linalg.lstsq(A, b, rcond=None)[0]
    return float(x[0]), float(x[1]), float(np.sqrt(x[2] + x[0] ** 2 + x[1] ** 2))


def find_alignment(upper: np.ndarray, nose: np.ndarray) -> dict:
    """Bestimmt Rumpfachse (X,Y) und Trennebene Z aus der Geometrie."""
    fits = []
    Pn = nose.reshape(-1, 3)
    zmin, zmax = Pn[:, 2].min(), Pn[:, 2].max()
    for z0 in np.linspace(zmin, zmax - 5, 12):
        Q = Pn[(Pn[:, 2] >= z0) & (Pn[:, 2] < z0 + 4)][:, :2]
        if len(Q) > 50:
            fits.append(_fit_circle(Q))
    Pu = upper.reshape(-1, 3)
    z_split = float(Pu[:, 2].min())
    z_top = float(Pu[:, 2].max())
    # Oberteil-Rohr oberhalb der Knotenbleche (obere 40 % der Hoehe) -> nur Rohr, keine Arme
    for z0 in np.linspace(z_split + 0.6 * (z_top - z_split), z_top - 4, 8):
        Q = Pu[(Pu[:, 2] >= z0) & (Pu[:, 2] < z0 + 4)][:, :2]
        if len(Q) > 50:
            f = _fit_circle(Q)
            if 20 < f[2] < 45:
                fits.append(f)
    F = np.array(fits)
    ax, ay = float(np.median(F[:, 0])), float(np.median(F[:, 1]))
    return {"axis_x": ax, "axis_y": ay, "split_z": z_split, "n_fits": int(len(F)),
            "axis_scatter_mm": [float(F[:, 0].std()), float(F[:, 1].std())],
            "offset_to_model": [-ax, -ay, -z_split]}


def build_reference(force: bool = False, verbose: bool = True) -> dict:
    """Erzeugt den Cache (falls noetig) und liefert die Metadaten."""
    if META.exists() and not force:
        return json.loads(META.read_text(encoding="utf-8"))
    from build123d import import_step
    REF_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    comp = import_step(str(STEP))
    shells = comp.shells()
    meshes: dict[str, np.ndarray] = {}
    meta: dict = {"source": STEP.name, "tessellation": {"linear_tol_mm": LIN_TOL, "angular_tol_rad": ANG_TOL},
                  "shells": {}, "note": "Tessellierung ganzer Schalen; Flaechen ohne Triangulierung werden uebersprungen und gezaehlt."}
    for name, idxs in SHELL_OF.items():
        tris_l, n_faces, failed, occ_area = [], 0, [], 0.0
        for i in idxs:
            t, fl = _tessellate_shell(shells[i])
            tris_l.append(t)
            n_faces += len(shells[i].faces())
            failed += fl
            occ_area += float(shells[i].area)
        tris = np.concatenate(tris_l)
        meshes[name] = tris
        cov = 1.0 - sum(failed) / occ_area
        meta["shells"][name] = {
            "step_shells": idxs, "faces_total": n_faces, "faces_failed": len(failed),
            "area_failed_mm2": float(sum(failed)), "occ_area_mm2": occ_area,
            "coverage_area_fraction": cov, "coverage_face_fraction": 1 - len(failed) / n_faces,
        }
        if name in ("upper", "lower"):
            from build123d import Solid
            so = Solid(shells[idxs[0]])
            meta["shells"][name]["occ_volume_mm3"] = float(so.volume)
            meta["shells"][name]["occ_solid_valid"] = bool(so.is_valid)
    meshes["nose"] = np.concatenate([meshes["nose_cap"], meshes["nose_insert"]])
    meta["shells"]["nose"] = {"step_shells": [1, 2], "note": "nose = nose_cap + nose_insert (Schalen offen, Volumen aus Mesh unzuverlaessig)",
                              "occ_area_mm2": meta["shells"]["nose_cap"]["occ_area_mm2"] + meta["shells"]["nose_insert"]["occ_area_mm2"],
                              "coverage_area_fraction": 1.0}

    al = find_alignment(meshes["upper"], meshes["nose_cap"])
    meta["alignment"] = al
    off = np.array(al["offset_to_model"])
    meta["parts"] = {}
    for name, tris in meshes.items():
        M.write_stl(REF_DIR / f"{name}.stl", tris + off, "Boreas reference, model coords")
        m = M.mesh_metrics(tris + off)
        m["frontal_area_z_mm2"] = M.projected_area(tris + off, "z")
        m["frontal_area_x_mm2"] = M.projected_area(tris + off, "x")
        meta["parts"][name] = m
    full = np.concatenate([meshes[k] for k in ("upper", "lower", "nose_cap", "nose_insert")]) + off
    M.write_stl(REF_DIR / "full.stl", full, "Boreas reference full, model coords")
    meta["full_model_aligned"] = {"bbox_mm": M.mesh_metrics(full)["bbox_mm"], "area_mm2": M.mesh_metrics(full)["area_mm2"],
                                  "frontal_area_z_mm2": M.projected_area(full, "z"),
                                  "frontal_area_x_mm2": M.projected_area(full, "x")}
    meta["build_seconds"] = round(time.time() - t0, 1)
    META.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    (REF_DIR / "reference_transform.json").write_text(json.dumps({
        "description": "Referenz-STLs (Mohammed_0.1 Full Shell.step) sind bereits ins PLAN.md-Koordinatensystem transformiert: "
                       "p_model = p_file + offset_to_model (nur Translation, keine Rotation). Ursprung = Rumpfachse in der "
                       "Trennebene Oberteil/Unterteil, Z nach oben, mm.",
        "offset_to_model_mm": al["offset_to_model"],
        "axis_xy_in_file_mm": [al["axis_x"], al["axis_y"]], "split_z_in_file_mm": al["split_z"],
        "axis_fit_scatter_mm": al["axis_scatter_mm"],
        "files": {
            "upper.stl": "Oberteil = STEP-Shell 3",
            "lower.stl": "Unterteil = STEP-Shell 0 (Z ca. -131.4 .. +2.6, Zapfen ragt 2.6 mm ueber die Trennebene)",
            "nose.stl": "Nase komplett = Shell 1 (Kappe) + Shell 2 (Einsatz) zusammen",
            "nose_cap.stl": "nur Nasenkappe = Shell 1", "nose_insert.stl": "nur Einsatz = Shell 2",
            "full.stl": "alle vier Shells (upper + lower + nose_cap + nose_insert)",
        },
        "note": "Die Nase liegt in der Referenz ca. 82 mm ueber dem Oberteil-Ende (Z 199 .. 300 im Modell-KS; Oberteil endet bei Z 117.1): "
                "Explosionsdarstellung, nicht Sitz-Position. Tessellierung: lin. Toleranz %.2f mm; Netze sind keine "
                "wasserdichten Volumenkoerper (Schalen aus einzelnen Flaechen, offene Kanten) -> Volumen aus Mesh nur naeherungsweise, "
                "OCC-Kennwerte stehen in reference_meta.json." % LIN_TOL,
        "coverage": {k: v.get("coverage_area_fraction") for k, v in meta["shells"].items()},
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    if verbose:
        print(json.dumps({"alignment": al, "coverage": {k: v.get("coverage_area_fraction") for k, v in meta["shells"].items()}}, indent=1))
    return meta


_CACHE: dict = {}


def load_reference(aligned: bool = True) -> dict[str, np.ndarray]:
    """Teile der Referenz (upper, lower, nose, nose_cap, nose_insert) als Dreiecksarrays; baut den Cache bei Bedarf."""
    key = "aligned" if aligned else "file"
    if key in _CACHE:
        return _CACHE[key]
    meta = build_reference()
    out = {n: M.read_stl(REF_DIR / f"{n}.stl") for n in ("upper", "lower", "nose", "nose_cap", "nose_insert")}
    if not aligned:
        off = np.array(meta["alignment"]["offset_to_model"])
        out = {n: t - off for n, t in out.items()}
    _CACHE[key] = out
    return out


def reference_meta() -> dict:
    return build_reference()


def compare_to_reference(part_tris: np.ndarray, part: str, do_icp: bool = True) -> dict:
    """Vergleicht ein Teil-Mesh (Modell-KS) mit dem ausgerichteten Referenzteil.

    Ergebnis: Abweichung nur mit Offset ('offset_only') und - falls do_icp - nach starrer ICP
    ('after_icp') samt Resttransformation (Rotation in Grad, Translation in mm).
    Bei Zentroid-Abstand > 5 mm (z. B. Nase, die in der Referenz verschoben liegt) wird vor der ICP
    um den Schwerpunktabstand vorverschoben; dieser Wert steht in 'pre_translation_mm'.
    """
    refs = load_reference(True)
    ref = refs["nose_cap"] if part == "nose" and "nose_cap" in refs else refs[part]
    out = {"part": part, "reference_triangles": int(len(ref))}
    if part in ("nose", "nose_insert"):
        # Die Nase liegt in der STEP-Datei explodiert (~90 mm zu hoch): an der Spitze (max. Z) ausrichten
        dz = float(part_tris[..., 2].max() - ref[..., 2].max())
        ref = ref + np.array([0.0, 0.0, dz])
        out["explosion_shift_z_mm"] = dz
    idx_ref = M.SurfaceIndex(ref, 500_000)
    out["offset_only"] = M.deviation(part_tris, ref, n_query=120_000, n_index=500_000, index_b=idx_ref)
    if do_icp:
        c_part, c_ref = part_tris.reshape(-1, 3).mean(0), ref.reshape(-1, 3).mean(0)
        pre = c_ref - c_part if np.linalg.norm(c_ref - c_part) > 5.0 else np.zeros(3)
        start = part_tris + pre
        res = M.icp(start, ref, index_dst=idx_ref)
        moved = M.apply_transform(start, res["R"], res["t_mm"])
        res["pre_translation_mm"] = [float(x) for x in pre]
        res["total_translation_mm"] = [float(x) for x in (np.asarray(res["R"]) @ pre + np.asarray(res["t_mm"]))]
        res["total_translation_norm_mm"] = float(np.linalg.norm(res["total_translation_mm"]))
        out["icp"] = res
        out["after_icp"] = M.deviation(moved, ref, n_query=120_000, n_index=500_000, index_b=idx_ref)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Referenz tessellieren und ausrichten")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    meta = build_reference(force=a.force)
    print("Meta:", META)
    return 0 if meta else 1


if __name__ == "__main__":
    sys.exit(main())
