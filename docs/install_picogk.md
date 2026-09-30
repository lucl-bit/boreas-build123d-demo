# Installation PicoGK unter Windows 11 (headless, Konsolenprojekt)

Stand: 30.09.2026. Geprüft heisst: Paket-ID, Version und Quelltext gelesen bzw. per `winget show` abgefragt. **Nicht ausgeführt**: Auf diesem Rechner ist noch kein .NET-SDK installiert (`dotnet` nicht gefunden), die Installation ist Sache des Voxel-Agents/der Koordination. Der Snippet unten wurde gegen den Quelltext von PicoGK 2.3.0 geprüft, aber noch nicht kompiliert.

## 1. Voraussetzungen (Rechner geprüft)

| Punkt | Befund |
|---|---|
| Betriebssystem | Windows 11 Pro 10.0.26200, x64. PicoGK liefert nativ nur `win-x64` und `osx-arm64` mit (offizielles NuGet) |
| VC++-Laufzeit | `vcruntime140.dll`, `msvcp140.dll`, `vcruntime140_1.dll` in Version 14.50.35719.0 sind bereits vorhanden. Falls trotzdem `DllNotFoundException` auftritt: `winget install --id Microsoft.VCRedist.2015+.x64 -e` (ID geprüft, 14.51.36247.0). Ob die PicoGK-DLL selbst die VC++-Laufzeit braucht, konnte ohne Herunterladen der DLL nicht belegt werden. Es ist bei einer mit MSVC gebauten OpenVDB-DLL wahrscheinlich, deshalb der Hinweis |
| Grafik | Nur für den Viewer relevant (`Library.Go`), OpenGL 4.1 Core. Headless nicht nötig. Rechner hat NVIDIA + Intel (Hybridgrafik); PicoGK 2.2.0 hat dafür einen Viewer-Absturz behoben |
| Speicher | 31.6 GB RAM, i7-13700HX (24 Threads) |

## 2. .NET SDK installieren

```powershell
winget install --id Microsoft.DotNet.SDK.9 -e --source winget
```

