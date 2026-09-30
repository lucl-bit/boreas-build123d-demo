using System.Numerics;
using PicoGK;

namespace BoreasVoxel;

/// <summary>Geometrie-Helfer: Lofts/Rotationskoerper als geschlossene Netze, Netz->Voxel, Voxel->Netz, Volumen.
/// Konstruktionsprinzip: Formen werden als GESCHLOSSENE DREIECKSNETZE aus Querschnittsringen aufgebaut
/// (schnell, Aufwand ~ Oberflaeche) und dann mit new Voxels(mesh) gerastert. Boolesche Operationen laufen danach im Voxelfeld.</summary>
public static class Geo
{
    public const float Deg = MathF.PI / 180f;

    /// <summary>Ring-Loft: gleich viele Punkte je Ring, Ringe hintereinander; Enden werden mit ebenen Kappen geschlossen
    /// (Faecher bei konvexen Ringen, sonst Ear-Clipping). Ringe, die auf einen Punkt zusammenfallen, gelten als Spitze.</summary>
    public static TriMesh Loft(IList<Vector3[]> rings, bool capStart = true, bool capEnd = true)
    {
        var m = new TriMesh();
        int n = rings[0].Length, k = rings.Count;
        var idx = new int[k][];
        for (int i = 0; i < k; i++)
        {
            idx[i] = new int[n];
            for (int j = 0; j < n; j++) idx[i][j] = m.Add(rings[i][j]);
        }
        for (int i = 0; i + 1 < k; i++)
            for (int j = 0; j < n; j++)
            {
                int j2 = (j + 1) % n;
                Vector3 a = rings[i][j], b = rings[i][j2], c = rings[i + 1][j2], d = rings[i + 1][j];
                bool degA = (a - b).LengthSquared() < 1e-10f, degB = (c - d).LengthSquared() < 1e-10f;
                if (!degA && !degB) { m.Tri(idx[i][j], idx[i][j2], idx[i + 1][j2]); m.Tri(idx[i][j], idx[i + 1][j2], idx[i + 1][j]); }
                else if (degA && !degB) m.Tri(idx[i][j], idx[i + 1][j2], idx[i + 1][j]);
                else if (!degA && degB) m.Tri(idx[i][j], idx[i][j2], idx[i + 1][j2]);
            }
        // Loftrichtung und Ringorientierung bestimmen, damit die Kappen zu den Seitenflaechen passen
        Vector3 Ctr(Vector3[] r) { var c = Vector3.Zero; foreach (var p in r) c += p; return c / r.Length; }
        var dir = Ctr(rings[k - 1]) - Ctr(rings[0]);
        var nr = Newell(rings[0]); if (nr.LengthSquared() < 1e-12f) nr = Newell(rings[k - 1]);
        float sgn = Vector3.Dot(nr, dir) >= 0 ? 1f : -1f;
        void Cap(int ring, Vector3 target)
        {
            var pts = rings[ring]; var c = Ctr(pts);
            if (pts.All(p => (p - c).LengthSquared() < 1e-10f)) return;
            foreach (var (a, b, cc) in TriangulatePolygon(pts, target)) m.Tri(idx[ring][a], idx[ring][b], idx[ring][cc]);
        }
        if (capStart) Cap(0, -dir * sgn);
        if (capEnd) Cap(k - 1, dir * sgn);
        if (m.Mass().Volume < 0) m = m.Flipped();
        return m;
    }

    public static Vector3 Newell(Vector3[] p)
    {
        Vector3 n = Vector3.Zero;
        for (int i = 0; i < p.Length; i++) { var a = p[i]; var b = p[(i + 1) % p.Length]; n += new Vector3((a.Y - b.Y) * (a.Z + b.Z), (a.Z - b.Z) * (a.X + b.X), (a.X - b.X) * (a.Y + b.Y)); }
        return n;
    }

