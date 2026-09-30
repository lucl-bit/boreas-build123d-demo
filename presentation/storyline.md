# Storyline: B-rep (build123d) gegen Voxel (PicoGK)

Talk von Lucas, 15 bis 20 Minuten, neben einer Live-Demo (Web-GUI, Modi ① Feature-Tour, ② Werkbank, ③ Pipeline, ④ Vergleich).
Zielpublikum: Leute, die weder die Werkzeuge noch den Unterschied zwischen B-rep und Voxel kennen.
Ziel: Das Publikum kann am Ende **selbst erklären**, worin der Unterschied besteht und wann welche Technik sinnvoll ist.

Stand: 30.09.2026. Alle Ergebnisse sind Platzhalter, bis der Benchmark gelaufen ist (Konvention unten).

## Lesehinweise

**Platzhalter-Konvention** (alles, was noch zu ersetzen ist, steht in doppelten eckigen Klammern und lässt sich mit Suchen nach `[[` finden):

| Muster | Bedeutung |
|---|---|
| `[[ERGEBNIS: B07 Genauigkeit vs. Voxelgrösse]]` | Benchmark-Ergebnis der Aufgabe mit dieser ID (IDs aus PLAN.md) |
| `[[ZAHL: …]]` | einzelne Zahl innerhalb eines Satzes |
| `[[BILD: …]]` | Screenshot/Render aus der Demo oder dem Benchmark |
| `[[FAKT PRÜFEN: …]]` | Sachaussage über ein Werkzeug, die der Recherche-Agent (docs/, feature_matrix.json) belegen muss |
| `[[EMPFEHLUNG: …]]` | Entscheidung, die erst nach den Ergebnissen feststeht |

**Layout-Angaben** sind generisch (Titel, Abschnitt, Inhalt, Bild gross, zwei Spalten, Tabelle). Die Zuordnung auf die echten Layouts der Vorlage steht in `template_notes.md`, sobald die Vorlage ausgewertet ist.

**Farbkonvention in allen Figuren:** B-rep = Blau, Voxel = Orange, neutral = Grau/Schwarz. Auf jeder Folie mit Vergleich konsequent so verwenden.

**Sprache:** Deutsch, Schweizer Schreibweise (kein Eszett, „Grösse“, „gross“).

## Zeitplan

| Nr. | Folie | Min. | Demo |
|---|---|---|---|
| 1 | Titel | 0:30 | |
| 2 | Ausgangslage | 1:00 | |
| 3 | CAD-Kern und Vektor/Pixel-Analogie | 1:00 | |
| 4 | B-rep | 1:15 | ① Feature-Tour, Schritt „STEP-Import & Topologie“ |
| 5 | Voxel und Distanzfeld | 1:15 | |
| 6 | Die zwei Kandidaten | 0:30 | |
| 7 | Dasselbe Bauteil in beiden Welten | 1:00 | ④ Vergleich |
| 8 | Fünf Bewertungsziele | 0:30 | |
| 9 | Benchmark-Objekt und Parametergruppen | 1:15 | ② Werkbank oder ④ Regler |
| 10 | Methode | 0:45 | |
| 11 | Ergebnis: Funktionen und Limitierungen | 1:00 | |
| 12 | Ergebnis: Geometrie, Aero, Kühlung | 1:15 | ④ Vergleich (Voxelgrösse) |
| 13 | Ergebnis: Leistung und Regeneration | 0:45 | |
| 14 | Nur B-rep kann das | 1:00 | ② Werkbank, bemasste Zeichnung |
| 15 | Nur Voxel kann das | 1:00 | ④ Vergleich (Gitter, Kühlkanal) |
| 16 | API, KI-Agenten, Pipeline | 1:15 | ③ Pipeline |
| 17 | Empfehlung | 1:30 | |
| 18 | Nächste Schritte | 0:30 | |
| | **Summe** | **17:15** | plus Demo-Sprünge (je 30 bis 60 s) = ca. 20 Min. |

**Kurzpfad für 15 Minuten:** Folien 6, 8 und 13 nur einblenden und einen Satz sagen; Folie 10 auf 20 Sekunden kürzen; nur zwei Demo-Sprünge (Folie 7 und Folie 14).

**Rote Linie durch den Vortrag:** *Wie wird Form gespeichert? → Das bestimmt, was leicht und was schwer ist. → Welche Teile von Boreas sind welcher Art?*

## Demo-Übersicht (wo gewechselt wird)

| Folie | Wechsel zu | Was gezeigt wird | Zurück zur Folie mit |
|---|---|---|---|
| 4 | ① Feature-Tour, „STEP-Import & Topologie“ | Farbige Flächentypen am echten Bauteil: jede Farbe ist ein anderer Flächentyp | Satz „Das sind die Flächen aus meiner Skizze“ |
| 7 | ④ Vergleich | Dasselbe Bauteil links B-rep, rechts Voxel, Voxelgrösse umschalten | „Sieht gleich aus, ist innen verschieden“ |
| 9 | ② Werkbank (oder ④, Regler) | Einen Parameter der Gruppe `body_fins` ziehen, nur die Fins ändern sich | „Eine Gruppe, ein Effekt“ |
| 12 | ④ Vergleich | Voxelgrösse grob nach fein, Abweichung und Rechenzeit ablesen | „Der Regler heisst Voxelgrösse“ |
| 14 | ② Werkbank | Bemasste Zeichnung (2 × A3) aus demselben Modell | „Das Voxel-Modell hat keine Bemassung“ |
| 15 | ④ Vergleich | Gitter-Infill oder Kühlkanal, falls im Modus vorhanden, sonst [[BILD: V01/V02]] | „Das ist die Stärke des Rasters“ |
| 16 | ③ Pipeline | Anforderungen → CAD → Simulation → Optimierung → Report, ohne Klicks | „Das läuft auch ohne Oberfläche“ |

Reserve bei Demo-Ausfall: Für jede Demo-Stelle ein Screenshot als `[[BILD: …]]` vorhalten.

