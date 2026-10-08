// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "RankCore.h"
#include "Kills.h"
#include <nlohmann/json.hpp>
#include <fstream>

#include <SimpleIni.h>
#include <sstream>

namespace AG
{
	namespace
	{
		std::array<std::atomic<int>, kRankCount - 1> g_min{ 12, 24, 40, 60, 80 };  // read every frame, set from the MCM
		std::atomic<int>                             g_sLevel{ 80 }, g_sDefault{ 80 };
		ThreatTuning g_threat;

		int SnapSLevel(int a_level)
		{
			a_level = std::clamp(a_level, kSLevelMin, kSLevelMax);
			return (a_level + kSLevelStep / 2) / kSLevelStep * kSLevelStep;
		}

		// "+2", "floor C", "+1 floor B", "max B" -> rule; false if nothing usable
		bool ParseRule(const std::string& a_key, std::string a_val, KeywordRule& a_out)
		{
			a_out = { a_key, 0, -1, -1 };
			for (auto& ch : a_val) ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
			std::istringstream in(a_val);
			std::string        tok;
			while (in >> tok) {
				if (tok == "floor") {
					if (in >> tok && !tok.empty()) a_out.floor = FromLetter(tok[0]);
				} else if (tok == "max") {
					if (in >> tok && !tok.empty()) a_out.atMost = FromLetter(tok[0]);
				} else if (tok[0] == '+' || tok[0] == '-' || std::isdigit(static_cast<unsigned char>(tok[0]))) {
					try { a_out.bump = std::stoi(tok); } catch (...) {}
				}
			}
			return a_out.bump != 0 || a_out.floor >= 0 || a_out.atMost >= 0;
		}
	}

	void SetSLevel(int a_level)
	{
		const int s = SnapSLevel(a_level);
		Bands     b;
		b.min = { 12, 24, 36, 48, 60 };  // 60: the table as it was before 1.4.0
		if (s != 60) {
			b.min[2] = static_cast<int>(std::lround(24.0 + (s - 24) * 16.0 / 56.0));
			b.min[3] = static_cast<int>(std::lround(24.0 + (s - 24) * 36.0 / 56.0));
			b.min[4] = s;
		}
		const bool changed = g_sLevel.exchange(s) != s;
		for (int i = 0; i < kRankCount - 1; ++i) g_min[i] = b.min[i];
		if (changed) SKSE::log::info("Bands: S at level {} -> D>={} C>={} B>={} A>={} S>={}", s, b.min[0], b.min[1], b.min[2], b.min[3], b.min[4]);
	}

	int GetSLevel() { return g_sLevel.load(); }
	int DefaultSLevel() { return g_sDefault.load(); }
	int MinLevel(int a_rank) { return a_rank <= 0 ? 1 : g_min[std::min(a_rank, kRankCount - 1) - 1].load(std::memory_order_relaxed); }

