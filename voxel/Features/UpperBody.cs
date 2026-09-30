using System.Numerics;
using PicoGK;

namespace BoreasVoxel;

/// <summary>Gruppe upper_body: fassfoermiges Rohr (Rotationskoerper), Innenkontur, NACA-Kuehlluft-Einlaesse.</summary>
public static class UpperBody
{
    public static List<Op> Build(Library lib, Skeleton sk, GroupView g)
    {
        float wall = g.F("wall"), bulge = g.F("bulge"), bpos = g.F("bulge_pos");
        float z0 = sk.SplitZ, zN = sk.NoseJointZ, H = zN - z0;
        float q = MathF.Log(0.5f) / MathF.Log(bpos);
        float Ro(float z) { float zeta = Math.Clamp((z - z0) / H, 0f, 1f); return sk.JointRadius + (sk.NoseJointRadius - sk.JointRadius) * zeta + bulge * MathF.Sin(MathF.PI * MathF.Pow(zeta, q)); }
        float Ri(float z) => Ro(Math.Clamp(z, z0, zN)) - wall;
        int seg = Geo.Segs(sk.JointRadius + bulge, lib.fVoxelSize);
        int nz = Math.Max(60, (int)MathF.Ceiling(H / 1.0f));

        var outer = new List<Vector2> { new(0, z0) };
        for (int i = 0; i <= nz; i++) { float z = z0 + H * i / nz; outer.Add(new Vector2(Ro(z), z)); }
        outer.Add(new Vector2(0, zN));
        var meshO = Geo.Revolve(outer, seg);

        var inner = new List<Vector2> { new(0, z0 - 1) };
        inner.Add(new Vector2(Ri(z0), z0 - 1));
        for (int i = 0; i <= nz; i++) { float z = z0 + H * i / nz; inner.Add(new Vector2(Ri(z), z)); }
        inner.Add(new Vector2(Ri(zN), zN + 1)); inner.Add(new Vector2(0, zN + 1));
        var meshI = Geo.Revolve(inner, seg);

        var ops = new List<Op>
        {
            new("upper", false, meshO.ToVoxels(lib), "Rohr_aussen", 0, meshO),
            new("upper", true, meshI.ToVoxels(lib), "Rohr_innen", 1, meshI)
        };

        if (g.B("intake_enabled"))
        {
            float len = g.F("intake_length"), top = g.F("intake_top_offset"), wl = g.F("intake_width"), wt = g.F("intake_width_top"), depth = g.F("intake_depth");
            float zt = zN - top, zl = zt - len;
            float uMax = sk.JointRadius + bulge + sk.NoseJointRadius;   // grosszuegig ueber die Aussenkontur
            var intakes = new TriMesh();
            for (int i = 0; i < sk.ArmCount; i++)
            {
                float phi = sk.ArmAngleOffset + (i + 0.5f) * 360f / sk.ArmCount;
                float uT = Ro(zt), uL = Ro(zl) - depth;
                var ringT = new[] { new Vector2(uT, -wt / 2), new Vector2(uMax, -wt / 2), new Vector2(uMax, wt / 2), new Vector2(uT, wt / 2) };
                var ringL = new[] { new Vector2(uL, -wl / 2), new Vector2(uMax, -wl / 2), new Vector2(uMax, wl / 2), new Vector2(uL, wl / 2) };
                float c = MathF.Cos(phi * Geo.Deg), s = MathF.Sin(phi * Geo.Deg);
                Vector3 P(Vector2 v, float z) => new(c * v.X - s * v.Y, s * v.X + c * v.Y, z);
                intakes.Append(Geo.Loft(new[] { ringL.Select(v => P(v, zl)).ToArray(), ringT.Select(v => P(v, zt)).ToArray() }));
            }
            ops.Add(new Op("upper", true, intakes.ToVoxels(lib), "Einlaesse", 3, intakes));
        }
        return ops;
    }
}
