// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "NoticeWatch.h"

#include "Counter.h"
#include "Guild.h"
#include "Loc.h"
#include "PrismaToast.h"
#include "QuestBoard.h"
#include "RankCore.h"

#include <fstream>
#include <mutex>
#include <unordered_map>

namespace AG::NoticeWatch
{
	void WithdrawAboveRank();

	namespace
	{
		struct Notice
		{
			char        tier{ 'E' };
			int         done{ -1 };       // the stage that completes the quest
			std::string noteAlias;        // the alias holding the note on the board ("" = this quest posts none)
			bool        gated{ false };   // the rank condition was put on it (only these are ever taken down)
		};

		std::mutex                             g_lock;
		std::unordered_map<RE::FormID, Notice> g_watch;  // quest -> what the Guild knows about it
		RE::FormID                             g_boardBase{ 0 };  // the Notice Board activator
		RE::FormID                             g_boardRef{ 0 };   // the one container every board opens
		RE::FormID                             g_questList{ 0 };  // the quests the boards start each time one loads
		bool                                   g_active{ false };

		std::uint32_t Hex(const nlohmann::json& a_v) { return static_cast<std::uint32_t>(std::stoul(a_v.get<std::string>(), nullptr, 16)); }

		// On the board now: running, not yet accepted, and its note is still in the board's container.
		bool Posted(RE::TESQuest* a_q, const Notice& a_n)
		{
			if (a_n.noteAlias.empty() || !QuestBoard::Running(a_q) || a_q->GetCurrentStageID() != 0) return false;
			auto* note = QuestBoard::AliasRef(a_q, a_n.noteAlias);
			auto* board = RE::TESForm::LookupByID<RE::TESObjectREFR>(g_boardRef);
			if (!note || !board || !note->GetBaseObject()) return false;
			auto counts = board->GetInventoryCounts();
			auto it = counts.find(note->GetBaseObject());
			return it != counts.end() && it->second > 0;
		}

		class Sink :
			public RE::BSTEventSink<RE::TESQuestStageEvent>,
			public RE::BSTEventSink<RE::TESActivateEvent>
		{
		public:
			static Sink* Get()
			{
				static Sink s;
				return &s;
			}

			RE::BSEventNotifyControl ProcessEvent(const RE::TESQuestStageEvent* a_event, RE::BSTEventSource<RE::TESQuestStageEvent>*) override
			{
				if (!a_event) return RE::BSEventNotifyControl::kContinue;
				Notice n;
				{
					std::lock_guard l(g_lock);
					auto it = g_watch.find(a_event->formID);
					if (it == g_watch.end()) return RE::BSEventNotifyControl::kContinue;
					n = it->second;
				}
				if (Counter::IsOpen()) Counter::Refresh();  // accepted, failed, done: the counter's list follows
				if (a_event->stage != n.done) return RE::BSEventNotifyControl::kContinue;
				std::string title = "Guild Notice";
				if (auto* q = RE::TESForm::LookupByID<RE::TESQuest>(a_event->formID)) title = QuestBoard::StripRank(q->GetFullName());
				PrismaToast::Show(Loc::T("$AG_Toast_Notice", "NOTICE COMPLETE"), Loc::T("$AG_Toast_MissiveSub", "Submit your report at any guild counter"));
				Guild::OnNoticeCompleted(FromLetter(n.tier), title);
				SKSE::log::info("NoticeWatch: quest complete (rank {})", n.tier);
				return RE::BSEventNotifyControl::kContinue;
			}

			// The player uses a Notice Board: an unregistered player is pointed to the Guild, as at a Missives board.
			RE::BSEventNotifyControl ProcessEvent(const RE::TESActivateEvent* a_event, RE::BSTEventSource<RE::TESActivateEvent>*) override
			{
				if (!a_event || !g_boardBase || !a_event->objectActivated || !a_event->actionRef || !a_event->actionRef->IsPlayerRef())
					return RE::BSEventNotifyControl::kContinue;
				auto* base = a_event->objectActivated->GetBaseObject();
					if (base && base->GetFormID() == g_boardBase)
						SKSE::GetTaskInterface()->AddTask([] {
						WithdrawAboveRank();
						Guild::OnBoardApproached();
					});
				return RE::BSEventNotifyControl::kContinue;
			}
		};

		// Papyrus has finished starting the quests: the counter, if it is open, lists what went up.
		class Posted_ : public RE::BSScript::IStackCallbackFunctor
		{
		public:
			void operator()(RE::BSScript::Variable) override
			{
				if (Counter::IsOpen()) Counter::Refresh();
			}
			bool CanSave() const override { return false; }
			void SetObject(const RE::BSTSmartPointer<RE::BSScript::Object>&) override {}
		};

