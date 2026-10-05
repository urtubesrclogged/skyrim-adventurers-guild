// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

#include <nlohmann/json.hpp>

// The Notice Board SE ("notice board.esp", MannyGT), optional: nothing here runs unless that plugin is loaded, and
// AdventurersGuild.esp does not depend on it. Like MissiveWatch for Missives, everything is applied in memory on top
// of whatever won the load order - no record of the mod is overridden.
//
// The mod has about twenty quests, one of each kind, and no difficulty tiers: each quest's guild rank comes from
// SKSE/Plugins/AdventurersGuild/notices.json. Its boards all open one shared container, so the notices are the same
// everywhere in the province ("Provincial Notices" on the counter, next to Missives' per-hold "Local Missives").
//
// Two rules, decided with the user:
//  - Nothing the player has TAKEN is taken back. A gated notice that is only posted (still on the board) above the
//    player's rank is taken down, as Missives postings are; it goes back up when the rank allows it.
//  - When in doubt, do not gate. A quest is rank-gated only if the boards start it themselves (so a failed start is
//    simply retried the next time a board loads) and it has an alias the condition can sit on. The rest are labelled
//    and counted, and open to every rank.
namespace AG::NoticeWatch
{
	void Register();  // at kDataLoaded: read notices.json, gate and label, watch stages and board use
	bool Active();    // "notice board.esp" is loaded and its quests resolved
	void WithdrawAboveRank();  // on game load and when a board is used: take down posted, untaken notices above rank

	void Post();  // the counter was opened: post what a board would on loading (the list refreshes when it is done)

	// Notices on the board now (running, not yet accepted, the note still in the board). [{id, tier, title}]
	nlohmann::json Postings();
	bool           Owns(const std::string& a_formIdHex);  // one of this mod's quests (the counter's Take / Details)
	// The notice as the player would read it. {id, tier, title, posted, text, kind: "notice"}
	nlohmann::json Details(const std::string& a_formIdHex);
	// Take a notice from the counter: the note moves from the board to the player and the quest is accepted, exactly
	// as if the player had read it off the board.
	std::string    Accept(const std::string& a_formIdHex);
}
