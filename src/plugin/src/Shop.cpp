// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "Shop.h"

#include "Guild.h"
#include "Loc.h"
#include "RankCore.h"

#include <set>
#include <fstream>
#include <mutex>
#include <unordered_set>

namespace AG::Shop
{
	namespace
	{
		struct Item
		{
			RE::TESBoundObject* form{ nullptr };
			int                 merit{ 0 };
			int                 rank{ 0 };
		};
		struct Trophy
		{
			std::string              key;
			RE::TESBoundObject*      form{ nullptr };
			int                      merit{ 0 };
			std::string              group;
			std::vector<std::string> words;  // of its in-game name, for matching other mods' variants
			std::int32_t             value{ 0 };
		};
		// One trophy the player carries: a listed item, or another mod's variant of one (Hunterborn's
		// "Wolf Pelt (Fine)" counts as a Wolf Pelt, paid by its value against the original's).
		struct Found
		{
			std::string         key;
			RE::TESBoundObject* form{ nullptr };
			std::string         group;
			int                 each{ 0 };
			int                 count{ 0 };
		};
		struct Library
		{
			std::string                    skill;
			std::array<RE::TESObjectBOOK*, 5> books{};
		};

		std::mutex           g_lock;
		std::vector<Library> g_library;
		std::array<int, 5>   g_libraryMerit{ 15, 25, 40, 60, 90 };
		std::vector<Item>    g_tomes, g_supplies;
		std::vector<Trophy>  g_trophies;
		std::unordered_map<RE::FormID, int> g_variantOf;  // item -> index in g_trophies, or -1 (names never change)
		int                  g_trainAmount{ 10 }, g_trainPerRank{ 2 }, g_trainBase{ 40 }, g_trainStep{ 20 };
		std::array<int, 3>   g_appMerit{ 10, 75, 250 }, g_appRank{ 0, 1, 3 }, g_appTrophy{ 0, 25, 50 };

		constexpr const char* kStatName[3]{ "Vitality", "Endurance", "Arcana" };
		constexpr const char* kStatAv[3]{ "Health", "Stamina", "Magicka" };
		constexpr const char* kRoman[3]{ "I", "II", "III" };

		template <class T = RE::TESBoundObject>
		T* Resolve(const std::string& a_key)
		{
			const auto bar = a_key.find('|');
			if (bar == std::string::npos) return nullptr;
			auto* dh = RE::TESDataHandler::GetSingleton();
			const auto id = static_cast<RE::FormID>(std::stoul(a_key.substr(bar + 1), nullptr, 16));
			// Untyped lookup + As<T>: TESDataHandler::LookupForm<T> compares T::FORMTYPE exactly, so for a base
			// class like TESBoundObject (potions, ingredients, misc items) it always returned nullptr.
			auto* form = dh ? dh->LookupForm(id, a_key.substr(0, bar)) : nullptr;
			return form ? form->As<T>() : nullptr;
		}

		nlohmann::json ReadJson(const char* a_path)
		{
			std::ifstream f(a_path);
			if (!f) {
				SKSE::log::warn("Shop: {} missing", a_path);
				return {};
			}
			return nlohmann::json::parse(f, nullptr, true, true);
		}

		// lower-case words of a name, plurals folded ("Bear Claws" -> bear, claw) so "Bear Claw (Fine)" still matches
		std::vector<std::string> Words(std::string_view a_name)
		{
			std::vector<std::string> out;
			std::string              w;
			auto flush = [&] {
				if (w.size() > 3 && w.back() == 's' && w[w.size() - 2] != 's') w.pop_back();
				if (!w.empty()) out.push_back(std::move(w));
				w.clear();
			};
			for (const char ch : a_name) {
				const auto c = static_cast<unsigned char>(ch);
				if (std::isalnum(c) || c >= 0x80) w += static_cast<char>(std::tolower(c));
				else flush();
			}
			flush();
			return out;
		}

		std::vector<Item> Items(const nlohmann::json& a_list)
		{
			std::vector<Item> out;
			for (auto& e : a_list) {
				auto* f = Resolve(e.value("form", ""));
				if (!f) continue;
				out.push_back({ f, e.value("merit", 0), std::clamp(e.value("rank", 0), 0, kRankCount - 1) });
			}
			return out;
		}

