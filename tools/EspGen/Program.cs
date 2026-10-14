// Generates AdventurersGuild.esp (a normal plugin: see the header-flag note below) and resolves the editor IDs named in the mod's json
// config against the vanilla masters. Any unknown ID fails the build.
//   dotnet run -- <outDir> [configDir] [Missives.esp path]   (Missives 2.03 is a hard master)
//   dotnet run -- --probe <factions|npcs|races|keywords|books|activators|locations|classes> [regex] [plugin]
// FormIDs are FIXED once released (saves reference them): never renumber, only append.
//   0x800-0x81F  globals, quests, dialogue branches/topics (0x812/0x813 About, 0x814/0x815 fee globals, 0x816-0x819 fee choice topics)
//   0x900-0x9FF  Missives note variants per rank (MissivesPatch.cs)
//   0xA00-0xBFF  dialogue INFOs, pinned per key in config/dialogue.ids.json; full since 1.4.0, they go on in 0xD00-0xFFF
//   0x81F the party-member faction
//   0x810-0x81F  registration quest + missive; 0x81A the physical Guild Card (1.2.0), 0x81B-0x81E its replacement topic, fee and "missing" flag
//   0x8C0-0x8CF  world awareness: greetings quest/topics, retired-adventurer faction, recent-promotion global,
//                liaison faction (0x8C6) and reports-waiting global (0x8C7) for the SkyrimNet actions
//   0x8D0-0x8FF  party blessing: ability 0x8D0, Bond tier / members-present globals 0x8D1-0x8D2, one global per
//                trait from 0x8D3 (traits.json order, append only), then the effects of the first 8 traits
//   0xC80        the wandering-adventurer faction
//   0xC88-0xC8A  MCM > Audio (1.5.0): AG_GreetingsGlobal, AG_InteractionsGlobal, AG_RepLinesGlobal; 0xCE3 AG_FollowerCommentsGlobal
//   0xC81-0xC87  the notices' sounds (1.5.0), the "Skyrim" set: sound descriptors of ours that play the game's own files
//   0xC8B-0xC8F, 0xCE7-0xCE8  the "Guild Drums" set: the same seven notices, playing the mod's own drums (Sound\FX\AdventurersGuild)
//   0xC91-0xC92  AG_AdventurerRankFaction, AG_AdventurerPromotedFaction (a named member's rank, and "just promoted")
//   0xC93-0xC94  Teldryn Sero's "You're with the Adventurers Guild?" branch and topic
//   0xC90        AG_MissivesSolstheimGlobal (one global per Missives add-on, 0xC90-0xC9F)
//   0xCA0-0xCD7  Guild Augments: effects 0xCA0+, abilities 0xCC0+, perks 0xCD0+
//   0xCE0-0xCE5  Show Guild Card: the strongholds' branch and topic (0xCE4/5). 0xCE0-0xCE3 were the College's and the Treasury House's in
//                development builds only (never released): free.
//   0xC00-0xC7B  party traits 9+: their globals 0xC00-0xC0F (trait 9 = 0xC00), then their effects and perks
//   0xC7C-0xC7F  a dead adventurer's card (1.5.0): AG_MemberCardBloody, AG_MemberCardMorrowindBloody, and their inventory art
using System.Text.Json;
using System.Text.Json.Nodes;
using Mutagen.Bethesda;
using Mutagen.Bethesda.FormKeys.SkyrimSE;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Skyrim;

if (args.Length > 0 && args[0] == "--probe") { Probe.Run(args); return; }

const SkyrimRelease Rel = SkyrimRelease.SkyrimSE;
var outDir = args.Length > 0 ? args[0] : ".";
var configDir = args.Length > 1 ? args[1] : Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "../../../../../config/SKSE/Plugins/AdventurersGuild"));
Directory.CreateDirectory(outDir);

var masters = Probe.LoadMasters();
int errors = 0;

// ---------- editor ID resolution (later masters win, like the game) ----------
Dictionary<string, FormKey> Index(Func<ISkyrimModGetter, IEnumerable<IMajorRecordGetter>> pick)
{
    var d = new Dictionary<string, FormKey>(StringComparer.OrdinalIgnoreCase);
    foreach (var m in masters)
        foreach (var r in pick(m))
            if (!string.IsNullOrEmpty(r.EditorID)) d[r.EditorID] = r.FormKey;
    return d;
}
var idx = new Dictionary<string, Dictionary<string, FormKey>>
{
    ["factions"] = Index(m => m.Factions),
    ["races"] = Index(m => m.Races),
    ["keywords"] = Index(m => m.Keywords),
    ["npcs"] = Index(m => m.Npcs),
    ["globals"] = Index(m => m.Globals),
};
// Items the shop and trophy lists name with a single "form" string (books, potions, ingredients, misc).
var voiceIdx = Index(m => m.VoiceTypes);
var questIdx = Index(m => m.Quests);
var itemIdx = Index(m => m.Books.Cast<IMajorRecordGetter>().Concat(m.Ingestibles).Concat(m.Ingredients).Concat(m.MiscItems));
string Key(FormKey fk) => $"{fk.ModKey.FileName}|0x{fk.ID:X6}";

// Replaces every {"factions"|"races"|"keywords"|"npcs": [edid...]} list under a node with resolved keys.
JsonNode? ResolveNode(JsonNode? node, string where)
{
    switch (node)
    {
        case JsonObject o:
        {
            var outObj = new JsonObject();
            foreach (var (k, v) in o)
            {
                if (k.StartsWith("_")) continue;  // comments stay in the source file only
                if (idx.TryGetValue(k, out var map) && v is JsonArray arr)
                {
                    var res = new JsonArray();
                    foreach (var e in arr)
                    {
                        var edid = e!.GetValue<string>();
                        if (map.TryGetValue(edid, out var fk)) res.Add(Key(fk));
                        else { Console.Error.WriteLine($"ERROR {where}: unknown {k} editor ID '{edid}'"); errors++; }
                    }
                    outObj[k] = res;
                }
                else if (k == "form" && v is JsonValue pv && pv.TryGetValue<string>(out var key1) && key1.Contains('|'))
                    outObj[k] = key1;  // "Plugin.esp|0x0123": another mod's item, looked up at runtime (absent plugin = skipped)
                else if (k == "form" && v is JsonValue fv && fv.TryGetValue<string>(out var edid1))
                {
                    if (itemIdx.TryGetValue(edid1, out var fk1)) outObj[k] = Key(fk1);
                    else { Console.Error.WriteLine($"ERROR {where}: unknown item editor ID '{edid1}'"); errors++; }
                }
                else outObj[k] = ResolveNode(v, where);
            }
            return outObj;
        }
        case JsonArray a:
        {
            var outArr = new JsonArray();
            foreach (var e in a) outArr.Add(ResolveNode(e, where));
            return outArr;
        }
        default:
            return node?.DeepClone();
    }
}
JsonNode ReadConfig(string name) =>
    JsonNode.Parse(File.ReadAllText(Path.Combine(configDir, name + ".json")), documentOptions: new JsonDocumentOptions { CommentHandling = JsonCommentHandling.Skip, AllowTrailingCommas = true })!;
foreach (var name in new[] { "adventurers", "trophies", "shop", "traits" })
{
    var parsed = ReadConfig(name);
    // "wanderers": every vanilla NPC whose editor ID starts with one of npcPrefix, listed for the DLL
    if (name == "adventurers" && parsed["wanderers"] is JsonObject wn && wn["npcPrefix"] is JsonArray pf)
    {
        var prefixes = pf.Select(x => x!.GetValue<string>()).ToList();
        var found = idx["npcs"].Keys.Where(k => prefixes.Any(p => k.StartsWith(p, StringComparison.OrdinalIgnoreCase))).OrderBy(k => k).ToList();
        wn["npcs"] = new JsonArray(found.Select(k => (JsonNode)JsonValue.Create(k)!).ToArray());
        Console.WriteLine($"wanderers: {found.Count} vanilla wandering adventurers");
    }
    // "lostCards": every vanilla NPC whose editor ID matches one of a group's npcMatch, listed for the DLL
    if (name == "adventurers" && parsed["lostCards"] is JsonArray lost)
        foreach (var g in lost)
            if (g is JsonObject go && go["npcMatch"] is JsonArray pats)
            {
                var res = pats.Select(x => new System.Text.RegularExpressions.Regex(x!.GetValue<string>(), System.Text.RegularExpressions.RegexOptions.IgnoreCase)).ToList();
                var hit = idx["npcs"].Keys.Where(k => res.Any(r => r.IsMatch(k))).OrderBy(k => k).ToList();
                go["npcs"] = new JsonArray(hit.Select(k => (JsonNode)JsonValue.Create(k)!).ToArray());
                go.Remove("npcMatch");
                Console.WriteLine($"lost cards: group '{go["id"]}' - {hit.Count} vanilla bodies");
            }
    var resolved = ResolveNode(parsed, name + ".json");
    if (name == "shop" && resolved!["library"] is JsonObject lib)
    {
        // Guild Library: the vanilla skill books Skill<Skill>1..5, in tier order, per listed skill.
        var books = new JsonObject();
        foreach (var skill in lib["skills"]!.AsArray().Select(x => x!.GetValue<string>()))
        {
            var tiers = new JsonArray();
            for (int t = 1; t <= 5; t++)
            {
                var bedid = $"Skill{skill}{t}";
                if (itemIdx.TryGetValue(bedid, out var bk)) tiers.Add(Key(bk));
                else { Console.Error.WriteLine($"ERROR shop.json: no vanilla skill book '{bedid}'"); errors++; }
            }
            books[skill] = tiers;
        }
        lib["books"] = books;
    }
    File.WriteAllText(Path.Combine(outDir, name + ".resolved.json"), resolved!.ToJsonString(new JsonSerializerOptions { WriteIndented = true }));
    Console.WriteLine($"resolved {name}.json");
}
if (errors > 0) { Console.Error.WriteLine($"{errors} unresolved editor ID(s) - fix the config"); Environment.Exit(1); }

// ---------- plugin ----------
var modKey = ModKey.FromNameAndExtension("AdventurersGuild.esp");
var mod = new SkyrimMod(modKey, Rel);
// ESL-flagged (light plugin): no full load-order slot. Skyrim VR needs "Skyrim VR ESL Support" for this
// (standard in the big VR lists). The 2026-09-23 data-load CTD (CrashLogger, DLBR 0xFE04E808) came with
// two changes fixed at once, the DIAL SNAM=0 defect and dropping this flag; the SNAM defect is the likely
// cause, and this build re-tests the flag. Every new record must stay in the light range 0x800-0xFFF.
mod.ModHeader.Flags |= SkyrimModHeader.HeaderFlag.Small;
mod.ModHeader.Author = "urtubesrclogged";
mod.ModHeader.Description = "Adventurers Guild: guild ranks for adventurers, threat ranks for everything you fight, registration and promotion at the inn of each hold capital.";
FormKey FK(uint id)
{
    if (id < 0x800 || id > 0xFFF) { Console.Error.WriteLine($"ERROR FormID 0x{id:X} is outside the light-plugin range 0x800-0xFFF"); Environment.Exit(1); }
    return new(modKey, id);
}

// Globals kept in sync by AdventurersGuild.dll, so plain vanilla conditions (ours and other plugins',
// e.g. the Missives patch) can read guild state without a custom condition function.
GlobalShort Global(uint id, string edid, short value)
{
    var g = new GlobalShort(FK(id), Rel) { EditorID = edid, Data = value };
    mod.Globals.Add(g);
    return g;
}
var gRank = Global(0x800, "AG_PlayerRankGlobal", -1);        // guild rank 0..5, -1 = not registered
var gRegistered = Global(0x801, "AG_RegisteredGlobal", 0);
var gPromoReady = Global(0x802, "AG_PromotionReadyGlobal", 0);
// Fees shown in the player's topic text ("(<Global=AG_RegisterFee> gold)", the vanilla carriage-fare pattern)
// and required by the liaison lines; the DLL sets both from guild.json on load.
var gRegFee = Global(0x814, "AG_RegisterFee", 50);
var gPromoFee = Global(0x815, "AG_PromotionFee", 50);
// Hold stamps (1.5.0), both kept by the DLL: 1 in a hold whose stamp is on the card the player carries (merchants there charge
// less, and some say so); 1 for a member in a hold whose stamp is NOT on the card (some people hint that it is worth earning).
var gStampDiscount = Global(0xCF4, "AG_StampDiscountGlobal", 0);
var gStampWanted = Global(0xCF6, "AG_StampWantedGlobal", 0);
// MCM > Audio (1.5.0), each 1 unless the player turns it off there (the DLL sets them: Papyrus.cpp, SetAudioOption):
//   greetings     every unprompted line (guards, townsfolk, wanderers, named members, merchants on the stamp)
//   interactions  what can be asked of people who are no representative, and Show Guild Card
//   rep lines     the representatives' own replies; at 0 each answers "Of course.", the game's line, in her own voice
var gGreetings = Global(0xC88, "AG_GreetingsGlobal", 1);
var gInteractions = Global(0xC89, "AG_InteractionsGlobal", 1);
var gRepLines = Global(0xC8A, "AG_RepLinesGlobal", 1);
//   follower comments  the same unprompted lines, from someone who is following the player (asked of a player on Nexus,
//                      2026-10-14: a guild line now and then from Serana jars with Serana Dialogue Add-On's). 0xCE3: the
//                      College's development topic once, never released.
var gFollowerComments = Global(0xCE3, "AG_FollowerCommentsGlobal", 1);
// Other adventurers' guild cards (1.5.0), kept by the DLL: how many the player carries that can be brought back, and the
// weightiest case among them (what a representative says when they are handed in).
var gCardsCarried = Global(0xCF9, "AG_CardsCarriedGlobal", 0);
var gCardCase = Global(0xCFA, "AG_CardCaseGlobal", 0);
var gCardFee = Global(0x81D, "AG_CardFee", 25);            // a replacement guild card (the DLL sets it from guild.json)
// 1 while a Missives add-on is loaded (the DLL sets it on every load): dialogue that depends on its board reads it
var addonGlobals = new Dictionary<string, GlobalShort> { ["AG_MissivesSolstheimGlobal"] = Global(0xC90, "AG_MissivesSolstheimGlobal", 0) };
Global(0x81E, "AG_CardMissingGlobal", 0);                  // 1 while a member carries no card (SkyrimNet action eligibility; DLL keeps it)

// ---------- MCM quest (SkyUI / MCM Helper wiring, structure unchanged from the proven Ranks quest) ----------
var cfgFk = FK(0x803);
mod.Quests.Add(new Quest(cfgFk, Rel)
{
    EditorID = "AG_ConfigQuest",
    Name = "Adventurers Guild Config",
    Flags = Quest.Flag.StartGameEnabled,
    Priority = 50,
    // ANAM, "next alias ID": the field that introduces a quest's aliases. The game loads the quest without it, but
    // Wrye Bash requires it and failed on this plugin (KeyError b'FNAM' while building a Bashed Patch, reported
    // 2026-10-10): it only knows how to read an alias once it has seen ANAM. One alias (ID 0), so the next is 1.
    NextAliasID = 1,
    Aliases =
    {
        new QuestAlias
        {
            Name = "PlayerAlias",
            Flags = QuestAlias.Flag.Optional,
            ForcedReference = new FormLinkNullable<IPlacedGetter>(FormKey.Factory("000014:Skyrim.esm")),
        },
    },
    VirtualMachineAdapter = new QuestAdapter
    {
        Scripts = { new ScriptEntry { Name = "AG_MCM", Properties = { new ScriptStringProperty { Name = "ModName", Data = "$AG_MCM_ModName" } } } },  // SkyUI's own MCM API (no MCM Helper)
        Aliases =
        {
            new QuestFragmentAlias
            {
                Property = new ScriptObjectProperty { Name = "", Object = new FormLinkNullable<ISkyrimMajorRecordGetter>(cfgFk), Alias = 0 },
                Scripts = { new ScriptEntry { Name = "SKI_PlayerLoadGameAlias" }, new ScriptEntry { Name = "AG_SkyrimNetInit" } },
            },
        },
    },
});

