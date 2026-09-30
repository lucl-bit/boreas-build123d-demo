# B-rep gegen Voxel: zwei Arten, einen Körper zu beschreiben

Stand: 30.09.2026. Für Laien und Ingenieure. Zahlen aus der Recherche (`research_build123d.md`, `research_picogk.md`) und lokalen Messungen an der Referenzgeometrie sind als solche gekennzeichnet; alles andere ist Abschätzung oder Hypothese, die der Benchmark bestätigen oder widerlegen soll.

## 1. Die Idee in drei Sätzen (für Laien)

- **B-rep** (Boundary Representation, "Hüllenmodell") beschreibt einen Körper wie eine Bauzeichnung: Wo ist welche Fläche, welche Kante, welcher Kreis mit welchem Radius. Ein Loch hat exakt 5.000 mm, weil es als Zylinder mit Radius 2.5 mm gespeichert ist. Vergleichbar mit einer **Vektorgrafik**.
- **Voxel** (bei PicoGK genauer: ein **Abstandsfeld**, englisch Signed Distance Field) beschreibt den Körper als Raster aus winzigen Würfeln und speichert für jeden Punkt in der Nähe der Oberfläche, wie weit er von ihr entfernt ist. Ein Loch ist dann "ein paar Würfel weniger". Vergleichbar mit einem **Pixelbild in 3D**.
- Beides hat seinen Platz. Die Vektorgrafik bleibt bei jeder Vergrösserung scharf und lässt sich vermassen. Das Pixelbild kann dafür Verläufe, Netze und Schwämme mühelos, wo eine Zeichnung an ihre Grenzen kommt.

## 2. Für Ingenieure: die beiden Modelle im Detail

### B-rep (build123d auf OpenCascade)

- Topologie (Solid, Shell, Face, Edge, Vertex) plus Geometrie (Ebene, Zylinder, Torus, B-Spline/NURBS). Kanten und Flächen sind **benennbar und selektierbar** ("alle Kanten am Rohrende").
- Operationen sind geometrisch exakt: Boolean, Fillet, Chamfer, Offset/Shell, Loft, Sweep. Sie sind aber **algorithmisch empfindlich**: Tangentiale oder deckungsgleiche Flächen, sehr enge Radien und freie B-Spline-Flächen können Fehler auslösen (lokal gemessen: Offset und Fillet auf dem importierten Freiform-Unterteil schlugen in allen Versuchen fehl, Boolean liefen sauber).
- Genauigkeit unabhängig von einer Auflösung (Modelltoleranz im Bereich 1e-7 mm). Masse, Schwerpunkt, Trägheit exakt (Rauschen der Volumenintegration lokal rund 5 ppm).
- Austausch: STEP (exakt, Flächen bleiben Flächen), daneben Netzformate (STL, 3MF), DXF/SVG für Zeichnungen.

### Voxel / Abstandsfeld (PicoGK auf OpenVDB)

- Gitter mit fester **Voxelgrösse** (z. B. 0.25 mm). Gespeichert wird nur ein Band um die Oberfläche (sparse).
- Operationen sind **Rechnen mit Abstandsfeldern**: Vereinigung = Minimum, Schnitt = Maximum, Differenz = Maximum mit negiertem Feld, Offset = Feld verschieben, Glätten = Offset hin und zurück. Deshalb gelingen Booleans praktisch immer (auch mit Netzen, die Löcher, Überlappungen oder Selbstdurchdringungen hätten, solange der Rand als geschlossen gilt).
- Beliebige Formeln sind Körper: eine Funktion `f(x,y,z)` (Gyroid, Wandstärke in Abhängigkeit vom Ort) lässt sich direkt "einrechnen".
- Genauigkeit begrenzt durch das Gitter: Merkmale kleiner als 2 bis 3 Voxel verschwinden oder verrunden, Kanten sind nie ganz scharf. **Mass ist ein Voxel-Mass**, nicht ein Konstruktionsmass.
- Austausch: Netz (STL binär), OpenVDB (Felder), CLI (Schichten für Metalldruck), Bilder. Kein STEP.

## 3. Gegenüberstellung