		RE::TESQuest* Find(const std::string& a_formIdHex, Notice& a_out)
		{
			try {
				const auto id = static_cast<RE::FormID>(std::stoul(a_formIdHex, nullptr, 16));
				std::lock_guard l(g_lock);
				if (auto it = g_watch.find(id); it != g_watch.end()) {
					a_out = it->second;
					return RE::TESForm::LookupByID<RE::TESQuest>(id);
				}
			} catch (...) {}
			return nullptr;
		}
	}

	bool Active() { return g_active; }

	void Register()
	{
		auto* dh = RE::TESDataHandler::GetSingleton();
		std::ifstream f("Data/SKSE/Plugins/AdventurersGuild/notices.json");
		if (!dh || !f) {
			if (dh) SKSE::log::error("NoticeWatch: SKSE/Plugins/AdventurersGuild/notices.json missing - Notice Board features inactive");
			return;
		}
		try {
			auto       j = nlohmann::json::parse(f, nullptr, true, true);
			const auto plugin = j.value("plugin", std::string("notice board.esp"));
			if (!dh->LookupLoadedModByName(plugin)) {
				SKSE::log::info("NoticeWatch: {} not loaded - watch inactive", plugin);
				return;
			}
			auto* rankGlobal = dh->LookupForm<RE::TESGlobal>(Hex(j.at("rankGlobal")), "AdventurersGuild.esp");
			if (auto* act = dh->LookupForm(Hex(j.at("boardActivator")), plugin)) g_boardBase = act->GetFormID();
			if (auto* ref = dh->LookupForm(Hex(j.at("boardContainerRef")), plugin)) g_boardRef = ref->GetFormID();
			if (j.contains("questList"))
				if (auto* list = dh->LookupForm<RE::BGSListForm>(Hex(j.at("questList")), plugin)) g_questList = list->GetFormID();
			int resolved = 0, missing = 0, gated = 0, open = 0, labeled = 0;
			std::lock_guard l(g_lock);
			for (auto& e : j.value("quests", nlohmann::json::array())) {
				auto*      quest = dh->LookupForm<RE::TESQuest>(Hex(e.at("formId")), plugin);
				const auto tier = e.value("rank", std::string());
				if (!quest || tier.empty()) { ++missing; continue; }
				++resolved;
				auto& entry = g_watch[quest->GetFormID()] = { tier[0], e.value("done", -1), e.value("noteAlias", std::string()) };
				QuestBoard::Label(quest, tier[0]);
				if (e.contains("note"))
					if (auto* book = dh->LookupForm<RE::TESObjectBOOK>(Hex(e.at("note")), plugin)) { QuestBoard::Label(book, tier[0]); ++labeled; }
				// gate only what the boards start themselves and what has somewhere to put the condition (see the header)
				auto* alias = e.value("gate", false) && rankGlobal ? QuestBoard::GateAlias(quest) : nullptr;
				if (alias) {
					QuestBoard::Gate(alias->conditions, rankGlobal, FromLetter(tier[0]));
					entry.gated = true;
					++gated;
				} else {
					++open;
				}
			}
			if (!rankGlobal) SKSE::log::error("NoticeWatch: AG_PlayerRankGlobal not found - notices are NOT rank-gated");
			SKSE::log::info("NoticeWatch: {} quests resolved, {} missing; {} rank-gated, {} open to every rank, {} notes labeled; board {:08X}, container {:08X}",
				resolved, missing, gated, open, labeled, g_boardBase, g_boardRef);
			if (!resolved) return;
		} catch (const std::exception& e) {
			SKSE::log::error("NoticeWatch: notices.json error: {}", e.what());
			return;
		}
		RE::ScriptEventSourceHolder::GetSingleton()->AddEventSink<RE::TESQuestStageEvent>(Sink::Get());
		RE::ScriptEventSourceHolder::GetSingleton()->AddEventSink<RE::TESActivateEvent>(Sink::Get());
		g_active = true;
		SKSE::log::info("NoticeWatch: registered");
	}