    /// <summary>Triangulation eines ebenen, einfachen Polygons (konvex: Faecher, sonst Ear-Clipping). Die Dreiecke werden so orientiert,
    /// dass ihre Normale in Richtung target zeigt.</summary>
    public static List<(int, int, int)> TriangulatePolygon(Vector3[] pts, Vector3 target)
    {
        int n = pts.Length; var res = new List<(int, int, int)>();
        var nr = Newell(pts); if (nr.LengthSquared() < 1e-14f) return res; nr = Vector3.Normalize(nr);
        var ax = MathF.Abs(nr.X) < 0.9f ? Vector3.UnitX : Vector3.UnitY; var u = Vector3.Normalize(Vector3.Cross(nr, ax)); var v = Vector3.Cross(nr, u);
        var p2 = pts.Select(p => new Vector2(Vector3.Dot(p, u), Vector3.Dot(p, v))).ToArray();
        float Cross(Vector2 a, Vector2 b, Vector2 c) => (b.X - a.X) * (c.Y - a.Y) - (b.Y - a.Y) * (c.X - a.X);
        // Polygon ist bezueglich nr positiv (CCW) orientiert (Newell)
        bool convex = true; for (int i = 0; i < n && convex; i++) if (Cross(p2[i], p2[(i + 1) % n], p2[(i + 2) % n]) < -1e-7f) convex = false;
        if (convex) { for (int i = 1; i + 1 < n; i++) res.Add((0, i, i + 1)); }
        else
        {
            var idx = Enumerable.Range(0, n).ToList(); int guard = 0;
            while (idx.Count > 3 && guard++ < 100000)
            {
                bool clipped = false;
                for (int ii = 0; ii < idx.Count; ii++)
                {
                    int ia = idx[(ii + idx.Count - 1) % idx.Count], ib = idx[ii], ic = idx[(ii + 1) % idx.Count];
                    if (Cross(p2[ia], p2[ib], p2[ic]) <= 1e-9f) continue;
                    bool inside = false;
                    foreach (int q in idx) { if (q == ia || q == ib || q == ic) continue; if (PointInTri(p2[q], p2[ia], p2[ib], p2[ic])) { inside = true; break; } }
                    if (inside) continue;
                    res.Add((ia, ib, ic)); idx.RemoveAt(ii); clipped = true; break;
                }
                if (!clipped) break;   // entartet: Rest verwerfen
            }
            if (idx.Count == 3) res.Add((idx[0], idx[1], idx[2]));
        }
        // Orientierung
        if (Vector3.Dot(nr, target) < 0) res = res.Select(t => (t.Item1, t.Item3, t.Item2)).ToList();
        return res;
    }
    static bool PointInTri(Vector2 p, Vector2 a, Vector2 b, Vector2 c)
    {
        float d1 = (p.X - b.X) * (a.Y - b.Y) - (a.X - b.X) * (p.Y - b.Y), d2 = (p.X - c.X) * (b.Y - c.Y) - (b.X - c.X) * (p.Y - c.Y), d3 = (p.X - a.X) * (c.Y - a.Y) - (c.X - a.X) * (p.Y - a.Y);
        bool neg = d1 < 0 || d2 < 0 || d3 < 0, pos = d1 > 0 || d2 > 0 || d3 > 0; return !(neg && pos);
    }

    /// <summary>Prisma aus einem XY-Polygon (Punkte in Reihenfolge) zwischen z0 und z1.</summary>
    public static TriMesh Prism(IList<Vector2> poly, float z0, float z1)
    {
        var a = poly.Select(p => new Vector3(p.X, p.Y, z0)).ToArray(); var b = poly.Select(p => new Vector3(p.X, p.Y, z1)).ToArray();
        return Loft(new[] { a, b });
    }

    /// <summary>Quader in lokalen Koordinaten (u radial, v quer, z) am Winkel deg um die Z-Achse.</summary>
    public static TriMesh LocalBox(float deg, float u0, float u1, float v0, float v1, float z0, float z1)
    {
        var poly = new[] { new Vector2(u0, v0), new Vector2(u1, v0), new Vector2(u1, v1), new Vector2(u0, v1) };
        float c = MathF.Cos(deg * Deg), s = MathF.Sin(deg * Deg);
        return Prism(poly.Select(p => new Vector2(c * p.X - s * p.Y, s * p.X + c * p.Y)).ToArray(), z0, z1);
    }

    /// <summary>Segmentzahl fuer Kreise: Pfeilhoehe &lt;= voxel/8, mindestens 64, Vielfaches von 4.</summary>
    public static int Segs(float radius, float voxel)
    {
        float sag = MathF.Max(voxel / 8f, 0.005f); float r = MathF.Max(radius, 0.5f);
        int n = (int)MathF.Ceiling(MathF.PI / MathF.Acos(MathF.Max(0f, 1f - sag / r)));
        n = Math.Clamp(n, 64, 1440); return (n + 3) / 4 * 4;
    }

