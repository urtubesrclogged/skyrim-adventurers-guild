// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

// Reputation for kills, credited the moment a foe dies (no report to hand in, no HUD line - the counter shows the
// total). Amount by the victim's threat rank (guild.json "kills"), times the highest of: bossMultiplier for a foe
// placed as a dungeon Boss, or the race size multiplier (Large / Extra Large). The player's kill pays in full; a
// follower's or the player's summon's kill pays followerShare.
// An assist (your side hit it in the last assistSeconds, someone else finished it) pays assistShare.
// Summoned or reanimated victims, allies and anything not hostile to the player pay nothing.
namespace AG::Kills
{
	void Register();  // TESDeathEvent sink, call at kDataLoaded
	bool IsBoss(RE::Actor* a_actor);  // placed as the boss of a dungeon or a clearable place

	// dev/test (DevBench): credit a kill of that actor as if the player made it; returns what it paid and why
	std::string DebugKill(RE::FormID a_ref);
	// threat-rank breakdown of loaded actors near the player (also logged)
	std::string DebugThreat();
}
