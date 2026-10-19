// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "Diag.h"

#include "Counter.h"
#include "Loc.h"
#include "MissiveWatch.h"
#include "NoticeWatch.h"

#include <SimpleIni.h>
#include <Windows.h>

#include <filesystem>

namespace AG::Diag
{
	namespace
	{
		std::atomic<bool> g_ini{ false }, g_mcm{ false };
		std::atomic<bool> g_skyrimNet{ false };  // AG_SkyrimNetInit registered every decorator with SkyrimNet this session
		std::uint32_t     g_skse = 0;

		void Apply()
		{
			const auto level = g_ini.load() || g_mcm.load() ? spdlog::level::debug : spdlog::level::info;
			spdlog::set_level(level);
			spdlog::flush_on(level);
		}

		// "1.5.0.0, 1970176 bytes" for a loaded DLL: the size tells builds apart when the author never bumped the version
		std::string Module(const wchar_t* a_name)
		{
			auto* mod = GetModuleHandleW(a_name);
			if (!mod) return "not loaded";
			wchar_t path[MAX_PATH]{};
			if (!GetModuleFileNameW(mod, path, MAX_PATH)) return "loaded";
			std::error_code ec;
			const auto      size = std::filesystem::file_size(path, ec);
			const auto      ver = REL::GetFileVersion(path);
			return std::format("{}, {} bytes", ver ? ver->string(".") : "no version info", ec ? 0 : size);
		}

		std::string Plugin(std::string_view a_name)
		{
			auto*       data = RE::TESDataHandler::GetSingleton();
			const auto* file = data ? data->LookupModByName(a_name) : nullptr;
			if (!file || file->GetCompileIndex() == 0xFF) return "not active";
			return file->IsLight() ? std::format("active, light plugin FE:{:03X}", file->GetSmallFileCompileIndex())
			                       : std::format("active, full plugin {:02X}", file->GetCompileIndex());
		}
	}