	void LoadConfig()
	{
		g_threat = {};
		CSimpleIniA ini;
		ini.SetUnicode();
		if (ini.LoadFile("Data/SKSE/Plugins/AdventurersGuild.ini") < 0) {
			SKSE::log::info("AdventurersGuild.ini not found - using default bands");
			SetSLevel(g_sDefault);
			return;
		}
		g_sDefault = SnapSLevel(static_cast<int>(ini.GetLongValue("Ranks", "SLevel", 80)));
		SetSLevel(g_sDefault);
		SKSE::log::info("Bands: a new game starts with S at level {} (the MCM holds it per save)", g_sDefault.load());

		g_threat.score = ini.GetBoolValue("Threat", "DangerScore", true);
		constexpr const char* scoreKeys[]{ "ScoreD", "ScoreC", "ScoreB", "ScoreA", "ScoreS" };
		for (int i = 0; i < 5; ++i) {
			g_threat.scoreMin[i] = static_cast<float>(ini.GetDoubleValue("Threat", scoreKeys[i], g_threat.scoreMin[i]));
		}
		for (int i = 1; i < 5; ++i) {
			if (g_threat.scoreMin[i] <= g_threat.scoreMin[i - 1]) {
				SKSE::log::warn("AdventurersGuild.ini [Threat] Score* not ascending - reverting to defaults");
				g_threat.scoreMin = ThreatTuning{}.scoreMin;
				break;
			}
		}
		g_threat.raceRules = ini.GetBoolValue("Threat", "RaceRules", true);
		g_threat.sGate = ini.GetBoolValue("Threat", "SGate", true);
		if (const std::string list = ini.GetValue("Threat", "SKeywords", ""); !list.empty()) {
			g_threat.sKeywords.clear();
			std::istringstream in(list);
			for (std::string tok; std::getline(in, tok, ',');) {
				tok.erase(0, tok.find_first_not_of(" \t"));
				tok.erase(tok.find_last_not_of(" \t") + 1);
				if (!tok.empty()) g_threat.sKeywords.push_back(tok);
			}
		}
		g_threat.fantasyTier = static_cast<int>(ini.GetLongValue("Appraisal", "FantasyTier", g_threat.fantasyTier));
		g_threat.highTier = static_cast<int>(ini.GetLongValue("Appraisal", "HighRankTier", g_threat.highTier));
		if (const int r = FromLetter(*ini.GetValue("Appraisal", "HighRank", "A")); r >= 0) g_threat.highRank = r;
		if (const std::string list = ini.GetValue("Appraisal", "FantasyKeywords", ""); !list.empty()) {
			g_threat.fantasyKeywords.clear();
			std::istringstream in(list);
			for (std::string tok; std::getline(in, tok, ',');) {
				tok.erase(0, tok.find_first_not_of(" \t"));
				tok.erase(tok.find_last_not_of(" \t") + 1);
				if (!tok.empty()) g_threat.fantasyKeywords.push_back(tok);
			}
		}
		if (CSimpleIniA::TNamesDepend keys; ini.GetAllKeys("ThreatKeywords", keys)) {
			g_threat.keywords.clear();  // the section replaces the built-in list
			for (auto& k : keys) {
				KeywordRule r;
				if (ParseRule(k.pItem, ini.GetValue("ThreatKeywords", k.pItem, ""), r)) g_threat.keywords.push_back(r);
				else SKSE::log::warn("[ThreatKeywords] {}: expected \"+N\", \"floor X\" and/or \"max X\"", k.pItem);
			}
		}
		SKSE::log::info("Threat: danger score {} (D>={} C>={} B>={} A>={} S>={}), {} keyword rule(s)", g_threat.score ? "on" : "off",
			g_threat.scoreMin[0], g_threat.scoreMin[1], g_threat.scoreMin[2], g_threat.scoreMin[3], g_threat.scoreMin[4], g_threat.keywords.size());
	}

	Bands GetBands()
	{
		Bands b;
		for (int i = 0; i < kRankCount - 1; ++i) b.min[i] = g_min[i].load(std::memory_order_relaxed);
		return b;
	}

	int FromLevel(int a_level)
	{
		int r = 0;
		for (int i = 0; i < 5; ++i) {
			if (a_level >= g_min[i].load(std::memory_order_relaxed)) r = i + 1;
		}
		return r;
	}

	void LoadRaceRules()
	{
		g_threat.races.clear();
		g_threat.actors.clear();
		if (!g_threat.raceRules) {
			SKSE::log::info("Threat: race rules off ([Threat] RaceRules = 0)");
			return;
		}
		try {
			std::ifstream f("Data/SKSE/Plugins/AdventurersGuild/threat.resolved.json");
			if (!f) {
				SKSE::log::warn("Threat: threat.resolved.json missing - no race rules");
				return;
			}
			auto  j = nlohmann::json::parse(f, nullptr, true, true);
			auto* dh = RE::TESDataHandler::GetSingleton();
			for (auto& e : j.value("races", nlohmann::json::array())) {
				const auto key = e.value("race", std::string());
				const auto bar = key.find('|');
				if (bar == std::string::npos || !dh) continue;
				if (auto* race = dh->LookupForm(static_cast<RE::FormID>(std::stoul(key.substr(bar + 1), nullptr, 16)), key.substr(0, bar)))
				{
					RaceRule r;
					if (const auto a = e.value("atLeast", std::string()); !a.empty()) r.atLeast = FromLetter(a[0]);
					if (const auto a = e.value("atMost", std::string()); !a.empty()) r.atMost = FromLetter(a[0]);
					r.fromLevel = e.value("fromLevel", 0);
					g_threat.races[race->GetFormID()] = r;
				}
			}
			for (auto& e : j.value("actors", nlohmann::json::array())) {
				const auto key = e.value("actor", std::string());
				const auto bar = key.find('|');
				const auto a = e.value("atLeast", std::string());
				if (bar == std::string::npos || !dh || a.empty()) continue;
				if (auto* npc = dh->LookupForm(static_cast<RE::FormID>(std::stoul(key.substr(bar + 1), nullptr, 16)), key.substr(0, bar)))
					g_threat.actors[npc->GetFormID()] = FromLetter(a[0]);
			}
			SKSE::log::info("Threat: {} race rule(s), {} named actor(s)", g_threat.races.size(), g_threat.actors.size());
		} catch (const std::exception& e) {
			SKSE::log::error("Threat: threat.resolved.json error: {} - no race rules", e.what());
		}
	}

