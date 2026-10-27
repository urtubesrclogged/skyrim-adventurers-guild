// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

// Legacy of the Dragonborn (2.0.0), optional: its repeatable relic work (One Man's Junk, Research Project, Relic Hunt,
// The Dig, Finders Keepers) is credited as Guild work. LotD pays its own reward; each completion is a report worth a
// missive of the quest's rank (lotd.json), as a Jarl's bounty is. Nothing of LotD is changed: the quests are only
// watched, and only while LegacyoftheDragonborn.esm is loaded.
namespace AG::LotdWatch
{
	void Register();  // at kDataLoaded
	int  State();     // 0 not loaded, 1 loaded but none of its quests found (another version?), 2 active (MCM Debug page)
}
