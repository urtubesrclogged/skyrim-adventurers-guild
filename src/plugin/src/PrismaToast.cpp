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
		std::atomic<int>            g_sounds{ 0 };     // MCM "Notification sounds": SoundSet
		// The Guild Drums: the same notices, in the same order as the game's set (0xC81..0xC87); EspGen, Cue
		constexpr RE::FormID kDrumId[] = { 0, 0xC8B, 0xC8C, 0xC8D, 0xC8E, 0xC8F, 0xCE7, 0xCE8 };
		std::atomic<std::uint32_t>  g_replaced{ 0 };   // bit per Cue: another mod has put its own file where the game's is

		// The game's file each cue plays (tools/EspGen/Program.cs, Cue), under Data. The game keeps every one of them in
		// its archives, so a loose file at that path is another mod's. A list that restyles its interface sounds
		// (Librum: "Paper UI Sounds", "No UI Sounds") gave a promotion a rustle of paper in place of the sound chosen
		// for it (in game, 2026-10-13); the author would have no sound there over the wrong one. A replacement packed
		// into a mod's own archive is not seen this way: only loose files, which is how such mods come.
		constexpr const char* kCueFile[] = { nullptr,
			"Sound\\FX\\UI\\UI_LevelUp", "Music\\Stinger\\MUS_Stinger_02", "Music\\Reward\\MUS_Reward_01", "Sound\\fx\\ui\\ui_skill_increase",
			"Sound\\fx\\ui\\ui_quest_update", "Sound\\FX\\UI\\Smithing\\UI_Smithing_CreateGeneric_01", "Sound\\FX\\mgk\\firebolt\\mag_firebolt_fail" };

		std::atomic<std::uint32_t> g_unready{ (1u << 2) | (1u << 3) };  // bit per Cue: a music cue whose file has not been given yet

		// The two music cues (dungeon entered, registered). A sound record cannot name a music file, so each of ours is
		// written with a stand-in and is given here the game's own reference to the file, read from the game's own
		// track record (Skyrim.esm MUSStinger02 0x08DC79, MUSReward01 0x02482C). It then plays as any sound does: once.
		void BorrowTracks()
		{
			auto* dh = RE::TESDataHandler::GetSingleton();
			if (!dh) return;
			const std::pair<std::uint32_t, RE::FormID> kTracks[] = { { 2, 0x08DC79 }, { 3, 0x02482C } };
			for (const auto& [cue, trackId] : kTracks) {
				auto* form = dh->LookupForm(0xC80 + cue, "AdventurersGuild.esp");
				auto* sd = form ? form->As<RE::BGSSoundDescriptorForm>() : nullptr;
				auto* def = sd && sd->soundDescriptor ? skyrim_cast<RE::BGSStandardSoundDef*>(sd->soundDescriptor) : nullptr;
				auto* wrap = dh->LookupForm<RE::BGSMusicTrackFormWrapper>(trackId, "Skyrim.esm");
				auto* track = wrap && wrap->track && wrap->track->GetType() == RE::BSIMusicTrack::TrackType::kSingleTrack
					? static_cast<RE::BGSMusicSingleTrack*>(wrap->track) : nullptr;
				if (!def || def->soundFiles.empty() || !track) {
					SKSE::log::warn("PrismaToast: the music of a notice could not be set up (cue {}: record {}, track {:06X} {}) - that notice is silent",
						cue, def ? "found" : "missing", trackId, track ? "found" : "missing or not a single track");
					continue;
				}
				def->soundFiles[0] = track->trackID;
				g_unready.fetch_and(~(1u << cue));
			}
		}

		void FindReplaced()
		{
			std::uint32_t bits = 0;
			std::string   names;
			for (std::uint32_t c = 1; c < std::size(kCueFile); ++c) {
				std::error_code ec;
				for (const auto ext : { ".wav", ".xwm" })
					if (std::filesystem::exists(std::string("Data\\") + kCueFile[c] + ext, ec)) {
						bits |= 1u << c;
						names += std::string(names.empty() ? "" : ", ") + kCueFile[c] + ext;
						break;
					}
			}
			g_replaced.store(bits);
			if (bits) SKSE::log::info("PrismaToast: another mod replaces {} - the notices these belong to come without a sound", names);
		}
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
				// 0 the Guild Drums, 1 the game's own, 2 none (an ini from before 1.5.0 only had the on/off NoticeSounds)
				const int set = static_cast<int>(ini.GetLongValue("System", "NoticeSoundSet", ini.GetBoolValue("System", "NoticeSounds", true) ? 0 : 2));
				SetSounds(static_cast<SoundSet>(std::clamp(set, 0, 2)));
				SetVolume(static_cast<int>(ini.GetLongValue("System", "NoticeVolume", 0)));
				SetHoldSeconds(static_cast<float>(ini.GetDoubleValue("System", "NoticeSeconds", 5.0)));
			}
		}
		FindReplaced();
		BorrowTracks();
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

	// another mod replaces it: only the game's set can be (the drums are under names of the mod's own)
	bool Replaced(Cue a_cue) { return Sounds() == SoundSet::kSkyrim && ((g_replaced.load() >> static_cast<std::uint32_t>(a_cue)) & 1u); }

	bool Play(Cue a_cue, bool a_evenIfReplaced)
	{
		// the set chosen; none chosen, a test still plays the drums (it asked for a sound)
		auto set = Sounds();
		if (set == SoundSet::kNone) {
			if (!a_evenIfReplaced) return false;
			set = SoundSet::kDrums;
		}
		const bool skyrim = set == SoundSet::kSkyrim;
		if (skyrim && !a_evenIfReplaced && Replaced(a_cue)) return false;
		if (skyrim && ((g_unready.load() >> static_cast<std::uint32_t>(a_cue)) & 1u)) return false;  // still its stand-in: never played
		// AdventurersGuild.esp 0xC81.. in the order of the enum (tools/EspGen/Program.cs, Cue)
		if (a_cue == Cue::kNone) return false;
		auto* dh = RE::TESDataHandler::GetSingleton();
		auto* am = RE::BSAudioManager::GetSingleton();
		const auto local = skyrim ? 0xC80 + static_cast<RE::FormID>(a_cue) : kDrumId[static_cast<std::size_t>(a_cue)];
		auto*      form = dh ? dh->LookupForm(local, "AdventurersGuild.esp") : nullptr;
		auto* sd = form ? form->As<RE::BGSSoundDescriptorForm>() : nullptr;
		if (!sd || !sd->soundDescriptor || !am) {
			static std::atomic<bool> said{ false };
			if (!said.exchange(true)) SKSE::log::warn("PrismaToast: the sound record of a notice was not found (cue {}) - the notices are silent", static_cast<int>(a_cue));
			return false;
		}
		// What the game plays is the descriptor INSIDE the record, not the record: handed the record itself
		// (BSAudioManager::Play by FormID does that) the game reported success and played something else, a page turning
		// (heard in game, 2026-10-13). And on the game's own thread: a notice is often raised from an event's.
		const auto id = sd->GetFormID();
		// The level: each sound's own cut at the default step, 4 dB less or more a step, never above the file itself.
		// The drums' default is 4 dB above where 1.5.0's first builds played them (the level-up record's 7.9 dB cut,
		// barely heard in a modlist that keeps interface sounds low); the game's own sounds keep their records' cuts.
		// Order of the enum: promoted, dungeon entered, registered, promotion ready, complete, stamped, Reputation lost.
		constexpr float kCutSkyrim[] = { 0.0f, 7.93f, 7.93f, 7.93f, 3.96f, 5.73f, 5.73f, 7.93f };
		const float     cut = (skyrim ? kCutSkyrim[static_cast<std::size_t>(a_cue)] : 3.93f) - 4.0f * static_cast<float>(Volume());
		const float     gain = std::pow(10.0f, -std::max(cut, 0.0f) / 20.0f);
		SKSE::GetTaskInterface()->AddTask([id, gain] {
			auto* f = RE::TESForm::LookupByID<RE::BGSSoundDescriptorForm>(id);
			auto* m = RE::BSAudioManager::GetSingleton();
			if (!f || !f->soundDescriptor || !m) return;
			RE::BSSoundHandle h;
			if (m->GetSoundHandle(h, f->soundDescriptor)) {
				h.SetVolume(gain);
				h.Play();
			}
		});
		return true;
	}

	SoundSet Sounds() { return static_cast<SoundSet>(g_sounds.load(std::memory_order_relaxed)); }
	void     SetSounds(SoundSet a_set) { g_sounds.store(static_cast<int>(a_set), std::memory_order_relaxed); }

	namespace
	{
		std::atomic<int> g_volume{ 0 };
	}
	int  Volume() { return g_volume.load(std::memory_order_relaxed); }
	void SetVolume(int a_step) { g_volume.store(std::clamp(a_step, -1, 1), std::memory_order_relaxed); }

	void Show(std::string_view a_title, std::string_view a_subtitle, std::string_view a_seal, Priority a_priority, Cue a_cue)
	{
		if (!Active() || !g_enabled.load(std::memory_order_relaxed)) return;
		if (a_cue != Cue::kNone && Sounds() != SoundSet::kNone) Play(a_cue);  // only with a notice that is shown: a sound alone says nothing

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
