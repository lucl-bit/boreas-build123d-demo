using System.Diagnostics;
using System.Numerics;
using PicoGK;
using SkiaSharp;

namespace BoreasVoxel;

/// <summary>Alle Benchmark-Aufgaben der Voxel-Seite (Task-IDs aus PLAN.md). Jede Aufgabe liefert ein TaskResult;
/// Aufgaben, die Voxel nicht kann, liefern "unsupported"/"partial" mit Begruendung.</summary>
public static class Tasks
{
    public static TaskResult Run(Ctx c) => c.Task switch
    {
        "B01" => B01(c), "B02" => B02(c), "B03" => B03(c), "B04" => B04(c), "B05" => B05(c), "B06" => B06(c),
        "B07" => B07(c), "B08" => B08(c), "B09" => B09(c), "B10" => B10(c),
        "R01" => R01(c), "R02" => R02(c), "R03" => R03(c), "R04" => R04(c),
        "V01" => V01(c), "V02" => V02(c), "V03" => V03(c), "V04" => V04(c),
        _ => throw new SpecException($"Unbekannte Aufgabe {c.Task}")
    };

    // ------------------------------------------------------------------ Hilfen
    static (Model m, TaskResult r) BuildModel(Ctx c)
    {
        var sw = Stopwatch.StartNew();
        var m = Model.Build(c.Spec, c.Lib);
        var r = new TaskResult();
        r.Metrics["build_timing_s"] = new Dictionary<string, object?>
        {
            ["groups_s"] = m.GroupSeconds.ToDictionary(k => k.Key, k => (object?)Math.Round(k.Value, 3)),
            ["booleans_s"] = Math.Round(m.AssembleSeconds, 3), ["total_s"] = Math.Round(sw.Elapsed.TotalSeconds, 3)
        };
        r.Metrics["voxel_size_mm"] = c.Voxel;
        return (m, r);
    }

    static double S(Stopwatch sw) => Math.Round(sw.Elapsed.TotalSeconds, 3);
    static double Kb(string path) => Math.Round(new FileInfo(path).Length / 1024.0, 1);
    static void Note(TaskResult r, string s) => r.Notes = (r.Notes + " " + s).Trim();

    static Voxels Group(Model m, string group, string part)
    {
        var v = new Voxels(m.Lib);
        foreach (var o in m.Ops[group].Where(o => o.Part == part && !o.Cut && o.Vox != null)) v.BoolAdd(o.Vox!);
        return v;
    }

    // ------------------------------------------------------------------ B01–B10
    static TaskResult B01(Ctx c)
    {
        var (m, r) = BuildModel(c);
        var meshes = Outputs.WriteModel(c, r, m.Parts);
        var dev = new Dictionary<string, object?>();
        foreach (var part in new[] { "upper", "lower" })
        {
            var sw = Stopwatch.StartNew();
            var refPath = Path.Combine(c.RefDir, part + ".stl");
            if (!File.Exists(refPath)) { Note(r, $"Referenz {part}.stl fehlt."); r.Status = "partial"; continue; }
            var refMesh = TriMesh.LoadStl(refPath);
            double tLoad = S(sw);
            var refVox = refMesh.ToVoxels(c.Lib);                  // Referenz rastern (STEP geht nicht, nur Netz)
            double tVox = S(sw) - tLoad;
            var refTri = refVox.ToTri();
            var refIdx = new MeshDistance(refMesh, 2f);
            var modIdx = new MeshDistance(meshes[part], 2f);
            var a = MeshDistance.Deviation(meshes[part], refIdx);
            var b = MeshDistance.Deviation(refMesh, modIdx);
            dev[part] = new Dictionary<string, object?>
            {
                ["model_to_ref"] = a, ["ref_to_model"] = b,
                ["mean_mm"] = ((double)a["mean_mm"]! + (double)b["mean_mm"]!) / 2,
                ["ref_load_s"] = tLoad, ["ref_voxelize_s"] = Math.Round(tVox, 3),
                ["ref_voxelized_volume_mm3"] = refTri.Mass().Volume, ["ref_mesh_triangles"] = refMesh.TriCount
            };
            if (part == "lower") { refTri.SaveBinaryStl(c.Out("reference_lower_voxelized.stl")); r.Files["reference_voxelized"] = "reference_lower_voxelized.stl"; }
        }
        r.Metrics["deviation_to_reference"] = dev;
        Note(r, "PicoGK kann kein STEP lesen: Die Referenz kommt als STL (vom Runner aus dem STEP tesselliert) und wird gerastert. " +
                "Aus dem offenen Freihand-Netz entsteht dabei trotzdem ein geschlossener Voxelkoerper (Voxelisierung repariert Luecken). " +
                "Die exakten Flaechen (B-Splines, Radien) gehen dabei verloren, das Modell existiert nur noch als Abstandsfeld.");
        return r;
    }

