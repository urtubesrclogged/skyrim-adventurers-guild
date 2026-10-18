// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "Diag.h"
#include "ControlsGuard.h"
#include "GuildCard.h"
#include "Guild.h"

#include "Adventurers.h"
#include "Dungeons.h"
#include "MemberCards.h"
#include "Party.h"
#include "Counter.h"
#include "MissiveWatch.h"
#include "Loc.h"
#include "PrismaToast.h"
#include "RankCore.h"
#include "Shop.h"

#include <SimpleIni.h>
#include <chrono>
#include <deque>
#include <unordered_set>
#include <fstream>
#include <mutex>

namespace AG::Guild
{
	namespace
	{
		constexpr const char* kPlugin = "AdventurersGuild.esp";
		constexpr std::uint32_t kUID = 'AGLD';
		constexpr std::uint32_t kRec = 'DATA';
		constexpr std::size_t   kHistoryCap = 60;

		// ---- config (guild.json) ----
		struct Config
		{
			int                          fee{ 50 };
			int                          promotionFee{ 50 };
			int                          cardFee{ 25 };  // a replacement guild card (the first is free)
			int                          memberCardRep{ 5 };       // Reputation for another adventurer's card brought back
			float                        memberCardDays{ 3.0f };   // days until a member whose card is gone has a replacement
			int                          stampDungeons{ 8 };  // dungeons cleared in a hold for its stamp on the card
			float                        repPerBountyGold{ 0.1f };  // Reputation lost per gold of new bounty
			int                          bountyFeePercent{ 5 };     // the Guild's fee for paying the player's bounties at a counter (1.5.0)
			float                        abandonShare{ 0.5f };      // of a taken missive's Reputation, lost when it is given up
			std::array<int, kRankCount>  reputation{ 0, 100, 300, 700, 1500, 3000 };
			int                          cap{ 2 };  // C
			std::array<int, kRankCount>  missiveMerit{ 5, 10, 15, 25, 30, 50 };
			std::array<int, kRankCount>  missiveRep{ 8, 15, 30, 55, 65, 75 };
			std::array<int, kRankCount>  dungeonMerit{ 5, 10, 20, 30, 40, 50 };
			std::array<int, kRankCount>  dungeonRep{ 10, 20, 40, 70, 110, 170 };
			KillRewards                  kills;
			std::array<int, kRankCount>  dungeonGold{ 50, 100, 175, 275, 400, 600 };
			std::array<int, kRankCount>  intelMerit{ 5, 8, 12, 18, 25, 35 };
		};
		Config g_cfg;

		// ---- state (co-save) ----
		struct Report
		{
			std::string kind, title, detail;
			int         gold{ 0 }, merit{ 0 }, rep{ 0 };
			std::string key;  // a cleared dungeon's report: which dungeon (hold stamps count it once handed in)
		};
		struct Entry
		{
			float       day{ 0 };
			std::string text;
		};

		std::mutex                   g_lock;
		bool                         g_registered{ false };
		int                          g_rank{ -1 };
		int                          g_merit{ 0 };
		int                          g_reputation{ 0 };
		float                        g_repCarry{ 0.0f };  // fractional Reputation (kills pay 0.5) not yet whole
		bool                         g_regMissiveGiven{ false };
		bool                         g_lastReady{ false };
		float                        g_registeredDay{ -1.0f };
		float                        g_promotedDay{ -1.0f };  // game day of the last promotion (world gossip)
		constexpr float              kGossipDays = 3.0f;      // guards talk about a promotion this long
		std::array<int, kRankCount>  g_missives{};
		int                          g_goldEarned{ 0 };
		// career record for the Guild Card (counted from v1.11: older saves start these at 0)
		int                          g_kills{ 0 };        // foes credited to the player's side
		int                          g_bigKills{ 0 };     // dragons, giants, bosses
		int                          g_trophiesSold{ 0 };
		std::vector<Report>          g_reports;   // unclaimed, paid at the counter
		std::deque<Entry>            g_history;   // newest first
		std::atomic<int>             g_appraisal{ 0 };  // 0 = none, 1..3 = Appraisal I..III
		// "Prepare to Uninstall" (MCM): every ability and perk of ours is taken back and nothing re-grants it, so
		// the plugin can be removed without leaving stat changes baked into the save. Cancel restores everything.
		std::atomic<bool>            g_dormant{ false };
		std::atomic<SaveData>        g_saveData{ SaveData::kNone };  // set as a save loads; see Guild.h
		std::array<int, 3>           g_training{};      // purchased steps: Health, Stamina, Magicka

		// ---- our forms ----
		RE::TESGlobal*       g_gRank{ nullptr };
		RE::TESGlobal*       g_gRegistered{ nullptr };
		RE::TESGlobal*       g_gRecentPromo{ nullptr };      // AG_RecentPromotionGlobal: rank just reached, else -1
		RE::TESFaction*      g_retiredFaction{ nullptr };    // AG_RetiredAdventurerFaction, for world dialogue
		RE::TESFaction*      g_wandererFaction{ nullptr };   // AG_WanderingAdventurerFaction: rank in it = their Guild rank
		RE::TESFaction*      g_rankFaction{ nullptr };       // AG_AdventurerRankFaction: a NAMED member's rank (their own lines read it)
		RE::TESFaction*      g_promotedFaction{ nullptr };   // AG_AdventurerPromotedFaction: rank 0 for a few days after one rises
		RE::TESFaction*      g_liaisonFaction{ nullptr };    // AG_GuildLiaisonFaction, for SkyrimNet actions
		RE::TESGlobal*       g_gReports{ nullptr };          // AG_ReportsWaitingGlobal, for SkyrimNet actions
		RE::TESGlobal*       g_gReady{ nullptr };
		RE::TESGlobal*       g_gRegFee{ nullptr };
		RE::TESGlobal*       g_gPromoFee{ nullptr };
		RE::TESGlobal* g_gCardFee{ nullptr };
		// Conduct: the bounty last seen in each crime faction (by StableKey; co-save), so a rise can be told from a
		// bounty the player already had. g_bountyKnown is false on a save from before this existed: the first look only
		// takes note. g_bountyActive: the player has a bounty somewhere, which puts promotion on hold.
		std::map<std::string, int> g_bountySeen;
		bool                       g_bountyKnown{ false };
		double                     g_bountyCarry{ 0.0 };  // the fraction of a Reputation point small bounties have not yet cost
		std::atomic<bool>          g_bountyActive{ false };
		std::string                g_bountyWhere;         // where it is, for the counter: "Whiterun (40 gold)", more joined by commas
		RE::TESTopic*  g_replaceTopic{ nullptr };  // the player's "I've lost my guild card" line: the DLL writes the fee into it
		// Liaison dialogue lines by role (dialogue.resolved.json). Staff/referral lines are not listed,
		// so choosing a topic at a non-guild inn only gets the innkeeper's pointer to the right city.
		//
		// A line is recognised WHEN IT IS SPOKEN, never from a table of forms looked up at start-up (1.4.2). Until 1.4.1
		// each line was looked up once, at kDataLoaded, and kept; on a player's 1.6.1170 game with some 2,900 light
		// plugins every one of the 147 lookups failed (their log, 2026-10-11: "0 register, 0 promote, 0 business lines";
		// every other record of the plugin was found), so for that whole session the innkeeper said her line and nothing
		// happened. The same file on another 1.6.1170 game found them all: the cause is in that install, unknown and not
		// ours to find. So nothing here depends on that moment any more: the line's own ID is taken apart when the game
		// reports it (RoleOfLine), and a line that is not at our IDs is recognised by its topic and kind.
		enum class Role { kNone, kRegister, kPromote, kBusiness, kReplace, kStamp, kCardHandIn };
		RE::TESFaction*                         g_stampEarnedFaction = nullptr;  // on a liaison whose hold's stamp is earned
		RE::TESFaction*                         g_stampDueFaction = nullptr;     // on a stamp keeper who owes the player a stamp
		RE::BGSPerk*                            g_stampPerk = nullptr;           // buy prices x0.85 while g_gStampDiscount is 1
		RE::TESGlobal*                          g_gStampDiscount = nullptr;      // 1 in a hold whose stamp is on the card in hand
		RE::TESGlobal*                          g_gStampWanted = nullptr;        // 1 for a member in a hold whose stamp is not on the card
		std::mutex                              g_stampActorsLock;
		std::vector<RE::ObjectRefHandle>        g_stampActors;                   // liaisons and keepers seen loaded this session
		std::unordered_map<std::uint32_t, Role> g_roleOfLocal;  // the plugin's own line IDs (0xA00...), as the json gives them
		std::atomic<RE::FormID>                 g_ownBase{ 0 }, g_ownMask{ 0 };  // this session's form IDs of the plugin: base and local part
		std::atomic<bool>                       g_saidByTopic{ false };
		std::atomic<std::uint32_t>              g_saidNothing{ 0 };  // one bit for each of the four acting topics: "spoken, nothing done" is logged once
		std::vector<std::uint32_t>              g_lineLocals;        // every line ID the json names, for the count taken again at the first load
		int                                     g_foundAtStart = -1;
		RE::TESQuest*        g_regQuest{ nullptr };
		RE::TESObjectBOOK*   g_regMissive{ nullptr };
		RE::TESBoundObject*  g_gold{ nullptr };
		std::array<RE::BGSPerk*, 3>                g_appraisalPerks{};
		std::array<std::vector<RE::SpellItem*>, 3> g_trainSpells;  // [stat][step-1]
		std::vector<RE::SpellItem*>                g_augmentSpells;  // [index in shop.json's list]
		int                                        g_augment{ -1 };  // the Augment the player has; guarded by g_lock
		float                                      g_augmentUntil{ 0.0f };  // game days passed at which it ends

		void Hud(const std::string& a_msg)
		{
			SKSE::GetTaskInterface()->AddTask([a_msg] { RE::SendHUDMessage::ShowHUDMessage(a_msg.c_str()); });
		}

		void SendModEvent(const char* a_name, const std::string& a_str, float a_num)
		{
			SKSE::ModCallbackEvent ev{ a_name, a_str.c_str(), a_num, RE::PlayerCharacter::GetSingleton() };
			if (auto* src = SKSE::GetModCallbackEventSource()) src->SendEvent(&ev);
		}

		float Today()
		{
			auto* cal = RE::Calendar::GetSingleton();
			return cal ? cal->GetDaysPassed() : 0.0f;
		}

		// caller holds g_lock
		void LogLocked(std::string a_text)
		{
			g_history.push_front({ Today(), std::move(a_text) });
			while (g_history.size() > kHistoryCap) g_history.pop_back();
		}

		// Quest objective display goes through Papyrus (Quest.SetObjectiveDisplayed has no native
		// CommonLib equivalent): tiny global functions in AG_QuestHelper.psc.
		void CallQuestFn(const char* a_fn)
		{
			auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton();
			if (!vm || !g_regQuest) return;
			RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> cb;
			auto* args = RE::MakeFunctionArguments(static_cast<RE::TESQuest*>(g_regQuest));
			vm->DispatchStaticCall("AG_QuestHelper", a_fn, args, cb);
		}

		int GoldCount()
		{
			auto* pc = RE::PlayerCharacter::GetSingleton();
			if (!pc || !g_gold) return 0;
			auto counts = pc->GetInventoryCounts([](RE::TESBoundObject& o) { return &o == g_gold; });
			auto it = counts.find(g_gold);
			return it == counts.end() ? 0 : it->second;
		}

		// caller holds g_lock
		bool ReadyLocked()
		{
			if (!g_registered || g_rank < 0 || g_rank >= kRankCount - 1) return false;
			auto* pc = RE::PlayerCharacter::GetSingleton();
			const int next = g_rank + 1;
			return pc && !g_bountyActive.load() && g_reputation >= g_cfg.reputation[next] && pc->GetLevel() >= MinLevel(next);
		}

		// Everything a promotion needs is met, but a bounty has it on hold
		bool BlockedLocked()
		{
			if (!g_registered || g_rank < 0 || g_rank >= kRankCount - 1 || !g_bountyActive.load()) return false;
			auto* pc = RE::PlayerCharacter::GetSingleton();
			const int next = g_rank + 1;
			return pc && g_reputation >= g_cfg.reputation[next] && pc->GetLevel() >= MinLevel(next);
		}

		// Placement at registration: highest rank whose level floor the player meets, capped.
		int PlacementLocked()
		{
			auto* pc = RE::PlayerCharacter::GetSingleton();
			const int level = pc ? pc->GetLevel() : 1;
			return std::min(FromLevel(level), std::clamp(g_cfg.cap, 0, kRankCount - 1));
		}