    /// <summary>Rotationskoerper um die Z-Achse aus einem (r, z)-Profil (r &gt;= 0). Erster/letzter Punkt duerfen r=0 haben.</summary>
    public static TriMesh Revolve(IList<Vector2> profileRZ, int segments = 96, Func<float, float, float>? rScale = null)
    {
        var rings = new List<Vector3[]>();
        foreach (var p in profileRZ)
        {
            var ring = new Vector3[segments];
            for (int j = 0; j < segments; j++)
            {
                float a = 2 * MathF.PI * j / segments;
                float r = p.X * (rScale?.Invoke(a, p.Y) ?? 1f);
                ring[j] = new Vector3(r * MathF.Cos(a), r * MathF.Sin(a), p.Y);
            }
            rings.Add(ring);
        }
        return Loft(rings, profileRZ[0].X > 1e-6f, profileRZ[^1].X > 1e-6f);
    }

    public static Vector3 RotZ(Vector3 v, float deg) { float a = deg * Deg, c = MathF.Cos(a), s = MathF.Sin(a); return new Vector3(c * v.X - s * v.Y, s * v.X + c * v.Y, v.Z); }
    public static TriMesh RotatedZ(this TriMesh m, float deg) => m.Transformed(v => RotZ(v, deg));

    // ---- Voxel <-> Netz -------------------------------------------------------
    public static Voxels ToVoxels(this TriMesh m, Library lib) => new Voxels(m.ToPico(lib));
    public static TriMesh ToTri(this Voxels v) => TriMesh.FromPico(v.mshAsMesh());

    /// <summary>Volumen aus dem Oberflaechennetz (Divergenzsatz). ACHTUNG: PicoGK 2.3.0 Voxels.CalculateProperties
    /// liefert bei HOHLEN Koerpern (Innenhohlraum) das Volumen inkl. Hohlraum (getestet: Kugelschale 112845 statt 21142 mm3).
    /// Darum wird das Volumen nie ueber CalculateProperties, sondern immer ueber das Netz gerechnet.</summary>
    public static double Volume(this Voxels v) => v.ToTri().Mass().Volume;

    /// <summary>Aequivalent zu voxBoolSubtract, aber ohne den Operanden zu veraendern.</summary>
    public static Voxels Minus(this Voxels a, Voxels b) { var r = a.voxDuplicate(); r.BoolSubtract(b); return r; }
    public static Voxels Plus(this Voxels a, Voxels b) { var r = a.voxDuplicate(); r.BoolAdd(b); return r; }
    public static Voxels Both(this Voxels a, Voxels b) { var r = a.voxDuplicate(); r.BoolIntersect(b); return r; }

    /// <summary>Hohlkoerper mit Wandstaerke t (Innenraum nach innen versetzt). Explizite Variante statt voxShell(neg,pos,smooth) (in 2.3.0 defekt).</summary>
    public static Voxels Hollow(this Voxels v, float wall) => v.Minus(v.voxOffset(-wall));

    /// <summary>Implizite Funktion aus einem Lambda (vorzeichenbehafteter Abstand, negativ = innen).</summary>
    public sealed class Sdf : IImplicit
    {
        readonly Func<Vector3, float> _f;
        public Sdf(Func<Vector3, float> f) { _f = f; }
        public float fSignedDistance(in Vector3 v) => _f(v);
    }

    public static BBox3 Box(Vector3 mn, Vector3 mx) => new BBox3(mn, mx);
    public static BBox3 Box(TriMesh m, float pad = 0) { var (a, b) = m.BBox(); return new BBox3(a - new Vector3(pad), b + new Vector3(pad)); }

    // ---- Skalarfunktionen ------------------------------------------------------
    public static float Smoothstep(float e0, float e1, float x) { float t = Math.Clamp((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t); }
    public static float Lerp(float a, float b, float t) => a + (b - a) * t;
    /// <summary>Lineare Interpolation in einer (x, y)-Tabelle, ausserhalb geklemmt.</summary>
    public static float Interp(IList<Vector2> tab, float x)
    {
        if (x <= tab[0].X) return tab[0].Y; if (x >= tab[^1].X) return tab[^1].Y;
        int i = 1; while (tab[i].X < x) i++;
        float t = (x - tab[i - 1].X) / (tab[i].X - tab[i - 1].X); return Lerp(tab[i - 1].Y, tab[i].Y, t);
    }
}
