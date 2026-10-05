#pragma once

namespace AG::LevelDisplay
{
	// Shows "N (X)" in the player's level readout (Stats menu header, Tween menu bottom bar).
	void Register();  // call at kDataLoaded
	// DevBench: set the fit mode (0 auto, 1 shift, 2 shrink; -1 keeps it) and the shrink margin (-1 keeps it), re-apply
	// to the open menus, and return what was measured on each before this call.
	std::string DebugFit(int a_mode, float a_margin);
	// DevBench: every clip in the open menus' level strip with its real bounds (call twice: the dump is made on the UI
	// thread after the first call); a_avail > 0 forces the shrink mode's room for the text, <= 0 measures it.
	std::string DebugDump(float a_avail);
	bool Enabled();
	void SetEnabled(bool a_on);
}
