using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Skyrim;
using Noggog;

// Survey: exterior doors in Tamriel that lead into a house, and the large static they sit on (the building shell),
// with the door's offset in the shell's own frame - so a shell and its door can be placed together at run time.
static class Survey
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string nameFilter)
    {
        var tamriel = new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x3C);
        var bases = new Dictionary<FormKey, ISkyrimMajorRecordGetter>();
        foreach (var m in mods) { foreach (var s in m.Statics) bases[s.FormKey] = s; foreach (var d in m.Doors) bases[d.FormKey] = d; }
        var cellsIn = mods.SelectMany(m => m.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(sb => sb.Cells)).ToList();
        var refCell = new Dictionary<FormKey, ICellGetter>();
        foreach (var c in cellsIn) foreach (var r in c.Persistent.Concat(c.Temporary)) refCell[r.FormKey] = c;
        var outside = mods[0].Worldspaces.First(w => w.FormKey == tamriel);
        var all = outside.EnumerateMajorRecords<IPlacedObjectGetter>().ToList();
        var statics = all.Where(r => bases.TryGetValue(r.Base.FormKey, out var b) && b is IStaticGetter).ToList();
        foreach (var d in all.Where(r => r.TeleportDestination is not null && bases.TryGetValue(r.Base.FormKey, out var b) && b is IDoorGetter))
        {
            var into = refCell.GetValueOrDefault(d.TeleportDestination!.Door.FormKey);
            if (into is null || !System.Text.RegularExpressions.Regex.IsMatch(into.EditorID ?? "", nameFilter, System.Text.RegularExpressions.RegexOptions.IgnoreCase)) continue;
            var dp = d.Placement!.Position;
            var shell = statics.Where(s => s.Placement is not null)
                .Select(s => (s, dist: Math.Sqrt(Math.Pow(s.Placement!.Position.X - dp.X, 2) + Math.Pow(s.Placement.Position.Y - dp.Y, 2))))
                .Where(t => t.dist < 900 && ((IStaticGetter)bases[t.s.Base.FormKey]).ObjectBounds is { } ob && (ob.Second.X - ob.First.X) * (ob.Second.Y - ob.First.Y) > 400 * 400)
                .OrderBy(t => t.dist).Take(3).ToList();
            Console.WriteLine($"DOOR {d.FormKey.ID:X6} {bases[d.Base.FormKey].EditorID} -> {into.EditorID} at ({dp.X:F0},{dp.Y:F0},{dp.Z:F0}) rot {d.Placement.Rotation.Z:F3}");
            foreach (var (s, dist) in shell)
            {
                var sp = s.Placement!; var ob = ((IStaticGetter)bases[s.Base.FormKey]).ObjectBounds!;
                // door position in the shell's frame (game yaw: positive turns clockwise seen from above)
                double a = sp.Rotation.Z, dx = dp.X - sp.Position.X, dy = dp.Y - sp.Position.Y;
                double lx = dx * Math.Cos(a) - dy * Math.Sin(a), ly = dx * Math.Sin(a) + dy * Math.Cos(a);
                Console.WriteLine($"   shell {s.FormKey.ID:X6} {bases[s.Base.FormKey].EditorID} {ob.Second.X - ob.First.X}x{ob.Second.Y - ob.First.Y}x{ob.Second.Z - ob.First.Z} scale {s.Scale ?? 1:F2} at ({sp.Position.X:F0},{sp.Position.Y:F0},{sp.Position.Z:F0}) rot {sp.Rotation.Z:F3}  door local ({lx:F0},{ly:F0},{dp.Z - sp.Position.Z:F0}) rel.rot {d.Placement.Rotation.Z - sp.Rotation.Z:F3}");
            }
        }
    }
}
