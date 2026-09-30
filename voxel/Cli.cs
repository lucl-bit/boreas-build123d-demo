using System.Diagnostics;
using System.Globalization;
using System.Text.Json;
using PicoGK;

namespace BoreasVoxel;

/// <summary>Ergebnis einer Aufgabe (wird zu result.json).</summary>
public sealed class TaskResult
{
    public string Status = "ok";                       // ok | partial | unsupported | failed
    public Dictionary<string, object?> Metrics = new();
    public Dictionary<string, object?> Files = new();
    public string Notes = "";
    public Dictionary<string, object?> Extra = new();  // zusaetzliche Top-Level-Felder
    public int? CodeLoc;
}

/// <summary>Kontext eines CLI-Aufrufs.</summary>
public sealed class Ctx
{
    public Spec Spec = null!;
    public string OutDir = "";
    public float Voxel = 0.5f;
    public string RepoRoot = "";
    public string RefDir = "";
    public Library Lib = null!;
    public string Task = "";
    public List<string> Sets = new();
    public Dictionary<string, string> Args = new();

    public string Out(string rel) { var p = System.IO.Path.Combine(OutDir, rel); Directory.CreateDirectory(System.IO.Path.GetDirectoryName(p)!); return p; }
}

public static class Cli
{
    public const string ToolName = "voxel";

    public static int Run(string[] args)
    {
        var ctx = new Ctx();
        var sw = Stopwatch.StartNew();
        TaskResult res;
        int exit = 0;
        string toolVersion = "PicoGK ?";
        try
        {
            ParseArgs(args, ctx);
            Directory.CreateDirectory(ctx.OutDir);
            toolVersion = "PicoGK 2.3.0 (" + Library.strName() + " " + Library.strVersion() + ")";
            ctx.Spec = Spec.Load(ctx.Args["spec"], ctx.Sets);
            ctx.RepoRoot = FindRepoRoot(ctx.Args["spec"]);
            ctx.RefDir = ctx.Args.TryGetValue("ref", out var rd) ? rd : System.IO.Path.Combine(ctx.RepoRoot, "bench", "reference");
            using var lib = new Library(ctx.Voxel);   // HEADLESS: kein Viewer, kein Fenster, keine Logdatei
            ctx.Lib = lib;
            res = Tasks.Run(ctx);
        }
        catch (SpecException ex) { res = new TaskResult { Status = "failed", Notes = "Spec-Fehler: " + ex.Message }; exit = 2; }
        catch (Exception ex)
        {
            res = new TaskResult { Status = "failed", Notes = $"Ausnahme {ex.GetType().Name}: {ex.Message}\n{ex.StackTrace}" };
            exit = 1;
        }
        sw.Stop();
        try { WriteResult(ctx, res, sw.Elapsed.TotalSeconds, toolVersion); }
        catch (Exception ex) { Console.Error.WriteLine("result.json konnte nicht geschrieben werden: " + ex.Message); return 3; }
        Console.WriteLine($"[{ctx.Task}] status={res.Status} runtime={sw.Elapsed.TotalSeconds:0.00}s -> {ctx.OutDir}");
        return exit;
    }

    static void ParseArgs(string[] a, Ctx c)
    {
        for (int i = 0; i < a.Length; i++)
        {
            string k = a[i];
            string Next() => i + 1 < a.Length ? a[++i] : throw new SpecException($"Argument {k} braucht einen Wert");
            switch (k)
            {
                case "--spec": c.Args["spec"] = Next(); break;
                case "--task": c.Task = Next().ToUpperInvariant(); break;
                case "--out": c.OutDir = System.IO.Path.GetFullPath(Next()); break;
                case "--set": c.Sets.Add(Next()); break;
                case "--voxel": c.Voxel = float.Parse(Next(), CultureInfo.InvariantCulture); break;
                case "--ref": c.Args["ref"] = Next(); break;
                case "--opt": { var kv = Next().Split('=', 2); c.Args[kv[0]] = kv.Length > 1 ? kv[1] : "true"; break; }
                default: throw new SpecException($"Unbekanntes Argument '{k}'. Erwartet: --spec <json> --task <ID> --out <dir> [--set g.p=v ...] [--voxel mm]");
            }
        }
        if (!c.Args.ContainsKey("spec")) throw new SpecException("--spec fehlt");
        if (c.Task == "") throw new SpecException("--task fehlt");
        if (c.OutDir == "") throw new SpecException("--out fehlt");
        if (c.Voxel <= 0) throw new SpecException("--voxel muss > 0 sein");
    }

