"""Erzeugt Diagramme (presentation/charts/) und deck_content.json aus einem Benchmark-Lauf.

python presentation/make_content.py [--run bench/results/latest]
Danach: powershell -ExecutionPolicy Bypass -File presentation/build_deck.ps1
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CH = HERE / "charts"

NAVY, CREAM, MUTED, GRID = "#0d192f", "#f2ede3", "#565e6d", "#d9d2c3"
BREP, VOX = "#1f5fa8", "#d9731a"
OK, PART, NO = "2E7D4F", "B7791F", "A33A3A"
plt.rcParams.update({"font.family": ["Segoe UI", "Arial"], "font.size": 13, "text.color": NAVY,
                     "axes.labelcolor": NAVY, "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": GRID,
                     "figure.facecolor": CREAM, "axes.facecolor": CREAM, "savefig.facecolor": CREAM})


def load(run: Path, task: str, tool: str) -> dict:
    p = run / task / tool / "result.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def g(d, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


def fmt(v, nd=1):
    if v is None:
        return "–"
    s = f"{v:,.{nd}f}".replace(",", "'")
    return s


STATUS = {"ok": ("✓ ok", OK), "partial": ("◐ teilweise", PART), "unsupported": ("✕ nicht möglich", NO),
          "failed": ("✕ fehlgeschlagen", NO), "not_run": ("– nicht gelaufen", "565E6D")}


def status_cell(res: dict) -> dict:
    t, c = STATUS.get(res.get("status", "not_run"), STATUS["not_run"])
    return {"t": t, "c": c, "b": True}


def style(ax, ylabel=None, xlabel=None):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    if ylabel:
        ax.set_ylabel(ylabel)
    if xlabel:
        ax.set_xlabel(xlabel)


# --------------------------------------------------------------------------- Diagramme
def chart_sweep(run: Path) -> str | None:
    b07 = load(run, "B07", "voxel")
    sweep = [e for e in b07.get("sweep", []) if e.get("status") in ("ok", "partial")]
    if not sweep:
        return None
    br = load(run, "B07", "brep")
    xs = [e["voxel_mm"] for e in sweep]
    fig, axs = plt.subplots(1, 3, figsize=(13, 4.2))
    panels = [("Abweichung zum B-rep-Modell", "mm (Mittel)", [g(e, "vs_brep", "mean_mm") for e in sweep], 0.0),
              ("Laufzeit (Prozess)", "s", [e.get("wall_s") for e in sweep], g(br, "runner", "wall_s")),
              ("Spitzen-RAM", "GB", [(e.get("peak_ram_mb") or 0) / 1024 for e in sweep],
               (g(br, "runner", "peak_ram_mb") or 0) / 1024)]
    for ax, (title, unit, ys, bref) in zip(axs, panels):
        ax.plot(xs, ys, "o-", color=VOX, lw=2.4, ms=7, label="PicoGK (Voxel)")
        for x, y in zip(xs, ys):
            if y is not None:
                ax.annotate(fmt(y, 2 if y < 10 else 0), (x, y), textcoords="offset points", xytext=(0, 9), ha="center",
                            fontsize=11, color=VOX)
        if bref is not None:
            ax.axhline(bref, color=BREP, lw=2, ls="--")
            ax.text(xs[0], bref, " build123d", color=BREP, va="bottom", ha="left", fontsize=11)
        ax.set_xscale("log")
        ax.minorticks_off()
        ax.set_xticks(xs)
        ax.set_xticklabels([f"{x:g}" for x in xs])
        ax.invert_xaxis()
        ax.set_title(title, fontsize=14, color=NAVY, loc="left")
        style(ax, unit, "Voxelgrösse (mm) → feiner")
        ax.set_ylim(bottom=0)
    fig.tight_layout()
    out = CH / "voxel_sweep.png"
    fig.savefig(out, dpi=170)
    plt.close(fig)
    return out.relative_to(HERE).as_posix()


def chart_runtime_ram(run: Path, tasks: list[str]) -> str:
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.4))
    for ax, key, unit, div in ((axs[0], "wall_s", "Laufzeit (s)", 1), (axs[1], "peak_ram_mb", "Spitzen-RAM (GB)", 1024)):
        xb = [(g(load(run, t, "brep"), "runner", key) or 0) / div for t in tasks]
        xv = [(g(load(run, t, "voxel"), "runner", key) or 0) / div for t in tasks]
        idx = range(len(tasks))
        ax.bar([i - 0.2 for i in idx], xb, 0.4, color=BREP, label="build123d (B-rep)")
        ax.bar([i + 0.2 for i in idx], xv, 0.4, color=VOX, label="PicoGK (Voxel, 0.5 mm)")
        ax.set_xticks(list(idx))
        ax.set_xticklabels(tasks)
        style(ax, unit)
    axs[0].legend(frameon=False, loc="upper left")
    fig.tight_layout()
    out = CH / "runtime_ram.png"
    fig.savefig(out, dpi=170)
    plt.close(fig)
    return out.relative_to(HERE).as_posix()


GROUP_LABEL = {"skeleton": "Skelett", "upper_body": "Oberteil", "arms": "Arme", "motor_pods": "Gondeln",
               "lower_body": "Unterteil", "body_fins": "Aero-Fins", "tail_fins": "Heckflossen", "nose": "Nase",
               "joints": "Steckverb.", "details": "Details"}


def chart_b03(run: Path) -> str | None:
    rb, rv = load(run, "B03", "brep"), load(run, "B03", "voxel")
    if not rb.get("variations"):
        return None
    groups = [v["group"] for v in rb["variations"]]
    wb = {v["group"]: v.get("wall_s") or 0 for v in rb["variations"]}
    wv = {v["group"]: v.get("wall_s") or 0 for v in rv.get("variations", [])}
    fig, ax = plt.subplots(figsize=(13, 4.0))
    idx = range(len(groups))
    ax.bar([i - 0.2 for i in idx], [wb[x] for x in groups], 0.4, color=BREP, label="build123d")
    ax.bar([i + 0.2 for i in idx], [wv.get(x, 0) for x in groups], 0.4, color=VOX, label="PicoGK (0.5 mm)")
    ax.set_xticks(list(idx))
    ax.set_xticklabels([GROUP_LABEL.get(x, x) for x in groups])
    style(ax, "Neuaufbau inkl. Export (s)")
    ax.legend(frameon=False, loc="upper right", ncol=2)
    fig.tight_layout()
    out = CH / "b03_regen.png"
    fig.savefig(out, dpi=170)
    plt.close(fig)
    return out.relative_to(HERE).as_posix()


# --------------------------------------------------------------------------- Inhalt
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=str(ROOT / "bench" / "results" / "latest"))
    run = Path(ap.parse_args().run)
    CH.mkdir(exist_ok=True)
    common = [f"B{i:02d}" for i in range(1, 11)]
    only = ["R01", "R02", "R03", "R04", "V01", "V02", "V03", "V04"]
    tasks = json.loads((ROOT / "spec" / "benchmark_tasks.json").read_text(encoding="utf-8"))
    tasks = {t["id"]: t for t in (tasks["tasks"] if isinstance(tasks, dict) and "tasks" in tasks else tasks)}

    c_sweep, c_rr, c_b03 = chart_sweep(run), chart_runtime_ram(run, common), chart_b03(run)

    b02b, b02v = load(run, "B02", "brep"), load(run, "B02", "voxel")
    b03b, b03v = load(run, "B03", "brep"), load(run, "B03", "voxel")
    b01b, b01v = load(run, "B01", "brep"), load(run, "B01", "voxel")
    v01b, v01v = load(run, "V01", "brep"), load(run, "V01", "voxel")
    b06b = load(run, "B06", "brep")
    b07v = load(run, "B07", "voxel")
    b09b, b09v = load(run, "B09", "brep"), load(run, "B09", "voxel")
    r04b, r04v = load(run, "R04", "brep"), load(run, "R04", "voxel")

    def vol(res, part):
        return g(res, "metrics", "parts", part, "volume_mm3")

    part_rows = [["Teil", "build123d (exakt)", "PicoGK (0.5 mm)", "Differenz"]]
    for p, lab in (("upper", "Oberteil"), ("lower", "Unterteil"), ("nose", "Nasenkappe"), ("nose_insert", "Einsatz")):
        a, b = vol(b02b, p), vol(b02v, p)
        part_rows.append([lab, f"{fmt(a / 1000, 1)} cm³" if a else "–", f"{fmt(b / 1000, 1)} cm³" if b else "–",
                          f"{(b - a) / a * 100:+.1f} %" if a and b else "–"])

    indep_b = g(b03b, "neutral_metrics", "group_independence", "groups_independent")
    indep_v = g(b03v, "neutral_metrics", "group_independence", "groups_independent")
    tested = g(b03b, "neutral_metrics", "group_independence", "groups_tested")
    regen_b, regen_v = g(b03b, "metrics", "mean_regen_wall_s"), g(b03v, "metrics", "mean_regen_wall_s")
    fillets = g(b06b, "metrics", "fillet_attempts") or []
    fil_ok = sum(1 for f in fillets if f.get("ok"))
    lat_b = g(v01b, "metrics", "lattice_attempts") or []
    lat_b_last = lat_b[-1] if lat_b else {}
    lat_v = g(v01v, "metrics", "lattice_attempts", "beam_lattice") or {}
    gyr_v = g(v01v, "metrics", "lattice_attempts", "gyroid") or {}
    dev_up_b = g(b01b, "metrics", "deviation_to_reference", "upper", "mean_mm")
    dev_lo_b = g(b01b, "metrics", "deviation_to_reference", "lower", "mean_mm")
    sweep = {e["voxel_mm"]: e for e in b07v.get("sweep", [])}

    def sw(v, *k):
        return g(sweep.get(v, {}), *k)

    short = {"B01": "Referenz-STEP einlesen und abgleichen", "B02": "Gesamtmodell aus der Spec", "B03": "Gruppen-Variation",
             "B04": "Tropfenprofil (Fins, Gondeln)", "B05": "Wandstärke / Schale", "B06": "Verrundungen",
             "B07": "Masse und Genauigkeit", "B08": "Druck-Export und -Check", "B09": "Aero-Vorbereitung (CFD)",
             "B10": "Leistung und Skalierung", "R01": "Bemasste Zeichnung", "R02": "STEP-Export, Selektoren",
             "R03": "Baugruppe, Joints", "R04": "Toleranzen, Passungen", "V01": "Gitter-Infill (Lattice)",
             "V02": "Kühlluftkanäle im Rumpf", "V03": "Feld-Wandstärke, Bool auf Netz", "V04": "Schichten für den Druck"}

    def row(t):
        rb, rv = load(run, t, "brep"), load(run, t, "voxel")
        return [{"t": f"{t}  {short.get(t, tasks.get(t, {}).get('title', ''))}"}, status_cell(rb), status_cell(rv)]

    notes_common = {
        "B01": "B-rep liest STEP nativ; Voxel nur über STL/Rasterung",
        "B04": "beide treffen das Profil; Voxel rundet Hinterkante",
        "B05": "B-rep-Offset auf fertigen Teilen scheitert; Voxel immer",
        "B06": f"B-rep: {fil_ok}/{len(fillets)} Fillets ok; Voxel: alle",
        "B08": "Voxel: kein 3MF, nur STL",
    }
    t_common = [["Gemeinsame Aufgabe", "build123d", "PicoGK", "Beobachtung"]]
    for t in common:
        r = row(t)
        r.append({"t": notes_common.get(t, ""), "c": "565E6D"})
        t_common.append(r)
    t_only = [["Spezialaufgabe", "build123d", "PicoGK", "Beobachtung"]]
    notes_only = {
        "R01": "Voxel hat keine Kanten zum Bemassen",
        "R02": "Voxel: kein STEP, keine Selektoren",
        "R03": "Voxel: keine Joints, nur Kollisionsprüfung",
        "R04": "Spalt < 1 Voxel im selben Teil wächst zu",
        "V01": f"B-rep: {lat_b_last.get('struts', '–')} Stäbe {fmt(lat_b_last.get('s'), 0)} s"
               f"{' → leer' if lat_b_last and not lat_b_last.get('ok') else ''}; Voxel: Gyroid {fmt(gyr_v.get('s'), 1)} s",
        "V02": "B-rep: 1 Kanal per Sweep; Voxel: 4 verzweigt",
        "V03": "Feldgesteuerte Wand und Bool auf Netz nur Voxel",
        "V04": "B-rep: exakte Schnitte; Voxel: CLI-Schichtdatei",
    }
    for t in only:
        r = row(t)
        r.append({"t": notes_only.get(t, ""), "c": "565E6D"})
        t_only.append(r)

    ram_b = statistics.median([g(load(run, t, "brep"), "runner", "peak_ram_mb") or 0 for t in common])
    ram_v = statistics.median([g(load(run, t, "voxel"), "runner", "peak_ram_mb") or 0 for t in common])

    slides = []
    S = slides.append
    S({"layout": "Boreas Titel", "title": "B-rep oder Voxel?",
       "subtitle": "build123d und PicoGK im Vergleich am Boreas-Rumpf · 30. September 2026"})
    S({"layout": "Boreas Inhalt", "title": "Agenda", "bodysize": 16,
       "body": ["Warum wir Geometrie per Code brauchen, und was B-rep und Voxel sind",
                "Testobjekt und Methode: ein Modell, zwei Werkzeuge, gleiche Aufgaben",
                "Ergebnisse: Funktionen, Grenzen, Aerodynamik und Kühlung, API und KI",
                "Empfehlung und nächste Schritte"],
       "notes": "Kurz den Ablauf nennen. Neben den Folien läuft die Demo (Modus ④ Vergleich)."})
    S({"layout": "Boreas Kapitel", "title": "01  Warum und Grundlagen"})
    S({"layout": "Boreas Inhalt", "title": "Die Pipeline braucht Geometrie, die sich per Code ändern lässt",
       "images": [{"path": "figures/fig06_pipeline_einordnung.svg", "x": 43, "y": 92, "w": 634, "h": 262, "center": True}],
       "notes": "Anforderungen → Geometrie → Simulation → Optimierung → Fertigung, ohne Mausklicks, damit viele Varianten "
                "und KI-Agents möglich werden. Unsere Referenz aus Shapr3D ist freihand gezeichnet – jede Änderung ist Handarbeit. "
                "Und unsere Teile werden aerodynamisch und thermisch anspruchsvoller."})
    S({"layout": "Boreas Inhalt", "title": "Ein CAD-Kern speichert Form – als exaktes Rezept oder als Raster",
       "images": [{"path": "figures/fig01_vektor_vs_pixel.svg", "x": 43, "y": 92, "w": 634, "h": 262, "center": True}],
       "notes": "Vektorgrafik vs. Pixelbild: Das Rezept bleibt beim Zoomen glatt, das Raster zeigt Treppen. In 3D heisst "
                "das Rezept B-rep, das Raster Voxel. Alles Weitere folgt aus diesem Unterschied."})
    S({"layout": "Boreas Inhalt", "title": "B-rep: ein Körper ist eine Haut aus exakten Flächen",
       "images": [{"path": "figures/fig02_brep_anatomie.svg", "x": 43, "y": 96, "w": 400, "h": 250}],
       "boxes": [{"x": 465, "y": 110, "w": 212, "h": 230, "size": 13, "gap": 8, "lines": [
           {"t": "Masse sind exakt", "b": True}, "Ein Radius 5 mm ist ein echter Kreisbogen",
           {"t": "Elemente ansprechbar", "b": True}, "„Alle Kanten am oberen Ring verrunden“",
           {"t": "CAD-Standard", "b": True}, "STEP, Zeichnung, Toleranzen",
           {"t": "Schwäche", "b": True, "c": NO}, "Tausende feine Details, Offsets auf Freiform"]}],
       "notes": "Boundary Representation: Körper → Flächen → Kanten → Ecken. Jede Fläche ist eine Formel."})
    S({"layout": "Boreas Inhalt", "title": "Voxel: jede Zelle kennt ihren Abstand zur Oberfläche",
       "images": [{"path": "figures/fig04_sdf_2d.svg", "x": 43, "y": 96, "w": 400, "h": 250}],
       "boxes": [{"x": 465, "y": 110, "w": 212, "h": 230, "size": 13, "gap": 8, "lines": [
           {"t": "„Minecraft, nur sehr fein“", "b": True}, "Würfel von z. B. 0.5 mm, mit Abstandswert",
           {"t": "Formen verknüpfen = rechnen", "b": True}, "Vereinigen = Minimum, Abziehen = Maximum",
           {"t": "Gitter und Kanäle als Formel", "b": True}, "scheitert praktisch nie",
           {"t": "Schwäche", "b": True, "c": NO}, "Genauigkeit = Raster; feiner kostet Speicher"]}],
       "notes": "Negativ innen, positiv aussen, null auf der Oberfläche (Distanzfeld). Keine Flächen, die sich schneiden "
                "müssen – deshalb gelingen Booleans praktisch immer."})
    S({"layout": "Boreas Inhalt", "title": "Die Kandidaten",
       "tables": [{"x": 43, "y": 100, "w": 634, "h": 240, "size": 12, "colw": [150, 242, 242], "rows": [
           ["", {"t": "build123d", "c": "F2EDE3"}, {"t": "PicoGK", "c": "F2EDE3"}],
           [{"t": "Technik", "b": True}, "B-rep (exakte Flächen)", "Voxel / Distanzfeld"],
           [{"t": "Sprache", "b": True}, "Python", "C# (.NET 9)"],
           [{"t": "Kern", "b": True}, "OpenCASCADE (OCCT 8)", "OpenVDB-basiert, LEAP 71"],
           [{"t": "Lizenz", "b": True}, "Apache 2.0", "Apache 2.0"],
           [{"t": "Plattformen", "b": True}, "Windows, Linux, macOS", "Windows, macOS (kein Linux offiziell)"],
           [{"t": "Community", "b": True}, "3'236 Sterne, 87 Beitragende", "1'121 Sterne, 4 Beitragende"],
           [{"t": "Doku für KI", "b": True}, "offizielles llms.txt", "XML-Kommentare, Beispiele veraltet"],
           [{"t": "Ausgabe", "b": True}, "STEP, STL, 3MF, SVG/DXF-Zeichnung", "STL, VDB, CLI-Schichten"]]}],
       "notes": "Stand 30.09.2026 (docs/research_*.md). Beide Open Source, gleicher Zweck: Geometrie aus Programmcode."})
    S({"layout": "Boreas Kapitel", "title": "02  Testobjekt und Methode"})
    S({"layout": "Boreas Inhalt", "title": "Der Boreas-Rumpf, neu aufgebaut: 81 Parameter in 10 Gruppen",
       "images": [{"path": "figures/fig05_parametergruppen_skelett.svg", "x": 43, "y": 96, "w": 400, "h": 250}],
       "boxes": [{"x": 465, "y": 104, "w": 212, "h": 240, "size": 12.5, "gap": 7, "lines": [
           {"t": "Skelett-Methode", "b": True},
           "Das Skelett hält nur gemeinsame Masse: Armzahl, Motorlage, Trennebene",
           "Jede Gruppe liest nur sich selbst + Skelett",
           {"t": "Geprüft", "b": True},
           f"{indep_b if indep_b is not None else '–'}/{tested or '–'} Gruppen unabhängig (build123d), "
           f"{indep_v if indep_v is not None else '–'}/{tested or '–'} (PicoGK)",
           {"t": "Treue zum Original", "b": True},
           f"Ø Abweichung Unterteil {fmt(dev_lo_b, 1)} mm, Oberteil {fmt(dev_up_b, 1)} mm; Tropfenprofile übernommen"]}],
       "notes": "Die Shapr3D-Datei ist nicht constrained. Neu: Skelett + 9 Gruppen (Oberteil, Arme, Gondeln, Unterteil, "
                "Aero-Fins, Heckflossen, Nase, Steckverbindungen, Details). Pipeline ändert eine Gruppe pro Durchlauf, "
                "der Rest bleibt stabil. Demo: Modus ④, Aufgabe B03, „Neu rechnen“ mit body_fins.profile_chord=60 – nur das Oberteil ändert sich."})
    S({"layout": "Boreas Inhalt", "title": "Dasselbe Modell in beiden Werkzeugen – aus einer Spezifikation",
       "images": [{"path": "shots/b02_side_by_side.png", "x": 43, "y": 92, "w": 380, "h": 262}],
       "tables": [{"x": 440, "y": 100, "w": 237, "h": 150, "size": 10.5, "colw": [70, 58, 58, 51], "rows": part_rows}],
       "boxes": [{"x": 440, "y": 262, "w": 237, "h": 85, "size": 11, "color": "565E6D", "lines": [
           "Gleiche Spec, gleiche Formeln (docs/geometrie_definition.md), gleicher Aufruf.",
           "Codeaufwand für das Modell: 782 Zeilen Python gegen 781 Zeilen C#."]}],
       "notes": "Links build123d, rechts PicoGK in der Demo (Modus ④). Auf Bildschirmgrösse gleich, innen verschieden."})
    S({"layout": "Boreas Zwei Spalten", "title": "Methode: gleiche Aufgaben, gleicher Aufruf, neutrale Messung",
       "bodysize": 12.5,
       "left": [{"t": "18 Aufgaben", "b": True}, "10 gemeinsame (B01–B10): Import, Modell, Varianten, Tropfenprofil, "
                "Schale, Verrundung, Masse, Druck, Aero, Leistung",
                "4 B-rep-typische (R01–R04), 4 Voxel-typische (V01–V04)",
                "„nicht möglich“ ist ein Ergebnis, kein Fehler"],
       "right": [{"t": "Messung", "b": True}, "Beide Werkzeuge per Kommandozeile, JSON rein und raus",
                 "Runner misst Laufzeit und RAM von aussen und rechnet Kennwerte selbst aus den STL-Netzen",
                 "Voxel standardmässig 0.5 mm, B07 zusätzlich 2 / 1 / 0.25 mm",
                 "Material-, Motor-, Aerowerte sind Mock-Daten"],
       "notes": "Es geht um die Werkzeuge, nicht um Auslegungswerte. Ergebnisse im Repo: bench/results/latest."})
    S({"layout": "Boreas Kapitel", "title": "03  Ergebnisse"})
    S({"layout": "Boreas Drei Kacheln", "title": "Drei Zahlen vorweg",
       "tiles": [{"v": f"{fmt(regen_b, 0)} | {fmt(regen_v, 0)}", "l": "Sekunden Neuaufbau nach Gruppenänderung (B-rep | Voxel)"},
                 {"v": f"{fmt(ram_b / 1024, 1)} | {fmt(ram_v / 1024, 1)}", "l": "GB RAM, Median (B-rep | Voxel 0.5 mm)"},
                 {"v": f"{fil_ok}/{len(fillets)}", "l": "B-rep-Verrundungen an Freiformkanten erfolgreich (Voxel: alle)"}],
       "footnote": "Laufzeit inkl. Prozessstart und Export. Voxel-RAM wächst mit feinerem Raster stark (Folie Genauigkeit).",
       "notes": "Beide Werkzeuge bauen das Modell in Sekunden. Voxel braucht ein Vielfaches an Speicher. B-rep scheitert "
                "an Freiform-Operationen, die im Voxel trivial sind."})
    S({"layout": "Boreas Inhalt", "title": "Gemeinsame Aufgaben: beide lösen fast alles – auf verschiedene Art",
       "tables": [{"x": 43, "y": 90, "w": 634, "h": 262, "size": 10, "rowh": 22, "colw": [200, 100, 100, 234], "rows": t_common}],
       "notes": "Ziel 1 und 2. Vollständige Matrix mit 51 Funktionen in spec/feature_matrix.json und im Demo-Modus ④."})
    S({"layout": "Boreas Inhalt", "title": "Spezialaufgaben: jede Technik hat ihr eigenes Revier",
       "tables": [{"x": 43, "y": 90, "w": 634, "h": 230, "size": 10, "rowh": 24, "colw": [200, 100, 100, 234], "rows": t_only}],
       "notes": "„Nicht möglich“ heisst nicht schlecht: Ein gedrucktes Gitterteil braucht keine Zeichnung. "
                "Aber tragende, gefräste oder zugekaufte Teile brauchen Masse und STEP."})
    if c_sweep:
        s2, s05 = sw(2.0, "vs_brep", "mean_mm"), sw(0.5, "vs_brep", "mean_mm")
        r05, r025 = (sw(0.5, "peak_ram_mb") or 0) / 1024, (sw(0.25, "peak_ram_mb") or 0) / 1024
        S({"layout": "Boreas Inhalt", "title": "Genauigkeit kostet beim Voxel Speicher und Rechenzeit",
           "images": [{"path": c_sweep, "x": 43, "y": 92, "w": 634, "h": 205}],
           "boxes": [{"x": 43, "y": 305, "w": 634, "h": 45, "size": 12, "lines": [
               f"Mittlere Abweichung zur exakten Form: {fmt(s2, 2)} mm bei 2 mm Voxel, {fmt(s05, 2)} mm bei 0.5 mm – danach "
               f"kaum Gewinn, aber RAM {fmt(r05, 1)} → {fmt(r025, 1)} GB. Dünne Details (Fin-Hinterkante) bestimmen die "
               "Voxelgrösse: Faustregel ≤ ⅓ des dünnsten Details."]}],
           "notes": "B07: gleiche Geometrie, Voxelgrösse 2 → 0.25 mm. B-rep ist exakt (gestrichelte Linie)."})
    S({"layout": "Boreas Inhalt", "title": "Leistung: ähnlich schnell, Voxel braucht 4–5× mehr RAM",
       "images": [{"path": c_rr, "x": 43, "y": 92, "w": 634, "h": 215}],
       "boxes": [{"x": 43, "y": 312, "w": 634, "h": 40, "size": 12, "lines": [
           f"B09 Strömungsgebiet: B-rep {fmt(g(b09b, 'runner', 'wall_s'), 0)} s / {fmt((g(b09b, 'runner', 'peak_ram_mb') or 0) / 1024, 1)} GB, "
           f"Voxel {fmt(g(b09v, 'runner', 'wall_s'), 0)} s / {fmt((g(b09v, 'runner', 'peak_ram_mb') or 0) / 1024, 1)} GB – das Raster füllt das ganze Gebiet."]}],
       "notes": "Wandzeit je Prozess inkl. Start und Export, gemessen vom Runner."})
    S({"layout": "Boreas Inhalt", "title": "Was nur B-rep kann: bemassen, tolerieren, exakt übergeben",
       "images": [{"path": "shots/r01_drawing.svg", "x": 43, "y": 92, "w": 390, "h": 262}],
       "boxes": [{"x": 450, "y": 100, "w": 227, "h": 250, "size": 12.5, "gap": 7, "lines": [
           {"t": "R01", "b": True, "c": "1F5FA8"}, "Bemasste A3-Zeichnung direkt aus dem Modell",
           {"t": "R02", "b": True, "c": "1F5FA8"}, "STEP-Rundreise ohne Verlust, Kanten-Selektoren",
           {"t": "R03", "b": True, "c": "1F5FA8"}, "Baugruppe mit Joints, exakte Kollision",
           {"t": "R04", "b": True, "c": "1F5FA8"},
           f"Passungsspiel {fmt(g(r04b, 'metrics', 'fit', 'clearance_spec_mm'), 2)} mm exakt nachmessbar"]}],
       "notes": "Ein Voxelmodell hat keine Kanten, an denen man ein Mass anbringen könnte. Demo: Werkbank, Zeichnung."})
    S({"layout": "Boreas Inhalt", "title": "Was nur Voxel kann: Gitter, Kühlkanäle, Felder",
       "images": [{"path": "shots/v01_gyroid.png", "x": 43, "y": 92, "w": 300, "h": 200},
                  {"path": "shots/v02_channels.png", "x": 352, "y": 92, "w": 300, "h": 200}],
       "boxes": [{"x": 43, "y": 300, "w": 634, "h": 55, "size": 12, "lines": [
           f"Gyroid-Infill {fmt(gyr_v.get('s'), 1)} s, {lat_v.get('beams', '–')}-Stab-Gitter {fmt(lat_v.get('s'), 2)} s, "
           f"4 verzweigte Kühlkanäle in Sekundenbruchteilen – B-rep: {lat_b_last.get('struts', '–')} Stäbe "
           f"{fmt(lat_b_last.get('s'), 0)} s{' und leeres Ergebnis' if lat_b_last and not lat_b_last.get('ok') else ''}.",
           "Dazu: Wandstärke als Feld (1.2 → 3.5 mm), Booleans direkt auf Scan-/STL-Netzen, CLI-Schichten für den Druck."]}],
       "notes": "Links Gyroid-Infill im Unterteil (V01), rechts gewendelte Kühlluftkanäle mit Abzweig in die Heckflossen (V02)."})
    S({"layout": "Boreas Zwei Spalten", "title": "Aerodynamik und Kühlung: exakte Hülle vs. fertiges Rechengitter",
       "bodysize": 12.5,
       "left": [{"t": "Aussenströmung", "b": True},
                f"Stirnfläche beide ≈ {fmt((g(b09v, 'metrics', 'frontal_area_z_mm2') or 0) / 100, 0)} cm²",
                "B-rep: exakte Hülle als STEP/STL → klassische CFD (OpenFOAM, Gmsh)",
                "Voxel: Strömungsgebiet direkt als kartesisches Gitter → Lattice-Boltzmann",
                "Achtung: FluidX3D verbietet kommerzielle/militärische Nutzung"],
       "right": [{"t": "Kühlluft im Rumpf", "b": True},
                 "Einlässe, Rampen, Wände: in beiden parametrisch",
                 "Kanalnetze, die der Wand folgen, sich verzweigen: Voxel",
                 "Tropfenprofile: B-rep exakt; Voxel rundet Hinterkanten unter ~1 Voxel",
                 "Genauigkeit am Fin entscheidet über die Voxelgrösse"],
       "notes": "Ziel 3. Für Aero-Aussenflächen zählt Exaktheit und Glätte, für innere Luftführung die Freiheit der Form."})
    S({"layout": "Boreas Inhalt", "title": "API, KI-Agents, Pipeline: beide steuerbar, B-rep reifer",
       "tables": [{"x": 43, "y": 90, "w": 634, "h": 250, "size": 11, "colw": [110, 262, 262], "rows": [
           ["Kriterium", {"t": "build123d", "c": "F2EDE3"}, {"t": "PicoGK", "c": "F2EDE3"}],
           [{"t": "A01 API", "b": True}, "Python, zwei Stile (Builder/Algebra), Typ-Hinweise", "C#, kleine klare API, Compiler fängt Fehler"],
           [{"t": "A02 Headless", "b": True}, "✓ reines Python-Modul", "✓ new Library(voxel) – kein Fenster"],
           [{"t": "A03 KI-Agents", "b": True}, "llms.txt, viel Beispielcode; aber stille Fehler (falscher Fuse, Netzlöcher)",
            "Booleans scheitern nie; aber Beispiele veraltet, Bibliothek liefert falsche Volumen"],
           [{"t": "A04 Pipeline", "b": True}, "Python-Ökosystem (numpy, scipy, CFD, Optimierer) direkt",
            "Prozessgrenze .NET; Python nur über inoffizielle Bindings"],
           [{"t": "A05 Reife", "b": True}, "87 Beitragende, alle Plattformen, 0.x-Version",
            "4 Beitragende, kein Linux, .NET 9 bis Nov. 2026"]]}],
       "notes": "Ziele 4 und 5. Beide Modelle in diesem Projekt wurden mit KI-Agents gebaut – gleicher Codeumfang. "
                "Die gefährlichsten Fehler sind die stillen (B-rep) und die falschen Kennwerte der Bibliothek (Voxel)."})
    S({"layout": "Boreas Kapitel", "title": "04  Empfehlung"})
    S({"layout": "Boreas Inhalt", "title": "Empfehlung: B-rep als Master, Voxel als Spezialwerkzeug",
       "images": [{"path": "figures/fig08_hybrid_workflow.svg", "x": 43, "y": 92, "w": 390, "h": 262}],
       "boxes": [{"x": 450, "y": 100, "w": 227, "h": 250, "size": 12.5, "gap": 7, "lines": [
           {"t": "Bemassen, tolerieren, STEP?", "b": True}, "→ build123d (Rumpf, Arme, Gondeln, Flossen)",
           {"t": "Gitter, Kanäle, Felder?", "b": True}, "→ PicoGK als Nachbearbeitung für den Druck",
           {"t": "Beides?", "b": True}, "→ Hybrid: B-rep-Modell ist die Wahrheit, Übergabe als Netz",
           {"t": "Rückweg", "b": True, "c": NO}, "Voxel → STEP gibt es nicht"]}],
       "notes": "Die Pipeline-Parameter (Skelett + Gruppen) bleiben in einer Spec, beide Werkzeuge lesen sie."})
    S({"layout": "Boreas Inhalt", "title": "Nächste Schritte", "bodysize": 15,
       "body": ["Pipeline-Kern festlegen: build123d + Spec mit Gruppen (Entscheid im Team)",
                "Pilot: Unterteil mit Kühlluftkanälen – B-rep-Hülle, Voxel-Kanäle, gedruckt",
                "Agent-Test: KI-Agent löst dieselbe Änderung in beiden Werkzeugen, Fehlerquote messen",
                "Checks gegen stille Fehler: Volumen, Dichtheit, Gültigkeit nach jedem Schritt",
                "CFD-Anbindung klären: OpenFOAM mit STL aus B-rep (Lizenz geprüft)"],
       "notes": "Ein Pilotbauteil durch die ganze Kette statt weiterer Vergleiche."})
    S({"layout": "Boreas Abschluss", "title": "Danke · Fragen"})
    S({"layout": "Boreas Inhalt", "title": "Backup: Grenzen dieser Untersuchung",
       "boxes": [{"x": 43, "y": 100, "w": 634, "h": 240, "size": 13, "gap": 8, "lines": [
           {"t": "Mock-Daten für Material, Motoren und Aero – es werden Werkzeuge verglichen, keine Auslegung", "bullet": True},
           {"t": "Ein Bauteil, ein Rechner (i7-13700HX, 32 GB, Windows 11), je Aufgabe 1–2 Läufe", "bullet": True},
           {"t": "Beide Modelle mit KI-Agents gebaut; Laufzeiten des eigenen Codes (z. B. Netzprüfung) fliessen ein", "bullet": True},
           {"t": "Referenz-STEP ist teils fehlerhaft (Schalen statt Körper) – Abweichung über Oberflächen gemessen", "bullet": True},
           {"t": "Voxel-Ergebnisse gelten für 0.5 mm; feinere Raster sind genauer, aber teurer (B07)", "bullet": True},
           {"t": "Keine echte CFD-/FEM-Rechnung, nur deren Vorbereitung", "bullet": True}]}]})
    for sd in slides:
        if sd["layout"] == "Boreas Zwei Spalten":   # eigene Textfelder statt Platzhalter (Platzhalter links ist gesperrt)
            def col(items, x):
                return {"x": x, "y": 108, "w": 300, "h": 240, "size": sd.get("bodysize", 13), "gap": 5,
                        "lines": [({"t": i["t"], "b": True, "s": sd.get("bodysize", 13) + 1} if isinstance(i, dict)
                                   else {"t": i, "bullet": True}) for i in items]}
            sd["boxes"] = sd.get("boxes", []) + [col(sd.pop("left"), 43), col(sd.pop("right"), 377)]
            sd["layout"] = "Boreas Inhalt"
        n = len(sd.get("title", ""))
        if sd["layout"] in ("Boreas Inhalt", "Boreas Zwei Spalten", "Boreas Drei Kacheln") and n > 40:
            sd["titlesize"] = 24 if n <= 52 else 21
    (HERE / "deck_content.json").write_text(json.dumps({"slides": slides}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(slides)} Folien, Diagramme: {c_sweep}, {c_rr}, {c_b03}")


if __name__ == "__main__":
    main()