## Figuren-Index

| Datei | Verwendung |
|---|---|
| `figures/fig01_vektor_vs_pixel.svg` | Folie 3 |
| `figures/fig02_brep_anatomie.svg` | Folie 4 |
| `figures/fig04_sdf_2d.svg` | Folie 5 |
| `figures/fig03_fin_kurve_vs_voxel.svg` | Folie 7 |
| `figures/fig05_parametergruppen_skelett.svg` | Folie 9 |
| `figures/fig07_genauigkeit_vs_voxelgroesse.svg` | Folie 12 (Schema; ersetzen durch echte Kurve aus B07) |
| `figures/fig06_pipeline_einordnung.svg` | Folie 16 |
| `figures/fig08_hybrid_workflow.svg` | Folie 17 und Backup B5 |

---

# Hauptteil

## Folie 1: Der Boreas-Rumpf lässt sich per Code bauen, aber auf zwei grundverschiedene Arten

- **Layout:** Titel
- **Auf der Folie:** Haupttitel (siehe oben), Untertitel „Vergleich build123d (B-rep) und PicoGK (Voxel) für die Design-Automation-Pipeline“, Name, Datum. Kleines Bild: Boreas-Abfangdrohne, links blau eingefärbt, rechts orange (zwei Render aus dem Vergleichsmodus, `[[BILD: Boreas-Gesamtansicht B-rep | Voxel]]`).
- **Sprechtext:** Guten Tag zusammen. Ich zeige heute, wie man Bauteile unserer Abfangdrohne nicht mehr von Hand zeichnet, sondern per Programmcode erzeugt. Dafür gibt es zwei sehr verschiedene Techniken, und ich habe sie am selben Bauteil gegeneinander getestet. Wer am Ende nicht nur weiss, welche Technik ich empfehle, sondern auch erklären kann, worin sie sich unterscheiden, für den hat sich die Viertelstunde gelohnt. Neben den Folien läuft eine Live-Demo, in die ich ein paarmal wechsle.
- **Demo:** keine

## Folie 2: Eine Design-Pipeline ist nur so gut wie der Geometrie-Baustein, der in ihr steckt

- **Layout:** Inhalt mit Bild (links Text, rechts Schema)
- **Auf der Folie:** Schema in fünf Kästchen: Anforderungen → Geometrie → Simulation → Optimierung → Fertigung, mit Rückpfeil. Drei Stichworte daneben:
  - Varianten in Minuten statt Tagen
  - KI-Agenten als Mitarbeiter im Ablauf
  - Komplexe Aero- und Kühlluft-Formen
- **Sprechtext:** Unser Ziel ist eine Pipeline. Am Anfang stehen Anforderungen, etwa Nutzlast oder Fluggeschwindigkeit. Daraus entsteht Geometrie, die geht in Simulationen, eine Optimierung ändert Parameter, und am Ende kommen Fertigungsdaten heraus. Das Ganze soll ohne Mausklicks laufen, damit wir viele Varianten durchrechnen können und damit auch ein KI-Agent mitarbeiten kann. Genau in der Mitte dieser Kette sitzt die Geometrie. Unsere Referenz, die Datei aus Shapr3D, ist von Hand gezeichnet und nicht durch Bemassungen gesteuert. Wer eine Flosse ändern will, muss von Hand nacharbeiten. Das wollen wir ändern. Dazu kommt: Unsere Teile werden aerodynamisch und thermisch anspruchsvoller, mit schrägen Aero-Fins, tropfenförmigen Gondeln und Kühlluftführung im Rumpf. Die Frage ist also nicht nur „Können wir Geometrie per Code erzeugen?“, sondern „Mit welcher Technik geht das für unsere Teile am besten?“.
- **Demo:** keine (Pipeline-Ansicht kommt bei Folie 16)

## Folie 3: Ein CAD-Kern speichert Form, und die Art des Speicherns entscheidet, was leicht und was schwer ist

- **Layout:** Bild gross
- **Auf der Folie:** `fig01_vektor_vs_pixel.svg`. Eine Zeile Definition am Rand: „CAD-Kern = die Rechenmaschine unter der Oberfläche: speichert Formen, verknüpft sie, misst sie.“
- **Sprechtext:** Was ist ein CAD-Kern? Er ist der Teil eines CAD-Programms, der Formen speichert und damit rechnet: zwei Körper vereinigen, ein Loch abziehen, eine Kante verrunden, das Volumen messen. Die Oberfläche mit den Knöpfen sitzt obendrauf. Der springende Punkt ist, wie der Kern eine Form speichert. Dafür kennen Sie alle ein Bild aus dem Alltag: Eine Vektorgrafik, zum Beispiel ein Logo, speichert ein Rezept, nämlich Kurve durch diese Punkte. Sie können beliebig hineinzoomen, die Linie bleibt glatt. Ein Pixelbild dagegen speichert ein Raster aus farbigen Punkten. Zoomen Sie hinein, sehen Sie Treppen. In 3D gibt es genau denselben Unterschied. Das Rezept heisst B-rep, das Raster heisst Voxel. Voxel ist einfach ein Pixel in 3D, ein winziger Würfel. Alles Weitere folgt aus diesem einen Unterschied.
- **Demo:** keine

## Folie 4: B-rep beschreibt einen Körper als exaktes Rezept aus Flächen

- **Layout:** Bild gross oder zwei Spalten (Bild links, drei Aussagen rechts)
- **Auf der Folie:** `fig02_brep_anatomie.svg` (Körper → Flächen → Kanten → Ecken; Flächentypen). Rechts oder darunter, kurz:
  - Masse sind exakt (Rundung = echter Kreisbogen)
  - Man kann Kanten und Flächen gezielt ansprechen
  - Austauschformat: STEP
  - Schwäche: schwierig bei sehr vielen, feinen Details