| Kriterium | B-rep | Voxel |
|---|---|---|
| Kernidee | Flächen und Kanten, exakt | Abstandsfeld auf Gitter |
| Genauigkeit | Modelltoleranz, unabhängig von Auflösung | etwa ein halbes Voxel, nie feiner als das Gitter |
| Scharfe Kanten, Passungen | ja | nein (leicht verrundet), Passung nur grösser als Voxel |
| Bemassung, Zeichnung | ja (DXF/SVG, Massketten) | nein |
| STEP-Austausch mit Zulieferern und Fertigung | ja, exakt | nein (nur Netz) |
| Selektoren, Feature-Bezug | ja | nein |
| Gitterstrukturen, Schwämme, TPMS | mühsam, langsam | native Stärke |
| Konforme Kanäle, Wärmetauscher | machbar für wenige Kanäle | Stärke, viele Kanäle unproblematisch |
| Organische Übergänge, Glätten | begrenzt, oft fehleranfällig | Stärke |
| Robustheit der Booleans | gut auf sauberem CAD, empfindlich bei Sonderfällen | sehr hoch, auch auf Netzen |
| Variable Wandstärke nach Feld | Umweg | direkt |
| Masse, Trägheit | exakt | Volumen ja, Rest selbst berechnen; Genauigkeit an Voxel gebunden |
| Speicher, Rechenzeit | wächst mit Flächenzahl | wächst mit Oberfläche/Voxelgrösse², fein aufgelöste grosse Teile teuer |
| Dateigrösse (lokal, Unterteil) | STEP Original 5.6 MB, von build123d neu geschrieben 12.8 MB; STL 3.6 MB | STL je nach Voxelgrösse; VDB sparse (Abschätzung unten) |
| Automation | Python, reif, Doku für KI | C#, kleines Team, Doku knapp |

Abschätzung Voxelgrösse (Rechnung, keine Messung): Das Unterteil hat 56'222 mm² Oberfläche (lokal gemessen). Bei 0.25 mm Voxel sind das rund 0.9 Mio. Oberflächenvoxel, mit einem Band von einigen Voxeln rund 5 Mio. Werte, also grob 20 MB unkomprimiert. Bei 0.1 mm rund das 6.25-Fache. Der Benchmark B07/B10 misst das.

## 4. Warum Voxel bei Gittern, Kanälen, Organischem so stark ist

1. **Keine Topologie, die brechen kann.** Ein Gitter mit 10'000 Streben ist als B-rep ein Boolean mit 10'000 Zylindern. Als Abstandsfeld ist es eine Summe von Feldern.
2. **Offsets sind trivial.** Kühlkanal 3 mm unter der Aussenhaut: Feld der Aussenhaut um 3 mm verschieben. Im B-rep muss die versetzte Fläche selbst konstruiert werden, was bei freien Flächen häufig scheitert.
3. **Formeln statt Modelle.** Wandstärke oder Gitterdichte in Abhängigkeit von Ort, Belastung oder Abstand zur Oberfläche sind eine Funktion im Code.
4. **Robust gegen schlechte Eingangsdaten.** Scandaten und Netze mit Fehlern liefern trotzdem ein Ergebnis.
5. **Fertigungsnah.** 3D-Druckdaten sind ohnehin Schichten. Der Weg Voxel → Schicht (CLI-Datei für Laser-Pulverbett) ist eine Funktion.

## 5. Warum B-rep bei Mass, Zeichnung, STEP, Toleranz stark bleibt

1. **Exakte Masse**: Steckverbindung mit 0.1 mm Spiel lässt sich als B-rep exakt ausführen. Im Voxelmodell wäre dafür ein Gitter unter 0.03 mm nötig (Speicher und Zeit explodieren).
2. **Zeichnung**: Aus dem B-rep folgt die Werkstattzeichnung (Ansichten, verdeckte Kanten, Massketten). Ein Voxelmodell kennt keine Kanten.
3. **STEP-Austausch**: Lieferanten, Fräser, Simulationsabteilungen erwarten STEP. Ein Netz als STEP hat Zehntausende Dreiecksflächen, ist nicht editierbar und in CAD unbrauchbar.
4. **Selektoren, Joints, Constraints**: "Fläche A gleitet auf Fläche B" ist eine Topologiefrage.
5. **Toleranz und Nachvollziehbarkeit**: Prüfplan, Messprotokoll und Freigabe beziehen sich auf Konstruktionsmasse.

## 6. Relevanz für Aerodynamik und Kühlluft (Boreas)

