using System.Numerics;
using PicoGK;
using SkiaSharp;

namespace BoreasVoxel;

/// <summary>Schreibt Teile (binaeres STL), Gesamtnetz und Vorschau-PNG; berechnet die Kennwerte je Teil aus dem Netz.</summary>
public static class Outputs
{
    public static readonly Dictionary<string, SKColor> PartColors = new()
    {
        ["upper"] = new SKColor(90, 150, 210), ["lower"] = new SKColor(120, 190, 130), ["nose"] = new SKColor(230, 150, 90), ["nose_insert"] = new SKColor(200, 90, 90)
    };

    /// <summary>Teile als STL + model.stl + preview.png; fuellt result.Metrics/Files.</summary>
    public static Dictionary<string, TriMesh> WriteModel(Ctx c, TaskResult r, IDictionary<string, Voxels> parts, string sub = "", bool preview = true)
    {
        string P(string f) => string.IsNullOrEmpty(sub) ? f : sub + "/" + f;
        double rho = c.Spec.MetaNumber("density_g_cm3") ?? 1.24;
        var meshes = new Dictionary<string, TriMesh>();
        var partFiles = new Dictionary<string, object?>(); var partMetrics = new Dictionary<string, object?>();
        var all = new TriMesh(); double vol = 0, area = 0;
        var sw = System.Diagnostics.Stopwatch.StartNew();
        void Log(string s) { Console.Error.WriteLine($"  [{sw.Elapsed.TotalSeconds:0.0}s] {s}"); }
        foreach (var kv in parts)
        {
            var t = kv.Value.ToTri(); meshes[kv.Key] = t; Log($"{kv.Key}: Netz {t.TriCount} Dreiecke");
            t.SaveBinaryStl(c.Out(P(kv.Key + ".stl")), "Boreas voxel " + kv.Key); Log("STL");
            partFiles[kv.Key] = P(kv.Key + ".stl");
            var mp = t.Mass(); double a = t.Area(); Log("Masse"); var topo = t.CheckTopology(1e-4); Log("Topologie");
            partMetrics[kv.Key] = new Dictionary<string, object?>
            {
                ["volume_mm3"] = mp.Volume, ["area_mm2"] = a, ["mass_g"] = mp.Volume * rho / 1000.0, ["bbox_mm"] = Analysis.BBoxOf(t),
                ["centroid_mm"] = mp.Centroid, ["watertight"] = topo.Watertight, ["closed_and_oriented"] = topo.ClosedAndOriented,
                ["triangles"] = t.TriCount, ["topology"] = topo.ToDict()
            };
            all.Append(t); vol += mp.Volume; area += a;
        }
        // Kein zusaetzliches model.stl: Voxelnetze sind gross (Mio. Dreiecke), der Runner setzt das Gesamtnetz aus den Teilen zusammen.
        r.Files["parts"] = partFiles;
        r.Metrics["volume_mm3"] = vol; r.Metrics["area_mm2"] = area; r.Metrics["mass_g"] = vol * rho / 1000.0;
        r.Metrics["bbox_mm"] = Analysis.BBoxOf(all); r.Metrics["density_g_cm3"] = rho; r.Metrics["parts"] = partMetrics;
        r.Metrics["watertight_all"] = partMetrics.Values.All(v => (bool)((Dictionary<string, object?>)v!)["watertight"]!);
        if (preview)
        {
            var layers = meshes.Select(kv => new Preview.Layer { Mesh = kv.Value, Name = kv.Key, Color = PartColors.GetValueOrDefault(kv.Key, new SKColor(180, 180, 190)) }).ToList();
            Preview.RenderPng(layers, c.Out(P("preview.png")));
            r.Files["image"] = P("preview.png");
        }
        return meshes;
    }
}