- **Sprechtext:** B-rep steht für „Boundary Representation“, also Begrenzungs-Beschreibung. Man kann es sich wie ein Papiermodell aus exakt geformten Blättern vorstellen. Ein Körper wird durch seine Haut beschrieben. Die Haut besteht aus Flächen, jede Fläche ist eine mathematische Formel, zum Beispiel eben, zylindrisch, kegelig oder frei geformt. Wo zwei Flächen zusammentreffen, liegt eine Kante, und wo Kanten zusammentreffen, eine Ecke. Das hat drei Folgen. Erstens sind Masse exakt: Eine Verrundung mit fünf Millimeter Radius ist wirklich ein Kreisbogen mit fünf Millimeter. Zweitens kann man Elemente gezielt ansprechen, zum Beispiel „alle Kanten am oberen Ring verrunden“, und das funktioniert auch noch, wenn sich der Durchmesser ändert. Drittens ist es der Standard der CAD-Welt: Das Austauschformat STEP transportiert genau diese Flächen. Der Preis: Bei sehr vielen kleinen Details, etwa tausenden Gitterstreben, wird das Rechnen langsam oder unzuverlässig. Zu build123d komme ich gleich.
- **Demo:** Wechsel zu ① Feature-Tour, Schritt „STEP-Import & Topologie“. Zeigen: Die Farben am Boreas-Teil sind die Flächentypen, „das sind die Flächen und Kanten, von denen ich gerade gesprochen habe“. Danach zurück.

## Folie 5: Voxel beschreibt einen Körper als Raster, in dem jede Zelle weiss, wie weit die Oberfläche entfernt ist

- **Layout:** Bild gross
- **Auf der Folie:** `fig04_sdf_2d.svg`. Dazu ein Merksatz: „Voxel = Minecraft, nur sehr fein.“
- **Sprechtext:** Voxel funktioniert ganz anders. Stellen Sie sich Minecraft vor: Die Welt besteht aus Würfeln, jeder Würfel ist da oder nicht. Für Ingenieurteile nimmt man sehr feine Würfel, etwa einen halben Millimeter. Der Clou bei PicoGK und ähnlichen Systemen ist, dass jede Zelle mehr weiss als „da oder nicht da“. Sie merkt sich den Abstand zur Oberfläche, mit Vorzeichen: negativ innen, positiv aussen, null genau auf der Oberfläche. Das nennt man ein Distanzfeld. Das Bild zeigt es in 2D an einem Kreis. Der Vorteil: Formen kombinieren wird zu simplem Rechnen. Vereinigen ist das Minimum zweier Zahlen, Abziehen ein Maximum. Es gibt keine Flächen, die sich schneiden müssen, deshalb gelingen Booleans praktisch immer. Eine Wand der Dicke w besteht einfach aus allen Zellen, deren Abstand zur Fläche höchstens die halbe Wandstärke beträgt. Gitterstrukturen und Kühlkanäle lassen sich damit wie Formeln hinschreiben. Der Preis ist die Genauigkeit: Sie ist so gut wie das Raster, und ein feineres Raster kostet Speicher und Rechenzeit.
- **Demo:** keine (die Voxelgrösse wird bei Folie 12 live verstellt)

## Folie 6: Die Kandidaten: build123d rechnet exakt in Flächen, PicoGK rechnet im Raster

- **Layout:** Zwei Spalten
- **Auf der Folie:** Zwei Kästen, links blau, rechts orange, jeweils vier Zeilen.

| | build123d | PicoGK |
|---|---|---|
| Technik | B-rep | Voxel / Distanzfeld |
| Sprache | Python | C# (.NET) |
| Basis | Open-Source-Kern OpenCASCADE | Open-Source-Kern von LEAP 71 `[[FAKT PRÜFEN: A05 Lizenz, Herkunft, Basis]]` |
| Typische Ausgabe | STEP, Zeichnung, STL | STL, Schichtdaten |

- **Sprechtext:** Die beiden Kandidaten. Auf der blauen Seite steht build123d, eine Python-Bibliothek, die auf dem verbreiteten Open-Source-CAD-Kern OpenCASCADE aufsetzt. Sie erzeugt exakte Flächen und exportiert STEP. Auf der orangen Seite steht PicoGK, ein Voxel-Kern, entwickelt von der Firma LEAP 71, geschrieben in C#. LEAP 71 setzt ihn nach eigener Darstellung für Triebwerke und Wärmetauscher ein `[[FAKT PRÜFEN: A05]]`. Beide Werkzeuge haben denselben Zweck, nämlich Geometrie aus Programmcode. Sie unterscheiden sich in dem, was ich eben erklärt habe. Das machen wir gleich am selben Bauteil sichtbar.
- **Demo:** keine

## Folie 7: Dasselbe Bauteil sieht in beiden Welten gleich aus, ist aber innen grundverschieden

- **Layout:** Bild gross (zwei Bilder nebeneinander) oder zwei Spalten
- **Auf der Folie:** Links Boreas-Oberteil als B-rep-Render (blau), rechts als Voxel-Render (orange) `[[BILD: Oberteil B-rep | Voxel, gleiche Ansicht]]`. Darunter oder als zweite Folienhälfte `fig03_fin_kurve_vs_voxel.svg` (Tropfenprofil der Aero-Fins mit Zoom auf die Hinterkante).
- **Sprechtext:** Hier sehen Sie unser Oberteil, links als B-rep, rechts als Voxel. Auf Bildschirmgrösse sieht man kaum einen Unterschied. Der Unterschied liegt in dem, was gespeichert ist. Ich zoome auf eine typische Stelle: das Tropfenprofil unserer Aero-Fins. Links die exakte Kurve, mit scharfer Hinterkante, beliebig vergrösserbar. In der Mitte ein grobes Raster, die Hinterkante ist ausgefallen, weil sie schmaler ist als eine Zelle. Rechts ein feines Raster, die Treppe ist kaum sichtbar. Merken Sie sich den Satz, der uns durch den ganzen Vortrag begleitet: Je dünner das Detail, desto feiner muss das Raster sein, und ein feineres Raster kostet in 3D sehr schnell sehr viel Speicher.
- **Demo:** Wechsel zu ④ Vergleich. Dasselbe Teil links B-rep, rechts Voxel; Voxelgrösse einmal grob, einmal fein stellen; auf Fin-Hinterkante oder Gondelspitze zoomen. Danach zurück.

