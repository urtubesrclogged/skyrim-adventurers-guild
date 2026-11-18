// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "QuestBoard.h"
#include "Adventurers.h"
#include "MissiveWatch.h"

#include "Counter.h"
#include "Dungeons.h"
#include "Guild.h"
#include "GuildHall.h"
#include "Loc.h"
#include "PrismaToast.h"
#include "RankCore.h"

#include <fstream>
#include <mutex>
#include <nlohmann/json.hpp>
#include <atomic>
#include <cmath>
#include <random>
#include <thread>
#include <unordered_map>
#include <unordered_set>

// Declared (not defined) by CommonLibVR. Two reference pointers, whose order the code below does not
// rely on: it looks for the player in one and a board trigger in the other.
namespace RE
{
	struct TESTriggerEnterEvent
	{
		NiPointer<TESObjectREFR> first;
		NiPointer<TESObjectREFR> second;
	};
}

namespace AG::MissiveWatch
{
	namespace
	{
		std::mutex                                g_lock;
		std::unordered_map<RE::FormID, char>      g_watch;  // resolved runtime FormID -> tier letter
		bool                                       g_active{ false };
		std::unordered_set<RE::FormID>             g_boardBases;  // _M_ActivatorBoard trigger bases
		std::unordered_set<RE::FormID>             g_boardContainers;  // _M_MissiveBoard: the board the player opens
		// The Messages a mod titles its notes from (manifest "messages"): its scripts rebuild some titles from scratch as
		// they post (an enchanting or potion order), so the label is put back each time a board is opened.
		std::vector<std::pair<RE::FormID, char>>   g_titles;
		void                                       RelabelTitles();
		// Each board's own refresh timer, as Missives keeps it on the trigger by the board (_M_ActivatorScript:
		// LastUpdate, RefreshRate): read when the trigger's town loads, since the trigger exists only then. Keyed by
		// the board's StableKey (boards are persistent: the counter can find them). Co-save.
		struct BoardTimer
		{
			float last{ -100.0f };  // GameDaysPassed of its last refresh (Missives starts every board at -100)
			float rate{ 3.0f };     // days between refreshes
			std::string hold;       // the Missives hold whose lists it rolls (read off its trigger's lists; "" until then)
		};
		std::unordered_map<std::string, BoardTimer> g_timers;
		// The Guild Hall as a Missives board (2.0; tools/hall-private/board/INTEGRATION.md, option 2, tested 2026-10-27): a
		// container of Missives' own board base, placed hidden in the great hall at run time, so a missive started while the
		// hall is loaded posts its note there, for any hold. The hall rolls a hold as Missives' board does, when that hold is
		// due (its town boards and the hall share one timer per hold: whichever rolled last), and its roll counts as the
		// hold's refresh. Missives' own and Missives for the Good Guys' quests only (the others: Voice and Quest Expansion and
		// Worldspace Additions pick their hold from where the player stands; Monster Hunt posts into the board by itself;
		// the Bad Guys keep to their refuges). Co-save.
		std::unordered_set<RE::FormID>          g_hallRoll;    // the quests the hall rolls
		std::unordered_map<std::string, float> g_hallRolled;  // hold -> GameDaysPassed of the hall's last roll of it
		RE::FormID                             g_hallBoard{ 0 };  // the placed container
		// Missives for the Good Guys and the Bad Guys, when installed: the list their _M_ActivatorScript finds "the nearest
		// board" in. See FaceBoardList.
		RE::BGSListForm*                            g_boardList{ nullptr };
		float                                       g_dueSince{ -1.0f };  // the last registration or promotion: boards refreshed before it are due
		std::unordered_map<RE::FormID, std::string> g_tag;  // the counter's mark for a mod's own missives ([VQE], [MH]); none for Missives' own
		std::unordered_map<RE::FormID, int>         g_postedStage;  // a quest whose "posted on a board" stage is not 0 (Monster Hunt Missives: 10)
		int PostedStage(RE::FormID a_id)
		{
			const auto it = g_postedStage.find(a_id);
			return it == g_postedStage.end() ? 0 : it->second;
		}
		std::unordered_map<RE::FormID, std::string> g_hold;       // quest -> Missives hold name (Whiterun, Haafingar, ...)
		std::unordered_set<RE::FormID> g_taken;  // missives the player has taken and not finished (for "gave it up")
		// Missives that can never be finished, kept off the boards (1.5.2). Missives 2.03's "Gather Common Ore" for Whiterun
		// (_M_QuestWhiterunGatherOreLow) fills its "Player" alias with the nearest MISSIVE BOARD (GetIsID _M_MissiveBoard)
		// where its 98 sister quests name the player: the ore count watches the board's inventory, never moves past what
		// was carried when the job was taken, and the turn-in needs it to reach the total. Found by that shape, not by name,
		// so an add-on with the same slip is caught too.
		std::unordered_set<RE::FormID> g_broken;
		// one global per known Missives add-on, and whether that add-on is loaded: set on every load, because a save
		// carries the value it had (dialogue reads these: Geldis Sadri and the Raven Rock board)
		std::vector<std::pair<RE::TESGlobal*, float>> g_addonGlobals;

		// Missives names its boards by hold; the guild's liaisons are named by capital.
		std::string HoldOf(const std::string& a_city)
		{
			static const std::unordered_map<std::string, std::string> m{
				{ "Whiterun", "Whiterun" }, { "Solitude", "Haafingar" }, { "Windhelm", "Eastmarch" },
				{ "Riften", "Rift" }, { "Markarth", "Reach" }, { "Morthal", "Hjaalmarch" },
				{ "Dawnstar", "Pale" }, { "Winterhold", "Winterhold" }, { "Falkreath", "Falkreath" },
				{ "Raven Rock", "Solstheim" },  // Missives - Worldspace Additions (missives.addons.json)
			};
			auto it = m.find(a_city);
			return it == m.end() ? std::string{} : it->second;
		}

		// Papyrus Quest.IsRunning(). NOT CommonLib's TESQuest::IsRunning(), which is only "not stopping" and is
		// true for every idle quest (it listed all 29 Whiterun missives as posted when 9 were running).
		bool Running(const RE::TESQuest* a_q) { return a_q && a_q->IsEnabled() && !a_q->IsStopping(); }

		RE::TESObjectREFR* AliasRef(RE::TESQuest* a_q, std::string_view a_name)
		{
			for (auto* a : a_q->aliases) {
				if (a && a->aliasName == a_name) return a_q->GetAliasedRef(a->aliasID).get().get();
			}
			return nullptr;
		}

		// The settlement the player is in (walking up from e.g. the Bannered Mare to Whiterun): the first
		// location carrying LocTypeCity or LocTypeTown. Falls back to the location itself.
		RE::BGSLocation* SettlementOf(RE::BGSLocation* a_loc)
		{
			for (auto* l = a_loc; l; l = l->parentLoc) {
				if (l->HasKeywordString("LocTypeCity") || l->HasKeywordString("LocTypeTown")) return l;
			}
			return a_loc;
		}

		bool Within(RE::BGSLocation* a_loc, const RE::BGSLocation* a_area)
		{
			for (auto* l = a_loc; l; l = l->parentLoc) {
				if (l == a_area) return true;
			}
			return false;
		}

		// Posted on THIS settlement's board: running, not yet accepted, and its note is actually inside a board
		// container located here. A hold has several boards (Whiterun hold: Whiterun, Riverwood, ...) sharing
		// one quest list, so the hold alone isn't enough.
		bool PostedHere(RE::TESQuest* a_q, const RE::BGSLocation* a_area)
		{
			if (!Running(a_q) || a_q->GetCurrentStageID() != PostedStage(a_q->GetFormID())) return false;
			auto* note = AliasRef(a_q, "Missive");
			auto* board = AliasRef(a_q, "MissiveBoard");
			if (!note || !board || !note->GetBaseObject()) return false;
			if (a_area && !Within(board->GetCurrentLocation(), a_area)) return false;
			auto counts = board->GetInventoryCounts();
			auto it = counts.find(note->GetBaseObject());
			return it != counts.end() && it->second > 0;
		}

		std::string StripRank(std::string a_s)
		{
			a_s = QuestBoard::StripRank(std::move(a_s));
			return a_s;
		}

		// The posting's own note title (Missives fills <Alias=...> tokens in it), e.g. "Slay the Giant at
		// Bleakwind Basin"; the quest's journal name if the note can't be read or is still unresolved.
		std::string PostingTitle(RE::TESQuest* a_q)
		{
			std::string title;
			for (auto* alias : a_q->aliases) {
				if (!alias || alias->aliasName != "Missive") continue;
				if (auto note = a_q->GetAliasedRef(alias->aliasID).get()) {
					if (const char* n = note->GetDisplayFullName(); n && *n) title = n;
				}
				break;
			}
			if (title.empty() || title.find("<Alias") != std::string::npos) title = a_q->GetFullName();
			title = StripRank(title);
			if (const auto prefix = Loc::T("$AG_MissivePrefix", "Missive:"); !prefix.empty() && title.starts_with(prefix)) {
				title.erase(0, prefix.size());  // Missives' own title prefix, as its translation writes it
				title.erase(0, title.find_first_not_of(' '));
			}
			return title;
		}

