// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "Loc.h"
#include "Adventurers.h"

#include "Guild.h"
#include "RankCore.h"

#include <fstream>
#include <mutex>
#include <unordered_map>
#include <unordered_set>

namespace AG::Adventurers
{
	namespace
	{
		// A named NPC the Guild has on its books (adventurers.json "named"): Sinmir, a C-rank who drinks at the
		// Bannered Mare. Active until the world says they took another service (the Stormcloaks make him captain).
		struct Named
		{
			RE::BGSLocation* where{ nullptr };
			RE::BGSKeyword*  keyword{ nullptr };
			float            value{ 0.0f };
			int              rank{ -1 };  // fixed Guild rank, or -1: from their level
			std::string      note, retiredNote;
			bool Retired() const
			{
				if (!where || !keyword) return false;
				for (auto& d : where->keywordData)
					if (d.keyword == keyword) return d.data == value;
				return false;
			}
		};
		std::unordered_map<RE::FormID, Named> g_named;  // by actor base
		std::unordered_set<RE::FormID>        g_joinOnRecruitNpcs;  // actor bases treated like g_joinOnRecruit's factions

		// A liaison's successor (dialogue.json "successor"): keeps the counter once the liaison they follow is dead,
		// whoever runs the inn. With the Unofficial Patch Mikael takes the Bannered Mare over; Ysolda takes the counter.
		struct Successor
		{
			RE::FormID       npc{ 0 }, of{ 0 };  // actor bases
			RE::TESQuest*    quest{ nullptr };   // the hold's Dialogue quest ...
			std::uint32_t    alias{ 0 };         // ... and its Innkeeper alias: the game swaps the backup in on death
			RE::FormID       ref{ 0 };           // the successor's own reference
			RE::TESObjectCELL* cell{ nullptr };  // the inn: Guild business only there
			std::string      city;
		};
		std::vector<Successor> g_successors;

		// adventurers.json "notes": a SkyrimNet bio line for an NPC who is not (only) a named member, optionally only
		// once another NPC is dead (the one who keeps a counter after an innkeeper, or says it has closed)
		struct BioNote
		{
			RE::TESNPC* whenDead{ nullptr };
			std::string text;
		};
		std::unordered_multimap<RE::FormID, BioNote> g_notes;
		std::string                                  g_wandererNote;

		// The game's own GetDeadCount, as dialogue conditions ask it: true once that NPC has died
		bool HasDied(RE::TESNPC* a_npc)
		{
			auto* pc = RE::PlayerCharacter::GetSingleton();
			if (!a_npc || !pc) return false;
			RE::TESConditionItem c;
			c.next = nullptr;
			c.data.functionData.function = RE::FUNCTION_DATA::FunctionID::kGetDeadCount;
			c.data.functionData.params[0] = a_npc;
			c.data.comparisonValue.f = 1.0f;
			c.data.flags.opCode = RE::CONDITION_ITEM_DATA::OpCode::kGreaterThanOrEqualTo;
			c.data.object = RE::CONDITIONITEMOBJECT::kSelf;
			RE::ConditionCheckParams params(pc, pc);
			return c.IsTrue(params);
		}

		// Reads only game state. The successor, if the liaison they follow is dead and they are alive.
		RE::Actor* Active(const Successor& a_s)
		{
			if (!a_s.quest) return nullptr;
			auto  held = a_s.quest->GetAliasedRef(a_s.alias).get();
			auto* holder = held ? held->As<RE::Actor>() : nullptr;
			auto* hbase = holder ? holder->GetActorBase() : nullptr;
			// the Innkeeper alias still holds the original, alive: nothing has happened
			if (hbase && hbase->GetFormID() == a_s.of && !holder->IsDead()) return nullptr;
			auto* actor = RE::TESForm::LookupByID<RE::Actor>(a_s.ref);
			return actor && !actor->IsDead() ? actor : nullptr;
		}
		// ... and where they can do the Guild's business
		bool AtInn(const Successor& a_s, RE::Actor* a_actor) { return !a_s.cell || (a_actor && a_actor->GetParentCell() == a_s.cell); }

