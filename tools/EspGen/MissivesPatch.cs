using System.Text.Json;
using System.Text.RegularExpressions;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Skyrim;

// Missives 2.03 integration. AdventurersGuild.esp does NOT override any Missives record: other Missives patches (e.g.
// "Quest Edits for Unique Missive Boards", Bounties Redone) edit the same 264 quests, and an override copied from
// Missives.esp would silently undo them whenever this plugin loads later. Instead EspGen writes missives.json and
// AdventurersGuild.dll (MissiveWatch) applies the integration in memory at data load, on top of whichever version of
// each quest won the load order:
//
// Gating: Missives' own board script (_M_ActivatorScript.UpdateQuests) calls Quest.Start() and handles a failed start
// gracefully (logs, retries next refresh). The DLL puts "AG_PlayerRankGlobal >= rank" first on one of the quest's
// non-Optional conditioned aliases, so the quest cannot start below that guild rank (-1 before registering).
//
// Labels: the DLL appends " [Rank X]" to each quest's name (journal) and to the missive notes. Only 25 distinct Book
// records exist for 264 quests; 22 belong to one rank. The other 3 (CourierLetter/Potion/Weapon) are shared across
// ranks E/D/C: the original note is labeled for its lowest rank and NEW book variants (our own records, cloned field
// by field here) carry the higher ranks; the DLL points a quest's "Missive" alias at its rank's variant, but only
// while that alias still creates the original Missives note (a patch that changed the note is left alone).
static class MissivesPatch
{
    public const string MissivesVersion = "2.03";  // confirmed via tools/nexus.sh mod 17576
    public static readonly ModKey Missives = ModKey.FromNameAndExtension("Missives.esp");

    // Low=E(0), Med=D(1), High=C(2), VeryHigh=B(3). A and S get no Missives content (decided with the user).
    static readonly Dictionary<string, (int rank, char letter)> TierRank = new()
    {
        ["Low"] = (0, 'E'), ["Med"] = (1, 'D'), ["High"] = (2, 'C'), ["VeryHigh"] = (3, 'B'),
    };
    static char Letter(int r) => "EDCB"[r];

    // Missives add-ons the Guild knows (Missives - Worldspace Additions, Nexus 26788): the plugin, and the global the
    // DLL sets to 1 while it is loaded (dialogue reads it: Geldis Sadri and the Raven Rock board).
    public static readonly (string plugin, string global)[] Addons = { ("Missives - Solstheim.esp", "AG_MissivesSolstheimGlobal") };
    // Missives' own notes by rank, from Apply(): (note, rank) -> the note to use (the original, or our rank variant)
    static readonly Dictionary<(FormKey book, int rank), FormKey> NoteVariant = new();

