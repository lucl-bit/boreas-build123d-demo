using System.Numerics;
using PicoGK;

namespace BoreasVoxel;

/// <summary>Gruppe arms: Stege unter dem Fin (Oberteil) und V-Kiele mit gestufter Oberseite (Unterteil).</summary>
public static class Arms
{
    public static List<Op> Build(Library lib, Skeleton sk, GroupView g)
    {
        var ops = new List<Op>();
        float z0 = sk.SplitZ, RM = sk.MotorRadius;

        // ---- Stege: {|q| <= w/2, z0-d <= z <= z0, rho_a <= rho <= rho_b}, Stirnflaechen = Zylinder um die Rumpfachse
        float ww = g.F("web_width"), wd = g.F("web_depth"), ra = g.F("web_start"), rb = RM - g.F("web_end_offset");
        if (wd > 1e-4f && rb > ra)
        {
            var webs = new TriMesh();
            for (int i = 0; i < sk.ArmCount; i++)
            {
                var poly = new List<Vector2>();
                int na = 6;
                for (int k = 0; k <= na; k++) { float qq = -ww / 2 + ww * k / na; poly.Add(new Vector2(MathF.Sqrt(ra * ra - qq * qq), qq)); }
                for (int k = na; k >= 0; k--) { float qq = -ww / 2 + ww * k / na; poly.Add(new Vector2(MathF.Sqrt(rb * rb - qq * qq), qq)); }
                float th = sk.ArmAngle(i), c = MathF.Cos(th * Geo.Deg), s = MathF.Sin(th * Geo.Deg);
                webs.Append(Geo.Prism(poly.Select(v => new Vector2(c * v.X - s * v.Y, s * v.X + c * v.Y)).ToArray(), z0 - wd, z0));
            }
            ops.Add(new Op("upper", false, webs.ToVoxels(lib), "Stege", 0, webs));
        }

        // ---- V-Kiele
        float zk = z0 - g.F("keel_top_offset"), hRoot = g.F("keel_height_root"), hTip = g.F("keel_height_tip"), tanA = MathF.Tan(g.F("keel_half_angle") * Geo.Deg);
        float rEnd = g.F("keel_end_radius"), padStart = g.F("pad_start"), padLen = g.F("pad_length"), padH = g.F("pad_height"), drop = g.F("tip_drop");
        float rJ = sk.JointRadius, se = RM - rEnd;
        float Hk(float s) => hRoot + (hTip - hRoot) * (s - rJ) / (se - rJ);
        float Zap(float s) => zk - Hk(s);
        // Abschnitte konstanter Oberkante
        var seg = new List<(float a, float b, float ztop)>();
        float padEnd = padStart + padLen;
        if (padLen > 1e-4f)
        {
            seg.Add((0, MathF.Min(padStart, RM), zk));
            if (padStart < RM) seg.Add((padStart, MathF.Min(padEnd, RM), zk + padH));
            if (padEnd < RM) seg.Add((padEnd, RM, zk - drop));
        }
        else { seg.Add((0, MathF.Min(padStart, RM), zk)); if (padStart < RM) seg.Add((padStart, RM, zk - drop)); }
        var keels = new TriMesh();
        for (int i = 0; i < sk.ArmCount; i++)
        {
            float th = sk.ArmAngle(i), c = MathF.Cos(th * Geo.Deg), sn = MathF.Sin(th * Geo.Deg);
            foreach (var (a, b, zt) in seg)
            {
                if (b - a < 1e-4f) continue;
                Vector3[] Ring(float s)
                {
                    float za = Zap(s), hw = (zt - za) * tanA;
                    Vector3 P(float qq, float z) => new(c * s - sn * qq, sn * s + c * qq, z);
                    return new[] { P(0, za), P(-hw, zt), P(hw, zt) };
                }
                keels.Append(Geo.Loft(new[] { Ring(a), Ring(b) }));
            }
        }
        var kv = keels.ToVoxels(lib);
        // Freigang zur Gondel: Zylinder r = keel_end_radius um jede Motorachse abziehen
        var cyl = new TriMesh();
        for (int i = 0; i < sk.ArmCount; i++)
        {
            var m = sk.MotorPos(i); var prof = new List<Vector2> { new(0, zk - 60), new(rEnd, zk - 60), new(rEnd, zk + 20), new(0, zk + 20) };
            cyl.Append(Geo.Revolve(prof, Geo.Segs(rEnd, lib.fVoxelSize)).Transformed(v => v + new Vector3(m.X, m.Y, 0)));
        }
        kv.BoolSubtract(cyl.ToVoxels(lib));
        ops.Add(new Op("lower", false, kv, "Kiele", 0, keels));
        return ops;
    }
}
