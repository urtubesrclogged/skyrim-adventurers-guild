// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "Faces.h"
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
#include "GuildBoard.h"
#include "LeaderBoard.h"
#include "GuildHall.h"
#include "hall/hall.h"
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
#include "SkyrimNetData.h"
#include "ChimData.h"
#include "UiHost.h"
#include "Wares.h"

#include <spdlog/sinks/basic_file_sink.h>

#include <atomic>
#include <chrono>
#include <thread>

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

	// Which job mods are in, for the clerks' lines, and whether the Guild Hall is (for the lore and the innkeepers' menu): every
	// load, so a mod taken out flips them for an old save.
	void SyncJobModGlobals()
	{
		auto* dh = RE::TESDataHandler::GetSingleton();
		if (!dh) return;
		if (auto* g = dh->LookupForm<RE::TESGlobal>(0xFDB, "AdventurersGuild.esp")) g->value = AG::MissiveWatch::Active() ? 1.0f : 0.0f;
		if (auto* g = dh->LookupForm<RE::TESGlobal>(0xFDC, "AdventurersGuild.esp")) g->value = AG::NoticeWatch::Active() ? 1.0f : 0.0f;
		if (auto* g = dh->LookupForm<RE::TESGlobal>(0x807, "AdventurersGuild.esp")) g->value = AG::GuildHall::Loaded() ? 1.0f : 0.0f;
		// which hall (2.0, 2026-11-17): 0 none, 1 Riverwood, 2 Solitude, from the installed hall's layout, for the lines and the lore
		// that name its place
		if (auto* g = dh->LookupForm<RE::TESGlobal>(0x80E, "AdventurersGuild.esp")) g->value = static_cast<float>(Hall::SitePlace());
	}

	// A save has been read (or a new game begun): the Guild catches up with it.
	void GameLoaded(bool a_newGame)
	{
		const AG::Diag::Timed timed("the work done once a game is loaded", 250);
		AG::Guild::OnGameLoaded();
		AG::Guild::SyncSuccessors();
		AG::MissiveWatch::OnGameLoaded();
		SyncJobModGlobals();
		AG::GuildCard::CheckArt();
		AG::GuildCard::Sync(false);  // a member from before 1.2.0, or one who lost theirs, gets a card
		AG::ControlsGuard::OnGameLoaded();
		AG::Dungeons::OnGameLoaded();
		AG::Party::DropCreatures();
		AG::SkyrimNetData::OnGameLoaded();  // SkyrimNet reads this save's Guild record from now on
		AG::ChimData::OnGameLoaded();       // ... and CHIM's server is sent it
		AG::Wares::OnGameLoaded();
		AG::GuildHall::SwitchVanillaLights();  // every load, so a save follows Light Limit Fix being added or removed
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

	void OnMessage(SKSE::MessagingInterface::Message* a_msg);

	// A game begun with neither a save read nor a new game started: "coc <cell>" typed at the main menu. SKSE sends no message
	// for it, so the Guild never caught up and the Guild Hall was never placed. A loading screen that closes, with no load or new
	// game heard of since the main menu was last open, is taken for a new game: a moment later (a real new game's message comes
	// first), with the player in the world, the co-save's revert and then the new-game work run as if SKSE had sent kNewGame.
	std::atomic<bool> g_started = false;  // a save read or a new game begun since the main menu was last open
	std::atomic<bool> g_loading = false;  // a save being read (kPreLoadGame until kPostLoadGame)

	void StartedWithoutMessage()
	{
		auto* pc = RE::PlayerCharacter::GetSingleton();
		auto* ui = RE::UI::GetSingleton();
		if (g_started || g_loading || !pc || !pc->GetParentCell() || (ui && ui->IsMenuOpen(RE::MainMenu::MENU_NAME))) return;
		SKSE::log::info("A game began with no save read and no new game started (coc at the main menu): taken for a new game");
		AG::Guild::RevertState();
		SKSE::MessagingInterface::Message m{};
		m.type = SKSE::MessagingInterface::kNewGame;
		OnMessage(&m);
	}

	class StartSink : public RE::BSTEventSink<RE::MenuOpenCloseEvent>
	{
	public:
		static StartSink* Get()
		{
			static StartSink s;
			return std::addressof(s);
		}

		RE::BSEventNotifyControl ProcessEvent(const RE::MenuOpenCloseEvent* a_e, RE::BSTEventSource<RE::MenuOpenCloseEvent>*) override
		{
			if (!a_e) return RE::BSEventNotifyControl::kContinue;
			if (a_e->opening && a_e->menuName == RE::MainMenu::MENU_NAME) g_started = false;
			else if (!a_e->opening && a_e->menuName == RE::LoadingMenu::MENU_NAME && !g_started && !g_loading)
				std::thread([] {
					std::this_thread::sleep_for(std::chrono::seconds(2));
					SKSE::GetTaskInterface()->AddTask(StartedWithoutMessage);
				}).detach();
			return RE::BSEventNotifyControl::kContinue;
		}
	};

	void OnMessage(SKSE::MessagingInterface::Message* a_msg)
	{
		switch (a_msg->type) {
		case SKSE::MessagingInterface::kPostLoad:
			break;
		case SKSE::MessagingInterface::kPostPostLoad:
			Hall::GrassInstall();  // every SKSE plugin loaded: off when No Grass In Objects is one of them
			AG::Faces::ApplyTint();  // every SKSE plugin loaded, no game plugin read yet: the hall's faces keep their skin tint
			break;
		case SKSE::MessagingInterface::kDataLoaded:
			AG::Diag::LogEnvironment();
			AG::Loc::Load();
			AG::LoadConfig();
			AG::Guild::LoadConfig();
			AG::Party::LoadConfig();
			AG::LeaderBoard::LoadConfig();
			AG::Adventurers::Load();
			AG::Shop::Load();
			AG::Wares::Load();
			AG::Guild::Register();
			AG::LevelDisplay::Register();
			AG::UiHost::Init();  // Prisma UI or Magelight UI, before any page is made
			AG::PrismaToast::Install();
			AG::LoadRaceRules();
			AG::Counter::Install();
			AG::GuildHall::TuneLighting();
			AG::GuildHall::ApplyLux();     // the hall's cells on Lux's house lighting when Lux is loaded
			AG::GuildHall::ApplyHelios();  // the hall's windowed cells follow the sky when Helios is loaded
			AG::GuildHall::VanillaLighting();  // without Light Limit Fix: fewer lights, more ambient (after Lux's template)
			AG::GuildHall::JoinVoiceLists();  // the hall folk's own voices on vanilla's follower and marriage voice lists
			AG::GuildBoard::Install();  // the Guild Hall's board (2.0): its page, opened by activating it
			AG::LeaderBoard::Install();  // the hall's party leader board (2.0): its page, opened by activating it
			AG::LeaderBoard::Register();
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
			AG::SkyrimNetData::Install();
			AG::Faces::OnDataLoaded();  // High Poly Head's heads on the Guild Hall's people, when it is loaded
			AG::ChimData::Install();  // CHIM, when installed: the Guild's state to its server, the ledger's news to its NPCs
			if (auto* ui = RE::UI::GetSingleton()) ui->AddEventSink<RE::MenuOpenCloseEvent>(StartSink::Get());  // coc at the main menu
			SKSE::log::info("Data loaded; sinks registered");
			break;
		case SKSE::MessagingInterface::kPreLoadGame:
			g_loading = true;
			// the one line that tells a load that never ends from one that does: "Game loaded" follows it, or nothing does
			SKSE::log::info("Loading a save");
			break;
		case SKSE::MessagingInterface::kPostLoadGame:
		case SKSE::MessagingInterface::kNewGame:
			g_loading = false;
			g_started = true;
			GameLoaded(a_msg->type == SKSE::MessagingInterface::kNewGame);
			break;
		default:
			break;
		}
		Nav::OnMessage(a_msg);  // the Guild Hall's outside and navmesh (hall/): does nothing without the hall's plugin
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
	SKSE::AllocTrampoline(4096 + 256);  // one for the whole plugin: the name hook's call sites (4096 of it), ChoiceSwap's two, the hall's grass fix's three
	AG::Names::Install();
	AG::Faces::InstallTint();  // logs the tint sites' bytes; ApplyTint patches them once every SKSE plugin has loaded
	AG::Guild::SetupSerialization();
	SKSE::GetMessagingInterface()->RegisterListener(OnMessage);
	SKSE::GetPapyrusInterface()->Register(AG::RegisterPapyrus);
	SKSE::GetPapyrusInterface()->Register(Nav::RegisterPapyrus);  // the hall's natives (AGHallNative)
	return true;
}
