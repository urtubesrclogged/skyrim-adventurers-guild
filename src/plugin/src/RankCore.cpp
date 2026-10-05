// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "RankCore.h"

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

		g_threat.healthBase = static_cast<float>(ini.GetDoubleValue("Threat", "HealthBase", g_threat.healthBase));
		g_threat.healthPerLevel = static_cast<float>(ini.GetDoubleValue("Threat", "HealthPerLevel", g_threat.healthPerLevel));
		g_threat.tough1 = static_cast<float>(ini.GetDoubleValue("Threat", "ToughRatio1", g_threat.tough1));
		g_threat.tough2 = static_cast<float>(ini.GetDoubleValue("Threat", "ToughRatio2", g_threat.tough2));
		if (CSimpleIniA::TNamesDepend keys; ini.GetAllKeys("ThreatKeywords", keys)) {
			g_threat.keywords.clear();  // the section replaces the built-in list
			for (auto& k : keys) {
				KeywordRule r;
				if (ParseRule(k.pItem, ini.GetValue("ThreatKeywords", k.pItem, ""), r)) g_threat.keywords.push_back(r);
				else SKSE::log::warn("[ThreatKeywords] {}: expected \"+N\" and/or \"floor X\"", k.pItem);
			}
		}
		SKSE::log::info("Threat: health {}+{}/lvl, tough x{} / x{}, {} keyword rule(s)", g_threat.healthBase, g_threat.healthPerLevel,
			g_threat.tough1, g_threat.tough2, g_threat.keywords.size());
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

	ThreatInfo ExplainThreat(RE::Actor* a_actor)
	{
		ThreatInfo t;
		if (!a_actor) return t;
		t.level = a_actor->GetLevel();
		t.byLevel = FromLevel(t.level);

		// toughness
		int tough = 0;
		if (auto* av = a_actor->AsActorValueOwner()) {
			t.health = av->GetPermanentActorValue(RE::ActorValue::kHealth);
			const float expected = g_threat.healthBase + g_threat.healthPerLevel * static_cast<float>(t.level);
			if (expected > 0.0f) t.ratio = t.health / expected;
			if (g_threat.tough2 > 0.0f && t.ratio >= g_threat.tough2) tough = 2;
			else if (g_threat.tough1 > 0.0f && t.ratio >= g_threat.tough1) tough = 1;
		}
		t.bump = tough;
		if (tough) t.why = std::format("tough x{:.1f}", t.ratio);

		// keywords: the largest bump and the highest floor win (they don't stack with toughness)
		auto*       base = a_actor->GetActorBase();
		auto*       race = a_actor->GetRace();
		for (auto& r : g_threat.keywords) {
			const bool has = (base && base->HasApplicableKeywordString(r.keyword)) || (race && race->HasKeywordString(r.keyword));
			if (!has) continue;
			if (r.bump > t.bump) t.bump = r.bump;
			if (r.floor > t.floor) t.floor = r.floor;
			t.why += (t.why.empty() ? "" : ", ") + r.keyword;
		}
		t.rank = std::clamp(std::max(t.byLevel + t.bump, t.floor), 0, kRankCount - 1);
		return t;
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
