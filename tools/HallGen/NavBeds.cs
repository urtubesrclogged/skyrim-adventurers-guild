using System.Text.RegularExpressions;
using Mutagen.Bethesda.Skyrim;
// NavBeds: does vanilla's navmesh run under its beds? (2026-10-30, the hall's NPCs walking to the room under their beds: the NPC session's
// idea, that a bed in a hole in its floor's navmesh resolves to the floor below.) For every bed in the interiors: is the bed's own
// point on a navmesh triangle of its own floor, and how far is the nearest triangle of its floor from it if not.
//   dotnet run -- navbeds ["<cell editor ID regex>"]    (EXTRA_PLUGINS=<the hall's plugin> for ours)
public static class NavBeds
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string rx)
    {
        var r = new Regex(rx);
        var beds = new HashSet<Mutagen.Bethesda.Plugins.FormKey>();
        foreach (var m in mods) foreach (var f in m.Furniture) if (f.EditorID is { } e && Regex.IsMatch(e, "Bed(?!roll)", RegexOptions.IgnoreCase)) beds.Add(f.FormKey);
        int on = 0, off = 0; var near = new List<double>(); var shown = 0;
        foreach (var m in mods) foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells)
        {
            if (c.EditorID is not { } e || !r.IsMatch(e)) continue;
            var nav = c.NavigationMeshes.Select(n => n.Data).Where(d => d is not null && d.Triangles.Count > 0).ToList();
            if (nav.Count == 0) continue;
            foreach (var o in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>())
            {
                if (!beds.Contains(o.Base.FormKey) || o.Placement is not { } pl) continue;
                var p = pl.Position; bool inside = false; double best = 1e9;
                foreach (var d in nav)
                    foreach (var t in d!.Triangles)
                    {
                        var A = d.Vertices[t.Vertices.X]; var B = d.Vertices[t.Vertices.Y]; var C = d.Vertices[t.Vertices.Z];
                        var zm = (A.Z + B.Z + C.Z) / 3;
                        if (Math.Abs(zm - p.Z) > 45) continue;
                        double D = (B.Y - C.Y) * (A.X - C.X) + (C.X - B.X) * (A.Y - C.Y);
                        if (Math.Abs(D) < 1e-6) continue;
                        double u = ((B.Y - C.Y) * (p.X - C.X) + (C.X - B.X) * (p.Y - C.Y)) / D, v = ((C.Y - A.Y) * (p.X - C.X) + (A.X - C.X) * (p.Y - C.Y)) / D;
                        if (u >= 0 && v >= 0 && u + v <= 1) inside = true;
                        best = Math.Min(best, Math.Min(Math.Sqrt((A.X - p.X) * (A.X - p.X) + (A.Y - p.Y) * (A.Y - p.Y)), Math.Min(Math.Sqrt((B.X - p.X) * (B.X - p.X) + (B.Y - p.Y) * (B.Y - p.Y)), Math.Sqrt((C.X - p.X) * (C.X - p.X) + (C.Y - p.Y) * (C.Y - p.Y)))));
                    }
                if (inside) on++; else { off++; near.Add(best); }
                if (shown++ < 14 || !e.StartsWith("Whiterun") && e.StartsWith("AG")) Console.WriteLine($"  {e,-30} bed at ({p.X:F0}, {p.Y:F0}, {p.Z:F0}): {(inside ? "ON its floor's navmesh" : $"in a hole, nearest vertex {best:F0}")}");
            }
        }
        near.Sort();
        Console.WriteLine($"beds on their floor's navmesh {on}, in a hole {off}" + (near.Count > 0 ? $"; nearest vertex median {near[near.Count / 2]:F0}" : ""));
    }
}
// NavBedSides: how wide a walkable strip vanilla leaves beside its single beds (2026-10-30, the NPC session: the hall's bed meshes enter from left and right only; Merila
// stood on her bed): from the middle of each long side outward, the first navmesh and how far it runs, each side, by the wider side per bed.
//   dotnet run -- navbedsides ["<cell regex>"] [--list]    (EXTRA_PLUGINS=<the hall's plugin> for ours)
public static class NavBedSides
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string rx, bool list)
    {
        var r = new Regex(rx); var beds = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, IFurnitureGetter>();
        foreach (var m in mods) foreach (var f in m.Furniture) if (f.EditorID is { } e && Regex.IsMatch(e, "Bed(?!roll)", RegexOptions.IgnoreCase) && f.ObjectBounds is { } b && Math.Min(b.Second.X - b.First.X, b.Second.Y - b.First.Y) < 140) beds[f.FormKey] = f;
        var wide = new List<double>(); var gap = new List<double>(); int none = 0;
        foreach (var m in mods) foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells)
        {
            if (c.EditorID is not { } e || !r.IsMatch(e)) continue;
            var nav = c.NavigationMeshes.Select(n => n.Data).Where(d => d is not null && d.Triangles.Count > 0).ToList();
            if (nav.Count == 0) continue;
            foreach (var o in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>())
            {
                if (!beds.TryGetValue(o.Base.FormKey, out var bd) || o.Placement is not { } pl) continue;
                double a = pl.Rotation.Z, ca = Math.Cos(a), sa = Math.Sin(a), wx_ = bd.ObjectBounds.Second.X - bd.ObjectBounds.First.X, wy_ = bd.ObjectBounds.Second.Y - bd.ObjectBounds.First.Y, hw = Math.Min(wx_, wy_) / 2.0 * (o.Scale ?? 1), cx = (bd.ObjectBounds.First.X + bd.ObjectBounds.Second.X) / 2.0, cy = (bd.ObjectBounds.First.Y + bd.ObjectBounds.Second.Y) / 2.0;
                var tris = new List<(Noggog.P3Float A, Noggog.P3Float B, Noggog.P3Float C)>();
                foreach (var d in nav) foreach (var t in d!.Triangles)
                {
                    var A = d.Vertices[t.Vertices.X]; var B = d.Vertices[t.Vertices.Y]; var C = d.Vertices[t.Vertices.Z];
                    if (Math.Abs((A.Z + B.Z + C.Z) / 3 - pl.Position.Z) > 45) continue;
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
                var sides = new List<(double w, double g)>();
                foreach (var sgn in new[] { -1.0, 1.0 })
                {
                    double? st = null; double en = 0;
                    for (double s = hw - 12; s <= hw + 300; s += 2)
                    {
                        double lx = cx + (wx_ < wy_ ? sgn * s : 0), ly = cy + (wx_ < wy_ ? 0 : sgn * s), x = pl.Position.X + lx * ca + ly * sa, y = pl.Position.Y - lx * sa + ly * ca;
                        if (On(x, y)) { st ??= s; en = s; } else if (st is not null) break;
                    }
                    if (st is not null) sides.Add((en - st.Value, st.Value - hw));
                }
                if (sides.Count == 0) { none++; if (list) Console.WriteLine($"{e,-28} {bd.EditorID,-26} no navmesh beside it"); continue; }
                var best = sides.OrderByDescending(q => q.w).First(); wide.Add(best.w); gap.Add(best.g);
                if (list) Console.WriteLine($"{e,-28} {bd.EditorID,-26} ({pl.Position.X:F0}, {pl.Position.Y:F0}, {pl.Position.Z:F0}) wider side {best.w:F0} wide, starts {best.g:F0} off the bed" + (sides.Count > 1 ? $"; other side {sides.Min(q => q.w):F0}" : "; one side only"));
            }
        }
        wide.Sort(); gap.Sort(); double P(List<double> l, double f) => l.Count == 0 ? 0 : l[(int)(f * (l.Count - 1))];
        Console.WriteLine($"single beds {wide.Count}, none beside {none}; the wider side's strip 5/25/50/75% {P(wide, .05):F0} {P(wide, .25):F0} {P(wide, .5):F0} {P(wide, .75):F0}; its gap from the bed 5/50/95% {P(gap, .05):F0} {P(gap, .5):F0} {P(gap, .95):F0}; under 56 wide: {wide.Count(x => x < 56)}");
    }
}
