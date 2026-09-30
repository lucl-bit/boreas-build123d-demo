# Vendored: LEAP 71 ShapeKernel und LatticeLibrary (Apache-2.0)

Beide Bibliotheken werden von LEAP 71 nur als Quellcode verteilt (kein NuGet-Paket). Unveraenderte Kopien:

| Ordner | Quelle | Commit | Stand | Lizenz |
|---|---|---|---|---|
| LEAP71_ShapeKernel/ShapeKernel | https://github.com/leap71/LEAP71_ShapeKernel | 7b9097842446a28bb5d49203724622e594ce7510 | Mon Aug 10 15:50:10 2026 +1200 | Apache-2.0 (LICENSE im Ordner) |
| LEAP71_LatticeLibrary/{LatticeLibrary,ImplicitLibrary} | https://github.com/leap71/LEAP71_LatticeLibrary | 81c3c7b2064c19e573c38d76ac09bf1cd2f562d5 | Sun Jul 27 17:43:18 2025 +0100 | Apache-2.0 (LICENSE im Ordner) |

Befund: beide kompilieren ohne Aenderung gegen PicoGK 2.3.0 (net9.0). Sie benoetigen die globale Bibliothek
(`Library.RegisterGlobalLibrary(lib)`), sonst wirft PicoGK "Your code relies on being called using Library::Go".
Beispiele und Doku wurden nicht uebernommen. Diese Dateien zaehlen nicht zu code_loc.
