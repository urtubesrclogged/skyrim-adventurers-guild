// npcgen: writes AGNpcSpike.esp, the Guild Hall NPC spike's plugin (tools/HallSpike/npcs, private, not part of the mod).
//   dotnet run -- <AGHallSpike.esp> <out dir> [seed]
// Faces are recipes, not FaceGen files: each candidate takes its face sliders from one vanilla NPC of its race and sex
// (with a small jitter), its nose/eyes/mouth shapes and brows from a second, its skin (tint layers, complexion, face
// detail texture) from a third, its hair and hair colour from a fourth and its eyes from a fifth. The game builds the face
// at run time (AGFaceSpike.dll keeps the tint and swaps in High Poly Head's heads when it is loaded).
// Writes recipes.json beside the plugin: what each candidate was made from, so a face can be rebuilt or varied.
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Cache;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Skyrim;
using Noggog;

// Two ways to run (the hall folk ship WITH THE HALL, in its own plugin):
//   npcgen <hall.esp> <out dir> [seed]          the spike: AGNpcSpike.esp, a light plugin of its own mastering the hall's
//   npcgen merge <hall.esp> <out.esp> [seed]    the release: the same records added INTO the hall's freshly built plugin
//                                               (its ModKey, its cell; no copy of the cell header), written to out.esp
// Merged, every record of ours takes the spike's ID + 0x7800: the block 0x8000-0x8FFF, which the hall's build never uses,
// and the second block 0x9000-0x97FF (spike 0x1800-0x1FFF), granted by the hall session 2026-11-05.
var merge = args[0] == "merge";
if (merge) args = args[1..];
var hallPath = args[0];
var outDir = merge ? Path.GetDirectoryName(Path.GetFullPath(args[1]))! : args[1];
var mergeOut = merge ? Path.GetFullPath(args[1]) : null;
var seed = args.Length > 2 ? int.Parse(args[2]) : 1;
uint idBase = merge ? 0x7800u : 0u;
var data = @"C:\Games\steamapps\common\Skyrim Special Edition\Data";
var vanilla = new[] { "Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm", "Dragonborn.esm" }
    .Select(f => SkyrimMod.CreateFromBinaryOverlay(Path.Combine(data, f), SkyrimRelease.SkyrimSE)).ToList();
var hall = SkyrimMod.CreateFromBinaryOverlay(hallPath, SkyrimRelease.SkyrimSE);
var all = new List<ISkyrimModGetter>(vanilla) { hall };
var cache = all.ToImmutableLinkCache();
var winners = ((IEnumerable<ISkyrimModGetter>)all).Reverse().ToList();

var mod = merge ? SkyrimMod.CreateFromBinary(hallPath, SkyrimRelease.SkyrimSE) : new SkyrimMod(ModKey.FromFileName("AGNpcSpike.esp"), SkyrimRelease.SkyrimSE);
if (!merge) mod.ModHeader.Flags |= SkyrimModHeader.HeaderFlag.Small;
// the NPC block lies beyond a light plugin's 0x800-0xFFF: the hall's plugin is full from hall2at.
// MERGE_TEST_FULL=1 clears the flag on the output, to try the merge on an older (light) build; never for a deploy.
if (merge && mod.ModHeader.Flags.HasFlag(SkyrimModHeader.HeaderFlag.Small))
{
    if (Environment.GetEnvironmentVariable("MERGE_TEST_FULL") != "1") throw new Exception($"merge: {hall.ModKey.FileName} is a light plugin; the NPC block 0x8000-0x8FFF needs the full plugin (hall2at on)");
    mod.ModHeader.Flags &= ~SkyrimModHeader.HeaderFlag.Small;
    Console.WriteLine("WARNING merge test: the light flag cleared on the output (MERGE_TEST_FULL)");
}
var hallIds = merge ? hall.EnumerateMajorRecords().Where(r => r.FormKey.ModKey == hall.ModKey).Select(r => r.FormKey.ID).ToHashSet() : new HashSet<uint>();
uint next = 0x800;
FormKey Key(uint id)
{
    var at = idBase + id;
    // the NPC blocks: 0x8000-0x8FFF, and 0x9000-0x97FF (spike 0x1800-0x1FFF; the hall session's grant, 2026-11-05)
    // ... and the promotion trials' block, 0x9800-0x99FF (spike 0x2000-0x21FF; the hall session's grant, 2026-11-05)
    if (merge && (at < 0x8000 || at > 0x99FF)) throw new Exception($"ID 0x{at:X} is outside the NPC blocks 0x8000-0x99FF of the hall's plugin");
    if (merge && hallIds.Contains(at)) throw new Exception($"ID 0x{at:X} is already used by the hall's plugin");
    return new(mod.ModKey, at);
}
FormKey NewKey() => Key(next++);
// fixed ID blocks of their own, with a running cursor (KeyIn): a talk node with "ids": its topic and replies in that block of their own (64 IDs, a running cursor per block), so a node
// added to a voiced group moves no recorded line's ID (Cassius's regulars, 0x1E80). "backIds": the
// back choice to that node in the block (a back choice the new nodes brought in: here to CA3 and CA1).
var idCursor = new Dictionary<uint, uint>();
FormKey KeyIn(uint from)
{
    var at = idCursor.TryGetValue(from, out var c) ? c : from;
    if (at >= from + 0x40) throw new Exception($"the talk block 0x{from:X} is full");
    idCursor[from] = at + 1;
    return Key(at);
}
uint? BlockOf(JsonElement n) => n.TryGetProperty("ids", out var b) ? Convert.ToUInt32(b.GetString(), 16) : null;
// Records in a fixed stretch of IDs of their own (the second block), so whether they are built never moves another's ID
T InIds<T>(uint from, uint to, string what, Func<T> make)
{
    var keep = next;
    next = from;
    var made = make();
    if (next > to) throw new Exception($"{what} ran to 0x{next:X}, past their IDs' end at 0x{to:X}");
    next = keep;
    return made;
}

var edCache = new Dictionary<(Type, string), object>();
T Ed<T>(string editorId) where T : class, IMajorRecordGetter
{
    if (!edCache.TryGetValue((typeof(T), editorId), out var r))
        edCache[(typeof(T), editorId)] = r = winners.SelectMany(m => m.EnumerateMajorRecords<T>()).First(x => x.EditorID == editorId);
    return (T)r;
}
// NPCGEN_PROBE_PACKAGES=EdA,EdB prints those vanilla packages' inputs by index (a sandbox's 1 eating, 4 conversation,
// 5 idle markers, 6 sitting, 7 wandering, 31 special furniture) and stops: how a copied package was measured, 2026-11-07
if (Environment.GetEnvironmentVariable("NPCGEN_PROBE_PACKAGES") is { Length: > 0 } probe)
{
    foreach (var ed in probe.Split(','))
    {
        var pk = Ed<IPackageGetter>(ed);
        Console.WriteLine($"{ed}: template {pk.PackageTemplate.FormKey}");
        foreach (var (k, v) in pk.Data.OrderBy(x => x.Key))
            Console.WriteLine($"  {k,3}: {v switch { IPackageDataBoolGetter b => b.Data.ToString(), IPackageDataTargetGetter t => $"target {t.Target?.GetType().Name} {(t.Target as IPackageTargetSpecificReferenceGetter)?.Reference.FormKey}", IPackageDataFloatGetter f => f.Data.ToString(), IPackageDataLocationGetter l => $"location r{(l.Location as ILocationTargetRadiusGetter)?.Radius} {((l.Location as ILocationTargetRadiusGetter)?.Target)?.GetType().Name} {(((l.Location as ILocationTargetRadiusGetter)?.Target) as ILocationTargetGetter)?.Link.FormKey}{(((l.Location as ILocationTargetRadiusGetter)?.Target) as ILocationFallbackGetter)?.Type}", _ => v.GetType().Name }}");
    }
    return;
}
var npcsByKey = winners.SelectMany(m => m.Npcs).GroupBy(n => n.FormKey).Select(g => g.First()).ToList();

var rng = new Random(seed);
var recipes = new List<object>();

// vanilla NPCs whose face can be borrowed: unique, of this race and sex, with face sliders, tint layers and hair of
// their own (not templated)
// young (the clerks are young and lively; round 1 looked old): donors only from the
// race's character-creation presets and from women with young voices
var youngVoices = new HashSet<string> { "FemaleYoungEager", "FemaleSultry", "FemaleEvenToned" };
List<INpcGetter> Pool(string race, bool female, bool needBeard = false, bool young = false)
{
    var raceKey = Ed<IRaceGetter>(race).FormKey;
    return npcsByKey
        .Where(n => n.Race.FormKey == raceKey)
        .Where(n => n.Configuration.Flags.HasFlag(NpcConfiguration.Flag.Female) == female)
        .Where(n => n.Configuration.Flags.HasFlag(NpcConfiguration.Flag.Unique) && n.Template.IsNull)
        .Where(n => n.FaceMorph != null && n.FaceParts != null && n.TintLayers.Count > 0 && n.HeadParts.Count > 0)
        .Where(n => Has(n, HeadPart.TypeEnum.Hair) && (!needBeard || Has(n, HeadPart.TypeEnum.FacialHair)))
        .Where(n => !young || (n.EditorID ?? "").Contains("Preset") || (n.Voice.TryResolve(cache)?.EditorID is { } vt && youngVoices.Contains(vt)))
        .OrderBy(n => n.FormKey.ToString()).ToList();
}

bool Has(INpcGetter n, HeadPart.TypeEnum t) => Part(n, t) != null;
IHeadPartGetter? Part(INpcGetter n, HeadPart.TypeEnum t) =>
    n.HeadParts.Select(h => cache.TryResolve<IHeadPartGetter>(h.FormKey, out var p) ? p : null).FirstOrDefault(p => p?.Type == t);

// eyes and parts made for vampires, the Dremora, the blind or the undead: never on a guild clerk
var Odd = new System.Text.RegularExpressions.Regex("Demon|Vampire|Blind|Dremora|Draugr|Snow|Glow|Undead", System.Text.RegularExpressions.RegexOptions.IgnoreCase);
var pools = new Dictionary<(string, bool, bool, bool), List<INpcGetter>>();
float J(float v) => Math.Clamp(v + (float)(rng.NextDouble() * 0.16 - 0.08), -1f, 1f);

// Hair from Vanilla hair remake by jg1 (Nexus SE 63979; shipped with credit, its permissions checked),
// copied under meshes\AdventurersGuild\Hair so only our NPCs use it: the mod itself replaces vanilla's
// files in place, which would change every NPC in the game. Our head parts copy vanilla's records (race list, hairline
// extra part) with our model paths, and are NOT playable, so they never show in the player's RaceMenu list.
uint hairNext = 0x810;
// the talks' back choice from their top answer (so "Tell me about yourself" has a way back up): its own
// block after the board lines, 0x17C0-0x17FF, so no record made earlier moves
uint topNext = 0x17C0;
var ourHair = new Dictionary<string, HeadPart>();
HeadPart ShipHair(string vanillaEd, string newEd, string nif, string? tri, HeadPart? extra)
{
    var h = Ed<IHeadPartGetter>(vanillaEd).Duplicate(Key(hairNext++));
    h.EditorID = newEd;
    h.Model = new Model { File = $@"AdventurersGuild\Hair\{nif}" };
    h.Parts.Clear();
    if (tri != null) h.Parts.Add(new Mutagen.Bethesda.Skyrim.Part { PartType = Mutagen.Bethesda.Skyrim.Part.PartTypeEnum.Tri, FileName = $@"AdventurersGuild\Hair\{tri}" });
    h.ExtraParts.Clear();
    if (extra != null) h.ExtraParts.Add(extra.ToLink());
    h.Flags &= ~HeadPart.Flag.Playable;
    mod.HeadParts.Add(h);
    return ourHair[newEd] = h;
}
// the day clerk's: vanilla Nord 17 remade (side-swept, a braid coiled at the nape); the evening clerk's: Dark Elf 04
// remade (two buns, loose strands at the sides), with the hairline vanilla gives it (Dark Elf 03's)
ShipHair("HairFemaleNord17", "AGHairClerkBraidBun", "hair17.nif", "hair17.tri",
    ShipHair("HairLineFemaleNord17", "AGHairLineClerkBraidBun", "hairline17.nif", "hairline17.tri", null));
var twinBuns = ShipHair("HairFemaleDarkElf04", "AGHairClerkTwinBuns", "femaledarkelfhair04.nif", "femaledarkelfhair04.tri",
    ShipHair("HairLineFemaleDarkElf03", "AGHairLineClerkTwinBuns", "femaledarkelfhair03_hairline.nif", "femaledarkelfhair03_hairline.tri", null));
// an elf hair on a human head: rendered on the Imperial and Dunmer heads (FemaleHeadRaces.tri), it sits the same on both;
// the race list only filters RaceMenu's menus, and this record is ours, so it takes every race but the beast races
twinBuns.ValidRaces.SetTo(Ed<IFormListGetter>("HeadPartsAllRacesMinusBeast"));
foreach (var x in twinBuns.ExtraParts) ourHair.Values.First(h => h.FormKey == x.FormKey).ValidRaces.SetTo(Ed<IFormListGetter>("HeadPartsAllRacesMinusBeast"));

Npc Make(string editorId, string name, string race, bool female, string voice, string outfit, string package, bool beard, string? hairStyle = null, bool clean = false, bool young = false)
{
    var pool = pools.TryGetValue((race, female, beard, young), out var pl) ? pl : pools[(race, female, beard, young)] = Pool(race, female, beard, young);
    INpcGetter Pick() => pool[rng.Next(pool.Count)];
    var (shape, parts, skin, hair, eyes) = (Pick(), Pick(), Pick(), Pick(), Pick());
    var whiskers = beard ? Pick() : null;

    var npc = new Npc(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = editorId,
        Name = name,
        Race = Ed<IRaceGetter>(race).ToLink(),
        Voice = Ed<IVoiceTypeGetter>(voice).ToNullableLink(),
        Class = Ed<IClassGetter>("Citizen").ToLink(),
        DefaultOutfit = Ed<IOutfitGetter>(outfit).ToNullableLink(),
        Height = 1.0f,
        Weight = Math.Clamp(shape.Weight + rng.Next(-15, 16), 0, 100),
        HairColor = hair.HairColor.FormKeyNullable is { } hc ? new FormLinkNullable<IColorRecordGetter>(hc) : new FormLinkNullable<IColorRecordGetter>(),
        HeadTexture = skin.HeadTexture.FormKeyNullable is { } ht ? new FormLinkNullable<ITextureSetGetter>(ht) : new FormLinkNullable<ITextureSetGetter>(),
        TextureLighting = skin.TextureLighting,
        FaceParts = parts.FaceParts!.DeepCopy(),
        FaceMorph = shape.FaceMorph!.DeepCopy(),
    };
    var m = npc.FaceMorph;
    foreach (var p in typeof(NpcFaceMorph).GetProperties().Where(p => p.PropertyType == typeof(float) && p.Name != "Unknown"))
        p.SetValue(m, J((float)p.GetValue(m)!));
    npc.Configuration.Flags = NpcConfiguration.Flag.Unique | NpcConfiguration.Flag.Protected | NpcConfiguration.Flag.AutoCalcStats
        | (female ? NpcConfiguration.Flag.Female : 0);
    npc.Configuration.Level = new NpcLevel { Level = 10 };
    // a new NPC's speed multiplier is 0 unless set (vanilla's are 100): at 0 they could not walk (Marius stuck on a table,
    // Ghrulek standing still) and a +20 from elsewhere made Zhasim walk in slow motion (2026-11-06)
    npc.Configuration.SpeedMultiplier = 100;
    // clean (the hall's staff): no dirt and no war paint from the skin donor, and no rough complexion
    var raceRec = Ed<IRaceGetter>(race);
    var maskTypes = ((female ? raceRec.HeadData?.Female : raceRec.HeadData?.Male)?.TintMasks ?? new List<ITintAssetsGetter>())
        .Where(t => t.Index != null).GroupBy(t => (int)t.Index!).ToDictionary(g => g.Key, g => g.First().MaskType?.ToString() ?? "");
    // young: no wrinkle layers (laugh lines, forehead) and a lighter eyeliner
    string MaskType(ITintLayerGetter t) => t.Index is { } ti && maskTypes.TryGetValue(ti, out var mt) ? mt : "";
    var drop = new HashSet<string>(clean ? new[] { "Dirt", "Paint" } : Array.Empty<string>());
    if (young) { drop.Add("LaughLines"); drop.Add("Forehead"); }
    foreach (var t in skin.TintLayers.Where(t => !drop.Contains(MaskType(t))))
    {
        var c = t.DeepCopy();
        if (young && MaskType(t) == "Eyeliner" && c.InterpolationValue is { } iv) c.InterpolationValue = iv * 0.4f;
        npc.TintLayers.Add(c);
    }
    if ((clean || young) && skin.HeadTexture.TryResolve(cache) is { } hts && ((hts.EditorID ?? "").Contains("Rough") || (young && (hts.EditorID ?? "").Contains("Age"))))
        npc.HeadTexture.Clear();
    // head parts: the hair donor's hair, the eye donor's eyes, the shape-parts donor's brows, the beard donor's beard;
    // the face itself stays the race's default (which High Poly Head can swap)
    foreach (var (donor, type) in new[] { (hair, HeadPart.TypeEnum.Hair), (eyes, HeadPart.TypeEnum.Eyes), (parts, HeadPart.TypeEnum.Eyebrows), (whiskers, HeadPart.TypeEnum.FacialHair) })
        if (type == HeadPart.TypeEnum.Hair && hairStyle != null) npc.HeadParts.Add(ourHair.TryGetValue(hairStyle, out var oh) ? oh.ToLink() : Ed<IHeadPartGetter>(hairStyle).ToLink());
        else if (donor != null && Part(donor, type) is { } hp && !Odd.IsMatch(hp.EditorID ?? "")) npc.HeadParts.Add(hp.ToLink());
    npc.Packages.Add(Ed<IPackageGetter>(package).ToLink());
    npc.AIData.Confidence = Confidence.Average;
    npc.AIData.Responsibility = Responsibility.NoCrime;
    mod.Npcs.Add(npc);
    recipes.Add(new
    {
        editorId, formId = $"{npc.FormKey.ID:X6}", name, race, female, voice,
        shape = shape.EditorID, parts = parts.EditorID, skin = skin.EditorID, hair = hair.EditorID, eyes = eyes.EditorID, beard = whiskers?.EditorID,
        headParts = npc.HeadParts.Select(h => ourHair.Values.FirstOrDefault(x => x.FormKey == h.FormKey)?.EditorID ?? cache.Resolve<IHeadPartGetter>(h.FormKey).EditorID).ToList(),
    });
    return npc;
}

// The clerks: both women, one FemaleCommoner, one FemaleYoungEager, their hair two styles chosen from Vanilla hair
// remake (only that mod's hair), matched to its files by rendering them.
// the day clerk, standing behind the guild services counter, facing the public side (hall -x = cell -y). hall2t: the
// counter at hall x 832..882 from the front wall to the pen's wall at y 570; she stands in the pen at hall (945, 250), the evening clerk at (945, 460).
// Hall (x, y) is cell (-y, x). (hall2s had the counter at 764..814; placed for that, she stood inside hall2t's counter.)
// Audition (env AUDITION="<prefix>:<race>:<voice>:<hair head part>:<count>;..."): only clean candidates, none placed,
// written to <out dir>/audition/AGNpcSpike.esp + recipes.json for facedata and render_face.py; the spike plugin is untouched.
if (Environment.GetEnvironmentVariable("AUDITION") is { Length: > 0 } aud)
{
    next = 0x900;   // clear of the hair records at 0x810..
    foreach (var spec in aud.Split(';'))
    {
        var f = spec.Split(':');
        for (int i = 1; i <= int.Parse(f[4]); i++)
            Make($"AGAud{f[0]}{i:00}", $"{f[0]} {i}", f[1], true, f[2], "FineClothesOutfit01", "DefaultStayAtCurrentLocationSkipFallout", false, f[3], clean: true, young: f.Length > 5 && f[5] == "young");
    }
    var audDir = Path.Combine(outDir, "audition"); Directory.CreateDirectory(audDir);
    mod.ModHeader.Stats.NextFormID = Math.Max(next, hairNext);
    mod.WriteToBinary(Path.Combine(audDir, "AGNpcSpike.esp"), new BinaryWriteParameters { ModKey = ModKeyOption.CorrectToPath, MastersListContent = MastersListContentOption.Iterate, MastersListOrdering = new MastersListOrderingByLoadOrder(all.Select(x => x.ModKey).ToList()) });
    File.WriteAllText(Path.Combine(audDir, "recipes.json"), JsonSerializer.Serialize(new { seed, recipes }, new JsonSerializerOptions { WriteIndented = true }));
    Console.WriteLine($"wrote {audDir}: {mod.Npcs.Count} candidates; young pools: " + string.Join(", ", pools.Where(kv => kv.Key.Item4).Select(kv => $"{kv.Key.Item1} {kv.Value.Count}")));
    return;
}

// A face cloned from a vanilla NPC (three rounds of generated faces fell short; vanilla records are free to reuse and
// rebuild exactly at run time): the donor's race, sliders, feature
// types, complexion, weight, eyes and brows; our remake hair in its own colour; the donor's tint without dirt or paint.
ColorRecord HairColour(string ed, int r, int g, int b)
{
    var c = new ColorRecord(Key(hairNext++), SkyrimRelease.SkyrimSE) { EditorID = ed, Color = System.Drawing.Color.FromArgb(r, g, b) };
    mod.Colors.Add(c); return c;
}
// hairEd/hairColour null: the donor's own hair and colour (vanilla's records, so a player's hair replacer applies to them).
// The donor's beard and scars come along (the clerks' donors have neither).
void Clone(Npc npc, string donorEd, string? hairEd, ColorRecord? hairColour)
{
    var d = npcsByKey.First(n => n.EditorID == donorEd);
    var race = cache.Resolve<IRaceGetter>(d.Race.FormKey);
    var female = d.Configuration.Flags.HasFlag(NpcConfiguration.Flag.Female);
    var types = ((female ? race.HeadData?.Female : race.HeadData?.Male)?.TintMasks ?? new List<ITintAssetsGetter>()).Where(t => t.Index != null)
        .GroupBy(t => (int)t.Index!).ToDictionary(g => g.Key, g => g.First().MaskType?.ToString() ?? "");
    npc.Race.SetTo(d.Race.FormKey);
    npc.FaceMorph = d.FaceMorph?.DeepCopy();
    npc.FaceParts = d.FaceParts?.DeepCopy();
    npc.TextureLighting = d.TextureLighting;
    npc.HeadTexture.SetTo(d.HeadTexture.FormKeyNullable);
    npc.Weight = d.Weight;
    npc.TintLayers.Clear();
    // no war paint (Muiri's teal eye sockets and blue eyeliner count as war paint too)
    var paint = new HashSet<string> { "Dirt", "Paint", "EyeSocketUpper", "EyeSocketLower", "Eyeliner" };
    // except on beast races: a Khajiit's or Argonian's "Paint" layers are its fur stripes and scale patterns
    // (KhajiitStripes*.dds) and its eye markings are part of the face; stripping them turned Ma'jhad's black fur grey
    if (race.EditorID is { } re && (re.Contains("Khajiit") || re.Contains("Argonian"))) paint.Clear();
    npc.TintLayers.AddRange(d.TintLayers.Where(t => !(t.Index is { } i && types.TryGetValue(i, out var mt) && paint.Contains(mt))).Select(t => t.DeepCopy()));
    // some vanilla NPCs (Mena) carry their skin colour only in QNAM, with no SkinTone layer: the CK's bake falls back to
    // it, a face built at run time might not. Give the clone the layer explicitly.
    if (!npc.TintLayers.Any(t => t.Index is { } i && types.TryGetValue(i, out var mt) && mt == "SkinTone") && d.TextureLighting is { } q
        && types.FirstOrDefault(kv => kv.Value == "SkinTone") is { Value: "SkinTone" } st)
        npc.TintLayers.Insert(0, new TintLayer { Index = (ushort)st.Key, Color = q, InterpolationValue = 1.0f, Preset = -1 });
    npc.HeadParts.Clear();
    // our own hair (ourHair), or a vanilla one by its editor ID (Willem gets HairMaleElder6; Jod's
    // HairMaleRedguard2 showed patches on MGO, where High Poly Head replaces that mesh)
    if (hairEd != null) npc.HeadParts.Add(ourHair.TryGetValue(hairEd, out var ownHair) ? ownHair.ToLink()
        : Ed<IHeadPartGetter>(hairEd).ToLink());
    foreach (var hp in d.HeadParts.Select(h => cache.Resolve<IHeadPartGetter>(h.FormKey)).Where(h => h.Type is HeadPart.TypeEnum.Eyes
        or HeadPart.TypeEnum.Eyebrows or HeadPart.TypeEnum.FacialHair or HeadPart.TypeEnum.Scars
        // with the donor's own hair, its Misc parts too: some list the hairline separately (the Altmer preset's
        // HairLineMaleDarkElf01; without it the noble's slicked hair rendered as a flat cap)
        || (hairEd == null && h.Type is HeadPart.TypeEnum.Hair or HeadPart.TypeEnum.Misc)))
        npc.HeadParts.Add(hp.ToLink());
    // The race's default mouth is a Misc part too. Only vanilla's chargen presets name a Misc part of their own (no NPC
    // does), so whether the engine still adds the default mouth then is unproven: name it explicitly.
    if (npc.HeadParts.Any(h => (mod.HeadParts.TryGetValue(h.FormKey, out var own) ? own.Type : cache.Resolve<IHeadPartGetter>(h.FormKey).Type) == HeadPart.TypeEnum.Misc))
        foreach (var dp in ((female ? race.HeadData?.Female : race.HeadData?.Male)?.HeadParts ?? new List<IHeadPartReferenceGetter>())
            .Select(r => cache.Resolve<IHeadPartGetter>(r.Head.FormKey)).Where(h => h.Type == HeadPart.TypeEnum.Misc))
            if (!npc.HeadParts.Any(h => h.FormKey == dp.FormKey)) npc.HeadParts.Add(dp.ToLink());
    if (hairColour != null) npc.HairColor.SetTo(hairColour); else npc.HairColor.SetTo(d.HairColor.FormKeyNullable);
    recipes.Add(new { editorId = npc.EditorID, clonedFrom = donorEd, race = race.EditorID, hair = hairEd ?? "donor's", hairColour = hairColour?.EditorID ?? "donor's" });
}
// hair colours from two reference pictures: copper-blonde (braided bun), auburn (twin buns)
var copper = HairColour("AGHairColourCopper", 158, 94, 51);
var auburn = HairColour("AGHairColourAuburn", 115, 43, 20);

// The clerks' hair from KS Hairdos SSE by Kalilies and Stealthic (Nexus SE 6817: free for NPC mods with credit and a link),
// chosen after the remake's styles: Sky275 (two loose braids) for the day clerk, Aftershock (low
// twin buns) for the evening clerk. Under meshes\ and textures\AdventurersGuild\Hair\KS, the meshes' texture paths
// rewritten by retexture_nif.py. Records built the way KS builds them (hair plus its hairline and its "HL" second pass as
// extra parts), from vanilla's records for everything KS leaves at the defaults. The remake's records above stay, unused.
HeadPart KsPart(string templateEd, string newEd, string nif, string tri, string races, params HeadPart[] extras)
{
    var h = ShipHair(templateEd, newEd, $@"KS\{nif}", $@"KS\{tri}", null);
    foreach (var x in extras) h.ExtraParts.Add(x.ToLink());
    h.ValidRaces.SetTo(Ed<IFormListGetter>(races));
    return h;
}
var ksHairline = KsPart("HairLineFemaleNord17", "AGHairLineKSStraightHuman", @"hairline\straightscalpHUMAN.nif", @"hairline\straightscalpHUMAN.tri", "HeadPartsHumansandVampires");
KsPart("HairFemaleNord17", "AGHairClerkTwinBraids", "Sky275.nif", "Sky275.tri", "HeadPartsAllRacesMinusBeast", ksHairline,
    KsPart("HairLineFemaleNord17", "AGHairClerkTwinBraidsHL", "Sky275Hl.nif", "Sky275.tri", "HeadPartsAllRacesMinusBeast"));
KsPart("HairFemaleNord17", "AGHairClerkLowBuns", "Aftershock.nif", "Aftershock.tri", "HeadPartsHumansOrcsandVampires",
    KsPart("HairLineFemaleNord17", "AGHairClerkLowBunsHL", "AftershockHl.nif", "Aftershock.tri", "HeadPartsHumansOrcsandVampires"));

// (dressed as the inns' counter keepers, and not alike: Margot as most of them, Nessa as Hulda)
var clerk = Make("AGHallClerkDay", "Margot Belleau", "ImperialRace", true, "FemaleCommoner", "BarkeepClothes01", "DefaultStayAtEditorLocation", false, "AGHairClerkBraidBun", clean: true);
// colours swapped: the day clerk takes the auburn (it rendered red, the look wanted for her), the
// evening clerk a browner auburn (option C of six rendered); copper is no longer worn
var auburnBrown = HairColour("AGHairColourAuburnBrown", 80, 48, 34);
Clone(clerk, "Muiri", "AGHairClerkTwinBraids", auburn);
// ... but on the KS braids' light texture the auburn came out bright orange in game, not vanilla's red: the closest
// vanilla colour for a red head instead, vanilla's own HairColor06Auburn, the one Aela, Ysolda and Hulda wear. The auburn record stays (its ID reserved), unworn.
clerk.HairColor.SetTo(Ed<IColorRecordGetter>("HairColor06Auburn").FormKey);
// the hall's interior cell (0x908, whatever the hall's plugin is called): merged, the hall's own record; the spike, a copy
var cellCtx = cache.ResolveContext<ICell, ICellGetter>(new FormKey(hall.ModKey, 0x908));
var cell = merge ? mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).First(c => c.FormKey == cellCtx.Record.FormKey)
    : cellCtx.GetOrAddAsOverride(mod);
// the hall is all of its interior cells (the basement and the strongroom are cells of their own but still part of the
// guild hall): a check that someone is "in the hall" is one GetInCell per cell,
// ORed (2026-11-03: Nessa's archery in the basement left her with no line at all, so a click did nothing)
var hallCells = hall.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells)
    .Where(c => c.FormKey.ModKey == hall.ModKey && c.Flags.HasFlag(Cell.Flag.IsInteriorCell)).Select(c => c.FormKey).ToList();
if (!hallCells.Contains(cellCtx.Record.FormKey)) throw new Exception("the hall's main cell is not among its interior cells");
Console.WriteLine($"hall cells: {string.Join(", ", hall.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).Where(c => hallCells.Contains(c.FormKey)).Select(c => c.EditorID))}");
// in any of the hall's cells: the subject (no reference) or a named reference; the OR group ends at the last cell, so it
// must be the last of an OR group, never followed by more ORed conditions
Condition[] InHallCells(FormKey? reference = null) => hallCells.Select((k, i) =>
{
    var d = new GetInCellConditionData();
    if (reference is { } r) { d.RunOnType = Condition.RunOnType.Reference; d.Reference.SetTo(r); }
    d.Cell.Link.SetTo(k);
    return (Condition)new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = d,
        Flags = i < hallCells.Count - 1 ? Condition.Flag.OR : 0 };
}).ToArray();
// in none of them: one GetInCell == 0 per cell, ANDed
Condition[] OutOfHall(FormKey reference) => hallCells.Select(k =>
{
    var d = new GetInCellConditionData { RunOnType = Condition.RunOnType.Reference };
    d.Reference.SetTo(reference); d.Cell.Link.SetTo(k);
    return (Condition)new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 0, Data = d };
}).ToArray();
// Staff spots come from markers the hall session places and moves with its counters (tools/HallSpike/COORDINATION.md:
// the hall plugin owns where staff stand, this plugin owns who stands there). Until a marker exists, the last spot
// agreed by hand is used, and the build says so.
// the hall's named references, by editor ID; two with one name is the hall build's mistake, and the merge says which
// (2026-10-27: a retired board ref kept the live activator's name, and ToDictionary only said "same key")
Dictionary<string, IPlacedObjectGetter> ByName(ICellGetter c)
{
    var named = c.Persistent.Concat(c.Temporary).OfType<IPlacedObjectGetter>().Where(r => r.EditorID != null).ToList();
    var dup = named.GroupBy(r => r.EditorID!).Where(g => g.Count() > 1)
        .Select(g => $"{g.Key} ({string.Join(", ", g.Select(r => $"0x{r.FormKey.ID:X}"))})").ToList();
    if (dup.Count > 0) throw new Exception($"the hall's cell has references sharing an editor ID: {string.Join("; ", dup)}");
    return named.ToDictionary(r => r.EditorID!, r => r);
}
var hallMarkers = ByName(cellCtx.Record);
Placement Spot(string marker, P3Float fallback)
{
    if (hallMarkers.TryGetValue(marker, out var m) && m.Placement is { } at)
    {
        Console.WriteLine($"spot {marker}: from the hall plugin, {at.Position}");
        return new Placement { Position = at.Position, Rotation = at.Rotation };
    }
    Console.WriteLine($"WARNING spot {marker}: not in the hall plugin yet; using the hand-placed {fallback}");
    return new Placement { Position = fallback, Rotation = new(0, 0, MathF.PI) };
}
cell.Persistent.Add(new PlacedNpc(NewKey(), SkyrimRelease.SkyrimSE)
{
    EditorID = "AGHallClerkDayRef",
    Base = clerk.ToNullableLink(),
    Placement = Spot("AGHallClerkDayMarker", new(-250, 945, 0)),
});

// the audition: ten more Imperial women for the clerk, and two bearded middle-aged Nord men (the Guild Master's kind, and
// a test of High Poly Head's beard twins). Spawned by hand: player.placeatme <id>.
for (int i = 1; i <= 10; i++)
    Make($"AGHallFaceCandidate{i:00}", $"Candidate {i}", "ImperialRace", true, "FemaleCommoner", "FineClothesOutfit01", "DefaultStayAtCurrentLocationSkipFallout", false);
for (int i = 11; i <= 12; i++)
    Make($"AGHallFaceCandidate{i:00}", $"Candidate {i}", "NordRace", false, "MaleNord", "FineClothesOutfit02", "DefaultStayAtCurrentLocationSkipFallout", true);

// the evening clerk (after the audition so every earlier ID stays put): a young Breton, in the elf twin buns, at the pen's other end
var evening = Make("AGHallClerkEvening", "Nessa", "BretonRace", true, "FemaleYoungEager", "FarmClothesOutfit02", "DefaultStayAtEditorLocation", false, "AGHairClerkTwinBuns", clean: true);
Clone(evening, "Mena", "AGHairClerkLowBuns", auburnBrown);
cell.Persistent.Add(new PlacedNpc(NewKey(), SkyrimRelease.SkyrimSE)
{
    EditorID = "AGHallClerkEveningRef",
    Base = evening.ToNullableLink(),
    Placement = Spot("AGHallClerkEveMarker", new(-460, 945, 0)),
});

// The rest of the staff (chosen from the vanilla face galleries): each a clone of a vanilla face with
// that NPC's race, placed where the hall session puts its marker; with no marker yet the NPC exists but is not placed
// (COORDINATION.md: the hall plugin owns where staff stand). Names are the roles until named. IDs from 0x830,
// clear of the hair records from 0x810.
// The waitress's hair, from the tied-back KS styles: Chignon (bun at the crown, short fringe).
// After every other hair record, so their IDs stay put.
KsPart("HairFemaleNord17", "AGHairServerChignon", "Chignon.nif", "Chignon.tri", "HeadPartsAllRacesMinusBeast",
    KsPart("HairLineFemaleNord17", "AGHairServerChignonHL", "ChignonHl.nif", "Chignon.tri", "HeadPartsAllRacesMinusBeast"));
next = 0x830;
var placed = 2;
Npc Staff(string ed, string name, string donor, bool female, string voice, string outfit, string marker, string? hair = null, ColorRecord? colour = null, (short Preset, System.Drawing.Color Rgb, float Value)? lips = null)
{
    var d = npcsByKey.First(n => n.EditorID == donor);
    var npc = Make(ed, name, cache.Resolve<IRaceGetter>(d.Race.FormKey).EditorID!, female, voice, outfit, "DefaultStayAtEditorLocation", false, clean: true);
    Clone(npc, donor, hair, colour);
    if (lips is var (preset, rgb, value))
    {
        var masks = (female ? cache.Resolve<IRaceGetter>(d.Race.FormKey).HeadData?.Female : cache.Resolve<IRaceGetter>(d.Race.FormKey).HeadData?.Male)?.TintMasks;
        var lip = masks?.FirstOrDefault(t => t.MaskType == TintAssets.TintMaskType.LipColor)?.Index;
        npc.TintLayers.RemoveAll(t => t.Index == lip);
        npc.TintLayers.Add(new TintLayer { Index = lip, Color = rgb, InterpolationValue = value, Preset = preset });
    }
    // the reference's ID is reserved whether or not the marker exists yet, so no NPC's ID depends on which markers the hall
    // has placed (2026-10-27: the residents' markers arriving shifted every later resident's ID by one)
    var refKey = NewKey();
    if (hallMarkers.TryGetValue(marker, out var m) && m.Placement is { } at)
    {
        Console.WriteLine($"spot {marker}: from the hall plugin, {at.Position}");
        cell.Persistent.Add(new PlacedNpc(refKey, SkyrimRelease.SkyrimSE) { EditorID = ed + "Ref", Base = npc.ToNullableLink(), Placement = new Placement { Position = at.Position, Rotation = at.Rotation } });
        placed++;
    }
    else Console.WriteLine($"NOT PLACED {ed}: no {marker} in the hall plugin yet");
    return npc;
}
// voices: the Guild Master's is a placeholder until a voice type of his own exists
Staff("AGHallGuildMaster", "Willem", "Jod", false, "MaleCommander", "FineClothesOutfit02", "AGHallGuildMasterMarker", "HairMaleElder6");
Staff("AGHallAssistant", "Merila Andalen", "DLC2RRDreylaAlor", true, "FemaleDarkElf", "FineClothesOutfit01Variant", "AGHallAssistantMarker");
// the barkeeper is Imperial (his donor's race): MaleEvenToned, as vanilla's Imperial innkeeper Corpulus Vinius and the donor
Staff("AGHallBarkeeper", "Cassius Varro", "TG04EECDockmaster", false, "MaleEvenToned", "BarkeepClothes02", "AGHallBarLeanMarker");
// "Old Henriette" to everyone, as vanilla's Nana Ildene; her own name is Henriette (the short name dialogue uses)
// Henriette: Hafjorg's face (ElderRace, vanilla's way for an old woman; Ildene's Breton Age50 face, the oldest a Breton
// gets, looked far too young for her old voice)
Staff("AGHallCook", "Old Henriette", "Hafjorg", true, "FemaleOldKindly", "ChefOutfit", "AGHallCookMarker").ShortName = "Henriette";
Staff("AGHallServer", "Brynja", "IdgrodTheYounger", true, "FemaleSultry", "ClothesTavernWenchOutfit", "AGHallServerMarker", "AGHairServerChignon",
    // Idgrod's dark bluish lips warmed, the rest of her face kept: the Nord women's RedTintLight preset
    lips: (656, System.Drawing.Color.FromArgb(169, 84, 82), 0.38f));

// The resident adventurers (chosen from the face galleries), with the design page's voices. Names are
// their roles until named; placed once the hall session gives each a marker where they live.
Staff("AGHallResidentOrc", "Ghrulek", "Ghorbash", false, "MaleOrc", "ArmorOrcStrongholdNoHelmetOutfit", "AGHallResidentOrcMarker");
Staff("AGHallResidentRanger", "Ylva", "Threki", true, "FemaleCommander", "DA05HunterOutfit2", "AGHallResidentRangerMarker");
Staff("AGHallResidentScout", "Zhasim", "Majhad", false, "MaleKhajiit", "ArmorLeatherNoHelmetOutfit", "AGHallResidentScoutMarker");   // (with gauntlets)
Staff("AGHallResidentVeteran", "Marius Crassus", "SailorXander", false, "MaleOldGrumpy", "MerchantClothesOutfit01NoHat", "AGHallResidentVeteranMarker");
// (after the veteran, so the earlier IDs stay put) the fifth resident, the arrogant rival: the noble's son with a bought rank who sneers at
// commoners. An Altmer character-creation preset (no one's face in the game), gilded Elven armour, the haughty elf voice.
Staff("AGHallResidentNoble", "Caralion of Cloudrest", "HighElfMalePreset03", false, "MaleElfHaughty", "ArmorElvenGildedNoHelmetOutfit", "AGHallResidentNobleMarker");

// Factions and ownership (the Guild, like Jorrvaskr). Vanilla's Jorrvaskr, measured: CompanionsFaction
// owns the cells and is its people's crime faction (TrackCrime, DoNotReportCrimesAgainstMembers); the Harbinger's rooms
// belong to CompanionsHarbingerFaction; senior members' beds and chests are owned by name, the members' bunks by the faction.
// The hall's factions are the hall plugin's records; their flags and the cells' owners are set there.
Npc Hall(string ed) => mod.Npcs.First(n => n.EditorID == ed);
var hallFolk = new[] { "AGHallClerkDay", "AGHallClerkEvening", "AGHallGuildMaster", "AGHallAssistant", "AGHallBarkeeper", "AGHallCook", "AGHallServer",
    "AGHallResidentOrc", "AGHallResidentRanger", "AGHallResidentScout", "AGHallResidentVeteran", "AGHallResidentNoble" }.Select(Hall).ToList();
IFactionGetter? HallFaction(string ed) => hall.Factions.FirstOrDefault(f => f.EditorID == ed);
var guildFaction = HallFaction("AGHall2GuildFaction") ?? throw new Exception("the hall plugin has no AGHall2GuildFaction");
var gmFaction = HallFaction("AGHall2GuildMasterFaction");
if (gmFaction is null) Console.WriteLine("WARNING AGHall2GuildMasterFaction: not in the hall plugin yet; Willem is not given his quarters' faction");
void Join(Npc n, FormKey f, int rank = 0) => n.Factions.Add(new RankPlacement { Faction = f.ToLink<IFactionGetter>(), Rank = (sbyte)rank });
foreach (var n in hallFolk)
{
    Join(n, guildFaction.FormKey);
    n.CrimeFaction.SetTo(guildFaction.FormKey);
    // the staff are civilians who flee; the fighters (below) stand
    n.AIData.Aggression = Aggression.Unaggressive; n.AIData.Confidence = Confidence.Cowardly;
    n.AIData.Responsibility = Responsibility.NoCrime; n.AIData.Assistance = Assistance.HelpsAllies;
}
if (gmFaction is not null) Join(Hall("AGHallGuildMaster"), gmFaction.FormKey);
// Willem and his assistant Merila each carry the Guild Hall Key (the hall's KEYM: the upstairs display case, locked at
// Expert, and the strongroom, at Adept). An inventory item, as vanilla's keyholders carry theirs,
// so it can be pickpocketed or looted.
var hallKey = hall.Keys.FirstOrDefault(k => k.EditorID == "AGHall2DisplayCaseKey");
if (hallKey is null) Console.WriteLine("WARNING AGHall2DisplayCaseKey: not in the hall plugin yet; Willem and Merila carry no Guild Hall Key");
else
    foreach (var ed in new[] { "AGHallGuildMaster", "AGHallAssistant" })
    {
        var n = Hall(ed);
        n.Items ??= new();
        n.Items.Add(new ContainerEntry { Item = new ContainerItem { Item = hallKey.ToLink<IItemGetter>(), Count = 1 } });
    }
// (the Back Office Key is gone: the counter's back office door is unlocked, after Uthgerd walked
// through it locked; the hall's commit 94f1d4a removed the record)
// the weapon Willem's practice uses (schedules.json's train): vanilla's practice package draws the trainee's
// own weapon, so he carries a steel sword. An archer is handed her bow by the practice itself (Make1's archery: the
// bow is for practice only, so Nessa's never shows at the counter).
var willem = Hall("AGHallGuildMaster");
willem.Items ??= new();
willem.Items.Add(new ContainerEntry { Item = new ContainerItem { Item = Ed<IWeaponGetter>("SteelSword").ToLink<IItemGetter>(), Count = 1 } });
// Willem and both clerks essential (the counter must keep working), everyone else protected (Make's default)
foreach (var ed in new[] { "AGHallGuildMaster", "AGHallClerkDay", "AGHallClerkEvening" })
{
    var n = Hall(ed);
    n.Configuration.Flags = (n.Configuration.Flags & ~NpcConfiguration.Flag.Protected) | NpcConfiguration.Flag.Essential;
}
// fighters: the residents, the Guild Master and the old sergeant; Caralion has the training and not the nerve
foreach (var (ed, cls, brave) in new[] { ("AGHallGuildMaster", "CombatWarrior1H", true), ("AGHallResidentOrc", "CombatWarrior2H", true),
    ("AGHallResidentRanger", "CombatRanger", true), ("AGHallResidentScout", "CombatScout", true), ("AGHallResidentVeteran", "CombatWarrior1H", true),
    ("AGHallResidentNoble", "CombatSpellsword", false) })
{
    var n = Hall(ed);
    n.Class.SetTo(Ed<IClassGetter>(cls).FormKey);
    if (brave) { n.AIData.Confidence = Confidence.Brave; n.AIData.Assistance = Assistance.HelpsFriendsAndAllies; }
}
// The followers' weapons (added after Zhasim was recruited bare-handed: their outfits are armour
// only). Ghrulek an Orcish Battleaxe (his stronghold's make, his bio's axe); Ylva an Elven bow, arrows and a steel dagger
// (a B-rank's bow), and a hunter's supplies (potions, food and the like); Zhasim two steel
// daggers, with vanilla's Thieves Guild combat style (csTGStandard), one that allows dual wielding, or he would fight
// with one. Caralion an Elven sword and, below, two spells, as vanilla's spellswords fight. Their helmets are not here:
// AGHallFollowerTIF puts one on when they are recruited and takes it off when dismissed (bareheaded in the hall, as the
// outfits and Ghrulek's bio have it). Items on their records only: no record of their own, so no ID moves.
foreach (var (ed, gear) in new[] {
    ("AGHallResidentOrc", new[] { ("OrcishBattleaxe", 1) }),
    ("AGHallResidentRanger", new[] { ("ElvenBow", 1), ("ElvenArrow", 30), ("SteelDagger", 1),
        ("RestoreHealth02", 3), ("RestoreStamina02", 2), ("CureDisease", 1), ("FoodVenisonCooked", 2), ("FoodRabbitCooked", 2), ("FoodApple", 2) }),
    ("AGHallResidentScout", new[] { ("SteelDagger", 2) }),
    ("AGHallResidentNoble", new[] { ("ElvenSword", 1) }) })
{
    var n = Hall(ed);
    n.Items ??= new();
    foreach (var (item, count) in gear)
        n.Items.Add(new ContainerEntry { Item = new ContainerItem { Item = Ed<IItemGetter>(item).ToLink<IItemGetter>(), Count = count } });
}
Hall("AGHallResidentScout").CombatStyle.SetTo(Ed<ICombatStyleGetter>("csTGStandard").FormKey);
{   // Caralion's spells: an apprentice's destruction and healing, the NPC (left-hand) versions vanilla's spellswords carry
    var caralion = Hall("AGHallResidentNoble");
    caralion.ActorEffect ??= new();
    foreach (var sp in new[] { "FireboltLeftHand", "FastHealingLeftHand" })
        caralion.ActorEffect.Add(Ed<ISpellGetter>(sp).ToLink<ISpellRecordGetter>());
}
// The tavern: Cassius and Brynja sell food and drink as servers, as Saadia does at the Bannered Mare (JobMerchantFaction -1,
// JobInnServer 0 and the inn's services faction, a vendor faction with a merchant chest and the innkeeper's list). Not
// JobInnkeeperFaction: AG's generic innkeeper line ("You won't find one out here") would fire inside the Guild's own hall.
var merchantChest = (Container)Ed<IContainerGetter>("MerchantWhiterunBannerdMareChest").Duplicate(NewKey());
merchantChest.EditorID = "AGHallMerchantChest";
mod.Containers.Add(merchantChest);
var merchantChestRef = new PlacedObject(NewKey(), SkyrimRelease.SkyrimSE)
{
    // out of sight under the hall's floor, as merchant chests are kept out of reach
    EditorID = "AGHallMerchantChestRef", Base = merchantChest.ToNullableLink(),
    Placement = new Placement { Position = new P3Float(0, 0, -2000), Rotation = new P3Float(0, 0, 0) },
};
cell.Persistent.Add(merchantChestRef);
var services = new Faction(NewKey(), SkyrimRelease.SkyrimSE)
{
    EditorID = "AGHallServicesFaction", Name = "Guild Hall Services",
    Flags = Faction.FactionFlag.Vendor | Faction.FactionFlag.CanBeOwner | Faction.FactionFlag.HiddenFromPC,
    MerchantContainer = merchantChestRef.ToNullableLink(),
    VendorBuySellList = Ed<IFormListGetter>("VendorItemsInnkeeper").ToNullableLink(),
    // open from her shift's start (breakfast from 6) until she goes to bed at 21: she stays in the
    // tavern through her supper and evening, and a closed shop there read as broken. Cassius has his own, below
    VendorValues = new VendorValues { StartHour = 6, EndHour = 21 },
    // the shop is the whole hall, as the Bannered Mare's services are: every vanilla vendor faction names a location, and
    // without one the engine never counts its vendor as offering services (no "What have you got for sale?")
    VendorLocation = new LocationTargetRadius { Target = new LocationCell { Link = new FormLink<ICellGetter>(cellCtx.Record.FormKey) } },
};
mod.Factions.Add(services);
foreach (var ed in new[] { "AGHallBarkeeper", "AGHallServer" })
{
    var n = Hall(ed);
    Join(n, Ed<IFactionGetter>("JobMerchantFaction").FormKey, -1);
    Join(n, Ed<IFactionGetter>("JobInnServer").FormKey);
    Join(n, services.FormKey);
}
// Followers: the three good-natured residents who still take contracts. Vanilla's "Follow me. I need your help." asks for
// PotentialFollowerFaction, a relationship rank of 1 or more with the player and a follower voice (MaleOrc, FemaleCommander
// and MaleKhajiit all are); the relationship is a record, as custom followers do it. Marius is retired; Caralion is not nice.
var player = new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x7);
foreach (var ed in new[] { "AGHallResidentOrc", "AGHallResidentRanger", "AGHallResidentScout" })
{
    var n = Hall(ed);
    Join(n, Ed<IFactionGetter>("PotentialFollowerFaction").FormKey);
    Join(n, Ed<IFactionGetter>("CurrentFollowerFaction").FormKey, -1);
    mod.Relationships.Add(new Relationship(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = ed + "PlayerRel", Parent = n.FormKey.ToLink<INpcGetter>(), Child = player.ToLink<INpcGetter>(), Rank = Relationship.RankType.Friend,
    });
}
// Marriageable (Margot, Nessa, Brynja and Ylva; plans/vanilla-follower-marriage-lines.md):
// vanilla's marriage lines ask for PotentialMarriageFaction, the NPC's marriage voice list (the DLL joins theirs) and, to
// propose, a relationship rank of 1 or more. Ylva has hers as a follower; Margot, Nessa and Brynja reach it later, each by
// a quest or favor of her own. No record of its own, so no ID moves.
foreach (var ed in new[] { "AGHallClerkDay", "AGHallClerkEvening", "AGHallServer", "AGHallResidentRanger" })
    Join(Hall(ed), Ed<IFactionGetter>("PotentialMarriageFaction").FormKey);
// Room 5, the hall's best room: its own faction rather than Caralion by name (so the player can
// take it over from him), as the Guild Master's quarters are the Guild Master faction's. Caralion is its one member;
// handing the room over later (a quest, or a high enough rank and something "unfortunate" happening to him: undecided)
// is adding the player to it. After every other record, so no earlier ID moves.
var room5 = new Faction(NewKey(), SkyrimRelease.SkyrimSE)
{
    EditorID = "AGHallRoom5Faction", Name = "Guild Hall's Best Room", Flags = Faction.FactionFlag.CanBeOwner | Faction.FactionFlag.HiddenFromPC,
};
mod.Factions.Add(room5);
Join(Hall("AGHallResidentNoble"), room5.FormKey);
// Beds and their chests, owned by name; the hall session names them (AGHallBed*, AGHallBunk*, AGHallChest*) and owns the
// rest. An override of a hall reference, refreshed from the deployed hall on every build, as the cell header is.
// the named beds and chests of every hall cell (2026-11-06: Henriette's AGHallBedRoom6 and chest stand in the basement, and a
// main-cell-only lookup left them unowned); a name in two cells stops the build, as a name twice in one cell does
var hallRefs = ByName(cellCtx.Record);
foreach (var c in hall.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells)
             .Where(c => hallCells.Contains(c.FormKey) && c.FormKey != cellCtx.Record.FormKey))
    foreach (var (name, r) in ByName(c))
        if (!hallRefs.TryAdd(name, r))
            throw new Exception($"the hall's cells share an editor ID: {name} (0x{hallRefs[name].FormKey.ID:X}, 0x{r.FormKey.ID:X})");
// (Willem's bed and furniture are the Guild Master faction's, set by the hall, so that a player who
// one day becomes Guild Master inherits them, as a new Harbinger inherits Kodlak's)
var beds = new List<(string Bed, string Owner)> {
    ("Bunk1", "AGHallResidentOrc"), ("Bunk2", "AGHallResidentRanger"), ("Bunk3", "AGHallResidentScout"), ("Bunk4", "AGHallResidentVeteran"),
    ("Bunk5", "AGHallBarkeeper") };
// the staff rooms: the clerks share the room the hall session gives two beds (its second bed named ...b); the others one
// each, in room order: Merila, Henriette, Brynja
var clerksRoom = new[] { "3", "4", "6", "7" }.FirstOrDefault(r => hallRefs.ContainsKey($"AGHallBedRoom{r}b"));
if (clerksRoom is not null)
{
    beds.Add(($"BedRoom{clerksRoom}", "AGHallClerkDay"));
    beds.Add(($"BedRoom{clerksRoom}b", "AGHallClerkEvening"));
    foreach (var (room, ed) in new[] { "3", "4", "6", "7" }.Where(r => r != clerksRoom).Zip(new[] { "AGHallAssistant", "AGHallCook", "AGHallServer" }))
        beds.Add(($"BedRoom{room}", ed));
}
else Console.WriteLine("WARNING staff beds: no staff room has a second bed (AGHallBedRoom<n>b) yet; staff rooms not assigned");
void Own(FormKey at, FormKey owner)
{
    // (2026-11-06) any of the hall's cells: Henriette's room, its bed and chest are in the basement
    var o = merge ? mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).Where(c => hallCells.Contains(c.FormKey))
            .SelectMany(c => c.Persistent.Concat(c.Temporary)).OfType<PlacedObject>().First(x => x.FormKey == at)
        : (PlacedObject)cache.ResolveContext<IPlacedObject, IPlacedObjectGetter>(at).GetOrAddAsOverride(mod);
    o.Owner.SetTo(owner);
}
var owned = 0;
foreach (var (bed, owner) in beds)
    foreach (var name in new[] { "AGHall" + bed, "AGHallChest" + bed.Replace("Bed", "") })
    {
        if (!hallRefs.TryGetValue(name, out var r)) { Console.WriteLine($"WARNING {name}: not in the hall plugin yet; not owned"); continue; }
        Own(r.FormKey, Hall(owner).FormKey);
        owned++;
    }
foreach (var name in new[] { "AGHallBedRoom5", "AGHallChestRoom5" })
{
    if (!hallRefs.TryGetValue(name, out var r)) { Console.WriteLine($"WARNING {name}: not in the hall plugin yet; not owned"); continue; }
    Own(r.FormKey, room5.FormKey);
    owned++;
}
// the player's own bunk (only the first bed, by the windows as you walk in, with a safe storage chest): bunk 6, inside the attic door by the dormer, and its chest (AGHall2Chest, which
// never respawns), owned by vanilla's PlayerFaction as a bought home is; bunks 7 and 8 stay the guild's, for members
foreach (var name in new[] { "AGHallBunk6", "AGHallChestBunk6" })
{
    if (!hallRefs.TryGetValue(name, out var r)) { Console.WriteLine($"WARNING {name}: not in the hall plugin yet; not owned"); continue; }
    Own(r.FormKey, Ed<IFactionGetter>("PlayerFaction").FormKey);
    owned++;
}
// the bedroom doors close only when their sleeper goes to bed (the back office door still closes behind everyone, the guild master's suite door
// and the attic's are left as they are left). AGHallBedroomDoor on each, its Sleeper the one bed behind it: the rooms as
// groupOwner names them below (plan D), Caralion's room 5, Willem's bedroom. A door the hall no longer has stops the build.
foreach (var (door, sleeper) in new[] { ("AGHall2Room3Door", "AGHallClerkEvening"), ("AGHall2Room4Door", "AGHallClerkDay"), ("AGHall2Room5Door", "AGHallResidentNoble"),
                                        ("AGHall2Room6Door", "AGHallAssistant"), ("AGHall2Room7Door", "AGHallServer"), ("AGHall2GMBedroomDoor", "AGHallGuildMaster") })
{
    if (!hallRefs.TryGetValue(door, out var dr)) throw new Exception($"bedroom doors: no door named {door} in the hall");
    var o = merge ? mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).Where(c => hallCells.Contains(c.FormKey))
            .SelectMany(c => c.Persistent.Concat(c.Temporary)).OfType<PlacedObject>().First(x => x.FormKey == dr.FormKey)
        : (PlacedObject)cache.ResolveContext<IPlacedObject, IPlacedObjectGetter>(dr.FormKey).GetOrAddAsOverride(mod);
    var who = cell.Persistent.OfType<PlacedNpc>().First(r => r.EditorID == sleeper + "Ref").FormKey;
    o.VirtualMachineAdapter = new VirtualMachineAdapter { Scripts = { new ScriptEntry { Name = "AGHallBedroomDoor", Properties = {
        new ScriptObjectProperty { Name = "Sleeper", Object = new FormLink<ISkyrimMajorRecordGetter>(who), Flags = ScriptProperty.Flag.Edited } } } } };
}
// Caralion's armor: his family's ebony plate, "Cuirass of Cloudrest" and the rest, each with one
// of vanilla's Eminent (04) enchantments, a mixed set. It waits in his chest in room 5 (Expert, his key
// on him) and he wears it only in his quest's ambush (AGHallCaralionQuestScript.Ambush moves whatever is still in the
// chest onto him); spared, he leaves with it; killed, it is on his body; dead before his quest, it is still in the chest
// when the player buys the room (AG_TIF_HallRoom5Buy unlocks it; the room's faction owns it, so nothing is stolen).
// Own IDs (0x1E00 here, 0x9600 merged), so no other record's ID moves. The chest gets a container of its own holding the
// set, and turns persistent: the quest reaches it from Riverwood, with the hall's cells unloaded.
var cloudrest = new List<Armor>();
Key? cloudrestKey = null;
InIds(0x1E00u, 0x1E10u, "Caralion's armor", () =>
{
    var noDisenchant = Ed<IKeywordGetter>("MagicDisallowEnchanting").FormKey;
    foreach (var (piece, baseEd, ench) in new[] {
        ("Cuirass", "ArmorEbonyCuirass", "EnchArmorFortifyHealth04"), ("Gauntlets", "ArmorEbonyGauntlets", "EnchArmorFortifyOneHanded04"),
        ("Boots", "ArmorEbonyBoots", "EnchArmorResistMagic04"), ("Helmet", "ArmorEbonyHelmet", "EnchArmorFortifyDestruction04") })
    {
        var src = Ed<IArmorGetter>(baseEd);
        var a = (Armor)src.Duplicate(NewKey());
        a.EditorID = $"AGHallCloudrest{piece}"; a.Name = $"{piece} of Cloudrest";
        a.ObjectEffect.SetTo(Ed<IEffectRecordGetter>(ench).FormKey);
        a.TemplateArmor.SetTo(src.FormKey);   // as vanilla's enchanted variants: tempered and crafted as their base
        a.Keywords ??= new();
        if (!a.Keywords.Any(k => k.FormKey == noDisenchant)) a.Keywords.Add(noDisenchant);   // a unique: not to be learned, as vanilla's artifacts
        mod.Armors.Add(a);
        cloudrest.Add(a);
    }
    var key = (Key)Ed<IKeyGetter>("RiftenSnowShodHouseKey").Duplicate(NewKey());
    key.EditorID = "AGHallCaralionChestKey"; key.Name = "Caralion's Chest Key"; key.VirtualMachineAdapter = null;
    mod.Keys.Add(key);
    cloudrestKey = key;
    if (!hallRefs.TryGetValue("AGHallChestRoom5", out var chestRef)) { Console.WriteLine("WARNING AGHallChestRoom5: not in the hall plugin yet; Caralion's armor has no chest"); return 0; }
    var box = (Container)cache.Resolve<IContainerGetter>(chestRef.Base.FormKey).Duplicate(NewKey());
    box.EditorID = "AGHallCaralionChest";
    box.Items = new(cloudrest.Select(a => new ContainerEntry { Item = new ContainerItem { Item = a.ToLink<IItemGetter>(), Count = 1 } }));
    mod.Containers.Add(box);
    if (!merge) { Console.WriteLine("WARNING Caralion's chest: only the merged build makes it persistent; the spike plugin leaves room 5's chest as it is"); return 0; }
    var hallCellsOf = mod.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).Where(c => hallCells.Contains(c.FormKey));
    var (home, o) = hallCellsOf.SelectMany(c => c.Persistent.Concat(c.Temporary).OfType<PlacedObject>().Select(x => (c, x))).First(t => t.x.FormKey == chestRef.FormKey);
    o.Base.SetTo(box.FormKey);
    o.Lock = new LockData { Level = LockLevel.Expert };
    o.Lock.Key.SetTo(key.FormKey);
    if (home.Temporary.Remove(o)) { o.MajorRecordFlagsRaw |= 0x400; home.Persistent.Add(o); }
    return 0;
});
if (cloudrestKey is not null)
{
    var c_ = Hall("AGHallResidentNoble");
    c_.Items ??= new();
    c_.Items.Add(new ContainerEntry { Item = new ContainerItem { Item = cloudrestKey.ToLink<IItemGetter>(), Count = 1 } });
}
// Everything else that is someone's (a member takes the guild's clutter freely, but not from the
// staff's and residents' rooms, the tavern's stock or the kitchen). The hall's build lists which of its pieces stand
// where, in hall-owners.json beside its plugin ({"groups": {"room3": ["0x0009A1", ...], "bunk1": [...], "tavern": [...],
// "kitchen": [...]}}, local IDs in the hall's plugin); who owns each group is ours to say. The wall weapons, display
// cases, counter coin and Willem's quarters are the Guild Master faction's, set by the hall itself.
var groupOwner = new Dictionary<string, FormKey> { ["room5"] = room5.FormKey,   // (no "kitchen": kitchen clutter is free to take)
    ["tavern"] = services.FormKey, ["bunk1"] = Hall("AGHallResidentOrc").FormKey, ["bunk2"] = Hall("AGHallResidentRanger").FormKey,
    ["bunk3"] = Hall("AGHallResidentScout").FormKey, ["bunk4"] = Hall("AGHallResidentVeteran").FormKey, ["bunk5"] = Hall("AGHallBarkeeper").FormKey,
    ["henriette"] = Hall("AGHallCook").FormKey };   // her basement room, the hall's "henriette" group
// a staff room's clutter: whoever sleeps in that room. hall-owners.json groups pieces by the room they stand in, and since
// plan D (2026-11-06) the bed names no longer match the rooms: the clerks next door to each other
// (Nessa room 3 with Room3b, Margot room 4 with AGHallBedRoom3), Merila room 6 (AGHallBedRoom4), Henriette's AGHallBedRoom6
// in the basement. So the rooms are named here, not read off the beds.
foreach (var (room, ed) in new[] { ("room3", "AGHallClerkEvening"), ("room4", "AGHallClerkDay"), ("room6", "AGHallAssistant"), ("room7", "AGHallServer") })
    groupOwner[room] = Hall(ed).FormKey;
var ownersPath = Path.Combine(Path.GetDirectoryName(Path.GetFullPath(hallPath))!, "hall-owners.json");
var grouped = 0;
if (File.Exists(ownersPath))
{
    var groups = JsonDocument.Parse(File.ReadAllText(ownersPath)).RootElement.GetProperty("groups");
    // every cell of the hall (main, basement, strongroom): a group may stand in any of them (Henriette's, the basement)
    var inCell = hall.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells).Where(c => hallCells.Contains(c.FormKey))
        .SelectMany(c => c.Persistent.Concat(c.Temporary)).Select(r => r.FormKey.ID).ToHashSet();
    foreach (var g in groups.EnumerateObject())
    {
        if (!groupOwner.TryGetValue(g.Name, out var owner)) { Console.WriteLine($"WARNING hall-owners.json: no owner for group {g.Name} (left the guild's)"); continue; }
        foreach (var id in g.Value.EnumerateArray().Select(v => Convert.ToUInt32(v.GetString()!, 16)))
        {
            if (!inCell.Contains(id)) throw new Exception($"hall-owners.json: {g.Name} lists 0x{id:X}, not a reference in any of the hall's cells");
            Own(new FormKey(hall.ModKey, id), owner);
            grouped++;
        }
    }
}
else Console.WriteLine("WARNING hall-owners.json: not beside the hall's plugin yet; the rooms' clutter stays the guild's");
Console.WriteLine($"ownership: {hallFolk.Count} in the guild, {owned} beds and chests owned by name, {grouped} pieces by room, clerks' room {clerksRoom ?? "(none yet)"}");

Directory.CreateDirectory(outDir);
var outPath = mergeOut ?? Path.Combine(outDir, "AGNpcSpike.esp");
// merged, the file keeps the hall's name: it is the hall's plugin, its ModKey and every master reference unchanged
if (merge && !string.Equals(Path.GetFileName(outPath), hall.ModKey.FileName, StringComparison.OrdinalIgnoreCase))
    throw new Exception($"merge: write to a file named {hall.ModKey.FileName}, not {Path.GetFileName(outPath)}");
// The clerks keep the hall's Guild counter (their lines: clerk_dialogue.json).
// AG's own "I have guild business." as a topic of our own, in our own start-game quest: each clerk's reply opens the
// counter through AG's fragment (AG_TIF_GuildBusiness: AG_Native.ActionOpenCounter, which gives a hall clerk the hall's
// view; its ShowBarterMenu name is what lets SkyrimNet offer the line as an action). As AG's business topic does: one
// RANDOM group of lines per clerk, each line with its full conditions (registered, the player's rank); while AG's
// representative lines are switched off (MCM > Audio, AG_RepLinesGlobal 0) a twin borrows the game's "Of course."
// (Skyrim.esm 0x0DBA22). Our clerks, our cell: GetIsID and GetInCell on our own records.
var agEsp = ModKey.FromFileName("AdventurersGuild.esp");
var gRank = new FormKey(agEsp, 0x800);       // AG_PlayerRankGlobal: 0..5 = E..S, -1 not registered
var gRegistered = new FormKey(agEsp, 0x801); // AG_RegisteredGlobal
var gRepLines = new FormKey(agEsp, 0xC8A);   // AG_RepLinesGlobal
ConditionFloat GlobalIs(FormKey g, CompareOperator op, float v)
{
    var d = new GetGlobalValueConditionData();
    d.Global.Link.SetTo(g);
    return new ConditionFloat { CompareOperator = op, ComparisonValue = v, Data = d };
}
var clerkDlg = JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "clerk_dialogue.json"))).RootElement;
var clerkQuest = new Quest(NewKey(), SkyrimRelease.SkyrimSE)
{
    EditorID = "AGHallClerkDialogue", Name = "Guild Hall", Flags = Quest.Flag.StartGameEnabled, Priority = 50,
};
mod.Quests.Add(clerkQuest);
var clerkBranch = new DialogBranch(NewKey(), SkyrimRelease.SkyrimSE)
{
    EditorID = "AGHallClerkBranchBusiness", Quest = clerkQuest.ToLink<IQuestGetter>(),
    Category = DialogBranch.CategoryType.Player, Flags = DialogBranch.Flag.TopLevel,
};
mod.DialogBranches.Add(clerkBranch);
var clerkTopic = new DialogTopic(NewKey(), SkyrimRelease.SkyrimSE)
{
    EditorID = "AGHallClerkTopicBusiness", Name = clerkDlg.GetProperty("prompt").GetString(), Priority = 50,
    Branch = clerkBranch.ToNullableLink(), Quest = clerkQuest.ToNullableLink(),
    Category = DialogTopic.CategoryEnum.Topic, Subtype = DialogTopic.SubtypeEnum.Custom,
    SubtypeName = new RecordType("CUST"),   // as AG's EspGen: Mutagen writes 0 unless set, and every working topic has CUST
};
clerkBranch.StartingTopic.SetTo(clerkTopic.FormKey);
DialogResponsesAdapter OpensCounter() => new()
{
    ScriptFragments = new ScriptFragments
    {
        FileName = "AG_TIF_GuildBusiness",
        OnEnd = new ScriptFragment { ScriptName = "AG_TIF_GuildBusiness", FragmentName = "Fragment_0" },
    },
};
var twins = new List<DialogResponses>();
var lines = new List<DialogResponses>();
var clerkLines = new List<(string Key, string Clerk, uint Id, string Text)>();   // for the voice files and translations
foreach (var c in clerkDlg.GetProperty("clerks").EnumerateObject())
{
    var clerkNpc = Hall(c.Name);
    Condition[] Who()
    {
        var isId = new GetIsIDConditionData(); isId.Object.Link.SetTo(clerkNpc.FormKey);
        return new Condition[] { new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = isId },
            GlobalIs(gRegistered, CompareOperator.EqualTo, 1) }.Concat(InHallCells()).ToArray();
    }
    var twin = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = $"AGHallInfo_{c.Name}_business_short", Flags = new DialogResponseFlags { Flags = DialogResponses.Flag.Goodbye },
        ResponseData = new FormLinkNullable<IDialogResponsesGetter>(new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x0DBA22)),
        VirtualMachineAdapter = OpensCounter(),
    };
    twin.Conditions.Add(GlobalIs(gRepLines, CompareOperator.EqualTo, 0));
    twin.Conditions.AddRange(Who());
    twins.Add(twin);
    // These are also the clerk's greeting when the player clicks on her (her Hello, built in its
    // own topic further down, AGHallClerkTopicHello); "I have guild business." has short replies of its own, which open
    // the counter. Created here, in the same order as before, so each keeps its ID and its voice file.
    DialogResponses Line(string key, string text, IEnumerable<Condition> extra)
    {
        var info = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE)
        {
            EditorID = $"AGHallInfo_{c.Name}_{key}",
            Flags = new DialogResponseFlags { Flags = DialogResponses.Flag.Random },
        };
        info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
        info.Conditions.Add(GlobalIs(gRepLines, CompareOperator.EqualTo, 1));   // first, ANDed with all after it
        info.Conditions.AddRange(Who());
        info.Conditions.AddRange(extra);
        lines.Add(info);
        clerkLines.Add(($"{c.Name}:{key}", c.Name, info.FormKey.ID, text));
        return info;
    }
    var byRank = c.Value.GetProperty("byRank");
    const string ranks = "EDCBAS";
    var plain = byRank.EnumerateObject().Select(r => (Condition)GlobalIs(gRank, CompareOperator.NotEqualTo, ranks.IndexOf(r.Name))).ToList();
    foreach (var r in byRank.EnumerateObject())
        Line($"business_{r.Name}", r.Value.GetString()!, new Condition[] { GlobalIs(gRank, CompareOperator.EqualTo, ranks.IndexOf(r.Name)) });
    var n = 0;
    foreach (var x in c.Value.GetProperty("extra").EnumerateArray()) Line($"business_x{++n}", x.GetString()!, Array.Empty<Condition>());
    Line("business", c.Value.GetProperty("business").GetString()!, plain).Flags!.Flags |= DialogResponses.Flag.RandomEnd;   // the next clerk's lines are their own group
}
// the business topic: the twins first (the first reply whose conditions pass is said); the clerks' short replies follow
// them, built in the clerks' own ID block below
for (var i = 0; i < twins.Count; i++)
{
    if (i > 0) twins[i].PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(twins[i - 1].FormKey);
    clerkTopic.Responses.Add(twins[i]);
}
mod.DialogTopics.Add(clerkTopic);
const string clerkHelloEd = "AGHallClerkTopicHello";   // its first 15 letters are the business topic's: the voice files keep their names
var npcsDir = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));
Directory.CreateDirectory(Path.Combine(npcsDir, "build"));
File.WriteAllText(Path.Combine(npcsDir, "build", "clerk_lines.json"), JsonSerializer.Serialize(clerkLines.Select(l => new { key = l.Key, npc = l.Clerk,
    voice = cache.Resolve<IVoiceTypeGetter>(Hall(l.Clerk).Voice.FormKey).EditorID, info = $"{l.Id:X8}", quest = clerkQuest.EditorID, topic = clerkHelloEd, text = l.Text }),
    new JsonSerializerOptions { WriteIndented = true }));
Console.WriteLine($"clerks: {lines.Count} greetings and {twins.Count} twins");
// A recorded line's voice file is named after its INFO ID. If a record added mid-build moved the IDs (2026-10-28: a
// faction did, by one), every take would play under the wrong line: stop the build rather than ship that.
CheckTakes(clerkLines.Select(l => (l.Key, l.Id)));
void CheckTakes(IEnumerable<(string Key, uint Id)> built)
{
    var takesPath = Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "..", "hall-private", "npcs", "elevenlabs", "takes.json");
    if (!File.Exists(takesPath)) return;
    var ids = built.ToDictionary(l => l.Key, l => l.Id);
    foreach (var t in JsonDocument.Parse(File.ReadAllText(takesPath)).RootElement.EnumerateObject())
    {
        var key = t.Value.GetProperty("key").GetString()!;
        var m = System.Text.RegularExpressions.Regex.Match(t.Name, "_([0-9a-fA-F]{8})_\\d+$");
        if (!m.Success || !ids.TryGetValue(key, out var id)) continue;
        var was = Convert.ToUInt32(m.Groups[1].Value, 16);
        var now = id >= 0x8000 ? id : idBase + id;   // the merged plugin's ID, which the voice files are named after
        if (was != now)
            throw new Exception($"{key}: its recorded voice file is for line 0x{was:X8} but the line is now 0x{now:X8}: a record added before it moved the IDs. Add new records after the routines, in their own ID block.");
    }
}

// The bar's own shop (Cassius sells drinks, food and some limited supplies; Brynja food and drink): Cassius leaves the shared services faction (Brynja's alone now: the innkeeper's food and
// drink, 10-24) for a vendor faction of his own, as vanilla gives each inn its services faction: the innkeeper's food and
// drink plus a few adventurer's supplies (torches, lockpicks, minor healing potions), 12-24, his shift. After every other
// record, so no earlier ID moves.
var barChest = (Container)Ed<IContainerGetter>("MerchantWhiterunBannerdMareChest").Duplicate(NewKey());
barChest.EditorID = "AGHallBarChest";
barChest.Items ??= new();
foreach (var (item, count) in new[] { (new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x01D4EC), 10),   // Torch01
                                      (new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x00000A), 10),   // Lockpick
                                      (new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x03EADD), 5) })  // RestoreHealth01
    barChest.Items.Add(new ContainerEntry { Item = new ContainerItem { Item = new FormLink<IItemGetter>(item), Count = count } });
mod.Containers.Add(barChest);
var barChestRef = new PlacedObject(NewKey(), SkyrimRelease.SkyrimSE)
{
    EditorID = "AGHallBarChestRef", Base = barChest.ToNullableLink(),
    Placement = new Placement { Position = new P3Float(0, 0, -2050), Rotation = new P3Float(0, 0, 0) },
};
cell.Persistent.Add(barChestRef);
var barShop = new Faction(NewKey(), SkyrimRelease.SkyrimSE)
{
    EditorID = "AGHallBarFaction", Name = "Guild Hall Bar",
    Flags = Faction.FactionFlag.Vendor | Faction.FactionFlag.CanBeOwner | Faction.FactionFlag.HiddenFromPC,
    MerchantContainer = barChestRef.ToNullableLink(),
    VendorBuySellList = Ed<IFormListGetter>("VendorItemsInnkeeper").ToNullableLink(),
    // the bar runs to 2 AM, and vendor hours cannot cross midnight (no vanilla vendor's do): open at all hours, selling
    // only within 350 of the bar, as Eorlund's and Fralia's services sell only near their stalls (a reference and a
    // radius); his schedule keeps him there 12-2
    VendorValues = new VendorValues { StartHour = 0, EndHour = 24, Radius = 350 },
    VendorLocation = new LocationTargetRadius { Target = new LocationTarget { Link = new FormLink<IPlacedGetter>(
        (hallRefs.TryGetValue("AGHallBarLeanMarker", out var barLean) ? barLean : throw new Exception("the hall has no AGHallBarLeanMarker")).FormKey) } },
};
mod.Factions.Add(barShop);
var cassius = Hall("AGHallBarkeeper");
cassius.Factions.RemoveAll(f => f.Faction.FormKey == services.FormKey);
Join(cassius, barShop.FormKey);
Console.WriteLine("shops: Brynja (AGHallServicesFaction, 6-21), Cassius (AGHallBarFaction, at the bar, with supplies)");

// The routines' packages come and go as the schedule changes, so they have a block of their own (from 0x900 in the spike,
// 0x8100 merged): a schedule edit never moves another record's ID.
next = Math.Max(next, 0x900u);
// The daily routines (schedules.json, from SCHEDULES.md). Each block is a copy of the vanilla
// package that does the same thing, with our spot, radius and hours: work = Saadia's Sandbox at her work area (close,
// busy), leisure = the Companions' training Sandbox (sit, eat, wander), eat = the Companions' Eat, sleep = the
// Companions' Sleep, sent to the NPC's own bed. The engine takes the first package whose schedule applies, so the timed
// blocks come first and an all-day leisure Sandbox at the NPC's default spot closes the list (the Companions'
// HangOutInJorrvaskr). After every other record, so no earlier ID moves.
var sched = JsonDocument.Parse(File.ReadAllText(Path.Combine(npcsDir, "schedules.json"))).RootElement;
var spotRadius = sched.GetProperty("spots").EnumerateObject().ToDictionary(p => p.Name, p => p.Value.GetSingle());
var ownRadius = sched.GetProperty("own").GetSingle();
// every named ref in the hall's cells (the Strongroom is a cell of its own)
var hallNamed = hall.Cells.Records.SelectMany(b => b.SubBlocks).SelectMany(s => s.Cells)
    .SelectMany(c => c.Persistent.Concat(c.Temporary)).OfType<IPlacedObjectGetter>().Where(r => r.EditorID != null)
    .GroupBy(r => r.EditorID!).ToDictionary(g => g.Key, g => g.First().FormKey);
// lean = Wilhelm's SitTarget on his bar's lean marker (Vilemyr Inn; Ungrien, Mallus and Haelga lean the same way): the
// NPC goes to the marker and leans there for the shift, as a sitter takes a chair, offering services as he does. Work's
// Sandbox let the clerks drift (2026-10-28, read in game: Nessa 177 units from her marker, turned away from the counter).
// train and archery (the basement: Willem's sword drill and Nessa's archery) are vanilla's
// practice packages, measured: a Riften guard's UseWeapon at a dummy (a heading marker 140-166 in front, the dummy's ref
// the target) and Sky Haven's archery (a heading marker 400-425 from an XMarker on the target, the bow already held). Each
// block names its stand ('where') and its target ('target'); until the hall places both, the block is leisure at its
// stand-in. noSpecial (any Sandbox block): the Sandbox's "Allow Special Furniture" off, so a wander through the great hall
// does not end at the hearth's cooking spit.
var pkgSrc = new Dictionary<string, IPackageGetter> { ["work"] = Ed<IPackageGetter>("WhiterunSaadiaBanneredMarePackage9x12"),
    ["lean"] = Ed<IPackageGetter>("IvarsteadWilhelmBarkeeperPackage0x0"),
    // sit = a jarl's throne package, a sit on one named piece of furniture for the whole block (so
    // Willem does not stand by his desk all day: his desk hours seated, all of them)
    ["sit"] = Ed<IPackageGetter>("WindhelmJarlSitInThrone"),
    ["use"] = Ed<IPackageGetter>("MGRAppBrelynaStage20Read"),   // UseIdleMarker on one idle marker (60 such in Skyrim.esm, measured 2026-11-04)
    ["leisure"] = Ed<IPackageGetter>("CompanionsShift2Train7x5"), ["eat"] = Ed<IPackageGetter>("CompanionsShift2Eat13x3"),
    ["sleep"] = Ed<IPackageGetter>("CompanionsShift2Sleep22x8"),
    ["train"] = Ed<IPackageGetter>("GuardRiftenPracticeDayDummy01_20x2"), ["archery"] = Ed<IPackageGetter>("MQSkyHavenTempleArcheryPracticeA8x2") };
var missingSpots = new SortedSet<string>();
var packages = 0;
string[] clerkIds = { "AGHallClerkDay", "AGHallClerkEvening" };
var coverLater = new List<Action>();   // the clerks' cover packages, made after every routine so no routine's ID moves
foreach (var n in sched.GetProperty("npcs").EnumerateObject())
{
    var npc = Hall(n.Name);
    var ownMarker = n.Value.GetProperty("default").GetString()!;
    (FormKey At, float Radius) Where(string where, string kind, float? radius, string? orElse = null, float? orElseRadius = null)
    {
        if (where == "bed") where = n.Value.GetProperty("bed").GetString()!;
        var r = radius ?? (spotRadius.TryGetValue(where, out var sr) ? sr : kind == "sleep" ? 150 : ownRadius);
        if (hallNamed.TryGetValue(where, out var fk)) return (fk, r);
        missingSpots.Add(where);
        // the block's own stand-in ("else"), when the hall has it, before the NPC's default spot
        if (orElse != null && hallNamed.TryGetValue(orElse, out var f1)) return (f1, orElseRadius ?? ownRadius);
        // a spot the hall has not placed yet: the NPC's own default spot
        if (hallNamed.TryGetValue(ownMarker, out var f2)) return (f2, ownRadius);
        throw new Exception($"schedules.json: {n.Name}: neither {where} nor {ownMarker} is in the hall's plugin");
    }
    Package Make1(string kind, string ed, string where, float? radius, int hour, int hours, string? days, string? orElse = null, float? orElseRadius = null,
        string? target = null, bool noSpecial = false)
    {
        // a lean marker the hall has not placed yet: the shift works from the stand-in instead
        if (kind is "lean" or "sit" && !hallNamed.ContainsKey(where)) { missingSpots.Add(where); kind = "work"; where = orElse ?? ownMarker; radius = orElseRadius; }
        // an idle marker the hall has not placed yet: leisure at the stand-in instead
        if (kind == "use" && !hallNamed.ContainsKey(where)) { missingSpots.Add(where); kind = "leisure"; where = orElse ?? ownMarker; radius = orElseRadius; }
        // practice whose stand or target the hall has not placed yet: leisure at the stand-in instead
        if (kind is "train" or "archery" && !(hallNamed.ContainsKey(where) && target != null && hallNamed.ContainsKey(target)))
        {
            missingSpots.Add(hallNamed.ContainsKey(where) ? target ?? "(no target)" : where); kind = "leisure"; where = orElse ?? ownMarker; radius = orElseRadius;
        }
        var pk = (Package)pkgSrc[kind].Duplicate(NewKey());
        pk.EditorID = ed;
        // a routine runs by its schedule alone: drop whatever conditions the vanilla source carried (2026-11-03: the Sky Haven
        // Temple archery's "Blades moved in" marker and its rain and snow checks kept Nessa from ever practising)
        pk.Conditions.Clear();
        // ... and its owner quest: a package in an NPC's own list must have none (2026-11-04: the "use" kind, copied from
        // Brelyna's MGRAppBrelynaStage20Read, kept MGRApp's; the engine rejects such a package at data load and its removal
        // from the list never ends: every install hung on the first loading screen)
        pk.OwnerQuest.Clear();
        pk.ScheduleHour = (sbyte)hour; pk.ScheduleMinute = 0; pk.ScheduleDurationInMinutes = hours * 60;
        pk.ScheduleDayOfWeek = days is null ? Package.DayOfWeek.Any : Enum.Parse<Package.DayOfWeek>(days);
        var (at, r) = Where(where, kind, radius, orElse, orElseRadius);
        if (kind is "lean" or "use" or "sit")
            pk.Data.Values.OfType<PackageDataTarget>().First().Target = new PackageTargetSpecificReference { Reference = new FormLink<IPlacedGetter>(at) };
        else if (kind is "train" or "archery")
        {
            // vanilla's inputs: 3 Use Weapon Location (the stand, radius 32 as vanilla's), 4 Target to Attack and 28 Trigger Ref
            ((PackageDataLocation)pk.Data[3]).Location = new LocationTargetRadius { Target = new LocationTarget { Link = new FormLink<IPlacedGetter>(at) }, Radius = 32 };
            foreach (var k in new sbyte[] { 4, 28 })
                ((PackageDataTarget)pk.Data[k]).Target = new PackageTargetSpecificReference { Reference = new FormLink<IPlacedGetter>(hallNamed[target!]) };
            // archery: the bow and arrows only for the practice (npcs/papyrus/PF_AGHallPracticeBow.psc, built by
            // build_scripts.sh): handed over and equipped as it begins, taken back when it ends or the schedule moves on
            if (kind == "archery")
            {
                const string pf = "PF_AGHallPracticeBow";
                pk.VirtualMachineAdapter = new PackageAdapter
                {
                    Scripts = { new ScriptEntry { Name = pf, Properties = {
                        new ScriptObjectProperty { Name = "Bow", Object = Ed<IWeaponGetter>("HuntingBow").ToLink<ISkyrimMajorRecordGetter>(), Flags = ScriptProperty.Flag.Edited },
                        new ScriptObjectProperty { Name = "Arrows", Object = Ed<IAmmunitionGetter>("IronArrow").ToLink<ISkyrimMajorRecordGetter>(), Flags = ScriptProperty.Flag.Edited } } } },
                    ScriptFragments = new PackageScriptFragments
                    {
                        FileName = pf,
                        OnBegin = new ScriptFragment { ScriptName = pf, FragmentName = "Fragment_0" },
                        OnEnd = new ScriptFragment { ScriptName = pf, FragmentName = "Fragment_1" },
                        OnChange = new ScriptFragment { ScriptName = pf, FragmentName = "Fragment_1" },
                    },
                };
            }
        }
        else
            ((PackageDataLocation)pk.Data[0]).Location = new LocationTargetRadius
            {
                Target = new LocationTarget { Link = new FormLink<IPlacedGetter>(at) }, Radius = (uint)r,
            };
        if (noSpecial && pk.Data.TryGetValue(31, out var sp) && sp is PackageDataBool spb) spb.Data = false;   // Sandbox: Allow Special Furniture
        mod.Packages.Add(pk);
        packages++;
        return pk;
    }
    npc.Packages.Clear();
    var i = 0;
    foreach (var b in n.Value.GetProperty("blocks").EnumerateArray())
    {
        var kind = b.GetProperty("do").GetString()!;
        var hour = b.GetProperty("at").GetInt32();
        var pk = Make1(kind, $"{n.Name}Pkg{++i:00}{char.ToUpper(kind[0])}{kind[1..]}{hour:00}", b.GetProperty("where").GetString()!,
            b.TryGetProperty("radius", out var rr) ? rr.GetSingle() : null, hour, b.GetProperty("hours").GetInt32(),
            b.TryGetProperty("days", out var dd) ? dd.GetString() : null,
            b.TryGetProperty("else", out var ee) ? ee.GetString() : null, b.TryGetProperty("elseRadius", out var er) ? er.GetSingle() : null,
            b.TryGetProperty("target", out var tg) ? tg.GetString() : null, b.TryGetProperty("noSpecial", out var ns) && ns.GetBoolean());
        // allow (any Sandbox block): switch on what Saadia's Sandbox, the work blocks' source, has off (measured 2026-11-07:
        // no wandering, no sitting, no special furniture, so a worker stood frozen). "wander" (7) walks the area, "sit" (6)
        // takes a chair, "special" (31) uses special furniture such as a cooking pot, as vanilla's forge workers do
        if (b.TryGetProperty("allow", out var al))
            foreach (var a in al.EnumerateArray().Select(x => x.GetString()))
            {
                sbyte k = a switch { "wander" => 7, "sit" => 6, "special" => 31, _ => throw new Exception($"{n.Name}: allow '{a}' is not wander, sit or special") };
                if (pk.Data.TryGetValue(k, out var dv) && dv is PackageDataBool db) db.Data = true;
                else throw new Exception($"{n.Name}: a '{kind}' block has no Sandbox input {k} to allow '{a}'");
            }
        // deny: the reverse, off what the source has on (the residents' wandering blocks neither cook
        // at the hearth's spit or Henriette's pot nor nap in a bed by day): "special" (31), "sleep" (3), "sit" (6), "wander" (7)
        if (b.TryGetProperty("deny", out var dn))
            foreach (var a in dn.EnumerateArray().Select(x => x.GetString()))
            {
                sbyte k = a switch { "wander" => 7, "sit" => 6, "special" => 31, "sleep" => 3, _ => throw new Exception($"{n.Name}: deny '{a}' is not wander, sit, special or sleep") };
                if (pk.Data.TryGetValue(k, out var dv) && dv is PackageDataBool db) db.Data = false;
                else throw new Exception($"{n.Name}: a '{kind}' block has no Sandbox input {k} to deny '{a}'");
            }
        npc.Packages.Add(pk.ToLink<IPackageGetter>());
    }
    // all day, when no block applies: leisure at their default spot (schedule "any time": hour -1, no duration)
    var idle = Make1("leisure", $"{n.Name}PkgIdle", ownMarker, null, 0, 0, null);
    idle.ScheduleHour = -1; idle.ScheduleMinute = -1; idle.ScheduleDurationInMinutes = 0;
    npc.Packages.Add(idle.ToLink<IPackageGetter>());
    // the counter's cover (see OnShift): through the other clerk's hours outside her own, while that clerk is out of the
    // hall, she leans at her own place at the counter, ahead of every other block
    if (clerkIds.Contains(n.Name))
    {
        var me = n.Name;
        coverLater.Add(() =>
        {
            var lean = n.Value.GetProperty("blocks").EnumerateArray().First(b => b.GetProperty("do").GetString() == "lean");
            var (at, end) = ShiftOf(me);
            var other = clerkIds.First(c => c != me);
            var (oAt, oEnd) = ShiftOf(other);
            var (from, to) = oEnd > end ? (end, oEnd) : (oAt, at);
            var pk = Make1("lean", $"{me}PkgCover{from:00}", lean.GetProperty("where").GetString()!, null, from, to - from, null,
                lean.TryGetProperty("else", out var ee) ? ee.GetString() : null, lean.TryGetProperty("elseRadius", out var er) ? er.GetSingle() : null);
            pk.Conditions.AddRange(OutOfHall(ClerkRef(other)));
            npc.Packages.Insert(0, pk.ToLink<IPackageGetter>());
        });
    }
}
foreach (var cover in coverLater) cover();
if (next > 0xA00) throw new Exception($"the routines and the clerks' cover ran to 0x{next:X}, into the clerk business's block at 0xA00");
foreach (var s in missingSpots) Console.WriteLine($"WARNING routine spot {s}: not in the hall plugin yet; its blocks use their stand-in ('else') or the NPC's own marker");
Console.WriteLine($"routines: {packages} packages for {sched.GetProperty("npcs").EnumerateObject().Count()} NPCs");

// The clerks' guild business (2.0: registration and promotion at the hall, in the clerks' own
// voices). Its own ID block (0xA00 here, 0x8200 merged), after the routines' (0x900-0x9FF): nothing added before it
// moves its IDs, and its voiced lines keep their files. As AG's innkeeper topics (tools/EspGen MakeTopic) and the DLL's
// rules for them (Guild.cpp RoleOfLine, by these topics' editor IDs): in RegisterPay and PromotePay the lines that act
// are the Goodbyes, so only "register"/"promote" are, and only with the fee in hand; in Replace the acting line ends
// nothing and needs the fee; every CardHandIn line acts. The clerks speak these whatever AG_RepLinesGlobal says (that
// switch is for the innkeepers' lines). Not tied to the hall-only toggles: at the hall these are always offered.
next = Math.Max(next, 0xA00u);
// AG's DLL offers the Guild's SkyrimNet actions at the hall (register, promotion, card, reports, the counter) to this
// faction's members, found by its editor ID at run time (the board session's request, 2026-10-28)
var clerkFaction = new Faction(NewKey(), SkyrimRelease.SkyrimSE)
{
    EditorID = "AGHallClerkFaction", Name = "Guild Hall Clerks", Flags = Faction.FactionFlag.HiddenFromPC,
};
mod.Factions.Add(clerkFaction);
var agDlg = JsonDocument.Parse(File.ReadAllText(Path.Combine(npcsDir, "..", "..", "..", "config", "dialogue.json"))).RootElement;
string Prompt(string k) => agDlg.GetProperty("prompts").GetProperty(k).GetString()!;
var gPromoReady = new FormKey(agEsp, 0x802);   // AG_PromotionReadyGlobal
var gRegFee = new FormKey(agEsp, 0x814);       // AG_RegisterFee
var gPromoFee = new FormKey(agEsp, 0x815);     // AG_PromotionFee
// the pay lines show "(<Global=AG_RegisterFee> gold)": the game fills a <Global=> only from the owning quest's
// Text Display Globals, as AG's own dialogue quest does; without them the clerks' line reads "((...) gold)"
clerkQuest.TextDisplayGlobals.Add(new FormLink<IGlobalGetter>(gRegFee));
clerkQuest.TextDisplayGlobals.Add(new FormLink<IGlobalGetter>(gPromoFee));
var gCardFee = new FormKey(agEsp, 0x81D);      // AG_CardFee
var gCardsCarried = new FormKey(agEsp, 0xCF9); // AG_CardsCarriedGlobal
var gCardCase = new FormKey(agEsp, 0xCFA);     // AG_CardCaseGlobal: 1 alive, 2 dead, 3 fell in the player's party, 4 worn
var guildCard = new FormKey(agEsp, 0x81A);
Condition Gold(FormKey fee, bool enough)   // the player (the dialogue target) carries at least / less than the fee
{
    var d = new GetItemCountConditionData { RunOnType = Condition.RunOnType.Target };
    d.ItemOrList.Link.SetTo(new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x00000F));   // Gold001
    return new ConditionGlobal { CompareOperator = enough ? CompareOperator.GreaterThanOrEqualTo : CompareOperator.LessThan,
        ComparisonValue = new FormLink<IGlobalGetter>(fee), Data = d };
}
Condition NoCard()
{
    var d = new GetItemCountConditionData { RunOnType = Condition.RunOnType.Target };
    d.ItemOrList.Link.SetTo(guildCard);
    return new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 0, Data = d };
}
var topicLines = new List<(string Key, string Clerk, uint Id, string Text, string Topic)>();
var clerkTopics = clerkDlg.GetProperty("topics");
Condition[] At(Npc who)
{
    var isId = new GetIsIDConditionData(); isId.Object.Link.SetTo(who.FormKey);
    return new Condition[] { new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = isId } }
        .Concat(InHallCells()).ToArray();
}
// The counter is closed outside the clerks' shifts (schedules.json's lean blocks, Margot 6-16, Nessa
// 12-22): a clerk does the Guild's business only on shift; off it, "afterHours" below. The menu only: SkyrimNet's and CHIM's
// actions have no hours: a player who talks a clerk into opening the counter after hours is not blocked.
(int At, int End) ShiftOf(string clerk)
{
    var b = sched.GetProperty("npcs").GetProperty(clerk).GetProperty("blocks").EnumerateArray().First(x => x.GetProperty("do").GetString() == "lean");
    return (b.GetProperty("at").GetInt32(), b.GetProperty("at").GetInt32() + b.GetProperty("hours").GetInt32());
}
ConditionFloat Hour(CompareOperator op, float v, bool or = false) =>
    new() { CompareOperator = op, ComparisonValue = v, Data = new GetCurrentTimeConditionData(), Flags = or ? Condition.Flag.OR : 0 };
// The counter's cover: while one clerk is out of the hall (her own quest, a SkyrimNet follow),
// the other counts as on shift through both clerks' hours, so the counter never stands empty with a clerk in the hall.
// Skyrim reads conditions with the ORs binding first and ANDs joining the groups: the hours both shifts span, AND
// (her own shift's edge OR the other clerk not in the hall). "Not in the hall" is in none of its cells, so the edge is
// ORed with each cell's check in turn: (edge OR not in A) AND (edge OR not in B) ...
FormKey ClerkRef(string clerk) => cell.Persistent.OfType<PlacedNpc>().First(r => r.EditorID == clerk + "Ref").FormKey;
Condition[] InHall(string clerk) => InHallCells(ClerkRef(clerk));
Condition[] EdgeOrOutOfHall(Func<ConditionFloat> edge, string clerk) =>
    OutOfHall(ClerkRef(clerk)).SelectMany(o => new[] { (Condition)edge(), o }).ToArray();
Condition[] OnShift(string clerk)
{
    var (at, end) = ShiftOf(clerk);
    var other = clerkIds.First(c => c != clerk);
    var (oAt, oEnd) = ShiftOf(other);
    if (oAt > end || at > oEnd) throw new Exception("schedules.json: the clerks' shifts must meet for the counter's cover");
    var c = new List<Condition> { Hour(CompareOperator.GreaterThanOrEqualTo, Math.Min(at, oAt)), Hour(CompareOperator.LessThan, Math.Max(end, oEnd)) };
    if (oEnd > end) c.AddRange(EdgeOrOutOfHall(() => Hour(CompareOperator.LessThan, end, or: true), other));
    if (oAt < at) c.AddRange(EdgeOrOutOfHall(() => Hour(CompareOperator.GreaterThanOrEqualTo, at, or: true), other));
    return c.ToArray();
}
DialogBranch NewBranch(string stem) { var b = new DialogBranch(NewKey(), SkyrimRelease.SkyrimSE)
    { EditorID = $"AGHallClerkBranch{stem}", Quest = clerkQuest.ToLink<IQuestGetter>(), Category = DialogBranch.CategoryType.Player,
      Flags = DialogBranch.Flag.TopLevel }; mod.DialogBranches.Add(b); return b; }
DialogTopic NewTopic(DialogBranch b, string stem, string text) { var t = new DialogTopic(NewKey(), SkyrimRelease.SkyrimSE)
    { EditorID = $"AGHallClerkTopic{stem}", Name = text, Priority = 50, Branch = b.ToNullableLink(), Quest = clerkQuest.ToNullableLink(),
      Category = DialogTopic.CategoryEnum.Topic, Subtype = DialogTopic.SubtypeEnum.Custom, SubtypeName = new RecordType("CUST") };
    mod.DialogTopics.Add(t); return t; }
DialogResponses Say(DialogTopic t, string clerk, string slot, bool goodbye, IEnumerable<Condition> conds, FormKey? key = null)
{
    var text = clerkTopics.GetProperty(clerk).GetProperty(slot).GetString()!;
    var info = new DialogResponses(key ?? NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = $"AGHallInfo_{clerk}_{slot.Replace(':', '_')}",
        Flags = new DialogResponseFlags { Flags = goodbye ? DialogResponses.Flag.Goodbye : 0 },
    };
    info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
    info.Conditions.AddRange(At(Hall(clerk)));
    info.Conditions.AddRange(conds);
    if (t.Responses.Count > 0) info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(t.Responses[^1].FormKey);
    t.Responses.Add(info);
    topicLines.Add(($"{clerk}:{slot}", clerk, info.FormKey.ID, text, t.EditorID!));
    return info;
}
var clerkNames = clerkTopics.EnumerateObject().Select(c => c.Name).ToList();
foreach (var ed in clerkNames) Join(Hall(ed), clerkFaction.FormKey);
// Register and Promote: the ask names the fee and offers "Here's the fee." / "Not now."; the pay line acts (a Goodbye)
void FeeTopics(string stem, string role, FormKey fee, Condition[] state)
{
    var b = NewBranch(stem);
    var ask = NewTopic(b, stem, Prompt(role));
    b.StartingTopic.SetTo(ask.FormKey);
    var pay = NewTopic(b, stem + "Pay", Prompt(role + "Pay"));
    var later = NewTopic(b, stem + "Later", Prompt("later"));
    foreach (var c in clerkNames)
    {
        var a = Say(ask, c, role + "Ask", false, state.Concat(OnShift(c)));
        a.LinkTo.Add(new FormLink<IDialogTopicGetter>(pay.FormKey));
        a.LinkTo.Add(new FormLink<IDialogTopicGetter>(later.FormKey));
        Say(pay, c, role, true, state.Append(Gold(fee, true)));
        Say(pay, c, role + "Nofee", false, state.Append(Gold(fee, false)));
        Say(later, c, role + "Later", false, state);
    }
}
FeeTopics("Register", "register", gRegFee, new[] { (Condition)GlobalIs(gRegistered, CompareOperator.EqualTo, 0) });
FeeTopics("Promote", "promote", gPromoFee, new[] { (Condition)GlobalIs(gRegistered, CompareOperator.EqualTo, 1), GlobalIs(gPromoReady, CompareOperator.EqualTo, 1) });
{
    // a lost card: the fee is in the player's own line, so no ask; the new card does not end the conversation
    var b = NewBranch("Replace");
    var t = NewTopic(b, "Replace", Prompt("replace"));
    b.StartingTopic.SetTo(t.FormKey);
    var state = new[] { (Condition)GlobalIs(gRegistered, CompareOperator.EqualTo, 1), NoCard() };
    foreach (var c in clerkNames)
    {
        Say(t, c, "replace", false, state.Append(Gold(gCardFee, true)).Concat(OnShift(c)));
        Say(t, c, "replaceNofee", false, state.Append(Gold(gCardFee, false)).Concat(OnShift(c)));
    }
}
{
    // other adventurers' cards, by the weightiest of those carried (AG's MemberCards.cpp keeps the two globals)
    var b = NewBranch("CardHandIn");
    var t = NewTopic(b, "CardHandIn", Prompt("cardHandIn"));
    b.StartingTopic.SetTo(t.FormKey);
    // the hall folk they knew: a dead or fallen resident's card (Willem's too) gets each clerk's own line
    // for them, before the plain ones. AG's DLL sets AGHallCardOwnerGlobal (merged 0x96C0) to the owner's placed ref, as
    // the card's key names it. Its own IDs: the global at 0x1EC0, the lines from 0x1ED0, so no recorded line moves.
    var gOwner = InIds(0x1EC0u, 0x1EC1u, "the card owner global", () => { var g = new GlobalShort(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallCardOwnerGlobal", Data = 0 }; mod.Globals.Add(g); return g; });
    if (merge && gOwner.FormKey.ID != 0x96C0) throw new Exception($"AGHallCardOwnerGlobal is 0x{gOwner.FormKey.ID:X}; AG's DLL reads 0x96C0");
    foreach (var c in clerkNames)
    {
        foreach (var ed in new[] { "AGHallGuildMaster", "AGHallResidentVeteran", "AGHallResidentRanger", "AGHallResidentOrc", "AGHallResidentScout", "AGHallResidentNoble" })
        {
            if (!clerkTopics.GetProperty(c).TryGetProperty($"cardHandIn:{ed}", out _)) continue;
            var refId = cell.Persistent.OfType<PlacedNpc>().First(r => r.EditorID == ed + "Ref").FormKey.ID;
            Say(t, c, $"cardHandIn:{ed}", false, new Condition[] { GlobalIs(gRegistered, CompareOperator.EqualTo, 1),
                GlobalIs(gCardsCarried, CompareOperator.GreaterThanOrEqualTo, 1), GlobalIs(gCardCase, CompareOperator.GreaterThanOrEqualTo, 2),
                GlobalIs(gCardCase, CompareOperator.LessThanOrEqualTo, 3), GlobalIs(gOwner.FormKey, CompareOperator.EqualTo, refId) }.Concat(OnShift(c)), KeyIn(0x1ED0u));
        }
        foreach (var (name, n) in new[] { ("fallen", 3), ("dead", 2), ("alive", 1), ("worn", 4) })
            Say(t, c, $"cardHandIn:{name}", false, new Condition[] { GlobalIs(gRegistered, CompareOperator.EqualTo, 1),
                GlobalIs(gCardsCarried, CompareOperator.GreaterThanOrEqualTo, 1), GlobalIs(gCardCase, CompareOperator.EqualTo, n) }.Concat(OnShift(c)));
    }
}
CheckTakes(topicLines.Select(l => (l.Key, l.Id)));
File.WriteAllText(Path.Combine(npcsDir, "build", "clerk_topic_lines.json"), JsonSerializer.Serialize(topicLines.Select(l => new { key = l.Key, npc = l.Clerk,
    voice = cache.Resolve<IVoiceTypeGetter>(Hall(l.Clerk).Voice.FormKey).EditorID, info = $"{l.Id:X8}", quest = clerkQuest.EditorID, topic = l.Topic, text = l.Text }),
    new JsonSerializerOptions { WriteIndented = true }));
Console.WriteLine($"clerk topics: {topicLines.Count} lines in Register, Promote, Replace and CardHandIn; faction {clerkFaction.EditorID} on {clerkNames.Count} clerks");

// The clerks' greetings become their Hello: said when the player clicks on her
// (IsInDialogueWithPlayer, as vanilla's click-only openers use it: the Old Hroldan's keeper, Wulf Wild-Blood), to a
// member, during her counter shift; a walk-by or another hour gets vanilla's. "I have guild business." then gets short
// replies of their own (clerk_dialogue.json "replies"), which open the counter as the greetings used to. Until those
// replies are approved the greetings stay where they were, as the business topic's replies. After every record above.
var replies = clerkDlg.TryGetProperty("replies", out var rp) ? rp : default;
var helloLines = new List<(string Key, string Clerk, uint Id, string Text, string Topic)>();
if (replies.ValueKind == JsonValueKind.Object)
{
    var hello = new DialogTopic(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = clerkHelloEd, Priority = 50, Quest = clerkQuest.ToNullableLink(),
        Category = DialogTopic.CategoryEnum.Misc, Subtype = DialogTopic.SubtypeEnum.Hello, SubtypeName = new RecordType("HELO"),
    };
    var clerkOf = clerkLines.ToDictionary(l => l.Id, l => l.Clerk);
    var shift = sched.GetProperty("npcs").EnumerateObject().ToDictionary(x => x.Name,
        x => x.Value.GetProperty("blocks").EnumerateArray().Where(b => b.GetProperty("do").GetString() == "lean")
              .Select(b => (At: b.GetProperty("at").GetInt32(), Hours: b.GetProperty("hours").GetInt32())).FirstOrDefault());
    for (var i = 0; i < lines.Count; i++)
    {
        var info = lines[i];
        var (at, hours) = shift[clerkOf[info.FormKey.ID]];
        var talking = new IsInDialogueWithPlayerConditionData();
        info.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = talking });
        info.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.GreaterThanOrEqualTo, ComparisonValue = at, Data = new GetCurrentTimeConditionData() });
        info.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.LessThan, ComparisonValue = at + hours, Data = new GetCurrentTimeConditionData() });
        if (i > 0) info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(lines[i - 1].FormKey);
        hello.Responses.Add(info);
    }
    mod.DialogTopics.Add(hello);
    // (the twins open the counter too, so they keep the same hours)
    var twinClerks = clerkDlg.GetProperty("clerks").EnumerateObject().Select(c => c.Name).ToList();
    for (var i = 0; i < twins.Count; i++) twins[i].Conditions.AddRange(OnShift(twinClerks[i]));
    // the replies, after the twins in the business topic: one RANDOM group per clerk, each a Goodbye that opens the counter
    foreach (var c in replies.EnumerateObject())
    {
        var who = Hall(c.Name);
        var texts = c.Value.EnumerateArray().Select(x => x.GetString()!).ToList();
        for (var k = 0; k < texts.Count; k++)
        {
            var info = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE)
            {
                EditorID = $"AGHallInfo_{c.Name}_reply{k + 1}",
                Flags = new DialogResponseFlags { Flags = DialogResponses.Flag.Goodbye | DialogResponses.Flag.Random | (k == texts.Count - 1 ? DialogResponses.Flag.RandomEnd : 0) },
                VirtualMachineAdapter = OpensCounter(),
            };
            info.Responses.Add(new DialogResponse { Text = texts[k], Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
            info.Conditions.Add(GlobalIs(gRepLines, CompareOperator.EqualTo, 1));
            info.Conditions.AddRange(At(who));
            info.Conditions.Add(GlobalIs(gRegistered, CompareOperator.EqualTo, 1));
            info.Conditions.AddRange(OnShift(c.Name));
            info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(clerkTopic.Responses[^1].FormKey);
            clerkTopic.Responses.Add(info);
            helloLines.Add(($"{c.Name}:reply{k + 1}", c.Name, info.FormKey.ID, texts[k], clerkTopic.EditorID!));
        }
    }
    CheckTakes(helloLines.Select(l => (l.Key, l.Id)));
    Console.WriteLine($"clerk greetings: {lines.Count} in {clerkHelloEd} (on click, on shift); {helloLines.Count} replies in {clerkTopic.EditorID}");
}
else
{
    // not yet: the greetings answer "I have guild business." as before, Goodbyes that open the counter
    var prev = clerkTopic.Responses.Count > 0 ? clerkTopic.Responses[^1] : null;
    foreach (var info in lines)
    {
        info.Flags!.Flags |= DialogResponses.Flag.Goodbye;
        info.VirtualMachineAdapter = OpensCounter();
        if (prev != null) info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(prev.FormKey);
        clerkTopic.Responses.Add(info);
        prev = info;
    }
    Console.WriteLine($"clerk greetings: no approved replies yet (clerk_dialogue.json \"replies\"): the {lines.Count} greetings stay the replies to \"I have guild business.\"");
}
File.WriteAllText(Path.Combine(npcsDir, "build", "clerk_reply_lines.json"), JsonSerializer.Serialize(helloLines.Select(l => new { key = l.Key, npc = l.Clerk,
    voice = cache.Resolve<IVoiceTypeGetter>(Hall(l.Clerk).Voice.FormKey).EditorID, info = $"{l.Id:X8}", quest = clerkQuest.EditorID, topic = l.Topic, text = l.Text }),
    new JsonSerializerOptions { WriteIndented = true }));

// A voice of her own (the vanilla lines too, in the clerk's own voice; Margot first, as a test):
// a voice type of our own ("voiceTypes"), allowed vanilla's default dialogue, so the game hands her vanilla's generic lines
// that test no voice type, played from the files recorded under it (vanilla_lines.json: Sound\Voice\Skyrim.esm\<it>\);
// her own lines' files move to its folder. Her own click greetings off shift and for a non-member, and her goodbyes
// ("greetings"), take the place of vanilla's. All after every record above, so nothing earlier moves.
// Only the first voice type is made here, where Margot's was when her voiced lines were built; every later one is made
// at the very end of the build (2026-10-29: Nessa's, made here, moved Margot's voiced greetings by one ID). Each NPC's
// voice is named now, so the line lists carry it.
var ownVoice = new Dictionary<string, string>();
var laterVoices = new List<(string Npc, string Ed)>();
void MakeVoice(string npc, string ed)
{
    var who = Hall(npc);
    var vt = new VoiceType(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = ed, Flags = VoiceType.Flag.AllowDefaultDialog };
    if (who.Configuration.Flags.HasFlag(NpcConfiguration.Flag.Female)) vt.Flags |= VoiceType.Flag.Female;
    mod.VoiceTypes.Add(vt);
    who.Voice.SetTo(vt);
}
if (clerkDlg.TryGetProperty("voiceTypes", out var vts))
    foreach (var v in vts.EnumerateObject())
    {
        ownVoice[v.Name] = v.Value.GetString()!;
        if (ownVoice.Count == 1) MakeVoice(v.Name, ownVoice[v.Name]);
        else laterVoices.Add((v.Name, ownVoice[v.Name]));
    }
var greetLines = new List<(string Key, string Clerk, uint Id, string Text, string Topic)>();
if (clerkDlg.TryGetProperty("greetings", out var greet) && mod.DialogTopics.FirstOrDefault(t => t.EditorID == clerkHelloEd) is { } helloTopic)
{
    var byeTopic = new DialogTopic(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = "AGHallClerkTopicGoodbye", Priority = 50, Quest = clerkQuest.ToNullableLink(),
        Category = DialogTopic.CategoryEnum.Misc, Subtype = DialogTopic.SubtypeEnum.Goodbye, SubtypeName = new RecordType("GBYE"),
    };
    var shiftOf = sched.GetProperty("npcs").EnumerateObject().ToDictionary(x => x.Name,
        x => x.Value.GetProperty("blocks").EnumerateArray().Where(b => b.GetProperty("do").GetString() == "lean")
              .Select(b => (At: b.GetProperty("at").GetInt32(), Hours: b.GetProperty("hours").GetInt32())).FirstOrDefault());
    ConditionFloat Talking() => new() { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = new IsInDialogueWithPlayerConditionData() };
    // one RANDOM group per clerk and slot, each line with its full conditions, after whatever the topic holds
    void Group(DialogTopic t, string clerk, string slot, IReadOnlyList<Condition> conds)
    {
        var texts = greet.GetProperty(clerk).GetProperty(slot).EnumerateArray().Select(x => x.GetString()!).ToList();
        for (var k = 0; k < texts.Count; k++)
        {
            var info = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE)
            {
                EditorID = $"AGHallInfo_{clerk}_{slot}{k + 1}",
                Flags = new DialogResponseFlags { Flags = DialogResponses.Flag.Random | (k == texts.Count - 1 ? DialogResponses.Flag.RandomEnd : 0) },
            };
            info.Responses.Add(new DialogResponse { Text = texts[k], Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
            foreach (var c in conds) info.Conditions.Add(c.DeepCopy());
            if (t.Responses.Count > 0) info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(t.Responses[^1].FormKey);
            t.Responses.Add(info);
            greetLines.Add(($"{clerk}:{slot}{k + 1}", clerk, info.FormKey.ID, texts[k], t.EditorID!));
        }
    }
    foreach (var c in greet.EnumerateObject())
    {
        var at = At(Hall(c.Name));
        var (from, hours) = shiftOf[c.Name];
        if (c.Value.TryGetProperty("helloOff", out _))   // a member clicks on her outside her shift (before it OR from its end)
            Group(helloTopic, c.Name, "helloOff", at.Concat(new Condition[] { GlobalIs(gRegistered, CompareOperator.EqualTo, 1), Talking(),
                new ConditionFloat { CompareOperator = CompareOperator.LessThan, ComparisonValue = from, Data = new GetCurrentTimeConditionData(), Flags = Condition.Flag.OR },
                new ConditionFloat { CompareOperator = CompareOperator.GreaterThanOrEqualTo, ComparisonValue = from + hours, Data = new GetCurrentTimeConditionData() } }).ToList());
        if (c.Value.TryGetProperty("helloNew", out _))   // someone not yet a member clicks on her, any time
            Group(helloTopic, c.Name, "helloNew", at.Concat(new Condition[] { GlobalIs(gRegistered, CompareOperator.EqualTo, 0), Talking() }).ToList());
        if (c.Value.TryGetProperty("goodbye", out _))
            Group(byeTopic, c.Name, "goodbye", at.ToList());
    }
    if (byeTopic.Responses.Count > 0) mod.DialogTopics.Add(byeTopic);
    CheckTakes(greetLines.Select(l => (l.Key, l.Id)));
    Console.WriteLine($"clerk own voice: {string.Join(", ", ownVoice.Select(kv => $"{kv.Key} {kv.Value}"))}; {greetLines.Count} own greetings and goodbyes");
}
string VoiceOf(string npc) => ownVoice.TryGetValue(npc, out var v) ? v : cache.Resolve<IVoiceTypeGetter>(Hall(npc).Voice.FormKey).EditorID!;
File.WriteAllText(Path.Combine(npcsDir, "build", "clerk_greeting_lines.json"), JsonSerializer.Serialize(greetLines.Select(l => new { key = l.Key, npc = l.Clerk,
    voice = VoiceOf(l.Clerk), info = $"{l.Id:X8}", quest = clerkQuest.EditorID, topic = l.Topic, text = l.Text }), new JsonSerializerOptions { WriteIndented = true }));

// The clerks' answers to AG's own "What's Guild work like around here?" ("about": the hall's area, Riverwood and Whiterun
// Hold), and their idles ("idles": what each says to herself when the player is near).
// One RANDOM group per clerk in each topic. After every record above.
var extraLines = new List<(string Key, string Clerk, uint Id, string Text, string Topic)>();
// Idles only while she is up and the player can be seen (at 03:30 they talked constantly, heard a
// floor below; the SkyrimNet log had a clerk's idle every 16 seconds, from up to 780 away): between her waking and her bedtime
// by schedules.json, not asleep (she can lie awake), in line of sight of the player, and each line waits four game hours
// (vanilla's idles wait 0.2 to 2; these are personal lines, which wear out sooner).
// (they still ran through all six and stopped. A line's wait is its own, and the engine asks for an idle every
// 10-20 seconds, fIdleChatterCommentTimer, so a pool with no chance on it empties in a minute and a half. Vanilla's idles roll
// GetRandomPercent, 25% at most; here 1% a line, rolled per line, so six lines speak about every four minutes.)
Condition[] Idling(string clerk)
{
    var bed = sched.GetProperty("npcs").GetProperty(clerk).GetProperty("blocks").EnumerateArray().First(x => x.GetProperty("do").GetString() == "sleep");
    var (asleep, wake) = (bed.GetProperty("at").GetInt32(), (bed.GetProperty("at").GetInt32() + bed.GetProperty("hours").GetInt32()) % 24);
    if (asleep == 0) asleep = 24;   // (bed at midnight, as Caralion's: awake from waking until 24, not "before 0", which is never)
    var los = new GetLineOfSightConditionData();
    los.Target.Link.SetTo(new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x14));
    // (a day that crosses midnight, as Cassius's does: awake from his waking OR before his bedtime)
    return new Condition[] { Hour(CompareOperator.GreaterThanOrEqualTo, wake, asleep < wake), Hour(CompareOperator.LessThan, asleep),
        new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 0, Data = new GetSleepingConditionData() },
        new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = los },
        new ConditionFloat { CompareOperator = CompareOperator.LessThan, ComparisonValue = 1, Data = new GetRandomPercentConditionData() } };
}
void RandomGroup(DialogTopic t, string clerk, string slot, IEnumerable<string> texts, Condition[]? extra = null, float resetHours = 0)
{
    var list = texts.ToList();
    for (var k = 0; k < list.Count; k++)
    {
        var info = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE)
        {
            EditorID = $"AGHallInfo_{clerk}_{slot}{k + 1}",
            Flags = new DialogResponseFlags { Flags = DialogResponses.Flag.Random | (k == list.Count - 1 ? DialogResponses.Flag.RandomEnd : 0), ResetHours = resetHours },
        };
        info.Responses.Add(new DialogResponse { Text = list[k], Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
        info.Conditions.AddRange(At(Hall(clerk)));
        if (extra != null) info.Conditions.AddRange(extra);
        if (t.Responses.Count > 0) info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(t.Responses[^1].FormKey);
        t.Responses.Add(info);
        extraLines.Add(($"{clerk}:{slot}{k + 1}", clerk, info.FormKey.ID, list[k], t.EditorID!));
    }
}
if (clerkDlg.TryGetProperty("about", out var aboutDlg))
{
    var b = NewBranch("About");
    var t = NewTopic(b, "About", Prompt("about"));
    b.StartingTopic.SetTo(t.FormKey);
    // members only (the hall's talk that assumes a new member is hidden until the player joins)
    foreach (var c in aboutDlg.EnumerateObject()) RandomGroup(t, c.Name, "about", c.Value.EnumerateArray().Select(x => x.GetString()!),
        new Condition[] { GlobalIs(gRegistered, CompareOperator.EqualTo, 1) });
}
if (clerkDlg.TryGetProperty("idles", out var idleDlg))
{
    var t = new DialogTopic(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = "AGHallClerkTopicIdle", Priority = 50, Quest = clerkQuest.ToNullableLink(),
        Category = DialogTopic.CategoryEnum.Misc, Subtype = DialogTopic.SubtypeEnum.Idle, SubtypeName = new RecordType("IDLE"),
    };
    foreach (var c in idleDlg.EnumerateObject()) RandomGroup(t, c.Name, "idle", c.Value.EnumerateArray().Select(x => x.GetString()!), Idling(c.Name), 4);
    mod.DialogTopics.Add(t);
}
CheckTakes(extraLines.Select(l => (l.Key, l.Id)));
File.WriteAllText(Path.Combine(npcsDir, "build", "clerk_extra_lines.json"), JsonSerializer.Serialize(extraLines.Select(l => new { key = l.Key, npc = l.Clerk,
    voice = VoiceOf(l.Clerk), info = $"{l.Id:X8}", quest = clerkQuest.EditorID, topic = l.Topic, text = l.Text }), new JsonSerializerOptions { WriteIndented = true }));
if (extraLines.Count > 0) Console.WriteLine($"clerk about and idles: {extraLines.Count} lines");
// the later voice types (see MakeVoice): after every other record. Anything new goes after these.
foreach (var (npc, ed) in laterVoices) MakeVoice(npc, ed);
// After hours: "I have guild business." stays, and off shift she sends the player to the other
// clerk if she is working, or says when the counter opens. One line each ("afterHours": no alternates). Neither is a Goodbye
// and neither has the counter's fragment: AG's line watcher opens the counter on a business line flagged Goodbye (End
// Scene). A non-member has no business topic, so their "join" gets the same line, shared (DNAM, vanilla's way, as the
// twins share "Of course."), so one voice file serves both. After every record above.
var hoursLines = new List<(string Key, string Clerk, uint Id, string Text, string Topic)>();
if (clerkDlg.TryGetProperty("afterHours", out var hoursDlg))
{
    var regTopic = mod.DialogTopics.First(t => t.EditorID == "AGHallClerkTopicRegister");
    var names = hoursDlg.EnumerateObject().Select(c => c.Name).ToList();
    var (open, close) = (names.Min(n => ShiftOf(n).At), names.Max(n => ShiftOf(n).End));
    void AfterHours(string clerk, string slot, string text, Condition[] when)
    {
        var who = Hall(clerk);
        var info = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = $"AGHallInfo_{clerk}_{slot}1", Flags = new DialogResponseFlags() };
        info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
        info.Conditions.AddRange(At(who));
        info.Conditions.Add(GlobalIs(gRegistered, CompareOperator.EqualTo, 1));
        info.Conditions.AddRange(when);
        info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(clerkTopic.Responses[^1].FormKey);
        clerkTopic.Responses.Add(info);
        hoursLines.Add(($"{clerk}:{slot}1", clerk, info.FormKey.ID, text, clerkTopic.EditorID!));
        var join = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE)
        {
            EditorID = $"AGHallInfo_{clerk}_{slot}Join", Flags = new DialogResponseFlags(),
            ResponseData = new FormLinkNullable<IDialogResponsesGetter>(info.FormKey),
        };
        join.Conditions.AddRange(At(who));
        join.Conditions.Add(GlobalIs(gRegistered, CompareOperator.EqualTo, 0));
        join.Conditions.AddRange(when);
        join.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(regTopic.Responses[^1].FormKey);
        regTopic.Responses.Add(join);
    }
    foreach (var c in hoursDlg.EnumerateObject())
    {
        var mine = ShiftOf(c.Name);
        var other = ShiftOf(names.First(n => n != c.Name));
        // the hours the other clerk works and she doesn't: after her shift or before it
        var (from, to) = other.End > mine.End ? (mine.End, other.End) : (other.At, mine.At);
        // ("she has the counter now" only while she is in the hall: otherwise this clerk keeps the counter, OnShift's cover)
        AfterHours(c.Name, "otherClerk", c.Value.GetProperty("otherClerk").GetString()!,
            new Condition[] { Hour(CompareOperator.GreaterThanOrEqualTo, from), Hour(CompareOperator.LessThan, to),
            }.Concat(InHall(names.First(n => n != c.Name))).ToArray());
        AfterHours(c.Name, "closed", c.Value.GetProperty("closed").GetString()!,
            new Condition[] { Hour(CompareOperator.LessThan, open, or: true), Hour(CompareOperator.GreaterThanOrEqualTo, close) });
    }
    Console.WriteLine($"clerk after hours: {hoursLines.Count} lines; the counter's hours {open}-{close}");
}
CheckTakes(hoursLines.Select(l => (l.Key, l.Id)));
File.WriteAllText(Path.Combine(npcsDir, "build", "clerk_hours_lines.json"), JsonSerializer.Serialize(hoursLines.Select(l => new { key = l.Key, npc = l.Clerk,
    voice = VoiceOf(l.Clerk), info = $"{l.Id:X8}", quest = clerkQuest.EditorID, topic = l.Topic, text = l.Text }), new JsonSerializerOptions { WriteIndented = true }));
// The counter exchanges: two clerks chatting while their shifts overlap. Vanilla's
// way, measured on the Sleeping Giant's (DialogueRiverwoodSleepingGiantScene8 and 784 like it): each is a quest of its own,
// started by the engine's Actor Dialogue event (ADIA) when two NPCs near each other are free to talk, its scene beginning
// with the quest and ending it; Actor1 and Actor2 are the event's two speakers, by ID; the scene runs on unique-actor aliases.
// The Story Manager picks one. Riverwood's nodes hang under the hold's, by location; the hall's are a branch of their own near
// the top of the event's children, so generic chatter does not take the event first, held to this cell and the overlap by
// the branch's conditions. An exchange that names someone needs them alive and in the hall: each such group is its own
// quest node, as a node's conditions are the ones the Story Manager reads. Each waits a game day before it can play again.
var chatLines = new List<(string Key, string Clerk, uint Id, string Text, string Topic, string Quest)>();
if (clerkDlg.TryGetProperty("chats", out var chats))
{
    var (margot, nessa) = (Hall("AGHallClerkDay"), Hall("AGHallClerkEvening"));
    var overlap = (From: Math.Max(ShiftOf("AGHallClerkDay").At, ShiftOf("AGHallClerkEvening").At), To: Math.Min(ShiftOf("AGHallClerkDay").End, ShiftOf("AGHallClerkEvening").End));
    var sample = Ed<IStoryManagerQuestNodeGetter>("RiverwoodSleepingGiantScenes").Conditions[0].Data;   // how vanilla names the event's data
    T Event<T>(T d) where T : ConditionData { d.RunOnType = sample.RunOnType; d.RunOnTypeIndex = sample.RunOnTypeIndex; return d; }
    Condition Present(FormKey placed, ConditionData d, float want) { d.RunOnType = Condition.RunOnType.Reference; d.Reference.SetTo(placed); return new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = want, Data = d }; }
    var branch = new StoryManagerBranchNode(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallChatsBranch", MaxConcurrentQuests = 1 };
    branch.Parent.SetTo(new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x015FCE));   // the Actor Dialogue event's node
    branch.PreviousSibling.SetTo(Ed<IStoryManagerBranchNodeGetter>("MainQuestPartyScenes").FormKey);
    var inCell = Event(new GetInCellConditionData()); inCell.Cell.Link.SetTo(cell.FormKey);
    branch.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = inCell });
    branch.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.GreaterThanOrEqualTo, ComparisonValue = overlap.From, Data = Event(new GetCurrentTimeConditionData()) });
    branch.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.LessThan, ComparisonValue = overlap.To, Data = Event(new GetCurrentTimeConditionData()) });
    mod.StoryManagerBranchNodes.Add(branch);
    Quest MakeChat(int n, JsonElement chat)
    {
        var q = new Quest(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = $"AGHallChat{n}", Priority = 30, Event = new RecordType("ADIA"), NextAliasID = 4 };
        foreach (var (id, name, data) in new[] { (0u, "Actor1", 12626), (1u, "Actor2", 12882) })   // the event's R1 and R2
        {
            var a = new QuestAlias { ID = id, Name = name, Type = QuestAlias.TypeEnum.Reference, Flags = 0, FindMatchingRefFromEvent = new FindMatchingRefFromEvent { FromEvent = new RecordType("ADIA"), EventData = (GetEventDataConditionData.EventMember)data } };
            foreach (var who in new[] { margot, nessa })
            {
                var isId = new GetIsIDConditionData(); isId.Object.Link.SetTo(who.FormKey);
                a.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = isId, Flags = Condition.Flag.OR });
            }
            q.Aliases.Add(a);
        }
        q.Aliases.Add(new QuestAlias { ID = 2, Name = "Margot", Type = QuestAlias.TypeEnum.Reference, Flags = QuestAlias.Flag.AllowReuseInQuest, UniqueActor = new FormLinkNullable<INpcGetter>(margot.FormKey) });
        q.Aliases.Add(new QuestAlias { ID = 3, Name = "Nessa", Type = QuestAlias.TypeEnum.Reference, Flags = QuestAlias.Flag.AllowReuseInQuest, UniqueActor = new FormLinkNullable<INpcGetter>(nessa.FormKey) });
        mod.Quests.Add(q);
        var scene = new Scene(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = $"AGHallChat{n}Scene", Flags = Scene.Flag.BeginOnQuestStart | Scene.Flag.StopQuestOnEnd | Scene.Flag.ShowAllText, Quest = q.ToNullableLink() };
        foreach (var id in new uint[] { 2, 3 })
            scene.Actors.Add(new SceneActor { ID = id, Flags = 0, BehaviorFlags = SceneActor.BehaviorFlag.DeathEnd | SceneActor.BehaviorFlag.CombatEnd | SceneActor.BehaviorFlag.DialoguePause });
        var spoken = chat.GetProperty("lines").EnumerateArray().ToList();
        for (var i = 0; i < spoken.Count; i++)
        {
            var (npc, text) = (spoken[i].GetProperty("npc").GetString()!, spoken[i].GetProperty("text").GetString()!);
            var t = new DialogTopic(NewKey(), SkyrimRelease.SkyrimSE)
            {
                EditorID = $"AGHallChat{n}Line{i + 1}", Priority = 50, Quest = q.ToNullableLink(),
                Category = DialogTopic.CategoryEnum.Scene, Subtype = DialogTopic.SubtypeEnum.Scene, SubtypeName = new RecordType("SCEN"),
            };
            var info = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = $"AGHallInfo_{npc}_chat{n}_{i + 1}", Flags = new DialogResponseFlags() };
            info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
            t.Responses.Add(info);
            mod.DialogTopics.Add(t);
            scene.Phases.Add(new ScenePhase { Name = "", Unused = new ScenePhaseUnusedData(), Unused2 = new ScenePhaseUnusedData(), EditorWidth = 200 });
            scene.Actions.Add(new SceneAction { Type = SceneAction.TypeEnum.Dialog, Name = "", ActorID = npc == "AGHallClerkDay" ? 2 : 3, Index = (uint)(i + 1), StartPhase = (uint)i, EndPhase = (uint)i,
                Topic = new FormLinkNullable<IDialogTopicGetter>(t.FormKey), HeadtrackActorID = -1, LoopingMax = 10, LoopingMin = 1, Emotion = Emotion.Neutral, EmotionValue = 0 });
            chatLines.Add(($"{npc}:chat{n}_{i + 1}", npc, info.FormKey.ID, text, t.EditorID!, q.EditorID!));
        }
        scene.LastActionIndex = (uint)spoken.Count;
        mod.Scenes.Add(scene);
        return q;
    }
    // one quest node per "needs" (named people first: a node that cannot run leaves the event to the next)
    var groups = chats.EnumerateArray().Select((c, i) => (Chat: c, N: i + 1, Needs: string.Join(",", c.GetProperty("needs").EnumerateArray().Select(x => x.GetString()))))
        .GroupBy(x => x.Needs).OrderBy(g => g.Key == "" ? 1 : 0).ToList();
    FormKey? prev = null;
    foreach (var g in groups)
    {
        var node = new StoryManagerQuestNode(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = $"AGHallChats{(g.Key == "" ? "Clerks" : g.Key.Replace("AGHall", ""))}", Flags = StoryManagerQuestNode.Flag.Random };
        node.Parent.SetTo(branch.FormKey);
        if (prev is { } p) node.PreviousSibling.SetTo(p);
        foreach (var ed in g.Key.Split(',', StringSplitOptions.RemoveEmptyEntries))
        {
            var named = cell.Persistent.OfType<PlacedNpc>().First(r => r.EditorID == ed + "Ref").FormKey;
            node.Conditions.Add(Present(named, new GetDeadConditionData(), 0));
            var there = new GetInCellConditionData(); there.Cell.Link.SetTo(cell.FormKey);
            node.Conditions.Add(Present(named, there, 1));
        }
        foreach (var c in g) node.Quests.Add(new StoryManagerQuest { Quest = new FormLinkNullable<IQuestGetter>(MakeChat(c.N, c.Chat).FormKey), HoursUntilReset = 24 });
        mod.StoryManagerQuestNodes.Add(node);
        prev = node.FormKey;
    }
    Console.WriteLine($"clerk exchanges: {chatLines.Count} lines in {chats.GetArrayLength()} scenes, {overlap.From}-{overlap.To}, {groups.Count} nodes");
}
CheckTakes(chatLines.Select(l => (l.Key, l.Id)));
File.WriteAllText(Path.Combine(npcsDir, "build", "clerk_chat_lines.json"), JsonSerializer.Serialize(chatLines.Select(l => new { key = l.Key, npc = l.Clerk,
    voice = VoiceOf(l.Clerk), info = $"{l.Id:X8}", quest = l.Quest, topic = l.Topic, text = l.Text }), new JsonSerializerOptions { WriteIndented = true }));
// the line lists written above named each clerk's voice type before she got her own: name the one her files now live under
foreach (var f in new[] { "clerk_lines.json", "clerk_topic_lines.json", "clerk_reply_lines.json" })
{
    var p = Path.Combine(npcsDir, "build", f);
    var arr = System.Text.Json.Nodes.JsonNode.Parse(File.ReadAllText(p))!.AsArray();
    foreach (var n in arr) if (ownVoice.TryGetValue(n!["npc"]!.GetValue<string>(), out var v)) n["voice"] = v;
    File.WriteAllText(p, arr.ToJsonString(new JsonSerializerOptions { WriteIndented = true }));
}

// The other five staff's standard lines (staff_dialogue.json): greetings, goodbyes, idles
// and the Guild work answers, in the clerks' own topics, one RANDOM group per NPC and slot. Willem greets by the player's
// rank; Cassius and Brynja on and off shift; someone not yet a member gets helloNew at any hour. Willem's taunts test a
// vanilla voice type there, so his are in a topic of our own (vanilla's exact words).
// After every record above, and the voice types after those: anything new goes after these.
// Held out of the plugin until each of their voice files is in build/Sound (the hall session, 2026-11-01): a voice type with
// no files leaves the NPC silent, and the hall rebuilds all through a walk. Being the last records, they keep their IDs
// either way, and the first merge after the recording takes them in. AG_STAFF_BUILD=1 builds them regardless, which is how
// a new line gets the ID its voice file is named after; staff_lines.json is left alone by a build that holds them out.
var staffLines = new List<(string Key, string Clerk, uint Id, string Text, string Topic)>();
var staffPath = Path.Combine(npcsDir, "staff_dialogue.json");
bool StaffRecorded()
{
    if (Environment.GetEnvironmentVariable("AG_STAFF_BUILD") == "1") return true;
    var d = JsonDocument.Parse(File.ReadAllText(staffPath)).RootElement;
    var vanillaLines = JsonDocument.Parse(File.ReadAllText(Path.Combine(npcsDir, "..", "..", "hall-private", "npcs", "vanilla_lines.json"))).RootElement.GetProperty("lines").EnumerateArray().ToList();
    int Fuz(string plugin, string vt)
    {
        var dir = Path.Combine(npcsDir, "build", "Sound", "Voice", plugin, vt);
        return Directory.Exists(dir) ? Directory.GetFiles(dir, "*.fuz").Length : 0;
    }
    var missing = 0;
    foreach (var v in d.GetProperty("voiceTypes").EnumerateObject())
    {
        var vt = v.Value.GetString()!;
        missing += Math.Max(0, d.GetProperty("lines").GetProperty(v.Name).EnumerateObject().Count() - Fuz(hall.ModKey.FileName, vt));
        // each vanilla line's own file, under its own plugin and voice (vanilla_lines.json names both): counting Skyrim.esm's
        // folder alone took Brynja's HearthFires lines for missing files and held every staff voice out (2026-11-06)
        missing += vanillaLines.Count(l => l.GetProperty("npc").GetString() == v.Name && !File.Exists(Path.Combine(npcsDir, "build", "Sound",
            "Voice", l.GetProperty("plugin").GetString()!, l.GetProperty("voice").GetString()!, l.GetProperty("file").GetString()!)));
    }
    if (missing > 0) Console.WriteLine($"WARNING staff lines held out of this build: {missing} voice files not in build/Sound yet; the five keep their vanilla voices");
    return missing == 0;
}
if (File.Exists(staffPath) && StaffRecorded())
{
    var staffDlg = JsonDocument.Parse(File.ReadAllText(staffPath)).RootElement;
    foreach (var v in staffDlg.GetProperty("voiceTypes").EnumerateObject()) ownVoice[v.Name] = v.Value.GetString()!;
    DialogTopic Topic(string ed) => mod.DialogTopics.First(t => t.EditorID == ed);
    var (helloT, byeT, idleT) = (Topic(clerkHelloEd), Topic("AGHallClerkTopicGoodbye"), Topic("AGHallClerkTopicIdle"));
    // The staff's about lines answer a question of their own ("What's Guild work like around
    // here?" is the clerks' alone): Willem and Merila "Tell me about the Adventurers Guild.", the cook, barkeeper and
    // server "Tell me about the Guild Hall."; each a top-level choice like the clerks' About, in the second block at
    // 0x1800-0x180F (merged 0x9000-). The lines keep their IDs and voice files: a file is named for the topic's first 15
    // characters, "AGHallClerkTopi", the same for every one of these topics.
    var aboutOf = new Dictionary<string, DialogTopic>();
    InIds(0x1800, 0x1810, "the about questions", () =>
    {
        foreach (var g in staffDlg.GetProperty("aboutTopics").EnumerateObject().Where(g => !g.Name.StartsWith("_")))
        {
            var b = NewBranch("About" + g.Name);
            var t = NewTopic(b, "About" + g.Name, g.Value.GetProperty("prompt").GetString()!);
            b.StartingTopic.SetTo(t.FormKey);
            foreach (var n in g.Value.GetProperty("npcs").EnumerateArray()) aboutOf.Add(n.GetString()!, t);
        }
        return 0;
    });
    var tauntModel = vanilla.SelectMany(m => m.DialogTopics).First(t => t.SubtypeName == new RecordType("TAUT"));
    var tauntT = new DialogTopic(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = "AGHallClerkTopicTaunt", Priority = tauntModel.Priority, Quest = clerkQuest.ToNullableLink(),
        Category = tauntModel.Category, Subtype = tauntModel.Subtype, SubtypeName = tauntModel.SubtypeName,
    };
    ConditionFloat Member(int v) => GlobalIs(gRegistered, CompareOperator.EqualTo, v);
    ConditionFloat Talking() => new() { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = new IsInDialogueWithPlayerConditionData() };
    // one RANDOM group: each line with its full conditions, after whatever the topic holds
    void StaffPool(DialogTopic t, string npc, List<(string Slot, string Text, Condition[] Conds)> group, float resetHours = 0)
    {
        for (var k = 0; k < group.Count; k++)
        {
            var info = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE)
            {
                EditorID = $"AGHallInfo_{npc}_{group[k].Slot}",
                Flags = new DialogResponseFlags { Flags = DialogResponses.Flag.Random | (k == group.Count - 1 ? DialogResponses.Flag.RandomEnd : 0), ResetHours = resetHours },
            };
            info.Responses.Add(new DialogResponse { Text = group[k].Text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
            foreach (var c in group[k].Conds) info.Conditions.Add(c.DeepCopy());
            if (t.Responses.Count > 0) info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(t.Responses[^1].FormKey);
            t.Responses.Add(info);
            staffLines.Add(($"{npc}:{group[k].Slot}", npc, info.FormKey.ID, group[k].Text, t.EditorID!));
        }
    }
    void Person(JsonProperty person)
    {
        var npc = person.Name;
        var who = Hall(npc);
        var mine = person.Value.EnumerateObject().Select(l => (Slot: l.Name, Stem: l.Name.TrimEnd("0123456789".ToCharArray()), Text: l.Value.GetString()!)).ToList();
        var at = At(who);
        var member = at.Concat(new Condition[] { Member(1), Talking() }).ToArray();
        List<(string, string, Condition[])> Lines(string stem, IEnumerable<Condition> conds) =>
            mine.Where(l => l.Stem == stem).Select(l => (l.Slot, l.Text, conds.ToArray())).ToList();
        // (a resident, Caralion, has no shift: only helloOn/helloOff need one)
        var shift = sched.GetProperty("npcs").GetProperty(npc).GetProperty("blocks").EnumerateArray()
            .Where(b => b.GetProperty("do").GetString() is "lean" or "work").Select(b => (From: b.GetProperty("at").GetInt32(), To: b.GetProperty("at").GetInt32() + b.GetProperty("hours").GetInt32()))
            .DefaultIfEmpty((From: -1, To: -1)).First();
        if (shift.From < 0 && mine.Any(l => l.Stem is "helloOn" or "helloOff")) throw new Exception($"staff_dialogue.json: {npc} has on/off-shift lines but no shift in schedules.json");
        var (on, off) = shift.To <= 24
            ? (new Condition[] { Hour(CompareOperator.GreaterThanOrEqualTo, shift.From), Hour(CompareOperator.LessThan, shift.To) },
               new Condition[] { Hour(CompareOperator.LessThan, shift.From, true), Hour(CompareOperator.GreaterThanOrEqualTo, shift.To) })
            : (new Condition[] { Hour(CompareOperator.GreaterThanOrEqualTo, shift.From, true), Hour(CompareOperator.LessThan, shift.To - 24) },
               new Condition[] { Hour(CompareOperator.GreaterThanOrEqualTo, shift.To - 24), Hour(CompareOperator.LessThan, shift.From) });
        StaffPool(helloT, npc, Lines("helloNew", at.Concat(new Condition[] { Member(0), Talking() })));
        if (mine.Any(l => l.Stem == "helloLow"))   // Willem: ranks E and D, each higher rank's own line, and the any-rank lines, one group
            StaffPool(helloT, npc, Lines("helloLow", member.Append(GlobalIs(gRank, CompareOperator.LessThanOrEqualTo, 1)))
                .Concat(new[] { ("rankC", 2), ("rankB", 3), ("rankA", 4), ("rankS", 5) }.SelectMany(r => Lines(r.Item1, member.Append(GlobalIs(gRank, CompareOperator.EqualTo, r.Item2)))))
                .Concat(Lines("anyRank", member)).ToList());
        if (mine.Any(l => l.Stem == "hello")) StaffPool(helloT, npc, Lines("hello", member));
        if (mine.Any(l => l.Stem == "helloOn"))
        {
            StaffPool(helloT, npc, Lines("helloOn", member.Concat(on)));
            StaffPool(helloT, npc, Lines("helloOff", member.Concat(off)));
        }
        StaffPool(byeT, npc, Lines("goodbye", at));
        if (aboutOf.TryGetValue(npc, out var aboutT)) StaffPool(aboutT, npc, Lines("about", at));
        else foreach (var _ in Lines("about", at)) NewKey();   // no answer for them (Caralion): the IDs stay reserved
        StaffPool(idleT, npc, Lines("idle", at.Concat(Idling(npc))), 4);
        if (mine.Any(l => l.Stem == "taunt")) StaffPool(tauntT, npc, Lines("taunt", at.Take(1)));
    }
    foreach (var person in staffDlg.GetProperty("lines").EnumerateObject()) Person(person);
    mod.DialogTopics.Add(tauntT);
    CheckTakes(staffLines.Select(l => (l.Key, l.Id)));
    Console.WriteLine($"staff lines: {staffLines.Count} for {staffDlg.GetProperty("lines").EnumerateObject().Count()} staff");
    foreach (var v in staffDlg.GetProperty("voiceTypes").EnumerateObject()) MakeVoice(v.Name, v.Value.GetString()!);
    File.WriteAllText(Path.Combine(npcsDir, "build", "staff_lines.json"), JsonSerializer.Serialize(staffLines.Select(l => new { key = l.Key, npc = l.Clerk,
        voice = VoiceOf(l.Clerk), info = $"{l.Id:X8}", quest = clerkQuest.EditorID, topic = l.Topic, text = l.Text }), new JsonSerializerOptions { WriteIndented = true }));

    // The three followers' standard lines and their own voice types (follower_dialogue.json),
    // in an ID block of their own (0x1900-0x19FF, merged 0x9100-) so nothing else moves whether or not they
    // are built. Built only once they go live ("live": true, or AG_FOLLOWER_VOICES=1 for the recording build): their own
    // voice type takes them off vanilla's follower voice lists until the DLL adds the new voices to them, and a voice type
    // with no files leaves them silent. A live build with any file missing holds them out, and the merge's hold gate stops.
    var followerPath = Path.Combine(npcsDir, "follower_dialogue.json");
    if (File.Exists(followerPath))
    {
        var fDlg = JsonDocument.Parse(File.ReadAllText(followerPath)).RootElement;
        var live = Environment.GetEnvironmentVariable("AG_FOLLOWER_VOICES") == "1" || (fDlg.TryGetProperty("live", out var lv) && lv.GetBoolean());
        if (!live) Console.WriteLine("followers' lines and voices: not live (follower_dialogue.json \"live\"; AG_FOLLOWER_VOICES=1 to build them for recording)");
        else
        {
            var before = staffLines.Count;
            InIds(0x1900, 0x1A00, "the followers' lines", () =>
            {
                foreach (var v in fDlg.GetProperty("voiceTypes").EnumerateObject()) ownVoice[v.Name] = v.Value.GetString()!;
                foreach (var person in fDlg.GetProperty("lines").EnumerateObject()) Person(person);
                foreach (var v in fDlg.GetProperty("voiceTypes").EnumerateObject()) MakeVoice(v.Name, v.Value.GetString()!);
                return 0;
            });
            var mineF = staffLines.Skip(before).ToList();
            // a voice file is named as vanilla names one: quest and topic cut to 25 characters together, the INFO's ID, the part
            string FollowerFile(string topic, uint id)
            {
                var (q, t) = (clerkQuest.EditorID!, topic);
                if (q.Length + t.Length > 25) { q = q[..10]; t = t[..Math.Min(t.Length, 25 - q.Length)]; }
                return $"{q}_{t}_{id:X8}_1.fuz".ToLowerInvariant();
            }
            File.WriteAllText(Path.Combine(npcsDir, "build", "follower_lines.json"), JsonSerializer.Serialize(mineF.Select(l => new { key = l.Key, npc = l.Clerk,
                voice = VoiceOf(l.Clerk), info = $"{l.Id:X8}", quest = clerkQuest.EditorID, topic = l.Topic, text = l.Text }), new JsonSerializerOptions { WriteIndented = true }));
            var fMissing = mineF.Count(l => !File.Exists(Path.Combine(npcsDir, "build", "Sound", "Voice", hall.ModKey.FileName, VoiceOf(l.Clerk),
                FollowerFile(l.Topic, l.Id))));
            if (fMissing > 0 && Environment.GetEnvironmentVariable("AG_FOLLOWER_VOICES") != "1")
                Console.WriteLine($"WARNING followers' lines held out of this build: {fMissing} of {mineF.Count} voice files not in build/Sound yet");
            Console.WriteLine($"followers' lines: {mineF.Count} for {fDlg.GetProperty("lines").EnumerateObject().Count()} followers");

            // THE FOLLOWERS' OWN FOLLOWER DIALOGUE. Their own voice
            // types cost them every follower choice wherever a dialogue mod ties vanilla's follower lines to exact voice types
            // (Relationship Dialogue Overhaul does, for every humanoid line). So, as Sofia, Inigo and Lucien do, they get their own
            // follower quest: a copy of each vanilla follower topic and branch they speak in (same prompt, type, priority), holding
            // their recorded vanilla lines (vanilla_lines.json, DialogueFollower and DialogueFavorGeneric) as INFOs of ours: the
            // winning vanilla INFO with its voice-type tests swapped for GetIsID, its links pointed at our copies, and its
            // fragment done by AGHallFollowerTIF through vanilla's follower quest (so NFF still takes over). The DLL no longer adds
            // their voices to the Orc/Rough/Neutral follower lists (GuildHall.cpp), so vanilla's own follower topics never match
            // them and no choice appears twice. Spoken from the recorded takes (copyOf, no credits). Fixed IDs 0x1A80-0x1AFF
            // (merged 0x9280-0x92FF); held out until every copied file is in build/Sound (AG_FOLLOWER_VOICES=1 builds them).
            var vPath = Path.Combine(npcsDir, "..", "..", "hall-private", "npcs", "vanilla_lines.json");
            var folk = fDlg.GetProperty("voiceTypes").EnumerateObject().Select(v => v.Name).ToHashSet();
            var skyrimKey = ModKey.FromFileName("Skyrim.esm");
            var cmdSrc = JsonDocument.Parse(File.ReadAllText(vPath)).RootElement.GetProperty("lines").EnumerateArray()
                .Where(l => folk.Contains(l.GetProperty("npc").GetString()!) && l.GetProperty("plugin").GetString() == "Skyrim.esm"
                            && l.GetProperty("vanillaTopic").GetString() is "DialogueFollower" or "DialogueFavorGeneric")
                .Select(l => (Key: l.GetProperty("key").GetString()!, Npc: l.GetProperty("npc").GetString()!, Text: l.GetProperty("text").GetString()!,
                              Info: new FormKey(skyrimKey, Convert.ToUInt32(l.GetProperty("key").GetString()!.Split(':')[2], 16))))
                .ToList();
            var wanted = cmdSrc.Select(s => s.Info).ToHashSet();
            var topicOf = new Dictionary<FormKey, FormKey>();
            foreach (var t in vanilla[0].DialogTopics)
                foreach (var r in t.Responses)
                    if (wanted.Contains(r.FormKey)) topicOf[r.FormKey] = t.FormKey;
            // the player's words for each choice topic (Skyrim.esm keeps them in its strings files; these are vanilla's own)
            var prompts = new Dictionary<uint, string>
            {
                [0x0B0EE6] = "Follow me. I need your help.", [0x075083] = "Follow me.", [0x075084] = "Wait here.",
                [0x060020] = "I need to trade some things with you.", [0x026E0E] = "I need you to do something.",
                [0x026DFF] = "Yes. Let me show you.", [0x026DFD] = "No. Never mind.", [0x05C80C] = "It's time for us to part ways.",
            };
            // what vanilla's fragment in each choice topic does (Skyrim.esm's TIF__ sources, one action per topic)
            var actions = new Dictionary<uint, string>
            {
                [0x0B0EE6] = "Fragment_Recruit", [0x075083] = "Fragment_Follow", [0x075084] = "Fragment_Wait", [0x060020] = "Fragment_Trade",
                [0x026E0E] = "Fragment_FavorStart", [0x026DFD] = "Fragment_FavorEnd", [0x05C80C] = "Fragment_Dismiss",
            };
            var dialogueFollower = new FormKey(skyrimKey, 0x0750BA);
            var raceLists = new[] { 0x0D8E1Eu, 0x0D23AEu, 0x0D23ACu }.Select(i => new FormKey(skyrimKey, i)).ToHashSet();   // VoicesFollowerOrc / Rough / Neutral
            var maleKhajiit = new FormKey(skyrimKey, 0x013AEC);   // the MaleKhajiit voice type: vanilla's Khajiit followers' own lines test it exactly
            var followerVoice = new Dictionary<string, FormKey> {
                ["AGHallResidentOrc"] = new FormKey(skyrimKey, 0x0D8E1E), ["AGHallResidentRanger"] = new FormKey(skyrimKey, 0x0D23AE), ["AGHallResidentScout"] = maleKhajiit };
            var dismissed = Ed<IFactionGetter>("DismissedFollowerFaction").FormKey;
            // their road helmets (outfits kept, gaps filled), matching what each wears
            // (none for Zhasim or Ylva: a helmet looked wrong on both)
            var helmets = new Dictionary<string, string> { ["AGHallResidentOrc"] = "ArmorOrcishHelmet" };
            var cmdLines = new List<(string Key, string Npc, uint Id, string Text, string Topic, string? CopyOf)>();   // CopyOf null: a new line, recorded
            var myTopics = new Dictionary<FormKey, DialogTopic>();
            var myBranches = new Dictionary<FormKey, DialogBranch>();
            Quest? fQuest = null;
            var fInfos = new List<(DialogResponses Mine, IDialogResponsesGetter Src)>();
            InIds(0x1A80, 0x1B00, "the followers' own follower dialogue", () =>
            {
                var vq = cache.Resolve<IQuestGetter>(dialogueFollower);
                fQuest = new Quest(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallFollowerQuest", Flags = Quest.Flag.StartGameEnabled, Priority = vq.Priority };
                foreach (var s in cmdSrc)
                {
                    if (!topicOf.TryGetValue(s.Info, out var tKey)) throw new Exception($"followers' dialogue: {s.Key} names no INFO of Skyrim.esm");
                    var src = cache.Resolve<IDialogResponsesGetter>(s.Info);   // the winning vanilla version (a DLC may fix one)
                    // only the lines the race follower lists let them speak: the rest (idles such as "Don't get too far ahead.")
                    // test no voice and still play from vanilla, in their voice. Any other voice test is a case to look at first
                    var voiceTests = src.Conditions.Select(c => c.Data).OfType<GetIsVoiceTypeConditionData>().Select(d => d.VoiceTypeOrList.Link.FormKey).ToList();
                    if (voiceTests.Count == 0) continue;
                    if (voiceTests.Any(v => !raceLists.Contains(v) && v != maleKhajiit)) throw new Exception($"followers' dialogue: {s.Key} tests a voice other than the follower voices ({string.Join(", ", voiceTests)})");
                    // each speaks what vanilla gives a follower of their voice: Zhasim the MaleKhajiit lines ("Khajiit will
                    // follow."), not the Neutral list's, as a vanilla Khajiit follower does
                    if (!voiceTests.Contains(followerVoice[s.Npc])) continue;
                    if (!myTopics.TryGetValue(tKey, out var mt))
                    {
                        var vt = cache.Resolve<IDialogTopicGetter>(tKey);
                        mt = vt.Duplicate(NewKey());
                        mt.Responses.Clear();
                        mt.EditorID = "AGHallFollower" + (vt.EditorID ?? $"{vt.SubtypeName}{tKey.ID:X6}");
                        mt.Quest.SetTo(fQuest);
                        var choice = vt.Subtype == DialogTopic.SubtypeEnum.Custom && vt.Name != null;   // (the favor's blocking topic has none: the NPC opens it)
                        if (choice && !prompts.TryGetValue(tKey.ID, out var pr)) throw new Exception($"followers' dialogue: no prompt for choice topic {vt.EditorID}");
                        mt.Name = choice ? prompts[tKey.ID] : null;
                        if (!vt.Branch.IsNull)
                        {
                            if (!myBranches.TryGetValue(vt.Branch.FormKey, out var mb))
                            {
                                var vb = cache.Resolve<IDialogBranchGetter>(vt.Branch.FormKey);
                                mb = vb.Duplicate(NewKey());
                                mb.EditorID = "AGHallFollower" + (vb.EditorID ?? $"Branch{vb.FormKey.ID:X6}");
                                mb.Quest.SetTo(fQuest);
                                myBranches[vt.Branch.FormKey] = mb;
                            }
                            mt.Branch.SetTo(mb);
                        }
                        myTopics[tKey] = mt;
                    }
                    var said = src.Responses.Count > 0 ? src.Responses : src.ResponseData.IsNull ? src.Responses : cache.Resolve<IDialogResponsesGetter>(src.ResponseData.FormKey).Responses;
                    if (said.Count != 1) throw new Exception($"followers' dialogue: {s.Key} speaks {said.Count} responses; only one was recorded");
                    if (said[0].Text.String != s.Text) throw new Exception($"followers' dialogue: {s.Key} says '{said[0].Text.String}' in vanilla, '{s.Text}' recorded");
                    var mine = src.Duplicate(NewKey());
                    mine.EditorID = $"AGHallFollower_{s.Npc}_{s.Info.ID:X6}";
                    mine.PreviousDialog.Clear();
                    mine.ResponseData.Clear();
                    mine.Responses.Clear();
                    var resp = said[0].DeepCopy(); resp.ResponseNumber = 1; mine.Responses.Add(resp);
                    // swap the voice tests for "is this NPC"; one inside an OR group would change the group's meaning
                    var conds = mine.Conditions.ToList();
                    for (var k = 0; k < conds.Count; k++)
                        if (conds[k].Data is GetIsVoiceTypeConditionData && (conds[k].Flags.HasFlag(Condition.Flag.OR) || (k > 0 && conds[k - 1].Flags.HasFlag(Condition.Flag.OR))))
                            throw new Exception($"followers' dialogue: {s.Key} tests a voice type inside an OR group");
                    mine.Conditions.Clear();
                    var isId = new GetIsIDConditionData(); isId.Object.Link.SetTo(Hall(s.Npc).FormKey);
                    mine.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = isId });
                    foreach (var c in conds) if (c.Data is not GetIsVoiceTypeConditionData) mine.Conditions.Add(c);
                    // vanilla's recruit lines test GetRelationshipRank with no target (Skyrim.esm stores 0); name the player
                    foreach (var c in mine.Conditions)
                        if (c.Data is GetRelationshipRankConditionData rr && rr.TargetNpc.Link.IsNull)
                            rr.TargetNpc.Link.SetTo(new FormKey(skyrimKey, 0x14));
                    // vanilla's fragment, done by ours on the same side of the line (begin or end)
                    if (src.VirtualMachineAdapter is { } vmad && (vmad.Scripts.Count > 0 || vmad.ScriptFragments != null))
                    {
                        if (!actions.TryGetValue(tKey.ID, out var frag)) throw new Exception($"followers' dialogue: {s.Key} has a fragment in a topic with no known action");
                        var onEnd = vmad.ScriptFragments?.OnEnd != null;
                        var sf = new ScriptFragments { FileName = "AGHallFollowerTIF" };
                        var piece = new ScriptFragment { ScriptName = "AGHallFollowerTIF", FragmentName = frag };
                        if (onEnd) sf.OnEnd = piece; else sf.OnBegin = piece;
                        mine.VirtualMachineAdapter = new DialogResponsesAdapter
                        {
                            Scripts = { new ScriptEntry { Name = "AGHallFollowerTIF", Properties = {
                                new ScriptObjectProperty { Name = "pDialogueFollower", Object = new FormLink<ISkyrimMajorRecordGetter>(dialogueFollower), Flags = ScriptProperty.Flag.Edited },
                                new ScriptObjectProperty { Name = "DismissedFollowerFaction", Object = new FormLink<ISkyrimMajorRecordGetter>(dismissed), Flags = ScriptProperty.Flag.Edited } } } },
                            ScriptFragments = sf,
                        };
                        // the road helmet, on at recruiting and off at dismissal (AGHallFollowerTIF), for those who wear one
                        if (helmets.TryGetValue(s.Npc, out var helm))
                            mine.VirtualMachineAdapter.Scripts[0].Properties.Add(new ScriptObjectProperty { Name = "Helmet",
                                Object = new FormLink<ISkyrimMajorRecordGetter>(Ed<IArmorGetter>(helm).FormKey), Flags = ScriptProperty.Flag.Edited });
                    }
                    else mine.VirtualMachineAdapter = null;
                    mt.Responses.Add(mine);
                    fInfos.Add((mine, src));
                    cmdLines.Add(($"{s.Npc}:follower:{s.Info.ID:X6}", s.Npc, mine.FormKey.ID, s.Text, mt.EditorID!, s.Key));
                }
                // links and branch starts pointed at our copies (a link to a topic we did not copy would leave our quest)
                foreach (var (mine, src) in fInfos)
                {
                    mine.LinkTo.Clear();
                    foreach (var l in src.LinkTo)
                    {
                        if (!myTopics.TryGetValue(l.FormKey, out var to)) throw new Exception($"followers' dialogue: {mine.EditorID} links to {l.FormKey}, which has no copy");
                        mine.LinkTo.Add(new FormLink<IDialogTopicGetter>(to.FormKey));
                    }
                }
                foreach (var (vKey, mb) in myBranches)
                {
                    var start = cache.Resolve<IDialogBranchGetter>(vKey).StartingTopic.FormKey;
                    if (!myTopics.TryGetValue(start, out var st)) throw new Exception($"followers' dialogue: branch {mb.EditorID} starts at {start}, which has no copy");
                    mb.StartingTopic.SetTo(st);
                }
                // WHO THEY FOLLOW (follower_dialogue.json "followGate"): Guild members only, at least
                // one rank below their own. Vanilla's "Follow me. I need your help." stays; its accept line (the one with the
                // recruit fragment) gets the bar, and beside it a refusal for each way of falling short, with the accept's own
                // vanilla conditions so it shows exactly when the accept would have. Built last, so no ID above moves.
                var recruitTopic = new FormKey(skyrimKey, 0x0B0EE6);
                if (fDlg.TryGetProperty("followGate", out var gate))
                {
                    if (!myTopics.TryGetValue(recruitTopic, out var rt)) throw new Exception("followers' dialogue: no copy of \"Follow me. I need your help.\" to gate");
                    foreach (var g in gate.EnumerateObject())
                    {
                        var accepts = fInfos.Where(f => rt.Responses.Contains(f.Mine) && f.Mine.Conditions.Any(c => c.Data is GetIsIDConditionData id && id.Object.Link.FormKey == Hall(g.Name).FormKey)
                                                         && f.Mine.VirtualMachineAdapter?.ScriptFragments is { } sf && (sf.OnBegin ?? sf.OnEnd)?.FragmentName == "Fragment_Recruit").ToList();
                        if (accepts.Count != 1) throw new Exception($"followers' dialogue: {g.Name} has {accepts.Count} recruit lines in \"Follow me. I need your help.\" (the gate expects one)");
                        var acc = accepts[0].Mine;
                        if (acc.Conditions.Count > 0 && acc.Conditions[^1].Flags.HasFlag(Condition.Flag.OR)) throw new Exception($"followers' dialogue: {acc.EditorID} ends in an OR group; the gate would join it");
                        var vanillaConds = acc.Conditions.Select(c => c.DeepCopy()).ToList();
                        var minRank = g.Value.GetProperty("minRank").GetInt32();
                        acc.Conditions.Add(GlobalIs(gRegistered, CompareOperator.EqualTo, 1));
                        if (minRank > 0) acc.Conditions.Add(GlobalIs(gRank, CompareOperator.GreaterThanOrEqualTo, minRank));
                        void Refuse(string slot, string text, params Condition[] bar)
                        {
                            var info = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = $"AGHallFollower_{g.Name}_follow{char.ToUpper(slot[0])}{slot[1..]}", Flags = acc.Flags?.DeepCopy() };
                            info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
                            info.Conditions.AddRange(vanillaConds.Select(c => c.DeepCopy()));
                            info.Conditions.AddRange(bar);
                            rt.Responses.Add(info);
                            cmdLines.Add(($"{g.Name}:new:followRefuse{char.ToUpper(slot[0])}{slot[1..]}1", g.Name, info.FormKey.ID, text, rt.EditorID!, null));
                        }
                        Refuse("new", g.Value.GetProperty("notMember").GetString()!, GlobalIs(gRegistered, CompareOperator.EqualTo, 0));
                        if (minRank > 0)
                            Refuse("rank", g.Value.GetProperty("lowRank").GetString()!, GlobalIs(gRegistered, CompareOperator.EqualTo, 1), GlobalIs(gRank, CompareOperator.LessThan, minRank));
                    }
                }
                return 0;
            });
            string CmdFile(string q, string tp, uint id)
            {
                if (q.Length + tp.Length > 25) { q = q[..10]; tp = tp[..Math.Min(tp.Length, 25 - q.Length)]; }
                return $"{q}_{tp}_{id:X8}_1.fuz".ToLowerInvariant();
            }
            File.WriteAllText(Path.Combine(npcsDir, "build", "follower_cmd_lines.json"), JsonSerializer.Serialize(cmdLines.Select(l => new { key = l.Key, npc = l.Npc,
                voice = VoiceOf(l.Npc), info = $"{l.Id:X8}", quest = fQuest!.EditorID, topic = l.Topic, text = l.Text, copyOf = l.CopyOf }), new JsonSerializerOptions { WriteIndented = true }));
            var cMissing = cmdLines.Count(l => !File.Exists(Path.Combine(npcsDir, "build", "Sound", "Voice", hall.ModKey.FileName, VoiceOf(l.Npc), CmdFile(fQuest!.EditorID!, l.Topic, l.Id))));
            if (cMissing > 0 && Environment.GetEnvironmentVariable("AG_FOLLOWER_VOICES") != "1")
                Console.WriteLine($"WARNING followers' own follower dialogue held out of this build: {cMissing} of {cmdLines.Count} voice files not in build/Sound yet");
            else
            {
                mod.Quests.Add(fQuest!);
                foreach (var b in myBranches.Values) mod.DialogBranches.Add(b);
                foreach (var t in myTopics.Values) mod.DialogTopics.Add(t);
            }
            Console.WriteLine($"followers' own follower dialogue: {cmdLines.Count} lines in {myTopics.Count} topics, {myBranches.Count} branches ({string.Join(", ", myTopics.Values.Select(t => t.EditorID))})");
        }
    }
    // The followers' contracts away (away_dialogue.json; SCHEDULES.md "Away on contract"):
    // a global per follower, 1 while away (the away quest's script sets it); "Have you seen ...?", a top-level choice shown
    // only then, answered by the clerks; and one idle per absentee from whoever would notice. Their own ID block
    // (0x1A00-0x1A7F, merged 0x9200-); built once live ("live", or AG_AWAY_BUILD=1 for the recording build).
    var awayPath = Path.Combine(npcsDir, "away_dialogue.json");
    if (File.Exists(awayPath))
    {
        var aDlg = JsonDocument.Parse(File.ReadAllText(awayPath)).RootElement;
        var aLive = Environment.GetEnvironmentVariable("AG_AWAY_BUILD") == "1" || (aDlg.TryGetProperty("live", out var al) && al.GetBoolean());
        if (!aLive) Console.WriteLine("contracts away: not live (away_dialogue.json \"live\"; AG_AWAY_BUILD=1 to build them for recording)");
        else
        {
            var beforeA = staffLines.Count;
            InIds(0x1A00, 0x1A80, "the contracts away", () =>
            {
                var gAway = new Dictionary<string, FormKey>();
                foreach (var w in aDlg.GetProperty("away").EnumerateObject())
                {
                    var g = new GlobalShort(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = w.Value.GetProperty("global").GetString()!, Data = 0 };
                    mod.Globals.Add(g);
                    gAway[w.Name] = g.FormKey;
                }
                foreach (var ch in aDlg.GetProperty("choices").EnumerateObject())
                {
                    var who = ch.Value.GetProperty("who").GetString()!;
                    var b = NewBranch(ch.Name);
                    var t = NewTopic(b, ch.Name, ch.Value.GetProperty("prompt").GetString()!);
                    b.StartingTopic.SetTo(t.FormKey);
                    foreach (var ans in aDlg.GetProperty("answers").EnumerateObject())
                        if (ans.Value.TryGetProperty(ch.Name, out var tx))
                            StaffPool(t, ans.Name, new() { ($"away{ch.Name}", tx.GetString()!, At(Hall(ans.Name)).Append(GlobalIs(gAway[who], CompareOperator.EqualTo, 1))
                                .Append(GlobalIs(gRegistered, CompareOperator.EqualTo, 1)).ToArray()) });   // members only
                }
                foreach (var idl in aDlg.GetProperty("idles").EnumerateObject())
                    StaffPool(idleT, idl.Name, new() { ("awayIdle", idl.Value.GetProperty("text").GetString()!,
                        At(Hall(idl.Name)).Concat(Idling(idl.Name)).Append(GlobalIs(gAway[idl.Value.GetProperty("about").GetString()!], CompareOperator.EqualTo, 1)).ToArray()) }, 4);
                // the quest that sends them out and brings them back (AGHallAwayScript, src/hall/papyrus): start-game, its script
                // given each follower's placed reference, away global, bunk marker and leaving weekday, the hall's cells, GameHour
                var days = new Dictionary<string, int> { ["Sundas"] = 0, ["Morndas"] = 1, ["Tirdas"] = 2, ["Middas"] = 3, ["Turdas"] = 4, ["Fredas"] = 5, ["Loredas"] = 6 };
                var folk = new ScriptObjectListProperty { Name = "Folk", Flags = ScriptProperty.Flag.Edited };
                var globs = new ScriptObjectListProperty { Name = "AwayGlobals", Flags = ScriptProperty.Flag.Edited };
                var homes = new ScriptObjectListProperty { Name = "HomeMarkers", Flags = ScriptProperty.Flag.Edited };
                var leave = new ScriptIntListProperty { Name = "LeaveDays", Flags = ScriptProperty.Flag.Edited };
                var cells = new ScriptObjectListProperty { Name = "HallCells", Flags = ScriptProperty.Flag.Edited };
                foreach (var w in aDlg.GetProperty("away").EnumerateObject())
                {
                    var npcEd = w.Value.GetProperty("npc").GetString()!;
                    var placed = cell.Persistent.OfType<PlacedNpc>().First(r => r.EditorID == npcEd + "Ref").FormKey;
                    folk.Objects.Add(new ScriptObjectProperty { Object = new FormLink<ISkyrimMajorRecordGetter>(placed) });
                    globs.Objects.Add(new ScriptObjectProperty { Object = new FormLink<ISkyrimMajorRecordGetter>(gAway[w.Name]) });
                    if (!hallNamed.TryGetValue(npcEd + "Marker", out var home)) throw new Exception($"contracts away: the hall has no {npcEd}Marker to bring {w.Name} back to");
                    homes.Objects.Add(new ScriptObjectProperty { Object = new FormLink<ISkyrimMajorRecordGetter>(home) });
                    leave.Data.Add(days[w.Value.GetProperty("leaves").GetString()!.Split(' ')[0]]);
                }
                foreach (var c in hallCells) cells.Objects.Add(new ScriptObjectProperty { Object = new FormLink<ISkyrimMajorRecordGetter>(c) });
                var awayQ = new Quest(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallAwayQuest", Flags = Quest.Flag.StartGameEnabled, Priority = 10 };
                awayQ.VirtualMachineAdapter = new QuestAdapter
                {
                    Scripts = { new ScriptEntry { Name = "AGHallAwayScript", Properties = { folk, globs, homes, leave, cells,
                        new ScriptObjectProperty { Name = "GameHour", Object = new FormLink<ISkyrimMajorRecordGetter>(new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x38)), Flags = ScriptProperty.Flag.Edited } } } },
                };
                mod.Quests.Add(awayQ);
                return 0;
            });
            var mineA = staffLines.Skip(beforeA).ToList();
            File.WriteAllText(Path.Combine(npcsDir, "build", "away_lines.json"), JsonSerializer.Serialize(mineA.Select(l => new { key = l.Key, npc = l.Clerk,
                voice = VoiceOf(l.Clerk), info = $"{l.Id:X8}", quest = clerkQuest.EditorID, topic = l.Topic, text = l.Text }), new JsonSerializerOptions { WriteIndented = true }));
            string AwayFile(string topic, uint id)
            {
                var (q, t) = (clerkQuest.EditorID!, topic);
                if (q.Length + t.Length > 25) { q = q[..10]; t = t[..Math.Min(t.Length, 25 - q.Length)]; }
                return $"{q}_{t}_{id:X8}_1.fuz".ToLowerInvariant();
            }
            var aMissing = mineA.Count(l => !File.Exists(Path.Combine(npcsDir, "build", "Sound", "Voice", hall.ModKey.FileName, VoiceOf(l.Clerk), AwayFile(l.Topic, l.Id))));
            if (aMissing > 0 && Environment.GetEnvironmentVariable("AG_AWAY_BUILD") != "1")
                Console.WriteLine($"WARNING contracts away held out of this build: {aMissing} of {mineA.Count} voice files not in build/Sound yet");
            Console.WriteLine($"contracts away: {mineA.Count} lines, {aDlg.GetProperty("choices").EnumerateObject().Count()} choices");
        }
    }
}

// The Guild conversations (guild_talk.json): one top-level branch for Willem, Merila and
// the clerks. An answer offers its own follow-ups and "Let's talk about something else.", which goes up one level; an
// answer with no follow-ups offers the list it was picked from again (the first build mixed
// every follow-up in with the choices above it). The back choice's records come after every group's, so adding them moved
// nothing; until each of its replies is approved and recorded the old links stay. An answer longer than vanilla's 150 characters is several responses in one INFO, each with its own voice file. Anyone can
// ask at any hour, the clerks too (only the counter itself keeps hours); a node's "gate" narrows that.
// Own ID block (0x1000 here, 0x8800 merged), so nothing
// above moves these IDs. Held out of the plugin until each voice file is in build/Sound, as the staff's were; AG_TALK_BUILD=1
// builds them regardless. A merge writes talk_lines.json, whose IDs name the voice files, whether or not they are held out.
// The same builder makes the staff's own conversations (staff_talk.json, staff_talk_export.py) in a block of their own
// after room 5's: those always take the back choice (no old links to keep), and add rank steps ('rank', the lowest rank
// that hears the answer), their locked replies below it ('lock', after the list it came from) and
// 'needs' (a resident who must be alive).
var lateQuests = new List<(GetQuestCompletedConditionData Data, string Quest, DialogResponses Info)>();
void BuildTalk(string talkPath, uint block, string what, string linesName, bool staff)
{
    if (!File.Exists(talkPath)) return;
    next = Math.Max(next, block);
    var gMissivesIn = new FormKey(agEsp, 0xFDB);   // AG_MissivesInstalledGlobal: the DLL, from MissiveWatch::Active()
    var gNoticesIn = new FormKey(agEsp, 0xFDC);    // AG_NoticeBoardInstalledGlobal: the DLL, from NoticeWatch::Active()
    Condition[] Installed(string version) => version switch
    {
        "" => Array.Empty<Condition>(),
        "both" => new Condition[] { GlobalIs(gMissivesIn, CompareOperator.EqualTo, 1), GlobalIs(gNoticesIn, CompareOperator.EqualTo, 1) },
        "missives" => new Condition[] { GlobalIs(gMissivesIn, CompareOperator.EqualTo, 1), GlobalIs(gNoticesIn, CompareOperator.EqualTo, 0) },
        "notices" => new Condition[] { GlobalIs(gMissivesIn, CompareOperator.EqualTo, 0), GlobalIs(gNoticesIn, CompareOperator.EqualTo, 1) },
        "none" => new Condition[] { GlobalIs(gMissivesIn, CompareOperator.EqualTo, 0), GlobalIs(gNoticesIn, CompareOperator.EqualTo, 0) },
        _ => throw new Exception($"guild_talk.json: unknown version {version}"),
    };
    Condition Gate(string g) => g switch
    {
        "member" => GlobalIs(gRegistered, CompareOperator.EqualTo, 1),
        "belowS" => GlobalIs(gRank, CompareOperator.LessThan, 5),
        _ => throw new Exception($"{what}: unknown gate {g}"),
    };
    string? OpenedBy(JsonElement n) => n.GetProperty("says").EnumerateObject().SelectMany(w => w.Value.EnumerateObject())
        .Select(v => v.Name).FirstOrDefault(v => v.StartsWith("opened:"))?[7..];
    Condition QuestDone(string quest, bool done)
    {
        var q = new GetQuestCompletedConditionData(); q.Quest.Link.SetTo(Ed<IQuestGetter>(quest).FormKey);
        return new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = done ? 1 : 0, Data = q };
    }
    // rank steps: AG_PlayerRankGlobal 0..5 = E..S
    int RankOf(string r) => "EDCBAS".IndexOf(r) is var i and >= 0 ? i : throw new Exception($"{what}: unknown rank {r}");
    string? RankAt(JsonElement n) => n.TryGetProperty("rank", out var r) && r.ValueKind == JsonValueKind.String ? r.GetString() : null;
    // needs: a resident alive (GetDead == 0 on his placed ref)
    Condition Alive(string ed)
    {
        var d = new GetDeadConditionData { RunOnType = Condition.RunOnType.Reference };
        d.Reference.SetTo(cell.Persistent.OfType<PlacedNpc>().First(r => r.EditorID == ed + "Ref").FormKey);
        return new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 0, Data = d };
    }
    IEnumerable<Condition> Needs(JsonElement n) => n.TryGetProperty("needs", out var nd) ? nd.EnumerateArray().Select(x => Alive(x.GetString()!)) : Array.Empty<Condition>();
    // whileOpen: quests that must not be completed yet (Cassius on Caralion: dead or his quest complete, no choice).
    // A quest built later in this run (AGHallCaralionQuest) is linked just before the write, in LinkLateQuests.
    IEnumerable<Condition> WhileOpen(JsonElement n, DialogResponses info) => n.TryGetProperty("whileOpen", out var wo) ? wo.EnumerateArray().Select(x =>
    {
        var d = new GetQuestCompletedConditionData();
        lateQuests.Add((d, x.GetString()!, info));
        return (Condition)new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 0, Data = d };
    }).ToList() : Array.Empty<Condition>();
    var talkBranches = new List<DialogBranch>();
    var talkTopics = new List<DialogTopic>();
    var talkLines = new List<(string Key, string Npc, uint Id, int Part, string Text, string Topic)>();
    var backLines = new List<(string Key, string Npc, uint Id, int Part, string Text, string Topic)>();
    var backTopicsAll = new List<DialogTopic>();
    var talkLinks = new List<(DialogResponses Info, Func<bool, List<DialogTopic>> Links)>();   // filled once we know whether the back choice ships
    var talkGroups = new List<Action>();
    foreach (var group in JsonDocument.Parse(File.ReadAllText(talkPath)).RootElement.GetProperty("groups").EnumerateArray())
    {
        var stem = group.GetProperty("stem").GetString()!;
        var nodes = group.GetProperty("nodes").EnumerateArray().ToList();
        string? Parent(JsonElement n) => n.GetProperty("parent").GetString();
        string Id(JsonElement n) => n.GetProperty("id").GetString()!;
        JsonElement Node(string id) => nodes.Single(x => Id(x) == id);
        var root = nodes.Single(n => Parent(n) == null);
        var hasBack = group.TryGetProperty("back", out var back);
        var backTopics = new Dictionary<string, DialogTopic>();
        var branch = new DialogBranch(NewKey(), SkyrimRelease.SkyrimSE)
        {
            EditorID = $"AGHallTalkBranch{stem}", Quest = clerkQuest.ToLink<IQuestGetter>(), Category = DialogBranch.CategoryType.Player, Flags = DialogBranch.Flag.TopLevel,
        };
        talkBranches.Add(branch);
        var topics = nodes.ToDictionary(Id, n => new DialogTopic(BlockOf(n) is { } tb ? KeyIn(tb) : NewKey(), SkyrimRelease.SkyrimSE)
        {
            EditorID = $"AGHallTalk{Id(n)}", Name = n.GetProperty("prompt").GetString(), Priority = 50, Branch = branch.ToNullableLink(), Quest = clerkQuest.ToNullableLink(),
            Category = DialogTopic.CategoryEnum.Topic, Subtype = DialogTopic.SubtypeEnum.Custom, SubtypeName = new RecordType("CUST"),
        });
        branch.StartingTopic.SetTo(topics[Id(root)].FormKey);
        IEnumerable<string> Children(string id) => nodes.Where(n => Parent(n) == id).Select(Id);
        // a list of choices: those under x, and below the top the back choice to the list x was picked from ("^" + that node)
        // (from the top answer, "^*": back to the NPC's own list; "*" is that list, which offers nothing of ours)
        List<string> Menu(string x) => x == "*" ? new List<string>() : Children(x).Concat(x == Id(root) ? new[] { "^*" } : new[] { "^" + Parent(Node(x)) }).ToList();
        // after an answer: its own follow-ups, or with none the list it was picked from
        List<string> After(JsonElement n) => Children(Id(n)).Any() || Parent(n) == null ? Menu(Id(n)) : Menu(Parent(n)!);
        List<DialogTopic> Resolve(IEnumerable<string> offer) => offer.Select(o => o[0] == '^' ? backTopics[o[1..]] : topics[o]).ToList();
        // the old links (before the back choice): its own follow-ups first, then the choices it came from
        List<string> Offers(JsonElement n)
        {
            var offer = Children(Id(n)).ToList();
            for (var at = Parent(n); at != null; at = Parent(nodes.Single(x => Id(x) == at)))
            {
                offer.AddRange(Children(at).Where(c => !offer.Contains(c)));
                if (at == Id(root) || offer.Count > 1) break;
            }
            return offer;
        }
        foreach (var n in nodes)
        {
            var t = topics[Id(n)];
            var gates = n.GetProperty("gate").EnumerateArray().Select(g => Gate(g.GetString()!)).ToList();
            foreach (var who in n.GetProperty("says").EnumerateObject())
                foreach (var version in who.Value.EnumerateObject())
                {
                    var suffix = version.Name == "" ? "" : version.Name.StartsWith("opened:") ? ".opened" : $".{version.Name}";
                    var info = new DialogResponses(BlockOf(n) is { } ib ? KeyIn(ib) : NewKey(), SkyrimRelease.SkyrimSE) { EditorID = $"AGHallInfo_{who.Name}_talk_{Id(n)}{suffix.Replace('.', '_')}", Flags = new DialogResponseFlags() };
                    var part = 0;
                    foreach (var text in version.Value.EnumerateArray().Select(p => p.GetString()!))
                    {
                        info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = (byte)++part });
                        talkLines.Add(($"{who.Name}:talk:{Id(n)}{suffix}#{part}", who.Name, info.FormKey.ID, part, text, t.EditorID!));
                    }
                    info.Conditions.AddRange(At(Hall(who.Name)));
                    foreach (var g in gates) info.Conditions.Add(g.DeepCopy());
                    // "opened:<quest>": the answer once that quest is completed, at any rank (Ghrulek's GH3 and The Cursed Tribe);
                    // the node's other answers then wait for it to be not completed
                    if (version.Name.StartsWith("opened:")) info.Conditions.Add(QuestDone(version.Name[7..], true));
                    else
                    {
                        info.Conditions.AddRange(Installed(version.Name));
                        if (OpenedBy(n) is { } oq) info.Conditions.Add(QuestDone(oq, false));
                    }
                    info.Conditions.AddRange(Needs(n));
                    info.Conditions.AddRange(WhileOpen(n, info));
                    if (RankAt(n) is { } rank && !version.Name.StartsWith("opened:")) info.Conditions.Add(GlobalIs(gRank, CompareOperator.GreaterThanOrEqualTo, RankOf(rank)));
                    var node = n;
                    talkLinks.Add((info, withBack => withBack && hasBack ? Resolve(After(node)) : Offers(node).Select(o => topics[o]).ToList()));
                    if (t.Responses.Count > 0) info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(t.Responses[^1].FormKey);
                    t.Responses.Add(info);
                }
            // below its rank: the locked reply, in the same topic, and the list it was picked from again
            if (n.TryGetProperty("lock", out var lk) && lk.ValueKind == JsonValueKind.Object)
                foreach (var who in lk.EnumerateObject())
                {
                    var info = new DialogResponses(BlockOf(n) is { } lb ? KeyIn(lb) : NewKey(), SkyrimRelease.SkyrimSE) { EditorID = $"AGHallInfo_{who.Name}_talk_{Id(n)}lock", Flags = new DialogResponseFlags() };
                    var part = 0;
                    foreach (var text in who.Value.EnumerateArray().Select(p => p.GetString()!))
                    {
                        info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = (byte)++part });
                        talkLines.Add(($"{who.Name}:talk:{Id(n)}lock#{part}", who.Name, info.FormKey.ID, part, text, t.EditorID!));
                    }
                    info.Conditions.AddRange(At(Hall(who.Name)));
                    foreach (var g in gates) info.Conditions.Add(g.DeepCopy());
                    info.Conditions.AddRange(Needs(n));
                    info.Conditions.AddRange(WhileOpen(n, info));
                    info.Conditions.Add(GlobalIs(gRank, CompareOperator.LessThan, RankOf(RankAt(n) ?? throw new Exception($"{what}: {Id(n)} has a lock but no rank"))));
                    if (OpenedBy(n) is { } lq) info.Conditions.Add(QuestDone(lq, false));   // (no lock once the quest has opened it)
                    var from = Parent(n) ?? throw new Exception($"{what}: the root {Id(n)} cannot be locked");
                    talkLinks.Add((info, _ => Resolve(Menu(from))));
                    if (t.Responses.Count > 0) info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(t.Responses[^1].FormKey);
                    t.Responses.Add(info);
                }
        }
        talkTopics.AddRange(topics.Values);
        // the back choice, one topic per list it returns to, each speaker's reply in it; made after every group's records
        if (hasBack) talkGroups.Add(() =>
        {
            var ups = new HashSet<string>();
            var todo = new Queue<string>(nodes.SelectMany(After));
            while (todo.Count > 0)
            {
                var o = todo.Dequeue();
                if (o[0] != '^' || !ups.Add(o[1..])) continue;
                foreach (var x in Menu(o[1..])) todo.Enqueue(x);
            }
            foreach (var x in nodes.Select(Id).Where(ups.Contains))
            {
                uint? bb = Node(x).TryGetProperty("backIds", out var bi) ? Convert.ToUInt32(bi.GetString(), 16) : null;
                FormKey BackKey() => bb is { } v ? KeyIn(v) : NewKey();
                var t = new DialogTopic(BackKey(), SkyrimRelease.SkyrimSE)
                {
                    EditorID = $"AGHallTalkBack{x}", Name = back.GetProperty("prompt").GetString(), Priority = 50, Branch = branch.ToNullableLink(), Quest = clerkQuest.ToNullableLink(),
                    Category = DialogTopic.CategoryEnum.Topic, Subtype = DialogTopic.SubtypeEnum.Custom, SubtypeName = new RecordType("CUST"),
                };
                foreach (var who in back.GetProperty("says").EnumerateObject())
                {
                    var text = who.Value.GetString()!;
                    var info = new DialogResponses(BackKey(), SkyrimRelease.SkyrimSE) { EditorID = $"AGHallInfo_{who.Name}_talk_back{x}", Flags = new DialogResponseFlags() };
                    info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
                    backLines.Add(($"{who.Name}:talk:back{x}#1", who.Name, info.FormKey.ID, 1, text, t.EditorID!));
                    info.Conditions.AddRange(At(Hall(who.Name)));
                    var to = x;
                    talkLinks.Add((info, _ => Resolve(Menu(to))));
                    if (t.Responses.Count > 0) info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(t.Responses[^1].FormKey);
                    t.Responses.Add(info);
                }
                backTopics[x] = t;
                backTopicsAll.Add(t);
            }
            // back from the top answer: the same choice and reply, linking nowhere, so the game shows the NPC's own list again;
            // in its own block (topNext), so the IDs of every record made before it stay as they were
            if (ups.Contains("*"))
            {
                var t = new DialogTopic(Key(topNext++), SkyrimRelease.SkyrimSE)
                {
                    EditorID = $"AGHallTalkBackTop{stem}", Name = back.GetProperty("prompt").GetString(), Priority = 50, Branch = branch.ToNullableLink(), Quest = clerkQuest.ToNullableLink(),
                    Category = DialogTopic.CategoryEnum.Topic, Subtype = DialogTopic.SubtypeEnum.Custom, SubtypeName = new RecordType("CUST"),
                };
                foreach (var who in back.GetProperty("says").EnumerateObject())
                {
                    var text = who.Value.GetString()!;
                    var info = new DialogResponses(Key(topNext++), SkyrimRelease.SkyrimSE) { EditorID = $"AGHallInfo_{who.Name}_talk_backTop{stem}", Flags = new DialogResponseFlags() };
                    info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
                    backLines.Add(($"{who.Name}:talk:backTop{stem}#1", who.Name, info.FormKey.ID, 1, text, t.EditorID!));
                    info.Conditions.AddRange(At(Hall(who.Name)));
                    if (t.Responses.Count > 0) info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(t.Responses[^1].FormKey);
                    t.Responses.Add(info);
                }
                backTopics["*"] = t;
                backTopicsAll.Add(t);
                if (topNext > 0x1800) throw new Exception($"the talks' back-from-the-top ran to 0x{topNext:X}, past its block's end at 0x1800");
            }
        });
    }
    foreach (var g in talkGroups) g();
    CheckTakes(talkLines.Concat(backLines).Select(l => (l.Key, l.Id)));
    string TalkFile(string topic, uint id, int part)
    {
        var (q, t) = (clerkQuest.EditorID!, topic);
        if (q.Length + t.Length > 25) { q = q[..10]; t = t[..Math.Min(t.Length, 25 - q.Length)]; }
        return $"{q}_{t}_{id:X8}_{part}.fuz".ToLowerInvariant();
    }
    uint Merged(uint id) => id >= 0x8000 ? id : idBase + id;
    int Missing(IEnumerable<(string Key, string Npc, uint Id, int Part, string Text, string Topic)> lines) =>
        lines.Count(l => !File.Exists(Path.Combine(npcsDir, "build", "Sound", "Voice", "AdventurersGuild - Guild Hall.esp", VoiceOf(l.Npc), TalkFile(l.Topic, Merged(l.Id), l.Part))));
    var forced = Environment.GetEnvironmentVariable("AG_TALK_BUILD") == "1";
    var talkMissing = Missing(talkLines);
    var backMissing = Missing(backLines);
    // (the staff's talks: the back choice always, and its replies count with the rest, so nothing ships half voiced)
    var withBack = backLines.Count > 0 && (staff || backMissing == 0 || forced);
    if (staff) { talkMissing += backMissing; backMissing = 0; }
    foreach (var (info, links) in talkLinks) foreach (var t in links(withBack)) info.LinkTo.Add(new FormLink<IDialogTopicGetter>(t.FormKey));
    if (talkMissing == 0 || forced)
    {
        foreach (var b in talkBranches) mod.DialogBranches.Add(b);
        foreach (var t in talkTopics) mod.DialogTopics.Add(t);
        if (withBack) foreach (var t in backTopicsAll) mod.DialogTopics.Add(t);
        Console.WriteLine($"{what}: {talkTopics.Count} topics, {talkLines.Count} spoken parts; back choice: " +
            (withBack ? $"{backTopicsAll.Count} topics, {backLines.Count} replies" : backLines.Count == 0 ? "none approved yet, old links" : $"held, {backMissing} of {backLines.Count} voice files missing, old links"));
    }
    else Console.WriteLine($"WARNING {what} held out of this build: {talkMissing} of {talkLines.Count + (staff ? backLines.Count : 0)} voice files not in build/Sound yet");
    if (merge) File.WriteAllText(Path.Combine(npcsDir, "build", linesName), JsonSerializer.Serialize(talkLines.Concat(backLines).Select(l => new { key = l.Key, npc = l.Npc,
        voice = VoiceOf(l.Npc), info = $"{l.Id:X8}", response = l.Part, quest = clerkQuest.EditorID, topic = l.Topic, text = l.Text }), new JsonSerializerOptions { WriteIndented = true }));
}
BuildTalk(Path.Combine(npcsDir, "guild_talk.json"), 0x1000u, "guild talk", "talk_lines.json", false);

// Room 5 as the player's home (BACKLOG.md, plans/room5-home.md). Willem sells Caralion's old room
// once Caralion is gone: dead, or AGHallCaralionGoneGlobal set by his own quest when he leaves Skyrim (not written yet).
// Then any spouse can be asked to live at the hall: AG's own topic beside vanilla's house choices, answered in vanilla's
// own recorded move lines, so no vanilla record is overridden (Spouses Can Live Everywhere and Hearthfire Multiple
// Adoptions both replace RelationshipMarriageFIN's script). A spouse from outside goes into AGHallHomeQuest's alias (room 5
// by night, the hall by day); the hall's own folk keep their routines and only sleep in room 5. Whichever, the packages
// read FIN's SpouseCurrentHome, which the move sets to 99 and vanilla overwrites when it moves the spouse to a house, so
// they let go by themselves. Own ID block (0x1400 here, 0x8C00 merged). Held out until npcs/room5.json is approved and
// Willem's lines are recorded (AG_TALK_BUILD=1 builds it regardless); the spouse's side needs no recording.
var room5Path = Path.Combine(npcsDir, "room5.json");
if (File.Exists(room5Path))
{
    next = Math.Max(next, 0x1400u);
    var r5 = JsonDocument.Parse(File.ReadAllText(room5Path)).RootElement;
    var forced5 = Environment.GetEnvironmentVariable("AG_TALK_BUILD") == "1";
    var approved5 = r5.GetProperty("approved").GetBoolean() || forced5;
    var skyrim = ModKey.FromFileName("Skyrim.esm");
    var playerRef = new FormKey(skyrim, 0x14);
    ConditionFloat C(ConditionData d, CompareOperator op, float v, bool or = false) =>
        new() { CompareOperator = op, ComparisonValue = v, Data = d, Flags = or ? Condition.Flag.OR : 0 };
    ConditionData OnRef(ConditionData d, FormKey r) { d.RunOnType = Condition.RunOnType.Reference; d.Reference.SetTo(r); return d; }
    FormKey RefOf(string npcEd) => cell.Persistent.OfType<PlacedNpc>().First(r => r.EditorID == npcEd + "Ref").FormKey;
    FormKey HallRef(string ed) => hallNamed.TryGetValue(ed, out var k) ? k : throw new Exception($"room 5: {ed} is not in the hall's plugin");
    var fin = Ed<IQuestGetter>("RelationshipMarriageFIN");
    var married = Ed<IFactionGetter>("PlayerMarriedFaction");
    ConditionData AtHall() { var d = new GetVMQuestVariableConditionData { VariableName = "::SpouseCurrentHome_var" }; d.Quest.Link.SetTo(fin.FormKey); return d; }
    ConditionData InFaction(FormKey f) { var d = new GetInFactionConditionData(); d.Faction.Link.SetTo(f); return d; }

    var gGone = new GlobalShort(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallCaralionGoneGlobal", Data = 0 };
    mod.Globals.Add(gGone);
    var folk = new FormList(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallFolkList" };
    foreach (var n in sched.GetProperty("npcs").EnumerateObject()) folk.Items.Add(new FormLink<ISkyrimMajorRecordGetter>(Hall(n.Name).FormKey));
    mod.FormLists.Add(folk);
    var homeQuest = new Quest(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = "AGHallHomeQuest", Name = "Guild Hall Home", Flags = Quest.Flag.StartGameEnabled, Priority = 60,
    };
    mod.Quests.Add(homeQuest);

    // the spouse's packages: by night the double bed (near reference, as Hearthfire's room-scale homes), by day the hall
    // around the tavern; both only while FIN's SpouseCurrentHome says the hall
    var bed = HallRef("AGHallBedRoom5");   // (room 5 is one double bed from the start, Caralion's)
    Package SpousePkg(string kind, string ed, FormKey at, uint radius, int hour, int hours)
    {
        var pk = (Package)pkgSrc[kind].Duplicate(NewKey());
        pk.EditorID = ed; pk.Conditions.Clear(); pk.OwnerQuest.Clear();   // (no vanilla owner quest on a copy: see Make1)
        pk.ScheduleHour = (sbyte)hour; pk.ScheduleMinute = (sbyte)(hour < 0 ? -1 : 0); pk.ScheduleDurationInMinutes = hours * 60;
        pk.ScheduleDayOfWeek = Package.DayOfWeek.Any;
        ((PackageDataLocation)pk.Data[0]).Location = new LocationTargetRadius { Target = new LocationTarget { Link = new FormLink<IPlacedGetter>(at) }, Radius = radius };
        pk.Conditions.Add(C(AtHall(), CompareOperator.EqualTo, 99));
        mod.Packages.Add(pk);
        return pk;
    }
    var sleep5 = SpousePkg("sleep", "AGHallHomeSpouseSleep22", bed, 150, 22, 8);
    var day5 = SpousePkg("leisure", "AGHallHomeSpouseHall", HallRef("AGHallSpotTavern"), 1500, -1, 0);
    var spouseAlias = new QuestAlias { ID = 0, Name = "Spouse", Type = QuestAlias.TypeEnum.Reference, Flags = QuestAlias.Flag.Optional | QuestAlias.Flag.AllowReserved };
    spouseAlias.PackageData.Add(sleep5.ToLink<IPackageGetter>());
    spouseAlias.PackageData.Add(day5.ToLink<IPackageGetter>());
    homeQuest.Aliases.Add(spouseAlias);
    // the hall's own folk: their own sleep block, in the double, ahead of their usual one, while married and at the hall
    foreach (var n in sched.GetProperty("npcs").EnumerateObject())
    {
        var s = n.Value.GetProperty("blocks").EnumerateArray().First(b => b.GetProperty("do").GetString() == "sleep");
        var pk = SpousePkg("sleep", $"{n.Name}PkgSleepRoom5", bed, 150, s.GetProperty("at").GetInt32(), s.GetProperty("hours").GetInt32());
        pk.Conditions.Add(C(InFaction(married.FormKey), CompareOperator.EqualTo, 1));
        Hall(n.Name).Packages.Insert(0, pk.ToLink<IPackageGetter>());
    }

    // "Let's live at the Guild Hall.": one reply per vanilla marriage voice list, each sharing vanilla's own move reply
    // (RelationshipMarriageFINWhiterunHouse's), so every vanilla spouse answers in their own recorded voice
    var homeBranch = new DialogBranch(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = "AGHallHomeBranch", Quest = homeQuest.ToLink<IQuestGetter>(), Category = DialogBranch.CategoryType.Player, Flags = DialogBranch.Flag.TopLevel,
    };
    var homeTopic = new DialogTopic(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = "AGHallHomeTopic", Name = r5.GetProperty("home").GetProperty("prompt").GetString(), Priority = 50,
        Branch = homeBranch.ToNullableLink(), Quest = homeQuest.ToNullableLink(),
        Category = DialogTopic.CategoryEnum.Topic, Subtype = DialogTopic.SubtypeEnum.Custom, SubtypeName = new RecordType("CUST"),
    };
    homeBranch.StartingTopic.SetTo(homeTopic.FormKey);
    var adoption = Ed<IQuestGetter>("BYOHRelationshipAdoption");
    foreach (var v in Ed<IDialogTopicGetter>("RelationshipMarriageFINWhiterunHouse").Responses)
    {
        var info = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE)
        {
            EditorID = $"AGHallInfo_home_{v.FormKey.ID:X6}", Flags = new DialogResponseFlags(),
            ResponseData = new FormLinkNullable<IDialogResponsesGetter>(v.ResponseData.FormKeyNullable ?? v.FormKey),
            VirtualMachineAdapter = new DialogResponsesAdapter
            {
                Scripts = { new ScriptEntry { Name = "AG_TIF_HallHomeMove", Properties = {
                    new ScriptObjectProperty { Name = "MarriageFIN", Object = fin.ToLink<ISkyrimMajorRecordGetter>(), Flags = ScriptProperty.Flag.Edited },
                    new ScriptObjectProperty { Name = "Spouse", Object = homeQuest.ToLink<ISkyrimMajorRecordGetter>(), Alias = 0, Flags = ScriptProperty.Flag.Edited },
                    new ScriptObjectProperty { Name = "HallFolk", Object = folk.ToLink<ISkyrimMajorRecordGetter>(), Flags = ScriptProperty.Flag.Edited } } } },
                ScriptFragments = new ScriptFragments
                {
                    FileName = "AG_TIF_HallHomeMove",
                    OnEnd = new ScriptFragment { ScriptName = "AG_TIF_HallHomeMove", FragmentName = "Fragment_0" },
                },
            },
        };
        foreach (var c in v.Conditions.Where(c => c.Data is IGetIsVoiceTypeConditionDataGetter)) info.Conditions.Add(c.DeepCopy());
        info.Conditions.Add(C(InFaction(married.FormKey), CompareOperator.EqualTo, 1));
        info.Conditions.Add(C(OnRef(InFaction(room5.FormKey), playerRef), CompareOperator.EqualTo, 1));
        info.Conditions.Add(C(AtHall(), CompareOperator.NotEqualTo, 99));
        var running = new GetQuestRunningConditionData(); running.Quest.Link.SetTo(adoption.FormKey);
        info.Conditions.Add(C(running, CompareOperator.EqualTo, 0));   // (Hearthfire's adopted children can't come to the hall)
        if (homeTopic.Responses.Count > 0) info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(homeTopic.Responses[^1].FormKey);
        homeTopic.Responses.Add(info);
    }

    // Willem: "About Caralion's old room...", once Caralion is gone and while the room isn't the player's
    var w = r5.GetProperty("willem");
    var gm = Hall("AGHallGuildMaster");
    var r5Branch = new DialogBranch(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = "AGHallRoom5Branch", Quest = clerkQuest.ToLink<IQuestGetter>(), Category = DialogBranch.CategoryType.Player, Flags = DialogBranch.Flag.TopLevel,
    };
    DialogTopic R5Topic(string ed, string prompt) => new(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = ed, Name = prompt, Priority = 50, Branch = r5Branch.ToNullableLink(), Quest = clerkQuest.ToNullableLink(),
        Category = DialogTopic.CategoryEnum.Topic, Subtype = DialogTopic.SubtypeEnum.Custom, SubtypeName = new RecordType("CUST"),
    };
    var tOffer = R5Topic("AGHallRoom5Offer", w.GetProperty("offer").GetProperty("prompt").GetString()!);
    var tTake = R5Topic("AGHallRoom5Take", w.GetProperty("take").GetProperty("prompt").GetString()!);
    var tLater = R5Topic("AGHallRoom5Later", w.GetProperty("later").GetProperty("prompt").GetString()!);
    r5Branch.StartingTopic.SetTo(tOffer.FormKey);
    var r5Lines = new List<(string Key, string Npc, uint Id, int Part, string Text, string Topic)>();
    DialogResponses R5Line(DialogTopic t, string slot, IEnumerable<Condition> extra)
    {
        var text = w.GetProperty(slot).GetProperty("text").GetString()!;
        var info = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = $"AGHallInfo_AGHallGuildMaster_room5_{slot}", Flags = new DialogResponseFlags() };
        info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
        info.Conditions.AddRange(At(gm));
        info.Conditions.AddRange(extra);
        if (t.Responses.Count > 0) info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(t.Responses[^1].FormKey);
        t.Responses.Add(info);
        r5Lines.Add(($"AGHallGuildMaster:room5:{slot}#1", "AGHallGuildMaster", info.FormKey.ID, 1, text, t.EditorID!));
        return info;
    }
    ConditionData PlayerGold() { var d = new GetItemCountConditionData(); d.ItemOrList.Link.SetTo(new FormKey(skyrim, 0xF)); return OnRef(d, playerRef); }
    var dead = OnRef(new GetDeadConditionData(), RefOf("AGHallResidentNoble"));
    var offer = R5Line(tOffer, "offer", new Condition[] { C(dead, CompareOperator.EqualTo, 1, or: true), GlobalIs(gGone.FormKey, CompareOperator.EqualTo, 1),
        C(OnRef(InFaction(room5.FormKey), playerRef), CompareOperator.EqualTo, 0) });
    offer.LinkTo.Add(new FormLink<IDialogTopicGetter>(tTake.FormKey));
    offer.LinkTo.Add(new FormLink<IDialogTopicGetter>(tLater.FormKey));
    var price = r5.GetProperty("price").GetInt32();
    var take = R5Line(tTake, "take", new Condition[] { C(PlayerGold(), CompareOperator.GreaterThanOrEqualTo, price) });
    take.VirtualMachineAdapter = new DialogResponsesAdapter
    {
        Scripts = { new ScriptEntry { Name = "AG_TIF_HallRoom5Buy", Properties = {
            new ScriptObjectProperty { Name = "Gold", Object = new FormLink<ISkyrimMajorRecordGetter>(new FormKey(skyrim, 0xF)), Flags = ScriptProperty.Flag.Edited },
            new ScriptIntProperty { Name = "Price", Data = price, Flags = ScriptProperty.Flag.Edited },
            new ScriptObjectProperty { Name = "Room5Faction", Object = room5.ToLink<ISkyrimMajorRecordGetter>(), Flags = ScriptProperty.Flag.Edited },
            new ScriptObjectProperty { Name = "Bed", Object = new FormLink<ISkyrimMajorRecordGetter>(HallRef("AGHallBedRoom5")), Flags = ScriptProperty.Flag.Edited },
            new ScriptObjectProperty { Name = "PlayerBedOwnership", Object = new FormLink<ISkyrimMajorRecordGetter>(new FormKey(skyrim, 0xF2073)), Flags = ScriptProperty.Flag.Edited },
            new ScriptObjectProperty { Name = "Chest", Object = new FormLink<ISkyrimMajorRecordGetter>(HallRef("AGHallChestRoom5")), Flags = ScriptProperty.Flag.Edited } } } },
        ScriptFragments = new ScriptFragments
        {
            FileName = "AG_TIF_HallRoom5Buy",
            OnEnd = new ScriptFragment { ScriptName = "AG_TIF_HallRoom5Buy", FragmentName = "Fragment_0" },
        },
    };
    R5Line(tTake, "nofee", new Condition[] { C(PlayerGold(), CompareOperator.LessThan, price) });
    R5Line(tLater, "later", Array.Empty<Condition>());
    CheckTakes(r5Lines.Select(l => (l.Key, l.Id)));
    string R5File(string topic, uint id) { var (q, t) = (clerkQuest.EditorID!, topic); if (q.Length + t.Length > 25) { q = q[..10]; t = t[..Math.Min(t.Length, 25 - q.Length)]; } return $"{q}_{t}_{id:X8}_1.fuz".ToLowerInvariant(); }
    var r5Missing = r5Lines.Count(l => !File.Exists(Path.Combine(npcsDir, "build", "Sound", "Voice", "AdventurersGuild - Guild Hall.esp", VoiceOf(l.Npc), R5File(l.Topic, l.Id >= 0x8000 ? l.Id : idBase + l.Id))));
    if (approved5)
    {
        mod.DialogBranches.Add(homeBranch); mod.DialogTopics.Add(homeTopic);
        Console.WriteLine($"room 5: the spouse's home, {homeTopic.Responses.Count} replies (vanilla's voices), 2 spouse packages, {folk.Items.Count} hall-folk sleep packages");
    }
    else Console.WriteLine("room 5: the spouse's home held out of this build (npcs/room5.json not approved yet)");
    if (approved5 && (r5Missing == 0 || forced5))
    {
        mod.DialogBranches.Add(r5Branch); foreach (var t in new[] { tOffer, tTake, tLater }) mod.DialogTopics.Add(t);
        Console.WriteLine($"room 5: Willem's sale, {r5Lines.Count} lines");
    }
    else Console.WriteLine($"room 5: Willem's sale held out of this build ({(approved5 ? $"{r5Missing} of {r5Lines.Count} voice files missing" : "not approved yet")})");
    if (merge) File.WriteAllText(Path.Combine(npcsDir, "build", "room5_lines.json"), JsonSerializer.Serialize(r5Lines.Select(l => new { key = l.Key, npc = l.Npc,
        voice = VoiceOf(l.Npc), info = $"{l.Id:X8}", response = l.Part, quest = clerkQuest.EditorID, topic = l.Topic, text = l.Text }), new JsonSerializerOptions { WriteIndented = true }));
}

// The staff's own conversations ("Tell me about yourself", members only, rank steps with locked
// replies): the talk builder above, own ID block (0x1600 here, 0x8E00 merged), held out until every voice file is in.
if (next > 0x1600) throw new Exception($"room 5 ran to 0x{next:X}, into the staff talk's block at 0x1600");
BuildTalk(Path.Combine(npcsDir, "staff_talk.json"), 0x1600u, "staff talk", "staff_talk_lines.json", true);

// Nessa at her archery practice (nessa_basement.json): while her archery package runs, "Tell me
// about yourself." is put off ("Now's not a good time.", ahead of her story in its topic), and "What are you doing down
// here?" is asked, answered by whether her own quest is done (AGHallNessaQuestDoneGlobal, for that quest to set). After the
// staff talk's records, ahead of Caralion's quest's block, so no recorded line moves.
var nbPath = Path.Combine(npcsDir, "nessa_basement.json");
if (File.Exists(nbPath))
{
    var nb = JsonDocument.Parse(File.ReadAllText(nbPath)).RootElement;
    var nessaNpc = Hall("AGHallClerkEvening");
    var archery = mod.Packages.First(p => p.EditorID == "AGHallClerkEveningPkg02Archery08");
    ConditionFloat Practising() { var d = new GetIsCurrentPackageConditionData(); d.Package.Link.SetTo(archery.FormKey); return new() { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = d }; }
    var gDone = new GlobalShort(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallNessaQuestDoneGlobal", Data = 0 };
    mod.Globals.Add(gDone);
    var nbLines = new List<(string Key, string Npc, uint Id, int Part, string Text, string Topic)>();
    DialogResponses NLine(DialogTopic t, string slot, string text)
    {
        var info = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = $"AGHallInfo_AGHallClerkEvening_{slot}", Flags = new DialogResponseFlags() };
        info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
        info.Conditions.AddRange(At(nessaNpc));
        info.Conditions.Add(Practising());
        nbLines.Add(($"AGHallClerkEvening:{slot}#1", "AGHallClerkEvening", info.FormKey.ID, 1, text, t.EditorID!));
        return info;
    }
    // "Now's not a good time.": first in her story's opening topic (members only, as the story is)
    var el0 = mod.DialogTopics.FirstOrDefault(t => t.EditorID == "AGHallTalkEL0");
    var busyTopic = el0 ?? new DialogTopic(FormKey.Null, SkyrimRelease.SkyrimSE) { EditorID = "AGHallTalkEL0" };
    var busy = NLine(busyTopic, "talk_EL0busy", nb.GetProperty("busy").GetString()!);
    busy.Conditions.Add(GlobalIs(gRegistered, CompareOperator.EqualTo, 1));
    if (el0 != null)
    {
        el0.Responses.Insert(0, busy);
        if (el0.Responses.Count > 1) el0.Responses[1].PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(busy.FormKey);
    }
    // "What are you doing down here?": a topic of its own, asked only while she practises; members only
    var downBranch = new DialogBranch(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallNessaPracticeBranch", Quest = clerkQuest.ToLink<IQuestGetter>(), Category = DialogBranch.CategoryType.Player, Flags = DialogBranch.Flag.TopLevel };
    var down = new DialogTopic(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = "AGHallNessaPracticeTopic", Name = nb.GetProperty("prompt").GetString(), Priority = 50, Branch = downBranch.ToNullableLink(), Quest = clerkQuest.ToNullableLink(),
        Category = DialogTopic.CategoryEnum.Topic, Subtype = DialogTopic.SubtypeEnum.Custom, SubtypeName = new RecordType("CUST"),
    };
    downBranch.StartingTopic.SetTo(down.FormKey);
    var before = NLine(down, "practice_before", nb.GetProperty("before").GetString()!);
    before.Conditions.Add(GlobalIs(gDone.FormKey, CompareOperator.EqualTo, 0));
    before.Conditions.Add(GlobalIs(gRegistered, CompareOperator.EqualTo, 1));
    down.Responses.Add(before);
    var after = NLine(down, "practice_after", nb.GetProperty("after").GetString()!);
    after.Conditions.Add(GlobalIs(gDone.FormKey, CompareOperator.EqualTo, 1));
    after.Conditions.Add(GlobalIs(gRegistered, CompareOperator.EqualTo, 1));
    after.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(before.FormKey);
    down.Responses.Add(after);
    CheckTakes(nbLines.Select(l => (l.Key, l.Id)));
    if (el0 != null)
    {
        mod.DialogBranches.Add(downBranch); mod.DialogTopics.Add(down);
        Console.WriteLine($"nessa at practice: {nbLines.Count} lines");
    }
    else Console.WriteLine("nessa at practice: held out with the staff talk");
    if (merge) File.WriteAllText(Path.Combine(npcsDir, "build", "nessa_basement_lines.json"), JsonSerializer.Serialize(nbLines.Select(l => new { key = l.Key, npc = l.Npc,
        voice = VoiceOf(l.Npc), info = $"{l.Id:X8}", response = l.Part, quest = clerkQuest.EditorID, topic = l.Topic, text = l.Text }), new JsonSerializerOptions { WriteIndented = true }));
}
if (next > 0x1700) throw new Exception($"the staff talk ran to 0x{next:X}, into Caralion's quest's block at 0x1700");

// Caralion's quest, The Golden Hand (plans/caralion-quest.md, caralion_quest.json). Own ID
// block (0x1700 here, 0x8F00 merged). The quest script (npcs/papyrus/AGHallCaralionQuestScript.psc) runs the stages; no
// stage fragments: every stage is set by our own scripts, which call the quest script.
// (built by default since 2026-11-04, its scripts written and lines voiced; AG_CARALION_BUILD=0 leaves it out)
var cqPath = Path.Combine(npcsDir, "caralion_quest.json");
if (File.Exists(cqPath) && Environment.GetEnvironmentVariable("AG_CARALION_BUILD") != "0")
{
    next = Math.Max(next, 0x1700u);
    var cq = JsonDocument.Parse(File.ReadAllText(cqPath)).RootElement;
    var cqLines = new List<(string Key, string Npc, uint Id, int Part, string Text, string Topic)>();
    var caralion = Hall("AGHallResidentNoble");
    FormKey NamedRef(string ed) => cell.Persistent.OfType<PlacedNpc>().First(r => r.EditorID == ed + "Ref").FormKey;
    var quest = new Quest(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = "AGHallCaralionQuest", Name = cq.GetProperty("name").GetString(), Priority = 70, Type = Quest.TypeEnum.SideQuest,
        Flags = Quest.Flag.RunOnce,
    };
    mod.Quests.Add(quest);
    // Caralion's party: him and his sellswords, who stop fighting when he yields
    var hand = new Faction(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallGoldenHandFaction", Name = "The Golden Hand", Flags = Faction.FactionFlag.HiddenFromPC };
    mod.Factions.Add(hand);
    Join(caralion, hand.FormKey);
    // (he was still far too easy) his level the player's, by his record, as vanilla's leveled uniques
    // (Ancano: x1.0, 15-50; Mercer Frey: x1.2, 10-50), so the game works out his spellsword's skills and health at it.
    // Fixed at 10 he fought with One-Handed 34 and 134 health at the player's 48. Capped at 81, not vanilla's 50, so he
    // keeps pace past it
    caralion.Configuration.Level = new PcLevelMult { LevelMult = 1.0f };   // (Mutagen writes the flag from this type)
    caralion.Configuration.CalcMinLevel = 10;
    caralion.Configuration.CalcMaxLevel = 81;
    // Vohd: a vanilla frost troll of its own, unique; its level and stats set by the quest at spawn (player + 10)
    var vohd = (Npc)Ed<INpcGetter>(cq.GetProperty("vohd").GetProperty("base").GetString()!).Duplicate(NewKey());
    vohd.EditorID = "AGHallVohd"; vohd.Name = cq.GetProperty("vohd").GetProperty("name").GetString();
    vohd.Configuration.Flags |= NpcConfiguration.Flag.Unique;
    mod.Npcs.Add(vohd);
    // the sellswords: vanilla's Goldenglow mercenary, its name kept ("Mercenary"); in Caralion's party
    var merc = (Npc)Ed<INpcGetter>(cq.GetProperty("sellsword").GetProperty("base").GetString()!).Duplicate(NewKey());
    merc.EditorID = "AGHallGoldenHandSellsword";
    merc.Factions.Add(new RankPlacement { Faction = hand.ToLink<IFactionGetter>(), Rank = 0 });
    // hired, but dressed as the Golden Hand's men: vanilla's full elven armor outfit and the
    // Thalmor's elven one-handed weapons in place of the Goldenglow mercenary's
    merc.DefaultOutfit = Ed<IOutfitGetter>("ArmorElvenAllOutfit").ToNullableLink();
    var mercWeapon = Ed<ILeveledItemGetter>("TG02MercLItemWeapon1H").FormKey;
    foreach (var e in merc.Items ?? new())
        if (e.Item.Item.FormKey == mercWeapon) e.Item.Item.SetTo(Ed<ILeveledItemGetter>("SublistThalmorWeaponElven1H").FormKey);
    mod.Npcs.Add(merc);
    // Vohd's head: a quest item (no trophy or ingredient keyword, so AG neither buys nor counts it); its model a placeholder
    // until a model is chosen (the vanilla troll skull)
    var skull = Ed<IMiscItemGetter>(cq.GetProperty("head").GetProperty("model").GetString()!);
    var head = new MiscItem(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = "AGHallVohdHead", Name = cq.GetProperty("head").GetProperty("name").GetString(), Value = 0, Weight = 5,
        Model = skull.Model?.DeepCopy(), ObjectBounds = skull.ObjectBounds.DeepCopy(),
        PickUpSound = skull.PickUpSound.AsNullable(), PutDownSound = skull.PutDownSound.AsNullable(),
        Keywords = new() { Ed<IKeywordGetter>("VendorItemAnimalPart").ToLinkGetter() },   // the creature-part icon, as the trophies (2026-11-07)
    };
    mod.MiscItems.Add(head);
    // where the quest's actors are made, disabled, before they are moved into the world: out of sight under the hall's floor
    var anchor = new PlacedObject(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = "AGHallQuestAnchorMarker", Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x3B)),   // XMarker
        Placement = new Placement { Position = new P3Float(0, 0, -2000), Rotation = new P3Float(0, 0, 0) },
    };
    cell.Persistent.Add(anchor);

    // aliases: 0 Caralion, 1 Willem (forced, the hall's refs), 2 Vohd, 3 the head, 4-7 the sellswords, 8 the lair, 9-11 the
    // ambush spots (filled by the script), 12 the player (the load event)
    QuestAlias Ref(uint id, string name, QuestAlias.Flag flags = QuestAlias.Flag.Optional) =>
        new() { ID = id, Name = name, Type = QuestAlias.TypeEnum.Reference, Flags = flags };
    // optional (in game, condemned, he stayed essential): Condemned() clears the alias to lift his
    // protection, and the game refuses to clear a non-optional one ("Cannot clear a non-optional alias")
    var aCaralion = Ref(0, "Caralion", QuestAlias.Flag.Essential | QuestAlias.Flag.AllowReserved | QuestAlias.Flag.Optional);
    aCaralion.ForcedReference = new FormLinkNullable<IPlacedGetter>(NamedRef("AGHallResidentNoble"));
    var aWillem = Ref(1, "Willem", QuestAlias.Flag.AllowReserved);
    aWillem.ForcedReference = new FormLinkNullable<IPlacedGetter>(NamedRef("AGHallGuildMaster"));
    quest.Aliases.Add(aCaralion); quest.Aliases.Add(aWillem);
    quest.Aliases.Add(Ref(2, "Vohd", QuestAlias.Flag.Optional | QuestAlias.Flag.AllowReserved));
    quest.Aliases.Add(Ref(3, "VohdHead", QuestAlias.Flag.Optional | QuestAlias.Flag.QuestObject));
    var sellswords = cq.GetProperty("sellswords").GetInt32();
    for (var i = 0; i < sellswords; i++) quest.Aliases.Add(Ref((uint)(4 + i), $"Sellsword{i + 1}", QuestAlias.Flag.Optional | QuestAlias.Flag.AllowReserved));
    var spotBase = (uint)(4 + sellswords);
    quest.Aliases.Add(Ref(spotBase, "Lair"));
    var ambushSpots = cq.GetProperty("spots").GetProperty("ambush").GetArrayLength();
    for (var i = 0; i < ambushSpots; i++) quest.Aliases.Add(Ref(spotBase + 1 + (uint)i, $"Ambush{i + 1}"));
    var playerAliasId = spotBase + 1 + (uint)ambushSpots;
    var aPlayer = Ref(playerAliasId, "Player", QuestAlias.Flag.AllowReserved);
    aPlayer.ForcedReference = new FormLinkNullable<IPlacedGetter>(new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x14));
    quest.Aliases.Add(aPlayer);
    quest.NextAliasID = playerAliasId + 1;

    // stages (the script sets each, plans/caralion-quest.md): 10 started, 20 the hall scene, 30 Vohd placed, 40 Vohd dead,
    // 50 the head taken (the ambush), 60 Caralion yields, 65 spared, 66 condemned, 70 back to Willem, 80 told of the ambush,
    // 100 done; 25 Willem's word after the scene
    var journal = cq.GetProperty("journal");
    foreach (var s in new ushort[] { 10, 20, 25, 30, 40, 50, 60, 65, 66, 70, 80, 100 })
    {
        var entry = new QuestLogEntry { Flags = s == 100 ? QuestLogEntry.Flag.CompleteQuest : 0 };
        if (journal.TryGetProperty(s.ToString(), out var text)) entry.Entry = text.GetString();
        quest.Stages.Add(new QuestStage { Index = s, LogEntries = { entry } });
    }
    var lairAlias = (int)spotBase;
    foreach (var o in cq.GetProperty("objectives").EnumerateObject())
    {
        var ix = ushort.Parse(o.Name);
        var target = ix switch { 10 or 20 => 2, _ => 1 };   // Vohd (alive, then his body), then Willem
        quest.Objectives.Add(new QuestObjective { Index = ix, DisplayText = o.Value.GetString(),
            Targets = { new QuestObjectiveTarget { AliasID = target } } });
    }

    // the lines: a topic each (scene, custom or player choice), the speaker's INFO with its conditions
    ConditionFloat Stage(CompareOperator op, float v) { var d = new GetStageConditionData(); d.Quest.Link.SetTo(quest.FormKey); return new() { CompareOperator = op, ComparisonValue = v, Data = d }; }
    // Willem's sale of Caralion's old room waits for this quest's end (it was offered before the ambush
    // was reported and the head handed in): the head handed in (100), or the quest not running at all (Caralion dead
    // without it). The offer's own "dead OR gone" stays; ORs bind first, so it reads (dead OR gone) AND (100 OR not running)
    if (mod.DialogTopics.SelectMany(t => t.Responses).FirstOrDefault(r => r.EditorID == "AGHallInfo_AGHallGuildMaster_room5_offer") is { } roomOffer)
    {
        var done = new GetStageDoneConditionData(); done.Quest.Link.SetTo(quest.FormKey); done.Stage = 100;
        var runs = new GetQuestRunningConditionData(); runs.Quest.Link.SetTo(quest.FormKey);
        roomOffer.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = done, Flags = Condition.Flag.OR });
        roomOffer.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 0, Data = runs });
    }
    DialogTopic Topic(string ed, DialogTopic.CategoryEnum cat, DialogTopic.SubtypeEnum sub, string subName, string? prompt = null, DialogBranch? branch = null)
    {
        var t = new DialogTopic(NewKey(), SkyrimRelease.SkyrimSE)
        {
            EditorID = ed, Priority = 50, Quest = quest.ToNullableLink(), Category = cat, Subtype = sub, SubtypeName = new RecordType(subName), Name = prompt,
        };
        if (branch != null) t.Branch.SetTo(branch.FormKey);
        mod.DialogTopics.Add(t);
        return t;
    }
    DialogResponses Line(DialogTopic t, string key, string? fragment = null, string? begin = null)
    {
        var l = cq.GetProperty("lines").GetProperty(key);
        var npc = l.GetProperty("npc").GetString()!;
        var info = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = $"AGHallInfo_{npc}_caralionq_{key}", Flags = new DialogResponseFlags() };
        var part = 0;
        foreach (var text in l.GetProperty("parts").EnumerateArray().Select(x => x.GetString()!))   // (split as the talks are: caralion_quest.json)
        {
            info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = (byte)++part });
            cqLines.Add(($"{npc}:caralionq:{key}#{part}", npc, info.FormKey.ID, part, text, t.EditorID!));
        }
        var isId = new GetIsIDConditionData(); isId.Object.Link.SetTo(Hall(npc).FormKey);
        info.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = isId });
        // (in game, his reply played and Willem never came) a line's fragment runs only on its script,
        // and the game makes that script only when the line lists it: every one of Skyrim.esm's 5,540 lines with fragments
        // does, as the promotion trials' (which run in game) do. Caralion's listed none, so none of his fragments ran
        if (fragment != null || begin != null)
            info.VirtualMachineAdapter = new DialogResponsesAdapter
            {
                Scripts = { new ScriptEntry { Name = "AGHallCaralionTIF" } },
                ScriptFragments = new ScriptFragments
                {
                    FileName = "AGHallCaralionTIF",
                    OnBegin = begin == null ? null : new ScriptFragment { ScriptName = "AGHallCaralionTIF", FragmentName = begin },
                    OnEnd = fragment == null ? null : new ScriptFragment { ScriptName = "AGHallCaralionTIF", FragmentName = fragment },
                },
            };
        if (t.Responses.Count > 0) info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(t.Responses[^1].FormKey);
        t.Responses.Add(info);
        return info;
    }

    // stage 20, the hall: Caralion walks up to the player (a copy of vanilla's bounty collector's force-greet) and complains
    // (C1); its end starts the scene: Willem's contract (W1), Caralion's last word (C2)
    var tC1 = Topic("AGHallCaralionC1", DialogTopic.CategoryEnum.Misc, DialogTopic.SubtypeEnum.ForceGreet, "FRCE");
    tC1.Category = DialogTopic.CategoryEnum.Topic; tC1.Subtype = DialogTopic.SubtypeEnum.Custom; tC1.SubtypeName = new RecordType("CUST");
    var c1 = Line(tC1, "C1");
    c1.Conditions.Add(Stage(CompareOperator.EqualTo, 10));
    // (in game, at stage 10 he walked up but the menu showed his everyday topics) as every vanilla
    // force-greet topic (Aela's C03, Mercer's TG02, Tolfdir's MG05...) C1 sits in a blocking branch of its own, and its
    // line says goodbye, so the scene its fragment starts (its actors pause for dialogue) is not left waiting on his menu,
    // as vanilla's one-line hand-off dunDarklightIllia does. C5 (the shout he Says) gets a plain branch: Skyrim.esm has no
    // topic without one. The branches take IDs of their own (0x1E10, after the Cloudrest armor), so no voiced line moves.
    // (a second test: with the branch blocking, his line played and no window opened, as with the
    // goodbye; the window opened on 11-09, before the branch blocked) the challenge branch no longer blocks: his window
    // opens, with the player's reply (C1r) beside his everyday topics
    // (the Dawnguard recruiter and the courier hold the camera and show the window only once
    // they finish speaking; Caralion's window popped while he spoke) blocking again, as the recruiter's
    // DLC1VQ00 branch is: the same records otherwise (a plain line linking to the player's replies). The no-window fault
    // of 11-10 was the reply with no words (C1r), not the blocking flag
    var (c1Branch, c5Branch) = InIds(0x1E10u, 0x1E20u, "Caralion's branches", () =>
    {
        var b1 = new DialogBranch(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallCaralionChallengeBranch", Quest = quest.ToLink<IQuestGetter>(), Category = DialogBranch.CategoryType.Player, Flags = DialogBranch.Flag.Blocking };
        var b5 = new DialogBranch(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallCaralionShoutBranch", Quest = quest.ToLink<IQuestGetter>(), Category = DialogBranch.CategoryType.Player, Flags = DialogBranch.Flag.Blocking };   // (the ambush talk since 2026-11-11: C4, then C5)
        mod.DialogBranches.Add(b1); mod.DialogBranches.Add(b5);
        return (b1, b5);
    });
    c1Branch.StartingTopic.SetTo(tC1.FormKey); tC1.Branch.SetTo(c1Branch.FormKey);
    // (in game, with C1 saying goodbye no window opened, and its fragment never ran, so the scene never
    // started) C1 opens his window again, and the player's one reply (C1r, "Is that a threat?") closes it: his
    // answer to it is silent and says goodbye, and its fragment starts the scene, where Willem cuts in (W1). The reply's
    // topic and line take IDs of their own (0x1E20), so no voiced line moves
    InIds(0x1E20u, 0x1E30u, "Caralion's challenge reply", () =>
    {
        var t = Topic("AGHallCaralionC1r", DialogTopic.CategoryEnum.Topic, DialogTopic.SubtypeEnum.Custom, "CUST",
            cq.GetProperty("lines").GetProperty("C1r").GetProperty("prompt").GetString(), c1Branch);
        var r = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE)
        {
            EditorID = "AGHallInfo_AGHallResidentNoble_caralionq_C1r", Flags = new DialogResponseFlags { Flags = DialogResponses.Flag.Goodbye },
            VirtualMachineAdapter = new DialogResponsesAdapter
            {
                Scripts = { new ScriptEntry { Name = "AGHallCaralionTIF" } },   // (its fragment runs only on a listed script: Line above)
                ScriptFragments = new ScriptFragments { FileName = "AGHallCaralionTIF", OnEnd = new ScriptFragment { ScriptName = "AGHallCaralionTIF", FragmentName = "Fragment_C1" } },
            },
        };
        // (a third test: his line played and still no window) the game drops a reply whose answer
        // has no words, and Skyrim.esm has none: of 4,482 replies a line links to, every one has words (1,038 more share
        // another line's). So he answers, with Yngvar's vanilla line, voiced as his other lines are
        var c1rText = cq.GetProperty("lines").GetProperty("C1r").GetProperty("text").GetString()!;
        r.Responses.Add(new DialogResponse { Text = c1rText, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
        cqLines.Add(("AGHallResidentNoble:caralionq:C1r#1", "AGHallResidentNoble", r.FormKey.ID, 1, c1rText, t.EditorID!));
        var isId = new GetIsIDConditionData(); isId.Object.Link.SetTo(Hall("AGHallResidentNoble").FormKey);
        r.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = isId });
        r.Conditions.Add(Stage(CompareOperator.EqualTo, 10));
        t.Responses.Add(r);
        c1.LinkTo.Add(new FormLink<IDialogTopicGetter>(t.FormKey));
        return t;
    });
    var scene = new Scene(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallCaralionScene", Flags = Scene.Flag.ShowAllText, Quest = quest.ToNullableLink() };
    foreach (var id in new uint[] { 0, 1 })
        scene.Actors.Add(new SceneActor { ID = id, Flags = 0, BehaviorFlags = SceneActor.BehaviorFlag.DeathEnd | SceneActor.BehaviorFlag.CombatEnd | SceneActor.BehaviorFlag.DialoguePause });
    // who each speaker looks at (the action's headtrack alias, as vanilla's two-NPC scenes set it: MQSovngardeConv2, 5 looks
    // at 6 and 6 at 5): Willem's W1 is said to Caralion, so he looks at him; Caralion's C2 is said to the player (-1: no
    // alias, the player). With none set, Willem spoke to Caralion while looking at the player
    var sceneLines = new[] { ("W1", 1u, 0), ("C2", 0u, -1) };
    for (var i = 0; i < sceneLines.Length; i++)
    {
        var (key, actor, lookAt) = sceneLines[i];
        var t = Topic($"AGHallCaralion{key}", DialogTopic.CategoryEnum.Scene, DialogTopic.SubtypeEnum.Scene, "SCEN");
        Line(t, key);
        scene.Phases.Add(new ScenePhase { Name = "", Unused = new ScenePhaseUnusedData(), Unused2 = new ScenePhaseUnusedData(), EditorWidth = 200 });
        scene.Actions.Add(new SceneAction { Type = SceneAction.TypeEnum.Dialog, Name = "", ActorID = (int)actor, Index = (uint)(i + 1), StartPhase = (uint)i, EndPhase = (uint)i,
            Topic = new FormLinkNullable<IDialogTopicGetter>(t.FormKey), HeadtrackActorID = lookAt, LoopingMax = 10, LoopingMin = 1, Emotion = Emotion.Neutral, EmotionValue = 0 });
    }
    scene.LastActionIndex = (uint)sceneLines.Length;
    mod.Scenes.Add(scene);
    // 20-50: while the race runs, his idle (in the hall's idle topic, ahead of his everyday idles, at their rate)
    var idleTopic = mod.DialogTopics.First(t => t.EditorID == "AGHallClerkTopicIdle");
    {
        var tmp = Topic("AGHallCaralionC3Holder", DialogTopic.CategoryEnum.Misc, DialogTopic.SubtypeEnum.Idle, "IDLE");
        var c3 = Line(tmp, "C3");
        tmp.Responses.Remove(c3); mod.DialogTopics.Remove(tmp);
        foreach (var x in cqLines.Where(x => x.Topic == tmp.EditorID).ToList()) { cqLines.Remove(x); cqLines.Add((x.Key, x.Npc, x.Id, x.Part, x.Text, idleTopic.EditorID!)); }
        c3.Conditions.AddRange(InHallCells());
        c3.Conditions.Add(Stage(CompareOperator.GreaterThanOrEqualTo, 20)); c3.Conditions.Add(Stage(CompareOperator.LessThan, 50));
        c3.Conditions.AddRange(Idling("AGHallResidentNoble"));
        c3.Flags!.ResetHours = 4;   // (the hall's idles' rate)
        c3.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>();
        idleTopic.Responses.Insert(0, c3);
        if (idleTopic.Responses.Count > 1) idleTopic.Responses[1].PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(c3.FormKey);
    }
    // 50: the ambush. (in game, his shout, Said by the script, was never heard, and nothing told the
    // player what was happening) a locked talk, as the challenge: he walks up (his force-greet, blocking branch) with C4,
    // the player's one reply "Come and take it." is C5's topic, and his answer is C5 (his order to his men, the same
    // voiced line: its topic keeps its name, so its file does); its end starts the fight, as walking away from C4 does
    var tC5 = Topic("AGHallCaralionC5", DialogTopic.CategoryEnum.Topic, DialogTopic.SubtypeEnum.Custom, "CUST",
        cq.GetProperty("lines").GetProperty("C5").GetProperty("prompt").GetString(), c5Branch);
    var c5 = Line(tC5, "C5", "Fragment_Attack");
    c5.Flags!.Flags |= DialogResponses.Flag.Goodbye;
    c5.Conditions.Add(Stage(CompareOperator.EqualTo, 50));
    var (tC4, fgAmbush) = InIds(0x1E60u, 0x1E70u, "Caralion's ambush talk", () =>
    {
        var t = Topic("AGHallCaralionC4", DialogTopic.CategoryEnum.Topic, DialogTopic.SubtypeEnum.Custom, "CUST", null, c5Branch);
        var c4 = Line(t, "C4", null, "Fragment_AmbushTalk");
        c4.Conditions.Add(Stage(CompareOperator.EqualTo, 50));
        c4.LinkTo.Add(new FormLink<IDialogTopicGetter>(tC5.FormKey));
        return (t, ForceGreet("WEBountyCollectorForcegreet", "AGHallCaralionPkgAmbush", t, 50, close: true, run: true));
    });
    c5Branch.StartingTopic.SetTo(tC4.FormKey);
    // 60: he yields (a copy of vanilla's force-greet after bleedout); the player spares him or condemns him. Blocking, as
    // vanilla's DGIntimidateVictory branch (2026-11-09). Walking away from his plea without choosing condemns him:
    // Q4's begin starts the quest watching the dialogue menu close (AGHallCaralionQuestScript.WatchWalkAway)
    var yieldBranch = new DialogBranch(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallCaralionYieldBranch", Quest = quest.ToLink<IQuestGetter>(), Category = DialogBranch.CategoryType.Player, Flags = DialogBranch.Flag.Blocking };
    mod.DialogBranches.Add(yieldBranch);
    var tQ4 = Topic("AGHallCaralionQ4", DialogTopic.CategoryEnum.Topic, DialogTopic.SubtypeEnum.Custom, "CUST", null, yieldBranch);
    yieldBranch.StartingTopic.SetTo(tQ4.FormKey);
    var q4 = Line(tQ4, "Q4", null, "Fragment_Yield");
    q4.Conditions.Add(Stage(CompareOperator.EqualTo, 60));
    foreach (var (key, frag) in new[] { ("Q4a", "Fragment_Spare"), ("Q4b", "Fragment_Condemn") })
    {
        var t = Topic($"AGHallCaralion{key}", DialogTopic.CategoryEnum.Topic, DialogTopic.SubtypeEnum.Custom, "CUST", cq.GetProperty("lines").GetProperty(key).GetProperty("prompt").GetString(), yieldBranch);
        var r = Line(t, key, frag);
        r.Flags!.Flags |= DialogResponses.Flag.Goodbye;
        r.Conditions.Add(Stage(CompareOperator.EqualTo, 60));
        q4.LinkTo.Add(new FormLink<IDialogTopicGetter>(t.FormKey));
    }
    // 70-80: back at the hall, Willem: the player's account of the ambush (W2t), then the head (W2)
    var willemBranch = new DialogBranch(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallCaralionWillemBranch", Quest = quest.ToLink<IQuestGetter>(), Category = DialogBranch.CategoryType.Player, Flags = DialogBranch.Flag.TopLevel };
    mod.DialogBranches.Add(willemBranch);
    var tW2t = Topic("AGHallCaralionW2t", DialogTopic.CategoryEnum.Topic, DialogTopic.SubtypeEnum.Custom, "CUST", cq.GetProperty("lines").GetProperty("W2t").GetProperty("prompt").GetString(), willemBranch);
    willemBranch.StartingTopic.SetTo(tW2t.FormKey);
    var w2t = Line(tW2t, "W2t", "Fragment_Told");
    w2t.Conditions.Add(Stage(CompareOperator.EqualTo, 70));
    var tW2 = Topic("AGHallCaralionW2", DialogTopic.CategoryEnum.Topic, DialogTopic.SubtypeEnum.Custom, "CUST", cq.GetProperty("lines").GetProperty("W2").GetProperty("prompt").GetString(), willemBranch);
    var w2 = Line(tW2, "W2", "Fragment_HandIn");
    w2.Conditions.Add(Stage(CompareOperator.EqualTo, 80));
    var holds = new GetItemCountConditionData { RunOnType = Condition.RunOnType.Reference }; holds.Reference.SetTo(new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x14)); holds.ItemOrList.Link.SetTo(head.FormKey);
    w2.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.GreaterThanOrEqualTo, ComparisonValue = 1, Data = holds });
    w2t.LinkTo.Add(new FormLink<IDialogTopicGetter>(tW2.FormKey));
    foreach (var i in new[] { w2t, w2 }) i.Conditions.InsertRange(1, InHallCells());

    // Caralion's force-greets: walking up to the player in the hall (stage 10) and after his bleedout (stage 60)
    Package ForceGreet(string src, string ed, DialogTopic t, int stage, bool close = false, bool run = false)
    {
        var pk = (Package)Ed<IPackageGetter>(src).Duplicate(NewKey());
        pk.EditorID = ed; pk.Conditions.Clear();
        // (Caralion and Willem stopped across the room from the player) the bounty collector greets from
        // 512 (input 0x4B, "Forcegreet Distance"), about 7 m, and the scene played where he stopped; Helgen Reborn's Balok
        // greets from 200, at arm's length, as these do
        if (close) ((PackageDataLocation)pk.Data[0x4B]).Location.Radius = 200;
        pk.OwnerQuest.SetTo(quest.FormKey);
        pk.VirtualMachineAdapter = null;
        // in the hall he walks up, a noble with a complaint; at the ambush he runs, as the bounty collector does (the
        // player walked right past him at the old spots, so he stands closer and runs)
        pk.PreferredSpeed = run ? Package.Speed.Run : Package.Speed.Walk;
        pk.Conditions.Add(Stage(CompareOperator.EqualTo, stage));
        var topics = pk.Data.Values.OfType<PackageDataTopic>().FirstOrDefault() ?? throw new Exception($"{src}: no topic input");
        topics.Topics.Clear();
        topics.Topics.Add(new TopicReference { Reference = new FormLink<IDialogTopicGetter>(t.FormKey) });
        mod.Packages.Add(pk);
        return pk;
    }
    var fgHall = ForceGreet("WEBountyCollectorForcegreet", "AGHallCaralionPkgChallenge", tC1, 10, close: true);
    fgHall.Conditions.AddRange(InHallCells(new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x14)));
    var fgYield = ForceGreet("DGForceGreetAfterBleedoutPackage", "AGHallCaralionPkgYield", tQ4, 60);
    // (both Caralion and Willem must be ready and present for the scene) while Caralion walks
    // up (10) and through the scene (20), Willem follows him, as MS11's guard follows Jorleif (a copy of it: within
    // 128-256, accompanying), so the Guildmaster is at hand when he cuts in, and out of his bed or chair whatever his hour;
    // in the scene Caralion holds where he stands, as the Markarth wizard's StayAtCurrentLocation scene package does. The
    // quest script starts the scene only once Willem is beside them (AGHallCaralionQuestScript.Challenged). IDs of their own
    var (pkWillem, pkHold) = InIds(0x1E30u, 0x1E40u, "the challenge scene's places", () =>
    {
        var w = (Package)Ed<IPackageGetter>("MS11GuardFollowJorleif").Duplicate(NewKey());
        w.EditorID = "AGHallCaralionPkgWillemFollow"; w.Conditions.Clear(); w.OwnerQuest.SetTo(quest.FormKey); w.VirtualMachineAdapter = null;
        // the guard's package draws the weapon (flag 0x800000, Weapon Drawn): not his, so Willem does not
        // draw his weapon
        w.Flags &= ~Package.Flag.WeaponDrawn;
        w.Data.Values.OfType<PackageDataTarget>().First().Target = new PackageTargetAlias { Alias = 0 };
        w.Conditions.Add(Stage(CompareOperator.GreaterThanOrEqualTo, 10));
        w.Conditions.Add(Stage(CompareOperator.LessThan, 30));
        var h = (Package)Ed<IPackageGetter>("dunMarkarthWizard_StayAtCurrentLocationAicantarScene").Duplicate(NewKey());
        h.EditorID = "AGHallCaralionPkgHold"; h.Conditions.Clear(); h.OwnerQuest.SetTo(quest.FormKey); h.VirtualMachineAdapter = null;
        h.Conditions.Add(Stage(CompareOperator.EqualTo, 20));
        mod.Packages.Add(w); mod.Packages.Add(h);
        return (w, h);
    });
    // 25: the scene over, Willem turns to the player and closes it, as vanilla's exchanges end on a talk with the quest's
    // giver: his word (W3), then "One troll head coming right up." (W3a: his "Good hunting.", a
    // vanilla line, since the game drops a reply whose answer has no words; it ends the talk and places Vohd, 30) or
    // "Anything I should be worried about?" (W3q: his answer, then both choices again). Walking away from his window
    // places Vohd too (W3's begin watches the menu, as Q4's does). His force-greet comes first in his alias's list, ahead
    // of his following. IDs of their own (0x1E40)
    var pkWillemWord = InIds(0x1E40u, 0x1E60u, "Willem's word after the scene", () =>
    {
        var wb = new DialogBranch(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallCaralionWillemWordBranch", Quest = quest.ToLink<IQuestGetter>(), Category = DialogBranch.CategoryType.Player, Flags = DialogBranch.Flag.Blocking };   // (blocking, as the recruiter's: above)
        mod.DialogBranches.Add(wb);
        var tW3 = Topic("AGHallCaralionW3", DialogTopic.CategoryEnum.Topic, DialogTopic.SubtypeEnum.Custom, "CUST", null, wb);
        wb.StartingTopic.SetTo(tW3.FormKey);
        var w3 = Line(tW3, "W3", null, "Fragment_WillemWord");
        var tW3a = Topic("AGHallCaralionW3a", DialogTopic.CategoryEnum.Topic, DialogTopic.SubtypeEnum.Custom, "CUST",
            cq.GetProperty("lines").GetProperty("W3a").GetProperty("prompt").GetString(), wb);
        var w3a = Line(tW3a, "W3a", "Fragment_Accepted");
        w3a.Flags!.Flags |= DialogResponses.Flag.Goodbye;
        var tW3q = Topic("AGHallCaralionW3q", DialogTopic.CategoryEnum.Topic, DialogTopic.SubtypeEnum.Custom, "CUST",
            cq.GetProperty("lines").GetProperty("W3q").GetProperty("prompt").GetString(), wb);
        var w3q = Line(tW3q, "W3q");
        foreach (var i in new[] { w3, w3a, w3q }) i.Conditions.Add(Stage(CompareOperator.EqualTo, 25));
        foreach (var i in new[] { w3, w3q }) { i.LinkTo.Add(new FormLink<IDialogTopicGetter>(tW3a.FormKey)); i.LinkTo.Add(new FormLink<IDialogTopicGetter>(tW3q.FormKey)); }
        return ForceGreet("WEBountyCollectorForcegreet", "AGHallCaralionPkgWillemWord", tW3, 25, close: true);
    });
    aWillem.PackageData.Add(pkWillemWord.ToLink<IPackageGetter>());
    aWillem.PackageData.Add(pkWillem.ToLink<IPackageGetter>());
    aCaralion.PackageData.Add(pkHold.ToLink<IPackageGetter>());
    aCaralion.PackageData.Add(fgAmbush.ToLink<IPackageGetter>());
    aCaralion.PackageData.Add(fgHall.ToLink<IPackageGetter>());
    aCaralion.PackageData.Add(fgYield.ToLink<IPackageGetter>());

    // the scripts: the quest's own (the stages), and on the aliases Vohd (his death), the head (taken), Caralion (his
    // bleedout) and the player (each load: Vohd's level set again)
    ScriptObjectProperty Obj(string name, IMajorRecordGetter r) => new() { Name = name, Object = new FormLink<ISkyrimMajorRecordGetter>(r.FormKey), Flags = ScriptProperty.Flag.Edited };
    ScriptObjectProperty AliasProp(string name, int alias) => new() { Name = name, Object = quest.ToLink<ISkyrimMajorRecordGetter>(), Alias = (short)alias, Flags = ScriptProperty.Flag.Edited };
    var qs = new ScriptEntry { Name = "AGHallCaralionQuestScript", Properties = {
        AliasProp("CaralionAlias", 0), AliasProp("WillemAlias", 1), AliasProp("VohdAlias", 2), AliasProp("HeadAlias", 3), AliasProp("LairAlias", (int)spotBase),
        Obj("VohdBase", vohd), Obj("SellswordBase", merc), Obj("HeadItem", head), Obj("Anchor", anchor), Obj("GoldenHand", hand), Obj("ChallengeScene", scene), Obj("GoneGlobal", mod.Globals.First(g => g.EditorID == "AGHallCaralionGoneGlobal")), Obj("ShoutTopic", tC5),
        Obj("XMarker", Ed<IStaticGetter>("XMarker")),
        new ScriptFloatListProperty { Name = "LairSpot", Data = new ExtendedList<float>(cq.GetProperty("spots").GetProperty("lair").EnumerateArray().Select(x => x.GetSingle())), Flags = ScriptProperty.Flag.Edited },
        new ScriptFloatListProperty { Name = "AmbushSpots", Data = new ExtendedList<float>(cq.GetProperty("spots").GetProperty("ambush").EnumerateArray().SelectMany(a => a.EnumerateArray().Select(x => x.GetSingle()))), Flags = ScriptProperty.Flag.Edited },
        new ScriptIntProperty { Name = "LevelsAbovePlayer", Data = cq.GetProperty("vohd").GetProperty("levelsAbovePlayer").GetInt32(), Flags = ScriptProperty.Flag.Edited },
    } };
    var sellProps = new ScriptObjectListProperty { Name = "SellswordAliases", Flags = ScriptProperty.Flag.Edited };
    for (var i = 0; i < sellswords; i++) sellProps.Objects.Add(new ScriptObjectProperty { Object = quest.ToLink<ISkyrimMajorRecordGetter>(), Alias = (short)(4 + i) });
    var ambushProps = new ScriptObjectListProperty { Name = "AmbushAliases", Flags = ScriptProperty.Flag.Edited };
    for (var i = 0; i < ambushSpots; i++) ambushProps.Objects.Add(new ScriptObjectProperty { Object = quest.ToLink<ISkyrimMajorRecordGetter>(), Alias = (short)(spotBase + 1 + i) });
    qs.Properties.Add(sellProps); qs.Properties.Add(ambushProps);
    // his Cloudrest armor: whatever of it is still in his chest, he puts on for the ambush
    if (cloudrest.Count > 0 && hallRefs.TryGetValue("AGHallChestRoom5", out var cChest))
    {
        var armorProp = new ScriptObjectListProperty { Name = "CloudrestArmor", Flags = ScriptProperty.Flag.Edited };
        foreach (var a in cloudrest) armorProp.Objects.Add(new ScriptObjectProperty { Object = a.ToLink<ISkyrimMajorRecordGetter>() });
        qs.Properties.Add(armorProp);
        qs.Properties.Add(new ScriptObjectProperty { Name = "CaralionChest", Object = new FormLink<ISkyrimMajorRecordGetter>(cChest.FormKey), Flags = ScriptProperty.Flag.Edited });
    }
    else Console.WriteLine("WARNING Caralion's quest: no Cloudrest armor or chest; he fights in his clothes");
    QuestFragmentAlias AliasScript(int alias, string script) => new()
    {
        Property = new ScriptObjectProperty { Object = quest.ToLink<ISkyrimMajorRecordGetter>(), Alias = (short)alias },
        Scripts = { new ScriptEntry { Name = script } },
    };
    quest.VirtualMachineAdapter = new QuestAdapter
    {
        Scripts = { qs },
        Aliases = { AliasScript(0, "AGHallCaralionAliasCaralion"), AliasScript(2, "AGHallCaralionAliasVohd"), AliasScript(3, "AGHallCaralionAliasHead"), AliasScript((int)playerAliasId, "AGHallCaralionAliasPlayer") },
    };

    // the start, and his death: a start-game quest of its own with Caralion and the player in aliases
    // (AGHallCaralionWatchScript): it starts the quest when the player's party passes his on the leader board; his death
    // before it disbands his party (LeaderBoardEndRival 3), his death after the player condemned him ends it (1)
    var watch = new Quest(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallCaralionWatch", Flags = Quest.Flag.StartGameEnabled | Quest.Flag.RunOnce, Priority = 10, NextAliasID = 2 };
    var wCaralion = Ref(0, "Caralion", QuestAlias.Flag.AllowReserved);
    wCaralion.ForcedReference = new FormLinkNullable<IPlacedGetter>(NamedRef("AGHallResidentNoble"));
    var wPlayer = Ref(1, "Player", QuestAlias.Flag.AllowReserved);
    wPlayer.ForcedReference = new FormLinkNullable<IPlacedGetter>(new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x14));
    watch.Aliases.Add(wCaralion); watch.Aliases.Add(wPlayer);
    watch.VirtualMachineAdapter = new QuestAdapter
    {
        Scripts = { new ScriptEntry { Name = "AGHallCaralionWatchScript", Properties = {
            Obj("CaralionQuest", quest),
            new ScriptObjectProperty { Name = "PassedRival", Object = new FormLink<ISkyrimMajorRecordGetter>(new FormKey(agEsp, 0xFDD)), Flags = ScriptProperty.Flag.Edited },
            new ScriptObjectProperty { Name = "CaralionAlias", Object = watch.ToLink<ISkyrimMajorRecordGetter>(), Alias = 0, Flags = ScriptProperty.Flag.Edited } } } },
        Aliases = {
            new QuestFragmentAlias { Property = new ScriptObjectProperty { Object = watch.ToLink<ISkyrimMajorRecordGetter>(), Alias = 0 }, Scripts = { new ScriptEntry { Name = "AGHallCaralionWatchAlias" } } },
            new QuestFragmentAlias { Property = new ScriptObjectProperty { Object = watch.ToLink<ISkyrimMajorRecordGetter>(), Alias = 1 }, Scripts = { new ScriptEntry { Name = "AGHallCaralionWatchPlayer" } } },
        },
    };
    mod.Quests.Add(watch);

    CheckTakes(cqLines.Select(l => (l.Key, l.Id)));
    if (merge) File.WriteAllText(Path.Combine(npcsDir, "build", "caralion_lines.json"), JsonSerializer.Serialize(cqLines.Select(l => new { key = l.Key, npc = l.Npc,
        voice = VoiceOf(l.Npc), info = $"{l.Id:X8}", response = l.Part, quest = quest.EditorID, topic = l.Topic, text = l.Text }), new JsonSerializerOptions { WriteIndented = true }));
    Console.WriteLine($"caralion quest: {quest.Stages.Count} stages, {quest.Aliases.Count} aliases, {cqLines.Count} spoken parts");
    if (next > 0x1760) throw new Exception($"Caralion's quest ran to 0x{next:X}, into the board talk's block at 0x1760");
}

// The party leaderboard in the Guild talk (board_talk.json): new choices under existing
// Guild talk nodes ('under'). Own ID block (0x1760 here, 0x8F60 merged), after Caralion's quest, so no recorded line moves.
// The new choice joins its parent's list the way the talk builder would have put it there: an answer that already had
// follow-ups gains one more (every INFO offering that list offers it), and one that had none now offers it with the back
// choice up a level. Its own answer offers that same list again, as the talk builder's answers do. Held out until every
// voice file is in.
var btPath = Path.Combine(npcsDir, "board_talk.json");
if (File.Exists(btPath))
{
    next = Math.Max(next, 0x1760u);
    var gtNodes = JsonDocument.Parse(File.ReadAllText(Path.Combine(npcsDir, "guild_talk.json"))).RootElement.GetProperty("groups").EnumerateArray()
        .SelectMany(g => g.GetProperty("nodes").EnumerateArray()).ToDictionary(n => n.GetProperty("id").GetString()!, n => n.GetProperty("parent").GetString());
    var btLines = new List<(string Key, string Npc, uint Id, int Part, string Text, string Topic)>();
    var btTopics = new List<(DialogTopic Topic, string Under)>();
    foreach (var n in JsonDocument.Parse(File.ReadAllText(btPath)).RootElement.GetProperty("nodes").EnumerateArray())
    {
        var id = n.GetProperty("id").GetString()!;
        var under = n.GetProperty("under").GetString()!;
        if (!gtNodes.ContainsKey(under)) throw new Exception($"board talk: {id} is under {under}, which guild_talk.json does not have");
        var t = new DialogTopic(NewKey(), SkyrimRelease.SkyrimSE)
        {
            EditorID = $"AGHallTalk{id}", Name = n.GetProperty("prompt").GetString(), Priority = 50, Quest = clerkQuest.ToNullableLink(),
            Category = DialogTopic.CategoryEnum.Topic, Subtype = DialogTopic.SubtypeEnum.Custom, SubtypeName = new RecordType("CUST"),
        };
        foreach (var who in n.GetProperty("says").EnumerateObject())
        {
            var info = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = $"AGHallInfo_{who.Name}_talk_{id}", Flags = new DialogResponseFlags() };
            var part = 0;
            foreach (var text in who.Value.EnumerateArray().Select(p => p.GetString()!))
            {
                if (text.Length > 150) throw new Exception($"board talk: {id} part {part + 1} is {text.Length} characters, over vanilla's 150");
                info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = (byte)++part });
                btLines.Add(($"{who.Name}:talk:{id}#{part}", who.Name, info.FormKey.ID, part, text, t.EditorID!));
            }
            if (t.Responses.Count > 0) info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(t.Responses[^1].FormKey);
            t.Responses.Add(info);
        }
        btTopics.Add((t, under));
    }
    CheckTakes(btLines.Select(l => (l.Key, l.Id)));
    string BtFile(string topic, uint fid, int part)
    {
        var (q, tp) = (clerkQuest.EditorID!, topic);
        if (q.Length + tp.Length > 25) { q = q[..10]; tp = tp[..Math.Min(tp.Length, 25 - q.Length)]; }
        return $"{q}_{tp}_{fid:X8}_{part}.fuz".ToLowerInvariant();
    }
    var btMissing = btLines.Count(l => !File.Exists(Path.Combine(npcsDir, "build", "Sound", "Voice", "AdventurersGuild - Guild Hall.esp", VoiceOf(l.Npc),
        BtFile(l.Topic, l.Id >= 0x8000 ? l.Id : idBase + l.Id, l.Part))));
    DialogTopic? Topic(string ed) => mod.DialogTopics.FirstOrDefault(x => x.EditorID == ed);
    var heldTalk = btTopics.Select(b => b.Under).Distinct().Where(u => Topic($"AGHallTalk{u}") == null).ToList();
    if (heldTalk.Count > 0) Console.WriteLine($"WARNING board talk held out: the Guild talk it hangs from is not in this build ({string.Join(", ", heldTalk)})");
    else if (btMissing > 0 && Environment.GetEnvironmentVariable("AG_TALK_BUILD") != "1")
        Console.WriteLine($"WARNING board talk held out of this build: {btMissing} of {btLines.Count} voice files not in build/Sound yet");
    else
    {
        foreach (var (t, under) in btTopics)
        {
            var parentTopic = Topic($"AGHallTalk{under}")!;
            t.Branch = parentTopic.Branch.FormKeyNullable is { } br ? new FormLinkNullable<IDialogBranchGetter>(br) : t.Branch;
            var link = new FormLink<IDialogTopicGetter>(t.FormKey);
            var children = gtNodes.Where(kv => kv.Value == under).Select(kv => kv.Key).ToList();
            List<FormLink<IDialogTopicGetter>> offer;
            if (children.Count > 0)
            {
                // every INFO that offers the list under 'under' (its first follow-up's topic) offers the new choice too
                var first = Topic($"AGHallTalk{children[0]}")!.FormKey;
                foreach (var info in mod.DialogTopics.SelectMany(x => x.Responses).Where(r => r.LinkTo.Any(l => l.FormKey == first)))
                    if (!info.LinkTo.Any(l => l.FormKey == t.FormKey)) info.LinkTo.Add(link);
                offer = parentTopic.Responses[0].LinkTo.Select(l => new FormLink<IDialogTopicGetter>(l.FormKey)).ToList();
            }
            else
            {
                // an answer with no follow-ups had offered the list above it; now it offers its one follow-up and the back
                // choice to that list (or, where the back choice is not built, that list itself, as before)
                var up = gtNodes[under] ?? throw new Exception($"board talk: {under} is a root with no follow-ups");
                var back = Topic($"AGHallTalkBack{up}");
                offer = new List<FormLink<IDialogTopicGetter>> { link };
                if (back != null) offer.Add(new FormLink<IDialogTopicGetter>(back.FormKey));
                else offer.AddRange(parentTopic.Responses[0].LinkTo.Select(l => new FormLink<IDialogTopicGetter>(l.FormKey)));
                foreach (var info in parentTopic.Responses)
                {
                    info.LinkTo.Clear();
                    foreach (var l in offer) info.LinkTo.Add(new FormLink<IDialogTopicGetter>(l.FormKey));
                }
            }
            foreach (var info in t.Responses)
            {
                // who may hear it: as the answer above it, for the same speaker
                var npc = info.EditorID!["AGHallInfo_".Length..^$"_talk_{t.EditorID!["AGHallTalk".Length..]}".Length];
                var from = parentTopic.Responses.FirstOrDefault(r => r.EditorID == $"AGHallInfo_{npc}_talk_{under}")
                    ?? throw new Exception($"board talk: {info.EditorID} has no answer of {npc}'s under {under} to take its conditions from");
                foreach (var c in from.Conditions) info.Conditions.Add(c.DeepCopy());
                foreach (var l in offer) info.LinkTo.Add(new FormLink<IDialogTopicGetter>(l.FormKey));
            }
            mod.DialogTopics.Add(t);
        }
        Console.WriteLine($"board talk: {btTopics.Count} topics, {btLines.Count} spoken parts");
    }
    if (merge) File.WriteAllText(Path.Combine(npcsDir, "build", "board_talk_lines.json"), JsonSerializer.Serialize(btLines.Select(l => new { key = l.Key, npc = l.Npc,
        voice = VoiceOf(l.Npc), info = $"{l.Id:X8}", response = l.Part, quest = clerkQuest.EditorID, topic = l.Topic, text = l.Text }), new JsonSerializerOptions { WriteIndented = true }));
    if (next > 0x1790) throw new Exception($"the board talk ran to 0x{next:X}, into the board lines' block at 0x1790");
}

// The leaderboard's idles and once-lines (board_lines.json). Own ID block (0x1790 here,
// 0x8F90 merged). Idles: one RANDOM group per NPC in the staff's idle topic, put AHEAD of that NPC's own idles (a topic
// speaks its first group whose conditions pass) and played only within 'near' of the leaderboard's ledger marker; each line
// rolls its chance as the staff's do, so a miss falls through to their usual idles. Once-lines: Say Once, ahead of the
// NPC's hellos, for a member whose party holds that place (AG_LB_PlayerPlaceGlobal). Moving records within a topic keeps
// their IDs. Held out until every voice file is in.
var blPath = Path.Combine(npcsDir, "board_lines.json");
if (File.Exists(blPath))
{
    next = Math.Max(next, 0x1790u);
    var bl = JsonDocument.Parse(File.ReadAllText(blPath)).RootElement;
    var gPlace = new FormKey(agEsp, 0xFDF);   // AG_LB_PlayerPlaceGlobal: the player's party's place on the board, 0 = none
    var blLines = new List<(string Key, string Npc, uint Id, string Text, string Topic)>();
    var blIdles = new List<(string Npc, List<DialogResponses> Infos)>();
    var blOnce = new List<(string Npc, DialogResponses Info)>();
    var idleTopic = mod.DialogTopics.FirstOrDefault(t => t.EditorID == "AGHallClerkTopicIdle");
    var blHello = mod.DialogTopics.FirstOrDefault(t => t.EditorID == clerkHelloEd);
    var anchor = hallNamed.TryGetValue("AGHallLeaderBoardWriteMarker", out var anc) ? anc : (FormKey?)null;
    ConditionFloat Near(float d)
    {
        var c = new GetDistanceConditionData();
        c.Target.Link.SetTo(anchor!.Value);
        return new ConditionFloat { CompareOperator = CompareOperator.LessThan, ComparisonValue = d, Data = c };
    }
    // 'late': lines made after all the others (Marius's, voiced 2026-11-05), so no recorded line's ID moves
    var gRenownLb = new FormKey(agEsp, 0xFDE);   // AG_LB_PartyRenownGlobal: the player's best party's Renown
    var blNear = new Dictionary<string, float>();   // each NPC's 'near', wherever its idles were read from ('idles' or 'late')
    void BlRead(JsonElement bl)
    {
    if (bl.TryGetProperty("idles", out var blIdlesJson))
    foreach (var who in blIdlesJson.EnumerateObject())
    {
        var near = (float)who.Value.GetProperty("near").GetDouble();
        blNear[who.Name] = near;
        var group = who.Value.GetProperty("lines").EnumerateObject().ToList();
        var infos = new List<DialogResponses>();
        for (var k = 0; k < group.Count; k++)
        {
            var info = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE)
            {
                EditorID = $"AGHallInfo_{who.Name}_{group[k].Name}",
                Flags = new DialogResponseFlags { Flags = DialogResponses.Flag.Random | (k == group.Count - 1 ? DialogResponses.Flag.RandomEnd : 0), ResetHours = 4 },
            };
            info.Responses.Add(new DialogResponse { Text = group[k].Value.GetString()!, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
            infos.Add(info);
            blLines.Add(($"{who.Name}:{group[k].Name}", who.Name, info.FormKey.ID, group[k].Value.GetString()!, "AGHallClerkTopicIdle"));
        }
        blIdles.Add((who.Name, infos));
    }
    if (bl.TryGetProperty("once", out var blOnceJson))
    foreach (var who in blOnceJson.EnumerateObject())
        foreach (var line in who.Value.EnumerateObject())
        {
            var info = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE)
            {
                EditorID = $"AGHallInfo_{who.Name}_{line.Name}", Flags = new DialogResponseFlags { Flags = DialogResponses.Flag.SayOnce },
            };
            var text = line.Value.GetProperty("text").GetString()!;
            info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
            if (line.Value.TryGetProperty("place", out var place)) info.Conditions.Add(GlobalIs(gPlace, CompareOperator.EqualTo, place.GetInt32()));
            else info.Conditions.Add(GlobalIs(gRenownLb, CompareOperator.GreaterThan, line.Value.GetProperty("renownAbove").GetInt32()));
            blOnce.Add((who.Name, info));
            blLines.Add(($"{who.Name}:{line.Name}", who.Name, info.FormKey.ID, text, clerkHelloEd));
        }
    }
    BlRead(bl);
    if (bl.TryGetProperty("late", out var blLate)) BlRead(blLate);
    CheckTakes(blLines.Select(l => (l.Key, l.Id)));
    var blMissing = blLines.Count(l => !File.Exists(Path.Combine(npcsDir, "build", "Sound", "Voice", "AdventurersGuild - Guild Hall.esp", VoiceOf(l.Npc),
        $"{clerkQuest.EditorID![..Math.Min(clerkQuest.EditorID!.Length, 10)]}_{l.Topic[..Math.Min(l.Topic.Length, 15)]}_{(l.Id >= 0x8000 ? l.Id : idBase + l.Id):X8}_1.fuz".ToLowerInvariant())));
    // (the file name: as voicelines.voice_filename, quest and topic cut to 10 + 15 letters when together over 25)
    // put a group ahead of the NPC's own first record in a topic, keeping the topic's PreviousDialog chain
    void AheadOf(DialogTopic t, string npc, string slot, List<DialogResponses> infos)
    {
        var at = t.Responses.ToList().FindIndex(r => (r.EditorID ?? "").StartsWith($"AGHallInfo_{npc}_{slot}"));
        // an NPC with no lines of his own in the topic (Marius: the residents have no idles or hellos yet) gets them at its end
        // (only the board lines' own records of his are in the topic then: nothing of his to go ahead of)
        if (at < 0 && t.Responses.Where(r => (r.EditorID ?? "").StartsWith($"AGHallInfo_{npc}_")).All(r => blLines.Any(l => l.Id == r.FormKey.ID)))
        {
            var last = t.Responses.Count > 0 ? t.Responses[^1].FormKey : (FormKey?)null;
            foreach (var i in infos) { i.PreviousDialog = last is { } l ? new FormLinkNullable<IDialogResponsesGetter>(l) : new FormLinkNullable<IDialogResponsesGetter>(); last = i.FormKey; t.Responses.Add(i); }
            return;
        }
        if (at < 0) throw new Exception($"board lines: {npc} has no {slot} in {t.EditorID} to go ahead of");
        var prev = at > 0 ? t.Responses[at - 1].FormKey : (FormKey?)null;
        foreach (var i in infos) { i.PreviousDialog = prev is { } p ? new FormLinkNullable<IDialogResponsesGetter>(p) : new FormLinkNullable<IDialogResponsesGetter>(); prev = i.FormKey; }
        t.Responses[at].PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(prev!.Value);
        for (var k = 0; k < infos.Count; k++) t.Responses.Insert(at + k, infos[k]);
    }
    if (idleTopic == null || blHello == null || anchor == null)
        Console.WriteLine($"WARNING board lines held out: {(anchor == null ? "the hall has no AGHallLeaderBoardWriteMarker" : "the staff lines are not in this build")}");
    else if (blMissing > 0 && Environment.GetEnvironmentVariable("AG_STAFF_BUILD") != "1")
        Console.WriteLine($"WARNING board lines held out of this build: {blMissing} of {blLines.Count} voice files not in build/Sound yet");
    else
    {
        foreach (var (npc, infos) in blIdles)
        {
            var near = blNear[npc];
            foreach (var i in infos) { foreach (var c in At(Hall(npc)).Concat(Idling(npc))) i.Conditions.Add(c.DeepCopy()); i.Conditions.Add(Near(near)); }
            AheadOf(idleTopic, npc, "idle", infos);   // (after the quest's own idles, as Caralion's C3)
        }
        foreach (var (npc, info) in blOnce)
        {
            var once = new List<Condition>(info.Conditions);
            info.Conditions.Clear();
            foreach (var c in At(Hall(npc))) info.Conditions.Add(c.DeepCopy());
            info.Conditions.Add(GlobalIs(gRegistered, CompareOperator.EqualTo, 1));
            info.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = new IsInDialogueWithPlayerConditionData() });
            foreach (var c in once) info.Conditions.Add(c);
            AheadOf(blHello, npc, "hello", new List<DialogResponses> { info });
        }
        Console.WriteLine($"board lines: {blIdles.Sum(g => g.Infos.Count)} idles, {blOnce.Count} once-lines");
    }
    if (merge) File.WriteAllText(Path.Combine(npcsDir, "build", "board_lines.json"), JsonSerializer.Serialize(blLines.Select(l => new { key = l.Key, npc = l.Npc,
        voice = VoiceOf(l.Npc), info = $"{l.Id:X8}", quest = clerkQuest.EditorID, topic = l.Topic, text = l.Text }), new JsonSerializerOptions { WriteIndented = true }));
    if (next > 0x17C0) throw new Exception($"the board lines ran to 0x{next:X}, past their block's end at 0x17C0");
}

// Marius's own talk about the leaderboard (marius_talk.json): the talk
// builder, in the last free IDs (0x17E0-0x17FF, merged 0x8FE0-0x8FFF; the back choice from the top takes topNext's)
if (topNext > 0x17E0) throw new Exception($"the talks' back-from-the-top ran to 0x{topNext:X}, into Marius's talk at 0x17E0");
BuildTalk(Path.Combine(npcsDir, "marius_talk.json"), 0x17E0u, "Marius's talk", "marius_talk_lines.json", true);
// The four adventurers' own conversations (residents_talk.json, residents_talk_export.py), in an
// ID block of their own (0x1B00-0x1BFF, merged 0x9300-0x93FF) so nothing earlier moves; held out until each voice file is in
// build/Sound, as the staff's (AG_TALK_BUILD=1 builds them regardless). Their back-from-the-top takes topNext's next IDs.
if (File.Exists(Path.Combine(npcsDir, "residents_talk.json")))
    InIds(0x1B00u, 0x1C00u, "the adventurers' talks", () => { BuildTalk(Path.Combine(npcsDir, "residents_talk.json"), 0x1B00u, "the adventurers' talks", "residents_talk_lines.json", true); return 0; });

// Banter between the hall's people (banter.json: the staff, the old hands, the adventurers and Caralion's
// rubs, about 30 exchanges), built as the clerks' exchanges are: vanilla's Actor Dialogue event (ADIA) starts a quest when two
// NPCs near each other are free to talk; the quest fills only if they are this pair (Actor1/Actor2 by ID), and its scene plays
// the exchange and ends it. One branch of its own after the clerks', in the hall's cell; one quest node per pair (both alive
// and in the hall), its exchanges picked at random, each once a game day. No hours: a pair only meets where its routines put
// both near each other. Own ID block 0x1C00-0x1DFF (merged 0x9400-0x95FF); held out until every voice file is in build/Sound
// (AG_BANTER_BUILD=1 builds it regardless).
var banterPath = Path.Combine(npcsDir, "banter.json");
if (File.Exists(banterPath))
{
    var banterLines = new List<(string Key, string Npc, uint Id, string Text, string Topic, string Quest)>();
    var bQuests = new List<Quest>(); var bScenes = new List<Scene>(); var bTopics = new List<DialogTopic>(); var bNodes = new List<StoryManagerQuestNode>();
    StoryManagerBranchNode? bBranch = null;
    InIds(0x1C00u, 0x1E00u, "the banter", () =>
    {
        var bd = JsonDocument.Parse(File.ReadAllText(banterPath)).RootElement;
        var sample = Ed<IStoryManagerQuestNodeGetter>("RiverwoodSleepingGiantScenes").Conditions[0].Data;   // how vanilla names the event's data
        Condition Present(FormKey placed, ConditionData d, float want) { d.RunOnType = Condition.RunOnType.Reference; d.Reference.SetTo(placed); return new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = want, Data = d }; }
        bBranch = new StoryManagerBranchNode(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallBanterBranch", MaxConcurrentQuests = 1 };
        bBranch.Parent.SetTo(new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x015FCE));   // the Actor Dialogue event's node
        var chatsBranch = mod.StoryManagerBranchNodes.FirstOrDefault(b => b.EditorID == "AGHallChatsBranch");
        bBranch.PreviousSibling.SetTo(chatsBranch?.FormKey ?? Ed<IStoryManagerBranchNodeGetter>("MainQuestPartyScenes").FormKey);
        var inCell = new GetInCellConditionData { RunOnType = sample.RunOnType, RunOnTypeIndex = sample.RunOnTypeIndex }; inCell.Cell.Link.SetTo(cell.FormKey);
        bBranch.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = inCell });
        var n = 0;
        FormKey? prev = null;
        foreach (var pair in bd.GetProperty("pairs").EnumerateArray())
        {
            var who = pair.GetProperty("npcs").EnumerateArray().Select(x => x.GetString()!).ToArray();
            if (who.Length != 2) throw new Exception("banter.json: a pair is two people");
            var node = new StoryManagerQuestNode(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = $"AGHallBanter{who[0].Replace("AGHall", "").Replace("AGSpike", "")}{who[1].Replace("AGHall", "").Replace("AGSpike", "")}", Flags = StoryManagerQuestNode.Flag.Random };
            node.Parent.SetTo(bBranch.FormKey);
            if (prev is { } p) node.PreviousSibling.SetTo(p);
            foreach (var ed in who)
            {
                var placed = cell.Persistent.OfType<PlacedNpc>().First(r => r.EditorID == ed + "Ref").FormKey;
                node.Conditions.Add(Present(placed, new GetDeadConditionData(), 0));
                var there = new GetInCellConditionData(); there.Cell.Link.SetTo(cell.FormKey);
                node.Conditions.Add(Present(placed, there, 1));
            }
            foreach (var ex in pair.GetProperty("exchanges").EnumerateArray())
            {
                n++;
                // an exchange is its lines, or {"lines": [...], "sitting": true}
                var sitting = ex.ValueKind == JsonValueKind.Object && ex.TryGetProperty("sitting", out var st) && st.GetBoolean();
                var exLines = ex.ValueKind == JsonValueKind.Object ? ex.GetProperty("lines") : ex;
                var q = new Quest(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = $"AGHallBanter{n}", Priority = 30, Event = new RecordType("ADIA"), NextAliasID = 4 };
                foreach (var (id, name, data) in new[] { (0u, "Actor1", 12626), (1u, "Actor2", 12882) })   // the event's R1 and R2
                {
                    var a = new QuestAlias { ID = id, Name = name, Type = QuestAlias.TypeEnum.Reference, Flags = 0, FindMatchingRefFromEvent = new FindMatchingRefFromEvent { FromEvent = new RecordType("ADIA"), EventData = (GetEventDataConditionData.EventMember)data } };
                    foreach (var ed in who)
                    {
                        var isId = new GetIsIDConditionData(); isId.Object.Link.SetTo(Hall(ed).FormKey);
                        a.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = isId, Flags = Condition.Flag.OR });
                    }
                    // "sitting": both seated (Marius and Willem's chair: they sit together);
                    // GetSitting 3 = sitting
                    if (sitting) a.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 3, Data = new GetSittingConditionData() });
                    q.Aliases.Add(a);
                }
                for (var k = 0; k < 2; k++)
                    q.Aliases.Add(new QuestAlias { ID = (uint)(2 + k), Name = who[k], Type = QuestAlias.TypeEnum.Reference, Flags = QuestAlias.Flag.AllowReuseInQuest, UniqueActor = new FormLinkNullable<INpcGetter>(Hall(who[k]).FormKey) });
                var scene = new Scene(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = $"AGHallBanter{n}Scene", Flags = Scene.Flag.BeginOnQuestStart | Scene.Flag.StopQuestOnEnd | Scene.Flag.ShowAllText, Quest = q.ToNullableLink() };
                foreach (var id in new uint[] { 2, 3 })
                    scene.Actors.Add(new SceneActor { ID = id, Flags = 0, BehaviorFlags = SceneActor.BehaviorFlag.DeathEnd | SceneActor.BehaviorFlag.CombatEnd | SceneActor.BehaviorFlag.DialoguePause });
                var spoken = exLines.EnumerateArray().ToList();
                for (var i = 0; i < spoken.Count; i++)
                {
                    var (npc, text) = (spoken[i][0].GetString()!, spoken[i][1].GetString()!);
                    var actor = Array.IndexOf(who, npc);
                    if (actor < 0) throw new Exception($"banter.json: {npc} speaks in a pair of {who[0]} and {who[1]}");
                    var t = new DialogTopic(NewKey(), SkyrimRelease.SkyrimSE)
                    {
                        EditorID = $"AGHallBanter{n}Line{i + 1}", Priority = 50, Quest = q.ToNullableLink(),
                        Category = DialogTopic.CategoryEnum.Scene, Subtype = DialogTopic.SubtypeEnum.Scene, SubtypeName = new RecordType("SCEN"),
                    };
                    var info = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = $"AGHallInfo_{npc}_banter{n}_{i + 1}", Flags = new DialogResponseFlags() };
                    info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
                    t.Responses.Add(info);
                    bTopics.Add(t);
                    scene.Phases.Add(new ScenePhase { Name = "", Unused = new ScenePhaseUnusedData(), Unused2 = new ScenePhaseUnusedData(), EditorWidth = 200 });
                    scene.Actions.Add(new SceneAction { Type = SceneAction.TypeEnum.Dialog, Name = "", ActorID = 2 + actor, Index = (uint)(i + 1), StartPhase = (uint)i, EndPhase = (uint)i,
                        Topic = new FormLinkNullable<IDialogTopicGetter>(t.FormKey), HeadtrackActorID = -1, LoopingMax = 10, LoopingMin = 1, Emotion = Emotion.Neutral, EmotionValue = 0 });
                    banterLines.Add(($"{npc}:banter{n}_{i + 1}", npc, info.FormKey.ID, text, t.EditorID!, q.EditorID!));
                }
                scene.LastActionIndex = (uint)spoken.Count;
                bQuests.Add(q); bScenes.Add(scene);
                node.Quests.Add(new StoryManagerQuest { Quest = new FormLinkNullable<IQuestGetter>(q.FormKey), HoursUntilReset = 24 });
            }
            bNodes.Add(node);
            prev = node.FormKey;
        }
        return 0;
    });
    CheckTakes(banterLines.Select(l => (l.Key, l.Id)));
    string BanterFile(string q, string tp, uint id)
    {
        if (q.Length + tp.Length > 25) { q = q[..10]; tp = tp[..Math.Min(tp.Length, 25 - q.Length)]; }
        return $"{q}_{tp}_{id:X8}_1.fuz".ToLowerInvariant();
    }
    File.WriteAllText(Path.Combine(npcsDir, "build", "banter_lines.json"), JsonSerializer.Serialize(banterLines.Select(l => new { key = l.Key, npc = l.Npc,
        voice = VoiceOf(l.Npc), info = $"{l.Id:X8}", quest = l.Quest, topic = l.Topic, text = l.Text }), new JsonSerializerOptions { WriteIndented = true }));
    var bMissing = banterLines.Count(l => !File.Exists(Path.Combine(npcsDir, "build", "Sound", "Voice", hall.ModKey.FileName, VoiceOf(l.Npc), BanterFile(l.Quest, l.Topic, l.Id))));
    if (bMissing > 0 && Environment.GetEnvironmentVariable("AG_BANTER_BUILD") != "1")
        Console.WriteLine($"WARNING the banter held out of this build: {bMissing} of {banterLines.Count} voice files not in build/Sound yet");
    else
    {
        mod.StoryManagerBranchNodes.Add(bBranch!);
        foreach (var x in bNodes) mod.StoryManagerQuestNodes.Add(x);
        foreach (var x in bQuests) mod.Quests.Add(x);
        foreach (var x in bScenes) mod.Scenes.Add(x);
        foreach (var x in bTopics) mod.DialogTopics.Add(x);
    }
    Console.WriteLine($"the banter: {bQuests.Count} exchanges between {bNodes.Count} pairs, {banterLines.Count} lines");
}
if (next > 0x1800) throw new Exception($"Marius's talk ran to 0x{next:X}, past the NPC block's end (merged 0x8FFF)");

// Marius's training (marius_training.json: One-handed and Block to 75, Two-handed, Light and Heavy
// Armor to 50, gold at vanilla's price, members only). Vanilla's trainer teaches the one skill his class names (CLAS
// Teaches and MaxTrainingLevel), so Marius gets a class of his own, a copy of his combat class, and each skill's reply sets
// the skill and cap on it through AG's DLL before opening vanilla's training menu (AGHallTrainerTIF). In the second block,
// 0x1810-0x183F (merged 0x9010-), so nothing else moves; the dialogue waits for its one voiced reply, as the other talks do.
InIds(0x1810, 0x1840, "Marius's training", () =>
{
    var tr = JsonDocument.Parse(File.ReadAllText(Path.Combine(npcsDir, "marius_training.json"))).RootElement;
    var marius = Hall("AGHallResidentVeteran");
    var cls = (Class)Ed<IClassGetter>("CombatWarrior1H").Duplicate(NewKey());
    cls.EditorID = "AGHallVeteranClass";
    var first = tr.GetProperty("skills")[0];
    cls.Teaches = (Skill)first.GetProperty("skill").GetInt32();
    cls.MaxTrainingLevel = (byte)first.GetProperty("max").GetInt32();
    mod.Classes.Add(cls);
    marius.Class.SetTo(cls.FormKey);

    var b = new DialogBranch(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = "AGHallTrainBranch", Quest = clerkQuest.ToLink<IQuestGetter>(), Category = DialogBranch.CategoryType.Player,
        Flags = DialogBranch.Flag.TopLevel,
    };
    DialogTopic NewT(string stem, string text) => new(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = $"AGHallTrainTopic{stem}", Name = text, Priority = 50, Branch = b.ToNullableLink(), Quest = clerkQuest.ToNullableLink(),
        Category = DialogTopic.CategoryEnum.Topic, Subtype = DialogTopic.SubtypeEnum.Custom, SubtypeName = new RecordType("CUST"),
    };
    var ask = NewT("Ask", tr.GetProperty("ask").GetString()!);
    b.StartingTopic.SetTo(ask.FormKey);
    var member = At(marius).Append(GlobalIs(gRegistered, CompareOperator.EqualTo, 1)).ToArray();
    var reply = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallInfo_AGHallResidentVeteran_train1", Flags = new DialogResponseFlags() };
    var replyText = tr.GetProperty("reply").GetString()!;
    reply.Responses.Add(new DialogResponse { Text = replyText, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
    foreach (var c in member) reply.Conditions.Add(c.DeepCopy());
    ask.Responses.Add(reply);
    var skills = new List<DialogTopic>();
    var pickText = tr.GetProperty("pick").GetString()!;
    var pickCopyOf = tr.GetProperty("pickCopyOf").GetString()!;
    var pickLines = new List<(string Key, string Npc, uint Id, string Text, string Topic, string? CopyOf)>();
    var k = 0;
    foreach (var s in tr.GetProperty("skills").EnumerateArray())
    {
        var t = NewT($"Skill{++k}", s.GetProperty("choice").GetString()!);
        // the menu opens when his line ends (vanilla's trainers open it from their reply's script the same way)
        var info = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE)
        {
            EditorID = $"AGHallInfo_AGHallResidentVeteran_trainSkill{k}", Flags = new DialogResponseFlags { Flags = DialogResponses.Flag.Goodbye },
            VirtualMachineAdapter = new DialogResponsesAdapter
            {
                Scripts = { new ScriptEntry { Name = "AGHallTrainerTIF", Properties = {
                    new ScriptIntProperty { Name = "Skill", Data = s.GetProperty("skill").GetInt32(), Flags = ScriptProperty.Flag.Edited },
                    new ScriptIntProperty { Name = "MaxLevel", Data = s.GetProperty("max").GetInt32(), Flags = ScriptProperty.Flag.Edited } } } },
                ScriptFragments = new ScriptFragments
                {
                    FileName = "AGHallTrainerTIF",
                    OnEnd = new ScriptFragment { ScriptName = "AGHallTrainerTIF", FragmentName = "Fragment_0" },
                },
            },
        };
        // one spoken line: an info with no response never shows as a choice; the reply is
        // his recorded vanilla "Of course." (vanilla_lines.json), copied under each info's own name
        info.Responses.Add(new DialogResponse { Text = pickText, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
        foreach (var c in member) info.Conditions.Add(c.DeepCopy());
        t.Responses.Add(info);
        reply.LinkTo.Add(t);
        skills.Add(t);
        pickLines.Add(($"AGHallResidentVeteran:train:skill{k}", "AGHallResidentVeteran", info.FormKey.ID, pickText, t.EditorID!, pickCopyOf));
    }
    var trLines = new List<(string Key, string Npc, uint Id, string Text, string Topic, string? CopyOf)> { ("AGHallResidentVeteran:train:train1", "AGHallResidentVeteran", reply.FormKey.ID, replyText, ask.EditorID!, null) };
    trLines.AddRange(pickLines);
    CheckTakes(trLines.Select(l => (l.Key, l.Id)));
    string TrFile(string topic, uint fid)
    {
        var (q, tp) = (clerkQuest.EditorID!, topic);
        if (q.Length + tp.Length > 25) { q = q[..10]; tp = tp[..Math.Min(tp.Length, 25 - q.Length)]; }
        return $"{q}_{tp}_{fid:X8}_1.fuz".ToLowerInvariant();
    }
    var trMissing = trLines.Count(l => !File.Exists(Path.Combine(npcsDir, "build", "Sound", "Voice", "AdventurersGuild - Guild Hall.esp", VoiceOf(l.Npc),
        TrFile(l.Topic, l.Id >= 0x8000 ? l.Id : idBase + l.Id))));
    if (merge) File.WriteAllText(Path.Combine(npcsDir, "build", "train_lines.json"), JsonSerializer.Serialize(trLines.Select(l => new { key = l.Key, npc = l.Npc,
        voice = VoiceOf(l.Npc), info = $"{(l.Id >= 0x8000 ? l.Id : idBase + l.Id):X8}", quest = clerkQuest.EditorID, topic = l.Topic, text = l.Text, copyOf = l.CopyOf }), new JsonSerializerOptions { WriteIndented = true }));
    if (trMissing > 0 && Environment.GetEnvironmentVariable("AG_TRAIN_BUILD") != "1")
        Console.WriteLine($"WARNING Marius's training talk held out of this build: {trMissing} of {trLines.Count} voice files not in build/Sound yet (his class is in)");
    else
    {
        mod.DialogBranches.Add(b);
        mod.DialogTopics.Add(ask);
        foreach (var t in skills) mod.DialogTopics.Add(t);
        Console.WriteLine($"Marius's training: {skills.Count} skills, members only");
    }
    return 0;
});

// Cassius's and Brynja's shop: vanilla's "What have you got
// for sale?" lives in DialogueGeneric, whose quest conditions ask for a voice on DefaultNPCVoiceTypes, so it closed for
// them when their own voices went live (2026-11-10; GetIsVoiceType DefaultNPCVoiceTypes 0 on Cassius, read in game).
// Vanilla's prompt as a top-level choice of the hall's own, while the engine says they are trading (GetOffersServicesNow,
// as vanilla's line asks); the reply is vanilla's "Depends. Are you thirsty, hungry, both?", the take each already
// recorded for vanilla's line (copyOf, no credits), and AGHallBarterTIF opens their shop when it ends. In its own block,
// 0x1F40-0x1F4F (merged 0x9740-), so nothing else moves; held out until both copied takes are in, as the other talks are.
InIds(0x1F40u, 0x1F50u, "the tavern's shop", () =>
{
    var b = new DialogBranch(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = "AGHallSaleBranch", Quest = clerkQuest.ToLink<IQuestGetter>(), Category = DialogBranch.CategoryType.Player,
        Flags = DialogBranch.Flag.TopLevel,
    };
    var t = new DialogTopic(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = "AGHallSaleTopic", Name = "What have you got for sale?", Priority = 50, Branch = b.ToNullableLink(),
        Quest = clerkQuest.ToNullableLink(), Category = DialogTopic.CategoryEnum.Topic, Subtype = DialogTopic.SubtypeEnum.Custom,
        SubtypeName = new RecordType("CUST"),
    };
    b.StartingTopic.SetTo(t.FormKey);
    const string replyText = "Depends. Are you thirsty, hungry, both?";
    var saleLines = new List<(string Key, string Npc, uint Id, string Text, string CopyOf)>();
    foreach (var ed in new[] { "AGHallBarkeeper", "AGHallServer" })
    {
        var info = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE)
        {
            EditorID = $"AGHallInfo_{ed}_sale", Flags = new DialogResponseFlags { Flags = DialogResponses.Flag.Goodbye },
            VirtualMachineAdapter = new DialogResponsesAdapter
            {
                // the script attached as well as named by the fragment, as vanilla's 0xDEE85 and Marius's training lines:
                // a fragment with no attached script has nothing to run on, so the line played and no shop opened (2026-11-12)
                Scripts = { new ScriptEntry { Name = "AGHallBarterTIF" } },
                ScriptFragments = new ScriptFragments
                {
                    FileName = "AGHallBarterTIF",
                    OnEnd = new ScriptFragment { ScriptName = "AGHallBarterTIF", FragmentName = "Fragment_0" },
                },
            },
        };
        info.Responses.Add(new DialogResponse { Text = replyText, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
        foreach (var c in At(Hall(ed))) info.Conditions.Add(c.DeepCopy());
        info.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = new GetOffersServicesNowConditionData() });
        t.Responses.Add(info);
        saleLines.Add(($"{ed}:sale", ed, info.FormKey.ID, replyText, $"{ed}:vanilla:0DEE85"));
    }
    CheckTakes(saleLines.Select(l => (l.Key, l.Id)));
    string SaleFile(uint fid)
    {
        var (q, tp) = (clerkQuest.EditorID!, t.EditorID!);
        if (q.Length + tp.Length > 25) { q = q[..10]; tp = tp[..Math.Min(tp.Length, 25 - q.Length)]; }
        return $"{q}_{tp}_{fid:X8}_1.fuz".ToLowerInvariant();
    }
    uint Real(uint id) => id >= 0x8000 ? id : idBase + id;
    var saleMissing = saleLines.Count(l => !File.Exists(Path.Combine(npcsDir, "build", "Sound", "Voice", "AdventurersGuild - Guild Hall.esp", VoiceOf(l.Npc),
        SaleFile(Real(l.Id)))));
    if (merge) File.WriteAllText(Path.Combine(npcsDir, "build", "sale_lines.json"), JsonSerializer.Serialize(saleLines.Select(l => new { key = l.Key, npc = l.Npc,
        voice = VoiceOf(l.Npc), info = $"{Real(l.Id):X8}", quest = clerkQuest.EditorID, topic = t.EditorID, text = l.Text, copyOf = l.CopyOf }), new JsonSerializerOptions { WriteIndented = true }));
    if (saleMissing > 0 && Environment.GetEnvironmentVariable("AG_SALE_BUILD") != "1")
        Console.WriteLine($"WARNING the tavern's sale line held out of this build: {saleMissing} of {saleLines.Count} voice files not in build/Sound yet");
    else
    {
        mod.DialogBranches.Add(b);
        mod.DialogTopics.Add(t);
        Console.WriteLine("the tavern's shop: \"What have you got for sale?\" for Cassius and Brynja");
    }
    return 0;
});

// Merila's welcome (merila_welcome.json): once, the first time a member is in the
// hall with her, she walks up and welcomes them, then offers "What's upstairs?", "What's in the basement?" and "That's
// all.". Modelled on the Companions' welcome: a quest of its own (priority over the hall's dialogue quest) whose alias on
// Merila carries a ForceGreet copied from vanilla's C00AelaForceGreet (the player as target, 5000 reach), its topic the
// welcome, in a Blocking branch so clicking her first gives the welcome too. AGHallWelcomeTIF sets AGHallWelcomeDoneGlobal
// as the welcome begins, which ends the package and the welcome for good. Its own block, 0x1F50-0x1F70 (merged 0x9750-);
// held out until its recordings are in (AG_WELCOME_BUILD=1 builds it without them).
var mwPath = Path.Combine(npcsDir, "merila_welcome.json");
if (File.Exists(mwPath)) InIds(0x1F50u, 0x1F70u, "Merila's welcome", () =>
{
    var mw = JsonDocument.Parse(File.ReadAllText(mwPath)).RootElement;
    const string M = "AGHallAssistant";
    var merila = Hall(M);
    var merilaRef = cell.Persistent.OfType<PlacedNpc>().First(r => r.EditorID == M + "Ref").FormKey;
    var playerRef = new FormKey(ModKey.FromFileName("Skyrim.esm"), 0x14);
    var gDone = new GlobalShort(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallWelcomeDoneGlobal", Data = 0 };
    var q = new Quest(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallWelcomeQuest", Flags = Quest.Flag.StartGameEnabled, Priority = 60 };
    var b = new DialogBranch(NewKey(), SkyrimRelease.SkyrimSE)
        { EditorID = "AGHallWelcomeBranch", Quest = q.ToLink<IQuestGetter>(), Category = DialogBranch.CategoryType.Player, Flags = DialogBranch.Flag.Blocking };
    DialogTopic T(string ed, string? prompt, DialogBranch? br) => new(NewKey(), SkyrimRelease.SkyrimSE)
    {
        EditorID = ed, Name = prompt, Priority = 50, Branch = br!.ToNullableLink(), Quest = q.ToNullableLink(),
        Category = DialogTopic.CategoryEnum.Topic, Subtype = DialogTopic.SubtypeEnum.Custom, SubtypeName = new RecordType("CUST"),
    };
    var tWelcome = T("AGHallWelcomeTopic", null, b);
    b.StartingTopic.SetTo(tWelcome.FormKey);
    var ch = mw.GetProperty("choices");
    var tUp = T("AGHallWelcomeUp", ch.GetProperty("up").GetString(), b);
    var tDown = T("AGHallWelcomeDown", ch.GetProperty("down").GetString(), b);
    var tBye = T("AGHallWelcomeBye", ch.GetProperty("bye").GetString(), b);
    var mwLines = new List<(string Key, string Npc, uint Id, int Part, string Text, string Topic)>();
    DialogResponses Say(DialogTopic t, string slot, bool goodbye)
    {
        var info = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE)
            { EditorID = $"AGHallInfo_{M}_welcome_{slot}", Flags = new DialogResponseFlags { Flags = goodbye ? DialogResponses.Flag.Goodbye : 0 } };
        var part = 0;
        foreach (var text in mw.GetProperty(slot).EnumerateArray().Select(x => x.GetString()!))
        {
            if (text.Length > 150) throw new Exception($"Merila's welcome: {slot} part {part + 1} is {text.Length} characters, over vanilla's 150");
            info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = (byte)++part });
            mwLines.Add(($"{M}:welcome:{slot}#{part}", M, info.FormKey.ID, part, text, t.EditorID!));
        }
        foreach (var c in At(merila)) info.Conditions.Add(c.DeepCopy());
        info.Conditions.Add(GlobalIs(gRegistered, CompareOperator.EqualTo, 1));
        t.Responses.Add(info);
        return info;
    }
    var welcome = Say(tWelcome, "welcome", false);
    welcome.Conditions.Add(GlobalIs(gDone.FormKey, CompareOperator.EqualTo, 0));
    welcome.VirtualMachineAdapter = new DialogResponsesAdapter
    {
        Scripts = { new ScriptEntry { Name = "AGHallWelcomeTIF", Properties = { new ScriptObjectProperty { Name = "Done", Object = gDone.ToLink<ISkyrimMajorRecordGetter>(), Flags = ScriptProperty.Flag.Edited } } } },
        ScriptFragments = new ScriptFragments { FileName = "AGHallWelcomeTIF", OnBegin = new ScriptFragment { ScriptName = "AGHallWelcomeTIF", FragmentName = "Fragment_0" } },
    };
    var up = Say(tUp, "up", false);
    var down = Say(tDown, "down", false);
    Say(tBye, "bye", true);
    // after the welcome all three; after an answer the other and "That's all."
    foreach (var x in new[] { tUp, tDown, tBye }) welcome.LinkTo.Add(new FormLink<IDialogTopicGetter>(x.FormKey));
    foreach (var x in new[] { tDown, tBye }) up.LinkTo.Add(new FormLink<IDialogTopicGetter>(x.FormKey));
    foreach (var x in new[] { tUp, tBye }) down.LinkTo.Add(new FormLink<IDialogTopicGetter>(x.FormKey));

    // the ForceGreet: vanilla's, its topic the welcome; only while she and a member player share a hall cell, she is up and
    // about (her day runs 6 to 22) and the welcome has not begun
    var fg = (Package)Ed<IPackageGetter>("C00AelaForceGreet").Duplicate(NewKey());
    fg.EditorID = "AGHallWelcomeForceGreet";
    fg.VirtualMachineAdapter = null;
    fg.OwnerQuest.SetTo(q.FormKey);
    fg.Conditions.Clear();
    var topicData = new PackageDataTopic();
    topicData.Topics.Add(new TopicReference { Reference = tWelcome.ToLink<IDialogTopicGetter>() });
    fg.Data[7] = topicData;
    // her greeting distance (she started the conversation from too far away): the template's
    // "Forcegreet Distance (Don't change ref, just radius)" input, near the player; vanilla leaves it at the template's 300 (about
    // 4.3 m, read from ForceGreet 0003C1C4), here 150 (about 2 m) so she walks up first
    fg.Data[75] = new PackageDataLocation { Location = new LocationTargetRadius { Target = new LocationTarget { Link = new FormLink<IPlacedGetter>(playerRef) }, Radius = 150 } };
    // her trigger: the template's "Trigger Location (Player here causes forcegreet)" input, near herself; the template's 500
    // (about 7 m) leaves her at the map until the player walks over. 8000 spans the hall's main cell, so she sets off as soon
    // as the package's conditions hold (same cell, member, her hours)
    if (fg.Data.TryGetValue(62, out var trig) && trig is PackageDataLocation tl && tl.Location is LocationTargetRadius tr) tr.Radius = 8000;
    else throw new Exception("Merila's welcome: the ForceGreet has no trigger location input 62");
    fg.Conditions.Add(GlobalIs(gDone.FormKey, CompareOperator.EqualTo, 0));
    fg.Conditions.Add(GlobalIs(gRegistered, CompareOperator.EqualTo, 1));
    fg.Conditions.Add(Hour(CompareOperator.GreaterThanOrEqualTo, 6));
    fg.Conditions.Add(Hour(CompareOperator.LessThan, 22));
    { var d = new GetInSameCellConditionData(); d.Target.Link.SetTo(playerRef); fg.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = d }); }
    { var d = new GetSleepingConditionData(); fg.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 0, Data = d }); }
    { var d = new IsInCombatConditionData { RunOnType = Condition.RunOnType.Reference }; d.Reference.SetTo(playerRef); fg.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 0, Data = d }); }
    foreach (var c in InHallCells()) fg.Conditions.Add(c);
    var alias = new QuestAlias
    {
        ID = 0, Name = "Merila", Type = QuestAlias.TypeEnum.Reference, Flags = QuestAlias.Flag.AllowReserved,
        ForcedReference = new FormLinkNullable<IPlacedGetter>(merilaRef),
    };
    alias.PackageData.Add(fg.ToLink<IPackageGetter>());
    q.Aliases.Add(alias);
    q.NextAliasID = 1;
    // her wait (she was half the hall away when the player signed up; she should meet the player as soon as they sign up,
    // or on their first visit if already registered):
    // until the welcome is done, 06:00-22:00, she roams the services nook by the map of Skyrim (the hall's
    // AGHallAssistantMapMarker, a StudyMarker she uses as she wanders), meals included. An alias package after the ForceGreet, so
    // the welcome wins the moment it can run, and none of her own packages' IDs move; made last in this block so nothing moves here
    var mapMarker = hallNamed.TryGetValue("AGHallAssistantMapMarker", out var mm) ? mm : throw new Exception("Merila's wait: AGHallAssistantMapMarker is not in the hall's plugin");
    var wait = (Package)pkgSrc["leisure"].Duplicate(NewKey());
    wait.EditorID = "AGHallWelcomeWait";
    wait.VirtualMachineAdapter = null;
    wait.OwnerQuest.SetTo(q.FormKey);
    wait.Conditions.Clear();
    wait.ScheduleHour = 6; wait.ScheduleMinute = 0; wait.ScheduleDurationInMinutes = 16 * 60;
    wait.ScheduleDayOfWeek = Package.DayOfWeek.Any;
    ((PackageDataLocation)wait.Data[0]).Location = new LocationTargetRadius { Target = new LocationTarget { Link = new FormLink<IPlacedGetter>(mapMarker) }, Radius = 200 };
    // the Sandbox's inputs (measured, see NPCGEN_PROBE_PACKAGES): on 5 idle markers, 7 wandering; off 1 eating, 3 sleeping, 6 sitting,
    // 31 special furniture (the nook's hearth)
    foreach (var (k, on) in new (sbyte, bool)[] { (5, true), (7, true), (1, false), (3, false), (6, false), (31, false) })
        if (wait.Data.TryGetValue(k, out var dv) && dv is PackageDataBool db) db.Data = on;
        else throw new Exception($"Merila's wait: the Sandbox has no input {k}");
    wait.Conditions.Add(GlobalIs(gDone.FormKey, CompareOperator.EqualTo, 0));
    alias.PackageData.Add(wait.ToLink<IPackageGetter>());

    CheckTakes(mwLines.Select(l => (l.Key, l.Id)));
    uint Real(uint id) => id >= 0x8000 ? id : idBase + id;
    string FileOf(uint fid, int part, string topic)
    {
        var (qq, tp) = (q.EditorID!, topic);
        if (qq.Length + tp.Length > 25) { qq = qq[..10]; tp = tp[..Math.Min(tp.Length, 25 - qq.Length)]; }
        return $"{qq}_{tp}_{fid:X8}_{part}.fuz".ToLowerInvariant();
    }
    var missing = mwLines.Count(l => !File.Exists(Path.Combine(npcsDir, "build", "Sound", "Voice", "AdventurersGuild - Guild Hall.esp", VoiceOf(l.Npc),
        FileOf(Real(l.Id), l.Part, l.Topic))));
    if (merge) File.WriteAllText(Path.Combine(npcsDir, "build", "welcome_lines.json"), JsonSerializer.Serialize(mwLines.Select(l => new { key = l.Key, npc = l.Npc,
        voice = VoiceOf(l.Npc), info = $"{Real(l.Id):X8}", response = l.Part, quest = q.EditorID, topic = l.Topic, text = l.Text }), new JsonSerializerOptions { WriteIndented = true }));
    if (missing > 0 && Environment.GetEnvironmentVariable("AG_WELCOME_BUILD") != "1")
        Console.WriteLine($"WARNING Merila's welcome held out of this build: {missing} of {mwLines.Count} voice files not in build/Sound yet");
    else
    {
        mod.Globals.Add(gDone); mod.Quests.Add(q); mod.DialogBranches.Add(b);
        foreach (var x in new[] { tWelcome, tUp, tDown, tBye }) mod.DialogTopics.Add(x);
        mod.Packages.Add(fg); mod.Packages.Add(wait);
        Console.WriteLine($"Merila's welcome: {mwLines.Count} lines, once, on the first visit as a member");
    }
    return 0;
});

// The promotion trials (trial_quests.json; plans/promotion-trial.md in the hall's notes).
// Their own ID block, 0x2000-0x21FF here (merged 0x9800-0x99FF, the hall session's grant 2026-11-05). The first
// records sit at fixed IDs the DLL reads (GuildHall.cpp): 0x2000 the trials' global (AG's MCM toggle, kept by the DLL),
// 0x2001 their dialogue quest, 0x2002-0x2006 the five quests (D ... S), 0x2007-0x200B the five creatures, 0x200C-0x2010
// the five trophies. Willem's two topics ("I'm ready for my trial." / "It's done. Here's the trophy.") are their dialogue
// quest's; the clerks' trial lines go AHEAD of their own in AGHallClerkTopicPromote, and Willem's trial W0 ahead of his
// guild-talk W0, each of theirs given a trials-off condition (the NPC session's records, not its code). Held out until every
// voice file is in (AG_TRIAL_BUILD=1 forces it in, =0 leaves it out); build/trial_lines.json is written either way, so the
// lines can be recorded under their real names. A part said twice is one take ("copyOf"): every brief is said after
// Willem's intro (the first trial) and on its own; the clerk's done line is followed by her recorded promote line.
var trPath = Path.Combine(npcsDir, "trial_quests.json");
if (File.Exists(trPath) && Environment.GetEnvironmentVariable("AG_TRIAL_BUILD") != "0")
{
    var tq = JsonDocument.Parse(File.ReadAllText(trPath)).RootElement;
    var trLines = new List<(string Key, string Npc, uint Id, int Part, string Text, string Topic, string Quest, string? CopyOf)>();
    var trAdd = new List<Action>();   // what joins the plugin, once the build includes the trials
    var skyrim = ModKey.FromFileName("Skyrim.esm");
    var trWillem = Hall("AGHallGuildMaster");
    FormKey RefOf(string ed) => cell.Persistent.OfType<PlacedNpc>().First(r => r.EditorID == ed + "Ref").FormKey;
    var trials = tq.GetProperty("trials").EnumerateArray().ToList();
    InIds(0x2000u, 0x2200u, "the promotion trials", () =>
    {
        // the fixed IDs first, in the DLL's order
        var gTrials = new GlobalShort(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallTrialsGlobal", Data = 1 };
        var dlgQuest = new Quest(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallTrials", Flags = Quest.Flag.StartGameEnabled, Priority = 60 };
        var quests = trials.Select(t => new Quest(NewKey(), SkyrimRelease.SkyrimSE)
        {
            EditorID = t.GetProperty("quest").GetString(), Name = t.GetProperty("name").GetString(), Priority = 70, Type = Quest.TypeEnum.SideQuest,
        }).ToList();
        var creatures = trials.Select(t =>
        {
            var c = t.GetProperty("creature");
            var src = Ed<INpcGetter>(c.GetProperty("base").GetString()!);
            var n = (Npc)src.Duplicate(NewKey());
            n.EditorID = $"AGHallTrialCreature{t.GetProperty("rank").GetString()}";
            n.Configuration.Flags |= NpcConfiguration.Flag.Unique;
            // a template's stats would win over ours: the copy keeps its own (Dawnguard's copies carry the same numbers)
            if (!n.Template.IsNull) n.Configuration.TemplateFlags &= ~NpcConfiguration.TemplateFlag.Stats;
            n.Configuration.HealthOffset = (short)(n.Configuration.HealthOffset + c.GetProperty("healthAdd").GetInt32());
            if (c.TryGetProperty("spellsAdd", out var sp))
            {
                n.ActorEffect ??= new ExtendedList<IFormLinkGetter<ISpellRecordGetter>>();
                foreach (var x in sp.EnumerateArray()) n.ActorEffect.Add(Ed<ISpellGetter>(x.GetString()!).ToLink<ISpellRecordGetter>());
            }
            if (c.TryGetProperty("aggressive", out var ag) && ag.GetBoolean()) n.AIData.Aggression = Aggression.Aggressive;
            Console.WriteLine($"trials: {n.EditorID} from {src.EditorID}: health offset {n.Configuration.HealthOffset}, template {(n.Template.IsNull ? "none" : n.Template.FormKey.ToString())} ({n.Configuration.TemplateFlags})");
            return n;
        }).ToList();
        var trophies = trials.Select(t =>
        {
            var src = Ed<IMiscItemGetter>(t.GetProperty("trophy").GetProperty("model").GetString()!);
            return new MiscItem(NewKey(), SkyrimRelease.SkyrimSE)
            {
                EditorID = $"AGHallTrialTrophy{t.GetProperty("rank").GetString()}", Name = t.GetProperty("trophy").GetProperty("name").GetString(),
                Value = 0, Weight = src.Weight, Model = src.Model?.DeepCopy(), ObjectBounds = src.ObjectBounds.DeepCopy(),
                PickUpSound = src.PickUpSound.AsNullable(), PutDownSound = src.PutDownSound.AsNullable(),
                // (the inventory picks a misc item's icon by its keywords, and
                // with none a trophy showed the fallback box) the creature-part icon, as hagraven claws and vanilla's heads carry
                Keywords = new() { Ed<IKeywordGetter>("VendorItemAnimalPart").ToLinkGetter() },
            };
        }).ToList();
        var gIntro = new GlobalShort(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = "AGHallTrialIntroGlobal", Data = 0 };
        // where the creature is made, disabled, before it moves out: Caralion's anchor under the hall's floor, else our own
        var anchorRef = cell.Persistent.OfType<PlacedObject>().FirstOrDefault(r => r.EditorID == "AGHallQuestAnchorMarker");
        PlacedObject? ownAnchor = null;
        if (anchorRef == null)
        {
            ownAnchor = new PlacedObject(NewKey(), SkyrimRelease.SkyrimSE)
            {
                EditorID = "AGHallTrialAnchorMarker", Base = new FormLinkNullable<IPlaceableObjectGetter>(new FormKey(skyrim, 0x3B)),
                Placement = new Placement { Position = new P3Float(0, 0, -2000), Rotation = new P3Float(0, 0, 0) },
            };
            anchorRef = ownAnchor;
        }

        ConditionFloat StageOf(Quest q, CompareOperator op, float v, bool or = false)
        { var d = new GetStageConditionData(); d.Quest.Link.SetTo(q.FormKey); return new() { CompareOperator = op, ComparisonValue = v, Data = d, Flags = or ? Condition.Flag.OR : 0 }; }
        ConditionFloat Running(Quest q, bool yes)
        { var d = new GetQuestRunningConditionData(); d.Quest.Link.SetTo(q.FormKey); return new() { CompareOperator = CompareOperator.EqualTo, ComparisonValue = yes ? 1 : 0, Data = d }; }
        ConditionFloat Completed(FormKey q, bool yes)
        { var d = new GetQuestCompletedConditionData(); d.Quest.Link.SetTo(q); return new() { CompareOperator = CompareOperator.EqualTo, ComparisonValue = yes ? 1 : 0, Data = d }; }
        ConditionFloat Holds(MiscItem item)
        {
            var d = new GetItemCountConditionData { RunOnType = Condition.RunOnType.Reference }; d.Reference.SetTo(new FormKey(skyrim, 0x14)); d.ItemOrList.Link.SetTo(item.FormKey);
            return new() { CompareOperator = CompareOperator.GreaterThanOrEqualTo, ComparisonValue = 1, Data = d };
        }
        ConditionFloat IsWillem() { var d = new GetIsIDConditionData(); d.Object.Link.SetTo(trWillem.FormKey); return new() { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = d }; }
        ConditionFloat TrialsOn(bool on) => GlobalIs(gTrials.FormKey, CompareOperator.EqualTo, on ? 1 : 0);

        // each trial: aliases 0 Willem, 1-2 the clerks (the hall's refs), 3 the creature, 4 its trophy, 5 its spot, 6 the player
        QuestAlias Alias(uint id, string name, QuestAlias.Flag flags) => new() { ID = id, Name = name, Type = QuestAlias.TypeEnum.Reference, Flags = flags };
        for (var i = 0; i < trials.Count; i++)
        {
            var t = trials[i]; var q = quests[i];
            var aW = Alias(0, "Willem", QuestAlias.Flag.AllowReserved); aW.ForcedReference = new FormLinkNullable<IPlacedGetter>(RefOf("AGHallGuildMaster"));
            q.Aliases.Add(aW);
            for (var k = 0; k < clerkIds.Length; k++)
            {
                var a = Alias((uint)(1 + k), clerkIds[k], QuestAlias.Flag.AllowReserved | QuestAlias.Flag.Optional);
                a.ForcedReference = new FormLinkNullable<IPlacedGetter>(RefOf(clerkIds[k]));
                q.Aliases.Add(a);
            }
            q.Aliases.Add(Alias(3, "Creature", QuestAlias.Flag.Optional | QuestAlias.Flag.AllowReserved));
            q.Aliases.Add(Alias(4, "Trophy", QuestAlias.Flag.Optional | QuestAlias.Flag.QuestObject));
            q.Aliases.Add(Alias(5, "Spot", QuestAlias.Flag.Optional));
            var aP = Alias(6, "Player", QuestAlias.Flag.AllowReserved); aP.ForcedReference = new FormLinkNullable<IPlacedGetter>(new FormKey(skyrim, 0x14));
            q.Aliases.Add(aP);
            q.NextAliasID = 7;
            var journal = t.GetProperty("journal");
            foreach (var st in new ushort[] { 10, 15, 20, 30, 40, 50, 100 })
            {
                if (!journal.TryGetProperty(st.ToString(), out var text)) continue;
                var entry = new QuestLogEntry { Flags = st == 100 ? QuestLogEntry.Flag.CompleteQuest : 0, Entry = text.GetString() };
                q.Stages.Add(new QuestStage { Index = st, LogEntries = { entry } });
            }
            foreach (var o in t.GetProperty("objectives").EnumerateObject())
            {
                var ix = ushort.Parse(o.Name);
                var obj = new QuestObjective { Index = ix, DisplayText = o.Value.GetString() };
                foreach (var alias in ix switch { 20 or 30 => new[] { 3 }, 50 => new[] { 1, 2 }, _ => new[] { 0 } })
                    obj.Targets.Add(new QuestObjectiveTarget { AliasID = alias });
                q.Objectives.Add(obj);
            }
            ScriptObjectProperty Obj(string name, FormKey k) => new() { Name = name, Object = new FormLink<ISkyrimMajorRecordGetter>(k), Flags = ScriptProperty.Flag.Edited };
            ScriptObjectProperty AliasProp(string name, int alias) => new() { Name = name, Object = q.ToLink<ISkyrimMajorRecordGetter>(), Alias = (short)alias, Flags = ScriptProperty.Flag.Edited };
            var c = t.GetProperty("creature");
            var qs = new ScriptEntry { Name = "AGHallTrialQuestScript", Properties = {
                new ScriptIntProperty { Name = "RankIndex", Data = t.GetProperty("rankIndex").GetInt32(), Flags = ScriptProperty.Flag.Edited },
                Obj("CreatureBase", creatures[i].FormKey), Obj("TrophyItem", trophies[i].FormKey), Obj("Anchor", anchorRef.FormKey),
                Obj("XMarker", Ed<IStaticGetter>("XMarker").FormKey), Obj("IntroGlobal", gIntro.FormKey),
                AliasProp("CreatureAlias", 3), AliasProp("TrophyAlias", 4), AliasProp("SpotAlias", 5),
                new ScriptFloatListProperty { Name = "Spot", Data = new ExtendedList<float>(t.GetProperty("spot").EnumerateArray().Select(x => x.GetSingle())), Flags = ScriptProperty.Flag.Edited },
            } };
            if (c.TryGetProperty("armorAdd", out var arm)) qs.Properties.Add(new ScriptFloatProperty { Name = "ArmorAdd", Data = arm.GetSingle(), Flags = ScriptProperty.Flag.Edited });
            if (c.TryGetProperty("headless", out var hl)) qs.Properties.Add(Obj("HeadlessBase", Ed<INpcGetter>(hl.GetString()!).FormKey));
            QuestFragmentAlias AliasScript(int alias, string script) => new()
            {
                Property = new ScriptObjectProperty { Object = q.ToLink<ISkyrimMajorRecordGetter>(), Alias = (short)alias },
                Scripts = { new ScriptEntry { Name = script } },
            };
            q.VirtualMachineAdapter = new QuestAdapter
            {
                Scripts = { qs },
                Aliases = { AliasScript(3, "AGHallTrialAliasCreature"), AliasScript(4, "AGHallTrialAliasTrophy"), AliasScript(6, "AGHallTrialAliasPlayer") },
            };
        }

        // the lines
        DialogResponsesAdapter Tif(string fragment, ScriptProperty prop) => new()
        {
            Scripts = { new ScriptEntry { Name = "AGHallTrialTIF", Properties = { prop } } },
            ScriptFragments = new ScriptFragments { FileName = "AGHallTrialTIF", OnEnd = new ScriptFragment { ScriptName = "AGHallTrialTIF", FragmentName = fragment } },
        };
        ScriptObjectProperty TrialProp(Quest q) => new() { Name = "Trial", Object = q.ToLink<ISkyrimMajorRecordGetter>(), Flags = ScriptProperty.Flag.Edited };
        ScriptObjectListProperty TrialsProp()
        {
            var p = new ScriptObjectListProperty { Name = "Trials", Flags = ScriptProperty.Flag.Edited };
            foreach (var q in quests) p.Objects.Add(new ScriptObjectProperty { Object = q.ToLink<ISkyrimMajorRecordGetter>() });
            return p;
        }
        DialogResponses Info(string ed, string npc, string keyStem, IEnumerable<(string Text, string? CopyOf)> parts, string topic, string quest)
        {
            var info = new DialogResponses(NewKey(), SkyrimRelease.SkyrimSE) { EditorID = ed, Flags = new DialogResponseFlags() };
            var part = 0;
            foreach (var (text, copyOf) in parts)
            {
                if (text.Length > 150) throw new Exception($"trials: {ed} part {part + 1} is {text.Length} characters, over vanilla's 150");
                info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = (byte)++part });
                trLines.Add(($"{keyStem}#{part}", npc, info.FormKey.ID, part, text, topic, quest, copyOf));
            }
            return info;
        }
        List<string> Parts(JsonElement e) => e.EnumerateArray().Select(x => x.GetString()!).ToList();
        DialogBranch Branch(string ed) => new(NewKey(), SkyrimRelease.SkyrimSE)
            { EditorID = ed, Quest = dlgQuest.ToLink<IQuestGetter>(), Category = DialogBranch.CategoryType.Player, Flags = DialogBranch.Flag.TopLevel };
        DialogTopic Topic(string ed, DialogBranch b, string prompt)
        {
            var x = new DialogTopic(NewKey(), SkyrimRelease.SkyrimSE)
            {
                EditorID = ed, Name = prompt, Priority = 50, Branch = b.ToNullableLink(), Quest = dlgQuest.ToNullableLink(),
                Category = DialogTopic.CategoryEnum.Topic, Subtype = DialogTopic.SubtypeEnum.Custom, SubtypeName = new RecordType("CUST"),
            };
            b.StartingTopic.SetTo(x.FormKey);
            return x;
        }
        void Chain(DialogTopic t, DialogResponses r) { if (t.Responses.Count > 0) r.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(t.Responses[^1].FormKey); t.Responses.Add(r); }
        var bStart = Branch("AGHallTrialBranchStart"); var tStart = Topic("AGHallTrialTopicStart", bStart, tq.GetProperty("prompts").GetProperty("trialStart").GetString()!);
        var bHand = Branch("AGHallTrialBranchHandIn"); var tHand = Topic("AGHallTrialTopicHandIn", bHand, tq.GetProperty("prompts").GetProperty("trialHandIn").GetString()!);
        const string W = "AGHallGuildMaster";
        var intro = Parts(tq.GetProperty("willem").GetProperty("intro"));
        string? firstIntro = null;   // the intro is recorded once, under the first trial's INFO
        for (var i = 0; i < trials.Count; i++)
        {
            var t = trials[i]; var q = quests[i]; var rank = t.GetProperty("rank").GetString()!;
            var brief = Parts(t.GetProperty("brief"));
            Condition[] Before() => new Condition[] { IsWillem() }.Concat(InHallCells()).Append(TrialsOn(true))
                .Append(StageOf(q, CompareOperator.GreaterThanOrEqualTo, 10)).Append(StageOf(q, CompareOperator.LessThan, 20)).ToArray();
            FormKey? waits = t.GetProperty("creature").TryGetProperty("waitsFor", out var wf) ? Ed<IQuestGetter>(wf.GetString()!).FormKey : null;
            if (waits is { } mq)
            {
                var ny = Info($"AGHallInfo_{W}_trial_notYet{rank}", W, $"{W}:trial:notYet{rank}",
                    Parts(tq.GetProperty("willem").GetProperty("notYet" + rank)).Select(x => (x, (string?)null)), tStart.EditorID!, dlgQuest.EditorID!);
                ny.Conditions.AddRange(Before()); ny.Conditions.Add(Completed(mq, false));
                ny.VirtualMachineAdapter = Tif("Fragment_NotYet", TrialProp(q));
                Chain(tStart, ny);
            }
            var briefKey = $"{W}:trial:brief{rank}";
            var withIntro = Info($"AGHallInfo_{W}_trial_introBrief{rank}", W, $"{W}:trial:introBrief{rank}",
                intro.Select((x, k) => (x, firstIntro == null ? null : (string?)$"{firstIntro}#{k + 1}"))
                     .Concat(brief.Select((x, k) => (x, (string?)$"{briefKey}#{k + 1}"))), tStart.EditorID!, dlgQuest.EditorID!);
            firstIntro ??= $"{W}:trial:introBrief{rank}";
            withIntro.Conditions.AddRange(Before()); withIntro.Conditions.Add(GlobalIs(gIntro.FormKey, CompareOperator.EqualTo, 0));
            if (waits is { } mq2) withIntro.Conditions.Add(Completed(mq2, true));
            withIntro.VirtualMachineAdapter = Tif("Fragment_Brief", TrialProp(q));
            Chain(tStart, withIntro);
            var alone = Info($"AGHallInfo_{W}_trial_brief{rank}", W, briefKey, brief.Select(x => (x, (string?)null)), tStart.EditorID!, dlgQuest.EditorID!);
            alone.Conditions.AddRange(Before());
            if (waits is { } mq3) alone.Conditions.Add(Completed(mq3, true));
            alone.VirtualMachineAdapter = Tif("Fragment_Brief", TrialProp(q));
            Chain(tStart, alone);
            var done = Info($"AGHallInfo_{W}_trial_done{rank}", W, $"{W}:trial:done{rank}", Parts(t.GetProperty("done")).Select(x => (x, (string?)null)), tHand.EditorID!, dlgQuest.EditorID!);
            done.Conditions.Add(IsWillem()); done.Conditions.AddRange(InHallCells()); done.Conditions.Add(TrialsOn(true));
            done.Conditions.Add(StageOf(q, CompareOperator.EqualTo, 40)); done.Conditions.Add(Holds(trophies[i]));
            done.VirtualMachineAdapter = Tif("Fragment_HandIn", TrialProp(q));
            Chain(tHand, done);
        }
        // the clerks: ahead of their own lines in AGHallClerkTopicPromote ("I'd like to apply for promotion."), with the same
        // conditions (who, where, on shift, registered, eligible) and the trial's own
        var tPromote = mod.DialogTopics.FirstOrDefault(x => x.EditorID == "AGHallClerkTopicPromote");
        var tW0 = mod.DialogTopics.FirstOrDefault(x => x.EditorID == "AGHallTalkW0");
        var clerkTexts = clerkDlg.GetProperty("topics");
        var clerkInfos = new List<(DialogResponses Theirs, List<DialogResponses> Mine)>();
        foreach (var clerk in clerkIds)
        {
            var theirs = tPromote?.Responses.FirstOrDefault(r => r.EditorID == $"AGHallInfo_{clerk}_promoteAsk");
            var lines = tq.GetProperty("clerks").GetProperty(clerk);
            var ask = Info($"AGHallInfo_{clerk}_trial_ask", clerk, $"{clerk}:trial:ask", Parts(lines.GetProperty("trialAsk")).Select(x => (x, (string?)null)), "AGHallClerkTopicPromote", clerkQuest.EditorID!);
            var done = Info($"AGHallInfo_{clerk}_trial_done", clerk, $"{clerk}:trial:done",
                Parts(lines.GetProperty("trialDone")).Select(x => (x, (string?)null)).Append((clerkTexts.GetProperty(clerk).GetProperty("promote").GetString()!, (string?)$"{clerk}:promote")),
                "AGHallClerkTopicPromote", clerkQuest.EditorID!);
            done.Flags!.Flags |= DialogResponses.Flag.Goodbye;
            // the trial is done and already applied for: the player's line says so (the INFO's own prompt, RNAM, as vanilla does)
            done.Prompt = tq.GetProperty("prompts").GetProperty("clerkReady").GetString()!;
            ask.VirtualMachineAdapter = Tif("Fragment_Ask", TrialsProp());
            done.VirtualMachineAdapter = Tif("Fragment_Done", TrialsProp());
            if (theirs == null) continue;
            foreach (var x in new[] { ask, done }) foreach (var cnd in theirs.Conditions) x.Conditions.Add(cnd.DeepCopy());
            ask.Conditions.Add(TrialsOn(true));
            foreach (var q in quests) ask.Conditions.Add(Running(q, false));
            done.Conditions.Add(TrialsOn(true));
            for (var k = 0; k < quests.Count; k++) done.Conditions.Add(StageOf(quests[k], CompareOperator.EqualTo, 50, or: k < quests.Count - 1));
            clerkInfos.Add((theirs, new List<DialogResponses> { done, ask }));
        }
        // Willem's W0 with the trials on, ahead of his own: the approved first part, then his recorded others (their takes)
        var theirW0 = tW0?.Responses.FirstOrDefault(r => r.EditorID == $"AGHallInfo_{W}_talk_W0");
        var w0 = Info($"AGHallInfo_{W}_trial_W0", W, $"{W}:trial:W0", Parts(tq.GetProperty("willem").GetProperty("W0")).Select(x => (x, (string?)null))
            .Concat((theirW0?.Responses.Skip(1) ?? Enumerable.Empty<DialogResponse>()).Select(r => (r.Text!.String!, (string?)$"{W}:talk:W0#{r.ResponseNumber}"))), "AGHallTalkW0", clerkQuest.EditorID!);
        if (theirW0 != null)
        {
            foreach (var cnd in theirW0.Conditions) w0.Conditions.Add(cnd.DeepCopy());
            w0.Conditions.Add(TrialsOn(true));
            foreach (var l in theirW0.LinkTo) w0.LinkTo.Add(new FormLink<IDialogTopicGetter>(l.FormKey));
            w0.Flags!.Flags = theirW0.Flags?.Flags ?? 0;
        }

        // into the plugin, when the build includes them
        trAdd.Add(() =>
        {
            mod.Globals.Add(gTrials); mod.Globals.Add(gIntro);
            mod.Quests.Add(dlgQuest); foreach (var q in quests) mod.Quests.Add(q);
            foreach (var n in creatures) mod.Npcs.Add(n);
            foreach (var x in trophies) mod.MiscItems.Add(x);
            if (ownAnchor != null) cell.Persistent.Add(ownAnchor);
            mod.DialogBranches.Add(bStart); mod.DialogBranches.Add(bHand);
            mod.DialogTopics.Add(tStart); mod.DialogTopics.Add(tHand);
            // ahead of their record in its topic, keeping the topic's PreviousDialog chain; theirs then waits for trials off
            void Ahead(DialogTopic t, DialogResponses theirs, List<DialogResponses> mine)
            {
                var at = t.Responses.IndexOf(theirs);
                var prev = at > 0 ? t.Responses[at - 1].FormKey : (FormKey?)null;
                foreach (var m in mine) { m.PreviousDialog = prev is { } p ? new FormLinkNullable<IDialogResponsesGetter>(p) : new FormLinkNullable<IDialogResponsesGetter>(); prev = m.FormKey; }
                theirs.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(prev!.Value);
                for (var k = 0; k < mine.Count; k++) t.Responses.Insert(at + k, mine[k]);
                theirs.Conditions.Add(TrialsOn(false));
            }
            foreach (var (theirs, mine) in clerkInfos) Ahead(tPromote!, theirs, mine);
            if (theirW0 != null) Ahead(tW0!, theirW0, new List<DialogResponses> { w0 });
            if (clerkInfos.Count < clerkIds.Length) Console.WriteLine("WARNING trials: the clerks' promote lines are not in this build: their trial lines left out");
            if (theirW0 == null) Console.WriteLine("WARNING trials: Willem's guild-talk W0 is not in this build: his trial W0 left out");
        });
        return 0;
    });
    CheckTakes(trLines.Select(l => (l.Key, l.Id)));
    string TrFile(string quest, string topic, uint fid, int part)
    {
        var (q, tp) = (quest, topic);
        if (q.Length + tp.Length > 25) { q = q[..Math.Min(q.Length, 10)]; tp = tp[..Math.Min(tp.Length, 25 - q.Length)]; }
        return $"{q}_{tp}_{fid:X8}_{part}.fuz".ToLowerInvariant();
    }
    var trMissing = trLines.Count(l => !File.Exists(Path.Combine(npcsDir, "build", "Sound", "Voice", "AdventurersGuild - Guild Hall.esp", VoiceOf(l.Npc),
        TrFile(l.Quest, l.Topic, l.Id >= 0x8000 ? l.Id : idBase + l.Id, l.Part))));
    if (trMissing > 0 && Environment.GetEnvironmentVariable("AG_TRIAL_BUILD") != "1")
        Console.WriteLine($"WARNING promotion trials held out of this build: {trMissing} of {trLines.Count} voice files not in build/Sound yet");
    else
    {
        foreach (var a in trAdd) a();
        Console.WriteLine($"promotion trials: {trials.Count} quests, {trLines.Count} spoken parts ({trLines.Count(l => l.CopyOf != null)} reuse a take){(trMissing > 0 ? $", {trMissing} voice files missing (AG_TRIAL_BUILD=1)" : "")}");
    }
    if (merge) File.WriteAllText(Path.Combine(npcsDir, "build", "trial_lines.json"), JsonSerializer.Serialize(trLines.Select(l => new { key = l.Key, npc = l.Npc,
        voice = VoiceOf(l.Npc), info = $"{(l.Id >= 0x8000 ? l.Id : idBase + l.Id):X8}", response = l.Part, quest = l.Quest, topic = l.Topic, text = l.Text, copyOf = l.CopyOf }),
        new JsonSerializerOptions { WriteIndented = true }));
}

// merged, only what ships: not the audition's candidate faces, nor the hair and colours no one wears (their IDs stay
// reserved, so every shipped record keeps its ID)
if (merge)
{
    var gone = mod.Npcs.Where(n => n.FormKey.ID >= 0x8000 && (n.EditorID ?? "").StartsWith("AGHallFaceCandidate")).Select(n => n.FormKey).ToList();
    foreach (var k in gone) mod.Npcs.Remove(k);
    var worn = new HashSet<FormKey>();
    void Wear(FormKey k)
    {
        if (!worn.Add(k) || !mod.HeadParts.TryGetValue(k, out var hp)) return;
        foreach (var x in hp.ExtraParts) Wear(x.FormKey);
    }
    foreach (var n in mod.Npcs) foreach (var h in n.HeadParts) Wear(h.FormKey);
    var hairGone = mod.HeadParts.Where(h => h.FormKey.ID >= 0x8000 && !worn.Contains(h.FormKey)).Select(h => h.FormKey).ToList();
    foreach (var k in hairGone) mod.HeadParts.Remove(k);
    var colours = mod.Npcs.Select(n => n.HairColor.FormKeyNullable).Where(k => k != null).Select(k => k!.Value).ToHashSet();
    var colourGone = mod.Colors.Where(c => c.FormKey.ID >= 0x8000 && !colours.Contains(c.FormKey)).Select(c => c.FormKey).ToList();
    foreach (var k in colourGone) mod.Colors.Remove(k);
    Console.WriteLine($"merge: left out {gone.Count} audition faces, {hairGone.Count} unworn head parts, {colourGone.Count} unworn hair colours");
}
next = Math.Max(next, hairNext);
next = Math.Max(next, topNext);
// The header's next ID is past every record the plugin holds: sections in fixed blocks (InIds: the about questions at
// merged 0x9000, the trials at 0x9800) reset `next` behind them, so `next` alone left it at 0x8FE7, inside those blocks,
// where xEdit or the CK would hand out colliding IDs (AG Detail Work, 2026-11-05).
var lastId = mod.EnumerateMajorRecords().Where(r => r.FormKey.ModKey == mod.ModKey).Select(r => r.FormKey.ID).DefaultIfEmpty(0u).Max();
mod.ModHeader.Stats.NextFormID = Math.Max(merge ? Math.Max(mod.ModHeader.Stats.NextFormID, idBase + next) : next, lastId + 1);
// No NPC's own package list may hold a package with an owner quest: the engine rejects it at data load and hangs removing it
// (2026-11-04, every install stuck on the first loading screen). Quest packages belong on the quest's aliases.
{
    var questPkgs = mod.Packages.Where(p => !p.OwnerQuest.IsNull).Select(p => p.FormKey).ToHashSet();
    var questListed = mod.Npcs.SelectMany(n => n.Packages.Where(l => questPkgs.Contains(l.FormKey)).Select(l => $"{n.EditorID} lists {mod.Packages[l.FormKey].EditorID}")).ToList();
    if (questListed.Count > 0) throw new Exception($"{questListed.Count} NPC package(s) with an owner quest (the engine hangs at data load on them): {string.Join("; ", questListed)}");
}
// AG's own plugin loads before the hall's (the clerks' lines read its globals and run its fragment)
var loadOrder = vanilla.Select(x => x.ModKey).Append(agEsp).Append(hall.ModKey).ToList();
// whileOpen's quests, now that every quest is built; one left out of this build (AG_CARALION_BUILD=0) drops the condition
foreach (var (lqData, qed, info) in lateQuests)
{
    var q = mod.Quests.FirstOrDefault(x => x.EditorID == qed);
    if (q != null) lqData.Quest.Link.SetTo(q.FormKey);
    else { info.Conditions.RemoveAll(c => c.Data == lqData); Console.WriteLine($"whileOpen: {qed} is not in this build; {info.EditorID} shows without it"); }
}
mod.WriteToBinary(outPath, new BinaryWriteParameters { ModKey = ModKeyOption.CorrectToPath, MastersListContent = MastersListContentOption.Iterate, MastersListOrdering = new MastersListOrderingByLoadOrder(loadOrder) });
// Start-game-enabled quests that own dialogue must be listed in SEQ/<plugin>.seq or their topics can fail to appear
// (AG's EspGen, the same format: uint32 FormIDs as stored in the plugin, the top byte the plugin's own index = its
// master count). Written to npcs/build/SEQ; merge_npcs.sh puts it beside the hall's plugin.
using (var written = SkyrimMod.CreateFromBinaryOverlay(outPath, SkyrimRelease.SkyrimSE))
{
    var self = (uint)written.ModHeader.MasterReferences.Count;
    var seqQuests = written.Quests.Where(q => q.FormKey.ModKey == written.ModKey && q.Flags.HasFlag(Quest.Flag.StartGameEnabled)
        && written.DialogTopics.Any(t => t.Quest.FormKey == q.FormKey)).Select(q => q.FormKey.ID).OrderBy(id => id).ToList();
    var seqDir = Path.Combine(npcsDir, "build", "SEQ"); Directory.CreateDirectory(seqDir);
    var seqPath = Path.Combine(seqDir, Path.ChangeExtension(Path.GetFileName(outPath), ".seq"));
    using (var bw = new BinaryWriter(File.Create(seqPath))) foreach (var id in seqQuests) bw.Write((self << 24) | id);
    Console.WriteLine($"wrote SEQ/{Path.GetFileName(seqPath)}: {string.Join(", ", seqQuests.Select(id => $"0x{id:X}"))} (masters {self}: {string.Join(",", written.ModHeader.MasterReferences.Select(m => m.Master.FileName))})");
}
File.WriteAllText(Path.Combine(outDir, "recipes.json"), JsonSerializer.Serialize(new { seed, recipes }, new JsonSerializerOptions { WriteIndented = true }));
Console.WriteLine($"wrote {outPath}{(merge ? " (merged into the hall's plugin)" : "")}: {mod.Npcs.Count} NPCs, {placed} placed (next ID {mod.ModHeader.Stats.NextFormID:X}); pools: Imperial women {Pool("ImperialRace", true).Count}, bearded Nord men {Pool("NordRace", false, true).Count}");