		// The "Join the Guild" missive's note has done its job once the player is registered: it goes from their pack
		// (it used to stay, unlike a finished missive's note - Nexus, 2026-10-16). 1.5.0.
		void DropRegistrationNote()
		{
			auto* pc = RE::PlayerCharacter::GetSingleton();
			if (!pc || !g_regMissive) return;
			const auto counts = pc->GetInventoryCounts([](RE::TESBoundObject& a_o) { return &a_o == g_regMissive; });
			const auto it = counts.find(g_regMissive);
			if (it == counts.end() || it->second <= 0) return;
			pc->RemoveItem(g_regMissive, it->second, RE::ITEM_REMOVE_REASON::kRemove, nullptr, nullptr);
			SKSE::log::info("Guild: the registration missive's note is taken from the player's pack (registered)");
		}

		void DoRegister()
		{
			const int fee = g_cfg.fee;
			if (GoldCount() < fee) {
				Hud(Loc::F("$AG_Reg_FeeNeeded", "The Guild's registration fee is {} gold.", fee));
				return;
			}
			int rank;
			{
				std::lock_guard l(g_lock);
				if (g_registered) return;
				g_registered = true;
				g_rank = rank = PlacementLocked();
				g_registeredDay = Today();
				LogLocked(Loc::F("$AG_Log_Registered", "Registered with the Adventurers Guild as a Rank {} adventurer.", Letter(rank)));
			}
			if (fee > 0) {
				RE::PlayerCharacter::GetSingleton()->RemoveItem(g_gold, fee, RE::ITEM_REMOVE_REASON::kRemove, nullptr, nullptr);
				Hud(Loc::F("$AG_Hud_GoldRemoved", "{} gold removed.", fee));
			}
			SyncGlobals();
			CallQuestFn("CompleteRegistrationQuest");
			DropRegistrationNote();
			GuildCard::Sync(true);  // "Here's your guild card."
			PrismaToast::Show(Loc::T("$AG_Toast_Registration", "GUILD REGISTRATION"), Loc::F("$AG_Toast_RankAdventurer", "Rank {} Adventurer", Letter(rank)), std::format("tex/rank_{}.png", Letter(rank)),
				PrismaToast::Priority::kImportant, PrismaToast::Cue::kRegistered);
			Hud(rank > 0 ? Loc::F("$AG_Reg_Assessed", "Your experience has been assessed: you are registered as a Rank {} adventurer.", Letter(rank))
			             : Loc::T("$AG_Reg_RankE", "You are registered as a Rank E adventurer."));
			SendModEvent("AG_Registered", LetterStr(rank), static_cast<float>(rank));
			MissiveWatch::MakeBoardsDue("registration");  // every board refreshes when the player next walks up to it (1.5.0)
			SKSE::log::info("Guild: registered at rank {} (level {})", Letter(rank), RE::PlayerCharacter::GetSingleton()->GetLevel());
		}

		// The crime factions a bounty can be paid to: a jail and a chest for stolen goods, as the holds and Raven Rock
		// have (1.5.0; see the sync below). Read once.
		const std::vector<RE::TESFaction*>& PayableFactions()
		{
			static const std::vector<RE::TESFaction*> list = [] {
				std::vector<RE::TESFaction*> out;
				if (auto* dh = RE::TESDataHandler::GetSingleton())
					for (auto* f : dh->GetFormArray<RE::TESFaction>())
						if (f && f->TracksCrimes() && f->crimeData.factionJailMarker && f->crimeData.factionStolenContainer) out.push_back(f);
				SKSE::log::info("Guild: {} crime factions with a jail and a stolen-goods chest (bounties are read from these)", out.size());
				return out;
			}();
			return list;
		}

		// Every payable bounty the player has now: (faction, gold), and the total
		std::vector<std::pair<RE::TESFaction*, int>> Bounties(int& a_total)
		{
			std::vector<std::pair<RE::TESFaction*, int>> out;
			a_total = 0;
			for (auto* f : PayableFactions())
				if (const int g = f->GetCrimeGold(); g > 0) {
					out.emplace_back(f, g);
					a_total += g;
				}
			return out;
		}

		int BountyFee(int a_total) { return static_cast<int>(std::ceil(a_total * g_cfg.bountyFeePercent / 100.0)); }

		void DoPromote()
		{
			const int fee = g_cfg.promotionFee;
			if (GoldCount() < fee) {   // the dialogue already checks; this guards other paths (DevBench, a mod calling in)
				Hud(Loc::F("$AG_Promo_FeeNeeded", "The Guild's promotion fee is {} gold.", fee));
				return;
			}
			int rank;
			{
				std::lock_guard l(g_lock);
				if (!ReadyLocked()) {
					SKSE::log::info("Guild: promotion requested but not eligible");
					return;
				}
				rank = ++g_rank;
				g_promotedDay = Today();
				LogLocked(Loc::F("$AG_Log_Promoted", "Promoted to Rank {}.", Letter(rank)));
			}
			if (fee > 0) {
				RE::PlayerCharacter::GetSingleton()->RemoveItem(g_gold, fee, RE::ITEM_REMOVE_REASON::kRemove, nullptr, nullptr);
				Hud(Loc::F("$AG_Hud_GoldRemoved", "{} gold removed.", fee));
			}
			SyncGlobals();
			PrismaToast::Show(Loc::T("$AG_Toast_Promoted", "PROMOTED"), Loc::F("$AG_Toast_RankAdventurer", "Rank {} Adventurer", Letter(rank)), std::format("tex/rank_{}.png", Letter(rank)),
				PrismaToast::Priority::kImportant, PrismaToast::Cue::kPromoted);
			Hud(Loc::F("$AG_Promo_Done", "The Guild has promoted you to Rank {}.", Letter(rank)));
			GuildCard::Sync(true);  // "I've updated your guild card."
			SendModEvent("AG_RankChanged", LetterStr(rank), static_cast<float>(rank));
			MissiveWatch::MakeBoardsDue("promotion");
			SKSE::log::info("Guild: promoted to rank {}", Letter(rank));
		}

		// ---- event sinks ----

		// Which of the plugin's own lines a form ID is: true with its local ID (0xA00...) when the ID is one of this
		// plugin's. Worked out from the ID alone; the plugin's base is asked for once it can be given.
		bool OwnLocal(RE::FormID a_id, std::uint32_t& a_local)
		{
			auto base = g_ownBase.load(std::memory_order_relaxed);
			if (!base) {
				auto* dh = RE::TESDataHandler::GetSingleton();
				base = dh ? dh->LookupFormID(0, kPlugin) : 0;
				if (!base) return false;
				g_ownMask = (base >> 24) == 0xFE ? 0xFFFu : 0xFFFFFFu;  // a light plugin's records have 12 bits, a full one's 24
				g_ownBase = base;
			}
			const auto mask = g_ownMask.load(std::memory_order_relaxed);
			if ((a_id & ~mask) != base) return false;
			a_local = a_id & mask;
			return true;
		}

		int GoldCount();  // below

		// What a line that is starting means to the Guild. First by its ID (exact: the line is one of ours and the json
		// names it). Failing that, and only for a line said to the player in conversation, by what it is: the topic it
		// belongs to (topics keep their editor IDs at run time) and its kind. Checked against every INFO of the released
		// plugin (2026-10-11): in AG_TopicRegisterPay, AG_TopicPromotePay and AG_TopicBusiness the lines that act are
		// exactly the ones flagged Goodbye (15 / 15 / 103; the 1 / 1 / 26 others are not); in AG_TopicReplace the 14
		// that act are not flagged, and are told from the other 5 by who speaks (a rep, at her counter) and by the
		// player having the fee. That second way is what still works if a line of ours is not where its ID says.
		Role RoleOfLine(RE::FormID a_id, RE::TESObjectREFR* a_speaker)
		{
			std::uint32_t local = 0;
			const bool    own = OwnLocal(a_id, local);
			if (own)
				if (auto it = g_roleOfLocal.find(local); it != g_roleOfLocal.end()) return it->second;
			auto* mtm = RE::MenuTopicManager::GetSingleton();
			if (!mtm || !a_speaker) return Role::kNone;
			const bool toPlayer = mtm->speaker.get().get() == a_speaker;  // otherwise idle talk: not said to the player
			// A line with one of our IDs that the json does not name is one that does nothing (a greeting, "you can't
			// afford it"), unless the IDs have already proved wrong this session. A line with someone else's ID is looked
			// at even when it is not said to the player: if it turns out to be ours, the log has to say why nothing came of it.
			const bool suspect = !own || g_saidByTopic.load(std::memory_order_relaxed);
			if (!toPlayer && !suspect && !own) return Role::kNone;  // (a line of ours said outside a conversation is looked at: her stamp line)
			auto* info = RE::TESForm::LookupByID<RE::TESTopicInfo>(a_id);
			if (!info && mtm->currentTopicInfo && mtm->currentTopicInfo->GetFormID() == a_id) info = mtm->currentTopicInfo;
			auto*       topic = info ? info->parentTopic : nullptr;
			const char* name = topic ? topic->GetFormEditorID() : nullptr;
			if (!name || std::strncmp(name, "AG_Topic", 8) != 0) return Role::kNone;
			const std::string_view edid(name);
			if (edid.starts_with("AG_TopicStampSaid")) {
				SKSE::log::info("Guild: {} says her stamp line ({}, {:08X})", a_speaker->GetDisplayFullName(), name, a_id);
				Counter::StampLineStarted();
				return Role::kNone;
			}
			const bool             goodbye = info->data.flags.any(RE::TOPIC_INFO_DATA::TOPIC_INFO_FLAGS::kStartSceneOnEnd);  // bit 0: Skyrim's "Goodbye"
			if (edid == "AG_TopicStampAsk") return toPlayer ? Role::kStamp : Role::kNone;  // the line's own conditions say she owes one
			if (edid == "AG_TopicCardHandIn") return toPlayer ? Role::kCardHandIn : Role::kNone;  // likewise: the player carries one
			const int              acting = edid == "AG_TopicRegisterPay" ? 0 : edid == "AG_TopicPromotePay" ? 1 : edid == "AG_TopicBusiness" ? 2 : edid == "AG_TopicReplace" ? 3 : -1;
			if (acting < 0) return Role::kNone;
			Role        role = Role::kNone;
			std::string why;
			if (!toPlayer) {
				auto* with = mtm->speaker.get().get();
				why = std::format("it was not said in the player's conversation (which is with {})", with ? std::format("{:08X}", with->GetFormID()) : std::string("nobody"));
			} else if (acting < 3) {
				if (goodbye) role = acting == 0 ? Role::kRegister : acting == 1 ? Role::kPromote : Role::kBusiness;
				else why = "the line is not one that ends the conversation (in this topic those are the ones that act)";
			} else {
				const bool rep = Adventurers::IsLiaison(a_speaker->As<RE::Actor>());
				const int  gold = GoldCount();
				if (!goodbye && rep && gold >= g_cfg.cardFee) role = Role::kReplace;
				else why = goodbye ? "the line ends the conversation (in this topic those do not act)" : !rep ? "the speaker is not one of the Guild's representatives"
				                   : std::format("the player has {} gold and the card costs {}", gold, g_cfg.cardFee);
			}
			if (role == Role::kNone && suspect && !(g_saidNothing.fetch_or(1u << acting) & (1u << acting)))
				SKSE::log::warn("Guild: line {:08X} of {} was spoken by {:08X} and the Guild did nothing: {}. (Said once for this topic. The line's ID is {}.)", a_id, name,
					a_speaker->GetFormID(), why, own ? "one of ours that the plugin does not know" : "not one of ours");
			if (role != Role::kNone && !g_saidByTopic.exchange(true))
				SKSE::log::warn("Guild: line {:08X} of {} is not at one of this plugin's line IDs ({}) - recognised by its topic and kind instead. Something in this load order has moved the plugin's dialogue; the Guild works all the same.",
					a_id, name, own ? "an ID of ours the plugin does not know" : "not an ID of ours");
			return role;
		}

		// Retired adventurers (a guard or soldier who once held a guild rank, Adventurers::Of) join
		// AG_RetiredAdventurerFaction as they load, so world dialogue can pick them out with a plain
		// GetInFaction condition. The same NPC always gets the same answer, so this is idempotent.
		struct RetiredSink final : RE::BSTEventSink<RE::TESObjectLoadedEvent>
		{
			static RetiredSink* Get()
			{
				static RetiredSink s;
				return &s;
			}

