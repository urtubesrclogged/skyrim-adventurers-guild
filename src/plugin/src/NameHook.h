#pragma once

namespace AG::Names
{
	// 0 = off, 1 = suffix at every patched call site, 2 = only at whitelisted sites
	void Install();  // scan .text for calls to GetDisplayFullName and route them through our thunk
	void SetMode(int a_mode);
	// Interact prompt: guild rank "(C)" / "(C, retired)" on adventurers only.
	// Enemy health meter: guild rank on adventurers, threat rank "[C]" on everything else you fight.
	void SetShowGuild(bool a_on);
	bool ShowGuild();
	void SetShowThreat(bool a_on);
	bool ShowThreat();
	int  GetMode();
	void AllowSite(int a_rva, bool a_on);
	void ClearAllowed();
	void ResetCounts();
	std::vector<std::string> SiteReport();  // "rva|count|sample|A/-" sorted by hit count
}