    static TaskResult B02(Ctx c)
    {
        var (m, r) = BuildModel(c);
        Outputs.WriteModel(c, r, m.Parts);
        var sw = Stopwatch.StartNew();
        var vdb = new Dictionary<string, object?>();
        foreach (var kv in m.Parts) { var p = c.Out(kv.Key + ".vdb"); kv.Value.SaveToVdbFile(p); vdb[kv.Key] = kv.Key + ".vdb"; }
        r.Files["vdb"] = vdb; r.Metrics["vdb_export_s"] = S(sw);
        r.Metrics["groups"] = Model.Groups.Length + 1;
        Note(r, $"Gesamtmodell aus derselben Spec (Skelett + 9 Gruppen). Formen werden als Netze aus Querschnitten erzeugt und bei {c.Voxel} mm gerastert, " +
                "alle Booleschen Operationen laufen im Voxelfeld (robust, nie 'fehlgeschlagen'). Zusatzformat: OpenVDB (.vdb) je Teil.");
        return r;
    }

    static TaskResult B03(Ctx c)
    {
        var (m, r) = BuildModel(c);
        Outputs.WriteModel(c, r, m.Parts, preview: false);
        Note(r, "Regeneration: jede Gruppe wird aus Skelett + eigenen Parametern gerastert; die Teile werden im Voxelfeld neu kombiniert.");
        return r;
    }

    static TaskResult B04(Ctx c)
    {
        var (m, r) = BuildModel(c);
        var parts = new Dictionary<string, Voxels>
        {
            ["body_fins"] = Group(m, "body_fins", "upper"), ["tail_fins"] = Group(m, "tail_fins", "lower"), ["motor_pods"] = Group(m, "motor_pods", "upper")
        };
        var meshes = Outputs.WriteModel(c, r, parts);
        var dev = new Dictionary<string, object?>();
        foreach (var (g, part) in new[] { ("body_fins", "upper"), ("tail_fins", "lower"), ("motor_pods", "upper") })
        {
            var ideal = new TriMesh();
            foreach (var o in m.Ops[g].Where(o => o.Ideal != null)) ideal.Append(o.Ideal!);
            if (ideal.TriCount == 0) continue;
            // Fins werden bei z0 abgeschnitten -> Abweichung nur Voxel->Ideal messen (Voxel-Oberflaeche liegt auf dem Ideal)
            dev[g] = MeshDistance.Deviation(meshes[g], new MeshDistance(ideal, 2f));
        }
        r.Metrics["voxel_vs_ideal_profile"] = dev;
        Note(r, "Tropfenprofil wird als Netz aus Querschnitten (81 Punkte je Profil) aufgebaut und gerastert. Die Oberflaeche weicht um einen " +
                "Bruchteil der Voxelgroesse vom idealen Profil ab (siehe Kennzahlen); scharfe Hinterkanten werden auf ~1 Voxel verrundet.");
        return r;
    }

