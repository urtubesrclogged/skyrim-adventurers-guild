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
}
