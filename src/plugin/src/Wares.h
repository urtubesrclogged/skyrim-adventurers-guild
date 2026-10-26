// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

#include <nlohmann/json.hpp>

#include <optional>
#include <string>
#include <vector>

// Guild Wares (1.6.0): a gear piece bought at the counter and enchanted on the spot (wares.json). The piece comes from
// vanilla's leveled lists at the player's level; its enchantment is made at run time the way the enchanting table makes
// one (BGSCreatedObjectManager + InventoryChanges::EnchantObject), from vanilla's base enchantments at a strength set by
// the tier: Guild (weak), Blessed (strong), Cursed (twice the strongest vanilla, plus a curse), Heroic (two effects).
// A worn Cursed Item carries its curse inside its enchantment; a cursed weapon's owner gets the curse as an ability
// (AdventurersGuild.esp 0xFE0+) while it is equipped.
namespace AG::Wares
{
	void Load();          // at kDataLoaded
	void OnGameLoaded();  // after the co-save is read: the curse abilities as the equipped weapons call for

	// the co-save's part (inside the Guild's JSON)
	nlohmann::json Saved();
	void           Restore(const nlohmann::json& a_j);  // an empty object on a new game or revert; never throws

	// What the counter offers: the tiers with a rank (Heroic has none until Hero status exists), in order, with the
	// player's text translated.
	struct Offer
	{
		int         tier{ 0 };
		std::string name, desc;  // "Cursed Item", what it is
		int         rank{ 0 }, merit{ 0 }, reputation{ 0 }, gold{ 0 };
	};
	std::vector<Offer> Offers();

	// A ware made: its name, and its description as the item card reads it, one line per effect (curse = the price).
	struct Made
	{
		std::string tier, name;
		struct Line
		{
			std::string text;
			bool        curse{ false };
		};
		std::vector<Line> lines;
		std::string       log;  // the same, for the log and DevBench
	};
	// Makes a ware of tier 0..3 and gives it to the player; nullopt on failure, with the reason in a_err.
	std::optional<Made> Make(int a_tier, std::string& a_err);

	void        SyncCurses();  // equipped cursed weapons -> curse abilities (main thread)
	std::string DebugDump();   // families, their vanilla ranges, the cursed weapons known
}