    /// An add-on brings its own quests, sorted into "_M_ListQuests<Region><Tier>" lists like Missives' own. Nothing of
    /// it is copied or overridden: this writes the same kind of manifest (FormIDs and ranks) for the DLL, which applies
    /// it only while the add-on is loaded. The add-on's plugin is needed at BUILD time only (MISSIVES_ADDONS: folders
    /// to look in, separated by ';'); without it the manifest in config/ is left as it is.
    public static void ApplyAddons(string configDir, FormKey rankGlobal, IReadOnlyDictionary<string, FormKey> globals)
    {
        var rel = SkyrimRelease.SkyrimSE;
        var dirs = (Environment.GetEnvironmentVariable("MISSIVES_ADDONS") ?? "").Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        var path = Path.Combine(configDir, "missives.addons.json");
        var listNameRe = new Regex(@"^_M_ListQuests([A-Za-z]+?)(Low|Med|High|VeryHigh)$");
        var addons = new List<object>();
        foreach (var (plugin, global) in Addons)
        {
            var file = dirs.Select(d => Path.Combine(d, plugin)).FirstOrDefault(File.Exists);
            if (file is null) { Console.WriteLine($"Missives add-on {plugin}: not found (MISSIVES_ADDONS) - {path} left as it is"); return; }
            var addon = SkyrimMod.CreateFromBinaryOverlay(file, rel);
            var quests = new List<object>();
            var ownNotes = new Dictionary<FormKey, SortedSet<int>>();
            int gateable = 0, reused = 0, unlabeled = 0;
            foreach (var list in addon.FormLists)
            {
                var m = listNameRe.Match(list.EditorID ?? "");
                if (!m.Success) continue;
                var (rank, letter) = TierRank[m.Groups[2].Value];
                foreach (var item in list.Items)
                {
                    if (item.FormKey.ModKey != addon.ModKey) { reused++; continue; }   // one of Missives' own: already in missives.json
                    var q = addon.Quests.FirstOrDefault(x => x.FormKey == item.FormKey);
                    if (q is null) { Console.WriteLine($"WARNING {plugin}: quest {item.FormKey} is listed but not defined - skipped"); continue; }
                    if (q.Aliases.Any(a => a.Conditions.Count > 0 && !(a.Flags?.HasFlag(QuestAlias.Flag.Optional) ?? false))) gateable++;
                    else Console.WriteLine($"WARNING {plugin}: {q.EditorID} has no gateable alias");
                    string? noteFrom = null, noteTo = null;
                    var note = q.Aliases.FirstOrDefault(a => a.Name == "Missive" && a.CreateReferenceToObject is not null)?.CreateReferenceToObject!.Object.FormKey;
                    if (note is FormKey nk)
                    {
                        if (nk.ModKey == addon.ModKey) { if (!ownNotes.TryGetValue(nk, out var rs)) ownNotes[nk] = rs = new(); rs.Add(rank); }
                        else if (NoteVariant.TryGetValue((nk, rank), out var use)) { if (use != nk) { noteFrom = $"0x{nk.ID:X6}"; noteTo = $"0x{use.ID:X6}"; } }
                        else { unlabeled++; Console.WriteLine($"WARNING {plugin}: {q.EditorID} (rank {letter}) uses a Missives note that has no rank {letter} label"); }
                    }
                    quests.Add(new { formId = $"0x{item.FormKey.ID:X6}", tier = letter.ToString(), hold = m.Groups[1].Value, noteFrom, noteTo });
                }
            }
            foreach (var (nk, rs) in ownNotes.Where(kv => kv.Value.Count > 1))
                Console.WriteLine($"WARNING {plugin}: its note {nk} serves ranks {string.Join(",", rs.Select(Letter))} - labeled for the lowest");
            var books = ownNotes.Select(kv => new { formId = $"0x{kv.Key.ID:X6}", tier = Letter(kv.Value.Min).ToString() }).ToList();
            var boards = addon.Containers.Where(c => (c.EditorID ?? "").StartsWith("_M_MissiveBoard")).Select(c => $"0x{c.FormKey.ID:X6}").ToList();
            var triggers = addon.Activators.Where(a => (a.EditorID ?? "").StartsWith("_M_ActivatorBoard")).Select(a => $"0x{a.FormKey.ID:X6}").ToList();
            addons.Add(new { plugin, global = $"0x{globals[global].ID:X6}", rankGlobal = $"0x{rankGlobal.ID:X6}", quests, books, boardTriggers = triggers, boardContainers = boards });
            Console.WriteLine($"Missives add-on {plugin}: {quests.Count} quests ({gateable} gateable, {reused} of Missives' own reused), {books.Count} notes of its own, " +
                              $"{boards.Count} board container(s), {unlabeled} notes without a label");
        }
        File.WriteAllText(path, JsonSerializer.Serialize(new
        {
            _comment = "Missives add-ons (Missives - Worldspace Additions): each one's quests with the guild rank of its difficulty list, its own notes and its board. Generated by tools/EspGen from the add-on's plugin; AdventurersGuild.dll applies an entry only while that plugin is loaded. FormIDs are local to the add-on (noteTo: to AdventurersGuild.esp).",
            addons,
        }, new JsonSerializerOptions { WriteIndented = true, DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull }));
        Console.WriteLine($"wrote {path}");
    }