- Paket-ID `Microsoft.DotNet.SDK.9` geprüft mit `winget show`: Version 9.0.318, Publisher Microsoft, Lizenz MIT (30.09.2026).
- **Wichtig:** .NET 9 ist STS-Version, der Support endet am **10.11.2026** (https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core). Für neue Projekte ist .NET 10 (LTS bis 14.11.2028) im Katalog (`Microsoft.DotNet.SDK.10`, 10.0.401). PicoGK 2.3.0 zielt auf `net9.0`; ein `net10.0`-Projekt darf es referenzieren (nicht ausgeführt). Der PicoGK-Doku-Stand ist .NET 9 ("we use version 9.0", https://picogk.org/doc/setup.html). Empfehlung: SDK 9 wie in der Doku installieren, das Projekt auf `net9.0` festlegen und den Wechsel auf .NET 10 bewusst als eigenen Schritt nach dem ersten grünen Benchmark planen.
- Neues Terminal öffnen (PATH), dann prüfen:

```powershell
dotnet --list-sdks
dotnet --version
```

## 3. Konsolenprojekt anlegen

```powershell
cd C:\Users\Aeolos-04\Desktop\boreas\builder123d
dotnet new console -n voxel -f net9.0 -o voxel
cd voxel
dotnet add package PicoGK --version 2.3.0
```

Ergebnis in `voxel\voxel.csproj` (oder von Hand so schreiben):

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net9.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <PlatformTarget>x64</PlatformTarget>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="PicoGK" Version="2.3.0" />
  </ItemGroup>
</Project>
```

- Das NuGet-Paket (21.4 MB, Apache-2.0) enthält die nativen DLLs unter `runtimes/win-x64/native` (`picogk.26.2.dll`, `tbb12.dll`, `blosc.dll`, `lz4.dll`, `z.dll`, `zstd.dll`) und hängt nur an SkiaSharp 3.119.0. `dotnet build` kopiert sie neben die EXE.
- Version festpinnen. 2.x hatte Breaking Changes in Minor-Versionen (2.3.0: `Rad` statt `float`).
- `dotnet run --project voxel -c Release -- ...` passt zum CLI-Vertrag in `PLAN.md`.

## 4. Headless-Snippet (PicoGK 2.3.0)

Ohne `Library.Go`, also **ohne Fenster und ohne Logdatei**. Alle Objekte bekommen die `Library` explizit (2.x-Stil).

```csharp
using System.Numerics;
using PicoGK;

float voxelMm = 0.5f;                          // Voxelgrösse: der zentrale Genauigkeits-Regler
string outDir = args.Length > 0 ? args[0] : ".";
Directory.CreateDirectory(outDir);

try
{
    using Library lib = new(voxelMm);          // headless (seit PicoGK 1.6.0)

    using Voxels body = Voxels.voxSphere(lib, Vector3.Zero, 20f);
    using Voxels cutter = Voxels.voxLatticeBeam(lib, new Vector3(0, 0, -30), 5f, new Vector3(0, 0, 30), 5f);
    using Voxels part = body - cutter;         // Boolean-Differenz, Operatoren: + - &

    part.CalculateProperties(out float volMm3, out BBox3 box);
    Console.WriteLine($"Volumen {volMm3:F1} mm3, Voxelgrösse {voxelMm} mm, BBox {box}");

    using Mesh mesh = part.mshAsMesh();
    mesh.SaveToStlFile(Path.Combine(outDir, "part.stl"));   // binäres STL, Einheit mm
    part.SaveToVdbFile(Path.Combine(outDir, "part.vdb"));   // OpenVDB
}
catch (Exception e)
{
    Console.Error.WriteLine(e);
    return 1;
}
return 0;
```

Ausführen: `dotnet run --project voxel -c Release -- .\out\smoke`.

Hinweise dazu:

- STL laden: `Mesh.mshFromStlFile(path, libSet: lib)` gefolgt von `new Voxels(mesh)`. Das Netz muss geschlossen sein und **binäres** STL (ASCII wirft `NotImplementedException`).
- Die Kurzformen aus älteren Beispielen (`Voxels.voxSphere(center, r)` ohne `lib`) funktionieren nur mit registrierter globaler Bibliothek (`Library.RegisterGlobalLibrary(lib)`). Explizite `lib`-Übergabe ist sicherer.
- **Nicht** `Library.Go(...)` im Batch benutzen: es öffnet immer das Viewer-Fenster.
- Fallen in 2.3.0 (siehe `docs/research_picogk.md`): `voxShell(neg, pos, smooth)` (nur 1-Argument-Variante verwenden oder `voxOffset(pos) - voxOffset(neg)`), `IntersectImplicit` unter etwa 0.34 mm Voxelgrösse (nativer Abbruch), `bIsInside` zweifelhaft.
- Speicher pro Objekttyp: `lib.nVoxelsMemUsage()`, `lib.nTotalMemUsage()` (für die Messung `peak_mem_mb` im Ergebnis-JSON; zusätzlich den Prozessspeicher von aussen messen).
- Der Prozess läuft in **einem Prozess je Aufruf**; Parallelität über mehrere Prozesse. Ein Lauf mit mehreren `Library`-Objekten nacheinander ist seit 1.7.0 unterstützt (Speicherfreigabe-Fix), aber für Messungen wird ein frischer Prozess je Task empfohlen.

## 5. Optional: ShapeKernel und LatticeLibrary

Beide werden als **Quellcode** eingebunden, es gibt kein NuGet-Paket:

```powershell
cd C:\Users\Aeolos-04\Desktop\boreas\builder123d\voxel
git clone https://github.com/leap71/LEAP71_ShapeKernel.git ext\ShapeKernel
git clone https://github.com/leap71/LEAP71_LatticeLibrary.git ext\LatticeLibrary
```

Dann `ext\ShapeKernel\ShapeKernel` und `ext\LatticeLibrary\LatticeLibrary` (plus `ImplicitLibrary`) als Quellordner ins Projekt aufnehmen (Standard-SDK-Projekte kompilieren alle `.cs` unterhalb des Projektordners automatisch; die Ordner `Examples` der Repos ausschliessen, da sie eigene `Program`-Einstiege und teils die 1.x-API nutzen könnten). Ob ShapeKernel `main` gegen PicoGK 2.3.0 ohne Anpassung kompiliert, ist **nicht geprüft**: Letzter Push 10.08.2026, ein Release nur v1.0.0. Vor der Einbindung Kompilierversuch einplanen. Alternativ die benötigten Funktionen (Lattice, Implicit-TPMS) direkt gegen PicoGK schreiben.

## 6. Fehlerbilder

| Symptom | Ursache und Massnahme |
|---|---|
| `DllNotFoundException`/`Failed to load PicoGK library` | Native DLL fehlt oder VC++-Laufzeit fehlt. Prüfen, ob `picogk.26.2.dll` neben der EXE liegt (`bin\Release\net9.0\`); ggf. VC++-Redistributable (siehe oben) |
| `BadImageFormatException` | ARM-/x86-Prozess. `PlatformTarget` auf `x64` setzen. Auf Windows-ARM-Geräten läuft es nicht |
| Prozess bricht ohne Ausnahme ab | Native Ausnahme (Issue #27), typisch `IntersectImplicit`/`ProjectZSlice` bei Voxel < 0.34 bzw. 0.17 mm. Voxelgrösse erhöhen |
| Viewer-Fenster öffnet sich | `Library.Go` statt `new Library(...)` benutzt |
| Sehr hoher Speicher | Voxelgrösse zu klein für die Bauteilgrösse; grob Faktor 4 je Halbierung |

## 7. Alternative: Python-Zugang (nicht empfohlen als Basis)

Nur zur Kenntnis, **nicht ausgeführt**: `pip install picopie` (Community, Wheels für Windows x64, macOS arm64, Linux x86-64, CPython 3.10 bis 3.13, Version 0.7.0 vom 02.07.2026). Kein .NET nötig, bindet dieselbe Runtime. Siehe `docs/research_picogk.md` Abschnitt 7.

## Quellen

- https://picogk.org/doc/setup.html (Voraussetzungen, .NET 9, Plattformen)
- https://www.nuget.org/packages/PicoGK (Version 2.3.0, 04.08.2026, 21.41 MB, SkiaSharp)
- https://github.com/leap71/PicoGK (`PicoGK.csproj`: `net9.0`, `runtimes/win-x64/native`)
- https://github.com/leap71/PicoGK/discussions/30 (Headless-Beispiel, ab 1.6.0)
- https://github.com/leap71/PicoGK/releases (Notizen zu 1.6.0, 1.7.0, 1.7.7.5, 2.0.0, 2.2.0)
- `winget show --id Microsoft.DotNet.SDK.9`, `winget show --id Microsoft.VCRedist.2015+.x64` (30.09.2026)
- https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core
