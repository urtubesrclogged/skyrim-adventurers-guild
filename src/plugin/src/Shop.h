#pragma once

#include <nlohmann/json.hpp>

// What Merit buys at the guild counter, and the trophies the Guild takes in exchange for Merit.
// Catalog: shop.resolved.json / trophies.resolved.json (tools/EspGen resolves the editor IDs in
// config/.../shop.json and trophies.json against the vanilla masters). Appraisal tiers: guild.json.
namespace AG::Shop
{
	void Load();  // at kDataLoaded (and AG_Native.ReloadConfig)

	// Rows for the counter's Services tab: {section,id,name,desc,cost,available,note}. Called with the
	// Guild lock held, so it must not call back into Guild.
	nlohmann::json ServicesData(int a_rank, int a_merit, int a_appraisal, const std::array<int, 3>& a_training);
	std::string    Buy(const std::string& a_id);  // "appraisal", "train:<0-2>", "lib:<Skill>", "tome:<n>", "supply:<n>"

	// Trophies tab: the trophy items the player carries, with their Merit value.
	nlohmann::json TrophiesData();
	std::string    TurnIn(const std::string& a_key);  // one item key ("Plugin|0xID") or "all"

	int TrophyBonusPercent(int a_appraisal);
}