		std::string Name(RE::TESForm* a_form)
		{
			const char* n = a_form ? a_form->GetName() : nullptr;
			return n && *n ? n : "?";
		}

		int Carried(RE::TESBoundObject* a_obj)
		{
			auto* pc = RE::PlayerCharacter::GetSingleton();
			if (!pc || !a_obj) return 0;
			auto counts = pc->GetInventoryCounts([a_obj](RE::TESBoundObject& o) { return &o == a_obj; });
			auto it = counts.find(a_obj);
			return it == counts.end() ? 0 : it->second;
		}

		bool KnowsSpellFrom(RE::TESObjectBOOK* a_book)
		{
			auto* pc = RE::PlayerCharacter::GetSingleton();
			auto* sp = (a_book && a_book->TeachesSpell()) ? a_book->GetSpell() : nullptr;
			return pc && sp && pc->HasSpell(sp);
		}

		// caller holds g_lock. Next unread book of a library row (tier 1..5), or 0 when the set is read.
		int NextTier(const Library& a_lib)
		{
			for (int t = 0; t < 5; ++t) {
				if (a_lib.books[t] && !a_lib.books[t]->IsRead()) return t + 1;
			}
			return 0;
		}

		int TrainCap(int a_rank) { return g_trainPerRank * (std::max(a_rank, 0) + 1); }
		int TrainCost(int a_done) { return g_trainBase + g_trainStep * a_done; }

		std::string SkillLabel(const std::string& a_skill)
		{
			std::string en = a_skill;
			if (a_skill == "OneHanded") en = "One-Handed";
			else if (a_skill == "TwoHanded") en = "Two-Handed";
			else if (a_skill == "Marksman") en = "Archery";
			else if (a_skill == "LightArmor") en = "Light Armor";
			else if (a_skill == "HeavyArmor") en = "Heavy Armor";
			else if (a_skill == "Speechcraft") en = "Speech";
			return Loc::T("$AG_Skill_" + a_skill, en);
		}

		void Give(RE::TESBoundObject* a_obj)
		{
			RE::PlayerCharacter::GetSingleton()->AddObjectToContainer(a_obj, nullptr, 1, nullptr);
		}

		bool Pay(int a_cost, const std::string& a_record, std::string& a_err)
		{
			if (Guild::TrySpendMerit(a_cost, a_record)) return true;
			a_err = Loc::F("$AG_Svc_NeedMerit", "You need {} Merit.", a_cost);
			return false;
		}
	}

	namespace
	{
		int VariantOfLocked(RE::TESBoundObject* a_obj);

		// ---- parts of creatures other mods add (1.2.1) ----
		// The trophy list names vanilla monster parts. A creature another mod adds drops parts the list has never heard
		// of, so they are worked out from the records: an ingredient, or a misc item tagged as an animal hide or part,
		// that another mod defines and that a creature which starts fights (Aggressive or worse) carries or drops.
		// Harmless wildlife (Unaggressive: deer, goats, a mod's cattle or mounts) adds nothing. Meat is food, not a
		// trophy, as with vanilla. Merit comes from the item's gold value, capped: the Guild cannot tell a tooth taken
		// from a wild beast from one taken from a tame one, and a mod's price tag should not out-pay a dragon bone.
		struct ModCreatures
		{
			bool enabled{ true };
			int  goldPerMerit{ 10 };
			int  maxMerit{ 5 };
			std::vector<std::string> notTrophies{ "meat", "flesh", "fish" };  // a word of the item's name: food, not proof of a hunt
			int  maxPartsPerCreature{ 5 };  // more distinct parts than this is an alchemist's or a looter's pockets, not a body
		};

