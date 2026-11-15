using System.Text.RegularExpressions;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Skyrim;
// Interiors: how vanilla builds a hall, measured (Guild Hall interior research, 2026-10-24). For every interior cell whose
// editor ID matches the pattern, one JSON line: its settings (lighting template, image space, acoustic space, music,
// location, owner, flags, own lighting), its extent, the floor levels its kit floors stand at, what it holds by record
// type and by kind (chandeliers, trophies, banners, window light, tables...), its lights (shadow casters apart), its
// room markers, portals and occlusion planes, its doors, and its navmesh.
static class Interiors
{
    static readonly (string kind, string pattern)[] Kinds =
    {
        ("chandelier", "chandelier"), ("trophy", "trophy|mounted|plaque"), ("banner", "banner|tapestry"),
        ("window light", "lightray|lightbeam|godray|lightshaft|fxlight|windowlight|rays"), ("window", "window"),
        ("fire", "fireplace|firepit|hearth|fxfire"), ("counter", "counter|bar0|barend|barcorner"), ("table", "table"),
        ("bench/chair", "bench|chair|stool|throne"), ("bed", "bed"), ("rug", "rug|carpet"), ("shelf", "shelf|bookcase|bookshelf"),
        ("rack/case", "rack|displaycase|mannequin"), ("pillar/beam", "pillar|column|beam|post"), ("stair", "stair"),
        ("railing/balcony", "rail|balcon|balust|banister|walkway|catwalk"), ("skull/bones", "skull|bones|dragonbone"),
    };

