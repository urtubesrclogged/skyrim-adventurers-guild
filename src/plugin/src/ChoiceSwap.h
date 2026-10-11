// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

// Show Guild Card: a topic of the mod's own is offered to the player in place of a vanilla choice (a guard's Persuade,
// the robber's Intimidate) when one of its replies would be said. Done as the game builds the list of choices, so the
// plugin file carries no vanilla dialogue record. See ChoiceSwap.cpp.
namespace AG::ChoiceSwap
{
	void Install();  // at kDataLoaded, once the forms exist. Needs room in the trampoline (Names::Install makes it).
}
