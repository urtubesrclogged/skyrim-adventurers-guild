// facedata: everything the game builds a face from, read from NPC records, as JSON for the offline face renderer
// (tools/HallSpike/npcs/render_face.py). Ours or vanilla's: vanilla NPCs also name their baked FaceGen file, the
// renderer's ground truth.
//   dotnet run -- <out.json> <plugin to add (or -)> <npc editor id> [...]
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Skyrim;

var data = @"C:\Games\steamapps\common\Skyrim Special Edition\Data";
var mods = new[] { "Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm", "Dragonborn.esm" }
    .Select(f => (ISkyrimModGetter)SkyrimMod.CreateFromBinaryOverlay(Path.Combine(data, f), SkyrimRelease.SkyrimSE)).ToList();
foreach (var extra in args[1].Split(';').Where(x => x != "-"))
    mods.Add(SkyrimMod.CreateFromBinaryOverlay(extra, SkyrimRelease.SkyrimSE));
var cache = mods.ToImmutableLinkCache();
var winners = ((IEnumerable<ISkyrimModGetter>)mods).Reverse().ToList();

string? P(dynamic? a) => a == null || a.IsNull ? null : (string)a.DataRelativePath.ToString();
object Part(IHeadPartGetter h) => new
{
    editorId = h.EditorID, type = h.Type.ToString(), nif = P(h.Model?.File),
    tris = h.Parts.Select(p => new { type = p.PartType?.ToString(), path = P(p.FileName) }).ToList(),
    textureSet = h.TextureSet.TryResolve(cache) is { } ts ? Tex(ts) : null,
    extras = h.ExtraParts.Select(e => Part(cache.Resolve<IHeadPartGetter>(e.FormKey))).ToList(),
};
object Tex(ITextureSetGetter t) => new { editorId = t.EditorID, diffuse = P(t.Diffuse), normal = P(t.NormalOrGloss), subsurface = P(t.EnvironmentMaskOrSubsurfaceTint), detail = P(t.GlowOrDetailMap), specular = P(t.BacklightMaskOrSpecular) };
float[] Rgb(System.Drawing.Color c) => new[] { c.R / 255f, c.G / 255f, c.B / 255f };

var outList = new List<object>();
foreach (var ed in args.Skip(2))
{
    var n = winners.SelectMany(m => m.Npcs).FirstOrDefault(x => x.EditorID == ed);
    if (n == null) { Console.WriteLine($"no NPC {ed}: skipped"); continue; }
    var race = cache.Resolve<IRaceGetter>(n.Race.FormKey);
    var female = n.Configuration.Flags.HasFlag(NpcConfiguration.Flag.Female);
    var hd = female ? race.HeadData!.Female! : race.HeadData!.Male!;
    var own = n.HeadParts.Select(h => cache.Resolve<IHeadPartGetter>(h.FormKey)).ToList();
    // the race's defaults fill every type the NPC names none of (face, eyes, mouth, brows)
    var defaults = hd.HeadParts.Select(h => cache.Resolve<IHeadPartGetter>(h.Head.FormKey))
        .Where(d => !own.Any(o => o.Type == d.Type)).ToList();
    var masks = hd.TintMasks.ToDictionary(t => (int)(t.Index ?? 0), t => t);
    var morph = n.FaceMorph;
    var fm = morph == null ? new Dictionary<string, float>() : typeof(INpcFaceMorphGetter).GetProperties()
        .Where(p => p.PropertyType == typeof(float) && p.Name != "Unknown").ToDictionary(p => p.Name, p => (float)p.GetValue(morph)!);
    var faceTex = n.HeadTexture.TryResolve(cache) ?? hd.DefaultFaceTexture.TryResolve(cache);
    outList.Add(new
    {
        editorId = ed, formId = $"{n.FormKey.ID:X6}", plugin = n.FormKey.ModKey.FileName.String, name = n.Name?.String,
        race = race.EditorID, female, weight = n.Weight,
        faceGen = $@"meshes\actors\character\facegendata\facegeom\{n.FormKey.ModKey.FileName}\{n.FormKey.ID:X8}.nif",
        faceTint = $@"textures\actors\character\facegendata\facetint\{n.FormKey.ModKey.FileName}\{n.FormKey.ID:X8}.dds",
        headParts = own.Concat(defaults).Select(Part).ToList(),
        sliders = fm,
        faceParts = n.FaceParts == null ? null : new { nose = n.FaceParts.Nose, eyes = n.FaceParts.Eyes, mouth = n.FaceParts.Mouth },
        skinTone = n.TextureLighting is { } q ? Rgb(q) : null,
        // no hair colour of its own: the engine uses the race's default for the sex
        hairColor = (n.HairColor.IsNull ? (female ? race.DefaultHairColors?.Female : race.DefaultHairColors?.Male) : n.HairColor)
            ?.TryResolve(cache) is { } hc ? Rgb(hc.Color) : null,
        faceTexture = faceTex == null ? null : Tex(faceTex),
        // every tint mask the race offers, to design a face's tint from scratch (render_face.py / design.py)
        raceTints = hd.TintMasks.Select(m => new { index = m.Index, maskType = m.MaskType?.ToString(), mask = P(m.FileName) }).ToList(),
        tints = n.TintLayers.Select(t => new
        {
            index = t.Index, color = t.Color is { } c ? Rgb(c) : null, alpha = t.InterpolationValue, preset = t.Preset,
            mask = t.Index is { } i && masks.TryGetValue(i, out var m) ? P(m.FileName) : null,
            maskType = t.Index is { } j && masks.TryGetValue(j, out var m2) ? m2.MaskType?.ToString() : null,
        }).ToList(),
    });
}
File.WriteAllText(args[0], JsonSerializer.Serialize(outList, new JsonSerializerOptions { WriteIndented = true }));
Console.WriteLine($"wrote {args[0]}: {outList.Count} NPC(s)");
