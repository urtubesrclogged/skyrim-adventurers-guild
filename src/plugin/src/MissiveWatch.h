// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

#include <nlohmann/json.hpp>

// Missives 2.03 is a hard master of AdventurersGuild.esp, which gates its 264 board quests by guild rank
// (tools/EspGen/MissivesPatch.cs). This watches those quests: the counter's board list and Take/Details,
// withdrawing postings above the player's rank, and on a successful turn-in a report to hand in and a toast. Quest tiers and holds come from SKSE/Plugins/AdventurersGuild/
// missives.json, written by the same build step.
//
// Completion signal: every one of the 264 board quests reaches stage 100 on success,
// 105 on failure - verified directly against all 264 quest records, including the 9
// TrackVampire quests that reach stage 100 without ever setting Quest.IsCompleted()'s
// backing flag. Stage number via RE::TESQuestStageEvent is the one fully generic
// signal; watched via a native engine event, no polling.
namespace AG::MissiveWatch
{
	void Register();  // event sink + manifest load, call at kDataLoaded
	bool Active();    // Missives.esp is loaded and its quests resolved
	void OnGameLoaded();  // after a load: note which missives the player is carrying
	int  ExpansionState();  // Missives - Voice and Quest Expansion: 0 not loaded, 1 loaded but not taken in, 2 active
	int  MonsterHuntState();  // Monster Hunt Missives (1.5.0): the same
	int  WorldspaceState();   // Missives - Worldspace Additions (its Raven Rock board, 1.4.0): the same

	// Dev/test hook (DevBench): synthesize the stage-100 event for one quest FormID
	// (hex string, e.g. "0x0201A2B3"), bypassing a real Missives board turn-in.
	void DebugComplete(const std::string& a_formIdHex);
	void DebugBoard();

	// Withdraw (Missives' own stage 110) every posted, not-yet-accepted missive above the player's guild
	// rank. Postings made before the rank gate applied would otherwise linger until Missives' random
	// refresh happens to reset them. Called on walking up to a board and on game load.
	void WithdrawAboveRank();  // as if the player walked up to a Missives board
	// Every board's own refresh made due (Missives' timer on its trigger, reset as each board's town loads):
	// registration and promotion. Missives itself posts the new jobs when the player next walks up to a board.
	void MakeBoardsDue(std::string_view a_why);
	// The counter's own board (the one in the town the player is in): {name, due, hours} - hours until Missives'
	// next refresh of it, 0 when it is due; null when the town has no board.
	nlohmann::json BoardStatus();
	nlohmann::json Save();
	void           Load(const nlohmann::json& a_j);
	void           Revert();

	// The guild counter's view of the local board: missives currently posted (running, stage 0) in the
	// hold whose capital is a_city, at or below the player's rank. [{id, tier, title}]
	nlohmann::json Postings(const std::string& a_city);
	int            InProgress();  // missives the player has taken and not yet finished
	// The posting's note as the player would read it: its text with every <Alias=...> filled in from the
	// quest instance, book markup removed. {id, tier, title, posted, text}
	nlohmann::json Details(const std::string& a_formIdHex);
	// Take a posting from the counter (the note moves from the board to the player; Missives accepts it).
	std::string Accept(const std::string& a_formIdHex);
}
