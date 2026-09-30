using System.Numerics;
using PicoGK;

namespace BoreasVoxel;

/// <summary>Gruppe lower_body: hohler Kegelrumpf, oben Kragen mit zylindrischer Bohrung, unten offen.</summary>
public static class LowerBody
{
    public static List<Op> Build(Library lib, Skeleton sk, GroupView g)
    {
        float cl = g.F("collar_length"), ct = g.F("collar_taper"), rb = g.F("bottom_radius"), wall = g.F("wall"), cw = g.F("collar_wall");
        float z0 = sk.SplitZ, zB = sk.BodyBottomZ, rJ = sk.JointRadius;
        int seg = Geo.Segs(rJ, lib.fVoxelSize);
        // Aussenkontur: (0,z0) -> A -> B -> C -> (0,zB)
        var A = new Vector2(rJ, z0); var B = new Vector2(rJ - ct, z0 - cl); var C = new Vector2(rb, zB);
        var outer = new List<Vector2> { new(0, z0), A, B, C, new(0, zB) };
        // Achtung: Revolve erwartet aufsteigende Reihenfolge nicht zwingend, Ringe werden in Profilreihenfolge verbunden
        var meshO = Geo.Revolve(outer, seg);

        // Innenkontur: r_in(z) = min(rJ - collar_wall, r_BC(z) - wall), r_BC = Gerade durch B und C (auch oberhalb B)
        float RBC(float z) => B.X + (C.X - B.X) * (z - B.Y) / (C.Y - B.Y);
        float Rin(float z) => MathF.Min(rJ - cw, RBC(z) - wall);
        // Knickstelle: rJ - cw == RBC(z) - wall  ->  linear aufloesen
        float zk = B.Y + (rJ - cw + wall - B.X) * (C.Y - B.Y) / (C.X - B.X);
        var zs = new List<float> { z0 + 1, zB - 1 };
        if (zk < z0 + 1 && zk > zB - 1) zs.Add(zk);
        zs.Sort((a, b) => b.CompareTo(a));
        var inner = new List<Vector2> { new(0, zs[0]) };
        foreach (var z in zs) inner.Add(new Vector2(Rin(z), z));
        inner.Add(new Vector2(0, zs[^1]));
        var meshI = Geo.Revolve(inner, seg);
        return new List<Op>
        {
            new("lower", false, meshO.ToVoxels(lib), "Kegel_aussen", 0, meshO),
            new("lower", true, meshI.ToVoxels(lib), "Kegel_innen", 1, meshI)
        };
    }
}
