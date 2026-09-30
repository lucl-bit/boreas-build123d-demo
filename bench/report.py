"""Aggregiert einen Benchmark-Lauf zu summary.json, summary.md (Deutsch) und Diagrammen (PNG).

Aufruf:  python -m bench.report [run_dir]        (Standard: bench/results/latest)
Diagramme: charts/runtime.png, ram.png, filesize.png, voxel_sweep.png, b03_regen.png
Farben durchgaengig: B-rep = Blau, Voxel = Orange (farbenblind-sicher).
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "bench" / "results"
COLORS = {"brep": "#1f6fb2", "voxel": "#e08a1e"}
LABELS = {"brep": "B-rep (build123d)", "voxel": "Voxel (PicoGK)"}
TOOLS = ("brep", "voxel")
SECTIONS = [("common", "Gemeinsame Aufgaben (B01-B10)", "B"), ("brep_only", "Nur bzw. klar besser in B-rep (R01-R04)", "R"),
            ("voxel_only", "Nur bzw. klar besser in Voxel (V01-V04)", "V")]
STATUS_RANK = {"ok": 0, "partial": 1, "failed": 3, "unsupported": 4, "not_run": 5, None: 6}


# --------------------------------------------------------------------------- Laden / Verdichten

def _load(run_dir: Path) -> dict:
    out: dict = {}
    for tdir in sorted(run_dir.iterdir()):
        if not tdir.is_dir() or not tdir.name[:1] in "BVR" or len(tdir.name) != 3:
            continue
        for tool in TOOLS:
            rj = tdir / tool / "result.json"
            if rj.exists():
                try:
                    out.setdefault(tdir.name, {})[tool] = json.loads(rj.read_text(encoding="utf-8"))
                except Exception as e:
                    out.setdefault(tdir.name, {})[tool] = {"status": "failed", "notes": f"result.json unlesbar: {e}"}
    return out


def _g(d, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d if d is not None else default


def condense(res: dict) -> dict:
    nm = res.get("neutral_metrics") or {}
    mesh = nm.get("mesh") or {}
    rd = nm.get("reference_deviation") or {}
    dev_mean = [v["offset_only"]["symmetric_mean_mm"] for v in rd.values() if _g(v, "offset_only", "symmetric_mean_mm") is not None]
    dev_p95 = [v["offset_only"]["symmetric_p95_mm"] for v in rd.values() if _g(v, "offset_only", "symmetric_p95_mm") is not None]
    icp_mean = [v["after_icp"]["symmetric_mean_mm"] for v in rd.values() if _g(v, "after_icp", "symmetric_mean_mm") is not None]
    runner = res.get("runner") or {}
    rep = runner.get("repeats") or {}
    return {
        "status": res.get("status"), "notes": (res.get("notes") or "").strip(),
        "tool_version": res.get("tool_version"),
        "wall_s": rep.get("wall_median_s", runner.get("wall_s")), "runtime_s_reported": res.get("runtime_s"),
        "peak_ram_mb": runner.get("peak_ram_mb"), "peak_mem_mb_reported": res.get("peak_mem_mb"),
        "exit_code": runner.get("exit_code"), "runner_status": runner.get("status"),
        "code_loc": res.get("code_loc"),
        "triangles": mesh.get("triangles"), "file_size_bytes": mesh.get("file_size_bytes"),
        "volume_mm3": mesh.get("volume_mm3"), "area_mm2": mesh.get("area_mm2"),
        # Teile, die sich beruehren, teilen im Gesamtnetz Kanten -> Dichtheit je Teil beurteilen, wenn Teile vorliegen
        "watertight": (all(_g(v, "topology", "watertight") for v in nm["parts"].values()) if nm.get("parts")
                       else _g(mesh, "topology", "watertight")),
        "open_edges": _g(mesh, "topology", "open_edges"),
        "non_manifold_edges": _g(mesh, "topology", "non_manifold_edges"),
        "bbox_mm": mesh.get("bbox_mm"),
        "frontal_area_z_mm2": _g(mesh, "frontal_area_z", "area_mm2"), "frontal_area_x_mm2": _g(mesh, "frontal_area_x", "area_mm2"),
        "frontal_pixel_mm": _g(mesh, "frontal_area_z", "pixel_mm"),
        "parts": sorted((nm.get("parts") or {}).keys()),
        "ref_dev_mean_mm": (sum(dev_mean) / len(dev_mean)) if dev_mean else None,
        "ref_dev_p95_mm": max(dev_p95) if dev_p95 else None,
        "ref_dev_after_icp_mean_mm": (sum(icp_mean) / len(icp_mean)) if icp_mean else None,
        "ref_dev_parts": {p: {"mean_mm": _g(v, "offset_only", "symmetric_mean_mm"), "p95_mm": _g(v, "offset_only", "symmetric_p95_mm"),
                              "max_mm": _g(v, "offset_only", "hausdorff_mm"), "icp_mean_mm": _g(v, "after_icp", "symmetric_mean_mm"),
                              "icp_rot_deg": _g(v, "icp", "rotation_deg"), "icp_trans_mm": _g(v, "icp", "total_translation_norm_mm")}
                          for p, v in rd.items()},
        "self_report_vol_rel_diff": _g(nm, "self_report_check", "volume_mm3", "rel_diff"),
        "self_report_area_rel_diff": _g(nm, "self_report_check", "area_mm2", "rel_diff"),
        "frame_warning": nm.get("frame_warning"),
    }


# --------------------------------------------------------------------------- Formatierung

def f(v, nd=2, unit="", na="-"):
    if v is None:
        return na
    if isinstance(v, bool):
        return "ja" if v else "nein"
    if isinstance(v, (int,)) and not isinstance(v, bool):
        return f"{v:,}".replace(",", "'") + (f" {unit}" if unit else "")
    try:
        return f"{v:.{nd}f}" + (f" {unit}" if unit else "")
    except Exception:
        return str(v)


def mb(b):
    return None if b is None else b / 1e6


def short(s, n=140):
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[: n - 1] + "..."


# --------------------------------------------------------------------------- Gewinner

def decide(task: str, cs: dict, section: str) -> dict:
    """Bestimmt einen Gewinner mit Begruendung aus den Zahlen. cs = {tool: condensed}."""
    ok = {t: c for t, c in cs.items() if c["status"] in ("ok", "partial")}
    reasons: list[str] = []
    if not cs:
        return {"winner": None, "reason": "Keine Ergebnisse."}
    nr = [t for t, c in cs.items() if c["status"] == "not_run"]
    for t in nr:
        reasons.append(f"{LABELS[t]}: nicht gelaufen ({short(cs[t]['notes'], 90)})")
    if len(ok) == 0:
        uns = [t for t, c in cs.items() if c["status"] == "unsupported"]
        if uns and len(uns) == len(cs):
            return {"winner": None, "reason": "Beide Werkzeuge: unsupported. " + " ".join(short(cs[t]["notes"], 100) for t in uns)}
        return {"winner": None, "reason": "; ".join(reasons) or "Kein Werkzeug hat ein verwertbares Ergebnis geliefert."}
    if len(ok) == 1:
        w = next(iter(ok))
        o = [t for t in cs if t != w]
        why = f"Nur {LABELS[w]} liefert ein Ergebnis (Status {ok[w]['status']})."
        for t in o:
            if cs[t]["status"] in ("unsupported", "failed"):
                why += f" {LABELS[t]}: {cs[t]['status']} - {short(cs[t]['notes'], 110)}"
        return {"winner": w, "reason": " ".join([why] + [r for r in reasons if "nicht gelaufen" in r]), "basis": "einziges Ergebnis"}
    a, b = "brep", "voxel"
    ca, cb = ok[a], ok[b]
    pts = {a: 0, b: 0}
    lines = []

    def cmp(label, va, vb, lower=True, unit="", nd=2, rel_tol=0.05, weight=1):
        if va is None or vb is None:
            return
        better = None
        if abs(va - vb) > rel_tol * max(abs(va), abs(vb), 1e-12):
            better = a if (va < vb) == lower else b
            pts[better] += weight
        ratio = (max(va, vb) / min(va, vb)) if min(va, vb) > 0 else None
        lines.append(f"{label}: B-rep {f(va, nd)} {unit} vs. Voxel {f(vb, nd)} {unit}" +
                     (f" (Faktor {ratio:.1f}, {'B-rep' if better == a else 'Voxel'} besser)" if better and ratio else " (gleichauf)"))

    # primaere Kriterien je Aufgabe
    if task in ("B01", "B02", "B07") and ca["ref_dev_mean_mm"] is not None and cb["ref_dev_mean_mm"] is not None:
        cmp("mittlere Abweichung zur Referenz (nur Offset)", ca["ref_dev_mean_mm"], cb["ref_dev_mean_mm"], True, "mm", 3, 0.10, weight=3)
    if task == "B02" or task == "B01":
        pa, pb = len(ca["parts"]), len(cb["parts"])
        if pa != pb:
            better = a if pa > pb else b
            pts[better] += 3
            lines.append(f"Teile im Ergebnis: B-rep {pa} vs. Voxel {pb} ({'B-rep' if better == a else 'Voxel'} vollstaendiger)")
    if task in ("B02", "B08", "B10", "B05", "B06", "B04", "B09") and ca["watertight"] is not None and cb["watertight"] is not None \
            and ca["watertight"] != cb["watertight"]:
        better = a if ca["watertight"] else b
        pts[better] += 2
        lines.append(f"Wasserdichtes Mesh: B-rep {f(ca['watertight'])} vs. Voxel {f(cb['watertight'])}")
    if task == "B09" and ca["frontal_area_z_mm2"] and cb["frontal_area_z_mm2"]:
        lines.append(f"Stirnflaeche Z: B-rep {f(ca['frontal_area_z_mm2'], 0)} mm2 vs. Voxel {f(cb['frontal_area_z_mm2'], 0)} mm2 (Rasterung, Info)")
    cmp("Wandzeit", ca["wall_s"], cb["wall_s"], True, "s", 2, 0.10, weight=2)
    cmp("Spitzen-RAM", ca["peak_ram_mb"], cb["peak_ram_mb"], True, "MB", 0, 0.10, weight=1)
    cmp("Dateigroesse Mesh", mb(ca["file_size_bytes"]), mb(cb["file_size_bytes"]), True, "MB", 2, 0.10, weight=1)
    winner = a if pts[a] > pts[b] else (b if pts[b] > pts[a] else None)
    return {"winner": winner, "score": pts, "reason": "; ".join(lines) or "Keine vergleichbaren Kennzahlen.",
            "basis": "Punkte: Genauigkeit/Vollstaendigkeit 3, Wandzeit 2, RAM/Dateigroesse/Wasserdichtheit 1-2"}


def decide_b03(cs: dict, raw: dict) -> dict:
    ok = {t: raw[t] for t in raw if raw[t].get("variations")}
    if len(ok) < 2:
        return decide("B03", cs, "common")
    info = {}
    for t, r in ok.items():
        v = [x for x in r["variations"] if x.get("independent") is not None]
        info[t] = {"indep": sum(1 for x in v if x["independent"]), "n": len(v),
                   "mean": _g(r, "metrics", "mean_regen_wall_s")}
    a, b = info["brep"], info["voxel"]
    reason = (f"Unabhaengigkeit: B-rep {a['indep']}/{a['n']}, Voxel {b['indep']}/{b['n']}; mittlere Regenerationszeit "
              f"B-rep {f(a['mean'])} s, Voxel {f(b['mean'])} s")
    if a["indep"] != b["indep"]:
        w = "brep" if a["indep"] > b["indep"] else "voxel"
    elif a["mean"] and b["mean"] and abs(a["mean"] - b["mean"]) > 0.1 * max(a["mean"], b["mean"]):
        w = "brep" if a["mean"] < b["mean"] else "voxel"
    else:
        w = None
    return {"winner": w, "reason": reason, "basis": "erst Unabhaengigkeit der Gruppen, dann Regenerationszeit"}


# --------------------------------------------------------------------------- Diagramme

def _mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.alpha": 0.25, "axes.axisbelow": True, "figure.dpi": 100})
    return plt


def bar_chart(plt, tasks, values, title, xlabel, path, fmt="{:.1f}", log_if_ratio=30):
    """Horizontale Gruppenbalken je Aufgabe; values[tool][task]."""
    import numpy as np
    tasks = [t for t in tasks if any(values[tl].get(t) is not None for tl in TOOLS)]
    if not tasks:
        return None
    fig, ax = plt.subplots(figsize=(8.5, 0.55 * len(tasks) + 1.8))
    y = np.arange(len(tasks))
    h = 0.38
    allv = [v for tl in TOOLS for v in values[tl].values() if v]
    use_log = bool(allv) and max(allv) / max(min(allv), 1e-9) > log_if_ratio
    for i, tl in enumerate(TOOLS):
        vals = [values[tl].get(t) for t in tasks]
        xs = [v if v is not None else 0 for v in vals]
        ax.barh(y + (i - 0.5) * h, xs, height=h, color=COLORS[tl], label=LABELS[tl])
        for yy, v in zip(y + (i - 0.5) * h, vals):
            if v is not None:
                ax.text(v, yy, " " + fmt.format(v), va="center", fontsize=8)
    ax.set_yticks(y)
    ax.set_yticklabels(tasks)
    ax.invert_yaxis()
    if use_log:
        ax.set_xscale("log")
        xlabel += " (logarithmisch)"
    ax.set_xlabel(xlabel)
    ax.set_title(title, loc="left", fontsize=11, pad=22)
    ax.grid(axis="y", visible=False)
    ax.legend(frameon=False, loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=2, borderaxespad=0.2)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _plain_axes(ax, xs, ys=None, ylog=None):
    """Logarithmische x-Achse mit den Voxelgroessen als Ticks; y log nur bei grosser Spanne."""
    from matplotlib.ticker import FuncFormatter, NullFormatter
    ax.set_xscale("log")
    ax.set_xticks(xs)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.xaxis.set_minor_formatter(NullFormatter())
    vals = [v for v in (ys or []) if v]
    if ylog is None:
        ylog = bool(vals) and max(vals) / min(vals) > 8
    if ylog:
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
        ax.yaxis.set_minor_formatter(NullFormatter())
    elif vals:
        ax.set_ylim(0, max(vals) * 1.15)


def make_charts(run_dir: Path, cond: dict, raw: dict) -> list[str]:
    charts = []
    try:
        plt = _mpl()
    except Exception as e:
        return [f"(matplotlib nicht verfuegbar: {e})"]
    cdir = run_dir / "charts"
    cdir.mkdir(exist_ok=True)
    tasks = sorted(cond)
    fake = "  [FAKE-Lauf]" if _is_fake(run_dir) else ""
    for key, title, xl, fmt, fname in (
            ("wall_s", "Laufzeit je Aufgabe (Wandzeit inkl. Prozessstart)" + fake, "Sekunden", "{:.1f}", "runtime.png"),
            ("peak_ram_mb", "Spitzen-RAM je Aufgabe (Prozessbaum)" + fake, "MB", "{:.0f}", "ram.png")):
        vals = {tl: {t: cond[t][tl][key] for t in tasks if tl in cond[t] and cond[t][tl]["status"] in ("ok", "partial")} for tl in TOOLS}
        p = bar_chart(plt, tasks, vals, title, xl, cdir / fname, fmt)
        if p:
            charts.append(f"charts/{fname}")
    vals = {tl: {t: mb(cond[t][tl]["file_size_bytes"]) for t in tasks if tl in cond[t] and cond[t][tl]["file_size_bytes"]} for tl in TOOLS}
    p = bar_chart(plt, tasks, vals, "Dateigroesse des Gesamt-Meshes (STL)" + fake, "MB", cdir / "filesize.png", "{:.2f}")
    if p:
        charts.append("charts/filesize.png")

    # B07: Genauigkeit / Zeit / RAM gegen Voxelgroesse
    sweep = (raw.get("B07", {}).get("voxel") or {}).get("sweep") or []
    sweep = [s for s in sweep if s.get("status") in ("ok", "partial")]
    if sweep:
        sweep.sort(key=lambda s: s["voxel_mm"])
        x = [s["voxel_mm"] for s in sweep]
        fig, axs = plt.subplots(2, 2, figsize=(10, 7))
        ax = axs[0, 0]
        for key, lab, ls in (("mean_mm", "Mittel", "-"), ("p95_mm", "95. Perzentil", "--")):
            ys = [(s.get("vs_brep") or {}).get(key) for s in sweep]
            if any(v is not None for v in ys):
                ax.plot(x, ys, ls, marker="o", color=COLORS["voxel"], label=f"Voxel vs. B-rep: {lab}")
        for key, lab, ls in (("mean_mm", "Mittel", "-"), ("p95_mm", "95. Perzentil", "--")):
            ys = [(s.get("reference_deviation") or {}).get("upper", {}).get(key) for s in sweep]
            if any(v is not None for v in ys):
                ax.plot(x, ys, ls, marker="s", color=COLORS["voxel"], alpha=0.55, mfc="white", label=f"Voxel vs. STEP-Referenz (Oberteil): {lab}")
        _plain_axes(ax, x, [v for l in ax.get_lines() for v in l.get_ydata()], ylog=True)
        ax.set_xlabel("Voxelgroesse (mm)"); ax.set_ylabel("Abweichung (mm)")
        ax.set_title("Geometrie-Abweichung", loc="left", fontsize=10)
        ax.legend(frameon=False, fontsize=7)
        ax = axs[0, 1]
        ys = [abs((s.get("vs_brep") or {}).get("volume_rel_err")) * 100 if (s.get("vs_brep") or {}).get("volume_rel_err") is not None else None for s in sweep]
        ya = [abs((s.get("vs_brep") or {}).get("area_rel_err")) * 100 if (s.get("vs_brep") or {}).get("area_rel_err") is not None else None for s in sweep]
        if any(v is not None for v in ys):
            ax.plot(x, ys, "-o", color=COLORS["voxel"], label="Volumen")
            ax.plot(x, ya, "--o", color=COLORS["voxel"], alpha=0.6, label="Oberflaeche")
            _plain_axes(ax, x, ys + ya, ylog=False)
            ax.legend(frameon=False)
        ax.set_xlabel("Voxelgroesse (mm)"); ax.set_ylabel("Betrag rel. Fehler (%)")
        ax.set_title("Masse/Flaeche vs. B-rep", loc="left", fontsize=10)
        ax = axs[1, 0]
        ax.plot(x, [s.get("wall_s") for s in sweep], "-o", color=COLORS["voxel"])
        bw = (cond.get("B07", {}).get("brep") or {}).get("wall_s")
        if bw:
            ax.axhline(bw, color=COLORS["brep"], lw=1.5, label="B-rep (einmalig)")
            ax.legend(frameon=False)
        _plain_axes(ax, x, [s.get("wall_s") for s in sweep] + [bw])
        ax.set_xlabel("Voxelgroesse (mm)"); ax.set_ylabel("Wandzeit (s)")
        ax.set_title("Laufzeit", loc="left", fontsize=10)
        ax = axs[1, 1]
        ax.plot(x, [s.get("peak_ram_mb") for s in sweep], "-o", color=COLORS["voxel"])
        br = (cond.get("B07", {}).get("brep") or {}).get("peak_ram_mb")
        if br:
            ax.axhline(br, color=COLORS["brep"], lw=1.5, label="B-rep (einmalig)")
            ax.legend(frameon=False)
        _plain_axes(ax, x, [s.get("peak_ram_mb") for s in sweep] + [br])
        ax.set_xlabel("Voxelgroesse (mm)"); ax.set_ylabel("Spitzen-RAM (MB)")
        ax.set_title("Speicher", loc="left", fontsize=10)
        fig.suptitle("B07: Voxel-Genauigkeit gegen Aufloesung" + fake, x=0.01, ha="left", fontsize=12)
        fig.tight_layout()
        fig.savefig(cdir / "voxel_sweep.png", dpi=150)
        plt.close(fig)
        charts.append("charts/voxel_sweep.png")

    # B10: Laufzeit ueber Armzahl
    arms = {}
    for tl in TOOLS:
        pts = [(int(sc["label"][4:]), sc["wall_s"], sc.get("peak_ram_mb")) for sc in ((raw.get("B10", {}).get(tl) or {}).get("scaling") or [])
               if sc["label"].startswith("arms") and sc.get("status") in ("ok", "partial") and sc.get("wall_s")]
        if pts:
            arms[tl] = sorted(pts)
    if arms:
        fig, axs = plt.subplots(1, 2, figsize=(10, 3.8))
        for tl, pts in arms.items():
            axs[0].plot([p[0] for p in pts], [p[1] for p in pts], "-o", color=COLORS[tl], label=LABELS[tl])
            axs[1].plot([p[0] for p in pts], [p[2] for p in pts], "-o", color=COLORS[tl], label=LABELS[tl])
        for ax, yl in zip(axs, ("Wandzeit (s)", "Spitzen-RAM (MB)")):
            ax.set_xlabel("Anzahl Arme"); ax.set_ylabel(yl); ax.set_ylim(bottom=0)
            ax.set_xticks(sorted({p[0] for pts in arms.values() for p in pts}))
        axs[0].legend(frameon=False)
        fig.suptitle("B10: Skalierung mit der Armzahl" + fake, x=0.01, ha="left", fontsize=11)
        fig.tight_layout()
        fig.savefig(cdir / "b10_scaling.png", dpi=150)
        plt.close(fig)
        charts.append("charts/b10_scaling.png")

    # B03: Regenerationszeit je Gruppe
    b03 = {tl: (raw.get("B03", {}).get(tl) or {}).get("variations") for tl in TOOLS}
    if any(b03.values()):
        import numpy as np
        groups = []
        for tl in TOOLS:
            for v in b03[tl] or []:
                if v["group"] not in groups:
                    groups.append(v["group"])
        vals = {tl: {v["group"]: v.get("wall_s") for v in (b03[tl] or []) if v.get("status") in ("ok", "partial")} for tl in TOOLS}
        p = bar_chart(plt, groups, vals, "B03: Regenerationszeit nach Aenderung einer Gruppe" + fake, "Sekunden", cdir / "b03_regen.png", "{:.1f}")
        if p:
            charts.append("charts/b03_regen.png")
    return charts


def _is_fake(run_dir: Path) -> bool:
    try:
        return bool(json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8")).get("fake"))
    except Exception:
        return False


# --------------------------------------------------------------------------- Markdown

def table(head: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x).replace("|", "/") for x in r) + " |")
    return "\n".join(out) + "\n"


def write_markdown(run_dir: Path, meta: dict, cond: dict, raw: dict, winners: dict, charts: list[str], fm: dict | None) -> str:
    title = meta.get("task_titles", {})
    L: list[str] = []
    L.append(f"# Benchmark-Zusammenfassung {meta.get('run_id', run_dir.name)}\n")
    if meta.get("fake"):
        L.append("> **ACHTUNG: FAKE-Lauf.** Die Werkzeuge wurden per `--tool-cmd` durch die Attrappe `bench/_fake_tool.py` ersetzt "
                 "(altes Oberteil, Voxel-Simulation durch Gitter-Rundung). Diese Zahlen sind KEINE Benchmark-Ergebnisse, "
                 "sondern nur der Pipeline-Test.\n")
    L.append(f"Stand: {meta.get('started', '?')} - Dauer {meta.get('total_s', '?')} s - Rechner: {_g(meta, 'host', 'platform')}, "
             f"Python {_g(meta, 'host', 'python')}, build123d {_g(meta, 'host', 'build123d')}, {_g(meta, 'host', 'cpu_count')} CPU-Threads\n")
    L.append("## Werkzeug-Verfuegbarkeit\n")
    L.append(table(["Werkzeug", "verfuegbar", "Grund / Kommando"],
                   [[LABELS.get(t, t), f(v.get("available")), short(v.get("reason") or " ".join(map(str, v.get("cmd", []))), 110)]
                    for t, v in (meta.get("availability") or {}).items()]))
    ref = meta.get("reference") or {}
    if ref:
        al = ref["alignment"]
        L.append("## Referenz und Ausrichtung\n")
        L.append(f"Referenz = `Mohammed_0.1 Full Shell.step`, tessellierte Schalen (Abdeckung: " +
                 ", ".join(f"{k} {v * 100:.4f} %" for k, v in ref["coverage"].items() if v is not None) + ").  \n"
                 f"Modell-Koordinatensystem = Datei-KS + Offset ({al['offset_to_model'][0]:.3f}, {al['offset_to_model'][1]:.3f}, "
                 f"{al['offset_to_model'][2]:.3f}) mm; Streuung der Achsen-Fits {al['axis_scatter_mm'][0]:.2f}/{al['axis_scatter_mm'][1]:.2f} mm.  \n"
                 "Abweichungen sind flaechengewichtete Punkt-zu-Dreieck-Abstaende in beiden Richtungen; 'nur Offset' = keine Nachausrichtung, "
                 "'ICP' = zusaetzliche starre Verfeinerung (Restdrehung/-verschiebung in der Tabelle).\n")
    if charts:
        L.append("## Diagramme\n")
        for c in charts:
            L.append(f"![{Path(c).stem}]({c})\n")

    # Gesamtuebersicht
    L.append("## Gewinner je Aufgabe\n")
    rows = []
    for t in sorted(cond):
        w = winners.get(t, {})
        rows.append([t, title.get(t, ""), LABELS.get(w.get("winner"), "kein Gewinner"), short(w.get("reason", ""), 260)])
    L.append(table(["Aufgabe", "Titel", "Gewinner", "Begruendung (Zahlen)"], rows))
    L.append("Bewertungsregel: Genauigkeit/Vollstaendigkeit (3 Punkte) > Wandzeit (2) > RAM, Dateigroesse, Wasserdichtheit (1-2); "
             "Unterschiede unter 5-10 % zaehlen als gleichauf. Ist nur ein Werkzeug faehig, gewinnt dieses mit Vermerk.\n")

    for sec_key, sec_title, prefix in SECTIONS:
        ts = [t for t in sorted(cond) if t.startswith(prefix)]
        if not ts:
            continue
        L.append(f"## {sec_title}\n")
        rows = []
        for t in ts:
            for tl in TOOLS:
                c = cond[t].get(tl)
                if not c:
                    continue
                rows.append([t, LABELS[tl], c["status"], f(c["wall_s"], 2), f(c["runtime_s_reported"], 2), f(c["peak_ram_mb"], 0),
                             f(c["triangles"]), f(mb(c["file_size_bytes"]), 2), f(c["volume_mm3"] and c["volume_mm3"] / 1000, 2),
                             f(c["area_mm2"] and c["area_mm2"] / 100, 1), f(c["watertight"]), f(c["ref_dev_mean_mm"], 3), f(c["code_loc"]),
                             short(c["notes"], 110)])
        L.append(table(["Aufgabe", "Tool", "Status", "Wand s", "Tool s", "RAM MB", "Dreiecke", "STL MB", "Vol cm3", "Flaeche cm2",
                        "dicht", "Abw. Ref. mm", "LOC", "Bemerkung"], rows))
    # Details Referenzabgleich
    ref_rows = []
    for t in sorted(cond):
        for tl in TOOLS:
            c = cond[t].get(tl)
            for p, v in (c or {}).get("ref_dev_parts", {}).items():
                ref_rows.append([t, LABELS[tl], p, f(v["mean_mm"], 3), f(v["p95_mm"], 3), f(v["max_mm"], 2), f(v["icp_mean_mm"], 3),
                                 f(v["icp_rot_deg"], 2), f(v["icp_trans_mm"], 2)])
    if ref_rows:
        L.append("## Abweichung zur STEP-Referenz je Teil\n")
        L.append(table(["Aufgabe", "Tool", "Teil", "Mittel mm", "p95 mm", "Max mm", "Mittel nach ICP mm", "ICP Drehung deg", "ICP Verschiebung mm"], ref_rows))
        L.append("Hinweis: Die Nasenkappe liegt in der Referenz ca. 82 mm ueber dem Oberteil (Explosionsdarstellung); dort meldet die ICP "
                 "deshalb die Vorverschiebung (Zentroid-Abstand) als Verschiebung.\n")
    # B03
    for tl in TOOLS:
        r = raw.get("B03", {}).get(tl)
        if r and r.get("variations"):
            L.append(f"## B03 Gruppen-Variation - {LABELS[tl]}\n")
            rows = [[v["group"], v.get("param", "-"), f"{v.get('baseline_value')} -> {v.get('new_value')}", v.get("status"), f(v.get("wall_s"), 2),
                     ", ".join(v.get("changed_parts", [])) or "-", ", ".join(v.get("expected_parts", [])) or "-",
                     ("ja" if v.get("independent") else "NEIN: " + ",".join(v.get("unexpected_changes", []))) if v.get("independent") is not None else "-"]
                    for v in r["variations"]]
            L.append(table(["Gruppe", "Parameter", "Wert", "Status", "Regen s", "geaenderte Teile", "erwartet (Annahme)", "unabhaengig"], rows))
    # B07
    sw = (raw.get("B07", {}).get("voxel") or {}).get("sweep")
    if sw:
        L.append("## B07 Voxelgroessen-Sweep (Voxel)\n")
        rows = [[f"{s['voxel_mm']:g}", s.get("status"), f(s.get("wall_s"), 2), f(s.get("peak_ram_mb"), 0), f(s.get("triangles")), f(mb(s.get("file_size_bytes")), 2),
                 f((s.get("volume_mm3") or 0) / 1000, 2), f(((s.get("vs_brep") or {}).get("volume_rel_err") or 0) * 100 if (s.get("vs_brep") or {}).get("volume_rel_err") is not None else None, 2),
                 f((s.get("vs_brep") or {}).get("mean_mm"), 3), f((s.get("vs_brep") or {}).get("p95_mm"), 3), f((s.get("vs_brep") or {}).get("max_mm"), 2),
                 f(s["vs_brep_inertia_rel_err"] * 100 if s.get("vs_brep_inertia_rel_err") is not None else None, 2), f(s.get("watertight"))] for s in sw]
        L.append(table(["Voxel mm", "Status", "Wand s", "RAM MB", "Dreiecke", "STL MB", "Vol cm3", "Vol-Fehler %", "Abw. Mittel mm", "p95 mm", "Max mm", "Traegheit-Fehler %", "dicht"], rows))
        L.append(_g(raw, "B07", "voxel", "sweep_note", default="") + "\n")
        co = _g(raw, "B07", "voxel", "sweep_convergence_order_mean_dev")
        cv = _g(raw, "B07", "voxel", "sweep_convergence_order_volume_err")
        if co is not None or cv is not None:
            L.append(f"Konvergenzordnung (Steigung im log-log-Diagramm ueber die Voxelgroesse): mittlere Abweichung {f(co, 2)}, Volumenfehler {f(cv, 2)}.\n")
    # B10 Skalierung
    b10rows = []
    for tl in TOOLS:
        for sc in (raw.get("B10", {}).get(tl) or {}).get("scaling") or []:
            b10rows.append([LABELS[tl], sc["label"], sc.get("status"), f(sc.get("wall_s"), 2), f(sc.get("peak_ram_mb"), 0), f(sc.get("triangles")),
                            f(mb(sc.get("file_size_bytes")), 2), f(mb(sc.get("step_size_bytes")), 2), f(sc.get("watertight"))])
    if b10rows:
        L.append("## B10 Skalierung (B02 in Stufen)\n")
        L.append(table(["Tool", "Stufe", "Status", "Wand s", "RAM MB", "Dreiecke", "STL MB", "STEP MB", "dicht"], b10rows))
    # Stirnflaechen
    fa = [[t, LABELS[tl], f(c["frontal_area_z_mm2"], 0), f(c["frontal_area_x_mm2"], 0), f(c["frontal_pixel_mm"], 3)]
          for t in sorted(cond) for tl in TOOLS if (c := cond[t].get(tl)) and c.get("frontal_area_z_mm2")]
    if fa:
        L.append("## Stirnflaechen aus dem Mesh (Rasterung)\n")
        L.append(table(["Aufgabe", "Tool", "Draufsicht Z mm2", "Frontansicht X mm2", "Pixel mm"], fa))
        L.append("Stirnflaeche X = Projektion auf die YZ-Ebene (Anstroemung entlang X), Z = auf die XY-Ebene. "
                 "Randbias der Rasterung <= Umfang x Pixel / 2 (im Selbsttest < 0.1 % bei Kugel/Quader).\n")
    # API
    L.append("## API und Automatisierung (A01-A05)\n")
    api_rows = []
    for tl in TOOLS:
        cs = [cond[t][tl] for t in cond if tl in cond[t]]
        n_ok = sum(1 for c in cs if c["status"] in ("ok", "partial"))
        n_uns = sum(1 for c in cs if c["status"] == "unsupported")
        n_fail = sum(1 for c in cs if c["status"] == "failed")
        n_nr = sum(1 for c in cs if c["status"] == "not_run")
        over = [c["wall_s"] - c["runtime_s_reported"] for c in cs if c["wall_s"] and c["runtime_s_reported"] and c["status"] in ("ok", "partial")]
        loc = [c["code_loc"] for c in cs if c.get("code_loc")]
        api_rows.append([LABELS[tl], f"{n_ok} ok/partial, {n_uns} unsupported, {n_fail} failed, {n_nr} nicht gelaufen",
                         f(statistics.median(over), 2) if over else "-", f(max(loc)) if loc else "-", "ja (result.json je Aufruf)" if cs else "-"])
    L.append(table(["Werkzeug", "Aufgaben-Status", "Start-Overhead s (Wandzeit - Tool-Zeit, Median)", "max. LOC/Aufgabe", "headless CLI"], api_rows))
    if fm:
        L.append("Weitere Kriterien (Lizenz, Doku, KI-Eignung) siehe `spec/feature_matrix.json` (Agent Recherche); der Runner misst nur die obigen Kennzahlen.\n")
    L.append("## Grenzen der Messung\n"
             "- RAM = Spitzen-Working-Set (Windows) des Prozessbaums, Abfrage alle 0.1 s; kurze Spitzen am Ende koennen fehlen.\n"
             "- Wandzeit enthaelt Prozessstart (Python-Import bzw. .NET-Start); die Tool-eigene Zeit steht daneben.\n"
             "- Mesh-Metriken kommen aus den STL-Dateien (Weld-Toleranz 1e-3 mm); Volumen nur bei wasserdichtem Mesh belastbar.\n"
             "- Abweichungen sind Stichproben-Naeherungen (200k Punkte je Richtung, exakter Punkt-Dreieck-Abstand der 6 naechsten Kandidaten).\n")
    txt = "\n".join(L)
    (run_dir / "summary.md").write_text(txt, encoding="utf-8")
    return txt


# --------------------------------------------------------------------------- Hauptfunktion

def build_report(run_dir) -> dict:
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "run_meta.json").read_text(encoding="utf-8")) if (run_dir / "run_meta.json").exists() else {}
    raw = _load(run_dir)
    cond = {t: {tl: condense(r) for tl, r in d.items()} for t, d in raw.items()}
    winners = {}
    for t, cs in cond.items():
        winners[t] = decide_b03(cs, raw[t]) if t == "B03" else decide(t, cs, t[0])
    charts = make_charts(run_dir, cond, raw)
    fm_path = ROOT / "spec" / "feature_matrix.json"
    fm = json.loads(fm_path.read_text(encoding="utf-8")) if fm_path.exists() else None
    write_markdown(run_dir, meta, cond, raw, winners, charts, fm)
    summary = {
        "run_id": meta.get("run_id", run_dir.name), "fake": meta.get("fake", False), "meta": meta,
        "tasks": {t: {"title": meta.get("task_titles", {}).get(t), "section": {"B": "common", "V": "voxel_only", "R": "brep_only"}[t[0]],
                      "tools": cond[t], "winner": winners[t]} for t in sorted(cond)},
        "b07_sweep": _g(raw, "B07", "voxel", "sweep"), "charts": charts,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return summary


def main() -> int:
    d = Path(sys.argv[1]) if len(sys.argv) > 1 else RESULTS / "latest"
    build_report(d)
    print("Report:", d / "summary.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