    static TaskResult B05(Ctx c)
    {
        var (m, r) = BuildModel(c);
        var tries = new Dictionary<string, object?>();
        // Schale eines beliebigen Koerpers: Unterteil-Aussenform (Kegel + Kiele + Heckflossen) ohne Hohlraum, dann Offset nach innen
        var solidLower = new Voxels(c.Lib);
        foreach (var g in new[] { "lower_body", "arms", "tail_fins" })
            foreach (var o in m.Ops[g].Where(o => o.Part == "lower" && !o.Cut && o.Vox != null)) solidLower.BoolAdd(o.Vox!);
        var parts = new Dictionary<string, Voxels>();
        foreach (var w in new[] { 1.2f, 2.0f })
        {
            var sw = Stopwatch.StartNew();
            var shell = solidLower.Hollow(w);
            tries[$"lower_shell_{w}mm"] = new Dictionary<string, object?> { ["ok"] = !shell.bIsEmpty(), ["s"] = S(sw) };
            if (w == 1.2f) parts["lower"] = shell;
        }
        var sw2 = Stopwatch.StartNew();
        var upperShell = m.Parts["upper"].Hollow(0.8f);
        tries["upper_part_shell_0.8mm"] = new Dictionary<string, object?> { ["ok"] = !upperShell.bIsEmpty(), ["s"] = S(sw2) };
        parts["upper"] = m.Parts["upper"];
        r.Metrics["shell_attempts"] = tries;
        var wall = Analysis.WallThickness(parts["lower"], 1500);
        r.Metrics["measured_wall_lower"] = wall;
        Outputs.WriteModel(c, r, parts);
        Note(r, "Schale = Koerper minus nach innen versetzter Koerper (Offset im Abstandsfeld). Funktioniert auf jedem Koerper, auch auf dem fertig " +
                "verrechneten Oberteil mit Fins/Gondeln (Kiele und Heckflossen werden dabei ebenfalls hohl). Wandstaerke gemessen per Strahl durch die Wand. " +
                "Hinweis: voxShell(neg,pos,smooth) ist in 2.3.0 defekt, deshalb explizite Variante.");
        return r;
    }

    static TaskResult B06(Ctx c)
    {
        var (m, r) = BuildModel(c);
        var tries = new List<object?>();
        Voxels? best = null;
        foreach (var rad in new[] { 0.4f, 1.0f, 2.0f, 3.0f })
        {
            var sw = Stopwatch.StartNew();
            var v = m.Parts["lower"].voxDuplicate();
            v.Fillet(rad);
            v = v.voxOffset(-rad).voxOffset(rad);
            tries.Add(new Dictionary<string, object?> { ["radius_mm"] = rad, ["ok"] = !v.bIsEmpty(), ["s"] = S(sw), ["whole_part"] = true });
            if (rad == 1.0f) best = v;
        }
        r.Metrics["fillet_attempts"] = tries;
        var withDetails = Spec.Load(c.Args["spec"], c.Sets.Concat(new[] { "details.pod_fillet=1.0", "details.tail_root_fillet=1.0" }));
        var sw3 = Stopwatch.StartNew();
        var m2 = Model.Build(withDetails, c.Lib);
        r.Metrics["local_fillet_model_s"] = S(sw3);
        Outputs.WriteModel(c, r, new Dictionary<string, Voxels> { ["upper"] = m2.Parts["upper"], ["lower"] = best! });
        Note(r, "Verrundung ohne Kantenauswahl: Fillet (konkav) + Offset −r/+r (konvex) rundet ALLE Kanten eines Teils oder, ueber eine Einflusszone, " +
                "nur einen Bereich (Gondel-Uebergaenge). Scheitert nie, aber es gibt keinen exakten Radius an einer bestimmten Kante; Radien unter ~1 Voxel verschwinden.");
        return r;
    }

    static TaskResult B07(Ctx c)
    {
        var (m, r) = BuildModel(c);
        var meshes = Outputs.WriteModel(c, r, m.Parts, preview: false);
        double rho = c.Spec.MetaNumber("density_g_cm3") ?? 1.24;
        r.Metrics["mass_properties"] = meshes.ToDictionary(k => k.Key, k => (object?)Analysis.MassProperties(k.Value, rho));
        long mem = 0; foreach (var v in m.Parts.Values) mem += (long)v.nMemUsage();
        r.Metrics["voxel_memory_mb"] = Math.Round(mem / 1048576.0, 2);
        Note(r, $"Masseneigenschaften aus dem Oberflaechennetz des Voxelfelds (Voxel {c.Voxel} mm). PicoGK selbst liefert nur Volumen und Bounding Box " +
                "(und das Volumen ist bei Hohlkoerpern in 2.3.0 falsch), Schwerpunkt/Traegheit selbst gerechnet. Genauigkeit haengt von der Voxelgroesse ab.");
        return r;
    }

