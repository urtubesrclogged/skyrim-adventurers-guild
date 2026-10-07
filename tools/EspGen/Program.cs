// Generates AdventurersGuild.esp (a normal plugin: see the header-flag note below) and resolves the editor IDs named in the mod's json
// config against the vanilla masters. Any unknown ID fails the build.
//   dotnet run -- <outDir> [configDir] [Missives.esp path]   (Missives 2.03 is a hard master)
//   dotnet run -- --probe <factions|npcs|races|keywords|books|activators|locations|classes> [regex] [plugin]
// FormIDs are FIXED once released (saves reference them): never renumber, only append.
//   0x800-0x81F  globals, quests, dialogue branches/topics (0x812/0x813 About, 0x814/0x815 fee globals, 0x816-0x819 fee choice topics)
//   0x900-0x9FF  Missives note variants per rank (MissivesPatch.cs)
//   0xA00-0xBFF  dialogue INFOs, pinned per key in config/dialogue.ids.json
//   0x81F the party-member faction
//   0x810-0x81F  registration quest + missive; 0x81A the physical Guild Card (1.2.0), 0x81B-0x81E its replacement topic, fee and "missing" flag
//   0x8C0-0x8CF  world awareness: greetings quest/topics, retired-adventurer faction, recent-promotion global,
//                liaison faction (0x8C6) and reports-waiting global (0x8C7) for the SkyrimNet actions
//   0x8D0-0x8FF  party blessing: ability 0x8D0, Bond tier / members-present globals 0x8D1-0x8D2, one global per
//                trait from 0x8D3 (traits.json order, append only), then the effects of the first 8 traits
//   0xC80        the wandering-adventurer faction
//   0xC00-0xC7F  party traits 9+: their globals 0xC00-0xC0F (trait 9 = 0xC00), then their effects and perks
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
var gCardFee = Global(0x81D, "AG_CardFee", 25);            // a replacement guild card (the DLL sets it from guild.json)
Global(0x81E, "AG_CardMissingGlobal", 0);                  // 1 while a member carries no card (SkyrimNet action eligibility; DLL keeps it)

