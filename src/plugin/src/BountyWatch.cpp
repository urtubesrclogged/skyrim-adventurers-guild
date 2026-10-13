// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "BountyWatch.h"

#include "Counter.h"
#include "Dungeons.h"
#include "Guild.h"
#include "Loc.h"
#include "PrismaToast.h"
#include "QuestBoard.h"
#include "RankCore.h"

#include <mutex>
#include <unordered_map>

namespace AG::BountyWatch
{
	namespace
	{
		constexpr int kTaken = 10, kSlain = 100, kCollected = 200;

		std::mutex              g_lock;
		std::vector<RE::FormID> g_quests;  // the bounty quests, found by their aliases
		// The rank of a bounty, kept from when it was first worked out: by the time the hold pays, its target is dead and
		// may be gone. Keyed by quest and by which run of the quest this is, so a reload to another bounty is another key.
		std::unordered_map<std::uint64_t, int> g_rank;

		bool Has(RE::TESQuest* a_q, std::initializer_list<std::string_view> a_names)
		{
			for (const auto n : a_names)
				if (!QuestBoard::AliasNamed(a_q, n)) return false;
			return true;
		}

		bool Mine(RE::FormID a_id)
		{
			std::lock_guard l(g_lock);
			return std::find(g_quests.begin(), g_quests.end(), a_id) != g_quests.end();
		}

		const RE::BGSQuestInstanceText* Instance(RE::TESQuest* a_q)
		{
			for (auto* it : a_q->instanceData)
				if (it && it->id == a_q->currentInstanceID) return it;
			return nullptr;
		}

		// A location alias has no reference to ask; the form whose name fills its <Alias=...> is the location itself.
		RE::BGSLocation* LocationOf(RE::TESQuest* a_q, std::string_view a_alias)
		{
			auto* alias = QuestBoard::AliasNamed(a_q, a_alias);
			auto* inst = Instance(a_q);
			if (!alias || !inst) return nullptr;
			for (auto& sd : inst->stringData)
				if (sd.aliasID == alias->aliasID)
					if (auto* loc = RE::TESForm::LookupByID<RE::BGSLocation>(sd.fullNameFormID)) return loc;
			return nullptr;
		}

		// The counter city of the hold the bounty is for. The hold alias itself when it can be read; otherwise from where
		// the people of the bounty belong (the innkeeper who offers it, the Jarl, the steward): all of them are of the hold.
		std::string CityOf(RE::TESQuest* a_q)
		{
			if (auto* hold = LocationOf(a_q, "Hold"))
				if (auto city = Dungeons::CityOf(hold); !city.empty()) return city;
			for (const auto who : { "Innkeeper", "Jarl", "Steward" }) {
				auto* ref = QuestBoard::AliasRef(a_q, who);
				if (!ref) continue;
				auto* loc = ref->GetEditorLocation();
				if (!loc) loc = ref->GetCurrentLocation();
				if (auto city = Dungeons::CityOf(loc); !city.empty()) return city;
			}
			return {};
		}

		// The rank: the target's threat rank, or the place's own (its encounter zone, as the Guild ranks any dungeon)
		// when that is higher. A target far away is not loaded and may not have its level yet; the place does.
		int Rank(RE::TESQuest* a_q)
		{
			const auto key = (static_cast<std::uint64_t>(a_q->GetFormID()) << 32) | a_q->currentInstanceID;
			{
				std::lock_guard l(g_lock);
				if (auto it = g_rank.find(key); it != g_rank.end()) return it->second;
			}
			int   rank = -1;
			auto* ref = QuestBoard::AliasRef(a_q, "Bounty");
			auto* target = ref ? ref->As<RE::Actor>() : nullptr;
			if (target) rank = ThreatRank(target);
			rank = std::max(rank, Dungeons::RankOf(LocationOf(a_q, "BountyLocation")));
			if (rank < 0) return 0;  // nothing to go on: not remembered, so it is worked out again when there is
			rank = std::min(rank, kRankCount - 1);
			if (a_q->GetCurrentStageID() < kSlain && target && !target->IsDead()) {
				std::lock_guard l(g_lock);
				g_rank[key] = rank;
			}
			return rank;
		}

