// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "ChimData.h"

#include "Adventurers.h"
#include "Guild.h"
#include "Loc.h"
#include "Party.h"
#include "RankCore.h"
#include "SkyrimNetData.h"

#include <chrono>
#include <condition_variable>
#include <fstream>
#include <nlohmann/json.hpp>
#include <thread>
#include <winhttp.h>

namespace AG::ChimData
{
	namespace
	{
		constexpr const char* kPath = "/HerikaServer/ext/adventurersguild/api/state.php";
		constexpr int         kRetrySeconds = 30;  // after a failed report: CHIM's server may simply not be started yet

		bool                                               g_on{ false };
		std::vector<std::pair<std::string, RE::TESFaction*>> g_factions;  // chim.json: the factions the lore depends on
		std::vector<std::string>                           g_plugins;      // chim.json: the other mods the lore covers, loaded ones
		std::string                                        g_sent;         // the last report taken (without "hello")
		std::atomic<bool>                                  g_hello{ false };         // this game's first report is still to be taken
		std::atomic<bool>                                  g_helloInFlight{ false };  // ... and is with the worker now
		std::atomic<bool>                                  g_accepted{ false };

		// the worker: one report at a time, the newest wins
		std::mutex              g_qLock;
		std::condition_variable g_qCv;
		std::string             g_queued;
		bool                    g_queuedHello{ false };
		std::thread             g_worker;
		std::chrono::steady_clock::time_point g_nextTry{};

		struct Server
		{
			std::string host{ "127.0.0.1" };
			int         port{ 8081 };
			bool        found{ false };
		} g_server;

		std::wstring Wide(const std::string& a_s)
		{
			if (a_s.empty()) return {};
			const int n = MultiByteToWideChar(CP_UTF8, 0, a_s.data(), static_cast<int>(a_s.size()), nullptr, 0);
			std::wstring w(static_cast<std::size_t>(n), L'\0');
			MultiByteToWideChar(CP_UTF8, 0, a_s.data(), static_cast<int>(a_s.size()), w.data(), n);
			return w;
		}

		// Skyrim's strings are Windows-1252; the server reads UTF-8 JSON
		std::string Utf8(const char* a_s)
		{
			if (!a_s || !*a_s) return {};
			const int n = MultiByteToWideChar(1252, 0, a_s, -1, nullptr, 0);
			std::wstring w(static_cast<std::size_t>(n), L'\0');
			MultiByteToWideChar(1252, 0, a_s, -1, w.data(), n);
			const int m = WideCharToMultiByte(CP_UTF8, 0, w.c_str(), -1, nullptr, 0, nullptr, nullptr);
			std::string out(static_cast<std::size_t>(m), '\0');
			WideCharToMultiByte(CP_UTF8, 0, w.c_str(), -1, out.data(), m, nullptr, nullptr);
			if (!out.empty() && out.back() == '\0') out.pop_back();
			return out;
		}

