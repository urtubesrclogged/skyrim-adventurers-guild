// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "MemberCards.h"

#include "Adventurers.h"
#include "Diag.h"
#include "Dungeons.h"
#include "GuildCard.h"
#include "Loc.h"
#include "RankCore.h"

#include <algorithm>
#include <array>
#include <mutex>
#include <unordered_map>
#include <unordered_set>

namespace AG::MemberCards
{
	namespace
	{
		constexpr std::string_view kPlugin = "AdventurersGuild.esp";

		struct Record
		{
			std::string key;     // who it belongs to (Adventurers::StableKey of the reference)
			std::string name;    // as written on the card
			int         rank{ 0 };
			int         year{ 201 }, month{ 7 }, day{ 17 };  // registered (month 0..11)
			std::string seal;    // "" Skyrim's, "morrowind"
			std::vector<std::string> stamps;  // stamp file names, in order
			bool        retired{ false };
			int         number{ 0 };  // the Guild's ledger number, on the card for flavour
		};

		RE::TESObjectBOOK* g_personal = nullptr;
		RE::TESObjectBOOK* g_worn = nullptr;
		std::mutex         g_lock;
		std::unordered_map<std::string, Record> g_records;  // by item name, lower case
		std::unordered_set<std::string>         g_issued;   // keys of everyone who has been given a card of either kind

