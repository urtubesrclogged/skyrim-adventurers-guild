using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Skyrim;
// LandOwners: which active plugins carry the LAND record of the cells around a hall position (in load order; the last
// one wins in game) - who a landscape edit there would have to agree with.
//   landowners <MO2 instance dir> <profile> <x,y,floor,yaw> <x0,x1,y0,y1 in the hall frame>
static class LandOwners
{
    public static void Run(string inst, string profile, string site, string area)
    {
        var order = File.ReadAllLines(Path.Combine(inst, "profiles", profile, "modlist.txt")).Where(l => l.StartsWith("+")).Select(l => l[1..]).ToList();
        var byName = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var m in Enumerable.Reverse(order))
        {
            var dir = Path.Combine(inst, "mods", m);
            if (!Directory.Exists(dir)) continue;
            foreach (var f in Directory.GetFiles(dir).Where(f => f.EndsWith(".esm", true, null) || f.EndsWith(".esp", true, null) || f.EndsWith(".esl", true, null)))
                byName[Path.GetFileName(f)] = f;
        }
        var active = new List<string> { "Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm", "Dragonborn.esm" };
        active.AddRange(File.ReadAllLines(Path.Combine(inst, "profiles", profile, "plugins.txt")).Where(l => l.StartsWith("*")).Select(l => l[1..].Trim()));
        var s = site.Split(',').Select(double.Parse).ToArray(); var ar = area.Split(',').Select(double.Parse).ToArray();
        double a = s[3] * Math.PI / 180, ca = Math.Cos(a), sa = Math.Sin(a);
        var cellsWanted = new HashSet<(int, int)>();
        foreach (var hx in new[] { ar[0], (ar[0] + ar[1]) / 2, ar[1] })
            foreach (var hy in new[] { ar[2], (ar[2] + ar[3]) / 2, ar[3] })
            {
                double lx = -hy, ly = hx, wx = s[0] + lx * ca + ly * sa, wy = s[1] - lx * sa + ly * ca;
                cellsWanted.Add(((int)Math.Floor(wx / 4096), (int)Math.Floor(wy / 4096)));
            }
        foreach (var p in active.Distinct(StringComparer.OrdinalIgnoreCase))
        {
            if (!byName.TryGetValue(p, out var path)) continue;
            ISkyrimModDisposableGetter m;
            try { m = SkyrimMod.CreateFromBinaryOverlay(path, SkyrimRelease.SkyrimSE); } catch { continue; }
            foreach (var w in m.Worldspaces.Where(w => w.EditorID == "Tamriel" || w.FormKey.ID == 0x3C))
                foreach (var c in w.SubCells.SelectMany(b => b.Items).SelectMany(sb => sb.Items))
                    if (c.Grid is { } g && cellsWanted.Contains((g.Point.X, g.Point.Y)) && c.Landscape is { } l)
                        Console.WriteLine($"cell {g.Point.X},{g.Point.Y}: LAND {l.FormKey} in {p}" + (l.VertexHeightMap is null ? " (no heights)" : ""));
        }
        Console.WriteLine("cells: " + string.Join(" ", cellsWanted.OrderBy(c => c.Item1).ThenBy(c => c.Item2)));
    }
}