// ---------- guild dialogue at every innkeeper ----------
// New top-level player topics only; the sole link to vanilla is the JobInnkeeperFaction condition,
// so no NPC, cell or vanilla dialogue record is overridden. AdventurersGuild.dll acts on the
// response through a TESTopicInfoEvent sink (no script fragments).
var dlgQuest = new Quest(FK(0x804), Rel)
{
    EditorID = "AG_GuildDialogueQuest",
    Name = "Adventurers Guild",
    Flags = Quest.Flag.StartGameEnabled,
    Priority = 50,
};
// SkyrimNet actions (external/adventurersguild.skyrimnet/actions/*.yaml) call member functions of this script on
// this quest; they hand straight to AdventurersGuild.dll, which applies the same checks as the dialogue.
dlgQuest.VirtualMachineAdapter = new QuestAdapter { Scripts = { new ScriptEntry { Name = "AG_SkyrimNetActions" } } };
dlgQuest.TextDisplayGlobals.Add(new FormLink<IGlobalGetter>(gRegFee.FormKey));
dlgQuest.TextDisplayGlobals.Add(new FormLink<IGlobalGetter>(gPromoFee.FormKey));
mod.Quests.Add(dlgQuest);

// The nine Guild reps join this hidden faction as they load (AdventurersGuild.dll), so SkyrimNet actions can pick them
// out with is_in_faction; reports waiting to be handed in, kept by the DLL for the same reason.
// active members of the player's adventuring party (the DLL adds and removes them): for dialogue conditions
var partyFaction = new Faction(FK(0x81F), Rel) { EditorID = "AG_PartyMemberFaction", Name = "Adventuring Party Member", Flags = Faction.FactionFlag.HiddenFromPC };
mod.Factions.Add(partyFaction);
// wandering adventurers (the DLL adds them as they load, at their Guild rank): for their greetings
var wandererFaction = new Faction(FK(0xC80), Rel) { EditorID = "AG_WanderingAdventurerFaction", Name = "Wandering Adventurer", Flags = Faction.FactionFlag.HiddenFromPC };
mod.Factions.Add(wandererFaction);
// a NAMED member's Guild rank (rank in the faction, kept by the DLL), and "has just been promoted" (rank 0 for a few days)
var rankFaction = new Faction(FK(0xC91), Rel) { EditorID = "AG_AdventurerRankFaction", Name = "Adventurer", Flags = Faction.FactionFlag.HiddenFromPC };
var promotedFaction = new Faction(FK(0xC92), Rel) { EditorID = "AG_AdventurerPromotedFaction", Name = "Adventurer", Flags = Faction.FactionFlag.HiddenFromPC };
mod.Factions.Add(rankFaction);
mod.Factions.Add(promotedFaction);
// Hold stamps (1.5.0), both kept by the DLL. Earned: on a liaison whose hold's stamp the player has earned (her replacement
// reply says the new card is stamped). Due: on whoever inherited an inn and its stamp, while a stamp is owed there.
var stampEarnedFaction = new Faction(FK(0xCEA), Rel) { EditorID = "AG_HoldStampEarnedFaction", Name = "Adventurers Guild Liaison", Flags = Faction.FactionFlag.HiddenFromPC };
var stampDueFaction = new Faction(FK(0xCEB), Rel) { EditorID = "AG_HoldStampDueFaction", Name = "Adventurers Guild Stamp Keeper", Flags = Faction.FactionFlag.HiddenFromPC };
mod.Factions.Add(stampEarnedFaction);
// on a dead body the DLL has looked at for a lost guild card (MemberCards): asked once, whatever the answer was
mod.Factions.Add(new Faction(FK(0xCFB), Rel) { EditorID = "AG_CardCheckedFaction", Name = "Adventurer", Flags = Faction.FactionFlag.HiddenFromPC });
mod.Factions.Add(stampDueFaction);
var liaisonFaction = new Faction(FK(0x8C6), Rel) { EditorID = "AG_GuildLiaisonFaction", Name = "Adventurers Guild Liaison", Flags = Faction.FactionFlag.HiddenFromPC };
mod.Factions.Add(liaisonFaction);
var gReports = Global(0x8C7, "AG_ReportsWaitingGlobal", 0);

ConditionFloat QuestDone(string edid, bool done)
{
    var d = new GetQuestCompletedConditionData();
    if (questIdx.TryGetValue(edid, out var qk)) d.Quest.Link.SetTo(qk);
    else { Console.Error.WriteLine($"ERROR: unknown quest editor ID '{edid}'"); errors++; }
    return new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = done ? 1 : 0, Data = d };
}

// An NPC (by base) is dead / not dead: GetDeadCount, the way vanilla asks about a unique actor.
ConditionFloat Dead(string edid, bool dead)
{
    var d = new GetDeadCountConditionData();
    d.Npc.Link.SetTo(Npc(edid));
    return new ConditionFloat { CompareOperator = dead ? CompareOperator.GreaterThanOrEqualTo : CompareOperator.EqualTo, ComparisonValue = dead ? 1 : 0, Data = d };
}
// "Plugin.esp|0x00ABCD" (the form the DLL's keys use) as a FormKey
FormKey KeyFk(string key)
{
    var bar = key.IndexOf('|');
    return new FormKey(ModKey.FromFileName(key[..bar]), Convert.ToUInt32(key[(bar + 1)..], 16));
}
// The speaker is (not) in an interior cell.
ConditionFloat InCell(FormKey cell, bool inside)
{
    var d = new GetInCellConditionData();
    d.Cell.Link.SetTo(cell);
    return new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = inside ? 1 : 0, Data = d };
}
ConditionFloat InFaction(FormKey faction)
{
    var d = new GetInFactionConditionData();
    d.Faction.Link.SetTo(faction);
    return new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = d };
}
// The player (the dialogue target) carries at least / less than the fee global's worth of gold.
ConditionGlobal Gold(GlobalShort fee, bool enough)
{
    var d = new GetItemCountConditionData { RunOnType = Condition.RunOnType.Target };
    d.ItemOrList.Link.SetTo(Skyrim.MiscItem.Gold001.FormKey);
    return new ConditionGlobal
    {
        CompareOperator = enough ? CompareOperator.GreaterThanOrEqualTo : CompareOperator.LessThan,
        ComparisonValue = new FormLink<IGlobalGetter>(fee.FormKey),
        Data = d,
    };
}
// The player (the dialogue target) carries none of an item.
ConditionFloat HasNone(FormKey item)
{
    var d = new GetItemCountConditionData { RunOnType = Condition.RunOnType.Target };
    d.ItemOrList.Link.SetTo(item);
    return new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 0, Data = d };
}
ConditionFloat GlobalIs(GlobalShort g, float v)
{
    var d = new GetGlobalValueConditionData();
    d.Global.Link.SetTo(g.FormKey);
    return new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = v, Data = d };
}

// All innkeeper dialogue comes from config/dialogue.json. INFO FormIDs are pinned in config/dialogue.ids.json
// (voice files are named after them): existing keys keep their ID, new keys get the next free ID >= 0xA00. That block ends at 0xBFF (0xC00-0xCFF is
// other records), so it continues at 0xD00; 0xFFF is the last ID a light plugin may use.
var dlgPath = Path.GetFullPath(Path.Combine(configDir, "../../../dialogue.json"));
var idsPath = Path.GetFullPath(Path.Combine(configDir, "../../../dialogue.ids.json"));
var dlg = JsonNode.Parse(File.ReadAllText(dlgPath), documentOptions: new JsonDocumentOptions { CommentHandling = JsonCommentHandling.Skip, AllowTrailingCommas = true })!;
var ids = File.Exists(idsPath)
    ? JsonSerializer.Deserialize<SortedDictionary<string, string>>(File.ReadAllText(idsPath))!
    : new SortedDictionary<string, string>();
uint nextId = Math.Max(0xA00u, ids.Values.Select(v => Convert.ToUInt32(v, 16) + 1).DefaultIfEmpty(0xA00u).Max());
uint InfoId(string key)
{
    if (!ids.TryGetValue(key, out var hex))
    {
        if (nextId is >= 0xC00 and < 0xD00) nextId = 0xD00;
        if (nextId > 0xFFF) { Console.Error.WriteLine($"ERROR dialogue: no FormIDs left for '{key}' (0xA00-0xBFF and 0xD00-0xFFF are full)"); Environment.Exit(1); }
        hex = $"0x{nextId++:X3}"; ids[key] = hex;
    }
    return Convert.ToUInt32(hex, 16);
}
FormKey Npc(string edid)
{
    if (idx["npcs"].TryGetValue(edid, out var fk)) return fk;
    Console.Error.WriteLine($"ERROR dialogue.json: unknown NPC editor ID '{edid}'");
    Environment.Exit(1);
    return default;
}
ConditionFloat IsNpc(FormKey npc, bool or)
{
    var d = new GetIsIDConditionData();
    d.Object.Link.SetTo(npc);
    var c = new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = d };
    if (or) c.Flags |= Condition.Flag.OR;
    return c;
}
// The representatives' lines switched off (MCM > Audio, AG_RepLinesGlobal 0): she still has to answer, because the plugin
// acts as her reply starts and a choice with no worded reply is not offered at all. So every reply that does something
// has a twin that says the game's own "Of course." (Skyrim.esm 0x0DBA22, a line of DialogueGenericSharedInfo: made to
// be borrowed, the way vanilla's bounty quests borrow their lines, and recorded in 42 voices, every representative's
// and successor's among them). The twin has no words of its own: it names that line as its response data, so the
// words, the subtitle and the recording are the game's. Lines that only inform ("you cannot afford it", a referral
// to the hold's counter, the answer to "what is the Guild?") have no twin: with the lines off, those choices are gone.
var ofCourse = new FormKey(Skyrim.ModKey, 0x0DBA22);
DialogResponses ShortReply(string key, bool goodbye, IEnumerable<Condition> conds)
{
    var info = new DialogResponses(FK(InfoId(key)), Rel)
    {
        EditorID = "AG_Info_" + key.Replace(":", "_"),
        Flags = new DialogResponseFlags { Flags = goodbye ? DialogResponses.Flag.Goodbye : 0 },
        ResponseData = new FormLinkNullable<IDialogResponsesGetter>(ofCourse),
    };
    info.Conditions.Add(GlobalIs(gRepLines, 0));
    foreach (var c in conds) info.Conditions.Add(c);
    return info;
}
// the twins go before every line of the topic (the first reply whose conditions pass is the one said), in order
void PutFirst(DialogTopic t, List<DialogResponses> shorts)
{
    if (shorts.Count == 0) return;
    t.Responses.InsertRange(0, shorts);
    for (var i = 0; i < t.Responses.Count; i++)
        t.Responses[i].PreviousDialog = i == 0 ? new FormLinkNullable<IDialogResponsesGetter>() : new FormLinkNullable<IDialogResponsesGetter>(t.Responses[i - 1].FormKey);
}
var roles = new Dictionary<string, List<string>> { ["register"] = new(), ["promote"] = new(), ["business"] = new(), ["replace"] = new(), ["stamp"] = new(), ["cardhandin"] = new() };
var liaisonKeys = new List<string>();
var prompts = dlg["prompts"]!;

