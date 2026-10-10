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
	// The seal a card carries is the region's that issued it: Stamp() at registration and at a replacement, with the
	// liaison's city ("Raven Rock" is Morrowind's; anywhere else, and every card from before 1.4.0, Skyrim's).
	void        Stamp(const std::string& a_city);
	std::string Seal();                           // "" (Skyrim) or "morrowind": the page's tex/seal_<name>.png
	void        SetSeal(const std::string& a_seal);  // co-save
	std::string Replace(const std::string& a_city = {});  // a liaison hands over a new card for Guild::CardFee() gold; the line for the HUD

	// Hold stamps (1.5.0): a hold's crest, inked on the card at that hold's counter once the member has cleared
	// Guild::StampDungeons() dungeons in the hold. Whether a stamp is EARNED is never stored: it is counted from the
	// record of cleared dungeons each time (Dungeons::ClearedIn). What is stored is what is ON THIS CARD, in the order
	// it was stamped: a replacement card starts with none and is stamped again counter by counter.
	std::vector<std::string> HoldStamps();                         // counter cities, in the order stamped
	void SetHoldStamps(std::vector<std::string> a_cities);         // co-save
	bool CollectHoldStamp(const std::string& a_city);              // at that city's counter: stamps the card if earned and not there yet
	std::string StampFile(const std::string& a_city);              // "Raven Rock" -> "ravenrock": the page's tex/skin/stamp_<name>.png

	// MCM: a key that opens the card (a book cannot be favourited). SkyUI key code, 0 or less = none (the default).
	void SetHotkey(int a_key);
	void Toggle();  // what the key does: open the card in the world, or close it (also the VRIK gesture action)
	int  Hotkey();

	// co-save (Guild.cpp): the free first card has been handed over
	bool Issued();
	void SetIssued(bool a_issued);
}
