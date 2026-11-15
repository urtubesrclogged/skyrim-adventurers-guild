using Mutagen.Bethesda.Skyrim;
// WaterSurvey: the interior cells that hold water (2026-10-28, the basement's pool, real water as the bathhouse mods use):
// each one's water height and water type, as the masters set them.
//   dotnet run -c Release -- watersurvey [cell editor ID ...]
static class WaterSurvey
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string[] names)
    {
        var eds = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, string>();
        foreach (var m in mods) foreach (var w in m.Waters) eds[w.FormKey] = w.EditorID ?? "";
        var seen = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, string>();
        foreach (var m in mods) foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells)
        {
            if (names.Length > 0)   // (named cells: their flags too, whether or not they set a water height)
            {
                if (names.Contains(c.EditorID ?? "")) seen[c.FormKey] = $"{c.EditorID}	{c.Flags}	{c.WaterHeight}	{c.Water.FormKeyNullable}";
                continue;
            }
            if (c.WaterHeight is not { } h || Math.Abs(h) > 1e6 || c.Water.FormKeyNullable is not { } wk) continue;
            seen[c.FormKey] = $"{c.EditorID}\t{h}\t{eds.GetValueOrDefault(wk, wk.ToString())}\t{wk}";
        }
        foreach (var s in seen.Values.OrderBy(s => s)) Console.WriteLine(s);
    }
}
