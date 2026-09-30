"""Werkzeug-neutrale Mesh-Metriken fuer den Boreas-Benchmark (nur numpy/scipy/PIL).

Alle Zahlen werden aus den ausgegebenen STL-Dateien berechnet, nicht aus den Selbstauskuenften
der Tools. Einheiten: mm, mm^2, mm^3, mm^5 (Traegheit bei Dichte 1).

Oeffentliche Funktionen:
    read_stl / write_stl        binaeres oder ASCII-STL <-> (N,3,3)-Array
    mesh_metrics(tris)          Topologie, Volumen, Flaeche, BBox, Schwerpunkt, Traegheit
    deviation(a, b)             Abweichung a->b und b->a (Punkt-zu-Dreieck, flaechengewichtet)
    projected_area(tris, axis)  Stirnflaeche durch Rasterung der Projektion
    icp(src, dst)               starre ICP-Verfeinerung (getrimmt), gibt Resttransformation zurueck
    meshes_differ(a, b)         Geometrie-Vergleich (fuer B03-Gruppenunabhaengigkeit)
"""
from __future__ import annotations

import os
import struct
import time
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

# --------------------------------------------------------------------------- STL I/O

_BIN_DTYPE = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("attr", "<u2")])


def read_stl(path) -> np.ndarray:
    """Liest binaeres oder ASCII-STL, Rueckgabe (N,3,3) float64."""
    path = Path(path)
    size = path.stat().st_size
    with open(path, "rb") as fh:
        head = fh.read(84)
    if len(head) >= 84:
        n = struct.unpack("<I", head[80:84])[0]
        if 84 + 50 * n == size:
            data = np.fromfile(path, dtype=_BIN_DTYPE, count=n, offset=84)
            return data["v"].astype(np.float64)
    # ASCII
    txt = path.read_text(errors="ignore")
    vals = []
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith("vertex"):
            vals.append([float(x) for x in s.split()[1:4]])
    arr = np.asarray(vals, dtype=np.float64)
    if len(arr) % 3:
        raise ValueError(f"{path}: ungueltiges STL (Vertexzahl {len(arr)} nicht durch 3 teilbar)")
    return arr.reshape(-1, 3, 3)


def write_stl(path, tris: np.ndarray, header: str = "bench") -> None:
    """Schreibt binaeres STL."""
    tris = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.divide(n, ln, out=np.zeros_like(n), where=ln > 0)
    rec = np.zeros(len(tris), dtype=_BIN_DTYPE)
    rec["n"] = n
    rec["v"] = tris
    with open(path, "wb") as fh:
        fh.write(header.encode()[:80].ljust(80, b"\0"))
        fh.write(struct.pack("<I", len(tris)))
        fh.write(rec.tobytes())


# --------------------------------------------------------------------------- Topologie

def weld(tris: np.ndarray, tol: float = 1e-3):
    """Verschweisst Vertices auf einem Raster der Weite tol. Rueckgabe (verts, faces[N,3])."""
    flat = tris.reshape(-1, 3)
    key = np.round(flat / tol).astype(np.int64)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    verts = uniq.astype(np.float64) * tol
    return verts, inv.reshape(-1, 3)


