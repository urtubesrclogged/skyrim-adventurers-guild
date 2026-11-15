using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Skyrim;
// GrassOf: what grows on given landscape textures in a real MO2 load order (last override wins): per LTEX its GRAS records
// with density and model, and which enabled mod supplies that model as a loose file (else it comes from an archive).
//   grassof <MO2 instance dir> <profile> <LTEX EditorID,...>
static class GrassOf
{
    public static void Run(string inst, string profile, string ltexIds)
    {
        var order = File.ReadAllLines(Path.Combine(inst, "profiles", profile, "modlist.txt")).Where(l => l.StartsWith("+")).Select(l => l[1..]).ToList();
        var byName = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var m in Enumerable.Reverse(order))
        {
            var dir = Path.Combine(inst, "mods", m);
            if (!Directory.Exists(dir)) continue;
            foreach (var f in Directory.GetFiles(dir).Where(f => f.EndsWith(".esm", true, null) || f.EndsWith(".esp", true, null) || f.EndsWith(".esl", true, null)))
                byName[Path.GetFileName(f)] = f;
        }
        var active = new List<string> { "Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm", "Dragonborn.esm" };
        active.AddRange(File.ReadAllLines(Path.Combine(inst, "profiles", profile, "plugins.txt")).Where(l => l.StartsWith("*")).Select(l => l[1..].Trim()));
        var loaded = new List<ISkyrimModDisposableGetter>();
        foreach (var p in active.Distinct(StringComparer.OrdinalIgnoreCase))
        {
            if (!byName.TryGetValue(p, out var path)) continue;
            try { loaded.Add(SkyrimMod.CreateFromBinaryOverlay(path, SkyrimRelease.SkyrimSE)); } catch { }
        }
        var ltex = new Dictionary<FormKey, (ILandscapeTextureGetter t, string mod)>();
        var gras = new Dictionary<FormKey, (IGrassGetter g, string mod)>();
        foreach (var m in loaded)
        {
            foreach (var t in m.LandscapeTextures) ltex[t.FormKey] = (t, m.ModKey.FileName);
            foreach (var g in m.Grasses) gras[g.FormKey] = (g, m.ModKey.FileName);
        }
        string? Loose(string rel)                                  // highest-priority enabled mod with the file loose
        {
            foreach (var m in order)
            {
                var p = Path.Combine(inst, "mods", m, "meshes", rel);
                if (File.Exists(p)) return p;
            }
            return null;
        }
        foreach (var id in ltexIds.Split(','))
        {
            var hit = ltex.Values.Where(v => string.Equals(v.t.EditorID, id, StringComparison.OrdinalIgnoreCase)).ToList();
            if (hit.Count == 0) { Console.WriteLine($"{id}: not found"); continue; }
            var (t, mod) = hit[0];
            Console.WriteLine($"{id} (winning record from {mod}): {t.Grasses.Count} grasses");
            foreach (var gl in t.Grasses)
            {
                if (!gras.TryGetValue(gl.FormKey, out var g)) { Console.WriteLine($"   {gl.FormKey}: unresolved"); continue; }
                var model = g.g.Model?.File.DataRelativePath.ToString() ?? "";
                var rel = model.StartsWith("meshes\\", StringComparison.OrdinalIgnoreCase) ? model[7..] : model;
                Console.WriteLine($"   {g.g.EditorID} [{g.mod}] density {g.g.Density} slope {g.g.MinSlope}-{g.g.MaxSlope} heightRange {g.g.HeightRange} posRange {g.g.PositionRange} flags {g.g.Flags}\t{rel}\t{Loose(rel) ?? "(archive)"}");
            }
        }
    }
}
