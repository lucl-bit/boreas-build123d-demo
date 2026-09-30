using System.Numerics;
using PicoGK;

namespace BoreasVoxel;

/// <summary>Gruppe body_fins: geneigte Aero-Fins Rumpf -> Motor, NACA-Tropfenprofil, entlang der Vorderkante verschoben, bei split_z abgeschnitten.</summary>
public static class BodyFins
{
    public static List<Op> Build(Library lib, Skeleton sk, GroupView g)
    {
        float c = g.F("profile_chord"), Tr = g.F("thickness_root"), Tt = g.F("thickness_tip"), p = g.F("max_thickness_pos");
        float zr = g.F("le_height_root"), zt = g.F("le_height_tip"), cant = g.F("cant_angle");
        float z0 = sk.SplitZ, rJ = sk.JointRadius, RM = sk.MotorRadius;
        (float T, float zLE) F(float s) { float lam = (s - rJ) / (RM - rJ); return (Tr + (Tt - Tr) * lam, z0 + zr + (zt - zr) * lam); }

        var stations = Profiles.Stations(0, RM, 12f);
        var ideal = new TriMesh(); var fins = new Voxels(lib);
        for (int i = 0; i < sk.ArmCount; i++)
        {
            float th = sk.ArmAngle(i);
            var raw = Profiles.SpanLoft(th, stations, F, c, p);
            if (MathF.Abs(cant) > 1e-4f)
            {
                // Drehung um die Spannweitenachse {q = 0, z = z0}: positiv = Oberseite Richtung +q
                var e = new Vector3(MathF.Cos(th * Geo.Deg), MathF.Sin(th * Geo.Deg), 0); var t = new Vector3(-e.Y, e.X, 0);
                float ca = MathF.Cos(cant * Geo.Deg), sa = MathF.Sin(cant * Geo.Deg);
                raw = raw.Transformed(v => { float zz = v.Z - z0; float qq = Vector3.Dot(v, t); float s = Vector3.Dot(v, e); float q2 = qq * ca + zz * sa, z2 = -qq * sa + zz * ca; return e * s + t * q2 + new Vector3(0, 0, z0 + z2); });
            }
            ideal.Append(raw);
            fins.BoolAdd(raw.ToVoxels(lib));
        }
        // Fin = Fin_roh  ∩  {z >= z0}
        var half = Geo.LocalBox(0, -400, 400, -400, 400, z0, z0 + 400).ToVoxels(lib);
        fins.BoolIntersect(half);
        return new List<Op> { new("upper", false, fins, "Fins", 0, ideal) };
    }
}