		bool Vanilla(const RE::TESForm* a_form)
		{
			static constexpr std::string_view kVanilla[]{ "Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm", "Dragonborn.esm" };
			auto*      dh = RE::TESDataHandler::GetSingleton();
			const auto id = a_form->GetFormID();
			const RE::TESFile* file = nullptr;
			if ((id >> 24) == 0xFE) file = dh->LookupLoadedLightModByIndex(static_cast<std::uint16_t>((id >> 12) & 0xFFF));
			else if ((id >> 24) != 0xFF) file = dh->LookupLoadedModByIndex(static_cast<std::uint8_t>(id >> 24));
			if (!file) return true;  // unknown origin (created in game): leave it alone
			return std::ranges::any_of(kVanilla, [&](std::string_view v) { return _stricmp(file->GetFilename().data(), v.data()) == 0; });
		}

		// what an actor base uses from its template, followed through (a template may be a leveled list of actors)
		using UseFlag = RE::ACTOR_BASE_DATA::TEMPLATE_USE_FLAG;
		void Bases(RE::TESForm* a_form, UseFlag a_flag, int a_depth, std::vector<RE::TESNPC*>& a_out)
		{
			if (!a_form || a_depth > 6) return;
			if (auto* npc = a_form->As<RE::TESNPC>()) {
				if (npc->baseTemplateForm && npc->actorData.templateUseFlags.all(a_flag)) Bases(npc->baseTemplateForm, a_flag, a_depth + 1, a_out);
				else a_out.push_back(npc);
			} else if (auto* list = a_form->As<RE::TESLevCharacter>()) {
				for (auto& e : list->entries) Bases(e.form, a_flag, a_depth + 1, a_out);
			}
		}

		void Parts(RE::TESForm* a_form, int a_depth, std::vector<RE::TESBoundObject*>& a_out)
		{
			if (!a_form || a_depth > 6) return;
			if (auto* list = a_form->As<RE::TESLevItem>()) {
				for (auto& e : list->entries) Parts(e.form, a_depth + 1, a_out);
			} else if (a_form->Is(RE::FormType::Ingredient) || a_form->Is(RE::FormType::Misc)) {
				a_out.push_back(a_form->As<RE::TESBoundObject>());
			}
		}

		// g_lock held. Adds the trophies; returns how many.
		int AddModCreatureTrophies(const ModCreatures& a_cfg)
		{
			auto* dh = RE::TESDataHandler::GetSingleton();
			if (!a_cfg.enabled || !dh) return 0;
			int added = 0, creatures = 0, looters = 0;
			std::unordered_set<RE::FormID> seen;
			for (auto* npc : dh->GetFormArray<RE::TESNPC>()) {
				if (!npc || Vanilla(npc)) continue;
				auto* race = npc->GetRace();
				// people are not hunted for parts: the keyword, or a face-generated head (custom human races often lack the keyword)
				if (!race || race->HasKeywordString("ActorTypeNPC") || race->data.flags.any(RE::RACE_DATA::Flag::kFaceGenHead)) continue;
				std::vector<RE::TESNPC*> ai, inv;
				Bases(npc, UseFlag::kAIData, 0, ai);
				if (!std::ranges::any_of(ai, [](RE::TESNPC* b) { return b->GetAggressionLevel() >= RE::ACTOR_AGGRESSION::kAggressive; })) continue;
				Bases(npc, UseFlag::kInventory, 0, inv);
				std::vector<RE::TESBoundObject*> all, parts;
				for (auto* b : inv) {
					b->ForEachContainerObject([&](RE::ContainerObject& e) {
						Parts(e.obj, 0, all);
						return RE::BSContainer::ForEachResult::kContinue;
					});
					Parts(b->deathItem, 0, all);
				}
				// what of it could be a part of the creature: another mod's, worth something, a hide or part if misc
				std::set<std::string> names;
				for (auto* p : all) {
					if (!p || Vanilla(p) || p->GetGoldValue() <= 0 || Name(p).empty()) continue;
					if (p->Is(RE::FormType::Misc)) {
						auto* kw = p->As<RE::BGSKeywordForm>();
						if (!kw || !(kw->HasKeywordString("VendorItemAnimalHide") || kw->HasKeywordString("VendorItemAnimalPart"))) continue;
					}
					// meat and fish are food, whatever kind of record the mod made them (Zombie Flesh, Rainbow Fish)
					const auto words = Words(Name(p));
					if (std::ranges::any_of(a_cfg.notTrophies, [&](const std::string& w) { return std::ranges::find(words, w) != words.end(); })) continue;
					if (std::ranges::find(parts, p) == parts.end()) parts.push_back(p);
					names.insert(Name(p));
				}
				if (parts.empty()) continue;
				// A beast drops a few parts of itself. One that carries dozens of different ingredients (a Falmer
				// alchemist, a mod's "creature" merchant) is carrying loot, and none of it is proof of a hunt.
				if (static_cast<int>(names.size()) > a_cfg.maxPartsPerCreature) {
					++looters;
					SKSE::log::debug("Shop: {} ({:08X}) carries {} different parts - loot, not trophies", Name(npc), npc->GetFormID(), names.size());
					continue;
				}
				++creatures;
				auto group = npc->GetName() && *npc->GetName() ? std::string(npc->GetName()) : std::string(race->GetName() ? race->GetName() : "");
				for (auto* p : parts) {
					if (!seen.insert(p->GetFormID()).second) continue;
					if (std::ranges::find(g_trophies, p, &Trophy::form) != g_trophies.end() || VariantOfLocked(p) >= 0) continue;  // already one
					const int merit = std::clamp(static_cast<int>(std::lround(static_cast<double>(p->GetGoldValue()) / std::max(1, a_cfg.goldPerMerit))), 1, std::max(1, a_cfg.maxMerit));
					g_trophies.push_back({ std::format("mod:{:08X}", p->GetFormID()), p, merit, group, {}, p->GetGoldValue() });
					SKSE::log::debug("Shop: {} ({:08X}, {} gold) is a trophy worth {} Merit: carried by {}", Name(p), p->GetFormID(), p->GetGoldValue(), merit, group);
					++added;
				}
			}
			SKSE::log::info("Shop: {} trophies from {} hostile creatures added by other mods; {} more carry loot and were left out (the detailed log lists them)", added, creatures, looters);
			return added;
		}
	}