// One topic: every INFO, in evaluation order (liaison lines first, catch-all last), chained through PNAM.
// A fee (register, promote) turns one topic into a small exchange, all in one branch:
//   player: "<prompt>"            liaison: "<role>:ask" (there's a fee, will you pay?) -> choices below
//     player: "<payPrompt> (<Global=fee> gold)"   liaison line (the per-NPC "<role>:<npc>", DLL acts on it) if
//                                                 the player has the gold, else "<role>:nofee"
//     player: "Not now."                          liaison: "<role>:later", back to the topic list
// Liaison INFO FormIDs never change; the pay topic's editor ID truncates to the same 15 characters as the old
// single topic's (voice file names use it), so the existing voiced lines still match.
// payNow (the replacement guild card): the fee is in the player's own line, so there is no ask and no second choice.
// The liaison line (DLL acts on it) plays if the player has the gold, else "<role>:nofee", both in the one topic.
void MakeTopic(uint branchId, uint topicId, string stem, string role, bool goodbyeForLiaison, ConditionFloat[] state, bool referrals,
               GlobalShort? fee = null, uint payTopicId = 0, uint laterTopicId = 0, bool payNow = false)
{
    var branch = new DialogBranch(FK(branchId), Rel)
    {
        EditorID = $"AG_Branch{stem}",
        Quest = new FormLink<IQuestGetter>(dlgQuest.FormKey),
        Category = DialogBranch.CategoryType.Player,
        Flags = DialogBranch.Flag.TopLevel,
        StartingTopic = new FormLinkNullable<IDialogTopicGetter>(FK(topicId)),
    };
    mod.DialogBranches.Add(branch);
    DialogTopic NewTopic(uint id, string edid, string text) => new DialogTopic(FK(id), Rel)
    {
        EditorID = edid,
        Name = text,
        Priority = 50,
        Branch = new FormLinkNullable<IDialogBranchGetter>(branch.FormKey),
        Quest = new FormLinkNullable<IQuestGetter>(dlgQuest.FormKey),
        Category = DialogTopic.CategoryEnum.Topic,
        Subtype = DialogTopic.SubtypeEnum.Custom,
        SubtypeName = new RecordType("CUST"),  // Mutagen writes 0 unless set; every working topic has CUST
    };
    var topic = NewTopic(topicId, $"AG_Topic{stem}", prompts[role]!.GetValue<string>());
    var prevOf = new Dictionary<DialogTopic, DialogResponses>();
    var shorts = new Dictionary<DialogTopic, List<DialogResponses>>();
    DialogResponses Short(DialogTopic t, string key, bool goodbye, IEnumerable<Condition> who, bool acts)
    {
        var info = ShortReply(key, goodbye, who.Concat(state));
        if (!shorts.TryGetValue(t, out var list)) shorts[t] = list = new();
        list.Add(info);
        if (acts && roles.ContainsKey(role)) roles[role].Add(ids[key]);
        return info;
    }
    // conditions that make a successor (Ysolda after Hulda) this liaison: in the DLL's faction, and at her inn
    List<Condition> Succeeded(JsonNode l)
    {
        var c = new List<Condition>();
        if (l["successor"] is not JsonNode su) return c;
        c.Add(InFaction(liaisonFaction.FormKey));
        if (su["cell"] is JsonNode cell) c.Add(InCell(KeyFk(cell.GetValue<string>()), true));
        return c;
    }
    DialogResponses Info(DialogTopic t, string key, string[] lines, bool goodbye, IEnumerable<Condition> who)
    {
        var info = new DialogResponses(FK(InfoId(key)), Rel)
        {
            EditorID = "AG_Info_" + key.Replace(":", "_"),
            Flags = new DialogResponseFlags { Flags = goodbye ? DialogResponses.Flag.Goodbye : 0 },
        };
        byte n = 1;
        foreach (var line in lines) info.Responses.Add(new DialogResponse { Text = line, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = n++ });
        info.Conditions.Add(GlobalIs(gRepLines, 1));  // first, so it is ANDed with everything after it, OR groups included
        foreach (var c in who) info.Conditions.Add(c);
        foreach (var c in state) info.Conditions.Add(c);
        if (prevOf.TryGetValue(t, out var prev)) info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(prev.FormKey);
        t.Responses.Add(info);
        prevOf[t] = info;
        return info;
    }
    List<Condition> AnyLiaison()
    {
        var ls = dlg["liaisons"]!.AsArray().Where(x => x!["successor"] is null).Select(x => Npc(x!["npc"]!.GetValue<string>())).ToList();
        var any = ls.Select(fk => (Condition)IsNpc(fk, true)).ToList();
        any.Add(InFaction(liaisonFaction.FormKey));  // ... OR a successor: the DLL adds them to the faction when they take the inn over
        return any;
    }
    string Line(string section) => dlg[section]![role]!.GetValue<string>();

    // A successor away from her inn says so, on every topic that does business (first, so nothing else answers for her)
    if (role != "about")
        foreach (var l in dlg["liaisons"]!.AsArray())
            if (l!["successor"] is JsonNode su && su["cell"] is JsonNode cell && l["away"] is JsonNode away)
                Info(topic, $"{role}:away:{l["npc"]!.GetValue<string>()}", new[] { away.GetValue<string>() }, false,
                    new Condition[] { IsNpc(Npc(l["npc"]!.GetValue<string>()), false), InFaction(liaisonFaction.FormKey), InCell(KeyFk(cell.GetValue<string>()), false) });
    // the per-liaison lines: in the pay topic when there's a fee, else straight in the topic
    DialogTopic? pay = null, later = null;
    if (fee is not null && !payNow)
    {
        pay = NewTopic(payTopicId, $"AG_Topic{stem}Pay", prompts[$"{role}Pay"]!.GetValue<string>());
        later = NewTopic(laterTopicId, $"AG_Topic{stem}Later", prompts["later"]!.GetValue<string>());
        // a liaison's own "<role>Ask" line (e.g. checks the ledger, congratulates, then names the fee) comes first;
        // the shared ask line covers any liaison without one
        var asks = new List<DialogResponses>();
        foreach (var l in dlg["liaisons"]!.AsArray())
        {
            if (l![$"{role}Ask"] is not JsonNode own) continue;
            var npc = l["npc"]!.GetValue<string>();
            var askWho = new List<Condition> { IsNpc(Npc(npc), false) };
            askWho.AddRange(Succeeded(l));
            asks.Add(Info(topic, $"{role}:ask:{npc}", new[] { own.GetValue<string>() }, false, askWho));
        }
        asks.Add(Info(topic, $"{role}:ask", new[] { Line("ask") }, false, AnyLiaison()));
        asks.Add(Short(topic, $"{role}:ask:short", false, AnyLiaison(), false));
        foreach (var ask in asks)
        {
            ask.LinkTo.Add(new FormLink<IDialogTopicGetter>(pay.FormKey));
            ask.LinkTo.Add(new FormLink<IDialogTopicGetter>(later.FormKey));
        }
    }
    var liaisonTopic = pay ?? topic;
    foreach (var l in dlg["liaisons"]!.AsArray())
    {
        var npc = l!["npc"]!.GetValue<string>();
        var node = l[role]!;
        var lines = node is JsonArray arr ? arr.Select(x => x!.GetValue<string>()).ToArray() : new[] { node.GetValue<string>() };
        var key = $"{role}:{npc}";
        List<Condition> Who()
        {
            var w = new List<Condition> { IsNpc(Npc(npc), false) };
            w.AddRange(Succeeded(l));  // only once they keep the counter, and only at their inn
            if (fee is not null) w.Add(Gold(fee, true));
            return w;
        }
        DialogResponses Add(string k, string[] ls, IEnumerable<Condition> extra)
        {
            var w = Who();
            w.AddRange(extra);
            var info = Info(liaisonTopic, k, ls, goodbyeForLiaison, w);
            if (roles.ContainsKey(role)) roles[role].Add(ids[k]);
            // SkyrimNet only offers its AI a dialogue line as an action ("Actions <npc> can take", fired through
            // TriggerDialogueLine) when the INFO has a script fragment that does something. This one opens the counter,
            // so "I have guild business" in an AI conversation plays our real line. In the vanilla menu the
            // TESTopicInfoEvent sink opens it as well; Counter::OpenAfterDialogue is a single pending flag, so it opens once.
            if (role == "business")
                info.VirtualMachineAdapter = new DialogResponsesAdapter
                {
                    ScriptFragments = new ScriptFragments
                    {
                        FileName = "AG_TIF_GuildBusiness",
                        OnEnd = new ScriptFragment { ScriptName = "AG_TIF_GuildBusiness", FragmentName = "Fragment_0" },
                    },
                };
            // A rep's business lines are one RANDOM group (as the world greetings are): the engine picks among the
            // INFOs of the group whose conditions pass. So each line carries its full conditions and none relies on
            // its place in the stack: the rank's own line, the plain line (only at ranks with no line of their own),
            // and the extras ("businessExtra", any rank; "businessByRankExtra", that rank only).
            if (role == "business") info.Flags = new DialogResponseFlags { Flags = (info.Flags?.Flags ?? 0) | DialogResponses.Flag.Random };
            return info;
        }
        // the plain business line (and what replaces it) is not said at a rank that has its own line
        var plain = new List<Condition>();
        if (role == "business" && l["businessByRank"] is JsonObject ranked)
            foreach (var r in new[] { "S", "A", "B", "C" })
                if (ranked[r] is not null) plain.Add(GlobalCmp(gRank, CompareOperator.NotEqualTo, "EDCBAS".IndexOf(r)));
        var basePlain = new List<Condition>(plain);
        // the player's rank picks the line (highest first; the plain line is E-D)
        if (role == "business" && l["businessByRank"] is JsonObject byRank)
            foreach (var r in new[] { "S", "A", "B", "C" })
            {
                if (byRank[r] is JsonNode t)
                    Add($"{key}:{r}", new[] { t.GetValue<string>() }, new Condition[] { GlobalCmp(gRank, CompareOperator.EqualTo, "EDCBAS".IndexOf(r)) });
                if (l["businessByRankExtra"] is JsonObject more && more[r] is JsonNode t2)
                    Add($"{key}:{r}:2", new[] { t2.GetValue<string>() }, new Condition[] { GlobalCmp(gRank, CompareOperator.EqualTo, "EDCBAS".IndexOf(r)) });
            }
        if (role == "business" && l["businessExtra"] is JsonArray extras)
            for (var n = 0; n < extras.Count; n++)
                Add($"{key}:x{n + 1}", new[] { extras[n]!.GetValue<string>() }, Array.Empty<Condition>());
        // a vanilla quest's completion changes what they say (Thoring and Waking Nightmare)
        if (l["afterQuest"] is JsonObject after && after[role] is JsonNode an)
        {
            var als = an is JsonArray aa ? aa.Select(x => x!.GetValue<string>()).ToArray() : new[] { an.GetValue<string>() };
            Add($"{key}:after", als, role == "business" ? plain.Append(QuestDone(after["quest"]!.GetValue<string>(), true)) : new Condition[] { QuestDone(after["quest"]!.GetValue<string>(), true) });
            if (role == "business") basePlain.Add(QuestDone(after["quest"]!.GetValue<string>(), false));
        }
        // a global the DLL keeps changes what they say (Geldis Sadri, once Raven Rock has a missive board)
        if (l["whenGlobal"] is JsonObject wg && wg[role] is JsonNode wn)
        {
            var wls = wn is JsonArray wa ? wa.Select(x => x!.GetValue<string>()).ToArray() : new[] { wn.GetValue<string>() };
            Add($"{key}:when", wls, role == "business" ? plain.Append(GlobalIs(addonGlobals[wg["global"]!.GetValue<string>()], 1)) : new Condition[] { GlobalIs(addonGlobals[wg["global"]!.GetValue<string>()], 1) });
            if (role == "business") basePlain.Add(GlobalIs(addonGlobals[wg["global"]!.GetValue<string>()], 0));
        }
        // the hold's stamp is earned: the new card is stamped at once, and she says so (GuildCard::Replace does it)
        if (role == "replace" && l["replaceStamped"] is JsonNode rs)
            Add($"{key}:stamped", new[] { rs.GetValue<string>() }, new Condition[] { InFaction(stampEarnedFaction.FormKey) });
        var last = Add(key, lines, role == "business" ? basePlain : Array.Empty<Condition>());
        if (role != "about") Short(liaisonTopic, $"{key}:short", goodbyeForLiaison, Who(), true);
        if (role == "business") last.Flags!.Flags |= DialogResponses.Flag.RandomEnd;   // the next rep's lines are their own group
    }
    if (fee is not null)
    {
        var poor = AnyLiaison();
        poor.Add(Gold(fee, false));
        Info(pay ?? topic, $"{role}:nofee", new[] { Line("nofee") }, false, poor);
        if (later is not null)
        {
            Info(later, $"{role}:later", new[] { Line("later") }, false, AnyLiaison());
            Short(later, $"{role}:later:short", false, AnyLiaison(), false);
        }
    }
    if (referrals)
    {
        void Group(string kind, JsonNode g)
        {
            var npcs = g["npcs"]!.AsArray().Select(x => Npc(x!.GetValue<string>())).ToList();
            var conds = npcs.Select((fk, i) => (Condition)IsNpc(fk, i < npcs.Count - 1)).ToList();  // A OR B OR C, then AND state
            if (g["whileAlive"] is JsonNode wa) conds.Add(Dead(wa.GetValue<string>(), false));
            if (g["whenDead"] is JsonNode wd) conds.Add(Dead(wd.GetValue<string>(), true));
            if (g["unlessInFaction"] is JsonNode uf)  // asked of another reference, not of the speaker
            {
                var fd = new GetInFactionConditionData { RunOnType = Condition.RunOnType.Reference };
                fd.Reference.SetTo(KeyFk(uf["ref"]!.GetValue<string>()));
                fd.Faction.Link.SetTo(idx["factions"][uf["faction"]!.GetValue<string>()]);
                conds.Add(new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 0, Data = fd });
            }
            // a second line for the same people (after their innkeeper's death) needs its own key
            var gk = $"{role}:{kind}:{g["npcs"]![0]!.GetValue<string>()}" + (g["whenDead"] is JsonNode dd ? ":after" + dd.GetValue<string>() : "");
            Info(topic, gk, new[] { g["line"]!.GetValue<string>() }, false, conds);
        }
        foreach (var g in dlg["staff"]!.AsArray()) Group("staff", g!);
        foreach (var g in dlg["referrals"]!.AsArray()) Group("ref", g!);
        // Any other innkeeper, other mods' included - but not one who is travelling with the player: follower mods put
        // tavern staff in JobInnkeeperFaction (Immersive Wenches), and a follower is no innkeeper while she follows.
        var notFollowing = InFaction(Skyrim.Faction.CurrentFollowerFaction.FormKey);   // in it = rank 0 and up; dismissed is rank -1
        notFollowing.ComparisonValue = 0;
        Info(topic, $"{role}:generic", new[] { dlg["generic"]!.GetValue<string>() }, false, new Condition[] {
            InFaction(Skyrim.Faction.JobInnkeeperFaction.FormKey),
            new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 0, Data = new GetPlayerTeammateConditionData() },
            notFollowing });
    }
    foreach (var (t, list) in shorts) PutFirst(t, list);
    mod.DialogTopics.Add(topic);
    if (pay is not null) mod.DialogTopics.Add(pay);
    if (later is not null) mod.DialogTopics.Add(later);
}
var liaisonCities = new Dictionary<string, string>();
var successors = new List<object>();
var stampKeepers = new List<object>();  // hold stamps: who keeps a dead liaison's stamp
var cardNoDrinks = new List<string>();  // returned cards: the representatives who stand nobody a round
var choiceSwaps = new List<object>();   // Show Guild Card: the vanilla choice, and the topic of ours offered in its place
foreach (var l in dlg["liaisons"]!.AsArray())
{
    var k = Key(Npc(l!["npc"]!.GetValue<string>()));
    if (l["successor"] is JsonNode su)
    {
        successors.Add(new { npc = k, of = Key(Npc(su["of"]!.GetValue<string>())), quest = su["quest"]!.GetValue<string>(), alias = su["alias"]!.GetValue<int>(),
            @ref = su["ref"]?.GetValue<string>() ?? "", cell = su["cell"]?.GetValue<string>() ?? "", city = l["city"]!.GetValue<string>() });
        continue;
    }
    liaisonKeys.Add(k);
    liaisonCities[k] = l["city"]!.GetValue<string>();
}
MakeTopic(0x805, 0x806, "Register", "register", true, new[] { GlobalIs(gRegistered, 0) }, true, gRegFee, 0x816, 0x817);
MakeTopic(0x808, 0x809, "Promote", "promote", true, new[] { GlobalIs(gRegistered, 1), GlobalIs(gPromoReady, 1) }, true, gPromoFee, 0x818, 0x819);
MakeTopic(0x80B, 0x80C, "Business", "business", true, new[] { GlobalIs(gRegistered, 1) }, true);
MakeTopic(0x812, 0x813, "About", "about", false, Array.Empty<ConditionFloat>(), false);
// A lost guild card: only offered to a member who carries none, and the choice itself pays (no confirmation).
// The DLL writes the fee into the player's line (Guild.cpp): a <Global=> tag added to a quest that is already
// running in a save shows as "[...]".
MakeTopic(0x81B, 0x81C, "Replace", "replace", false, new[] { GlobalIs(gRegistered, 1), HasNone(FK(0x81A)) }, false, gCardFee, payNow: true);