    static TaskResult B08(Ctx c)
    {
        var (m, r) = BuildModel(c);
        var meshes = Outputs.WriteModel(c, r, m.Parts);
        var all = new TriMesh(); foreach (var t in meshes.Values) all.Append(t);
        double over = 0, tot = 0;
        for (int i = 0; i < all.TriCount; i++)
        {
            var a = all.V[all.T[3 * i]]; var b = all.V[all.T[3 * i + 1]]; var cc = all.V[all.T[3 * i + 2]];
            var n = Vector3.Cross(b - a, cc - a); float ar = n.Length() / 2; tot += ar;
            if (ar > 0 && n.Z / (2 * ar) < -MathF.Cos(45 * Geo.Deg)) over += ar;
        }
        var wl = Analysis.WallThickness(m.Parts["lower"], 2000); var wu = Analysis.WallThickness(m.Parts["upper"], 2000);
        r.Metrics["printability"] = new Dictionary<string, object?>
        {
            ["overhang_area_share_45deg"] = over / tot, ["wall_lower"] = wl, ["wall_upper"] = wu,
            ["min_wall_limit_mm"] = c.Spec.View("details").F("min_wall")
        };
        r.Status = "partial";
        Note(r, "Binaeres STL je Teil (PicoGK: nur STL, kein 3MF). Druckbarkeit: Mindestwand wird direkt im Feld gemessen (Strahl durch die Wand) – " +
                "das geht auch fuer Formen ohne Wand-Parameter. 3MF fehlt, daher 'teilweise'.");
        return r;
    }

    static TaskResult B09(Ctx c)
    {
        var (m, r) = BuildModel(c);
        Outputs.WriteModel(c, r, m.Parts);
        var body = new Voxels(c.Lib);
        foreach (var k in new[] { "upper", "lower", "nose" }) body.BoolAdd(m.Parts[k]);
        var sw = Stopwatch.StartNew();
        r.Metrics["frontal_area_z_mm2"] = Math.Round(Analysis.ProjectedArea(body, Voxels.ESliceAxis.Z, c.Voxel), 1);
        r.Metrics["frontal_area_s"] = S(sw);
        sw.Restart();
        var bb = body.ToTri().BBox(); var ctr = (bb.min + bb.max) / 2; var sz = bb.max - bb.min;
        // Rechengebiet: seitlich 1 x, vorne 1 x, hinten 2 x Koerperlaenge Abstand (typisch fuer eine erste Aussenstroemung)
        var mn = new Vector3(ctr.X - 1.5f * sz.X, ctr.Y - 1.5f * sz.Y, bb.min.Z - 2f * sz.Z); var mx = new Vector3(ctr.X + 1.5f * sz.X, ctr.Y + 1.5f * sz.Y, bb.max.Z + 1f * sz.Z);
        var dom = Geo.LocalBox(0, mn.X, mx.X, mn.Y, mx.Y, mn.Z, mx.Z).ToVoxels(c.Lib);
        dom.BoolSubtract(body);
        r.Metrics["fluid_domain_s"] = S(sw);
        r.Metrics["fluid_domain_size_mm"] = new double[] { mx.X - mn.X, mx.Y - mn.Y, mx.Z - mn.Z };
        dom.SaveToVdbFile(c.Out("fluid_domain.vdb")); r.Files["fluid_domain_vdb"] = "fluid_domain.vdb";
        r.Metrics["fluid_domain_vdb_kb"] = Kb(c.Out("fluid_domain.vdb"));
        long cells = (long)((mx.X - mn.X) / c.Voxel) * (long)((mx.Y - mn.Y) / c.Voxel) * (long)((mx.Z - mn.Z) / c.Voxel);
        r.Metrics["fluid_domain_cells_dense"] = cells;
        Note(r, "Stroemungsgebiet = Quader − Drohne direkt im Voxelfeld; das Raster ist selbst schon ein kartesisches Gitter (direkt nutzbar fuer " +
                "Lattice-Boltzmann-Loeser); gespeichert als VDB-Feld. Als STL waere das Gebiet bei 0.5 mm Voxel unbrauchbar gross (74 Mio. Dreiecke im ersten " +
                "Versuch) – fuer klassische CFD (OpenFOAM/snappyHexMesh) nimmt man stattdessen das STL der Drohne. Stirnflaeche aus der Projektion des Abstandsfelds.");
        return r;
    }