    static string FindRepoRoot(string specPath)
    {
        var d = new DirectoryInfo(System.IO.Path.GetDirectoryName(System.IO.Path.GetFullPath(specPath))!);
        while (d != null) { if (File.Exists(System.IO.Path.Combine(d.FullName, "PLAN.md"))) return d.FullName; d = d.Parent; }
        return System.IO.Path.GetFullPath(System.IO.Path.Combine(System.IO.Path.GetDirectoryName(System.IO.Path.GetFullPath(specPath))!, ".."));
    }

    static void WriteResult(Ctx c, TaskResult r, double runtime, string toolVersion)
    {
        long peak = Process.GetCurrentProcess().PeakWorkingSet64;
        var doc = new Dictionary<string, object?>
        {
            ["task"] = c.Task, ["tool"] = ToolName, ["tool_version"] = toolVersion, ["status"] = r.Status,
            ["runtime_s"] = Math.Round(runtime, 3), ["peak_mem_mb"] = Math.Round(peak / 1048576.0, 1),
            ["params"] = new Dictionary<string, object?> { ["voxel_size_mm"] = (double)c.Voxel, ["overrides"] = c.Spec?.Overrides ?? new() },
            ["metrics"] = r.Metrics, ["files"] = r.Files,
            ["code_loc"] = r.CodeLoc ?? CodeStats.ModelLoc(), ["notes"] = r.Notes
        };
        foreach (var kv in r.Extra) doc[kv.Key] = kv.Value;
        var opts = new JsonSerializerOptions { WriteIndented = true, Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping, NumberHandling = System.Text.Json.Serialization.JsonNumberHandling.AllowNamedFloatingPointLiterals };
        File.WriteAllText(System.IO.Path.Combine(c.OutDir, "result.json"), JsonSerializer.Serialize(Sanitize(doc), opts));
    }

    /// <summary>NaN/Infinity -> null, damit das JSON gueltig bleibt.</summary>
    internal static object? Sanitize(object? o) => o switch
    {
        double d => double.IsFinite(d) ? d : null,
        float f => float.IsFinite(f) ? f : null,
        Dictionary<string, object?> dd => dd.ToDictionary(k => k.Key, k => Sanitize(k.Value)),
        System.Collections.IEnumerable e when o is not string => e.Cast<object?>().Select(Sanitize).ToList(),
        _ => o
    };
}

/// <summary>Zaehlt Codezeilen (ohne Leerzeilen und reine Kommentarzeilen) fuer code_loc.</summary>
public static class CodeStats
{
    static string Dir => System.IO.Path.GetDirectoryName(typeof(Cli).Assembly.Location) ?? "";
    public static string? SourceDir()
    {
        var d = new DirectoryInfo(AppContext.BaseDirectory);
        while (d != null) { if (File.Exists(System.IO.Path.Combine(d.FullName, "BoreasVoxel.csproj"))) return d.FullName; d = d.Parent; }
        return null;
    }
    public static int Loc(string file)
    {
        int n = 0; bool block = false;
        foreach (var raw in File.ReadLines(file))
        {
            var l = raw.Trim();
            if (block) { if (l.Contains("*/")) block = false; continue; }
            if (l.Length == 0 || l.StartsWith("//")) continue;
            if (l.StartsWith("/*")) { if (!l.Contains("*/")) block = true; continue; }
            n++;
        }
        return n;
    }
    static readonly string[] ModelFiles = { "Spec.cs", "Skeleton.cs", "Assembly.cs", "Geo.cs", "Features/" };
    /// <summary>Geometrie-Modell (Spec-Leser, Skelett, Gruppen-Features, Baugruppe, Geometrie-Helfer), ohne CLI/Vorschau/Tasks.</summary>
    public static int ModelLoc()
    {
        var s = SourceDir(); if (s == null) return -1;
        return Files(s).Where(f => IsModel(s, f)).Sum(Loc);
    }
    public static int TotalLoc() { var s = SourceDir(); return s == null ? -1 : Files(s).Sum(Loc); }
    public static Dictionary<string, int> Breakdown()
    {
        var s = SourceDir(); var d = new Dictionary<string, int>(); if (s == null) return d;
        foreach (var f in Files(s)) d[System.IO.Path.GetRelativePath(s, f).Replace('\\', '/')] = Loc(f);
        return d;
    }
    public static IEnumerable<string> Files(string src) => Directory.EnumerateFiles(src, "*.cs", SearchOption.AllDirectories)
        .Where(f => { var r = System.IO.Path.GetRelativePath(src, f).Replace('\\', '/'); return !r.StartsWith("obj/") && !r.StartsWith("bin/") && !r.StartsWith("external/") && !r.StartsWith("out/"); });
    static bool IsModel(string src, string f) { var r = System.IO.Path.GetRelativePath(src, f).Replace('\\', '/'); return ModelFiles.Any(m => m.EndsWith("/") ? r.StartsWith(m) : r == m); }
}