Die Hüllgeometrie (Rumpf, Tropfenprofile der Fins und Gondeln) ist **glatt, stetig und wenig detailreich**. Für die Bauform ist B-rep die natürliche Beschreibung. Bei innen liegenden Kühlwegen und Strukturen im Rumpf spielt Voxel seine Stärke aus.

### 6.1 Strömungssimulation (CFD) aus B-rep

- **STEP → Netzgenerator.** Gmsh liest STEP über den OpenCASCADE-Kern und erzeugt Volumennetze (Delaunay, Frontal, HXT). Flächen bleiben identifizierbar, das macht **benannte Randflächen** (Einlass, Auslass, Wand, Motorgondel) einfach. Quelle: https://gmsh.info/doc/texinfo/gmsh.html
- **STL → snappyHexMesh.** OpenFOAMs `snappyHexMesh` verlangt Oberflächen als STL/OBJ/NAS (`constant/triSurface`) und erzeugt daraus in drei Schritten (Castellation, Snapping, Layers) ein hexdominantes Netz mit Prismenschichten an der Wand. Quelle: https://doc.cfd.direct/openfoam/user-guide-v13/snappyhexmesh . Das heisst: **auch aus B-rep wird für diesen Weg zuerst tesselliert.** Der Vorteil von B-rep ist hier die kontrollierte Netzfeinheit (Toleranz beim STL-Export) und saubere Flächen, nicht ein exakter Flächenbezug.
- **Fluid-Domäne** entsteht als Boolean: Box minus Körper. Das ist im B-rep (`box - body`) und im Voxelmodell (`voxBoolSubtract`) einfach; robuster ist es im Voxelmodell.
- **Grenzschicht.** Für Widerstandsvorhersage brauchen wandaufgelöste Netze glatte Oberflächen. Ein voxelbasierter Rand hat Treppenstufen der Grösse des Voxels, bei zu grobem Gitter verfälscht das die Reibung. Dagegen hilft Glätten und ein feiner Export, kostet aber Auflösung und Speicher.

### 6.2 Voxelnative Löser (Lattice-Boltzmann)

