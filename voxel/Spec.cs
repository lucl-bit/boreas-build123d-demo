using System.Globalization;
using System.Text.Json;

namespace BoreasVoxel;

/// <summary>Ein Parameter der tool-neutralen Spec (spec/boreas_spec.json).</summary>
public sealed class Param
{
    public string Group = "", Name = "";
    public object Value = 0.0;          // double | bool | string
    public double? Min, Max, Step;
    public string Unit = "", Label = "", Description = "";
    public string[]? Choices;           // optional: erlaubte Strings

    public double AsDouble => Value switch
    {
        double d => d,
        bool b => b ? 1 : 0,
        _ => throw new SpecException($"Parameter {Group}.{Name} ist kein Zahlenwert: {Value}")
    };
    public override string ToString() => Value is double d ? d.ToString("0.######", CultureInfo.InvariantCulture) : Value.ToString() ?? "";
}

public sealed class SpecException : Exception { public SpecException(string m) : base(m) { } }

/// <summary>Spec laden, mit "gruppe.param=wert" ueberschreiben, gegen min/max pruefen.</summary>
public sealed class Spec
{
    public Dictionary<string, Dictionary<string, Param>> Groups = new();
    public Dictionary<string, string> GroupLabels = new();
    public Dictionary<string, object> Overrides = new();
    public JsonElement Meta;
    public string Path = "";

    public static Spec Load(string path, IEnumerable<string>? sets = null)
    {
        var spec = new Spec { Path = path };
        using var doc = JsonDocument.Parse(File.ReadAllText(path), new JsonDocumentOptions { AllowTrailingCommas = true, CommentHandling = JsonCommentHandling.Skip });
        var root = doc.RootElement;
        if (root.TryGetProperty("meta", out var meta)) spec.Meta = meta.Clone();
        foreach (var g in root.GetProperty("groups").EnumerateObject())
        {
            var ps = new Dictionary<string, Param>();
            if (g.Value.TryGetProperty("label", out var gl)) spec.GroupLabels[g.Name] = gl.GetString() ?? g.Name;
            foreach (var p in g.Value.GetProperty("params").EnumerateObject())
            {
                var e = p.Value;
                var prm = new Param { Group = g.Name, Name = p.Name };
                var v = e.GetProperty("value");
                prm.Value = v.ValueKind switch
                {
                    JsonValueKind.Number => v.GetDouble(),
                    JsonValueKind.True => true,
                    JsonValueKind.False => false,
                    JsonValueKind.String => v.GetString() ?? "",
                    _ => throw new SpecException($"{g.Name}.{p.Name}: nicht unterstuetzter Werttyp {v.ValueKind}")
                };
                if (e.TryGetProperty("min", out var mn) && mn.ValueKind == JsonValueKind.Number) prm.Min = mn.GetDouble();
                if (e.TryGetProperty("max", out var mx) && mx.ValueKind == JsonValueKind.Number) prm.Max = mx.GetDouble();
                if (e.TryGetProperty("step", out var st) && st.ValueKind == JsonValueKind.Number) prm.Step = st.GetDouble();
                if (e.TryGetProperty("unit", out var un)) prm.Unit = un.GetString() ?? "";
                if (e.TryGetProperty("label", out var lb)) prm.Label = lb.GetString() ?? "";
                if (e.TryGetProperty("description", out var ds)) prm.Description = ds.GetString() ?? "";
                if (e.TryGetProperty("choices", out var ch) && ch.ValueKind == JsonValueKind.Array)
                    prm.Choices = ch.EnumerateArray().Select(x => x.GetString() ?? "").ToArray();
                if (e.TryGetProperty("options", out var op) && op.ValueKind == JsonValueKind.Array)
                    prm.Choices = op.EnumerateArray().Select(x => x.GetString() ?? "").ToArray();
                ps[p.Name] = prm;
            }
            spec.Groups[g.Name] = ps;
        }
        if (sets != null) foreach (var s in sets) spec.Set(s);
        spec.Validate();
        return spec;
    }

