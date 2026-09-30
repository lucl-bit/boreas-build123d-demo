using System.Numerics;
using System.Security.Cryptography;
using PicoGK;

namespace BoreasVoxel;

/// <summary>Eigenes, indiziertes Dreiecksnetz (unabhaengig von PicoGK.Mesh) fuer Loft-Konstruktion,
/// STL-Ein-/Ausgabe, Topologie-Pruefung und Masseneigenschaften.</summary>
public sealed class TriMesh
{
    public readonly List<Vector3> V = new();
    public readonly List<int> T = new();      // 3 Indizes je Dreieck
    public int TriCount => T.Count / 3;

    public int Add(Vector3 p) { V.Add(p); return V.Count - 1; }
    public void Tri(int a, int b, int c) { T.Add(a); T.Add(b); T.Add(c); }
    public void Tri(Vector3 a, Vector3 b, Vector3 c) { int i = Add(a); Add(b); Add(c); Tri(i, i + 1, i + 2); }
    public void Quad(int a, int b, int c, int d) { Tri(a, b, c); Tri(a, c, d); }

    public void Append(TriMesh o)
    {
        int off = V.Count; V.AddRange(o.V);
        foreach (var i in o.T) T.Add(i + off);
    }

    public TriMesh Transformed(Func<Vector3, Vector3> f)
    {
        var m = new TriMesh(); foreach (var v in V) m.V.Add(f(v)); m.T.AddRange(T); return m;
    }
    public TriMesh Transformed(Matrix4x4 mat) => Transformed(v => Vector3.Transform(v, mat));
    public TriMesh Flipped()
    {
        var m = new TriMesh(); m.V.AddRange(V);
        for (int i = 0; i < T.Count; i += 3) m.Tri(T[i], T[i + 2], T[i + 1]);
        return m;
    }

    public (Vector3 min, Vector3 max) BBox()
    {
        var mn = new Vector3(float.MaxValue); var mx = new Vector3(float.MinValue);
        foreach (var v in V) { mn = Vector3.Min(mn, v); mx = Vector3.Max(mx, v); }
        return (mn, mx);
    }

    // ---- PicoGK <-> TriMesh -------------------------------------------------
    public static TriMesh FromPico(PicoGK.Mesh m)
    {
        var t = new TriMesh();
        int nv = m.nVertexCount();
        for (int i = 0; i < nv; i++) t.V.Add(m.vecVertexAt(i));
        int nt = m.nTriangleCount();
        for (int i = 0; i < nt; i++) { var tri = m.oTriangleAt(i); t.Tri(tri.A, tri.B, tri.C); }
        return t;
    }

    public PicoGK.Mesh ToPico(Library lib)
    {
        var m = new PicoGK.Mesh(lib);
        var map = new int[V.Count];
        for (int i = 0; i < V.Count; i++) map[i] = m.nAddVertex(V[i]);
        for (int i = 0; i < T.Count; i += 3) m.nAddTriangle(map[T[i]], map[T[i + 1]], map[T[i + 2]]);
        return m;
    }

    // ---- STL ---------------------------------------------------------------
    public void SaveBinaryStl(string path, string header = "Boreas voxel (PicoGK)")
    {
        Directory.CreateDirectory(System.IO.Path.GetDirectoryName(System.IO.Path.GetFullPath(path))!);
        using var fs = new FileStream(path, FileMode.Create, FileAccess.Write, FileShare.None, 1 << 20);
        using var w = new BinaryWriter(fs);
        var h = new byte[80]; System.Text.Encoding.ASCII.GetBytes(header.Length > 79 ? header[..79] : header, 0, Math.Min(79, header.Length), h, 0);
        w.Write(h); w.Write((uint)TriCount);
        for (int i = 0; i < T.Count; i += 3)
        {
            var a = V[T[i]]; var b = V[T[i + 1]]; var c = V[T[i + 2]];
            var n = Vector3.Cross(b - a, c - a); float l = n.Length(); n = l > 0 ? n / l : Vector3.Zero;
            w.Write(n.X); w.Write(n.Y); w.Write(n.Z);
            w.Write(a.X); w.Write(a.Y); w.Write(a.Z); w.Write(b.X); w.Write(b.Y); w.Write(b.Z); w.Write(c.X); w.Write(c.Y); w.Write(c.Z);
            w.Write((ushort)0);
        }
    }

