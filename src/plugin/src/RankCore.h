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
	struct RaceRule
	{
		int atLeast{ -1 };   // never below this rank ...
		int fromLevel{ 0 };  // ... once the creature is at least this level (0 = always)
		int atMost{ -1 };    // never above this rank
	};
	struct ThreatTuning
	{
		// Danger score: sqrt(max Health x attack), for creatures that fight with their own body (not people, not the
		// ones that rely on carried weapons). It moves the level rank by one at most, towards the rank the score
		// gives. Works for any creature a mod adds.
		bool                               score{ true };
		std::array<float, kRankCount - 1>  scoreMin{ 45.0f, 100.0f, 200.0f, 300.0f, 500.0f };  // lowest score of D,C,B,A,S
		std::vector<KeywordRule>           keywords{ { "ActorTypeDragon", 2, -1 } };
		// Judgement calls by race (threat.json -> threat.resolved.json): never below / never above a rank
		bool                                    raceRules{ true };
		std::unordered_map<RE::FormID, RaceRule> races;
	};

	// How a threat rank was reached, for the debug readout.
	struct ThreatInfo
	{
		int         level{ 0 }, byLevel{ -1 }, byScore{ -1 }, bump{ 0 }, floor{ -1 }, rank{ -1 };
		float       health{ 0.0f }, attack{ 0.0f }, score{ 0.0f };  // score 0 = not scored (a person, or a weapon user)
		std::string why;
	};

	void LoadConfig();  // Data/SKSE/Plugins/AdventurersGuild.ini
	void LoadRaceRules();  // at kDataLoaded (needs forms): threat.resolved.json
	const Bands& GetBands();

	int         FromLevel(int a_level);
	int         ThreatRank(RE::Actor* a_actor);  // level band, moved by the danger score and the creature rules; -1 if null
	ThreatInfo  ExplainThreat(RE::Actor* a_actor);
	char        Letter(int a_rank);              // '?' outside 0..5
	std::string LetterStr(int a_rank);
	int         FromLetter(char a_letter);       // -1 if not E..S
}
