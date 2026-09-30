# Recherche: PicoGK (LEAP 71)

Stand: 30.09.2026. Alle Zahlen sind mit Datum belegt; "gelesen" heisst: im Quellcode oder in der Doku nachgelesen, "nicht ausgeführt" heisst: auf diesem Rechner (noch) nicht getestet, weil das .NET-SDK fehlt. Ausgeführte Messungen kommen erst mit dem Benchmark (Welle 2/3).

## 1. Kurzprofil

| Punkt | Befund | Quelle |
|---|---|---|
| Was | "Compact and robust geometry kernel for Computational Engineering", Voxel-Kernel (Level-Set / Signed Distance Field) als dünne Schicht auf OpenVDB | https://picogk.org/doc/internals.html |
| Hersteller | LEAP 71 (Dubai). Autor und Hauptentwickler Lin Kayser; Nebenautorin Josefine Lissner (ShapeKernel, LatticeLibrary) | https://picogk.org/doc/ |
| Aktuelle Version | PicoGK 2.3.0, NuGet veröffentlicht 04.08.2026 (GitHub-Release 05.08.2026), Runtime "26.2", Ziel `net9.0` | https://www.nuget.org/packages/PicoGK , https://github.com/leap71/PicoGK/releases |
| Lizenz | Apache-2.0 (kommerzielle Nutzung erlaubt, keine Zusatzklauseln) | https://github.com/leap71/PicoGK/blob/main/LICENSE |
| Sprache | C# (.NET 9). Native C++-Runtime (`PicoGKRuntime`, `extern "C"`-Schnittstelle) | https://github.com/leap71/PicoGKRuntime |
| Plattform (offiziell) | Windows x64 und macOS Apple Silicon (arm64). Kein Linux im offiziellen NuGet-Paket | https://picogk.org/doc/setup.html , `PicoGK.csproj` (gelesen: `runtimes/win-x64`, `runtimes/osx-arm64`) |
| Community | GitHub 1'121 Sterne, 189 Forks, 62 Beobachter (30.09.2026); NuGet 34'500 Downloads gesamt, 1'500 für 2.3.0 | https://github.com/leap71/PicoGK , NuGet |
| Contributors | Nur 4 im Hauptrepo; 321 von rund 330 Commits von einer Person (LinKayser) | GitHub-API `contributors` (30.09.2026) |
| Issues | GitHub-Issues sind deaktiviert; Support läuft über Discussions und Pull Requests (3 offene PRs) | GitHub-API `has_issues=false` |

## 2. Kernel und Darstellung

