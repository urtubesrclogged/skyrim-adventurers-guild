using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Skyrim;
// LandGrid: where grass grows around a hall position, in the hall's frame, from a real MO2 load order (every active
// plugin's LTEX / GRAS / LAND, last override wins). Per landscape vertex: the blended weight of textures that grow grass,
// and each texture's own weight (texs), so a check can look up which grasses grow there; z: the terrain height there,
// relative to the floor, from the same winning LAND.
//   landgrid <MO2 instance dir> <profile> <x,y,floor,yaw> <x0,x1,y0,y1> <out.json>
static class LandGrid
{
    public static void Run(string inst, string profile, string site, string area, string outPath)
    {
        var mods = Directory.GetDirectories(Path.Combine(inst, "mods"));
        // mod priority: modlist.txt lists highest priority first; enabled lines start with '+'
        var order = File.ReadAllLines(Path.Combine(inst, "profiles", profile, "modlist.txt")).Where(l => l.StartsWith("+")).Select(l => l[1..]).ToList();
        var byName = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var m in Enumerable.Reverse(order))                       // lowest priority first, higher ones overwrite
        {
            var dir = Path.Combine(inst, "mods", m);
            if (!Directory.Exists(dir)) continue;
            foreach (var f in Directory.GetFiles(dir).Where(f => f.EndsWith(".esm", true, null) || f.EndsWith(".esp", true, null) || f.EndsWith(".esl", true, null)))
                byName[Path.GetFileName(f)] = f;
        }
        var active = new List<string> { "Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm", "Dragonborn.esm" };
        active.AddRange(File.ReadAllLines(Path.Combine(inst, "profiles", profile, "plugins.txt")).Where(l => l.StartsWith("*")).Select(l => l[1..].Trim()));
        var loaded = new List<ISkyrimModDisposableGetter>();
        foreach (var p in active.Distinct(StringComparer.OrdinalIgnoreCase))
        {
            if (!byName.TryGetValue(p, out var path)) { Console.Error.WriteLine("not found: " + p); continue; }
            try { loaded.Add(SkyrimMod.CreateFromBinaryOverlay(path, SkyrimRelease.SkyrimSE)); } catch (Exception e) { Console.Error.WriteLine($"skip {p}: {e.Message}"); }
        }
        Console.Error.WriteLine($"{loaded.Count} plugins loaded");
        var ltex = new Dictionary<FormKey, ILandscapeTextureGetter>();
        foreach (var m in loaded) foreach (var t in m.LandscapeTextures) ltex[t.FormKey] = t;
        bool Grows(FormKey k) => ltex.TryGetValue(k, out var t) && t.Grasses.Count > 0;
        var s = site.Split(',').Select(double.Parse).ToArray(); var ar = area.Split(',').Select(double.Parse).ToArray();
        double a = s[3] * Math.PI / 180, ca = Math.Cos(a), sa = Math.Sin(a);
        (double, double) W(double hx, double hy) { double lx = -hy, ly = hx; return (s[0] + lx * ca + ly * sa, s[1] - lx * sa + ly * ca); }
        var lands = new Dictionary<(int, int), ILandscapeGetter>();
        ILandscapeGetter? Land(int cx, int cy)
        {
            if (lands.TryGetValue((cx, cy), out var l)) return l;
            ILandscapeGetter? found = null;
            foreach (var m in loaded)
                foreach (var w in m.Worldspaces.Where(w => w.EditorID == "Tamriel"))
                    foreach (var c in w.SubCells.SelectMany(b => b.Items).SelectMany(sb => sb.Items))
                        if (c.Grid is { } g && g.Point.X == cx && g.Point.Y == cy && c.Landscape is { } ll) found = ll;
            lands[(cx, cy)] = found!; return found;
        }
        double? Height(double wx, double wy)                            // the terrain height (bilinear on the winning LAND's vertex heights)
        {
            int cx = (int)Math.Floor(wx / 4096), cy = (int)Math.Floor(wy / 4096);
            var land = Land(cx, cy);
            if (land?.VertexHeightMap is not { } vh) return null;
            var hm = vh.HeightMap; var H = new double[33, 33]; double col = vh.Offset;
            for (int y = 0; y < 33; y++)
            {
                col += (sbyte)hm[new Noggog.P2Int(0, y)]; double v = col;
                for (int x = 0; x < 33; x++) { if (x > 0) v += (sbyte)hm[new Noggog.P2Int(x, y)]; H[x, y] = v * 8; }
            }
            double fx = (wx - cx * 4096) / 128, fy = (wy - cy * 4096) / 128; int i = Math.Min((int)fx, 31), j = Math.Min((int)fy, 31); double u = fx - i, t = fy - j;
            return H[i, j] * (1 - u) * (1 - t) + H[i + 1, j] * u * (1 - t) + H[i, j + 1] * (1 - u) * t + H[i + 1, j + 1] * u * t;
        }
        var cells = new List<object>();
        for (double hy = ar[2]; hy <= ar[3]; hy += 64)
            for (double hx = ar[0]; hx <= ar[1]; hx += 64)
            {
                var (wx, wy) = W(hx, hy);
                int cx = (int)Math.Floor(wx / 4096), cy = (int)Math.Floor(wy / 4096);
                int vx = (int)Math.Round((wx - cx * 4096) / 128), vy = (int)Math.Round((wy - cy * 4096) / 128);
                int quad = (vx >= 16 ? 1 : 0) + (vy >= 16 ? 2 : 0);
                int qx = vx - (vx >= 16 ? 16 : 0), qy = vy - (vy >= 16 ? 16 : 0);
                ushort pos = (ushort)(qy * 17 + qx);
                var land = Land(cx, cy);
                double grass = 0; string top = ""; object[] texs = Array.Empty<object>();
                if (land?.Layers is { } layers)
                {
                    var w = new List<(FormKey t, double w)>();
                    foreach (var layer in layers.Where(l => (int)l.Header!.Quadrant == quad).OrderBy(l => l is IAlphaLayerGetter al ? al.Header!.LayerNumber : -1))
                    {
                        if (layer is IAlphaLayerGetter al)
                        {
                            double op = 0;
                            foreach (var e in al.AlphaLayerData ?? Enumerable.Empty<IAlphaLayerDataGetter>()) if (e.Position == pos) op = e.Opacity;
                            if (op <= 0) continue;
                            w = w.Select(x => (x.t, x.w * (1 - op))).ToList(); w.Add((al.Header!.Texture.FormKey, op));
                        }
                        else w.Add((layer.Header!.Texture.FormKey, 1.0));
                    }
                    grass = w.Where(x => Grows(x.t)).Sum(x => x.w);
                    var best = w.OrderByDescending(x => x.w).FirstOrDefault();
                    top = ltex.TryGetValue(best.t, out var bt) ? bt.EditorID ?? "" : "";
                    texs = w.GroupBy(x => x.t).Select(g => (t: g.Key, w: g.Sum(x => x.w))).Where(x => x.w > 0.05).OrderByDescending(x => x.w)
                            .Select(x => (object)new object[] { ltex.TryGetValue(x.t, out var tt) ? tt.EditorID ?? "" : x.t.ToString(), Math.Round(x.w, 2) }).ToArray();
                }
                var hz = Height(wx, wy);
                cells.Add(new { x = hx, y = hy, grass = Math.Round(grass, 2), tex = top, texs, z = hz is { } zz ? Math.Round(zz - s[2], 1) : (double?)null });
            }
        File.WriteAllText(outPath, System.Text.Json.JsonSerializer.Serialize(new { site = s, cells }));
        Console.WriteLine($"wrote {outPath}: {cells.Count} points");
    }
}
