using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Skyrim;
// Verify: read a built hall plugin back and print what the walk depends on: each interior cell's lighting template and
// inheritance, its refs by base (with the base's editor ID where the plugin or a master has it), and every load door's
// destination (the door it names, that door's cell, the landing point). Read-only.
//   dotnet run -c Release -- verify <plugin.esp>
static class Verify
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string path)
    {
        using var mod = SkyrimMod.CreateFromBinaryOverlay(path, SkyrimRelease.SkyrimSE);
        var all = mods.Cast<ISkyrimModGetter>().Append(mod).ToList();
        var ed = new Dictionary<FormKey, string>();
        foreach (var m in all) foreach (var r in m.EnumerateMajorRecords()) if (r.EditorID is { } e) ed[r.FormKey] = e;
        var cellOf = new Dictionary<FormKey, string>();
        var cells = mod.Cells.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).ToList();
        foreach (var c in cells) foreach (var r in c.Persistent.Concat(c.Temporary)) cellOf[r.FormKey] = c.EditorID ?? c.FormKey.ToString();
        foreach (var c in cells)
        {
            Console.WriteLine($"CELL {c.EditorID} {c.FormKey} name '{c.Name?.String}' template {(c.LightingTemplate.FormKeyNullable is { } t ? ed.GetValueOrDefault(t, t.ToString()) : "none")} inherits {(c.Lighting is { } l ? $"{l.Inherits} ambient {l.AmbientColor.R},{l.AmbientColor.G},{l.AmbientColor.B}" : "-")}");
            foreach (var g in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>().GroupBy(r => r.Base.FormKey).OrderBy(g => ed.GetValueOrDefault(g.Key, "")))
                Console.WriteLine($"   {g.Count(),3} x {ed.GetValueOrDefault(g.Key, g.Key.ToString())} ({g.Key})");
            foreach (var r in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>().Where(r => r.TeleportDestination is not null))
            {
                var td = r.TeleportDestination!;
                Console.WriteLine($"   LOAD DOOR {r.EditorID ?? r.FormKey.ToString()} [{ed.GetValueOrDefault(r.Base.FormKey, "?")}] persistent {(r.MajorRecordFlagsRaw & 0x400) != 0} -> door {td.Door.FormKey} in {cellOf.GetValueOrDefault(td.Door.FormKey, "?")}, land at {td.Position} rot {td.Rotation}");
            }
        }
    }
}