		void Announce(char a_tier, RE::FormID a_quest)
		{
			// The quest's journal name, minus the " [Rank X]" label the patch appends.
			std::string a_title = Loc::T("$AG_Title_GuildMissive", "Guild Missive");
			if (auto* q = RE::TESForm::LookupByID<RE::TESQuest>(a_quest)) {
				a_title = q->GetFullName();
				a_title = QuestBoard::StripRank(std::move(a_title));
			}
			PrismaToast::Show(Loc::T("$AG_Toast_Missive", "MISSIVE COMPLETE"), Loc::T("$AG_Toast_MissiveSub", "Submit your report at any guild counter"), {},
				PrismaToast::Priority::kImportant, PrismaToast::Cue::kComplete);
			Guild::OnMissiveCompleted(FromLetter(a_tier), a_title);
			SKSE::log::info("MissiveWatch: quest complete (tier {})", a_tier);
		}

		bool IsBoard(RE::TESObjectREFR* a_ref)
		{
			auto* base = a_ref ? a_ref->GetBaseObject() : nullptr;
			return base && g_boardBases.contains(base->GetFormID());
		}

		bool ReadTrigger(RE::TESObjectREFR* a_trigger);  // below, with the board timers
		bool IsGuildBoard(RE::TESObjectREFR* a_ref);     // below, with the Guild Hall's board
		void ScheduleHallRoll(std::string a_why, int a_seconds);
		void ScheduleHallRoll(std::string a_why, int a_seconds, int a_tries);

		class Sink :
			public RE::BSTEventSink<RE::TESQuestStageEvent>,
			public RE::BSTEventSink<RE::TESTriggerEnterEvent>,
			public RE::BSTEventSink<RE::TESActivateEvent>,
			public RE::BSTEventSink<RE::TESCellAttachDetachEvent>
		{
		public:
			static Sink* Get()
			{
				static Sink s;
				return &s;
			}

			RE::BSEventNotifyControl ProcessEvent(const RE::TESQuestStageEvent* a_event,
				RE::BSTEventSource<RE::TESQuestStageEvent>*) override
			{
				if (!a_event) return RE::BSEventNotifyControl::kContinue;
				char tier = 0;
				{
					std::lock_guard l(g_lock);
					auto it = g_watch.find(a_event->formID);
					if (it == g_watch.end()) return RE::BSEventNotifyControl::kContinue;
					tier = it->second;
				}
				// accepted (20), withdrawn (110), done: the counter's board list must follow
				if (Counter::IsOpen()) Counter::Refresh();
				// Taken, then given up (110: the note discarded) or failed (105): the Guild takes note. A missive
				// withdrawn from the board (0 -> 110) was never taken.
				bool abandoned = false;
				{
					std::lock_guard l(g_lock);
					if (a_event->stage == 100) g_taken.erase(a_event->formID);
					// one that could never be finished (g_broken) costs nothing to give up
					else if (a_event->stage == 105 || a_event->stage == 110) abandoned = g_taken.erase(a_event->formID) > 0 && !g_broken.contains(a_event->formID);
					else if (a_event->stage > PostedStage(a_event->formID)) g_taken.insert(a_event->formID);
				}
				if (abandoned) {
					std::string title = Loc::T("$AG_Title_GuildMissive", "Guild Missive");
					if (auto* q = RE::TESForm::LookupByID<RE::TESQuest>(a_event->formID)) title = QuestBoard::StripRank(q->GetFullName());
					Guild::OnMissiveAbandoned(FromLetter(tier), title);
				}
				if (a_event->stage != 100) return RE::BSEventNotifyControl::kContinue;
				Announce(tier, a_event->formID);
				return RE::BSEventNotifyControl::kContinue;
			}

			RE::BSEventNotifyControl ProcessEvent(const RE::TESTriggerEnterEvent* a_event,
				RE::BSTEventSource<RE::TESTriggerEnterEvent>*) override
			{
				if (!a_event || g_boardBases.empty()) return RE::BSEventNotifyControl::kContinue;
				auto* a = a_event->first.get();
				auto* b = a_event->second.get();
				const bool hit = (a && a->IsPlayerRef() && IsBoard(b)) || (b && b->IsPlayerRef() && IsBoard(a));
				if (hit) {
					// counted in the log: how often a board reports the player tells a support log whether a
					// board's trigger is firing over and over (the first 20, then every 50th)
					static std::atomic<int> entries{ 0 };
					if (const int n = ++entries; n <= 20 || n % 50 == 0) SKSE::log::info("MissiveWatch: the player entered a board's trigger ({} this session)", n);
					// walking up to a board only takes down what is above the player's rank. The Guild's notice to an
					// unregistered player waits until the board is used (1.3.0: it used to be handed out here, to
					// anyone who walked past - Whiterun's board stands by the gate).
					SKSE::GetTaskInterface()->AddTask([] { WithdrawAboveRank(); });
					// Missives may have just refreshed this board: its timer is read again once its own event has run
					auto* trigger = a && a->IsPlayerRef() ? b : a;
					if (trigger) {
						const auto h = trigger->GetHandle();
						std::thread([h] {
							std::this_thread::sleep_for(std::chrono::seconds(3));
							SKSE::GetTaskInterface()->AddTask([h] {
								if (auto r = h.get()) ReadTrigger(r.get());
							});
						}).detach();
					}
				}
				return RE::BSEventNotifyControl::kContinue;
			}

			// A board's trigger comes into the world with its town: its timer is read (and reset when due)
			RE::BSEventNotifyControl ProcessEvent(const RE::TESCellAttachDetachEvent* a_event, RE::BSTEventSource<RE::TESCellAttachDetachEvent>*) override
			{
				if (!a_event || !a_event->attached || !a_event->reference) return RE::BSEventNotifyControl::kContinue;
				// the great hall comes in (its Guild Board loads): the hall posts the work of every hold that is due
				if (g_active && !g_hallRoll.empty() && IsGuildBoard(a_event->reference.get())) {
					ScheduleHallRoll("the great hall loaded", 2);
					return RE::BSEventNotifyControl::kContinue;
				}
				if (g_boardBases.empty()) return RE::BSEventNotifyControl::kContinue;
				auto* base = a_event->reference->GetBaseObject();
				if (!base || !g_boardBases.contains(base->GetFormID())) return RE::BSEventNotifyControl::kContinue;
				const auto h = a_event->reference->GetHandle();
				SKSE::GetTaskInterface()->AddTask([h] {
					auto ref = h.get();
					if (ref && !ReadTrigger(ref.get()))
						SKSE::GetTaskInterface()->AddTask([h] {
							if (auto r = h.get(); r && !ReadTrigger(r.get())) SKSE::log::warn("MissiveWatch: a board's trigger has no Missives script bound - its refresh timer was not read");
						});
				});
				return RE::BSEventNotifyControl::kContinue;
			}

			// The player opens a board
			RE::BSEventNotifyControl ProcessEvent(const RE::TESActivateEvent* a_event, RE::BSTEventSource<RE::TESActivateEvent>*) override
			{
				if (!a_event || g_boardContainers.empty() || !a_event->objectActivated || !a_event->actionRef || !a_event->actionRef->IsPlayerRef())
					return RE::BSEventNotifyControl::kContinue;
				auto* base = a_event->objectActivated->GetBaseObject();
				if (base && g_boardContainers.contains(base->GetFormID())) RelabelTitles();  // before the board's list is drawn
				if (base && g_boardContainers.contains(base->GetFormID()))
					SKSE::GetTaskInterface()->AddTask([] {
						WithdrawAboveRank();
						Guild::OnBoardApproached();
					});
				return RE::BSEventNotifyControl::kContinue;
			}
		};
	}

	namespace
	{
		std::uint32_t Hex(const nlohmann::json& a_v) { return static_cast<std::uint32_t>(std::stoul(a_v.get<std::string>(), nullptr, 16)); }

		void Label(RE::TESFullName* a_named, char a_tier)
		{
			if (!a_named) return;
			const std::string_view cur = a_named->GetFullName();
			if (QuestBoard::StripRank(std::string(cur)) != cur) return;  // already labeled
			a_named->fullName = std::string(cur) + QuestBoard::RankSuffix(a_tier);
		}

		void RelabelTitles()
		{
			std::lock_guard l(g_lock);
			for (const auto& [id, tier] : g_titles)
				if (auto* msg = RE::TESForm::LookupByID<RE::BGSMessage>(id); msg && *msg->GetFullName()) Label(msg, tier);
		}

		int Count(const RE::TESCondition* a_cond)
		{
			int n = 0;
			for (auto* i = a_cond ? a_cond->head : nullptr; i; i = i->next) ++n;
			return n;
		}

		// The alias a quest cannot start without: non-Optional, the richest existing filter. The rank condition goes
		// first on it. False if the quest has none (it is then shown to every rank).
		bool GateQuest(RE::TESQuest* a_quest, RE::TESGlobal* a_rank, int a_min)
		{
			RE::BGSRefAlias* best = nullptr;
			for (auto* base : a_quest->aliases) {
				if (!base || base->GetVMTypeID() != RE::BGSRefAlias::VMTYPEID) continue;
				auto* alias = static_cast<RE::BGSRefAlias*>(base);
				if (alias->flags.any(RE::BGSBaseAlias::FLAGS::kOptional) || !alias->conditions || !alias->conditions->head) continue;
				if (!best || Count(alias->conditions) > Count(best->conditions)) best = alias;
			}
			// None that is required: the board alias itself, optional or not, if it has conditions. Monster Hunt Missives
			// marks every alias optional and keeps a contract only if its board alias filled (its floor controller stops
			// it otherwise), so a contract above the player's rank is simply never posted.
			if (!best)
				for (auto* base : a_quest->aliases)
					if (base && base->GetVMTypeID() == RE::BGSRefAlias::VMTYPEID && base->aliasName == "MissiveBoard") {
						auto* alias = static_cast<RE::BGSRefAlias*>(base);
						if (alias->conditions && alias->conditions->head) best = alias;
					}
			if (best) QuestBoard::Gate(best->conditions, a_rank, a_min);
			return best != nullptr;
		}

