// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

#include <nlohmann/json.hpp>

// The guild cards of the other adventurers (1.5.0). The player's own card is a different item and is untouched by this.
//
// Two items. AG_MemberCard: a card that belongs to one person. Every copy carries its own display name ("Guild Card:
// Mjoll the Lioness"), as a renamed item does, and that name is what ties the copy to its record here (name, rank,
// date of registration, seal, stamps). AG_WornCard: "the remains of a card", for an adventurer with no name of their
// own; every copy is the same and there is nothing to read.
//
// Who has a name: a unique person, or one whose shown name differs from their record's (a names mod, Real Names and
// the like, renames the individual; "Hjalti [Bandit]" is read as Hjalti).
//
// A card is made when someone looks: the first time the player activates a member or opens their inventory. To the
// player they always had one; the save only holds records for cards that were seen.
//
// Handing cards in. A representative takes every card carried at once: a living owner's goes back to them, the
// others are kept by the Guild. Only a card of the dead, or a worn one, earns Reputation (guild.json), and not a
// copy the game marks as stolen: a living member's card is only ever stolen or taken in trade. A fallen party
// member's card has most representatives stand the party a round. A living member whose card is gone has a
// replacement after a few days, as the player can buy one; an old card handed in after that is kept by the Guild.
namespace AG::MemberCards
{
	void Install();  // at kDataLoaded
	void Sync();     // game thread, every few seconds and as a container closes: the two globals dialogue reads
	int  Carried();  // other adventurers' cards in the player's inventory, counted now (the card page's Field Notes)
	void HandIn(RE::Actor* a_rep);      // a representative's reply to "I found a guild card" has started

	void Given(RE::Actor* a_owner);  // from Papyrus, once the named copy is in their inventory: an open menu is refreshed
	bool IsWorn(const RE::TESForm* a_form);      // AG_WornCard: opens the card page as a sheet nothing can be read from
	bool IsPersonal(const RE::TESForm* a_form);  // AG_MemberCard: opens the card page, in its member view
	// The item name of the copy selected in the open inventory or container menu ("" when none is).
	std::string SelectedItemName();
	// What the card page shows for the copy with this item name; null when the name is not one of ours.
	nlohmann::json CardFor(const std::string& a_itemName);
	// SkyrimNet's "show your guild card" (AG_ShowGuildCard.yaml): the card this adventurer carries, opened for the player
	// to read as if they had read it themselves. A status line, for the log.
	std::string ShowCardOf(RE::Actor* a_actor);

	nlohmann::json Save();
	void           Load(const nlohmann::json& a_j);
	void           Revert();

	std::string Debug();  // records and counts, for DevBench
}
