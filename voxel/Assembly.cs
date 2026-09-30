using System.Diagnostics;
using PicoGK;

namespace BoreasVoxel;

/// <summary>Eine Operation einer Feature-Gruppe auf ein Bauteil: Material hinzufuegen (Add) oder wegnehmen (Cut).</summary>
/// Stage ordnet die Bool-Reihenfolge des Teils (docs/geometrie_definition.md Kap. 1): je Stufe zuerst alle Add, dann alle Cut.
/// Ideal = analytisches Netz vor der Rasterung (nur fuer B04, Abweichung Voxel gegen Ideal). Post = Nachbearbeitung auf Teil-Ebene (Gruppe details).
public sealed record Op(string Part, bool Cut, Voxels? Vox, string Label, int Stage = 0, TriMesh? Ideal = null, Func<Voxels, Voxels>? Post = null);

/// <summary>Baugruppe: Gruppen-Features -> Teile upper / lower / nose / nose_insert.
/// Jede Gruppe wird aus Skelett + eigenen Parametern gebaut (Features/*.cs), die Baugruppe fuegt sie per Voxel-Boolean zusammen.</summary>
public sealed class Model
{
    public static readonly string[] Groups = { "upper_body", "arms", "motor_pods", "lower_body", "body_fins", "tail_fins", "nose", "joints", "details" };
    public static readonly string[] PartNames = { "upper", "lower", "nose", "nose_insert" };

    public readonly Spec Spec; public readonly Library Lib; public readonly Skeleton Sk;
    public readonly Dictionary<string, List<Op>> Ops = new();          // je Gruppe
    public readonly Dictionary<string, double> GroupSeconds = new();   // Bauzeit je Gruppe
    public readonly Dictionary<string, string> GroupFingerprint = new();
    public readonly Dictionary<string, Voxels> Parts = new();
    public double AssembleSeconds;
    public readonly Dictionary<string, HashSet<string>> GroupParts = new();  // welche Teile eine Gruppe beruehrt

    Model(Spec s, Library l) { Spec = s; Lib = l; Sk = Skeleton.From(s); }

    /// <summary>Baut alle Gruppen und die Teile. Mit reuse (Vorlauf) werden nur Gruppen neu gebaut, deren Parameter (oder das Skelett) sich geaendert haben.</summary>
    public static Model Build(Spec spec, Library lib, Model? reuse = null, Action<string>? log = null)
    {
        var m = new Model(spec, lib);
        bool skeletonChanged = reuse == null || reuse.Sk.Fingerprint() != m.Sk.Fingerprint();
        foreach (var g in Groups)
        {
            var fp = spec.View(g).Fingerprint();
            bool rebuild = reuse == null || skeletonChanged || reuse.GroupFingerprint.GetValueOrDefault(g) != fp;
            if (!rebuild && reuse != null && reuse.Ops.TryGetValue(g, out var old))
            {
                m.Ops[g] = old; m.GroupFingerprint[g] = fp; m.GroupSeconds[g] = 0; continue;
            }
            var sw = Stopwatch.StartNew();
            m.Ops[g] = Features.Build(g, lib, m.Sk, spec.View(g));
            m.GroupSeconds[g] = sw.Elapsed.TotalSeconds; m.GroupFingerprint[g] = fp;
            log?.Invoke($"  Gruppe {g}: {sw.Elapsed.TotalSeconds:0.00} s ({m.Ops[g].Count} Operationen)");
        }
        foreach (var kv in m.Ops) m.GroupParts[kv.Key] = kv.Value.Select(o => o.Part).ToHashSet();
        var swa = Stopwatch.StartNew();
        // Teile nur neu zusammensetzen, wenn eine Gruppe daran beteiligt war, die neu gebaut wurde
        foreach (var part in PartNames)
        {
            bool touched = reuse == null || skeletonChanged || m.Ops.Any(kv => m.GroupSeconds[kv.Key] > 0 && kv.Value.Any(o => o.Part == part))
                           || reuse.Ops.Any(kv => !m.Ops.ContainsKey(kv.Key) && kv.Value.Any(o => o.Part == part));
            if (!touched && reuse!.Parts.TryGetValue(part, out var pv)) { m.Parts[part] = pv; continue; }
            m.Parts[part] = Compose(lib, part, m.Ops.Values.SelectMany(x => x).Where(o => o.Part == part).ToList());
        }
        m.AssembleSeconds = swa.Elapsed.TotalSeconds;
        return m;
    }

    /// <summary>Je Stufe (aufsteigend): Vereinigung aller Add, dann Abzug aller Cut; zuletzt die Nachbearbeitungen (Post).</summary>
    static Voxels Compose(Library lib, string part, List<Op> ops)
    {
        var res = new Voxels(lib);
        foreach (var stage in ops.Where(o => o.Post == null).Select(o => o.Stage).Distinct().OrderBy(x => x))
        {
            var adds = ops.Where(o => o.Post == null && o.Stage == stage && !o.Cut).Select(o => o.Vox!).ToList();
            if (adds.Count > 0) res.BoolAddAll(adds);
            foreach (var c in ops.Where(o => o.Post == null && o.Stage == stage && o.Cut)) res.BoolSubtract(c.Vox!);
        }
        foreach (var o in ops.Where(o => o.Post != null)) res = o.Post!(res);
        return res;
    }

    public TriMesh PartMesh(string part) => Parts[part].ToTri();
}