		// A quest whose "Player" alias is filled by matching a GetIsID that names someone other than the player: whatever
		// it watches (an inventory, a kill) is never the player's. See g_broken.
		bool PlayerAliasIsNotPlayer(RE::TESQuest* a_quest)
		{
			for (auto* base : a_quest->aliases) {
				if (!base || base->GetVMTypeID() != RE::BGSRefAlias::VMTYPEID || base->aliasName != "Player") continue;
				auto* alias = static_cast<RE::BGSRefAlias*>(base);
				if (alias->fillType.get() != RE::BGSBaseAlias::FILL_TYPE::kConditions || !alias->conditions) return false;
				for (auto* i = alias->conditions->head; i; i = i->next) {
					if (i->data.functionData.function.get() != RE::FUNCTION_DATA::FunctionID::kGetIsID) continue;
					auto* who = static_cast<RE::TESForm*>(i->data.functionData.params[0]);
					if (who && who->GetFormID() != 0x7) return true;  // 0x7: the player's own NPC record
				}
				return false;
			}
			return false;
		}

		// Kept off every board: a condition no rank meets goes first on its alias, as the rank gate does, so Missives
		// never posts it. Caller holds g_lock.
		void ShutIfBroken(RE::TESQuest* a_quest, RE::TESGlobal* a_rank)
		{
			if (!a_rank || !PlayerAliasIsNotPlayer(a_quest)) return;
			for (auto* base : a_quest->aliases)
				if (base && base->GetVMTypeID() == RE::BGSRefAlias::VMTYPEID && base->aliasName == "Player") {
					auto* alias = static_cast<RE::BGSRefAlias*>(base);
					if (alias->conditions) QuestBoard::Gate(alias->conditions, a_rank, 99);
				}
			g_broken.insert(a_quest->GetFormID());
			SKSE::log::warn("MissiveWatch: {} ({:08X}) can never be finished - its Player alias is not the player - kept off the boards",
				a_quest->GetFormEditorID(), a_quest->GetFormID());
		}

		// "Plugin.esp|0x00ABCD" -> the form, or nullptr
		RE::TESForm* KeyForm(RE::TESDataHandler* a_dh, const std::string& a_key)
		{
			const auto bar = a_key.find('|');
			if (bar == std::string::npos) return nullptr;
			return a_dh->LookupForm(static_cast<RE::FormID>(std::stoul(a_key.substr(bar + 1), nullptr, 16)), a_key.substr(0, bar));
		}

		// "Missives - Voice and Quest Expansion" (MissivesExpansion.esp), when it is loaded: its missives are Guild
		// missives like any other. missives_expansion.json (tools/EspGen) names each with its rank; one quest serves
		// every hold, so it has no hold of its own here (the board its note is on says where it is posted).
		// g_lock held. Returns how many were taken in.
		// The same, for any other mod that posts missives of its own on Missives' boards: Monster Hunt Missives (1.5.0,
		// missives_monsterhunt.json - its hunt contracts; its broker still pays the gold, the Guild credits the report),
		// and Missives for the Good Guys (1.6.0, missives_goodguys.json - its missives are per hold, as Missives' own), and
		// its sister mod Missives for the Bad Guys (1.6.0, missives_badguys.json - on boards of its own, in the Outlaw Refuges).
		std::atomic<int> g_expansion{ 0 };  // 0 not loaded, 1 loaded but nothing taken in, 2 active (MCM Debug page)
		std::atomic<int> g_monsterHunt{ 0 };
		std::atomic<int> g_goodGuys{ 0 };
		std::atomic<int> g_badGuys{ 0 };

		// A quest's "Missive" alias pointed at the rank variant of a Missives note (noteFrom: Missives.esp, noteTo:
		// AdventurersGuild.esp), only while it still creates Missives' original. 1 swapped, -1 left as another patch set
		// it, 0 nothing to do.
		int RetargetNote(RE::TESDataHandler* a_dh, RE::TESQuest* a_quest, const nlohmann::json& a_from, const nlohmann::json& a_to)
		{
			RE::BGSRefAlias* missive = nullptr;
			for (auto* base : a_quest->aliases) {
				if (!base || base->GetVMTypeID() != RE::BGSRefAlias::VMTYPEID) continue;
				auto* alias = static_cast<RE::BGSRefAlias*>(base);
				if (alias->aliasName == "Missive" && alias->fillType.all(RE::BGSBaseAlias::FILL_TYPE::kCreated)) missive = alias;
			}
			if (!missive) return 0;
			// untyped lookup + As<>: LookupForm<T> matches T::FORMTYPE exactly, so <TESBoundObject> never finds a book
			auto* fromForm = a_dh->LookupForm(Hex(a_from), "Missives.esp");
			auto* from = fromForm ? fromForm->As<RE::TESBoundObject>() : nullptr;
			auto* to = a_dh->LookupForm(Hex(a_to), "AdventurersGuild.esp");
			auto*& obj = missive->fillData.created.object;
			if (obj && obj == from && to && to->As<RE::TESBoundObject>()) {
				obj = to->As<RE::TESBoundObject>();
				return 1;
			}
			return from && obj != from ? -1 : 0;
		}

		int IntegrateExpansion(RE::TESDataHandler* a_dh, RE::TESGlobal* a_rankGlobal, const char* a_file, std::atomic<int>& a_state)
		{
			a_state = 0;
			std::ifstream f(std::string("Data/SKSE/Plugins/AdventurersGuild/") + a_file);
			if (!f) return 0;
			auto j = nlohmann::json::parse(f, nullptr, true, true);
			const auto plugin = j.value("plugin", "");
			if (plugin.empty() || (!a_dh->LookupLoadedModByName(plugin) && !a_dh->LookupLoadedLightModByName(plugin))) return 0;
			a_state = 1;
			int taken = 0, gated = 0, missing = 0, labeled = 0, retargeted = 0;
			// a board of its own (the Bad Guys' refuge boards): opened like Missives' own; their trigger is Missives'
			for (auto& b : j.value("boardContainers", nlohmann::json::array()))
				if (auto* c = KeyForm(a_dh, b.get<std::string>())) g_boardContainers.insert(c->GetFormID());
			for (auto& e : j.value("quests", nlohmann::json::array())) {
				auto* form = KeyForm(a_dh, e.value("form", ""));
				auto* quest = form ? form->As<RE::TESQuest>() : nullptr;
				const auto tier = e.value("tier", "");
				if (!quest || tier.empty()) {
					++missing;
					continue;
				}
				g_watch[quest->GetFormID()] = tier[0];
				g_hold[quest->GetFormID()] = e.value("hold", "");  // none: any hold
				// the Good Guys' missives are per hold, from Missives' own lists: the Guild Hall rolls them too
				if (std::string_view(a_file) == "missives_goodguys.json" && !e.value("hold", "").empty()) g_hallRoll.insert(quest->GetFormID());
				if (const int ps = j.value("postedStage", 0); ps != 0) g_postedStage[quest->GetFormID()] = ps;
				if (const auto tg = j.value("tag", std::string()); !tg.empty()) g_tag[quest->GetFormID()] = tg;
				Label(quest, tier[0]);
				if (a_rankGlobal && GateQuest(quest, a_rankGlobal, FromLetter(tier[0]))) ++gated;
				ShutIfBroken(quest, a_rankGlobal);
				if (e.contains("noteTo") && RetargetNote(a_dh, quest, e.at("noteFrom"), e.at("noteTo")) == 1) ++retargeted;
				++taken;
			}
			for (auto& b : j.value("books", nlohmann::json::array())) {
				auto* form = KeyForm(a_dh, b.value("form", ""));
				auto* book = form ? form->As<RE::TESObjectBOOK>() : nullptr;
				const auto tier = b.value("tier", "");
				if (book && !tier.empty()) {
					Label(book, tier[0]);
					++labeled;
				}
			}
			// the Messages a mod titles its notes from at run time (Missives for the Good Guys: "Miner Needed: Collect and
			// Deliver 11 Iron Ore to Falkreath"), each used at one rank: the title keeps the label it is built from
			int titles = 0;
			for (auto& m : j.value("messages", nlohmann::json::array())) {
				auto* form = KeyForm(a_dh, m.value("form", ""));
				auto* msg = form ? form->As<RE::BGSMessage>() : nullptr;
				const auto tier = m.value("tier", "");
				if (msg && !tier.empty()) {
					Label(msg, tier[0]);
					g_titles.emplace_back(msg->GetFormID(), tier[0]);  // g_lock is held (Install)
					++titles;
				}
			}
			SKSE::log::info("MissiveWatch: {} - {} missives taken in ({} rank-gated, {} notes and {} note titles labeled, {} notes swapped to rank variants, "
							"{} not found: a different version of it?)",
				plugin, taken, gated, labeled, titles, retargeted, missing);
			if (taken > 0) a_state = 2;
			return taken;
		}

