// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

// The guild's PrismaUI notice ("toast"): a non-interactive, non-pausing overlay used for
// registration, promotion, missive and dungeon notices (PrismaUI/views/AdventurersGuild/index.html).
// The first version (in the Ranks mod) was modelled on the look of Isekai Hero's screen-flourish
// view (github.com/dstNr/isekai-hero-skyrim, MIT); it has since been redesigned as the guild's own
// parchment notice and shares no code with it.
//
// Entirely runtime-gated: if PrismaUI isn't loaded, or the guild's view file isn't deployed,
// every call here is a safe no-op.
namespace AG::PrismaToast
{
	// At kDataLoaded: request the PrismaUI API and, if present and our view file exists,
	// create the view. Safe when neither is there.
	void Install();

	// True when the toast is actually usable (PrismaUI loaded, view valid).
	bool Active();

	// Show the flourish overlay. No-op if !Active() or the MCM toggle is off.
	// How long a notice holds depends on how much the player needs to read it:
	//   kImportant - news the game hands you mid-play (registered, promoted, promotion ready, missive done,
	//                dungeon entered / cleared): the MCM "Important notices" duration.
	//   kMinor     - confirmation of something the player just did in a menu (intel bought): "Minor notices".
	enum class Priority { kImportant, kMinor };
	// The sound a notice comes with (1.5.0): the game's own, played through sound records of ours (EspGen, Cue). Chosen by
	// ear by the author. A dungeon cleared has none (the game plays its own then), nor has anything bought in a menu.
	enum class Cue { kNone, kPromoted, kDungeonEntered, kRegistered, kPromotionReady, kComplete, kStamped, kReputationLost };

	// a_seal: image in the view's folder shown in place of the guild emblem, e.g. "tex/rank_C.png" ("" = emblem).
	void Show(std::string_view a_title, std::string_view a_subtitle, std::string_view a_seal = {}, Priority a_priority = Priority::kImportant, Cue a_cue = Cue::kNone);
	bool Sounds();              // MCM "Notice sounds" (AdventurersGuild.ini [System] NoticeSounds), on unless turned off
	void SetSounds(bool a_on);
	bool Play(Cue a_cue);       // the sound alone (dev/test); false when its record is not there

	// MCM: how long a notice stays fully visible (seconds, clamped 2..15; default 5). The whole notice is
	// that plus a 0.3 s fade-in and a 0.5 s fade-out.
	float HoldSeconds();
	void  SetHoldSeconds(float a_seconds);
	float MinorHoldSeconds();               // clamped 1..10, default 2.5
	void  SetMinorHoldSeconds(float a_seconds);

	// MCM-facing toggle (default on).
	bool Enabled();
	void SetEnabled(bool a_on);
}