	// Notices that went up before the gate applied (a save from before Adventurers Guild, or before registering): a
	// gated notice above the player's rank that is still ON the board - posted, never taken - comes down, and the
	// gate keeps it from going back up. Anything the player took stays theirs; ungated quests are never touched.
	void WithdrawAboveRank()
	{
		if (!g_active) return;
		const int rank = Guild::Rank();  // -1 before registering: every gated notice is above it
		std::vector<std::pair<RE::TESQuest*, std::string>> stale;
		{
			std::lock_guard l(g_lock);
			for (auto& [id, n] : g_watch) {
				if (!n.gated || FromLetter(n.tier) <= rank) continue;
				auto* q = RE::TESForm::LookupByID<RE::TESQuest>(id);
				if (q && Posted(q, n)) stale.emplace_back(q, n.noteAlias);
			}
		}
		auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton();
		auto* board = RE::TESForm::LookupByID<RE::TESObjectREFR>(g_boardRef);
		if (!vm || !board) return;
		for (auto& [q, alias] : stale) {
			RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> cb;
			vm->DispatchStaticCall("AG_QuestHelper", "WithdrawNotice",
				RE::MakeFunctionArguments(static_cast<RE::TESQuest*>(q), RE::BSFixedString(alias), static_cast<RE::TESObjectREFR*>(board)), cb);
		}
		if (!stale.empty()) SKSE::log::info("NoticeWatch: took down {} posted notice(s) above guild rank {}", stale.size(), rank);
	}

	// A board only starts its quests when its cell loads, so after a promotion nothing new is posted until the player
	// next walks up to one - and the counter, which lists what is posted, showed nothing new either. The counter is a
	// board too: opening it does what a board does on loading (start every quest of the mod's list that is not
	// running; the rank condition decides which go up), then the list is refreshed.
	void Post()
	{
		if (!g_active || !g_questList || !Guild::Registered()) return;
		auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton();
		auto* list = RE::TESForm::LookupByID<RE::BGSListForm>(g_questList);
		if (!vm || !list) return;
		RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> cb(new Posted_());
		vm->DispatchStaticCall("AG_QuestHelper", "PostNotices", RE::MakeFunctionArguments(static_cast<RE::BGSListForm*>(list)), cb);
	}

	nlohmann::json Postings()
	{
		auto out = nlohmann::json::array();
		if (!g_active) return out;
		std::vector<std::tuple<RE::TESQuest*, char, std::string>> posted;
		{
			std::lock_guard l(g_lock);
			for (auto& [id, n] : g_watch) {
				auto* q = RE::TESForm::LookupByID<RE::TESQuest>(id);
				if (q && Posted(q, n)) posted.emplace_back(q, n.tier, n.noteAlias);
			}
		}
		std::sort(posted.begin(), posted.end(), [](auto& a, auto& b) {
			return std::get<1>(a) != std::get<1>(b) ? FromLetter(std::get<1>(a)) > FromLetter(std::get<1>(b)) : std::get<0>(a)->GetFormID() < std::get<0>(b)->GetFormID();
		});
		for (auto& [q, tier, alias] : posted)
			out.push_back({ { "id", std::format("{:08X}", q->GetFormID()) }, { "tier", std::string(1, tier) }, { "title", QuestBoard::NoteTitle(q, alias) } });
		return out;
	}

	bool Owns(const std::string& a_formIdHex)
	{
		Notice n;
		return Find(a_formIdHex, n) != nullptr;
	}

	nlohmann::json Details(const std::string& a_formIdHex)
	{
		nlohmann::json out{ { "id", a_formIdHex }, { "kind", "notice" } };
		Notice         n;
		auto*          q = Find(a_formIdHex, n);
		if (!q) return out;
		out["tier"] = std::string(1, n.tier);
		out["title"] = QuestBoard::NoteTitle(q, n.noteAlias);
		out["posted"] = Posted(q, n);
		out["text"] = QuestBoard::NoteText(q, n.noteAlias);
		return out;
	}

	std::string Accept(const std::string& a_formIdHex)
	{
		Notice n;
		auto*  q = Find(a_formIdHex, n);
		if (!q || !Posted(q, n)) return Loc::T("$AG_Notice_Gone", "That notice is no longer posted.");
		auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton();
		if (!vm) return "";
		const auto title = QuestBoard::NoteTitle(q, n.noteAlias);
		RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> cb;
		vm->DispatchStaticCall("AG_QuestHelper", "AcceptNotice",
			RE::MakeFunctionArguments(static_cast<RE::TESQuest*>(q), RE::BSFixedString(n.noteAlias), RE::TESForm::LookupByID<RE::TESObjectREFR>(g_boardRef)), cb);
		SKSE::log::info("NoticeWatch: accepted {:08X} ({}) from the counter", q->GetFormID(), title);
		return Loc::F("$AG_Notice_Taken", "Notice taken: {}", title);
	}
}
