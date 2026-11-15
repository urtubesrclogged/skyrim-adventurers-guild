using System.Text.RegularExpressions;
using Mutagen.Bethesda.Skyrim;
// NavDoubleBeds: how vanilla stands a double bed in a player home (room 5 as the player's home:
// the double fits with only one side walkable). For every double bed (the narrower side of its bounds 140 or more) in the
// cells whose editor ID matches: each long side's strip of navmesh beside it (how wide, how far off the bed), so a bed with one
// side against a wall shows "none" on that side. Like NavBedSides, which takes only the singles.
//   dotnet run -c Release -- navdoublebeds "<cell editor ID regex>"
public static class NavDoubleBeds
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string rx)
    {
        var r = new Regex(rx); var beds = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, IFurnitureGetter>();
        foreach (var m in mods) foreach (var f in m.Furniture)
            if (f.EditorID is { } e && Regex.IsMatch(e, "Bed(?!roll)", RegexOptions.IgnoreCase) && f.ObjectBounds is { } b && Math.Min(b.Second.X - b.First.X, b.Second.Y - b.First.Y) >= 140) beds[f.FormKey] = f;
        foreach (var m in mods) foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells)
        {
            if (c.EditorID is not { } e || !r.IsMatch(e)) continue;
            var nav = c.NavigationMeshes.Select(n => n.Data).Where(d => d is not null && d.Triangles.Count > 0).ToList();
            foreach (var o in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>())
            {
                if (!beds.TryGetValue(o.Base.FormKey, out var bd) || o.Placement is not { } pl) continue;
                var ob = bd.ObjectBounds; double sc = o.Scale ?? 1, a = pl.Rotation.Z, ca = Math.Cos(a), sa = Math.Sin(a);
                double wx = (ob.Second.X - ob.First.X) * sc, wy = (ob.Second.Y - ob.First.Y) * sc;
                double cx = (ob.First.X + ob.Second.X) / 2.0 * sc, cy = (ob.First.Y + ob.Second.Y) / 2.0 * sc;
                bool sideX = wx <= wy;                                    // (the long sides run along the longer bound)
                double hw = (sideX ? wx : wy) / 2;
                var tris = nav.SelectMany(d => d!.Triangles.Select(t => (A: d.Vertices[t.Vertices.X], B: d.Vertices[t.Vertices.Y], C: d.Vertices[t.Vertices.Z])))
                              .Where(t => Math.Abs((t.A.Z + t.B.Z + t.C.Z) / 3 - pl.Position.Z) <= 45).ToList();
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
                var parts = new List<string>();
                foreach (var sgn in new[] { -1.0, 1.0 })
                {
                    double? st = null; double en = 0;
                    for (double s = hw - 12; s <= hw + 300; s += 2)
                    {
                        double lx = cx + (sideX ? sgn * s : 0), ly = cy + (sideX ? 0 : sgn * s), x = pl.Position.X + lx * ca + ly * sa, y = pl.Position.Y - lx * sa + ly * ca;
                        if (On(x, y)) { st ??= s; en = s; } else if (st is not null) break;
                    }
                    parts.Add(st is null ? "none" : $"{en - st.Value:F0} wide, {st.Value - hw:F0} off");
                }
                Console.WriteLine($"{e,-30} {bd.EditorID,-28} ({pl.Position.X:F0}, {pl.Position.Y:F0}, {pl.Position.Z:F0})  one side: {parts[0],-20} other: {parts[1]}" + (nav.Count == 0 ? "  (no navmesh)" : ""));
            }
        }
    }
}