		// Adventurers met on the road (adventurers.json "wanderers"): the game's own, by actor base, and any other
		// mod's generic person called an adventurer.
		struct Wanderers
		{
			std::unordered_set<RE::FormID> bases;
			std::vector<std::string>       names, notNames;  // lower case
			std::vector<RE::TESFaction*>   notFactions;
		};
		Wanderers g_wanderers;

		std::string Lower(std::string a_s)
		{
			std::ranges::transform(a_s, a_s.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
			return a_s;
		}

		struct ChanceGroup
		{
			std::string                    id;
			Kind                           kind{ Kind::kMember };
			std::uint32_t                  percent{ 0 };
			std::vector<RE::TESFaction*>   factions;
		};

		std::mutex                              g_lock;
		std::vector<RE::TESFaction*>            g_members;
		std::vector<RE::TESFaction*>            g_joinOnRecruit;
		std::vector<ChanceGroup>                g_chance;
		std::unordered_set<RE::FormID>          g_liaisons;  // base NPCs who keep a guild counter (dialogue.json)
		std::unordered_map<RE::FormID, std::string> g_liaisonCity;
		std::unordered_set<std::string>         g_recruited;  // StableKey of refs that joined on recruitment
		std::unordered_map<RE::FormID, Kind>    g_cache;      // decided kind for non-recruited refs

		RE::TESFaction* Resolve(const std::string& a_key)
		{
			const auto bar = a_key.find('|');
			if (bar == std::string::npos) return nullptr;
			const auto plugin = a_key.substr(0, bar);
			const auto id = static_cast<RE::FormID>(std::stoul(a_key.substr(bar + 1), nullptr, 16));
			auto* dh = RE::TESDataHandler::GetSingleton();
			return dh ? dh->LookupForm<RE::TESFaction>(id, plugin) : nullptr;
		}

		std::vector<RE::TESFaction*> Factions(const nlohmann::json& a_obj, const char* a_where)
		{
			std::vector<RE::TESFaction*> out;
			if (!a_obj.contains("factions")) return out;
			for (auto& k : a_obj.at("factions")) {
				auto* f = Resolve(k.get<std::string>());
				if (f) out.push_back(f);
				else SKSE::log::warn("Adventurers: {} faction {} not loaded - skipped", a_where, k.get<std::string>());
			}
			return out;
		}

		bool InAny(RE::Actor* a_actor, const std::vector<RE::TESFaction*>& a_list)
		{
			for (auto* f : a_list) {
				if (a_actor->IsInFaction(f)) return true;
			}
			return false;
		}

		// splitmix64: a well-mixed, deterministic roll from the reference FormID
		std::uint32_t Roll(RE::FormID a_id)
		{
			std::uint64_t z = a_id + 0x9E3779B97F4A7C15ull;
			z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
			z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
			return static_cast<std::uint32_t>((z ^ (z >> 31)) % 100);
		}

		// caller holds g_lock. a_rule receives a short reason for Describe().
		// g_lock held
		bool WandererLocked(RE::Actor* a_actor)
		{
			auto* base = a_actor ? a_actor->GetActorBase() : nullptr;
			if (!base) return false;
			if (g_wanderers.bases.contains(base->GetFormID())) return true;
			// a levelled actor's base is made at run time: the record it was made from says who it is
			if (auto* root = base->GetRootFaceNPC(); root && g_wanderers.bases.contains(root->GetFormID())) return true;
			if (g_wanderers.names.empty() || base->IsUnique()) return false;
			const char* n = a_actor->GetDisplayFullName();
			const auto  name = Lower(n ? n : "");
			if (std::ranges::none_of(g_wanderers.names, [&](const std::string& w) { return name.find(w) != std::string::npos; })) return false;
			if (std::ranges::any_of(g_wanderers.notNames, [&](const std::string& w) { return name.find(w) != std::string::npos; })) return false;
			return !InAny(a_actor, g_wanderers.notFactions);
		}

		Kind Decide(RE::Actor* a_actor, std::string* a_rule)
		{
			auto*      dbase = a_actor->GetActorBase();
			const bool exception = InAny(a_actor, g_joinOnRecruit) || (dbase && g_joinOnRecruitNpcs.contains(dbase->GetFormID()));
			if (!exception && InAny(a_actor, g_members)) {
				if (a_rule) *a_rule = "member faction";
				return Kind::kMember;
			}
			if (!exception && WandererLocked(a_actor)) {
				if (a_rule) *a_rule = "wandering adventurer";
				return Kind::kMember;
			}
			const auto roll = Roll(a_actor->GetFormID());
			for (auto& g : g_chance) {
				if (!InAny(a_actor, g.factions)) continue;
				if (a_rule) *a_rule = std::format("chance group '{}' roll {} vs {}%", g.id, roll, g.percent);
				return roll < g.percent ? g.kind : Kind::kNone;
			}
			if (a_rule) *a_rule = exception ? "joins when recruited" : "not an adventurer";
			return Kind::kNone;
		}
	}