def topology(tris: np.ndarray, tol: float = 1e-3) -> dict:
    """Wasserdichtheit, Nicht-Mannigfaltigkeit, Orientierung, Komponenten, Euler-Charakteristik."""
    if len(tris) == 0:
        return {"watertight": False, "open_edges": 0, "non_manifold_edges": 0, "triangles": 0}
    verts, f = weld(tris, tol)
    nondeg = (f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])
    degenerate = int((~nondeg).sum())
    f = f[nondeg]
    nv = len(verts)
    d = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])  # gerichtete Kanten
    dkey = d[:, 0].astype(np.int64) * nv + d[:, 1]
    _, dcnt = np.unique(dkey, return_counts=True)
    flipped_dir = int((dcnt > 1).sum())  # gleiche Richtung mehrfach = inkonsistente Orientierung
    u = np.sort(d, axis=1)
    ukey = u[:, 0].astype(np.int64) * nv + u[:, 1]
    uk, ucnt = np.unique(ukey, return_counts=True)
    open_e = int((ucnt == 1).sum())
    nonman = int((ucnt > 2).sum())
    # Komponenten ueber Dreiecke, die einen Vertex teilen
    used = np.unique(f)
    remap = -np.ones(nv, dtype=np.int64)
    remap[used] = np.arange(len(used))
    r = remap[f]
    rows = np.concatenate([r[:, 0], r[:, 1], r[:, 2]])
    cols = np.concatenate([r[:, 1], r[:, 2], r[:, 0]])
    g = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(used), len(used)))
    ncomp = connected_components(g, directed=False)[0]
    n_edges = len(uk)
    chi = len(used) - n_edges + len(f)
    return {
        "triangles": int(len(tris)),
        "vertices_welded": int(len(used)),
        "weld_tol_mm": tol,
        "degenerate_triangles": degenerate,
        "open_edges": open_e,
        "non_manifold_edges": nonman,
        "inconsistent_orientation_edges": flipped_dir,
        "watertight": bool(open_e == 0 and nonman == 0),
        "closed_and_oriented": bool(open_e == 0 and nonman == 0 and flipped_dir == 0),
        "components": int(ncomp),
        "euler_characteristic": int(chi),
    }


# --------------------------------------------------------------------------- Massen

def mass_properties(tris: np.ndarray) -> dict:
    """Volumen, Schwerpunkt, Traegheitstensor (Dichte 1) aus den Tetraedern (Ursprung, a, b, c).

    Zweites Moment eines Tetraeders mit v0=0: C = V/20 * (a a^T + b b^T + c c^T + s s^T), s=a+b+c.
    Traegheit I = tr(C) E - C. Verschiebung in den Schwerpunkt per Steiner.
    """
    shift = tris.reshape(-1, 3).mean(0)
    t = tris - shift  # Ursprung nahe am Koerper -> bessere numerische Genauigkeit
    a, b, c = t[:, 0], t[:, 1], t[:, 2]
    v = np.einsum("ij,ij->i", a, np.cross(b, c)) / 6.0
    V = v.sum()
    cen_t = (a + b + c) / 4.0
    cen = (v[:, None] * cen_t).sum(0) / V if abs(V) > 1e-12 else np.zeros(3)
    s = a + b + c

    def outer(x, y):
        return x[:, :, None] * y[:, None, :]

    C = ((v / 20.0)[:, None, None] * (outer(a, a) + outer(b, b) + outer(c, c) + outer(s, s))).sum(0)
    Ccm = C - V * np.outer(cen, cen)  # um den Schwerpunkt
    I = np.trace(Ccm) * np.eye(3) - Ccm
    if V < 0:
        I = -I
    w = np.linalg.eigvalsh(I)
    return {
        "volume_mm3": float(abs(V)),
        "signed_volume_mm3": float(V),
        "centroid_mm": [float(x) for x in (cen + shift)],
        "inertia_tensor_mm5": I.tolist(),
        "principal_moments_mm5": [float(x) for x in w],
    }


def triangle_areas(tris: np.ndarray) -> np.ndarray:
    return 0.5 * np.linalg.norm(np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1)


def mesh_metrics(tris: np.ndarray, file_path=None, weld_tol: float = 1e-3) -> dict:
    """Alle Standardmetriken eines Meshes."""
    tris = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    out: dict = {"triangles": int(len(tris))}
    if file_path is not None and os.path.exists(file_path):
        out["file_size_bytes"] = int(os.path.getsize(file_path))
    if len(tris) == 0:
        out["error"] = "leeres Mesh"
        return out
    P = tris.reshape(-1, 3)
    mn, mx = P.min(0), P.max(0)
    out["bbox_mm"] = [float(x) for x in (*mn, *mx)]
    out["bbox_size_mm"] = [float(x) for x in (mx - mn)]
    out["area_mm2"] = float(triangle_areas(tris).sum())
    out["topology"] = topology(tris, weld_tol)
    out.update(mass_properties(tris))
    out["volume_reliable"] = bool(out["topology"]["watertight"])
    return out


# --------------------------------------------------------------------------- Abtastung / Abweichung

