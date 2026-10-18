// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "ControlsGuard.h"
#include "Adventurers.h"
#include "BountyWatch.h"
#include "Counter.h"
#include "SteamVRAim.h"
#include "ChoiceSwap.h"
#include "Diag.h"
#include "MemberCards.h"
#include "Dungeons.h"
#include "GuildCard.h"
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

	// A save has been read (or a new game begun): the Guild catches up with it.
	void GameLoaded(bool a_newGame)
	{
		const AG::Diag::Timed timed("the work done once a game is loaded", 250);
		AG::Guild::OnGameLoaded();
		AG::Guild::SyncSuccessors();
		AG::MissiveWatch::OnGameLoaded();
		AG::GuildCard::Sync(false);  // a member from before 1.2.0, or one who lost theirs, gets a card
		AG::ControlsGuard::OnGameLoaded();
		AG::Dungeons::OnGameLoaded();
		// Taking a posted job down cannot be undone, and here it would be done on what the save said a moment ago.
		// Only a save read whole is believed; otherwise it waits until the player walks up to a board.
		if (AG::Guild::SaveState() == AG::Guild::SaveData::kClean) {
			AG::MissiveWatch::WithdrawAboveRank();
			AG::NoticeWatch::WithdrawAboveRank();
		} else {
			SKSE::log::info("Game loaded without the Guild's own record ({}): posted jobs are left as they are until a board is visited",
				a_newGame ? "a new game" : AG::Guild::SaveState() == AG::Guild::SaveData::kBroken ? "it could not be read" : "this save has none");
		}
		SKSE::log::info("Game loaded: player level {}, {}", RE::PlayerCharacter::GetSingleton()->GetLevel(), AG::Guild::Dump());
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
			AG::LoadRaceRules();
			AG::Counter::Install();
			AG::MemberCards::Install();  // the other adventurers' guild cards
			AG::ChoiceSwap::Install();  // Show Guild Card: our choice in place of a vanilla one, with no vanilla record
			AG::SteamVRAim::Install();  // native SteamVR: Prisma UI 1.5.1's lasers need aim poses nobody else gives it
			AG::GuildCard::Install();
			AG::MissiveWatch::Register();
			AG::NoticeWatch::Register();
			AG::BountyWatch::Register();
			AG::Dungeons::Install();
			AG::Kills::Register();
			AG::Party::Register();
			SKSE::log::info("Data loaded; sinks registered");
			break;
		case SKSE::MessagingInterface::kPreLoadGame:
			// the one line that tells a load that never ends from one that does: "Game loaded" follows it, or nothing does
			SKSE::log::info("Loading a save");
			break;
		case SKSE::MessagingInterface::kPostLoadGame:
		case SKSE::MessagingInterface::kNewGame:
			GameLoaded(a_msg->type == SKSE::MessagingInterface::kNewGame);
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
	SKSE::log::info("Adventurers Guild {}.{}.{}{} loading (runtime {})", AG_VERSION_MAJOR, AG_VERSION_MINOR, AG_VERSION_PATCH, AG_VERSION_LABEL, a_skse->RuntimeVersion().string());

	AG::LoadConfig();
	SKSE::AllocTrampoline(4096);  // one for the whole plugin: the name hook's call sites, and ChoiceSwap's two
	AG::Names::Install();
	AG::Guild::SetupSerialization();
	SKSE::GetMessagingInterface()->RegisterListener(OnMessage);
	SKSE::GetPapyrusInterface()->Register(AG::RegisterPapyrus);
	return true;
}