    static TaskResult B10(Ctx c)
    {
        var (m, r) = BuildModel(c);
        Outputs.WriteModel(c, r, m.Parts, preview: false);
        long mem = 0; foreach (var v in m.Parts.Values) mem += (long)v.nMemUsage();
        r.Metrics["voxel_memory_mb"] = Math.Round(mem / 1048576.0, 2);
        double stl = 0; foreach (var p in ((Dictionary<string, object?>)r.Files["parts"]!).Values) stl += Kb(c.Out((string)p!));
        r.Metrics["stl_size_kb"] = Math.Round(stl, 1);
        m.Parts["upper"].SaveToVdbFile(c.Out("upper.vdb")); r.Metrics["vdb_upper_kb"] = Kb(c.Out("upper.vdb"));
        Note(r, "Vollstaendiger Aufbau inkl. STL-Export. Laufzeit/RAM misst der Runner; Speicher und Dateigroessen wachsen mit feinerer Voxelgroesse stark.");
        return r;
    }

    // ------------------------------------------------------------------ R01–R04 (B-rep-Staerken)
    static TaskResult R01(Ctx c)
    {
        var (m, r) = BuildModel(c);
        Outputs.WriteModel(c, r, m.Parts, preview: false);
        var body = new Voxels(c.Lib); foreach (var k in new[] { "upper", "lower", "nose" }) body.BoolAdd(m.Parts[k]);
        SliceImage(body, c.Out("section_y0.png"), Voxels.ESliceAxis.Y, 0.5f);
        r.Files["images"] = new List<object?> { "section_y0.png" }; r.Files["image"] = "section_y0.png";
        r.Status = "unsupported";
        Note(r, "Keine technische Zeichnung: Ein Voxelfeld kennt keine Kanten, Flaechen oder Masse, die man bemassen koennte. Moeglich sind nur " +
                "Schnittbilder (hier Mittelschnitt als Rasterbild). Fuer Fertigungszeichnungen braucht es ein B-rep-Modell.");
        return r;
    }

    static TaskResult R02(Ctx c)
    {
        var (m, r) = BuildModel(c);
        Outputs.WriteModel(c, r, m.Parts, preview: false);
        r.Status = "unsupported";
        Note(r, "Kein STEP-Export und keine Selektoren fuer Kanten/Flaechen (es gibt keine). Austausch nur als Netz (STL) oder Feld (VDB); " +
                "in CAD-Systemen kommt das als Dreiecksnetz an, nicht als bearbeitbarer Volumenkoerper.");
        return r;
    }

    static TaskResult R03(Ctx c)
    {
        var (m, r) = BuildModel(c);
        Outputs.WriteModel(c, r, m.Parts);
        var inter = new Dictionary<string, object?>();
        foreach (var (a, b) in new[] { ("upper", "lower"), ("upper", "nose") })
            inter[$"{a}∩{b}_mm3"] = m.Parts[a].Both(m.Parts[b]).Volume();
        r.Metrics["interference"] = inter;
        r.Status = "partial";
        Note(r, "Keine Baugruppen-, Joint- oder Constraint-Struktur: Die Teile liegen bereits an ihrer Einbauposition im selben Koordinatensystem. " +
                "Kollisionspruefung per Schnittmenge im Voxelfeld funktioniert (Genauigkeit ~ Voxelgroesse).");
        return r;
    }