- Ein Körper (`Voxels`) ist ein **Level-Set / Signed-Distance-Feld auf einem gleichmässigen Gitter** in einem dünnen Band um die Oberfläche (OpenVDB, "narrow band" von Standard 3 Voxeln, siehe PicoGKRuntime-Issue #26). Es gibt keine Kanten, Flächen oder Features, nur Abstand zur Oberfläche.
- **Eine globale Voxelgrösse pro `Library`-Instanz** (z. B. 0.25 mm). Alle Felder einer Instanz teilen sie. Sie ist der zentrale Regler für Genauigkeit, Rechenzeit und Speicher.
- Koordinaten und Vektoren sind 32-bit-Float (`System.Numerics.Vector3`). Bei Bauteilen von rund 1 m Länge und 0.1 mm Auflösung liegt man nahe an der Float-Genauigkeit (Hinweis, keine Messung).
- Weitere Typen: `Mesh` (Dreiecksnetz), `Lattice` (Balken und Kugeln), `PolyLine`, `ScalarField`, `VectorField` (beide auf OpenVDB-Basis, seit 1.5.0 für die Kopplung mit Simulationen), `OpenVdbFile`.
- Geplante Nachfolge: `PicoGK.Core` (Repo, C++ plus .NET 10 / C# 14, "Early development - do not use yet", Versionen `3.0.0-alpha.*`). Höheres (Gitter, Sweeps) soll aus dem Kern nach oben wandern. Für die Kernwahl heisst das: PicoGK 2.x ist stabil-aktiv, aber ein Generationswechsel ist angekündigt. Quelle: https://github.com/leap71/PicoGK.Core

## 3. Modellieroperationen (gelesen in `Base/Voxels.cs`, Version 2.3.0)

| Gruppe | Funktionen |
|---|---|
| Primitive | `voxSphere`, `voxLatticeBeam` (konischer Balken), `Utils.mshCreateCube`, Mesh-Erzeugung von Zylinder/Kegel/Kugel |
| Booleans | `BoolAdd`, `BoolSubtract`, `BoolIntersect`, Operatoren `+`, `-`, `&`, `voxCombineAll`, `Trim(BBox3)` |
| Offsets | `Offset(±mm)`, `DoubleOffset`, `TripleOffset` = `Smoothen`, `OverOffset`, `Fillet(r)` (= `OverOffset(r)`), `voxShell(offset)`, `voxShell(neg, pos, smooth)` |
| Eingabe | `Voxels(Mesh)` bzw. `RenderMesh` (Mesh muss geschlossen sein), `RenderImplicit(IImplicit, BBox3)`, `IntersectImplicit(IImplicit)`, `RenderLattice(Lattice)`, `voxMeshShell`, `ProjectZSlice` |
| Abfragen | `bIsInside`, `vecSurfaceNormal`, `bClosestPointOnSurface`, `bRayCastToSurface`, `oCalculateBoundingBox`, `CalculateProperties` (nur **Volumen + Bounding Box**), `bIsEqual` |
| Slices | `GetVoxelSlice`, `GetInterpolatedVoxelSlice` (nicht ganzzahlige Z), `oVectorize` (Marching Squares, Polygone je Schicht) |

Bemerkungen:

- `Fillet` und `Smoothen` wirken **global** auf alle Kanten (Offset nach aussen dann innen, entfernt Details unterhalb des Radius). Selektives Verrunden einzelner Kanten gibt es nicht. Quelle: Kommentare in `Voxels.cs`.
- Schwerpunkt, Trägheitstensor, Oberfläche: **nicht vorhanden** (im heruntergeladenen Quellcode keine Treffer für inertia/centroid). Volumen läuft über `CalculateProperties`, das intern Voxels → Mesh → Voxels wandelt und dann Voxel zählt (Kommentar im Code: nötig wegen "spurious surface voxels").
- **Offene Fehler in 2.3.0 (gelesen, noch nicht ausgeführt)**, alle mit offenem Fix-PR oder Issue:
  1. `voxShell(neg, pos, smooth)` liefert nur die massive äussere Offset-Hülle, weil Rückgabewerte verworfen werden. Die Variante mit einem Argument ist korrekt. PR #119 (28.09.2026) https://github.com/leap71/PicoGK/pull/119 . Workaround: `voxOffset(pos) - voxOffset(neg)`.
  2. `Voxels.bIsInside` lieferte auf Linux immer `true` (Marshalling von `bool`). PR #115 (25.09.2026), unter Windows/macOS nicht getestet. https://github.com/leap71/PicoGK/pull/115
  3. `IntersectImplicit` bricht bei Voxelgrösse unter rund 0.34 mm mit einer nicht abfangbaren nativen Ausnahme ab (Prozess stirbt); `ProjectZSlice` erzeugt unter rund 0.17 mm offene Netze. PicoGKRuntime-Issue #26 mit unabhängiger Bestätigung vom 12.09.2026, Fix-PR #28 noch offen. https://github.com/leap71/PicoGKRuntime/issues/26
  4. Speicherüberwachungs-Timer (`nTotalMemUsage`) kann Heap beschädigen, ca. 1 % Abstürze in Batch-Läufen unter CPU-Überlast (Linux). PicoGKRuntime-Issue #31 (28.09.2026). https://github.com/leap71/PicoGKRuntime/issues/31
  5. Native Ausnahmen laufen über die C-Schnittstelle nach aussen und beenden den Prozess (Issue #27).

  Konsequenz für den Benchmark: Gitter/TPMS über `IntersectImplicit` (V01) mit dem geplanten Standard `--voxel 0.25` **läuft voraussichtlich in den Abbruch**. Auf 0.35 mm ausweichen oder Gitter über `Lattice`/`RenderImplicit` bauen und beides dokumentieren.

## 4. Formate: Import, Export

Aus `IO/*.cs` (gelesen):

| Format | Lesen | Schreiben | Bemerkung |
|---|---|---|---|
| STL binär | ja (`Mesh.mshFromStlFile`, mit Einheitenwahl) | ja (`SaveToStlFile`) | ASCII-STL laden: **nicht implementiert** (wirft `NotImplementedException`) |
| OpenVDB `.vdb` | ja | ja (Voxels, ScalarField, VectorField, Metadaten) | Nur Level-Set-Grids; OpenVDB seit 2.2.0 auf V13 |
| CLI (Slice-Austausch, LPBF) | ja (ASCII und binär) | ja (ASCII) | seit 1.7.0, für EOS-artige Drucker |
| TGA (Bilder/Slices) | ja | ja | dazu Skia-Bitmaps (PNG etc. über SkiaSharp) |
| CSV | - | ja | Hilfsklasse |
| **STEP / IGES / BREP** | **nein** | **nein** | Kein B-rep im Kernel |
| **3MF / OBJ / PLY** | **nein** | **nein** | Wunsch für 3MF offen (LatticeLibrary-Issue #3 vom 17.05.2024) |
| DXF / SVG / PDF | nein | nein | Slices als Bild oder Polygone, keine Zeichnungsableitung |

Für die Referenzgeometrie heisst das: `Mohammed_0.1 Full Shell.step` muss ausserhalb von PicoGK zu **binärem STL** gewandelt werden (z. B. mit build123d `export_stl`, lokal gemessen 0.18 s, 3.6 MB bei 0.05 mm Toleranz). Erst dann kann `Voxels(Mesh)` es lesen. Die Meshes müssen geschlossen (wasserdicht) sein.

## 5. Installation und Headless-Betrieb

Siehe `docs/install_picogk.md`. Kurzfassung:

- Seit 1.7.7.5 (05.08.2025) nur noch **NuGet-Paket**, der Installer ist eingestellt. Paket enthält die nativen DLLs (`picogk.26.2.dll`, `tbb12.dll`, `blosc.dll`, `lz4.dll`, `z.dll`, `zstd.dll`), Paketgrösse 21.4 MB, einzige Abhängigkeit SkiaSharp 3.119.0.
- **Headless seit 1.6.0** (23.05.2024): `using var lib = new Library(voxelSizeMm);` statt `Library.Go(...)`. `Library.Go` startet immer das OpenGL-4.1-Fenster (Viewer). Im Headless-Betrieb gibt es weder Viewer noch Logdatei. Das ist ausdrücklich für Parameter-Sweeps gedacht. Quelle: https://github.com/leap71/PicoGK/discussions/30
- Seit 2.0.0 sind Objekte an eine `Library`-Instanz gebunden (`new Voxels(lib)`, `Voxels.voxSphere(lib, ...)`). Die Kurzformen ohne `lib` in `GlobalObjects.cs` greifen auf die global registrierte Bibliothek zu (`Library.RegisterGlobalLibrary`, wird von `Library.Go` gesetzt). Wichtig für KI-Agents: das offizielle Beispiel-Repo `PicoGK_Examples` nutzt noch PicoGK **1.7.7.4** und die globale Kurzform.

## 6. Ökosystem: ShapeKernel, LatticeLibrary, Weiteres

| Repo | Inhalt | Stand |
|---|---|---|
| `LEAP71_ShapeKernel` | BaseShapes (Box, Cylinder, Cone, Sphere, Ring, Lens, Pipe, PipeSegment, Revolve), LocalFrame/Frames, Splines (Control-Point-, Tangential-, Cylindrical-), Line- und Surface-Modulationen (variable Radien/Dicken), LatticeManifold/LatticePipe, ImplicitUtility (SuperEllipsoid, Gyroid), Mesh-Painter, Messfunktionen. Wird als **Quellcode** eingebunden (ZIP oder Git-Submodul), kein NuGet | 307 Sterne, 73 Forks, letzter Push 10.08.2026, 3 offene Einträge (1 Issue zu gebogenen Pipe-Segmenten, 2 PRs). Einziges Release v1.0.0 (17.10.2023) |
| `LEAP71_LatticeLibrary` | Zellarrays (regulär, **konform** auf Box/Lens/PipeSegment), Gittertypen (BodyCentre, Octahedron, RandomSpline), 4 Balkendicken-Strategien (konstant, zellbasiert, globale Funktion, **randabstandsbasiert**); **Implicit Library** mit TPMS (Schwarz Primitive, Schwarz Diamond, Lidinoid, Radial Gyroid, Split-Wall/Void-Gyroid, randomisiert, modulare Presets) | 79 Sterne, letzter Push 27.07.2025 |
| `LEAP71_HelixHeatX` | Wendel-Wärmetauscher als Referenzprojekt | 84 Sterne, Push 23.03.2026 |
| `PicoGK_SimulationExample` | Austausch mit Simulation über Skalar/Vektorfelder in VDB | 34 Sterne, Push 02.12.2024 |
| Weitere | RoverWheel, QuasiCrystals, PicoGK-Fasteners (Dritte), PicoGH (Grasshopper-Wrapper, Dritte) | siehe https://github.com/leap71 |

Der ShapeKernel deckt **keine** Profilbibliothek (NACA o. ä.) ab. Tropfenprofile für Fins und Gondeln müssen über Konturen/Splines (`BaseRevolve`, `BaseLens`, `LineModulation`) oder eine eigene `IImplicit`-Funktion gebaut werden. Das ist der Hauptaufwand für B04 (Hypothese, in Welle 2 zu bestätigen).

## 7. Python-Zugang (geprüft, nicht angenommen)

- **Offiziell: keiner.** Maintainer Lin Kayser (Mai bis August 2026): bewusste Entscheidung für C# (Performance, starke Typisierung, klare Architektur). Quelle: https://github.com/leap71/PicoGK/discussions/26
- **Community, ohne Verbindung zu LEAP 71:**
  - **PicoPie** (`pip install picopie`, aktuell 0.7.0 vom 02.07.2026; 10 Sterne). Bindet dieselbe native Runtime (OpenVDB 13, PicoGK 26.2) per ctypes, NumPy-freundliche API, Wheels für CPython 3.10 bis 3.13 auf Windows x64, macOS arm64 **und Linux x86-64**. Kein .NET nötig. https://github.com/Borderliner/PicoPie , https://pypi.org/project/picopie/
  - **PycoGK** (`pip install pycogk`, 0.3.0 vom 17.03.2026; 8 Sterne). Setzt ShapeKernel-, LatticeLibrary- und Implicit-Library-Ports auf, Viewer über `vedo`, Python >= 3.11, Runtime nur win-x64/osx-arm64. https://github.com/ghedo44/PycoGK
- Beide sind Beta, klein und nicht unterstützt. PicoPie hat die oben genannten Runtime-Fehler (#26, #27) gefunden und patcht sie beim Build. **Einschätzung:** als Beobachtung interessant, für eine Pipeline mit Verantwortung heute nicht als Basis empfohlen. Nicht ausgeführt (fremde native Binärpakete wurden bewusst nicht installiert).

## 8. Genauigkeitsmodell

- Die Oberfläche liegt im Feld zwischen Gitterpunkten und wird per Interpolation extrahiert. Praktisch gilt: **Formfehler in der Grössenordnung eines halben Voxels**, kleine Merkmale unter 2 bis 3 Voxel Ausdehnung verschwinden oder verrunden (Wandstärke, Hinterkante eines Tropfenprofils). Hypothese für B07: Volumenfehler fällt mit der Voxelgrösse ungefähr linear bis quadratisch.
- Scharfe Kanten werden immer leicht verrundet (etwa im Bereich eines Voxels). Ein Sollmass aus dem Modell (z. B. Bohrung 5.000 mm) ist nach dem Export nur auf etwa Voxelgrösse genau.
- Volumen: Voxelzählung, keine Fläche/Schwerpunkt (siehe Abschnitt 3).
- Für **Zeichnung, Passung, Toleranz** ist das ungeeignet, für **Strömungspfade, Gitter, Wandstärkenfelder** reicht es.

## 9. Performance und Speicher

- Speicher folgt der **Oberfläche**, nicht dem Volumen (sparse VDB): ungefähr proportional zu Fläche / Voxelgrösse². Halbiert man die Voxelgrösse, wächst der Speicher grob um Faktor 4 und die Rechenzeit der Booleans/Offsets grob um Faktor 4 bis 8 (Abschätzung aus der Datenstruktur, im Benchmark B10 zu messen).
- Mehrkern: OpenVDB nutzt Intel TBB (`tbb12.dll` liegt bei), also parallele Voxeloperationen.
- `Library` meldet Speicher pro Objekttyp (`nVoxelsMemUsage()` usw.), praktisch für B10.
- Praxisbeleg eines Dritten: rund 1'300 Verifikationsläufe pro Stunde auf einem 32-Thread-Linux-Knoten mit 16 Prozessen parallel (PicoGKRuntime PR #30, 28.09.2026). Nur als Grössenordnung, nicht vergleichbar mit unserer Geometrie.
- Grosse Bauteile mit feiner Auflösung sind der Engpass (z. B. rund 1 m Länge bei 0.1 mm wären etwa 10^4 Voxel je Achse). Genaue Grenzen misst B10.

## 10. Visualisierung

- Eingebauter OpenGL-4.1-Viewer (GLFW, Dear ImGui), mit Schnittansichten (`VoxCutViz`), Slice-Ansicht, Überhang-Warnung (`Overhang`-Datentyp seit 2.2.0), Animationen und Zeitraffer. Er läuft nicht im Headless-Modus.
- 2.2.0 (05.06.2026) behob Viewer-Abstürze bei Windows-Rechnern mit Hybridgrafik (dieser Rechner hat NVIDIA + Intel, siehe install-Doku).
- Für die GUI dieses Projekts genügt binäres STL, das der Web-Viewer lädt.

## 11. Reife, Release-Rhythmus, Dokumentation

- Releases seit Oktober 2023: 1.0 (17.10.2023) bis 1.7.7.5 (05.08.2025), dann Pause und 2.0.0 (21.04.2026), 2.1.0 (25.05.2026), 2.2.0 (05.06.2026), 2.3.0 (05.08.2026). Rhythmus 2026: etwa monatlich bis zweimonatlich, mit **Breaking Changes** auch in Minor-Versionen (2.3.0: `Rad` statt `float` für Winkel; 2.0.0: Library-Instanzen).
- Sehr kleines Kernteam, stark firmengetrieben (LEAP 71 baut damit eigene Produkte, z. B. Raketentriebwerke). Quelle: https://leap71.com/2024/06/18/leap-71-hot-fires-3d-printed-liquid-fuel-rocket-engine-designed-through-noyron-computational-model/
- Dokumentation: Seiten `picogk.org/doc` (Getting started, Setup, Internals), XML-Doc-Kommentare im Code (sehr ausführlich, gute Grundlage für Agents), Buch "Coding for Engineers" (Kapitelweise, https://picogk.org/coding-for-engineers/), GitHub Discussions. Im Beispiel-Repo liegen nur zwei Beispiele (`HelloWorld`, `BooleanShowCase`). Kein `llms.txt` (404 am 30.09.2026).
- Hacker-News-Diskussion (April 2024): API "könnte Feinschliff vertragen", Beispiele fast nur für 3D-Druck ausgelegt (Fertigung durch Zerspanung kaum adressiert). https://news.ycombinator.com/item?id=40034563

## 12. Eignung für KI-Agents (Einschätzung, A03)

| Aspekt | Befund | Wirkung |
|---|---|---|
| Sprache | C# ist stark trainiert, aber das Namensschema (`voxBoolAdd`, `vecSurfaceNormal`, `nAddTriangle`, ungarische Notation) ist eigen | mittel |
| Typisierung | Statisch getypt, Compiler fängt Tippfehler und falsche Typen früh ab. Guter Rückkanal für Agents | positiv |
| API-Drift | Beispiele und Blogs im Netz nutzen 1.x-Globals (`Voxels.voxSphere(vec, r)`), 2.x verlangt `Library`. Trainingsdaten sind gemischt | negativ |
| Menge an Beispielen | Wenig öffentlicher Code, ShapeKernel-Beispiele vorhanden, Dritt-Repos klein (4 bis 10 Sterne) | negativ |
| Fehlermeldungen | Native Fehler sind "usually devoid of real information" (Kommentar im Code von `GlobalInstance`); harte Abbrüche durch native Ausnahmen (Issue #27) | negativ |
| Dokumentation | Kompakt, XML-Kommentare gut, kein `llms.txt` | mittel |
| Build-Zyklus | `dotnet build` je Änderung (Sekunden), danach Lauf | leicht langsamer als Python |
| Bekannte Fallen | 3-Argument-`voxShell`, `IntersectImplicit` bei feiner Auflösung, `bIsInside` | Agent muss diese Liste kennen |

Fazit: Agents können PicoGK-Code schreiben, brauchen aber eine Projektregel-Datei (API-Version 2.3.0, headless-Muster, Fallenliste) und Testläufe. Das ist einmaliger Aufwand.

## 13. Bekannte Einschränkungen (Zusammenfassung)

1. Kein STEP/IGES, kein 3MF, kein DXF/SVG. Austausch nur über binäres STL, VDB, CLI, TGA.
2. Keine Topologie: keine Kanten/Flächen-Selektion, keine Zeichnungsableitung, keine Baugruppen/Joints/Constraints.
3. Toleranzen kleiner als die Voxelgrösse sind nicht darstellbar; Kanten sind immer leicht verrundet.
4. Keine Masseneigenschaften ausser Volumen und Bounding Box (Schwerpunkt/Trägheit selbst berechnen).
5. Offizielle Plattformen: Windows x64, macOS arm64. Linux nur über selbst gebaute Runtime (PR #90 und #30 offen).
6. Die in Abschnitt 3 genannten offenen Fehler (`voxShell` 3-Arg, `IntersectImplicit` unter 0.34 mm, `bIsInside`).
7. Kleines Kernteam, Generationswechsel (`PicoGK.Core`, .NET 10) angekündigt.
8. .NET 9 ist STS: Support endet am 10.11.2026 (Microsoft, https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core). PicoGK 2.3.0 zielt auf `net9.0`, läuft aber laut Microsoft-Kompatibilitätsregeln auch aus einem .NET-10-Projekt heraus (nicht ausgeführt).

## Quellen

- https://github.com/leap71/PicoGK (Repo, Release-Notes, `PicoGK.csproj`, `Base/Voxels.cs`, `IO/*.cs`, `Library/*.cs`)
- https://github.com/leap71/PicoGK/releases
- https://www.nuget.org/packages/PicoGK
- https://picogk.org/doc/ , https://picogk.org/doc/setup.html , https://picogk.org/doc/internals.html
- https://github.com/leap71/PicoGK/discussions/30 (headless), https://github.com/leap71/PicoGK/discussions/26 (Python)
- https://github.com/leap71/PicoGKRuntime (Issues #26, #27, #30, #31)
- https://github.com/leap71/PicoGK/pull/115 , https://github.com/leap71/PicoGK/pull/119 , https://github.com/leap71/PicoGK/pull/90
- https://github.com/leap71/PicoGK.Core
- https://github.com/leap71/LEAP71_ShapeKernel , https://github.com/leap71/LEAP71_LatticeLibrary , https://github.com/leap71/PicoGK_Examples
- https://github.com/Borderliner/PicoPie , https://pypi.org/project/picopie/ , https://github.com/ghedo44/PycoGK , https://pypi.org/project/pycogk/
- https://news.ycombinator.com/item?id=40034563
