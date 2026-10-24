// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

// What SkyrimNet's prompts and actions know of the Guild, kept where its NATIVE decorators read it (1.5.2). Until 1.5.1 this
// came from Papyrus decorators (guild_rank_of, ag_player, ag_party, ag_join_status), which SkyrimNet has deprecated: each
// call is a trip into Papyrus, and they were registered only once a save had loaded, so actions checked in the first
// seconds logged "Decorator not found".
//
// Per NPC, as faction ranks (get_faction_rank), on the actors near the player:
//   AG_SkyrimNetStandingFaction  0..5 a member at rank E..S, 10..15 retired at rank E..S, 20 can never join (a child, a
//                                summon). An open member is never hidden: an assassin's secret membership is not marked.
//   AG_SkyrimNetNoteFaction      the number of their bio line in state.json "notes"
//   AG_SkyrimNetPartyFaction     Party::SkyrimNetTie: 0..4 an active member at that Bond tier, 10 + n a former member
// The player's side, in Data/SKSE/Plugins/AdventurersGuild/SkyrimNet/state.json (read_json), rewritten when it changes:
//   {"version":1, "letters":[..], "notes":[..], "ledger":{Guild::LedgerJson}, "party":{Party::SkyrimNetState}}
// Nothing is done without SkyrimNet.dll.
namespace AG::SkyrimNetData
{
	void Install();        // kDataLoaded
	void OnGameLoaded();   // after a load or a new game: the file for this save, and the actors already around
	void Tick();           // game thread, on the Guild's few-second beat (Guild::ConductTick)
	void Mark(RE::Actor* a_actor);  // game thread: one actor's marks, now (an NPC who has just joined)
	bool Active();         // SkyrimNet is here and its data is being kept (the MCM's Debug page)
}
