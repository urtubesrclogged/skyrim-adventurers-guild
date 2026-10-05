#pragma once

// Support logging. The log (SKSE/AdventurersGuild.log, rewritten each launch) records what is needed to read someone
// else's problem: an environment block at startup, the loaded config, the Guild state on every load. The detailed log
// adds the high-volume lines (each kill's Reputation, each counter action and its result) - off by default, switched
// on from the MCM (Debug page) or with [Debug] DetailedLog = 1 in AdventurersGuild.ini (which also
// covers the lines written before a save is loaded).
namespace AG::Diag
{
	void Init(std::uint32_t a_skseVersion);  // at plugin load, after the log file is open: reads the ini switch
	void LogEnvironment();                   // at kDataLoaded: game, SKSE, our plugin, and the mods we depend on
	bool DetailedLog();                      // the MCM's switch
	void SetDetailedLog(bool a_on);
}