    /// <summary>Binaeres oder ASCII-STL lesen; Eckpunkte werden ueber exakte Koordinaten verschweisst.</summary>
    public static TriMesh LoadStl(string path)
    {
        var bytes = File.ReadAllBytes(path);
        var m = new TriMesh();
        var map = new Dictionary<(float, float, float), int>();
        int Idx(float x, float y, float z)
        {
            if (!map.TryGetValue((x, y, z), out int i)) { i = m.Add(new Vector3(x, y, z)); map[(x, y, z)] = i; }
            return i;
        }
        bool binary = bytes.Length >= 84 && 84L + 50L * BitConverter.ToUInt32(bytes, 80) == bytes.Length;
        if (binary)
        {
            uint n = BitConverter.ToUInt32(bytes, 80);
            for (uint i = 0; i < n; i++)
            {
                int o = 84 + 50 * (int)i + 12;
                int a = Idx(BitConverter.ToSingle(bytes, o), BitConverter.ToSingle(bytes, o + 4), BitConverter.ToSingle(bytes, o + 8));
                int b = Idx(BitConverter.ToSingle(bytes, o + 12), BitConverter.ToSingle(bytes, o + 16), BitConverter.ToSingle(bytes, o + 20));
                int c = Idx(BitConverter.ToSingle(bytes, o + 24), BitConverter.ToSingle(bytes, o + 28), BitConverter.ToSingle(bytes, o + 32));
                m.Tri(a, b, c);
            }
        }
        else
        {
            var tri = new List<int>();
            foreach (var line in System.Text.Encoding.ASCII.GetString(bytes).Split('\n'))
            {
                var s = line.Trim();
                if (!s.StartsWith("vertex")) continue;
                var p = s.Split(' ', StringSplitOptions.RemoveEmptyEntries);
                tri.Add(Idx(float.Parse(p[1], System.Globalization.CultureInfo.InvariantCulture), float.Parse(p[2], System.Globalization.CultureInfo.InvariantCulture), float.Parse(p[3], System.Globalization.CultureInfo.InvariantCulture)));
                if (tri.Count == 3) { m.Tri(tri[0], tri[1], tri[2]); tri.Clear(); }
            }
        }
        return m;
    }

    // ---- Kennwerte ---------------------------------------------------------
    public double Area()
    {
        double s = 0;
        for (int i = 0; i < T.Count; i += 3) s += 0.5 * Vector3.Cross(V[T[i + 1]] - V[T[i]], V[T[i + 2]] - V[T[i]]).Length();
        return s;
    }

    /// <summary>Volumen, Schwerpunkt und Traegheitstensor (Dichte 1, Ursprung = Koordinatenursprung) ueber den Divergenzsatz.</summary>
    public MassProps Mass()
    {
        double vol = 0; double cx = 0, cy = 0, cz = 0;
        double xx = 0, yy = 0, zz = 0, xy = 0, xz = 0, yz = 0;   // Integrale von x^2 etc. ueber das Volumen
        for (int i = 0; i < T.Count; i += 3)
        {
            var a = V[T[i]]; var b = V[T[i + 1]]; var c = V[T[i + 2]];
            double d = Vector3.Dot(a, Vector3.Cross(b, c));      // 6 * Tetraedervolumen
            vol += d / 6.0;
            cx += d / 24.0 * (a.X + b.X + c.X); cy += d / 24.0 * (a.Y + b.Y + c.Y); cz += d / 24.0 * (a.Z + b.Z + c.Z);
            double f(double p, double q, double r) => p * p + q * q + r * r + p * q + p * r + q * r;
            xx += d / 60.0 * f(a.X, b.X, c.X); yy += d / 60.0 * f(a.Y, b.Y, c.Y); zz += d / 60.0 * f(a.Z, b.Z, c.Z);
            double g(double a1, double b1, double c1, double a2, double b2, double c2) =>
                2 * (a1 * a2 + b1 * b2 + c1 * c2) + a1 * b2 + a1 * c2 + b1 * a2 + b1 * c2 + c1 * a2 + c1 * b2;
            xy += d / 120.0 * g(a.X, b.X, c.X, a.Y, b.Y, c.Y);
            xz += d / 120.0 * g(a.X, b.X, c.X, a.Z, b.Z, c.Z);
            yz += d / 120.0 * g(a.Y, b.Y, c.Y, a.Z, b.Z, c.Z);
        }
        var mp = new MassProps { Volume = vol };
        if (Math.Abs(vol) > 1e-12) mp.Centroid = new double[] { cx / vol, cy / vol, cz / vol };
        else mp.Centroid = new double[] { 0, 0, 0 };
        // Traegheitstensor um den Schwerpunkt (Dichte 1)
        double Ixx = (yy + zz) - vol * (mp.Centroid[1] * mp.Centroid[1] + mp.Centroid[2] * mp.Centroid[2]);
        double Iyy = (xx + zz) - vol * (mp.Centroid[0] * mp.Centroid[0] + mp.Centroid[2] * mp.Centroid[2]);
        double Izz = (xx + yy) - vol * (mp.Centroid[0] * mp.Centroid[0] + mp.Centroid[1] * mp.Centroid[1]);
        double Ixy = -(xy - vol * mp.Centroid[0] * mp.Centroid[1]);
        double Ixz = -(xz - vol * mp.Centroid[0] * mp.Centroid[2]);
        double Iyz = -(yz - vol * mp.Centroid[1] * mp.Centroid[2]);
        mp.Inertia = new double[][] { new[] { Ixx, Ixy, Ixz }, new[] { Ixy, Iyy, Iyz }, new[] { Ixz, Iyz, Izz } };
        return mp;
    }

