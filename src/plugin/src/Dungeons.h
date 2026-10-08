// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

#include <nlohmann/json.hpp>

// Dungeon threat ranks and guild clear reports.
//   Entering a clearable location (LocTypeClearable / LocTypeDungeon on it or a parent): its threat rank comes
//   from the cell's encounter zone - the level the zone locked at, else the player's level clamped to the
//   zone's min/max - banded like any threat (RankCore::FromLevel). First visit: a toast with the rank plaque;
//   later visits: a HUD line.
//   Clearing it (the engine's "Dungeons Cleared" tracked stat): a DUNGEON CLEARED toast and, once registered,
//   a report to hand in at any counter (guild.json dungeonMerit / dungeonGold by rank). Once per location per
//   save, quest or not.
namespace AG::Dungeons
{
	void Install();  // at kDataLoaded: player cell-change + tracked-stat sinks

	void           SetNotDungeons(std::vector<std::string> a_keys);  // guild.json "notDungeons" ("Plugin|0xID")
	void           SetPointsOfInterest(const nlohmann::json& a_cfg); // guild.json "pointsOfInterest"
	nlohmann::json Save();
	int            ClearedCount();  // dungeons cleared this save (each counted once)
	void           Load(const nlohmann::json& a_j);
	void           Revert();

	// Intel service (counter > Services > Intel): uncleared dungeons in the player's hold whose map marker is
	// still hidden, priced in Merit by threat rank. Buying reveals the marker (Papyrus AddToMap, no fast travel).
	nlohmann::json IntelServices(int a_merit, bool a_registered);  // Services rows, section "Intel"
	std::string    BuyIntel(const std::string& a_id);             // "intel:<FormID hex>" -> status line
	// Points of Interest (Intel's second tab): places worth knowing that are no dungeon - an Orc stronghold, a standing
	// stone, a hunters' shack. Found from the game's map markers by icon (so other mods' places count), in categories
	// with one Merit price each (guild.json "pointsOfInterest"). Nothing to clear, no rank, no notice on entering.
	nlohmann::json PoiServices(int a_merit, bool a_registered);    // Services rows, section "Intel", group "poi"
	std::string    BuyPoi(const std::string& a_id);                // "poi:<marker FormID hex>" -> status line

	// dev/test (DevBench)
	std::string DebugInfo();   // current location, zone, level, rank, visited/reported state
	std::string DebugClear();  // run the clear path for the current dungeon (as if the stat fired)
}