		// "Kill the bandit leader located at Halted Stream Camp": the quest's own first objective, in the player's
		// language and as whichever mod won it words it, with its place filled in.
		std::string Title(RE::TESQuest* a_q)
		{
			std::string text;
			for (auto* o : a_q->objectives)
				if (o && o->index == kTaken && o->displayText.c_str()) text = o->displayText.c_str();
			auto*       inst = Instance(a_q);
			std::string out;
			for (std::size_t i = 0; i < text.size();) {
				if (text[i] != '<') { out += text[i++]; continue; }
				const auto end = text.find('>', i);
				if (end == std::string::npos) return {};
				const auto tag = text.substr(i + 1, end - i - 1);
				const auto eq = tag.find('=');
				if (!tag.starts_with("Alias") || eq == std::string::npos) return {};
				const auto name = tag.substr(eq + 1);
				const auto filled = QuestBoard::AliasText(a_q, inst, name, tag.starts_with("Alias.BaseName"));
				if (filled.empty() || filled == name) return {};  // not filled in: no title is better than "<BountyLocation>"
				out += filled;
				i = end + 1;
			}
			return out;
		}

		std::string TitleOr(RE::TESQuest* a_q)
		{
			auto title = Title(a_q);
			return title.empty() ? Loc::T("$AG_Title_Bounty", "Jarl's Bounty") : title;
		}

		// who pays: the steward, or the Jarl where the hold has no steward
		std::string Payer(RE::TESQuest* a_q)
		{
			for (const auto who : { "Steward", "Jarl" })
				if (auto* ref = QuestBoard::AliasRef(a_q, who))
					if (const char* n = ref->GetDisplayFullName(); n && *n) return n;
			return {};
		}

		RE::TESQuest* Find(const std::string& a_formIdHex)
		{
			try {
				const auto id = static_cast<RE::FormID>(std::stoul(a_formIdHex, nullptr, 16));
				if (Mine(id)) return RE::TESForm::LookupByID<RE::TESQuest>(id);
			} catch (...) {}
			return nullptr;
		}

