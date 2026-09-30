using System.Numerics;
using PicoGK;

namespace BoreasVoxel;

/// <summary>Gruppe joints: Nasen-Schlitze/-Laschen, Randkerben Unterteil, Laschen Oberteil (docs/geometrie_definition.md Kap. 9).
/// Laschenmasse sind abgeleitet (Schlitz − Spiel). Stufen: 2 = nach den Hohlraeumen anfuegen, 3 = zuletzt abziehen.</summary>
public static class Joints
{
    public static List<Op> Build(Library lib, Skeleton sk, GroupView g)
    {
        float cl = g.F("clearance"), sw = g.F("nose_slot_width"), sd = g.F("nose_slot_depth"), nt = g.F("nose_tab_thickness");
        float nha = g.F("rim_notch_half_angle"), nd = g.F("rim_notch_depth"), nm = g.F("rim_notch_margin"), ut = g.F("upper_tab_thickness");
        int nCount = g.I("nose_tab_count"); float nAngle = g.F("nose_tab_angle"); bool upperTab = g.B("upper_tab_enabled");
        float zN = sk.NoseJointZ, rN = sk.NoseJointRadius, z0 = sk.SplitZ, rJ = sk.JointRadius;

        var slots = new TriMesh(); var noseTabs = new TriMesh(); var notches = new TriMesh(); var tabs = new TriMesh();
        for (int k = 0; k < nCount; k++)
        {
            float a = nAngle + k * 360f / nCount;
            float r0 = rN - nt - cl;
            slots.Append(Geo.LocalBox(a, r0, r0 + 20, -sw / 2, sw / 2, zN - sd, zN - sd + 20));
            // Lasche: {|v| <= Schlitz/2 − Spiel, rN − nt <= rho <= rN, zN − (sd − Spiel) <= z <= zN}
            float hw = sw / 2 - cl;
            noseTabs.Append(Geo.Prism(Rot(ChordBand(rN - nt, rN, hw), a), zN - (sd - cl), zN));
        }
        float rMid = rJ - ut / 2, tabHalf = nha - cl / rMid / Geo.Deg;
        for (int i = 0; i < sk.ArmCount; i++)
        {
            float psi = sk.ArmAngleOffset + i * 360f / sk.ArmCount;       // Nennwinkel (ungespreizt)
            notches.Append(Geo.Prism(Sector(psi, nha, 0, rJ + nm), z0 - nd, z0 + 5));
            if (upperTab) tabs.Append(Geo.Prism(Sector(psi, tabHalf, rJ - ut, rJ), z0 - (nd - cl), z0));
        }
        var ops = new List<Op>
        {
            new("upper", true, slots.ToVoxels(lib), "Nasen-Schlitze", 3, slots),
            new("nose", false, noseTabs.ToVoxels(lib), "Nasen-Laschen", 2, noseTabs),
            new("lower", true, notches.ToVoxels(lib), "Randkerben", 3, notches)
        };
        if (upperTab) ops.Add(new Op("upper", false, tabs.ToVoxels(lib), "Laschen_OT", 2, tabs));
        return ops;
    }

    /// <summary>Ring- oder Kreissektor (Polygon in XY) um die Rumpfachse.</summary>
    static Vector2[] Sector(float centerDeg, float halfDeg, float rIn, float rOut, int n = 48)
    {
        var pts = new List<Vector2>();
        for (int j = 0; j <= n; j++) { float a = (centerDeg - halfDeg + 2 * halfDeg * j / n) * Geo.Deg; pts.Add(new Vector2(rOut * MathF.Cos(a), rOut * MathF.Sin(a))); }
        if (rIn <= 1e-4f) pts.Add(Vector2.Zero);
        else for (int j = n; j >= 0; j--) { float a = (centerDeg - halfDeg + 2 * halfDeg * j / n) * Geo.Deg; pts.Add(new Vector2(rIn * MathF.Cos(a), rIn * MathF.Sin(a))); }
        return pts.ToArray();
    }

    /// <summary>Band |v| <= hw zwischen zwei Kreisen (lokal u radial, v quer), Kreisboegen als Enden.</summary>
    static Vector2[] ChordBand(float rIn, float rOut, float hw, int n = 16)
    {
        var pts = new List<Vector2>();
        for (int j = 0; j <= n; j++) { float v = -hw + 2 * hw * j / n; pts.Add(new Vector2(MathF.Sqrt(rOut * rOut - v * v), v)); }
        for (int j = n; j >= 0; j--) { float v = -hw + 2 * hw * j / n; pts.Add(new Vector2(MathF.Sqrt(MathF.Max(rIn * rIn - v * v, 0)), v)); }
        return pts.ToArray();
    }

    static Vector2[] Rot(Vector2[] p, float deg)
    {
        float c = MathF.Cos(deg * Geo.Deg), s = MathF.Sin(deg * Geo.Deg);
        return p.Select(v => new Vector2(c * v.X - s * v.Y, s * v.X + c * v.Y)).ToArray();
    }
}

/// <summary>Gruppe details: Nachbearbeitung auf Teil-Ebene. Voxel-Weg: lokale Verrundung per Fillet (Offset-Trick) im Bereich der
/// Gondel-Uebergaenge bzw. der Heckflossen-Wurzeln – ohne Kantenauswahl, nur ueber eine Einflusszone.</summary>
public static class Details
{
    public static List<Op> Build(Library lib, Skeleton sk, GroupView g)
    {
        float podF = g.F("pod_fillet"), tailF = g.F("tail_root_fillet");
        var ops = new List<Op>();
        if (podF > 1e-4f)
        {
            ops.Add(new Op("upper", false, null, $"Gondel-Verrundung r={podF}", 9, null, v =>
            {
                // Zone: Zylinder um jede Motorachse, grosszuegig; darin konkave (Fillet) und konvexe (Offset −/+) Kanten runden
                var zone = new TriMesh();
                for (int i = 0; i < sk.ArmCount; i++)
                {
                    var m = sk.MotorPos(i);
                    zone.Append(Geo.Revolve(new List<Vector2> { new(0, sk.SplitZ - 1), new(25, sk.SplitZ - 1), new(25, sk.SplitZ + 60), new(0, sk.SplitZ + 60) }, 64)
                        .Transformed(p => p + new Vector3(m.X, m.Y, 0)));
                }
                return Blend(lib, v, zone.ToVoxels(lib), podF);
            }));
        }
        if (tailF > 1e-4f)
        {
            ops.Add(new Op("lower", false, null, $"Heckflossen-Wurzel r={tailF}", 9, null, v =>
            {
                var zone = Geo.Revolve(new List<Vector2> { new(0, sk.BodyBottomZ - 1), new(40, sk.BodyBottomZ - 1), new(40, sk.BodyBottomZ + 70), new(0, sk.BodyBottomZ + 70) }, 64);
                return Blend(lib, v, zone.ToVoxels(lib), tailF);
            }));
        }
        return ops;
    }

    /// <summary>Verrundetes Feld nur innerhalb der Zone uebernehmen: (v − zone) ∪ (glatt(v) ∩ zone).</summary>
    static Voxels Blend(Library lib, Voxels v, Voxels zone, float r)
    {
        var smooth = v.voxDuplicate();
        smooth.Fillet(r);                     // konkave Kanten
        smooth = smooth.voxOffset(-r).voxOffset(r);   // konvexe Kanten
        smooth.BoolIntersect(zone);
        var res = v.voxDuplicate();
        res.BoolSubtract(zone);
        res.BoolAdd(smooth);
        return res;
    }
}
