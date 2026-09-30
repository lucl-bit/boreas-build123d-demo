using System.Numerics;
using PicoGK;

namespace BoreasVoxel;

/// <summary>Gruppe motor_pods: Zylinder-Sockel + Potenz-Ogive je Motorachse, optional Schale (wall) und Kabelloch.</summary>
public static class MotorPods
{
    public static List<Op> Build(Library lib, Skeleton sk, GroupView g)
    {
        float R = g.F("radius"), hb = g.F("base_height"), hd = g.F("dome_height"), n = g.F("tip_exponent"), wall = g.F("wall"), hole = g.F("cable_hole_d");
        float z0 = sk.SplitZ; int seg = Geo.Segs(R, lib.fVoxelSize);

        List<Vector2> Profile(float zStart)
        {
            var p = new List<Vector2> { new(0, zStart), new(R, zStart), new(R, z0 + hb) };
            int m = 80;
            for (int j = 1; j <= m; j++)
            {
                float zeta = 1f - MathF.Pow(1f - (float)j / m, 2f);
                p.Add(new Vector2(j == m ? 0f : R * MathF.Pow(1f - zeta, n), z0 + hb + zeta * hd));
            }
            return p;
        }
        var solid = Geo.Revolve(Profile(z0), seg);                      // Ursprung auf der Achse (0,0), spaeter verschoben
        var ext = wall > 1e-4f ? Geo.Revolve(Profile(z0 - 3f * wall), seg) : null;
        var ideal = new TriMesh();
        // Eine Gondel je Arm. PicoGK kann Voxelfelder nicht verschieben (nur Netze transformieren), und die Verschiebung ist nicht
        // gitterausgerichtet, daher wird jede Gondel einzeln aus dem verschobenen Netz gerastert.
        var union = new Voxels(lib);
        for (int i = 0; i < sk.ArmCount; i++)
        {
            var m = sk.MotorPos(i); var off = new Vector3(m.X, m.Y, 0);
            var mesh = solid.Transformed(v => v + off); ideal.Append(mesh);
            Voxels v1 = mesh.ToVoxels(lib);
            if (wall > 1e-4f) v1 = v1.Minus(ext!.Transformed(v => v + off).ToVoxels(lib).voxOffset(-wall));
            if (hole > 1e-4f)
                v1.BoolSubtract(Geo.Revolve(new List<Vector2> { new(0, z0 - 10), new(hole / 2, z0 - 10), new(hole / 2, z0 + hb), new(0, z0 + hb) }, 48).Transformed(v => v + off).ToVoxels(lib));
            union.BoolAdd(v1);
        }
        return new List<Op> { new("upper", false, union, "Gondeln", 0, ideal) };
    }
}
