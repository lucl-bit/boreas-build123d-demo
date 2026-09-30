using System.Numerics;
using SkiaSharp;

namespace BoreasVoxel;

/// <summary>Software-Rasterizer (orthografisch, Z-Buffer, Lambert) fuer Vorschaubilder.
/// PicoGK kann headless nichts rendern (der Viewer ist ein GLFW-Fenster), daher rendern wir die Netze selbst mit SkiaSharp.</summary>
public static class Preview
{
    public sealed class Layer { public TriMesh Mesh = new(); public SKColor Color = new(180, 190, 200); public string Name = ""; }

    /// <summary>Drei Ansichten (Iso, Seite, Oben) auf ein PNG.</summary>
    public static void RenderPng(IList<Layer> layers, string path, int width = 1500, int height = 900)
    {
        Directory.CreateDirectory(System.IO.Path.GetDirectoryName(System.IO.Path.GetFullPath(path))!);
        var all = new TriMesh(); foreach (var l in layers) all.V.AddRange(l.Mesh.V);
        if (all.V.Count == 0) { using var e = new SKBitmap(width, height); e.Erase(SKColors.White); Save(e, path); return; }
        var (mn, mx) = all.BBox(); var ctr = (mn + mx) / 2; float diag = (mx - mn).Length();

        using var bmp = new SKBitmap(width, height); bmp.Erase(new SKColor(245, 247, 250));
        int wl = (int)(width * 0.55), wr = width - wl;
        var iso = Render(layers, ctr, diag, ViewBasis(35, 25), wl, height);
        var side = Render(layers, ctr, diag, ViewBasis(0, 0), wr, height / 2);
        var top = Render(layers, ctr, diag, TopBasis(), wr, height - height / 2);
        using (var c = new SKCanvas(bmp))
        {
            c.DrawBitmap(iso, 0, 0); c.DrawBitmap(side, wl, 0); c.DrawBitmap(top, wl, height / 2);
            using var p = new SKPaint { Color = new SKColor(150, 160, 170), StrokeWidth = 1 };
            c.DrawLine(wl, 0, wl, height, p); c.DrawLine(wl, height / 2, width, height / 2, p);
            using var font = new SKFont(SKTypeface.Default, 16); using var tp = new SKPaint { Color = new SKColor(60, 70, 80), IsAntialias = true };
            c.DrawText("Iso", 10, 22, font, tp); c.DrawText("Seite (Blick entlang +Y, Z oben)", wl + 10, 22, font, tp); c.DrawText("Oben (Blick entlang -Z)", wl + 10, height / 2 + 22, font, tp);
        }
        iso.Dispose(); side.Dispose(); top.Dispose();
        Save(bmp, path);
    }

    static void Save(SKBitmap b, string path)
    {
        using var img = SKImage.FromBitmap(b); using var data = img.Encode(SKEncodedImageFormat.Png, 90);
        using var fs = File.Create(path); data.SaveTo(fs);
    }

    // Blickbasis: right, up, forward (Blickrichtung). Z-up-Welt.
    static (Vector3 r, Vector3 u, Vector3 f) ViewBasis(float azDeg, float elDeg)
    {
        float az = azDeg * MathF.PI / 180, el = elDeg * MathF.PI / 180;
        // Kamera sitzt bei -Y (Seite) gedreht um az, erhoeht um el; Blick zum Ursprung.
        var camDir = new Vector3(MathF.Sin(az) * MathF.Cos(el), -MathF.Cos(az) * MathF.Cos(el), MathF.Sin(el));   // vom Objekt zur Kamera
        var f = -camDir; var r = Vector3.Normalize(Vector3.Cross(f, Vector3.UnitZ)); var u = Vector3.Cross(r, f);
        return (r, u, f);
    }
    static (Vector3 r, Vector3 u, Vector3 f) TopBasis() => (Vector3.UnitX, Vector3.UnitY, -Vector3.UnitZ);

