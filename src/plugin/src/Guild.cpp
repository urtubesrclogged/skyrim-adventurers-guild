// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "ControlsGuard.h"
#include "GuildCard.h"
#include "Guild.h"

#include "Adventurers.h"
#include "Dungeons.h"
#include "Party.h"
#include "Counter.h"
#include "Loc.h"
#include "PrismaToast.h"
#include "RankCore.h"
#include "Shop.h"

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
			float                        repPerBountyGold{ 0.1f };  // Reputation lost per gold of new bounty
			float                        abandonShare{ 0.5f };      // of a taken missive's Reputation, lost when it is given up
			std::array<int, kRankCount>  reputation{ 0, 100, 300, 700, 1500, 3000 };
			int                          cap{ 2 };  // C
			std::array<int, kRankCount>  missiveMerit{ 5, 10, 15, 25, 0, 0 };
			std::array<int, kRankCount>  missiveRep{ 8, 15, 30, 55, 0, 0 };
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
		std::array<int, 3>           g_training{};      // purchased steps: Health, Stamina, Magicka

		// ---- our forms ----
		RE::TESGlobal*       g_gRank{ nullptr };
		RE::TESGlobal*       g_gRegistered{ nullptr };
		RE::TESGlobal*       g_gRecentPromo{ nullptr };      // AG_RecentPromotionGlobal: rank just reached, else -1
		RE::TESFaction*      g_retiredFaction{ nullptr };    // AG_RetiredAdventurerFaction, for world dialogue
		RE::TESFaction*      g_wandererFaction{ nullptr };   // AG_WanderingAdventurerFaction: rank in it = their Guild rank
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
		RE::TESTopic*  g_replaceTopic{ nullptr };  // the player's "I've lost my guild card" line: the DLL writes the fee into it
		// Liaison dialogue lines by role (dialogue.resolved.json). Staff/referral lines are not listed,
		// so choosing a topic at a non-guild inn only gets the innkeeper's pointer to the right city.
		std::unordered_set<RE::FormID> g_infoRegister, g_infoPromote, g_infoBusiness, g_infoReplace;
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
			GuildCard::Sync(true);  // "Here's your guild card."
			PrismaToast::Show(Loc::T("$AG_Toast_Registration", "GUILD REGISTRATION"), Loc::F("$AG_Toast_RankAdventurer", "Rank {} Adventurer", Letter(rank)), std::format("tex/rank_{}.png", Letter(rank)));
			Hud(rank > 0 ? Loc::F("$AG_Reg_Assessed", "Your experience has been assessed: you are registered as a Rank {} adventurer.", Letter(rank))
			             : Loc::T("$AG_Reg_RankE", "You are registered as a Rank E adventurer."));
			SendModEvent("AG_Registered", LetterStr(rank), static_cast<float>(rank));
			SKSE::log::info("Guild: registered at rank {} (level {})", Letter(rank), RE::PlayerCharacter::GetSingleton()->GetLevel());
		}

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
			PrismaToast::Show(Loc::T("$AG_Toast_Promoted", "PROMOTED"), Loc::F("$AG_Toast_RankAdventurer", "Rank {} Adventurer", Letter(rank)), std::format("tex/rank_{}.png", Letter(rank)));
			Hud(Loc::F("$AG_Promo_Done", "The Guild has promoted you to Rank {}.", Letter(rank)));
			GuildCard::Sync(true);  // "I've updated your guild card."
			SendModEvent("AG_RankChanged", LetterStr(rank), static_cast<float>(rank));
			SKSE::log::info("Guild: promoted to rank {}", Letter(rank));
		}

		// ---- event sinks ----

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
				if (g_infoRegister.contains(id)) {
					SKSE::GetTaskInterface()->AddTask(DoRegister);
				} else if (g_infoPromote.contains(id)) {
					SKSE::GetTaskInterface()->AddTask(DoPromote);
				} else if (g_infoReplace.contains(id)) {
					// "Here, a fresh one.": the player's own line named the fee, so it is paid without asking again
					SKSE::GetTaskInterface()->AddTask([] {
						if (auto msg = GuildCard::Replace(); !msg.empty()) RE::SendHUDMessage::ShowHUDMessage(msg.c_str());
					});
				} else if (g_infoBusiness.contains(id)) {
					// the line is a Goodbye: the counter opens as the menu closes, labelled with this branch
					Counter::OpenAfterDialogue(Adventurers::LiaisonCity(a_e->speakerRef.get()));
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
				j["bounties"] = g_bountySeen;
				j["bountyKnown"] = g_bountyKnown;
				j["bountyCarry"] = g_bountyCarry;
				j["counterMask"] = ControlsGuard::Masked();  // the engine saves the control flags (ControlsGuard.h)
				auto& reports = j["reports"] = nlohmann::json::array();
				for (auto& r : g_reports) reports.push_back({ { "kind", r.kind }, { "title", r.title }, { "detail", r.detail }, { "gold", r.gold }, { "merit", r.merit }, { "rep", r.rep } });
				auto& history = j["history"] = nlohmann::json::array();
				for (auto& h : g_history) history.push_back({ { "day", h.day }, { "text", h.text } });
			}
			j["recruited"] = Adventurers::Save();
			j["heldS"] = Adventurers::SaveHeldS();
			j["sLevel"] = GetSLevel();
			j["dungeons"] = Dungeons::Save();
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
			Party::Revert();
			SetSLevel(DefaultSLevel());  // a save this mod has never been in: as a new game
			std::uint32_t type, ver, len;
			while (a->GetNextRecordInfo(type, ver, len)) {
				if (type != kRec) continue;
				std::string s(len, '\0');
				a->ReadRecordData(s.data(), len);
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
							g_reports.push_back({ r.value("kind", ""), r.value("title", ""), r.value("detail", ""), r.value("gold", 0), r.value("merit", 0), r.value("rep", r.value("merit", 0)) });
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
					// a save from before 1.4.0 keeps the levels it always had; the MCM (which holds the setting) agrees
					SetSLevel(j.value("sLevel", kSLevelBefore140));
					Dungeons::Load(j.value("dungeons", nlohmann::json::object()));
					Party::Load(j.value("parties", nlohmann::json::array()));
				} catch (const std::exception& e) {
					SKSE::log::error("Guild: co-save parse error: {}", e.what());
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
			Party::Revert();
			SetSLevel(DefaultSLevel());
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
				if (j.contains("conduct")) {
					c.repPerBountyGold = std::max(0.0f, j.at("conduct").value("repPerBountyGold", c.repPerBountyGold));
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
		g_wandererFaction = Own<RE::TESFaction>(0xC80);
		g_gReports = Own<RE::TESGlobal>(0x8C7);
		RE::ScriptEventSourceHolder::GetSingleton()->AddEventSink<RE::TESObjectLoadedEvent>(RetiredSink::Get());
		try {
			std::ifstream df("Data/SKSE/Plugins/AdventurersGuild/dialogue.resolved.json");
			auto dj = nlohmann::json::parse(df, nullptr, true, true);
			auto load = [&](const char* a_role, std::unordered_set<RE::FormID>& a_out) {
				a_out.clear();
				for (auto& hex : dj.at("roles").value(a_role, nlohmann::json::array())) {
					if (auto* i = Own<RE::TESTopicInfo>(static_cast<RE::FormID>(std::stoul(hex.get<std::string>(), nullptr, 16))))
						a_out.insert(i->GetFormID());
				}
			};
			load("register", g_infoRegister);
			load("promote", g_infoPromote);
			load("business", g_infoBusiness);
			load("replace", g_infoReplace);
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
		SKSE::log::info("Guild: forms resolved ({} register, {} promote, {} business lines), sinks registered",
			g_infoRegister.size(), g_infoPromote.size(), g_infoBusiness.size());
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
	}

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
			PrismaToast::Show(Loc::T("$AG_Toast_RepLost", "REPUTATION LOST"), Loc::F("$AG_Toast_RepLostSub", "-{} Reputation · {}", lost, a_why));
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
			if (!actor || actor->IsPlayerRef() || actor->IsDead() || !Adventurers::IsWanderer(actor)) continue;
			const auto info = Adventurers::Of(actor);
			if (info.kind != Adventurers::Kind::kMember) continue;
			const auto rank = static_cast<std::int8_t>(std::clamp(info.rank, 0, 5));
			if (!actor->IsInFaction(g_wandererFaction) || actor->GetFactionRank(g_wandererFaction, false) != rank) actor->AddToFaction(g_wandererFaction, rank);
		}
	}

	namespace
	{
		void AugmentTick();  // below, with the abilities
	}

	void ConductTick()
	{
		SyncWanderers();
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
			static const std::vector<RE::TESFaction*> crimeFactions = [] {
				std::vector<RE::TESFaction*> out;
				if (auto* dh = RE::TESDataHandler::GetSingleton())
					for (auto* f : dh->GetFormArray<RE::TESFaction>())
						if (f && f->TracksCrimes()) out.push_back(f);
				SKSE::log::info("Guild: {} factions track crime (bounties are read from these)", out.size());
				return out;
			}();
			for (auto* faction : crimeFactions) {
				const int bounty = faction->GetCrimeGold();
				if (bounty <= 0) continue;
				any = true;
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
			SKSE::log::info("Guild: bounty {} - promotion {}", any ? "active" : "cleared", any ? "on hold" : "no longer on hold");
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

	void AddReport(std::string a_kind, std::string a_title, std::string a_detail, int a_gold, int a_merit, int a_rep)
	{
		{
			std::lock_guard l(g_lock);
			if (!g_registered) return;
			g_reports.push_back({ std::move(a_kind), std::move(a_title), std::move(a_detail), std::max(0, a_gold), std::max(0, a_merit), std::max(0, a_rep) });
		}
		SyncGlobals();  // AG_ReportsWaitingGlobal (SkyrimNet's "take reports" action)
		Counter::Refresh();
	}

	std::string ClaimAll()
	{
		const int bonus = Party::GoldRewardPercent();  // Coin-Bound; read before g_lock (Party has its own)
		int gold = 0, merit = 0, rep = 0;
		std::size_t n;
		{
			std::lock_guard l(g_lock);
			n = g_reports.size();
			if (!n) return Loc::T("$AG_Claim_None", "No reports to submit.");
			for (auto& r : g_reports) {
				gold += r.gold;
				merit += r.merit;
				rep += r.rep;
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
		const auto plural = n == 1 ? "" : "s";
		return gold > 0 ? std::format("Submitted {} report{}: {} gold, {} Merit and {} Reputation.", n, plural, gold, merit, rep)
		                : std::format("Submitted {} report{}: {} Merit and {} Reputation.", n, plural, merit, rep);
	}

	std::string BuyService(const std::string& a_id)
	{
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
		j["today"] = Today();
		// today's calendar date, so the page can turn a stored "days passed" into a date ("3rd of Hearthfire, 4E 201")
		if (auto* cal = RE::Calendar::GetSingleton())
			j["date"] = { { "year", cal->GetYear() }, { "month", cal->GetMonth() }, { "day", static_cast<int>(cal->GetDay()) }, { "hour", cal->GetHour() } };
		j["registeredDay"] = g_registeredDay;
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
		j["services"] = std::move(services);
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
				std::format("tex/rank_{}.png", Letter(next)));
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

	void SyncSuccessors()
	{
		if (!g_liaisonFaction) return;
		for (auto* actor : Adventurers::SucceededLiaisons())
			if (!actor->IsInFaction(g_liaisonFaction)) {
				actor->AddToFaction(g_liaisonFaction, 0);
				SKSE::log::info("Guild: {} keeps a dead liaison's Adventurers Guild counter now", actor->GetDisplayFullName());
			}
	}

	int CardFee() { return g_cfg.cardFee; }

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
		const auto msg = ClaimAll();
		Hud(msg);
		return msg;
	}

	std::string ActionReplaceCard(RE::Actor* a_liaison)
	{
		if (!Adventurers::IsLiaison(a_liaison)) return "not a Guild rep";
		if (!Registered()) return "not registered";
		const auto msg = GuildCard::Replace();
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
