// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "MemberCards.h"

#include "Counter.h"

#include "Adventurers.h"
#include "Diag.h"
#include "Dungeons.h"
#include "GuildCard.h"
#include "Guild.h"
#include "Loc.h"
#include "Party.h"
#include "RankCore.h"

#include <algorithm>
#include <array>
#include <fstream>
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
			std::string city;         // the counter that issued it: their hold's (where they were first met)
			int         level{ 1 };   // as last seen (their rank follows from it, and so do the figures below)
			std::string item;         // the copy's name, as written (the look-up key is this in lower case)
			bool        dead{ false };          // seen dead (kept: a body is cleaned away, and its owner can no longer be asked)
			float       missingSince{ -1.0f };  // the game day the player was first seen carrying it; -1 while nothing is counted
		};

		RE::TESObjectBOOK* g_personal = nullptr;
		RE::TESObjectBOOK* g_personalMw = nullptr;  // the same card with Morrowind's wax (a member of Solstheim): an item of its own for its mesh
		RE::TESObjectBOOK* g_bloody = nullptr;      // a dead adventurer's card, bloodied (and its Morrowind twin): items of their own for their meshes
		RE::TESObjectBOOK* g_bloodyMw = nullptr;
		bool Card(const RE::TESForm* a_form)
		{
			return a_form && (a_form == g_personal || (g_personalMw && a_form == g_personalMw) || (g_bloody && a_form == g_bloody) || (g_bloodyMw && a_form == g_bloodyMw));
		}
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

		// Until 2026-10-12 a member's card was named "Guild Card: <name>"; it is "Adventurers Guild Card (NPC) - <name>"
		// now, so the three kinds of card sit together in an inventory. A copy made before that keeps the old name until
		// it is seen (Rename), and is found under either.
		constexpr std::string_view kOldPrefix = "Guild Card: ";
		bool Old(const std::string& a_item)
		{
			return a_item.size() > kOldPrefix.size() && _strnicmp(a_item.c_str(), kOldPrefix.data(), kOldPrefix.size()) == 0;
		}
		std::string Renamed(const std::string& a_item)
		{
			return Old(a_item) ? Loc::F("$AG_MemberCard_Name", "Adventurers Guild Card (NPC) - {}", a_item.substr(kOldPrefix.size())) : a_item;
		}
		std::string Key(const std::string& a_item) { return Lower(Renamed(a_item)); }

		// the copies someone holds that still carry the old name are given the new one
		void Rename(RE::TESObjectREFR* a_holder)
		{
			if (!a_holder || !g_personal) return;
			for (auto& [object, data] : a_holder->GetInventory([](RE::TESBoundObject& a_o) { return Card(&a_o); })) {
				auto& entry = data.second;
				if (!entry || !entry->extraLists) continue;
				for (auto* xl : *entry->extraLists) {
					auto* text = xl ? xl->GetByType<RE::ExtraTextDisplayData>() : nullptr;
					const char* shown = xl ? xl->GetDisplayName(object) : nullptr;
					if (!text || !shown || !Old(shown)) continue;
					const auto now = Renamed(shown);
					SKSE::log::info("MemberCards: \"{}\" is now \"{}\"", shown, now);
					text->SetName(now.c_str());
				}
			}
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


		// ---- bringing cards back ----
		RE::TESGlobal*  g_gCarried = nullptr;      // AG_CardsCarriedGlobal: cards the player carries that can be brought back
		RE::TESTopic*   g_handInTopic = nullptr;   // AG_TopicCardHandIn: the player's line, worded for one card or several
		RE::TESFaction* g_checked = nullptr;       // AG_CardCheckedFaction: a dead body that has been asked for a lost card
		RE::TESGlobal*  g_gCase = nullptr;         // AG_CardCaseGlobal: the weightiest of them (1 alive, 2 dead, 3 fallen party member, 4 worn only)
		RE::TESBoundObject* g_mead = nullptr;
		RE::TESBoundObject* g_sujamma = nullptr;
		std::unordered_set<RE::FormID>  g_noDrinks;  // representatives (by base) who stand nobody a round

		// one stack of cards in the player's inventory
		struct Carried
		{
			RE::TESBoundObject* object{ nullptr };
			RE::ExtraDataList*  extra{ nullptr };  // the stack's own data (its name, its owner); null for plain worn cards
			int                 count{ 1 };
			bool                worn{ false };     // a worn card, or a named one this save has no record of: nobody's
			bool                stolen{ false };   // the game holds it to be someone else's property
			std::string         item, key, name;   // the copy's name; whose it is; the name on it
		};

		std::vector<Carried> Scan()
		{
			std::vector<Carried> out;
			auto* pc = RE::PlayerCharacter::GetSingleton();
			if (!pc || !g_personal || !g_worn) return out;
			auto* self = pc->GetActorBase();
			Rename(pc);
			auto  inv = pc->GetInventory([](RE::TESBoundObject& a_o) { return Card(&a_o) || &a_o == g_worn; });
			for (auto& [object, data] : inv) {
				auto& [count, entry] = data;
				if (count <= 0 || !entry) continue;
				int listed = 0;
				if (entry->extraLists)
					for (auto* xl : *entry->extraLists) {
						if (!xl) continue;
						Carried c;
						c.object = object;
						c.extra = xl;
						c.count = std::max(1, static_cast<int>(xl->GetCount()));
						c.worn = object == g_worn;
						auto* owner = xl->GetOwner();
						c.stolen = owner && owner != self && owner != pc;
						if (!c.worn) {
							const char* shown = xl->GetDisplayName(object);
							c.item = shown ? shown : "";
						}
						listed += c.count;
						out.push_back(std::move(c));
					}
				if (count > listed) {
					Carried c;
					c.object = object;
					c.count = count - listed;
					c.worn = true;
					out.push_back(std::move(c));
				}
			}
			std::lock_guard l(g_lock);
			for (auto& c : out) {
				if (c.worn) continue;
				if (const auto it = g_records.find(Key(c.item)); it != g_records.end()) {
					c.key = it->second.key;
					c.name = it->second.name;
				} else {
					c.worn = true;
				}
			}
			return out;
		}

		enum class Fate { kAlive, kDead, kFallen };

		// What became of a card's owner. Someone who cannot be found any more is taken to be alive, unless they were
		// seen dead while they could be.
		Fate FateOf(const Carried& a_card, RE::Actor*& a_owner)
		{
			a_owner = nullptr;
			if (auto* form = Adventurers::FormOfKey(a_card.key)) a_owner = form->As<RE::Actor>();
			if (Party::IsFallen(a_card.key)) return Fate::kFallen;
			const bool deadNow = a_owner && a_owner->IsDead();
			std::lock_guard l(g_lock);
			const auto it = g_records.find(Key(a_card.item));
			if (it == g_records.end()) return deadNow ? Fate::kDead : Fate::kAlive;
			if (deadNow) it->second.dead = true;
			return it->second.dead ? Fate::kDead : Fate::kAlive;
		}

		bool HasCard(RE::Actor* a_actor)
		{
			for (auto& [object, data] : a_actor->GetInventory([](RE::TESBoundObject& a_o) { return Card(&a_o); }))
				if (data.first > 0) return true;
			return false;
		}

		// The named copy is made by the game (AG_QuestHelper.GiveMemberCard), a frame or two from now.
		void Give(RE::Actor* a_actor, const std::string& a_item, bool a_bloody = false)
		{
			// which item: the one whose wax is on their card, bloodied if its owner is dead
			RE::TESObjectBOOK* form = g_personal;
			{
				std::lock_guard l(g_lock);
				const bool mw = [&] { const auto it = g_records.find(Key(a_item)); return it != g_records.end() && it->second.seal == "morrowind"; }();
				if (a_bloody && g_bloody) form = mw && g_bloodyMw ? g_bloodyMw : g_bloody;
				else if (mw && g_personalMw) form = g_personalMw;
			}
			if (auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton()) {
				RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> cb;
				vm->DispatchStaticCall("AG_QuestHelper", "GiveMemberCard",
					RE::MakeFunctionArguments(static_cast<RE::Actor*>(a_actor), static_cast<RE::TESForm*>(form), RE::BSFixedString(a_item)), cb);
			}
		}

		// Their blood is on the card of someone who is dead: seen dead, fell in the player's party, or lying dead now. The ONE
		// test, for the card page (CardFor) and for the object (Bloody) alike: the object followed only the first of the
		// three and stayed clean on Uthgerd's body while her page showed blood (Librum, 2026-10-14).
		bool OwnerDead(const Record& a_r)
		{
			if (a_r.dead || Party::IsFallen(a_r.key)) return true;
			auto* form = Adventurers::FormOfKey(a_r.key);
			auto* actor = form ? form->As<RE::Actor>() : nullptr;
			return actor && actor->IsDead();
		}

		// A dead adventurer's card looks it (1.5.0): a clean copy whose owner the Guild knows to be dead is taken out of the
		// holder's inventory and the bloodied one, with the same name, put in its place. The player's (on every sync) and a
		// body's (when the crosshair finds it). On the game's thread.
		void Bloody(RE::Actor* a_holder)
		{
			if (!a_holder || !g_bloody) return;
			std::vector<std::pair<RE::TESBoundObject*, RE::ExtraDataList*>> swap;
			std::vector<std::string>                                        names;
			for (auto& [object, data] : a_holder->GetInventory([](RE::TESBoundObject& a_o) { return &a_o == g_personal || (g_personalMw && &a_o == g_personalMw); })) {
				auto& entry = data.second;
				if (data.first <= 0 || !entry || !entry->extraLists) continue;
				for (auto* xl : *entry->extraLists) {
					const char* shown = xl ? xl->GetDisplayName(object) : nullptr;
					if (!shown || !*shown) continue;
					Record r;
					{
						std::lock_guard l(g_lock);
						const auto it = g_records.find(Key(shown));
						if (it == g_records.end()) continue;
						r = it->second;
					}
					if (OwnerDead(r)) {
						swap.emplace_back(object, xl);
						names.emplace_back(shown);
					}
				}
			}
			for (std::size_t i = 0; i < swap.size(); ++i) {
				a_holder->RemoveItem(swap[i].first, 1, RE::ITEM_REMOVE_REASON::kRemove, swap[i].second, nullptr);
				Give(a_holder, names[i], true);
				SKSE::log::info("MemberCards: \"{}\" is bloodied ({} holds it; its owner is dead)", names[i], a_holder->GetDisplayFullName());
			}
		}

		void SetMissing(const std::string& a_item, float a_since)
		{
			std::lock_guard l(g_lock);
			if (const auto it = g_records.find(Key(a_item)); it != g_records.end()) it->second.missingSince = a_since;
		}

		// A living member whose card is gone has a new one from the Guild after a few days, as the player can buy one.
		// The days are counted from when the player was first seen carrying it (a_start), and go on counting whatever
		// the player does with it after that.
		void Replace(RE::Actor* a_owner, const std::string& a_item, bool a_start)
		{
			if (!a_owner || a_owner->IsDead()) return;
			float since;
			{
				std::lock_guard l(g_lock);
				const auto it = g_records.find(Key(a_item));
				if (it == g_records.end()) return;
				since = it->second.missingSince;
			}
			if (since < 0.0f && !a_start) return;
			if (HasCard(a_owner)) {
				if (since >= 0.0f) SetMissing(a_item, -1.0f);
				return;
			}
			const float now = Guild::Day();
			if (since < 0.0f) {
				SetMissing(a_item, now);
			} else if (now - since >= Guild::CardReplaceDays() && a_owner->Is3DLoaded()) {
				SetMissing(a_item, -1.0f);
				Give(a_owner, a_item);
				SKSE::log::info("MemberCards: \"{}\" was gone {:.1f} days - its owner has a replacement", a_item, now - since);
			}
		}

		std::string ItemOfKey(const std::string& a_key)
		{
			std::lock_guard l(g_lock);
			for (auto& [item, r] : g_records)
				if (r.key == a_key) return r.item.empty() ? item : r.item;   // as it is written on the copy, not the look-up key
			return {};
		}

		// A lost card: someone found dead who was no member may still have one on them (adventurers.json "lostCards":
		// the bodies the game leaves in dungeons, a hunter, a bandit who robbed an adventurer). Asked once per body. The
		// answer is kept by the game, not by this mod: the body joins AG_CardCheckedFaction, which is saved with it and
		// goes when the body does.
		void Lost(RE::Actor* a_actor)
		{
			if (!g_checked || !a_actor->IsDead() || a_actor->IsInFaction(g_checked) || !a_actor->HasKeywordString("ActorTypeNPC")) return;
			a_actor->AddToFaction(g_checked, 0);
			std::string group;
			if (!Adventurers::HasLostCard(a_actor, &group)) return;
			a_actor->AddObjectToContainer(g_worn, nullptr, 1, nullptr);
			SKSE::log::info("MemberCards: a lost guild card on {} ({:08X}, '{}')", a_actor->GetDisplayFullName(), a_actor->GetFormID(), group);
		}

		// A member is given their card: the first time, and again once theirs has been gone for a few days.
		void Ensure(RE::Actor* a_actor)
		{
			if (!a_actor || a_actor->IsPlayerRef() || !g_personal || !g_worn) return;
			const auto info = Adventurers::Of(a_actor);
			if (info.kind == Adventurers::Kind::kNone) {
				Lost(a_actor);
				return;
			}
			const auto key = Adventurers::StableKey(a_actor);
			bool       issued = false;
			{
				std::lock_guard l(g_lock);
				if (!g_issued.insert(key).second) {
					issued = true;
				}
			}
			if (issued) {
				Rename(a_actor);
				if (const auto item = ItemOfKey(key); !item.empty()) Replace(a_actor, item, false);
				return;
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
			r.city = solstheim ? std::string("Raven Rock") : Dungeons::CityOf(a_actor->GetCurrentLocation());
			r.level = a_actor->GetLevel();
			r.dead = a_actor->IsDead();
			Registered(a_actor, key, r.rank, r);
			r.stamps = Stamps(a_actor, key, r.rank, solstheim);
			auto item = Loc::F("$AG_MemberCard_Name", "Adventurers Guild Card (NPC) - {}", name);
			{
				std::lock_guard l(g_lock);
				// two people with the same name: the later card says which, by its ledger number
				if (auto it = g_records.find(Key(item)); it != g_records.end() && it->second.key != key)
					item = Loc::F("$AG_MemberCard_NameNo", "Adventurers Guild Card (NPC) - {} (No. {})", name, r.number);
				r.item = item;
				g_records[Key(item)] = r;
			}
			// The copy is named as a renamed item is: its own display name, kept by the game with the item wherever it
			// goes. The game makes it (AG_QuestHelper.GiveMemberCard: a reference of the card, renamed, moved into their
			// inventory), a frame or two from now; AG_Native.MemberCardGiven then has an open inventory show it.
			Give(a_actor, item);
			SKSE::log::info("MemberCards: \"{}\" made for {} - rank {}, registered {}/{}/4E {}, {} seal, {} stamp(s){}", item, key, Letter(r.rank), r.day,
				r.month + 1, r.year, solstheim ? "Morrowind" : "Skyrim", r.stamps.size(), r.retired ? ", retired" : "");
		}

		// The moments someone looks: activating them (looting, picking a pocket), their inventory opening by any other
		// road (a follower's, through dialogue), and the crosshair resting on a body (a quick-loot mod lists what is on
		// it without opening anything).
		class Sinks : public RE::BSTEventSink<RE::TESActivateEvent>, public RE::BSTEventSink<RE::MenuOpenCloseEvent>, public RE::BSTEventSink<SKSE::CrosshairRefEvent>
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

			RE::BSEventNotifyControl ProcessEvent(const SKSE::CrosshairRefEvent* a_e, RE::BSTEventSource<SKSE::CrosshairRefEvent>*) override
			{
				auto* actor = a_e && a_e->crosshairRef ? a_e->crosshairRef->As<RE::Actor>() : nullptr;
				if (!actor || !actor->IsDead()) return RE::BSEventNotifyControl::kContinue;  // the living are asked when they are activated
				const auto handle = actor->GetHandle();
				SKSE::GetTaskInterface()->AddTask([handle] {
					auto ref = handle.get();
					if (auto* body = ref ? ref->As<RE::Actor>() : nullptr) {
						Ensure(body);
						Bloody(body);
					}
				});
				return RE::BSEventNotifyControl::kContinue;
			}

			RE::BSEventNotifyControl ProcessEvent(const RE::MenuOpenCloseEvent* a_e, RE::BSTEventSource<RE::MenuOpenCloseEvent>*) override
			{
				if (!a_e || a_e->menuName != RE::ContainerMenu::MENU_NAME) return RE::BSEventNotifyControl::kContinue;
				if (!a_e->opening) {
					SKSE::GetTaskInterface()->AddTask(Sync);  // a card may have changed hands: whoever is spoken to next knows at once
					return RE::BSEventNotifyControl::kContinue;
				}
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
		// (asked for by its kind, a drink is not found: "an object" is no kind of record the game can look up)
		const auto Drink = [](RE::TESForm* a_form) { return a_form ? a_form->As<RE::TESBoundObject>() : nullptr; };
		auto* dh = RE::TESDataHandler::GetSingleton();
		g_personal = dh ? dh->LookupForm<RE::TESObjectBOOK>(0xCF7, kPlugin) : nullptr;
		g_personalMw = dh ? dh->LookupForm<RE::TESObjectBOOK>(0xCFC, kPlugin) : nullptr;
		g_bloody = dh ? dh->LookupForm<RE::TESObjectBOOK>(0xC7C, kPlugin) : nullptr;
		g_bloodyMw = dh ? dh->LookupForm<RE::TESObjectBOOK>(0xC7D, kPlugin) : nullptr;
		g_worn = dh ? dh->LookupForm<RE::TESObjectBOOK>(0xCF8, kPlugin) : nullptr;
		if (!g_personal || !g_worn) {
			SKSE::log::warn("MemberCards: the two card items are not in {} - other adventurers carry no card", kPlugin);
			return;
		}
		g_gCarried = dh->LookupForm<RE::TESGlobal>(0xCF9, kPlugin);
		g_gCase = dh->LookupForm<RE::TESGlobal>(0xCFA, kPlugin);
		g_checked = dh->LookupForm<RE::TESFaction>(0xCFB, kPlugin);
		g_handInTopic = dh->LookupForm<RE::TESTopic>(0xCFF, kPlugin);
		g_mead = Drink(dh->LookupForm(0x034C5D, "Skyrim.esm"));       // Nord Mead
		g_sujamma = Drink(dh->LookupForm(0x0207E6, "Dragonborn.esm"));  // Sujamma, at Raven Rock
		g_noDrinks.clear();
		try {
			std::ifstream df("Data/SKSE/Plugins/AdventurersGuild/dialogue.resolved.json");
			const auto    dj = nlohmann::json::parse(df, nullptr, true, true);
			for (auto& k : dj.value("cardNoDrinks", nlohmann::json::array()))
				if (auto* form = Adventurers::FormOfKey(k.get<std::string>())) g_noDrinks.insert(form->GetFormID());
		} catch (const std::exception& e) {
			SKSE::log::warn("MemberCards: dialogue.resolved.json: {} - every representative stands a round for a fallen party member", e.what());
		}
		if (!g_gCarried || !g_gCase) SKSE::log::warn("MemberCards: the records for handing a card in are not in {} - cards cannot be handed in", kPlugin);
		if (auto* src = RE::ScriptEventSourceHolder::GetSingleton()) src->AddEventSink<RE::TESActivateEvent>(Sinks::Get());
		if (auto* ui = RE::UI::GetSingleton()) ui->AddEventSink<RE::MenuOpenCloseEvent>(Sinks::Get());
		if (auto* cross = SKSE::GetCrosshairRefEventSource()) cross->AddEventSink(Sinks::Get());
		SKSE::log::info("MemberCards: an adventurer is given their card the first time the player looks");
	}

	bool IsPersonal(const RE::TESForm* a_form) { return Card(a_form); }
	bool IsWorn(const RE::TESForm* a_form) { return a_form && a_form == g_worn; }

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

	std::string ShowCardOf(RE::Actor* a_actor)
	{
		if (!a_actor) return "no one";
		for (auto& [object, data] : a_actor->GetInventory([](RE::TESBoundObject& a_o) { return Card(&a_o); })) {
			auto& entry = data.second;
			if (data.first <= 0 || !entry || !entry->extraLists) continue;
			for (auto* xl : *entry->extraLists) {
				const char* shown = xl ? xl->GetDisplayName(object) : nullptr;
				if (!shown || !*shown) continue;
				auto member = CardFor(shown);
				if (member.is_null()) continue;  // a copy this save has no record of: try the next
				SKSE::log::info("MemberCards: {} shows the player their card (\"{}\")", a_actor->GetDisplayFullName(), shown);
				Counter::OpenMemberCard(member);
				return std::string("shown: ") + shown;
			}
		}
		return std::string(a_actor->GetDisplayFullName()) + " carries no guild card the Guild has a record of";
	}

	nlohmann::json CardFor(const std::string& a_itemName)
	{
		Record r;
		bool   inParty = false;
		{
			std::lock_guard l(g_lock);
			const auto it = g_records.find(Key(a_itemName));
			if (it == g_records.end()) return nullptr;
			r = it->second;
		}
		const bool dead = OwnerDead(r);  // their blood is on it
		// the rank is the one they show now, while they can be found; otherwise the one last seen
		if (auto* form = Adventurers::FormOfKey(r.key))
			if (auto* actor = form->As<RE::Actor>(); actor && actor->Is3DLoaded()) {
				const auto info = Adventurers::Of(actor);
				if (info.kind != Adventurers::Kind::kNone && info.rank >= 0) {
					r.rank = std::clamp(info.rank, 0, 5);
					r.retired = info.kind == Adventurers::Kind::kRetired;
					r.level = actor->GetLevel();
					inParty = Party::IsActiveMember(actor);
					std::lock_guard l(g_lock);
					if (auto it = g_records.find(Key(a_itemName)); it != g_records.end()) {
						it->second.rank = r.rank;
						it->second.retired = r.retired;
						it->second.level = r.level;
					}
				}
			}
		// Merit, Reputation and the way to the next rank, as the Guild would have them on its books. Nothing of this is
		// kept: an NPC's rank follows from their level, so their Reputation is placed between what their rank asked
		// for and what the next one asks, as far along as their level is, a little to either side per person. Never
		// enough for the next rank (they would hold it). The level on the card is their own.
		const auto seed = Seed(r.key);
		const int  repHere = Guild::ReputationFor(r.rank);
		nlohmann::json out = { { "name", r.name }, { "letter", LetterStr(r.rank) }, { "date", { { "year", r.year }, { "month", r.month }, { "day", r.day } } },
			{ "seal", r.seal }, { "stamps", r.stamps }, { "retired", r.retired }, { "number", r.number }, { "level", r.level },
			{ "issuedAt", r.city.empty() ? std::string() : Guild::CityName(r.city) }, { "party", inParty ? Party::Name() : std::string() }, { "dead", dead } };
		int reputation;
		if (r.rank < 5) {
			const int   next = r.rank + 1, repNext = Guild::ReputationFor(next), lvlHere = MinLevel(r.rank), lvlNext = MinLevel(next);
			const float along = lvlNext > lvlHere ? static_cast<float>(r.level - lvlHere) / static_cast<float>(lvlNext - lvlHere) : 0.5f;
			const float nudge = (static_cast<float>((seed >> 3) % 21u) - 10.0f) / 100.0f;
			reputation = repHere + static_cast<int>(static_cast<float>(repNext - repHere) * std::clamp(along + nudge, 0.03f, 0.96f));
			out["next"] = { { "letter", LetterStr(next) }, { "reputation", repNext }, { "level", lvlNext } };
		} else {
			reputation = repHere + static_cast<int>((seed >> 3) % 2000u);
		}
		out["reputation"] = reputation;
		out["merit"] = static_cast<int>((seed >> 5) % static_cast<std::uint32_t>(20 + 25 * r.rank));
		out["goldEarned"] = (reputation * 9 + static_cast<int>((seed >> 7) % 400u)) / 5 * 5;
		return out;
	}

	void Sync()
	{
		if (!g_personal || !g_gCarried || !g_gCase) return;
		Bloody(RE::PlayerCharacter::GetSingleton());  // the cards of the dead the player carries look it
		int total = 0, weight = 0;
		for (auto& c : Scan()) {
			total += c.count;
			if (c.worn) continue;
			RE::Actor* owner = nullptr;
			const auto fate = FateOf(c, owner);
			weight = std::max(weight, fate == Fate::kFallen ? 3 : fate == Fate::kDead ? 2 : 1);
			if (fate == Fate::kAlive && owner) Replace(owner, c.item, true);
		}
		g_gCarried->value = static_cast<float>(total);
		// the player's line says what they hold: one card, or several (however they came by them)
		if (g_handInTopic && total > 0) {
			const auto line = total == 1 ? Loc::T("$AG_Dlg_CardHandIn", "I have a guild card to hand in.") : Loc::T("$AG_Dlg_CardsHandIn", "I have guild cards to hand in.");
			if (line != g_handInTopic->fullName.c_str()) g_handInTopic->fullName = line;
		}
		g_gCase->value = static_cast<float>(total == 0 ? 0 : weight == 0 ? 4 : weight);
	}

	int Carried()
	{
		int n = 0;
		for (auto& c : Scan()) n += c.count;
		return n;
	}

	void HandIn(RE::Actor* a_rep)
	{
		auto* pc = RE::PlayerCharacter::GetSingleton();
		if (!pc || !a_rep || !g_personal) return;
		int  rep = 0, worn = 0, cards = 0, paid = 0;
		bool fallen = false;
		for (auto& c : Scan()) {
			cards += c.count;
			if (c.worn) {
				// nobody's card: it pays unless it was lifted from a living adventurer's pocket
				if (!c.stolen) rep += Guild::CardReturnReputation() * c.count, paid += c.count;
				worn += c.count;
				pc->RemoveItem(c.object, c.count, RE::ITEM_REMOVE_REASON::kRemove, c.extra, nullptr);
				continue;
			}
			RE::Actor* owner = nullptr;
			const auto fate = FateOf(c, owner);
			// Only a card of the dead pays. A living member's card is in the player's hands because it was stolen or
			// taken in trade: the Guild sees it home and owes nothing for that.
			const bool pays = fate != Fate::kAlive && !c.stolen;
			if (pays) rep += Guild::CardReturnReputation() * c.count, paid += c.count;
			// a living owner has it back from the Guild (unless they have a replacement already)
			const bool back = fate == Fate::kAlive && owner && !HasCard(owner);
			pc->RemoveItem(c.object, c.count, back ? RE::ITEM_REMOVE_REASON::kStoreInContainer : RE::ITEM_REMOVE_REASON::kRemove, c.extra, back ? owner : nullptr);
			if (fate == Fate::kAlive) SetMissing(c.item, -1.0f);
			fallen |= fate == Fate::kFallen;
			Guild::Record(fate == Fate::kAlive ? Loc::F("$AG_Log_CardHandedIn", "Handed in {}'s guild card. The Adventurers Guild will see it back to them.", c.name)
				: fate == Fate::kFallen ? Loc::F("$AG_Log_CardFallen", "Handed in the guild card of {}, who fell at your side.", c.name)
				: Loc::F("$AG_Log_CardDead", "Handed in the guild card of {}, who is dead.", c.name));
			SKSE::log::info("MemberCards: \"{}\" handed in to {} - its owner {}{}", c.item, a_rep->GetDisplayFullName(),
				fate == Fate::kAlive ? (back ? "lives and has it back" : "lives (the card is kept: they have another, or cannot be found)") : fate == Fate::kFallen ? "fell in the player's party" : "is dead",
				pays ? "" : "; no Reputation");
		}
		if (cards == 0) {
			Sync();
			return;
		}
		if (worn == 1) Guild::Record(Loc::T("$AG_Log_CardWorn", "Handed in a worn guild card."));
		else if (worn > 1) Guild::Record(Loc::F("$AG_Log_CardsWorn", "Handed in {} worn guild cards.", worn));
		if (worn > 0) SKSE::log::info("MemberCards: {} worn card(s) handed in to {}", worn, a_rep->GetDisplayFullName());
		if (rep > 0) Guild::AddReward(0, rep, paid == 1 ? Loc::T("$AG_Why_CardHandedIn", "guild card handed in") : Loc::T("$AG_Why_CardsHandedIn", "guild cards handed in"));
		// a fallen party member: most representatives stand the party a round, one each for those still standing
		auto* base = a_rep->GetActorBase();
		if (fallen && !(base && g_noDrinks.contains(base->GetFormID()))) {
			auto* drink = Adventurers::LiaisonCity(a_rep) == "Raven Rock" && g_sujamma ? g_sujamma : g_mead;
			const int n = 1 + Party::LivingActiveCount();
			if (!drink) SKSE::log::warn("MemberCards: {} would stand the party a round, and the drink is not in this game", a_rep->GetDisplayFullName());
			if (drink) {
				pc->AddObjectToContainer(drink, nullptr, n, nullptr);
				RE::SendHUDMessage::ShowHUDMessage(Loc::F("$AG_Hud_DrinksOnHouse", "{} ({}) on the house", drink->GetName(), n).c_str());
				SKSE::log::info("MemberCards: {} stands the party a round - {} x {}", a_rep->GetDisplayFullName(), n, drink->GetName());
			}
		}
		Sync();
	}

	nlohmann::json Save()
	{
		std::lock_guard l(g_lock);
		auto cards = nlohmann::json::object();
		for (auto& [item, r] : g_records)
			cards[item] = { { "item", r.item }, { "key", r.key }, { "name", r.name }, { "rank", r.rank }, { "y", r.year }, { "m", r.month }, { "d", r.day }, { "seal", r.seal },
				{ "stamps", r.stamps }, { "retired", r.retired }, { "no", r.number }, { "city", r.city }, { "level", r.level }, { "dead", r.dead }, { "miss", r.missingSince } };
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
				r.city = c.value("city", "");
				r.level = c.value("level", 1);
				r.dead = c.value("dead", false);
				r.missingSince = c.value("miss", -1.0f);
				r.item = c.value("item", "");
				if (r.item.empty() || Old(r.item)) r.item = Renamed(r.item.empty() ? std::string(kOldPrefix) + r.name : r.item);
				g_records[Key(item)] = std::move(r);
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
		std::string out = std::format("{} personal card(s), {} adventurer(s) given a card of either kind; carried {} (case {}), {} representative(s) who pour nothing", g_records.size(), g_issued.size(),
			g_gCarried ? static_cast<int>(g_gCarried->value) : -1, g_gCase ? static_cast<int>(g_gCase->value) : -1, g_noDrinks.size());
		int n = 0;
		for (auto& [item, r] : g_records) {
			if (++n > 12) break;
			out += std::format("\n  \"{}\": {} rank {} {}/{}/{} {}{}{}", item, r.key, Letter(r.rank), r.day, r.month + 1, r.year, r.retired ? "retired" : "", r.dead ? " dead" : "",
				r.missingSince >= 0.0f ? std::format(" gone since day {:.1f}", r.missingSince) : std::string());
		}
		return out;
	}
}
