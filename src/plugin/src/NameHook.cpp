// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "NameHook.h"

#include "Loc.h"

#include "Adventurers.h"
#include "Guild.h"
#include "RankCore.h"

#include <SimpleIni.h>
#include <intrin.h>
#include <mutex>
#include <unordered_map>
#include <unordered_set>

namespace AG::Names
{
	namespace
	{
		using Fn = const char* (*)(RE::TESObjectREFR*);

		Fn             g_orig{ nullptr };
		std::uintptr_t g_base{ 0 };
		std::atomic<int> g_mode{ 1 };

		std::mutex g_lock;

		struct Site
		{
			std::uint32_t count{ 0 };
			std::string   sample;
			bool          actor{ false };
		};
		std::unordered_map<std::uint32_t, Site> g_sites;  // keyed by return-address RVA
		enum class SiteKind : std::uint8_t { kPrompt, kMeter };
		std::unordered_map<std::uint32_t, SiteKind> g_allow;  // configured call sites and what they show
		std::atomic<bool> g_showGuild{ true };   // "(C)" on adventurers at the interact prompt
		std::atomic<bool> g_showThreat{ true };  // "[C]" threat / "(C)" guild rank on the enemy health meter
		std::unordered_set<std::string>         g_intern;  // node-based: pointers stay valid forever

		const char* Intern(const std::string& a_s)
		{
			std::lock_guard l(g_lock);
			return g_intern.insert(a_s).first->c_str();
		}

		__declspec(noinline) const char* Thunk(RE::TESObjectREFR* a_ref)
		{
			const auto ra = static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(_ReturnAddress()) - g_base);
			const char* name = g_orig(a_ref);
			if (!a_ref || !name || !*name) return name;

			auto* actor = a_ref->As<RE::Actor>();
			if (!actor) return name;

			{
				std::lock_guard l(g_lock);
				auto& s = g_sites[ra];
				++s.count;
				s.actor = true;
				if (s.sample.empty()) s.sample = name;
			}

			const int mode = g_mode.load(std::memory_order_relaxed);
			if (mode == 0 || actor->IsPlayerRef()) return name;
			SiteKind kind = SiteKind::kMeter;  // mode 1 (debug: every site) uses the meter style
			if (mode == 2) {
				std::lock_guard l(g_lock);
				auto it = g_allow.find(ra);
				if (it == g_allow.end()) return name;
				kind = it->second;
			}

			// Ranks are read through the Appraisal skill: without it, no labels at all.
			const int appraisal = Guild::AppraisalLevel();
			if (appraisal < 1) return name;

			// Guild rank belongs to adventurers only; everything else you fight carries a threat rank.
			// Appraisal III also sees through a hidden (assassin's) membership.
			const auto info = Adventurers::Of(actor);
			const bool covert = info.kind == Adventurers::Kind::kHidden && appraisal >= 3;
			const bool guild = info.kind == Adventurers::Kind::kMember || info.kind == Adventurers::Kind::kRetired || covert;
			// translated once (names are formatted every frame): "Lydia (C, retired)"
			static const std::string kRetired = Loc::T("$AG_Name_Retired", ", retired"), kCovert = Loc::T("$AG_Name_Covert", ", covert");
			const char* retired = info.kind == Adventurers::Kind::kRetired ? kRetired.c_str() : covert ? kCovert.c_str() : "";
			if (kind == SiteKind::kPrompt) {
				if (!guild || !g_showGuild.load(std::memory_order_relaxed)) return name;
				return Intern(std::format("{} ({}{})", name, Letter(info.rank), retired));
			}
			if (!g_showThreat.load(std::memory_order_relaxed)) return name;
			if (guild) return Intern(std::format("{} ({}{})", name, Letter(info.rank), retired));
			const int threat = ThreatRank(actor);
			return threat < 0 ? name : Intern(std::format("{} [{}]", name, Letter(threat)));
		}