// ---------- MCM quest (SkyUI / MCM Helper wiring, structure unchanged from the proven Ranks quest) ----------
var cfgFk = FK(0x803);
mod.Quests.Add(new Quest(cfgFk, Rel)
{
    EditorID = "AG_ConfigQuest",
    Name = "Adventurers Guild Config",
    Flags = Quest.Flag.StartGameEnabled,
    Priority = 50,
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
// (voice files are named after them): existing keys keep their ID, new keys get the next free ID >= 0xA00.
var dlgPath = Path.GetFullPath(Path.Combine(configDir, "../../../dialogue.json"));
var idsPath = Path.GetFullPath(Path.Combine(configDir, "../../../dialogue.ids.json"));
var dlg = JsonNode.Parse(File.ReadAllText(dlgPath), documentOptions: new JsonDocumentOptions { CommentHandling = JsonCommentHandling.Skip, AllowTrailingCommas = true })!;
var ids = File.Exists(idsPath)
    ? JsonSerializer.Deserialize<SortedDictionary<string, string>>(File.ReadAllText(idsPath))!
    : new SortedDictionary<string, string>();
uint nextId = Math.Max(0xA00u, ids.Values.Select(v => Convert.ToUInt32(v, 16) + 1).DefaultIfEmpty(0xA00u).Max());
uint InfoId(string key)
{
    if (!ids.TryGetValue(key, out var hex)) { hex = $"0x{nextId++:X3}"; ids[key] = hex; }
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
var roles = new Dictionary<string, List<string>> { ["register"] = new(), ["promote"] = new(), ["business"] = new(), ["replace"] = new() };
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
        void Add(string k, string[] ls, IEnumerable<Condition> extra)
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
        }
        // the player's rank picks the line (highest first; the plain line is E-D)
        if (role == "business" && l["businessByRank"] is JsonObject byRank)
            foreach (var r in new[] { "S", "A", "B", "C" })
                if (byRank[r] is JsonNode t)
                    Add($"{key}:{r}", new[] { t.GetValue<string>() }, new Condition[] { GlobalCmp(gRank, CompareOperator.EqualTo, "EDCBAS".IndexOf(r)) });
        // a vanilla quest's completion changes what they say (Thoring and Waking Nightmare)
        if (l["afterQuest"] is JsonObject after && after[role] is JsonNode an)
        {
            var als = an is JsonArray aa ? aa.Select(x => x!.GetValue<string>()).ToArray() : new[] { an.GetValue<string>() };
            Add($"{key}:after", als, new Condition[] { QuestDone(after["quest"]!.GetValue<string>(), true) });
        }
        Add(key, lines, Array.Empty<Condition>());
    }
    if (fee is not null)
    {
        var poor = AnyLiaison();
        poor.Add(Gold(fee, false));
        Info(pay ?? topic, $"{role}:nofee", new[] { Line("nofee") }, false, poor);
        if (later is not null) Info(later, $"{role}:later", new[] { Line("later") }, false, AnyLiaison());
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
        Info(topic, $"{role}:generic", new[] { dlg["generic"]!.GetValue<string>() }, false, new Condition[] { InFaction(Skyrim.Faction.JobInnkeeperFaction.FormKey) });
    }
    mod.DialogTopics.Add(topic);
    if (pay is not null) mod.DialogTopics.Add(pay);
    if (later is not null) mod.DialogTopics.Add(later);
}
var liaisonCities = new Dictionary<string, string>();
var successors = new List<object>();
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
    if (ln["who"] is JsonNode who) { conds.Add(IsNpc(Npc(who.GetValue<string>()), false)); kind = "npc"; }
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
    var status = ln["status"]?.GetValue<string>() ?? "registered";
    if (status != "any") conds.Add(GlobalIs(gRegistered, status == "unregistered" ? 0 : 1));  // "any": registered or not
    if (ln["rank"] is JsonNode rk) conds.AddRange(RankConds(rk.GetValue<string>()));

    if (ln["topic"] is JsonNode prompt)  // a player topic (Ysolda's), not a greeting
    {
        // one player topic per NPC: branch and topic FormIDs are fixed here (append only)
        var whoId = ln["who"]!.GetValue<string>();
        var (branchId, topicId) = whoId switch { "Ysolda" => (0x8C2u, 0x8C3u), "Sinmir" => (0x8C8u, 0x8C9u), "Uthgerd" => (0x8CAu, 0x8CBu),
            "Mjoll" => (0x8CCu, 0x8CDu), "Annekke" => (0x8CEu, 0x8CFu), _ => (0u, 0u) };
        if (branchId == 0) { Console.Error.WriteLine($"ERROR world_dialogue.json: no topic FormIDs assigned for '{whoId}' (tools/EspGen/Program.cs)"); errors++; continue; }
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
        worldCount++;
        continue;
    }
    conds.Add(Chance(ln["chance"]?.GetValue<int>() ?? chance[kind]!.GetValue<int>()));
    conds.AddRange(voices);  // the OR group last, so it stands alone
    var info = new DialogResponses(FK(InfoId("world:" + id)), Rel)
    {
        EditorID = "AG_Info_world_" + id,
        Flags = new DialogResponseFlags { Flags = DialogResponses.Flag.Random, ResetHours = kind == "npc" ? 24f : 6f },
    };
    info.Responses.Add(new DialogResponse { Text = text, Emotion = Emotion.Neutral, EmotionValue = 50, ResponseNumber = 1 });
    foreach (var c in conds) info.Conditions.Add(c);
    hello.Responses.Add(info);
    worldCount++;
}
mod.DialogTopics.Add(hello);
Console.WriteLine($"world dialogue: {worldCount} lines");