		std::string Lower(std::string a_s)
		{
			std::transform(a_s.begin(), a_s.end(), a_s.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
			return a_s;
		}

		// the same number for the same person in every session (std::hash is not promised to be)
		std::uint32_t Seed(const std::string& a_key)
		{
			std::uint32_t h = 2166136261u;
			for (unsigned char c : a_key) h = (h ^ c) * 16777619u;
			return h;
		}

		// "Hjalti [Bandit]" and "Hjalti\n[Bandit]" (how a names mod may show a renamed person) -> "Hjalti"
		std::string PersonalName(std::string a_shown)
		{
			if (const auto cut = a_shown.find_first_of("[\n"); cut != std::string::npos) a_shown.erase(cut);
			while (!a_shown.empty() && std::isspace(static_cast<unsigned char>(a_shown.back()))) a_shown.pop_back();
			return a_shown;
		}

		// Skyrim's calendar: Gregorian month lengths, no leap years
		constexpr std::array<int, 12> kMonthDays{ 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 };
		int Ordinal(int a_year, int a_month, int a_day)
		{
			int n = a_year * 365 + a_day;
			for (int m = 0; m < a_month && m < 12; ++m) n += kMonthDays[m];
			return n;
		}
		void FromOrdinal(int a_n, int& a_year, int& a_month, int& a_day)
		{
			a_year = (a_n - 1) / 365;
			int rest = a_n - a_year * 365;
			a_month = 0;
			while (a_month < 11 && rest > kMonthDays[a_month]) rest -= kMonthDays[a_month++];
			a_day = std::max(1, rest);
		}
		int TodayOrdinal()
		{
			auto* cal = RE::Calendar::GetSingleton();
			return cal ? Ordinal(static_cast<int>(cal->GetYear()), static_cast<int>(cal->GetMonth()), static_cast<int>(cal->GetDay())) : Ordinal(201, 7, 17);
		}

		bool OnSolstheim(RE::Actor* a_actor)
		{
			if (Dungeons::CityOf(a_actor->GetCurrentLocation()) == "Raven Rock") return true;
			auto* base = a_actor->GetActorBase();
			auto* file = base ? base->GetFile(0) : nullptr;
			return file && _stricmp(std::string(file->GetFilename()).c_str(), "Dragonborn.esm") == 0;
		}

		// When they registered. A named member's is written down (adventurers.json); one who joined during this
		// playthrough registered that day; for anyone else it follows from their rank, the same every time: the higher
		// the rank, the longer ago.
		void Registered(RE::Actor* a_actor, const std::string& a_key, int a_rank, Record& a_r)
		{
			if (Adventurers::NamedRegistered(a_actor, a_r.year, a_r.month, a_r.day)) return;
			const int today = TodayOrdinal();
			if (const float joined = Adventurers::RecruitedDay(a_key); joined >= 0.0f) {
				auto* cal = RE::Calendar::GetSingleton();
				const int ago = cal ? std::max(0, static_cast<int>(cal->GetDaysPassed() - joined)) : 0;
				FromOrdinal(today - ago, a_r.year, a_r.month, a_r.day);
				return;
			}
			static constexpr std::array<std::pair<int, int>, 6> kYears{ { { 0, 1 }, { 1, 3 }, { 2, 6 }, { 4, 10 }, { 8, 20 }, { 12, 25 } } };  // E..S: years ago, from-to
			const auto [from, to] = kYears[std::clamp(a_rank, 0, 5)];
			const auto seed = Seed(a_key);
			const int  days = from * 365 + static_cast<int>(seed % static_cast<std::uint32_t>((to - from) * 365)) + 20;  // never "today"
			FromOrdinal(today - days, a_r.year, a_r.month, a_r.day);
		}

		// Stamps on an NPC's card are decoration: there is no record of what they did. More at a higher rank, the hold
		// they were met in first, the rest picked by their seed.
		std::vector<std::string> Stamps(RE::Actor* a_actor, const std::string& a_key, int a_rank, bool a_solstheim)
		{
			static constexpr std::array<const char*, 9> kHolds{ "Whiterun", "Solitude", "Windhelm", "Riften", "Markarth", "Falkreath", "Morthal", "Dawnstar", "Winterhold" };
			auto seed = Seed(a_key) / 7u;
			static constexpr std::array<std::pair<int, int>, 6> kCount{ { { 0, 0 }, { 0, 1 }, { 1, 2 }, { 2, 4 }, { 3, 6 }, { 5, 8 } } };  // E..S: from-to
			const auto [lo, hi] = kCount[std::clamp(a_rank, 0, 5)];
			int want = lo + static_cast<int>(seed % static_cast<std::uint32_t>(hi - lo + 1));
			std::vector<std::string> cities;
			const auto add = [&](const std::string& a_city) {
				if (!a_city.empty() && std::find(cities.begin(), cities.end(), a_city) == cities.end()) cities.push_back(a_city);
			};
			if (want > 0) add(a_solstheim ? std::string("Raven Rock") : Dungeons::CityOf(a_actor->GetCurrentLocation()));
			for (int i = 0; static_cast<int>(cities.size()) < want && i < 40; ++i) {
				seed = seed * 1664525u + 1013904223u;
				add(kHolds[(seed >> 8) % kHolds.size()]);
			}
			std::vector<std::string> files;
			for (auto& c : cities) files.push_back(GuildCard::StampFile(c));
			return files;
		}

		// A member is given their card: the first time only, whatever became of it since.
		void Ensure(RE::Actor* a_actor)
		{
			if (!a_actor || a_actor->IsPlayerRef() || !g_personal || !g_worn) return;
			const auto info = Adventurers::Of(a_actor);
			if (info.kind == Adventurers::Kind::kNone) return;
			const auto key = Adventurers::StableKey(a_actor);
			{
				std::lock_guard l(g_lock);
				if (!g_issued.insert(key).second) return;
			}
			auto*       base = a_actor->GetActorBase();
			const char* shownRaw = a_actor->GetDisplayFullName();
			const char* baseRaw = base ? base->GetFullName() : nullptr;
			const auto  name = PersonalName(shownRaw ? shownRaw : "");
			const bool  personal = !name.empty() && ((base && base->IsUnique()) || _stricmp(name.c_str(), baseRaw ? baseRaw : "") != 0);
			if (!personal) {
				a_actor->AddObjectToContainer(g_worn, nullptr, 1, nullptr);
				SKSE::log::info("MemberCards: {} ({}) has no name of their own - a worn card", shownRaw ? shownRaw : "?", key);
				return;
			}
			Record r;
			r.key = key;
			r.name = name;
			r.rank = std::clamp(info.rank, 0, 5);
			r.retired = info.kind == Adventurers::Kind::kRetired;
			r.number = 1000 + static_cast<int>(Seed(key) % 9000u);
			const bool solstheim = OnSolstheim(a_actor);
			r.seal = solstheim ? "morrowind" : "";
			Registered(a_actor, key, r.rank, r);
			r.stamps = Stamps(a_actor, key, r.rank, solstheim);
			auto item = Loc::F("$AG_MemberCard_Name", "Guild Card: {}", name);
			{
				std::lock_guard l(g_lock);
				// two people with the same name: the later card says which, by its ledger number
				if (auto it = g_records.find(Lower(item)); it != g_records.end() && it->second.key != key)
					item = Loc::F("$AG_MemberCard_NameNo", "Guild Card: {} (No. {})", name, r.number);
				g_records[Lower(item)] = r;
			}
			// The copy is named as a renamed item is: its own display name, kept by the game with the item wherever it
			// goes. The game makes it (AG_QuestHelper.GiveMemberCard: a reference of the card, renamed, moved into their
			// inventory), a frame or two from now; AG_Native.MemberCardGiven then has an open inventory show it.
			if (auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton()) {
				RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> cb;
				vm->DispatchStaticCall("AG_QuestHelper", "GiveMemberCard",
					RE::MakeFunctionArguments(static_cast<RE::Actor*>(a_actor), static_cast<RE::TESForm*>(g_personal), RE::BSFixedString(item)), cb);
			}
			SKSE::log::info("MemberCards: \"{}\" made for {} - rank {}, registered {}/{}/4E {}, {} seal, {} stamp(s){}", item, key, Letter(r.rank), r.day,
				r.month + 1, r.year, solstheim ? "Morrowind" : "Skyrim", r.stamps.size(), r.retired ? ", retired" : "");
		}

		// The two moments someone looks: activating them (looting, picking a pocket), and their inventory opening by any
		// other road (a follower's, through dialogue).
		class Sinks : public RE::BSTEventSink<RE::TESActivateEvent>, public RE::BSTEventSink<RE::MenuOpenCloseEvent>
		{
		public:
			static Sinks* Get()
			{
				static Sinks s;
				return &s;
			}

			RE::BSEventNotifyControl ProcessEvent(const RE::TESActivateEvent* a_e, RE::BSTEventSource<RE::TESActivateEvent>*) override
			{
				if (!a_e || !a_e->objectActivated || !a_e->actionRef || !a_e->actionRef->IsPlayerRef()) return RE::BSEventNotifyControl::kContinue;
				auto* actor = a_e->objectActivated->As<RE::Actor>();
				if (!actor) return RE::BSEventNotifyControl::kContinue;
				const Diag::Timed timed("giving an adventurer their guild card as they are activated");
				Ensure(actor);
				return RE::BSEventNotifyControl::kContinue;
			}

			RE::BSEventNotifyControl ProcessEvent(const RE::MenuOpenCloseEvent* a_e, RE::BSTEventSource<RE::MenuOpenCloseEvent>*) override
			{
				if (!a_e || !a_e->opening || a_e->menuName != RE::ContainerMenu::MENU_NAME) return RE::BSEventNotifyControl::kContinue;
				SKSE::GetTaskInterface()->AddTask([] {
					RE::NiPointer<RE::TESObjectREFR> target;
					if (!RE::LookupReferenceByHandle(RE::ContainerMenu::GetTargetRefHandle(), target) || !target) return;
					auto* actor = target->As<RE::Actor>();
					if (!actor) return;
					bool had;
					{
						std::lock_guard l(g_lock);
						had = g_issued.contains(Adventurers::StableKey(actor));
					}
					Ensure(actor);
					if (!had) RE::SendUIMessage::SendInventoryUpdateMessage(actor, nullptr);  // the list was built before the card was there
				});
				return RE::BSEventNotifyControl::kContinue;
			}
		};

		template <class Menu>
		std::string SelectedIn()
		{
			auto* ui = RE::UI::GetSingleton();
			auto  menu = ui ? ui->GetMenu<Menu>() : nullptr;
			auto* list = menu ? menu->GetRuntimeData().itemList : nullptr;
			auto* item = list ? list->GetSelectedItem() : nullptr;
			auto* entry = item ? item->data.objDesc : nullptr;
			const char* name = entry ? entry->GetDisplayName() : nullptr;
			return name ? name : "";
		}
	}