	std::string StableKey(const RE::TESForm* a_form)
	{
		if (!a_form) return {};
		if (a_form->IsDynamicForm()) return std::format("FF|0x{:08X}", a_form->GetFormID());
		// "Plugin|local id" of the plugin the form COMES FROM, which its FormID says: the top byte is that plugin's
		// load index (0xFE + three more digits for a light plugin). Not GetFile(0): for a reference that other mods
		// edit, that returned one of the editing plugins on SE 1.5.97 (Jenassa in a list with Interesting NPCs was
		// keyed "3DNPC.esp|0x0E1BA9"), a key that then resolves to nothing - the party could not find its own
		// member, so presence, Bond and Affinities all treated her as unknown.
		const auto  id = a_form->GetFormID();
		auto*       dh = RE::TESDataHandler::GetSingleton();
		const bool  light = (id >> 24) == 0xFE;
		const auto* file = !dh ? nullptr : light ? dh->LookupLoadedLightModByIndex(static_cast<std::uint16_t>((id >> 12) & 0xFFF)) : dh->LookupLoadedModByIndex(static_cast<std::uint8_t>(id >> 24));
		return file ? std::format("{}|0x{:06X}", file->GetFilename(), light ? (id & 0xFFF) : (id & 0xFFFFFF)) : std::format("?|0x{:08X}", id);
	}

	RE::TESForm* FormOfKey(const std::string& a_key)
	{
		const auto bar = a_key.find('|');
		if (bar == std::string::npos) return nullptr;
		const auto    file = a_key.substr(0, bar);
		RE::FormID    id = 0;
		try {
			id = static_cast<RE::FormID>(std::stoul(a_key.substr(bar + 1), nullptr, 16));
		} catch (...) {
			return nullptr;
		}
		if (file == "FF" || file == "?") return RE::TESForm::LookupByID(id);
		auto* dh = RE::TESDataHandler::GetSingleton();
		if (!dh) return nullptr;
		if (auto* f = dh->LookupForm(id, file)) return f;
		// A key from before 1.1.0 may name a plugin that only EDITS the form. The form then belongs to one of that
		// plugin's masters: the same local id, looked up in each of them.
		if (const auto* named = dh->LookupModByName(file); named && named->masterPtrs) {
			for (std::uint32_t i = 0; i < named->masterCount; ++i) {
				const auto* m = named->masterPtrs[i];
				if (!m) continue;
				if (auto* f = dh->LookupForm(id, m->GetFilename())) return f;
			}
		}
		return nullptr;
	}

	namespace
	{
		std::atomic<int> g_keysChanged{ 0 }, g_keysLost{ 0 };
	}