	void Load()
	{
		std::lock_guard l(g_lock);
		g_library.clear();
		g_tomes.clear();
		g_supplies.clear();
		g_trophies.clear();
		try {
			auto shop = ReadJson("Data/SKSE/Plugins/AdventurersGuild/shop.resolved.json");
			if (shop.contains("library")) {
				auto& lib = shop.at("library");
				if (lib.contains("meritByTier")) {
					auto v = lib.at("meritByTier").get<std::vector<int>>();
					for (std::size_t i = 0; i < 5 && i < v.size(); ++i) g_libraryMerit[i] = v[i];
				}
				for (auto& [skill, keys] : lib.value("books", nlohmann::json::object()).items()) {
					Library row{ skill };
					for (std::size_t t = 0; t < 5 && t < keys.size(); ++t) row.books[t] = Resolve<RE::TESObjectBOOK>(keys[t].get<std::string>());
					g_library.push_back(std::move(row));
				}
			}
			g_tomes = Items(shop.value("tomes", nlohmann::json::array()));
			g_supplies = Items(shop.value("supplies", nlohmann::json::array()));
			if (shop.contains("training")) {
				auto& t = shop.at("training");
				g_trainAmount = t.value("amount", g_trainAmount);
				g_trainPerRank = std::max(1, t.value("perRank", g_trainPerRank));
				g_trainBase = t.value("baseMerit", g_trainBase);
				g_trainStep = t.value("stepMerit", g_trainStep);
			}
			auto trophies = ReadJson("Data/SKSE/Plugins/AdventurersGuild/trophies.resolved.json");
			g_variantOf.clear();
			for (auto& e : trophies.value("trophies", nlohmann::json::array())) {
				const auto key = e.value("form", "");
				if (auto* f = Resolve(key)) g_trophies.push_back({ key, f, e.value("merit", 1), e.value("group", ""), Words(Name(f)), f->GetGoldValue() });
			}
			// name-only trophies: parts other mods add with no vanilla item to point at (Hunterborn's Troll Hide);
			// matched by name like any variant, quality against "value"
			// "name" may list the item's name in several languages ("Troll Hide", "Peau de troll", ...): any match counts
			for (auto& e : trophies.value("byName", nlohmann::json::array())) {
				std::vector<std::string> names;
				if (e.contains("name") && e.at("name").is_array()) names = e.at("name").get<std::vector<std::string>>();
				else if (auto n = e.value("name", ""); !n.empty()) names.push_back(n);
				for (auto& name : names)
					if (!name.empty()) g_trophies.push_back({ "name:" + names.front(), nullptr, e.value("merit", 1), e.value("group", ""), Words(name), e.value("value", 0) });
			}
			ModCreatures modCreatures;
			std::ifstream gf("Data/SKSE/Plugins/AdventurersGuild/guild.json");
			if (gf) {
				auto g = nlohmann::json::parse(gf, nullptr, true, true);
				if (g.contains("appraisal")) {
					auto fill = [&](const char* k, std::array<int, 3>& out) {
						if (!g.at("appraisal").contains(k)) return;
						auto v = g.at("appraisal").at(k).get<std::vector<int>>();
						for (std::size_t i = 0; i < 3 && i < v.size(); ++i) out[i] = v[i];
					};
					fill("merit", g_appMerit);
					fill("rank", g_appRank);
					fill("trophyBonus", g_appTrophy);
				}
				if (g.contains("modCreatureTrophies")) {
					auto& m = g.at("modCreatureTrophies");
					modCreatures.enabled = m.value("enabled", modCreatures.enabled);
					modCreatures.goldPerMerit = m.value("goldPerMerit", modCreatures.goldPerMerit);
					modCreatures.maxMerit = m.value("maxMerit", modCreatures.maxMerit);
					modCreatures.maxPartsPerCreature = m.value("maxPartsPerCreature", modCreatures.maxPartsPerCreature);
					if (m.contains("notTrophies")) {
						modCreatures.notTrophies.clear();
						for (auto& w : m.at("notTrophies"))
							for (auto& t : Words(w.get<std::string>())) modCreatures.notTrophies.push_back(t);  // same spelling rules as item names
					}
				}
			}
			AddModCreatureTrophies(modCreatures);  // after the listed ones: an item already a trophy, or a variant of one, stays that
		} catch (const std::exception& e) {
			SKSE::log::error("Shop: config error: {}", e.what());
		}
		SKSE::log::info("Shop: {} library rows, {} tomes, {} supplies, {} trophies", g_library.size(), g_tomes.size(), g_supplies.size(), g_trophies.size());
	}

