# Boreas · build123d Demo

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
