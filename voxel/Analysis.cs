using System.Numerics;
using PicoGK;

namespace BoreasVoxel;

/// <summary>Voxel-native Messungen: Projektionsflaeche, Schnittbilder, Wandstaerke, Massenkennwerte.</summary>
public static class Analysis
{
    /// <summary>Projizierte Flaeche in Achsrichtung (Blick entlang der Achse) aus dem Voxelfeld.
    /// Je Schicht wird die Deckung (Anteil innen, aus dem Abstandsfeld, Subvoxel-genau) bestimmt, ueber alle Schichten wird das Maximum gebildet.</summary>
    public static double ProjectedArea(Voxels v, Voxels.ESliceAxis axis, float voxel)
    {
        var img = v.imgAllocateSlice(out int n, axis);
        float[]? cover = null;
        for (int i = 0; i < n; i++)
        {
            v.GetVoxelSlice(i, ref img, Voxels.ESliceMode.SignedDistance, axis);
            cover ??= new float[img.nWidth * img.nHeight];
            for (int y = 0; y < img.nHeight; y++)
                for (int x = 0; x < img.nWidth; x++)
                {
                    float sd = img.fValue(x, y);                       // in Voxeln, <0 innen
                    float c = Math.Clamp(0.5f - sd, 0f, 1f);
                    int k = y * img.nWidth + x; if (c > cover[k]) cover[k] = c;
                }
        }
        double s = 0; if (cover != null) foreach (var c in cover) s += c;
        return s * voxel * voxel;
    }

    /// <summary>Volumen-Momente aus dem Netz: Volumen, Schwerpunkt, Traegheitstensor (um den Schwerpunkt, Dichte rho).</summary>
    public static Dictionary<string, object?> MassProperties(TriMesh m, double densityGcm3)
    {
        var mp = m.Mass();
        double rho = densityGcm3 / 1000.0;   // g/mm3
        var I = mp.Inertia.Select(r => r.Select(x => x * rho).ToArray()).ToArray();
        return new()
        {
            ["volume_mm3"] = mp.Volume, ["mass_g"] = mp.Volume * rho, ["centroid_mm"] = mp.Centroid,
            ["inertia_g_mm2"] = I, ["density_g_cm3"] = densityGcm3
        };
    }

    /// <summary>Mindest-/mittlere Wandstaerke eines Hohlkoerpers: Abstandsfeld-Methode. Fuer Punkte auf der Aussenflaeche wird der
    /// Strahl nach innen bis zum Wiederaustritt verfolgt (Netz-Raycast ueber den Voxelkern: bRayCastToSurface).</summary>
    public static Dictionary<string, object?> WallThickness(Voxels v, int samples = 4000, int seed = 1)
    {
        var m = v.ToTri(); var rng = new Random(seed);
        var d = new List<float>();
        int tries = 0;
        while (d.Count < samples && tries < samples * 4 && m.TriCount > 0)
        {
            tries++;
            int t = rng.Next(m.TriCount);
            var a = m.V[m.T[3 * t]]; var b = m.V[m.T[3 * t + 1]]; var c = m.V[m.T[3 * t + 2]];
            var n = Vector3.Cross(b - a, c - a); float nl = n.Length(); if (nl < 1e-9f) continue; n /= nl;
            var ctr = (a + b + c) / 3f;
            var start = ctr - n * 0.02f;                                // knapp unter die Flaeche
            if (v.bRayCastToSurface(start, -n, out Vector3 hit)) d.Add(Vector3.Distance(ctr, hit));
        }
        if (d.Count == 0) return new() { ["samples"] = 0 };
        d.Sort();
        return new() { ["samples"] = d.Count, ["min_mm"] = d[0], ["p05_mm"] = d[(int)(d.Count * 0.05)], ["median_mm"] = d[d.Count / 2], ["mean_mm"] = d.Average(), ["max_mm"] = d[^1] };
    }

    public static double[] BBoxOf(TriMesh m) { var (a, b) = m.BBox(); return new double[] { a.X, a.Y, a.Z, b.X, b.Y, b.Z }; }
}
