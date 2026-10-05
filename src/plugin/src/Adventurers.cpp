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
		Kind Decide(RE::Actor* a_actor, std::string* a_rule)
		{
			const bool exception = InAny(a_actor, g_joinOnRecruit);
			if (!exception && InAny(a_actor, g_members)) {
				if (a_rule) *a_rule = "member faction";
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
		const auto* file = a_form->GetFile(0);
		return file ? std::format("{}|0x{:06X}", file->GetFilename(), a_form->GetLocalFormID()) : std::format("?|0x{:08X}", a_form->GetFormID());
	}

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
			}
			if (j.contains("joinOnRecruit")) g_joinOnRecruit = Factions(j.at("joinOnRecruit"), "joinOnRecruit");
			for (auto& c : j.value("chance", nlohmann::json::array())) {
				ChanceGroup g;
				g.id = c.value("id", std::string("?"));
				const auto kind = c.value("kind", std::string("member"));
				g.kind = kind == "retired" ? Kind::kRetired : kind == "hidden" ? Kind::kHidden : Kind::kMember;
				g.percent = std::clamp(c.value("percent", 0), 0, 100);
				g.factions = Factions(c, g.id.c_str());
				g_chance.push_back(std::move(g));
			}
			SKSE::log::info("Adventurers: {} member factions, {} join-on-recruit factions, {} chance groups",
				g_members.size(), g_joinOnRecruit.size(), g_chance.size());
		} catch (const std::exception& e) {
			SKSE::log::error("Adventurers: adventurers.resolved.json error: {}", e.what());
		}
	}

	Info Of(RE::Actor* a_actor)
	{
		if (!a_actor || a_actor->IsPlayerRef()) return {};
		Kind kind;
		bool joined = false;
		{
			std::lock_guard l(g_lock);
			const auto key = StableKey(a_actor);
			if (g_recruited.contains(key)) {
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
		return { kind, FromLevel(a_actor->GetLevel()) };
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

	bool IsLiaison(RE::Actor* a_actor)
	{
		auto* base = a_actor ? a_actor->GetActorBase() : nullptr;
		std::lock_guard l(g_lock);
		return base && g_liaisons.contains(base->GetFormID());
	}

	std::string LiaisonCity(RE::TESObjectREFR* a_ref)
	{
		auto* actor = a_ref ? a_ref->As<RE::Actor>() : nullptr;
		auto* base = actor ? actor->GetActorBase() : nullptr;
		std::lock_guard l(g_lock);
		auto it = base ? g_liaisonCity.find(base->GetFormID()) : g_liaisonCity.end();
		return it == g_liaisonCity.end() ? std::string() : it->second;
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
			for (auto& k : a_j) g_recruited.insert(k.get<std::string>());
		}
	}

	void Revert()
	{
		std::lock_guard l(g_lock);
		g_recruited.clear();
		g_cache.clear();
	}
}