## Folie 8: Wir bewerten die beiden Techniken an fünf Zielen

- **Layout:** Inhalt (Liste mit Nummern)
- **Auf der Folie:**
  1. Funktionsvergleich
  2. Limitierungen: Was kann welche Technik besser?
  3. B-rep gegen Voxel bei komplexer Geometrie, Aerodynamik, Kühlluft
  4. API: Automatisierung per Code, KI-Agenten
  5. Eignung für die Design-Automation-Pipeline
- **Sprechtext:** Ich habe mir fünf Fragen gestellt. Erstens: Was können die Werkzeuge überhaupt, und zwar Funktion für Funktion? Zweitens: Wo liegen die Grenzen, und was kann die eine Technik, was die andere nicht? Drittens: Wie schlagen sich beide bei komplexer Geometrie, Aerodynamik und Kühlluftführung, also genau dort, wo unsere Teile schwierig werden? Viertens: Wie gut lassen sich die Werkzeuge per Code und durch KI-Agenten bedienen? Und fünftens: Passen sie in eine Design-Automation-Pipeline? Jede Ergebnisfolie später ist einem dieser Ziele zugeordnet.
- **Demo:** keine

## Folie 9: Als Testobjekt dient das Boreas-Rumpfmodell, aufgeteilt in Parametergruppen mit einem gemeinsamen Skelett

- **Layout:** Bild gross
- **Auf der Folie:** `fig05_parametergruppen_skelett.svg`. Zeile darunter: „Referenz: Shapr3D-Export, 4 Körper (Unterteil, Oberteil, Nasenkappe, Einsatz).“
- **Sprechtext:** Als Testobjekt nehme ich unser eigenes Bauteil: den Rumpf mit Unterteil, Oberteil und Nasenkappe, aufgebaut aus der Shapr3D-Datei. Wichtig ist nicht das Teil, sondern die Ordnung dahinter. Ich habe alle Parameter in zehn Gruppen sortiert, zum Beispiel Arme, Motorgondeln, Aero-Fins, Heckflossen. In der Mitte steht das Skelett. Es enthält nur die Masse, die mehrere Teile gemeinsam brauchen, etwa Anzahl der Arme, Motorposition und Lage der Trennebene. Die Regel lautet: Jede Gruppe darf nur ihre eigenen Parameter und das Skelett lesen, nie eine andere Gruppe. Dadurch ändert sich beim Verstellen einer Gruppe auch nur diese Geometrie. Das ist Voraussetzung für eine Pipeline, in der ein Agent gezielt einen Hebel bewegt und der Rest stabil bleibt. Und es ist ein fairer Test: Beide Werkzeuge müssen genau dieselbe Aufgabe lösen.
- **Demo:** Wechsel zu ② Werkbank (oder ④ mit Parameterregler). Parameter der Gruppe `body_fins` ziehen, z. B. die Sehne. Nur die Fins ändern sich, Rumpf und Arme bleiben. Danach zurück.

## Folie 10: Beide Werkzeuge lösen dieselben Aufgaben, gemessen wird neutral und identisch

- **Layout:** Zwei Spalten (Aufgaben links, Methode rechts)
- **Auf der Folie:** Zehn gemeinsame Aufgaben B01 bis B10 (nur Kurzform, eine Zeile): Import, Gesamtmodell, Gruppen-Variation, Tropfenprofil, Wandstärke, Verrundungen, Masse und Genauigkeit, Druck-Export, Aero-Vorbereitung, Skalierung. Rechts:
  - gleicher Aufruf, gleiche Spec, gleicher Rechner
  - gemessen: Laufzeit, Speicher, Codezeilen, Ergebnis-Status
  - „nicht möglich“ zählt als Ergebnis
  - Hinweis: Material-, Motor- und Aerowerte der Demo sind Mock-Daten (es geht um die Werkzeuge, nicht um die Auslegung)
- **Sprechtext:** Zur Methode. Es gibt zehn gemeinsame Aufgaben, von „Referenz einlesen“ über „Wandstärke“ bis zu „Laufzeit und Speicher bei feiner werdender Auflösung“. Beide Werkzeuge bekommen dieselbe Parameterdatei und werden über denselben Aufruf gestartet, und sie schreiben ihr Ergebnis in dieselbe Struktur: Laufzeit, Speicherbedarf, Volumen, Fläche, Dateien und die Zahl der Codezeilen. Wenn ein Werkzeug eine Aufgabe nicht lösen kann, steht dort „nicht unterstützt“ mit Begründung. Das ist ein Ergebnis, kein Fehler. Dazu kommen Aufgaben, die nur für eine Seite Sinn ergeben, zum Beispiel Gitterstrukturen für Voxel und die bemasste Zeichnung für B-rep. Ein wichtiger Hinweis: Alle Material-, Motor- und Aerowerte in meiner Demo sind Platzhalter-Daten. Es geht um den Vergleich der Werkzeuge, nicht um belastbare Auslegungswerte.
- **Demo:** keine

## Folie 11: [[ERGEBNIS: Ziele 1 und 2, Funktionsvergleich]] Jede Technik hat klare Stärken, und die Überschneidung ist kleiner als erwartet

- **Layout:** Tabelle
- **Auf der Folie:** Feature-Matrix (Auszug aus `spec/feature_matrix.json`), Spalten B-rep | Voxel, Symbole: erfüllt / teilweise / nicht möglich (Symbole zusätzlich zur Farbe, Projektor!). Zeilen zum Beispiel:

| Funktion | B-rep | Voxel |
|---|---|---|
| Bemasste technische Zeichnung (R01) | `[[ERGEBNIS: R01]]` | `[[ERGEBNIS: R01]]` |
| STEP-Export (R02) | `[[ERGEBNIS: R02]]` | `[[ERGEBNIS: R02]]` |
| Constraints, Baugruppen-Joints, URDF (R03) | `[[ERGEBNIS: R03]]` | `[[ERGEBNIS: R03]]` |
| Exakte Masse, Toleranzen (R04) | `[[ERGEBNIS: R04]]` | `[[ERGEBNIS: R04]]` |
| Gitter-Infill (V01) | `[[ERGEBNIS: V01]]` | `[[ERGEBNIS: V01]]` |
| Kühlkanäle durch den Rumpf (V02) | `[[ERGEBNIS: V02]]` | `[[ERGEBNIS: V02]]` |
| Booleans auf Scan-Mesh, variable Wandstärke (V03) | `[[ERGEBNIS: V03]]` | `[[ERGEBNIS: V03]]` |
| Slices für den Druck (V04) | `[[ERGEBNIS: V04]]` | `[[ERGEBNIS: V04]]` |
| Referenz-STEP importieren (B01) | `[[ERGEBNIS: B01]]` | `[[ERGEBNIS: B01, nur über Mesh?]]` |

- **Sprechtext:** Zuerst Ziel eins und zwei, der Funktionsvergleich. Ich zeige einen Auszug aus der Matrix, die vollständige steht im Anhang. `[[ERGEBNIS: Kernaussage in einem Satz, z. B. „B-rep deckt alles Bemassbare ab, Voxel alles Gitter- und Feldartige, nur wenige Funktionen liegen bei beiden“]]`. Besonders auffällig ist `[[ERGEBNIS: auffälligste Zeile]]`. Ich möchte darauf hinweisen, dass „nicht möglich“ nicht „schlecht“ heisst: Ein Voxel-Werkzeug braucht keine Zeichnung, wenn das Teil am Ende gedruckt wird.
- **Demo:** keine

## Folie 12: [[ERGEBNIS: B07 Genauigkeit vs. Voxelgrösse]] Bei [[ZAHL: Voxelgrösse]] mm bleibt der Voxel-Fehler unter [[ZAHL: Fehler]] %, dünne Hinterkanten brauchen [[ZAHL: Voxelgrösse fein]] mm

- **Layout:** Bild gross
- **Auf der Folie:** Vorläufig `fig07_genauigkeit_vs_voxelgroesse.svg` als Schema; sobald B07/B10 vorliegen, ersetzen durch echte Kurven `[[ERGEBNIS: B07 Genauigkeit vs. Voxelgrösse]]` und `[[ERGEBNIS: B10 Speicher/Laufzeit vs. Voxelgrösse]]`. Darunter drei Kacheln: `[[ERGEBNIS: B04 Tropfenprofil]]` | `[[ERGEBNIS: B05 Wandstärke]]` | `[[ERGEBNIS: B09 Aero-Vorbereitung]]`.
- **Sprechtext:** Jetzt zu Ziel drei, komplexe Geometrie, Aerodynamik und Kühlluft. Hier wirkt der Unterschied am stärksten. Links sehen Sie, wie weit die Voxel-Version von der exakten Form abweicht, je nach Voxelgrösse. Die B-rep-Version liegt praktisch bei null. Rechts sehen Sie den Preis: Jede Halbierung der Zellgrösse bedeutet in einem dichten Raster achtmal so viele Zellen. Weil PicoGK nur die Zellen in Oberflächennähe speichert, ist der Anstieg flacher, nämlich ungefähr viermal `[[FAKT PRÜFEN: A01 Speicherverhalten PicoGK]]`. Für unsere Aero-Fins bedeutet das: `[[ERGEBNIS: B04, z. B. Grösse der Abweichung an Nase und Hinterkante]]`. Für Wandstärken und Schalen: `[[ERGEBNIS: B05]]`. Für die Vorbereitung einer Strömungsrechnung, also Stirnfläche, benetzte Fläche und Rechengebiet: `[[ERGEBNIS: B09]]`. Die Faustregel, die daraus folgt, ist `[[ERGEBNIS: Faustregel Voxelgrösse zu kleinstem Detail]]`.
- **Demo:** Wechsel zu ④ Vergleich, Voxelgrösse grob nach fein stellen, Abweichung und Rechenzeit ablesen. Danach zurück.

## Folie 13: [[ERGEBNIS: B03 und B10 Leistung]] Änderungen an einer Gruppe regenerieren in [[ZAHL]] s (B-rep) gegenüber [[ZAHL]] s (Voxel)

- **Layout:** Tabelle (oder zwei kleine Balkendiagramme)
- **Auf der Folie:** Tabelle je Werkzeug: Regenerationszeit pro Gruppe (10 Gruppen), Spitzen-Speicher, Dateigrösse, Codezeilen für das Gesamtmodell. `[[ERGEBNIS: B03 Gruppen-Variation]]`, `[[ERGEBNIS: B10 Performance und Skalierung]]`, `[[ERGEBNIS: B02 Codezeilen Gesamtmodell]]`. Dazu Haken: „Nur die betroffene Gruppe ändert sich“ (ja/nein je Werkzeug).
- **Sprechtext:** Ziel fünf beginnt mit einer praktischen Frage: Wie lange dauert es, wenn ein Agent einen Parameter ändert und das Modell neu aufbauen lässt? Ich habe für jede der zehn Gruppen einen Parameter geändert und die Zeit gemessen. Ergebnis: `[[ERGEBNIS: B03, Kernaussage, z. B. Voxel-Zeit hängt an der Voxelgrösse, B-rep-Zeit an der Zahl der Features]]`. Bei den Speicherwerten sehen wir `[[ERGEBNIS: B10]]`. Und ich habe geprüft, ob wirklich nur die betroffene Gruppe ihre Geometrie ändert: `[[ERGEBNIS: B03 Isolationstest]]`. Zur Einordnung: Dass die Zahlen absolut hoch oder niedrig sind, sagt weniger als ihr Verlauf.
- **Demo:** keine