    static TaskResult R04(Ctx c)
    {
        var (m, r) = BuildModel(c);
        var meshes = Outputs.WriteModel(c, r, m.Parts, preview: false);
        float cl = c.Spec.View("joints").F("clearance");
        var tabOp = m.Ops["joints"].First(o => o.Label == "Laschen_OT");
        var tab = tabOp.Vox!.ToTri();
        var lower = new MeshDistance(meshes["lower"], 1f);
        // Spiel = kleinster Abstand Laschen-Oberflaeche -> Unterteil (nur Punkte der Lasche, die nicht im Unterteil liegen)
        float gap = float.MaxValue;
        foreach (var v in tab.V) { float d = lower.Distance(v); if (d < gap) gap = d; }
        r.Metrics["fit"] = new Dictionary<string, object?> { ["clearance_spec_mm"] = cl, ["clearance_measured_mm"] = gap, ["error_mm"] = Math.Abs(gap - cl), ["voxel_mm"] = c.Voxel };
        r.Status = "partial";
        Note(r, $"Passungsspiel {cl} mm bei Voxel {c.Voxel} mm: Weil Lasche und Unterteil getrennte Felder sind, trifft die Subvoxel-Interpolation " +
                "das Spiel erstaunlich gut. Innerhalb EINES Feldes (z. B. Schlitz im selben Teil) wachsen Spalte unter etwa einer Voxelgroesse aber zu. " +
                "Keine Toleranz-/Passungsangaben am Modell, keine Bemassung.");
        return r;
    }

    // ------------------------------------------------------------------ V01–V04 (Voxel-Staerken)
    static TaskResult V01(Ctx c)
    {
        var (m, r) = BuildModel(c);
        var cavity = m.Ops["lower_body"].First(o => o.Cut).Vox!;
        var tries = new Dictionary<string, object?>();
        var parts = new Dictionary<string, Voxels>();
        // (a) Gyroid (TPMS) als implizite Funktion, mit dem Hohlraum geschnitten (BoolIntersect statt IntersectImplicit: Absturz < 0.34 mm)
        float cell = 8f, th = 0.6f;
        var sw = Stopwatch.StartNew();
        var gy = new Geo.Sdf(p =>
        {
            float k = 2 * MathF.PI / cell;
            float g = MathF.Sin(k * p.X) * MathF.Cos(k * p.Y) + MathF.Sin(k * p.Y) * MathF.Cos(k * p.Z) + MathF.Sin(k * p.Z) * MathF.Cos(k * p.X);
            return MathF.Abs(g) / k - th;       // Naeherung Abstand in mm
        });
        var bb = cavity.ToTri().BBox();
        var gyVox = new Voxels(c.Lib, gy, new BBox3(bb.min, bb.max));
        gyVox.BoolIntersect(cavity);
        var gyroidPart = m.Parts["lower"].Plus(gyVox);
        tries["gyroid"] = new Dictionary<string, object?> { ["cell_mm"] = cell, ["s"] = S(sw), ["ok"] = !gyroidPart.bIsEmpty() };
        parts["lower"] = gyroidPart;
        // (b) Stab-Gitter (Lattice) in derselben Zone
        sw.Restart();
        var lat = new Lattice(c.Lib); int beams = 0; float cs = 8f;
        for (float x = bb.min.X; x <= bb.max.X; x += cs)
            for (float y = bb.min.Y; y <= bb.max.Y; y += cs)
                for (float z = bb.min.Z; z <= bb.max.Z; z += cs)
                {
                    var p = new Vector3(x, y, z);
                    foreach (var d in new[] { Vector3.UnitX, Vector3.UnitY, Vector3.UnitZ }) { lat.AddBeam(p, p + d * cs, 0.6f, 0.6f, true); beams++; }
                }
        var latVox = new Voxels(lat); latVox.BoolIntersect(cavity);
        tries["beam_lattice"] = new Dictionary<string, object?> { ["cell_mm"] = cs, ["beams"] = beams, ["s"] = S(sw), ["ok"] = !latVox.bIsEmpty() };
        r.Metrics["lattice_attempts"] = tries;
        r.Metrics["infill_volume_mm3"] = gyVox.Volume();
        Outputs.WriteModel(c, r, parts);
        Note(r, "Gyroid-Infill (TPMS) als Formel direkt ins Voxelfeld gerechnet und mit dem Hohlraum geschnitten; Stab-Gitter ueber die Lattice-Klasse. " +
                "Beides in Sekunden, unabhaengig von der Anzahl Zellen – die Kernstaerke von Voxel/SDF.");
        return r;
    }