			RE::BSEventNotifyControl ProcessEvent(const RE::TESObjectLoadedEvent* a_e, RE::BSTEventSource<RE::TESObjectLoadedEvent>*) override
			{
				if (!a_e || !a_e->loaded) return RE::BSEventNotifyControl::kContinue;
				const Diag::Timed timed("marking an actor as it loaded (retired adventurers, wanderers, representatives)");
				auto* actor = RE::TESForm::LookupByID<RE::Actor>(a_e->formID);
				if (!actor || actor->IsPlayerRef()) return RE::BSEventNotifyControl::kContinue;
				if (g_retiredFaction && !actor->IsInFaction(g_retiredFaction) && Adventurers::Of(actor).kind == Adventurers::Kind::kRetired)
					actor->AddToFaction(g_retiredFaction, 0);
				// wandering adventurers, at their Guild rank: their greetings ask whether they outrank the player
				if (g_wandererFaction && !actor->IsInFaction(g_wandererFaction) && Adventurers::IsWanderer(actor)) {
					const auto info = Adventurers::Of(actor);
					if (info.kind == Adventurers::Kind::kMember) actor->AddToFaction(g_wandererFaction, static_cast<std::int8_t>(std::clamp(info.rank, 0, 5)));
				}
				// the nine Guild reps, for SkyrimNet actions' is_in_faction(currentActor, "AG_GuildLiaisonFaction")
				if (g_liaisonFaction && !actor->IsInFaction(g_liaisonFaction) && Adventurers::IsLiaison(actor))
					actor->AddToFaction(g_liaisonFaction, 0);
				// hold stamps: a liaison (or a successor) and a stamp keeper carry a mark dialogue reads; kept in step from here on
				if (auto* base = actor->GetActorBase(); base && (Adventurers::IsLiaisonBase(base->GetFormID()) || !Adventurers::StampKeeperCity(actor).empty())) {
					{
						std::lock_guard l(g_stampActorsLock);
						const auto h = actor->GetHandle();
						if (std::find(g_stampActors.begin(), g_stampActors.end(), h) == g_stampActors.end()) g_stampActors.push_back(h);
					}
					SKSE::GetTaskInterface()->AddTask(SyncStampMarks);
				}
				return RE::BSEventNotifyControl::kContinue;
			}
		};
		class Sinks :
			public RE::BSTEventSink<RE::TESTopicInfoEvent>,
			public RE::BSTEventSink<RE::LevelIncrease::Event>
		{
		public:
			static Sinks* Get()
			{
				static Sinks s;
				return &s;
			}

			RE::BSEventNotifyControl ProcessEvent(const RE::TESTopicInfoEvent* a_e, RE::BSTEventSource<RE::TESTopicInfoEvent>*) override
			{
				// Act once, when the innkeeper starts the line (verified in VR).
				if (!a_e || a_e->type != RE::TESTopicInfoEvent::TopicInfoEventType::kTopicBegin) return RE::BSEventNotifyControl::kContinue;
				const auto id = a_e->topicInfoFormID;
				if (!id) return RE::BSEventNotifyControl::kContinue;
				const Diag::Timed timed("looking at a line someone started to speak");
				// every line anyone says comes through here (some 25 a second in a busy inn): all but ours stop at this test
				const Role role = RoleOfLine(id, a_e->speakerRef.get());
				if (role == Role::kNone) return RE::BSEventNotifyControl::kContinue;
				if (role == Role::kStamp) {
					// "There. Markarth's ram.": whoever inherited the inn puts the old liaison's stamp on the card
					const auto hold = Adventurers::StampKeeperCity(a_e->speakerRef.get());
					SKSE::GetTaskInterface()->AddTask([hold] {
						if (!hold.empty()) GuildCard::CollectHoldStamp(hold);
						SyncStampMarks();
					});
					return RE::BSEventNotifyControl::kContinue;
				}
				if (role == Role::kCardHandIn) {
					// other adventurers' guild cards, handed in at this counter
					if (!a_e->speakerRef) return RE::BSEventNotifyControl::kContinue;
					const auto who = a_e->speakerRef->GetHandle();
					SKSE::GetTaskInterface()->AddTask([who] {
						auto  ref = who.get();
						if (auto* actor = ref ? ref->As<RE::Actor>() : nullptr) MemberCards::HandIn(actor);
					});
					return RE::BSEventNotifyControl::kContinue;
				}
				const std::string city = Adventurers::LiaisonCity(a_e->speakerRef.get());
				if (role == Role::kRegister) {
					SKSE::GetTaskInterface()->AddTask([city] {
						const bool was = Registered();
						DoRegister();
						if (!was && Registered()) GuildCard::Stamp(city);
					});
				} else if (role == Role::kPromote) {
					SKSE::GetTaskInterface()->AddTask(DoPromote);
				} else if (role == Role::kReplace) {
					// "Here, a fresh one.": the player's own line named the fee, so it is paid without asking again
					SKSE::GetTaskInterface()->AddTask([city] {
						if (auto msg = GuildCard::Replace(city); !msg.empty()) RE::SendHUDMessage::ShowHUDMessage(msg.c_str());
					});
				} else if (role == Role::kBusiness) {
					// the line is a Goodbye: the counter opens as the menu closes, labelled with this branch
					Counter::OpenAfterDialogue(city, a_e->speakerRef.get());
				}
				return RE::BSEventNotifyControl::kContinue;
			}

			RE::BSEventNotifyControl ProcessEvent(const RE::LevelIncrease::Event*, RE::BSTEventSource<RE::LevelIncrease::Event>*) override
			{
				SKSE::GetTaskInterface()->AddTask(SyncGlobals);
				return RE::BSEventNotifyControl::kContinue;
			}
		};

		// ---- co-save ----
		void OnSave(SKSE::SerializationInterface* a)
		{
			nlohmann::json j;
			{
				std::lock_guard l(g_lock);
				j["v"] = 2;
				j["registered"] = g_registered;
				j["rank"] = g_rank;
				j["merit"] = g_merit;
				j["reputation"] = g_reputation;
				j["repCarry"] = g_repCarry;
				j["regMissive"] = g_regMissiveGiven;
				j["registeredDay"] = g_registeredDay;
				j["promotedDay"] = g_promotedDay;
				j["missives"] = g_missives;
				j["goldEarned"] = g_goldEarned;
				j["kills"] = g_kills;
				j["bigKills"] = g_bigKills;
				j["trophiesSold"] = g_trophiesSold;
				j["appraisal"] = g_appraisal.load();
				j["training"] = g_training;
				if (g_augment >= 0) j["augment"] = { { "index", g_augment }, { "until", g_augmentUntil } };
				j["dormant"] = g_dormant.load();
				j["cardIssued"] = GuildCard::Issued();
				j["cardSeal"] = GuildCard::Seal();
				j["cardStamps"] = GuildCard::HoldStamps();
				j["cardIssuedAt"] = GuildCard::IssuedAt();
				j["cardStampsEver"] = GuildCard::EverStampedList();
				j["bounties"] = g_bountySeen;
				j["bountyKnown"] = g_bountyKnown;
				j["bountyCarry"] = g_bountyCarry;
				j["counterMask"] = ControlsGuard::Masked();  // the engine saves the control flags (ControlsGuard.h)
				auto& reports = j["reports"] = nlohmann::json::array();
				for (auto& r : g_reports) reports.push_back({ { "kind", r.kind }, { "title", r.title }, { "detail", r.detail }, { "gold", r.gold }, { "merit", r.merit }, { "rep", r.rep }, { "key", r.key } });
				auto& history = j["history"] = nlohmann::json::array();
				for (auto& h : g_history) history.push_back({ { "day", h.day }, { "text", h.text } });
			}
			j["recruited"] = Adventurers::Save();
			j["heldS"] = Adventurers::SaveHeldS();
			j["namedRanks"] = Adventurers::SaveNamedRanks();
			j["sLevel"] = GetSLevel();
			j["dungeons"] = Dungeons::Save();
			j["boards"] = MissiveWatch::Save();
			j["memberCards"] = MemberCards::Save();
			j["recruitedDays"] = Adventurers::SaveRecruitedDays();
			j["parties"] = Party::Save();
			const auto s = j.dump();
			a->WriteRecord(kRec, 2, s.data(), static_cast<std::uint32_t>(s.size()));
		}

		void Reset()
		{
			std::lock_guard l(g_lock);
			g_registered = false;
			g_rank = -1;
			g_merit = g_reputation = 0;
			g_repCarry = 0.0f;
			g_regMissiveGiven = false;
			GuildCard::SetIssued(false);
			GuildCard::SetSeal({});
			GuildCard::SetHoldStamps({});
			g_bountySeen.clear();
			g_bountyKnown = false;
			g_bountyCarry = 0.0;
			g_bountyActive = false;
			g_lastReady = false;
			g_registeredDay = -1.0f;
			g_promotedDay = -1.0f;
			g_missives.fill(0);
			g_goldEarned = 0;
			g_kills = g_bigKills = g_trophiesSold = 0;
			g_reports.clear();
			g_history.clear();
			g_appraisal = 0;
			g_training.fill(0);
			g_augment = -1;
			g_augmentUntil = 0.0f;
			g_dormant = false;
		}

		void OnLoad(SKSE::SerializationInterface* a)
		{
			Reset();
			Adventurers::Revert();
			Dungeons::Revert();
			MissiveWatch::Revert();
			MemberCards::Revert();
			Party::Revert();
			SetSLevel(DefaultSLevel());  // a save this mod has never been in: as a new game
			g_saveData = SaveData::kNone;
			std::uint32_t type, ver, len;
			while (a->GetNextRecordInfo(type, ver, len)) {
				if (type != kRec) continue;
				std::string s(len, '\0');
				const auto got = a->ReadRecordData(s.data(), len);
				g_saveData = SaveData::kBroken;  // until every part of it has been read
				if (got != len) {
					SKSE::log::error("Guild: co-save record cut short ({} of {} bytes read); this session takes no posted job down", got, len);
					continue;
				}
				try {
					auto j = nlohmann::json::parse(s);
					{
						std::lock_guard l(g_lock);
						g_registered = j.value("registered", false);
						g_rank = g_registered ? std::clamp(j.value("rank", 0), 0, kRankCount - 1) : -1;
						g_merit = j.value("merit", 0);
						g_reputation = j.value("reputation", 0);
						g_repCarry = j.value("repCarry", 0.0f);
						g_regMissiveGiven = j.value("regMissive", false);
						g_registeredDay = j.value("registeredDay", -1.0f);
						g_promotedDay = j.value("promotedDay", -1.0f);
						if (j.contains("missives")) {
							auto v = j.at("missives").get<std::vector<int>>();
							for (std::size_t i = 0; i < g_missives.size() && i < v.size(); ++i) g_missives[i] = v[i];
						}
						g_goldEarned = j.value("goldEarned", 0);
						g_kills = j.value("kills", 0);
						g_bigKills = j.value("bigKills", 0);
						g_trophiesSold = j.value("trophiesSold", 0);
						g_appraisal = std::clamp(j.value("appraisal", 0), 0, 3);
						g_dormant = j.value("dormant", false);
						GuildCard::SetIssued(j.value("cardIssued", false));
						GuildCard::SetSeal(j.value("cardSeal", std::string()));
						GuildCard::SetHoldStamps(j.value("cardStamps", std::vector<std::string>{}));
						GuildCard::SetIssuedAt(j.value("cardIssuedAt", std::string()));
						// a save from before this was kept: what is on the card now has been stamped before
						GuildCard::SetEverStamped(j.value("cardStampsEver", j.value("cardStamps", std::vector<std::string>{})));
						g_bountySeen = j.value("bounties", std::map<std::string, int>{});
						g_bountyKnown = j.value("bountyKnown", false);
						g_bountyCarry = j.value("bountyCarry", 0.0);
						ControlsGuard::Saved(j.value("counterMask", false));
						if (j.contains("augment")) {
							g_augment = j.at("augment").value("index", -1);
							g_augmentUntil = j.at("augment").value("until", 0.0f);
						}
						if (j.contains("training")) {
							auto v = j.at("training").get<std::vector<int>>();
							for (std::size_t i = 0; i < g_training.size() && i < v.size(); ++i) g_training[i] = std::max(0, v[i]);
						}
						for (auto& r : j.value("reports", nlohmann::json::array())) {
							g_reports.push_back({ r.value("kind", ""), r.value("title", ""), r.value("detail", ""), r.value("gold", 0), r.value("merit", 0), r.value("rep", r.value("merit", 0)), r.value("key", "") });
						}
						for (auto& h : j.value("history", nlohmann::json::array())) {
							g_history.push_back({ h.value("day", 0.0f), h.value("text", "") });
						}
						// saves registered before registeredDay existed: recover it from the registration record
						if (g_registered && g_registeredDay < 0.0f) {
							for (auto& h : g_history) {
								if (h.text.starts_with("Registered with the Adventurers Guild")) g_registeredDay = h.day;
							}
						}
					}
					if (j.contains("recruited")) Adventurers::Load(j.at("recruited"));
					if (j.contains("heldS")) Adventurers::LoadHeldS(j.at("heldS"));
					if (j.contains("namedRanks")) Adventurers::LoadNamedRanks(j.at("namedRanks"));
					// a save from before 1.4.0 keeps the levels it always had; the MCM (which holds the setting) agrees
					SetSLevel(j.value("sLevel", kSLevelBefore140));
					Dungeons::Load(j.value("dungeons", nlohmann::json::object()));
					MissiveWatch::Load(j.value("boards", nlohmann::json::object()));
					MemberCards::Load(j.value("memberCards", nlohmann::json::object()));
					Adventurers::LoadRecruitedDays(j.value("recruitedDays", nlohmann::json::object()));  // after "recruited", which clears them
					Party::Load(j.value("parties", nlohmann::json::array()));
					g_saveData = SaveData::kClean;
				} catch (const std::exception& e) {
					SKSE::log::error("Guild: co-save parse error: {}; this session takes no posted job down", e.what());
				}
			}
			SKSE::log::info("Guild: co-save loaded ({})", Dump());
			if (const auto [changed, lost] = Adventurers::TakeKeyStats(); changed || lost)
				SKSE::log::info("Guild: saved keys - {} corrected (written by a build before 1.1.0), {} no longer found (their mod is not loaded)", changed, lost);
			else
				SKSE::log::info("Guild: saved keys - all as written");
		}

