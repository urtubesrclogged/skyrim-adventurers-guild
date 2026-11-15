using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Skyrim;
// Manor: every placed ref of a BYOH house piece in HearthFires.esm's worldspaces, grouped around each house site
// (Lakeview, Windstad, Heljarchen), with position, rotation, scale and model - to rebuild the finished house offline.
static class Manor
{
    public static void Run(List<ISkyrimModDisposableGetter> mods)
    {
        var bases = mods.SelectMany(m => m.Statics).GroupBy(s => s.FormKey).ToDictionary(g => g.Key, g => g.Last());
        foreach (var m in mods)
            foreach (var w in m.Worldspaces)
                foreach (var r in w.EnumerateMajorRecords<IPlacedObjectGetter>())
                {
                    if (!bases.TryGetValue(r.Base.FormKey, out var b)) continue;
                    var model = b.Model?.File.ToString() ?? "";
                    if (!model.Contains("BYOHHouse", StringComparison.OrdinalIgnoreCase) || r.Placement is not { } p) continue;
                    if (b.EditorID?.Contains("INT") == true) continue;
                    Console.WriteLine($"{m.ModKey.FileName}\t{w.EditorID}\t{b.EditorID}\t{p.Position.X:F1}\t{p.Position.Y:F1}\t{p.Position.Z:F1}\t{p.Rotation.X:F4}\t{p.Rotation.Y:F4}\t{p.Rotation.Z:F4}\t{r.Scale ?? 1:F3}\t{model}");
                }
    }
}
