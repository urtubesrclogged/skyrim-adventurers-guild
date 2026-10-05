// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

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
