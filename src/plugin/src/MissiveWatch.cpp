// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "QuestBoard.h"
#include "MissiveWatch.h"

#include "Counter.h"
#include "Guild.h"
#include "Loc.h"
#include "PrismaToast.h"
#include "RankCore.h"

#include <fstream>
#include <mutex>
#include <nlohmann/json.hpp>
#include <atomic>
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
		std::unordered_map<RE::FormID, std::string> g_hold;       // quest -> Missives hold name (Whiterun, Haafingar, ...)
		std::unordered_set<RE::FormID> g_taken;  // missives the player has taken and not finished (for "gave it up")
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
			if (!Running(a_q) || a_q->GetCurrentStageID() != 0) return false;
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
			PrismaToast::Show(Loc::T("$AG_Toast_Missive", "MISSIVE COMPLETE"), Loc::T("$AG_Toast_MissiveSub", "Submit your report at any guild counter"));
			Guild::OnMissiveCompleted(FromLetter(a_tier), a_title);
			SKSE::log::info("MissiveWatch: quest complete (tier {})", a_tier);
		}

		bool IsBoard(RE::TESObjectREFR* a_ref)
		{
			auto* base = a_ref ? a_ref->GetBaseObject() : nullptr;
			return base && g_boardBases.contains(base->GetFormID());
		}

		class Sink :
			public RE::BSTEventSink<RE::TESQuestStageEvent>,
			public RE::BSTEventSink<RE::TESTriggerEnterEvent>,
			public RE::BSTEventSink<RE::TESActivateEvent>
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
					else if (a_event->stage == 105 || a_event->stage == 110) abandoned = g_taken.erase(a_event->formID) > 0;
					else if (a_event->stage > 0) g_taken.insert(a_event->formID);
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
				}
				return RE::BSEventNotifyControl::kContinue;
			}

			// The player opens a board
			RE::BSEventNotifyControl ProcessEvent(const RE::TESActivateEvent* a_event, RE::BSTEventSource<RE::TESActivateEvent>*) override
			{
				if (!a_event || g_boardContainers.empty() || !a_event->objectActivated || !a_event->actionRef || !a_event->actionRef->IsPlayerRef())
					return RE::BSEventNotifyControl::kContinue;
				auto* base = a_event->objectActivated->GetBaseObject();
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

		// "AG_PlayerRankGlobal >= rank" as the FIRST condition, so it is ANDed with the whole existing list (a leading
		// AND item forms its own group, whatever OR groups follow). Game heap (TESConditionItem redefines new).
		void Gate(RE::TESCondition* a_cond, RE::TESGlobal* a_rank, int a_min)
		{
			auto* item = new RE::TESConditionItem();
			item->data.object = RE::CONDITIONITEMOBJECT::kSelf;
			item->data.functionData.function = RE::FUNCTION_DATA::FunctionID::kGetGlobalValue;
			item->data.functionData.params[0] = a_rank;
			item->data.flags.opCode = RE::CONDITION_ITEM_DATA::OpCode::kGreaterThanOrEqualTo;
			item->data.flags.isOR = false;
			item->data.comparisonValue.f = static_cast<float>(a_min);
			item->next = a_cond->head;
			a_cond->head = item;
		}

		int Count(const RE::TESCondition* a_cond)
		{
			int n = 0;
			for (auto* i = a_cond ? a_cond->head : nullptr; i; i = i->next) ++n;
			return n;
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
				RE::BGSRefAlias* missive = nullptr;
				for (auto* base : quest->aliases) {
					if (!base || base->GetVMTypeID() != RE::BGSRefAlias::VMTYPEID) continue;
					auto* alias = static_cast<RE::BGSRefAlias*>(base);
					if (alias->aliasName == "Missive" && alias->fillType.all(RE::BGSBaseAlias::FILL_TYPE::kCreated)) missive = alias;
					if (alias->flags.any(RE::BGSBaseAlias::FLAGS::kOptional) || !alias->conditions || !alias->conditions->head) continue;
					if (!best || Count(alias->conditions) > Count(best->conditions)) best = alias;
				}
				if (best) {
					Gate(best->conditions, rankGlobal, FromLetter(tier[0]));
					++gated;
				} else {
					++ungated;
					SKSE::log::warn("MissiveWatch: {} has no gateable alias - shown to every rank", quest->GetFormEditorID());
				}
				// the rank variant of a shared note, only while the quest still creates Missives' original
				if (entry.contains("noteTo") && missive) {
					// untyped lookup + As<>: LookupForm<T> matches T::FORMTYPE exactly, so <TESBoundObject> never finds a book
					auto* fromForm = a_dh->LookupForm(Hex(entry.at("noteFrom")), "Missives.esp");
					auto* from = fromForm ? fromForm->As<RE::TESBoundObject>() : nullptr;
					auto* to = a_dh->LookupForm(Hex(entry.at("noteTo")), "AdventurersGuild.esp");
					auto*& obj = missive->fillData.created.object;
					if (obj && obj == from && to && to->As<RE::TESBoundObject>()) {
						obj = to->As<RE::TESBoundObject>();
						++retargeted;
					} else if (from && obj != from) {
						++keptPatched;
					}
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
		void LoadAddons(RE::TESDataHandler* a_dh)
		{
			g_addonGlobals.clear();
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
					LoadManifest(a, a_dh, plugin.c_str());
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
			LoadManifest(j, dh, "Missives.esp");
			LoadAddons(dh);
		} catch (const std::exception& e) {
			SKSE::log::error("MissiveWatch: missives.json error: {}", e.what());
			return;
		}

		RE::ScriptEventSourceHolder::GetSingleton()->AddEventSink<RE::TESQuestStageEvent>(Sink::Get());
		RE::ScriptEventSourceHolder::GetSingleton()->AddEventSink<RE::TESTriggerEnterEvent>(Sink::Get());
		RE::ScriptEventSourceHolder::GetSingleton()->AddEventSink<RE::TESActivateEvent>(Sink::Get());
		g_active = true;
		SKSE::log::info("MissiveWatch: registered");
	}

	bool Active() { return g_active; }

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
			if (q && Running(q) && q->GetCurrentStageID() > 0 && q->GetCurrentStageID() < 100) g_taken.insert(id);
		}
	}

	void WithdrawAboveRank()
	{
		if (!g_active) return;
		const int rank = Guild::Rank();  // -1 before registering: every posting is above it
		std::vector<RE::TESQuest*> stale;
		{
			std::lock_guard l(g_lock);
			for (auto& [id, tier] : g_watch) {
				if (FromLetter(tier) <= rank) continue;
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
		if (!stale.empty()) SKSE::log::info("MissiveWatch: withdrew {} posted missive(s) above guild rank {}", stale.size(), rank);
	}

	int InProgress()
	{
		if (!g_active) return 0;
		int n = 0;
		std::lock_guard l(g_lock);
		for (auto& [id, tier] : g_watch) {
			auto* q = RE::TESForm::LookupByID<RE::TESQuest>(id);
			if (q && Running(q) && q->GetCurrentStageID() != 0 && !q->IsCompleted()) ++n;  // stage 0 is "posted on a board"
		}
		return n;
	}

	nlohmann::json Postings(const std::string& a_city)
	{
		auto out = nlohmann::json::array();
		const auto hold = HoldOf(a_city);
		if (!g_active || hold.empty()) return out;
		const int rank = Guild::Rank();
		auto* player = RE::PlayerCharacter::GetSingleton();
		const auto* area = SettlementOf(player ? player->GetCurrentLocation() : nullptr);
		std::vector<std::pair<RE::TESQuest*, char>> posted;
		{
			std::lock_guard l(g_lock);
			for (auto& [id, tier] : g_watch) {
				if (FromLetter(tier) > rank) continue;
				auto h = g_hold.find(id);
				if (h == g_hold.end() || h->second != hold) continue;
				auto* q = RE::TESForm::LookupByID<RE::TESQuest>(id);
				if (q && PostedHere(q, area)) posted.emplace_back(q, tier);
			}
		}
		std::sort(posted.begin(), posted.end(), [](auto& a, auto& b) { return a.second != b.second ? FromLetter(a.second) > FromLetter(b.second) : a.first->GetFormID() < b.first->GetFormID(); });
		for (auto& [q, tier] : posted) {
			out.push_back({ { "id", std::format("{:08X}", q->GetFormID()) }, { "tier", std::string(1, tier) }, { "title", PostingTitle(q) } });
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
		out["posted"] = Running(q) && q->GetCurrentStageID() == 0;

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
		if (!q || !Running(q) || q->GetCurrentStageID() != 0) return Loc::T("$AG_Missive_Gone", "That missive is no longer posted.");
		auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton();
		if (!vm) return "";
		const auto title = PostingTitle(q);
		RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> cb;
		vm->DispatchStaticCall("AG_QuestHelper", "AcceptMissive", RE::MakeFunctionArguments(static_cast<RE::TESQuest*>(q)), cb);
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
