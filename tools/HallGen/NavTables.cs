using System.Text.RegularExpressions;
using Mutagen.Bethesda.Skyrim;
// NavTables: how far vanilla's navmesh keeps from its tables' edges (2026-11-04, Henriette found standing on the dining table, as Merila
// on her bed 2026-10-30): from each side's middle outward, how far past the table's bounds the first navmesh of its floor starts.
//   dotnet run -- navtables ["<cell regex>"] [--list]    (EXTRA_PLUGINS=<the hall's plugin> for ours)
public static class NavTables
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string rx, bool list)
    {
        var r = new Regex(rx); var tables = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, (string ed, Mutagen.Bethesda.Skyrim.IObjectBoundsGetter b)>();
        foreach (var m in mods)
        {
            foreach (var f in m.Statics) if (f.EditorID is { } e && Regex.IsMatch(e, "Table", RegexOptions.IgnoreCase) && !Regex.IsMatch(e, "Cloth|Book|Map|Alch|Ench|Smith", RegexOptions.IgnoreCase) && f.ObjectBounds is { } b) tables[f.FormKey] = (e, b);
            foreach (var f in m.Furniture) if (f.EditorID is { } e && Regex.IsMatch(e, "TableBench|TableChair", RegexOptions.IgnoreCase) && f.ObjectBounds is { } b) tables[f.FormKey] = (e, b);
        }
        var gaps = new List<double>(); var byEd = new SortedDictionary<string, List<double>>(); int none = 0;
        foreach (var m in mods) foreach (var bl in m.Cells) foreach (var sb in bl.SubBlocks) foreach (var c in sb.Cells)
        {
            if (c.EditorID is not { } e || !r.IsMatch(e)) continue;
            var nav = c.NavigationMeshes.Select(n => n.Data).Where(d => d is not null && d.Triangles.Count > 0).ToList();
            if (nav.Count == 0) continue;
            foreach (var o in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>())
            {
                if (!tables.TryGetValue(o.Base.FormKey, out var tb) || o.Placement is not { } pl) continue;
                var bd = tb.b; double s_ = o.Scale ?? 1, a = pl.Rotation.Z, ca = Math.Cos(a), sa = Math.Sin(a);
                var tris = new List<(Noggog.P3Float A, Noggog.P3Float B, Noggog.P3Float C)>();
                foreach (var d in nav) foreach (var t in d!.Triangles)
                {
                    var A = d.Vertices[t.Vertices.X]; var B = d.Vertices[t.Vertices.Y]; var C = d.Vertices[t.Vertices.Z];
                    if (Math.Abs((A.Z + B.Z + C.Z) / 3 - pl.Position.Z) > 30) continue;
                    tris.Add((A, B, C));
                }
                bool On(double x, double y)
                {
                    foreach (var (A, B, C) in tris)
                    {
                        if (Math.Max(A.X, Math.Max(B.X, C.X)) < x || Math.Min(A.X, Math.Min(B.X, C.X)) > x || Math.Max(A.Y, Math.Max(B.Y, C.Y)) < y || Math.Min(A.Y, Math.Min(B.Y, C.Y)) > y) continue;
                        double D = (B.Y - C.Y) * (A.X - C.X) + (C.X - B.X) * (A.Y - C.Y); if (Math.Abs(D) < 1e-9) continue;
                        double u = ((B.Y - C.Y) * (x - C.X) + (C.X - B.X) * (y - C.Y)) / D, v = ((C.Y - A.Y) * (x - C.X) + (A.X - C.X) * (y - C.Y)) / D;
                        if (u >= -1e-6 && v >= -1e-6 && u + v <= 1 + 1e-6) return true;
                    }
                    return false;
                }
                double cx = (bd.First.X + bd.Second.X) / 2.0, cy = (bd.First.Y + bd.Second.Y) / 2.0;
                var row = new List<string>();
                foreach (var (dx, dy, half) in new[] { (1.0, 0.0, (bd.Second.X - bd.First.X) / 2.0), (-1.0, 0.0, (bd.Second.X - bd.First.X) / 2.0), (0.0, 1.0, (bd.Second.Y - bd.First.Y) / 2.0), (0.0, -1.0, (bd.Second.Y - bd.First.Y) / 2.0) })
                {
                    if (On(pl.Position.X + (cx * ca + cy * sa) * s_, pl.Position.Y + (-cx * sa + cy * ca) * s_)) { row.Add("under"); continue; }
                    double? g = null;
                    for (double s = 0; s <= half + 200; s += 2)
                    {
                        double lx = cx + dx * s, ly = cy + dy * s, x = pl.Position.X + (lx * ca + ly * sa) * s_, y = pl.Position.Y + (-lx * sa + ly * ca) * s_;
                        if (On(x, y)) { g = (s - half) * s_; break; }
                    }
                    if (g is null) { none++; row.Add("none"); continue; }
                    if (g.Value > 150) { row.Add($">{g.Value:F0}"); continue; }   // (a wall or another piece there: not this table's margin)
                    gaps.Add(g.Value); if (!byEd.ContainsKey(tb.ed)) byEd[tb.ed] = new(); byEd[tb.ed].Add(g.Value); row.Add($"{g.Value:F0}");
                }
                if (list) Console.WriteLine($"  {e,-30} {tb.ed,-24} at ({pl.Position.X:F0}, {pl.Position.Y:F0}): {string.Join(" ", row)}");
            }
        }
        gaps.Sort();
        string Q(List<double> l) { l.Sort(); return l.Count == 0 ? "-" : $"n {l.Count}, 10% {l[l.Count / 10]:F0}, median {l[l.Count / 2]:F0}, 90% {l[l.Count * 9 / 10]:F0}"; }
        Console.WriteLine($"table sides with navmesh within 150 of the edge: {Q(gaps)}; {none} sides with none");
        foreach (var kv in byEd.Where(k => k.Value.Count >= 8)) Console.WriteLine($"  {kv.Key,-26} {Q(kv.Value)}");
    }
}
