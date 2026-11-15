using System.Text.RegularExpressions;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Skyrim;
// Links: how vanilla wires scripted furniture (Guild Hall, 2026-10-26: the working coat-of-arms rack). For every ref in the
// matching interior cells whose base's editor ID matches the second regex: its position, its linked references (keyword ->
// target and the target's base), its base's scripts with their properties, and any ref that links TO it.
//   dotnet run -c Release -- links "^BYOHHouse1FalkreathBasement$" "WeaponRack"
static class Links
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string cellPattern, string basePattern)
    {
        var cre = new Regex(cellPattern, RegexOptions.IgnoreCase); var bre = new Regex(basePattern, RegexOptions.IgnoreCase);
        var ed = new Dictionary<FormKey, string>(); var recs = new Dictionary<FormKey, IMajorRecordGetter>();
        foreach (var m in mods) foreach (var r in m.EnumerateMajorRecords()) { recs[r.FormKey] = r; if (r.EditorID is { } e) ed[r.FormKey] = e; }
        string Ed(FormKey k) => ed.GetValueOrDefault(k, k.ToString());
        var refs = new Dictionary<FormKey, IPlacedObjectGetter>();
        foreach (var m in mods)
            foreach (var c in m.Cells.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).Where(c => cre.IsMatch(c.EditorID ?? "")))
                foreach (var r in c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>()) refs[r.FormKey] = r;
        string Props(IEnumerable<IScriptEntryGetter> scripts) => string.Join(" | ", scripts.Select(s => s.Name + "(" + string.Join(", ", s.Properties.Select(p => p switch
            {
                IScriptObjectPropertyGetter o => $"{p.Name}={Ed(o.Object.FormKey)}",
                IScriptIntPropertyGetter i => $"{p.Name}={i.Data}", IScriptBoolPropertyGetter bo => $"{p.Name}={bo.Data}",
                IScriptFloatPropertyGetter f => $"{p.Name}={f.Data}", _ => p.Name })) + ")"));
        string Scripts(FormKey b)
        {
            if (!recs.TryGetValue(b, out var rec) || rec is not IHaveVirtualMachineAdapterGetter { VirtualMachineAdapter: { } vm }) return "";
            return Props(vm.Scripts);
        }
        foreach (var r in refs.Values.Where(r => bre.IsMatch(Ed(r.Base.FormKey))))
        {
            var p = r.Placement?.Position;
            Console.WriteLine($"{r.FormKey} {Ed(r.Base.FormKey)} at {p?.X:0},{p?.Y:0},{p?.Z:0} rot {r.Placement?.Rotation.Z * 180 / Math.PI:0.0}{((r.MajorRecordFlagsRaw & 0x400) != 0 ? " persistent" : "")}");
            foreach (var l in r.LinkedReferences)
                Console.WriteLine($"    link [{(l.KeywordOrReference.FormKey == r.FormKey ? "" : Ed(l.KeywordOrReference.FormKey))}] -> {l.Reference.FormKey} {(refs.TryGetValue(l.Reference.FormKey, out var t) ? Ed(t.Base.FormKey) : "?")}");
            var s = Scripts(r.Base.FormKey); if (s.Length > 0) Console.WriteLine($"    base scripts: {s}");
            if (r.VirtualMachineAdapter is { } rv) Console.WriteLine($"    ref scripts: {Props(rv.Scripts)}");
            if (r.EnableParent is { } ep) Console.WriteLine($"    enable parent: {ep.Reference.FormKey} {ep.Flags}");
            if ((r.MajorRecordFlagsRaw & 0x800) != 0) Console.WriteLine("    initially disabled");
            foreach (var o in refs.Values.Where(o => o.LinkedReferences.Any(l => l.Reference.FormKey == r.FormKey)))
                Console.WriteLine($"    linked from {o.FormKey} {Ed(o.Base.FormKey)}");
        }
    }
}