		// The Missives integration, in memory, on top of whichever version of each quest won the load order (see
		// tools/EspGen/MissivesPatch.cs for why nothing is overridden in the plugin). Data-load time, once.
		// a_plugin: whose quests and notes these are (Missives.esp, or an add-on of it)
		void Integrate(const nlohmann::json& a_j, RE::TESDataHandler* a_dh, const char* a_plugin)
		{
			auto* rankGlobal = a_dh->LookupForm<RE::TESGlobal>(Hex(a_j.at("rankGlobal")), "AdventurersGuild.esp");
			if (!rankGlobal) {
				SKSE::log::error("MissiveWatch: AG_PlayerRankGlobal not found - Missives are NOT rank-gated");
				return;
			}
			int gated = 0, ungated = 0, labeled = 0, retargeted = 0, keptPatched = 0;
			for (auto& entry : a_j.value("quests", nlohmann::json::array())) {
				auto* quest = a_dh->LookupForm<RE::TESQuest>(Hex(entry.at("formId")), a_plugin);
				const auto tier = entry.value("tier", "");
				if (!quest || tier.empty()) continue;
				Label(quest, tier[0]);
				// the must-fill alias: non-Optional, the richest existing filter (as the Missives patch always did)
				RE::BGSRefAlias* best = nullptr;
				for (auto* base : quest->aliases) {
					if (!base || base->GetVMTypeID() != RE::BGSRefAlias::VMTYPEID) continue;
					auto* alias = static_cast<RE::BGSRefAlias*>(base);
					if (alias->flags.any(RE::BGSBaseAlias::FLAGS::kOptional) || !alias->conditions || !alias->conditions->head) continue;
					if (!best || Count(alias->conditions) > Count(best->conditions)) best = alias;
				}
				if (best) {
					QuestBoard::Gate(best->conditions, rankGlobal, FromLetter(tier[0]));
					++gated;
				} else {
					++ungated;
					SKSE::log::warn("MissiveWatch: {} has no gateable alias - shown to every rank", quest->GetFormEditorID());
				}
				ShutIfBroken(quest, rankGlobal);
				// the rank variant of a shared note, only while the quest still creates Missives' original
				if (entry.contains("noteTo")) {
					const int r = RetargetNote(a_dh, quest, entry.at("noteFrom"), entry.at("noteTo"));
					if (r == 1) ++retargeted;
					if (r == -1) ++keptPatched;
				}
			}
			for (auto& b : a_j.value("books", nlohmann::json::array())) {
				auto* book = a_dh->LookupForm<RE::TESObjectBOOK>(Hex(b.at("formId")), a_plugin);
				const auto tier = b.value("tier", "");
				if (book && !tier.empty()) {
					Label(book, tier[0]);
					++labeled;
				}
			}
			SKSE::log::info("MissiveWatch: {} integration applied in memory - {} quests rank-gated, {} ungated, {} notes labeled, {} notes "
							"swapped to rank variants, {} left as another patch set them",
				a_plugin, gated, ungated, labeled, retargeted, keptPatched);
		}

		// One manifest (missives.json, or an add-on's entry in missives.addons.json): what to watch, then the
		// integration. Caller holds g_lock.
		void LoadManifest(const nlohmann::json& a_j, RE::TESDataHandler* a_dh, const char* a_plugin)
		{
			int resolved = 0, missing = 0;
			for (auto& b : a_j.value("boardTriggers", nlohmann::json::array())) {
				const auto localId = static_cast<std::uint32_t>(std::stoul(b.get<std::string>(), nullptr, 16));
				if (auto* act = a_dh->LookupForm(localId, a_plugin)) g_boardBases.insert(act->GetFormID());
			}
			for (auto& b : a_j.value("boardContainers", nlohmann::json::array())) {
				const auto localId = static_cast<std::uint32_t>(std::stoul(b.get<std::string>(), nullptr, 16));
				if (auto* c = a_dh->LookupForm(localId, a_plugin)) g_boardContainers.insert(c->GetFormID());
			}
			for (auto& entry : a_j.value("quests", nlohmann::json::array())) {
				const auto localId = static_cast<std::uint32_t>(std::stoul(entry.at("formId").get<std::string>(), nullptr, 16));
				const auto tierStr = entry.at("tier").get<std::string>();
				if (tierStr.empty()) continue;
				auto* quest = a_dh->LookupForm<RE::TESQuest>(localId, a_plugin);
				if (!quest) {
					missing++;
					continue;
				}
				g_watch[quest->GetFormID()] = tierStr[0];
				g_hold[quest->GetFormID()] = entry.value("hold", "");
				resolved++;
			}
			SKSE::log::info("MissiveWatch: {} - {} quests resolved, {} missing, {} board trigger bases, {} board containers", a_plugin, resolved, missing,
				g_boardBases.size(), g_boardContainers.size());
			Integrate(a_j, a_dh, a_plugin);
		}

		// Missives add-ons (missives.addons.json): each is applied only while its plugin is loaded. Caller holds g_lock.
		std::atomic<int> g_worldspace{ 0 };  // Missives - Worldspace Additions (its Raven Rock board): 0 not loaded, 1 loaded, 2 taken in

		void LoadAddons(RE::TESDataHandler* a_dh)
		{
			g_addonGlobals.clear();
			g_worldspace = 0;
			std::ifstream f("Data/SKSE/Plugins/AdventurersGuild/missives.addons.json");
			if (!f) return;
			try {
				auto j = nlohmann::json::parse(f, nullptr, true, true);
				for (auto& a : j.value("addons", nlohmann::json::array())) {
					const auto plugin = a.value("plugin", std::string());
					if (plugin.empty()) continue;
					const auto* file = a_dh->LookupModByName(plugin);
					const bool  loaded = file && file->compileIndex != 0xFF;
					if (a.contains("global"))
						if (auto* g = a_dh->LookupForm<RE::TESGlobal>(Hex(a.at("global")), "AdventurersGuild.esp")) {
							g->value = loaded ? 1.0f : 0.0f;
							g_addonGlobals.emplace_back(g, g->value);
						}
					if (!loaded) {
						SKSE::log::info("MissiveWatch: add-on {} not loaded", plugin);
						continue;
					}
					g_worldspace = 1;
					LoadManifest(a, a_dh, plugin.c_str());
					if (!a.value("quests", nlohmann::json::array()).empty()) g_worldspace = 2;
				}
			} catch (const std::exception& e) {
				SKSE::log::error("MissiveWatch: missives.addons.json error: {}", e.what());
			}
		}
	}

	void Register()
	{
		auto* dh = RE::TESDataHandler::GetSingleton();
		if (!dh || !dh->LookupLoadedModByName("Missives.esp")) {
			SKSE::log::info("MissiveWatch: Missives.esp not loaded - watch inactive");
			if (dh) {
				std::lock_guard l(g_lock);
				LoadAddons(dh);   // none can be loaded without it: their globals go to 0
			}
			return;
		}

		std::ifstream f("Data/SKSE/Plugins/AdventurersGuild/missives.json");
		if (!f) {
			SKSE::log::error("MissiveWatch: SKSE/Plugins/AdventurersGuild/missives.json missing - reinstall Adventurers Guild; missive features inactive");
			return;
		}

		try {
			auto j = nlohmann::json::parse(f, nullptr, true, true);
			std::lock_guard l(g_lock);
			g_watch.clear();
			g_hold.clear();
			g_postedStage.clear();
			g_tag.clear();
			g_titles.clear();
			LoadManifest(j, dh, "Missives.esp");
			g_hallRoll.clear();
			for (auto& [id, tier] : g_watch)
				if (!g_hold[id].empty()) g_hallRoll.insert(id);  // Missives' own: the hall rolls them
			LoadAddons(dh);
			// Missives - Voice and Quest Expansion (its own manifest: nothing of it is mastered)
			auto* rankGlobal = dh->LookupForm<RE::TESGlobal>(Hex(j.at("rankGlobal")), "AdventurersGuild.esp");
			for (const auto& [file, state] : { std::pair{ "missives_expansion.json", &g_expansion }, std::pair{ "missives_monsterhunt.json", &g_monsterHunt },
					 std::pair{ "missives_goodguys.json", &g_goodGuys }, std::pair{ "missives_badguys.json", &g_badGuys } }) {
				try {
					IntegrateExpansion(dh, rankGlobal, file, *state);
				} catch (const std::exception& e) {
					SKSE::log::error("MissiveWatch: {} error: {} - its missives are not ranked", file, e.what());
				}
			}
		} catch (const std::exception& e) {
			SKSE::log::error("MissiveWatch: missives.json error: {}", e.what());
			return;
		}

		g_boardList = dh->LookupForm<RE::BGSListForm>(0xA49, "MissivesSharedResources.esp");  // the two add-ons' board list; absent without them
		RE::ScriptEventSourceHolder::GetSingleton()->AddEventSink<RE::TESQuestStageEvent>(Sink::Get());
		RE::ScriptEventSourceHolder::GetSingleton()->AddEventSink<RE::TESTriggerEnterEvent>(Sink::Get());
		RE::ScriptEventSourceHolder::GetSingleton()->AddEventSink<RE::TESCellAttachDetachEvent>(Sink::Get());
		RE::ScriptEventSourceHolder::GetSingleton()->AddEventSink<RE::TESActivateEvent>(Sink::Get());
		g_active = true;
		SKSE::log::info("MissiveWatch: registered");
	}

