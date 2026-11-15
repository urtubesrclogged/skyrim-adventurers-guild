#pragma once
// The Guild Hall's outside, in AG's DLL: navmesh.cpp (the navmesh patches and the hall's natives), hall.cpp (the hall the
// DLL places and keeps) and outdoor.cpp (its outdoor navmesh). All of it waits on the hall's plugin (AG::GuildHall::Loaded()).

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
	std::string OutdoorStatus();
	void        OutdoorSetInfoLinks(bool a_on);

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
	bool RegisterPapyrus(RE::BSScript::IVirtualMachine* a_vm);      // HallStatus, HallRebuild, HallRemove, HallRef
}