## Folie 14: Was nur B-rep kann: bemassen, tolerieren, Baugruppen und exakte Übergabe

- **Layout:** Zwei Spalten (Liste links, Bild rechts)
- **Auf der Folie:** Vier Punkte, jeweils mit ID:
  - R01 Bemasste technische Zeichnung
  - R02 Exakter STEP-Export und Kanten/Flächen-Auswahl per Regel
  - R03 Constraints, Skelett, Baugruppen-Joints, URDF
  - R04 Exakte Masse, Toleranzen, Passungen
  Rechts: Screenshot der bemassten Zeichnung `[[BILD: Zeichnung A3 aus Werkbank]]` und `[[ERGEBNIS: R01–R04 Status im Benchmark]]`.
- **Sprechtext:** Diese Folie zeigt, was nur mit B-rep geht, und zwar prinzipbedingt. Weil B-rep Flächen und Kanten kennt, kann man Masse an ihnen anbringen. Daraus entsteht eine bemasste Werkstattzeichnung, wie sie für CNC-Teile, Prüfung und Freigabe nötig ist. Man kann Passungen und Toleranzen festlegen, Teile über Gelenke verbinden und ein Skelett definieren, aus dem sich Bauteile ableiten. Und man kann Volumen und Schwerpunkt exakt berechnen, ohne Raster-Fehler. Für die Live-Demo zeige ich die Zeichnung, die aus demselben Modell entsteht, das Sie eben gesehen haben. `[[ERGEBNIS: R01 bis R04, Status und Beleg]]`.
- **Demo:** Wechsel zu ② Werkbank, Reiter Zeichnung: bemasste Zeichnung (2 × A3) zeigen; Satz: „Ein Voxel-Modell hat keine Kanten, an denen man ein Mass anbringen könnte.“ Danach zurück.

## Folie 15: Was nur Voxel kann: Gitter, konforme Kühlkanäle und Felder als Wandstärke

- **Layout:** Zwei Spalten (Liste links, Bild rechts)
- **Auf der Folie:** Vier Punkte:
  - V01 Gitter-Infill (Lattice)
  - V02 Kühlkanäle, die der Rumpfform folgen
  - V03 Robuste Booleans auf Mesh und Scan, variable Wandstärke
  - V04 Schichtdaten für den 3D-Druck
  Rechts: `[[BILD: V01 Gitter-Infill im Rumpf, V02 Kühlkanal]]` und `[[ERGEBNIS: V01–V04 Status und Laufzeit im Benchmark]]`.
- **Sprechtext:** Und jetzt die andere Seite. Voxel ist stark, wo Formen nicht mehr aus einzelnen Flächen bestehen, sondern aus einer Menge feiner Strukturen. Ein Gitter aus tausenden Streben ist für einen Flächenkern eine Belastungsprobe. Im Raster ist es eine Formel. Dasselbe gilt für Kühlkanäle, die dem Rumpf folgen, und für Wände, deren Dicke sich mit einem Feld ändert. In unserem Kontext heisst das: Wärme abführen im Rumpf, leichter werden ohne Festigkeit zu verlieren, und Teile drucken, ohne zuerst eine Fläche dafür zu bauen. `[[ERGEBNIS: V01 bis V04, Status, Laufzeit, Bemerkungen]]`. Beachten Sie aber: Das Ergebnis ist ein Raster. Wer daraus später eine Zeichnung braucht, hat ein Problem, das wir auf der nächsten Folie einordnen.
- **Demo:** Wechsel zu ④ Vergleich, sofern der Modus Gitter oder Kanal zeigt; sonst Screenshot. Danach zurück.

## Folie 16: Beide Werkzeuge sind per Code steuerbar; [[ERGEBNIS: A03 Eignung für KI-Agenten]] entscheidet über die Pipeline-Tauglichkeit

- **Layout:** Bild gross
- **Auf der Folie:** `fig06_pipeline_einordnung.svg`. Darunter eine Zeile mit den Kriterien A01 bis A05 und je `[[ERGEBNIS: A0x]]` (API und Sprache, headless/CLI, KI-Agenten, Pipeline-Integration, Lizenz/Reife).
- **Sprechtext:** Ziele vier und fünf zusammen. Beide Werkzeuge werden ausschliesslich über Programmcode bedient, das ist die Grundvoraussetzung für Automation. Der Unterschied liegt in den Details: Wie gut ist die Dokumentation? Verstehen KI-Agenten den Code? Sind die Fehlermeldungen brauchbar? Läuft das Werkzeug ohne Oberfläche, etwa auf einem Server? Ich habe für dieselbe Aufgabe gezählt, wie viele Codezeilen nötig sind, und beobachtet, wie ein Agent beim ersten Versuch abschneidet. `[[ERGEBNIS: A01 API und Sprache]]` `[[ERGEBNIS: A02 Headless-Betrieb]]` `[[ERGEBNIS: A03 Codezeilen pro Aufgabe, Agent-Erstversuch]]` `[[ERGEBNIS: A04 Pipeline-Integration]]` `[[ERGEBNIS: A05 Lizenz, Plattform, Reife]]`. Auf dem Schema sehen Sie, wo ich je Stufe der Pipeline die Stärke erwarte. Das ist eine Erwartung, und die Ergebnisse bestätigen sie teilweise `[[ERGEBNIS: Abgleich Erwartung/Ergebnis]]`.
- **Demo:** Wechsel zu ③ Pipeline: Anforderungen, CAD, Simulationen, Optimierung, Report in einer Kette; ergänzen: „Das gleiche läuft im Terminal ohne Oberfläche“. Danach zurück.

## Folie 17: [[EMPFEHLUNG]] Wahrscheinlich B-rep als Master und Voxel dort, wo Gitter und Kanäle entstehen

