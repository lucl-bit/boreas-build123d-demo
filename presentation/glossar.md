# Glossar

Begriffe des Vortrags in einfacher Sprache. Jeder Eintrag: ein Satz Erklärung, dann ein Bezug zu Boreas oder ein Beispiel.
Die Begriffe sind thematisch geordnet; am Ende steht ein alphabetisches Register.

## 1. Grundbegriffe: Wie wird Form gespeichert?

**CAD-Kern**
Die Rechenmaschine unter der Oberfläche eines CAD-Programms: Sie speichert Formen und kann sie vereinigen, abziehen, verrunden und messen. Die Knöpfe und Menüs sind nur die Oberfläche darüber. *Hier verglichen: OpenCASCADE (unter build123d) und PicoGK.*

**B-rep (Boundary Representation)**
Ein Körper wird durch seine Haut beschrieben: Flächen, die an Kanten zusammentreffen, die an Ecken enden. Jede Fläche ist eine mathematische Formel. *Alltagsbild: Vektorgrafik. Bei Boreas: build123d.*

**Fläche, Kante, Ecke (Face, Edge, Vertex)**
Die drei Bausteine eines B-rep-Körpers. Eine Kante ist die Naht, an der zwei Flächen zusammentreffen; eine Ecke ist ein Punkt, an dem Kanten enden.

**NURBS**
Eine Formelsorte für frei geformte, glatte Flächen und Kurven, die alle gängigen CAD-Systeme verwenden. *Beispiel: das Tropfenprofil einer Aero-Fin.*

**Voxel**
Ein Pixel in 3D: ein winziger Würfel in einem regelmässigen Raster. Ein Körper besteht aus allen Würfeln, die „innen“ liegen. *Alltagsbild: Minecraft, nur sehr fein. Bei Boreas: PicoGK.*

**Voxelgrösse**
Die Kantenlänge einer Zelle, zum Beispiel 0.5 mm. Sie legt fest, wie fein das Raster ist und damit, wie genau die Form wird. Halbe Voxelgrösse bedeutet in einem dichten Raster achtmal so viele Zellen.

**Diskretisierung**
Das Umwandeln einer glatten Form in ein Raster oder in Dreiecke. Dabei geht immer etwas Genauigkeit verloren. *Ein Kreis wird zur Treppe.*

**Treppeneffekt (Staircase)**
Die sichtbaren Stufen an schrägen oder runden Flächen eines Voxel-Körpers. Sie werden mit kleineren Zellen feiner, verschwinden aber nie ganz.

**SDF (Signed Distance Field, Distanzfeld)**
Ein Raster, in dem jede Zelle den Abstand zur Oberfläche speichert, mit Vorzeichen: negativ innen, positiv aussen, null genau auf der Fläche. Daraus lassen sich Formen durch einfaches Rechnen kombinieren (min, max).

**Implizite Geometrie**
Eine Form, die nicht durch ihre Oberfläche beschrieben wird, sondern durch eine Funktion, die für jeden Punkt im Raum sagt, ob er innen oder aussen liegt (oder wie weit weg). Ein SDF ist die bekannteste Sorte.

**Mesh / Netz**
Eine Oberfläche aus vielen kleinen Dreiecken. Sie hat keine Formeln, nur Eckpunkte; Rundungen sind eine Näherung. *Beispiel: STL-Datei für den 3D-Druck.*

**Tessellierung**
Das Umwandeln exakter B-rep-Flächen in ein Dreiecksnetz, zum Beispiel für die Darstellung oder den 3D-Druck. Je feiner die Dreiecke, desto genauer, desto grösser die Datei.

**Wasserdicht (watertight)**
Ein Netz ohne Löcher, das einen Körper eindeutig einschliesst. Nötig, damit ein Programm Volumen berechnen oder drucken kann.

## 2. Dateiformate

**STEP**
Das Standard-Austauschformat für exakte CAD-Körper (B-rep, mit Flächen, Kanten, Baugruppenstruktur). *Die Referenzdatei von Boreas ist ein STEP aus Shapr3D.*

**STL**
Das einfachste Format für Dreiecksnetze; verbreitet im 3D-Druck. Enthält weder Masse noch Einheiten noch Farben.

**3MF**
Ein modernerer Ersatz für STL mit Einheiten, Farben und mehreren Körpern in einer Datei.

**URDF**
Beschreibt einen Roboter für Simulatoren: Teile, Gelenke, Massen, Trägheit. *Aus einem B-rep-Modell mit Joints erzeugbar.*

**Slice (Schicht)**
Ein Schnitt durch das Modell in einer bestimmten Höhe; der 3D-Drucker baut Schicht für Schicht. Bei Voxeln entstehen Slices direkt aus dem Raster.

## 3. Geometrie-Operationen

