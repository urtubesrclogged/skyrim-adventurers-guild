#include "ControlsGuard.h"
#include "Adventurers.h"
#include "Counter.h"
#include "Diag.h"
#include "Dungeons.h"
#include "Guild.h"
#include "Party.h"
#include "Kills.h"
#include "Loc.h"
#include "LevelDisplay.h"
#include "MissiveWatch.h"
#include "NameHook.h"
#include "NoticeWatch.h"
#include "Papyrus.h"
#include "PrismaToast.h"
#include "RankCore.h"
#include "Shop.h"

#include <spdlog/sinks/basic_file_sink.h>

namespace
{
	void InitLog()
	{
		auto path = SKSE::log::log_directory();
		if (!path) return;
		*path /= "AdventurersGuild.log";
		auto sink = std::make_shared<spdlog::sinks::basic_file_sink_mt>(path->string(), true);
		auto log = std::make_shared<spdlog::logger>("global", std::move(sink));
		spdlog::set_default_logger(std::move(log));
		spdlog::set_level(spdlog::level::info);
		spdlog::flush_on(spdlog::level::info);
	}

	void OnMessage(SKSE::MessagingInterface::Message* a_msg)
	{
		switch (a_msg->type) {
		case SKSE::MessagingInterface::kPostLoad:
			break;
		case SKSE::MessagingInterface::kDataLoaded:
			AG::Diag::LogEnvironment();
			AG::Loc::Load();
			AG::LoadConfig();
			AG::Guild::LoadConfig();
			AG::Party::LoadConfig();
			AG::Adventurers::Load();
			AG::Shop::Load();
			AG::Guild::Register();
			AG::LevelDisplay::Register();
			AG::PrismaToast::Install();
			AG::Counter::Install();
			AG::MissiveWatch::Register();
			AG::NoticeWatch::Register();
			AG::Dungeons::Install();
			AG::Kills::Register();
			AG::Party::Register();
			SKSE::log::info("Data loaded; sinks registered");
			break;
		case SKSE::MessagingInterface::kPostLoadGame:
		case SKSE::MessagingInterface::kNewGame:
			AG::Guild::OnGameLoaded();
			AG::ControlsGuard::OnGameLoaded();
			AG::MissiveWatch::WithdrawAboveRank();
			AG::NoticeWatch::WithdrawAboveRank();
			SKSE::log::info("Game loaded: player level {}, {}", RE::PlayerCharacter::GetSingleton()->GetLevel(), AG::Guild::Dump());
			break;
		default:
			break;
		}
	}
}

SKSEPluginInfo(
	.Version = { AG_VERSION_MAJOR, AG_VERSION_MINOR, AG_VERSION_PATCH, 0 },  // from project(VERSION) in CMakeLists.txt
	.Name = "AdventurersGuild",
	.Author = "urtubesrclogged",
	.RuntimeCompatibility = SKSE::VersionIndependence::AddressLibrary)

SKSEPluginLoad(const SKSE::LoadInterface* a_skse)
{
	SKSE::Init(a_skse);
	InitLog();
	AG::Diag::Init(a_skse->SKSEVersion());
	SKSE::log::info("Adventurers Guild {}.{}.{} loading (runtime {})", AG_VERSION_MAJOR, AG_VERSION_MINOR, AG_VERSION_PATCH, a_skse->RuntimeVersion().string());

	AG::LoadConfig();
	AG::Names::Install();
	AG::Guild::SetupSerialization();
	SKSE::GetMessagingInterface()->RegisterListener(OnMessage);
	SKSE::GetPapyrusInterface()->Register(AG::RegisterPapyrus);
	return true;
}