def sample_surface(tris: np.ndarray, n: int, rng=None, return_tri=False):
    """Flaechengewichtete Gleichverteilung von n Punkten auf der Oberflaeche."""
    rng = np.random.default_rng(0) if rng is None else rng
    area = triangle_areas(tris)
    tot = area.sum()
    if tot <= 0 or len(tris) == 0:
        return (np.zeros((0, 3)), np.zeros(0, dtype=int)) if return_tri else np.zeros((0, 3))
    idx = rng.choice(len(tris), size=n, p=area / tot)
    r1 = np.sqrt(rng.random(n))
    r2 = rng.random(n)
    t = tris[idx]
    pts = (1 - r1)[:, None] * t[:, 0] + (r1 * (1 - r2))[:, None] * t[:, 1] + (r1 * r2)[:, None] * t[:, 2]
    return (pts, idx) if return_tri else pts


def closest_dist_point_triangle(p: np.ndarray, tri: np.ndarray) -> np.ndarray:
    """Vektorisierter Abstand Punkt (M,3) zu Dreieck (M,3,3) nach Ericson (Real-Time Collision Detection)."""
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    ab, ac, ap = b - a, c - a, p - a
    d1 = np.einsum("ij,ij->i", ab, ap)
    d2 = np.einsum("ij,ij->i", ac, ap)
    bp = p - b
    d3 = np.einsum("ij,ij->i", ab, bp)
    d4 = np.einsum("ij,ij->i", ac, bp)
    cp = p - c
    d5 = np.einsum("ij,ij->i", ab, cp)
    d6 = np.einsum("ij,ij->i", ac, cp)
    vc = d1 * d4 - d3 * d2
    vb = d5 * d2 - d1 * d6
    va = d3 * d6 - d5 * d4
    eps = 1e-30
    denom = va + vb + vc
    denom = np.where(np.abs(denom) < eps, eps, denom)
    v = vb / denom
    w = vc / denom
    q = a + ab * v[:, None] + ac * w[:, None]  # Innenfall
    done = np.zeros(len(p), dtype=bool)

    m = (d1 <= 0) & (d2 <= 0)  # Ecke a
    q[m] = a[m]
    done |= m
    m = (d3 >= 0) & (d4 <= d3) & ~done  # Ecke b
    q[m] = b[m]
    done |= m
    m = (vc <= 0) & (d1 >= 0) & (d3 <= 0) & ~done  # Kante ab
    t = d1 / np.where(np.abs(d1 - d3) < eps, eps, d1 - d3)
    q[m] = (a + ab * t[:, None])[m]
    done |= m
    m = (d6 >= 0) & (d5 <= d6) & ~done  # Ecke c
    q[m] = c[m]
    done |= m
    m = (vb <= 0) & (d2 >= 0) & (d6 <= 0) & ~done  # Kante ac
    t = d2 / np.where(np.abs(d2 - d6) < eps, eps, d2 - d6)
    q[m] = (a + ac * t[:, None])[m]
    done |= m
    m = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0) & ~done  # Kante bc
    dd = (d4 - d3) + (d5 - d6)
    t = (d4 - d3) / np.where(np.abs(dd) < eps, eps, dd)
    q[m] = (b + (c - b) * t[:, None])[m]
    return np.linalg.norm(p - q, axis=1)


class SurfaceIndex:
    """Beschleunigungsstruktur fuer Abstandsanfragen an ein Dreiecksnetz."""

    def __init__(self, tris: np.ndarray, n_samples: int = 600_000, seed: int = 1):
        self.tris = tris
        pts, tid = sample_surface(tris, n_samples, np.random.default_rng(seed), return_tri=True)
        vt = tris.reshape(-1, 3)  # alle Eckpunkte zusaetzlich, damit spitze Kanten sicher gefunden werden
        self.pts = np.vstack([pts, vt])
        self.tid = np.concatenate([tid, np.repeat(np.arange(len(tris)), 3)])
        self.tree = cKDTree(self.pts)

    def distances(self, q: np.ndarray, k: int = 6, chunk: int = 100_000) -> np.ndarray:
        out = np.empty(len(q))
        for s in range(0, len(q), chunk):
            qq = q[s:s + chunk]
            _, ii = self.tree.query(qq, k=k, workers=-1)
            tids = self.tid[ii]  # (m,k)
            best = np.full(len(qq), np.inf)
            for j in range(k):
                best = np.minimum(best, closest_dist_point_triangle(qq, self.tris[tids[:, j]]))
            out[s:s + chunk] = best
        return out