	bool Active() { return g_active; }
	int  ExpansionState() { return g_active ? g_expansion.load() : 0; }
	int  MonsterHuntState() { return g_active ? g_monsterHunt.load() : 0; }
	int  GoodGuysState() { return g_active ? g_goodGuys.load() : 0; }
	int  BadGuysState() { return g_active ? g_badGuys.load() : 0; }
	int  WorldspaceState() { return g_active ? g_worldspace.load() : 0; }

	// After a load: which missives the player is carrying (running, past the board, not finished)
	void OnGameLoaded()
	{
		{
			std::lock_guard l(g_lock);
			for (auto& [global, value] : g_addonGlobals) global->value = value;   // the save brought its own
		}
		if (!g_active) return;
		std::lock_guard l(g_lock);
		g_taken.clear();
		for (auto& [id, tier] : g_watch) {
			auto* q = RE::TESForm::LookupByID<RE::TESQuest>(id);
			if (q && Running(q) && q->GetCurrentStageID() > PostedStage(id) && q->GetCurrentStageID() < 100) g_taken.insert(id);
		}
	}

	namespace
	{
		float DaysPassed()
		{
			auto* cal = RE::Calendar::GetSingleton();
			return cal ? cal->GetDaysPassed() : 0.0f;
		}

		// The script Missives puts on a board's trigger, while the trigger is loaded
		RE::BSTSmartPointer<RE::BSScript::Object> TriggerScript(RE::TESObjectREFR* a_trigger)
		{
			auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton();
			auto* policy = vm ? vm->GetObjectHandlePolicy() : nullptr;
			if (!policy || !a_trigger) return {};
			const auto handle = policy->GetHandleForObject(a_trigger->GetFormType(), a_trigger);
			RE::BSTSmartPointer<RE::BSScript::Object> obj;
			if (handle == policy->EmptyHandle() || !vm->FindBoundObject(handle, "_M_ActivatorScript", obj)) return {};
			return obj;
		}

		// The two add-ons' board script posts only while the board by the trigger is the nearest in their list, and it stops
		// the whole refresh otherwise ("Missives: Player teleported"). Each walled city has a board inside (WhiterunWorld) and
		// a twin in Tamriel at the same coordinates (Whiterun 22 units, Markarth 179), for the trigger on either side of the
		// walls, and Papyrus GetDistance measures across worldspaces: in Whiterun the Tamriel twin is nearer from half of the
		// trigger, and Riften's city board is not in the list at all, only its twin. So a board's trigger, as it loads, turns
		// the entries for its twin into its own board: in place, as a script may be reading the list. Nothing to undo: the
		// twin's trigger turns them back when the player is on that side.
		constexpr float kTwinReach = 300.0f;

		bool IsTwin(const RE::TESObjectREFR* a_board, const RE::TESObjectREFR* a_other)
		{
			if (!a_other || a_other == a_board) return false;
			const auto* world = a_board->GetWorldspace();
			const auto* other = a_other->GetWorldspace();
			if (!world || !other || world == other) return false;
			const auto here = a_board->GetPosition(), there = a_other->GetPosition();
			return std::hypot(here.x - there.x, here.y - there.y) <= kTwinReach;
		}

		void FaceBoardList(RE::TESObjectREFR* a_board)
		{
			if (!g_boardList) return;
			int turned = 0;
			for (auto*& form : g_boardList->forms) {
				if (form && IsTwin(a_board, form->As<RE::TESObjectREFR>())) {
					form = a_board;
					++turned;
				}
			}
			if (auto* added = g_boardList->scriptAddedTempForms) {  // the same, should an add-on's list be filled by script
				for (auto& id : *added) {
					if (IsTwin(a_board, RE::TESForm::LookupByID<RE::TESObjectREFR>(id))) {
						id = a_board->GetFormID();
						++turned;
					}
				}
			}
			static int said = 0;  // the first few in the log: the list is being kept right
			if (turned > 0 && ++said <= 5) SKSE::log::info("MissiveWatch: {} board list entry turned to the board at {}", turned, Adventurers::StableKey(a_board));
		}

		// A board's trigger has just loaded: copy its timer, and make it due if the player registered or was
		// promoted since its last refresh - Missives then refreshes the board itself as the player walks up.
		// On the game's thread. False if its script is not bound yet (asked again on the next frame, once).
		bool ReadTrigger(RE::TESObjectREFR* a_trigger)
		{
			auto obj = TriggerScript(a_trigger);
			if (!obj) return false;
			// by name, through the script's own table of variables (a property's value is in "::<Name>_var")
			const auto var = [&](std::string_view a_name) -> RE::BSScript::Variable* {
				auto* type = obj->GetTypeInfo();
				if (!type) return nullptr;
				const auto* it = type->GetVariableIter();
				for (std::uint32_t i = 0; i < type->GetNumVariables(); ++i)
					if (_stricmp(it[i].name.c_str(), std::string(a_name).c_str()) == 0) return &obj->variables[i];
				return nullptr;
			};
			auto* last = var("LastUpdate");
			auto* boardVar = var("::MissiveBoard_var");
			auto* rateVar = var("::RefreshRate_var");
			auto* board = boardVar ? boardVar->Unpack<RE::TESObjectREFR*>() : nullptr;
			auto* rate = rateVar ? rateVar->Unpack<RE::TESGlobal*>() : nullptr;
			if (!last || !board) {
				std::string names;
				if (auto* type = obj->GetTypeInfo())
					for (std::uint32_t i = 0; i < type->GetNumVariables(); ++i) names += std::string(names.empty() ? "" : ", ") + type->GetVariableIter()[i].name.c_str();
				SKSE::log::warn("MissiveWatch: a board's trigger {:08X} has no {} (its script's variables: {}) - its refresh timer was not read",
					a_trigger->GetFormID(), !last ? "LastUpdate" : "MissiveBoard", names);
				return true;
			}
			FaceBoardList(board);
			const auto key = Adventurers::StableKey(board);
			std::lock_guard l(g_lock);
			auto& t = g_timers[key];
			t.last = last->GetFloat();
			if (rate) t.rate = rate->value;
			// its hold: the hold of the first quest in its lists Missives knows by hold
			if (t.hold.empty())
				for (const auto* name : { "::QuestsLow_var", "::QuestsMed_var", "::QuestsHigh_var", "::QuestsVeryHigh_var" }) {
					auto* lv = var(name);
					auto* list = lv ? lv->Unpack<RE::BGSListForm*>() : nullptr;
					if (list)
						for (auto* f : list->forms)
							if (auto h = f ? g_hold.find(f->GetFormID()) : g_hold.end(); h != g_hold.end() && !h->second.empty()) {
								t.hold = h->second;
								break;
							}
					if (!t.hold.empty()) break;
				}
			static int reads = 0;  // the first few in the log: the timer is being read at all
			if (++reads <= 10) SKSE::log::info("MissiveWatch: board {} ({}) last refreshed on day {:.2f}, every {:.1f} days (today {:.2f})", key, t.hold.empty() ? "hold unknown" : t.hold, t.last, t.rate, DaysPassed());
			// the Guild Hall may have rolled this hold since: that was the hold's refresh, so this board waits its turn
			// (otherwise it would refresh at once and take down what the hall just posted)
			const auto hallIt = t.hold.empty() ? g_hallRolled.end() : g_hallRolled.find(t.hold);
			const float hall = hallIt == g_hallRolled.end() ? -100.0f : hallIt->second;
			const float since = std::max(t.last, hall);
			if (g_dueSince >= 0.0f && since >= 0.0f && since < g_dueSince) {
				last->SetFloat(-100.0f);  // as Missives starts every board: refreshed long ago
				t.last = -100.0f;
				SKSE::log::info("MissiveWatch: the board at {} is due a refresh (the player's rank changed since it last refreshed)", key);
			} else if (hall > t.last) {
				last->SetFloat(hall);
				t.last = hall;
				SKSE::log::info("MissiveWatch: the board at {} waits its turn: the Guild Hall posted {}'s work on day {:.2f}", key, t.hold, hall);
			}
			return true;
		}
	}

	// ---- The Guild Hall as a Missives board (see g_hallRoll) ----
	namespace
	{
		constexpr std::string_view kGuildBoardModel = "adventurersguild\\board\\agguildboard";  // as GuildBoard.cpp knows it
		constexpr float            kBelowFloor = 600.0f;  // the hall's Missives board sits this far under the Guild Board, out of sight

		bool IsGuildBoard(RE::TESObjectREFR* a_ref)
		{
			auto* base = a_ref ? a_ref->GetBaseObject() : nullptr;
			auto* model = base ? base->As<RE::TESModel>() : nullptr;
			const char* path = model ? model->GetModel() : nullptr;
			if (!path || !base->Is(RE::FormType::Activator)) return false;
			std::string p(path);
			std::ranges::transform(p, p.begin(), [](unsigned char c) { return static_cast<char>(c == '/' ? '\\' : std::tolower(c)); });
			return p.find(kGuildBoardModel) != std::string::npos;
		}

