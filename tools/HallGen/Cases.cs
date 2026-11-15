using System.Text.RegularExpressions;
using Mutagen.Bethesda.Skyrim;
// Cases: how vanilla sets its display cases (for a locked display case with a valuable weapon
// inside): every reference of a base whose editor ID matches, its base's record type, its lock (level, key) and owner, its
// links and what links to it; and the weapons whose editor ID matches a second regex, with value and playable flag.
//   dotnet run -- cases "<case regex>" "<weapon regex>"
static class Cases
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string casePat, string weapPat)
    {
        var re = new Regex(casePat, RegexOptions.IgnoreCase); var wre = new Regex(weapPat, RegexOptions.IgnoreCase);
        var ed = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, (string e, string t)>();
        foreach (var m in mods) foreach (var r in m.EnumerateMajorRecords()) if (r.EditorID is { } e) ed[r.FormKey] = (e, r.GetType().Name.Replace("BinaryOverlay", ""));
        foreach (var m in mods) foreach (var w in m.Weapons) if (wre.IsMatch(w.EditorID ?? ""))
            Console.WriteLine($"WEAPON {w.EditorID} {w.FormKey} \"{w.Name?.String}\" value {w.BasicStats?.Value} damage {w.BasicStats?.Damage} flags {w.Data?.Flags} model {w.Model?.File}");
        foreach (var m in mods) foreach (var w in m.Keys) if (wre.IsMatch(w.EditorID ?? ""))
            Console.WriteLine($"KEYM {w.EditorID} {w.FormKey} \"{w.Name?.String}\" model {w.Model?.File}");
        foreach (var m in mods) foreach (var w in m.Ammunitions) if (wre.IsMatch(w.EditorID ?? ""))
            Console.WriteLine($"AMMO {w.EditorID} {w.FormKey} \"{w.Name?.String}\" value {w.Value} damage {w.Damage} flags {w.Flags} model {w.Model?.File}");
        var all = new List<(string cell, IPlacedObjectGetter r)>();
        foreach (var m in mods) foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells)
            foreach (var r in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>()) all.Add((c.EditorID ?? "?", r));
        var into = all.SelectMany(x => x.r.LinkedReferences.Select(l => (to: l.Reference.FormKey, from: x.r))).ToLookup(x => x.to, x => x.from);
        var counts = new Dictionary<string, (int n, int locked)>();
        foreach (var (cell, r) in all)
        {
            if (!ed.TryGetValue(r.Base.FormKey, out var b) || !re.IsMatch(b.e)) continue;
            var k = $"{b.e} ({b.t})"; var cnt = counts.GetValueOrDefault(k); counts[k] = (cnt.n + 1, cnt.locked + (r.Lock is null ? 0 : 1));
            if (r.Lock is null) continue;
            Console.WriteLine($"LOCKED {b.e} {r.FormKey} in {cell}: level {r.Lock.Level} key {(r.Lock.Key.IsNull ? "none" : ed.GetValueOrDefault(r.Lock.Key.FormKey).e)} owner {(r.Owner.IsNull ? "none" : ed.GetValueOrDefault(r.Owner.FormKey).e)}; links " +
                string.Join(", ", r.LinkedReferences.Select(l => ed.GetValueOrDefault(l.KeywordOrReference.FormKey).e + "->" + ed.GetValueOrDefault(all.FirstOrDefault(a => a.r.FormKey == l.Reference.FormKey).r?.Base.FormKey ?? default).e)) +
                "; linked from " + string.Join(", ", into[r.FormKey].Select(f => ed.GetValueOrDefault(f.Base.FormKey).e)));
        }
        foreach (var kv in counts.OrderByDescending(k => k.Value.n)) Console.WriteLine($"COUNT {kv.Key}: {kv.Value.n} references, {kv.Value.locked} locked");
    }
}