	int TrophyBonusPercent(int a_appraisal)
	{
		std::lock_guard l(g_lock);
		return a_appraisal >= 1 && a_appraisal <= 3 ? g_appTrophy[a_appraisal - 1] : 0;
	}

	nlohmann::json ServicesData(int a_rank, int a_merit, int a_appraisal, const std::array<int, 3>& a_training)
	{
		std::lock_guard l(g_lock);
		auto rows = nlohmann::json::array();
		// a_section is the stable id (grouping, the page's section notes); its display name is translated
		auto add = [&](const char* a_section, std::string a_id, std::string a_name, std::string a_desc, int a_cost, int a_needRank, std::string a_block = {}) {
			std::string note = a_block;
			if (note.empty() && a_rank < a_needRank) note = Loc::F("$AG_Note_NeedRank", "Requires Rank {}", Letter(a_needRank));
			if (note.empty() && a_merit < a_cost) note = Loc::T("$AG_Note_NoMerit", "Not enough Merit");
			std::string secKey = "$AG_Sec_";
			for (char c : std::string_view(a_section)) if (c != ' ') secKey += c;
			rows.push_back({ { "section", Loc::T(secKey, a_section) }, { "sectionId", a_section }, { "id", std::move(a_id) }, { "name", std::move(a_name) },
				{ "desc", std::move(a_desc) }, { "cost", a_cost }, { "available", note.empty() }, { "note", note } });
		};
		auto stat = [](int st) { return Loc::T(std::format("$AG_Stat_{}", kStatName[st]), kStatName[st]); };
		auto av = [](int st) { return Loc::T(std::format("$AG_AV_{}", kStatAv[st]), kStatAv[st]); };

		// Guild skills
		if (a_appraisal < 3) {
			const int t = a_appraisal;  // next tier index
			const auto what = t == 0 ? Loc::T("$AG_Svc_Appraisal1", "Read an adventurer's guild rank and a foe's threat rank at a glance. Without it, no ranks are shown.")
			                 : t == 1 ? Loc::T("$AG_Svc_Appraisal2", "Merchants pay 5% more, and trophies earn 25% more Merit.")
			                          : Loc::T("$AG_Svc_Appraisal3", "Merchants pay 10% more, trophies earn 50% more Merit, and hidden ranks are revealed.");
			add("Guild Skills", "appraisal", Loc::F("$AG_Svc_AppraisalName", "Appraisal {}", kRoman[t]), what, g_appMerit[t], g_appRank[t]);
		}
		for (int st = 0; st < 3; ++st) {
			const int done = a_training[st], cap = TrainCap(a_rank), max = g_trainPerRank * kRankCount;
			std::string block = done >= max ? Loc::T("$AG_Note_FullyTrained", "Fully trained") : (done >= cap ? Loc::T("$AG_Note_RankLimit", "Limit for your rank reached") : "");
			add("Guild Skills", std::format("train:{}", st), Loc::F("$AG_Svc_TrainName", "{} training", stat(st)),
				Loc::F("$AG_Svc_TrainDesc", "Permanently +{} maximum {}. Trained {} of {} at your rank (currently +{}).", g_trainAmount, av(st), done, std::min(cap, max), done * g_trainAmount),
				TrainCost(done), 0, block);
		}

		// Guild Library
		for (auto& lib : g_library) {
			const int tier = NextTier(lib);
			if (!tier) continue;  // every book in the set already read
			auto* book = lib.books[tier - 1];
			add("Guild Library", "lib:" + lib.skill, Loc::F("$AG_Svc_LibName", "{}: {}", SkillLabel(lib.skill), Name(book)),
				Loc::F("$AG_Svc_LibDesc", "Skill book {} of 5. Reading it improves {}.", tier, SkillLabel(lib.skill)),
				g_libraryMerit[tier - 1], tier - 1, Carried(book) ? Loc::T("$AG_Note_InPack", "Already in your pack") : "");
		}

		// Spell tomes (hidden once the spell is known)
		for (std::size_t i = 0; i < g_tomes.size(); ++i) {
			auto* book = g_tomes[i].form->As<RE::TESObjectBOOK>();
			if (KnowsSpellFrom(book)) continue;
			add("Spell Tomes", std::format("tome:{}", i), Name(g_tomes[i].form), Loc::T("$AG_Svc_TomeDesc", "Teaches the spell when read."),
				g_tomes[i].merit, g_tomes[i].rank, Carried(g_tomes[i].form) ? Loc::T("$AG_Note_InPack", "Already in your pack") : "");
		}

		// Supplies
		for (std::size_t i = 0; i < g_supplies.size(); ++i) {
			add("Supplies", std::format("supply:{}", i), Name(g_supplies[i].form), Loc::F("$AG_Svc_Carry", "You carry {}.", Carried(g_supplies[i].form)),
				g_supplies[i].merit, g_supplies[i].rank);
		}
		return rows;
	}