	std::string CanonicalKey(const std::string& a_key)
	{
		if (a_key.empty()) return a_key;
		auto* f = FormOfKey(a_key);
		if (!f) {
			++g_keysLost;
			return a_key;
		}
		auto key = StableKey(f);
		if (key != a_key) {
			++g_keysChanged;
			SKSE::log::info("Adventurers: saved key {} corrected to {}", a_key, key);
		}
		return key;
	}

	std::pair<int, int> TakeKeyStats() { return { g_keysChanged.exchange(0), g_keysLost.exchange(0) }; }

	void Load()
	{
		std::lock_guard l(g_lock);
		g_members.clear();
		g_joinOnRecruit.clear();
		g_chance.clear();
		g_cache.clear();
		try {
			std::ifstream f("Data/SKSE/Plugins/AdventurersGuild/adventurers.resolved.json");
			if (!f) {
				SKSE::log::warn("Adventurers: adventurers.resolved.json missing - only recruited followers will hold a guild rank");
				return;
			}
			auto j = nlohmann::json::parse(f, nullptr, true, true);
			if (j.contains("members")) g_members = Factions(j.at("members"), "members");
			g_liaisons.clear();
			g_liaisonCity.clear();
			if (std::ifstream df("Data/SKSE/Plugins/AdventurersGuild/dialogue.resolved.json"); df) {
				auto dj = nlohmann::json::parse(df, nullptr, true, true);
				auto* dh = RE::TESDataHandler::GetSingleton();
				for (auto& k : dj.value("liaisons", nlohmann::json::array())) {
					const auto key = k.get<std::string>();
					const auto bar = key.find('|');
					if (bar == std::string::npos || !dh) continue;
					if (auto* npc = dh->LookupForm(static_cast<RE::FormID>(std::stoul(key.substr(bar + 1), nullptr, 16)), key.substr(0, bar))) {
						g_liaisons.insert(npc->GetFormID());
						if (dj.contains("cities")) g_liaisonCity[npc->GetFormID()] = dj.at("cities").value(key, "");
					}
				}
				g_successors.clear();
				for (auto& su : dj.value("successors", nlohmann::json::array())) {
					auto* npc = FormOfKey(su.value("npc", ""));
					auto* of = FormOfKey(su.value("of", ""));
					auto* q = FormOfKey(su.value("quest", ""));
					if (!npc || !of || !q || !q->As<RE::TESQuest>()) {
						SKSE::log::warn("Adventurers: a liaison successor does not resolve ({}) - they will not take the counter over", su.dump());
						continue;
					}
					auto* ref = FormOfKey(su.value("ref", ""));
					auto* cell = FormOfKey(su.value("cell", ""));
					if (!ref) {
						SKSE::log::warn("Adventurers: a liaison successor's reference does not resolve - they will not take the counter over");
						continue;
					}
					g_successors.push_back({ npc->GetFormID(), of->GetFormID(), q->As<RE::TESQuest>(), su.value("alias", 0u), ref->GetFormID(),
						cell ? cell->As<RE::TESObjectCELL>() : nullptr, su.value("city", "") });
				}
			}
			if (j.contains("joinOnRecruit")) g_joinOnRecruit = Factions(j.at("joinOnRecruit"), "joinOnRecruit");
			g_joinOnRecruitNpcs.clear();
			if (j.contains("joinOnRecruit"))
				for (auto& k : j.at("joinOnRecruit").value("npcs", nlohmann::json::array()))
					if (auto* f = FormOfKey(k.get<std::string>())) g_joinOnRecruitNpcs.insert(f->GetFormID());
			g_wanderers = {};
			if (j.contains("wanderers")) {
				auto& w = j.at("wanderers");
				for (auto& k : w.value("npcs", nlohmann::json::array()))
					if (auto* f = FormOfKey(k.get<std::string>())) g_wanderers.bases.insert(f->GetFormID());
				for (auto& n : w.value("names", nlohmann::json::array())) g_wanderers.names.push_back(Lower(n.get<std::string>()));
				for (auto& n : w.value("notNames", nlohmann::json::array())) g_wanderers.notNames.push_back(Lower(n.get<std::string>()));
				if (w.contains("not")) g_wanderers.notFactions = Factions(w.at("not"), "wanderers.not");
				SKSE::log::info("Adventurers: {} wandering adventurer bases, {} name words", g_wanderers.bases.size(), g_wanderers.names.size());
			}
			g_wandererNote = j.contains("wanderers") ? j.at("wanderers").value("note", "") : "";
			g_notes.clear();
			for (auto& n : j.value("notes", nlohmann::json::array())) {
				BioNote bn;
				bn.text = n.value("note", "");
				if (n.contains("whenDead")) {
					for (auto& k : n.at("whenDead").value("npcs", nlohmann::json::array()))
						if (auto* f = FormOfKey(k.get<std::string>())) bn.whenDead = f->As<RE::TESNPC>();
					if (!bn.whenDead) continue;  // names someone this game does not have: the line never applies
				}
				for (auto& k : n.value("npcs", nlohmann::json::array()))
					if (auto* f = FormOfKey(k.get<std::string>())) g_notes.emplace(f->GetFormID(), bn);
			}
			SKSE::log::info("Adventurers: {} bio notes", g_notes.size());
			g_named.clear();
			for (auto& n : j.value("named", nlohmann::json::array())) {
				Named nm;
				nm.note = n.value("note", "");
				nm.retiredNote = n.value("retiredNote", "");
				if (const auto r = n.value("rank", ""); !r.empty()) nm.rank = FromLetter(r[0]);
				if (n.contains("retiredWhen")) {
					auto& w = n.at("retiredWhen");
					auto* loc = FormOfKey(w.value("location", ""));
					auto* kw = FormOfKey(w.value("keyword", ""));
					nm.where = loc ? loc->As<RE::BGSLocation>() : nullptr;
					nm.keyword = kw ? kw->As<RE::BGSKeyword>() : nullptr;
					nm.value = w.value("value", 0.0f);
					if (!nm.where || !nm.keyword) SKSE::log::warn("Adventurers: named member's retiredWhen does not resolve - they stay an active member");
				}
				const int level = n.value("level", 0);
				for (auto& k : n.value("npcs", nlohmann::json::array())) {
					auto* f = FormOfKey(k.get<std::string>());
					auto* npc = f ? f->As<RE::TESNPC>() : nullptr;
					if (!npc) continue;
					// the level their rank is read from: raised here, in memory (no plugin edits their record)
					if (level > 0 && npc->actorData.level < level) {
						SKSE::log::info("Adventurers: {} is level {} in the game's records - raised to {} for their Guild rank", npc->GetName(), npc->actorData.level, level);
						npc->actorData.level = static_cast<std::uint16_t>(level);
					}
					g_named[npc->GetFormID()] = nm;
				}
			}
			for (auto& c : j.value("chance", nlohmann::json::array())) {
				ChanceGroup g;
				g.id = c.value("id", std::string("?"));
				const auto kind = c.value("kind", std::string("member"));
				g.kind = kind == "retired" ? Kind::kRetired : kind == "hidden" ? Kind::kHidden : Kind::kMember;
				g.percent = std::clamp(c.value("percent", 0), 0, 100);
				g.factions = Factions(c, g.id.c_str());
				g_chance.push_back(std::move(g));
			}
			SKSE::log::info("Adventurers: {} member factions, {} join-on-recruit factions, {} chance groups, {} named members",
				g_members.size(), g_joinOnRecruit.size(), g_chance.size(), g_named.size());
		} catch (const std::exception& e) {
			SKSE::log::error("Adventurers: adventurers.resolved.json error: {}", e.what());
		}
	}