File.WriteAllText(idsPath, JsonSerializer.Serialize(ids, new JsonSerializerOptions { WriteIndented = true }));
// ---------- threat safety net: the level each creature race has at its weakest in the unmodded game ----------
// A threat rank is a level band, and overhauls change levels (a giant set to level 5 would read rank E). The DLL
// never ranks a creature below what its race's weakest vanilla encounter variant gets: this lists that level per
// race. Only the game's own encounter actors (editor ID "Enc...", their own stats, a fixed level) are read, and
// only races that are not people. Level 12 and up only: below that the floor would be rank E, which is no floor.
{
    var races = masters.SelectMany(m => m.Races).GroupBy(r => r.FormKey).ToDictionary(g => g.Key, g => g.Last());
    var npcKw = idx["keywords"].TryGetValue("ActorTypeNPC", out var nk) ? nk : FormKey.Null;
    var weakest = new SortedDictionary<string, (int level, string edid, string from)>();
    foreach (var n in masters.SelectMany(m => m.Npcs).GroupBy(n => n.FormKey).Select(g => g.Last()))
    {
        var edid = n.EditorID ?? "";
        if (!System.Text.RegularExpressions.Regex.IsMatch(edid, @"^(DLC\d)?Enc") || edid.Contains("Test")) continue;
        if (n.Configuration.Level is not INpcLevelGetter fixedLevel) continue;                       // scales with the player
        if (!n.Template.IsNull && n.Configuration.TemplateFlags.HasFlag(NpcConfiguration.TemplateFlag.Stats)) continue;  // not its own level
        if (!races.TryGetValue(n.Race.FormKey, out var race)) continue;
        if (race.Keywords?.Any(k => k.FormKey == npcKw) == true) continue;                            // people
        var key = Key(race.FormKey);
        if (!weakest.TryGetValue(key, out var have) || fixedLevel.Level < have.level) weakest[key] = (fixedLevel.Level, race.EditorID ?? "", edid);
    }
    // threat.json: the author's corrections where level and danger part ways (a giant against a mammoth)
    var judged = ReadConfig("threat")["races"]?.AsObject() ?? new JsonObject();
    var byRace = new Dictionary<string, (string? atLeast, string? atMost)>();
    foreach (var (edid, node) in judged)
    {
        if (!idx["races"].TryGetValue(edid, out var rfk)) { Console.Error.WriteLine($"ERROR threat.json: unknown race '{edid}'"); errors++; continue; }
        byRace[Key(rfk)] = (node!["atLeast"]?.GetValue<string>(), node["atMost"]?.GetValue<string>());
        if (!weakest.ContainsKey(Key(rfk))) weakest[Key(rfk)] = (0, edid, "threat.json");
    }
    var floors = weakest.Where(kv => kv.Value.level >= 12 || byRace.ContainsKey(kv.Key)).Select(kv => new
    {
        race = kv.Key, name = kv.Value.edid, level = kv.Value.level, from = kv.Value.from,
        atLeast = byRace.TryGetValue(kv.Key, out var j1) ? j1.atLeast : null,
        atMost = byRace.TryGetValue(kv.Key, out var j2) ? j2.atMost : null,
    }).ToList();
    File.WriteAllText(Path.Combine(outDir, "threat.resolved.json"), JsonSerializer.Serialize(new
    {
        _comment = "Threat safety net: a creature of this race is never ranked as if it were below this level (its weakest encounter variant in the unmodded game, named in 'from'). Level and toughness can still rank it higher. atLeast / atMost (rank letters, from threat.json) are judgement calls where level and danger part ways: never below / never above that rank by level. Edit or delete a line as you like. [Threat] RaceFloors = 0 in AdventurersGuild.ini turns all of it off.",
        floors,
    }, new JsonSerializerOptions { WriteIndented = true, DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull }));
    Console.WriteLine($"threat floors: {floors.Count} creature races (of {weakest.Count} with encounter actors)");
}
File.WriteAllText(Path.Combine(outDir, "dialogue.resolved.json"), JsonSerializer.Serialize(new { roles, liaisons = liaisonKeys, cities = liaisonCities, successors }, new JsonSerializerOptions { WriteIndented = true }));
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
            LogEntries = { new QuestLogEntry { Entry = "The missive board only takes work from registered adventurers. The innkeeper of any hold capital can sign me up with the Adventurers Guild." } },
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
var note = new Book(FK(0x811), Rel)
{
    EditorID = "AG_RegistrationMissive",
    Name = "Missive: Register with the Adventurers Guild",
    Model = noteSrc.Model?.DeepCopy(),
    ObjectBounds = noteSrc.ObjectBounds?.DeepCopy(),
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
var card = new Book(FK(0x81A), Rel)
{
    EditorID = "AG_GuildCard",
    Name = "Adventurers Guild Card",
    Model = noteSrc.Model?.DeepCopy(),
    ObjectBounds = noteSrc.ObjectBounds?.DeepCopy(),
    PickUpSound = noteSrc.PickUpSound is { } cpu ? new FormLinkNullable<ISoundDescriptorGetter>(cpu.FormKey) : null,
    PutDownSound = noteSrc.PutDownSound is { } cpd ? new FormLinkNullable<ISoundDescriptorGetter>(cpd.FormKey) : null,
    InventoryArt = noteSrc.InventoryArt is { } cia ? new FormLinkNullable<IStaticGetter>(cia.FormKey) : null,
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
        0 => "You read an adventurer's guild rank and a foe's threat rank at a glance.",
        1 => $"You read ranks at a glance and know what spoils are worth: merchants pay {sellBonus[1]}% more, and trophies earn more Merit.",
        _ => $"Nothing escapes your eye, not even a hidden rank. Merchants pay {sellBonus[2]}% more, and trophies earn much more Merit.",
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
