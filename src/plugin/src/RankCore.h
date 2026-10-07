// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

// Rank letters and the level bands. Bands give the THREAT rank of anything you fight and the guild
// rank of NPC adventurers. The PLAYER's guild rank is not level-derived: it is earned (see Guild.h).
namespace AG
{
	// 0=E .. 5=S
	inline constexpr int kRankCount = 6;

	struct Bands
	{
		// Lowest level of ranks D,C,B,A,S (E starts at 1)
		std::array<int, kRankCount - 1> min{ 12, 24, 36, 48, 60 };
	};

	// Creature adjustment on top of level ([Threat] / [ThreatKeywords] in the ini). Level already tracks danger for
	// most foes (Skyrim's leveled lists scale them); these catch the ones it understates, vanilla or modded.
	struct KeywordRule
	{
		std::string keyword;  // race or actor keyword editor ID, e.g. ActorTypeDragon
		int         bump{ 0 };
		int         floor{ -1 };
	};
	struct ThreatTuning
	{
		// Toughness: permanent max Health against what a typical foe of that level has (base + perLevel * level).
		// Works for any creature a mod adds, keyword or not. 0 ratio = off.
		float                    healthBase{ 50.0f };
		float                    healthPerLevel{ 10.0f };
		float                    tough1{ 4.0f };  // at least this many times expected health: +1 rank
		float                    tough2{ 8.0f };  // +2 ranks
		std::vector<KeywordRule> keywords{ { "ActorTypeDragon", 2, -1 } };
		// Safety net (threat.resolved.json): race -> the level its weakest vanilla encounter variant has. A creature
		// is ranked as at least that level, so an overhaul that lowers its level cannot make a giant rank E.
		bool                                    raceFloors{ true };
		std::unordered_map<RE::FormID, int>     raceLevel;
		// ... and the judgement calls (threat.json): by race, never below / never above this rank by level
		std::unordered_map<RE::FormID, int>     raceAtLeast, raceAtMost;
	};

	// How a threat rank was reached, for the debug readout.
	struct ThreatInfo
	{
		int         level{ 0 }, byLevel{ -1 }, bump{ 0 }, floor{ -1 }, rank{ -1 };
		float       health{ 0.0f }, ratio{ 0.0f };
		std::string why;
	};

	void LoadConfig();  // Data/SKSE/Plugins/AdventurersGuild.ini
	void LoadRaceFloors();  // at kDataLoaded (needs forms): threat.resolved.json
	const Bands& GetBands();

	int         FromLevel(int a_level);
	int         ThreatRank(RE::Actor* a_actor);  // level band + creature adjustment; -1 if null
	ThreatInfo  ExplainThreat(RE::Actor* a_actor);
	char        Letter(int a_rank);              // '?' outside 0..5
	std::string LetterStr(int a_rank);
	int         FromLetter(char a_letter);       // -1 if not E..S
}