    /// "Missives for the Good Guys" (Nexus 98373, by Lizzy of the Wildlander Team; taken in with its author's permission):
    /// some 450 new missives in two plugins. It does not put them in Missives' per-hold lists in its plugins: SkyPatcher
    /// adds them at load, from SKSE/Plugins/Skypatcher/formList/MFTGG_Formlists.ini. So this reads that file, finds
    /// which "_M_ListQuests<Hold><Tier>" list (Missives', or Missives - Solstheim's) each line fills, and gives each new
    /// quest the rank of the lowest list it is in, as Missives' own. It also overrides 291 of Missives' quests (its
    /// bug fixes): those are already in missives.json, and the DLL gates whichever version wins. Writes
    /// missives_goodguys.json; nothing of the mod is mastered, copied or overridden. Run when the mod updates (set
    /// MISSIVES_GOODGUYS in local.env to its folder).
    public static void GoodGuys(string folder, string missivesPath, string configDir)
    {
        var rel = SkyrimRelease.SkyrimSE;
        var plugins = new[] { "MissivesforTheGoodGuys.esp", "MissivesforTheGoodGuysPart2.esp" }
            .Select(p => SkyrimMod.CreateFromBinaryOverlay(Path.Combine(folder, p), rel)).ToList();
        var ini = Path.Combine(folder, "SKSE", "Plugins", "Skypatcher", "formList", "MFTGG_Formlists.ini");
        var listNameRe = new Regex(@"^_M_ListQuests([A-Za-z]+?)(Low|Med|High|VeryHigh)$");
        // the lists a line may fill, by "plugin|local id": Missives' own, and Missives - Solstheim's when it is at hand
        var lists = new Dictionary<string, (string hold, int rank)>(StringComparer.OrdinalIgnoreCase);
        var ownRank = new Dictionary<FormKey, int>();  // Missives' own quests (and Solstheim's): the lowest list each is in
        void Lowest(Dictionary<FormKey, int> d, FormKey k, int r) => d[k] = d.TryGetValue(k, out var have) ? Math.Min(have, r) : r;
        void Lists(ISkyrimModGetter m)
        {
            foreach (var l in m.FormLists)
                if (listNameRe.Match(l.EditorID ?? "") is { Success: true } lm)
                {
                    var r = TierRank[lm.Groups[2].Value].rank;
                    lists[$"{m.ModKey.FileName}|{l.FormKey.ID:X}"] = (lm.Groups[1].Value, r);
                    foreach (var it in l.Items) Lowest(ownRank, it.FormKey, r);
                }
        }
        Lists(SkyrimMod.CreateFromBinaryOverlay(missivesPath, rel));
        var dirs = (Environment.GetEnvironmentVariable("MISSIVES_ADDONS") ?? "").Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        if (dirs.Select(d => Path.Combine(d, "Missives - Solstheim.esp")).FirstOrDefault(File.Exists) is string sol) Lists(SkyrimMod.CreateFromBinaryOverlay(sol, rel));
        else Console.WriteLine("Missives for the Good Guys: Missives - Solstheim.esp not found (MISSIVES_ADDONS) - its Solstheim missives are left out");

        var quests = plugins.SelectMany(p => p.Quests).Where(q => plugins.Any(p => p.ModKey == q.FormKey.ModKey)).ToDictionary(q => q.FormKey);
        var questAt = new Dictionary<FormKey, (string hold, int rank)>();
        int lines = 0, otherLists = 0, notOurs = 0;
        var lineRe = new Regex(@"^\s*filterByFormLists\s*=\s*([^|:]+)\|0x([0-9A-Fa-f]+)\s*:\s*formsToAdd\s*=\s*(.*)$");
        var formRe = new Regex(@"([^,|]+?\.es[pml])\|0x([0-9A-Fa-f]+)", RegexOptions.IgnoreCase);
        foreach (var line in File.ReadLines(ini))
        {
            var m = lineRe.Match(line);
            if (!m.Success) continue;
            lines++;
            if (!lists.TryGetValue($"{m.Groups[1].Value.Trim()}|{Convert.ToUInt32(m.Groups[2].Value, 16):X}", out var at)) { otherLists++; continue; }  // e.g. Raise Disposition's
            foreach (Match f in formRe.Matches(m.Groups[3].Value))
            {
                var fk = new FormKey(ModKey.FromFileName(f.Groups[1].Value.Trim()), Convert.ToUInt32(f.Groups[2].Value, 16));
                if (!quests.ContainsKey(fk)) { notOurs++; Lowest(ownRank, fk, at.rank); continue; }   // one of Missives' own (already in missives.json), or not a quest
                questAt[fk] = questAt.TryGetValue(fk, out var have) && have.rank <= at.rank ? have : at;
            }
        }

        string K(FormKey fk) => $"{fk.ModKey.FileName}|0x{fk.ID:X6}";
        var bookRanks = new SortedDictionary<string, SortedSet<int>>();
        var outQuests = new List<object>();
        int gateable = 0, retarget = 0;
        foreach (var (fk, at) in questAt.OrderBy(kv => kv.Key.ModKey.FileName.String).ThenBy(kv => kv.Key.ID))
        {
            var q = quests[fk];
            if (q.Aliases.Any(a => a.Conditions.Count > 0 && !(a.Flags?.HasFlag(QuestAlias.Flag.Optional) ?? false))) gateable++;
            else Console.WriteLine($"WARNING Missives for the Good Guys: {q.EditorID} has no gateable alias");
            string? noteFrom = null, noteTo = null;
            if (q.Aliases.FirstOrDefault(a => a.Name == "Missive" && a.CreateReferenceToObject is not null)?.CreateReferenceToObject!.Object.FormKey is FormKey nk)
            {
                if (nk.ModKey == Missives)
                {   // one of Missives' notes: its rank variant, as for Missives' own quests
                    if (NoteVariant.TryGetValue((nk, at.rank), out var use) && use != nk) { noteFrom = $"0x{nk.ID:X6}"; noteTo = $"0x{use.ID:X6}"; retarget++; }
                }
                else { if (!bookRanks.TryGetValue(K(nk), out var set)) bookRanks[K(nk)] = set = new(); set.Add(at.rank); }
            }
            outQuests.Add(new { form = K(fk), tier = Letter(at.rank).ToString(), hold = at.hold, noteFrom, noteTo, editorId = q.EditorID });
        }
        // a note used at one rank is labeled; a shared one is left as the mod wrote it (the quest still shows its rank)
        var books = bookRanks.Where(kv => kv.Value.Count == 1).Select(kv => new { form = kv.Key, tier = Letter(kv.Value.Min).ToString() }).ToList();
        // Most of its missives (and the Missives ones it rewrites) title their note at run time from a Message (the quest
        // script's m_Message, mostly in MissivesSharedResources.esp: "Miner Needed: Collect and Deliver 11 Iron Ore to
        // Falkreath"), not from the note's own name: those messages get the label too, each used at one rank. Not
        // _m_ItemName, which some of its scripts also have: that one names the item asked for, not the note.
        var msgRanks = new SortedDictionary<string, SortedSet<int>>();
        int titled = 0;
        foreach (var q in plugins.SelectMany(p => p.Quests))
        {
            int r;
            if (questAt.TryGetValue(q.FormKey, out var qa)) r = qa.rank;
            else if (ownRank.TryGetValue(q.FormKey, out var orr)) r = orr;
            else continue;  // on no board's list
            var msgs = (q.VirtualMachineAdapter?.Scripts ?? Enumerable.Empty<IScriptEntryGetter>())
                .SelectMany(s => s.Properties).OfType<IScriptObjectPropertyGetter>()
                .Where(p => p.Name.Equals("m_Message", StringComparison.OrdinalIgnoreCase))
                .Select(p => p.Object.FormKey).Where(k => !k.IsNull).Distinct().ToList();
            if (msgs.Count > 0) titled++;
            foreach (var k in msgs) { if (!msgRanks.TryGetValue(K(k), out var set)) msgRanks[K(k)] = set = new(); set.Add(r); }
        }
        var messages = msgRanks.Where(kv => kv.Value.Count == 1).Select(kv => new { form = kv.Key, tier = Letter(kv.Value.Min).ToString() }).ToList();
        var outPath = Path.Combine(configDir, "missives_goodguys.json");
        File.WriteAllText(outPath, JsonSerializer.Serialize(new
        {
            _comment = "Missives for the Good Guys (Nexus 98373, by Lizzy of the Wildlander Team; taken in with its author's permission): its missives with the Guild rank of the Missives difficulty list SkyPatcher puts each in (Low E, Med D, High C), generated by tools/EspGen from its plugins and MFTGG_Formlists.ini (see MissivesPatch.GoodGuys). Read only when MissivesforTheGoodGuys.esp is loaded; nothing of it is mastered, copied or shipped. noteFrom/noteTo: a Missives note swapped for its rank variant in AdventurersGuild.esp. The editor IDs are for reading only.",
            plugin = "MissivesforTheGoodGuys.esp", tag = "MFTGG", quests = outQuests, books, messages,
        }, new JsonSerializerOptions { WriteIndented = true, DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull }));
        Console.WriteLine($"Missives for the Good Guys: {lines} list lines ({otherLists} for other lists), {questAt.Count} missives ({gateable} gateable; " +
                          $"{string.Join(" ", questAt.GroupBy(kv => Letter(kv.Value.rank)).OrderBy(g => "EDCB".IndexOf(g.Key)).Select(g => g.Key + ":" + g.Count()))}), " +
                          $"{notOurs} entries not its own, {books.Count} of {bookRanks.Count} notes labeled, {messages.Count} of {msgRanks.Count} title messages labeled ({titled} quests titled by one), {retarget} Missives notes swapped -> {outPath}");
    }

