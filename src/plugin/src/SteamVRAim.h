#pragma once

// Lasers for Prisma UI under native SteamVR.
//
// Prisma UI 1.5.1 points at its VR panels only with aim poses that OpenComposite Unleashed publishes on the game
// window (the window property "OC_AIM_POSES"); under native SteamVR nothing publishes them, so its lasers are dead and
// a panel can be opened but not used, or even closed (reported 2026-10-10; reproduced by the author on FUS the same
// day; Prisma UI's log: "OC aim pose data unavailable; VR laser input requires OpenComposite Unleashed"). Prisma UI's
// licence forbids distributing a modified build, so this plugin publishes the same data itself, from SteamVR's own
// controller poses. Everything else in Prisma UI's laser (the beams, the hit test, the trigger) already runs on
// SteamVR, so with the poses present all of it works again, for every Prisma UI panel and not only the Guild's.
namespace AG::SteamVRAim
{
	// Call once the game's data is loaded. Does nothing outside VR, under OpenComposite (it publishes the poses
	// itself), on a Prisma UI that still has its own SteamVR laser (1.5.0), or when [VR] SteamVRLasers says off.
	void Install();
}
