// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

#include <nlohmann/json.hpp>

// Who holds a GUILD rank. Only adventurers do. Everything else you fight shows a THREAT rank
// (RankCore::ThreatRank). Rules come from adventurers.resolved.json (tools/EspGen resolves the
// editor IDs in config/.../adventurers.json against the vanilla masters).
//
// Checks, first match wins:
//   already recruited (co-save) -> member
//   current player teammate     -> joins on the spot (covers custom followers with no vanilla faction)
//   joinOnRecruit exception     -> no guild rank until recruited (housecarls, Serana, Companions...)
//   members factions            -> member (anyone who can be a follower or hired)
//   chance groups               -> member / retired / hidden, by a hash of the reference FormID
//                                  (the same NPC always gets the same answer, no save data)
// An NPC adventurer's rank comes from their level.
namespace AG::Adventurers
{
	enum class Kind : std::uint8_t
	{
		kNone,
		kMember,
		kRetired,
		kHidden,  // an assassin's secret membership: never shown on the name
	};

	struct Info
	{
		Kind kind{ Kind::kNone };
		int  rank{ -1 };
	};

	void        Load();                  // at kDataLoaded
	Info        Of(RE::Actor* a_actor);  // NPCs only; the player's rank lives in Guild
	const char* KindName(Kind a_kind);
	std::string Describe(RE::Actor* a_actor);  // debug: kind, rank and the rule that decided it
	// A named member's line for their SkyrimNet bio (adventurers.json "named": note / retiredNote), or "".
	std::string Note(RE::Actor* a_actor);

	// An NPC signs themselves up (SkyrimNet action AG_JoinAdventurersGuild): remembered like a recruited follower, so
	// they hold a rank from their level from now on. Refused for members, retired adventurers (Neutrality Oath),
	// children and the Guild reps. A hidden (assassin) membership becomes an open one. Returns a short status.
	std::string Join(RE::Actor* a_actor);
	// "can_join", or why not ("member", "retired", "guard", "child", "guild_rep", "invalid"): the SkyrimNet action's
	// eligibility rule (decorator ag_join_status) and Join() share it, so the AI is never offered a join that is refused.
	std::string JoinStatus(RE::Actor* a_actor);

	// The innkeepers who keep a guild counter: one per hold capital (dialogue.json "liaisons").
	bool IsLiaison(RE::Actor* a_actor);
	// Successors (dialogue.json "successor": Ysolda after Hulda) whose liaison is dead, wherever they are standing.
	// Game thread. Guild adds them to AG_GuildLiaisonFaction. IsLiaison() is true for them only at their inn.
	std::vector<RE::Actor*> SucceededLiaisons();
	bool                    IsLiaisonBase(RE::FormID a_base);  // one of the nine, or a successor's base (for death watching)
	std::string LiaisonCity(RE::TESObjectREFR* a_ref);  // "Whiterun" for Hulda, "" for anyone else

	// co-save (part of Guild's record)
	nlohmann::json Save();
	void           Load(const nlohmann::json& a_j);
	void           Revert();

	// "Plugin.esp|0x00ABCD" for a form, stable across load-order changes ("FF|0x..." for runtime refs)
	std::string StableKey(const RE::TESForm* a_form);
	// The form a saved key names, or nullptr. Also understands keys written by builds before 1.1.0, which named the
	// wrong plugin for a form another mod overrides (see StableKey).
	RE::TESForm* FormOfKey(const std::string& a_key);
	// A saved key as StableKey writes it today (unchanged if its form cannot be found, e.g. the mod was removed).
	std::string  CanonicalKey(const std::string& a_key);
	// How CanonicalKey fared since the last call (reset by it): keys it changed, and keys whose form it could not find.
	// Logged after a co-save loads: on a save whose keys were always right, both are 0.
	std::pair<int, int> TakeKeyStats();
}
