#include "Diag.h"

#include "Counter.h"

#include <SimpleIni.h>
#include <Windows.h>

#include <filesystem>

namespace AG::Diag
{
	namespace
	{
		std::atomic<bool> g_ini{ false }, g_mcm{ false };
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
		SKSE::log::info("Environment: {} {}, SKSE {}.{}.{}, Adventurers Guild {}.{}.{}, detailed log {}", edition, game.version().string("."),
			(g_skse >> 24) & 0xFF, (g_skse >> 16) & 0xFF, (g_skse >> 4) & 0xFFF, AG_VERSION_MAJOR, AG_VERSION_MINOR, AG_VERSION_PATCH,
			g_ini.load() || g_mcm.load() ? "on" : "off");
		SKSE::log::info("Environment: AdventurersGuild.esp {}", Plugin("AdventurersGuild.esp"));
		// required
		SKSE::log::info("Environment: PrismaUI {} (the counter and notices need it)", Module(L"PrismaUI.dll"));
		SKSE::log::info("Environment: SkyUI_SE.esp {} (the MCM needs it)", Plugin("SkyUI_SE.esp"));
		if (REL::Module::IsVR()) {
			SKSE::log::info("Environment: Skyrim VR ESL Support {} (VR needs it for a light plugin)", Module(L"skyrimvresl.dll"));
			SKSE::log::info("Environment: VR runtime {}", Counter::IsOpenComposite() ? "OpenComposite" : "SteamVR");
		}
		// optional integrations
		SKSE::log::info("Environment: optional - Missives.esp {}; notice board.esp {}; SkyrimNet {}", Plugin("Missives.esp"), Plugin("notice board.esp"),
			Module(L"SkyrimNet.dll"));
	}

	bool DetailedLog() { return g_mcm.load(); }

	void SetDetailedLog(bool a_on)
	{
		if (g_mcm.exchange(a_on) != a_on) {
			Apply();
			SKSE::log::info("Detailed log {} (MCM)", a_on ? "on" : (g_ini.load() ? "off in the MCM, still on from AdventurersGuild.ini" : "off"));
		}
	}
}
