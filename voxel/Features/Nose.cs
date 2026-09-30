using System.Numerics;
using PicoGK;

namespace BoreasVoxel;

/// <summary>Gruppe nose: hohle Potenz-Ogive (unten offen) und Einsatz in der Spitze.</summary>
public static class Nose
{
    public static List<Op> Build(Library lib, Skeleton sk, GroupView g)
    {
        float L = g.F("length"), m = g.F("shape_m"), n = g.F("shape_n"), wall = g.F("wall"), tipWall = g.F("tip_wall");
        float rIns = g.F("insert_radius"), zIns = g.F("insert_z"); bool insert = g.B("insert_enabled");
        float zN = sk.NoseJointZ, rN = sk.NoseJointRadius;
        int seg = Geo.Segs(rN, lib.fVoxelSize);

        // Aussen: Basis (0,zN) -> Ogive (Basis .. Spitze)
        var outer = new List<Vector2> { new(0, zN) }; outer.AddRange(Profiles.Ogive(rN, zN, L, m, n, 100));
        var meshO = Geo.Revolve(outer, seg);

        // Innen: Ogive der Laenge L - tip_wall mit Radius rN - wall, unterhalb der Basis auf den Basisradius geklemmt (nach unten offen)
        float Li = L - tipWall;
        var innerOg = Profiles.Ogive(rN - wall, zN, Li, m, n, 100);
        var inner = new List<Vector2> { new(0, zN - 1), new(rN - wall, zN - 1) };
        inner.AddRange(innerOg);
        var meshI = Geo.Revolve(inner, seg);

        var ops = new List<Op>
        {
            new("nose", false, meshO.ToVoxels(lib), "Ogive_aussen", 0, meshO),
            new("nose", true, meshI.ToVoxels(lib), "Ogive_innen", 1, meshI)
        };
        if (insert)
        {
            // Einsatz = Ogive_innen ∩ {rho <= insert_radius, z >= zN + insert_z}
            var vi = meshI.ToVoxels(lib);
            var clip = Geo.Revolve(new List<Vector2> { new(0, zN + zIns), new(rIns, zN + zIns), new(rIns, zN + L + 5), new(0, zN + L + 5) }, Geo.Segs(rIns, lib.fVoxelSize)).ToVoxels(lib);
            vi.BoolIntersect(clip);
            ops.Add(new Op("nose_insert", false, vi, "Einsatz", 0));
        }
        return ops;
    }
}
