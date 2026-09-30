using System.Numerics;

namespace BoreasVoxel;

/// <summary>Punkt-zu-Netz-Abstand ueber ein gleichmaessiges Raster (Zellenliste je Dreieck). Unabhaengig von Wasserdichtheit.
/// Genutzt fuer B01 (Abweichung Modell zu Referenz) und B04/B07 (Profilabweichung).</summary>
public sealed class MeshDistance
{
    readonly TriMesh _m; readonly float _cell; readonly Vector3 _origin; readonly int _nx, _ny, _nz;
    readonly Dictionary<long, List<int>> _grid = new();

    public MeshDistance(TriMesh m, float cell = 2f)
    {
        _m = m; _cell = cell;
        var (mn, mx) = m.BBox(); _origin = mn - new Vector3(cell);
        var size = mx - mn + new Vector3(2 * cell);
        _nx = (int)(size.X / cell) + 1; _ny = (int)(size.Y / cell) + 1; _nz = (int)(size.Z / cell) + 1;
        for (int t = 0; t < m.TriCount; t++)
        {
            var a = m.V[m.T[3 * t]]; var b = m.V[m.T[3 * t + 1]]; var c = m.V[m.T[3 * t + 2]];
            var lo = Vector3.Min(a, Vector3.Min(b, c)); var hi = Vector3.Max(a, Vector3.Max(b, c));
            var (x0, y0, z0) = Cell(lo); var (x1, y1, z1) = Cell(hi);
            for (int x = x0; x <= x1; x++) for (int y = y0; y <= y1; y++) for (int z = z0; z <= z1; z++)
            {
                long key = Key(x, y, z);
                if (!_grid.TryGetValue(key, out var l)) _grid[key] = l = new List<int>();
                l.Add(t);
            }
        }
    }
    (int, int, int) Cell(Vector3 p) => (Math.Clamp((int)((p.X - _origin.X) / _cell), 0, _nx - 1), Math.Clamp((int)((p.Y - _origin.Y) / _cell), 0, _ny - 1), Math.Clamp((int)((p.Z - _origin.Z) / _cell), 0, _nz - 1));
    long Key(int x, int y, int z) => ((long)x * _ny + y) * _nz + z;

    /// <summary>Kleinster Abstand von p zu einem Dreieck (Suche in wachsenden Zellschalen, maximal maxDist).</summary>
    public float Distance(Vector3 p, float maxDist = 50f)
    {
        var (cx, cy, cz) = Cell(p);
        float best = float.MaxValue;
        int maxR = (int)MathF.Ceiling(maxDist / _cell);
        for (int r = 0; r <= maxR; r++)
        {
            for (int x = cx - r; x <= cx + r; x++) for (int y = cy - r; y <= cy + r; y++) for (int z = cz - r; z <= cz + r; z++)
            {
                if (Math.Max(Math.Abs(x - cx), Math.Max(Math.Abs(y - cy), Math.Abs(z - cz))) != r) continue;
                if (x < 0 || y < 0 || z < 0 || x >= _nx || y >= _ny || z >= _nz) continue;
                if (!_grid.TryGetValue(Key(x, y, z), out var l)) continue;
                foreach (int t in l)
                {
                    float d = PointTri(p, _m.V[_m.T[3 * t]], _m.V[_m.T[3 * t + 1]], _m.V[_m.T[3 * t + 2]]);
                    if (d < best) best = d;
                }
            }
            if (best <= r * _cell) break;    // spaetere Schalen liegen mindestens r*cell entfernt
        }
        return best == float.MaxValue ? maxDist : best;
    }

    static float PointTri(Vector3 p, Vector3 a, Vector3 b, Vector3 c)
    {
        // Ericson, Real-Time Collision Detection: naechster Punkt auf Dreieck
        var ab = b - a; var ac = c - a; var ap = p - a;
        float d1 = Vector3.Dot(ab, ap), d2 = Vector3.Dot(ac, ap);
        if (d1 <= 0 && d2 <= 0) return (p - a).Length();
        var bp = p - b; float d3 = Vector3.Dot(ab, bp), d4 = Vector3.Dot(ac, bp);
        if (d3 >= 0 && d4 <= d3) return (p - b).Length();
        float vc = d1 * d4 - d3 * d2;
        if (vc <= 0 && d1 >= 0 && d3 <= 0) { float v = d1 / (d1 - d3); return (p - (a + v * ab)).Length(); }
        var cp = p - c; float d5 = Vector3.Dot(ab, cp), d6 = Vector3.Dot(ac, cp);
        if (d6 >= 0 && d5 <= d6) return (p - c).Length();
        float vb = d5 * d2 - d1 * d6;
        if (vb <= 0 && d2 >= 0 && d6 <= 0) { float w = d2 / (d2 - d6); return (p - (a + w * ac)).Length(); }
        float va = d3 * d6 - d5 * d4;
        if (va <= 0 && (d4 - d3) >= 0 && (d5 - d6) >= 0) { float w = (d4 - d3) / ((d4 - d3) + (d5 - d6)); return (p - (b + w * (c - b))).Length(); }
        float denom = 1f / (va + vb + vc); float v2 = vb * denom, w2 = vc * denom;
        return (p - (a + ab * v2 + ac * w2)).Length();
    }

    /// <summary>Statistik der Abstaende ausgewaehlter Punkte (Vertices) zu diesem Netz.</summary>
    public static Dictionary<string, object?> Deviation(TriMesh from, MeshDistance to, int maxSamples = 60000)
    {
        int step = Math.Max(1, from.V.Count / maxSamples);
        var d = new List<float>();
        for (int i = 0; i < from.V.Count; i += step) d.Add(to.Distance(from.V[i]));
        d.Sort();
        if (d.Count == 0) return new() { ["samples"] = 0 };
        double mean = d.Average(x => (double)x);
        return new()
        {
            ["samples"] = d.Count, ["mean_mm"] = mean, ["rms_mm"] = Math.Sqrt(d.Average(x => (double)x * x)),
            ["p50_mm"] = d[d.Count / 2], ["p95_mm"] = d[(int)(d.Count * 0.95)], ["p99_mm"] = d[(int)(d.Count * 0.99)], ["max_mm"] = d[^1]
        };
    }
}
