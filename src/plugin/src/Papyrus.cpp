// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "Papyrus.h"

#include "Adventurers.h"
#include "Counter.h"
#include "Diag.h"
#include "Dungeons.h"
#include "Guild.h"
#include "GuildCard.h"
#include "Loc.h"
#include "Party.h"
#include "Kills.h"
#include "LevelDisplay.h"
#include "MissiveWatch.h"
#include "NameHook.h"
#include "PrismaToast.h"
#include "RankCore.h"
#include "Shop.h"

namespace AG
{
	namespace
	{
		constexpr auto kClass = "AG_Native";
		using Tag = RE::StaticFunctionTag;

		// ---- guild / ranks ----
		std::int32_t GetGuildRank(Tag*) { return Guild::Rank(); }
		bool         IsRegistered(Tag*) { return Guild::Registered(); }
		std::int32_t GetMerit(Tag*) { return Guild::Merit(); }
		std::int32_t GetReputation(Tag*) { return Guild::Reputation(); }
		bool         IsPromotionReady(Tag*) { return Guild::PromotionReady(); }
		std::int32_t GetThreatRank(Tag*, RE::Actor* a_actor) { return ThreatRank(a_actor); }
		std::string  GetRankLetter(Tag*, std::int32_t a_rank) { return LetterStr(a_rank); }
		std::int32_t GetRankFromLevel(Tag*, std::int32_t a_level) { return FromLevel(a_level); }

		// Guild rank of any actor: the player's earned rank, an NPC adventurer's rank, or -1.
		// Hidden memberships (assassins) report -1: the secret is kept from other mods too.
		std::int32_t GetActorGuildRank(Tag*, RE::Actor* a_actor)
		{
			if (!a_actor) return -1;
			if (a_actor->IsPlayerRef()) return Guild::Rank();
			const auto info = Adventurers::Of(a_actor);
			return (info.kind == Adventurers::Kind::kMember || info.kind == Adventurers::Kind::kRetired) ? info.rank : -1;
		}
		std::string GetActorGuildStatus(Tag*, RE::Actor* a_actor)  // "member" / "retired" / "none" (hidden reads as none)
		{
			if (!a_actor) return "none";
			if (a_actor->IsPlayerRef()) return Guild::Registered() ? "member" : "none";
			const auto k = Adventurers::Of(a_actor).kind;
			return k == Adventurers::Kind::kHidden ? "none" : Adventurers::KindName(k);
		}

		bool IsGuildLiaison(Tag*, RE::Actor* a_actor) { return Adventurers::IsLiaison(a_actor); }

		void ReloadConfig(Tag*)
		{
			LoadConfig();
			Guild::LoadConfig();
			// on the game thread, like the party's 5 s evaluation that reads the same tables (no overlap)
			SKSE::GetTaskInterface()->AddTask([] { Party::LoadConfig(); });
			Adventurers::Load();
			Shop::Load();
		}

		// ---- MCM: uninstall ----
		bool        IsPreparedForUninstall(Tag*) { return Guild::Dormant(); }
		std::string PrepareUninstall(Tag*) { return Guild::PrepareUninstall(); }
		std::string CancelUninstall(Tag*) { return Guild::CancelUninstall(); }
		std::string UninstallText(Tag*, std::int32_t a_which)
		{
			switch (a_which) {
			case 0:
				return Loc::T("$AG_Uninstall_Confirm", "Prepare Adventurers Guild for removal? This takes back every Guild ability and party bonus "
					"from you and your companions and removes Guild items, so no stat changes stay in your save. Your Guild record is kept, "
					"so Cancel Uninstall can restore it.");
			case 1:
				return Loc::T("$AG_Uninstall_Already", "Already prepared for uninstall. Save, quit, and remove the mod, or use Cancel Uninstall.");
			default:
				return Loc::T("$AG_Uninstall_NotPrepared", "Adventurers Guild is not prepared for uninstall, so there is nothing to cancel.");
			}
		}

