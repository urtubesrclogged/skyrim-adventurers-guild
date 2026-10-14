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
	// ear by the author. A dungeon cleared has the "complete" one (it was left silent at first, on the belief that the
	// game plays its own then: clearing one in game, 2026-10-13, nothing was heard). Nothing bought in a menu has any.
	enum class Cue { kNone, kPromoted, kDungeonEntered, kRegistered, kPromotionReady, kComplete, kStamped, kReputationLost };

	// a_seal: image in the view's folder shown in place of the guild emblem, e.g. "tex/rank_C.png" ("" = emblem).
	void Show(std::string_view a_title, std::string_view a_subtitle, std::string_view a_seal = {}, Priority a_priority = Priority::kImportant, Cue a_cue = Cue::kNone);
	// MCM > Audio > Notification sounds: which sounds the notices play (AdventurersGuild.ini [System] NoticeSoundSet)
	enum class SoundSet { kDrums = 0, kSkyrim = 1, kNone = 2 };
	SoundSet Sounds();
	void     SetSounds(SoundSet a_set);
	// The sound alone. False when its record is not there, or when another mod has replaced the game's file it plays
	// (see Replaced) and a_evenIfReplaced is not set (dev/test sets it, to hear what the replacement is).
	bool Play(Cue a_cue, bool a_evenIfReplaced = false);
	// Another mod supplies its own file where the game's is: the sound heard would not be the one chosen for the notice,
	// so the notice comes without it. Looked up once, at start-up.
	bool Replaced(Cue a_cue);

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