	void Install()
	{
		auto* dh = RE::TESDataHandler::GetSingleton();
		g_personal = dh ? dh->LookupForm<RE::TESObjectBOOK>(0xCF7, kPlugin) : nullptr;
		g_worn = dh ? dh->LookupForm<RE::TESObjectBOOK>(0xCF8, kPlugin) : nullptr;
		if (!g_personal || !g_worn) {
			SKSE::log::warn("MemberCards: the two card items are not in {} - other adventurers carry no card", kPlugin);
			return;
		}
		if (auto* src = RE::ScriptEventSourceHolder::GetSingleton()) src->AddEventSink<RE::TESActivateEvent>(Sinks::Get());
		if (auto* ui = RE::UI::GetSingleton()) ui->AddEventSink<RE::MenuOpenCloseEvent>(Sinks::Get());
		SKSE::log::info("MemberCards: an adventurer is given their card the first time the player looks");
	}

	bool IsPersonal(const RE::TESForm* a_form) { return a_form && a_form == g_personal; }

	void Given(RE::Actor* a_owner)
	{
		if (!a_owner) return;
		const auto handle = a_owner->GetHandle();
		SKSE::GetTaskInterface()->AddTask([handle] {
			if (auto ref = handle.get()) RE::SendUIMessage::SendInventoryUpdateMessage(ref.get(), nullptr);
		});
	}

