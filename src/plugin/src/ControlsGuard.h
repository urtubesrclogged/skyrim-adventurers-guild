// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

// PrismaUI's VR module (PrismaVR) switches the player's fighting controls off while a controller's laser is on one of
// its panels, so a trigger click on the panel doesn't swing or cast, and switches them back on when the laser
// leaves. If the panel is hidden while the laser is still on it - clicking Close, or a notice fading out under the
// player's hand - they are never switched back on: no weapon draw, no casting, and the engine saves that state.
// (Measured in MGO, PrismaUI 1.5.0 under OpenComposite: the flag follows the laser at 0xFFFFFFBF / 0xFFFFFFFF.)
//
// Every panel of ours calls Shown() before it appears and Hidden() once it is gone. When the last one is gone, any
// player control that was on before the first appeared and is off now is turned back on.
namespace AG::ControlsGuard
{
	void Shown();
	void Hidden();

	// For a panel with nothing to click (the notice): PrismaVR masks fighting for it all the same, which would block
	// casting and weapon draw mid-fight for as long as the player's hand points at it. Called repeatedly on the game
	// thread while such a panel is up, this turns back on whatever was on before it appeared.
	void KeepOn();

	// The counter, in VR. PrismaVR's masking cannot be relied on: under SteamVR it does not happen at all (measured in
	// FUS, PrismaUI 1.5.0: every control stays on with the laser on the panel), so the trigger pull that clicks a
	// button also readies the player's weapon. The counter therefore switches fighting off itself while it is open,
	// as the game's own menus do, and back on when it closes. The flag is written directly, the way PrismaVR does it
	// (no event: nothing sheathes or reacts). Mask() after Shown(), Unmask() before Hidden().
	void Mask();
	void Unmask();
	bool Masked();  // for the co-save: the engine saves the control flags, so a save made with the counter open has
	                // fighting off; Saved(true) on load + OnGameLoaded() turn it back on
	void Saved(bool a_masked);
	void OnGameLoaded();
}