**Boolean (Boolesche Operation)**
Körper vereinigen, voneinander abziehen oder ihren Durchschnitt bilden. *Beispiel: Motorloch aus dem Arm herausschneiden.* Bei B-rep manchmal fehleranfällig, bei Voxel und Distanzfeld sehr robust.

**Fillet (Verrundung)**
Eine Kante wird durch eine gerundete Fläche ersetzt. Im B-rep ist das ein exakter Kreisbogen; im Voxel-Raster entsteht die Rundung durch Glätten.

**Chamfer (Fase)**
Wie Fillet, aber die Kante wird gerade abgeschrägt.

**Shell / Offset (Schale, Versatz)**
Einen Vollkörper aushöhlen (Wand behalten) beziehungsweise eine Fläche gleichmässig verschieben. *Beispiel: Rumpf mit 1.2 mm Wandstärke.* Im Voxel-Raster einfach, weil man nur den Abstand vergleichen muss.

**Loft**
Eine Fläche oder ein Körper, der durch mehrere Querschnitte verläuft und sie glatt verbindet. *Beispiel: Propeller aus verdrehten Ellipsen.*

**Sweep**
Ein Profil wird entlang einer Bahn gezogen. *Beispiel: Kabel als Kreis entlang einer Kurve.*

**Selektor**
Eine Regel, mit der man Flächen oder Kanten auswählt, statt sie anzuklicken. *Beispiel: „alle Kanten am oberen Ring“.* Macht Fillets robust gegen Parameteränderungen.

**Lattice (Gitterstruktur)**
Ein Körper aus einem regelmässigen oder angepassten Netz aus dünnen Streben. Spart Gewicht und kann Wärme oder Strömung führen. *Für Flächenkerne aufwendig, für Voxel-Raster eine Formel.*

**Infill**
Füllung im Inneren eines gedruckten Teils, meist als Gitter, um Material zu sparen.

**Konformer Kanal**
Ein Kanal (zum Beispiel für Kühlluft), der der Aussenform des Bauteils in gleichbleibendem Abstand folgt, statt gerade zu verlaufen.

## 4. Parametrik und Konstruktionsmethodik

**Parametrik**
Ein Modell wird durch Zahlen (Parameter) gesteuert; ändert man eine Zahl, baut sich das Modell neu auf. *Beispiel: `body_fins.chord = 40`.*

**Constraint (Bedingung)**
Eine Regel, die die Geometrie einschränkt: „diese Linie bleibt senkrecht“, „Mindestabstand 2 mm“. In Boreas prüfen elf Constraints die Auslegung.

**Skelett-Methode (Top-down-Design)**
Alle Masse, die mehrere Teile gemeinsam brauchen, liegen in einem zentralen „Skelett“. Jede Parametergruppe liest nur ihre eigenen Parameter und das Skelett. Dadurch ändert eine Gruppe nur ihre eigene Geometrie.

**Parametergruppe**
Eine Sammlung zusammengehöriger Parameter eines Teils, zum Beispiel `arms` oder `motor_pods`. Gruppen sind so geschnitten, dass man pro Durchlauf eine ändern kann.

**Abgeleitetes Mass**
Ein Mass, das aus anderen berechnet wird, zum Beispiel Laschenbreite = Schlitzbreite − 2 × Spiel. Kein freier Parameter.

**Geometrie-Hash**
Ein Fingerabdruck der Geometrie. Bleibt er nach einer Änderung gleich, hat sich die Geometrie nicht verändert. *Wird benutzt, um zu prüfen, dass eine Gruppenänderung nur diese Gruppe betrifft.*

**Regenerationszeit**
Die Zeit, die das Modell braucht, um sich nach einer Parameteränderung neu aufzubauen.

**Baugruppe und Joint**
Mehrere Teile, die über Gelenke (Joints) verbunden sind statt über feste Koordinaten. *Beispiel: Nasenkappe fest am Rumpf, Propeller drehbar.*

**Toleranz und Passung**
Erlaubte Abweichung eines Masses (Toleranz) beziehungsweise das Spiel zwischen zwei Teilen (Passung). Nur mit exakter Geometrie sinnvoll definierbar.

## 5. Simulation und Analyse

**CFD (Computational Fluid Dynamics)**
Strömungssimulation am Computer: Wie fliesst die Luft um die Drohne, wie gross ist der Widerstand?

**LBM (Lattice-Boltzmann-Methode)**
Ein CFD-Verfahren, das auf einem regelmässigen Raster arbeitet. Ein Voxel-Modell kann direkt als solches Raster dienen. `[[FAKT PRÜFEN: Eignung PicoGK-Raster als LBM-Gitter]]`

**FEM (Finite-Elemente-Methode)**
Ein Verfahren, um Verformung und Spannung eines Bauteils unter Last zu berechnen. *In der Demo: vereinfachter Balken-FEM für einen Ausleger.*

