using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Skyrim;

// Shells: every exterior load door in every worldspace, the largest static it stands on (the building), and the door's
// offset in that static's own frame. One line per building base, largest first, with where vanilla uses it - so a big
// shell and its door can be placed together at run time. Output: TSV.
static class Shells
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, int minSide)
    {
        var bases = new Dictionary<FormKey, ISkyrimMajorRecordGetter>();
        foreach (var m in mods) { foreach (var s in m.Statics) bases[s.FormKey] = s; foreach (var d in m.Doors) bases[d.FormKey] = d; }
        var interiors = mods.SelectMany(m => m.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(sb => sb.Cells)).ToList();
        var refCell = new Dictionary<FormKey, ICellGetter>();
        foreach (var c in interiors) foreach (var r in c.Persistent.Concat(c.Temporary)) refCell[r.FormKey] = c;
        var seen = new Dictionary<FormKey, string>();
        foreach (var w in mods.SelectMany(m => m.Worldspaces).GroupBy(w => w.FormKey).Select(g => g.Last()))
        {
            var all = mods.SelectMany(m => m.Worldspaces).Where(x => x.FormKey == w.FormKey).SelectMany(x => x.EnumerateMajorRecords<IPlacedObjectGetter>())
                .GroupBy(r => r.FormKey).Select(g => g.Last()).Where(r => r.Placement is not null).ToList();
            var statics = all.Where(r => bases.TryGetValue(r.Base.FormKey, out var b) && b is IStaticGetter s && s.ObjectBounds is { } ob
                && Math.Max(ob.Second.X - ob.First.X, ob.Second.Y - ob.First.Y) >= minSide).ToList();
            foreach (var d in all.Where(r => r.TeleportDestination is not null && bases.TryGetValue(r.Base.FormKey, out var b) && b is IDoorGetter))
            {
                var into = refCell.GetValueOrDefault(d.TeleportDestination!.Door.FormKey);
                if (into is null) continue;   // a door to another worldspace, not to an interior
                var dp = d.Placement!.Position;
                var hits = statics.Select(s => (s, dist: Math.Sqrt(Math.Pow(s.Placement!.Position.X - dp.X, 2) + Math.Pow(s.Placement.Position.Y - dp.Y, 2))))
                    .Where(t => { var ob = ((IStaticGetter)bases[t.s.Base.FormKey]).ObjectBounds!; return t.dist < Math.Max(ob.Second.X - ob.First.X, ob.Second.Y - ob.First.Y) * 0.75 * (t.s.Scale ?? 1); })
                    .OrderBy(t => t.dist).ToList();
                if (hits.Count == 0) continue;
                var (shell, _) = hits[0];
                var sb = (IStaticGetter)bases[shell.Base.FormKey];
                if (seen.ContainsKey(sb.FormKey)) { seen[sb.FormKey] += $", {into.Name?.String ?? into.EditorID}"; continue; }
                var sp = shell.Placement!; var o = sb.ObjectBounds!; float sc = shell.Scale ?? 1;
                double a = sp.Rotation.Z, dx = dp.X - sp.Position.X, dy = dp.Y - sp.Position.Y;
                double lx = (dx * Math.Cos(a) - dy * Math.Sin(a)) / sc, ly = (dx * Math.Sin(a) + dy * Math.Cos(a)) / sc;
                seen[sb.FormKey] = $"{(o.Second.X - o.First.X) * (o.Second.Y - o.First.Y)}\t{sb.FormKey.ModKey.FileName}:{sb.FormKey.ID:X6}\t{sb.EditorID}\t{o.Second.X - o.First.X}x{o.Second.Y - o.First.Y}x{o.Second.Z - o.First.Z}\t{sb.Model?.File}\tdoor {bases[d.Base.FormKey].EditorID} local ({lx:F0},{ly:F0},{(dp.Z - sp.Position.Z) / sc:F0}) rel.rot {(d.Placement.Rotation.Z - sp.Rotation.Z) * 180 / Math.PI:F0} deg\tscale {sc:F2}\t{w.EditorID}\tleads into: {into.Name?.String ?? into.EditorID}";
            }
        }
        foreach (var line in seen.Values.OrderByDescending(l => long.Parse(l.Split('\t')[0])))
            Console.WriteLine(line);
    }
}