		// ---- MCM ----
		bool GetShowGuildRank(Tag*) { return Names::ShowGuild(); }
		void SetShowGuildRank(Tag*, bool a_on) { Names::SetShowGuild(a_on); }
		bool GetShowThreatRank(Tag*) { return Names::ShowThreat(); }
		void SetShowThreatRank(Tag*, bool a_on) { Names::SetShowThreat(a_on); }
		bool GetShowLevelSuffix(Tag*) { return LevelDisplay::Enabled(); }
		void SetShowLevelSuffix(Tag*, bool a_on) { LevelDisplay::SetEnabled(a_on); }
		void SetCardHotkey(Tag*, std::int32_t a_key) { GuildCard::SetHotkey(a_key); }
		void ToggleGuildCard(Tag*) { GuildCard::Toggle(); }
		RE::BSFixedString CardKeyConflictText(Tag*, RE::BSFixedString a_other)
		{
			return Loc::F("$AG_MCM_CardKeyConflict", "This key is already used by:\n{}\n\nUse it for the Guild Card anyway?", a_other.c_str());
		}
		bool GetDetailedLog(Tag*) { return Diag::DetailedLog(); }
		void SetDetailedLog(Tag*, bool a_on) { Diag::SetDetailedLog(a_on); }
		bool GetShowRankUpToast(Tag*) { return PrismaToast::Enabled(); }
		void SetShowRankUpToast(Tag*, bool a_on) { PrismaToast::SetEnabled(a_on); }
		float GetToastSeconds(Tag*) { return PrismaToast::HoldSeconds(); }
		void  SetToastSeconds(Tag*, float a_s) { PrismaToast::SetHoldSeconds(a_s); }
		float GetMinorToastSeconds(Tag*) { return PrismaToast::MinorHoldSeconds(); }
		void  SetMinorToastSeconds(Tag*, float a_s) { PrismaToast::SetMinorHoldSeconds(a_s); }
		std::string GetPlayerLedger(Tag*) { return Guild::LedgerJson(); }  // SkyrimNet: ag_player()
		std::string GetPartyInfo(Tag*, RE::Actor* a_actor) { return Party::SkyrimNetJson(a_actor); }  // SkyrimNet: ag_party()
		std::string GetPartyName(Tag*) { return Party::Name(); }
		// SkyrimNet actions (AG_SkyrimNetActions)
		std::string ActionOpenCounter(Tag*, RE::Actor* a_liaison)
		{
			if (!Adventurers::IsLiaison(a_liaison) || !Guild::Registered()) return "refused";
			Counter::OpenAfterDialogue(Adventurers::LiaisonCity(a_liaison));
			return "opened";
		}
		std::string ActionRegister(Tag*, RE::Actor* a_liaison) { return Guild::ActionRegister(a_liaison); }
		std::string ActionPromote(Tag*, RE::Actor* a_liaison) { return Guild::ActionPromote(a_liaison); }
		std::string ActionReports(Tag*, RE::Actor* a_liaison) { return Guild::ActionReports(a_liaison); }
		std::string ActionReplaceCard(Tag*, RE::Actor* a_liaison) { return Guild::ActionReplaceCard(a_liaison); }
		std::string ActionJoinGuild(Tag*, RE::Actor* a_actor) { return Adventurers::Join(a_actor); }
		std::string GetJoinStatus(Tag*, RE::Actor* a_actor) { return Adventurers::JoinStatus(a_actor); }

		// ---- dev / test (DevBench) ----
		std::string  DebugDump(Tag*) { return Guild::Dump(); }
		// parties (DevBench): the ledger, and the lifecycle without the counter
		std::string DebugPartyDump(Tag*) { return Party::Dump(); }
		std::string DebugPartyFound(Tag*, std::string a_name, RE::Actor* a_founder) { return Party::Found(std::move(a_name), { a_founder }); }
		std::string DebugPartyAdd(Tag*, RE::Actor* a_actor) { return Party::Add(a_actor); }
		std::string DebugPartyRemove(Tag*, RE::Actor* a_actor) { return a_actor ? Party::Remove(Adventurers::StableKey(a_actor)) : ""; }
		std::string DebugPartyDisband(Tag*) { return Party::Disband(); }
		void        DebugPartyBond(Tag*, RE::Actor* a_actor, float a_amount) { Party::AddBond(a_actor, a_amount); }
		std::string  DebugDungeon(Tag*) { return Dungeons::DebugInfo(); }
		std::string  DebugClearDungeon(Tag*) { return Dungeons::DebugClear(); }
		void         DebugRegister(Tag*) { Guild::DebugRegister(); }
		void         DebugPromote(Tag*) { Guild::DebugPromote(); }
		void         DebugSetRank(Tag*, std::int32_t a_rank) { Guild::DebugSetRank(a_rank); }
		void         DebugAddMerit(Tag*, std::int32_t a_n) { Guild::AddReward(a_n, a_n, "debug"); }  // both currencies
		void         DebugAddRep(Tag*, std::int32_t a_n) { Guild::AddReputation(static_cast<float>(a_n), "debug"); }
		std::string  DebugThreat(Tag*) { return Kills::DebugThreat(); }
		std::string  DebugKill(Tag*, std::int32_t a_ref) { return Kills::DebugKill(static_cast<RE::FormID>(a_ref)); }
		void         DebugReset(Tag*) { Guild::DebugReset(); }
		void         DebugBoard(Tag*) { MissiveWatch::DebugBoard(); }
		void         DebugCompleteMissive(Tag*, std::string a_formId) { MissiveWatch::DebugComplete(a_formId); }
		std::string  DebugAdventurer(Tag*, RE::Actor* a_actor) { return Adventurers::Describe(a_actor); }
		void         OpenCounter(Tag*) { Counter::Open(); }
		std::string  DebugLevelLabel(Tag*, std::int32_t a_mode, float a_margin) { return LevelDisplay::DebugFit(a_mode, a_margin); }
		std::string  DebugLevelDump(Tag*, float a_avail) { return LevelDisplay::DebugDump(a_avail); }
		void         DebugToast(Tag*) { PrismaToast::Show("TEST NOTICE", "Adventurers Guild notice check"); }
		void         DebugSetAppraisal(Tag*, std::int32_t a_tier) { Guild::SetAppraisalLevel(a_tier); }
		std::int32_t GetAppraisalLevel(Tag*) { return Guild::AppraisalLevel(); }
		void         DebugAddReport(Tag*, std::string a_title, std::int32_t a_gold, std::int32_t a_merit) { Guild::AddReport("debug", a_title, "Added from DevBench", a_gold, a_merit, a_merit); }
		void         SetNameMode(Tag*, std::int32_t a_mode) { Names::SetMode(a_mode); }
		std::int32_t GetNameMode(Tag*) { return Names::GetMode(); }
		void         NameSiteAllow(Tag*, std::int32_t a_rva, bool a_on) { Names::AllowSite(a_rva, a_on); }
		void         NameSiteReset(Tag*) { Names::ResetCounts(); }
		std::vector<std::string> GetNameSites(Tag*) { return Names::SiteReport(); }
	}

