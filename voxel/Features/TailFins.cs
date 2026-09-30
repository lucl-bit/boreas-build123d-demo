using System.Numerics;
using PicoGK;

namespace BoreasVoxel;

/// <summary>Gruppe tail_fins: gepfeilte Heckflossen (NACA-Tropfen), Spitze als Zylinderbogen, Unterkante gerade mit Eckradius.</summary>
public static class TailFins
{
    public static List<Op> Build(Library lib, Skeleton sk, GroupView g)
    {
        float span = g.F("span_radius"), tipC = g.F("tip_chord"), sweep = MathF.Tan(g.F("sweep_angle") * Geo.Deg), c = g.F("profile_chord");
        float Tr = g.F("thickness_root"), Tt = g.F("thickness_tip"), p = g.F("max_thickness_pos"), boff = g.F("bottom_offset"), cr = g.F("corner_radius");
        float rJ = sk.JointRadius, zb = sk.BodyBottomZ + boff;
        (float T, float zLE) F(float s) { float lam = (s - rJ) / (span - rJ); return (Tr + (Tt - Tr) * lam, zb + tipC + (span - s) * sweep); }

        // Clip: Rotationskoerper um die Rumpfachse der (rho, z)-Flaeche [0, span] x [zb, zb+500], Ecke (span, zb) mit Radius cr gerundet
        var prof = new List<Vector2> { new(0, zb) };
        if (cr > 1e-3f)
        {
            prof.Add(new Vector2(span - cr, zb));
            for (int k = 1; k <= 16; k++) { float a = MathF.PI / 2 * k / 16; prof.Add(new Vector2(span - cr + cr * MathF.Sin(a), zb + cr - cr * MathF.Cos(a))); }
        }
        else prof.Add(new Vector2(span, zb));
        prof.Add(new Vector2(span, zb + 500)); prof.Add(new Vector2(0, zb + 500));
        var clip = Geo.Revolve(prof, Geo.Segs(span, lib.fVoxelSize)).ToVoxels(lib);

        var stations = Profiles.Stations(0, span + 5, 10f);
        var ideal = new TriMesh(); var fins = new Voxels(lib);
        for (int i = 0; i < sk.ArmCount; i++)
        {
            var raw = Profiles.SpanLoft(sk.ArmAngle(i), stations, F, c, p);
            ideal.Append(raw); fins.BoolAdd(raw.ToVoxels(lib));
        }
        fins.BoolIntersect(clip);
        return new List<Op> { new("lower", false, fins, "Heckflossen", 0, ideal) };
    }
}