		void OnRevert(SKSE::SerializationInterface*)
		{
			Reset();
			Adventurers::Revert();
			Dungeons::Revert();
			MissiveWatch::Revert();
			MemberCards::Revert();
			Party::Revert();
			SetSLevel(DefaultSLevel());
			g_saveData = SaveData::kNone;
		}

		template <class T>
		T* Own(RE::FormID a_local)
		{
			auto* dh = RE::TESDataHandler::GetSingleton();
			auto* f = dh ? dh->LookupForm<T>(a_local, kPlugin) : nullptr;
			if (!f) SKSE::log::error("Guild: {} 0x{:03X} not found in {} - is the plugin enabled?", typeid(T).name(), a_local, kPlugin);
			return f;
		}
	}

	void LoadConfig()
	{
		Config c;
		try {
			std::ifstream f("Data/SKSE/Plugins/AdventurersGuild/guild.json");
			if (f) {
				auto j = nlohmann::json::parse(f, nullptr, true, true);
				c.fee = std::max(0, j.value("registrationFee", c.fee));
				c.promotionFee = std::max(0, j.value("promotionFee", c.promotionFee));
				c.cardFee = std::max(0, j.value("cardReplacementFee", c.cardFee));
				c.stampDungeons = std::max(1, j.value("stampDungeons", c.stampDungeons));
				c.memberCardRep = std::max(0, j.value("memberCardReputation", c.memberCardRep));
				c.memberCardDays = std::max(0.0f, j.value("memberCardReplaceDays", c.memberCardDays));
				if (j.contains("conduct")) {
					c.repPerBountyGold = std::max(0.0f, j.at("conduct").value("repPerBountyGold", c.repPerBountyGold));
					c.bountyFeePercent = std::clamp(j.at("conduct").value("bountyFeePercent", c.bountyFeePercent), 0, 100);
					c.abandonShare = std::clamp(j.at("conduct").value("abandonShare", c.abandonShare), 0.0f, 1.0f);
				}
				if (j.contains("promotion")) {
					auto& p = j.at("promotion");
					auto fill = [&](const char* k, std::array<int, kRankCount>& out) {
						if (!p.contains(k)) return;
						auto v = p.at(k).get<std::vector<int>>();
						for (std::size_t i = 0; i < out.size() && i < v.size(); ++i) out[i] = v[i];
					};
					fill("reputation", c.reputation);
				}
				const auto cap = j.value("registrationCap", std::string("C"));
				if (const int r = FromLetter(cap.empty() ? '?' : cap[0]); r >= 0) c.cap = r;
				auto byRank = [&](const char* a_key, std::array<int, kRankCount>& a_out) {
					if (!j.contains(a_key)) return;
					for (auto& [k, v] : j.at(a_key).items()) {
						if (const int r = FromLetter(k.empty() ? '?' : k[0]); r >= 0) a_out[r] = v.get<int>();
					}
				};
				byRank("missiveMerit", c.missiveMerit);
				byRank("missiveRep", c.missiveRep);
				byRank("dungeonMerit", c.dungeonMerit);
				Dungeons::SetNotDungeons(j.value("notDungeons", std::vector<std::string>{ "Skyrim.esm|0x108A5A", "Skyrim.esm|0x0C342D" }));
				Dungeons::SetPointsOfInterest(j.value("pointsOfInterest", nlohmann::json::object()));
				byRank("dungeonRep", c.dungeonRep);
				if (j.contains("kills")) {
					auto& k = j.at("kills");
					if (k.contains("reputation")) {
						for (auto& [key, v] : k.at("reputation").items()) {
							if (const int r = FromLetter(key.empty() ? '?' : key[0]); r >= 0) c.kills.rep[r] = std::max(0.0f, v.get<float>());
						}
					}
					c.kills.bossMultiplier = std::max(0.0f, k.value("bossMultiplier", c.kills.bossMultiplier));
					c.kills.largeMultiplier = std::max(0.0f, k.value("largeMultiplier", c.kills.largeMultiplier));
					c.kills.extraLargeMultiplier = std::max(0.0f, k.value("extraLargeMultiplier", c.kills.extraLargeMultiplier));
					c.kills.followerShare = std::clamp(k.value("followerShare", c.kills.followerShare), 0.0f, 1.0f);
					c.kills.assistShare = std::clamp(k.value("assistShare", c.kills.assistShare), 0.0f, 1.0f);
					c.kills.assistSeconds = std::max(0.0f, k.value("assistSeconds", c.kills.assistSeconds));
				}
				byRank("dungeonGold", c.dungeonGold);
				byRank("intelMerit", c.intelMerit);
			} else {
				SKSE::log::warn("Guild: guild.json missing - using defaults");
			}
		} catch (const std::exception& e) {
			SKSE::log::error("Guild: guild.json error: {} - using defaults", e.what());
			c = {};
		}
		{
			std::lock_guard l(g_lock);
			g_cfg = c;
		}
		auto join = [](const std::array<int, kRankCount>& a) {
			std::string s;
			for (auto v : a) s += (s.empty() ? "" : ",") + std::to_string(v);
			return s;
		};
		SKSE::log::info("Guild: fee {}, cap {}, promotion rep [{}]", c.fee, Letter(c.cap), join(c.reputation));
		if (RE::PlayerCharacter::GetSingleton()) SyncGlobals();
	}

	void Register()
	{
		g_gRank = Own<RE::TESGlobal>(0x800);
		g_gRegistered = Own<RE::TESGlobal>(0x801);
		g_gReady = Own<RE::TESGlobal>(0x802);
		g_gRegFee = Own<RE::TESGlobal>(0x814);
		g_gPromoFee = Own<RE::TESGlobal>(0x815);
		g_gCardFee = Own<RE::TESGlobal>(0x81D);
		g_replaceTopic = Own<RE::TESTopic>(0x81C);
		g_gRecentPromo = Own<RE::TESGlobal>(0x8C5);
		g_retiredFaction = Own<RE::TESFaction>(0x8C4);
		g_liaisonFaction = Own<RE::TESFaction>(0x8C6);
		g_stampEarnedFaction = Own<RE::TESFaction>(0xCEA);
		g_stampDueFaction = Own<RE::TESFaction>(0xCEB);
		g_stampPerk = Own<RE::BGSPerk>(0xCF5);
		g_gStampDiscount = Own<RE::TESGlobal>(0xCF4);
		g_gStampWanted = Own<RE::TESGlobal>(0xCF6);
		g_wandererFaction = Own<RE::TESFaction>(0xC80);
		g_rankFaction = Own<RE::TESFaction>(0xC91);
		g_promotedFaction = Own<RE::TESFaction>(0xC92);
		g_gReports = Own<RE::TESGlobal>(0x8C7);
		RE::ScriptEventSourceHolder::GetSingleton()->AddEventSink<RE::TESObjectLoadedEvent>(RetiredSink::Get());
		int lines = 0, found = 0;
		try {
			std::ifstream df("Data/SKSE/Plugins/AdventurersGuild/dialogue.resolved.json");
			auto dj = nlohmann::json::parse(df, nullptr, true, true);
			g_roleOfLocal.clear();
			auto* dh = RE::TESDataHandler::GetSingleton();
			auto  load = [&](const char* a_role, Role a_is) {
				for (auto& hex : dj.at("roles").value(a_role, nlohmann::json::array())) {
					const auto local = static_cast<std::uint32_t>(std::stoul(hex.get<std::string>(), nullptr, 16));
					g_roleOfLocal[local] = a_is;
					g_lineLocals.push_back(local);
					++lines;
					// only to say so in the log: nothing is kept from this, and nothing depends on it
					if (dh && dh->LookupForm<RE::TESTopicInfo>(local, kPlugin)) ++found;
				}
			};
			load("register", Role::kRegister);
			load("promote", Role::kPromote);
			load("business", Role::kBusiness);
			load("replace", Role::kReplace);
			load("stamp", Role::kStamp);
			load("cardhandin", Role::kCardHandIn);
		} catch (const std::exception& e) {
			SKSE::log::error("Guild: dialogue.resolved.json error: {} - guild dialogue will do nothing", e.what());
		}
		g_regQuest = Own<RE::TESQuest>(0x810);
		g_regMissive = Own<RE::TESObjectBOOK>(0x811);
		g_gold = RE::TESForm::LookupByID<RE::TESBoundObject>(0x0000000F);
		for (int t = 0; t < 3; ++t) g_appraisalPerks[t] = Own<RE::BGSPerk>(0x820 + t);
		// Training steps: 0x840 + stat*0x20 + (step-1), as many as the ESP carries (stops at the first gap).
		auto* dh = RE::TESDataHandler::GetSingleton();
		for (int st = 0; st < 3; ++st) {
			g_trainSpells[st].clear();
			for (int n = 0; n < 32; ++n) {
				auto* sp = dh->LookupForm<RE::SpellItem>(0x840 + st * 0x20 + n, kPlugin);
				if (!sp) break;
				g_trainSpells[st].push_back(sp);
			}
		}
		g_augmentSpells.clear();
		for (int n = 0; n < 8; ++n) {
			auto* sp = dh->LookupForm<RE::SpellItem>(0xCC0 + n, kPlugin);
			if (!sp) break;
			g_augmentSpells.push_back(sp);
		}

		auto* s = Sinks::Get();
		RE::ScriptEventSourceHolder::GetSingleton()->AddEventSink<RE::TESTopicInfoEvent>(s);
		if (auto* src = RE::LevelIncrease::GetEventSource()) src->AddEventSink(s);
		SKSE::log::info("Guild: {} dialogue lines act for the Guild; they are recognised as they are spoken. Sinks registered", lines);
		// For testing the second way of recognising a line: [Debug] ForgetLineIDs = 1 empties the table of line IDs, so
		// every line has to be recognised by its topic and kind, as on an install where the IDs are of no use.
		{
			CSimpleIniA ini;
			ini.SetUnicode();
			if (ini.LoadFile("Data/SKSE/Plugins/AdventurersGuild.ini") >= 0 && ini.GetBoolValue("Debug", "ForgetLineIDs", false)) {
				g_roleOfLocal.clear();
				SKSE::log::warn("Guild: [Debug] ForgetLineIDs is on - no line is known by its ID; each is recognised by its topic and kind (a test setting)");
			}
		}
		g_foundAtStart = found;
		if (found < lines) {
			// The 1.4.1 failure, seen for what it is. What the game does hold for our topics goes in the log, so the next
			// such report says how: no lines yet (they come later), or lines under other IDs (something renumbered them).
			SKSE::log::warn("Guild: the game gave back {} of those {} lines by their IDs at start-up. 1.4.1 and earlier did nothing for a line it could not find here; from 1.4.2 this no longer matters. For the record:", found, lines);
			for (const RE::FormID t : { RE::FormID{ 0x816 }, RE::FormID{ 0x818 }, RE::FormID{ 0x80C }, RE::FormID{ 0x81C } }) {
				auto* dh = RE::TESDataHandler::GetSingleton();
				auto* topic = dh ? dh->LookupForm<RE::TESTopic>(t, kPlugin) : nullptr;
				if (!topic) {
					SKSE::log::warn("Guild:   topic 0x{:03X}: not found either", t);
					continue;
				}
				std::string ids;
				for (std::uint32_t i = 0; i < topic->numTopicInfos && i < 6 && topic->topicInfos; ++i)
					if (auto* x = topic->topicInfos[i]) ids += std::format(" {:08X}", x->GetFormID());
				SKSE::log::warn("Guild:   topic 0x{:03X} {} ({:08X}): {} lines in the game{}{}", t, topic->GetFormEditorID() ? topic->GetFormEditorID() : "", topic->GetFormID(),
					topic->numTopicInfos, ids.empty() ? "" : ", the first:", ids);
			}
		}
	}