    static TaskResult V02(Ctx c)
    {
        var (m, r) = BuildModel(c);
        var sk = m.Sk; var g = c.Spec.View("lower_body");
        float rb = g.F("bottom_radius"), ct = g.F("collar_taper"), cl = g.F("collar_length"), wall = g.F("wall");
        float Rout(float z) => rb + (sk.JointRadius - ct - rb) * (z - sk.BodyBottomZ) / (sk.SplitZ - cl - sk.BodyBottomZ);
        var sw = Stopwatch.StartNew();
        var outer = new Lattice(c.Lib); var inner = new Lattice(c.Lib);
        int channels = 4; float zTop = sk.SplitZ - 30, zBot = sk.BodyBottomZ + 15; int n = 60;
        for (int ch = 0; ch < channels; ch++)
        {
            float a0 = sk.ArmAngleOffset + ch * 360f / channels;
            Vector3 P(int k) { float u = (float)k / n; float z = zTop + (zBot - zTop) * u; float rr = Rout(z) - wall - 3f; float a = (a0 + 180f * u) * Geo.Deg; return new Vector3(rr * MathF.Cos(a), rr * MathF.Sin(a), z); }
            for (int k = 0; k < n; k++) { outer.AddBeam(P(k), P(k + 1), 3f, 3f, true); inner.AddBeam(P(k), P(k + 1), 2f, 2f, true); }
            // Abzweig in die jeweilige Heckflosse (Auslass)
            var pe = P(n); var th = sk.ArmAngle(ch) * Geo.Deg; var outp = new Vector3(pe.X + 20 * MathF.Cos(th), pe.Y + 20 * MathF.Sin(th), pe.Z);
            outer.AddBeam(pe, outp, 3f, 2.2f, true); inner.AddBeam(pe, outp, 2f, 1.4f, true);
        }
        var tube = new Voxels(outer); var bore = new Voxels(inner);
        var part = m.Parts["lower"].Plus(tube); part.BoolSubtract(bore);
        r.Metrics["channel"] = new Dictionary<string, object?> { ["channels"] = channels, ["d_inner_mm"] = 4.0, ["wall_mm"] = 1.0, ["segments"] = channels * (n + 1), ["s"] = S(sw) };
        Outputs.WriteModel(c, r, new Dictionary<string, Voxels> { ["lower"] = part });
        Note(r, "4 gewendelte Kuehlluftkanaele (Innen-Ø 4 mm, 1 mm Wand) mit Abzweig in die Heckflossen: Stabzug entlang der Bahn, einmal dick, einmal duenn, " +
                "Differenz = Rohr. Verzweigungen und Uebergaenge verschmelzen automatisch, keine Sonderfaelle.");
        return r;
    }

    static TaskResult V03(Ctx c)
    {
        var (m, r) = BuildModel(c);
        var sk = m.Sk; var g = c.Spec.View("lower_body");
        float rb = g.F("bottom_radius"), ct = g.F("collar_taper"), cl = g.F("collar_length");
        float Rout(float z) => rb + (sk.JointRadius - ct - rb) * (z - sk.BodyBottomZ) / (sk.SplitZ - cl - sk.BodyBottomZ);
        // Feldgesteuerte Wand: 3.5 mm oben (Lasteinleitung Arme) -> 1.2 mm unten
        float W(float z) => Geo.Lerp(1.2f, 3.5f, Math.Clamp((z - sk.BodyBottomZ) / (sk.SplitZ - cl - sk.BodyBottomZ), 0f, 1f));
        var sw = Stopwatch.StartNew();
        var solid = new Voxels(c.Lib);
        foreach (var gr in new[] { "lower_body", "arms", "tail_fins" })
            foreach (var o in m.Ops[gr].Where(o => o.Part == "lower" && !o.Cut && o.Vox != null)) solid.BoolAdd(o.Vox!);
        var cav = new Geo.Sdf(p =>
        {
            float rho = MathF.Sqrt(p.X * p.X + p.Y * p.Y);
            float zc = Math.Clamp(p.Z, sk.BodyBottomZ, sk.SplitZ - cl);
            float d = rho - (Rout(zc) - W(zc));
            if (p.Z > sk.SplitZ - cl) d = rho - (sk.JointRadius - g.F("collar_wall"));
            return d;
        });
        var cavVox = new Voxels(c.Lib, cav, new BBox3(new Vector3(-40, -40, sk.BodyBottomZ - 2), new Vector3(40, 40, sk.SplitZ + 2)));
        var graded = solid.Minus(cavVox);
        double tGraded = S(sw);
        var wall = Analysis.WallThickness(graded, 1500);
        // Bool auf Netzdaten: Referenz-STL (offenes Freihand-Netz) rastern und schneiden
        sw.Restart();
        var refPath = Path.Combine(c.RefDir, "lower.stl");
        Dictionary<string, object?> meshBool = new() { ["ok"] = false };
        if (File.Exists(refPath))
        {
            var refVox = TriMesh.LoadStl(refPath).ToVoxels(c.Lib);
            var cut = refVox.Minus(Geo.LocalBox(0, -10, 10, -100, 100, -70, -50).ToVoxels(c.Lib));
            var t = cut.ToTri(); var topo = t.CheckTopology(1e-4);
            meshBool = new() { ["ok"] = !cut.bIsEmpty(), ["watertight"] = topo.Watertight, ["s"] = S(sw) };
            t.SaveBinaryStl(c.Out("reference_lower_cut.stl")); r.Files["mesh_boolean"] = "reference_lower_cut.stl";
        }
        r.Metrics["graded_wall"] = new Dictionary<string, object?> { ["wall_bottom_mm"] = 1.2, ["wall_top_mm"] = 3.5, ["s"] = tGraded, ["measured"] = wall };
        r.Metrics["mesh_boolean"] = meshBool;
        Outputs.WriteModel(c, r, new Dictionary<string, Voxels> { ["lower"] = graded });
        Note(r, "Wandstaerke als Funktion der Hoehe (1.2 mm unten → 3.5 mm oben) direkt als Abstandsfunktion; Bool auf dem offenen Referenznetz " +
                "funktioniert nach dem Rastern ohne Reparatur.");
        return r;
    }