def _stats(d: np.ndarray) -> dict:
    if len(d) == 0:
        return {"mean": None, "rms": None, "p50": None, "p95": None, "p99": None, "max": None}
    return {
        "mean": float(d.mean()), "rms": float(np.sqrt((d ** 2).mean())),
        "p50": float(np.percentile(d, 50)), "p95": float(np.percentile(d, 95)),
        "p99": float(np.percentile(d, 99)), "max": float(d.max()),
    }


def deviation(a: np.ndarray, b: np.ndarray, n_query: int = 200_000, n_index: int = 600_000,
              seed: int = 0, index_b: SurfaceIndex | None = None, index_a: SurfaceIndex | None = None) -> dict:
    """Abweichung zwischen zwei Meshes in mm (Einheit der Eingabe).

    a_to_b: Abstand von Punkten auf a zur Oberflaeche von b, b_to_a umgekehrt.
    hausdorff = max beider Maxima (Naeherung, abhaengig von der Stichprobe);
    symmetric_mean = Mittel beider Richtungen.
    Methode: flaechengewichtete Zufallspunkte, kNN in dichter Punktwolke, danach exakter
    Punkt-zu-Dreieck-Abstand der k Kandidaten (Fehler << Abtastabstand).
    """
    rng = np.random.default_rng(seed)
    t0 = time.time()
    ib = index_b or SurfaceIndex(b, n_index)
    ia = index_a or SurfaceIndex(a, n_index)
    qa = sample_surface(a, n_query, rng)
    qb = sample_surface(b, n_query, rng)
    dab = ib.distances(qa)
    dba = ia.distances(qb)
    both = np.concatenate([dab, dba])
    return {
        "a_to_b_mm": _stats(dab), "b_to_a_mm": _stats(dba),
        "symmetric_mean_mm": float(both.mean()), "symmetric_p95_mm": float(np.percentile(both, 95)),
        "hausdorff_mm": float(both.max()),
        "n_query_per_direction": int(n_query), "n_index_points": int(n_index), "seconds": round(time.time() - t0, 2),
    }


def meshes_differ(a: np.ndarray, b: np.ndarray, tol_mm: float = 0.02) -> dict:
    """Ist die Geometrie geaendert? Schnellpruefung + Abweichungsmessung.

    changed = Hausdorff-Naeherung > tol_mm ODER Volumenabweichung > 1e-4 relativ.
    """
    if a is None or b is None or len(a) == 0 or len(b) == 0:
        return {"changed": None, "reason": "Mesh fehlt"}
    if a.shape == b.shape and np.allclose(a, b, atol=1e-5):
        return {"changed": False, "identical": True, "hausdorff_mm": 0.0, "volume_rel_change": 0.0}
    dev = deviation(a, b, n_query=60_000, n_index=200_000)
    va, vb = mass_properties(a)["volume_mm3"], mass_properties(b)["volume_mm3"]
    rel = abs(va - vb) / max(va, 1e-9)
    return {"changed": bool(dev["hausdorff_mm"] > tol_mm or rel > 1e-4), "identical": False,
            "hausdorff_mm": dev["hausdorff_mm"], "mean_mm": dev["symmetric_mean_mm"], "volume_rel_change": rel}


# --------------------------------------------------------------------------- ICP

def _kabsch(P, Q):
    cp, cq = P.mean(0), Q.mean(0)
    H = (P - cp).T @ (Q - cq)
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1, 1, d]) @ U.T
    t = cq - R @ cp
    return R, t