- **Layout:** Bild gross
- **Auf der Folie:** `fig08_hybrid_workflow.svg`. Daneben Entscheidungsregel in drei Zeilen:
  1. Muss das Teil bemasst, toleriert, gezeichnet oder als STEP übergeben werden? → **B-rep**
  2. Besteht das Teil im Kern aus Gitter, Kanal oder Feld? → **Voxel**
  3. Beides am selben Produkt? → **Hybrid**, Schnittstelle = Mesh
  Darunter: `[[EMPFEHLUNG: endgültige Wahl, erst nach Auswertung]]`
- **Sprechtext:** Zum Schluss die Empfehlung. Ich sage vorweg, dass die Gewichtung von den Ergebnissen abhängt, und ich skizziere die Entscheidungslogik so, wie ich sie heute erwarte. Erste Frage: Muss das Teil bemasst, toleriert oder als STEP übergeben werden? Dann brauchen wir B-rep. Das trifft auf die tragende Zelle zu, also Arme, Gondeln, Flossen, Rumpfrohre. Zweite Frage: Besteht das Teil im Kern aus Gitter, Kanal oder Feld? Dann ist Voxel im Vorteil, etwa bei Kühlluftführung im Rumpf. Wenn beides am selben Produkt vorkommt, ist ein Hybrid naheliegend: B-rep baut das Grundmodell parametrisch und exakt, und ein Voxel-Schritt ergänzt Gitter und Kanäle für den Druck. Die Schnittstelle dazwischen ist ein Mesh. Der Hinweis auf dem Bild ist wichtig: Der Rückweg vom Raster zum STEP ist nur als Mesh möglich, das heisst, die Wahrheitsquelle bleibt das Parametermodell. Ob wir wirklich beides brauchen, entscheidet `[[EMPFEHLUNG: Begründung mit Bezug auf B03, B07, B10, A03]]`. Die Alternativen sind reines B-rep, wenn wir keine Gitter oder Kanäle brauchen, und reines Voxel, wenn keine Zeichnungen und Toleranzen nötig sind und die Genauigkeit reicht.
- **Demo:** keine

## Folie 18: Nächste Schritte: ein Pilotbauteil, eine Schnittstelle, ein Agent-Test

- **Layout:** Inhalt (Liste mit Verantwortlichen und Terminen)
- **Auf der Folie:**
  1. Entscheidung über den Pipeline-Kern `[[EMPFEHLUNG]]` bis `[[TERMIN]]`
  2. Pilot: ein Bauteil mit Kühlluftführung im Rumpf, gebaut nach der gewählten Kette
  3. Agent-Test: ein KI-Agent löst dieselbe Aufgabe mit beiden Werkzeugen, Fehlerquote messen
  4. Mesh-Schnittstelle B-rep → Voxel in die Pipeline einbauen (falls Hybrid)
  5. Lücken schliessen: `[[ERGEBNIS: offene Punkte aus der Feature-Matrix]]`
- **Sprechtext:** Wie geht es weiter? Ich schlage vor, ein einziges Pilotbauteil komplett durch die gewählte Kette zu schicken, am besten eines mit Kühlluftführung, weil es die Stärken beider Ansätze berührt. Ausserdem möchte ich einen ehrlichen Agent-Test machen: Ein KI-Agent löst dieselbe Aufgabe mit beiden Werkzeugen, und wir messen, wie oft er beim ersten Versuch scheitert. Wenn wir einen Hybrid bauen, kommt die Mesh-Schnittstelle in die Pipeline. Und offene Punkte aus der Matrix schliessen wir nach Priorität. Ich freue mich auf Ihre Fragen, und ich zeige auch gern etwas noch einmal in der Demo.
- **Demo:** Fragerunde: Demo bereit halten (Modus ④ Vergleich)

---

# Backup-Folien

## Backup B1: Glossar (eine Seite)

- **Layout:** Tabelle (zwei Spalten)
- **Auf der Folie:** Die zwölf wichtigsten Begriffe mit je einer Zeile: B-rep, Voxel, Distanzfeld (SDF), Mesh/STL, STEP, CAD-Kern, Boolean, Fillet, Lattice, CFD, Headless, Skelett-Methode. Vollständig in `glossar.md`.
- **Sprechtext:** Falls ein Begriff gefallen ist, der nicht klar war: Hier steht er in einem Satz. Ausführlicher steht alles im Glossar zum Nachlesen.

## Backup B2: Benchmark-Aufgaben im Detail (B01 bis B10)

- **Layout:** Tabelle
- **Auf der Folie:** Spalten: ID, Aufgabe, B-rep-Status, Voxel-Status, Laufzeit B-rep, Laufzeit Voxel, Bemerkung. Alle `[[ERGEBNIS: B01]]` bis `[[ERGEBNIS: B10]]` mit den Aufgaben aus PLAN.md.
- **Sprechtext:** Die vollständige Tabelle. Bei den Zeilen mit „nicht unterstützt“ steht die Begründung in der Bemerkung.

## Backup B3: Feature-Matrix vollständig

- **Layout:** Tabelle
- **Auf der Folie:** Gesamte `spec/feature_matrix.json` (Feature × B-rep/Voxel, Status, Beleg). Ergänzt um A01 bis A05. `[[ERGEBNIS: Feature-Matrix vollständig]]`
- **Sprechtext:** Die Matrix mit allen Einträgen und dem jeweiligen Beleg. Wer eine Zeile anzweifelt, findet die Quelle.

## Backup B4: Grenzen der Untersuchung

- **Layout:** Inhalt
- **Auf der Folie:**
  - Ein Bauteil, ein Rechner, eine Version je Werkzeug `[[FAKT PRÜFEN: Versionen build123d 0.13.0, PicoGK]]`
  - Voxelgrösse als Parameter: Ergebnisse gelten für die geprüften Werte
  - Simulationen der Demo sind vereinfacht
  - Erfahrung mit build123d ist grösser als mit PicoGK (mögliche Verzerrung): Codezeilen und Agent-Erstversuch sind deshalb Hinweise, keine Beweise
