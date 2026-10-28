// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

// What CHIM's NPCs know of the Guild (1.6.0), the twin of SkyrimNetData. CHIM's own DLL uploads the Guild's server plugin
// (src/chim, shipped as CHIM/server-plugins/adventurersguild/<version>.dwpkg) to the CHIM server; this module feeds it:
//   - the state, POSTed to <server>/HerikaServer/ext/adventurersguild/api/state.php when it changes, off the game
//     thread: the player's record and party (as SkyrimNet's state.json), and the people near the player by name (CHIM
//     knows NPCs by name only): their guild standing, bio line, party tie and the factions chim.json lists;
//   - the news: every line of the player's Guild ledger, as an "info_guild" event through CHIM's own Papyrus API
//     (AIAgentFunctions.logMessage), which CHIM keeps for the people nearby.
// The server is found as CHIM finds it: Data/SKSE/Plugins/AIAgent.ini, then the CHIM launcher on 127.0.0.1:7135, then
// 127.0.0.1:8081. Nothing is done without CHIM (AIAgent.esp).
namespace AG::ChimData
{
	void Install();                     // kDataLoaded
	void OnGameLoaded();                // after a load or a new game: the next report says hello (the server brings Oghma up to date)
	void Tick();                        // game thread, on the Guild's few-second beat (Guild::ConductTick)
	void News(const std::string& a_line);  // any thread: a line just written in the player's Guild ledger
	bool Present();                     // CHIM is installed (the MCM's Debug page)
	bool Active();                      // ... and its server has taken a report
}
