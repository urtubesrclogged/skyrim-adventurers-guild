// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild
#pragma once

#include <nlohmann/json.hpp>

#include <optional>

// The Guild Hall (2.0): its counter sees every hold. Its two clerks are the Guild's representatives there, and a counter
// they open has the branch kBranch: its Quests tab lists every hold's missives and Jarls' bounties, with a hold filter.
// The clerks' records live in the hall's own plugin, which the core plugin cannot master, so they are found here by
// FormID (fixed by the hall's merge step) and given to the liaison list at run time.
namespace AG::GuildHall
{
	inline constexpr const char* kBranch = "Guild Hall";
	inline constexpr float       kSiteX = 16014.0f, kSiteY = -49358.0f;  // where it stands in Tamriel (its cells have no location): Intel's bearings
	bool IsBranch(const std::string& a_branch);
	bool Loaded();  // the hall's plugin is in the load order

	// What only the hall does (2.0, MCM > Guild Hall). Each has a toggle, on by default, and is the
	// hall's alone while its toggle is on AND the hall's plugin is loaded: without the hall, every counter does all of it.
	// The numbers are the MCM's (AG_Native.SetHallOnly): append only.
	enum class Only : std::int32_t { kRegistration, kPromotion, kTraining, kBoxes, kLibrary, kTomes, kAugments, kParties, kCount };
	void SetOnly(Only a_what, bool a_on);                          // the MCM's toggle (registration and promotion also keep their globals)
	bool OnlyAtHall(Only a_what);                                  // in effect now
	bool Allows(Only a_what, const std::string& a_branch);         // may a counter of this branch do it?
	std::string AtHallNote();                                      // "At the Guild Hall", in the player's language
	std::string RefusedHere();                                     // what a counter says when asked for one of them anyway
	std::optional<Only> ServiceFeature(std::string_view a_id);     // the feature a counter service (Services tab id) belongs to, if any
	void GreyServices(nlohmann::json& a_services, const std::string& a_branch);  // those this branch may not sell: greyed, "At the Guild Hall"
	// Followers who are not members are registered by hand, at a counter that registers (MCM > Guild Hall), on by default.
	// Unlike the hall-only toggles it holds without the hall too: the inns register them then.
	void SetFollowersByHand(bool a_on);
	bool FollowersByHand();

	// The promotion trials (2.0, MCM > Guild Hall > Promotion Trials, on by default; tools/hall-private/plans/promotion-trial.md):
	// with the hall's five trial quests loaded, a promotion goes through the Guild Master's trial and costs no fee, and only
	// the hall promotes. Without them (or toggled off), promotion is the old one exactly, fee and innkeepers included.
	void SetTrials(bool a_on);
	bool TrialsOn();                          // the toggle on AND the hall's trial quests loaded
	RE::TESQuest* TrialQuest(int a_rank);     // the trial for rank 1 (D) ... 5 (S), or nullptr
	int  TrialCreatureRank(RE::TESNPC* a_base);  // a trial creature's rank, 1 D ... 5 S (exactly that), or -1
	bool CallTrial(RE::TESQuest* a_quest, const char* a_function);  // a no-argument function of the trial's quest script

	std::vector<RE::FormID> ClerkBases();  // the clerks' actor bases, in the hall's plugin when it is loaded (else none)
	bool IsClerk(RE::Actor* a_actor);       // one of them (kept out of AG_GuildLiaisonFaction: GuildHall.cpp says why)
	bool IsBusinessTopic(std::string_view a_editorID);  // the clerks' "I have guild business." topic, by its editor ID
	// The clerks' other topics (2.0): "RegisterPay", "PromotePay", "Replace" or "CardHandIn" for AGHallClerkTopic<that>,
	// else empty. Guild acts on their lines as on the innkeepers' (the same rules: which lines act, the fee).
	std::string_view ClerkTopic(std::string_view a_editorID);

	// The hall counter's Quests data, added to the counter's: hall, holds [{key, name}], postings (every hold's missives,
	// each with hold, holdName, city), bounties (every hold's posted Jarl's bounty at or below the player's rank, and the
	// player's taken or slain one, the same, with state and payer), newBounty (the hall can hand out a new one).
	void CounterData(nlohmann::json& a_data);
	void NameHold(nlohmann::json& a_row);  // an Intel row with its "city": its hold and holdName too, for the hall's filter

	// The hall's lighting for this install, at kDataLoaded, before any cell loads: the plugin's values are for a game with no
	// screen-space GI; with Community Shaders' SSGI on, whose bounce adds what they would, its template and image space come
	// back down. Read from Community Shaders' own settings, so a player's GI setting is followed at the next start.
	void TuneLighting();
	void ApplyLux();     // with Lux.esp loaded: the hall's three cells on Lux's house template and image space
	void ApplyHelios();  // with Helios.esp loaded: the hall's two windowed cells Show Sky + Use Sky Lighting on Helios_WeatherPineForest
	// The hall folk's own voice types joined to vanilla's voice lists (follower, favour, combat, marriage), at kDataLoaded, so
	// vanilla's follower and marriage dialogue reaches them in their own voices. Only a voice of the hall's own is added (a
	// follower still on a vanilla voice keeps vanilla's lists as they are). In the DLL, not a patch plugin (no master, no
	// override of vanilla's lists): compatibility by DLL.
	void JoinVoiceLists();

	// Prepare to Uninstall (2.0, the release plan of 2026-11-08): the hall's part. PlayerInHall: in any of its three cells (main,
	// basement, strongroom), where the uninstall refuses, as removing the hall would leave the player in a cell that is gone.
	// PrepareUninstall: every running promotion trial cancelled, a hall NPC who follows the player dismissed as their own
	// "It's time for us to part ways." does (vanilla's follower quest, so a follower framework takes over). Returns how many of each.
	bool PlayerInHall();
	std::pair<int, int> PrepareUninstall();
}
