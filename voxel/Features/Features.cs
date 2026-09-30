using System.Numerics;
using PicoGK;

namespace BoreasVoxel;

/// <summary>Verteiler: jede Gruppe bekommt nur Skelett + eigene GroupView (Skelett-Methode).</summary>
public static class Features
{
    public static List<Op> Build(string group, Library lib, Skeleton sk, GroupView g) => group switch
    {
        "upper_body" => UpperBody.Build(lib, sk, g),
        "arms" => Arms.Build(lib, sk, g),
        "motor_pods" => MotorPods.Build(lib, sk, g),
        "lower_body" => LowerBody.Build(lib, sk, g),
        "body_fins" => BodyFins.Build(lib, sk, g),
        "tail_fins" => TailFins.Build(lib, sk, g),
        "nose" => Nose.Build(lib, sk, g),
        "joints" => Joints.Build(lib, sk, g),
        "details" => Details.Build(lib, sk, g),
        _ => throw new SpecException($"Unbekannte Gruppe {group}")
    };
}

/// <summary>NACA-Tropfenprofil mit verschiebbarer Dickenlage (docs/geometrie_definition.md Kap. 0.3) und Potenz-Ogive (Kap. 0.4).</summary>
public static class Profiles
{
    static float N(float x) { x = MathF.Max(x, 0f); return 0.2969f * MathF.Sqrt(x) - 0.1260f * x - 0.3516f * x * x + 0.2843f * x * x * x - 0.1015f * x * x * x * x; }
    static readonly float N03 = N(0.3f);
    static float W(float x, float p) => x <= p ? 0.3f * x / p : 0.3f + 0.7f * (x - p) / (1f - p);

    /// <summary>Halbe Profildicke h(delta; c, T, p).</summary>
    public static float H(float delta, float c, float T, float p) => T / 2f * N(W(Math.Clamp(delta / c, 0f, 1f), p)) / N03;

    /// <summary>Geschlossener Profilring in der (q, z)-Ebene: Vorderkante oben (z = zLE), Tiefe delta nach unten.
    /// K+1 Punkte auf der +q-Seite (Vorderkante bis Hinterkante), dann K Punkte zurueck auf der -q-Seite. deltaMax &lt; c erlaubt abgeschnittene Profile.</summary>
    public static List<Vector2> Ring(float c, float T, float p, float zLE, int K = 40, float? deltaMax = null)
    {
        var pts = new List<Vector2>(); float dm = deltaMax ?? c;
        for (int k = 0; k <= K; k++) { float d = dm * 0.5f * (1f - MathF.Cos(MathF.PI * k / K)); pts.Add(new Vector2(H(d, c, T, p), zLE - d)); }
        for (int k = K; k >= 1; k--) { float d = dm * 0.5f * (1f - MathF.Cos(MathF.PI * k / K)); pts.Add(new Vector2(-H(d, c, T, p), zLE - d)); }
        return pts;
    }

    /// <summary>Lofts einen Flossen-/Fin-Koerper: Ringe bei den Spannweiten s; lokales System e (radial, Winkel theta), t (quer).</summary>
    public static TriMesh SpanLoft(float thetaDeg, IList<float> s, Func<float, (float T, float zLE)> f, float c, float p, int K = 40)
    {
        float ct = MathF.Cos(thetaDeg * Geo.Deg), st = MathF.Sin(thetaDeg * Geo.Deg);
        var rings = new List<Vector3[]>();
        foreach (var si in s)
        {
            var (T, zle) = f(si);
            var r2 = Ring(c, T, p, zle, K);
            rings.Add(r2.Select(v => new Vector3(ct * si - st * v.X, st * si + ct * v.X, v.Y)).ToArray());
        }
        return Geo.Loft(rings);
    }

    public static float[] Stations(float a, float b, float maxStep)
    {
        int n = Math.Max(2, (int)MathF.Ceiling((b - a) / maxStep) + 1);
        return Enumerable.Range(0, n).Select(i => a + (b - a) * i / (n - 1)).ToArray();
    }

    /// <summary>Potenz-Ogive rho(zeta) = R (1 - zeta^m)^k als (rho, z)-Profil von der Basis zur Spitze, dicht an der Spitze.</summary>
    public static List<Vector2> Ogive(float R, float zBase, float L, float m, float k, int n = 80)
    {
        var pts = new List<Vector2>();
        for (int j = 0; j <= n; j++)
        {
            float zeta = 1f - MathF.Pow(1f - (float)j / n, 2f);           // dicht an der Spitze
            float r = R * MathF.Pow(MathF.Max(0f, 1f - MathF.Pow(zeta, m)), k);
            pts.Add(new Vector2(j == n ? 0f : r, zBase + zeta * L));
        }
        return pts;
    }
}
