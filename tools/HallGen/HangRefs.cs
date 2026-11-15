using System.Text.RegularExpressions;
using Mutagen.Bethesda.Skyrim;
// HangRefs: how high vanilla hangs a hanging light (the services' chandeliers went from
// head height to flat on the ceiling: placement is measured, not guessed). Every interior reference of
// the bases whose editor ID matches, with the floor under it read from its cell's own navmesh (the highest triangle under
// its x, y and below it), so: its origin over the floor, and with the mesh's own extents (bottom below the origin, rope's
// top above it, measured with module_bounds.py) the horns' clearance and the ceiling it hangs from.
//   dotnet run -- hangrefs <editor ID regex> <bottom> <rope top>
static class HangRefs
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string pattern, double bottom, double ropeTop)
    {
        var re = new Regex(pattern, RegexOptions.IgnoreCase);
        var bases = mods.SelectMany(m => m.Statics).Cast<ISkyrimMajorRecordGetter>().Concat(mods.SelectMany(m => m.MoveableStatics))
            .Where(s => re.IsMatch(s.EditorID ?? "")).GroupBy(s => s.FormKey).ToDictionary(g => g.Key, g => g.Last().EditorID!);
        var cells = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, (ICellGetter c, List<INavigationMeshGetter> navs)>();
        foreach (var m in mods) foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells)
        {
            if (!cells.TryGetValue(c.FormKey, out var e)) e = (c, new List<INavigationMeshGetter>());
            e.navs.AddRange(c.NavigationMeshes); cells[c.FormKey] = (c, e.navs);
        }
        var models = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, string>();   // what stands under it: its editor ID
        foreach (var r in mods.SelectMany(m => m.Statics).Cast<ISkyrimMajorRecordGetter>().Concat(mods.SelectMany(m => m.Furniture)).Concat(mods.SelectMany(m => m.Containers)).Concat(mods.SelectMany(m => m.MoveableStatics)))
            if (r.EditorID is { } e_) models[r.FormKey] = e_;
        var rows = new List<(string cell, string ed, double z, double floor, double s, string under, bool walk)>();
        foreach (var (c, navs) in cells.Values)
            foreach (var r in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>())
            {
                if (r.Placement is not { } p || !bases.TryGetValue(r.Base.FormKey, out var ed)) continue;
                // the floor: the highest navmesh triangle below it within 160 of its x, y (its centre's z), and whether one
                // lies right under it: a chandelier over a table hangs over a hole in the navmesh, so reading only the
                // triangle under it (the first version) left every one over furniture out of the sample
                double best = double.NegativeInfinity, nearD = double.PositiveInfinity; bool walkUnder = false;
                foreach (var n in navs)
                {
                    if (n.Data is not { } d) continue;
                    foreach (var t in d.Triangles)
                    {
                        var A = d.Vertices[t.Vertices.X]; var B = d.Vertices[t.Vertices.Y]; var C = d.Vertices[t.Vertices.Z];
                        double den = (B.Y - C.Y) * (A.X - C.X) + (C.X - B.X) * (A.Y - C.Y);
                        if (Math.Abs(den) < 1e-9) continue;
                        double a = ((B.Y - C.Y) * (p.Position.X - C.X) + (C.X - B.X) * (p.Position.Y - C.Y)) / den;
                        double bb = ((C.Y - A.Y) * (p.Position.X - C.X) + (A.X - C.X) * (p.Position.Y - C.Y)) / den;
                        double cc = 1 - a - bb;
                        double mz = (A.Z + B.Z + C.Z) / 3;
                        if (mz >= p.Position.Z - 60) continue;
                        if (a >= -1e-6 && bb >= -1e-6 && cc >= -1e-6)
                        {
                            double z = a * A.Z + bb * B.Z + cc * C.Z;
                            if (!walkUnder || z > best) { best = z; nearD = 0; walkUnder = true; }
                            continue;
                        }
                        if (walkUnder) continue;
                        double dx = (A.X + B.X + C.X) / 3 - p.Position.X, dy = (A.Y + B.Y + C.Y) / 3 - p.Position.Y, dd = Math.Sqrt(dx * dx + dy * dy);
                        if (dd < 160 && (dd < nearD - 40 || (dd < nearD + 40 && mz > best))) { best = mz; nearD = dd; }
                    }
                }
                if (double.IsNegativeInfinity(best)) continue;
                var under = c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>()
                    .Where(o => o != r && o.Placement is { } q && models.TryGetValue(o.Base.FormKey, out var e2) && !re.IsMatch(e2)
                                && Math.Abs(q.Position.X - p.Position.X) < 70 && Math.Abs(q.Position.Y - p.Position.Y) < 70
                                && q.Position.Z < p.Position.Z - 40 && q.Position.Z > best - 20
                                && !Regex.IsMatch(e2, "Floor|Rug|Wall|Ceiling|Beam|Plank|Room|Hall|Fx|Marker|Light|Dust|Debris|Tile|Mid|Corner", RegexOptions.IgnoreCase))
                    .Select(o => models[o.Base.FormKey]).Distinct().Take(4);
                rows.Add((c.EditorID ?? c.FormKey.ToString(), ed, p.Position.Z, best, r.Scale ?? 1f, string.Join(",", under), walkUnder));
            }
        Console.WriteLine("cell\tbase\tscale\torigin over floor\thorns' bottom over floor\trope's top (ceiling) over floor");
        foreach (var x in rows.OrderBy(x => (x.z + ropeTop * x.s) - x.floor))
            Console.WriteLine($"{x.cell}\t{x.ed}\t{x.s:0.00}\t{x.z - x.floor:0}\t{x.z - bottom * x.s - x.floor:0}\t{x.z + ropeTop * x.s - x.floor:0}	{(x.walk ? "walkway" : "over furniture")}	{x.under}");
        Console.WriteLine($"HANGREFS {rows.Count} references with a navmesh under them");
    }
}
