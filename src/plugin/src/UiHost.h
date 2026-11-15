// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

// The web-page host the Guild's four pages run on (the counter, the Guild Board, the leader board and the notices):
// Prisma UI or Magelight UI. One is picked at start-up and kept for the session; every page goes through here, so the
// rest of the plugin never asks which.
//
// Which one: [UI] Host in AdventurersGuild.ini, or in Data/SKSE/Plugins/AdventurersGuild/UIHost.ini when that file is
// there (a test override, read last):
//   auto       Magelight UI when it is installed (1.8.0 or newer), else Prisma UI (the default)
//   prisma     Prisma UI
//   magelight  Magelight UI
// A host asked for but not installed falls back to the other one, and the log says so.
//
// What each host differs in, and what this layer does about it:
//  - Calls from a page (agAction, agClose) reach the handler on the GAME thread, on both. Prisma UI calls them on its
//    own thread (posted with AddTask, as before); Magelight UI calls them inside the game's frame, where AddTask can hang
//    Skyrim VR, so they are posted with its PostGameTask.
//  - Magelight UI can end a page's input itself (Escape the page did not take, B/Y in VR, a load). That reaches the
//    page's module as its own Close (OnHostClosed).
//  - Magelight UI suspends the player's controls while a page has input, and handles VR lasers and text fields itself,
//    so the Prisma UI work-arounds (ControlsGuard, the DLL-run SteamVR keyboard) are for Prisma UI only.
#include <cstdint>
#include <string>
#include <string_view>

namespace AG::UiHost
{
	enum class Kind { kNone, kPrisma, kMagelight };

	// At kDataLoaded, before any page is made: picks the host and registers with it.
	void Init();

	Kind        Active();
	const char* Name();  // "Prisma UI", "Magelight UI", "none"

	// Magelight UI suspends the player's controls itself while a page has input (and releases them only once the button
	// that closed it is up): ControlsGuard is for Prisma UI only.
	bool ManagesControls();
	// In VR the page's text field works as it is (Magelight UI's own headset keyboard), so the DLL-run SteamVR keyboard
	// is not used.
	bool NativeVRText();

	using Handle = std::uint32_t;  // 0: no page
	using Listener = void (*)(const std::string& a_arg);  // runs on the game thread
	using Closed = void (*)();                             // runs on the game thread

	enum class Layer { kPanel, kNotice };  // a page the player uses; a notice drawn over play (and over a panel)

	struct Spec
	{
		const char* name;       // "counter": for the log and Magelight UI's view name
		const char* file;       // "counter.html", in Data/PrismaUI/views/AdventurersGuild/ (one copy for both hosts)
		Layer       layer;
		bool        textEntry;  // the page has a text field (the counter's party name)
		bool        prepaint;   // Magelight UI, flat: painted while hidden so the first open is quick (opened often)
	};

	// The page, hidden. 0 when no host is installed, the file is missing or the host refused it (logged).
	Handle Create(const Spec& a_spec);
	bool   Valid(Handle a_view);

	void Listen(Handle a_view, const char* a_name, Listener a_fn);  // window.<a_name>(arg) in the page
	void OnHostClosed(Handle a_view, Closed a_fn);                   // the host ended the page's input on its own
	void Js(Handle a_view, std::string_view a_script);

	void Show(Handle a_view);
	void Hide(Handle a_view);
	// The page takes the mouse, keyboard and lasers, and pauses the game. False when it could not (Magelight UI: another
	// mod's page holds input); the caller closes it again.
	bool Focus(Handle a_view);
	void Unfocus(Handle a_view);

	// Draw a_top over a_below (a notice over the open counter). Magelight UI's notice layer already is.
	void KeepAbove(Handle a_top, Handle a_below);
}
