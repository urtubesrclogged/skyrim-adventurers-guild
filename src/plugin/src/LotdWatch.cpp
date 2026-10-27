// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "LotdWatch.h"

#include "Guild.h"
#include "Loc.h"
#include "PrismaToast.h"
#include "RankCore.h"

#include <fstream>
#include <nlohmann/json.hpp>
#include <unordered_map>

namespace AG::LotdWatch
{
	namespace
	{
		struct Watched
		{
			int rank{ 0 };
			int done{ 0 };
		};
		std::unordered_map<RE::FormID, Watched> g_quests;  // written once at data load, read-only after
		std::atomic<int>                        g_state{ 0 };

		class Sink : public RE::BSTEventSink<RE::TESQuestStageEvent>
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
				const auto it = g_quests.find(a_event->formID);
				if (it == g_quests.end() || a_event->stage != it->second.done) return RE::BSEventNotifyControl::kContinue;
				const int  rank = it->second.rank;
				const auto id = a_event->formID;
				std::string title;
				if (auto* q = RE::TESForm::LookupByID<RE::TESQuest>(id)) title = q->GetFullName();
				SKSE::GetTaskInterface()->AddTask([id, rank, title] {
					if (!Guild::Registered() || Guild::Dormant()) return;  // LotD's own quest: nothing of ours for a non-member
					PrismaToast::Show(Loc::T("$AG_Toast_Lotd", "MUSEUM WORK DONE"), Loc::T("$AG_Toast_MissiveSub", "Submit your report at any guild counter"), {},
						PrismaToast::Priority::kImportant, PrismaToast::Cue::kComplete);
					Guild::OnLotdCompleted(rank, title);
					SKSE::log::info("LotdWatch: {:08X} done (rank {}): {}", id, Letter(rank), title);
				});
				return RE::BSEventNotifyControl::kContinue;
			}
		};
	}

	void Register()
	{
		g_state = 0;
		auto* dh = RE::TESDataHandler::GetSingleton();
		std::ifstream f("Data/SKSE/Plugins/AdventurersGuild/lotd.json");
		if (!dh || !f) return;
		try {
			auto       j = nlohmann::json::parse(f, nullptr, true, true);
			const auto plugin = j.value("plugin", std::string());
			const auto* file = dh->LookupModByName(plugin);
			if (!file || file->GetCompileIndex() == 0xFF) return;
			g_state = 1;
			int missing = 0;
			for (auto& e : j.value("quests", nlohmann::json::array())) {
				const auto local = static_cast<RE::FormID>(std::stoul(e.value("formId", std::string("0")), nullptr, 16));
				auto*      form = dh->LookupForm(local, plugin);
				auto*      quest = form ? form->As<RE::TESQuest>() : nullptr;
				const auto rank = e.value("rank", std::string());
				if (!quest || rank.empty()) {
					++missing;
					SKSE::log::warn("LotdWatch: {} ({}) not found in {} - a different version of it?", e.value("name", ""), e.value("formId", ""), plugin);
					continue;
				}
				g_quests[quest->GetFormID()] = { FromLetter(rank[0]), e.value("done", 0) };
			}
			if (g_quests.empty()) return;
			RE::ScriptEventSourceHolder::GetSingleton()->AddEventSink<RE::TESQuestStageEvent>(Sink::Get());
			g_state = 2;
			SKSE::log::info("LotdWatch: {} - {} relic quests credited as Guild work, {} not found", plugin, g_quests.size(), missing);
		} catch (const std::exception& e) {
			SKSE::log::error("LotdWatch: lotd.json error: {}", e.what());
		}
	}

	int State() { return g_state.load(); }
}
