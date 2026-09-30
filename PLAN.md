# Boreas CAD-Benchmark: B-rep (build123d) vs. Voxel (PicoGK)

Stand: 30.09.2026. Dieses Dokument ist der **gemeinsame Vertrag** für alle parallel arbeitenden Agents.
Wer eine Schnittstelle hier ändern will, meldet das zurück, statt sie eigenmächtig zu ändern.

## Ziele (vom Projekt vorgegeben)

1. Funktionsvergleich der beiden Programme
2. Limitierungen: was kann/hat/macht die eine besser als die andere (inkl. der Demo-Features wie technische Zeichnung)
3. B-rep vs. Voxel grundsätzlich, mit Fokus auf komplexe Geometrie, Aerodynamik und Kühlluftführung
4. API-Verfügbarkeit: Automatisierung per Code und Programmierung mit KI-Agents
5. Eignung für eine Design-Automation-Pipeline

## Referenzgeometrie

`Mohammed_0.1 Full Shell.step` (Shapr3D-Export, Freihand, nicht constrained): 4 geschlossene Körper.

| Shell | Teil | Z-Bereich (Datei-KS) | Inhalt |
|---|---|---|---|
| 0 | **Unterteil** | 1171.5 – 1305.5 | konischer Rumpf, 4 Arme, 4 schräge Aero-Fins entlang des Rumpfs zu den Armen/Motoren (Tropfenprofil), 4 Heckflossen unten |
| 3 | **Oberteil** | 1302.9 – 1420.0 | Rohr, 4 Arme mit Knotenblechen, 4 tropfenförmige Motorgondeln |
| 1 | Nasenkappe | 1502.0 – 1602.7 | Ogive |
| 2 | Nasenkappen-Einsatz | 1546.3 – 1596.2 | Einsatz in der Nase |

Das alte `boreas_upper.py` bildet nur das Oberteil + Nase ab. Neu kommen **Unterteil** und die **Aero-Formen 1:1** dazu
(Tropfenprofil der Fins und Gondeln bleibt so, wie es im STEP ist).

## Ordnerstruktur und Zuständigkeiten

```
spec/boreas_spec.json      Parameter-Gruppen (Single Source of Truth)      → Agent B-rep
spec/feature_matrix.json   Feature × {brep, voxel} mit Status und Beleg     → Agent Recherche
spec/benchmark_tasks.json  Benchmark-Aufgaben (IDs siehe unten)             → Agent Recherche
brep/                      build123d-Modell + CLI                           → Agent B-rep
voxel/                     PicoGK (C#/.NET 9) Modell + CLI                  → Agent Voxel (startet nach .NET-Installation)
bench/                     Benchmark-Runner, Metriken, Ergebnisse           → Agent Benchmark
gui/ + app.py              neuer Modus „④ Vergleich“                        → Agent GUI
docs/                      Recherche, Geometrie-Analyse, Findings           → jeweiliger Agent
presentation/              Storyline und Folieninhalte für Laien            → Agent Präsentation
```

Bestehende Dateien (`boreas_upper.py`, `tour.py`, `pipeline.py`, …) bleiben funktionsfähig; die alten Modi ①–③ bleiben.
Kein Agent committet; die Integration und die Commits übernimmt die Koordination.

## Koordinatensystem

mm, Z nach oben (Nase = +Z). Ursprung auf der Rumpfachse in der **Trennebene Oberteil/Unterteil**.
Arme bei `arm_angle_offset + i·360/arm_count` (Referenz: 45°).

## Parameter-Gruppen (Skelett-Methode)

Ziel der Pipeline: pro Durchlauf **nur eine Gruppe** ändern, der Rest bleibt stabil.
Deshalb gilt die Skelett-Methode (Top-down-Design):

- Die Gruppe **`skeleton`** enthält nur die Schnittstellenmasse, die mehrere Teile gemeinsam nutzen
  (Anzahl/Winkel der Arme, Motorposition, Lage der Trennebene, Rumpfradius an der Trennebene, Nasen-Anschluss).
