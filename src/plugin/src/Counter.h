// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

// The guild counter: an interactive PrismaUI window opened from the innkeeper topic "I have guild
// business." (Guild Card, Reports to claim, Merit services, Records). Built on the Deeds of Skyrim menu
// pattern (Show + Focus, JS listeners), which is proven for VR clicks. A safe no-op without PrismaUI.
namespace AG::Counter
{
	void Install();            // at kDataLoaded
	// opens once the Dialogue Menu closes; a_branch = the liaison's city, a_keeper = the liaison herself
	void OpenAfterDialogue(std::string a_branch, RE::TESObjectREFR* a_keeper = nullptr);
	// Hold stamps: the card was stamped during this visit; she says so as the counter closes (GuildCard tells us).
	void Stamped();
	// the representative of the last counter opened through her, has her say a topic of ours (0 = the stamp line)
	std::string SayStampLine(std::uint32_t a_topic = 0);
	void StampLineStarted();  // she has begun it: the lock on the line closes again
	std::string Branch();                           // city of the counter currently open ("" = none / debug)
	void Open();
	void OpenCard();           // the Guild Card page alone (the physical card, read anywhere)
	void Close();
	bool IsOpen();
	bool IsCardOnly();         // open as the physical card's single page
	void Refresh();            // push fresh data if open (any thread)
	bool IsOpenComposite();   // VR runtime is OpenComposite rather than SteamVR (false outside VR)
	int  ViewOrder();          // PrismaUI order of the counter view (-1 if none), so a toast can sit above it
}
