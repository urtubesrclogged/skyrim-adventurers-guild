using System.Text.RegularExpressions;
using Mutagen.Bethesda.Skyrim;
// StairNav: how vanilla navmeshes a stair (followers could not go up the
// stairs; our spiral's navmesh was 814 triangles, 753 of them slivers and 117 steeper than 45 degrees). For every placed
// reference of the matching stair statics, the navmesh triangles of its cell within its reach (radius r, and from its
// foot to its height), as JSON lines: {"cell", "ed", "ref": [x, y, z, rz, scale], "tris": [[[x,y,z],[x,y,z],[x,y,z]], ...]}
//   dotnet run -- stairnav <editor ID regex> <radius> <height> [max refs]
static class StairNav
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string pattern, double radius, double height, int max)
    {
        var re = new Regex(pattern, RegexOptions.IgnoreCase);
        var bases = mods.SelectMany(m => m.Statics).Where(s => re.IsMatch(s.EditorID ?? "")).GroupBy(s => s.FormKey).ToDictionary(g => g.Key, g => g.Last().EditorID!);
        var cells = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, (ICellGetter c, List<INavigationMeshGetter> navs)>();
        foreach (var m in mods) foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells)
        {
            if (!cells.TryGetValue(c.FormKey, out var e)) e = (c, new List<INavigationMeshGetter>());
            e.navs.AddRange(c.NavigationMeshes); cells[c.FormKey] = (c, e.navs);
        }
        int n = 0;
        foreach (var (c, navs) in cells.Values)
            foreach (var r in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>())
            {
                if (r.Placement is not { } p || !bases.TryGetValue(r.Base.FormKey, out var ed)) continue;
                var tris = new List<double[][]>();
                foreach (var nm in navs)
                {
                    if (nm.Data is not { } d) continue;
                    foreach (var t in d.Triangles)
                    {
                        var v = new[] { d.Vertices[t.Vertices.X], d.Vertices[t.Vertices.Y], d.Vertices[t.Vertices.Z] };
                        double cx = v.Average(q => q.X), cy = v.Average(q => q.Y), cz = v.Average(q => q.Z);
                        if (Math.Sqrt((cx - p.Position.X) * (cx - p.Position.X) + (cy - p.Position.Y) * (cy - p.Position.Y)) > radius) continue;
                        if (cz < p.Position.Z - 40 || cz > p.Position.Z + height + 40) continue;
                        tris.Add(v.Select(q => new double[] { Math.Round(q.X, 1), Math.Round(q.Y, 1), Math.Round(q.Z, 1) }).ToArray());
                    }
                }
                Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new { cell = c.EditorID, ed, @ref = new double[] { p.Position.X, p.Position.Y, p.Position.Z, p.Rotation.Z, r.Scale ?? 1f }, tris }));
                if (++n >= max) return;
            }
    }
}
