using Mutagen.Bethesda.Skyrim;
using System.Text.RegularExpressions;
// Refs: every placed reference whose base's editor ID matches a regex, with the plugin, cell and position.
//   EXTRA_PLUGINS=<path to Missives.esp> dotnet run -c Release -- refs "MissiveBoard"
static class Refs
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string pattern)
    {
        var re = new Regex(pattern, RegexOptions.IgnoreCase);
        var edid = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, string>();
        foreach (var m in mods)
            foreach (var r in m.EnumerateMajorRecords())
                if (r.EditorID is { } e) edid[r.FormKey] = e;
        foreach (var m in mods)
        {
            var cells = m.Cells.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).Select(c => (c, c.EditorID ?? "interior"))
                .Concat(m.Worldspaces.SelectMany(w => w.SubCells.SelectMany(b => b.Items).SelectMany(s => s.Items)
                    .Concat(w.TopCell is { } t ? new[] { t } : Array.Empty<ICellGetter>())
                    .Select(c => ((ICellGetter)c, $"{w.EditorID} {(c.Grid is { } g ? $"{g.Point.X},{g.Point.Y}" : "persistent")}{(c.EditorID is { } e ? " " + e : "")}"))));
            foreach (var (c, where) in cells)
                foreach (var r in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>())
                {
                    if (!edid.TryGetValue(r.Base.FormKey, out var b) || !re.IsMatch(b)) continue;
                    var p = r.Placement?.Position;
                    Console.WriteLine($"{m.ModKey}\t{where}\t{b}\t{r.FormKey}\t{(p is null ? "?" : $"{p.Value.X:0},{p.Value.Y:0},{p.Value.Z:0}")}");
                }
        }
    }

    // CellRefs: every placed ref with a model in the interior cells whose editor ID matches, as render_assembly.py reads them
    // (plugin, cell, base editor ID, x, y, z, rx, ry, rz radians, scale, model) - the last plugin's copy of each ref.
    //   dotnet run -c Release -- cellrefs "^WhiterunDragonsreach$"
    public static void CellRefs(List<ISkyrimModDisposableGetter> mods, string pattern)
    {
        var re = new Regex(pattern, RegexOptions.IgnoreCase);
        var all_ = Environment.GetEnvironmentVariable("CELLREFS_LIGHTS") == "1";   // (2026-11-05) the cell's lights too, model "(light)"
        var bases = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, (string ed, string model)>();
        foreach (var m in mods)
            foreach (var r in m.EnumerateMajorRecords())
                if (r is IModeledGetter { Model: { } md }) bases[r.FormKey] = (r.EditorID ?? "", md.File.ToString());
                else if (all_ && r is ILightGetter) bases[r.FormKey] = (r.EditorID ?? "", "(light)");
        var refs = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, (string mod, string cell, IPlacedObjectGetter r)>();
        foreach (var m in mods)
            foreach (var c in m.Cells.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).Where(c => re.IsMatch(c.EditorID ?? "")))
                foreach (var r in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>())
                    refs[r.FormKey] = (m.ModKey.FileName, c.EditorID!, r);
        foreach (var (mod, cell, r) in refs.Values)
        {
            if (r.IsDeleted || r.Placement is not { } p || !bases.TryGetValue(r.Base.FormKey, out var b) || b.model.Length == 0) continue;
            // (2026-10-28) only what the game draws: not the ledger's retired refs (initially disabled) nor markers, which the
            // basement's renders showed as a bucket that is gone and white boards before its doors
            if ((r.MajorRecordFlagsRaw & 0x800) != 0 || Regex.IsMatch(b.model, @"(^|\\)Marker", RegexOptions.IgnoreCase)) continue;
            Console.WriteLine($"{mod}\t{cell}\t{b.ed}\t{p.Position.X:F1}\t{p.Position.Y:F1}\t{p.Position.Z:F1}\t{p.Rotation.X:F4}\t{p.Rotation.Y:F4}\t{p.Rotation.Z:F4}\t{r.Scale ?? 1:F3}\t{b.model}");
        }
    }

    // CellLoc: the Location of the Tamriel exterior cells around (x, y), with each location's parents (the last plugin wins).
    //   dotnet run -c Release -- cellloc 3 -13
    public static void CellLoc(List<ISkyrimModDisposableGetter> mods, int cx, int cy)
    {
        var locs = mods.SelectMany(m => m.Locations).GroupBy(l => l.FormKey).ToDictionary(g => g.Key, g => g.Last());
        string Chain(Mutagen.Bethesda.Plugins.FormKey k)
        {
            var parts = new List<string>();
            for (var i = 0; i < 8 && locs.TryGetValue(k, out var l); i++) { parts.Add(l.EditorID ?? k.ToString()); if (l.ParentLocation.FormKeyNullable is not { } p) break; k = p; }
            return string.Join(" < ", parts);
        }
        var cells = new Dictionary<(int, int), ICellGetter>();
        foreach (var m in mods)
            foreach (var w in m.Worldspaces.Where(w => w.EditorID == "Tamriel"))
                foreach (var c in w.SubCells.SelectMany(b => b.Items).SelectMany(s => s.Items))
                    if (c.Grid is { } g && Math.Abs(g.Point.X - cx) <= 1 && Math.Abs(g.Point.Y - cy) <= 1) cells[(g.Point.X, g.Point.Y)] = c;
        foreach (var ((x, y), c) in cells.OrderBy(e => e.Key))
            Console.WriteLine($"{x},{y}\t{(c.Location.FormKeyNullable is { } k ? Chain(k) : "(no location)")}");
    }
}