		RE::TESBoundObject* HallBoardBase()
		{
			auto* dh = RE::TESDataHandler::GetSingleton();
			auto* f = dh ? dh->LookupForm(0x0012CB, "Missives.esp") : nullptr;  // _M_MissiveBoard
			return f ? f->As<RE::TESBoundObject>() : nullptr;
		}

		RE::TESObjectREFR* HallBoardRef()
		{
			RE::FormID id;
			{
				std::lock_guard l(g_lock);
				id = g_hallBoard;
			}
			auto* r = id ? RE::TESForm::LookupByID<RE::TESObjectREFR>(id) : nullptr;
			auto* base = HallBoardBase();
			return r && base && !r->IsDeleted() && r->GetBaseObject() == base ? r : nullptr;
		}

		// The Guild Board in the player's cell (the great hall; any of its arrangements), or null
		RE::TESObjectREFR* GuildBoardHere()
		{
			auto* pc = RE::PlayerCharacter::GetSingleton();
			RE::TESObjectREFR* found = nullptr;
			if (pc && pc->parentCell)
				pc->parentCell->ForEachReference([&](RE::TESObjectREFR* a_ref) {
					if (!IsGuildBoard(a_ref)) return RE::BSContainer::ForEachResult::kContinue;
					found = a_ref;
					return RE::BSContainer::ForEachResult::kStop;
				});
			return found;
		}

		// The hall's Missives board: the one placed before, or one placed now under the Guild Board. Missives finds it as the
		// nearest loaded board, so it must be enabled and in the great hall; nobody opens it (the Guild Board's page and the
		// hall counter take the notes out, as the inn counters do). Persistent, so it keeps its notes while the hall is unloaded.
		// Main thread.
		RE::TESObjectREFR* EnsureHallBoard(RE::TESObjectREFR* a_anchor)
		{
			auto* cell = a_anchor ? a_anchor->GetParentCell() : nullptr;
			if (!cell) return nullptr;
			if (auto* r = HallBoardRef(); r && r->GetParentCell() == cell) {
				if (r->IsDisabled()) r->Enable(false);
				return r;
			}
			auto* base = HallBoardBase();
			auto* dh = RE::TESDataHandler::GetSingleton();
			if (!base || !dh) {
				SKSE::log::warn("MissiveWatch: Missives' board (_M_MissiveBoard, Missives.esp 0x12CB) not found - the Guild Hall posts no missives");
				return nullptr;
			}
			auto pos = a_anchor->GetPosition();
			pos.z -= kBelowFloor;
			const auto ref = dh->CreateReferenceAtLocation(base, pos, RE::NiPoint3(), cell, nullptr, nullptr, nullptr, RE::ObjectRefHandle(), true, true).get();
			if (!ref) {
				SKSE::log::warn("MissiveWatch: the Guild Hall's Missives board was not created - the hall posts no missives");
				return nullptr;
			}
			{
				std::lock_guard l(g_lock);
				g_hallBoard = ref->GetFormID();
			}
			SKSE::log::info("MissiveWatch: the Guild Hall's Missives board placed ({:08X}, under the Guild Board)", ref->GetFormID());
			return ref.get();
		}

		float MissivesGlobal(RE::FormID a_id, float a_default)
		{
			auto* dh = RE::TESDataHandler::GetSingleton();
			auto* g = dh ? dh->LookupForm<RE::TESGlobal>(a_id, "Missives.esp") : nullptr;
			return g ? g->value : a_default;
		}

		// What the hall's board holds: missives posted there now
		int HallPosted()
		{
			auto* board = HallBoardRef();
			if (!board) return 0;
			int n = 0;
			std::lock_guard l(g_lock);
			for (auto& [id, tier] : g_watch) {
				auto* q = RE::TESForm::LookupByID<RE::TESQuest>(id);
				if (q && PostedHere(q, nullptr) && AliasRef(q, "MissiveBoard") == board) ++n;
			}
			return n;
		}

		// The hall's roll: Missives' own (_M_ActivatorScript.UpdateQuests) over every hold that is due. A hold is due when
		// neither the hall nor any of its town boards has rolled it within Missives' refresh rate, or none has since the
		// player registered or was promoted. Each quest of a due hold at or below the player's rank is rolled at Missives'
		// odds for its list; a hit starts one that isn't running (its note posts in the hall's board) and takes down one
		// still posted, as Missives does. a_force: every hold (DevBench). Main thread.
		void HallRoll(const std::string& a_why, bool a_force)
		{
			if (!g_active || g_hallRoll.empty() || !GuildHall::PlayerInHall()) return;
			if (Guild::SaveState() == Guild::SaveData::kBroken) return;  // the rank is not known this session
			const int rank = Guild::WorkRank();
			if (rank < 0) return;  // missives are for registered adventurers
			auto* anchor = GuildBoardHere();
			if (!anchor) return;  // the cellars or the strongroom: rolled on coming up into the great hall
			auto* board = EnsureHallBoard(anchor);
			if (!board) return;
			// Missives' odds per list (its own settings may change them) and its refresh rate. Low E, Med D, High C, VeryHigh B
			const float chance[4] = { MissivesGlobal(0x001D93, 50.0f), MissivesGlobal(0x001D94, 35.0f), MissivesGlobal(0x001D95, 20.0f),
				MissivesGlobal(0x009450, 5.0f) };
			const float rate = MissivesGlobal(0x001D96, 3.0f);
			static std::mt19937                  rng{ std::random_device{}() };
			std::uniform_int_distribution<int>   roll(0, 100);  // Utility.RandomInt(): 0 to 100
			std::vector<RE::TESQuest*>           starts, stops;
			std::vector<std::string>             rolled;
			{
				std::lock_guard l(g_lock);
				const float                            now = DaysPassed();
				std::unordered_map<std::string, float> lastOf;  // hold -> its last roll, by the hall or a town board
				for (auto id : g_hallRoll) lastOf.emplace(g_hold[id], -100.0f);
				for (auto& [h, day] : g_hallRolled)
					if (auto it = lastOf.find(h); it != lastOf.end()) it->second = std::max(it->second, day);
				for (auto& [k, t] : g_timers)
					if (auto it = lastOf.find(t.hold); it != lastOf.end()) it->second = std::max(it->second, t.last);
				std::unordered_set<std::string> due;
				for (auto& [h, last] : lastOf)
					if (a_force || (g_dueSince >= 0.0f && last < g_dueSince) || now > last + rate) {
						due.insert(h);
						g_hallRolled[h] = now;
						rolled.push_back(h);
					}
				for (auto id : g_hallRoll) {
					if (!due.contains(g_hold[id]) || g_broken.contains(id)) continue;
					const int list = FromLetter(g_watch[id]);
					if (list < 0 || list > 3 || list > rank) continue;
					if (static_cast<float>(roll(rng)) >= chance[list]) continue;  // Missives: RandomInt() < chance
					auto* q = RE::TESForm::LookupByID<RE::TESQuest>(id);
					if (!q) continue;
					if (!Running(q)) starts.push_back(q);
					else if (q->GetCurrentStageID() == PostedStage(id)) stops.push_back(q);
				}
			}
			if (rolled.empty()) return;
			std::ranges::sort(rolled);
			std::string holds;
			for (auto& h : rolled) holds += (holds.empty() ? "" : ", ") + h;
			SKSE::log::info("MissiveWatch: the Guild Hall rolled {} hold(s) ({}): {} to post, {} to take down [{}]", rolled.size(), a_why, starts.size(), stops.size(), holds);
			if (starts.empty() && stops.empty()) return;
			auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton();
			if (!vm) return;
			RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> cb;
			vm->DispatchStaticCall("AG_QuestHelper", "HallRoll", RE::MakeFunctionArguments(std::move(starts), std::move(stops), static_cast<RE::TESObjectREFR*>(board), g_goodGuys.load() > 0), cb);
			// a while later, in the log: what the hall's board holds (Papyrus starts them one by one)
			std::thread([] {
				std::this_thread::sleep_for(std::chrono::seconds(20));
				SKSE::GetTaskInterface()->AddTask([] { SKSE::log::info("MissiveWatch: the Guild Hall's board holds {} missive(s)", HallPosted()); });
			}).detach();
		}

		// a_tries: the great hall's board loads before the load screen ends, so the roll waits (2 s at a time) until the player
		// is in the great hall, for up to a minute
		void ScheduleHallRoll(std::string a_why, int a_seconds, int a_tries)
		{
			std::thread([why = std::move(a_why), a_seconds, a_tries] {
				std::this_thread::sleep_for(std::chrono::seconds(a_seconds));
				SKSE::GetTaskInterface()->AddTask([why, a_tries] {
					auto* ui = RE::UI::GetSingleton();
					const bool loading = ui && ui->IsMenuOpen(RE::LoadingMenu::MENU_NAME);
					if (loading || !GuildHall::PlayerInHall() || !GuildBoardHere()) {
						if (a_tries > 1) ScheduleHallRoll(why, 2, a_tries - 1);
						return;
					}
					HallRoll(why, false);
				});
			}).detach();
		}
		void ScheduleHallRoll(std::string a_why, int a_seconds) { ScheduleHallRoll(std::move(a_why), a_seconds, 30); }
	}

