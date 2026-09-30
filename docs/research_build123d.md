# Recherche: build123d

Stand: 30.09.2026. "Lokal gemessen" heisst: mit der installierten Version (build123d 0.13.0, cadquery-ocp-novtk 8.0.1.0.0, Python 3.12, Windows 11, i7-13700HX, 32 GB RAM) und der Referenzdatei `Mohammed_0.1 Full Shell.step` (5.6 MB) am 30.09.2026 ausgeführt. Einzelmessungen, keine Statistik.

## 1. Kurzprofil

| Punkt | Befund | Quelle |
|---|---|---|
| Was | Python-Bibliothek für parametrisches B-rep-CAD, "A python CAD programming library" | https://pypi.org/project/build123d/ |
| Kernel | Open CASCADE Technology (OCCT) über die Bindings `cadquery-ocp` (OCP). 0.13.0 nutzt OCP **8.0.1** | Release-Notes v0.13.0 https://github.com/gumyr/build123d/releases |
| Version | **0.13.0** vom 21.09.2026 (0.12.0 vom 18.09.2026, 0.11.x Juni/Juli 2026, 0.10.0 vom 05.11.2025, 0.9.0 vom 04.02.2025). Noch 0.x, also kein API-Stabilitätsversprechen | PyPI-Releasedaten |
| Lizenz | Apache-2.0. OCCT selbst LGPL 2.1 mit Ausnahme (nicht neu geprüft), für Nutzung als Bibliothek unkritisch | PyPI, GitHub |
| Python | 3.11 bis 3.14 | PyPI `requires_python` |
| Plattform | Reines Python plus binäre OCP-Wheels: Windows, Linux, macOS (x64 und arm64). Für Linux-aarch64 gibt es `py-lib3mf` als Ersatz | PyPI `requires_dist` |
| Community | GitHub 3'236 Sterne, 290 Forks, 87 Contributors (Hauptautor gumyr 1'805 Commits, danach jdegenstein 549, bernhard-42 287), letzter Push 29.09.2026. PyPI rund 609'500 Downloads in 30 Tagen (pypistats, 30.09.2026). Zum Vergleich CadQuery: 5'857 Sterne, rund 1.18 Mio. Downloads pro Monat | GitHub-API, pypistats |
| Issues | 313 offen (Issues plus PRs), davon 51 mit Label "bug". Aktuell offen: Sweep mit Binormal liefert mit 0.13.0/OCCT 8.0.1 ungültige Körper (#1474, 25.09.2026, reproduzierbar auch in FreeCAD-Nightly mit OCCT 8.0.1) | https://github.com/gumyr/build123d/issues |

## 2. Kernel und Darstellung (B-rep)

- Körper sind **Grenzflächenmodelle**: Solid, Shell, Face, Wire, Edge, Vertex mit exakter Geometrie (Ebene, Zylinder, Torus, B-Spline/NURBS). In der Referenz-Datei lokal gezählt: 447 Flächen (207 B-Spline, 157 Ebene, 69 Zylinder, 14 Torus), 1'322 Kanten.
- Zwei Schreibweisen: **Builder-Modus** (`with BuildPart() as p:`) und **Algebra-Modus** (`a + b - c`, `Pos(...) * Box(...)`). Beide sind dokumentiert.
- Zusätzlich vorhanden: `Airfoil` (NACA-4-stellig, `objects_curve.py`, lokal geprüft: `Airfoil("2412")` liefert Kurve in 4 ms), Gordon-Flächen (`make_gordon_surface`, Tutorial "Spitfire Wing"), `Helix`, Text, Joints, `Draft`, `pack`, `persistence`.
- Neu in 0.13.0 enthalten und interessant für Reverse-Engineering: `brep_from_stl.detect_primitives` (Modul vom 08.04.2026): rekonstruiert **näherungsweise** Ebenen, Zylinder und Kugeln aus einem STL-Netz und erzeugt build123d-Code dazu. Experimentell.

## 3. Kernfähigkeiten (aus Doku und lokaler Prüfung)

| Bereich | Umfang |
|---|---|
| Skizzen, Profile | `BuildLine`, `BuildSketch`, Kurven (Spline, Bézier, Ellipse, Tangentenbögen), Boolean auf Skizzen, Constraints-Tutorial |
| Körper | `extrude`, `revolve`, `loft`, `sweep` (mehrfach-Schnitt, Binormal), `thicken`, `offset` (Shell mit Öffnungen), `fillet`, `chamfer`, `draft`, `split`, `section`, `project` |
| Selektoren | `edges()`, `faces()`, `.filter_by(GeomType.LINE)`, `.sort_by(Axis.Z)`, `.group_by(...)`, `ShapeList`-Operatoren |
| Baugruppen | `RigidJoint`, `RevoluteJoint`, `LinearJoint`, `CylindricalJoint`, `BallJoint`, `Compound` mit Labels und Farben |
| Booleans | `+`, `-`, `&`, `fuse`, `cut`, `intersect`, `clean()`, `fix()`, `is_valid` |
| Masse | `volume`, `area`, `center(CenterOf.MASS)`, `mass` (mit Dichte), `matrix_of_inertia`, `static_moments`, `bounding_box()` |
| Zeichnungen | `TechnicalDrawing` (A-Formate, Rahmen, Schriftfeld), `DimensionLine`, `ExtensionLine`, `Draft`-Objekte, Projektion mit sichtbaren/verdeckten Kanten (`Compound.project_to_viewport`), Export `ExportDXF` und `ExportSVG` |

Lattices, TPMS/Gyroid, Voxel oder Signed-Distance-Felder: **nicht vorhanden** (0 Treffer für lattice, gyroid, TPMS, voxel, sdf in der gesamten Doku `llms-full.txt`, geprüft 30.09.2026). Gitter wären eine Vereinigung vieler Zylinder (Boolean-Kosten) oder ein externes Netz.

## 4. Formate

| Format | Import | Export | Bemerkung |
|---|---|---|---|
| STEP | `import_step` | `export_step` | Farben, Labels; Lokal: Import 5.3 s (5.6 MB, 447 Flächen); Re-Export 0.62 s, **12.8 MB** (grösser als das Original) |
| BREP (OCC nativ) | `import_brep` | `export_brep` | |
| STL | `import_stl` (liefert **eine Face-Hülle aus Dreiecken**, keinen Solid; lokal: 1 Face, `is_valid=False`) und `Mesher.read` | `export_stl` (Toleranz, Winkeltoleranz; lokal 0.18 s, 3.6 MB bei 0.05 mm/0.2 rad) | Netz → echter Solid ist nicht automatisch möglich |
| 3MF | `Mesher.read` | `Mesher.add_shape` plus `write` | **Lokal fehlgeschlagen** auf dem importierten Körper: `AttributeError: 'NoneType' object has no attribute 'NbNodes'` (eine Fläche mit leerer Triangulation, Warnung "1 face has been skipped"), auch mit gröberer Abweichung 0.1/0.2/0.5 mm. Bei einem einfachen Quader funktioniert 3MF (0.02 s) |
| glTF, OBJ | - | `export_gltf`, `export_obj` | |
| DXF, SVG | `import_dxf`, `import_svg` | `ExportDXF`, `ExportSVG` | Layer, Linientypen, Massketten |
| Vorschau | `ocp_vscode` (Extra `build123d[ocp_vscode]`), Jupyter | | |
| PCB-Bestellformat | | `export_to_pcbway` | nebensächlich |

Nicht vorhanden: VDB, CLI-Slices, Skalar/Vektorfelder, GD&T/PMI (0 Treffer in der Doku).

## 5. Ausrundungen, Offsets, Schalen, Booleans (Robustheit)

Lokal an der Referenz (Unterteil, gültiger Solid, 95'426 mm³, 56'222 mm²):

| Test | Ergebnis |
|---|---|
| Boolean Schnitt mit Quader | 0.38 s, gültig |
| Boolean Differenz mit Zylinder | 0.73 s, gültig (Volumendrift bei nicht schneidendem Zylinder: +0.4 mm³, also rund 5 ppm Rauschen der Volumenintegration) |
| `offset(amount=±1.0 ... ±3.0, kind=ARC oder INTERSECTION)` auf dem ganzen Körper | **schlägt in allen 8 Fällen fehl** (Fehlermeldung "offset Error, an alternative kind may resolve this error"), `Kind.TANGENT` nicht unterstützt. Ein Quader wird dagegen korrekt geschält (Volumen 512 exakt). |
| Verrunden von 1, 3, 10 geraden Kanten mit r = 0.3 mm | schlägt fehl ("Failed creating a fillet ... try a smaller value") |
| `thicken` auf 10 B-Spline-Flächen mit 1 mm | nur 2 von 10 ergeben gültige Körper |
| Ganzer STEP | 4 Shells: nur eine (Unterteil) ist ein gültiger Solid. Aus den 3 anderen (Volumen 159'853 / 30'207 / 405'549 mm³ als Solid berechnet) entsteht kein gültiger Solid (`is_valid=False`, auch nicht mit `ShapeFix_Solid`). **Abweichung von PLAN.md ("4 geschlossene Körper")**: vor Volumen-/Boolean-Vergleichen Hüllen prüfen und ggf. reparieren |

Einordnung: OCCT-Offsets und -Fillets sind auf freien B-Spline-Flächen (wie hier vom Shapr3D-Export) bekannt heikel. Für ein **eigenes** parametrisches Modell aus sauberen Profilen ist das erfahrungsgemäss weniger kritisch (Hypothese für B05/B06, der Benchmark muss das messen). Für die importierte Referenz ist das Ergebnis "Offset und Fillet auf Freiformkörper: nicht robust" ein belegter Punkt.

## 6. Genauigkeit, Performance, Speicher

- **Genauigkeit**: exakte Geometrie, Modelltoleranz 1e-7 mm im Kernel; Netzexport mit wählbarer Abweichung. Volumen/Fläche/Trägheit exakt bis auf Integrationsrauschen (Einzelmessung: 5 ppm).
- **Zeit** ist von der **Zahl und Art der Flächen** abhängig, nicht von der Bauteilgrösse. Einfache Booleans Sekundenbruchteile, komplexe B-Spline-Körper Sekunden bis Minuten.
- **Speicher**: klein (Bauteil im MB-Bereich), Skalierung nach Flächenzahl.
- **Parallelität**: Skripte laufen als eigene Prozesse trivial parallel (kein globaler Zustand ausser dem Prozess).

## 7. API, Headless, Automation

- Reines Python-Skript: `python script.py` oder `python -m paket`. Kein Fenster nötig. Kein Lizenzserver.
- `pip install build123d` (Extras: `ocp_vscode`, `stubs`, `docs`, `development`, `all`). Abhängigkeiten u. a. numpy, scipy, scikit-learn, sympy, ezdxf, lib3mf, svgpathtools, ocpsvg, ocp_gordon.
- Typhinweise: `py.typed` liegt im Paket (lokal geprüft), Stubs für OCP über Extra `stubs`.
- Aufgaben aus diesem Projekt (Demo `tour.py`, `pipeline.py`) laufen bereits headless.

## 8. Eignung für KI-Agents (A03, Einschätzung)

| Aspekt | Befund | Wirkung |
|---|---|---|
| Doku-Zugang | Offizielles **`llms.txt`** und **`llms-full.txt`** (591 KB, rund 150'000 Token geschätzt) unter https://build123d.readthedocs.io/en/latest/llms.txt (HTTP 200, 30.09.2026). Doku-Build erzeugt sie mit `sphinx-llms-txt` | stark positiv |
| Trainingsdaten | Viel öffentlicher Code, vergleichbar mit CadQuery (Vorgänger-Idee), viele Beispiele, Doku mit Tutorials, GitHub Discussions | positiv |
| Selbstanwendung | Das Projekt entwickelt selbst mit KI-Unterstützung (Datei `brep_from_stl.py` nennt "gumyr with codex gpt-5.4") | Indiz |
| Typisierung | `py.typed`, aussagekräftige Enums (`GeomType`, `Kind`, `Align`) | positiv |
| Fehlermeldungen | Meist verständlich ("Failed creating a fillet with radius of 0.3, try a smaller value or use max_fillet"), aber OCCT-Fehler wie "offset Error, an alternative kind may resolve this error" sind wenig konkret | mittel |
| API-Drift | Kein 1.0. 0.10.0 änderte Methoden zu Properties (`is_valid()` wird `is_valid`), 0.12.0 entfernte deprecated APIs, 0.11.0 wechselte auf `cadquery-ocp-novtk`. Agents mit altem Wissen erzeugen dadurch Fehler | negativ |
| Iteration | Sekundenschnelle Läufe, Ausnahme mit Stack-Trace, Ergebnis über `is_valid`, `volume`, Bounding Box prüfbar | positiv |

## 9. Bekannte Einschränkungen

1. Keine Gitter/TPMS/Voxel/SDF, keine variablen (feldbasierten) Wandstärken.
2. Offsets/Schalen/Fillets auf komplexen Freiformflächen können fehlschlagen (lokal belegt an der Referenz).
3. STL/3MF-Import erzeugt nur Dreiecksschalen; Solid-Erzeugung nicht robust. 3MF-Export scheiterte lokal an einer Fläche ohne Triangulation.
4. Booleans auf tangentialen oder deckungsgleichen Flächen können fehlschlagen oder ungültige Körper liefern (offene Issues #1363, #1428 u. a.).
5. Version 0.x mit Breaking Changes bei Minor-Releases, OCCT-8-Regressionen (#1474).
6. Keine GD&T/PMI-Annotationen im STEP, keine Toleranz-Ketten.
7. Keine eingebaute Strömungs- oder FEM-Funktion (Demo verwendet eigene Vereinfachungen).

## Quellen

- https://github.com/gumyr/build123d (Repo, Issues, Releases via API)
- https://build123d.readthedocs.io/en/latest/ , https://build123d.readthedocs.io/en/latest/llms.txt , https://build123d.readthedocs.io/en/latest/llms-full.txt
- https://pypi.org/project/build123d/ , https://pypistats.org/packages/build123d
- https://github.com/gumyr/build123d/issues/1474
- https://github.com/CadQuery/cadquery
- Lokale Messungen: `C:\Users\Aeolos-04\AppData\Local\Programs\Python\Python312\python.exe`, build123d 0.13.0