// ---------- world awareness: greetings from named NPCs and guards (config/world_dialogue.json) ----------
// One Hello topic in its own quest, the pattern proven by Bandit Lines Expansion: priority-50 start-game quest,
// Random-flagged INFOs gated by GetRandomPercent (so they mix with vanilla greetings instead of replacing them),
// guard lines gated by GetIsVoiceType on the voice types that have voice files. No vanilla record is touched.
var gRecentPromo = Global(0x8C5, "AG_RecentPromotionGlobal", -1);   // the rank just reached (a few days), else -1
var retiredFaction = new Faction(FK(0x8C4), Rel)
{
    EditorID = "AG_RetiredAdventurerFaction",
    Name = "Retired Adventurer",
    Flags = Faction.FactionFlag.HiddenFromPC,
};
mod.Factions.Add(retiredFaction);
var worldQuest = new Quest(FK(0x8C0), Rel)
{
    EditorID = "AG_WorldDialogueQuest",
    Name = "Adventurers Guild World Dialogue",
    Flags = Quest.Flag.StartGameEnabled,
    Priority = 50,
};
mod.Quests.Add(worldQuest);
var hello = new DialogTopic(FK(0x8C1), Rel)
{
    EditorID = "AG_WorldHello",
    Priority = 50,
    Quest = new FormLinkNullable<IQuestGetter>(worldQuest.FormKey),
    Category = DialogTopic.CategoryEnum.Misc,
    Subtype = DialogTopic.SubtypeEnum.Hello,
    SubtypeName = new RecordType("HELO"),
};
var worldPath = Path.GetFullPath(Path.Combine(configDir, "../../../world_dialogue.json"));
var world = JsonNode.Parse(File.ReadAllText(worldPath), documentOptions: new JsonDocumentOptions { CommentHandling = JsonCommentHandling.Skip, AllowTrailingCommas = true })!;
FormKey FactionFk(string edid)
{
    if (idx["factions"].TryGetValue(edid, out var fk)) return fk;
    Console.Error.WriteLine($"ERROR world_dialogue.json: unknown faction '{edid}'"); errors++;
    return default;
}
List<Condition> VoiceGroup(string listKey)
{
    var names = world[listKey]!.AsArray().Select(x => x!.GetValue<string>()).ToList();
    var conds = new List<Condition>();
    for (int i = 0; i < names.Count; i++)
    {
        if (!voiceIdx.TryGetValue(names[i], out var vfk)) { Console.Error.WriteLine($"ERROR world_dialogue.json: unknown voice type '{names[i]}'"); errors++; continue; }
        var d = new GetIsVoiceTypeConditionData();
        d.VoiceTypeOrList.Link.SetTo(vfk);
        var c = new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = d };
        if (i < names.Count - 1) c.Flags |= Condition.Flag.OR;
        conds.Add(c);
    }
    return conds;
}
ConditionFloat GlobalCmp(GlobalShort g, CompareOperator op, float v)
{
    var d = new GetGlobalValueConditionData();
    d.Global.Link.SetTo(g.FormKey);
    return new ConditionFloat { CompareOperator = op, ComparisonValue = v, Data = d };
}
ConditionFloat Chance(int pct) => new() { CompareOperator = CompareOperator.LessThanOrEqualTo, ComparisonValue = pct, Data = new GetRandomPercentConditionData() };
// "E" exact, "B+" at or above, "<B" below (registered only), "E-C" inclusive range
IEnumerable<Condition> RankConds(string spec)
{
    int R(string l) { var r = "EDCBAS".IndexOf(l.Trim().ToUpperInvariant()); if (r < 0) { Console.Error.WriteLine($"ERROR world_dialogue.json: bad rank '{spec}'"); errors++; } return r; }
    if (spec.EndsWith("+")) yield return GlobalCmp(gRank, CompareOperator.GreaterThanOrEqualTo, R(spec[..^1]));
    else if (spec.StartsWith("<")) { yield return GlobalCmp(gRank, CompareOperator.GreaterThanOrEqualTo, 0); yield return GlobalCmp(gRank, CompareOperator.LessThan, R(spec[1..])); }
    else if (spec.Contains('-')) { var p = spec.Split('-'); yield return GlobalCmp(gRank, CompareOperator.GreaterThanOrEqualTo, R(p[0])); yield return GlobalCmp(gRank, CompareOperator.LessThanOrEqualTo, R(p[1])); }
    else yield return GlobalCmp(gRank, CompareOperator.EqualTo, R(spec));
}
// the SPEAKER's own Guild rank (a named member: their rank in AG_AdventurerRankFaction), same notation as the player's
ConditionFloat OwnRankCmp(CompareOperator op, float v)
{
    var d = new GetFactionRankConditionData();
    d.Faction.Link.SetTo(rankFaction.FormKey);
    return new ConditionFloat { CompareOperator = op, ComparisonValue = v, Data = d };
}
IEnumerable<Condition> OwnRankConds(string spec)
{
    int R(string l) { var r = "EDCBAS".IndexOf(l.Trim().ToUpperInvariant()); if (r < 0) { Console.Error.WriteLine($"ERROR world_dialogue.json: bad ownRank '{spec}'"); errors++; } return r; }
    if (spec.EndsWith("+")) yield return OwnRankCmp(CompareOperator.GreaterThanOrEqualTo, R(spec[..^1]));
    else if (spec.StartsWith("<")) { yield return OwnRankCmp(CompareOperator.GreaterThanOrEqualTo, 0); yield return OwnRankCmp(CompareOperator.LessThan, R(spec[1..])); }
    else if (spec.Contains('-')) { var p = spec.Split('-'); yield return OwnRankCmp(CompareOperator.GreaterThanOrEqualTo, R(p[0])); yield return OwnRankCmp(CompareOperator.LessThanOrEqualTo, R(p[1])); }
    else yield return OwnRankCmp(CompareOperator.EqualTo, R(spec));
}
var worldTopics = new Dictionary<string, DialogTopic>();
var chance = world["chance"]!;
var holdGuards = world["holdGuards"]!.AsObject();
var worldCount = 0;
DialogBranch? ysoldaBranch = null;
foreach (var ln in world["lines"]!.AsArray())
{
    var id = ln!["id"]!.GetValue<string>();
    var text = ln["text"]!.GetValue<string>();
    var conds = new List<Condition>();
    var voices = new List<Condition>();
    string kind;
    if (ln["who"] is JsonNode who)
    {
        conds.Add(IsNpc(Npc(who.GetValue<string>()), false)); kind = "npc";
        if (ln["ownRank"] is JsonNode orank) conds.AddRange(OwnRankConds(orank.GetValue<string>()));
        if (ln["ownPromoted"] is not null) conds.Add(new ConditionFloat { CompareOperator = CompareOperator.GreaterThanOrEqualTo, ComparisonValue = 0, Data = new GetFactionRankConditionData { Faction = { Link = { FormKey = promotedFaction.FormKey } } } });
        // their rank against the player's
        if (ln["theirRank"] is JsonNode ntr)
        {
            var fr = new GetFactionRankConditionData();
            fr.Faction.Link.SetTo(rankFaction.FormKey);
            conds.Add(OwnRankCmp(CompareOperator.GreaterThanOrEqualTo, 0));
            conds.Add(new ConditionGlobal
            {
                CompareOperator = ntr.GetValue<string>() switch { "above" => CompareOperator.GreaterThan, "below" => CompareOperator.LessThan, _ => CompareOperator.EqualTo },
                ComparisonValue = new FormLink<IGlobalGetter>(gRank.FormKey), Data = fr,
            });
        }
    }
    else if (ln["wanderers"] is not null)
    {
        conds.Add(InFaction(wandererFaction.FormKey)); kind = "wanderer"; voices = VoiceGroup("wandererVoices");
        // the speaker's Guild rank (their rank in the faction) against the player's
        if (ln["theirRank"] is JsonNode tr)
        {
            var fr = new GetFactionRankConditionData();
            fr.Faction.Link.SetTo(wandererFaction.FormKey);
            conds.Add(new ConditionGlobal
            {
                CompareOperator = tr.GetValue<string>() switch { "above" => CompareOperator.GreaterThan, "below" => CompareOperator.LessThan, _ => CompareOperator.EqualTo },
                ComparisonValue = new FormLink<IGlobalGetter>(gRank.FormKey), Data = fr,
            });
        }
    }
    else
    {
        var g = ln["guards"]!.GetValue<string>();
        if (g == "retired") { conds.Add(InFaction(retiredFaction.FormKey)); kind = "retired"; voices = VoiceGroup("guardVoices"); }
        else if (g == "any") { conds.Add(InFaction(Skyrim.Faction.GuardDialogueFaction.FormKey)); kind = "guards"; voices = VoiceGroup("guardVoices"); }
        else if (g == "Solstheim") { conds.Add(InFaction(FactionFk(holdGuards["Solstheim"]!.GetValue<string>()))); kind = "guards"; voices = VoiceGroup("solstheimGuardVoices"); }
        else
        {
            conds.Add(InFaction(Skyrim.Faction.GuardDialogueFaction.FormKey));
            conds.Add(InFaction(FactionFk(holdGuards[g]!.GetValue<string>())));
            kind = "guards"; voices = VoiceGroup("guardVoices");
        }
    }
    if (ln["promoted"] is JsonNode pr) { conds.Add(GlobalCmp(gRecentPromo, CompareOperator.EqualTo, "EDCBAS".IndexOf(pr.GetValue<string>()))); kind = "promoted"; }
    if (ln["questDone"] is JsonNode qd) conds.Add(QuestDone(qd.GetValue<string>(), true));
    if (ln["questNotDone"] is JsonNode qn) conds.Add(QuestDone(qn.GetValue<string>(), false));
    if (ln["whileAlive"] is JsonNode wal) conds.Add(Dead(wal.GetValue<string>(), false));
    if (ln["whenDead"] is JsonNode wdd) conds.Add(Dead(wdd.GetValue<string>(), true));
    if (ln["liaison"] is not null) conds.Add(InFaction(liaisonFaction.FormKey));
    if (ln["inParty"] is JsonNode ip) { var pc = InFaction(partyFaction.FormKey); pc.ComparisonValue = ip.GetValue<bool>() ? 1 : 0; conds.Add(pc); }
    if (ln["teammate"] is JsonNode tm)
        conds.Add(new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = tm.GetValue<bool>() ? 1 : 0, Data = new GetPlayerTeammateConditionData() });
    if (ln["inFaction"] is JsonNode inf) conds.Add(InFaction(FactionFk(inf.GetValue<string>())));
    if (ln["notInFaction"] is JsonNode nif) { var nc = InFaction(FactionFk(nif.GetValue<string>())); nc.ComparisonValue = 0; conds.Add(nc); }
    // who holds Whiterun: the condition vanilla puts on Sinmir's own lines (CWOwner 2 = the Stormcloaks)
    if (ln["owner"] is JsonNode ow)
    {
        var od = new GetKeywordDataForLocationConditionData();
        od.Location.Link.SetTo(Skyrim.Location.WhiterunLocation.FormKey);
        od.Keyword.Link.SetTo(Skyrim.Keyword.CWOwner.FormKey);
        conds.Add(new ConditionFloat { CompareOperator = ow.GetValue<string>() == "sons" ? CompareOperator.EqualTo : CompareOperator.NotEqualTo, ComparisonValue = 2, Data = od });
    }
    if (ln["stamp"] is JsonNode st) conds.Add(GlobalIs(st.GetValue<string>() == "here" ? gStampDiscount : gStampWanted, 1));
    var status = ln["status"]?.GetValue<string>() ?? "registered";
    if (status != "any") conds.Add(GlobalIs(gRegistered, status == "unregistered" ? 0 : 1));  // "any": registered or not
    if (ln["rank"] is JsonNode rk) conds.AddRange(RankConds(rk.GetValue<string>()));

    if (ln["topic"] is JsonNode prompt)  // a player topic (Ysolda's), not a greeting
    {
        conds.Insert(0, GlobalIs(gInteractions, 1));  // MCM > Audio > NPC interactions
        // one player topic per NPC: branch and topic FormIDs are fixed here (append only)
        var whoId = ln["who"]!.GetValue<string>();
        var (branchId, topicId) = whoId switch { "Ysolda" => (0x8C2u, 0x8C3u), "Sinmir" => (0x8C8u, 0x8C9u), "Uthgerd" => (0x8CAu, 0x8CBu),
            "Mjoll" => (0x8CCu, 0x8CDu), "Annekke" => (0x8CEu, 0x8CFu), "DLC2RRTeldrynSero" => (0xC93u, 0xC94u), _ => (0u, 0u) };
        if (branchId == 0) { Console.Error.WriteLine($"ERROR world_dialogue.json: no topic FormIDs assigned for '{whoId}' (tools/EspGen/Program.cs)"); errors++; continue; }
        // a second answer to the same question (by the speaker's own rank): another INFO in the topic that is already
        // there. Order in the file is the order they are tried in, so the conditioned ones go first.
        if (worldTopics.TryGetValue(whoId, out var have))
        {
            var more = new DialogResponses(FK(InfoId("world:" + id)), Rel) { EditorID = "AG_Info_world_" + id };
            more.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
            foreach (var c in conds) more.Conditions.Add(c);
            more.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(have.Responses[^1].FormKey);
            have.Responses.Add(more);
            worldCount++;
            continue;
        }
        ysoldaBranch = new DialogBranch(FK(branchId), Rel)
        {
            EditorID = "AG_BranchWorld" + whoId,
            Quest = new FormLink<IQuestGetter>(worldQuest.FormKey),
            Category = DialogBranch.CategoryType.Player,
            Flags = DialogBranch.Flag.TopLevel,
            StartingTopic = new FormLinkNullable<IDialogTopicGetter>(FK(topicId)),
        };
        var t = new DialogTopic(FK(topicId), Rel)
        {
            EditorID = "AG_TopicWorld" + whoId,
            Name = prompt.GetValue<string>(),
            Priority = 50,
            Branch = new FormLinkNullable<IDialogBranchGetter>(ysoldaBranch.FormKey),
            Quest = new FormLinkNullable<IQuestGetter>(worldQuest.FormKey),
            Category = DialogTopic.CategoryEnum.Topic,
            Subtype = DialogTopic.SubtypeEnum.Custom,
            SubtypeName = new RecordType("CUST"),
        };
        var ti = new DialogResponses(FK(InfoId("world:" + id)), Rel) { EditorID = "AG_Info_world_" + id };
        ti.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
        foreach (var c in conds) ti.Conditions.Add(c);
        t.Responses.Add(ti);
        mod.DialogBranches.Add(ysoldaBranch);
        mod.DialogTopics.Add(t);
        worldTopics[whoId] = t;
        worldCount++;
        continue;
    }
    conds.Insert(0, GlobalIs(gGreetings, 1));  // MCM > Audio > NPC greetings
    // MCM > Audio > Follower comments: on, OR the speaker is not following the player. Whoever it is - a housecarl, Serana,
    // another mod's follower - goes by whether they follow now, not by name. Two items ORed, between ANDed ones.
    {
        var on = GlobalIs(gFollowerComments, 1);
        on.Flags |= Condition.Flag.OR;
        conds.Insert(1, on);
        conds.Insert(2, new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 0, Data = new GetPlayerTeammateConditionData() });
    }
    conds.Add(Chance(ln["chance"]?.GetValue<int>() ?? chance[kind]!.GetValue<int>()));
    conds.AddRange(voices);  // the OR group last, so it stands alone
    var info = new DialogResponses(FK(InfoId("world:" + id)), Rel)
    {
        EditorID = "AG_Info_world_" + id,
        Flags = new DialogResponseFlags { Flags = DialogResponses.Flag.Random, ResetHours = ln["restHours"] is JsonNode rest ? rest.GetValue<float>() : kind == "npc" ? 24f : kind == "wanderer" ? 0f : 6f },  // wanderers: no rest. Two or three lines per case, shared by every adventurer on the road: with a rest the first one met used them up (measured: 3 Guild lines in 48 greetings). The chance mixes them with the game's own instead
    };
    info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
    foreach (var c in conds) info.Conditions.Add(c);
    hello.Responses.Add(info);
    worldCount++;
}
mod.DialogTopics.Add(hello);