		bool OnOffer(RE::TESQuest* a_q) { return QuestBoard::Running(a_q) && a_q->GetCurrentStageID() < kTaken; }

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
				if (!a_event || !Mine(a_event->formID)) return RE::BSEventNotifyControl::kContinue;
				const auto id = a_event->formID;
				const int  stage = a_event->stage;
				auto*      q = RE::TESForm::LookupByID<RE::TESQuest>(id);
				if (!q) return RE::BSEventNotifyControl::kContinue;
				// Read now: the script of stage 200 stops the quest, and a stopped quest has no target and no place.
				const int  rank = Rank(q);
				const auto title = TitleOr(q);
				const auto key = (static_cast<std::uint64_t>(id) << 32) | q->currentInstanceID;
				SKSE::GetTaskInterface()->AddTask([id, stage, rank, title, key] {
					if (Counter::IsOpen()) Counter::Refresh();  // taken, slain, collected: the counter's tab follows
					if (stage == kCollected) {
						std::lock_guard l(g_lock);
						g_rank.erase(key);
					}
					if (!Guild::Registered() || Guild::Dormant()) return;  // the game's own quest: nothing of ours for a non-member
					if (stage == kTaken) {
						RE::SendHUDMessage::ShowHUDMessage(Loc::F("$AG_Hud_BountyTaken", "The Guild ranks this bounty {}.", Letter(rank)).c_str());
						SKSE::log::info("BountyWatch: {:08X} taken (rank {}): {}", id, Letter(rank), title);
					} else if (stage == kCollected) {
						PrismaToast::Show(Loc::T("$AG_Toast_Bounty", "BOUNTY COLLECTED"), Loc::T("$AG_Toast_MissiveSub", "Submit your report at any guild counter"));
						Guild::OnBountyCompleted(rank, title);
						SKSE::log::info("BountyWatch: {:08X} collected (rank {}): {}", id, Letter(rank), title);
					}
				});
				return RE::BSEventNotifyControl::kContinue;
			}
		};
	}

	void Register()
	{
		auto* dh = RE::TESDataHandler::GetSingleton();
		if (!dh) return;
		std::string found;
		{
			std::lock_guard l(g_lock);
			for (auto* q : dh->GetFormArray<RE::TESQuest>()) {
				if (!q || !Has(q, { "Bounty", "BountyLocation", "Letter", "Hold", "Jarl", "Steward", "Innkeeper" })) continue;
				g_quests.push_back(q->GetFormID());
				found += std::format("{}{:08X}", found.empty() ? "" : ", ", q->GetFormID());
			}
		}
		if (found.empty()) {
			SKSE::log::warn("BountyWatch: no bounty quest found (the game's own have aliases named Bounty, BountyLocation, Letter, Hold, Jarl, Steward and Innkeeper) - the Bounties tab stays empty");
			return;
		}
		RE::ScriptEventSourceHolder::GetSingleton()->AddEventSink<RE::TESQuestStageEvent>(Sink::Get());
		SKSE::log::info("BountyWatch: watching {}", found);
	}

	nlohmann::json Posting(const std::string& a_city)
	{
		if (a_city.empty()) return nullptr;
		std::vector<RE::FormID> quests;
		{
			std::lock_guard l(g_lock);
			quests = g_quests;
		}
		for (const auto id : quests) {
			auto* q = RE::TESForm::LookupByID<RE::TESQuest>(id);
			if (!q || !QuestBoard::Running(q)) continue;
			const int stage = q->GetCurrentStageID();
			if (stage >= kCollected || CityOf(q) != a_city) continue;
			return { { "id", std::format("{:08X}", id) }, { "tier", LetterStr(Rank(q)) }, { "title", TitleOr(q) },
				{ "state", stage < kTaken ? "offer" : stage < kSlain ? "taken" : "slain" }, { "payer", Payer(q) } };
		}
		return nullptr;
	}

	int InProgress()
	{
		std::vector<RE::FormID> quests;
		{
			std::lock_guard l(g_lock);
			quests = g_quests;
		}
		int n = 0;
		for (const auto id : quests) {
			auto* q = RE::TESForm::LookupByID<RE::TESQuest>(id);
			if (q && QuestBoard::Running(q) && q->GetCurrentStageID() >= kTaken && q->GetCurrentStageID() < kCollected) ++n;
		}
		return n;
	}

	bool Owns(const std::string& a_formIdHex) { return Find(a_formIdHex) != nullptr; }

	nlohmann::json Details(const std::string& a_formIdHex)
	{
		nlohmann::json out{ { "id", a_formIdHex }, { "kind", "bounty" } };
		auto*          q = Find(a_formIdHex);
		if (!q) return out;
		out["tier"] = LetterStr(Rank(q));
		out["title"] = TitleOr(q);
		out["posted"] = OnOffer(q);
		out["text"] = QuestBoard::NoteText(q, "Letter");
		return out;
	}

	std::string Accept(const std::string& a_formIdHex)
	{
		auto* q = Find(a_formIdHex);
		if (!q || !OnOffer(q)) return Loc::T("$AG_Bounty_Gone", "That bounty is no longer posted.");
		auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton();
		if (!vm) return "";
		const auto title = TitleOr(q);
		RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> cb;
		vm->DispatchStaticCall("AG_QuestHelper", "AcceptBounty", RE::MakeFunctionArguments(static_cast<RE::TESQuest*>(q)), cb);
		SKSE::log::info("BountyWatch: accepted {:08X} ({}) from the counter", q->GetFormID(), title);
		return Loc::F("$AG_Bounty_Taken", "Bounty taken: {}", title);
	}
}
