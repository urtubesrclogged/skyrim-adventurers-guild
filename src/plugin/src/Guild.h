// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

#include <nlohmann/json.hpp>

// The player's standing with the Adventurers Guild: registration, earned guild rank, Merit and
// Reputation, promotion at any innkeeper, the registration missive, and the co-save.
//
// Two currencies. Merit is spent on guild services (intel, Appraisal, training). Reputation is standing:
// promotion reads it and nothing spends it. Each reward sets its own amount of each (guild.json):
// trophies pay Merit only, kills Reputation only, missives and dungeon reports both.
namespace AG::Guild
{
	void LoadConfig();          // guild.json (also re-run by AG_Native.ReloadConfig)
	void Register();            // at kDataLoaded: resolve our forms, register event sinks
	void SetupSerialization();  // at plugin load
	void OnGameLoaded();        // kPostLoadGame / kNewGame

	bool Registered();
	int  Rank();                // 0..5, -1 when not registered
	int  Merit();
	int  Reputation();
	bool PromotionReady();

	// Reputation for kills, by the victim's threat rank (guild.json "kills").
	struct KillRewards
	{
		std::array<float, 6> rep{ 0.5f, 1.0f, 2.0f, 3.0f, 4.0f, 5.0f };
		float                bossMultiplier{ 5.0f };  // victim placed as a Boss (location ref type)
		float                largeMultiplier{ 2.0f };       // race size Large: centurions, cave bears, atronachs
		float                extraLargeMultiplier{ 5.0f };  // race size Extra Large: dragons, giants, mammoths
		float                followerShare{ 0.5f };   // killed by a follower or the player's summon
		float                assistShare{ 0.5f };     // someone else finished a foe your side hit recently
		float                assistSeconds{ 30.0f };
	};

	void AddMerit(int a_amount, std::string_view a_why);            // Merit only, HUD line
	void AddReputation(float a_amount, std::string_view a_why);     // Reputation only, silent; fractions carry
	void AddReward(int a_merit, int a_rep, std::string_view a_why);  // both, one HUD line
	KillRewards Kills();
	int  MissiveMerit(int a_rank);  // guild.json missiveMerit, 0 if unset
	int  MissiveRep(int a_rank);    // guild.json missiveRep
	int  DungeonRep(int a_rank);    // guild.json dungeonRep
	int  DungeonMerit(int a_rank);  // guild.json dungeonMerit, by the dungeon's threat rank
	int  DungeonGold(int a_rank);   // guild.json dungeonGold
	int  IntelMerit(int a_rank);    // guild.json intelMerit: price of a dungeon's location, by its threat rank
	void OnMissiveCompleted(int a_rank, std::string_view a_title);  // tally + record + a report to hand in
	void OnNoticeCompleted(int a_rank, std::string_view a_title);   // the same for a Notice Board quest (NoticeWatch)

	// Reports: rewards earned in the field (missives, dungeon clears) that wait to be claimed at a counter.
	void        AddReport(std::string a_kind, std::string a_title, std::string a_detail, int a_gold, int a_merit, int a_rep);
	std::string ClaimAll();                          // pays every report; returns a status line
	std::string BuyService(const std::string& a_id);  // returns a status line
	nlohmann::json CounterData();                    // everything the counter window shows
	void SyncGlobals();         // AG_PlayerRankGlobal / AG_RegisteredGlobal / AG_PromotionReadyGlobal

	// Missives board trigger (walked into by the player) -> registration missive when unregistered
	void OnBoardApproached();

	// Passive Guild skills bought with Merit (see Shop): Appraisal tier 0..3 and training steps per stat.
	int   AppraisalLevel();                     // lock-free; read by the name hook every frame
	void  SetAppraisalLevel(int a_tier);
	int   TrainingSteps(int a_stat);            // 0 = Health, 1 = Stamina, 2 = Magicka
	void  AddTrainingStep(int a_stat);
	bool  TrySpendMerit(int a_cost, std::string_view a_record);  // false if not enough; logs a_record
	void  AddGold(int a_amount);
	void  ApplyAbilities();                     // perks/abilities to match Appraisal + training (idempotent)
	// "Prepare to Uninstall" (MCM): take back every ability, perk and item of ours and stay dormant; Cancel undoes it
	bool        Dormant();
	std::string PrepareUninstall();
	std::string CancelUninstall();

	std::string Dump();

	// SkyrimNet actions (AG_SkyrimNetActions -> AG_Native): a Guild rep registering, promoting or taking reports in an
	// AI conversation. Same fees and checks as the dialogue; refused for anyone but a liaison. Return a short status.
	std::string ActionRegister(RE::Actor* a_liaison);
	std::string ActionPromote(RE::Actor* a_liaison);
	std::string ActionReports(RE::Actor* a_liaison);

	// SkyrimNet and other listeners: an SKSE mod event from the player ("AG_DungeonCleared", name, rank...).
	// AG_SkyrimNetInit turns these into remembered events; nothing depends on anyone listening.
	void Notify(const char* a_event, const std::string& a_str, float a_num);

	// For other modules (Party): the in-game day (Calendar days passed), a line in the Records log, and taking a fee
	// from the player (false, and nothing taken, if they cannot pay; a HUD line when paid).
	float Day();
	// career record (Guild Card): a foe credited to the player's side, trophies handed in
	void  CountKill(bool a_big);
	void  CountTrophies(int a_count);
	void  Record(std::string a_text);
	bool  PayGold(int a_amount);
	// The player's page of the Guild ledger, compact JSON for SkyrimNet (liaisons read it; see ag_player()).
	std::string LedgerJson();

	// dev/test (DevBench)
	void DebugRegister();
	void DebugPromote();
	void DebugSetRank(int a_rank);
	void DebugReset();
}
