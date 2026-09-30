# Befunde aus der Umsetzung (build123d vs. PicoGK)

Stand 30.09.2026. Beobachtungen beim Bau desselben Modells (Spec `spec/boreas_spec.json`, 81 Parameter in 10 Gruppen)
in beiden Werkzeugen. Zahlen aus den Selbsttests (`bench/results/*_selftest`) bzw. dem Benchmark-Lauf
(`bench/results/latest`, Auswertung `summary.md`). Material- und Anforderungswerte sind Mock-Daten.

## Gleich

- **Aufwand fürs Modell:** 782 Codezeilen (build123d) gegen 781 (PicoGK) für Spec-Leser, Skelett, 9 Gruppen und Baugruppe.
  Die Werkzeuge kosten beim Modellieren gleich viel Code; der Unterschied liegt darin, was danach geht.
- **Gleiche Geometrie:** Volumen je Teil stimmen auf 0.25 % (Oberteil), 0.3 % (Nase), 2.2 % (Unterteil) überein, Bounding
  Boxes auf ±0.4 mm (Voxel 0.5 mm). Beide Netze sind dicht.
- **Skelett-Methode funktioniert in beiden:** Test `brep/tests/test_groups.py`: Für jeden Parameter jeder Gruppe (ausser
  Skelett) ändern sich nur die Features dieser Gruppe. Der Runner prüft dasselbe für beide Werkzeuge (B03).
- **Beide headless und per CLI steuerbar,** identischer Aufrufvertrag (PLAN.md), JSON rein und raus.

## B-rep (build123d 0.13 / OCCT 8.0.1): Stärken

- Exakte Profile: Tropfenprofil der Fins weicht 0.0009 mm von der Formel ab (Schnitt bei halber Spannweite).
- Native STEP-Rundreise ohne Volumenverlust; STEP-Import der Shapr3D-Referenz in 4.4 s mit allen 447 exakten Flächen.
- Bemasste A3-Zeichnung, Selektoren (Kanten/Flächen nach Typ und Lage), Joints/Baugruppe, exaktes Nachmessen des
  Passungsspiels (Spalt skaliert exakt mit dem Parameter).
- Kleiner Speicherbedarf: ~0.6 GB Spitze, Modellaufbau ~5.5 s.

## B-rep: Schwächen und Stolpersteine (wichtig für KI-Agents: mehrere davon scheitern *still*)

1. **Falsches Ergebnis ohne Fehlermeldung:** `fuse()` mit vielen Körpern auf einmal lieferte 2 Körper und 44'090 statt
   303'579 mm³ (Kiele + Heckflossen am Kegel). Nacheinander vereinigt stimmt es. Nur durch Volumenkontrolle bemerkt.
2. **Löcher im STL:** Einzelne Freiformflächen werden bei 0.02 mm Toleranz nicht trianguliert ("1 face skipped") →
   Netz nicht dicht. Workaround: automatisch mit 0.002 mm neu vernetzen.
3. **Verrundungen:** 5 von 6 Fillet-Versuchen an Gondel-Übergang und Heckflossen-Wurzel scheitern (ValueError).
4. **Offset/Schale:** Offset auf das fertige Ober-/Unterteil scheitert; die Gondel-Schale scheitert bei 1.5 mm Wand
   (StdFail_NotDone) → analytischer Rückfallweg nötig.
5. **Gitter:** 423 Stäbe (Zelle 8 mm) → 39 s und **leeres** Ergebnis; 125 Stäbe 6 s. TPMS/Gyroid nicht machbar.
6. **Boolean auf Netzdaten:** Importiertes Referenz-STL ist kein gültiger Körper, Bool schlägt fehl.
7. API-Drift: `Wire([Polyline(...)])` wirft `Standard_TypeMismatch` in 0.13 (Polyline ist bereits ein Wire).

## Voxel (PicoGK 2.3.0 / .NET 9): Stärken

- **Booleans, Offsets, Schalen, Verrundungen scheitern nie:** Schale auf jedem Körper (auch ganzes Oberteil) < 1 s,
  Fillet r = 0.4…3 mm auf ganzen Teilen 1–4 s.
- **Gitter und Kanäle:** Gyroid-Infill im Unterteil 1.6 s, 3'456-Stab-Gitter 0.18 s, 4 verzweigte Kühlkanäle 0.09 s.
- **Feldgesteuerte Wand** (1.2 → 3.5 mm über die Höhe) als eine Formel; Bool auf offenem Referenz-STL funktioniert
  nach dem Rastern ohne Reparatur, Ergebnis dicht.
- Direkter Druckexport als CLI-Schichtdatei (60 µm), Strömungsgebiet direkt als Voxelgitter (LBM-tauglich).

## Voxel: Schwächen und Stolpersteine

1. **Kein STEP, keine Zeichnung, keine Kanten/Flächen, keine Toleranzen** – Austausch nur STL/VDB.
2. **Speicher:** ~2.5 GB Spitze bei 0.5 mm (B-rep 0.6 GB); Strömungsgebiet bei 0.5 mm: 9.4 GB RAM, 300 MB VDB und –
   als STL – 74 Mio. Dreiecke / 3.7 GB (unbrauchbar). Netze der Teile 2 Mio. Dreiecke (~90 MB STL).
3. **Falsche Werte der Bibliothek:** `CalculateProperties` liefert bei Hohlkörpern das Volumen inkl. Hohlraum
   (Kugelschale 112'845 statt 21'142 mm³); `voxShell(neg,pos,smooth)` liefert massiv statt hohl; `IntersectImplicit`
   stürzt unter ~0.34 mm Voxel nativ ab. → Kennwerte immer selbst aus dem Netz rechnen.
4. **Beispiele veraltet:** Offizielle Beispiele nutzen noch die 1.7-API (`Library.Go`, globale Bibliothek); 2.x
   braucht eine Library-Instanz. Kein `llms.txt`.
5. **Plattform:** Offiziell nur Windows x64 und macOS arm64 – kein Linux (Server/CI/Cloud) ohne Eigenbau.
   .NET 9 wird nur bis 10.11.2026 unterstützt (Wechsel auf .NET 10 nötig).
6. Performance-Falle im eigenen Code: Die Dichtheitsprüfung mit `Dictionary<long,…>` (Kantenschlüssel `lo<<32|hi`)
   war wegen schlechter Hash-Streuung quadratisch (> 10 min statt 1 s). Hat nichts mit PicoGK zu tun, zeigt aber: bei
   Millionen Dreiecken rächen sich naive Datenstrukturen.

## Aerodynamik und Kühlung

- **Aussenströmung (CFD):** B-rep liefert STEP (Gmsh/ANSYS) und STL (snappyHexMesh) der exakten Form; das
  Strömungsgebiet als exakter Körper (Quader − Drohne) entsteht in Sekunden. Voxel liefert das Gebiet direkt als
  kartesisches Gitter – ideal für Lattice-Boltzmann, aber Speicher wächst mit (Voxelgrösse)⁻³ im Gebiet.
- **Lizenzfalle:** FluidX3D (bekanntester GPU-LBM-Löser) verbietet kommerzielle und militärische Nutzung.
- **Kühlluft im Rumpf:** Einzelner Sweep-Kanal geht in B-rep; Netze aus Kanälen mit Verzweigungen/Übergängen sind in
  Voxel trivial.