	std::string Buy(const std::string& a_id)
	{
		const int rank = Guild::Rank();
		std::string err;
		if (a_id == "appraisal") {
			const int t = Guild::AppraisalLevel();
			if (t >= 3) return Loc::T("$AG_Buy_AppraisalMax", "You have mastered Appraisal.");
			int cost, need;
			{
				std::lock_guard l(g_lock);
				cost = g_appMerit[t];
				need = g_appRank[t];
			}
			if (rank < need) return Loc::F("$AG_Buy_AppraisalRank", "Appraisal {} requires Rank {}.", kRoman[t], Letter(need));
			if (!Pay(cost, Loc::F("$AG_Log_Appraisal2", "Learned Appraisal {} ({} Merit).", kRoman[t], cost), err)) return err;
			Guild::SetAppraisalLevel(t + 1);
			return Loc::F("$AG_Buy_Appraisal", "You have learned Appraisal {}.", kRoman[t]);
		}
		if (a_id.starts_with("train:")) {
			const int st = std::stoi(a_id.substr(6));
			if (st < 0 || st > 2) return Loc::T("$AG_Buy_Unknown", "That service is not available yet.");
			const int done = Guild::TrainingSteps(st);
			int cost, cap, max, amount;
			{
				std::lock_guard l(g_lock);
				cost = TrainCost(done);
				cap = TrainCap(rank);
				max = g_trainPerRank * kRankCount;
				amount = g_trainAmount;
			}
			const auto sname = Loc::T(std::format("$AG_Stat_{}", kStatName[st]), kStatName[st]);
			const auto savn = Loc::T(std::format("$AG_AV_{}", kStatAv[st]), kStatAv[st]);
			if (done >= max) return Loc::T("$AG_Buy_TrainMax", "You are fully trained.");
			if (done >= cap) return Loc::T("$AG_Buy_TrainCap", "You have trained as far as your rank allows.");
			if (!Pay(cost, Loc::F("$AG_Log_Train", "{} training: +{} {} ({} Merit).", sname, amount, savn, cost), err)) return err;
			Guild::AddTrainingStep(st);
			return Loc::F("$AG_Buy_Train", "{} training complete: +{} maximum {}.", sname, amount, savn);
		}
		if (a_id.starts_with("lib:")) {
			RE::TESObjectBOOK* book = nullptr;
			int                cost = 0, tier = 0;
			{
				std::lock_guard l(g_lock);
				for (auto& lib : g_library) {
					if (lib.skill != a_id.substr(4)) continue;
					tier = NextTier(lib);
					if (tier) {
						book = lib.books[tier - 1];
						cost = g_libraryMerit[tier - 1];
					}
				}
			}
			if (!book) return Loc::T("$AG_Buy_LibEmpty", "Nothing left to read in that collection.");
			if (rank < tier - 1) return Loc::F("$AG_Buy_BookRank", "That book requires Rank {}.", Letter(tier - 1));
			if (!Pay(cost, Loc::F("$AG_Log_Bought", "Bought {} ({} Merit).", Name(book), cost), err)) return err;
			Give(book);
			return Loc::F("$AG_Buy_Bought", "Bought {}.", Name(book));
		}
		const bool tome = a_id.starts_with("tome:"), supply = a_id.starts_with("supply:");
		if (tome || supply) {
			Item it;
			{
				std::lock_guard l(g_lock);
				auto& list = tome ? g_tomes : g_supplies;
				const auto i = static_cast<std::size_t>(std::stoul(a_id.substr(tome ? 5 : 7)));
				if (i >= list.size()) return Loc::T("$AG_Buy_Unknown", "That service is not available yet.");
				it = list[i];
			}
			if (rank < it.rank) return Loc::F("$AG_Buy_ItemRank", "That requires Rank {}.", Letter(it.rank));
			if (!Pay(it.merit, Loc::F("$AG_Log_Bought", "Bought {} ({} Merit).", Name(it.form), it.merit), err)) return err;
			Give(it.form);
			return Loc::F("$AG_Buy_Bought", "Bought {}.", Name(it.form));
		}
		return Loc::T("$AG_Buy_Unknown", "That service is not available yet.");
	}