	Info Of(RE::Actor* a_actor)
	{
		if (!a_actor || a_actor->IsPlayerRef()) return {};
		Kind kind;
		bool joined = false;
		int  pinned = -1;
		{
			std::lock_guard l(g_lock);
			const auto key = StableKey(a_actor);
			auto*      base = a_actor->GetActorBase();
			if (auto nm = base ? g_named.find(base->GetFormID()) : g_named.end(); nm != g_named.end()) {
				kind = nm->second.Retired() ? Kind::kRetired : Kind::kMember;  // asked each time: the world can change it
				pinned = nm->second.rank;
			} else if (g_recruited.contains(key)) {
				kind = Kind::kMember;
			} else if (a_actor->IsPlayerTeammate()) {
				// Anyone travelling with the player is an adventurer. Those who were not already a
				// member (story followers, custom followers with no vanilla faction) register now.
				auto it = g_cache.find(a_actor->GetFormID());
				const Kind before = it != g_cache.end() ? it->second : Decide(a_actor, nullptr);
				joined = before != Kind::kMember;
				g_recruited.insert(key);
				g_cache.erase(a_actor->GetFormID());
				kind = Kind::kMember;
			} else if (auto it = g_cache.find(a_actor->GetFormID()); it != g_cache.end()) {
				kind = it->second;
			} else {
				kind = Decide(a_actor, nullptr);
				g_cache.emplace(a_actor->GetFormID(), kind);
			}
		}
		if (joined) {
			const std::string name = a_actor->GetDisplayFullName();
			SKSE::log::info("Adventurers: {} joined the guild on recruitment", name);
			SKSE::GetTaskInterface()->AddTask([name] {
				RE::SendHUDMessage::ShowHUDMessage(Loc::F("$AG_Hud_Recruited", "{} has registered with the Adventurers Guild.", name).c_str());
			});
		}
		if (kind == Kind::kNone) return {};
		return { kind, pinned >= 0 ? pinned : FromLevel(a_actor->GetLevel()) };
	}