	namespace
	{
		// the hardest-hitting weapon the actor's record gives it outright (a giant's club); levelled gear is not read
		float CarriedWeaponDamage(RE::TESNPC* a_base)
		{
			float best = 0.0f;
			if (a_base)
				a_base->ForEachContainerObject([&](RE::ContainerObject& a_entry) {
					if (auto* w = a_entry.obj ? a_entry.obj->As<RE::TESObjectWEAP>() : nullptr)
						best = std::max(best, static_cast<float>(w->GetAttackDamage()));
					return RE::BSContainer::ForEachResult::kContinue;
				});
			return best;
		}

		// the strongest Health-damaging effect among the spells and abilities on the actor's record (a flame atronach's
		// firebolt, a netch's shock). Shouts are not read; anything above 250 is taken for a scripted effect and skipped.
		float SpellDamage(RE::TESNPC* a_base)
		{
			float best = 0.0f;
			auto* list = a_base ? a_base->actorEffects : nullptr;
			if (!list || !list->spells) return best;
			for (std::uint32_t i = 0; i < list->numSpells; ++i) {
				auto* spell = list->spells[i];
				if (!spell) continue;
				for (auto* e : spell->effects) {
					auto* m = e ? e->baseEffect : nullptr;
					if (!m || m->data.primaryAV != RE::ActorValue::kHealth) continue;
					using Flag = RE::EffectSetting::EffectSettingData::Flag;
					if (!m->data.flags.all(Flag::kHostile, Flag::kDetrimental)) continue;
					const float mag = e->effectItem.magnitude;
					if (mag > best && mag <= 250.0f) best = mag;
				}
			}
			return best;
		}
	}

