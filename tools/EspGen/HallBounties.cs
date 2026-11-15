using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Skyrim;

// The Guild Hall's "A new bounty?" (2.0): the hall hands out a Jarl's bounty for a hold that has none, the target unseen
// until the letter is read, as the game's own "I'm looking for work". The game's four bounty quests (BQ01 bandit leader, BQ02 Forsworn, BQ03 giant, BQ04 dragon)
// cannot be started for a chosen hold: they take their town from the player's change of location, which no script can
// send. So these are copies of them, started the way the game starts a quest for a place of its choosing: a Script Event
// (Keyword.SendStoryEventAndWait, the town as its location) and a Story Manager node of ours that lists the four.
//
// Copied from the winning master (Update.esm) record by record, changed only where the start differs:
//  - the event is the Script Event, and the town alias fills from its location (L1) instead of the new location (L2);
//  - the innkeeper is optional (the hall gives the letter, not the inn), kept so the quests keep the shape BountyWatch
//    finds bounty quests by;
//  - their own links (the scripts' alias properties) point at the copy.
// Everything else is the game's: the stages and their scripts (stage 0 marks the hold taken with BQActiveQuest, the lock
// the game's nodes check, so the game never posts a second bounty in that hold, and stage 200 clears it), the letter,
// the start conditions (giant from level 20, dragon from level 10 once the dragons have returned), and the reward line,
// whose voiced response is the game's shared one. The DLL takes the bounty at once (stage 10), so the copy never waits
// on an offer that the player's leaving town would withdraw.
//
// The text is the game's English here; the DLL replaces it at load with the game's own records' text (the player's
// language, or whatever a mod changed it to). Mods that change the game's bounties (reward, objectives) change the
// game's records only, not these.
static class HallBounties
{
    static readonly (uint quest, uint reward, string edid)[] Kinds =
    {
        (0x095125, 0x095121, "BQ01"), (0x0BD77F, 0x0BD68F, "BQ02"), (0x0BD78C, 0x0BD170, "BQ03"), (0x0CBA9A, 0x0CBA90, "BQ04"),
    };
    const uint ScriptEventNode = 0x01379A;  // Skyrim.esm: the Story Manager's Script Event node, where the game's own script-started quests hang
    const ushort EventLocation1 = 0x314C;   // event data L1: a Script Event's location (the CLOC event's L2 is its new location)

    // 0xFC0-0xFC3 the quests, 0xFC4-0xFC7 their reward branches, 0xFC8-0xFCB the reward topics, 0xFCC-0xFCF their lines,
    // 0xFD0 the event keyword, 0xFD1 the Story Manager node
    public static void Add(SkyrimMod mod, IReadOnlyList<ISkyrimModGetter> masters, Func<uint, FormKey> fk)
    {
        const SkyrimRelease Rel = SkyrimRelease.SkyrimSE;
        var skyrim = Mutagen.Bethesda.FormKeys.SkyrimSE.Skyrim.ModKey;
        T Winner<T>(IEnumerable<T> all, uint id) where T : IMajorRecordGetter => all.Last(r => r.FormKey == new FormKey(skyrim, id));

        var keyword = new Keyword(fk(0xFD0), Rel) { EditorID = "AG_HallNewBountyEvent" };
        mod.Keywords.Add(keyword);

        var node = new StoryManagerQuestNode(fk(0xFD1), Rel)
        {
            EditorID = "AG_HallNewBountyNode",
            Parent = new FormLinkNullable<IAStoryManagerNodeGetter>(new FormKey(skyrim, ScriptEventNode)),
            // first among its siblings, as the DLCs' own nodes there: it answers only our keyword, so order is no matter
            PreviousSibling = new FormLinkNullable<IAStoryManagerNodeGetter>(FormKey.Null),
            Flags = AStoryManagerNode.Flag.Random,
            QuestFlags = StoryManagerQuestNode.QuestFlag.DoAllBeforeRepeating,
            MaxConcurrentQuests = 0,
        };
        node.Conditions.Add(new ConditionFloat
        {
            CompareOperator = CompareOperator.EqualTo,
            ComparisonValue = 1,
            Data = new GetEventDataConditionData
            {
                Function = GetEventDataConditionData.EventFunction.GetIsID,
                Member = GetEventDataConditionData.EventMember.Keyword,
                Record = new FormLink<ISkyrimMajorRecordGetter>(keyword.FormKey),
            },
        });

        for (uint i = 0; i < Kinds.Length; i++)
        {
            var (questId, rewardId, edid) = Kinds[i];
            var srcQuest = Winner(masters.SelectMany(m => m.Quests), questId);
            var srcTopic = Winner(masters.SelectMany(m => m.DialogTopics), rewardId);
            var srcBranch = masters.SelectMany(m => m.DialogBranches).Last(b => b.FormKey == srcTopic.Branch.FormKey);
            if (srcTopic.Responses.Count != 1) throw new InvalidOperationException($"{edid}RewardTopic has {srcTopic.Responses.Count} lines, not the one it had when this was written");
            var srcInfo = srcTopic.Responses[0];

            var quest = new Quest(fk(0xFC0 + i), Rel);
            quest.DeepCopyIn(srcQuest);
            var branch = new DialogBranch(fk(0xFC4 + i), Rel);
            branch.DeepCopyIn(srcBranch);
            var topic = new DialogTopic(fk(0xFC8 + i), Rel);
            topic.DeepCopyIn(srcTopic, new DialogTopic.TranslationMask(defaultOn: true) { Responses = false });
            var info = new DialogResponses(fk(0xFCC + i), Rel);
            info.DeepCopyIn(srcInfo);
            topic.Responses.Add(info);

            var remap = new Dictionary<FormKey, FormKey>
            {
                [srcQuest.FormKey] = quest.FormKey, [srcBranch.FormKey] = branch.FormKey, [srcTopic.FormKey] = topic.FormKey, [srcInfo.FormKey] = info.FormKey,
            };
            quest.RemapLinks(remap);
            branch.RemapLinks(remap);
            topic.RemapLinks(remap);  // the line too: its stage-100 condition names the quest

            quest.EditorID = $"AG_Hall{edid}";
            branch.EditorID = $"AG_Hall{edid}Reward";
            topic.EditorID = $"AG_Hall{edid}RewardTopic";
            info.EditorID = null;
            quest.Event = new RecordType("SCPT");
            foreach (var a in quest.Aliases)
            {
                if (a.FindMatchingRefFromEvent is { } ev && a.Name == "Location")
                {
                    ev.FromEvent = new RecordType("SCPT");
                    ev.EventData = (GetEventDataConditionData.EventMember)EventLocation1;
                }
                if (a.Name == "Innkeeper") a.Flags = (a.Flags ?? 0) | QuestAlias.Flag.Optional;
            }
            if (!quest.Aliases.Any(a => a.Name == "Location" && a.FindMatchingRefFromEvent?.FromEvent == new RecordType("SCPT")))
                throw new InvalidOperationException($"{edid}: no Location alias filled from its event");

            mod.Quests.Add(quest);
            mod.DialogBranches.Add(branch);
            mod.DialogTopics.Add(topic);
            node.Quests.Add(new StoryManagerQuest { Quest = new FormLinkNullable<IQuestGetter>(quest.FormKey) });
        }
        mod.StoryManagerQuestNodes.Add(node);
    }
}