// ---------- Show Guild Card (1.5.0) ----------
// Where vanilla makes the player talk their way past someone, a member carrying the card can show it instead. No
// vanilla line is overridden. Wherever vanilla has a "(Persuade)" (or, for the robber, "(Intimidate)") choice, the card
// takes that choice over, by a reply ADDED to its topic (see below). The Orc strongholds have no such choice, so there
// the card takes over one of the gate guard's first-meeting choices and ALSO has a topic of its own in his menu, for a
// member who first came by below the rank it needs.
// The effect is always what vanilla's own success does: Faralda goes on into her vanilla "you're in" line; Rhiada's
// line sets MS01 to stage 50 (TIF__000D66BA); the orcs take the player into OrcFriendFaction (QF_FavorOrcsIntro,
// QF_RelationshipOrcs), which is all that Blood-Kin is to the game; the gates and the robber set their quest's stage.
{
    var sc = dlg["showCard"]!;
    var cardFk = FK(0x81A);
    FormKey Vanilla(uint id) => new FormKey(Skyrim.ModKey, id);
    Condition OnPlayer(ConditionFloat c) { c.Data.RunOnType = Condition.RunOnType.Target; return c; }
    ConditionFloat HasCard()
    {
        var d = new GetItemCountConditionData { RunOnType = Condition.RunOnType.Target };
        d.ItemOrList.Link.SetTo(cardFk);
        return new ConditionFloat { CompareOperator = CompareOperator.GreaterThanOrEqualTo, ComparisonValue = 1, Data = d };
    }
    ConditionFloat Stage(uint quest, CompareOperator op, float v)
    {
        var d = new GetStageConditionData();
        d.Quest.Link.SetTo(Vanilla(quest));
        return new ConditionFloat { CompareOperator = op, ComparisonValue = v, Data = d };
    }
    ConditionFloat StageDone(uint quest, int stage, bool done)
    {
        var d = new GetStageDoneConditionData { Stage = stage };
        d.Quest.Link.SetTo(Vanilla(quest));
        return new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = done ? 1 : 0, Data = d };
    }
    ConditionFloat FactionIs(string edid, bool member)
    {
        var c = InFaction(FactionFk(edid));
        c.ComparisonValue = member ? 1 : 0;
        return c;
    }
    DialogTopic Topic(uint branchId, uint topicId, string stem)
    {
        var b = new DialogBranch(FK(branchId), Rel)
        {
            EditorID = "AG_BranchShowCard" + stem,
            Quest = new FormLink<IQuestGetter>(worldQuest.FormKey),
            Category = DialogBranch.CategoryType.Player,
            Flags = DialogBranch.Flag.TopLevel,
            StartingTopic = new FormLinkNullable<IDialogTopicGetter>(FK(topicId)),
        };
        var t = new DialogTopic(FK(topicId), Rel)
        {
            EditorID = "AG_TopicShowCard" + stem,
            Name = sc[stem == "Orcs" ? "orcsPrompt" : "prompt"]!.GetValue<string>(),
            Priority = 50,
            Branch = new FormLinkNullable<IDialogBranchGetter>(b.FormKey),
            Quest = new FormLinkNullable<IQuestGetter>(worldQuest.FormKey),
            Category = DialogTopic.CategoryEnum.Topic,
            Subtype = DialogTopic.SubtypeEnum.Custom,
            SubtypeName = new RecordType("CUST"),
        };
        mod.DialogBranches.Add(b);
        mod.DialogTopics.Add(t);
        return t;
    }
    DialogResponses Line(DialogTopic t, string key, string text, IEnumerable<Condition> conds)
    {
        var info = new DialogResponses(FK(InfoId("showcard:" + key)), Rel) { EditorID = "AG_Info_showcard_" + key.Replace(':', '_') };
        info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
        foreach (var c in conds) info.Conditions.Add(c);
        info.Conditions.Add(HasCard());
        info.Conditions.Add(GlobalIs(gRegistered, 1));
        info.Conditions.Add(GlobalIs(gInteractions, 1));  // MCM > Audio > NPC interactions: off, the game's own choice is all there is
        if (t.Responses.Count > 0) info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(t.Responses[^1].FormKey);
        t.Responses.Add(info);
        return info;
    }
    DialogResponsesAdapter Fragment(string script, ScriptProperty prop) => new()
    {
        Scripts = { new ScriptEntry { Name = script, Properties = { prop } } },
        ScriptFragments = new ScriptFragments { FileName = script, OnEnd = new ScriptFragment { ScriptName = script, FragmentName = "Fragment_0" } },
    };
    ScriptObjectProperty Obj(string name, FormKey fk) => new() { Name = name, Object = new FormLinkNullable<ISkyrimMajorRecordGetter>(fk), Flags = ScriptProperty.Flag.Edited };

    const uint MG01 = 0x01F251, DialogueOrcs = 0x03907C;

    // the strongholds, a topic of our own: beside "How can I convince you to let me in?", from a gate guard who has already turned the
    // player away (DialogueOrcs stage 10), while the player is neither Blood-Kin nor an Orc. Not Largashbur, which
    // vanilla keeps out of this conversation for its own quest.
    // Hold stamps: what a representative says when she has stamped a card. Nobody chooses it (no branch): the plugin has
    // her say it as the counter closes (AG_QuestHelper.SayLine -> ObjectReference.Say).
    // It has to be an Idle topic: of three kinds tried (2026-10-11), Say() only played that one. An Idle topic is also
    // what the game picks from for idle chatter, so every line is tied to its speaker AND to AG_StampSayGlobal, which
    // the plugin sets to 1 only for the moment she is to say it.
    var gStampSay = Global(0xCE9, "AG_StampSayGlobal", 0);
    // The standing a stamp gives: merchants in a hold whose stamp is on the card the player carries sell 15% cheaper.
    // The game's own way (Haggling, Allure): a perk entry on buy prices. One hidden perk, given to every member; its
    // entry counts only while AG_StampDiscountGlobal is 1, which the DLL keeps (in such a hold, card in hand).
    {
        var perk = new Perk(FK(0xCF5), Rel) { EditorID = "AG_Perk_HoldStampStanding", Name = "Hold Stamp", Playable = false, Hidden = true, NumRanks = 1 };
        var entry = new PerkEntryPointModifyValue
        {
            EntryPoint = APerkEntryPointEffect.EntryType.ModBuyPrices, Modification = PerkEntryPointModifyValue.ModificationType.Multiply,
            Value = 0.85f, PerkConditionTabCount = 1,
        };
        var tab = new PerkCondition { RunOnTabIndex = 0 };
        tab.Conditions.Add(GlobalIs(gStampDiscount, 1));
        entry.Conditions.Add(tab);
        perk.Effects.Add(entry);
        mod.Perks.Add(perk);
    }
    {
        var t = new DialogTopic(FK(0xCE6), Rel)
        {
            EditorID = "AG_TopicStampSaid", Priority = 50, Quest = new FormLinkNullable<IQuestGetter>(worldQuest.FormKey),
            Category = DialogTopic.CategoryEnum.Misc, Subtype = DialogTopic.SubtypeEnum.Idle, SubtypeName = new RecordType("IDLE"),
        };
        // Random with no rest, as the wanderers' greetings: a line written with no flags record at all was said once and then
        // refused until a save was loaded (measured 2026-10-11; a second stamp or a replacement card would get silence)
        foreach (var l in dlg["liaisons"]!.AsArray())
        {
            if (l!["stamped"] is not JsonNode said) continue;
            var npc = l["npc"]!.GetValue<string>();
            var info = new DialogResponses(FK(InfoId("stampsaid:" + npc)), Rel)
            {
                EditorID = "AG_Info_stampsaid_" + npc,
                Flags = new DialogResponseFlags { Flags = DialogResponses.Flag.Random, ResetHours = 0f },
            };
            info.Responses.Add(new DialogResponse { Text = said.GetValue<string>(), Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
            info.Conditions.Add(IsNpc(Npc(npc), false));
            info.Conditions.Add(GlobalIs(gStampSay, 1));
            info.Conditions.Add(GlobalIs(gRepLines, 1));  // MCM > Audio: with her lines off the stamp goes on in silence
            t.Responses.Add(info);
            // the first time: the same, with a word that the merchants here might think the better of a stamped card
            if (l["stampedFirst"] is JsonNode firstSaid)
            {
                var first = new DialogResponses(FK(InfoId("stampsaid:" + npc + ":first")), Rel)
                {
                    EditorID = "AG_Info_stampsaid_" + npc + "_first",
                    Flags = new DialogResponseFlags { Flags = DialogResponses.Flag.Random, ResetHours = 0f },
                };
                first.Responses.Add(new DialogResponse { Text = firstSaid.GetValue<string>(), Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
                first.Conditions.Add(IsNpc(Npc(npc), false));
                first.Conditions.Add(GlobalIs(gStampSay, 2));
                first.Conditions.Add(GlobalIs(gRepLines, 1));
                t.Responses.Add(first);
            }
        }
        mod.DialogTopics.Add(t);
    }
    // Whoever inherited an inn whose counter closed keeps the old liaison's stamp, and puts it on a card when asked: a choice
    // of its own, shown only while the DLL has her in AG_HoldStampDueFaction. The DLL stamps the card as she starts her reply.
    {
        var b = new DialogBranch(FK(0xCEC), Rel)
        {
            EditorID = "AG_BranchStampAsk", Quest = new FormLink<IQuestGetter>(worldQuest.FormKey),
            Category = DialogBranch.CategoryType.Player, Flags = DialogBranch.Flag.TopLevel,
            StartingTopic = new FormLinkNullable<IDialogTopicGetter>(FK(0xCED)),
        };
        var t = new DialogTopic(FK(0xCED), Rel)
        {
            EditorID = "AG_TopicStampAsk", Name = dlg["prompts"]!["stampAsk"]!.GetValue<string>(), Priority = 50,
            Branch = new FormLinkNullable<IDialogBranchGetter>(b.FormKey), Quest = new FormLinkNullable<IQuestGetter>(worldQuest.FormKey),
            Category = DialogTopic.CategoryEnum.Topic, Subtype = DialogTopic.SubtypeEnum.Custom, SubtypeName = new RecordType("CUST"),
        };
        var keeperShorts = new List<DialogResponses>();
        foreach (var k in dlg["stampKeepers"]!.AsArray())
        {
            var npc = k!["npc"]!.GetValue<string>();
            keeperShorts.Add(ShortReply("stampask:" + npc + ":short", false, new Condition[] { IsNpc(Npc(npc), false), InFaction(stampDueFaction.FormKey) }));
            roles["stamp"].Add(ids["stampask:" + npc + ":short"]);
            if (k["lineFirst"] is JsonNode lf)
            {
                var fkey = "stampask:" + npc + ":first";
                var first = new DialogResponses(FK(InfoId(fkey)), Rel) { EditorID = "AG_Info_stampask_" + npc + "_first" };
                first.Responses.Add(new DialogResponse { Text = lf.GetValue<string>(), Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
                first.Conditions.Add(IsNpc(Npc(npc), false));
                var rank = new GetFactionRankConditionData();
                rank.Faction.Link.SetTo(stampDueFaction.FormKey);
                first.Conditions.Add(new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = rank });
                first.Conditions.Add(GlobalIs(gRepLines, 1));
                if (t.Responses.Count > 0) first.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(t.Responses[^1].FormKey);
                t.Responses.Add(first);
                roles["stamp"].Add(ids[fkey]);
            }
            var key = "stampask:" + npc;
            var info = new DialogResponses(FK(InfoId(key)), Rel) { EditorID = "AG_Info_stampask_" + npc };
            info.Responses.Add(new DialogResponse { Text = k["line"]!.GetValue<string>(), Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
            info.Conditions.Add(IsNpc(Npc(npc), false));
            info.Conditions.Add(InFaction(stampDueFaction.FormKey));
            info.Conditions.Add(GlobalIs(gRepLines, 1));
            if (t.Responses.Count > 0) info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(t.Responses[^1].FormKey);
            t.Responses.Add(info);
            roles["stamp"].Add(ids[key]);
            stampKeepers.Add(new { npc = Key(Npc(npc)), of = Key(Npc(k["of"]!.GetValue<string>())), city = k["city"]!.GetValue<string>() });
        }
        PutFirst(t, keeperShorts);
        mod.DialogBranches.Add(b);
        mod.DialogTopics.Add(t);
    }
    // Other adventurers' guild cards, handed in (1.5.0; MemberCards.cpp keeps the two globals). A representative at her
    // counter has one choice for it while any such card is carried (AG_CardsCarriedGlobal), and she answers for the
    // weightiest of them (AG_CardCaseGlobal: 1 the owner lives, 2 is dead, 3 fell as one of the player's party,
    // 4 nothing but worn cards). The DLL acts as the reply starts.
    // (A conversation with the owner, to give a card straight back, was built and cut the same day: a living member's
    // card is only ever stolen or taken in trade, and a follower's goes back through the trade menu.)
    {
        DialogTopic Own(uint branchId, uint topicId, string stem, string prompt)
        {
            var b = new DialogBranch(FK(branchId), Rel)
            {
                EditorID = "AG_Branch" + stem, Quest = new FormLink<IQuestGetter>(worldQuest.FormKey),
                Category = DialogBranch.CategoryType.Player, Flags = DialogBranch.Flag.TopLevel,
                StartingTopic = new FormLinkNullable<IDialogTopicGetter>(FK(topicId)),
            };
            var t = new DialogTopic(FK(topicId), Rel)
            {
                EditorID = "AG_Topic" + stem, Name = dlg["prompts"]![prompt]!.GetValue<string>(), Priority = 50,
                Branch = new FormLinkNullable<IDialogBranchGetter>(b.FormKey), Quest = new FormLinkNullable<IQuestGetter>(worldQuest.FormKey),
                Category = DialogTopic.CategoryEnum.Topic, Subtype = DialogTopic.SubtypeEnum.Custom, SubtypeName = new RecordType("CUST"),
            };
            mod.DialogBranches.Add(b);
            mod.DialogTopics.Add(t);
            return t;
        }
        void Reply(DialogTopic t, string role, string key, string text, IEnumerable<Condition> conds)
        {
            var info = new DialogResponses(FK(InfoId(key)), Rel) { EditorID = "AG_Info_" + key.Replace(':', '_') };
            info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
            foreach (var c in conds) info.Conditions.Add(c);
            if (t.Responses.Count > 0) info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(t.Responses[^1].FormKey);
            t.Responses.Add(info);
            roles[role].Add(ids[key]);
        }
        var handIn = Own(0xCFE, 0xCFF, "CardHandIn", "cardHandIn");
        var cases = new[] { ("fallen", 3), ("dead", 2), ("alive", 1), ("worn", 4) };
        var handInShorts = new List<DialogResponses>();
        foreach (var l in dlg["liaisons"]!.AsArray())
        {
            if (l!["cardHandIn"] is not JsonNode hi) continue;
            var npc = l["npc"]!.GetValue<string>();
            foreach (var (name, n) in cases)
            {
                var who = new List<Condition> { IsNpc(Npc(npc), false) };
                if (l["successor"] is JsonNode su)  // only once the counter is hers, and only at her inn
                {
                    who.Add(InFaction(liaisonFaction.FormKey));
                    if (su["cell"] is JsonNode cell) who.Add(InCell(KeyFk(cell.GetValue<string>()), true));
                }
                who.Add(GlobalIs(gRegistered, 1));
                who.Add(GlobalCmp(gCardsCarried, CompareOperator.GreaterThanOrEqualTo, 1));
                who.Add(GlobalIs(gCardCase, n));
                who.Add(GlobalIs(gRepLines, 1));
                Reply(handIn, "cardhandin", $"cardhandin:{npc}:{name}", hi[name]!.GetValue<string>(), who);
            }
            {
                var who = new List<Condition> { IsNpc(Npc(npc), false) };
                if (l["successor"] is JsonNode su)
                {
                    who.Add(InFaction(liaisonFaction.FormKey));
                    if (su["cell"] is JsonNode cell) who.Add(InCell(KeyFk(cell.GetValue<string>()), true));
                }
                who.Add(GlobalIs(gRegistered, 1));
                who.Add(GlobalCmp(gCardsCarried, CompareOperator.GreaterThanOrEqualTo, 1));
                handInShorts.Add(ShortReply($"cardhandin:{npc}:short", false, who));
                roles["cardhandin"].Add(ids[$"cardhandin:{npc}:short"]);
            }
            if (!(hi["drinks"]?.GetValue<bool>() ?? true)) cardNoDrinks.Add(Key(Npc(npc)));
        }
        PutFirst(handIn, handInShorts);
    }
    var orcs = Topic(0xCE4, 0xCE5, "Orcs");
    var orcRace = new GetIsRaceConditionData { RunOnType = Condition.RunOnType.Target };
    orcRace.Race.Link.SetTo(idx["races"]["OrcRace"]);
    var gate = Line(orcs, "orcs", sc["orcs"]!.GetValue<string>(),
        new Condition[] { FactionIs("OrcGuardFaction", true), FactionIs("TownLargashburFaction", false), StageDone(DialogueOrcs, 10, true),
            OnPlayer(FactionIs("OrcFriendFaction", false)), new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 0, Data = orcRace } }.Concat(RankConds("A+")));
    gate.VirtualMachineAdapter = Fragment("AG_TIF_ShowCardFaction", Obj("TargetFaction", FactionFk("OrcFriendFaction")));

    // ---- replies ADDED to a vanilla choice ----
    // Their choices are a fixed list on the speaker's line, so a topic of ours cannot join them. But each choice is a
    // topic, and a plugin may add an INFO to a vanilla topic without overriding the INFOs already in it. Ours carries its
    // own wording for the player's choice (the INFO's prompt) and does what vanilla's success does. The topic's own
    // record is copied from vanilla unchanged, as the place to hang it.
    // WHERE IT SITS, tested in game 2026-10-10 on the Riften gate: an added INFO with no "previous" INFO is tried LAST
    // (behind vanilla's refusal: never reached); named after a vanilla INFO, it is tried right after that one. It can
    // never be first. So it takes a choice over only when the vanilla INFOs before it fail their own conditions:
    //   Riften, "(Persuade)": behind the Speech success, before the refusal. A player whose Speech passes keeps vanilla's.
    //   Whiterun, "Riverwood calls for the Jarl's aid.": behind both vanilla INFOs, which need the Riverwood errand. A
    //     member who was not sent by Riverwood gets the card in the place vanilla leaves empty. (Its Persuade, Bribe and
    //     Intimidate each have one INFO that always passes: nothing behind them is ever reached.)
    //   the robber, "(Intimidate)": behind the Intimidate success, before the refusal; by Guild rank, no card needed.
    {
        // 1.5.0, second design. The replies used to be added to the vanilla topic itself, which meant carrying a copy of
        // that topic record: its text (in English), its settings, and a conflict with any mod that changes them (the
        // Unofficial Patch corrects one). Now each set of replies has a topic of the mod's own, with no branch, and the
        // DLL offers it IN PLACE of the vanilla choice when one of its replies would be said (ChoiceSwap). The plugin
        // carries no vanilla record for this.
        var swapOf = new Dictionary<uint, (uint id, string stem, string prompt)>
        {
            [0x0E66B4] = (0xCEE, "Riften", "prompt"), [0x0D1979] = (0xCEF, "Whiterun", "prompt"), [0x0B8106] = (0xCF0, "College", "prompt"),
            [0x0D6630] = (0xCF1, "Treasury", "prompt"), [0x0BBA89] = (0xCF2, "OrcGate", "orcs"), [0x0B8155] = (0xCF3, "Robber", "robber"),
        };
        DialogTopic Hang(uint topicId)
        {
            var (id, stem, prompt) = swapOf[topicId];
            var hang = new DialogTopic(FK(id), Rel)
            {
                EditorID = "AG_TopicShowCard" + stem,
                Name = prompt == "robber" ? sc["robber"]!["prompt"]!.GetValue<string>() : sc[prompt == "orcs" ? "orcsPrompt" : "prompt"]!.GetValue<string>(),
                Priority = 50, Quest = new FormLinkNullable<IQuestGetter>(worldQuest.FormKey),
                Category = DialogTopic.CategoryEnum.Topic, Subtype = DialogTopic.SubtypeEnum.Custom, SubtypeName = new RecordType("CUST"),
            };
            mod.DialogTopics.Add(hang);
            choiceSwaps.Add(new { vanilla = Key(Vanilla(topicId)), ours = $"0x{id:X3}" });
            return hang;
        }
        // WHO SPEAKS is not asked again on a reply that stands in for a vanilla choice. The game only offers that choice
        // to the right speaker, and our topic is reached no other way (it has no branch). Until 2026-10-12 the Riften
        // and robber replies carried the speaker conditions of a vanilla line, copied as they were: GetIsAliasRef, which
        // asks about an alias of the line's OWN quest. In the vanilla topic that was the gate's quest; in a topic of
        // ours it is our quest, which has no such alias, so the condition was never true and the choice never
        // appeared (seen in game at the Riften gate).
        FormKey QuestFk(string edid)
        {
            if (questIdx.TryGetValue(edid, out var qk)) return qk;
            Console.Error.WriteLine($"ERROR show guild card: unknown quest '{edid}'"); errors++;
            return default;
        }
        // one added INFO, tried right after "after". quest and stage: what the line sets (vanilla's own success), or null for none
        DialogResponses Added(DialogTopic hang, string key, string text, string prompt, FormKey after, IEnumerable<Condition> conds, string? quest, int stage)
        {
            var info = new DialogResponses(FK(InfoId("showcard:" + key)), Rel)
            {
                EditorID = "AG_Info_showcard_" + key.Replace(':', '_'),
                Flags = new DialogResponseFlags { Flags = DialogResponses.Flag.Goodbye },
            };
            // in a topic of our own the replies are tried in the order written ("after" named a vanilla line and is not used)
            if (hang.Responses.Count > 0) info.PreviousDialog = new FormLinkNullable<IDialogResponsesGetter>(hang.Responses[^1].FormKey);
            byte part = 0;
            foreach (var t in text.Split('\n')) info.Responses.Add(new DialogResponse { Text = t, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = ++part });
            foreach (var c in conds) info.Conditions.Add(c);
            if (quest != null)
            {
                info.VirtualMachineAdapter = Fragment("AG_TIF_ShowCardStage", Obj("TargetQuest", QuestFk(quest)));
                ((ScriptEntry)info.VirtualMachineAdapter.Scripts[0]).Properties.Add(new ScriptIntProperty { Name = "Stage", Data = stage, Flags = ScriptProperty.Flag.Edited });
            }
            hang.Responses.Add(info);
            return info;
        }
        // ... and Show Guild Card is on (MCM > Audio > NPC interactions): off, none of ours passes and the game's own choice is offered
        IEnumerable<Condition> Member() => new Condition[] { HasCard(), GlobalIs(gRegistered, 1), GlobalIs(gInteractions, 1) };
        var cardPrompt = sc["prompt"]!.GetValue<string>();
        // a reply in parts (a json list): the speaker asks for the card, looks, then answers. One response each, as
        // vanilla splits a longer reply; they play one after the other with the game's own short gap between them
        string Txt(JsonNode? n) => n is JsonArray a ? string.Join("\n", a.Select(x => x!.GetValue<string>())) : n!.GetValue<string>();

        // Riften, north gate: "This is obviously a shakedown. (Persuade)". Vanilla's success sets DialogueRiftenGateGuards to 30.
        const uint riftenPersuade = 0x0E66B4;
        var riften = Hang(riftenPersuade);
        // one reply whatever the rank: it is said once in a playthrough
        Added(riften, "riften", Txt(sc["riften"]), cardPrompt, Vanilla(0x0E66D2),
            Member(), "DialogueRiftenGateGuards", 30);

        // Whiterun, main gate: "Riverwood calls for the Jarl's aid.". Vanilla's successes set DialogueWhiterunGuardGateStop to 10.
        var whiterun = Hang(0x0D1979);
        Condition[] GateGuard() => new Condition[] { IsNpc(Npc("GuardWhiterunImperialGate"), false) };
        Added(whiterun, "whiterun", Txt(sc["whiterun"]), cardPrompt, Vanilla(0x0DF1F9),
            GateGuard().Concat(Member()), "DialogueWhiterunGuardGateStop", 10);

        // the College: "I think we both know I'll succeed here. (Persuade)", behind the Speech success (very hard) and
        // before the refusal. As that success does (INFO 0B810C): no pause, straight on into her own "Welcome, Apprentice"
        // line, whose script admits the player (MG01 stage 30) and has her lead the way. Any rank.
        var college = Hang(0x0B8106);
        var prev = Vanilla(0x0B810C);
        foreach (var (key, text, rank) in new[] { ("college:E", Txt(sc["college"]!["E"]), "E"), ("college", Txt(sc["college"]!["other"]), "") })
        {
            var who = new Condition[] { IsNpc(Npc("Faralda"), false) };
            var info = Added(college, key, text, cardPrompt, prev, (rank == "" ? who : who.Concat(RankConds(rank))).Concat(Member()), null, 0);
            info.Flags = new DialogResponseFlags { Flags = DialogResponses.Flag.InvisibleContinue };
            info.LinkTo.Add(new FormLink<IDialogTopicGetter>(Vanilla(0x0B8102)));
            prev = info.FormKey;
        }

        // the Treasury House: "He's expecting me. (Persuade)", behind the Speech success (average) and before the refusal.
        // Rank C and up; below that vanilla's Persuade is as it was. Vanilla's success sets MS01 to 50 and says no goodbye.
        Added(Hang(0x0D6630), "treasury", sc["treasury"]!.GetValue<string>(), cardPrompt, Vanilla(0x0D66BA),
            new Condition[] { IsNpc(Npc("Rhiada"), false) }.Concat(RankConds("C+")).Concat(Member()), "MS01", 50).Flags = new DialogResponseFlags { Flags = 0 };

        // the strongholds, at the first meeting: the gate guard's "I go where I please, Orc.", behind the reply an Orc
        // player gets and before the one that turns everyone else away. Rank A and up. Vanilla's replies here set
        // DialogueOrcs to 10 (the halt has been said); ours does too, and takes the player into OrcFriendFaction.
        var orcGate = Added(Hang(0x0BBA89), "orcs:gate", sc["orcs"]!.GetValue<string>(), cardPrompt, Vanilla(0x0BBA91),
            new Condition[] { FactionIs("TownLargashburFaction", false), OnPlayer(FactionIs("OrcFriendFaction", false)) }.Concat(RankConds("A+")).Concat(Member()), null, 0);
        orcGate.VirtualMachineAdapter = Fragment("AG_TIF_ShowCardFaction", Obj("TargetFaction", FactionFk("OrcFriendFaction")));
        var orcScript = (ScriptEntry)orcGate.VirtualMachineAdapter.Scripts[0];
        orcScript.Properties.Add(Obj("TargetQuest", Vanilla(DialogueOrcs)));
        orcScript.Properties.Add(new ScriptIntProperty { Name = "Stage", Data = 10, Flags = ScriptProperty.Flag.Edited });

        // the roadside robber: "Walk away. Right now. (Intimidate)". Vanilla's success sets WERJ02 to 100. Ranks E to C
        // are left to vanilla (the robber is not impressed); B backs off; A and S beg.
        const uint robberIntimidate = 0x0B8155;
        var robber = Hang(robberIntimidate);
        var rankPrompt = sc["robber"]!["prompt"]!.GetValue<string>();
        prev = Added(robber, "robber:AS", sc["robber"]!["AS"]!.GetValue<string>(), rankPrompt, Vanilla(0x0B8164),
            RankConds("A+").Append(GlobalIs(gInteractions, 1)), "WERJ02", 100).FormKey;
        Added(robber, "robber:B", sc["robber"]!["B"]!.GetValue<string>(), rankPrompt, prev,
            RankConds("B").Append(GlobalIs(gInteractions, 1)), "WERJ02", 100);
        Console.WriteLine("show guild card: 8 replies added to 6 vanilla choices (the College, the Treasury House, the strongholds, Riften, Whiterun, the robber)");
    }
    Console.WriteLine("show guild card: 1 topic of its own (the strongholds)");
}
Console.WriteLine($"world dialogue: {worldCount} lines");

File.WriteAllText(idsPath, JsonSerializer.Serialize(ids, new JsonSerializerOptions { WriteIndented = true }));
// ---------- threat: judgement calls by race ----------
// threat.json names races by editor ID; the DLL wants FormKeys. Nothing else is worked out here: the level rank and
// the danger score come from the creature in the game.
{
    var judged = ReadConfig("threat")["races"]?.AsObject() ?? new JsonObject();
    var rules = new List<object>();
    foreach (var (edid, node) in judged)
    {
        if (!idx["races"].TryGetValue(edid, out var rfk)) { Console.Error.WriteLine($"ERROR threat.json: unknown race '{edid}'"); errors++; continue; }
        rules.Add(new
        {
            race = Key(rfk), name = edid,
            atLeast = node!["atLeast"]?.GetValue<string>(),
            fromLevel = node["fromLevel"]?.GetValue<int>(),
            atMost = node["atMost"]?.GetValue<string>(),
        });
    }
    var named = new List<object>();
    foreach (var (edid, node) in ReadConfig("threat")["actors"]?.AsObject() ?? new JsonObject())
    {
        if (!idx["npcs"].TryGetValue(edid, out var afk)) { Console.Error.WriteLine($"ERROR threat.json: unknown actor '{edid}'"); errors++; continue; }
        named.Add(new { actor = Key(afk), name = edid, atLeast = node!["atLeast"]?.GetValue<string>() });
    }
    File.WriteAllText(Path.Combine(outDir, "threat.resolved.json"), JsonSerializer.Serialize(new
    {
        _comment = "Threat judgement calls, where neither level nor the danger score ranks a creature right. races: atLeast = never below this rank (fromLevel: only once the creature is at least that level); atMost = never above this rank, replacing the ceiling its keywords give it (wildlife stops at B). actors: one actor by name, never below this rank. Rank letters E D C B A S. Rank S is never reached by level alone: an \"atLeast\": \"S\" here is S, and so is a dragon from the A level up; anything else has to prove it (at the S level, with a danger score of ScoreS or more) or stops at A. Edit or delete a line as you like. [Threat] RaceRules = 0 in AdventurersGuild.ini turns all of it off.",
        races = rules,
        actors = named,
    }, new JsonSerializerOptions { WriteIndented = true, DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull }));
    Console.WriteLine($"threat rules: {rules.Count} races, {named.Count} actors");
}
File.WriteAllText(Path.Combine(outDir, "dialogue.resolved.json"), JsonSerializer.Serialize(new { roles, liaisons = liaisonKeys, cities = liaisonCities, successors, stampKeepers, choiceSwaps, cardNoDrinks }, new JsonSerializerOptions { WriteIndented = true }));
Console.WriteLine($"dialogue: {ids.Count} INFO ids pinned, {liaisonKeys.Count} liaisons");

// ---------- onboarding: the registration missive ----------
// Handed out by the DLL when an unregistered player uses a Missives board (no Missives record is touched).
var regQuest = new Quest(FK(0x810), Rel)
{
    EditorID = "AG_RegistrationQuest",
    Name = "Adventurer Registration",
    Type = Quest.TypeEnum.Misc,
    Priority = 40,
    Stages =
    {
        new QuestStage
        {
            Index = 10,
            // Flags is given even though it is empty: without it the entry is written with no QSDT, which the game and
            // xEdit read and Wrye Bash does not (IndexError; every vanilla log entry starts with QSDT)
            LogEntries = { new QuestLogEntry { Flags = (QuestLogEntry.Flag)0, Entry = "The missive board only takes work from registered adventurers. The innkeeper of any hold capital can sign me up with the Adventurers Guild." } },
        },
        new QuestStage
        {
            Index = 100,
            LogEntries = { new QuestLogEntry { Flags = QuestLogEntry.Flag.CompleteQuest, Entry = "I registered with the Adventurers Guild. Missives suited to my rank are now open to me." } },
        },
    },
    Objectives = { new QuestObjective { Index = 10, DisplayText = "Register with the Adventurers Guild at an inn in any hold capital" } },
};
mod.Quests.Add(regQuest);

// Shape copied from a vanilla note so the item looks, sounds and handles like one.
var noteSrc = masters.SelectMany(m => m.Books).First(b => b.EditorID == "MS07JareeRaNote");
// The size of a sheet of paper lying flat, written into every note and card of ours. It was copied from the note above,
// which has none (all zeros, one of 21 vanilla notes like that), and an item with no size goes through the floor when
// it is dropped: the cards did, and so did the game's own Ivarstead key and Balbus's fork, which have no size either,
// while everything with a size landed (Bannered Mare, 2026-10-13, 32 drops measured from outside the game). The
// collision in the mesh was never at fault. These are the figures other mods give the game's note.
ObjectBounds PaperBounds() => new ObjectBounds { First = new Noggog.P3Int16(-8, -5, 0), Second = new Noggog.P3Int16(8, 5, 0) };
var note = new Book(FK(0x811), Rel)
{
    EditorID = "AG_RegistrationMissive",
    Name = "Missive: Register with the Adventurers Guild",
    Model = noteSrc.Model?.DeepCopy(),
    ObjectBounds = PaperBounds(),
    PickUpSound = noteSrc.PickUpSound is { } pu ? new FormLinkNullable<ISoundDescriptorGetter>(pu.FormKey) : null,
    PutDownSound = noteSrc.PutDownSound is { } pd ? new FormLinkNullable<ISoundDescriptorGetter>(pd.FormKey) : null,
    InventoryArt = noteSrc.InventoryArt is { } ia ? new FormLinkNullable<IStaticGetter>(ia.FormKey) : null,
    Flags = noteSrc.Flags,
    Type = noteSrc.Type,
    Value = 0,
    Weight = 0,
    Description = "",
    BookText =
        "<p align=\"center\"><font size=\"30\">ADVENTURERS GUILD</font></p>" +
        "<p align=\"center\">Notice to all who would take work from this board</p><br>" +
        "<p>The missives posted here are Guild Missives. They are offered only to registered adventurers, " +
        "and only at a rank the Guild judges you fit for.</p><br>" +
        "<p>Registration is open at the inn of every hold capital, where the missive boards stand. Speak to the innkeeper. The fee is fifty septims.</p><br>" +
        "<p>Those with experience will be assessed and placed accordingly. Everything above that is earned: " +
        "trophies, cleared dungeons and completed missives build your standing with the Guild, and the same innkeepers " +
        "will hear your case for promotion once you have earned it.</p><br>" +
        "<p align=\"right\">- The Adventurers Guild</p>",
};
mod.Books.Add(note);

// The physical Guild Card (1.2.0): a note the DLL hands over at registration and renames at each promotion. Reading it
// opens the counter's Guild Card page (GuildCard.cpp watches the Book Menu); this text is only seen if that cannot
// happen (PrismaUI missing, or the card in the hands of someone the Guild does not know).
// The notices' sounds (1.5.0, PrismaToast.cpp plays them by these IDs). Each is a sound descriptor of OURS that names a file
// of the GAME's: no audio is shipped. Ours, and not the game's records, because the author chose single files by ear
// (2026-10-13) where the game's record picks one of several at random (its stingers, its reward music, the smithing
// sound). Every one is a copy of a game interface sound, with the file changed where one was chosen: they play once,
// flat, at the effects volume.
// Two of the files are MUSIC (dungeon entered, registered), and a sound record cannot name a music file: written with
// its real path, Data\Music\..., the record loads and plays nothing (in game, 2026-10-13). Played through the music
// system, as music types of ours, the track played over and over until the save was loaded again. So those two
// records are written with the level-up sound as a stand-in, and the DLL gives each the game's own reference to the
// music file, taken from the game's own track record, once the game has loaded (PrismaToast.cpp, BorrowTracks). A
// record still holding its stand-in is never played.
void Cue(uint id, string edid, string like, string? file)
{
    var src = masters.SelectMany(m => m.SoundDescriptors).Last(s => s.EditorID == like);
    var sd = new SoundDescriptor(FK(id), Rel);
    sd.DeepCopyIn(src);
    sd.EditorID = edid;
    if (file != null) { sd.SoundFiles.Clear(); sd.SoundFiles.Add(new Mutagen.Bethesda.Plugins.Assets.AssetLink<Mutagen.Bethesda.Skyrim.Assets.SkyrimSoundAssetType>(file)); }
    // Played once, whatever the record it was copied from says: the skill-increase sound has no such setting of its
    // own, and played from here it went on and on (in game, 2026-10-13). The level-up sound's, which is "no loop".
    sd.LoopAndRumble = masters.SelectMany(m => m.SoundDescriptors).Last(s => s.EditorID == "UILevelUpSD").LoopAndRumble?.DeepCopy();
    mod.SoundDescriptors.Add(sd);
}
Cue(0xC81, "AG_CuePromoted", "UILevelUpSD", null);
Cue(0xC82, "AG_CueDungeonEntered", "UILevelUpSD", null);   // MUSStinger02's file, given by the DLL
Cue(0xC83, "AG_CueRegistered", "UILevelUpSD", null);       // MUSReward01's file, given by the DLL
Cue(0xC84, "AG_CuePromotionReady", "UISkillIncreaseSD", null);
Cue(0xC85, "AG_CueComplete", "UIQuestComplete", null);
Cue(0xC86, "AG_CueStamped", "UISmithingCreateGeneric", @"Data\Sound\FX\UI\Smithing\UI_Smithing_CreateGeneric_01.wav");
Cue(0xC87, "AG_CueReputationLost", "UILevelUpSD", @"Data\Sound\FX\mgk\firebolt\mag_firebolt_fail.wav");
// The Guild Drums (MCM > Audio > Notification sounds, the default): the mod's own drums, made from arithmetic alone by
// tools/make_drums.py and chosen by ear by the author (2026-10-13). Under names of ours, so no sound mod replaces them.
// Same order as above (PrismaToast.cpp, kDrumId); several notices share a file, as the author chose.
Cue(0xC8B, "AG_DrumPromoted", "UILevelUpSD", @"Data\Sound\FX\AdventurersGuild\ag_stamp.wav");
Cue(0xC8C, "AG_DrumDungeonEntered", "UILevelUpSD", @"Data\Sound\FX\AdventurersGuild\ag_dungeon_entered.wav");
Cue(0xC8D, "AG_DrumRegistered", "UILevelUpSD", @"Data\Sound\FX\AdventurersGuild\ag_registered.wav");
Cue(0xC8E, "AG_DrumPromotionReady", "UILevelUpSD", @"Data\Sound\FX\AdventurersGuild\ag_promotion_ready.wav");
Cue(0xC8F, "AG_DrumComplete", "UILevelUpSD", @"Data\Sound\FX\AdventurersGuild\ag_cleared.wav");
Cue(0xCE7, "AG_DrumStamped", "UILevelUpSD", @"Data\Sound\FX\AdventurersGuild\ag_stamp.wav");
Cue(0xCE8, "AG_DrumReputationLost", "UILevelUpSD", @"Data\Sound\FX\AdventurersGuild\ag_reputation_lost.wav");

// What the inventory shows for a card, and what the Book Menu opens (a book's "inventory art"): the game's own menu
// note with its pages hidden and the card laid in it (tools/make_card_mesh.py, write_inventory, says why). 0xCE0-0xCE2,
// which development builds of Show Guild Card used and no release ever did.
FormLinkNullable<IStaticGetter> CardArt(uint id, string stem)
{
    var st = new Static(FK(id), Rel) { EditorID = "AG_" + stem + "Art", Model = new Model { File = @"AdventurersGuild\" + stem.ToLowerInvariant() + "_inv.nif" } };
    mod.Statics.Add(st);
    return new FormLinkNullable<IStaticGetter>(st.FormKey);
}
var cardArt = new Dictionary<string, FormLinkNullable<IStaticGetter>>
{
    ["guildcard"] = CardArt(0xCE0, "GuildCard"), ["guildcard_morrowind"] = CardArt(0xCE1, "GuildCard_Morrowind"), ["guildcard_worn"] = CardArt(0xCE2, "GuildCard_Worn"),
    ["guildcard_bloody"] = CardArt(0xC7E, "GuildCard_Bloody"), ["guildcard_morrowind_bloody"] = CardArt(0xC7F, "GuildCard_Morrowind_Bloody"),
};
var card = new Book(FK(0x81A), Rel)
{
    EditorID = "AG_GuildCard",
    Name = "Adventurers Guild Card",
    // its own mesh (tools/make_card_item.py): the sheet of the card page, the wax and the emblem standing proud of it.
    // A card issued at Raven Rock is given the mesh with Morrowind's wax by the DLL (GuildCard.cpp).
    Model = new Model { File = @"AdventurersGuild\guildcard.nif" },
    ObjectBounds = PaperBounds(),
    PickUpSound = noteSrc.PickUpSound is { } cpu ? new FormLinkNullable<ISoundDescriptorGetter>(cpu.FormKey) : null,
    PutDownSound = noteSrc.PutDownSound is { } cpd ? new FormLinkNullable<ISoundDescriptorGetter>(cpd.FormKey) : null,
    InventoryArt = cardArt["guildcard"],
    Flags = noteSrc.Flags,
    Type = noteSrc.Type,
    Value = 0,
    Weight = 0,
    Description = "",
    BookText =
        "<p align=\"center\"><font size=\"30\">ADVENTURERS GUILD</font></p>" +
        "<p align=\"center\">Member's Card</p><br>" +
        "<p>The bearer is a registered adventurer of the Guild. Rank, standing and record are kept in the Guild's ledger " +
        "and may be confirmed at the inn of any hold capital.</p><br>" +
        "<p align=\"right\">- The Adventurers Guild</p>",
};
mod.Books.Add(card);

// The other adventurers' cards (1.5.0, MemberCards.cpp). AG_MemberCard: one person's card; each copy carries its own display
// name ("Guild Card: Mjoll the Lioness") and reading it opens the card page in its member view. This text is only seen if
// that cannot happen. AG_WornCard: what an adventurer with no name of their own carries; there is nothing to read.
Book CardLike(uint id, string edid, string name, string mesh, string text) => new Book(FK(id), Rel)
{
    EditorID = edid, Name = name,
    Model = new Model { File = @"AdventurersGuild\" + mesh + ".nif" }, ObjectBounds = PaperBounds(),
    PickUpSound = noteSrc.PickUpSound is { } mpu ? new FormLinkNullable<ISoundDescriptorGetter>(mpu.FormKey) : null,
    PutDownSound = noteSrc.PutDownSound is { } mpd ? new FormLinkNullable<ISoundDescriptorGetter>(mpd.FormKey) : null,
    InventoryArt = cardArt[mesh],
    Flags = noteSrc.Flags, Type = noteSrc.Type, Value = 0, Weight = 0, Description = "", BookText = text,
};
mod.Books.Add(CardLike(0xCF7, "AG_MemberCard", "Adventurers Guild Card (NPC)", "guildcard",
    "<p align=\"center\"><font size=\"30\">ADVENTURERS GUILD</font></p>" +
    "<p align=\"center\">Member's Card</p><br>" +
    "<p>The bearer is a registered adventurer of the Guild. Rank, standing and record are kept in the Guild's ledger " +
    "and may be confirmed at the inn of any hold capital.</p><br>" +
    "<p align=\"right\">- The Adventurers Guild</p>"));
// the same card for a member of Solstheim: an item of its own only because the wax on its mesh is Morrowind's (one item, one mesh)
mod.Books.Add(CardLike(0xCFC, "AG_MemberCardMorrowind", "Adventurers Guild Card (NPC)", "guildcard_morrowind",
    "<p align=\"center\"><font size=\"30\">ADVENTURERS GUILD</font></p>" +
    "<p align=\"center\">Member's Card</p><br>" +
    "<p>The bearer is a registered adventurer of the Guild. Rank, standing and record are kept in the Guild's ledger " +
    "and may be confirmed at the inn of any hold capital.</p><br>" +
    "<p align=\"right\">- The Adventurers Guild</p>"));
// A dead adventurer's card (1.5.0): the same card, bloodied and torn as the card page shows it for them. The DLL puts it in
// place of the clean one, with the same name, once the owner is known to be dead (MemberCards.cpp, Bloody). Two, for the wax.
foreach (var (id, edid, mesh) in new[] { (0xC7Cu, "AG_MemberCardBloody", "guildcard_bloody"), (0xC7Du, "AG_MemberCardMorrowindBloody", "guildcard_morrowind_bloody") })
    mod.Books.Add(CardLike(id, edid, "Adventurers Guild Card (NPC)", mesh,
        "<p align=\"center\"><font size=\"30\">ADVENTURERS GUILD</font></p>" +
        "<p align=\"center\">Member's Card</p><br>" +
        "<p>The bearer is a registered adventurer of the Guild. Rank, standing and record are kept in the Guild's ledger " +
        "and may be confirmed at the inn of any hold capital.</p><br>" +
        "<p align=\"right\">- The Adventurers Guild</p>"));
mod.Books.Add(CardLike(0xCF8, "AG_WornCard", "Adventurers Guild Card (NPC) - Unreadable", "guildcard_worn",
    "<p>The remains of a card of the Adventurers Guild. The holder's name is no longer readable.</p>"));

// ---------- Appraisal: a passive Guild skill (0x820-0x82F) ----------
// One perk per tier; AdventurersGuild.dll keeps exactly the purchased tier's perk on the player. Each
// carries a visible marker ability (so the skill shows in Active Effects) and, from II up, a
// ModSellPrices multiplier: merchants pay more, the same entry point vanilla Haggling uses.
var guildCfg = ReadConfig("guild");
var sellBonus = guildCfg["appraisal"]!["sellBonus"]!.AsArray().Select(x => x!.GetValue<int>()).ToArray();
MagicEffect Marker(uint id, string edid, string name, string desc)
{
    var m = new MagicEffect(FK(id), Rel)
    {
        EditorID = edid, Name = name, Description = desc,
        Archetype = new MagicEffectArchetype { Type = MagicEffectArchetype.TypeEnum.PeakValueModifier, ActorValue = ActorValue.Health },
        CastType = CastType.ConstantEffect, TargetType = TargetType.Self, BaseCost = 0f,
        Flags = MagicEffect.Flag.Recover | MagicEffect.Flag.NoDuration | MagicEffect.Flag.PowerAffectsMagnitude,
    };
    mod.MagicEffects.Add(m);
    return m;
}
Spell Ability(uint id, string edid, string name, string desc, MagicEffect fx, float mag)
{
    var sp = new Spell(FK(id), Rel)
    {
        EditorID = edid, Name = name, Description = desc,
        Type = SpellType.Ability, CastType = CastType.ConstantEffect, TargetType = TargetType.Self, BaseCost = 0,
    };
    sp.Effects.Add(new Effect { BaseEffect = new FormLinkNullable<IMagicEffectGetter>(fx.FormKey), Data = new EffectData { Magnitude = mag } });
    mod.Spells.Add(sp);
    return sp;
}
string[] roman = { "I", "II", "III" };
for (int t = 0; t < 3; t++)
{
    var adesc = t switch
    {
        0 => "You read an adventurer's guild rank at a glance, the threat rank of people and wildlife, and the threat rank of a dungeon as you enter it.",
        1 => $"You also read the threat rank of creatures of legend. Merchants pay {sellBonus[1]}% more, and trophies earn more Merit.",
        _ => $"Nothing escapes your eye: not the deadliest threats, ranks A and S, nor a hidden rank. Merchants pay {sellBonus[2]}% more, and trophies earn much more Merit.",
    };
    var afx = Marker((uint)(0x823 + t), $"AG_MGEF_Appraisal{t + 1}", $"Appraisal {roman[t]}", adesc);
    var ab = Ability((uint)(0x826 + t), $"AG_Ab_Appraisal{t + 1}", $"Appraisal {roman[t]}", adesc, afx, 0f);
    var perk = new Perk(FK((uint)(0x820 + t)), Rel)
    {
        EditorID = $"AG_Appraisal{t + 1}", Name = $"Appraisal {roman[t]}", Description = adesc,
        Playable = false, Hidden = true, Trait = false, NumRanks = 1, Level = 0,
    };
    if (sellBonus[t] > 0)
    {
        perk.Effects.Add(new PerkEntryPointModifyValue
        {
            Rank = 0, Priority = 0, EntryPoint = APerkEntryPointEffect.EntryType.ModSellPrices,
            Modification = PerkEntryPointModifyValue.ModificationType.Multiply, Value = 1f + sellBonus[t] / 100f,
            PerkConditionTabCount = 2,  // measured on vanilla (MGArchMageVendorPerk): ModSellPrices has 2 tabs
        });
    }
    perk.Effects.Add(new PerkAbilityEffect { Rank = 0, Priority = 0, Ability = ab.ToLink() });
    mod.Perks.Add(perk);
}

// ---------- Guild Training: permanent +Health/Stamina/Magicka (0x830-0x8BF) ----------
// One visible ability per stat step (magnitude = step * amount); the DLL keeps exactly the current
// step's spell, so Active Effects shows a single "Guild Training" row per stat.
var training = ReadConfig("shop")["training"]!;
int amount = training["amount"]!.GetValue<int>(), steps = training["perRank"]!.GetValue<int>() * 6;
if (steps > 32) { Console.Error.WriteLine("ERROR shop.json: training.perRank * 6 must be <= 32"); Environment.Exit(1); }
(string key, string name, ActorValue av)[] stats = { ("Health", "Vitality", ActorValue.Health), ("Stamina", "Endurance", ActorValue.Stamina), ("Magicka", "Arcana", ActorValue.Magicka) };
for (int si = 0; si < 3; si++)
{
    var (key, sname, av) = stats[si];
    var tfx = new MagicEffect(FK((uint)(0x830 + si)), Rel)
    {
        EditorID = $"AG_MGEF_Train{key}", Name = $"Guild Training: {sname}",
        Description = $"Maximum {key.ToLower()} increased by <mag>.",
        Archetype = new MagicEffectArchetype { Type = MagicEffectArchetype.TypeEnum.PeakValueModifier, ActorValue = av },
        CastType = CastType.ConstantEffect, TargetType = TargetType.Self, BaseCost = 0f,
        Flags = MagicEffect.Flag.Recover | MagicEffect.Flag.NoDuration | MagicEffect.Flag.PowerAffectsMagnitude,
    };
    mod.MagicEffects.Add(tfx);
    for (int n = 1; n <= steps; n++)
        Ability((uint)(0x840 + si * 0x20 + (n - 1)), $"AG_Ab_Train{key}{n:D2}", $"Guild Training: {sname}",
            $"Maximum {key.ToLower()} increased by {n * amount}.", tfx, n * amount);
}

// ---------- Guild Augments (0xCA0-0xCD7): a timed boon, one at a time ----------
// One ability each: effects 0xCA0 + augment*4 (up to 4), the ability 0xCC0 + augment, a perk 0xCD0 + augment when it
// needs one. The DLL adds the ability on purchase and takes it away when its game time is up. Each effect is vanilla's
// own way of doing the same thing: Fortify Carry Weight, Fortify Barter (SpeechcraftModifier), Resist Disease / Poison,
// and Well Rested for skill gains (an effect that applies a perk with Mod Skill Use).
{
    var alist = ReadConfig("shop")["augments"]!["list"]!.AsArray();
    if (alist.Count > 8) { Console.Error.WriteLine("ERROR shop.json: at most 8 augments"); Environment.Exit(1); }
    for (int ai = 0; ai < alist.Count; ai++)
    {
        var a = alist[ai]!;
        string aid = a["id"]!.GetValue<string>(), aname = "Guild Augment: " + a["name"]!.GetValue<string>(), adesc = a["desc"]!.GetValue<string>();
        var asp = new Spell(FK((uint)(0xCC0 + ai)), Rel)
        {
            EditorID = $"AG_Ab_Augment_{aid}", Name = aname, Description = adesc,
            Type = SpellType.Ability, CastType = CastType.ConstantEffect, TargetType = TargetType.Self, BaseCost = 0,
        };
        uint slot = 0;
        MagicEffect AFx(string suffix, ActorValue av, float mag, string desc)
        {
            if (slot >= 4) { Console.Error.WriteLine($"ERROR shop.json: augment '{aid}' has more than 4 effects"); Environment.Exit(1); }
            var m = new MagicEffect(FK((uint)(0xCA0 + ai * 4) + slot++), Rel)
            {
                EditorID = $"AG_MGEF_Augment_{aid}_{suffix}", Name = aname, Description = desc,
                Archetype = new MagicEffectArchetype { Type = MagicEffectArchetype.TypeEnum.PeakValueModifier, ActorValue = av },
                CastType = CastType.ConstantEffect, TargetType = TargetType.Self, BaseCost = 0f,
                Flags = MagicEffect.Flag.Recover | MagicEffect.Flag.NoDuration | MagicEffect.Flag.PowerAffectsMagnitude,
            };
            mod.MagicEffects.Add(m);
            asp.Effects.Add(new Effect { BaseEffect = new FormLinkNullable<IMagicEffectGetter>(m.FormKey), Data = new EffectData { Magnitude = mag } });
            return m;
        }
        float? Num(string k) => a[k]?.GetValue<float>();
        if (Num("carry") is float carry) AFx("Carry", ActorValue.CarryWeight, carry, "Carry weight increased by <mag>.");
        if (Num("barter") is float barter) AFx("Barter", ActorValue.SpeechcraftModifier, barter, "Prices are <mag>% better.");
        if (Num("resistDisease") is float rd) AFx("Disease", ActorValue.ResistDisease, rd, "Resist <mag>% of disease.");
        if (Num("resistPoison") is float rp) AFx("Poison", ActorValue.PoisonResist, rp, "Resist <mag>% of poison.");
        if (Num("health") is float ah) AFx("Health", ActorValue.Health, ah, "Health increased by <mag>.");
        if (Num("stamina") is float ast) AFx("Stamina", ActorValue.Stamina, ast, "Stamina increased by <mag>.");
        if (Num("magicka") is float am) AFx("Magicka", ActorValue.Magicka, am, "Magicka increased by <mag>.");
        if (Num("skillRate") is float sr)
        {
            var perk = new Perk(FK((uint)(0xCD0 + ai)), Rel) { EditorID = $"AG_Perk_Augment_{aid}", Name = aname, Playable = false, Hidden = true, NumRanks = 1 };
            perk.Effects.Add(new PerkEntryPointModifyValue
            {
                EntryPoint = APerkEntryPointEffect.EntryType.ModSkillUse, Modification = PerkEntryPointModifyValue.ModificationType.Multiply,
                Value = 1f + sr / 100f, PerkConditionTabCount = 1,  // as vanilla's RestedWellPerk: one tab (perk owner)
            });
            mod.Perks.Add(perk);
            AFx("Skills", ActorValue.Health, 0f, $"Skills improve {sr:0}% faster.").PerkToApply.SetTo(perk);
        }
        if (asp.Effects.Count == 0) { Console.Error.WriteLine($"ERROR shop.json: augment '{aid}' does nothing"); Environment.Exit(1); }
        mod.Spells.Add(asp);
    }
    Console.WriteLine($"augments: {alist.Count}");
}

// ---------- Party blessing (0x8D0-0x8FF): Bond tiers + Party Traits, docs/PARTIES.md ----------
// One constant ability on the player and each active party member. Every bonus is its own effect gated by conditions:
// a global the DLL sets (Bond tier, members present, each trait switched on), the member's distance to the player,
// and for some traits the time of day or the combat target's faction. The DLL only sets globals and adds/removes the
// spell; the engine does the rest (no polling).
{
    var tcfg = ReadConfig("traits");
    float range = tcfg["range"]!.GetValue<float>();
    var bl = tcfg["blessing"]!;
    var gTier = Global(0x8D1, "AG_PartyBondTierGlobal", -1);       // -1 with no member present
    var gPresent = Global(0x8D2, "AG_PartyPresentGlobal", 0);      // members present (not counting the player)
    var traits = tcfg["traits"]!.AsArray();
    if (traits.Count > 24) { Console.Error.WriteLine("ERROR traits.json: at most 24 traits (0x8D3-0x8DA, 0xC00-0xC0F)"); Environment.Exit(1); }
    var tGlobals = new Dictionary<string, GlobalShort>();
    for (int i = 0; i < traits.Count; i++)
    {   // the DLL computes the same IDs (Party.cpp TraitGlobalId)
        var id = traits[i]!["id"]!.GetValue<string>();
        tGlobals[id] = Global(i < 8 ? (uint)(0x8D3 + i) : (uint)(0xC00 + i - 8), $"AG_PartyTrait_{id}", 0);
    }
    // FormIDs are handed out in order and pinned by it: the first 8 traits' effects fill 0x8DB-0x8FF, later ones 0xC10-0xC7F
    uint nextFx = 0x8DB, fxEnd = 0x8FF;
    uint NextId()
    {
        if (nextFx > fxEnd) { Console.Error.WriteLine($"ERROR party blessing: out of FormIDs (to 0x{fxEnd:X})"); Environment.Exit(1); }
        return nextFx++;
    }
    var spell = new Spell(FK(0x8D0), Rel)
    {
        EditorID = "AG_PartyBlessing", Name = "Party Blessing",
        Description = "The strength of your adventuring party: its Bond and the traits of those who travel together.",
        Type = SpellType.Ability, CastType = CastType.ConstantEffect, TargetType = TargetType.Self, BaseCost = 0,
    };
    Condition Near()
    {
        var d = new GetDistanceConditionData();
        d.Target.Link.SetTo(FormKey.Factory("000014:Skyrim.esm"));
        return new ConditionFloat { CompareOperator = CompareOperator.LessThanOrEqualTo, ComparisonValue = range, Data = d };
    }
    MagicEffect Add(string edid, string name, ActorValue av, float mag, params Condition[] conds)
    {
        var fx = new MagicEffect(FK(NextId()), Rel)
        {
            EditorID = edid, Name = name,
            Archetype = new MagicEffectArchetype { Type = MagicEffectArchetype.TypeEnum.PeakValueModifier, ActorValue = av },
            CastType = CastType.ConstantEffect, TargetType = TargetType.Self, BaseCost = 0f,
            Flags = MagicEffect.Flag.Recover | MagicEffect.Flag.NoDuration,
        };
        mod.MagicEffects.Add(fx);
        var e = new Effect { BaseEffect = new FormLinkNullable<IMagicEffectGetter>(fx.FormKey), Data = new EffectData { Magnitude = mag } };
        foreach (var c in conds) e.Conditions.Add(c);
        e.Conditions.Add(Near());
        spell.Effects.Add(e);
        return fx;
    }
    ConditionFloat Or(ConditionFloat c) { c.Flags |= Condition.Flag.OR; return c; }
    // Bond: regeneration per tier above Strangers, and a flat armor bonus while anyone is present (1.1.0: it was
    // "per member present", four stacking effects; with parties of up to nine that ran away). The four records stay,
    // in the same order, because every later effect's FormID follows from them: the first carries the bonus, the
    // other three have no magnitude and a condition that never holds.
    for (int k = 1; k <= 4; k++)
        Add($"AG_MGEF_BondHeal{k}", "Party Bond: health regeneration", ActorValue.HealRateMult, bl["healRatePerTier"]!.GetValue<float>(), GlobalCmp(gTier, CompareOperator.GreaterThanOrEqualTo, k));
    for (int k = 1; k <= 4; k++)
        Add($"AG_MGEF_BondStamina{k}", "Party Bond: stamina regeneration", ActorValue.StaminaRateMult, bl["staminaRatePerTier"]!.GetValue<float>(), GlobalCmp(gTier, CompareOperator.GreaterThanOrEqualTo, k));
    for (int k = 1; k <= 4; k++)
        Add($"AG_MGEF_BondArmor{k}", "Party Bond: armor", ActorValue.DamageResist, k == 1 ? bl["armor"]!.GetValue<float>() : 0f, GlobalCmp(gPresent, CompareOperator.GreaterThanOrEqualTo, k == 1 ? 1 : 1000));
    // Traits
    for (int ti = 0; ti < traits.Count; ti++)
    {
        var tn = traits[ti];
        if (ti == 8) { nextFx = 0xC10; fxEnd = 0xC7F; }
        var id = tn!["id"]!.GetValue<string>();
        var nm = tn["name"]!.GetValue<string>();
        var on = GlobalIs(tGlobals[id], 1);
        var extra = new List<Condition>();
        if (tn["night"]?.GetValue<bool>() == true)
        {   // night: 20:00-06:00 (OR binds before AND: on AND (after 20 OR before 6))
            extra.Add(Or(new ConditionFloat { CompareOperator = CompareOperator.GreaterThanOrEqualTo, ComparisonValue = 20, Data = new GetCurrentTimeConditionData() }));
            extra.Add(new ConditionFloat { CompareOperator = CompareOperator.LessThan, ComparisonValue = 6, Data = new GetCurrentTimeConditionData() });
        }
        if (tn["targets"]?["factions"] is JsonArray tf)
        {   // the combat target is in any of these factions
            var fl = tf.Select(x => x!.GetValue<string>()).ToList();
            for (int i = 0; i < fl.Count; i++)
            {
                if (!idx["factions"].TryGetValue(fl[i], out var ffk)) { Console.Error.WriteLine($"ERROR traits.json: unknown faction {fl[i]}"); Environment.Exit(1); }
                var d = new GetInFactionConditionData { RunOnType = Condition.RunOnType.CombatTarget };
                d.Faction.Link.SetTo(ffk);
                var c = new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = d };
                extra.Add(i < fl.Count - 1 ? Or(c) : c);
            }
        }
        if (tn["targets"]?["keywords"] is JsonArray tk)
        {   // the combat target has any of these keywords (ActorTypeUndead, Vampire, ...)
            var kl = tk.Select(x => x!.GetValue<string>()).ToList();
            for (int i = 0; i < kl.Count; i++)
            {
                if (!idx["keywords"].TryGetValue(kl[i], out var kfk)) { Console.Error.WriteLine($"ERROR traits.json: unknown keyword {kl[i]}"); Environment.Exit(1); }
                var d = new HasKeywordConditionData { RunOnType = Condition.RunOnType.CombatTarget };
                d.Keyword.Link.SetTo(kfk);
                var c = new ConditionFloat { CompareOperator = CompareOperator.EqualTo, ComparisonValue = 1, Data = d };
                extra.Add(i < kl.Count - 1 ? Or(c) : c);
            }
        }
        Condition[] Conds() => new Condition[] { GlobalIs(tGlobals[id], 1) }.Concat(extra.Select(c => c.DeepCopy())).ToArray();
        if (tn["damage"] is JsonNode dmg) Add($"AG_MGEF_Trait_{id}_Damage", nm, ActorValue.AttackDamageMult, dmg.GetValue<float>() / 100f, Conds());
        if (tn["armor"] is JsonNode arm) Add($"AG_MGEF_Trait_{id}_Armor", nm, ActorValue.DamageResist, arm.GetValue<float>(), Conds());
        if (tn["carry"] is JsonNode car) Add($"AG_MGEF_Trait_{id}_Carry", nm, ActorValue.CarryWeight, car.GetValue<float>(), Conds());
        if (tn["magicResist"] is JsonNode mr) Add($"AG_MGEF_Trait_{id}_MagicResist", nm, ActorValue.ResistMagic, mr.GetValue<float>(), Conds());
        if (tn["healing"] is JsonNode hl)
        {
            Add($"AG_MGEF_Trait_{id}_HealRate", nm, ActorValue.HealRateMult, hl.GetValue<float>(), Conds());
            Add($"AG_MGEF_Trait_{id}_Restoration", nm, ActorValue.RestorationModifier, hl.GetValue<float>(), Conds());
        }
        if (tn["magickaRegen"] is JsonNode mg) Add($"AG_MGEF_Trait_{id}_MagickaRate", nm, ActorValue.MagickaRateMult, mg.GetValue<float>(), Conds());
        if (tn["health"] is JsonNode hp) Add($"AG_MGEF_Trait_{id}_Health", nm, ActorValue.Health, hp.GetValue<float>(), Conds());
        if (tn["skillRate"] is JsonNode sr)
        {   // skills improve faster: vanilla's Well Rested pattern, an effect that applies a perk with Mod Skill Use x(1+rate).
            // The perk entry also checks the trait's global, so the bonus follows the switch even if the perk lingers.
            var perk = new Perk(FK(NextId()), Rel)
            {
                EditorID = $"AG_Perk_Trait_{id}_Skills", Name = nm, Playable = false, Hidden = true, NumRanks = 1,
            };
            var entry = new PerkEntryPointModifyValue
            {
                EntryPoint = APerkEntryPointEffect.EntryType.ModSkillUse, Modification = PerkEntryPointModifyValue.ModificationType.Multiply,
                Value = 1f + sr.GetValue<float>() / 100f, PerkConditionTabCount = 1,  // as vanilla: one tab (perk owner)
            };
            var tab = new PerkCondition { RunOnTabIndex = 0 };
            tab.Conditions.Add(GlobalIs(tGlobals[id], 1));
            entry.Conditions.Add(tab);
            perk.Effects.Add(entry);
            mod.Perks.Add(perk);
            var fx = Add($"AG_MGEF_Trait_{id}_Skills", nm, ActorValue.Health, 0f, Conds());
            fx.PerkToApply.SetTo(perk);
        }
    }
    mod.Spells.Add(spell);
    Console.WriteLine($"party blessing: {spell.Effects.Count} effects, {traits.Count} traits, FormIDs to 0x{nextFx - 1:X}");
}

// ---------- Missives (hard master): rank gating, rank labels, board manifest ----------
var missivesPath = args.Length > 2 ? args[2] : Environment.GetEnvironmentVariable("MISSIVES_ESP")
    ?? throw new ArgumentException("pass Missives.esp (2.03) as the third argument, or set MISSIVES_ESP");
var nextMissivesId = MissivesPatch.Apply(mod, missivesPath, outDir, gRank.FormKey, 0x900);
MissivesPatch.ApplyAddons(configDir, gRank.FormKey, addonGlobals.ToDictionary(kv => kv.Key, kv => kv.Value.FormKey));
// optional: refresh the manifest of "Missives - Voice and Quest Expansion" (the checked-in file is used otherwise)
if (Environment.GetEnvironmentVariable("MISSIVES_EXPANSION_ESP") is { Length: > 0 } expansionPath && File.Exists(expansionPath))
    MissivesPatch.Expansion(expansionPath, configDir);

// ---------- write ----------
mod.ModHeader.Stats.NextFormID = Math.Max(0x900u, nextMissivesId);
var path = Path.Combine(outDir, "AdventurersGuild.esp");
mod.WriteToBinary(path, new BinaryWriteParameters
{
    ModKey = ModKeyOption.CorrectToPath,
    MastersListContent = MastersListContentOption.Iterate,
    // masters in load order (Skyrim.esm first), not in the order records happen to reference them
    MastersListOrdering = new MastersListOrderingByLoadOrder(Probe.Masters.Select(m => ModKey.FromFileName(m)).Append(MissivesPatch.Missives).ToList()),
});
Console.WriteLine($"wrote {path}: {mod.Globals.Count} globals, {mod.Quests.Count} quests, {mod.DialogTopics.Count} topics, {mod.Books.Count} books");

// ---------- SEQ ----------
// Start-game-enabled quests that own dialogue must be listed in Data/SEQ/<plugin>.seq or their topics can
// fail to appear. Format (verified against a shipped .seq): uint32 FormIDs as stored in the plugin, i.e.
// top byte = the plugin's own index = its master count.
using (var written = SkyrimMod.CreateFromBinaryOverlay(path, Rel))
{
    var selfIndex = (uint)written.ModHeader.MasterReferences.Count;
    var seqDir = Path.Combine(outDir, "SEQ");
    Directory.CreateDirectory(seqDir);
    // Every start-game-enabled quest that owns a topic, derived from the plugin: v1.5.0 hard-coded only the guild
    // quest and the world-dialogue quest ran with none of its greetings or topics ever offered.
    var dialogueQuests = written.Quests
        .Where(q => q.FormKey.ModKey == modKey && q.Flags.HasFlag(Quest.Flag.StartGameEnabled)
                    && written.DialogTopics.Any(t => t.Quest.FormKey == q.FormKey))
        .Select(q => q.FormKey.ID).OrderBy(id => id).ToList();
    using var bw = new BinaryWriter(File.Create(Path.Combine(seqDir, "AdventurersGuild.seq")));
    foreach (var id in dialogueQuests) bw.Write((selfIndex << 24) | id);
    Console.WriteLine($"wrote SEQ/AdventurersGuild.seq: {string.Join(", ", dialogueQuests.Select(id => $"0x{id:X3}"))} (masters {selfIndex}: {string.Join(",", written.ModHeader.MasterReferences.Select(m => m.Master.FileName))})");
}
