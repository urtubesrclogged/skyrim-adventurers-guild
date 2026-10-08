// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

// Rank letters and the level bands. One table for everything: the THREAT rank of anything you fight, the rank of a
// dungeon, the guild rank of NPC adventurers, and the level each of the PLAYER's promotions needs (the player's rank
// itself is earned at the Guild, see Guild.h). The table follows one number, the level of rank S (MCM, per save).
namespace AG
{
	// 0=E .. 5=S
	inline constexpr int kRankCount = 6;

	struct Bands
	{
		// Lowest level of ranks D,C,B,A,S (E starts at 1)
		std::array<int, kRankCount - 1> min{ 12, 24, 40, 60, 80 };
	};
	inline constexpr int kSLevelMin = 60, kSLevelMax = 120, kSLevelStep = 10, kSLevelBefore140 = 60;

	// Creature adjustment on top of level ([Threat] / [ThreatKeywords] in the ini). Level already tracks danger for
	// most foes (Skyrim's leveled lists scale them); these catch the ones it understates, vanilla or modded.
	struct KeywordRule
	{
		std::string keyword;  // race or actor keyword editor ID, e.g. ActorTypeDragon
		int         bump{ 0 };
		int         floor{ -1 };
		int         atMost{ -1 };  // never above this rank (the lowest ceiling among the matching rules wins)
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
		// a dragon is one rank above its level and never below C; wildlife stops at B (a race rule can say otherwise)
		std::vector<KeywordRule>           keywords{ { "ActorTypeDragon", 1, 2, -1 }, { "ActorTypeAnimal", 0, -1, 3 } };
		// Rank S is never reached by level alone. LISTED: a race or actor rule that says "at least S", or one of these
		// keywords. PROVEN: at the S level and, for a creature, a danger score of ScoreS or more; for a person, a unique
		// actor placed as a dungeon boss. Anything else stops at A.
		bool                               sGate{ true };
		std::vector<std::string>           sKeywords{ "ActorTypeDragon" };
		// Judgement calls by race (threat.json -> threat.resolved.json): never below / never above a rank
		// Appraisal: a creature of legend (any of these race or actor keywords, or neither a person nor an animal) shows
		// "[?]" until the player's Appraisal reaches this tier. 0 = no such gate.
		int                      fantasyTier{ 2 };
		// ... and a threat of this rank or above is beyond measure ("[?]") until this tier. 0 = no such gate.
		int                      highTier{ 3 };
		int                      highRank{ 4 };  // A
		std::vector<std::string> fantasyKeywords{ "ActorTypeTroll", "ActorTypeUndead", "ActorTypeDaedra", "ActorTypeDragon",
			"ActorTypeDwarven", "ActorTypeGhost", "ActorTypeGiant", "Vampire" };
		bool                                    raceRules{ true };
		std::unordered_map<RE::FormID, RaceRule> races;
		std::unordered_map<RE::FormID, int>      actors;  // actor base -> never below this rank (Alduin: S at any level)
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
	Bands GetBands();
	// The level of rank S, 60..120 in tens. D and C stay at 12 and 24; B and A are spaced between C and S as 40 and 60
	// are for 80. 60 gives the table every version before 1.4.0 had (12/24/36/48/60).
	void  SetSLevel(int a_level);
	int   GetSLevel();
	int   DefaultSLevel();        // a new game's: [Ranks] SLevel in the ini
	int   MinLevel(int a_rank);   // lowest level of a rank (1 for E)

	int         FromLevel(int a_level);
	int         ThreatRank(RE::Actor* a_actor);  // level band, moved by the danger score and the creature rules; -1 if null
	ThreatInfo  ExplainThreat(RE::Actor* a_actor);
	bool        IsFantasy(RE::Actor* a_actor);   // not a person or an animal: a troll, a draugr, a vampire, a dragon
	int         FantasyTier();                   // Appraisal tier that reads their threat rank (0 = no gate)
	bool        ThreatReadable(RE::Actor* a_actor, int a_threat, int a_appraisal);  // false: the label shows "[?]"
	char        Letter(int a_rank);              // '?' outside 0..5
	std::string LetterStr(int a_rank);
	int         FromLetter(char a_letter);       // -1 if not E..S
}