	void SetupSerialization()
	{
		auto* s = SKSE::GetSerializationInterface();
		s->SetUniqueID(kUID);
		s->SetSaveCallback(OnSave);
		s->SetLoadCallback(OnLoad);
		s->SetRevertCallback(OnRevert);
	}

	void OnGameLoaded()
	{
		// Quiet re-sync: a player who was already eligible when they saved is not "newly" ready. Announcing here
		// fired during the loading screen, where the notice can't be seen. Only a change during play announces.
		{
			std::lock_guard l(g_lock);
			g_lastReady = ReadyLocked();
		}
		SyncGlobals();
		ApplyAbilities();
		if (Registered()) DropRegistrationNote();  // a game registered with a 1.5.0 beta still carries it
		// Once: the count of lines found by their IDs, taken again now that a game is loaded. Said only when it differs
		// from start-up - which would mean the answer depends on when it is asked (a timing fault, not a renumbering).
		static std::atomic<bool> counted{ false };
		if (!counted.exchange(true) && g_foundAtStart >= 0) {
			auto* dh = RE::TESDataHandler::GetSingleton();
			int   now = 0;
			for (const auto local : g_lineLocals)
				if (dh && dh->LookupForm<RE::TESTopicInfo>(local, kPlugin)) ++now;
			if (now != g_foundAtStart)
				SKSE::log::warn("Guild: {} of {} dialogue lines are found by their IDs now that a game is loaded; at start-up it was {}. The answer depends on when it is asked.", now,
					g_lineLocals.size(), g_foundAtStart);
		}
	}

	SaveData SaveState() { return g_saveData.load(); }
	bool Registered() { std::lock_guard l(g_lock); return g_registered; }
	int  Rank() { std::lock_guard l(g_lock); return g_registered ? g_rank : -1; }
	int  Merit() { std::lock_guard l(g_lock); return g_merit; }
	int  Reputation() { std::lock_guard l(g_lock); return g_reputation; }
	bool PromotionReady() { std::lock_guard l(g_lock); return ReadyLocked(); }

	namespace
	{
		// Credits both currencies under one lock; false when not registered. Reputation keeps its
		// fraction in g_repCarry so half-credit kills add up exactly.
		bool Credit(int a_merit, float a_rep, int& a_repWhole)
		{
			std::lock_guard l(g_lock);
			if (!g_registered) return false;  // the Guild only credits members
			g_merit += std::max(0, a_merit);
			g_repCarry += std::max(0.0f, a_rep);
			a_repWhole = static_cast<int>(g_repCarry);
			g_repCarry -= static_cast<float>(a_repWhole);
			g_reputation += a_repWhole;
			return true;
		}
	}

	// Reputation taken away (conduct). A rank is never lost; Reputation does not go below zero.
	void LoseReputation(int a_amount, const std::string& a_why)
	{
		if (a_amount <= 0) return;
		int lost;
		{
			std::lock_guard l(g_lock);
			if (!g_registered) return;
			lost = std::min(a_amount, g_reputation);
			if (lost <= 0) return;  // nothing left to lose: no ledger line, no notice
			g_reputation -= lost;
			LogLocked(Loc::F("$AG_Log_RepLost", "Lost {} Reputation: {}.", lost, a_why));
		}
		SKSE::log::info("Guild: -{} reputation ({})", lost, a_why);
		if (lost > 0) {
			PrismaToast::Show(Loc::T("$AG_Toast_RepLost", "REPUTATION LOST"), Loc::F("$AG_Toast_RepLostSub", "-{} Reputation · {}", lost, a_why), {},
				PrismaToast::Priority::kImportant, PrismaToast::Cue::kReputationLost);
			Hud(Loc::F("$AG_Hud_RepLost", "-{} Guild Reputation ({})", lost, a_why));
		}
		SyncGlobals();
		Counter::Refresh();
	}

	// The player's bounties, read every few seconds (the tick Party runs). A rise in a hold costs Reputation; any
	// bounty at all puts promotion on hold until it is paid or served. Only what a hold knows about counts.
	// Wandering adventurers near the player, kept in their faction at their Guild rank. The load event (RetiredSink)
	// does this too, but it does not reach every actor: one spawned by an encounter script was seen without it.
	void SyncWanderers()
	{
		auto* pl = RE::ProcessLists::GetSingleton();
		if (!g_wandererFaction || !pl || Dormant()) return;
		for (auto& h : pl->highActorHandles) {
			auto* actor = h.get().get();
			if (!actor || actor->IsPlayerRef() || actor->IsDead()) continue;
			const bool wanderer = Adventurers::IsWanderer(actor), named = !wanderer && g_rankFaction && Adventurers::IsNamed(actor);
			if (!wanderer && !named) continue;
			const auto info = Adventurers::Of(actor);
			if (info.kind != Adventurers::Kind::kMember) {
				if (named && actor->GetFactionRank(g_rankFaction, false) >= 0) actor->AddToFaction(g_rankFaction, -1);   // retired: no rank to speak of
				continue;
			}
			const auto rank = static_cast<std::int8_t>(std::clamp(info.rank, 0, 5));
			if (wanderer) {
				if (!actor->IsInFaction(g_wandererFaction) || actor->GetFactionRank(g_wandererFaction, false) != rank) actor->AddToFaction(g_wandererFaction, rank);
				continue;
			}
			// a named member (Uthgerd, Teldryn Sero): the lines in which they state their own rank are conditioned on this
			if (actor->GetFactionRank(g_rankFaction, false) != rank) actor->AddToFaction(g_rankFaction, rank);
			if (Adventurers::NoteRank(actor, rank, Today())) {
				const std::string name = actor->GetDisplayFullName();
				SKSE::log::info("Guild: {} rose to rank {} at the player's side", name, Letter(rank));
				RE::SendHUDMessage::ShowHUDMessage(Loc::F("$AG_Hud_CompanionPromoted", "{} has been promoted to Rank {} by the Adventurers Guild.", name, Letter(rank)).c_str());
			}
			if (g_promotedFaction) {
				const bool recent = Adventurers::RecentlyPromoted(actor, Today(), kGossipDays), marked = actor->GetFactionRank(g_promotedFaction, false) >= 0;
				if (recent != marked) actor->AddToFaction(g_promotedFaction, recent ? 0 : -1);
			}
		}
	}

	namespace
	{
		void AugmentTick();  // below, with the abilities
	}

	void SyncStampMarks()
	{
		if (!g_stampEarnedFaction || !g_stampDueFaction) return;
		std::vector<RE::ObjectRefHandle> seen;
		{
			std::lock_guard l(g_stampActorsLock);
			seen = g_stampActors;
		}
		const bool member = Registered() && !Dormant();
		const auto onCard = GuildCard::HoldStamps();
		// the standing a stamp gives: 15% off what merchants sell, in a hold whose stamp is on the card the player carries
		if (g_stampPerk && g_gStampDiscount) {
			auto* pc = RE::PlayerCharacter::GetSingleton();
			if (pc && member && !pc->HasPerk(g_stampPerk)) pc->AddPerk(g_stampPerk);
			const auto here = Dungeons::CityHere();
			const float on = member && GuildCard::Has() && !here.empty() && std::find(onCard.begin(), onCard.end(), here) != onCard.end() ? 1.0f : 0.0f;
			// ... and where it is not on the card, a few people say it would be worth having
			if (g_gStampWanted) g_gStampWanted->value = member && !here.empty() && on == 0.0f ? 1.0f : 0.0f;
			if (g_gStampDiscount->value != on) {
				g_gStampDiscount->value = on;
				SKSE::log::info("Guild: hold stamp standing {} ({})", on > 0.0f ? "applies here" : "does not apply here", here.empty() ? "no hold" : here);
			}
		}
		// a_rank: the rank to hold in the faction when in it (a keeper's is 1 while her hold has never stamped a card)
		const auto set = [](RE::Actor* a_actor, RE::TESFaction* a_faction, bool a_in, std::int8_t a_rank = 0) {
			const std::int8_t want = a_in ? a_rank : -1;
			if (a_actor->GetFactionRank(a_faction, false) != want) a_actor->AddToFaction(a_faction, want);
		};
		for (auto& h : seen) {
			auto ref = h.get();
			auto* actor = ref ? ref->As<RE::Actor>() : nullptr;
			if (!actor || !actor->Is3DLoaded()) continue;
			// a liaison at her counter: is her hold's stamp earned? (her replacement reply says the new card is stamped)
			const auto city = Adventurers::IsLiaison(actor) ? Adventurers::LiaisonCity(actor) : std::string();
			set(actor, g_stampEarnedFaction, member && !city.empty() && Dungeons::ClearedIn(city) >= StampDungeons());
			// a keeper: does she owe the player a stamp? (earned, not on the card, and the card is in hand)
			const auto hold = Adventurers::StampKeeperCity(actor);
			set(actor, g_stampDueFaction, member && !hold.empty() && GuildCard::Has() && Dungeons::ClearedIn(hold) >= StampDungeons() &&
				std::find(onCard.begin(), onCard.end(), hold) == onCard.end(), GuildCard::EverStamped(hold) ? 0 : 1);
		}
	}

	void ConductTick()
	{
		SyncWanderers();
		SyncSuccessors();
		SyncStampMarks();
		MemberCards::Sync();
		AugmentTick();
		auto* pc = RE::PlayerCharacter::GetSingleton();
		if (!pc || !pc->Is3DLoaded() || Dormant()) return;
		std::vector<std::pair<std::string, int>> rises;  // hold name, gold
		bool                                     any = false, was;
		{
			std::lock_guard l(g_lock);
			if (!g_registered) return;
			std::map<std::string, int> now;
			// asked of the game itself, faction by faction (what a guard's dialogue and Papyrus read): the player's own
			// bounty table read directly came back empty on SE 1.5.97
			const auto& crimeFactions = PayableFactions();
			std::string where;
			for (auto* faction : crimeFactions) {
				const int bounty = faction->GetCrimeGold();
				if (bounty <= 0) continue;
				any = true;
				{
					const char* n = faction->GetName();
					where += std::format("{}{} ({} gold)", where.empty() ? "" : ", ", n && *n ? n : Adventurers::StableKey(faction), bounty);
				}
				const auto key = Adventurers::StableKey(faction);
				now[key] = bounty;
				const auto seen = g_bountySeen.find(key);
				const int  before = seen == g_bountySeen.end() ? 0 : seen->second;
				if (g_bountyKnown && bounty > before) {
					const char* n = faction->GetName();
					rises.emplace_back(n && *n ? n : "", bounty - before);
				}
			}
			g_bountySeen = std::move(now);
			g_bountyKnown = true;
			was = g_bountyActive.exchange(any);
			g_bountyWhere = where;
		}
		for (auto& [hold, gold] : rises) {
			// exactly the share of the bounty, however it was run up: a small rise that is not yet worth a point is
			// carried to the next one, so a hundred petty thefts cost what one theft of the same total does
			int loss;
			{
				std::lock_guard l(g_lock);
				g_bountyCarry += gold * static_cast<double>(g_cfg.repPerBountyGold);
				loss = static_cast<int>(std::floor(g_bountyCarry + 1e-6));
				g_bountyCarry -= loss;
			}
			if (loss > 0) LoseReputation(loss, hold.empty() ? Loc::T("$AG_Why_Bounty", "a bounty on your head") : Loc::F("$AG_Why_BountyIn", "a bounty in {}", hold));
		}
		if (was != any) {
			bool blocked;
			{
				std::lock_guard l(g_lock);
				blocked = BlockedLocked();
			}
			if (any && blocked) Hud(Loc::T("$AG_Hud_PromoHold", "The Guild has put your promotion on hold until your bounty is cleared."));
			std::string where;
			{
				std::lock_guard l(g_lock);
				where = g_bountyWhere;
			}
			if (any) SKSE::log::info("Guild: bounty active ({}) - promotion on hold", where);
			else SKSE::log::info("Guild: bounty cleared - promotion no longer on hold");
			SyncGlobals();  // the promotion topic and the "ready" notice follow
			Counter::Refresh();
		}
	}

