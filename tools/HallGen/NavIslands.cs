using System.Text.RegularExpressions;
using Mutagen.Bethesda.Skyrim;
// NavIslands: when does a navmesh's NAVI entry carry island data? (2026-10-30, the NPC session of the hall's interior navmesh: two
// islands, the loft's by its ladder door, and no island data.) Per interior navmesh: its connected pieces by edge links (external
// links join nothing here), the sizes of them, and the entry's island: how many triangles and vertices it names.
//   dotnet run -- navislands ["<cell editor ID regex>"] [--list]    (EXTRA_PLUGINS=<the hall's plugin> for ours)
public static class NavIslands
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string rx, bool list)
    {
        var r = new Regex(rx);
        var infos = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, INavigationMapInfoGetter>();
        foreach (var m in mods) foreach (var navi in m.NavigationMeshInfoMaps) foreach (var i in navi.MapInfos) infos[i.NavigationMesh.FormKey] = i;
        var tally = new Dictionary<string, int>(); int noEntry = 0;
        foreach (var m in mods) foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells)
        {
            if (c.EditorID is not { } e || !r.IsMatch(e)) continue;
            foreach (var n in c.NavigationMeshes)
            {
                if (n.Data is not { } d || d.Triangles.Count == 0) continue;
                if (!infos.TryGetValue(n.FormKey, out var inf)) { noEntry++; continue; }
                var T = d.Triangles; var par = Enumerable.Range(0, T.Count).ToArray();
                int F(int x) { while (par[x] != x) { par[x] = par[par[x]]; x = par[x]; } return x; }
                for (int i = 0; i < T.Count; i++)
                    foreach (var l in new[] { (int)T[i].EdgeLink_0_1, T[i].EdgeLink_1_2, T[i].EdgeLink_2_0 })
                        if (l >= 0 && l < T.Count) par[F(i)] = F(l);
                var sizes = Enumerable.Range(0, T.Count).GroupBy(F).Select(g => g.Count()).OrderByDescending(x => x).ToList();
                var isl = inf.Island; string key = $"{(sizes.Count > 1 ? "several pieces" : "one piece")}, {(isl is null ? "no island" : "island")}";
                tally[key] = tally.GetValueOrDefault(key) + 1;
                if (list && (sizes.Count > 1 || isl is not null))
                    Console.WriteLine($"{e,-32} {n.FormKey} tris {T.Count,5} pieces {sizes.Count} [{string.Join(",", sizes.Take(6))}]  island {(isl is null ? "none" : $"tris {isl.Triangles.Count} verts {isl.Vertices.Count} min {isl.Min} max {isl.Max}")}  doors {inf.LinkedDoors.Count} point {inf.Point}");
            }
        }
        foreach (var kv in tally.OrderByDescending(k => k.Value)) Console.WriteLine($"{kv.Value,6}  {kv.Key}");
        Console.WriteLine($"{noEntry,6}  no NAVI entry");
    }
}