	std::string JoinStatus(RE::Actor* a_actor)
	{
		if (!a_actor || a_actor->IsPlayerRef() || a_actor->IsDead()) return "invalid";
		if (a_actor->IsChild()) return "child";
		if (IsLiaison(a_actor)) return "guild_rep";
		const auto kind = Of(a_actor).kind;  // takes g_lock itself
		if (kind == Kind::kMember) return "member";
		if (kind == Kind::kRetired) return "retired";  // set aside under the Neutrality Oath
		if (a_actor->IsGuard()) return "guard";        // in service: the Oath bars them while they serve
		return "can_join";                             // a hidden (assassin) membership may become an open one
	}

	std::string Join(RE::Actor* a_actor)
	{
		if (const auto why = JoinStatus(a_actor); why != "can_join") return "refused: " + why;
		{
			std::lock_guard l(g_lock);
			g_recruited.insert(StableKey(a_actor));
			g_cache.erase(a_actor->GetFormID());
		}
		const std::string name = a_actor->GetDisplayFullName();
		const int rank = FromLevel(a_actor->GetLevel());
		SKSE::log::info("Adventurers: {} joined the guild of their own accord (rank {})", name, rank);
		SKSE::GetTaskInterface()->AddTask([name] {
			RE::SendHUDMessage::ShowHUDMessage(Loc::F("$AG_Hud_Recruited", "{} has registered with the Adventurers Guild.", name).c_str());
		});
		Guild::Notify("AG_AdventurerJoined", name, static_cast<float>(rank));
		return "joined";
	}

	bool IsWanderer(RE::Actor* a_actor)
	{
		if (!a_actor || a_actor->IsPlayerRef() || a_actor->IsDead()) return false;
		std::lock_guard l(g_lock);
		return WandererLocked(a_actor);
	}

