using System.Text.Json;
using System.Text.RegularExpressions;
using Mutagen.Bethesda.Skyrim;
// CellPlan: an interior cell's floor plan as data (2026-11-12, the tavern study: how vanilla's and the mods' taverns lay out their
// floors): its navmesh triangles and every placed piece with its record's bounds, as the last loaded plugin has the cell.
//   dotnet run -- cellplan "<cell editor ID regex>" <out dir>      (EXTRA_PLUGINS=<mods' plugins>)  -> <out dir>/<cell>.json
public static class CellPlan
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string rx, string outDir)
    {
        var re = new Regex(rx, RegexOptions.IgnoreCase); Directory.CreateDirectory(outDir);
        var bases = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, (string ed, string type, float[] b)>();
        void Add<T>(IEnumerable<T> recs, string ty) where T : ISkyrimMajorRecordGetter, IObjectBoundedGetter
        { foreach (var r in recs) if (r.ObjectBounds is { } b) bases[r.FormKey] = (r.EditorID ?? "", ty, new float[] { b.First.X, b.First.Y, b.First.Z, b.Second.X, b.Second.Y, b.Second.Z }); }
        foreach (var m in mods) { Add(m.Statics, "STAT"); Add(m.Furniture, "FURN"); Add(m.Containers, "CONT"); Add(m.MoveableStatics, "MSTT"); Add(m.Activators, "ACTI"); Add(m.Florae, "FLOR"); Add(m.MiscItems, "MISC"); Add(m.Doors, "DOOR"); Add(m.IdleMarkers, "IDLM"); }
        // (every plugin's copy of the cell: a cell record overridden by a later plugin carries only that plugin's refs; refs and
        // navmeshes merged by their own form keys, the last plugin's copy of each winning)
        var cells = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, List<(ICellGetter c, string mod)>>();
        foreach (var m in mods) foreach (var bl in m.Cells) foreach (var sb in bl.SubBlocks) foreach (var c in sb.Cells)
            if (re.IsMatch(c.EditorID ?? "")) { if (!cells.ContainsKey(c.FormKey)) cells[c.FormKey] = new(); cells[c.FormKey].Add((c, m.ModKey.FileName)); }
        foreach (var copies in cells.Values)
        {
            var c = copies.Last().c; var mod = string.Join("+", copies.Select(x => x.mod).Distinct());
            var allRefs = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, IPlacedObjectGetter>();
            foreach (var (cc, _) in copies) foreach (var o in cc.Persistent.Concat(cc.Temporary).OfType<IPlacedObjectGetter>()) allRefs[o.FormKey] = o;
            var allNav = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, INavigationMeshGetter>();
            foreach (var (cc, _) in copies) foreach (var n in cc.NavigationMeshes) allNav[n.FormKey] = n;
            var refs = new List<object>();
            foreach (var o in allRefs.Values)
            {
                if (o.IsDeleted) continue;
                if (o.Placement is not { } pl || !bases.TryGetValue(o.Base.FormKey, out var b)) continue;
                refs.Add(new { ed = b.ed, type = b.type, pos = new[] { pl.Position.X, pl.Position.Y, pl.Position.Z }, rz = pl.Rotation.Z, scale = o.Scale ?? 1f, b = b.b });
            }
            var tris = new List<float[]>();
            foreach (var n in allNav.Values) if (n.Data is { } d)
                foreach (var t in d.Triangles) { var A = d.Vertices[t.Vertices.X]; var B = d.Vertices[t.Vertices.Y]; var C = d.Vertices[t.Vertices.Z]; tris.Add(new[] { A.X, A.Y, A.Z, B.X, B.Y, B.Z, C.X, C.Y, C.Z }); }
            var name = c.EditorID ?? c.FormKey.ToString();
            File.WriteAllText(Path.Combine(outDir, name + ".json"), JsonSerializer.Serialize(new { cell = name, mod, refs, tris }));
            Console.WriteLine($"{name} ({mod}): {refs.Count} refs, {tris.Count} navmesh triangles");
        }
    }
}