	// A missive or notice the player took and then gave up or failed
	void OnMissiveAbandoned(int a_rank, std::string_view a_title)
	{
		const int loss = std::max(1, static_cast<int>(std::lround(MissiveRep(a_rank) * g_cfg.abandonShare)));
		LoseReputation(loss, Loc::F("$AG_Why_Abandoned", "abandoned: {}", a_title));
	}

	void AddMerit(int a_amount, std::string_view a_why)
	{
		if (a_amount <= 0) return;
		int whole = 0;
		if (!Credit(a_amount, 0.0f, whole)) return;
		Hud(Loc::F("$AG_Hud_Merit", "+{} Guild Merit ({})", a_amount, a_why));
		SKSE::log::info("Guild: +{} merit ({})", a_amount, a_why);
		SyncGlobals();
		Counter::Refresh();
	}

	void AddReputation(float a_amount, std::string_view a_why)
	{
		if (a_amount <= 0.0f) return;
		int whole = 0;
		if (!Credit(0, a_amount, whole)) return;
		// one line per kill is most of a session's log: kills go to the detailed log, everything else stays
		if (a_why.starts_with("killed")) SKSE::log::debug("Guild: +{} reputation ({}), {} whole", a_amount, a_why, whole);
		else SKSE::log::info("Guild: +{} reputation ({}), {} whole", a_amount, a_why, whole);
		if (whole > 0) {  // silent: kills would spam the HUD; the counter shows the total
			SyncGlobals();
			Counter::Refresh();
		}
	}

	void AddReward(int a_merit, int a_rep, std::string_view a_why)
	{
		if (a_merit <= 0 && a_rep <= 0) return;
		int whole = 0;
		if (!Credit(a_merit, static_cast<float>(a_rep), whole)) return;
		std::string parts;
		if (a_merit > 0) parts = Loc::F("$AG_Hud_MeritPart", "+{} Guild Merit", a_merit);
		if (a_rep > 0) parts += (parts.empty() ? "" : ", ") + Loc::F("$AG_Hud_RepPart", "+{} Reputation", a_rep);
		Hud(std::format("{} ({})", parts, a_why));
		SKSE::log::info("Guild: +{} merit +{} reputation ({})", a_merit, a_rep, a_why);
		SyncGlobals();
		Counter::Refresh();
	}

	void OnMissiveCompleted(int a_rank, std::string_view a_title)
	{
		const int merit = MissiveMerit(a_rank), rep = MissiveRep(a_rank);
		{
			std::lock_guard l(g_lock);
			if (!g_registered) return;
			if (a_rank >= 0 && a_rank < kRankCount) ++g_missives[a_rank];
			LogLocked(Loc::F("$AG_Log_Missive", "Completed a Rank {} missive: {}.", Letter(a_rank), a_title));
		}
		Party::OnMissiveCompleted(a_rank);
		// Credit waits for the report: hand it in at any guild counter (Quests tab).
		AddReport("missive", std::string(a_title), Loc::F("$AG_Report_Missive", "Rank {} Guild Missive, completed", Letter(a_rank)), 0, merit, rep);
		SendModEvent("AG_MissiveCompleted", std::string(a_title), static_cast<float>(a_rank));
		Hud(Loc::T("$AG_Hud_MissiveDone", "Missive complete. Submit your report at any guild counter."));
	}

	// A Notice Board quest, ranked by notices.json: worth what a missive of that rank is, and it counts with them in
	// the career tally and the party's record. No Guild gold: the notice pays its own.
	void OnNoticeCompleted(int a_rank, std::string_view a_title)
	{
		const int merit = MissiveMerit(a_rank), rep = MissiveRep(a_rank);
		{
			std::lock_guard l(g_lock);
			if (!g_registered) return;
			if (a_rank >= 0 && a_rank < kRankCount) ++g_missives[a_rank];
			LogLocked(Loc::F("$AG_Log_Notice", "Completed a Rank {} notice: {}.", Letter(a_rank), a_title));
		}
		Party::OnMissiveCompleted(a_rank);
		AddReport("notice", std::string(a_title), Loc::F("$AG_Report_Notice", "Rank {} Guild Notice, completed", Letter(a_rank)), 0, merit, rep);
		SendModEvent("AG_MissiveCompleted", std::string(a_title), static_cast<float>(a_rank));
		Hud(Loc::T("$AG_Hud_NoticeDone", "Notice complete. Submit your report at any guild counter."));
	}

	// A Jarl's bounty (the game's own radiant bounty quests), once the hold has paid its gold: worth what a missive of
	// its rank is, and counted with them. The hold pays the gold; the Guild pays Merit and Reputation and no gold.
	void OnBountyCompleted(int a_rank, std::string_view a_title)
	{
		const int merit = MissiveMerit(a_rank), rep = MissiveRep(a_rank);
		{
			std::lock_guard l(g_lock);
			if (!g_registered) return;
			if (a_rank >= 0 && a_rank < kRankCount) ++g_missives[a_rank];
			LogLocked(Loc::F("$AG_Log_Bounty", "Collected a Rank {} bounty: {}.", Letter(a_rank), a_title));
		}
		Party::OnMissiveCompleted(a_rank);
		AddReport("bounty", std::string(a_title), Loc::F("$AG_Report_Bounty", "Rank {} Jarl's Bounty, collected", Letter(a_rank)), 0, merit, rep);
		SendModEvent("AG_MissiveCompleted", std::string(a_title), static_cast<float>(a_rank));
		Hud(Loc::T("$AG_Hud_BountyDone", "Bounty collected. Submit your report at any guild counter."));
	}

	void AddReport(std::string a_kind, std::string a_title, std::string a_detail, int a_gold, int a_merit, int a_rep, std::string a_key)
	{
		{
			std::lock_guard l(g_lock);
			if (!g_registered) return;
			g_reports.push_back({ std::move(a_kind), std::move(a_title), std::move(a_detail), std::max(0, a_gold), std::max(0, a_merit), std::max(0, a_rep), std::move(a_key) });
		}
		SyncGlobals();  // AG_ReportsWaitingGlobal (SkyrimNet's "take reports" action)
		Counter::Refresh();
	}

	std::string ClaimAll(const std::string& a_city)
	{
		const int bonus = Party::GoldRewardPercent();  // Coin-Bound; read before g_lock (Party has its own)
		int gold = 0, merit = 0, rep = 0;
		std::size_t n;
		std::vector<std::string> dungeons;  // the cleared dungeons among these reports
		{
			std::lock_guard l(g_lock);
			n = g_reports.size();
			if (!n) return Loc::T("$AG_Claim_None", "No reports to submit.");
			for (auto& r : g_reports) {
				gold += r.gold;
				merit += r.merit;
				rep += r.rep;
				if (!r.key.empty()) dungeons.push_back(r.key);
			}
			g_reports.clear();
			gold += gold * bonus / 100;
			g_goldEarned += gold;
			LogLocked(Loc::F("$AG_Log_Claimed", "Submitted {} report(s): {} gold, {} Merit, {} Reputation.", n, gold, merit, rep));
		}
		if (gold > 0 && g_gold) RE::PlayerCharacter::GetSingleton()->AddObjectToContainer(g_gold, nullptr, gold, nullptr);
		AddReward(merit, rep, Loc::T("$AG_Why_Reports", "reports"));
		SyncGlobals();  // reports cleared, even when they paid nothing
		SendModEvent("AG_ReportsSubmitted", std::format("{} report{} ({} gold, {} Merit, {} Reputation)", n, n == 1 ? "" : "s", gold, merit, rep), static_cast<float>(n));
		Counter::Refresh();
		SKSE::log::info("Guild: submitted {} reports ({} gold, {} merit, {} rep)", n, gold, merit, rep);
		// Hold stamps: the Guild now has these clears on record. A stamp they earn goes on the card here and now when this
		// is that hold's counter (and the card is in hand); any other is collected at its own counter, so say which.
		for (auto& city : Dungeons::HandIn(dungeons)) {
			SKSE::log::info("Guild: the {} stamp is earned ({} dungeon reports from the hold handed in)", city, StampDungeons());
			if (city == a_city && GuildCard::CollectHoldStamp(city)) continue;
			if (const auto keeper = Adventurers::StampKeeperName(city); !keeper.empty())
				Hud(Loc::F("$AG_Hud_StampEarnedKeeper", "{} in {} keeps the hold's stamp for your guild card.", keeper, CityName(city)));
			else
				Hud(Loc::F("$AG_Hud_StampEarned", "The {} counter of the Adventurers Guild has a stamp for your guild card.", CityName(city)));
		}
		if (!dungeons.empty()) {
			Counter::Refresh();
			SyncStampMarks();
		}
		const auto plural = n == 1 ? "" : "s";
		return gold > 0 ? std::format("Submitted {} report{}: {} gold, {} Merit and {} Reputation.", n, plural, gold, merit, rep)
		                : std::format("Submitted {} report{}: {} Merit and {} Reputation.", n, plural, merit, rep);
	}

	// MCM-free and rank-free: any member settles every bounty they have at any counter, for the bounties and the Guild's
	// fee, and keeps what they stole (a Nexus request, 2026-10-17). The game's own payment, as to a guard, without the
	// jail and without taking stolen goods.
	std::string PayBounties()
	{
		int        sum = 0;
		const auto list = Bounties(sum);
		if (list.empty()) return Loc::T("$AG_Bounty_NoneToPay", "You have no bounty to pay.");
		const int fee = BountyFee(sum);
		if (GoldCount() < sum + fee) return Loc::F("$AG_Bounty_NeedGold", "Paying off your bounties takes {} gold.", sum + fee);
		auto* pc = RE::PlayerCharacter::GetSingleton();
		if (fee > 0) pc->RemoveItem(g_gold, fee, RE::ITEM_REMOVE_REASON::kRemove, nullptr, nullptr);
		std::string where;
		for (auto& [f, g] : list) {
			f->PlayerPayCrimeGold(false, false);  // the bounty's own gold, paid as to a guard: no jail, stolen goods kept
			const char* n = f->GetName();
			where += std::format("{}{} ({})", where.empty() ? "" : ", ", n && *n ? n : "?", g);
		}
		SKSE::log::info("Guild: bounties paid at the counter - {} gold and a {} gold fee: {}", sum, fee, where);
		Hud(Loc::F("$AG_Hud_GoldRemoved", "{} gold removed.", sum + fee));
		{
			std::lock_guard l(g_lock);
			LogLocked(Loc::F("$AG_Log_BountiesPaid", "Paid off your bounties through the Guild: {} gold.", sum + fee));
		}
		ConductTick();  // promotion is no longer held
		Counter::Refresh();
		return Loc::F("$AG_Bounty_Paid", "Your bounties are paid: {} gold, the Guild's fee included.", sum + fee);
	}

	std::string BuyService(const std::string& a_id)
	{
		if (a_id == "bounties:pay") return PayBounties();
		if (a_id.starts_with("intel:")) {
			auto msg = Dungeons::BuyIntel(a_id);
			Counter::Refresh();
			return msg;
		}
		if (a_id.starts_with("poi:")) {
			auto msg = Dungeons::BuyPoi(a_id);
			Counter::Refresh();
			return msg;
		}
		return Shop::Buy(a_id);
	}

