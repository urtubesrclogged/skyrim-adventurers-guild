// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

#include <functional>

#include <nlohmann/json.hpp>

// The Jarls' bounties (1.5.0): the game's own radiant bounty quests (BQ01 bandit leader, BQ02 Forsworn, BQ03 giant,
// BQ04 dragon), brought into the Guild. Nothing of theirs is carried in AdventurersGuild.esp and no record is
// changed, in the file or in memory: other mods override all four (Better Quest Objectives, Bounty Gold and more),
// and whatever won the load order is what is watched.
//
// How the game runs them (read from Skyrim.esm and its scripts, 2026-10-13):
//  - One instance of each quest, so four bounties at most in the province, and ONE PER HOLD: the story manager
//    starts one when the player comes into a town of a hold that has none, and the quest marks the hold as taken.
//  - Untaken (stage 0) it lives only while the player is in that town: BQPlayerScript stops it when they leave.
//  - Stage 10: taken. "I'm looking for work. Got any leads?" to the innkeeper or the steward sets it; the stage
//    gives the Jarl's letter and the map marker. Stage 100: the target died. Stage 200: the Jarl or the steward was
//    told and paid the gold, and the quest stops.
//
// What the Guild adds: a rank (the target's threat rank, or the place's if that is higher), the hold's bounty on the
// counter's Quests tab with Take and Details, and when the hold has paid, a report to hand in at any counter for
// Merit and Reputation, as a missive's. The hold pays the gold; the Guild pays none. No rank gate:
// the game hands these out in villages that have no counter.
//
// Quests are found by shape, not by FormID: any quest with the aliases the four have (Bounty, BountyLocation, Letter,
// Hold, Jarl, Steward, Innkeeper). A mod that adds a bounty built on the game's own would be taken in with them.
//
// The Guild Hall's "A new bounty?" (2.0): the hall hands out a bounty for a hold that has none,
// the target unseen until the letter is read, as the steward's "I'm looking for work" does. AdventurersGuild.esp carries
// copies of the four for it (EspGen's HallBounties.cs says why copies, and what of the game's they keep): they start
// through the Story Manager for a hold's capital, and share the game's mark of a hold with a bounty running, so neither
// the game nor the hall posts two in one hold. Found by shape like the game's, they are watched, ranked and paid the same.
namespace AG::BountyWatch
{
	void Register();  // at kDataLoaded: find the bounty quests, watch their stages

	// The bounty of the hold whose counter is in a_city, or null when it has none (and for a city with no counter).
	// {id, tier, title, state: "offer" | "taken" | "slain", payer}. "offer" is the only one that can be taken.
	nlohmann::json Posting(const std::string& a_city);
	// The Guild Hall's view: every hold's bounty that is posted, taken or slain, not yet collected (any rank: the hall
	// filters the posted ones by rank). [{id, tier, title, state, payer, city}], as Posting, city being the counter city
	// of its hold.
	nlohmann::json All();
	int            InProgress();  // bounties taken and not yet collected, in every hold
	bool           Owns(const std::string& a_formIdHex);  // one of the bounty quests (the counter's Take / Details)
	// The Jarl's letter as the player would read it. {id, tier, title, posted, text, kind: "bounty"}
	nlohmann::json Details(const std::string& a_formIdHex);
	// Take the bounty from the counter: exactly what the innkeeper's line does (stage 10).
	std::string    Accept(const std::string& a_formIdHex);

	// The Guild Hall's "A new bounty?": a member, a hold with no bounty running, and one of the hall's four not running.
	bool NewBountyPossible();
	// Start one for a hold picked at random, and take it (the letter, the objective, the marker). Papyrus answers later:
	// a_done is called on the game thread with the line for the page ("Bounty taken: ..." or why there was none).
	void NewBounty(std::function<void(const std::string&)> a_done);
	// Prepare to Uninstall: the hall's running bounties stop and their holds are freed for the game's own.
	void StopHallBounties();
}
