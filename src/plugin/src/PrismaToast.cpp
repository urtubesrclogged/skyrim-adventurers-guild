// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "PrismaToast.h"

#include "ControlsGuard.h"
#include "Counter.h"
#include "PrismaUI_API.h"

#include <SimpleIni.h>
#include <atomic>
#include <chrono>
#include <filesystem>
#include <thread>

namespace AG::PrismaToast
{
	namespace
	{
		constexpr const char* kViewPath = "AdventurersGuild/index.html";
		constexpr const char* kViewFile = "Data\\PrismaUI\\views\\AdventurersGuild\\index.html";

		PRISMA_UI_API::IVPrismaUI1* g_api{ nullptr };
		PrismaView                  g_view{ 0 };
		std::atomic<bool>           g_enabled{ true };
		std::atomic<bool>           g_shown{ false };  // the notice is up (ControlsGuard is told once per appearance)
		std::atomic<std::uint32_t>  g_seq{ 0 };   // bumps per toast: a stale hide timer must not cut a newer toast short
		std::atomic<int>            g_holdMs{ 5000 };  // MCM "Important notices"; the view adds 0.3 s in + 0.5 s out
		std::atomic<int>            g_minorMs{ 2500 };  // MCM "Minor notices"

		// Standard JSON escaping for embedding a string in a JS call (drop control chars other
		// than \n/\t, escape the rest) - titles/subtitles here are plugin-authored text, not
		// player input, but escape anyway since it's cheap and correct.
		std::string Esc(std::string_view a_s)
		{
			std::string out;
			out.reserve(a_s.size());
			for (unsigned char c : a_s) {
				switch (c) {
				case '"':  out += "\\\""; break;
				case '\\': out += "\\\\"; break;
				case '\n': out += "\\n"; break;
				case '\r': break;
				case '\t': out += "\\t"; break;
				default:
					if (c >= 0x20) out += static_cast<char>(c);
					break;
				}
			}
			return out;
		}
	}

	void Install()
	{
		// the MCM's starting values (System page); the MCM, once in a save, sets these itself
		{
			CSimpleIniA ini;
			ini.SetUnicode();
			if (ini.LoadFile("Data/SKSE/Plugins/AdventurersGuild.ini") >= 0) {
				SetEnabled(ini.GetBoolValue("System", "ShowNotices", true));
				SetHoldSeconds(static_cast<float>(ini.GetDoubleValue("System", "NoticeSeconds", 5.0)));
			}
		}
		g_api = PRISMA_UI_API::RequestPluginAPI<PRISMA_UI_API::IVPrismaUI1>();
		if (!g_api) {
			SKSE::log::info("PrismaToast: PrismaUI not loaded - rank-up toast disabled");
			return;
		}

		std::error_code ec;
		if (!std::filesystem::exists(kViewFile, ec)) {
			SKSE::log::info("PrismaToast: PrismaUI present but {} is missing - rank-up toast disabled", kViewFile);
			g_api = nullptr;
			return;
		}

		g_view = g_api->CreateView(kViewPath);
		if (!g_api->IsValid(g_view)) {
			SKSE::log::error("PrismaToast: CreateView failed - rank-up toast disabled");
			g_api = nullptr;
			return;
		}
		g_api->Hide(g_view);
		SKSE::log::info("PrismaToast: view active (view {}, order {})", g_view, g_api->GetOrder(g_view));
	}

	bool Active() { return g_api != nullptr && g_api->IsValid(g_view); }

	namespace
	{
		int HoldMs(Priority a_p) { return a_p == Priority::kMinor ? g_minorMs.load() : g_holdMs.load(); }
	}

	void Show(std::string_view a_title, std::string_view a_subtitle, std::string_view a_seal, Priority a_priority)
	{
		if (!Active() || !g_enabled.load(std::memory_order_relaxed)) return;

		std::string json = "{\"title\":\"" + Esc(a_title) + "\",\"subtitle\":\"" + Esc(a_subtitle) + "\",\"seal\":\"" + Esc(a_seal) + "\",\"hold\":" + std::to_string(HoldMs(a_priority) / 1000.0) + ",\"flat\":" + (REL::Module::IsVR() ? "false" : "true") + "}";
		// A toast raised while the counter is open (e.g. intel bought) must draw above it, not behind it.
		if (const int co = Counter::ViewOrder(); co >= 0 && g_api->GetOrder(g_view) <= co) {
			g_api->SetOrder(g_view, co + 1);
			SKSE::log::info("PrismaToast: order raised above the counter ({} -> {})", co, g_api->GetOrder(g_view));
		}
		g_api->Invoke(g_view, ("window.rkFlourish(" + json + ")").c_str());
		// PrismaVR masks fighting controls while a laser is on any of its panels, the notice included (ControlsGuard.h).
		if (!g_shown.exchange(true)) {
			ControlsGuard::Shown();
			std::thread([]() {
				while (g_shown.load()) {
					std::this_thread::sleep_for(std::chrono::milliseconds(50));
					if (auto* task = SKSE::GetTaskInterface())
						task->AddTask([]() {
							if (g_shown.load() && !Counter::IsOpen()) ControlsGuard::KeepOn();  // the counter is clickable: leave its masking alone
						});
				}
			}).detach();
		}
		g_api->Show(g_view);  // no Focus() - purely visual, plays over live gameplay

		// Auto-hide after the CSS animation finishes so the (invisible but still "shown") view doesn't linger.
		// Only the latest toast's timer hides the view: a toast shown mid-way through another restarts the
		// animation, and the earlier timer would otherwise cut it off.
		const auto seq = ++g_seq;
		const int  hideMs = HoldMs(a_priority) + 800 + 200;  // hold + fades + slack
		std::thread([seq, hideMs]() {
			std::this_thread::sleep_for(std::chrono::milliseconds(hideMs));
			if (auto* task = SKSE::GetTaskInterface()) {
				task->AddTask([seq]() {
					if (seq == g_seq.load() && g_api && g_api->IsValid(g_view)) {
						g_api->Hide(g_view);
						if (g_shown.exchange(false)) ControlsGuard::Hidden();
					}
				});
			}
		}).detach();
	}

	float HoldSeconds() { return g_holdMs.load() / 1000.0f; }
	void  SetHoldSeconds(float a_seconds) { g_holdMs.store(static_cast<int>(std::clamp(a_seconds, 2.0f, 15.0f) * 1000.0f)); }
	float MinorHoldSeconds() { return g_minorMs.load() / 1000.0f; }
	void  SetMinorHoldSeconds(float a_seconds) { g_minorMs.store(static_cast<int>(std::clamp(a_seconds, 1.0f, 10.0f) * 1000.0f)); }

	bool Enabled() { return g_enabled.load(std::memory_order_relaxed); }
	void SetEnabled(bool a_on) { g_enabled.store(a_on, std::memory_order_relaxed); }
}