    /// <summary>Topologie ueber verschweisste Eckpunkte (Toleranz weld).</summary>
    public Topology CheckTopology(double weld = 1e-3)
    {
        var map = new Dictionary<(long, long, long), int>();
        var rep = new int[V.Count];
        int nw = 0;
        for (int i = 0; i < V.Count; i++)
        {
            var k = ((long)Math.Round(V[i].X / weld), (long)Math.Round(V[i].Y / weld), (long)Math.Round(V[i].Z / weld));
            if (!map.TryGetValue(k, out int id)) { id = nw++; map[k] = id; }
            rep[i] = id;
        }
        var edges = new Dictionary<(int, int), (int fwd, int bwd)>();
        var parent = Enumerable.Range(0, nw).ToArray();
        int Find(int x) { while (parent[x] != x) { parent[x] = parent[parent[x]]; x = parent[x]; } return x; }
        int degenerate = 0, nt = 0;
        for (int i = 0; i < T.Count; i += 3)
        {
            int a = rep[T[i]], b = rep[T[i + 1]], c = rep[T[i + 2]];
            if (a == b || b == c || a == c) { degenerate++; continue; }
            nt++;
            parent[Find(a)] = Find(b); parent[Find(b)] = Find(c);
            foreach (var (p, q) in new[] { (a, b), (b, c), (c, a) })
            {
                var key = (Math.Min(p, q), Math.Max(p, q));
                edges.TryGetValue(key, out var e);
                if (p < q) e.fwd++; else e.bwd++;
                edges[key] = e;
            }
        }
        int open = 0, nonMan = 0, inconsistent = 0;
        foreach (var (f, b) in edges.Values)
        {
            int tot = f + b;
            if (tot == 1) open++;
            else if (tot > 2) nonMan++;
            else if (f != 1 || b != 1) inconsistent++;
        }
        var used = new HashSet<int>();
        for (int i = 0; i < T.Count; i++) used.Add(rep[T[i]]);
        var comps = new HashSet<int>(); foreach (var u in used) comps.Add(Find(u));
        int euler = used.Count - edges.Count + nt;
        return new Topology
        {
            Triangles = TriCount, VerticesWelded = used.Count, DegenerateTriangles = degenerate, OpenEdges = open,
            NonManifoldEdges = nonMan, InconsistentOrientationEdges = inconsistent,
            Watertight = open == 0 && nonMan == 0, ClosedAndOriented = open == 0 && nonMan == 0 && inconsistent == 0,
            Components = comps.Count, EulerCharacteristic = euler, WeldTolMm = weld
        };
    }

    /// <summary>Stabiler Geometrie-Hash (Eckpunkte auf 1e-3 mm gerundet, reihenfolge-unabhaengig ueber sortierte Dreiecke).</summary>
    public string GeometryHash()
    {
        var keys = new List<string>(TriCount);
        for (int i = 0; i < T.Count; i += 3)
        {
            var s = new[] { Q(V[T[i]]), Q(V[T[i + 1]]), Q(V[T[i + 2]]) }; Array.Sort(s, StringComparer.Ordinal);
            keys.Add(string.Join("|", s));
        }
        keys.Sort(StringComparer.Ordinal);
        using var sha = SHA1.Create();
        foreach (var k in keys) sha.TransformBlock(System.Text.Encoding.ASCII.GetBytes(k), 0, k.Length, null, 0);
        sha.TransformFinalBlock(Array.Empty<byte>(), 0, 0);
        return Convert.ToHexString(sha.Hash!)[..16].ToLowerInvariant();
        static string Q(Vector3 v) => $"{Math.Round(v.X, 3):0.###},{Math.Round(v.Y, 3):0.###},{Math.Round(v.Z, 3):0.###}";
    }
}

public sealed class MassProps
{
    public double Volume; public double[] Centroid = new double[3]; public double[][] Inertia = Array.Empty<double[]>();
}

public sealed class Topology
{
    public int Triangles, VerticesWelded, DegenerateTriangles, OpenEdges, NonManifoldEdges, InconsistentOrientationEdges, Components, EulerCharacteristic;
    public bool Watertight, ClosedAndOriented; public double WeldTolMm;
    public Dictionary<string, object> ToDict() => new()
    {
        ["triangles"] = Triangles, ["vertices_welded"] = VerticesWelded, ["weld_tol_mm"] = WeldTolMm,
        ["degenerate_triangles"] = DegenerateTriangles, ["open_edges"] = OpenEdges, ["non_manifold_edges"] = NonManifoldEdges,
        ["inconsistent_orientation_edges"] = InconsistentOrientationEdges, ["watertight"] = Watertight,
        ["closed_and_oriented"] = ClosedAndOriented, ["components"] = Components, ["euler_characteristic"] = EulerCharacteristic
    };
}