	void DebugHallRoll()
	{
		SKSE::GetTaskInterface()->AddTask([] {
			if (!GuildHall::PlayerInHall()) SKSE::log::info("MissiveWatch::DebugHallRoll: not in the Guild Hall");
			HallRoll("DevBench", true);
		});
	}

	void PrepareUninstallHall()
	{
		auto* board = HallBoardRef();
		if (!board) return;
		// what it holds comes down (Missives' withdrawal, as at any board), then the board itself goes
		std::vector<RE::TESQuest*> posted;
		{
			std::lock_guard l(g_lock);
			for (auto& [id, tier] : g_watch) {
				auto* q = RE::TESForm::LookupByID<RE::TESQuest>(id);
				if (q && PostedHere(q, nullptr) && AliasRef(q, "MissiveBoard") == board) posted.push_back(q);
			}
		}
		if (auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton())
			for (auto* q : posted) {
				RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> cb;
				vm->DispatchStaticCall("AG_QuestHelper", "WithdrawMissive", RE::MakeFunctionArguments(static_cast<RE::TESQuest*>(q)), cb);
			}
		// the board goes once the withdrawals have run (Missives takes each note back out of it at stage 110)
		const auto h = board->GetHandle();
		const auto n = posted.size();
		std::thread([h, n] {
			std::this_thread::sleep_for(std::chrono::seconds(5));
			SKSE::GetTaskInterface()->AddTask([h, n] {
				if (auto r = h.get()) {
					r->Disable();
					r->SetDelete(true);
				}
				{
					std::lock_guard l(g_lock);
					g_hallBoard = 0;
				}
				SKSE::log::info("MissiveWatch: prepare to uninstall: the Guild Hall's Missives board removed, {} missive(s) on it withdrawn", n);
			});
		}).detach();
	}

	void MakeBoardsDue(std::string_view a_why)
	{
		{
			std::lock_guard l(g_lock);
			g_dueSince = DaysPassed();
			for (auto& [key, t] : g_timers) t.last = std::min(t.last, -100.0f);  // shown as due at once; the trigger itself is reset when it loads
		}
		SKSE::log::info("MissiveWatch: every board is due a refresh ({}): Missives refreshes each as the player next walks up to it", a_why);
		// a board already loaded around the player is reset now
		if (auto* player = RE::PlayerCharacter::GetSingleton(); player && player->parentCell)
			player->parentCell->ForEachReference([](RE::TESObjectREFR* a_ref) {
				auto* base = a_ref ? a_ref->GetBaseObject() : nullptr;
				if (base && g_boardBases.contains(base->GetFormID())) ReadTrigger(a_ref);
				return RE::BSContainer::ForEachResult::kContinue;
			});
		// in the great hall: the hall posts at once (every hold is due now)
		if (GuildHall::PlayerInHall()) ScheduleHallRoll(std::string(a_why), 1);
	}

	nlohmann::json BoardStatus()
	{
		auto* player = RE::PlayerCharacter::GetSingleton();
		const auto* area = SettlementOf(player ? player->GetCurrentLocation() : nullptr);
		if (!area || g_boardContainers.empty()) return nullptr;
		// the board of this town: a persistent reference, so it can be found from inside the inn
		static std::vector<RE::FormID> boards;
		if (boards.empty()) {
			const auto& [map, lock] = RE::TESForm::GetAllForms();
			RE::BSReadLockGuard rl{ lock };
			if (map)
				for (auto& [id, form] : *map) {
					auto* ref = form ? form->As<RE::TESObjectREFR>() : nullptr;
					auto* base = ref ? ref->GetBaseObject() : nullptr;
					if (base && g_boardContainers.contains(base->GetFormID())) boards.push_back(id);
				}
		}
		// A town may have more than one board (Whiterun: Missives' own, and one Missives - Worldspace Additions adds). The
		// one due soonest of those whose timer has been read; none read yet: nothing to say, unless the rank has just
		// changed, which made every board due.
		const char* name = area->GetFullName();
		bool        found = false, unread = false;
		float       soonest = std::numeric_limits<float>::max();
		for (const auto id : boards) {
			auto* board = RE::TESForm::LookupByID<RE::TESObjectREFR>(id);
			auto* loc = board ? board->GetCurrentLocation() : nullptr;
			if (!loc || !Within(loc, area)) continue;
			std::lock_guard l(g_lock);
			if (auto it = g_timers.find(Adventurers::StableKey(board)); it != g_timers.end()) {
				// Missives refreshes when GameDaysPassed > LastUpdate + RefreshRate; a roll of its hold by the Guild Hall since
				// counts (the board takes that time when its town next loads)
				float last = it->second.last;
				if (auto h = g_hallRolled.find(it->second.hold); !it->second.hold.empty() && h != g_hallRolled.end()) last = std::max(last, h->second);
				soonest = std::min(soonest, last + it->second.rate - DaysPassed());
				found = true;
			} else {
				unread = true;
			}
		}
		const auto status = [&](bool a_due, int a_hours) { return nlohmann::json{ { "name", name && *name ? name : "" }, { "due", a_due }, { "hours", a_hours } }; };
		if (found) return status(soonest <= 0.0f, soonest > 0.0f ? static_cast<int>(std::ceil(soonest * 24.0f)) : 0);
		if (unread && g_dueSince >= 0.0f) return status(true, 0);
		return nullptr;
	}

	nlohmann::json Save()
	{
		std::lock_guard l(g_lock);
		auto timers = nlohmann::json::object();
		for (auto& [k, t] : g_timers) timers[k] = { t.last, t.rate, t.hold };
		return { { "dueSince", g_dueSince }, { "timers", timers }, { "hallRolled", g_hallRolled }, { "hallBoard", g_hallBoard } };
	}

	void Load(const nlohmann::json& a_j)
	{
		std::lock_guard l(g_lock);
		g_timers.clear();
		g_dueSince = a_j.value("dueSince", -1.0f);
		if (a_j.contains("timers") && a_j.at("timers").is_object())
			for (auto& [k, v] : a_j.at("timers").items())
				if (v.is_array() && v.size() >= 2)
					g_timers[Adventurers::CanonicalKey(k)] = { v[0].get<float>(), v[1].get<float>(), v.size() > 2 && v[2].is_string() ? v[2].get<std::string>() : std::string() };
		g_hallRolled.clear();
		if (a_j.contains("hallRolled") && a_j.at("hallRolled").is_object())
			for (auto& [h, day] : a_j.at("hallRolled").items())
				if (day.is_number()) g_hallRolled[h] = day.get<float>();
		// a created reference keeps its FormID in the save (checked against Missives' board base when used)
		g_hallBoard = a_j.value("hallBoard", static_cast<RE::FormID>(0));
	}

	void Revert()
	{
		std::lock_guard l(g_lock);
		g_timers.clear();
		g_dueSince = -1.0f;
		g_hallRolled.clear();
		g_hallBoard = 0;
	}

	void WithdrawAboveRank()
	{
		if (!g_active) return;
		if (Guild::SaveState() == Guild::SaveData::kBroken) return;  // the rank is not known this session: nothing comes down on a guess
		const int rank = Guild::WorkRank();  // -1 before registering: every posting is above it
		std::vector<RE::TESQuest*> stale;
		{
			std::lock_guard l(g_lock);
			for (auto& [id, tier] : g_watch) {
				if (FromLetter(tier) <= rank && !g_broken.contains(id)) continue;  // one that can never be finished comes down too
				auto* q = RE::TESForm::LookupByID<RE::TESQuest>(id);
				if (Running(q) && q->GetCurrentStageID() == 0) stale.push_back(q);
			}
		}
		auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton();
		if (!vm) return;
		for (auto* q : stale) {
			RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> cb;
			vm->DispatchStaticCall("AG_QuestHelper", "WithdrawMissive", RE::MakeFunctionArguments(static_cast<RE::TESQuest*>(q)), cb);
		}
		if (!stale.empty()) SKSE::log::info("MissiveWatch: withdrew {} posted missive(s) above work rank {}", stale.size(), rank);
	}

	int InProgress()
	{
		if (!g_active) return 0;
		int n = 0;
		std::lock_guard l(g_lock);
		for (auto& [id, tier] : g_watch) {
			auto* q = RE::TESForm::LookupByID<RE::TESQuest>(id);
			if (q && Running(q) && q->GetCurrentStageID() > PostedStage(q->GetFormID()) && !q->IsCompleted()) ++n;  // up to the posted stage is "on a board"
		}
		return n;
	}

	nlohmann::json Postings(const std::string& a_city)
	{
		auto out = nlohmann::json::array();
		const auto hold = HoldOf(a_city);
		if (!g_active || hold.empty()) return out;
		const int rank = Guild::WorkRank();
		auto* player = RE::PlayerCharacter::GetSingleton();
		const auto* area = SettlementOf(player ? player->GetCurrentLocation() : nullptr);
		std::vector<std::pair<RE::TESQuest*, char>> posted;
		{
			std::lock_guard l(g_lock);
			for (auto& [id, tier] : g_watch) {
				if (FromLetter(tier) > rank || g_broken.contains(id)) continue;
				auto h = g_hold.find(id);
				if (h == g_hold.end() || (!h->second.empty() && h->second != hold)) continue;  // "" = a quest that serves every hold
				auto* q = RE::TESForm::LookupByID<RE::TESQuest>(id);
				if (q && PostedHere(q, area)) posted.emplace_back(q, tier);
			}
		}
		std::sort(posted.begin(), posted.end(), [](auto& a, auto& b) { return a.second != b.second ? FromLetter(a.second) > FromLetter(b.second) : a.first->GetFormID() < b.first->GetFormID(); });
		for (auto& [q, tier] : posted) {
			const auto tg = g_tag.find(q->GetFormID());
			out.push_back({ { "id", std::format("{:08X}", q->GetFormID()) }, { "tier", std::string(1, tier) }, { "title", PostingTitle(q) },
				{ "tag", tg == g_tag.end() ? std::string() : tg->second } });
		}
		return out;
	}