	nlohmann::json CounterData()
	{
		auto* pc = RE::PlayerCharacter::GetSingleton();
		const int level = pc ? pc->GetLevel() : 1;
		const int cardsCarried = MemberCards::Carried();  // before the lock: it reads the inventory and takes its own
		std::lock_guard l(g_lock);
		nlohmann::json j;
		j["name"] = pc ? pc->GetDisplayFullName() : "";
		j["registered"] = g_registered;
		j["rank"] = g_rank;
		j["letter"] = g_registered ? LetterStr(g_rank) : "-";
		j["level"] = level;
		j["merit"] = g_merit;
		j["reputation"] = g_reputation;
		j["ready"] = ReadyLocked();
		j["promotionBlocked"] = BlockedLocked();  // would be ready, but for a bounty
		j["bountyWhere"] = g_bountyWhere;          // where that bounty is, so it can be found and paid
		j["today"] = Today();
		// today's calendar date, so the page can turn a stored "days passed" into a date ("3rd of Hearthfire, 4E 201")
		if (auto* cal = RE::Calendar::GetSingleton())
			j["date"] = { { "year", cal->GetYear() }, { "month", cal->GetMonth() }, { "day", static_cast<int>(cal->GetDay()) }, { "hour", cal->GetHour() } };
		j["registeredDay"] = g_registeredDay;
		j["seal"] = GuildCard::Seal();   // which region's wax seal the card carries ("" = Skyrim's)
		j["cardsCarried"] = cardsCarried;         // Field Notes: other adventurers' cards that can be handed in
		j["issuedAt"] = GuildCard::IssuedAt().empty() ? std::string() : CityName(GuildCard::IssuedAt());  // the counter that issued the card in hand
		j["missives"] = g_missives;
		j["goldEarned"] = g_goldEarned;
		{
			int missives = 0;
			for (int m : g_missives) missives += m;
			j["career"] = { { "days", g_registered && g_registeredDay >= 0.0f ? static_cast<int>(Today() - g_registeredDay) : 0 },
				{ "kills", g_kills }, { "bigKills", g_bigKills }, { "dungeons", Dungeons::ClearedCount() }, { "missives", missives },
				{ "trophies", g_trophiesSold } };
		}
		if (g_registered && g_rank < kRankCount - 1) {
			const int next = g_rank + 1;
			j["next"] = { { "letter", LetterStr(next) }, { "reputation", g_cfg.reputation[next] }, { "level", MinLevel(next) },
				{ "prevReputation", g_cfg.reputation[g_rank] } };
		}
		auto& reports = j["reports"] = nlohmann::json::array();
		for (auto& r : g_reports) reports.push_back({ { "kind", r.kind }, { "title", r.title }, { "detail", r.detail }, { "gold", r.gold }, { "merit", r.merit }, { "rep", r.rep } });
		auto& history = j["history"] = nlohmann::json::array();
		for (auto& h : g_history) history.push_back({ { "day", h.day }, { "text", h.text } });
		j["appraisal"] = g_appraisal.load();
		j["training"] = g_training;
		auto services = Shop::ServicesData(g_rank, g_merit, g_appraisal.load(), g_training, g_augment, g_augment >= 0 ? (g_augmentUntil - Today()) * 24.0f : 0.0f);
		// Pay off all bounties: one row, only while there is something to pay
		{
			int        sum = 0;
			const auto list = Bounties(sum);
			if (!list.empty()) {
				const int   fee = BountyFee(sum);
				std::string where;
				for (auto& [f, g] : list) {
					const char* n = f->GetName();
					where += std::format("{}{} ({} gold)", where.empty() ? "" : ", ", n && *n ? n : "?", g);
				}
				const bool can = pc && pc->GetGoldAmount() >= sum + fee;
				services.push_back({ { "id", "bounties:pay" }, { "section", Loc::T("$AG_UI_SvcBounties", "Bounties") }, { "sectionId", "bounties" },
					{ "name", Loc::T("$AG_UI_PayBounties", "Pay off all bounties") },
					{ "desc", Loc::F("$AG_UI_PayBountiesDesc", "{0}, and the Guild's {1}% fee. Settled with every hold; no jail, and you keep what you carry.", where, g_cfg.bountyFeePercent) },
					{ "gold", sum + fee }, { "available", can }, { "note", can ? "" : Loc::T("$AG_UI_NotEnoughGold", "Not enough gold") } });
			}
		}
		j["services"] = std::move(services);
		// what was bought at the counter and is running out, for the Guild Card: name and whole hours left
		j["passives"] = nlohmann::json::array();
		if (g_augment >= 0)
			j["passives"].push_back({ { "name", Shop::AugmentName(g_augment) }, { "hours", std::max(1, static_cast<int>(std::ceil((g_augmentUntil - Today()) * 24.0f))) } });
		return j;
	}

	void SyncGlobals()
	{
		bool ready, announce = false;
		int  rank, next = -1, recent = -1, reports = 0;
		bool registered;
		{
			std::lock_guard l(g_lock);
			ready = ReadyLocked();
			registered = g_registered;
			rank = g_registered ? g_rank : -1;
			if (g_registered && g_promotedDay >= 0.0f && Today() - g_promotedDay <= kGossipDays) recent = g_rank;
			reports = static_cast<int>(g_reports.size());
			if (ready && !g_lastReady) {
				announce = true;
				next = g_rank + 1;
			}
			g_lastReady = ready;
		}
		if (g_gRank) g_gRank->value = static_cast<float>(rank);
		if (g_gRecentPromo) g_gRecentPromo->value = static_cast<float>(recent);
		if (g_gReports) g_gReports->value = static_cast<float>(reports);
		if (g_gRegistered) g_gRegistered->value = registered ? 1.0f : 0.0f;
		if (g_gReady) g_gReady->value = ready ? 1.0f : 0.0f;
		if (g_gRegFee) g_gRegFee->value = static_cast<float>(g_cfg.fee);
		if (g_gPromoFee) g_gPromoFee->value = static_cast<float>(g_cfg.promotionFee);
		if (g_gCardFee) g_gCardFee->value = static_cast<float>(g_cfg.cardFee);
		if (g_replaceTopic)
			g_replaceTopic->fullName = Loc::F("$AG_Dlg_ReplaceCard", "I've lost my guild card. I need a replacement. ({} gold)", g_cfg.cardFee);
		if (announce) {
			Hud(Loc::F("$AG_Hud_Ready", "You are eligible for promotion to Rank {}. Any innkeeper can hear your case.", Letter(next)));
			PrismaToast::Show(Loc::T("$AG_Toast_Ready", "PROMOTION READY"), Loc::F("$AG_Toast_ReadySub", "Rank {} awaits · a guild liaison can hear your case", Letter(next)),
				std::format("tex/rank_{}.png", Letter(next)), PrismaToast::Priority::kImportant, PrismaToast::Cue::kPromotionReady);
		}
	}

	void OnBoardApproached()
	{
		bool give;
		{
			std::lock_guard l(g_lock);
			if (g_registered) return;
			give = !g_regMissiveGiven;
			g_regMissiveGiven = true;
		}
		if (give && g_regMissive) {
			RE::PlayerCharacter::GetSingleton()->AddObjectToContainer(g_regMissive, nullptr, 1, nullptr);
			CallQuestFn("StartRegistrationQuest");
			Hud(Loc::T("$AG_Hud_RegNotice", "A Guild notice is pinned to the board. You take a copy."));
			SKSE::log::info("Guild: registration missive handed out");
		} else {
			// A reminder, not a nag: a board's trigger can report the player again and again (standing at its edge, or
			// a start that drops the player inside one), so it is said once and then not for five minutes.
			static std::chrono::steady_clock::time_point last{};
			const auto                                   now = std::chrono::steady_clock::now();
			if (last.time_since_epoch().count() == 0 || now - last >= std::chrono::minutes(5)) {
				last = now;
				Hud(Loc::T("$AG_Hud_RegOnly", "Missives are for registered adventurers. Any innkeeper can sign you up."));
			}
		}
	}

	int  AppraisalLevel() { return g_dormant.load(std::memory_order_relaxed) ? 0 : g_appraisal.load(std::memory_order_relaxed); }  // no rank labels while dormant

	void SetAppraisalLevel(int a_tier)
	{
		{
			std::lock_guard l(g_lock);
			g_appraisal = std::clamp(a_tier, 0, 3);
			if (a_tier > 0) LogLocked(Loc::F("$AG_Log_Appraisal", "Learned Appraisal {}.", a_tier == 1 ? "I" : a_tier == 2 ? "II" : "III"));
		}
		ApplyAbilities();
	}

	int TrainingSteps(int a_stat)
	{
		std::lock_guard l(g_lock);
		return (a_stat >= 0 && a_stat < 3) ? g_training[a_stat] : 0;
	}

	void AddTrainingStep(int a_stat)
	{
		if (a_stat < 0 || a_stat > 2) return;
		{
			std::lock_guard l(g_lock);
			++g_training[a_stat];
		}
		ApplyAbilities();
	}

	bool TrySpendMerit(int a_cost, std::string_view a_record)
	{
		std::lock_guard l(g_lock);
		if (!g_registered || a_cost < 0 || g_merit < a_cost) return false;
		g_merit -= a_cost;  // spending never lowers Reputation
		if (!a_record.empty()) LogLocked(std::string(a_record));
		return true;
	}

	void AddGold(int a_amount)
	{
		if (a_amount <= 0 || !g_gold) return;
		a_amount += a_amount * Party::GoldRewardPercent() / 100;  // Coin-Bound
		RE::PlayerCharacter::GetSingleton()->AddObjectToContainer(g_gold, nullptr, a_amount, nullptr);
		std::lock_guard l(g_lock);
		g_goldEarned += a_amount;
	}

	// Derive want/has every call (a pattern proven in VR) so the abilities can't drift from the save.
	void ApplyAbilities()
	{
		auto* pc = RE::PlayerCharacter::GetSingleton();
		if (!pc) return;
		const bool dormant = g_dormant.load();
		const int  tier = dormant ? 0 : g_appraisal.load();
		for (int t = 0; t < 3; ++t) {
			auto* perk = g_appraisalPerks[t];
			if (!perk) continue;
			const bool want = tier == t + 1, has = pc->HasPerk(perk);
			if (want && !has) pc->AddPerk(perk);
			else if (!want && has) pc->RemovePerk(perk);
		}
		std::array<int, 3> steps{};
		if (!dormant) {
			std::lock_guard l(g_lock);
			steps = g_training;
		}
		for (int st = 0; st < 3; ++st) {
			auto& spells = g_trainSpells[st];
			const int want = std::min<int>(steps[st], static_cast<int>(spells.size()));
			for (int n = 0; n < static_cast<int>(spells.size()); ++n) {
				const bool w = n + 1 == want, has = pc->HasSpell(spells[n]);
				if (w && !has) pc->AddSpell(spells[n]);
				else if (!w && has) pc->RemoveSpell(spells[n]);
			}
		}
		int augment = -1;
		if (!dormant) {
			std::lock_guard l(g_lock);
			augment = g_augment;
		}
		for (int n = 0; n < static_cast<int>(g_augmentSpells.size()); ++n) {
			const bool w = n == augment, has = pc->HasSpell(g_augmentSpells[n]);
			if (w && !has) pc->AddSpell(g_augmentSpells[n]);
			else if (!w && has) pc->RemoveSpell(g_augmentSpells[n]);
		}
	}

	bool HasAugmentSpell(int a_index) { return a_index >= 0 && a_index < static_cast<int>(g_augmentSpells.size()); }

	void SetAugment(int a_index, float a_days)
	{
		{
			std::lock_guard l(g_lock);
			g_augment = HasAugmentSpell(a_index) ? a_index : -1;
			g_augmentUntil = Today() + a_days;
		}
		ApplyAbilities();
	}

	namespace
	{
		// An Augment lasts until a game time, so a day spent waiting or sleeping uses it up as a day on the road does
		void AugmentTick()
		{
			{
				std::lock_guard l(g_lock);
				if (g_augment < 0 || Today() < g_augmentUntil) return;
				g_augment = -1;
			}
			ApplyAbilities();
			RE::SendHUDMessage::ShowHUDMessage(Loc::T("$AG_Hud_AugmentOver", "Your Guild Augment has worn off.").c_str());
			if (Counter::IsOpen()) Counter::Refresh();
		}
	}

	bool Dormant() { return g_dormant.load(); }

	namespace
	{
		bool Ours(const RE::TESForm* a_form)
		{
			const auto* file = a_form ? a_form->GetFile(0) : nullptr;
			return file && std::string_view(file->GetFilename()) == "AdventurersGuild.esp";
		}
	}

	std::string PrepareUninstall()
	{
		auto* pc = RE::PlayerCharacter::GetSingleton();
		if (!pc) return {};
		g_dormant = true;
		ApplyAbilities();  // Appraisal perks and training abilities, the way they were given
		// anything else of ours on the player (a sweep, whatever version granted it)
		std::vector<RE::SpellItem*> spells;
		for (auto* sp : pc->GetActorRuntimeData().addedSpells)
			if (Ours(sp)) spells.push_back(sp);
		for (auto* sp : spells) pc->RemoveSpell(sp);
		for (auto* perk : g_appraisalPerks)
			if (perk && pc->HasPerk(perk)) pc->RemovePerk(perk);
		const int companions = Party::StripForUninstall();
		int items = 0;
		for (auto& [obj, data] : pc->GetInventory([](RE::TESBoundObject& o) { return Ours(&o); })) {
			if (data.first <= 0) continue;
			pc->RemoveItem(obj, data.first, RE::ITEM_REMOVE_REASON::kRemove, nullptr, nullptr);
			items += data.first;
		}
		{
			std::lock_guard l(g_lock);
			LogLocked(Loc::T("$AG_Log_Uninstall", "Prepared for uninstall: the Guild's abilities were taken back."));
		}
		SKSE::log::info("Guild: prepared for uninstall ({} companions, {} items)", companions, items);
		return Loc::F("$AG_Uninstall_Done", "Done. The Guild's abilities are gone from you and {} companion(s), and {} Guild item(s) were removed. "
			"Now save, quit, and remove Adventurers Guild. (Changed your mind? Use Cancel Uninstall.)", companions, items);
	}