		void LoadIni()
		{
			CSimpleIniA ini;
			ini.SetUnicode();
			if (ini.LoadFile("Data/SKSE/Plugins/AdventurersGuild.ini") < 0) return;
			g_mode = static_cast<int>(ini.GetLongValue("Names", "Mode", 1));
			// the starting value of the MCM's one label switch (the MCM, once in a save, sets these itself)
			g_showGuild = g_showThreat = ini.GetBoolValue("System", "ShowRankLabels", true);
			// Call-site RVAs are specific to one game executable, so each runtime has its own lists.
			const char* rt = REL::Module::IsVR() ? "VR" : (REL::Module::IsAE() ? "AE" : "SE");
			auto read = [&](const char* a_prefix, SiteKind a_kind) {
				const auto key = std::string(a_prefix) + rt;
				std::stringstream ss(ini.GetValue("Names", key.c_str(), ""));
				std::string tok;
				int n = 0;
				while (std::getline(ss, tok, ',')) {
					try {
						g_allow[static_cast<std::uint32_t>(std::stoul(tok, nullptr, 0))] = a_kind;
						++n;
					} catch (...) {}
				}
				if (!n) SKSE::log::warn("Names: no {} list in AdventurersGuild.ini - that rank display will not appear", key);
			};
			read("Prompt", SiteKind::kPrompt);
			read("Meter", SiteKind::kMeter);
		}
	}

	void Install()
	{
		LoadIni();

		const auto target = REL::RelocationID(19354, 19781).address();
		if (!target) {
			SKSE::log::error("Names: GetDisplayFullName address not resolvable on this runtime");
			return;
		}
		g_orig = reinterpret_cast<Fn>(target);
		g_base = REL::Module::get().base();

		const auto text = REL::Module::get().segment(REL::Segment::textx);
		const auto* p = static_cast<const std::uint8_t*>(text.pointer());
		const auto  size = text.size();
		std::vector<std::uintptr_t> sites;
		for (std::size_t i = 0; i + 5 <= size; ++i) {
			if (p[i] != 0xE8) continue;
			std::int32_t rel;
			std::memcpy(&rel, p + i + 1, 4);
			if (text.address() + i + 5 + static_cast<std::intptr_t>(rel) == target) sites.push_back(text.address() + i);
		}
		SKSE::log::info("Names: GetDisplayFullName @ base+0x{:X}, {} direct call sites found", target - g_base, sites.size());
		if (sites.empty()) return;

		SKSE::AllocTrampoline(sites.size() * 14 + 64);
		auto& tr = SKSE::GetTrampoline();
		for (auto s : sites) {
			tr.write_call<5>(s, reinterpret_cast<std::uintptr_t>(&Thunk));
		}
		SKSE::log::info("Names: patched {} sites, mode {}", sites.size(), g_mode.load());
	}

	void SetMode(int a_mode) { g_mode = std::clamp(a_mode, 0, 2); }
	void SetShowGuild(bool a_on) { g_showGuild = a_on; }
	bool ShowGuild() { return g_showGuild.load(); }
	void SetShowThreat(bool a_on) { g_showThreat = a_on; }
	bool ShowThreat() { return g_showThreat.load(); }
	int  GetMode() { return g_mode.load(); }

	void AllowSite(int a_rva, bool a_on)
	{
		std::lock_guard l(g_lock);
		if (a_on) g_allow[static_cast<std::uint32_t>(a_rva)] = SiteKind::kMeter;
		else g_allow.erase(static_cast<std::uint32_t>(a_rva));
	}

	void ClearAllowed()
	{
		std::lock_guard l(g_lock);
		g_allow.clear();
	}

	void ResetCounts()
	{
		std::lock_guard l(g_lock);
		g_sites.clear();
	}

	std::vector<std::string> SiteReport()
	{
		std::vector<std::pair<std::uint32_t, Site>> v;
		{
			std::lock_guard l(g_lock);
			v.assign(g_sites.begin(), g_sites.end());
		}
		std::ranges::sort(v, [](auto& a, auto& b) { return a.second.count > b.second.count; });
		std::vector<std::string> out;
		for (auto& [rva, s] : v) {
			if (out.size() >= 100) break;  // Papyrus arrays cap at 128
			out.push_back(std::format("{}|{}|{}|{}", static_cast<std::int32_t>(rva), s.count, s.sample, s.actor ? "A" : "-"));
		}
		return out;
	}
}