    /// <summary>"gruppe.param=wert"</summary>
    public void Set(string assignment)
    {
        int eq = assignment.IndexOf('=');
        if (eq < 0) throw new SpecException($"--set erwartet gruppe.param=wert, erhalten: '{assignment}'");
        var key = assignment[..eq].Trim(); var val = assignment[(eq + 1)..].Trim();
        int dot = key.IndexOf('.');
        if (dot < 0) throw new SpecException($"--set: Schluessel '{key}' ohne Gruppe (erwartet gruppe.param)");
        var g = key[..dot]; var n = key[(dot + 1)..];
        if (!Groups.TryGetValue(g, out var ps)) throw new SpecException($"--set: unbekannte Gruppe '{g}'. Vorhanden: {string.Join(", ", Groups.Keys)}");
        if (!ps.TryGetValue(n, out var p)) throw new SpecException($"--set: unbekannter Parameter '{key}'. In '{g}' vorhanden: {string.Join(", ", ps.Keys)}");
        if (p.Value is bool) p.Value = val.Equals("true", StringComparison.OrdinalIgnoreCase) || val == "1";
        else if (p.Value is string) p.Value = val;
        else if (double.TryParse(val, NumberStyles.Float, CultureInfo.InvariantCulture, out var d)) p.Value = d;
        else throw new SpecException($"--set {key}: '{val}' ist keine Zahl");
        Overrides[key] = p.Value;
    }

    /// <summary>min/max/choices pruefen; wirft SpecException mit allen Verletzungen.</summary>
    public void Validate()
    {
        var errs = new List<string>();
        foreach (var ps in Groups.Values) foreach (var p in ps.Values)
        {
            if (p.Value is double d)
            {
                if (p.Min.HasValue && d < p.Min.Value - 1e-9) errs.Add($"{p.Group}.{p.Name}={d} < min {p.Min}");
                if (p.Max.HasValue && d > p.Max.Value + 1e-9) errs.Add($"{p.Group}.{p.Name}={d} > max {p.Max}");
            }
            else if (p.Value is string s && p.Choices != null && !p.Choices.Contains(s))
                errs.Add($"{p.Group}.{p.Name}='{s}' nicht in {string.Join("|", p.Choices)}");
        }
        if (errs.Count > 0) throw new SpecException("Spec-Validierung fehlgeschlagen: " + string.Join("; ", errs));
    }

    public bool Has(string group, string name) => Groups.TryGetValue(group, out var g) && g.ContainsKey(name);

    /// <summary>Sicht auf genau eine Gruppe (+ Skelett). Der Zugriff auf andere Gruppen ist bewusst unmoeglich
    /// (Skelett-Methode aus PLAN.md: eine Gruppe liest nur eigene Parameter und das Skelett).</summary>
    public GroupView View(string group) => new(this, group);

    public string? MetaString(string key) => Meta.ValueKind == JsonValueKind.Object && Meta.TryGetProperty(key, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;
    public double? MetaNumber(string key) => Meta.ValueKind == JsonValueKind.Object && Meta.TryGetProperty(key, out var v) && v.ValueKind == JsonValueKind.Number ? v.GetDouble() : null;
}

/// <summary>Lesezugriff auf die eigene Gruppe. Zugriffe werden protokolliert (Nachweis fuer B03/Skelett-Test).</summary>
public sealed class GroupView
{
    readonly Spec _spec; public readonly string Group;
    public readonly HashSet<string> Used = new();
    internal GroupView(Spec s, string g) { _spec = s; Group = g; if (!s.Groups.ContainsKey(g)) throw new SpecException($"Gruppe '{g}' fehlt in der Spec"); }

    Param P(string n)
    {
        if (!_spec.Groups[Group].TryGetValue(n, out var p)) throw new SpecException($"Parameter {Group}.{n} fehlt in der Spec");
        Used.Add(n); return p;
    }
    public double D(string n) => P(n).AsDouble;
    public float F(string n) => (float)P(n).AsDouble;
    public int I(string n) => (int)Math.Round(P(n).AsDouble);
    public bool B(string n) => P(n).Value is bool b ? b : P(n).AsDouble != 0;
    public string S(string n) => P(n).Value.ToString() ?? "";
    /// <summary>Wert mit Rueckfall, falls die Spec den Parameter (noch) nicht kennt.</summary>
    public double D(string n, double fallback) => _spec.Has(Group, n) ? D(n) : fallback;
    public bool Has(string n) => _spec.Has(Group, n);
    /// <summary>Kanonische Zeichenkette aller Werte der Gruppe (fuer Hash / Cache-Schluessel).</summary>
    public string Fingerprint() => string.Join(";", _spec.Groups[Group].OrderBy(k => k.Key).Select(k => k.Key + "=" + k.Value));
}