	std::string CancelUninstall()
	{
		g_dormant = false;
		// back on the game thread, where the ability sync and the party's evaluation normally run (called from the MCM)
		SKSE::GetTaskInterface()->AddTask([] {
			ApplyAbilities();
			Party::Refresh();
		});
		{
			std::lock_guard l(g_lock);
			LogLocked(Loc::T("$AG_Log_UninstallCancel", "Uninstall cancelled: the Guild's abilities are back."));
		}
		return Loc::T("$AG_Uninstall_Cancelled", "Uninstall cancelled. Your Guild abilities and party bonuses are back.");
	}

	void Notify(const char* a_event, const std::string& a_str, float a_num) { SendModEvent(a_event, a_str, a_num); }

	float Day() { return Today(); }

	void CountKill(bool a_big)
	{
		std::lock_guard l(g_lock);
		++g_kills;
		if (a_big) ++g_bigKills;
	}

	void CountTrophies(int a_count)
	{
		std::lock_guard l(g_lock);
		g_trophiesSold += std::max(0, a_count);
	}

	void Record(std::string a_text)
	{
		std::lock_guard l(g_lock);
		LogLocked(std::move(a_text));
	}

	// A successor is in the liaison faction while, and only while, the counter is theirs. Run on the 5-second beat and
	// when an innkeeper dies, and it works both ways: until 1.4.1 it ran once, as a game started or loaded, when the
	// city quests had not yet put anyone in their roles; the question came back empty, empty was read as "the innkeeper
	// is gone", and all four successors were marked for good with every innkeeper alive (seen on a new game,
	// 2026-10-11). An empty answer now means nothing has changed (Adventurers.cpp), and a mark that is wrong is removed.
	void SyncSuccessors()
	{
		if (!g_liaisonFaction) return;
		for (auto& [actor, keeps] : Adventurers::Successors()) {
			const bool marked = actor->GetFactionRank(g_liaisonFaction, false) >= 0;
			if (keeps && !marked) {
				actor->AddToFaction(g_liaisonFaction, 0);
				SKSE::log::info("Guild: {} keeps a dead liaison's Adventurers Guild counter now", actor->GetDisplayFullName());
			} else if (!keeps && marked) {
				actor->AddToFaction(g_liaisonFaction, -1);  // rank -1: no longer of the faction
				SKSE::log::info("Guild: {} does not keep an Adventurers Guild counter - the liaison is alive (the mark is taken back)", actor->GetDisplayFullName());
			}
		}
	}

	int CardFee() { return g_cfg.cardFee; }
	int StampDungeons() { return g_cfg.stampDungeons; }
	int CardReturnReputation() { return g_cfg.memberCardRep; }
	float CardReplaceDays() { return g_cfg.memberCardDays; }
	int ReputationFor(int a_rank) { return g_cfg.reputation[std::clamp(a_rank, 0, kRankCount - 1)]; }

	std::string CityName(const std::string& a_city)
	{
		std::string key = "$AG_City_";
		for (const char c : a_city)
			if (std::isalnum(static_cast<unsigned char>(c))) key += c;
		return a_city.empty() ? a_city : Loc::T(key, a_city);
	}

	bool PayGold(int a_amount)
	{
		if (a_amount <= 0) return true;
		if (GoldCount() < a_amount) return false;
		RE::PlayerCharacter::GetSingleton()->RemoveItem(g_gold, a_amount, RE::ITEM_REMOVE_REASON::kRemove, nullptr, nullptr);
		Hud(Loc::F("$AG_Hud_GoldRemoved", "{} gold removed.", a_amount));
		return true;
	}

	std::string LedgerJson()
	{
		auto* pc = RE::PlayerCharacter::GetSingleton();
		const int level = pc ? pc->GetLevel() : 1;
		const auto trophies = Shop::TrophiesData();
		const bool hasCard = GuildCard::Has();
		std::lock_guard l(g_lock);
		nlohmann::json j;
		j["registered"] = g_registered;
		// the real fees, so a liaison quotes them instead of inventing a number
		j["registrationFee"] = g_cfg.fee;
		j["promotionFee"] = g_cfg.promotionFee;
		j["cardFee"] = g_cfg.cardFee;
		j["hasCard"] = hasCard;  // a liaison knows when the card is lost, and what a new one costs
		if (!g_registered) return j.dump();
		j["rank"] = LetterStr(g_rank);
		j["merit"] = g_merit;
		j["reputation"] = g_reputation;
		j["promotionReady"] = ReadyLocked();
		if (g_rank < kRankCount - 1) {
			const int next = g_rank + 1;
			j["next"] = { { "rank", LetterStr(next) }, { "reputationShort", std::max(0, g_cfg.reputation[next] - g_reputation) },
				{ "levelShort", std::max(0, MinLevel(next) - level) } };
		}
		int gold = 0, merit = 0, rep = 0;
		for (auto& r : g_reports) {
			gold += r.gold;
			merit += r.merit;
			rep += r.rep;
		}
		j["reportsWaiting"] = { { "count", g_reports.size() }, { "gold", gold }, { "merit", merit }, { "reputation", rep } };
		nlohmann::json done;
		for (int r = 0; r < 4; ++r) done[LetterStr(r)] = g_missives[r];
		j["missivesCompleted"] = done;
		j["trophiesCarried"] = { { "kinds", trophies.value("items", nlohmann::json::array()).size() }, { "merit", trophies.value("total", 0) } };
		constexpr const char* app[]{ "none", "I", "II", "III" };
		j["appraisal"] = app[std::clamp(g_appraisal.load(), 0, 3)];
		j["goldPaidOut"] = g_goldEarned;
		if (g_registeredDay >= 0.0f) j["daysSinceRegistration"] = static_cast<int>(Today() - g_registeredDay);
		auto& recent = j["recentEntries"] = nlohmann::json::array();
		for (std::size_t i = 0; i < g_history.size() && i < 4; ++i) recent.push_back(g_history[i].text);
		return j.dump();
	}

	std::string Dump()
	{
		std::lock_guard l(g_lock);
		return std::format("registered={} rank={} merit={} reputation={} ready={} regMissive={} reports={} history={} appraisal={} training={}/{}/{} fee={} cap={}",
			g_registered, g_registered ? LetterStr(g_rank) : "-", g_merit, g_reputation, ReadyLocked(), g_regMissiveGiven,
			g_reports.size(), g_history.size(), g_appraisal.load(), g_training[0], g_training[1], g_training[2], g_cfg.fee, Letter(g_cfg.cap));
	}

	// ---- SkyrimNet actions: a Guild rep doing guild business in an AI conversation. Same paths (fees, eligibility) as
	// the dialogue; a non-liaison speaker is refused, so an action the AI picks by mistake does nothing.
	std::string ActionRegister(RE::Actor* a_liaison)
	{
		if (!Adventurers::IsLiaison(a_liaison)) return "not a Guild rep";
		if (Registered()) return "already registered";
		DoRegister();
		if (Registered()) GuildCard::Stamp(Adventurers::LiaisonCity(a_liaison));
		return Registered() ? "registered" : "not registered (fee)";
	}

	std::string ActionPromote(RE::Actor* a_liaison)
	{
		if (!Adventurers::IsLiaison(a_liaison)) return "not a Guild rep";
		if (!PromotionReady()) return "not eligible";
		const int before = Rank();
		DoPromote();
		return Rank() > before ? "promoted" : "not promoted (fee)";
	}

	std::string ActionReports(RE::Actor* a_liaison)
	{
		if (!Adventurers::IsLiaison(a_liaison)) return "not a Guild rep";
		const auto msg = ClaimAll(Adventurers::LiaisonCity(a_liaison));
		Hud(msg);
		return msg;
	}

	std::string ActionReplaceCard(RE::Actor* a_liaison)
	{
		if (!Adventurers::IsLiaison(a_liaison)) return "not a Guild rep";
		if (!Registered()) return "not registered";
		const auto msg = GuildCard::Replace(Adventurers::LiaisonCity(a_liaison));
		if (!msg.empty()) Hud(msg);
		return msg;
	}

	void DebugRegister() { DoRegister(); }
	void DebugPromote() { DoPromote(); }

	// MCM > Debug: the rank the player's level alone gives (the highest whose level floor it meets, no registration
	// cap), with exactly the Reputation that rank starts at. For a character whose record no longer fits: a save
	// that joined late, a level overhaul, a tester.
	namespace
	{
		int RankForLevel(int a_level) { return FromLevel(a_level); }
	}

	void OnBandsChanged()
	{
		SKSE::GetTaskInterface()->AddTask([] {
			if (!RE::PlayerCharacter::GetSingleton()) return;
			SyncGlobals();     // "ready for promotion" may have changed
			SyncWanderers();   // their rank in the faction their greetings read
			if (Counter::IsOpen()) Counter::Refresh();
		});
	}

	void NoticeRankLevelsKept()
	{
		SKSE::log::info("Guild: a save from before 1.4.0 - rank S stays at level {} here (new games: {})", GetSLevel(), DefaultSLevel());
		PrismaToast::Show(Loc::T("$AG_Toast_BandsKept", "RANK LEVELS KEPT"),
			Loc::F("$AG_Toast_BandsKeptSub", "Rank S stays at level {} in this game · new games use {} · change it in the MCM", GetSLevel(), DefaultSLevel()));
	}

	std::string RankResetText()
	{
		auto* pc = RE::PlayerCharacter::GetSingleton();
		std::lock_guard l(g_lock);
		if (!g_registered || !pc) return Loc::T("$AG_RankReset_NotRegistered", "You are not registered with the Adventurers Guild. Register at any hold capital's inn first.");
		const int level = pc->GetLevel(), rank = RankForLevel(level);
		return Loc::F("$AG_RankReset_Confirm", "You are level {}. This sets your guild rank to {} and your Reputation to {}, replacing rank {} and {} Reputation. Merit, Appraisal and training are not touched. Continue?",
			level, Letter(rank), g_cfg.reputation[rank], Letter(g_rank), g_reputation);
	}

	std::string RecalculateRank()
	{
		auto* pc = RE::PlayerCharacter::GetSingleton();
		int   level, rank, rep;
		{
			std::lock_guard l(g_lock);
			if (!g_registered || !pc) return Loc::T("$AG_RankReset_NotRegistered", "You are not registered with the Adventurers Guild. Register at any hold capital's inn first.");
			level = pc->GetLevel();
			rank = RankForLevel(level);
			rep = g_cfg.reputation[rank];
			g_rank = rank;
			g_reputation = rep;
			g_repCarry = 0.0f;
			LogLocked(Loc::F("$AG_Log_RankReset", "Guild record set from level {}: Rank {}, {} Reputation.", level, Letter(rank), rep));
		}
		SyncGlobals();
		GuildCard::Sync(false);  // the card carries the rank
		Counter::Refresh();
		SendModEvent("AG_RankChanged", LetterStr(rank), static_cast<float>(rank));
		SKSE::log::info("Guild: rank recalculated from level {} - rank {}, reputation {}", level, Letter(rank), rep);
		return Loc::F("$AG_RankReset_Done", "Level {}: you are now Rank {} with {} Reputation.", level, Letter(rank), rep);
	}

	void DebugSetRank(int a_rank)
	{
		{
			std::lock_guard l(g_lock);
			g_registered = a_rank >= 0;
			g_rank = std::clamp(a_rank, -1, kRankCount - 1);
		}
		SyncGlobals();
	}

	void DebugReset()
	{
		Reset();
		SyncGlobals();
	}

	int MissiveMerit(int a_rank)
	{
		std::lock_guard l(g_lock);
		return (a_rank >= 0 && a_rank < kRankCount) ? g_cfg.missiveMerit[a_rank] : 0;
	}

	int MissiveRep(int a_rank) { return (a_rank >= 0 && a_rank < kRankCount) ? g_cfg.missiveRep[a_rank] : 0; }
	int DungeonRep(int a_rank) { return (a_rank >= 0 && a_rank < kRankCount) ? g_cfg.dungeonRep[a_rank] : 0; }
	KillRewards Kills() { std::lock_guard l(g_lock); return g_cfg.kills; }
	int DungeonMerit(int a_rank) { return (a_rank >= 0 && a_rank < kRankCount) ? g_cfg.dungeonMerit[a_rank] : 0; }
	int DungeonGold(int a_rank) { return (a_rank >= 0 && a_rank < kRankCount) ? g_cfg.dungeonGold[a_rank] : 0; }
	int IntelMerit(int a_rank) { return (a_rank >= 0 && a_rank < kRankCount) ? g_cfg.intelMerit[a_rank] : 0; }
}
