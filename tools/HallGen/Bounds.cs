using Mutagen.Bethesda.Skyrim;
static class Bounds
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string[] eds)
    {
        // (2026-10-28, the basement's placement gate, blender/placement_check.py) --json <file of editor IDs, one a line>: every
        // record type the hall places, as one JSON object {ed: {type, obnd}} on stdout
        if (eds.FirstOrDefault() == "--json")
        {
            var want = File.ReadAllLines(eds[1]).Select(l => l.Trim()).Where(l => l != "").ToHashSet(StringComparer.OrdinalIgnoreCase);
            var all = mods.SelectMany(m => m.Statics).Cast<ISkyrimMajorRecordGetter>().Concat(mods.SelectMany(m => m.Doors))
                .Concat(mods.SelectMany(m => m.Furniture)).Concat(mods.SelectMany(m => m.Containers)).Concat(mods.SelectMany(m => m.MoveableStatics))
                .Concat(mods.SelectMany(m => m.Activators)).Concat(mods.SelectMany(m => m.Lights)).Concat(mods.SelectMany(m => m.Trees))
                .Concat(mods.SelectMany(m => m.MiscItems)).Concat(mods.SelectMany(m => m.Florae)).Concat(mods.SelectMany(m => m.Books))
                .Concat(mods.SelectMany(m => m.Ingestibles)).Concat(mods.SelectMany(m => m.Ingredients)).Concat(mods.SelectMany(m => m.Weapons))
                .Concat(mods.SelectMany(m => m.Armors)).Concat(mods.SelectMany(m => m.Ammunitions));
            var o = new Dictionary<string, object>(StringComparer.OrdinalIgnoreCase);
            foreach (var r in all)
                if (r.EditorID is { } e && want.Contains(e) && (r as IObjectBoundedGetter)?.ObjectBounds is { } b)
                    o[e] = new { type = r.GetType().Name.Replace("BinaryOverlay", ""), obnd = new[] { b.First.X, b.First.Y, b.First.Z, b.Second.X, b.Second.Y, b.Second.Z },
                                 name = (r as Mutagen.Bethesda.Plugins.Aspects.INamedGetter)?.Name,
                                 // (2026-11-13: the overlook's chair, CommonChair01L, entered from its left only) each marker's disabled entry points
                                 disabled = (r as IFurnitureGetter)?.Markers?.Select(k => (int)(k.DisabledEntryPoints?.Points ?? 0)).ToArray() };   // (2026-10-29: a player gets no prompt on what has no name)
            Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(o));
            return;
        }
        foreach (var e in eds)
        {
            // statics and doors, and (2026-10-26) furniture, containers and moveable statics: the interior's vanilla pieces
            var r = mods.SelectMany(m => m.Statics).Cast<ISkyrimMajorRecordGetter>().Concat(mods.SelectMany(m => m.Doors))
                        .Concat(mods.SelectMany(m => m.Furniture)).Concat(mods.SelectMany(m => m.Containers))
                        .Concat(mods.SelectMany(m => m.MoveableStatics)).LastOrDefault(x => x.EditorID == e);
            var ob = (r as IObjectBoundedGetter)?.ObjectBounds;
            Console.WriteLine(ob is null ? $"{e}\tnot found" : $"{e}\t{r!.FormKey}\tmin ({ob.First.X},{ob.First.Y},{ob.First.Z}) max ({ob.Second.X},{ob.Second.Y},{ob.Second.Z})\tmodel {(r as IModeledGetter)?.Model?.File}{(r is IContainerGetter ct ? $"\tflags {ct.Flags}" : "")}");
        }
    }
}