		bool Http(const std::string& a_method, const std::string& a_host, int a_port, const std::string& a_path, const std::string& a_body,
			std::string* a_answer, int a_timeoutMs)
		{
			bool ok = false;
			HINTERNET session = WinHttpOpen(L"AdventurersGuild", WINHTTP_ACCESS_TYPE_NO_PROXY, WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
			if (!session) return false;
			WinHttpSetTimeouts(session, a_timeoutMs, a_timeoutMs, a_timeoutMs, a_timeoutMs);
			HINTERNET connect = WinHttpConnect(session, Wide(a_host).c_str(), static_cast<INTERNET_PORT>(a_port), 0);
			HINTERNET request = connect ? WinHttpOpenRequest(connect, Wide(a_method).c_str(), Wide(a_path).c_str(), nullptr, WINHTTP_NO_REFERER,
											  WINHTTP_DEFAULT_ACCEPT_TYPES, 0) :
			                              nullptr;
			if (request) {
				const wchar_t* headers = L"Content-Type: application/json; charset=utf-8\r\n";
				const BOOL     sent = WinHttpSendRequest(request, a_body.empty() ? WINHTTP_NO_ADDITIONAL_HEADERS : headers, a_body.empty() ? 0 : static_cast<DWORD>(-1L),
                    a_body.empty() ? WINHTTP_NO_REQUEST_DATA : const_cast<char*>(a_body.data()), static_cast<DWORD>(a_body.size()), static_cast<DWORD>(a_body.size()), 0);
				if (sent && WinHttpReceiveResponse(request, nullptr)) {
					DWORD status = 0, size = sizeof(status);
					WinHttpQueryHeaders(request, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER, WINHTTP_HEADER_NAME_BY_INDEX, &status, &size, WINHTTP_NO_HEADER_INDEX);
					std::string data;
					DWORD       available = 0;
					while (WinHttpQueryDataAvailable(request, &available) && available > 0 && data.size() < 65536) {
						std::string chunk(available, '\0');
						DWORD       read = 0;
						if (!WinHttpReadData(request, chunk.data(), available, &read) || read == 0) break;
						data.append(chunk.data(), read);
					}
					if (a_answer) *a_answer = data;
					ok = status >= 200 && status < 300;
				}
				WinHttpCloseHandle(request);
			}
			if (connect) WinHttpCloseHandle(connect);
			WinHttpCloseHandle(session);
			return ok;
		}

		std::string Trim(std::string a_s)
		{
			const auto b = a_s.find_first_not_of(" \t\r\n");
			if (b == std::string::npos) return {};
			return a_s.substr(b, a_s.find_last_not_of(" \t\r\n") - b + 1);
		}

		// As CHIM's own DLL finds its server: AIAgent.ini (SERVER, PORT), then the CHIM launcher's discovery, then the default
		void Discover()
		{
			g_server.found = true;
			if (std::ifstream ini("Data/SKSE/Plugins/AIAgent.ini"); ini) {
				std::string line;
				bool        any = false;
				while (std::getline(ini, line)) {
					const auto eq = line.find('=');
					if (line.empty() || line[0] == '#' || line[0] == ';' || eq == std::string::npos) continue;
					const auto key = Trim(line.substr(0, eq)), value = Trim(line.substr(eq + 1));
					if (_stricmp(key.c_str(), "SERVER") == 0 && !value.empty()) {
						g_server.host = value;
						any = true;
					} else if (_stricmp(key.c_str(), "PORT") == 0) {
						try {
							g_server.port = std::stoi(value);
						} catch (...) {}
					}
				}
				if (any) return;
			}
			if (std::string body; Http("GET", "127.0.0.1", 7135, "/discover", {}, &body, 1500)) {
				body = Trim(body);
				if (const auto colon = body.find(':'); colon != std::string::npos) {
					g_server.host = body.substr(0, colon);
					try {
						g_server.port = std::stoi(body.substr(colon + 1));
					} catch (...) {}
				}
			}
		}

		void Work()
		{
			bool okSaid = false, failSaid = false;
			for (;;) {
				std::string body;
				bool        hello = false;
				{
					std::unique_lock l(g_qLock);
					g_qCv.wait(l, [] { return !g_queued.empty(); });
					body = std::move(g_queued);
					hello = g_queuedHello;
					g_queued.clear();
				}
				if (!g_server.found) Discover();
				std::string answer;
				if (Http("POST", g_server.host, g_server.port, kPath, body, &answer, 3000)) {
					if (hello) g_hello = false;  // the server has this game: Oghma is up to date
					g_helloInFlight = false;
					g_accepted = true;
					if (hello || !okSaid) SKSE::log::info("CHIM: {}", Trim(answer).substr(0, 300));
					okSaid = true;
					failSaid = false;
				} else {
					g_helloInFlight = false;
					std::lock_guard l(g_qLock);
					g_nextTry = std::chrono::steady_clock::now() + std::chrono::seconds(kRetrySeconds);
					g_sent.clear();  // Tick sends it again after the pause
					if (!failSaid)
						SKSE::log::info("CHIM: its server did not take the Guild's state at {}:{} ({}) - NPCs will not know Guild ranks until it does",
							g_server.host, g_server.port, answer.empty() ? "no answer: is the CHIM server running?" : Trim(answer).substr(0, 200));
					failSaid = true;
					g_server.found = false;  // look again next time: the launcher may have moved it
				}
			}
		}

		RE::TESFaction* FactionOf(const std::string& a_key)
		{
			const auto bar = a_key.find('|');
			auto*      dh = RE::TESDataHandler::GetSingleton();
			if (!dh || bar == std::string::npos) return nullptr;
			try {
				return dh->LookupForm<RE::TESFaction>(static_cast<RE::FormID>(std::stoul(a_key.substr(bar + 1), nullptr, 16)), a_key.substr(0, bar));
			} catch (...) {
				return nullptr;
			}
		}

		nlohmann::json Near()
		{
			auto  out = nlohmann::json::array();
			auto* pl = RE::ProcessLists::GetSingleton();
			if (!pl) return out;
			const auto notes = Adventurers::NoteTexts();
			for (auto& h : pl->highActorHandles) {
				auto  ptr = h.get();
				auto* a = ptr.get();
				if (!a || a->IsPlayerRef() || a->IsDead()) continue;
				const int standing = SkyrimNetData::Standing(a), note = Adventurers::NoteIndex(a), tie = Party::SkyrimNetTie(a);
				auto      factions = nlohmann::json::array();
				for (auto& [name, f] : g_factions)
					if (f && a->IsInFaction(f)) factions.push_back(name);
				if (standing < 0 && note < 0 && tie < 0 && factions.empty()) continue;
				out.push_back({ { "name", Utf8(a->GetDisplayFullName()) }, { "standing", standing },
					{ "note", note >= 0 && note < static_cast<int>(notes.size()) ? notes[note] : std::string() }, { "tie", tie }, { "factions", std::move(factions) } });
			}
			return out;
		}
	}