    static TaskResult V04(Ctx c)
    {
        var (m, r) = BuildModel(c);
        Outputs.WriteModel(c, r, new Dictionary<string, Voxels> { ["lower"] = m.Parts["lower"] }, preview: false);
        var sw = Stopwatch.StartNew();
        m.Parts["lower"].SaveToCliFile(c.Out("lower.cli"), 0.06f);
        r.Files["cli"] = "lower.cli"; r.Metrics["cli_s"] = S(sw); r.Metrics["cli_kb"] = Kb(c.Out("lower.cli"));
        var imgs = new List<object?>();
        foreach (var frac in new[] { 0.15f, 0.5f, 0.85f })
        {
            var name = $"slice_{(int)(frac * 100)}.png";
            SliceImage(m.Parts["lower"], c.Out(name), Voxels.ESliceAxis.Z, frac); imgs.Add(name);
        }
        r.Files["images"] = imgs; r.Files["image"] = imgs[1];
        r.Metrics["layer_height_mm"] = 0.06;
        Note(r, "Direkter Export als CLI-Schichtdatei (Industriestandard fuer Laser-Pulverbett-Drucker, 60 µm Schichten) plus Schnittbilder. " +
                "Kein Slicer-Zwischenschritt noetig.");
        return r;
    }

    /// <summary>Schnittbild aus dem Abstandsfeld (innen dunkel, Kontur blau).</summary>
    static void SliceImage(Voxels v, string path, Voxels.ESliceAxis axis, float frac)
    {
        var img = v.imgAllocateSlice(out int n, axis);
        v.GetVoxelSlice(Math.Clamp((int)(n * frac), 0, n - 1), ref img, Voxels.ESliceMode.SignedDistance, axis);
        int s = Math.Max(1, 900 / Math.Max(img.nWidth, img.nHeight));
        using var bmp = new SKBitmap(img.nWidth * s, img.nHeight * s);
        for (int y = 0; y < img.nHeight; y++)
            for (int x = 0; x < img.nWidth; x++)
            {
                float d = img.fValue(x, y);
                var col = d < -0.5f ? new SKColor(60, 70, 85) : d < 0.5f ? new SKColor(31, 95, 168) : new SKColor(250, 250, 250);
                for (int yy = 0; yy < s; yy++) for (int xx = 0; xx < s; xx++) bmp.SetPixel(x * s + xx, (img.nHeight - 1 - y) * s + yy, col);
            }
        using var data = bmp.Encode(SKEncodedImageFormat.Png, 90);
        using var f = File.OpenWrite(path); data.SaveTo(f);
    }
}
