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
                    ObjectBounds = source.ObjectBounds?.DeepCopy(),
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
