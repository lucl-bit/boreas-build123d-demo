# Benchmark-Runner: B-rep (build123d) vs. Voxel (PicoGK)

Vergleicht die beiden CLIs aus `PLAN.md` (`python -m brep.cli`, `dotnet run --project voxel ...`) auf denselben Aufgaben
und rechnet die Kennzahlen **werkzeugneutral aus den ausgegebenen STL-Dateien** nach, statt nur den Selbstauskuenften
der Tools zu glauben.

## Schnellstart

Alles im Repo-Root, mit dem Python, das build123d, numpy, scipy, matplotlib und pillow hat.

```bash
python -m bench.test_metrics                 # Selbsttest der Metriken (analytische Formen), ~20 s
python -m bench.reference                    # Referenz-Cache bauen (einmalig, ~20 s; --force = neu)
python -m bench.run_benchmark                # alles: beide Tools, alle Aufgaben, Sweep 1.0/0.5/0.25 mm
python -m bench.run_benchmark --tools brep --tasks B01,B02,B03
python -m bench.run_benchmark --tools voxel --tasks B07 --voxel-sizes 2,1,0.5,0.25
python -m bench.report bench/results/<run_id>   # Report eines Laufs neu erzeugen
```

Optionen von `run_benchmark`:

| Option | Bedeutung |
|---|---|
| `--tools brep,voxel` | welche Werkzeuge |
| `--tasks B01,B02,...\|all` | Aufgaben (`all` = B01-B10, V01-V04, R01-R04). Das Tool antwortet bei Nichtkoennen selbst mit `unsupported` |
| `--voxel-sizes 1.0,0.5,0.25` | Sweep fuer B07 (mm) |
| `--voxel-default X` | Voxelgroesse fuer alle uebrigen Voxel-Aufgaben (sonst Tool-Standard) |
| `--run-id ID` | Ordnername unter `bench/results/` (Standard: Zeitstempel) |
| `--spec PFAD` | Spec (Standard `spec/boreas_spec.json`) |
| `--timeout S` | Sekunden je Tool-Aufruf (Standard 1800) |
| `--repeats N` | Wiederholungen fuer B10 (Standard 3, jeweils frischer Prozess) |
| `--tool-cmd NAME="CMD"` | Kommando eines Tools ueberschreiben (z. B. Attrappe, oder anderer Interpreter). `--spec/--task/--out/--set/--voxel` werden angehaengt. Solche Laeufe erhalten das Praefix `fake_` und aktualisieren `latest` **nicht** (ausser `--update-latest`) |
| `--no-latest`, `--no-report` | Kopie nach `latest` bzw. Report unterdruecken |

Fehlt ein Werkzeug (kein `brep/cli.py`, kein `voxel/*.csproj`, kein `dotnet`, fehlgeschlagener Build), wird jede Aufgabe mit
`status: "not_run"` und Grund in `result.json` festgehalten; der Lauf geht weiter. `dotnet` wird ueber den PATH gesucht,
Rueckfall `C:\Program Files\dotnet\dotnet.exe`. Voxel wird einmal vorab mit `dotnet build voxel -c Release` gebaut
(Log in `run_meta.json`/`build_voxel.*.log`), die Messlaeufe nutzen `dotnet run ... --no-build`, damit die Compile-Zeit nicht
in der Laufzeit steckt.

## Was gemessen wird

**Pro Aufruf (Runner-Block)**: Wandzeit des Subprozesses (inkl. Start von Python/.NET), Spitzen-RAM, Exit-Code, Timeout,
vollstaendige Kommandozeile, `stdout.log`/`stderr.log`. RAM = `PeakWorkingSetSize` (Windows, ctypes) ueber den ganzen
Prozessbaum (Wurzel exakt, Kinder wie das App-Prozess unter `dotnet run` alle 0.1 s abgefragt), Wert = Maximum ueber die Prozesse.
Die Tool-eigenen Angaben (`runtime_s`, `peak_mem_mb`) bleiben daneben stehen.

**Werkzeugneutral aus den STL-Dateien** (`bench/metrics.py`, Block `neutral_metrics`):

