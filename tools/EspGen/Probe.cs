using System.Text.RegularExpressions;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Skyrim;

// Read-only look at the vanilla masters (and optionally another plugin), so every editor ID this
// mod's config names comes from the real records, not from memory.
//   dotnet run -- --probe <factions|npcs|races|keywords|books|activators|locations> [regex] [extra plugin path]
static class Probe
{
    // the game's Data folder (the vanilla masters are read from it): SKYRIM_DATA, which build.ps1 sets from local.env
    public static readonly string DataDir = Environment.GetEnvironmentVariable("SKYRIM_DATA")
        ?? throw new InvalidOperationException("SKYRIM_DATA is not set (the game's Data folder; see local.env.example)");
    public static readonly string[] Masters = { "Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm", "Dragonborn.esm" };

    public static List<ISkyrimModDisposableGetter> LoadMasters()
        => Masters.Select(m => SkyrimMod.CreateFromBinaryOverlay(Path.Combine(DataDir, m), SkyrimRelease.SkyrimSE)).ToList();

    public static void Run(string[] args)
    {
        var what = args.Length > 1 ? args[1] : "factions";
        var re = new Regex(args.Length > 2 ? args[2] : ".", RegexOptions.IgnoreCase);
        var mods = LoadMasters();
        if (args.Length > 3) mods.Add(SkyrimMod.CreateFromBinaryOverlay(args[3], SkyrimRelease.SkyrimSE));
        if (what == "missives") { Missives(mods[^1], re); return; }
        if (what == "npcinfo") {    // NPCs by editor ID: voice type and faction editor IDs (is this one recruitable?)
            var vts = mods.SelectMany(m => m.VoiceTypes).GroupBy(v => v.FormKey).ToDictionary(g => g.Key, g => g.Last().EditorID ?? "?");
            var fcs = mods.SelectMany(m => m.Factions).GroupBy(f => f.FormKey).ToDictionary(g => g.Key, g => g.Last().EditorID ?? "?");
            foreach (var n in mods.SelectMany(m => m.Npcs).GroupBy(n => n.FormKey).Select(g => g.Last()).Where(n => re.IsMatch(n.EditorID ?? "")))
                Console.WriteLine($"{n.FormKey}\t{n.EditorID}\t\"{n.Name?.String}\"\tvoice={(n.Voice.IsNull ? "-" : vts.GetValueOrDefault(n.Voice.FormKey, "?"))}\t" +
                    string.Join(",", n.Factions.Select(f => fcs.GetValueOrDefault(f.Faction.FormKey, "?"))));
            return;
        }
        if (what == "headparts") {  // the LAST plugin's NPC records (editor ID match): head parts, hair colour, race, template
            foreach (var n in mods[^1].Npcs.Where(n => re.IsMatch(n.EditorID ?? "")))
            {
                Console.WriteLine($"{n.FormKey}\t{n.EditorID}\trace={n.Race.FormKey}\ttemplate={(n.Template.IsNull ? "-" : n.Template.FormKey.ToString())}\thairColor={(n.HairColor.IsNull ? "-" : n.HairColor.FormKey.ToString())}\tfaceTex={(n.HeadTexture.IsNull ? "-" : n.HeadTexture.FormKey.ToString())}");
                foreach (var h in n.HeadParts) Console.WriteLine($"   headpart {h.FormKey}");
            }
            return;
        }
        if (what == "info") {       // INFOs by FormID (regex on the 8-digit hex): topic, subtype, quest + priority, flags, text
            var quests = mods.SelectMany(m => m.Quests).GroupBy(q => q.FormKey).ToDictionary(g => g.Key, g => g.Last());
            foreach (var m in mods)
                foreach (var t in m.DialogTopics)
                    foreach (var i in t.Responses.Where(i => re.IsMatch($"{i.FormKey.ID:X8}")))
                        Console.WriteLine($"{i.FormKey.ID:X8}\t{m.ModKey.FileName}\ttopic={t.EditorID}\tsubtype={t.Subtype}/{t.SubtypeName}\tquest={(quests.TryGetValue(t.Quest.FormKey, out var q) ? q.EditorID + " prio " + q.Priority : "?")}\tflags={i.Flags?.Flags}\tconds={i.Conditions.Count}\t\"{string.Join(" | ", i.Responses.Select(r => r.Text?.String))}\"");
            return;
        }
        if (what == "says") {       // every INFO whose conditions name this NPC (GetIsID), with its topic: what they say in vanilla
            var npcKey = mods.SelectMany(m => m.Npcs).FirstOrDefault(n => re.IsMatch(n.EditorID ?? ""))?.FormKey;
            if (npcKey is null) { Console.WriteLine("no NPC matches"); return; }
            foreach (var m in mods)
                foreach (var t in m.DialogTopics)
                    foreach (var i in t.Responses.Where(i => i.Conditions.Any(c => c.Data is IGetIsIDConditionDataGetter g && g.Object.Link.FormKey == npcKey)))
                        foreach (var r in i.Responses)
                            Console.WriteLine($"{m.ModKey.FileName}\t{i.FormKey.ID:X8}_{r.ResponseNumber}\t{t.EditorID}\t{t.Subtype}\t\"{r.Text?.String}\"");
            return;
        }
        if (what == "sayswhen") {   // like "says", with each INFO's other conditions and the NPC's level: WHEN they say it
            var npc = mods.SelectMany(m => m.Npcs).GroupBy(n => n.FormKey).Select(g => g.Last()).FirstOrDefault(n => re.IsMatch(n.EditorID ?? ""));
            if (npc is null) { Console.WriteLine("no NPC matches"); return; }
            var names = mods.SelectMany(m => m.EnumerateMajorRecords()).Where(r => r.EditorID != null).GroupBy(r => r.FormKey).ToDictionary(g => g.Key, g => g.Last().EditorID!);
            Console.WriteLine($"{npc.EditorID}: level {(npc.Configuration.Level is INpcLevelGetter nl ? nl.Level.ToString() : npc.Configuration.Level is IPcLevelMultGetter pm ? "player x" + pm.LevelMult : "?")} (calc {npc.Configuration.CalcMinLevel}-{npc.Configuration.CalcMaxLevel}), flags {npc.Configuration.Flags}, class {names.GetValueOrDefault(npc.Class.FormKey, "?")}, aggression {npc.AIData.Aggression}, confidence {npc.AIData.Confidence}");
            string Cond(IConditionGetter c)
            {
                var d = c.Data;
                var ps = d.GetType().GetProperties().Where(p => p.Name is not ("RunOnType" or "Reference" or "Unknown3" or "UseAliases" or "UsePackageData" or "StaticRegistration" or "Function"))
                    .Select(p => { object? v = null; try { v = p.GetValue(d); } catch { }
                        var link = v?.GetType().GetProperty("Link")?.GetValue(v) ?? v;
                        var fk = link?.GetType().GetProperty("FormKey")?.GetValue(link);
                        return fk is FormKey k ? names.GetValueOrDefault(k, k.ToString()) : (v is string or int or float or bool or Enum ? v.ToString() : null); })
                    .Where(x => !string.IsNullOrEmpty(x));
                var cmp = c is IConditionFloatGetter f ? f.ComparisonValue.ToString() : "global";
                return $"{d.GetType().Name.Replace("ConditionDataBinaryOverlay", "").Replace("ConditionData", "")}({string.Join(",", ps)}) {c.CompareOperator} {cmp}{(c.Flags.HasFlag(Condition.Flag.OR) ? " OR" : "")}";
            }
            foreach (var m in mods)
                foreach (var t in m.DialogTopics)
                    foreach (var i in t.Responses.Where(i => i.Conditions.Any(c => c.Data is IGetIsIDConditionDataGetter g && g.Object.Link.FormKey == npc.FormKey)))
                    {
                        Console.WriteLine($"[{t.EditorID} / {t.Subtype}] {string.Join(" | ", i.Responses.Select(r => "\"" + r.Text?.String + "\""))}");
                        Console.WriteLine("      when: " + string.Join("; ", i.Conditions.Where(c => c.Data is not IGetIsIDConditionDataGetter).Select(Cond)));
                    }
            return;
        }
        if (what == "npcdetail") {  // scripts (with object properties), packages and their conditions: what an NPC is wired to do
            var names = mods.SelectMany(m => m.EnumerateMajorRecords()).Where(r => r.EditorID != null).GroupBy(r => r.FormKey).ToDictionary(g => g.Key, g => g.Last().EditorID!);
            var pkgs = mods.SelectMany(m => m.Packages).GroupBy(x => x.FormKey).ToDictionary(g => g.Key, g => g.Last());
            foreach (var n in mods.SelectMany(m => m.Npcs).GroupBy(n => n.FormKey).Select(g => g.Last()).Where(n => re.IsMatch(n.EditorID ?? "")))
            {
                Console.WriteLine($"== {n.EditorID}");
                foreach (var sc in n.VirtualMachineAdapter?.Scripts ?? [])
                    Console.WriteLine($"   script {sc.Name}: " + string.Join(", ", sc.Properties.Select(pr => pr.Name + (pr is IScriptObjectPropertyGetter o ? "=" + names.GetValueOrDefault(o.Object.FormKey, o.Object.FormKey.ToString()) : ""))));
                foreach (var pk in n.Packages)
                {
                    if (!pkgs.TryGetValue(pk.FormKey, out var p)) continue;
                    var cs = string.Join("; ", p.Conditions.Select(c => c.Data.GetType().Name.Replace("ConditionDataBinaryOverlay", "") + "(" + string.Join(",", c.Data.GetType().GetProperties()
                        .Select(q => { object? v = null; try { v = q.GetValue(c.Data); } catch { } var link = v?.GetType().GetProperty("Link")?.GetValue(v); var fk = link?.GetType().GetProperty("FormKey")?.GetValue(link); return fk is FormKey k && !k.IsNull ? names.GetValueOrDefault(k, k.ToString()) : null; })
                        .Where(x => x != null)) + $") {c.CompareOperator} {(c is IConditionFloatGetter f ? f.ComparisonValue : 0)}"));
                    Console.WriteLine($"   package {p.EditorID}  when: {cs}");
                }
            }
            return;
        }
        if (what == "refsto") {     // every record that links to the NPC(s) matched (top-level records; INFOs via their topic)
            var keys = mods.SelectMany(m => m.Npcs).Where(n => re.IsMatch(n.EditorID ?? "")).Select(n => n.FormKey).ToHashSet();
            foreach (var m in mods)
                foreach (var r in m.EnumerateMajorRecords())
                {
                    if (r is INpcGetter || r is IPlacedGetter || r is IDialogResponsesGetter || r is IDialogTopicGetter) continue;
                    bool hit; try { hit = r.EnumerateFormLinks().Any(l => keys.Contains(l.FormKey)); } catch { continue; }
                    if (hit) Console.WriteLine($"{m.ModKey.FileName}	{r.GetType().Name.Replace("BinaryOverlay", "")}	{r.FormKey.ID:X6}	{r.EditorID}");
                }
            return;
        }
        if (what == "aliases") {    // a quest's aliases: who fills each, the factions and packages it gives, its scripts and fill conditions
            var names = mods.SelectMany(m => m.EnumerateMajorRecords()).Where(r => r.EditorID != null).GroupBy(r => r.FormKey).ToDictionary(g => g.Key, g => g.Last().EditorID!);
            string N(FormKey k) => k.IsNull ? "-" : names.GetValueOrDefault(k, k.ToString());
            foreach (var q in mods.SelectMany(m => m.Quests).GroupBy(x => x.FormKey).Select(g => g.Last()).Where(x => re.IsMatch(x.EditorID ?? "")))
            {
                Console.WriteLine($"== {q.EditorID}");
                var filter = args.Length > 3 ? new Regex(args[3], RegexOptions.IgnoreCase) : null;
                foreach (var al in q.Aliases)
                {
                    var line = $"   [{al.ID}] {al.Name}  unique={N(al.UniqueActor.FormKey)} forced={N(al.ForcedReference.FormKey)} flags={al.Flags}" +
                        $" | factions: {string.Join(",", al.Factions.Select(f => N(f.FormKey)))} | packages: {string.Join(",", al.PackageData.Select(f => N(f.FormKey)))}" +
                        $" | conditions: {string.Join("; ", al.Conditions.Select(c => c.Data.GetType().Name.Replace("ConditionDataBinaryOverlay", "") + " " + string.Join(",", c.Data.EnumerateFormLinks().Select(l => N(l.FormKey))) + $" {c.CompareOperator} {(c is IConditionFloatGetter f ? f.ComparisonValue : 0)}"))}";
                    if (filter == null || filter.IsMatch(line)) Console.WriteLine(line);
                }
                var vm = q.VirtualMachineAdapter;
                if (vm != null) foreach (var fa in vm.Aliases) Console.WriteLine($"   alias scripts [{fa.Property.Alias}]: " + string.Join("; ", fa.Scripts.Select(x => x.Name + "(" + string.Join(", ", x.Properties.Select(pr => pr.Name + (pr is IScriptObjectPropertyGetter o ? "=alias " + o.Alias + " of " + N(o.Object.FormKey) : ""))) + ")")));
            }
            return;
        }
        if (what == "cells") {      // interior cells by editor ID
            foreach (var m in mods)
                foreach (var c in m.EnumerateMajorRecords<ICellGetter>().Where(c => re.IsMatch(c.EditorID ?? "")))
                    Console.WriteLine($"{m.ModKey.FileName}|0x{c.FormKey.ID:X6}  {c.EditorID}  {c.Name?.String}");
            return;
        }
        if (what == "placed") {     // the placed references of the NPCs matched (a unique actor has one)
            var bases = mods.SelectMany(m => m.Npcs).Where(n => re.IsMatch(n.EditorID ?? "")).GroupBy(n => n.FormKey).ToDictionary(g => g.Key, g => g.Last().EditorID);
            foreach (var m in mods)
                foreach (var r in m.EnumerateMajorRecords<IPlacedNpcGetter>().Where(r => bases.ContainsKey(r.Base.FormKey)))
                    Console.WriteLine($"{bases[r.Base.FormKey]}\t{m.ModKey.FileName}|0x{r.FormKey.ID:X6}\t{r.EditorID}");
            return;
        }
        if (what == "questids") {   // quests by editor ID
            foreach (var q in mods.SelectMany(m => m.Quests).GroupBy(x => x.FormKey).Select(g => g.First()).Where(x => re.IsMatch(x.EditorID ?? "")))
                Console.WriteLine($"{q.FormKey.ModKey.FileName}|0x{q.FormKey.ID:X6}\t{q.EditorID}");
            return;
        }
        if (what == "creatures") {  // every vanilla encounter creature with its own stats: one TSV row each (threat calibration)
            var races = mods.SelectMany(m => m.Races).GroupBy(r => r.FormKey).ToDictionary(g => g.Key, g => g.Last());
            var classes = mods.SelectMany(m => m.Classes).GroupBy(r => r.FormKey).ToDictionary(g => g.Key, g => g.Last());
            var weapons = mods.SelectMany(m => m.Weapons).GroupBy(r => r.FormKey).ToDictionary(g => g.Key, g => g.Last());
            var armors = mods.SelectMany(m => m.Armors).GroupBy(r => r.FormKey).ToDictionary(g => g.Key, g => g.Last());
            var spells = mods.SelectMany(m => m.Spells).GroupBy(r => r.FormKey).ToDictionary(g => g.Key, g => g.Last());
            var kws = mods.SelectMany(m => m.Keywords).GroupBy(k => k.FormKey).ToDictionary(g => g.Key, g => g.Last().EditorID ?? "?");
            Console.WriteLine("formid\tedid\tname\trace\tlevel\thealthStart\thealthOffset\tclassHealthWeight\tunarmedDamage\tweaponDamage\tweapon\tattackMultMax\tskinArmor\tsize\tspells\taggression\tconfidence\tkeywords");
            foreach (var n in mods.SelectMany(m => m.Npcs).GroupBy(n => n.FormKey).Select(g => g.Last()))
            {
                var edid = n.EditorID ?? "";
                if (!Regex.IsMatch(edid, @"^(DLC\d)?Enc") || edid.Contains("Test") || !re.IsMatch(edid)) continue;
                if (n.Configuration.Level is not INpcLevelGetter lv) continue;
                if (!n.Template.IsNull && n.Configuration.TemplateFlags.HasFlag(NpcConfiguration.TemplateFlag.Stats)) continue;
                if (!races.TryGetValue(n.Race.FormKey, out var race)) continue;
                var rk = (race.Keywords ?? (IReadOnlyList<IFormLinkGetter<IKeywordGetter>>)Array.Empty<IFormLinkGetter<IKeywordGetter>>()).Select(k => kws.TryGetValue(k.FormKey, out var e) ? e : "?").ToList();
                if (rk.Contains("ActorTypeNPC")) continue;
                var start = race.Starting.TryGetValue(BasicStat.Health, out var h) ? h : 0f;
                var cw = classes.TryGetValue(n.Class.FormKey, out var cls) ? string.Join("/", new[] { BasicStat.Health, BasicStat.Magicka, BasicStat.Stamina }.Select(b => cls.StatWeights.TryGetValue(b, out var w) ? (int)w : 0)) : "";
                // the best weapon carried directly (creatures that fight with one: giants' clubs, draugr, falmer, rieklings)
                float wd = 0; string wn = "";
                foreach (var it in n.Items ?? (IReadOnlyList<IContainerEntryGetter>)Array.Empty<IContainerEntryGetter>())
                    if (weapons.TryGetValue(it.Item.Item.FormKey, out var wp) && (wp.BasicStats?.Damage ?? 0) > wd) { wd = wp.BasicStats!.Damage; wn = wp.EditorID ?? ""; }
                var am = race.Attacks.Count > 0 ? race.Attacks.Max(a => a.AttackData?.DamageMult ?? 1f) : 1f;
                var skin = !n.WornArmor.IsNull && armors.TryGetValue(n.WornArmor.FormKey, out var sa) ? sa.ArmorRating : (!race.Skin.IsNull && armors.TryGetValue(race.Skin.FormKey, out var rs) ? rs.ArmorRating : 0f);
                var sp = (n.ActorEffect?.Count ?? 0);
                Console.WriteLine(string.Join("\t", $"{n.FormKey.ID:X8}", edid, n.Name?.String ?? "", race.EditorID, lv.Level, start, n.Configuration.HealthOffset, cw, race.UnarmedDamage, wd, wn, am, skin, race.Size,
                    sp, n.AIData.Aggression, n.AIData.Confidence, string.Join(",", rk.Where(k => k.StartsWith("ActorType")))));
            }
            return;
        }
        if (what == "racedump") {   // one race's attack data and one actor's spells, every property (to see what the records offer)
            foreach (var race in mods.SelectMany(m => m.Races).GroupBy(r => r.FormKey).Select(g => g.Last()).Where(r => re.IsMatch(r.EditorID ?? "")))
            {
                Console.WriteLine($"== {race.EditorID} unarmed={race.UnarmedDamage} reach={race.UnarmedReach} mass={race.BaseMass} size={race.Size}");
                foreach (var a in race.Attacks)
                    Console.WriteLine("   attack " + a.AttackEvent + ": " + string.Join(", ", a.AttackData?.GetType().GetProperties().Where(p => p.PropertyType.IsPrimitive || p.PropertyType.IsEnum || p.PropertyType == typeof(float)).Select(p => { try { return p.Name + "=" + p.GetValue(a.AttackData); } catch { return ""; } }) ?? Array.Empty<string>()));
            }
            return;
        }
        if (what == "effects") {    // magic effects (editor ID or name matching): archetype and actor value
            foreach (var m in mods)
                foreach (var e in m.MagicEffects.Where(e => re.IsMatch(e.EditorID ?? "") || re.IsMatch(e.Name?.String ?? "")))
                {
                    Console.WriteLine($"{e.FormKey}\t{e.EditorID}\t\"{e.Name?.String}\"\t{e.Archetype.Type}\tav={e.Archetype.ActorValue}\tsecond={e.SecondActorValue}\tperk={e.PerkToApply.FormKeyNullable}");
                    var pk = mods.SelectMany(x => x.Perks).LastOrDefault(x => x.FormKey == e.PerkToApply.FormKeyNullable);
                    if (pk != null)
                        foreach (var en in pk.Effects)
                            Console.WriteLine($"      perk {pk.EditorID}: {en.GetType().Name.Replace("BinaryOverlay", "")} " +
                                (en is IPerkEntryPointModifyValueGetter mv ? $"{mv.EntryPoint} {mv.Modification} {mv.Value} tabs={mv.PerkConditionTabCount} conds={string.Join(",", mv.Conditions.Select(c => $"tab{c.RunOnTabIndex}:{c.Conditions.Count}"))}" : en is IAPerkEntryPointEffectGetter ep ? $"{ep.EntryPoint}" : ""));
                }
            return;
        }
        if (what == "plugin") {     // the LAST plugin at a glance: record counts, masters, its quests, containers, activators and books
            var m = mods[^1];
            Console.WriteLine($"{m.ModKey}  masters: {string.Join(", ", m.ModHeader.MasterReferences.Select(x => x.Master.FileName))}");
            Console.WriteLine(string.Join("  ", m.EnumerateMajorRecords().GroupBy(r => r.GetType().Name.Replace("BinaryOverlay", "")).OrderByDescending(g => g.Count()).Select(g => $"{g.Key}:{g.Count()}")));
            foreach (var c in m.Containers) Console.WriteLine($"CONT {c.FormKey.ID:X6} {c.EditorID} \"{c.Name?.String}\" scripts=[{string.Join(",", c.VirtualMachineAdapter?.Scripts.Select(s => s.Name) ?? [])}] own={c.FormKey.ModKey == m.ModKey}");
            foreach (var a in m.Activators) Console.WriteLine($"ACTI {a.FormKey.ID:X6} {a.EditorID} \"{a.Name?.String}\" scripts=[{string.Join(",", a.VirtualMachineAdapter?.Scripts.Select(s => s.Name) ?? [])}] own={a.FormKey.ModKey == m.ModKey}");
            foreach (var q in m.Quests.Where(q => re.IsMatch(q.EditorID ?? "")))
            {
                Console.WriteLine($"QUST {q.FormKey.ID:X6} {q.EditorID} \"{q.Name?.String}\" type={q.Type} flags={q.Flags} event={q.Event} prio={q.Priority} own={q.FormKey.ModKey == m.ModKey}");
                Console.WriteLine($"     scripts=[{string.Join(",", q.VirtualMachineAdapter?.Scripts.Select(s => s.Name) ?? [])}] dialogConds={q.DialogConditions.Count} eventConds={q.EventConditions.Count}");
                Console.WriteLine($"     stages: {string.Join(" ", q.Stages.Select(s => $"{s.Index}{(s.LogEntries.Any(l => l.Flags?.HasFlag(QuestLogEntry.Flag.CompleteQuest) == true) ? "(complete)" : "")}{(s.LogEntries.Any(l => l.Flags?.HasFlag(QuestLogEntry.Flag.FailQuest) == true) ? "(fail)" : "")}"))}");
                Console.WriteLine($"     objectives: {string.Join(" | ", q.Objectives.Select(o => $"{o.Index}:\"{o.DisplayText?.String}\""))}");
                foreach (var al in q.Aliases)
                    Console.WriteLine($"     alias {al.ID} {al.Name} [{al.Flags}] conds={al.Conditions.Count} created={(al.CreateReferenceToObject is null ? "-" : al.CreateReferenceToObject.Object.FormKey.ToString())} forced={(al.ForcedReference.IsNull ? "-" : al.ForcedReference.FormKey.ToString())} unique={(al.UniqueActor.IsNull ? "-" : al.UniqueActor.FormKey.ToString())}");
            }
            foreach (var b in m.Books.Where(b => re.IsMatch(b.EditorID ?? ""))) Console.WriteLine($"BOOK {b.FormKey.ID:X6} {b.EditorID} \"{b.Name?.String}\"");
            foreach (var f in m.FormLists) Console.WriteLine($"FLST {f.FormKey.ID:X6} {f.EditorID} items={f.Items.Count}: {string.Join(" ", f.Items.Select(i => $"{i.FormKey.ID:X6}"))}");
            foreach (var g in m.Globals) Console.WriteLine($"GLOB {g.FormKey.ID:X6} {g.EditorID}");
            return;
        }
        if (what == "ids") {        // every record of the LAST plugin: FormID, type, editor ID (to keep IDs stable)
            foreach (var r in mods[^1].EnumerateMajorRecords().OrderBy(r => r.FormKey.ID))
                Console.WriteLine($"{r.FormKey.ID:X6}\t{r.GetType().Name.Replace("BinaryOverlay", "")}\t{r.EditorID}\t{r.FormKey.ModKey}");
            return;
        }
        if (what == "boards") {     // every placed ref whose base is a Missives board container, with position
            var m = mods[^1];
            var bases = m.Containers.Where(c => re.IsMatch(c.EditorID ?? "")).ToDictionary(c => c.FormKey, c => c);
            foreach (var r in m.EnumerateMajorRecords<IPlacedObjectGetter>())
                if (bases.TryGetValue(r.Base.FormKey, out var c))
                    Console.WriteLine($"{r.FormKey.ID:X6} base={c.EditorID} model={c.Model?.File} pos=({r.Placement?.Position.X:F0},{r.Placement?.Position.Y:F0},{r.Placement?.Position.Z:F0}) rotZ={r.Placement?.Rotation.Z:F2} flags={r.MajorRecordFlagsRaw:X}");
            foreach (var c in bases.Values) Console.WriteLine($"base {c.FormKey.ID:X6} {c.EditorID} \"{c.Name?.String}\" model={c.Model?.File}");
            return;
        }
        if (what == "hellos") {     // every active plugin's Hello (HELO) topics with their quest priority: who outranks ours
            // env AG_PLUGINS_TXT = the profile's plugins.txt, AG_MODS_ROOT = the MO2 mods folder
            var active = File.ReadAllLines(Environment.GetEnvironmentVariable("AG_PLUGINS_TXT")!).Where(l => l.StartsWith("*")).Select(l => l[1..].Trim()).ToList();
            var files = Directory.EnumerateFiles(Environment.GetEnvironmentVariable("AG_MODS_ROOT")!, "*.es?", SearchOption.AllDirectories)
                .Where(f => Path.GetDirectoryName(f)!.Count(c => c == '\\' || c == '/') - Environment.GetEnvironmentVariable("AG_MODS_ROOT")!.Count(c => c == '\\' || c == '/') <= 1)
                .GroupBy(f => Path.GetFileName(f), StringComparer.OrdinalIgnoreCase).ToDictionary(g => g.Key, g => g.First(), StringComparer.OrdinalIgnoreCase);
            foreach (var name in Masters.Concat(active).Distinct(StringComparer.OrdinalIgnoreCase))
            {
                var path = files.TryGetValue(name, out var f) ? f : Path.Combine(DataDir, name);
                if (!File.Exists(path)) continue;
                try
                {
                    using var m = SkyrimMod.CreateFromBinaryOverlay(path, SkyrimRelease.SkyrimSE);
                    var quests = m.Quests.ToDictionary(q => q.FormKey, q => q);
                    foreach (var t in m.DialogTopics.Where(t => t.SubtypeName.Type == "HELO" && t.Responses.Count > 0))
                    {
                        var prio = quests.TryGetValue(t.Quest.FormKey, out var q) ? q.Priority.ToString() : "?";
                        var catchAll = t.Responses.Count(i => i.Conditions.Count == 0);
                        Console.WriteLine($"{prio}\t{name}\t{t.EditorID}\tquest={t.Quest.FormKey}\tinfos={t.Responses.Count}\tunconditioned={catchAll}");
                    }
                }
                catch (Exception e) { Console.Error.WriteLine($"{name}: {e.Message}"); }
            }
            return;
        }
        if (what == "dialog") {     // quests + dialogue topics of the LAST plugin: how another mod wires greetings/idles
            var m = mods[^1];
            foreach (var q in m.Quests)
                Console.WriteLine($"QUST {q.FormKey} {q.EditorID} prio={q.Priority} flags={q.Flags} type={q.Type}");
            foreach (var t in m.DialogTopics.Where(t => re.IsMatch(t.EditorID ?? "")))
            {
                Console.WriteLine($"DIAL {t.FormKey} {t.EditorID} quest={t.Quest.FormKey} cat={t.Category} sub={t.Subtype} ({t.SubtypeName}) prio={t.Priority} infos={t.Responses.Count} \"{t.Name?.String}\"");
                foreach (var i in t.Responses.Take(int.TryParse(Environment.GetEnvironmentVariable("AG_PROBE_INFOS"), out var nInfos) ? nInfos : 3))
                    Console.WriteLine($"   INFO {i.FormKey.ID:X6} pnam={(i.PreviousDialog.IsNull ? "-" : i.PreviousDialog.FormKey.ID.ToString("X6"))} flags={i.Flags?.Flags} resetH={i.Flags?.ResetHours} " +
                        string.Join(" & ", i.Conditions.Select(c => $"{c.Data.GetType().Name.Replace("ConditionData", "")}{(c is IConditionFloatGetter f ? $"{c.CompareOperator}{f.ComparisonValue}" : "")}{(c.Flags.HasFlag(Condition.Flag.OR) ? "|OR" : "")}")) +
                        $"  \"{i.Responses.FirstOrDefault()?.Text?.String}\"");
            }
            return;
        }
        if (what == "items") {      // misc items + ingredients of the LAST plugin loaded: value, weight, keywords (trophy matching)
            var kws = mods.SelectMany(m => m.Keywords).GroupBy(k => k.FormKey).ToDictionary(g => g.Key, g => g.Last().EditorID ?? "?");
            string K(IReadOnlyList<IFormLinkGetter<IKeywordGetter>>? l) => string.Join(",", (l ?? Array.Empty<IFormLinkGetter<IKeywordGetter>>()).Select(k => kws.TryGetValue(k.FormKey, out var e) ? e : k.FormKey.ToString()));
            var m = mods[^1];
            foreach (var i in m.MiscItems.Where(i => re.IsMatch(i.EditorID ?? "") || re.IsMatch(i.Name?.String ?? "")))
                Console.WriteLine($"MISC\t{i.FormKey}\t{i.EditorID}\t\"{i.Name?.String}\"\t{i.Value}g\t{K(i.Keywords)}");
            foreach (var i in m.Ingredients.Where(i => re.IsMatch(i.EditorID ?? "") || re.IsMatch(i.Name?.String ?? "")))
                Console.WriteLine($"INGR\t{i.FormKey}\t{i.EditorID}\t\"{i.Name?.String}\"\t{i.Value}g\t{K(i.Keywords)}");
            return;
        }
        if (what == "racesize") {   // race size class + starting health, for "large creature" rules
            foreach (var r in mods.SelectMany(m => m.Races).GroupBy(r => r.FormKey).Select(g => g.Last()).Where(r => re.IsMatch(r.EditorID ?? "")))
                Console.WriteLine($"{r.Size}\t{(r.Starting.TryGetValue(BasicStat.Health, out var h) ? h : 0)}\t{r.EditorID}");
            return;
        }
        if (what == "tough") {      // actors: level, health (race start + offset), race keywords - calibrates threat toughness
            var races = mods.SelectMany(m => m.Races).GroupBy(r => r.FormKey).ToDictionary(g => g.Key, g => g.Last());
            var kws = mods.SelectMany(m => m.Keywords).GroupBy(k => k.FormKey).ToDictionary(g => g.Key, g => g.Last().EditorID ?? "?");
            foreach (var n in mods.SelectMany(m => m.Npcs).GroupBy(n => n.FormKey).Select(g => g.Last()))
            {
                if (!re.IsMatch(n.EditorID ?? "") || !races.TryGetValue(n.Race.FormKey, out var race)) continue;
                var cfg = n.Configuration;
                var auto = cfg.Flags.HasFlag(NpcConfiguration.Flag.AutoCalcStats);
                var lvl = cfg.Level is INpcLevelGetter l ? l.Level.ToString() : cfg.Level is IPcLevelMultGetter p ? $"PCx{p.LevelMult}[{cfg.CalcMinLevel}-{cfg.CalcMaxLevel}]" : "?";
                var start = race.Starting.TryGetValue(BasicStat.Health, out var h) ? h : 0f;
                var rk = string.Join(",", (race.Keywords ?? (IReadOnlyList<IFormLinkGetter<IKeywordGetter>>)Array.Empty<IFormLinkGetter<IKeywordGetter>>())
                    .Select(k => kws.TryGetValue(k.FormKey, out var e) ? e : "?").Where(e => e.StartsWith("ActorType")));
                var tmpl = n.Template.IsNull ? "" : $" tmpl={cfg.TemplateFlags}";
                Console.WriteLine($"{n.EditorID}\tlvl={lvl}\tauto={auto}\thp={start}+{cfg.HealthOffset}={start + cfg.HealthOffset}\trace={race.EditorID}\t{rk}{tmpl}");
            }
            return;
        }
        if (what == "zones") {      // encounter zones: min/max level and location with its parent chain; regex filters the chain
            var locs = mods.SelectMany(m => m.Locations).GroupBy(l => l.FormKey).ToDictionary(g => g.Key, g => g.Last());
            string Chain(FormKey k)
            {
                var parts = new List<string>();
                for (int i = 0; i < 8 && !k.IsNull && locs.TryGetValue(k, out var l); i++)
                {
                    parts.Add(l.Name?.String ?? l.EditorID ?? "?");
                    k = l.ParentLocation.FormKey;
                }
                return string.Join(" < ", parts);
            }
            var clearKw = new[] { "LocTypeClearable", "LocTypeDungeon" };
            var kwIds = mods.SelectMany(m => m.Keywords).Where(k => clearKw.Contains(k.EditorID)).Select(k => k.FormKey).ToHashSet();
            bool Clearable(FormKey k) => locs.TryGetValue(k, out var l) && (l.Keywords?.Any(x => kwIds.Contains(x.FormKey)) ?? false);
            // zones are usually attached to cells (XEZN), and cells name their location (XLCN)
            var zones = mods.SelectMany(m => m.EncounterZones).GroupBy(z => z.FormKey).ToDictionary(g => g.Key, g => g.Last());
            var seen = new HashSet<(FormKey, FormKey)>();
            foreach (var cell in mods.SelectMany(m => m.EnumerateMajorRecords<ICellGetter>()))
            {
                var lk = cell.Location.FormKey; var zk = cell.EncounterZone.FormKey;
                if (lk.IsNull || zk.IsNull || !zones.TryGetValue(zk, out var z) || !seen.Add((lk, zk))) continue;
                var chain = Chain(lk);
                if (!re.IsMatch(chain) || !Clearable(lk)) continue;
                Console.WriteLine($"{z.MinLevel}\t{z.MaxLevel}\t{z.Flags}\t{chain}");
            }
            return;
        }
        if (what == "booktext") {   // raw book text: every <Alias=...>/<Global=...> token and markup tag, unstripped
            foreach (var b in mods[^1].Books.Where(b => re.IsMatch(b.EditorID ?? "")))
                Console.WriteLine($"== {b.EditorID}\n{b.BookText?.String}\n");
            return;
        }
        foreach (var m in mods)
        {
            IEnumerable<IMajorRecordGetter> recs = what switch
            {
                "factions" => m.Factions,
                "npcs" => m.Npcs,
                "races" => m.Races,
                "keywords" => m.Keywords,
                "books" => m.Books,
                "activators" => m.Activators,
                "locations" => m.Locations,
                "classes" => m.Classes,
                "ingredients" => m.Ingredients,
                "misc" => m.MiscItems,
                "potions" => m.Ingestibles,
                "formlists" => m.FormLists,
                "voicetypes" => m.VoiceTypes,
                "locreftypes" => m.LocationReferenceTypes,
                _ => Enumerable.Empty<IMajorRecordGetter>(),
            };
            foreach (var r in recs)
            {
                var edid = r.EditorID ?? "";
                if (!re.IsMatch(edid)) continue;
                var extra = r switch
                {
                    IFactionGetter f => $"name=\"{f.Name?.String}\"",
                    INpcGetter n => $"name=\"{n.Name?.String}\" voice={n.Voice.FormKey} factions=[{string.Join(",", n.Factions.Select(x => x.Faction.FormKey.ToString()))}]",
                    IBookGetter b => $"name=\"{b.Name?.String}\" value={b.Value} teaches={(b.Teaches is IBookSkillGetter sk ? "skill:" + sk.Skill : b.Teaches?.GetType().Name)}",
                    IIngredientGetter ig => $"name=\"{ig.Name?.String}\" value={ig.Value}",
                    IMiscItemGetter mi => $"name=\"{mi.Name?.String}\" value={mi.Value}",
                    IIngestibleGetter po => $"name=\"{po.Name?.String}\" value={po.Value}",
                    ILocationGetter lo => $"name=\"{lo.Name?.String}\" keywords=[{string.Join(",", (lo.Keywords ?? new List<IFormLinkGetter<IKeywordGetter>>()).Select(k => KwName(k.FormKey)))}]",
                    IActivatorGetter a => $"name=\"{a.Name?.String}\" model={a.Model?.File} scripts=[{string.Join(",", a.VirtualMachineAdapter?.Scripts.Select(s => s.Name) ?? Enumerable.Empty<string>())}]",
                    _ => "",
                };
                Console.WriteLine($"{m.ModKey.FileName}\t{r.FormKey.ID:X6}\t{edid}\t{extra}");
            }
        }
    }

    static Dictionary<FormKey, string>? _kw;
    static string KwName(FormKey k)
    {
        _kw ??= LoadMasters().SelectMany(m => m.Keywords).GroupBy(x => x.FormKey).ToDictionary(g => g.Key, g => g.Last().EditorID ?? "?");
        return _kw.TryGetValue(k, out var n) ? n : k.ToString();
    }

    // Missives internals: which tier lists a quest sits in (regex filters list editor IDs, e.g. "Whiterun"),
    // its aliases (name, scripts, how the ref is made), and the note Book's name/text.
    static void Missives(ISkyrimModDisposableGetter m, Regex listRe)
    {
        var books = m.Books.ToDictionary(b => b.FormKey);
        var quests = m.Quests.ToDictionary(q => q.FormKey);
        foreach (var list in m.FormLists.Where(l => (l.EditorID ?? "").StartsWith("_M_ListQuests") && listRe.IsMatch(l.EditorID!)))
        {
            Console.WriteLine($"== {list.EditorID} ({list.Items.Count})");
            foreach (var it in list.Items)
            {
                if (!quests.TryGetValue(it.FormKey, out var q)) { Console.WriteLine($"  {it.FormKey} (not a Missives quest)"); continue; }
                Console.WriteLine($"  {q.FormKey.ID:X6} {q.EditorID} \"{q.Name?.String}\" scripts=[{string.Join(",", q.VirtualMachineAdapter?.Scripts.Select(s => s.Name) ?? Enumerable.Empty<string>())}]");
                var aliasScripts = q.VirtualMachineAdapter is IQuestAdapterGetter qa
                    ? qa.Aliases.ToDictionary(a => (int)a.Property.Alias, a => string.Join(",", a.Scripts.Select(s => s.Name)))
                    : new Dictionary<int, string>();
                foreach (var a in q.Aliases)
                {
                    var how = a.CreateReferenceToObject is { } c
                        ? $"create obj={c.Object.FormKey} at=alias{c.AliasID}/{c.Create}"
                        : a.ForcedReference.FormKey.IsNull ? (a.Location?.GetType().Name ?? (a.External is null ? "" : "external")) : $"forced={a.ForcedReference.FormKey}";
                    Console.WriteLine($"    alias {a.ID} '{a.Name}' {how} scripts=[{(aliasScripts.TryGetValue((int)a.ID, out var sn) ? sn : "")}]");
                    if (a.CreateReferenceToObject is { } cc && books.TryGetValue(cc.Object.FormKey, out var b))
                    {
                        var txt = Regex.Replace(b.BookText?.String ?? "", "<[^>]+>|\\s+", " ").Trim();
                        Console.WriteLine($"      book {b.EditorID} \"{b.Name?.String}\" text: {txt[..Math.Min(260, txt.Length)]}");
                    }
                }
            }
        }
    }
}