    public static void Run(List<ISkyrimModDisposableGetter> mods, string pattern)
    {
        var re = new Regex(pattern, RegexOptions.IgnoreCase);
        var info = new Dictionary<FormKey, (string type, string ed, string model)>();
        void Add(IEnumerable<ISkyrimMajorRecordGetter> rs, string type)
        {
            foreach (var r in rs) info[r.FormKey] = (type, r.EditorID ?? "", ((r as IModeledGetter)?.Model?.File.ToString() ?? "").ToLowerInvariant());
        }
        foreach (var m in mods)
        {
            Add(m.Statics, "STAT"); Add(m.MoveableStatics, "MSTT"); Add(m.Furniture, "FURN"); Add(m.Containers, "CONT");
            Add(m.Doors, "DOOR"); Add(m.Lights, "LIGH"); Add(m.Activators, "ACTI"); Add(m.Florae, "FLOR"); Add(m.Trees, "TREE");
            Add(m.IdleMarkers, "IDLM"); Add(m.MiscItems, "MISC"); Add(m.Weapons, "WEAP"); Add(m.Armors, "ARMO"); Add(m.Books, "BOOK");
            Add(m.Ingestibles, "ALCH"); Add(m.Ingredients, "INGR"); Add(m.Keys, "KEYM"); Add(m.SoundMarkers, "SOUN"); Add(m.TextureSets, "TXST");
            Add(m.Hazards, "HAZD"); Add(m.Scrolls, "SCRL"); Add(m.Ammunitions, "AMMO"); Add(m.SoulGems, "SLGM"); Add(m.AddonNodes, "ADDN");
        }
        var names = new Dictionary<FormKey, string>();
        foreach (var m in mods)
            foreach (var r in m.LightingTemplates.Cast<IMajorRecordGetter>().Concat(m.ImageSpaces).Concat(m.AcousticSpaces).Concat(m.MusicTypes)
                         .Concat(m.Locations).Concat(m.EncounterZones).Concat(m.Factions).Concat(m.Npcs))
                names[r.FormKey] = r.EditorID ?? r.FormKey.ToString();
        string Ed(FormKey? k) => k is { } key ? names.GetValueOrDefault(key, key.ToString()) : "";
        var locs = mods.SelectMany(m => m.Locations).GroupBy(l => l.FormKey).ToDictionary(g => g.Key, g => g.Last());
        var kws = mods.SelectMany(m => m.Keywords).GroupBy(k => k.FormKey).ToDictionary(g => g.Key, g => g.Last().EditorID ?? "");
        var lights = mods.SelectMany(m => m.Lights).GroupBy(l => l.FormKey).ToDictionary(g => g.Key, g => g.Last());

        // the winning copy of each interior cell
        // every copy of the cell, in load order: an override (Update.esm) carries only the refs it changes
        var copies = new Dictionary<FormKey, List<ICellGetter>>();
        foreach (var m in mods)
            foreach (var c in m.Cells.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells))
                if (re.IsMatch(c.EditorID ?? "")) { if (!copies.TryGetValue(c.FormKey, out var l)) copies[c.FormKey] = l = new(); l.Add(c); }
        foreach (var all in copies.Values.OrderBy(l => l.Last().EditorID))
        {
            var c = all.Last();
            var merged = new Dictionary<FormKey, IPlacedGetter>();
            var navs = new Dictionary<FormKey, INavigationMeshGetter>();
            foreach (var cc in all)
            {
                foreach (var r in cc.Persistent.Concat(cc.Temporary)) merged[r.FormKey] = r;
                foreach (var n in cc.NavigationMeshes) navs[n.FormKey] = n;
            }
            var placed = merged.Values.Where(r => !r.IsDeleted).ToList();
            var objs = placed.OfType<IPlacedObjectGetter>().Where(r => r.Placement != null).ToList();
            var byType = new SortedDictionary<string, int>();
            var byKind = new SortedDictionary<string, int>();
            var folders = new Dictionary<string, int>();
            var floorZ = new SortedDictionary<int, int>();
            float x0 = float.MaxValue, y0 = float.MaxValue, z0 = float.MaxValue, x1 = float.MinValue, y1 = float.MinValue, z1 = float.MinValue;
            int rooms = 0, portals = 0, planes = 0, multibounds = 0, loadDoors = 0, doors = 0;
            var shadow = new List<object>(); int lightCount = 0;
            var examples = new Dictionary<string, HashSet<string>>();
            foreach (var r in objs)
            {
                if (!info.TryGetValue(r.Base.FormKey, out var b)) b = ("?", r.Base.FormKey.ToString(), "");
                byType[b.type] = byType.GetValueOrDefault(b.type) + 1;
                var p = r.Placement!.Position;
                var ed = b.ed.ToLowerInvariant();
                if (ed == "roommarker") { rooms++; continue; }
                if (ed == "portalmarker") { portals++; continue; }
                if (ed == "planemarker") { planes++; continue; }
                if (ed.Contains("multibound")) { multibounds++; continue; }
                if (b.type == "STAT" && b.model.Length > 0)
                {
                    x0 = Math.Min(x0, p.X); y0 = Math.Min(y0, p.Y); z0 = Math.Min(z0, p.Z); x1 = Math.Max(x1, p.X); y1 = Math.Max(y1, p.Y); z1 = Math.Max(z1, p.Z);
                    var parts = b.model.Split('\\', '/');
                    var folder = string.Join("\\", parts.Take(Math.Max(1, parts.Length - 1)).Take(3));
                    folders[folder] = folders.GetValueOrDefault(folder) + 1;
                    if (Regex.IsMatch(System.IO.Path.GetFileName(b.model), "floor")) { var k = (int)Math.Round(p.Z / 16) * 16; floorZ[k] = floorZ.GetValueOrDefault(k) + 1; }
                }
                if (b.type == "DOOR") { if (r.TeleportDestination is not null) loadDoors++; else doors++; }
                if (b.type == "LIGH")
                {
                    lightCount++;
                    if (lights.TryGetValue(r.Base.FormKey, out var l))
                    {
                        var f = l.Flags;
                        bool sh = f.HasFlag(Light.Flag.ShadowSpotlight) || f.HasFlag(Light.Flag.ShadowHemisphere) || f.HasFlag(Light.Flag.ShadowOmnidirectional);
                        if (sh) shadow.Add(new { ed = b.ed, kind = f.HasFlag(Light.Flag.ShadowSpotlight) ? "spot" : f.HasFlag(Light.Flag.ShadowHemisphere) ? "hemi" : "omni", radius = r.Radius ?? l.Radius, z = Math.Round(p.Z) });
                    }
                }
                var hay = b.ed.ToLowerInvariant() + " " + System.IO.Path.GetFileName(b.model);
                foreach (var (kind, pat) in Kinds)
                    if (Regex.IsMatch(hay, pat))
                    {
                        byKind[kind] = byKind.GetValueOrDefault(kind) + 1;
                        if (!examples.TryGetValue(kind, out var set)) examples[kind] = set = new HashSet<string>();
                        if (set.Count < 6) set.Add(b.ed);
                        break;
                    }
            }
            if (Environment.GetEnvironmentVariable("INTERIORS_MODELS") is { Length: > 0 } mre)   // optional: which bases match, and how often
            {
                var mr = new Regex(mre, RegexOptions.IgnoreCase);
                var hits = objs.Select(r => info.TryGetValue(r.Base.FormKey, out var b2) ? b2 : ("?", "", "")).Where(b2 => mr.IsMatch(b2.Item2 + " " + b2.Item3))
                    .GroupBy(b2 => $"{b2.Item1} {b2.Item2} {b2.Item3}").OrderByDescending(g => g.Count()).Select(g => $"{g.Count()} {g.Key}");
                Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new { cell = c.EditorID, models = hits }));
            }
            int npcs = placed.OfType<IPlacedNpcGetter>().Count();
            int tris = 0, verts = 0;
            foreach (var n in navs.Values) if (n.Data is { } d) { tris += d.Triangles.Count; verts += d.Vertices.Count; }
            var lt = c.Lighting;
            Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new
            {
                cell = c.EditorID, name = c.Name?.String, flags = c.Flags.ToString(),
                template = Ed(c.LightingTemplate.FormKeyNullable), imagespace = Ed(c.ImageSpace.FormKeyNullable), acoustic = Ed(c.AcousticSpace.FormKeyNullable), music = Ed(c.Music.FormKeyNullable),
                location = Ed(c.Location.FormKeyNullable), locKeywords = c.Location.FormKeyNullable is { } lk && locs.TryGetValue(lk, out var lo) ? (lo.Keywords ?? new List<IFormLinkGetter<IKeywordGetter>>()).Select(k => kws.GetValueOrDefault(k.FormKey, k.FormKey.ToString())) : null, zone = Ed(c.EncounterZone.FormKeyNullable), owner = Ed(c.Owner.FormKeyNullable),
                lighting = lt is null ? null : new { ambient = lt.AmbientColor.ToString(), directional = lt.DirectionalColor.ToString(), fogNear = lt.FogNear, fogFar = lt.FogFar, fade = new[] { lt.LightFadeBegin, lt.LightFadeEnd }, inherits = lt.Inherits.ToString() },
                extent = x0 == float.MaxValue ? null : new[] { Math.Round(x1 - x0), Math.Round(y1 - y0), Math.Round(z1 - z0) },
                floors = floorZ.Where(kv => kv.Value >= 3).Select(kv => new[] { kv.Key, kv.Value }),
                refs = objs.Count, npcs, byType, byKind, examples = examples.ToDictionary(kv => kv.Key, kv => kv.Value),
                kits = folders.OrderByDescending(kv => kv.Value).Take(6).Select(kv => $"{kv.Key} {kv.Value}"),
                lights = lightCount, shadowLights = shadow.Count, shadow,
                rooms, portals, planes, multibounds, doors, loadDoors, navmeshes = navs.Count, navTris = tris, navVerts = verts,
            }));
        }
    }
}