| Kennzahl | Methode |
|---|---|
| Dreiecke, Dateigroesse | Zaehlung |
| Wasserdicht, offene Kanten, nicht-mannigfaltige Kanten, inkonsistente Orientierung, Komponenten, Euler-Zahl | Vertices auf 1e-3 mm verschweisst; Kantenzaehlung |
| Volumen, Schwerpunkt, Traegheitstensor (Dichte 1, mm^5, um den Schwerpunkt) | Summe ueber Tetraeder (Ursprung, Dreieck); Volumen nur bei wasserdichtem Mesh belastbar (`volume_reliable`) |
| Oberflaeche, BBox | direkt |
| Abweichung zweier Meshes | 200k flaechengewichtete Zufallspunkte je Richtung; kNN in dichter Punktwolke, danach exakter Punkt-zu-Dreieck-Abstand der 6 Kandidaten. Ausgabe je Richtung Mittel/RMS/p50/p95/p99/Max, dazu symmetrisch und Hausdorff-Naeherung |
| Stirnflaeche Z (Draufsicht) und X (Frontansicht) | Projektion in ein Raster (max. 3000 px lange Seite), Aufloesung `pixel_mm` steht dabei. Selbsttest: Kugel/Quader/Zylinder < 0.1 % Fehler |
| Selbstauskunft-Check | Vergleich Volumen/Flaeche/BBox aus `result.json` mit der neutralen Rechnung |

Der Selbsttest (`python -m bench.test_metrics`, Ergebnis in `bench/results/metrics_selftest.json`) vergleicht Quader, Kugel,
Zylinder (mit build123d erzeugt, als STL exportiert) mit analytischen Werten, prueft die Fehlererkennung
(offenes Mesh, nicht-mannigfaltige Kante, zwei Komponenten, ASCII-STL) und die ICP.

## Referenz (STEP) und Ausrichtung

`python -m bench.reference` tessellier die vier Schalen aus `Mohammed_0.1 Full Shell.step` (ganze Schale, lin. Toleranz 0.05 mm;
Flaechen ohne Netz werden uebersprungen und als Abdeckung gemeldet: Unterteil 99.99999 % der Flaeche, alle anderen 100 %) und
legt sie im **PLAN.md-Koordinatensystem** ab (`bench/reference/`):

`upper.stl` (Shell 3), `lower.stl` (Shell 0), `nose.stl` (Shell 1+2), `nose_cap.stl`, `nose_insert.stl`, `full.stl` (alle vier),
`reference_transform.json` (Offset + Dateibeschreibung), `reference_meta.json` (Abdeckung, exakte OCC-Kennwerte, Mesh-Metriken).

Offset (Datei -> Modell, nur Translation): Achse X/Y = Kreisfit-Mittel ueber Schichten von Nasenkappe und Oberteil-Rohr
(679.701 / 23.163 mm, Streuung 0.13 mm), Trennebene Z = kleinste Z-Koordinate des Oberteils (1302.905 mm).
Die Nase liegt in der Referenz rund 82 mm ueber dem Oberteil (Explosionsdarstellung), nicht in Sitzposition.

Die Referenz-Netze sind Schalen aus einzelnen Flaechen mit offenen Kanten (keine wasserdichten Volumen). Fuer Abweichungen ist
das egal, fuer Volumen nicht; dort gelten die OCC-Werte in `reference_meta.json` (Unterteil 95'426 mm^3 gueltig; Oberteil ~405'549 mm^3,
Solid von OCC als ungueltig markiert; Nase offene Schale).

Vergleich mit der Referenz (B01, B02 und der B07-Sweep, Teile `upper`/`lower`/`nose`): (1) Abweichung nur mit Offset, (2) nach
optionaler getrimmter Punkt-zu-Ebene-ICP (starr, 90 % beste Punkte) mit ausgewiesener Resttransformation (Drehung in Grad,
Verschiebung in mm). Liegt der Schwerpunkt mehr als 5 mm daneben (z. B. Nase), wird vor der ICP um diesen Abstand vorverschoben
(`pre_translation_mm`).

## Sonderlaeufe