	nlohmann::json AllPostings()
	{
		auto out = nlohmann::json::array();
		if (!g_active) return out;
		const int rank = Guild::WorkRank();
		struct Row { RE::TESQuest* q; char tier; std::string hold, city; };
		std::vector<Row> posted;
		{
			std::lock_guard l(g_lock);
			for (auto& [id, tier] : g_watch) {
				if (FromLetter(tier) > rank || g_broken.contains(id)) continue;
				auto* q = RE::TESForm::LookupByID<RE::TESQuest>(id);
				if (!q || !PostedHere(q, nullptr)) continue;
				// the board it hangs on names the town; a quest that serves every hold ("") is of that town's hold
				auto*       board = AliasRef(q, "MissiveBoard");
				std::string city = board ? Dungeons::CityOf(board->GetCurrentLocation()) : std::string();
				auto        h = g_hold.find(id);
				std::string hold = h != g_hold.end() && !h->second.empty() ? h->second : HoldOf(city);
				if (hold.empty()) continue;
				posted.push_back({ q, tier, std::move(hold), std::move(city) });
			}
		}
		std::sort(posted.begin(), posted.end(), [](auto& a, auto& b) { return a.tier != b.tier ? FromLetter(a.tier) > FromLetter(b.tier) : a.q->GetFormID() < b.q->GetFormID(); });
		for (auto& r : posted) {
			const auto tg = g_tag.find(r.q->GetFormID());
			out.push_back({ { "id", std::format("{:08X}", r.q->GetFormID()) }, { "tier", std::string(1, r.tier) }, { "title", PostingTitle(r.q) },
				{ "tag", tg == g_tag.end() ? std::string() : tg->second }, { "hold", r.hold }, { "city", r.city } });
		}
		return out;
	}

	namespace
	{
		RE::BGSBaseAlias* AliasNamed(RE::TESQuest* a_q, std::string_view a_name)
		{
			for (auto* a : a_q->aliases) {
				if (a && a->aliasName == a_name) return a;
			}
			return nullptr;
		}

		// What the engine prints for <Alias=Name> in this quest instance: the quest's own instance text table
		// (alias -> form whose name fills it) covers ref AND location aliases; the filled ref's name is a fallback.
		std::string AliasText(RE::TESQuest* a_q, const RE::BGSQuestInstanceText* a_inst, const std::string& a_name, bool a_baseName)
		{
			auto* alias = AliasNamed(a_q, a_name);
			if (!alias) return a_name;
			if (a_inst && !a_baseName) {
				for (auto& sd : a_inst->stringData) {
					if (sd.aliasID != alias->aliasID) continue;
					if (auto* f = RE::TESForm::LookupByID(sd.fullNameFormID); f && f->GetName() && *f->GetName()) return f->GetName();
				}
			}
			if (auto ref = a_q->GetAliasedRef(alias->aliasID).get()) {
				if (auto* base = ref->GetBaseObject(); a_baseName && base && base->GetName() && *base->GetName()) return base->GetName();
				if (const char* n = ref->GetDisplayFullName(); n && *n) return n;
			}
			return a_name;
		}
	}

	nlohmann::json Details(const std::string& a_formIdHex)
	{
		nlohmann::json out{ { "id", a_formIdHex } };
		RE::TESQuest* q = nullptr;
		char tier = 0;
		try {
			const auto id = static_cast<RE::FormID>(std::stoul(a_formIdHex, nullptr, 16));
			std::lock_guard l(g_lock);
			if (auto it = g_watch.find(id); it != g_watch.end()) {
				q = RE::TESForm::LookupByID<RE::TESQuest>(id);
				tier = it->second;
			}
		} catch (...) {}
		if (!q) return out;
		out["tier"] = std::string(1, tier);
		out["title"] = PostingTitle(q);
		out["posted"] = Running(q) && q->GetCurrentStageID() == PostedStage(q->GetFormID());
		{
			std::lock_guard l(g_lock);
			if (const auto tg = g_tag.find(q->GetFormID()); tg != g_tag.end()) out["tag"] = tg->second;
		}

		auto* noteAlias = AliasNamed(q, "Missive");
		auto  note = noteAlias ? q->GetAliasedRef(noteAlias->aliasID).get() : nullptr;
		auto* book = note && note->GetBaseObject() ? note->GetBaseObject()->As<RE::TESObjectBOOK>() : nullptr;
		if (!book) return out;
		RE::BSString raw;
		book->GetDescription(raw, nullptr);

		// the instance of the quest text this note was stamped with (what the engine uses when it's read)
		std::uint32_t instId = q->currentInstanceID;
		if (auto* td = note->extraList.GetByType<RE::ExtraTextDisplayData>(); td && td->ownerQuest == q && td->ownerInstance.underlying() >= 0) {
			instId = static_cast<std::uint32_t>(td->ownerInstance.underlying());
		}
		const RE::BGSQuestInstanceText* inst = nullptr;
		for (auto* it : q->instanceData) {
			if (it && it->id == instId) inst = it;
		}

		// fill <Alias=X> / <Alias.BaseName=X>, drop book markup (<font ...>, </font>, <p ...>)
		std::string text;
		const std::string src = raw.c_str() ? raw.c_str() : "";
		for (std::size_t i = 0; i < src.size();) {
			if (src[i] != '<') { text += src[i++]; continue; }
			const auto end = src.find('>', i);
			if (end == std::string::npos) { text += src.substr(i); break; }
			const std::string tag = src.substr(i + 1, end - i - 1);
			if (tag.starts_with("Alias=")) text += AliasText(q, inst, tag.substr(6), false);
			else if (tag.starts_with("Alias.BaseName=")) text += AliasText(q, inst, tag.substr(15), true);
			else if (tag == "br" || tag == "br/" || tag == "p" || tag.starts_with("p ")) text += '\n';
			i = end + 1;
		}
		// tidy: trim each line, at most one blank line in a row, none at the ends
		std::string tidy;
		bool blank = false;
		std::size_t pos = 0;
		while (pos <= text.size()) {
			auto nl = text.find('\n', pos);
			if (nl == std::string::npos) nl = text.size();
			auto line = text.substr(pos, nl - pos);
			const auto a = line.find_first_not_of(" \t\r");
			line = a == std::string::npos ? std::string{} : line.substr(a, line.find_last_not_of(" \t\r") - a + 1);
			if (line.empty()) {
				if (!tidy.empty() && !blank) tidy += '\n';
				blank = true;
			} else {
				tidy += line + '\n';
				blank = false;
			}
			pos = nl + 1;
		}
		while (!tidy.empty() && tidy.back() == '\n') tidy.pop_back();
		out["text"] = tidy;
		return out;
	}

	std::string Accept(const std::string& a_formIdHex)
	{
		RE::TESQuest* q = nullptr;
		try {
			const auto id = static_cast<RE::FormID>(std::stoul(a_formIdHex, nullptr, 16));
			std::lock_guard l(g_lock);
			if (g_watch.contains(id)) q = RE::TESForm::LookupByID<RE::TESQuest>(id);
		} catch (...) {}
		if (!q || !Running(q) || q->GetCurrentStageID() != PostedStage(q->GetFormID())) return Loc::T("$AG_Missive_Gone", "That missive is no longer posted.");
		auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton();
		if (!vm) return "";
		const auto title = PostingTitle(q);
		RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> cb;
		vm->DispatchStaticCall("AG_QuestHelper", "AcceptMissive", RE::MakeFunctionArguments(static_cast<RE::TESQuest*>(q), static_cast<std::int32_t>(PostedStage(q->GetFormID()))), cb);
		SKSE::log::info("MissiveWatch: accepted {:08X} ({}) from the counter", q->GetFormID(), title);
		return Loc::F("$AG_Missive_Taken", "Missive taken: {}", title);
	}

	void DebugBoard()
	{
		WithdrawAboveRank();
		Guild::OnBoardApproached();
	}

	void DebugComplete(const std::string& a_formIdHex)
	{
		if (!g_active) {
			SKSE::log::warn("MissiveWatch::DebugComplete: watch inactive");
			return;
		}
		try {
			const auto formId = static_cast<RE::FormID>(std::stoul(a_formIdHex, nullptr, 16));
			char tier = 0;
			{
				std::lock_guard l(g_lock);
				auto it = g_watch.find(formId);
				if (it == g_watch.end()) {
					SKSE::log::warn("MissiveWatch::DebugComplete: {} not a watched quest", a_formIdHex);
					return;
				}
				tier = it->second;
			}
			Announce(tier, formId);
		} catch (const std::exception& e) {
			SKSE::log::error("MissiveWatch::DebugComplete: bad FormID '{}': {}", a_formIdHex, e.what());
		}
	}
}