	bool IsLiaison(RE::Actor* a_actor)
	{
		auto* base = a_actor ? a_actor->GetActorBase() : nullptr;
		if (!base) return false;
		std::lock_guard l(g_lock);
		if (g_liaisons.contains(base->GetFormID())) return true;
		for (auto& su : g_successors)
			if (su.npc == base->GetFormID()) return Active(su) == a_actor && AtInn(su, a_actor);  // only at her inn
		return false;
	}

	std::vector<RE::Actor*> SucceededLiaisons()
	{
		std::vector<RE::Actor*> out;
		std::lock_guard          l(g_lock);
		for (auto& su : g_successors)
			if (auto* a = Active(su)) out.push_back(a);
		return out;
	}

	bool IsLiaisonBase(RE::FormID a_base)
	{
		std::lock_guard l(g_lock);
		return g_liaisons.contains(a_base) || std::ranges::any_of(g_successors, [&](const Successor& su) { return su.npc == a_base; });
	}

	std::string LiaisonCity(RE::TESObjectREFR* a_ref)
	{
		auto* actor = a_ref ? a_ref->As<RE::Actor>() : nullptr;
		auto* base = actor ? actor->GetActorBase() : nullptr;
		std::lock_guard l(g_lock);
		auto it = base ? g_liaisonCity.find(base->GetFormID()) : g_liaisonCity.end();
		if (it != g_liaisonCity.end()) return it->second;
		for (auto& su : g_successors)
			if (base && su.npc == base->GetFormID() && Active(su) == actor) return su.city;
		return {};
	}

	std::string Note(RE::Actor* a_actor)
	{
		auto* base = a_actor ? a_actor->GetActorBase() : nullptr;
		std::lock_guard l(g_lock);
		if (!base) return {};
		std::string out;
		const auto  add = [&](const std::string& a_text) {
			if (!a_text.empty()) out += (out.empty() ? "" : " ") + a_text;
		};
		if (auto it = g_named.find(base->GetFormID()); it != g_named.end()) add(it->second.Retired() ? it->second.retiredNote : it->second.note);
		const auto range = g_notes.equal_range(base->GetFormID());
		for (auto n = range.first; n != range.second; ++n)
			if (!n->second.whenDead || HasDied(n->second.whenDead)) add(n->second.text);
		if (out.empty() && !g_wandererNote.empty() && WandererLocked(a_actor)) add(g_wandererNote);
		return out;
	}

	const char* KindName(Kind a_kind)
	{
		switch (a_kind) {
		case Kind::kMember: return "member";
		case Kind::kRetired: return "retired";
		case Kind::kHidden: return "hidden";
		default: return "none";
		}
	}

	std::string Describe(RE::Actor* a_actor)
	{
		if (!a_actor) return "no actor";
		std::string rule;
		{
			std::lock_guard l(g_lock);
			if (g_recruited.contains(StableKey(a_actor))) rule = "recruited (co-save)";
			else if (a_actor->IsPlayerTeammate()) rule = "current teammate";
			else Decide(a_actor, &rule);
		}
		const auto info = Of(a_actor);
		return std::format("{} [{}] level {}: guild={} rank={} threat={} ({})",
			a_actor->GetDisplayFullName(), StableKey(a_actor), a_actor->GetLevel(),
			KindName(info.kind), info.rank >= 0 ? LetterStr(info.rank) : "-", LetterStr(ThreatRank(a_actor)), rule);
	}

	nlohmann::json Save()
	{
		std::lock_guard l(g_lock);
		return nlohmann::json(std::vector<std::string>(g_recruited.begin(), g_recruited.end()));
	}

	void Load(const nlohmann::json& a_j)
	{
		std::lock_guard l(g_lock);
		g_recruited.clear();
		g_cache.clear();
		if (a_j.is_array()) {
			for (auto& k : a_j) g_recruited.insert(CanonicalKey(k.get<std::string>()));  // keys from before 1.1.0 are corrected
		}
	}

	void Revert()
	{
		std::lock_guard l(g_lock);
		g_recruited.clear();
		g_cache.clear();
	}
}