- Jede andere Gruppe darf **nur ihre eigenen Parameter + `skeleton`** lesen, nie Parameter einer anderen Gruppe.
- Abgeleitete Masse (z. B. Laschenbreite aus Schlitzbreite − 2·Spiel) werden im Code berechnet, sind keine freien Parameter.
- Test-Pflicht: Ändert man einen Parameter einer Nicht-Skelett-Gruppe, ändert sich nur die Geometrie dieser Gruppe
  (Geometrie-Hash der übrigen Features bleibt gleich).

Gruppen (Schlüssel verbindlich, Parameterliste legt Agent B-rep anhand der Messung fest):

| Schlüssel | Anzeige | Inhalt |
|---|---|---|
| `skeleton` | Skelett (Master) | arm_count, arm_angle_offset, motor_radius, split_z, joint_radius, nose_joint_z |
| `upper_body` | Oberteil-Rumpf | Rohrhöhe, Wand, Rohrform |
| `arms` | Ausleger | Breite, Stärke, Knotenbleche, Erleichterungen |
| `motor_pods` | Motorgondeln | Tropfenform der Gondeln (Radius, Höhe, Spitzen-Verhältnis), Wand, Kabelloch |
| `lower_body` | Unterteil-Rumpf | Länge, Endradius, Verjüngung, Wand |
| `body_fins` | Aero-Fins (Rumpf → Motor) | Tropfenprofil (Sehne, Dicke, Lage der max. Dicke), Pfeilung, Neigung |
| `tail_fins` | Heckflossen | Spannweite, Sehne, Dicke, Profil |
| `nose` | Nasenkappe | Länge, Form-Exponent, Einsatz |
| `joints` | Steckverbindungen | Schlitz/Lasche, Passungsspiel (Oberteil↔Unterteil, Nase↔Oberteil) |
| `details` | Detail/Fertigung | Verrundungen, Gravur, Mindestwandstärke |

Format `spec/boreas_spec.json`:

```json
{
  "meta": {"units": "mm", "reference": "Mohammed_0.1 Full Shell.step", "version": 1},
  "groups": {
    "skeleton": {
      "label": "Skelett (Master)", "description": "…",
      "params": {
        "arm_count": {"value": 4, "min": 3, "max": 8, "step": 1, "unit": "", "label": "Anzahl Arme", "description": "…"}
      }
    }
  }
}
```

Überschreiben von aussen immer als `gruppe.parameter=wert`, z. B. `--set body_fins.chord=40`.

## Benchmark-Aufgaben (IDs verbindlich)

Gemeinsam (beide Tools lösen dieselbe Aufgabe, Ergebnisse nebeneinander):

| ID | Aufgabe |
|---|---|
| B01 | Referenz importieren und mit eigenem Modell abgleichen (B-rep: STEP nativ, Voxel: nur über Mesh) |
| B02 | Parametrisches Gesamtmodell (Oberteil, Unterteil, Nase) aus der Spec aufbauen |
| B03 | Gruppen-Variation: je Gruppe ein Parameter geändert → Regenerationszeit, nur betroffenes Teil ändert sich |
| B04 | Tropfenprofil: Aero-Fins und Motorgondeln |
| B05 | Wandstärke / Schale (Shell vs. Offset) |
| B06 | Übergänge / Verrundungen (Kanten-Fillet vs. Voxel-Glättung) |
| B07 | Masseneigenschaften + Genauigkeit in Abhängigkeit der Voxelgrösse |
| B08 | Mesh-Export für 3D-Druck (STL/3MF) + Druckbarkeits-Check |
| B09 | Aero-Vorbereitung: Stirnfläche, benetzte Fläche, Strömungsdomäne für CFD |
| B10 | Performance und Skalierung: Laufzeit, RAM, Dateigrösse |

Nur bzw. klar besser in Voxel: `V01` Gitter-Infill (Lattice), `V02` konforme Kühlluftkanäle durch den Rumpf,
`V03` robuste Booleans auf Mesh/Scan-Daten und feldbasierte (variable) Wandstärken, `V04` Slices für den Druck.

Nur bzw. klar besser in B-rep: `R01` bemasste technische Zeichnung, `R02` exakter STEP-Export und Kanten/Flächen-Selektoren,
`R03` Constraints, Skelett, Baugruppen-Joints, URDF, `R04` exakte Masse, Toleranzen und Passungen.

