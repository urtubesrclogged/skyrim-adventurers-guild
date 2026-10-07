// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "RankCore.h"
#include <nlohmann/json.hpp>
#include <fstream>

#include <SimpleIni.h>
#include <sstream>

namespace AG
{
	namespace
	{
		Bands        g_bands;
		ThreatTuning g_threat;

		// "+2", "floor C", "+1 floor B" -> rule; false if nothing usable
		bool ParseRule(const std::string& a_key, std::string a_val, KeywordRule& a_out)
		{
			a_out = { a_key, 0, -1 };
			for (auto& ch : a_val) ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
			std::istringstream in(a_val);
			std::string        tok;
			while (in >> tok) {
				if (tok == "floor") {
					if (in >> tok && !tok.empty()) a_out.floor = FromLetter(tok[0]);
				} else if (tok[0] == '+' || tok[0] == '-' || std::isdigit(static_cast<unsigned char>(tok[0]))) {
					try { a_out.bump = std::stoi(tok); } catch (...) {}
				}
			}
			return a_out.bump != 0 || a_out.floor >= 0;
		}
	}

	void LoadConfig()
	{
		g_bands = {};
		g_threat = {};
		CSimpleIniA ini;
		ini.SetUnicode();
		if (ini.LoadFile("Data/SKSE/Plugins/AdventurersGuild.ini") < 0) {
			SKSE::log::info("AdventurersGuild.ini not found - using default bands");
			return;
		}
		constexpr const char* keys[]{ "D", "C", "B", "A", "S" };
		for (int i = 0; i < 5; ++i) {
			g_bands.min[i] = static_cast<int>(ini.GetLongValue("Bands", keys[i], g_bands.min[i]));
		}
		// enforce strictly ascending so a bad ini cannot make ranks non-monotonic
		for (int i = 1; i < 5; ++i) {
			if (g_bands.min[i] <= g_bands.min[i - 1]) {
				SKSE::log::warn("AdventurersGuild.ini bands not ascending - reverting to defaults");
				g_bands = {};
				break;
			}
		}
		SKSE::log::info("Bands: D>={} C>={} B>={} A>={} S>={}", g_bands.min[0], g_bands.min[1], g_bands.min[2], g_bands.min[3], g_bands.min[4]);

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
		g_threat.fantasyTier = static_cast<int>(ini.GetLongValue("Appraisal", "FantasyTier", g_threat.fantasyTier));
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
				else SKSE::log::warn("[ThreatKeywords] {}: expected \"+N\" and/or \"floor X\"", k.pItem);
			}
		}
		SKSE::log::info("Threat: danger score {} (D>={} C>={} B>={} A>={} S>={}), {} keyword rule(s)", g_threat.score ? "on" : "off",
			g_threat.scoreMin[0], g_threat.scoreMin[1], g_threat.scoreMin[2], g_threat.scoreMin[3], g_threat.scoreMin[4], g_threat.keywords.size());
	}

	const Bands& GetBands() { return g_bands; }

	int FromLevel(int a_level)
	{
		int r = 0;
		for (int i = 0; i < 5; ++i) {
			if (a_level >= g_bands.min[i]) r = i + 1;
		}
		return r;
	}

	void LoadRaceRules()
	{
		g_threat.races.clear();
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
			SKSE::log::info("Threat: {} race rule(s)", g_threat.races.size());
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

		// keywords: the largest adjustment and the highest floor win (a keyword bump does not stack with the score)
		for (auto& r : g_threat.keywords) {
			const bool has = (base && base->HasApplicableKeywordString(r.keyword)) || (race && race->HasKeywordString(r.keyword));
			if (!has) continue;
			if (r.bump > t.bump) t.bump = r.bump;
			if (r.floor > t.floor) t.floor = r.floor;
			t.why += (t.why.empty() ? "" : ", ") + r.keyword;
		}
		t.rank = std::clamp(std::max(t.byLevel + t.bump, t.floor), 0, kRankCount - 1);

		// judgement calls by race, last: they hold whatever the level and the score say
		if (g_threat.raceRules && race)
			if (auto it = g_threat.races.find(race->GetFormID()); it != g_threat.races.end()) {
				const auto& r = it->second;
				if (r.atLeast > t.rank && t.level >= r.fromLevel) {
					t.rank = r.atLeast;
					t.why += (t.why.empty() ? "" : ", ") + std::format("at least {} for its kind", Letter(t.rank));
				}
				if (r.atMost >= 0 && r.atMost < t.rank) {
					t.rank = r.atMost;
					t.why += (t.why.empty() ? "" : ", ") + std::format("at most {} for its kind", Letter(t.rank));
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
