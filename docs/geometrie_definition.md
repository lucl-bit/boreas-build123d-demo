# Geometrie-Definition Boreas (werkzeugneutral)

Stand: 30.09.2026 · Autor: Agent B-rep · Parameter: `spec/boreas_spec.json` (Version 1)

Dieses Dokument beschreibt **jede Gruppe mathematisch**, so dass ein zweites Werkzeug (PicoGK/C#, Voxel/SDF)
dieselbe Geometrie ohne Blick in den Python-Code nachbauen kann. Alle Formeln sind exakt so im B-rep-Modell
(`brep/`) umgesetzt. Wo B-rep eine Kurve als Spline durch Stützpunkte annähert, steht das dabei
(Abweichung < 0.01 mm).

Schreibweise: Parameter werden als `gruppe.name` geschrieben, Skelett-Parameter ohne Präfix fett
(**n** = `skeleton.arm_count`). Winkel in Grad, Längen in mm.

---

## 0. Koordinatensystem, Abkürzungen, Grundfunktionen

- Rechtshändig, mm, **Z nach oben** (Nase = +Z). Ursprung auf der Rumpfachse in der Trennebene (Referenz: `split_z = 0`).
- ρ = √(x² + y²) Abstand zur Rumpfachse.
- Abkürzungen aus dem Skelett:

| Symbol | Parameter | Referenz |
|---|---|---|
| n | `skeleton.arm_count` | 4 |
| ψ₀ | `skeleton.arm_angle_offset` | 45° |
| σ | `skeleton.arm_splay` | 5.2° |
| R_M | `skeleton.motor_radius` | 110.6 |
| z₀ | `skeleton.split_z` | 0 |
| r_J | `skeleton.joint_radius` | 32.15 |
| z_N | `skeleton.nose_joint_z` (absolut) | 114.0 |
| r_N | `skeleton.nose_joint_radius` | 32.55 |
| z_B | `skeleton.body_bottom_z` (absolut) | −134.5 |

### 0.1 Winkel

- **Nennwinkel** (ungespreizt): ψᵢ = ψ₀ + i·360/n, i = 0…n−1 → Kerben/Laschen Oberteil↔Unterteil.
- **Armwinkel** (gespreizt): θᵢ = ψᵢ + (−1)ⁱ·σ → Motoren, Gondeln, Fins, Stege, Kiele, Heckflossen.
  Referenz: 50.2°, 129.8°, 230.2°, 309.8° (die Motoren liegen auf einem Rechteck 141.6 × 170.0 mm).
- **Zwischenwinkel**: φᵢ = ψ₀ + (i + ½)·360/n → Kühlluft-Einlässe (Referenz 90°, 180°, 270°, 0°).

### 0.2 Lokales Armsystem

Für Arm i: eᵢ = (cos θᵢ, sin θᵢ, 0) (Spannweite), tᵢ = (−sin θᵢ, cos θᵢ, 0) (quer), Z bleibt.
Ein Punkt p hat die lokalen Koordinaten **s = p·eᵢ** (Spannweite), **q = p·tᵢ** (quer), z.
Motorachse: Mᵢ = R_M·eᵢ (senkrecht).

### 0.3 NACA-Tropfenprofil mit verschiebbarer Dickenlage

Das Tropfenprofil der Fins und Heckflossen ist das symmetrische NACA-4-Ziffern-Profil, dessen Dickenmaximum
über eine stückweise lineare Abbildung von x/c = 0.30 auf x/c = p verschoben wird:

```
N(x)   = 0.2969·√x − 0.1260·x − 0.3516·x² + 0.2843·x³ − 0.1015·x⁴        (0 ≤ x ≤ 1)
w(x,p) = 0.3·x/p                    für x ≤ p
       = 0.3 + 0.7·(x − p)/(1 − p)  für x > p
h(δ; c, T, p) = (T/2) · N( w(δ/c, p) ) / N(0.3)          N(0.3) = 0.100151…
```

- δ = Tiefe unter der Vorderkante (Profil läuft **von oben nach unten**, Vorderkante oben, Anströmung von +Z),
  c = Profilsehne, T = maximale Dicke (volle Dicke, nicht halbe), p = Lage der maximalen Dicke.
- h ist die **halbe Dicke**; der Querschnitt ist {|q| ≤ h(δ), 0 ≤ δ ≤ c}. Bei δ = c ist die halbe Dicke
  0.0105·T (offene Hinterkante), abgeschlossen durch eine gerade Linie.
- Die Abbildung w ist bei x = p stetig und hat dort Steigung 0 (N′(0.3) = 0), also C¹.
- B-rep: Stützpunkte δₖ = c·½·(1 − cos(π·k/K)), k = 0…K, K = 40 (dicht an der Vorderkante),
  eine Spline-Kurve durch alle Punkte (h(δₖ), −δₖ) von der Hinterkante der einen Seite über die Vorderkante
  zur anderen Seite, geschlossen durch die gerade Hinterkante.

### 0.4 Potenz-Ogive (Nase und Gondel)

```
ρ(ζ) = R · (1 − ζ^m)^k        ζ = (z − z_Basis)/L ∈ [0, 1]
```

R = Basisradius, L = Länge, m, k = Formexponenten. m = 1 ergibt die reine Potenzspitze R·(1 − ζ)^k
(Gondel), m = 2, k = 0.5 eine Halbellipse. B-rep: Spline durch 60 Punkte mit ζ = 1 − (1 − j/60)² (dicht an der Spitze)
und dem Punkt (0, z_Basis + L).

### 0.5 Rotationskörper

„Rotationskörper der Kontur ρ(z) über [z_a, z_b]“ = {z_a ≤ z ≤ z_b, ρ ≤ ρ(z)}. Innenkonturen sind
**horizontal** versetzt (ρ − Wand), nicht normal versetzt.

---

## 1. Teile und Bool-Reihenfolge (verbindlich)

| Teil | Aufbau |
|---|---|
| `upper` | U = ((Rohr_aussen ∪ Fins ∪ Stege ∪ Gondeln) − Rohr_innen) ∪ Laschen_OT − Einlässe − Nasen-Schlitze, dann Details (Gondel-Verrundung) |
| `lower` | L = (Kegel_aussen ∪ Kiele ∪ Heckflossen) − Kegel_innen − Randkerben, dann Details (Wurzel-Verrundung, Gravur) |
| `nose` | N = (Ogive_aussen − Ogive_innen) ∪ Nasen-Laschen |
| `nose_insert` | E = Ogive_innen ∩ {ρ ≤ nose.insert_radius, z ≥ z_N + nose.insert_z} |

Die Gruppen erzeugen **Features** (Rohkörper), die Baugruppe verrechnet sie in dieser Reihenfolge.
Jedes Feature hängt nur vom Skelett + der eigenen Gruppe ab.

| Gruppe | Features (Teil) |
|---|---|
| upper_body | Rohr_aussen, Rohr_innen, Einlässe (upper) |
| arms | Stege (upper), Kiele (lower) |
| motor_pods | Gondeln (upper) |
| body_fins | Fins (upper) |
| lower_body | Kegel_aussen, Kegel_innen (lower) |
| tail_fins | Heckflossen (lower) |
| nose | Ogive_aussen, Ogive_innen, Einsatz (nose, nose_insert) |
| joints | Laschen_OT, Nasen-Schlitze (upper), Randkerben (lower), Nasen-Laschen (nose) |
| details | Nachbearbeitung auf Teil-Ebene (Verrundungen, Gravur) |

---

## 2. Gruppe `upper_body` – Oberteil-Rohr und Kühlluft-Einlässe

Rohrhöhe H = z_N − z₀. Normierte Höhe ζ = (z − z₀)/H. Exponent q = ln(0.5)/ln(`bulge_pos`).

```
r_o(z) = r_J + (r_N − r_J)·ζ + bulge·sin(π·ζ^q)          (Aussenkontur, fassförmig)
r_i(z) = r_o(z) − wall                                    (Innenkontur)
```

- **Rohr_aussen** = Rotationskörper r_o über [z₀, z_N].
- **Rohr_innen** = Rotationskörper r_i über [z₀ − 1, z_N + 1], wobei r_i ausserhalb [z₀, z_N] auf den Randwert
  geklemmt wird (Rohr oben und unten offen).
- Referenz: r_o(0) = 32.15, max. 34.58 bei z ≈ 71, r_o(114) = 32.55.

**Einlässe** (nur wenn `intake_enabled` = 1), je Zwischenwinkel φᵢ, lokales System u = (cos φ, sin φ, 0)
(radial), v = (−sin φ, cos φ, 0) (quer):

```
z_t = z_N − intake_top_offset          (Rampenanfang, oben)
z_l = z_t − intake_length              (Lippe, unten)
b(z) = intake_width + (intake_width_top − intake_width)·(z − z_l)/intake_length      (volle Breite)
u_floor(z) = r_o(z_t) + (r_o(z_l) − intake_depth − r_o(z_t))·(z_t − z)/intake_length   (ebene Rampe)
Einlass = { z_l ≤ z ≤ z_t,  |p·v| ≤ b(z)/2,  p·u ≥ u_floor(z) }
```

Die Rampe ist eine Ebene (unabhängig von v); wo sie tiefer als die Wand liegt, öffnet der Einlass ins Rohr
(Kühlluftweg). Referenz: z_t = 88, z_l = 51, Lippe bei ρ ≈ 26.

---

## 3. Gruppe `arms` – Stege (Oberteil) und V-Kiele (Unterteil)

### 3.1 Steg (je Arm i)

```
Steg = { |q| ≤ web_width/2,  z₀ − web_depth ≤ z ≤ z₀,  web_start ≤ ρ ≤ R_M − web_end_offset }
```

Die Stirnflächen sind Zylinder um die **Rumpfachse** (ρ = const), wie in der Referenz (R 40.67 / 98.29).
web_depth = 0 → kein Steg.

### 3.2 V-Kiel (je Arm i)

```
z_k      = z₀ − keel_top_offset                                     (Grund-Oberkante)
s_e      = R_M − keel_end_radius
H_k(s)   = keel_height_root + (keel_height_tip − keel_height_root)·(s − r_J)/(s_e − r_J)
z_ap(s)  = z_k − H_k(s)                                             (V-Spitze, steigt nach aussen)
z_top(s) = z_k + pad_height   für pad_start ≤ s < pad_start + pad_length
         = z_k − tip_drop     für s ≥ pad_start + pad_length
         = z_k                sonst
Kiel = { 0 ≤ s ≤ R_M,  z_ap(s) ≤ z ≤ z_top(s),  |q| ≤ (z − z_ap(s))·tan(keel_half_angle) }
       − { Abstand zur Motorachse Mᵢ < keel_end_radius }
```

B-rep-Aufbau: Regelfläche (Loft) zwischen den Dreiecken bei s = 0 und s = R_M mit Oberkante z_k + pad_height,
danach Quader über der gestuften Oberkante abziehen, dann Zylinder um Mᵢ abziehen.

---

## 4. Gruppe `motor_pods` – Tropfen-Gondeln

Je Arm i, Achse Mᵢ, ρ′ = Abstand zur Achse Mᵢ:

```
Sockel = { z₀ ≤ z ≤ z₀ + base_height,  ρ′ ≤ radius }
Spitze = { z₀ + base_height ≤ z ≤ z₀ + base_height + dome_height,  ρ′ ≤ radius·(1 − ζ)^tip_exponent },
         ζ = (z − z₀ − base_height)/dome_height
Gondel = Sockel ∪ Spitze
```

- `wall` > 0: Gondel = Gondel − {Punkte der Gondel mit Abstand > wall zu allen Randflächen ausser der Bodenfläche}
  (gleichmässige Schale, unten offen; B-rep: `offset(..., openings=Boden)`).
- `cable_hole_d` > 0: Zylinder Ø cable_hole_d auf der Achse Mᵢ von z₀ − 10 bis z₀ + base_height abziehen.

Referenz: Spitze bei z = 45.2, r(30) = 12.8 → Fit-Residuum RMS 0.08 mm.

---

## 5. Gruppe `body_fins` – geneigte Aero-Fins Rumpf → Motor (Tropfenprofil)

Je Arm i im lokalen System (s, q, z), λ(s) = (s − r_J)/(R_M − r_J):

```
z_LE(s) = z₀ + le_height_root + (le_height_tip − le_height_root)·λ(s)      (geneigte Vorderkante)
T(s)    = thickness_root + (thickness_tip − thickness_root)·λ(s)           (Dicke, linear)
δ       = z_LE(s) − z                                                      (Tiefe unter Vorderkante)
Fin_roh = { 0 ≤ s ≤ R_M,  0 ≤ δ ≤ profile_chord,  |q| ≤ h(δ; profile_chord, T(s), max_thickness_pos) }
Fin     = Rot_cant(Fin_roh) ∩ { z ≥ z₀ }
```

- Rot_cant: Drehung um die Gerade {q = 0, z = z₀} (Spannweitenachse in der Trennebene) um `cant_angle`
  (positiv: Oberseite Richtung +q). Referenz 0.
- Der Querschnitt wird **nicht** gedreht, sondern entlang der geneigten Vorderkante **verschoben**
  (Schnittebene senkrecht zu eᵢ, Profilsehne immer senkrecht). Das entspricht der Referenz: gleiche Profilform
  bei allen s, nur die Dicke nimmt linear ab.
- Der Teil des Fins im Rohr (s < r_i) verschwindet durch „− Rohr_innen“, das Ende steckt in der Gondel.
- Pfeilung (abgeleitet) = atan((le_height_root − le_height_tip)/(R_M − r_J)) = 21.4° (Referenz).
- B-rep: Regelfläche (Loft) zwischen den Profilen bei s = 0 und s = R_M; weil T und z_LE linear in s sind,
  ist das exakt.

---

## 6. Gruppe `lower_body` – Kegelrumpf

```
Punkte der Aussenkontur (ρ, z):  A = (r_J, z₀),  B = (r_J − collar_taper, z₀ − collar_length),  C = (bottom_radius, z_B)
Kegel_aussen = Rotationskörper des Polygons (0, z₀) → A → B → C → (0, z_B)
r_BC(z)  = Gerade durch B und C (auch oberhalb B fortgesetzt)
r_in(z)  = min( r_J − collar_wall,  r_BC(z) − wall )
Kegel_innen = Rotationskörper r_in über [z_B − 1, z₀ + 1]      (oben und unten offen)
```

Referenz: Kegelflanke 8.07° Halbwinkel, Bohrung Ø 56.3, unten Öffnung Ø 24.7.

---

## 7. Gruppe `tail_fins` – Heckflossen

Je Arm i (Winkel θᵢ), λ_t(s) = (s − r_J)/(span_radius − r_J):

```
z_b     = z_B + bottom_offset                                               (Unterkante)
z_LE(s) = z_b + tip_chord + (span_radius − s)·tan(sweep_angle)              (Vorderkante, steigt nach innen)
T(s)    = thickness_root + (thickness_tip − thickness_root)·λ_t(s)
Flosse_roh = { 0 ≤ s ≤ span_radius + 5,  0 ≤ z_LE(s) − z ≤ profile_chord,  |q| ≤ h(z_LE(s) − z; profile_chord, T(s), max_thickness_pos) }
Clip    = Rotationskörper um die Rumpfachse der (ρ, z)-Fläche [0, span_radius] × [z_b, z_b + 500],
          Ecke (span_radius, z_b) mit Radius corner_radius gerundet
Flosse  = Flosse_roh ∩ Clip
```

Die Spitze ist damit ein Zylinderbogen ρ = span_radius, die untere Ecke ein Torus (wie Referenz).

---

## 8. Gruppe `nose` – Nasenkappe und Einsatz

```
Ogive_aussen = { z_N ≤ z ≤ z_N + length,  ρ ≤ r_N·(1 − ζ^shape_m)^shape_n },           ζ = (z − z_N)/length
Ogive_innen  = { z_N − 1 ≤ z ≤ z_N + length − tip_wall,  ρ ≤ (r_N − wall)·(1 − ζᵢ^shape_m)^shape_n },
               ζᵢ = max(0, z − z_N)/(length − tip_wall)
Nase    = Ogive_aussen − Ogive_innen                          (unten offen)
Einsatz = Ogive_innen ∩ { ρ ≤ insert_radius, z ≥ z_N + insert_z }      (nur wenn insert_enabled = 1)
```

Die Nase wird **montiert** gebaut (Basis bei z_N). In der STEP-Datei liegt sie 90 mm höher (explodiert).

---

## 9. Gruppe `joints` – Steckverbindungen

Abgeleitete Masse (keine freien Parameter):

| Grösse | Formel | Referenz |
|---|---|---|
| Laschenbreite Nase | nose_slot_width − 2·clearance | 11.2 |
| Laschenhöhe Nase | nose_slot_depth − clearance | 7.95 |
| Laschen-Halbwinkel Oberteil | rim_notch_half_angle − deg(clearance/(r_J − upper_tab_thickness/2)) | 21.1° |
| Laschenhöhe Oberteil | rim_notch_depth − clearance | 15.45 |

Mit αₖ = nose_tab_angle + k·360/nose_tab_count, u, v wie in Kap. 2:

```
Nasen-Schlitz_k (Schnitt im Oberteil) = { |p·v| ≤ nose_slot_width/2,  p·u ≥ r_N − nose_tab_thickness − clearance,  z ≥ z_N − nose_slot_depth }
Nasen-Lasche_k  (an der Nase)         = { |p·v| ≤ nose_slot_width/2 − clearance,  r_N − nose_tab_thickness ≤ ρ ≤ r_N,
                                          z_N − (nose_slot_depth − clearance) ≤ z ≤ z_N,  p·u > 0 }
Randkerbe_i (Schnitt im Unterteil)    = { |Winkel(p) − ψᵢ| ≤ rim_notch_half_angle,  ρ ≤ r_J + rim_notch_margin,  z ≥ z₀ − rim_notch_depth }
Lasche_OT_i (am Oberteil, wenn upper_tab_enabled = 1)
                                      = { |Winkel(p) − ψᵢ| ≤ Laschen-Halbwinkel,  r_J − upper_tab_thickness ≤ ρ ≤ r_J,
                                          z₀ − (rim_notch_depth − clearance) ≤ z ≤ z₀ }
```

Hinweis: Die Kerben sitzen auf den **Nennwinkeln** ψᵢ (45°, 135°, …), nicht auf den gespreizten Armwinkeln –
so ist es in der Referenz. Die Laschen am Oberteil sind eine Ergänzung (in der Referenz ist die Kerbe leer).

---

## 10. Gruppe `details`

Nachbearbeitung auf Teil-Ebene, nach allen Bools:

- `pod_fillet` > 0: Verrundung (Rollkugel) Radius r an den Kreiskanten Sockel/Spitze jeder Gondel
  (z = z₀ + base_height, ρ′ = radius). Voxel: lokale Glättung mit gleichem Radius zulässig.
- `tail_root_fillet` > 0: Verrundung der Schnittkanten Heckflosse/Kegel (konkav).
- `engrave` = 1: Text „BOREAS“, Schrifthöhe 8 mm, 0.6 mm tief, senkrecht laufend auf dem Kegel bei Winkel ψ₀ + 180/n
  (zwischen zwei Heckflossen), Mitte z = z₀ + (z_B − z₀)·0.45.
- `min_wall`: nur Grenzwert für den Druckbarkeits-Check (B08), keine Geometrie.

---

## 11. Gültigkeit und Grenzen

- Jede min/max-Grenze erzeugt ein gültiges, zusammenhängendes Teil, **wenn alle anderen Gruppen auf dem
  Referenzwert stehen** (so arbeitet die Pipeline: eine Gruppe pro Durchlauf). Kombinationen mehrerer Extremwerte
  können ungültig werden (z. B. sehr kurzes Unterteil + grosse Heckflossen-Pfeilung).
- Getestet in `brep/tests/test_groups.py` (min/max-Sweep aller Parameter).

## 12. Nicht modelliert (bewusst weggelassen)

Aus der Referenz nicht übernommen: Rastnasen/Stifte am Unterteil-Rand (Ø 1.6), Lippe/Haube über den
NACA-Einlässen, 4 kleine Innentaschen oben im Rohr, Torus-Rundung (r 3) an den Kielenden, 0.9° Verdrehung
der Fins gegenüber der Linie Achse→Motor (Freihand-Fehler), 0.84 mm Versatz der Motoren in +Y gegenüber der Rohrachse.