- Lattice-Boltzmann-Löser arbeiten auf einem **kartesischen Gitter** und voxelisieren die Geometrie selbst (meist aus STL). Das passt zum Voxelmodell, das Abstandsfeld liefert sogar Randabstände. PicoGK kennt `ScalarField`/`VectorField` und OpenVDB, ausdrücklich zur Kopplung mit Simulationen (Release 1.5.0, 11.05.2024). Beispiel: https://github.com/leap71/PicoGK_SimulationExample
- **Achtung Lizenz:** Der bekannte GPU-Löser **FluidX3D** verbietet in seiner Lizenz **kommerzielle Nutzung und militärische/Rüstungsnutzung** ausdrücklich (Punkte 2 und 3 der Lizenz, https://github.com/ProjectPhysX/FluidX3D/blob/master/LICENSE.md). Für Boreas (Abfangdrohne, Firmenzweck) ist er ohne schriftliche Erlaubnis des Autors **nicht einsetzbar**. Andere LBM-Löser haben andere Lizenzen und müssen einzeln geprüft werden. Als Fallback für die Pipeline bleibt OpenFOAM (GPL) mit `snappyHexMesh`.
- Grenzen: Voxel-LBM löst Wandschichten und hohe Reynolds-Zahlen nur mit Wandmodellen oder sehr feinem Gitter; Aussenumströmung mit scharfen Hinterkanten ist anspruchsvoll. Für Kühlluft durch Kanäle bei moderater Geschwindigkeit ist es dagegen ein guter Kandidat (Hypothese).

### 6.3 Konforme Kühlkanäle und Wärmetauscher

- Im Rumpf durch Arme und Gondeln führende Kanäle, die der Aussenkontur mit konstantem Abstand folgen, sind mit einem Abstandsfeld einfach: Feld nach innen verschieben, Kanal als Rohrkurve (ShapeKernel `BasePipe`, `LatticePipe`) subtrahieren, Übergänge verrunden. Als B-rep braucht man eine Sweep-Bahn im Raum je Kanal und jeweils einen Boolean. Das funktioniert für wenige Kanäle gut.
- Wärmetauscher-artige Strukturen (Lamellen, Gitter, Gyroid) sind der Kernanwendungsfall von PicoGK (LEAP 71 zeigt Wendel-Wärmetauscher, Triebwerke). Für B-rep sind sie kaum praktikabel.

## 7. Hybrid-Workflow (Empfehlung für die Pipeline)

**Grundregel: B-rep ist der Master für Masse und Schnittstellen, Voxel ist Nachbearbeitung für die Innenstruktur und geht in Richtung Druckdaten. Nichts geht zurück.**

| Schritt | Werkzeug | Ergebnis |
|---|---|---|
| 1 | build123d | Parametrisches Modell nach Skelett-Methode, Schnittstellen (Steckverbindungen, Motorlager, Trennebene) exakt, Zeichnungen |
| 2 | build123d | Export **STEP** (an Fertigung/Zulieferer) und **STL** (fein, wasserdicht) |
| 3 | PicoGK | STL laden, Voxelfeld erzeugen; Innenstrukturen (Gitter, Kanäle, variable Wand); Schnittstellenzonen ausgrenzen oder erhalten |
| 4 | PicoGK | Ausgabe STL für Druck oder CLI-Schichten, Volumen als Kontrolle gegen B-rep |
| 5 | Prüfung | Volumen und Bounding Box der Voxel-Ausgabe gegen B-rep (Toleranz = Voxelgrösse), Massenabschätzung |

Datenfluss zwischen den Welten:

- **B-rep → Netz → Voxel**: funktioniert zuverlässig, sofern das Netz **wasserdicht** und **binäres STL** ist (PicoGK liest kein ASCII-STL). Verlust: Konstruktionsmass wird zu Netz (Genauigkeit gleich der gröberen der beiden Auflösungen).
- **Voxel → B-rep**: **verlustbehaftet, nur als Netz.** Ergebnis bleibt ein Dreiecksnetz. Ein daraus erzeugtes STEP hat viele Dreiecksflächen und lässt sich nicht sinnvoll weiterbearbeiten. build123d bringt experimentell `brep_from_stl.detect_primitives` (Näherung durch Ebenen, Zylinder, Kugeln) mit. Lokal gemessen: `import_stl` liefert nur eine Dreiecksschale, der daraus gebildete Solid ist ungültig.
- **Koordinaten und Einheiten**: Beide in mm; Achsen wie in PLAN.md (Z nach oben) festlegen und in beiden Zweigen prüfen.
- **Reproduzierbarkeit**: Voxelgrösse als Pflichtparameter im Lauf mitschreiben.

## 8. Alternativen (nur zur Einordnung)

- **CadQuery**: gleicher OCCT-Kern wie build123d, Python, älter und grösser (rund 5'900 Sterne, 1.18 Mio. Downloads pro Monat), Stil "fluent"; kein Voxel. https://github.com/CadQuery/cadquery
- **nTop**: kommerzielle implizite Modelliersoftware mit Feldern, Gittern, Notebooks und Automatisierung (Voxel/Implizit-Denken, aber proprietär, Lizenzkosten). https://www.ntop.com/resources/blog/implicits-and-fields-for-beginners/
- **OpenVDB direkt** (C++, Python-Bindings): der Unterbau von PicoGK, mehr Freiheit, viel mehr Eigenaufwand. https://github.com/AcademySoftwareFoundation/openvdb
- **libfive und andere Implizit-Kerne**: Implizite Körper aus Formeln, Skript-orientiert, kleinere Community (1'665 Sterne, letzter Push 12.11.2025). https://github.com/libfive/libfive
- **Onshape (FeatureScript und REST-API)**: cloudbasiertes B-rep-CAD mit programmierbaren Features und HTTP-Schnittstelle, proprietär. https://www.onshape.com/en/blog/featurescript-custom-cad-features-vs-macros-api

## Quellen

- `docs/research_picogk.md`, `docs/research_build123d.md`
- https://gmsh.info/doc/texinfo/gmsh.html
- https://doc.cfd.direct/openfoam/user-guide-v13/snappyhexmesh
- https://github.com/ProjectPhysX/FluidX3D/blob/master/LICENSE.md
- https://github.com/leap71/PicoGK/releases (1.5.0 Felder, 1.6.0 Headless und ScalarField aus Voxels)
- https://github.com/leap71/PicoGK_SimulationExample
- Lokale Messungen an `Mohammed_0.1 Full Shell.step`, 30.09.2026
