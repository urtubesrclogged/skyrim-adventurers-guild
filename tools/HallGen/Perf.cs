using System.Text.RegularExpressions;
using Mutagen.Bethesda.Skyrim;
// Perf: what the engine pays for a cell (for a performance pass over the upper floors). Every
// placed reference of the interior cells whose editor ID matches, as JSON lines: its record type, base editor ID, model,
// position, rotation, scale, the reference's flags (persistent, don't havok settle, ...) and, for a light, the base's
// radius, flags (shadow kind, portal-strict) and fade with the reference's own trims. blender/perf_report.py reads it.
//   dotnet run -c Release -- perf "<cell regex>"   (EXTRA_PLUGINS=<the hall's plugin>)
static class Perf
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string pattern)
    {
        var re = new Regex(pattern, RegexOptions.IgnoreCase);
        var bases = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, ISkyrimMajorRecordGetter>();
        foreach (var m in mods) foreach (var r in m.EnumerateMajorRecords()) bases[r.FormKey] = (ISkyrimMajorRecordGetter)r;
        var refs = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, (string cell, ISkyrimMajorRecordGetter r)>();
        foreach (var m in mods)
            foreach (var c in m.Cells.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).Where(c => re.IsMatch(c.EditorID ?? "")))
                foreach (var r in c.Persistent.Concat(c.Temporary))
                    refs[r.FormKey] = (c.EditorID!, (ISkyrimMajorRecordGetter)r);
        foreach (var (cell, rec) in refs.Values)
        {
            if (rec.IsDeleted) continue;
            object? o = null;
            if (rec is IPlacedObjectGetter r && r.Placement is { } p)
            {
                bases.TryGetValue(r.Base.FormKey, out var b);
                var model = b is IModeledGetter { Model: { } md } ? md.File.ToString() : "";
                object? light = null;
                if (b is ILightGetter l)
                    light = new { radius = l.Radius, flags = l.Flags.ToString(), fade = l.FadeValue, refRadius = r.Radius, refFade = r.LightData?.FadeOffset };
                o = new
                {
                    cell, kind = b?.GetType().Name.Replace("BinaryOverlay", "") ?? "?", ed = b?.EditorID ?? r.Base.FormKey.ToString(), model,
                    pos = new[] { p.Position.X, p.Position.Y, p.Position.Z }, rot = new[] { p.Rotation.X, p.Rotation.Y, p.Rotation.Z },
                    scale = r.Scale ?? 1f, flags = r.MajorRecordFlagsRaw, prim = r.Primitive is { } pr ? new[] { pr.Bounds.X, pr.Bounds.Y, pr.Bounds.Z } : null,
                    light, enableParent = r.EnableParent != null,
                    obnd = b is IObjectBoundedGetter { ObjectBounds: { } ob } ? new[] { ob.First.X, ob.First.Y, ob.First.Z, ob.Second.X, ob.Second.Y, ob.Second.Z } : null
                };
            }
            else if (rec is IPlacedNpcGetter n && n.Placement is { } q)
                o = new { cell, kind = "NPC", ed = bases.TryGetValue(n.Base.FormKey, out var nb) ? nb.EditorID : n.Base.FormKey.ToString(), model = "",
                          pos = new[] { q.Position.X, q.Position.Y, q.Position.Z }, rot = new[] { 0f, 0f, q.Rotation.Z }, scale = n.Scale ?? 1f, flags = n.MajorRecordFlagsRaw };
            if (o != null) Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(o));
        }
    }
}