    /// "Missives - Voice and Quest Expansion" (Nexus 166094, MissivesExpansion.esp): 20 more missive types. It overrides
    /// Missives' per-hold lists to add a WRAPPER quest per type (script _ME_QuestBoard), which sets the hold and starts
    /// the real quest (property QuestToStart; its note is QuestToStartMissive). One real quest serves every hold. This
    /// writes missives_expansion.json for the DLL: each real quest with the rank of the lowest list its wrapper is in,
    /// and each note that belongs to one rank. Nothing of the expansion is mastered or overridden: the file is data,
    /// read only when the plugin is loaded. Run when the expansion updates (set MISSIVES_EXPANSION_ESP in local.env).
    public static void Expansion(string path, string configDir)
    {
        var exp = SkyrimMod.CreateFromBinaryOverlay(path, SkyrimRelease.SkyrimSE);
        var listNameRe = new Regex(@"^_M_ListQuests([A-Za-z]+?)(Low|Med|High|VeryHigh)$");
        var wrappers = exp.Quests.ToDictionary(q => q.FormKey);
        var questRank = new SortedDictionary<string, int>();                 // real quest key -> lowest rank
        var bookRanks = new SortedDictionary<string, SortedSet<int>>();      // note key -> ranks it is used at
        string K(FormKey fk) => $"{fk.ModKey.FileName}|0x{fk.ID:X6}";
        foreach (var list in exp.FormLists)
        {
            var m = listNameRe.Match(list.EditorID ?? "");
            if (!m.Success) continue;
            var rank = TierRank[m.Groups[2].Value].rank;
            foreach (var item in list.Items.Where(i => i.FormKey.ModKey == exp.ModKey))
            {
                if (!wrappers.TryGetValue(item.FormKey, out var w)) continue;
                var props = w.VirtualMachineAdapter?.Scripts.SelectMany(s => s.Properties).OfType<IScriptObjectPropertyGetter>().ToList() ?? new();
                var real = props.FirstOrDefault(p => p.Name == "QuestToStart")?.Object.FormKey;
                if (real is null || real.Value.IsNull) { Console.WriteLine($"WARNING: expansion list entry {w.EditorID} has no QuestToStart - skipped"); continue; }
                var rk = K(real.Value);
                questRank[rk] = questRank.TryGetValue(rk, out var have) ? Math.Min(have, rank) : rank;
                var note = props.FirstOrDefault(p => p.Name == "QuestToStartMissive")?.Object.FormKey;
                if (note is { IsNull: false } n) { if (!bookRanks.TryGetValue(K(n), out var set)) bookRanks[K(n)] = set = new(); set.Add(rank); }
            }
        }
        var quests = questRank.Select(kv => new { form = kv.Key, tier = Letter(kv.Value).ToString() }).ToList();
        // a note used at one rank is labeled; a shared one is left as the expansion wrote it (the quest still shows its rank)
        var books = bookRanks.Where(kv => kv.Value.Count == 1).Select(kv => new { form = kv.Key, tier = Letter(kv.Value.Min).ToString() }).ToList();
        var outPath = Path.Combine(configDir, "missives_expansion.json");
        File.WriteAllText(outPath, JsonSerializer.Serialize(new
        {
            _comment = "Missives - Voice and Quest Expansion (Nexus 166094): its missives with the Guild rank each needs, generated by tools/EspGen from the plugin (see MissivesPatch.Expansion). Read only when MissivesExpansion.esp is loaded.",
            plugin = exp.ModKey.FileName.String, tag = "VQE", quests, books,
        }, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine($"Missives expansion: {quests.Count} missives, {books.Count} notes to label ({string.Join(" ", quests.GroupBy(q => q.tier).OrderBy(g => g.Key).Select(g => g.Key + ":" + g.Count()))}) -> {outPath}");
    }

    /// Adds the Missives overrides and rank-variant notes to <paramref name="mod"/>; new books take FormIDs from
    /// <paramref name="nextBookId"/> up. Writes missives.json to <paramref name="outDir"/>. Returns the next free id.
    public static uint Apply(SkyrimMod mod, string missivesPath, string outDir, FormKey rankGlobal, uint nextBookId)
    {
        var rel = SkyrimRelease.SkyrimSE;
        var missives = SkyrimMod.CreateFromBinaryOverlay(missivesPath, rel);
        Console.WriteLine($"Missives: {missives.Quests.Count} quests, {missives.FormLists.Count} formlists ({missivesPath})");

        // FormKey -> tier/hold from the 36 "_M_ListQuests<Hold><Tier>" FormLists. Deliberately NOT parsed from quest
        // EditorIDs: 93 of 264 quest types (Kill/Track/Retrieve/GatherInn) don't suffix their own name with a tier.
        var listNameRe = new Regex(@"^_M_ListQuests([A-Za-z]+?)(Low|Med|High|VeryHigh)$");
        var questTier = new Dictionary<FormKey, (int rank, char letter, string tierName)>();
        var questHold = new Dictionary<FormKey, string>();
        foreach (var list in missives.FormLists)
        {
            var m = listNameRe.Match(list.EditorID ?? "");
            if (!m.Success) continue;
            var (rank, letter) = TierRank[m.Groups[2].Value];
            foreach (var item in list.Items)
            {
                if (questTier.ContainsKey(item.FormKey))
                {
                    Console.WriteLine($"WARNING: {item.FormKey} appears in more than one tier list - keeping the first");
                    continue;
                }
                questTier[item.FormKey] = (rank, letter, m.Groups[2].Value);
                questHold[item.FormKey] = m.Groups[1].Value;
            }
        }

        // ---- pass 1: which note each quest's "Missive" alias creates (read from Missives.esp, nothing overridden)
        var noteByQuest = new Dictionary<FormKey, FormKey>();
        int gateable = 0, missing = 0;
        foreach (var (formKey, (rank, letter, tierName)) in questTier)
        {
            var source = missives.Quests.FirstOrDefault(q => q.FormKey == formKey);
            if (source is null) { Console.WriteLine($"WARNING: quest {formKey} not found in Missives.esp - skipped"); missing++; continue; }
            var missiveAlias = source.Aliases.FirstOrDefault(a => a.Name == "Missive" && a.CreateReferenceToObject is not null);
            if (missiveAlias is not null) noteByQuest[formKey] = missiveAlias.CreateReferenceToObject!.Object.FormKey;
            if (source.Aliases.Any(a => a.Conditions.Count > 0 && !(a.Flags?.HasFlag(QuestAlias.Flag.Optional) ?? false))) gateable++;
            else Console.WriteLine($"WARNING: {source.EditorID} ({tierName}) has no gateable alias in Missives.esp");
        }
        Console.WriteLine($"Missives pass 1: {gateable} of {questTier.Count} quests gateable, {missing} missing");

        // ---- pass 2: note labels, and per-rank variants of the notes shared across ranks
        var bookLabels = new List<object>();
        var retarget = new Dictionary<FormKey, (FormKey from, FormKey to)>();
        int cloned = 0;
        foreach (var group in noteByQuest
                     .Select(kv => (quest: kv.Key, book: kv.Value, rank: questTier[kv.Key].rank))
                     .GroupBy(x => x.book))
        {
            var source = missives.Books.FirstOrDefault(b => b.FormKey == group.Key);
            if (source is null) { Console.WriteLine($"WARNING: book {group.Key} not in Missives.esp - skipped"); continue; }
            var ranks = group.Select(x => x.rank).Distinct().OrderBy(r => r).ToList();
            var baseName = source.Name?.String ?? source.EditorID ?? group.Key.ToString();
            bookLabels.Add(new { formId = $"0x{group.Key.ID:X6}", tier = Letter(ranks[0]).ToString() });
            NoteVariant[(group.Key, ranks[0])] = group.Key;
            if (ranks.Count == 1) continue;
            var variant = new Dictionary<int, FormKey> { [ranks[0]] = group.Key };
            foreach (var rank in ranks.Skip(1))
            {
                if (nextBookId > 0x9FF) throw new InvalidOperationException($"Missives note variants overflow 0x900-0x9FF (light-plugin range): 0x{nextBookId:X}");
                var clone = new Book(new FormKey(mod.ModKey, nextBookId++), rel)
                {
                    EditorID = $"AG_{source.EditorID}_Rank{Letter(rank)}",
                    Name = baseName + $" [Rank {Letter(rank)}]",
                    Model = source.Model?.DeepCopy(),
                    BookText = source.BookText.DeepCopy(),
                    PickUpSound = source.PickUpSound is { } pu ? new FormLinkNullable<ISoundDescriptorGetter>(pu.FormKey) : null,
                    PutDownSound = source.PutDownSound is { } pd ? new FormLinkNullable<ISoundDescriptorGetter>(pd.FormKey) : null,
                    Flags = source.Flags,
                    Type = source.Type,
                    Teaches = source.Teaches?.DeepCopy(),
                    Value = source.Value,
                    Weight = source.Weight,
                    InventoryArt = source.InventoryArt is { } ia ? new FormLinkNullable<IStaticGetter>(ia.FormKey) : null,
                    Description = source.Description.DeepCopy(),
                    // Missives' own notes have no size (all zeros), and an item with no size goes through the floor when
                    // dropped (Program.cs, PaperBounds): the copy is given a sheet of paper's unless the original has one
                    ObjectBounds = source.ObjectBounds is { } ob && (ob.First.X != 0 || ob.First.Y != 0 || ob.First.Z != 0 || ob.Second.X != 0 || ob.Second.Y != 0 || ob.Second.Z != 0)
                        ? ob.DeepCopy()
                        : new ObjectBounds { First = new Noggog.P3Int16(-8, -5, 0), Second = new Noggog.P3Int16(8, 5, 0) },
                };
                foreach (var kw in source.Keywords ?? Enumerable.Empty<IFormLinkGetter<IKeywordGetter>>())
                {
                    clone.Keywords ??= new();
                    clone.Keywords.Add(new FormLink<IKeywordGetter>(kw.FormKey));
                }
                mod.Books.Add(clone);
                variant[rank] = clone.FormKey;
                NoteVariant[(group.Key, rank)] = clone.FormKey;
                cloned++;
            }
            foreach (var (quest, _, rank) in group)
                if (variant[rank] != group.Key) retarget[quest] = (group.Key, variant[rank]);
        }
        Console.WriteLine($"Missives pass 2: {bookLabels.Count} notes to label, {cloned} rank variants, {retarget.Count} quests to retarget");

        // ---- missives.json for AdventurersGuild.dll (MissiveWatch): quests with tier + hold, and the board triggers
        var manifest = questTier.Select(kv => new
        {
            formId = $"0x{kv.Key.ID:X6}",
            tier = kv.Value.letter.ToString(),
            hold = questHold.TryGetValue(kv.Key, out var h) ? h : "",
            // Missives note -> our rank variant (AdventurersGuild.esp local ID), applied by the DLL
            noteFrom = retarget.TryGetValue(kv.Key, out var rt) ? $"0x{rt.from.ID:X6}" : null,
            noteTo = retarget.TryGetValue(kv.Key, out var rt2) ? $"0x{rt2.to.ID:X6}" : null,
        }).ToList();
        var boardTriggers = missives.Activators.Where(a => a.EditorID == "_M_ActivatorBoard").Select(a => $"0x{a.FormKey.ID:X6}").ToList();
        if (boardTriggers.Count == 0) Console.WriteLine("WARNING: no _M_ActivatorBoard found - missives above the player's rank will not be withdrawn on approach");
        // the board itself (a container): the player USING it is what hands out the Guild's notice
        var boardContainers = missives.Containers.Where(c => c.EditorID == "_M_MissiveBoard").Select(c => $"0x{c.FormKey.ID:X6}").ToList();
        if (boardContainers.Count == 0) Console.WriteLine("WARNING: no _M_MissiveBoard found - the registration missive will never be handed out");
        var manifestPath = Path.Combine(outDir, "missives.json");
        File.WriteAllText(manifestPath, JsonSerializer.Serialize(new { rankGlobal = $"0x{rankGlobal.ID:X6}", quests = manifest, books = bookLabels, boardTriggers, boardContainers },
            new JsonSerializerOptions { WriteIndented = true, DefaultIgnoreCondition = System.Text.Json.Serialization.JsonIgnoreCondition.WhenWritingNull }));
        Console.WriteLine($"wrote {manifestPath} ({manifest.Count} quests, {boardTriggers.Count} board trigger bases)");
        return nextBookId;
    }
}
