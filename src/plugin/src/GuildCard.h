// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

// The physical Guild Card (1.2.0): a note in the player's inventory (AG_GuildCard, 0x81A). Reading it opens the
// counter window showing the Guild Card page only, anywhere in the world - rank, progress and career without a trip to
// a hold capital. It is the card the innkeepers have always handed over in their lines ("Here's your guild card",
// "I've updated your guild card"): registration issues it, promotion renames it to the new rank.
//
// No script and no quest: the read is seen as the Book Menu opening on this book (engine event + BookMenu's target),
// the menu is closed again, and the card opens once the menus it was read from are gone.
namespace AG::GuildCard
{
	void Install();  // at kDataLoaded: find the record, watch the Book Menu

	// The card is named for the player's current rank, and the FIRST one is free: handed over at registration, or to a
	// member from before 1.2.0 when their save loads. After that a missing card (sold, dropped, left in a chest) is
	// not given again here: Replace() sells a new one (a liaison's dialogue line). Game thread. a_announce: say so on the HUD when
	// one is handed over (not during a load screen).
	void Sync(bool a_announce);

	bool        Has();      // the player carries a card
	std::string Replace();  // a liaison hands over a new card for Guild::CardFee() gold; the line for the HUD

	// MCM: a key that opens the card (a book cannot be favourited). SkyUI key code, 0 or less = none (the default).
	void SetHotkey(int a_key);
	int  Hotkey();

	// co-save (Guild.cpp): the free first card has been handed over
	bool Issued();
	void SetIssued(bool a_issued);
}
