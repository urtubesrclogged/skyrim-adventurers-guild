// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild
#pragma once

#include <nlohmann/json.hpp>

// The Guild Hall's party leader board (2.0): every party the Guild's ledger in Skyrim holds, ranked by Renown, on one
// hand-kept sheet pinned up in Services. A PrismaUI page of its own (leaderboard.html), opened by activating the board.
// Its parties: the player's (Party's ledger: the active one with its leader, the disbanded ones with their years), the
// Guild's old ones at the scores they ended on, two active parties the player never meets, and the rival, Caralion's
// Golden Hand. Those three climb with the player's own party (its Renown), not the calendar: none moves before the
// player has a party, the player catches the Golden Hand at a set Renown, and none of them reaches the top three.
// Everything but the rival's end (and when the player passed him) follows from the player's Renown, so the save holds
// little. guild.json "leaderBoard" holds the paces.
// The board's story pieces, two NIFs the hall places on the board's spot: a fresh slip shown once the player has a
// party (AGLeaderSlip.nif), the Golden Hand's row struck through once he is dishonored (AGLeaderStrike.nif).
namespace AG::LeaderBoard
{
	void LoadConfig();  // guild.json "leaderBoard" (also re-run by AG_Native.ReloadConfig)
	void Install();     // at kDataLoaded: the view, the board's activation
	void Register();    // at kDataLoaded: the passed-the-rival check, every half minute on the game thread
	void Open();        // also AG_Native.OpenLeaderBoard()
	void OpenAfterDialogue();  // an innkeeper's "Could I see the party rankings?" (2.0, no Guild Hall): opens as the Dialogue Menu closes
	void Close();
	bool IsOpen();
	void Invoke(const std::string& a_script);  // into the page while it is open: the controller's buttons (Counter's pad reader)

	// For Caralion's quest (the NPCs session): the player's active party's place on the board (1 = first; 0 without a
	// party), the Golden Hand's place (0 once he is done), and the end of it: 1 he fell, 2 he left Skyrim (both after his
	// treachery: struck out, "dishonored"), 3 he died before his quest ("disbanded"). His Renown freezes that day.
	// When the player's party first ranks above the Golden Hand, AG_LB_PassedRival (AdventurersGuild.esp 0xFDD) is set to
	// 1 for good and the mod event "AG_LeaderBoard_PassedRival" is sent. For dialogue conditions, every half minute:
	// AG_LB_PartyRenownGlobal (0xFDE, the player's best party's Renown, active or disbanded) and AG_LB_PlayerPlaceGlobal
	// (0xFDF, that same party's place; Rank() is the active party's).
	int  Rank();
	int  RivalRank();
	void EndRival(int a_how);

	std::string Dump();  // DevBench: every row as the page gets it, and the rival's state

	// co-save (part of Guild's record)
	nlohmann::json Save();
	void           Load(const nlohmann::json& a_j);
	void           Revert();
}