**Trägheit, Schwerpunkt**
Wie sich die Masse im Bauteil verteilt; wichtig für die Flugdynamik. Aus exakter Geometrie exakt berechenbar, aus Voxeln nur so genau wie das Raster.

**Stirnfläche, benetzte Fläche**
Die der Strömung zugewandte Projektionsfläche bzw. die gesamte von Luft überströmte Fläche; Eingangsgrössen für den Luftwiderstand.

**Strömungsdomäne**
Der Luftraum um das Bauteil, in dem die CFD-Rechnung stattfindet.

## 6. Aerodynamische Begriffe

**Tropfenprofil**
Eine Querschnittsform, vorne rund und hinten spitz, die Luft mit wenig Widerstand umströmt. *Bei Boreas: Aero-Fins und Motorgondeln.*

**Sehne (Chord)**
Die Länge des Profils von der Nase bis zur Hinterkante.

**Aero-Fin**
Eine schräge Leitfläche am Rumpf, die zum Arm beziehungsweise Motor führt.

**Gondel (Motor Pod)**
Die verkleidete Aufnahme eines Motors am Arm. Bei Boreas tropfenförmig.

## 7. Automation und Software

**API (Programmierschnittstelle)**
Die Menge der Befehle, über die ein Programm von aussen bedient wird. Bei build123d und PicoGK ist die API die Hauptschnittstelle, nicht eine Oberfläche.

**CLI (Kommandozeile)**
Ein Programm, das man über einen Textbefehl startet, zum Beispiel `python -m brep.cli --task B02`.

**Headless**
Betrieb ohne grafische Oberfläche, etwa auf einem Server oder in einer automatischen Kette. Voraussetzung für Pipelines.

**Design Automation (Konstruktionsautomatisierung)**
Der Ablauf von Anforderungen bis Fertigungsdaten läuft per Programm statt per Hand.

**Pipeline**
Eine Kette von Schritten, bei der das Ergebnis des einen die Eingabe des nächsten ist: Anforderungen → Geometrie → Simulation → Optimierung → Fertigung.

**KI-Agent**
Ein Programm mit einem Sprachmodell, das Aufgaben selbständig in Schritten löst, zum Beispiel Code schreiben, ausführen, Fehler lesen und korrigieren. Er kann CAD nur über Code oder API bedienen.

**Computational Engineering**
Bauteile werden nicht gezeichnet, sondern per Programm aus Regeln und Anforderungen berechnet. *LEAP 71 nutzt den Begriff für seinen Ansatz.* `[[FAKT PRÜFEN: A05]]`

**Mock-Daten**
Erfundene Beispielwerte für Material, Motor und Aerodynamik. In der Demo zeigen sie den Ablauf; sie sind keine belastbaren Auslegungswerte.

## 8. Werkzeuge und Firmen

**build123d**
Python-Bibliothek für B-rep-Modelle auf Basis von OpenCASCADE. Bietet zwei Schreibweisen (Builder- und Algebra-Modus).

**OpenCASCADE (OCCT)**
Freier CAD-Kern, der exakte Flächen und Booleans berechnet; wird von mehreren Programmen verwendet.

**PicoGK**
Voxel-basierter Geometriekern von LEAP 71, in C#/.NET, für rechnergestütztes Konstruieren. `[[FAKT PRÜFEN: A05]]`

**LEAP 71**
Firma, die PicoGK entwickelt hat und für Antriebe und Wärmetauscher einsetzt. `[[FAKT PRÜFEN: A05]]`

**Shapr3D**
Zeichenprogramm, aus dem die Boreas-Referenzdatei stammt; frei modelliert, nicht durch Bemassungen gesteuert.

**Hybrid-Workflow**
Beide Techniken zusammen: B-rep für das Bemassbare und die exakte Übergabe, Voxel für Gitter, Kanäle und Felder. Schnittstelle dazwischen ist ein Mesh.

---

## Alphabetisches Register

3MF · abgeleitetes Mass · API · Aero-Fin · B-rep · Baugruppe · benetzte Fläche · build123d · CAD-Kern · CFD · Chamfer · Chord · CLI · Computational Engineering · Constraint · Design Automation · Diskretisierung · Distanzfeld · Ecke · Fase · FEM · Fillet · Fläche · Geometrie-Hash · Gondel · Headless · Hybrid-Workflow · implizite Geometrie · Infill · Joint · Kante · KI-Agent · konformer Kanal · Lattice · LBM · LEAP 71 · Loft · Mesh · Mock-Daten · NURBS · OpenCASCADE · Offset · Parametergruppe · Parametrik · Passung · Pipeline · PicoGK · Regenerationszeit · SDF · Sehne · Selektor · Shapr3D · Shell · Skelett-Methode · Slice · STEP · Stirnfläche · STL · Strömungsdomäne · Sweep · Tessellierung · Toleranz · Trägheit · Treppeneffekt · Tropfenprofil · URDF · Voxel · Voxelgrösse · wasserdicht
