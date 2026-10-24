// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "SkyrimNetData.h"

#include "Adventurers.h"
#include "Diag.h"
#include "Guild.h"
#include "Party.h"
#include "RankCore.h"

#include <filesystem>
#include <fstream>
#include <nlohmann/json.hpp>

namespace AG::SkyrimNetData
{
	namespace
	{
		constexpr const char* kPlugin = "AdventurersGuild.esp";
		// read_json paths are relative to Data/SKSE/Plugins; the game's working directory is the game folder
		constexpr const char* kFile = "Data/SKSE/Plugins/AdventurersGuild/SkyrimNet/state.json";
		constexpr int         kRetired = 10, kNeverJoins = 20;

		bool            g_on{ false };
		RE::TESFaction* g_standing{ nullptr };  // AG_SkyrimNetStandingFaction 0xCD8
		RE::TESFaction* g_note{ nullptr };      // AG_SkyrimNetNoteFaction 0xCD9
		RE::TESFaction* g_party{ nullptr };     // AG_SkyrimNetPartyFaction 0xCDA
		std::string     g_written;              // what the file holds now ("" = write it whatever it holds)
		bool            g_failSaid{ false };

		// GetFactionRank is -2 for someone never in the faction and -1 for someone taken out of it (AddToFaction at -1, as
		// the rest of the mod does): only an actor who holds a rank is ever taken out, so bystanders are never touched.
		void Set(RE::Actor* a_actor, RE::TESFaction* a_faction, int a_want)
		{
			const auto have = a_actor->GetFactionRank(a_faction, false);
			if (a_want < 0) {
				if (have >= 0) a_actor->AddToFaction(a_faction, -1);
				return;
			}
			const auto want = static_cast<std::int8_t>(std::min(a_want, 127));
			if (have != want) a_actor->AddToFaction(a_faction, want);
		}

		int Standing(RE::Actor* a_actor)
		{
			const auto info = Adventurers::Of(a_actor);
			if (info.kind == Adventurers::Kind::kMember) return std::clamp(info.rank, 0, kRankCount - 1);
			if (info.kind == Adventurers::Kind::kRetired) return kRetired + std::clamp(info.rank, 0, kRankCount - 1);
			const auto why = Adventurers::JoinStatus(a_actor);
			return why == "child" || why == "summoned" ? kNeverJoins : -1;
		}

		void Write()
		{
			nlohmann::json j;
			j["version"] = 1;
			auto& letters = j["letters"] = nlohmann::json::array();
			for (int r = 0; r < kRankCount; ++r) letters.push_back(LetterStr(r));
			j["notes"] = Adventurers::NoteTexts();
			j["ledger"] = nlohmann::json::parse(Guild::LedgerJson(), nullptr, false);
			j["party"] = Party::SkyrimNetState();
			auto text = j.dump();
			if (text == g_written) return;
			const std::filesystem::path path(kFile), tmp(std::string(kFile) + ".tmp");
			std::error_code ec;
			std::filesystem::create_directories(path.parent_path(), ec);
			{
				std::ofstream f(tmp, std::ios::binary | std::ios::trunc);
				f << text;
				if (!f) ec = std::make_error_code(std::errc::io_error);
			}
			if (!ec) std::filesystem::rename(tmp, path, ec);  // whole or not at all: SkyrimNet never reads half a file
			if (ec) {
				std::filesystem::remove(tmp, ec);
				std::ofstream f(path, std::ios::binary | std::ios::trunc);
				f << text;
				if (!f) {
					if (!g_failSaid) SKSE::log::error("SkyrimNet: could not write {} - NPCs will not know the player's Guild record", kFile);
					g_failSaid = true;
					return;
				}
			}
			if (g_written.empty()) SKSE::log::info("SkyrimNet: the Guild's record for this game is in {}", kFile);
			g_written = std::move(text);
			Diag::SetSkyrimNetReady(true);
		}

		void MarkAround()
		{
			auto* pl = RE::ProcessLists::GetSingleton();
			if (!pl) return;
			for (auto& h : pl->highActorHandles)
				if (auto actor = h.get(); actor) Mark(actor.get());
		}

		struct LoadSink final : RE::BSTEventSink<RE::TESObjectLoadedEvent>
		{
			static LoadSink* Get()
			{
				static LoadSink s;
				return &s;
			}
			RE::BSEventNotifyControl ProcessEvent(const RE::TESObjectLoadedEvent* a_e, RE::BSTEventSource<RE::TESObjectLoadedEvent>*) override
			{
				if (a_e && a_e->loaded)
					if (auto* actor = RE::TESForm::LookupByID<RE::Actor>(a_e->formID)) Mark(actor);
				return RE::BSEventNotifyControl::kContinue;
			}
		};
	}

	void Install()
	{
		if (!GetModuleHandleW(L"SkyrimNet.dll")) return;
		auto* dh = RE::TESDataHandler::GetSingleton();
		g_standing = dh ? dh->LookupForm<RE::TESFaction>(0xCD8, kPlugin) : nullptr;
		g_note = dh ? dh->LookupForm<RE::TESFaction>(0xCD9, kPlugin) : nullptr;
		g_party = dh ? dh->LookupForm<RE::TESFaction>(0xCDA, kPlugin) : nullptr;
		if (!g_standing || !g_note || !g_party) {
			SKSE::log::error("SkyrimNet: the plugin's SkyrimNet factions (0xCD8-0xCDA) are missing - is AdventurersGuild.esp from this version?");
			return;
		}
		RE::ScriptEventSourceHolder::GetSingleton()->AddEventSink<RE::TESObjectLoadedEvent>(LoadSink::Get());
		g_on = true;
	}

	void Mark(RE::Actor* a_actor)
	{
		if (!g_on || !a_actor || a_actor->IsPlayerRef() || a_actor->IsDead() || Guild::Dormant()) return;
		Set(a_actor, g_standing, Standing(a_actor));
		Set(a_actor, g_note, Adventurers::NoteIndex(a_actor));
		Set(a_actor, g_party, Party::SkyrimNetTie(a_actor));
	}

	void OnGameLoaded()
	{
		if (!g_on) return;
		g_written.clear();  // another save: whatever the file says is someone else's
		Write();
		MarkAround();
	}

	void Tick()
	{
		if (!g_on || !RE::PlayerCharacter::GetSingleton()) return;
		const Diag::Timed timed("keeping SkyrimNet's view of the Guild up to date");
		MarkAround();
		Write();
	}

	bool Active() { return g_on && !g_written.empty(); }
}
