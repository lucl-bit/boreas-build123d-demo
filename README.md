# Boreas · build123d Demo und CAD-Benchmark B-rep vs. Voxel

Demo, die zeigt, was man mit [build123d](https://github.com/gumyr/build123d) machen kann – am Beispiel des Boreas-Oberteils
(nachgebaut aus `Mohammed_0.1 Full Shell.step`).

## Starten

```bash
pip install -r requirements.txt
python app.py
```

Dann http://localhost:8123 öffnen (unter Windows geht auch ein Doppelklick auf `start_gui.bat`).

## Inhalt

- **① Feature-Tour** – 20 Schritte: STEP-Import, Skizzen, Bauhistorie, Loft/Sweep, Builder- vs. Algebra-Modus,
  Selektoren, Detail-Features, Joints, Parametrik, Varianten, Trägheit, Kollision, FEM, Aero, Flugdynamik,
  Optimierung, Fertigung, Exporte, URDF, Pipeline. Jeder Schritt zeigt den zugehörigen build123d-Code.
- **② Werkbank** – Parameter live verstellen, Constraints, Vergleich mit dem Original-STEP, Exporte, bemaßte Zeichnung.
- **③ Pipeline** – Anforderungen → CAD → Simulationen → Optimierung → Exporte → Report.
  Headless: `python pipeline.py --all` (Ergebnisse in `out/`).

## Dateien

| Datei | Inhalt |
|---|---|
| `boreas_upper.py` | Parametrisches Modell, Constraints, Auto-Auslegung, Export |
| `analysis.py` | Trägheit, Kollision, Balken-FEM, Aero, Flugdynamik, Fertigung, Optimierung, URDF |
| `drawing.py` | Bemaßte Werkstattzeichnung (2 × A3) |
| `tour.py` / `pipeline.py` | Tour-Schritte bzw. Pipeline-Stufen |
| `app.py` + `gui/` | Lokaler Webserver und Oberfläche |
| `mock_data.json` | Mock-Anforderungen, Materialien, Grenzwerte |

**Hinweis:** Alle Material-, Motor- und Aerowerte sind Mock-Daten, die Simulationen sind bewusst vereinfacht –
es geht um die Einbindung von build123d, nicht um belastbare Auslegungswerte.

## Benchmark B-rep (build123d) vs. Voxel (PicoGK)

Dasselbe Modell (Ober-, Unterteil, Nase) in beiden Werkzeugen, aus einer gemeinsamen Spezifikation, mit denselben
18 Aufgaben verglichen. Vertrag und Aufgaben-IDs: [PLAN.md](PLAN.md), Befunde: [docs/befunde.md](docs/befunde.md).

| Ordner | Inhalt |
|---|---|
| `spec/boreas_spec.json` | 81 Parameter in 10 Gruppen (Skelett-Methode: jede Gruppe liest nur sich + Skelett) |
| `docs/geometrie_definition.md` | Werkzeugneutrale Konstruktionsbeschreibung (Formeln je Gruppe) |
| `brep/` | build123d-Modell (`python -m brep.cli --task B02 --out out/b02`), Test `python -m brep.tests.test_groups` |
| `voxel/` | PicoGK-Modell, C#/.NET 9 (`dotnet run --project voxel -c Release -- --spec spec/boreas_spec.json --task B02 --out out/v02`) |
| `bench/` | Runner mit neutralen Messungen: `python -m bench.run_benchmark` → `bench/results/latest/` + `summary.md` |
| `gui/compare.js` | Modus „④ Vergleich“: beide Werkzeuge nebeneinander, Status je Aufgabe, Feature-Matrix |
| `presentation/` | Präsentation (`python presentation/make_content.py`, dann `presentation/build_deck.ps1`), Storyline, Glossar |

Voraussetzungen: Python mit `requirements.txt`, .NET 9 SDK (`winget install Microsoft.DotNet.SDK.9`), PicoGK kommt per NuGet.
Für die Präsentation wird PowerPoint (Windows) verwendet.