- **Sprechtext:** Zur Einordnung der Ergebnisse. Ich habe ein Bauteil, einen Rechner und eine Softwareversion je Werkzeug verwendet. Ich habe mehr Erfahrung mit build123d als mit PicoGK. Das kann die Vergleichszahlen zu Gunsten von build123d verzerren, deshalb behandle ich Codezeilen und Agent-Erstversuche als Hinweise und nicht als Beweise.

## Backup B5: Hybrid-Workflow im Detail

- **Layout:** Bild gross
- **Auf der Folie:** `fig08_hybrid_workflow.svg`. Daneben Schnittstellen-Liste: Datenformat (STL/3MF), Einheiten (mm), Koordinatensystem (Z nach oben, Ursprung in der Trennebene), Voxelgrösse als Pipeline-Parameter, Prüfschritt (Volumen und Bounding-Box vor/nach).
- **Sprechtext:** Falls wir den Hybrid bauen: Wichtig ist, dass beide Werkzeuge dasselbe Koordinatensystem verwenden, dass die Einheiten stimmen und dass nach dem Übergang geprüft wird, ob Volumen und Umriss im Toleranzband liegen. Das ist ein kleiner, automatisierbarer Test.

## Backup B6: Bezugsgeometrie

- **Layout:** Tabelle
- **Auf der Folie:** Vier Körper aus `Mohammed_0.1 Full Shell.step`: Unterteil (Z 1171.5 bis 1305.5), Oberteil (1302.9 bis 1420.0), Nasenkappe (1502.0 bis 1602.7), Einsatz (1546.3 bis 1596.2). Inhalte kurz. `[[BILD: Vier Körper farbig]]`
- **Sprechtext:** Zur Referenz: vier geschlossene Körper. Wichtig für den Vergleich sind vor allem die schrägen Aero-Fins des Unterteils und die tropfenförmigen Gondeln des Oberteils, weil sie unsere Genauigkeitsfrage am besten zeigen.

## Backup B7: Wie wählt man die Voxelgrösse?

- **Layout:** Zwei Spalten
- **Auf der Folie:** Regel: Voxelgrösse höchstens 1/3 bis 1/5 des dünnsten wichtigen Details `[[FAKT PRÜFEN: Faustregel bestätigen, B07]]`; Beispiel Fin-Hinterkante; Tabelle Voxelgrösse → Zellenzahl → Speicher `[[ERGEBNIS: B10]]`. Grafik: `fig07_genauigkeit_vs_voxelgroesse.svg`.
- **Sprechtext:** Für die Praxis: Die Voxelgrösse legt man nicht nach Gefühl fest, sondern aus dem dünnsten Detail und der geforderten Toleranz. Das ist in der Pipeline ein Parameter wie jeder andere, und ein Agent kann ihn selbst wählen, wenn wir ihm die Regel geben.

---

# Register der Platzhalter

Alle Muster mit `[[` sind zu ersetzen. Nach Themen:

| Platzhalter | Folie(n) | Quelle |
|---|---|---|
| `[[BILD: Boreas-Gesamtansicht B-rep / Voxel]]` | 1 | GUI Modus ④ |
| `[[BILD: Oberteil B-rep / Voxel]]` | 7 | GUI Modus ④ |
| `[[BILD: Zeichnung A3 aus Werkbank]]` | 14 | Werkbank |
| `[[BILD: V01 Gitter, V02 Kühlkanal]]` | 15 | Voxel-Modell |
| `[[BILD: Vier Körper farbig]]` | B6 | tools/render_views.py |
| `[[ERGEBNIS: B01]]` bis `[[ERGEBNIS: B10]]` | 11, 12, 13, B2 | bench/results/latest |
| `[[ERGEBNIS: B07 Genauigkeit vs. Voxelgrösse]]` | 12, B7 | B07 |
| `[[ERGEBNIS: B10 Speicher/Laufzeit vs. Voxelgrösse]]` | 12, 13, B7 | B10 |
| `[[ERGEBNIS: R01]]` bis `[[ERGEBNIS: R04]]` | 11, 14, B3 | feature_matrix.json |
| `[[ERGEBNIS: V01]]` bis `[[ERGEBNIS: V04]]` | 11, 15, B3 | feature_matrix.json |
| `[[ERGEBNIS: A01]]` bis `[[ERGEBNIS: A05]]` | 16, B3 | docs/ (Recherche), Messung |
| `[[ERGEBNIS: Kernaussage Ziel 1 und 2]]` | 11 | Auswertung |
| `[[ERGEBNIS: Faustregel Voxelgrösse zu kleinstem Detail]]` | 12, B7 | B07 |
| `[[ERGEBNIS: Abgleich Erwartung/Ergebnis]]` | 16 | Auswertung |
| `[[ERGEBNIS: offene Punkte aus der Feature-Matrix]]` | 18 | Auswertung |
| `[[ZAHL: …]]` (Voxelgrösse, Fehler, Zeiten) | 12, 13 | B07, B03, B10 |
| `[[FAKT PRÜFEN: A05 Lizenz, Herkunft, Basis]]` | 6 | Recherche |
| `[[FAKT PRÜFEN: A01 Speicherverhalten PicoGK]]` | 12 | Recherche + B10 |
| `[[FAKT PRÜFEN: Versionen …]]` | B4 | Ergebnisdateien (`tool_version`) |
| `[[FAKT PRÜFEN: Faustregel bestätigen, B07]]` | B7 | B07 |
| `[[EMPFEHLUNG: …]]` | 17, 18 | nach Auswertung |
| `[[TERMIN]]` | 18 | Lucas |

Auch in `figures/fig07_genauigkeit_vs_voxelgroesse.svg` steht ein Hinweis auf B07 und B10 (Schema, wird ersetzt).
