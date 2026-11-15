using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Skyrim;
// Land: the terrain texture layers (and the grass each texture grows) at world points, from the last LAND override in
// the loaded masters - what the ground looks like under a static, and whether grass grows there.
//   land <x,y> [<x,y> ...]
static class Land
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string[] pts)
    {
        var ltex = mods.SelectMany(m => m.LandscapeTextures).GroupBy(t => t.FormKey).ToDictionary(g => g.Key, g => g.Last());
        var grass = mods.SelectMany(m => m.Grasses).GroupBy(t => t.FormKey).ToDictionary(g => g.Key, g => g.Last());
        var tsets = mods.SelectMany(m => m.TextureSets).GroupBy(t => t.FormKey).ToDictionary(g => g.Key, g => g.Last());
        string Tex(FormKey k)
        {
            if (!ltex.TryGetValue(k, out var t)) return $"{k} (not found)";
            var gr = string.Join(",", t.Grasses.Select(g => grass.TryGetValue(g.FormKey, out var gg) ? gg.EditorID : g.FormKey.ToString()));
            var ts = t.TextureSet.FormKeyNullable is { } tk && tsets.TryGetValue(tk, out var s) ? s.Diffuse?.ToString() : "";
            return $"{t.EditorID} [{ts}] grass: {(gr.Length > 0 ? gr : "none")}";
        }
        foreach (var arg in pts)
        {
            var xy = arg.Split(',').Select(float.Parse).ToArray();
            int cx = (int)Math.Floor(xy[0] / 4096), cy = (int)Math.Floor(xy[1] / 4096);
            float lx = (xy[0] - cx * 4096) / 128f, ly = (xy[1] - cy * 4096) / 128f;     // vertex units 0..32
            int vx = (int)Math.Round(lx), vy = (int)Math.Round(ly);
            int quad = (vx >= 16 ? 1 : 0) + (vy >= 16 ? 2 : 0);
            int qx = vx - (vx >= 16 ? 16 : 0), qy = vy - (vy >= 16 ? 16 : 0);
            ushort pos = (ushort)(qy * 17 + qx);
            ILandscapeGetter? land = null;
            foreach (var m in mods)
                foreach (var w in m.Worldspaces.Where(w => w.EditorID == "Tamriel"))
                    foreach (var c in w.SubCells.SelectMany(b => b.Items).SelectMany(s => s.Items))
                        if (c.Grid is { } g && g.Point.X == cx && g.Point.Y == cy && c.Landscape is { } l) land = l;
            Console.WriteLine($"## {arg}: cell {cx},{cy} vertex {vx},{vy} quadrant {quad}");
            if (land?.Layers is null) { Console.WriteLine("   no LAND"); continue; }
            foreach (var layer in land.Layers.Where(l => (int)l.Header!.Quadrant == quad))
            {
                if (layer is IAlphaLayerGetter a)
                {
                    float op = 0;
                    foreach (var e in a.AlphaLayerData ?? Enumerable.Empty<IAlphaLayerDataGetter>())
                        if (e.Position == pos) op = e.Opacity;
                    if (op > 0.05f) Console.WriteLine($"   layer {a.Header!.LayerNumber} opacity {op:F2}: {Tex(a.Header.Texture.FormKey)}");
                }
                else Console.WriteLine($"   base: {Tex(layer.Header!.Texture.FormKey)}");
            }
        }
    }
}
