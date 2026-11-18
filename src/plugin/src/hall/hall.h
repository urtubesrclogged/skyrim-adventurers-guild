#pragma once
// The Guild Hall's outside, in AG's DLL: navmesh.cpp (the navmesh patches and the hall's natives), hall.cpp (the hall the
// DLL places and keeps) and outdoor.cpp (its outdoor navmesh). All of it waits on the hall's plugin (AG::GuildHall::Loaded()).

#include "../Diag.h"

// Main-thread time of a hall pass, in the log: always when it took kSlowMs or more (a stall shows as a black screen in VR),
// and from kNoteMs with the detailed log on.
struct HallPassTimer
{
	static constexpr long long kSlowMs = 50, kNoteMs = 5;
	const char*                           what;
	std::chrono::steady_clock::time_point t0 = std::chrono::steady_clock::now();
	explicit HallPassTimer(const char* a_what) : what(a_what) {}
	~HallPassTimer()
	{
		const auto us = std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now() - t0).count();
		if (us >= kSlowMs * 1000 || (us >= kNoteMs * 1000 && AG::Diag::DetailedLog()))
			SKSE::log::info("Hall timing: {} took {}.{:03} ms on the main thread{}", what, us / 1000, us % 1000, us >= kSlowMs * 1000 ? " (slow)" : "");
	}
};

namespace Nav
{
	// Stitch every patch in Data/SKSE/Plugins/AdventurersGuild/Hall/navmesh/ into its navmesh where that navmesh is loaded and
	// does not hold it yet (a cell reload gives back the plugin's navmesh). On the game's main thread.
	void AutoApply();
	// Take every stitched patch out again.
	void RevertAll();

	// The hall's outdoor navmesh (outdoor.cpp): fitted into the loaded ground navmesh once the hall's cells are loaded.
	void        OutdoorApply();
	void        OutdoorRevert();
	void        OutdoorPreLoad();   // before a save loads: the swap taken out
	void        OutdoorGroundChanged();   // the hall hid (or hid again) refs on the ground: wait for the game's obstacle work
	std::string OutdoorStatus();
	void        OutdoorSetInfoLinks(bool a_on);
	// The outdoor navmesh's diagnostic (AGHallNative.OutdoorNav): "status", "watch", "last"
	std::string OutdoorNavStep(const std::string& a_step);
	// The stair foot (world x y z, on the land) that the door landing nearest a_out leads down to, from outdoor_nav.json alone;
	// none: a_why says what is missing
	std::optional<std::array<float, 3>> StairFoot(const RE::NiPoint3& a_out, std::string& a_why);

	// AG's DLL (main.cpp) hands these on: its messages, and its Papyrus registration (the AGHallNative class)
	void OnMessage(SKSE::MessagingInterface::Message* a_msg);
	bool RegisterPapyrus(RE::BSScript::IVirtualMachine* a_vm);
}

namespace Hall
{
	void Save(SKSE::SerializationInterface* a_intfc);               // the HALL record in AG's co-save (Guild.cpp)
	void Load(SKSE::SerializationInterface* a_intfc, std::uint32_t a_type, std::uint32_t a_version);
	void Revert();
	void OnDataLoaded();
	void OnGameLoaded(bool a_newGame);                              // after a save loads, or a new game starts
	bool Standing();                                                // the hall's pieces are placed in this game (not while g_lock is held)
	// The installed hall's site, from its layout (read at data load): its place (AG_GuildHallSiteGlobal: 1 Riverwood, 2 Solitude; 0
	// with no hall installed), where it stands, its map marker's spot and facing, its Helios sky region (0: none, or no Helios)
	int                                           SitePlace();
	std::optional<RE::NiPoint3>                   SitePos();
	std::optional<std::pair<RE::NiPoint3, float>> MarkerSpot();
	RE::FormID                                    HeliosRegion();

	// No grass through the hall's ground (grass.cpp): the engine's hand-over of a cell's grass checked and hooked at kPostLoad, the
	// hall's ground read at data load
	void GrassInstall();
	void GrassOnDataLoaded();
	bool RegisterPapyrus(RE::BSScript::IVirtualMachine* a_vm);      // HallStatus, HallRebuild, HallRemove, HallRef, HallWayOut, HallAnchor

	// The hall's map marker (marker.cpp): a run-time MapMarker reference on the forecourt, kept in the co-save's HMRK record
	void               MarkerEnsure(const char* a_why);  // on the main thread: made, given its map data, on the player's list
	RE::TESObjectREFR* MapMarker();                       // the marker, or none (no hall, or not made yet)
	void               MarkerRemove();                    // HallRemove: taken down
	void               MarkerSave(SKSE::SerializationInterface* a_intfc);
	void               MarkerLoad(SKSE::SerializationInterface* a_intfc, std::uint32_t a_type, std::uint32_t a_version);
	void               MarkerRevert();
}