	void Install()
	{
		auto* dh = RE::TESDataHandler::GetSingleton();
		if (!dh || !dh->LookupModByName("AIAgent.esp")) return;
		try {
			std::ifstream f("Data/SKSE/Plugins/AdventurersGuild/chim.json");
			const auto    j = nlohmann::json::parse(f, nullptr, true, true);
			for (auto& [name, key] : j.at("factions").items()) {
				auto* faction = FactionOf(key.get<std::string>());
				if (faction) g_factions.emplace_back(name, faction);
				else SKSE::log::warn("CHIM: faction {} ({}) not found", name, key.get<std::string>());
			}
			for (auto& p : j.at("plugins"))
				if (auto* file = dh->LookupModByName(p.get<std::string>()); file && file->GetCompileIndex() != 0xFF) g_plugins.push_back(p.get<std::string>());
		} catch (const std::exception& e) {
			SKSE::log::error("CHIM: chim.json could not be read ({}) - CHIM's NPCs will not know the Guild", e.what());
			return;
		}
		g_worker = std::thread(Work);
		g_worker.detach();
		g_on = true;
		SKSE::log::info("CHIM: found - the Guild's state goes to its server, and the Guild ledger's news to its NPCs");
	}

	void OnGameLoaded()
	{
		if (!g_on) return;
		std::lock_guard l(g_qLock);
		g_sent.clear();
		g_hello = true;
	}

	void Tick()
	{
		auto* player = RE::PlayerCharacter::GetSingleton();
		if (!g_on || !player || Guild::Dormant()) return;
		{
			std::lock_guard l(g_qLock);
			if (std::chrono::steady_clock::now() < g_nextTry) return;
		}
		nlohmann::json j;
		j["v"] = 1;
		j["ag"] = std::format("{}.{}.{}{}", AG_VERSION_MAJOR, AG_VERSION_MINOR, AG_VERSION_PATCH, AG_VERSION_LABEL);
		j["player"] = Utf8(player->GetDisplayFullName());
		auto& letters = j["letters"] = nlohmann::json::array();
		for (int r = 0; r < kRankCount; ++r) letters.push_back(LetterStr(r));
		j["ledger"] = nlohmann::json::parse(Guild::LedgerJson(), nullptr, false);
		j["party"] = Party::SkyrimNetState();
		j["near"] = Near();
		j["plugins"] = g_plugins;
		auto text = j.dump(-1, ' ', false, nlohmann::json::error_handler_t::replace);
		const bool hello = g_hello.load();
		std::lock_guard l(g_qLock);
		if (text == g_sent && (!hello || g_helloInFlight)) return;
		g_sent = text;
		if (hello) {
			j["hello"] = true;
			text = j.dump(-1, ' ', false, nlohmann::json::error_handler_t::replace);
		}
		g_queued = std::move(text);
		g_queuedHello = hello;
		if (hello) g_helloInFlight = true;
		g_qCv.notify_one();
	}

	void News(const std::string& a_line)
	{
		if (!g_on || a_line.empty()) return;
		SKSE::GetTaskInterface()->AddTask([a_line] {
			auto* player = RE::PlayerCharacter::GetSingleton();
			auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton();
			if (!player || !vm) return;
			const auto text = Loc::F("$AG_Chim_News", "{}'s Adventurers Guild ledger: {}", player->GetDisplayFullName(), a_line);
			RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> cb;
			vm->DispatchStaticCall("AIAgentFunctions", "logMessage", RE::MakeFunctionArguments(RE::BSFixedString(text), RE::BSFixedString("info_guild")), cb);
		});
	}

	bool Present() { return g_on; }
	bool Active() { return g_on && g_accepted.load(); }
}
