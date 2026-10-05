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

	// a_seal: image in the view's folder shown in place of the guild emblem, e.g. "tex/rank_C.png" ("" = emblem).
	void Show(std::string_view a_title, std::string_view a_subtitle, std::string_view a_seal = {}, Priority a_priority = Priority::kImportant);

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