	ThreatInfo ExplainThreat(RE::Actor* a_actor)
	{
		ThreatInfo t;
		if (!a_actor) return t;
		t.level = a_actor->GetLevel();
		t.byLevel = FromLevel(t.level);
		auto* base = a_actor->GetActorBase();
		auto* race = a_actor->GetRace();
		if (auto* av = a_actor->AsActorValueOwner()) t.health = av->GetPermanentActorValue(RE::ActorValue::kHealth);

		// danger score: creatures that fight with their own body. People and the creatures that rely on carried
		// weapons (draugr, falmer: unarmed damage 1 on the race) have no meaningful figure and keep their level rank.
		if (g_threat.score && race && race->data.unarmedDamage > 1.0f && !race->HasKeywordString("ActorTypeNPC")) {
			// three normal attacks to one power attack (x1.5); a weapon the record carries adds to the body's own damage
			const float melee = (race->data.unarmedDamage + CarriedWeaponDamage(base)) * 1.125f;
			t.attack = std::max(melee, SpellDamage(base));
			t.score = std::sqrt(std::max(1.0f, t.health) * t.attack);
			t.byScore = 0;
			for (int i = 0; i < 5; ++i)
				if (t.score >= g_threat.scoreMin[i]) t.byScore = i + 1;
			t.bump = std::clamp(t.byScore - t.byLevel, -1, 1);
			if (t.bump) t.why = std::format("score {:.0f} = {}", t.score, Letter(t.byScore));
		}

		const auto has = [&](const std::string& a_kw) { return (base && base->HasApplicableKeywordString(a_kw)) || (race && race->HasKeywordString(a_kw)); };
		const auto add = [&](std::string a_text) { t.why += (t.why.empty() ? "" : ", ") + a_text; };

		// keywords: the largest adjustment, the highest floor and the lowest ceiling win (a keyword bump does not stack
		// with the score)
		int ceiling = -1;
		for (auto& r : g_threat.keywords) {
			if (!has(r.keyword)) continue;
			if (r.bump > t.bump) t.bump = r.bump;
			if (r.floor > t.floor) t.floor = r.floor;
			if (r.atMost >= 0 && (ceiling < 0 || r.atMost < ceiling)) ceiling = r.atMost;
			if (r.bump || r.floor >= 0) add(r.keyword);
		}
		t.rank = std::clamp(std::max(t.byLevel + t.bump, t.floor), 0, kRankCount - 1);

		// judgement calls by race: they hold whatever the level and the score say, and a race's own ceiling replaces
		// the one its keywords gave it (a troll is wildlife to the game, and may still reach A)
		bool listed = false;
		if (g_threat.raceRules && race)
			if (auto it = g_threat.races.find(race->GetFormID()); it != g_threat.races.end()) {
				const auto& r = it->second;
				if (r.atLeast > t.rank && t.level >= r.fromLevel) {
					t.rank = r.atLeast;
					add(std::format("at least {} for its kind", Letter(t.rank)));
				}
				if (r.atLeast == kRankCount - 1 && t.level >= r.fromLevel) listed = true;
				if (r.atMost >= 0) ceiling = r.atMost;
			}
		if (ceiling >= 0 && ceiling < t.rank) {
			t.rank = ceiling;
			add(std::format("at most {} for its kind", Letter(t.rank)));
		}
		// ... and by name: the few that are what they are at any level
		if (g_threat.raceRules && base)
			if (auto it = g_threat.actors.find(base->GetFormID()); it != g_threat.actors.end()) {
				if (it->second > t.rank) {
					t.rank = it->second;
					add(std::format("{} by name", Letter(t.rank)));
				}
				if (it->second == kRankCount - 1) listed = true;
			}

		// Rank S is never reached by level alone: listed, or proven
		if (g_threat.sGate && t.rank == kRankCount - 1 && !listed) {
			for (auto& k : g_threat.sKeywords)
				if (has(k)) { listed = true; break; }
			if (!listed) {
				bool proven = t.byLevel == kRankCount - 1;
				if (proven) {
					if (race && race->HasKeywordString("ActorTypeNPC")) proven = base && base->IsUnique() && Kills::IsBoss(a_actor);
					else proven = t.byScore == kRankCount - 1;
				}
				if (!proven) {
					t.rank = kRankCount - 2;
					add("S not proven");
				}
			}
		}
		return t;
	}

	int FantasyTier() { return g_threat.fantasyTier; }

	bool IsFantasy(RE::Actor* a_actor)
	{
		auto* base = a_actor ? a_actor->GetActorBase() : nullptr;
		auto* race = a_actor ? a_actor->GetRace() : nullptr;
		if (!race) return false;
		const auto has = [&](const std::string& a_kw) { return race->HasKeywordString(a_kw) || (base && base->HasApplicableKeywordString(a_kw)); };
		for (auto& k : g_threat.fantasyKeywords)
			if (has(k)) return true;
		// what is left is fantasy unless the game calls it a person or an animal (a spriggan, a hagraven, a werewolf)
		return !has("ActorTypeNPC") && !has("ActorTypeAnimal");
	}

	bool ThreatReadable(RE::Actor* a_actor, int a_threat, int a_appraisal)
	{
		if (g_threat.highTier > 0 && a_appraisal < g_threat.highTier && a_threat >= g_threat.highRank) return false;
		if (g_threat.fantasyTier > 0 && a_appraisal < g_threat.fantasyTier && IsFantasy(a_actor)) return false;
		return true;
	}

	int ThreatRank(RE::Actor* a_actor)
	{
		return a_actor ? ExplainThreat(a_actor).rank : -1;
	}

	char Letter(int a_rank)
	{
		constexpr char l[] = "EDCBAS";
		return (a_rank >= 0 && a_rank < kRankCount) ? l[a_rank] : '?';
	}

	std::string LetterStr(int a_rank) { return std::string(1, Letter(a_rank)); }

	int FromLetter(char a_letter)
	{
		const auto pos = std::string_view("EDCBAS").find(static_cast<char>(std::toupper(static_cast<unsigned char>(a_letter))));
		return pos == std::string_view::npos ? -1 : static_cast<int>(pos);
	}
}
