using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Skyrim;
// RefDiff: what a new hall build did to the last one's references (2026-10-26, the fit-out's ledger): per interior cell,
// every ref by ID - kept as it was, moved (how far), re-based (a light given another record), retired (initially disabled),
// or new - and any ID whose record changed kind. Read-only.
//   dotnet run -c Release -- refdiff <old AGHallSpike.esp> <new AGHallSpike.esp> [--all]
static class RefDiff
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string a, string b, bool all)
    {
        using var ma = SkyrimMod.CreateFromBinaryOverlay(a, SkyrimRelease.SkyrimSE);
        using var mb = SkyrimMod.CreateFromBinaryOverlay(b, SkyrimRelease.SkyrimSE);
        var ed = new Dictionary<FormKey, string>();
        foreach (var m in mods.Cast<ISkyrimModGetter>().Append(ma).Append(mb)) foreach (var r in m.EnumerateMajorRecords()) if (r.EditorID is { } e) ed[r.FormKey] = e;
        string Ed(FormKey k) => ed.GetValueOrDefault(k, k.ToString());
        // (2026-10-27) across the rename (AGHallSpike.esp -> "AdventurersGuild - Guild Hall.esp") the old plugin's IDs are
        // compared by number; the NPC session's merged blocks (0x8000-0x97FF, and the promotion trials' 0x9800-0x99FF) are theirs, not this build's
        FormKey M(FormKey k) => k.ModKey == ma.ModKey ? new FormKey(mb.ModKey, k.ID) : k;
        static bool Npc(FormKey k) => k.ID >= 0x8000 && k.ID <= 0x99FF;
        Dictionary<FormKey, (string cell, IPlacedObjectGetter r)> Refs(ISkyrimModGetter m) =>
            m.Cells.SelectMany(x => x.SubBlocks).SelectMany(s => s.Cells).Where(c => c.EditorID?.StartsWith("AGHall2") == true)
             .SelectMany(c => c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>().Where(r => !Npc(r.FormKey)).Select(r => (c.EditorID!, r)))
             .ToDictionary(t => M(t.r.FormKey), t => t);
        var ra = Refs(ma); var rb = Refs(mb);
        // records of the old plugin whose ID now holds another kind of record
        var kinds = mb.EnumerateMajorRecords().Where(r => !Npc(r.FormKey)).ToDictionary(r => r.FormKey, r => r.GetType().Name);
        int clash = 0;
        foreach (var r in ma.EnumerateMajorRecords().Where(r => !Npc(r.FormKey)))
            if (kinds.TryGetValue(M(r.FormKey), out var k) && k != r.GetType().Name) { Console.WriteLine($"KIND {r.FormKey} was {r.GetType().Name} now {k}"); clash++; }
        var missing = ma.EnumerateMajorRecords().Where(r => !Npc(r.FormKey) && !kinds.ContainsKey(M(r.FormKey))).ToList();
        foreach (var r in missing) Console.WriteLine($"GONE {r.FormKey} {r.EditorID} {r.GetType().Name}");
        int same = 0, moved = 0, rebased = 0, retired = 0, added = 0;
        foreach (var (k, (cell, r)) in ra)
        {
            if (!rb.TryGetValue(k, out var nb)) { Console.WriteLine($"GONE  {cell} {k} {Ed(r.Base.FormKey)}"); continue; }
            var n = nb.r; var p0 = r.Placement!.Position; var p1 = n.Placement!.Position;
            double dist = Math.Sqrt(Math.Pow(p1.X - p0.X, 2) + Math.Pow(p1.Y - p0.Y, 2) + Math.Pow(p1.Z - p0.Z, 2));
            bool dis = (n.MajorRecordFlagsRaw & 0x800) != 0 && (r.MajorRecordFlagsRaw & 0x800) == 0;
            if (nb.cell != cell) Console.WriteLine($"CELL  {k} {cell} -> {nb.cell}");
            if (dis) { retired++; Console.WriteLine($"RETIRED {cell} {k} {Ed(r.Base.FormKey)} {r.EditorID}"); }
            else if (n.Base.FormKey != M(r.Base.FormKey)) { rebased++; if (all) Console.WriteLine($"REBASE {cell} {k} {Ed(r.Base.FormKey)} -> {Ed(n.Base.FormKey)} moved {dist:0}"); }
            else if (dist > 0.5 || Math.Abs(n.Placement.Rotation.Z - r.Placement.Rotation.Z) > 1e-3) { moved++; if (all) Console.WriteLine($"MOVED {cell} {k} {Ed(r.Base.FormKey)} {n.EditorID} by {dist:0}"); }
            else same++;
        }
        foreach (var (k, (cell, n)) in rb.Where(kv => !ra.ContainsKey(kv.Key))) { added++; if (all) Console.WriteLine($"NEW   {cell} {k} {Ed(n.Base.FormKey)} {n.EditorID}"); }
        Console.WriteLine($"REFDIFF {ra.Count} -> {rb.Count} refs: {same} unchanged, {moved} moved, {rebased} re-based (lights), {retired} retired, {added} new; {clash} IDs changed kind, {missing.Count} records gone");
    }
}