Nicht-geometrische Kriterien (Recherche + Messung): `A01` API und Sprache, `A02` Headless/CLI-Betrieb,
`A03` Eignung für KI-Agents (Doku, Fehlermeldungen, Codezeilen pro Aufgabe), `A04` Pipeline-Integration,
`A05` Lizenz, Plattform, Reife und Community.

Tut ein Tool eine Aufgabe nicht, liefert es trotzdem ein Ergebnis mit `status: "unsupported"` und Begründung.
Das ist ausdrücklich ein Ergebnis, kein Fehler.

## CLI-Vertrag (beide Tools identisch)

```
python -m brep.cli  --spec spec/boreas_spec.json --task B02 --out <dir> [--set gruppe.param=wert ...]
dotnet run --project voxel -c Release -- --spec spec/boreas_spec.json --task B02 --out <dir> [--set ...] [--voxel 0.25]
```

Jeder Aufruf schreibt `<dir>/result.json` und die Dateien, auf die es verweist:

```json
{
  "task": "B02", "tool": "brep", "tool_version": "build123d 0.13.0",
  "status": "ok | partial | unsupported | failed",
  "runtime_s": 1.23, "peak_mem_mb": 410,
  "params": {"voxel_size_mm": null, "overrides": {"body_fins.chord": 40}},
  "metrics": {
    "volume_mm3": 0, "area_mm2": 0, "mass_g": 0, "bbox_mm": [0, 0, 0, 0, 0, 0],
    "parts": {"upper": {"volume_mm3": 0}, "lower": {}, "nose": {}}
  },
  "files": {"mesh": "model.stl", "parts": {"upper": "upper.stl"}, "step": "model.step", "image": "preview.png"},
  "code_loc": 120,
  "notes": "Freitext: was ging gut, was nicht"
}
```

Pfade in `files` sind relativ zu `<dir>`. Meshes immer als binäres STL (Viewer lädt STL), zusätzliche Formate optional.
Ergebnisablage des Runners: `bench/results/<run_id>/<task>/<tool>/`, plus `bench/results/latest` als Kopie des letzten Laufs.

## Wellen

1. **Jetzt, parallel:** B-rep-Modell + Spec, Recherche + Feature-Matrix, GUI-Vergleichsmodus (mit Mock-Ergebnissen),
   Benchmark-Runner (B-rep-Seite zuerst), Präsentations-Storyline.
2. **Nach .NET-Installation:** PicoGK-Implementierung derselben Spec + Voxel-Spezialaufgaben.
3. **Integration:** echter Benchmark-Lauf, GUI mit echten Daten, Findings, Präsentation mit Ergebnissen.

## Entscheidungen (30.09.2026)

- Alle Material-, Motor- und Anforderungswerte bleiben **Mock-Daten** (Demo).
- .NET 9 SDK 9.0.318 ist installiert (`C:\Program Files\dotnet\dotnet.exe`, eventuell noch nicht im PATH der Shell).
- Präsentation: .pptx auf Basis der Vorlage `C:\Users\Aeolos-04\Downloads\Sprint_0_Review_Final.pptx`.
- Selbsttests: `bench/results/brep_selftest/` und `bench/results/voxel_selftest/`.
- Referenz-STLs (im Modell-Koordinatensystem): `bench/reference/{upper,lower,nose,nose_insert,full}.stl`.

## Stand (30.09.2026, abgeschlossen)

- B-rep-Modell `brep/` und Voxel-Modell `voxel/` aus derselben Spec; alle 18 Aufgaben laufen in beiden Werkzeugen.
- Benchmark-Lauf `bench/results/run1` (= `latest`), Auswertung `summary.md`; Neubewertung ohne Neulauf: `python -m bench.reevaluate`.
- Gruppen-Unabhängigkeit: 10/10 Gruppen in beiden Werkzeugen; Min/Max-Test aller 81 Parameter (B-rep) bestanden.
- Befunde: `docs/befunde.md`. Präsentation: `presentation/Boreas_CAD_Benchmark_BRep_vs_Voxel.pptx` (27 Folien, Vorlage Sprint 0).