	std::string SelectedItemName()
	{
		for (auto name : { SelectedIn<RE::InventoryMenu>(), SelectedIn<RE::ContainerMenu>(), SelectedIn<RE::BarterMenu>() })
			if (!name.empty()) return name;
		return {};
	}

	nlohmann::json CardFor(const std::string& a_itemName)
	{
		Record r;
		{
			std::lock_guard l(g_lock);
			const auto it = g_records.find(Lower(a_itemName));
			if (it == g_records.end()) return nullptr;
			r = it->second;
		}
		// the rank is the one they show now, while they can be found; otherwise the one last seen
		if (auto* form = Adventurers::FormOfKey(r.key))
			if (auto* actor = form->As<RE::Actor>(); actor && actor->Is3DLoaded()) {
				const auto info = Adventurers::Of(actor);
				if (info.kind != Adventurers::Kind::kNone && info.rank >= 0) {
					r.rank = std::clamp(info.rank, 0, 5);
					r.retired = info.kind == Adventurers::Kind::kRetired;
					std::lock_guard l(g_lock);
					if (auto it = g_records.find(Lower(a_itemName)); it != g_records.end()) {
						it->second.rank = r.rank;
						it->second.retired = r.retired;
					}
				}
			}
		return { { "name", r.name }, { "letter", LetterStr(r.rank) }, { "date", { { "year", r.year }, { "month", r.month }, { "day", r.day } } },
			{ "seal", r.seal }, { "stamps", r.stamps }, { "retired", r.retired }, { "number", r.number } };
	}

	nlohmann::json Save()
	{
		std::lock_guard l(g_lock);
		auto cards = nlohmann::json::object();
		for (auto& [item, r] : g_records)
			cards[item] = { { "key", r.key }, { "name", r.name }, { "rank", r.rank }, { "y", r.year }, { "m", r.month }, { "d", r.day }, { "seal", r.seal },
				{ "stamps", r.stamps }, { "retired", r.retired }, { "no", r.number } };
		return { { "cards", cards }, { "issued", std::vector<std::string>(g_issued.begin(), g_issued.end()) } };
	}

	void Load(const nlohmann::json& a_j)
	{
		std::lock_guard l(g_lock);
		g_records.clear();
		g_issued.clear();
		try {
			for (auto& [item, c] : a_j.value("cards", nlohmann::json::object()).items()) {
				Record r;
				r.key = c.value("key", "");
				r.name = c.value("name", "");
				r.rank = c.value("rank", 0);
				r.year = c.value("y", 201);
				r.month = c.value("m", 7);
				r.day = c.value("d", 17);
				r.seal = c.value("seal", "");
				r.stamps = c.value("stamps", std::vector<std::string>{});
				r.retired = c.value("retired", false);
				r.number = c.value("no", 0);
				g_records[item] = std::move(r);
			}
			for (auto& k : a_j.value("issued", nlohmann::json::array())) g_issued.insert(k.get<std::string>());
		} catch (const std::exception& e) {
			SKSE::log::error("MemberCards: co-save parse error: {}", e.what());
		}
	}

	void Revert()
	{
		std::lock_guard l(g_lock);
		g_records.clear();
		g_issued.clear();
	}

	std::string Debug()
	{
		std::lock_guard l(g_lock);
		std::string out = std::format("{} personal card(s), {} adventurer(s) given a card of either kind", g_records.size(), g_issued.size());
		int n = 0;
		for (auto& [item, r] : g_records) {
			if (++n > 12) break;
			out += std::format("\n  \"{}\": {} rank {} {}/{}/{} {}", item, r.key, Letter(r.rank), r.day, r.month + 1, r.year, r.retired ? "retired" : "");
		}
		return out;
	}
}
