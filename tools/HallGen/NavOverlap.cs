using Mutagen.Bethesda.Skyrim;
// NavOverlap: how vanilla navmesh carries ground stacked under walkway in ONE navmesh (2026-11-17: NPCs would not route on the road
// under site B's bridge, ours over vanilla ground). Every worldspace navmesh of the masters: triangles stacked over or under another of
// the same navmesh (overlapping in plan, their middles more than 150 apart in height) against the rest, by triangle flag.
//   dotnet run -- navoverlap
static class NavOverlap
{
    public static void Run(List<ISkyrimModDisposableGetter> mods)
    {
        var navs = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, (INavigationMeshGetter n, string ws)>();
        foreach (var m in mods) foreach (var ws in m.Worldspaces) foreach (var b in ws.SubCells) foreach (var sb in b.Items) foreach (var c in sb.Items)
            foreach (var n in c.NavigationMeshes) navs[n.FormKey] = (n, ws.EditorID ?? "?");
        var flags = Enum.GetValues(typeof(NavmeshTriangle.Flag)).Cast<NavmeshTriangle.Flag>().Where(f => (int)f != 0).ToList();
        var stackedCount = new Dictionary<string, long>(); var restCount = new Dictionary<string, long>();
        var hist = new SortedDictionary<int, int>(); long nStacked = 0, nRest = 0; int meshesWith = 0; var examples = new List<string>();
        foreach (var (key, (n, wsName)) in navs)
        {
            if (n.Data is not { } d) continue;
            var V = d.Vertices; var T = d.Triangles; int N = T.Count;
            var cx = new double[N]; var cy = new double[N]; var cz = new double[N]; var bb = new double[N, 4];
            var grid = new Dictionary<(int, int), List<int>>();
            for (int i = 0; i < N; i++)
            {
                var a = V[T[i].Vertices.X]; var b = V[T[i].Vertices.Y]; var c = V[T[i].Vertices.Z];
                cx[i] = (a.X + b.X + c.X) / 3; cy[i] = (a.Y + b.Y + c.Y) / 3; cz[i] = (a.Z + b.Z + c.Z) / 3;
                bb[i, 0] = Math.Min(a.X, Math.Min(b.X, c.X)); bb[i, 1] = Math.Max(a.X, Math.Max(b.X, c.X));
                bb[i, 2] = Math.Min(a.Y, Math.Min(b.Y, c.Y)); bb[i, 3] = Math.Max(a.Y, Math.Max(b.Y, c.Y));
                for (int gx = (int)Math.Floor(bb[i, 0] / 256); gx <= (int)Math.Floor(bb[i, 1] / 256); gx++)
                    for (int gy = (int)Math.Floor(bb[i, 2] / 256); gy <= (int)Math.Floor(bb[i, 3] / 256); gy++)
                    { if (!grid.TryGetValue((gx, gy), out var l)) grid[(gx, gy)] = l = new(); l.Add(i); }
            }
            bool In(int j, double x, double y)
            {
                var a = V[T[j].Vertices.X]; var b = V[T[j].Vertices.Y]; var c = V[T[j].Vertices.Z];
                double s1 = (b.X - a.X) * (y - a.Y) - (b.Y - a.Y) * (x - a.X), s2 = (c.X - b.X) * (y - b.Y) - (c.Y - b.Y) * (x - b.X), s3 = (a.X - c.X) * (y - c.Y) - (a.Y - c.Y) * (x - c.X);
                return (s1 >= 0 && s2 >= 0 && s3 >= 0) || (s1 <= 0 && s2 <= 0 && s3 <= 0);
            }
            var st = new bool[N]; int k = 0;
            for (int i = 0; i < N; i++)
            {
                if (!grid.TryGetValue(((int)Math.Floor(cx[i] / 256), (int)Math.Floor(cy[i] / 256)), out var l)) continue;
                foreach (var j in l) if (j != i && Math.Abs(cz[j] - cz[i]) > 150 && In(j, cx[i], cy[i])) { st[i] = true; st[j] = true; var dz = (int)(Math.Abs(cz[j] - cz[i]) / 50) * 50; hist[dz] = hist.GetValueOrDefault(dz) + 1; break; }
            }
            for (int i = 0; i < N; i++)
            {
                var dict = st[i] ? stackedCount : restCount; if (st[i]) { nStacked++; k++; } else nRest++;
                foreach (var f in flags) if (T[i].Flags.HasFlag(f)) dict[f.ToString()] = dict.GetValueOrDefault(f.ToString()) + 1;
                var raw = "raw " + ((int)T[i].Flags & 0xFF80).ToString("X4"); dict[raw] = dict.GetValueOrDefault(raw) + 1;
            }
            if (k > 0) { meshesWith++; if (examples.Count < 12) examples.Add($"{key} {wsName}: {k} stacked of {N}"); }
        }
        Console.WriteLine($"{navs.Count} worldspace navmeshes; {meshesWith} hold stacked triangles; stacked {nStacked}, rest {nRest}");
        foreach (var e in examples) Console.WriteLine("  " + e);
        Console.WriteLine("height apart (50s): " + string.Join(", ", hist.Select(p => $"{p.Key}:{p.Value}")));
        foreach (var f in stackedCount.Keys.Union(restCount.Keys).OrderBy(s => s))
            Console.WriteLine($"  {f,-22} stacked {100.0 * stackedCount.GetValueOrDefault(f) / Math.Max(1, nStacked),6:F1}%   rest {100.0 * restCount.GetValueOrDefault(f) / Math.Max(1, nRest),6:F1}%");
    }
}
