using System.Text.RegularExpressions;
using Mutagen.Bethesda.Skyrim;
// Vmad: where vanilla keeps an activator's script and its property values, on the base or on each reference (2026-10-29, the
// basement's weapon racks: no reference of WeaponRackMidACTIVATORPlayerHouse carried the script): the base's scripts, then
// its references counted with and without their own, one sample of each kind with its linked references' keywords.
//   dotnet run -- vmad "<activator editor ID regex>"
static class Vmad
{
    static string Props(IScriptEntryGetter s) => s.Name + " {" + string.Join(", ", s.Properties.Select(p => p.Name + "=" + (p switch
    {
        IScriptIntPropertyGetter i => i.Data.ToString(), IScriptBoolPropertyGetter b => b.Data.ToString(),
        IScriptFloatPropertyGetter f => f.Data.ToString(), IScriptObjectPropertyGetter o => o.Object.FormKey.ToString(), _ => "?"
    }))) + "}";
    public static void Run(List<ISkyrimModDisposableGetter> mods, string pattern)
    {
        var re = new Regex(pattern, RegexOptions.IgnoreCase);
        var bases = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, IActivatorGetter>();
        foreach (var m in mods) foreach (var a in m.Activators) if (re.IsMatch(a.EditorID ?? "")) bases[a.FormKey] = a;
        var kw = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, string>();
        foreach (var m in mods) foreach (var k in m.Keywords) kw[k.FormKey] = k.EditorID ?? "?";
        foreach (var a in bases.Values)
        {
            Console.WriteLine($"== {a.EditorID} {a.FormKey}: base scripts: " + (a.VirtualMachineAdapter is { } v ? string.Join("; ", v.Scripts.Select(Props)) : "none"));
            int with = 0, without = 0; IPlacedObjectGetter? sw = null, so = null; string? cw = null, co = null;
            foreach (var m in mods) foreach (var b in m.Cells) foreach (var sb in b.SubBlocks) foreach (var c in sb.Cells)
                foreach (var r in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>())
                {
                    if (r.Base.FormKey != a.FormKey) continue;
                    if (r.VirtualMachineAdapter is { Scripts.Count: > 0 }) { with++; if (sw is null) { sw = r; cw = c.EditorID; } }
                    else { without++; if (so is null) { so = r; co = c.EditorID; } }
                }
            Console.WriteLine($"   interior references: {with} with their own scripts, {without} without");
            foreach (var (r, c) in new[] { (sw, cw), (so, co) })
            {
                if (r is null) continue;
                Console.WriteLine($"   e.g. {r.FormKey} in {c}: persistent {r.MajorRecordFlagsRaw & 0x400}, scripts: " +
                    (r.VirtualMachineAdapter is { } rv ? string.Join("; ", rv.Scripts.Select(Props)) : "none") + "; links: " +
                    string.Join(", ", r.LinkedReferences.Select(l => kw.GetValueOrDefault(l.KeywordOrReference.FormKey, "(none)") + "->" + l.Reference.FormKey)));
            }
        }
    }
}
