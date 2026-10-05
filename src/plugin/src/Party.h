// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

#include <nlohmann/json.hpp>

// Adventuring parties (docs/PARTIES.md): the player founds one party at a Guild counter, leads it, and adds follower
// adventurers to it. The Guild keeps a ledger of every party, active or disbanded, with its members' fates (active,
// former, fallen). Bond is earned per member and the party's Bond is the average over its active members.
namespace AG::Party
{
	void LoadConfig();  // guild.json "party" (also re-run by AG_Native.ReloadConfig)

	// Lifecycle. Each returns a status line for the counter (or a HUD / log).
	// Needs a registered player, no active party, the fee, and at least one founder: a follower adventurer at the
	// player's side (no party of one). The founders join at once.
	std::string Found(std::string a_name, const std::vector<RE::Actor*>& a_founders);
	std::string Rename(std::string a_name);
	std::string Disband();
	std::string Add(RE::Actor* a_actor);                // an eligible follower (see Eligible)
	std::string Remove(const std::string& a_key);       // an active member, by Adventurers::StableKey

	void OnDeath(RE::Actor* a_actor);                   // Kills' death sink: an active member falls

	// Bond and the party's record (docs/PARTIES.md). Each counts only with a member present (following, loaded, near).
	void Register();                                    // at kDataLoaded: the field-time tick
	void OnKill(RE::Actor* a_victim, RE::Actor* a_killer, int a_rank, bool a_big);  // a foe credited to the player's side
	void OnDungeonCleared(int a_rank);
	void OnMissiveCompleted(int a_rank);

	// Bond blessing + Party Traits (traits.json, AG_PartyBlessing): re-evaluated every few seconds and after party changes.
	void        Refresh();                              // game thread: traits, globals, who carries the ability
	// The counter was opened, or the roster was changed there: re-read the roster and unselect every chosen trait it no
	// longer fits (a member removed or lost, the player cured of vampirism...). Away from the counter a chosen trait
	// is never unselected: it pauses while those at the player's side do not fit it, and resumes when they do.
	void        AtCounter();
	std::string ToggleTrait(const std::string& a_id);
	int         GoldRewardPercent();
	void        TraitsViewed();
	int         StripForUninstall();  // the Party Blessing off the player and every member ever; returns companions stripped       // the player has seen the Affinity page: nothing is "new" any more  // extra Guild gold from active traits (Coin-Bound), percent   // switch an unlocked trait on/off (at most maxActive on)

	bool           HasParty();
	std::string    Name();                              // "" without an active party
	bool           IsActiveMember(RE::Actor* a_actor);
	nlohmann::json CounterData();                       // the counter's Party tab
	std::string    Dump();                              // DevBench
	// SkyrimNet ag_party(actor): the player's party (name, members, Bond, renown) and this actor's own tie to a party.
	std::string    SkyrimNetJson(RE::Actor* a_actor);

	// Bond, 0..100, between the player and each NPC: it survives leaving, rejoining and new parties. The party's Bond is
	// the mean over its active members (0 with none); it and its blessing only apply with a member at the player's side.
	float BondOf(RE::Actor* a_actor);
	float PartyBond();
	int   BondTier(float a_bond);                       // 0 Strangers .. 4 Legend
	void  AddBond(RE::Actor* a_actor, float a_amount);  // an active member only; clamps to 0..100

	// co-save (part of Guild's record)
	nlohmann::json Save();
	void           Load(const nlohmann::json& a_j);
	void           Revert();
}