	namespace
	{
		// The listed trophy that another mod's item is a variant of: same kind of form, worth something, and its
		// name holds every word of the trophy's name ("Sabre Cat Snow Pelt (Fine)" -> Snow Sabre Cat Pelt). The
		// longest such name wins, so "Cave Bear Pelt (Poor)" is a Cave Bear Pelt, not a Bear Pelt. -1 if none.
		// Carcasses, fat and the like share the vendor keywords but no trophy's name, so they never match.
		int VariantOfLocked(RE::TESBoundObject* a_obj)
		{
			if (auto it = g_variantOf.find(a_obj->GetFormID()); it != g_variantOf.end()) return it->second;
			int best = -1;
			if (a_obj->GetGoldValue() > 0) {
				const auto words = Words(Name(a_obj));
				for (int i = 0; i < static_cast<int>(g_trophies.size()); ++i) {
					const auto& t = g_trophies[i];
					if (t.words.empty() || (t.form && t.form->GetFormType() != a_obj->GetFormType())) continue;
					const bool all = std::ranges::all_of(t.words, [&](const std::string& w) { return std::ranges::find(words, w) != words.end(); });
					if (all && (best < 0 || t.words.size() > g_trophies[best].words.size())) best = i;
				}
			}
			if (best >= 0) SKSE::log::info("Shop: {} ({:08X}) counts as trophy {}", Name(a_obj), a_obj->GetFormID(), g_trophies[best].key);
			g_variantOf[a_obj->GetFormID()] = best;
			return best;
		}