def icp(src: np.ndarray, dst: np.ndarray, iters: int = 40, n_src: int = 30_000, trim: float = 0.9,
        index_dst: SurfaceIndex | None = None) -> dict:
    """Getrimmte Punkt-zu-Ebene-ICP: bewegt src (Dreiecke) starr auf dst. Rueckgabe R, t, Restfehler.

    Punkt-zu-Ebene (Normale des naechsten Zieldreiecks, linearisierte Kleinwinkel-Loesung) konvergiert
    genauer als Punkt-zu-Punkt. Der Restfehler ist der RMS der besten `trim`-Anteile der Punktabstaende
    (robust gegen echte Formabweichungen). trim=1.0 bei identischen Formen.
    """
    idx = index_dst or SurfaceIndex(dst, 300_000)
    nrm = np.cross(dst[:, 1] - dst[:, 0], dst[:, 2] - dst[:, 0])
    nl = np.linalg.norm(nrm, axis=1, keepdims=True)
    nrm = np.divide(nrm, nl, out=np.zeros_like(nrm), where=nl > 0)
    P0 = sample_surface(src, n_src, np.random.default_rng(3))
    R, t = np.eye(3), np.zeros(3)
    hist = []
    for _ in range(iters):
        P = P0 @ R.T + t
        d, ii = idx.tree.query(P, workers=-1)
        keep = d <= np.quantile(d, trim)
        Pk, Qk, Nk = P[keep], idx.pts[ii[keep]], nrm[idx.tid[ii[keep]]]
        r = np.einsum("ij,ij->i", Pk - Qk, Nk)
        hist.append(float(np.sqrt((r ** 2).mean())))
        A = np.hstack([np.cross(Pk, Nk), Nk])
        x = np.linalg.lstsq(A, -r, rcond=None)[0]
        w, dt = x[:3], x[3:]
        th = np.linalg.norm(w)
        if th < 1e-12:
            dR = np.eye(3)
        else:  # Rodrigues
            k = w / th
            K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
            dR = np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * K @ K
        R, t = dR @ R, dR @ t + dt
        if len(hist) > 2 and abs(hist[-2] - hist[-1]) < 1e-5 and th < 1e-6:
            break
    ang = np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1)))
    return {"R": R.tolist(), "t_mm": [float(x) for x in t], "rotation_deg": float(ang),
            "translation_norm_mm": float(np.linalg.norm(t)), "trimmed_rms_first_mm": hist[0],
            "trimmed_rms_last_mm": hist[-1], "iterations": len(hist)}


def apply_transform(tris: np.ndarray, R, t) -> np.ndarray:
    return tris @ np.asarray(R).T + np.asarray(t)


# --------------------------------------------------------------------------- Stirnflaeche

def projected_area(tris: np.ndarray, axis: str = "z", pixel_mm: float | None = None, max_px: int = 3000) -> dict:
    """Projizierte Flaeche (Stirnflaeche) durch Rasterung.

    axis='z' projiziert auf die XY-Ebene (Draufsicht), axis='x' auf die YZ-Ebene (Anstroemung
    in X-Richtung), axis='y' auf XZ. Rasterung mit PIL-Polygonen; die Aufloesung (pixel_mm)
    wird mit ausgegeben. Randbias ~ Umfang * Pixel / 2 (wird im Test gegen Kugel/Quader geprueft).
    """
    from PIL import Image, ImageDraw
    ax = {"x": 0, "y": 1, "z": 2}[axis]
    keep = [i for i in range(3) if i != ax]
    P = tris[:, :, keep]
    mn, mx = P.reshape(-1, 2).min(0), P.reshape(-1, 2).max(0)
    ext = mx - mn
    px = pixel_mm or float(max(ext.max() / max_px, 1e-6))
    W, H = int(np.ceil(ext[0] / px)) + 3, int(np.ceil(ext[1] / px)) + 3
    Q = (P - mn) / px + 1.0
    img = Image.new("1", (W, H), 0)
    dr = ImageDraw.Draw(img)
    span = Q.max(1) - Q.min(1)
    small = span.max(1) < 1.0
    for i in np.where(~small)[0]:
        dr.polygon([tuple(v) for v in Q[i]], fill=1)
    arr = np.array(img, dtype=bool)
    sm = Q[small].mean(1)
    if len(sm):
        xi = np.clip(sm[:, 0].astype(int), 0, W - 1)
        yi = np.clip(sm[:, 1].astype(int), 0, H - 1)
        arr[yi, xi] = True
    area = float(arr.sum()) * px * px
    return {"axis": axis, "area_mm2": area, "pixel_mm": px, "raster_px": [W, H], "covered_px": int(arr.sum())}


# --------------------------------------------------------------------------- Komfort

def analyze_file(path, **kw) -> dict:
    t0 = time.time()
    tris = read_stl(path)
    m = mesh_metrics(tris, path, **kw)
    m["metrics_seconds"] = round(time.time() - t0, 2)
    return m
