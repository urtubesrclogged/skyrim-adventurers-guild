using System.Text.RegularExpressions;
using Mutagen.Bethesda.Skyrim;
// NavFlags: what a cell's navmesh triangles carry, flat ones and sloped ones (a stair's) apart (our
// stair's navmesh was unusable by NPCs; vanilla's spirals against ours): per navmesh, the triangle
// flags and cover flags counted, edge links (none, inside, to another navmesh), and its NAVI entry's fields.
//   dotnet run -- navflags "<cell regex>" [x y r]      (EXTRA_PLUGINS=<the hall's plugin> for ours)
static class NavFlags
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string pattern, double[] at)
    {
        var re = new Regex(pattern, RegexOptions.IgnoreCase);
        var navs = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, (string cell, INavigationMeshGetter n)>();
        foreach (var m in mods) foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells)
            if (re.IsMatch(c.EditorID ?? "")) foreach (var n in c.NavigationMeshes) navs[n.FormKey] = (c.EditorID!, n);
        var infos = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, INavigationMapInfoGetter>();
        foreach (var m in mods) foreach (var navi in m.NavigationMeshInfoMaps) foreach (var i in navi.MapInfos) infos[i.NavigationMesh.FormKey] = i;
        foreach (var (cell, n) in navs.Values)
        {
            if (n.Data is not { } d) continue;
            var V = d.Vertices; var flat = new Dictionary<string, int>(); var slope = new Dictionary<string, int>();
            int ext = 0, open = 0, inner = 0, nTri = 0, ccw = 0, cw = 0;
            foreach (var t in d.Triangles)
            {
                var a = V[t.Vertices.X]; var b = V[t.Vertices.Y]; var c = V[t.Vertices.Z];
                if (at.Length == 3)
                {
                    double cx = (a.X + b.X + c.X) / 3, cy = (a.Y + b.Y + c.Y) / 3;
                    if (Math.Sqrt((cx - at[0]) * (cx - at[0]) + (cy - at[1]) * (cy - at[1])) > at[2]) continue;
                }
                nTri++;
                double sxy = (b.X - a.X) * (c.Y - a.Y) - (b.Y - a.Y) * (c.X - a.X);   // (the winding seen from above)
                if (sxy > 0) ccw++; else if (sxy < 0) cw++;
                double zr = Math.Max(a.Z, Math.Max(b.Z, c.Z)) - Math.Min(a.Z, Math.Min(b.Z, c.Z));
                var key = $"flags {t.Flags} cover {t.CoverFlags}";
                var dict = zr > 4 ? slope : flat; dict[key] = dict.GetValueOrDefault(key) + 1;
                foreach (var l in new[] { t.EdgeLink_0_1, t.EdgeLink_1_2, t.EdgeLink_2_0 }) { if (l < 0) open++; else inner++; }
            }
            ext = d.EdgeLinks.Count;
            Console.WriteLine($"== {cell} {n.FormKey}: {nTri} triangles{(at.Length == 3 ? $" within {at[2]} of ({at[0]}, {at[1]})" : "")}; edges open {open}, linked {inner}; external edge links {ext}; door triangles {d.DoorTriangles.Count}; winding from above: {ccw} counter-clockwise, {cw} clockwise");
            foreach (var kv in slope.OrderByDescending(k => k.Value)) Console.WriteLine($"   sloped {kv.Value,5}  {kv.Key}");
            foreach (var kv in flat.OrderByDescending(k => k.Value).Take(6)) Console.WriteLine($"   flat   {kv.Value,5}  {kv.Key}");
            if (infos.TryGetValue(n.FormKey, out var inf))
                Console.WriteLine($"   NAVI: unknown {inf.Unknown} point {inf.Point} merged {inf.MergedTo.Count} preferred {inf.PreferredMerges.Count} doors {inf.LinkedDoors.Count} island {(inf.Island is null ? "none" : "yes")} parent {inf.Parent?.GetType().Name}");
            else Console.WriteLine("   NAVI: no entry");
        }
    }
}
