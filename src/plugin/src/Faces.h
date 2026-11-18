// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

// The Guild Hall's people ship no FaceGen files: the game builds their faces at run time from their records. Two things
// make that work (proven in the hall's NPC spike, tools/HallSpike/npcs/facespike, 2026-10-26):
//  - the tint fix: a face built at run time keeps its skin tint (Face Discoloration Fix's method; it steps aside when
//    the game is already patched, and writes nothing where the game's code is not what it expects);
//  - High Poly Head: when it is loaded, the hall's NPCs are given its twin of their face, brows and beard, in memory.
namespace AG::Faces
{
	void InstallTint();   // at plugin load: logs the sites' original bytes
	void ApplyTint();     // at kPostPostLoad (every SKSE plugin loaded, no game plugin read yet): the patch
	void OnDataLoaded();  // High Poly Head's heads on the hall's NPCs
	std::string Status();
	std::string Parts(RE::TESNPC* a_npc);  // the head parts the engine will build a face from, by editor ID (diagnostics)
}