    static SKBitmap Render(IList<Layer> layers, Vector3 ctr, float diag, (Vector3 r, Vector3 u, Vector3 f) B, int w, int h)
    {
        var bmp = new SKBitmap(w, h); bmp.Erase(new SKColor(245, 247, 250));
        // Massstab: gesamte Diagonale passt in das Feld
        float extent = MathF.Min(w, h) * 0.92f; float scale = extent / diag;
        if (Math.Abs(B.f.Z) < 0.5f) { }   // Seitenansichten: nach Bounds skalieren
        var zbuf = new float[w * h]; Array.Fill(zbuf, float.PositiveInfinity);
        var pix = new uint[w * h]; Array.Fill(pix, 0xFFFAF7F5u);   // BGRA (Skia N32 auf Windows: BGRA) -> 0xAARRGGBB als uint
        var lightDir = Vector3.Normalize(-B.f + 0.6f * B.u - 0.4f * B.r);   // Kopflicht mit Versatz
        foreach (var layer in layers)
        {
            var m = layer.Mesh; var col = layer.Color;
            var sp = new Vector3[m.V.Count];
            for (int i = 0; i < sp.Length; i++)
            {
                var d = m.V[i] - ctr;
                sp[i] = new Vector3(w / 2f + Vector3.Dot(d, B.r) * scale, h / 2f - Vector3.Dot(d, B.u) * scale, Vector3.Dot(d, B.f));
            }
            for (int t = 0; t < m.T.Count; t += 3)
            {
                var a = sp[m.T[t]]; var b = sp[m.T[t + 1]]; var c = sp[m.T[t + 2]];
                var n = Vector3.Cross(m.V[m.T[t + 1]] - m.V[m.T[t]], m.V[m.T[t + 2]] - m.V[m.T[t]]);
                float nl = n.Length(); if (nl < 1e-12f) continue; n /= nl;
                float lam = MathF.Abs(Vector3.Dot(n, lightDir));    // zweiseitig: Netz-Orientierung egal
                float shade = 0.28f + 0.72f * lam;
                uint rgb = 0xFF000000u | ((uint)Math.Min(255, col.Red * shade) << 16) | ((uint)Math.Min(255, col.Green * shade) << 8) | (uint)Math.Min(255, col.Blue * shade);
                int x0 = Math.Max(0, (int)MathF.Floor(MathF.Min(a.X, MathF.Min(b.X, c.X)))), x1 = Math.Min(w - 1, (int)MathF.Ceiling(MathF.Max(a.X, MathF.Max(b.X, c.X))));
                int y0 = Math.Max(0, (int)MathF.Floor(MathF.Min(a.Y, MathF.Min(b.Y, c.Y)))), y1 = Math.Min(h - 1, (int)MathF.Ceiling(MathF.Max(a.Y, MathF.Max(b.Y, c.Y))));
                float den = (b.Y - c.Y) * (a.X - c.X) + (c.X - b.X) * (a.Y - c.Y);
                if (MathF.Abs(den) < 1e-9f) continue;
                for (int y = y0; y <= y1; y++)
                    for (int x = x0; x <= x1; x++)
                    {
                        float px = x + 0.5f, py = y + 0.5f;
                        float l1 = ((b.Y - c.Y) * (px - c.X) + (c.X - b.X) * (py - c.Y)) / den;
                        float l2 = ((c.Y - a.Y) * (px - c.X) + (a.X - c.X) * (py - c.Y)) / den;
                        float l3 = 1 - l1 - l2;
                        if (l1 < -1e-4f || l2 < -1e-4f || l3 < -1e-4f) continue;
                        float z = l1 * a.Z + l2 * b.Z + l3 * c.Z;
                        int idx = y * w + x;
                        if (z < zbuf[idx]) { zbuf[idx] = z; pix[idx] = rgb; }
                    }
            }
        }
        var handle = System.Runtime.InteropServices.GCHandle.Alloc(pix, System.Runtime.InteropServices.GCHandleType.Pinned);
        try
        {
            var info = new SKImageInfo(w, h, SKColorType.Bgra8888, SKAlphaType.Premul);
            using var tmp = new SKBitmap(); tmp.InstallPixels(info, handle.AddrOfPinnedObject(), w * 4);
            using var cv = new SKCanvas(bmp); cv.DrawBitmap(tmp, 0, 0);
        }
        finally { handle.Free(); }
        return bmp;
    }
}