		// Every trophy the player carries, listed ones and variants, with Merit each before the Appraisal bonus.
		std::vector<Found> Scan()
		{
			std::vector<Found> out;
			auto*              pc = RE::PlayerCharacter::GetSingleton();
			if (!pc) return out;
			const auto counts = pc->GetInventoryCounts([](RE::TESBoundObject& o) {
				return o.Is(RE::FormType::Misc) || o.Is(RE::FormType::Ingredient);
			});
			std::lock_guard l(g_lock);
			for (auto& [form, n] : counts) {
				if (n <= 0) continue;
				const auto exact = std::ranges::find(g_trophies, form, &Trophy::form);
				if (exact != g_trophies.end()) {
					out.push_back({ exact->key, form, exact->group, exact->merit, n });
					continue;
				}
				const int i = VariantOfLocked(form);
				if (i < 0) continue;
				const auto& t = g_trophies[i];
				// quality: paid by its value against the original's, half to double ("Poor" pelts less, "Fine" more)
				const double ratio = t.value > 0 ? std::clamp(static_cast<double>(form->GetGoldValue()) / t.value, 0.5, 2.0) : 1.0;
				out.push_back({ std::format("{:08X}", form->GetFormID()), form, t.group, std::max(1, static_cast<int>(std::lround(t.merit * ratio))), n });
			}
			std::ranges::sort(out, [](const Found& x, const Found& y) { return x.each != y.each ? x.each > y.each : x.key < y.key; });
			return out;
		}
	}

	nlohmann::json TrophiesData()
	{
		const int bonus = TrophyBonusPercent(Guild::AppraisalLevel());
		auto      items = nlohmann::json::array();
		int       total = 0;
		for (auto& t : Scan()) {
			const int each = static_cast<int>(std::lround(t.each * (1.0 + bonus / 100.0)));
			total += each * t.count;
			std::string gk = "$AG_Group_";
			for (char c : t.group) if (c != ' ') gk += c;
			items.push_back({ { "key", t.key }, { "name", Name(t.form) }, { "group", t.group.empty() ? t.group : Loc::T(gk, t.group) }, { "count", t.count }, { "each", each },
				{ "merit", each * t.count } });
		}
		return { { "items", items }, { "total", total }, { "bonus", bonus } };
	}

	std::string TurnIn(const std::string& a_key)
	{
		const int bonus = TrophyBonusPercent(Guild::AppraisalLevel());
		auto*     pc = RE::PlayerCharacter::GetSingleton();
		if (!pc) return {};
		int merit = 0, items = 0;
		for (auto& t : Scan()) {
			if (a_key != "all" && t.key != a_key) continue;
			pc->RemoveItem(t.form, t.count, RE::ITEM_REMOVE_REASON::kRemove, nullptr, nullptr);
			merit += static_cast<int>(std::lround(t.each * (1.0 + bonus / 100.0))) * t.count;
			items += t.count;
		}
		if (!items) return Loc::T("$AG_Trophy_None", "You have no trophies the Guild wants.");
		Guild::AddMerit(merit, Loc::T("$AG_Why_Trophies", "trophies"));
		Guild::CountTrophies(items);
		Guild::Notify("AG_TrophiesHandedIn", std::format("{} troph{}", items, items == 1 ? "y" : "ies"), static_cast<float>(merit));
		SKSE::log::info("Shop: turned in {} trophies for {} merit (bonus {}%)", items, merit, bonus);
		return items == 1 ? Loc::F("$AG_Trophy_TookOne", "The Guild takes 1 trophy for {} Merit.", merit)
		                  : Loc::F("$AG_Trophy_TookMany", "The Guild takes {} trophies for {} Merit.", items, merit);
	}
}