- **B03 Gruppen-Variation**: liest die Spec, aendert je Gruppe den ersten numerischen Parameter auf den Mittelwert von min/max
  (auf `step` gerundet) und ruft `--task B03 --set gruppe.param=wert` auf; Baseline = `--task B03` ohne `--set`. Verglichen werden
  die Teil-STL gegen die Baseline (geaendert = Hausdorff-Naeherung > 0.02 mm oder Volumen > 1e-4 relativ). Ausgabe je Gruppe:
  Regenerationszeit, geaenderte Teile, erwartete Teile (Annahme in `EXPECTED_PARTS`, Skelett darf alles), unerwartete Aenderungen
  -> `independent`. Ordner: `B03/<tool>/baseline`, `B03/<tool>/var_<gruppe>`.
- **B07 Voxel-Sweep**: Voxel-Tool je Groesse aus `--voxel-sizes` unter `B07/voxel/sweep/v<groesse>/`; je Groesse Zeit, RAM,
  Dreiecke, Volumen-/Flaechenfehler und Abweichung gegen das B-rep-Modell desselben Laufs (`vs_brep`, Fallback `latest`) sowie
  gegen die STEP-Referenz. B-rep laeuft einmal. Die Tool-Standardgroesse liegt in `B07/voxel/result.json`.
- **B10**: `--repeats` Aufrufe in frischen Prozessen (1. = kalt), Median/Min/Max in `runner.repeats`.

## Ergebnis-Ablage

```
bench/results/<run_id>/
  run_meta.json            Argumente, Rechner, Verfuegbarkeit der Tools, Referenz-Ausrichtung, Voxel-Build
  summary.md / summary.json / charts/*.png      (Report)
  <task>/<tool>/result.json    Tool-Ergebnis (unveraendert in result_raw.json) + neutral_metrics + runner
  <task>/<tool>/*.stl, stdout.log, stderr.log
bench/results/latest/       Kopie des letzten echten Laufs
```

`result.json` = Ergebnis des Tools laut PLAN.md, erweitert um

- `runner`: `status` (ok / exit_nonzero / timeout / not_run), `wall_s`, `peak_ram_mb`, `exit_code`, `cmd`, Logs, bei B10 `repeats`.
- `neutral_metrics`: `mesh`, `parts.<name>`, `self_report_check`, `reference_deviation.<teil>.{offset_only,icp,after_icp}`, ggf. `frame_warning`.

## Report lesen

`summary.md` enthaelt: Werkzeug-Verfuegbarkeit, Referenz-Ausrichtung, Diagramme, **Gewinner je Aufgabe mit Zahlen**, Tabellen je
Abschnitt (gemeinsam / nur B-rep / nur Voxel), Abweichung zur Referenz je Teil, B03-, B07-Tabellen, Stirnflaechen, API-Kennzahlen,
Grenzen der Messung. Gewinnregel: Genauigkeit oder Vollstaendigkeit (3 Punkte) vor Wandzeit (2) vor RAM, Dateigroesse,
Wasserdichtheit (je 1-2); Unterschiede unter 5-10 % gelten als gleichauf; kann nur ein Tool die Aufgabe, gewinnt es mit Vermerk.
Die Regel bewertet nur Zahlen, nicht Bedienbarkeit; A01-A05 stehen in `spec/feature_matrix.json`.
Diagramme: Laufzeit, RAM, Dateigroesse je Aufgabe, B07-Sweep (Abweichung, Massenfehler, Zeit, RAM gegen Voxelgroesse), B03-Regenerationszeit.
Farben: B-rep blau, Voxel orange, in allen Diagrammen.

## Bekannte Grenzen

- RAM-Spitzen unter 0.1 s in Kindprozessen koennen fehlen; Wurzelprozess ist exakt.
- Nicht wasserdichte Meshes (Voxel-Tool oder B-rep-Tessellation) verfaelschen Volumen/Traegheit; das steht in `volume_reliable`.
- `bench/_fake_tool.py` + `bench/_fake_spec.json` sind eine **Attrappe** (altes Oberteil, Voxel-Simulation durch Gitterrundung) nur fuer
  den Pipeline-Test: `python -m bench.run_benchmark --spec bench/_fake_spec.json --tool-cmd brep="python -m bench._fake_tool --mode brep" --tool-cmd voxel="python -m bench._fake_tool --mode voxel"`.
  Ergebnisse solcher Laeufe (`fake_*`) sind keine Benchmark-Ergebnisse.
- `bench/reference/` ist ca. 36 MB gross (STL) und laesst sich jederzeit mit `python -m bench.reference --force` neu erzeugen.