	Timed::~Timed()
	{
		const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - _from).count();
		if (ms < _limit) return;
		static std::mutex                 lock;
		static std::map<const char*, int> times;  // by the literal's address: one entry for each place that is timed
		int                               n;
		{
			std::lock_guard l(lock);
			n = ++times[_what];
		}
		if (n <= 5 || n % 50 == 0)
			SKSE::log::warn("Slow: {} took {} ms ({} time(s) this session, counted from {} ms) - a hitch of that length at this moment is this mod's doing", _what, ms, n, _limit);
	}

	void Init(std::uint32_t a_skseVersion)
	{
		g_skse = a_skseVersion;
		CSimpleIniA ini;
		ini.SetUnicode();
		if (ini.LoadFile("Data/SKSE/Plugins/AdventurersGuild.ini") >= 0) g_ini = ini.GetBoolValue("Debug", "DetailedLog", false);
		Apply();
	}

	void LogEnvironment()
	{
		const auto& game = REL::Module::get();
		const char* edition = REL::Module::IsVR() ? "Skyrim VR" : REL::Module::IsAE() ? "Skyrim AE" : "Skyrim SE";
		SKSE::log::info("Environment: {} {}, SKSE {}.{}.{}, Adventurers Guild {}.{}.{}{}, detailed log {}", edition, game.version().string("."),
			(g_skse >> 24) & 0xFF, (g_skse >> 16) & 0xFF, (g_skse >> 4) & 0xFFF, AG_VERSION_MAJOR, AG_VERSION_MINOR, AG_VERSION_PATCH, AG_VERSION_LABEL,
			g_ini.load() || g_mcm.load() ? "on" : "off");
		SKSE::log::info("Environment: AdventurersGuild.esp {}", Plugin("AdventurersGuild.esp"));
		SKSE::log::info("Environment: SkyUI_SE.esp {} (the MCM needs it)", Plugin("SkyUI_SE.esp"));
		// The weight of the load order, and whether another plugin's version of one of this mod's own records wins
		if (auto* dh = RE::TESDataHandler::GetSingleton()) {
			const auto*              ours = dh->LookupModByName("AdventurersGuild.esp");
			std::vector<std::string> changed;
			const auto               look = [&](RE::TESForm* a_form) {
				if (!ours || !a_form || a_form->GetFile(0) != ours) return;
				if (const auto* last = a_form->GetFile(-1); last && last != ours) changed.push_back(std::format("{:08X} by {}", a_form->GetFormID(), last->GetFilename()));
			};
			for (auto* f : dh->GetFormArray<RE::TESQuest>()) look(f);
			for (auto* f : dh->GetFormArray<RE::TESTopic>()) look(f);
			for (auto* f : dh->GetFormArray<RE::TESGlobal>()) look(f);
			std::string list;
			for (std::size_t i = 0; i < changed.size() && i < 6; ++i) list += (i ? ", " : "") + changed[i];
			if (changed.empty())
				SKSE::log::info("Environment: {} full and {} light plugins active; no other plugin changes this mod's quests, topics or globals", dh->GetLoadedModCount(), dh->GetLoadedLightModCount());
			else
				SKSE::log::warn("Environment: {} full and {} light plugins active; ANOTHER PLUGIN CHANGES {} of this mod's quests, topics or globals: {}{}", dh->GetLoadedModCount(),
					dh->GetLoadedLightModCount(), changed.size(), list, changed.size() > 6 ? ", ..." : "");
		}
		if (REL::Module::IsVR()) {
			SKSE::log::info("Environment: Skyrim VR ESL Support {} (VR needs it for a light plugin)", Module(L"skyrimvresl.dll"));
			SKSE::log::info("Environment: VR runtime {}", Counter::IsOpenComposite() ? "OpenComposite" : "SteamVR");
		}
		// optional integrations
		SKSE::log::info("Environment: optional - Missives.esp {}; notice board.esp {}; SkyrimNet {}", Plugin("Missives.esp"), Plugin("notice board.esp"),
			Module(L"SkyrimNet.dll"));
	}

	std::vector<std::pair<std::string, std::string>> Integrations()
	{
		auto*      data = RE::TESDataHandler::GetSingleton();
		const auto plugin = [&](std::string_view a_name) {
			const auto* file = data ? data->LookupModByName(a_name) : nullptr;
			return file && file->GetCompileIndex() != 0xFF;
		};
		const auto none = Loc::T("$AG_MCM_Int_None", "Not Detected");
		const auto active = Loc::T("$AG_MCM_Int_Active", "Active");
		const auto inactive = Loc::T("$AG_MCM_Int_Inactive", "Inactive");
		std::vector<std::pair<std::string, std::string>> out;
		// optional: what this mod acted on, not only what is in the load order
		out.emplace_back("Missives", !plugin("Missives.esp") ? none : MissiveWatch::Active() ? active : inactive);
		// only with Missives itself: it adds to Missives' boards
		out.emplace_back("Missives - Voice and Quest Expansion", MissiveWatch::ExpansionState() == 2 ? active : MissiveWatch::ExpansionState() == 1 ? inactive : none);
		out.emplace_back("Missives - Worldspace Additions", MissiveWatch::WorldspaceState() == 2 ? active : MissiveWatch::WorldspaceState() == 1 ? inactive : none);
		out.emplace_back("Monster Hunt Missives", MissiveWatch::MonsterHuntState() == 2 ? active : MissiveWatch::MonsterHuntState() == 1 ? inactive : none);
		out.emplace_back("The Notice Board", !plugin("notice board.esp") ? none : NoticeWatch::Active() ? active : inactive);
		out.emplace_back("SkyrimNet", !GetModuleHandleW(L"SkyrimNet.dll") ? none : g_skyrimNet.load() ? active : inactive);
		return out;
	}

	void SetSkyrimNetReady(bool a_ready) { g_skyrimNet = a_ready; }

	bool DetailedLog() { return g_mcm.load(); }

	void SetDetailedLog(bool a_on)
	{
		if (g_mcm.exchange(a_on) != a_on) {
			Apply();
			SKSE::log::info("Detailed log {} (MCM)", a_on ? "on" : (g_ini.load() ? "off in the MCM, still on from AdventurersGuild.ini" : "off"));
		}
	}
}