	bool RegisterPapyrus(RE::BSScript::IVirtualMachine* a_vm)
	{
#define REG(fn) a_vm->RegisterFunction(#fn, kClass, fn)
		REG(GetGuildRank);
		REG(IsRegistered);
		REG(GetMerit);
		REG(GetReputation);
		REG(IsPromotionReady);
		REG(GetThreatRank);
		REG(GetRankLetter);
		REG(GetRankFromLevel);
		REG(GetActorGuildRank);
		REG(GetActorGuildStatus);
		REG(ReloadConfig);
		REG(IsPreparedForUninstall);
		REG(PrepareUninstall);
		REG(CancelUninstall);
		REG(UninstallText);
		REG(IsGuildLiaison);
		REG(GetShowGuildRank);
		REG(SetShowGuildRank);
		REG(GetShowThreatRank);
		REG(SetShowThreatRank);
		REG(GetShowLevelSuffix);
		REG(SetShowLevelSuffix);
		REG(SetCardHotkey);
		REG(ToggleGuildCard);
		REG(CardKeyConflictText);
		REG(GetDetailedLog);
		REG(SetDetailedLog);
		REG(GetShowRankUpToast);
		REG(SetShowRankUpToast);
		REG(GetToastSeconds);
		REG(SetToastSeconds);
		REG(GetMinorToastSeconds);
		REG(SetMinorToastSeconds);
		REG(GetPlayerLedger);
		REG(ActionOpenCounter);
		REG(ActionRegister);
		REG(ActionPromote);
		REG(ActionReports);
		REG(ActionReplaceCard);
		REG(ActionJoinGuild);
		REG(GetPartyInfo);
		REG(GetPartyName);
		REG(GetJoinStatus);
		REG(DebugDump);
		REG(DebugPartyDump);
		REG(DebugPartyFound);
		REG(DebugPartyAdd);
		REG(DebugPartyRemove);
		REG(DebugPartyDisband);
		REG(DebugPartyBond);
		REG(DebugDungeon);
		REG(DebugClearDungeon);
		REG(DebugRegister);
		REG(DebugPromote);
		REG(DebugSetRank);
		REG(DebugAddMerit);
		REG(DebugAddRep);
		REG(DebugThreat);
		REG(DebugKill);
		REG(DebugReset);
		REG(DebugBoard);
		REG(DebugCompleteMissive);
		REG(DebugAdventurer);
		REG(OpenCounter);
		REG(DebugToast);
		REG(DebugLevelDump);
		REG(DebugLevelLabel);
		REG(DebugSetAppraisal);
		REG(GetAppraisalLevel);
		REG(DebugAddReport);
		REG(SetNameMode);
		REG(GetNameMode);
		REG(NameSiteAllow);
		REG(NameSiteReset);
		REG(GetNameSites);
#undef REG
		SKSE::log::info("Papyrus natives registered on {}", kClass);
		return true;
	}
}
