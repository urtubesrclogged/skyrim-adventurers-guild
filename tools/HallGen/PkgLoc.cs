using Mutagen.Bethesda.Skyrim;
// PkgLoc: where vanilla's sleep packages point (2026-10-30, the hall's NPCs stopping under their beds): the location data of every package
// built on a template, by kind of target and radius.   dotnet run -- pkgloc <template editor ID regex>
public static class PkgLoc
{
    public static void Run(List<ISkyrimModDisposableGetter> mods, string rx)
    {
        var r = new System.Text.RegularExpressions.Regex(rx); var seen = new Dictionary<string, int>(); var ex = new Dictionary<string, string>();
        var byKey = new Dictionary<Mutagen.Bethesda.Plugins.FormKey, IPackageGetter>();
        foreach (var m in mods) foreach (var p in m.Packages) byKey[p.FormKey] = p;
        foreach (var p in byKey.Values)
        {
            var tmpl = byKey.TryGetValue(p.PackageTemplate.FormKey, out var t) ? t.EditorID ?? "" : "";
            if (!r.IsMatch(tmpl) && !r.IsMatch(p.EditorID ?? "")) continue;
            foreach (var kv in p.Data)
                if (kv.Value is IPackageDataLocationGetter l)
                {
                    var tg = l.Location.Target?.GetType().Name.Replace("BinaryOverlay", "").Replace("Location", "") ?? "null";
                    var key = $"{tg,-22} radius {l.Location.Radius}"; seen[key] = seen.GetValueOrDefault(key) + 1; ex[key] = p.EditorID ?? "";
                }
        }
        foreach (var kv in seen.OrderByDescending(k => k.Value).Take(16)) Console.WriteLine($"{kv.Value,5}  {kv.Key}   e.g. {ex[kv.Key]}");
    }
}
