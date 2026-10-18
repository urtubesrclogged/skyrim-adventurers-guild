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
	void Install();  // at kDataLoaded: location-change + tracked-stat sinks
	void OnGameLoaded();  // once a game is loaded: where the player is now (no location change says so)

	void           SetNotDungeons(std::vector<std::string> a_keys);  // guild.json "notDungeons" ("Plugin|0xID")
	void           SetPointsOfInterest(const nlohmann::json& a_cfg); // guild.json "pointsOfInterest"
	nlohmann::json Save();
	int            ClearedCount();  // dungeons cleared this save (each counted once)
	// Hold stamps (1.5.0): the dungeons of the hold a counter serves whose clearing the Guild has on record, i.e. whose
	// report has been handed in (at any counter). The counter is named by its city as the liaisons are ("Whiterun" ...
	// "Raven Rock", which is all of Solstheim). Counted from the saved record every time: cleared dungeons, less the
	// ones still waiting to be reported. A save from before 1.5.0 has no waiting list, so all it cleared counts.
	// -1 for a city that has no counter.
	int            ClearedIn(const std::string& a_city);
	std::string    CityOf(RE::BGSLocation* a_loc);  // the counter city of the hold a place is in ("" when it is in none)
	std::string    CityHere();  // the counter city of the hold the player is in ("" outside every hold)
	// The threat rank of a dungeon the player is not in, from its encounter zone (as Intel prices it). -1 when the place
	// has no zone the Guild knows, or is null.
	int            RankOf(const RE::BGSLocation* a_loc);
	int            WaitingIn(const std::string& a_city);  // cleared in that hold, report not handed in yet
	// The reports of these dungeons (their keys) have been handed in. Returns the counter cities whose stamp that
	// earned: the count was short before and is enough now.
	std::vector<std::string> HandIn(const std::vector<std::string>& a_keys);
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
	// every dungeon of the player's hold: the rank the Guild gives it (its zone) beside its bosses as they can be read
	// from here, before going in (one line each, tab-separated; also written to the log)
	std::string DebugHold();
	std::string DebugClear();  // run the clear path for the current dungeon (as if the stat fired)
}
