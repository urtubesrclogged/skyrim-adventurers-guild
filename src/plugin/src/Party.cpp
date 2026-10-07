// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "Party.h"

#include <chrono>

#include "Adventurers.h"
#include "Guild.h"
#include "Loc.h"
#include "RankCore.h"

#include <fstream>
#include <mutex>
#include <thread>
#include <unordered_set>

namespace AG::Party
{
	namespace
	{
		struct Config
		{
			int                  fee{ 100 };
			int                  maxMembers{ 9 };  // companions besides the player: a party is at most 10
			int                  nameMax{ 32 };
			std::array<float, 5> tiers{ 0.0f, 15.0f, 35.0f, 60.0f, 85.0f };  // Bond at which each tier starts
			// Bond gains (guild.json party.bond), for each member present; see docs/PARTIES.md
			float                perFieldHour{ 0.06f };  // in-game hour in the field together
			float                maxTickHours{ 0.5f };   // a bigger jump between ticks (wait, sleep, fast travel) is not field time
			std::array<float, 6> kill{ 0.05f, 0.1f, 0.2f, 0.35f, 0.5f, 0.8f };  // by the foe's threat rank E..S
			float                bigKill{ 3.0f };        // dragons, giants, dungeon bosses
			float                killDailyCap{ 5.0f };   // Bond from kills per member per in-game day
			std::array<float, 6> dungeon{ 1.0f, 1.5f, 2.0f, 3.0f, 4.0f, 5.0f };
			std::array<float, 6> missive{ 1.0f, 1.5f, 2.5f, 4.0f, 5.0f, 6.0f };
			float                diminish{ 150.0f };     // gains shrink as Bond rises: x (1 - bond / diminish), at least x0.2
			// Renown: how far the party's name has travelled (SkyrimNet). Points from its record; see Renown().
			std::array<float, 2> renown{ 15.0f, 60.0f };  // talked about in the holds / famous across Skyrim
		};

		// the 18 skills in the order the counter's Analysis tab reads them
		constexpr std::array kSkills{ RE::ActorValue::kOneHanded, RE::ActorValue::kTwoHanded, RE::ActorValue::kArchery,
			RE::ActorValue::kDestruction, RE::ActorValue::kConjuration, RE::ActorValue::kHeavyArmor, RE::ActorValue::kLightArmor,
			RE::ActorValue::kBlock, RE::ActorValue::kRestoration, RE::ActorValue::kIllusion, RE::ActorValue::kAlteration,
			RE::ActorValue::kSmithing, RE::ActorValue::kAlchemy, RE::ActorValue::kEnchanting, RE::ActorValue::kSneak,
			RE::ActorValue::kLockpicking, RE::ActorValue::kPickpocket, RE::ActorValue::kSpeech };
		using Skills = std::array<int, kSkills.size()>;

		struct Stats
		{
			float hours{ 0.0f };   // in the field with at least one member present
			int   kills{ 0 };
			int   bigKills{ 0 };   // dragons, giants, bosses
			int   dungeons{ 0 };
			int   missives{ 0 };
			int   bestTier{ 0 };   // highest Bond tier the party has reached
			float tierDay{ -1.0f };
		};

		struct Member
		{
			std::string key;     // Adventurers::StableKey of the reference
			std::string name;    // as last seen (a member may be unloaded or dead)
			std::string status;  // "active", "former", "fallen"
			float       joined{ -1.0f };
			float       left{ -1.0f };  // left, fell, or the party disbanded
			std::string where;          // where they fell
			int         kills{ 0 };     // foes this member finished while in the party (the MVP)
		};

		struct Record
		{
			int                 id{ 0 };
			std::string         name;
			float               founded{ -1.0f };
			float               disbanded{ -1.0f };  // -1 while active
			std::vector<Member> members;
			Stats               stats;
		};

		std::mutex          g_lock;
		Config              g_cfg;
		std::vector<Record> g_parties;  // oldest first; at most one with disbanded < 0
		// Bond is between the player and each NPC, not a party membership: removing and re-adding someone, or founding a
		// new party with the same companions, keeps what was built. Keyed by Adventurers::StableKey.
		std::unordered_map<std::string, float> g_bonds;
		std::unordered_map<std::string, Skills> g_skills;      // members' skills as last seen (unloaded members still chart)
		std::unordered_map<std::string, float>  g_killBond;    // Bond from kills today, per member (killDailyCap)
		int                                     g_killDay{ -1 };
		float                                   g_lastHours{ -1.0f };  // Calendar hours at the last tick

		// ---- blessing + traits (traits.resolved.json, AG_PartyBlessing 0x8D0 and its globals) ----
		struct TraitDef
		{
			std::string id, name, unlock, effect;
			float       days{ 0.0f };         // in-field days the party needs (Nobody Left Behind)
			float       goldRewards{ 0.0f };  // percent more Guild gold (Coin-Bound), applied by Guild on payout
		};
		struct TraitCfg
		{
			float                         range{ 4096.0f };
			int                           maxActive{ 3 };
			float                         healPerTier{ 10.0f }, staminaPerTier{ 10.0f }, armor{ 20.0f };
			std::vector<RE::BGSKeyword*>  vampireKw;
			std::vector<RE::TESFaction*>  werewolfFactions, housecarlFactions;
			std::vector<RE::TESFaction*>  hirelingFactions, collegeFactions, dawnguardFactions, spouseFactions;
			std::vector<RE::TESGlobal*>   werewolfGlobals;  // the player's PlayerIsWerewolf
			std::vector<TraitDef>         traits;
		};
		TraitCfg                                g_tcfg;
		// Trait i's global in AdventurersGuild.esp (tools/EspGen: the first 8 from 0x8D3, the rest from 0xC00)
		constexpr RE::FormID TraitGlobalId(std::size_t i) { return static_cast<RE::FormID>(i < 8 ? 0x8D3 + i : 0xC00 + (i - 8)); }
		RE::SpellItem*                          g_blessing{ nullptr };
		RE::TESGlobal*                          g_gTier{ nullptr };
		RE::TESFaction* g_partyFaction{ nullptr };  // AG_PartyMemberFaction: active members, for dialogue conditions
		RE::TESGlobal*                          g_gPresent{ nullptr };
		std::unordered_map<std::string, RE::TESGlobal*> g_gTrait;  // trait id -> its global
		std::vector<std::string>                g_traitOn;     // switched on by the player (at most maxActive), in order
		std::unordered_set<std::string>         g_traitSeen;   // ever unlocked (discovered)
		std::unordered_set<std::string>         g_traitNew;    // discovered but not yet looked at on the Affinity page
		// Two questions per trait (docs/PARTIES.md, Affinity): does the ROSTER fit it - every active member, wherever
		// they are - and do the people AT THE PLAYER'S SIDE fit it right now. The roster decides what the counter offers
		// and what a visit to the counter unselects; the people present decide whether a chosen trait is in effect.
		std::unordered_set<std::string>         g_unlocked;    // the roster fits it (last evaluation): choosable at the counter
		std::unordered_set<std::string>         g_active;      // chosen, the roster fits it, and those present fit it: in effect
		std::unordered_map<std::string, std::string> g_why;    // roster-fitting trait -> why ("Lydia is a housecarl")
		bool                                    g_rosterKnown = true;  // every active member could be read (now or from the last reading)
		// for the HUD line when a chosen trait pauses or resumes during play
		std::unordered_set<std::string>         g_lastOn, g_lastActive;
		bool                                    g_haveLast = false;
		std::unordered_map<std::string, std::chrono::steady_clock::time_point> g_lastSaid;
		// since when an active trait's condition has not held among those present: it only goes inactive after kGrace,
		// so followers catching up after a door, a fast travel or a sprint do not flick it off and on
		std::unordered_map<std::string, std::chrono::steady_clock::time_point> g_unmetSince;
		constexpr auto kGrace = std::chrono::seconds(20);
		std::unordered_set<std::string>         g_blessed;     // members we gave the ability to (to take it back)

		float BondLocked(const std::string& a_key)
		{
			auto it = g_bonds.find(a_key);
			return it == g_bonds.end() ? 0.0f : it->second;
		}

		// caller holds g_lock
		Record* ActiveLocked()
		{
			for (auto& p : g_parties)
				if (p.disbanded < 0.0f) return &p;
			return nullptr;
		}

		Member* FindLocked(Record& a_party, const std::string& a_key)
		{
			for (auto& m : a_party.members)
				if (m.key == a_key) return &m;
			return nullptr;
		}

		float MeanLocked(const Record& a_party)
		{
			float sum = 0.0f;
			int   n = 0;
			for (auto& m : a_party.members)
				if (m.status == "active") { sum += BondLocked(m.key); ++n; }
			return n ? sum / static_cast<float>(n) : 0.0f;
		}

		int TierOf(float a_bond)
		{
			int t = 0;
			for (int i = 0; i < 5; ++i)
				if (a_bond >= g_cfg.tiers[i]) t = i;
			return t;
		}

		// A StableKey back to the actor ("Plugin.esp|0x00ABCD" or "FF|0x..."); nullptr if gone.
		RE::Actor* Resolve(const std::string& a_key)
		{
			auto* f = Adventurers::FormOfKey(a_key);
			return f ? f->As<RE::Actor>() : nullptr;
		}

		// A party name as typed: control characters dropped, whitespace collapsed, trimmed, capped (UTF-8 safe).
		std::string Clean(std::string a_name)
		{
			std::string out;
			bool        space = false;
			for (unsigned char c : a_name) {
				if (c < 0x20 || c == 0x7F) c = ' ';
				if (c == ' ') { space = !out.empty(); continue; }
				if (space) { out += ' '; space = false; }
				out += static_cast<char>(c);
			}
			if (static_cast<int>(out.size()) > g_cfg.nameMax) {
				std::size_t cut = g_cfg.nameMax;
				while (cut > 0 && (static_cast<unsigned char>(out[cut]) & 0xC0) == 0x80) --cut;  // not mid-character
				out.resize(cut);
				while (!out.empty() && out.back() == ' ') out.pop_back();
			}
			return out;
		}

		std::string WhereOf(RE::Actor* a_actor)
		{
			if (auto* loc = a_actor->GetCurrentLocation(); loc && loc->GetFullName() && *loc->GetFullName()) return loc->GetFullName();
			if (auto* cell = a_actor->GetParentCell(); cell && cell->GetFullName() && *cell->GetFullName()) return cell->GetFullName();
			return {};
		}

		bool Following(RE::Actor* a_actor) { return a_actor && !a_actor->IsDead() && a_actor->IsPlayerTeammate(); }

		// Followers travelling with the player now (loaded, high process) who are Guild adventurers.
		std::vector<RE::Actor*> NearbyAdventurers()
		{
			std::vector<RE::Actor*> out;
			if (auto* pl = RE::ProcessLists::GetSingleton())
				for (auto& h : pl->highActorHandles)
					if (auto a = h.get(); a && Following(a.get()) && Adventurers::Of(a.get()).kind == Adventurers::Kind::kMember) out.push_back(a.get());
			return out;
		}

		void Hud(const std::string& a_msg) { RE::SendHUDMessage::ShowHUDMessage(a_msg.c_str()); }

		std::string TierWord(int a_tier)
		{
			switch (a_tier) {
			case 1: return Loc::T("$AG_Bond_Companions", "Companions");
			case 2: return Loc::T("$AG_Bond_Comrades", "Comrades");
			case 3: return Loc::T("$AG_Bond_Sworn", "Sworn");
			case 4: return Loc::T("$AG_Bond_Legend", "Legend");
			default: return Loc::T("$AG_Bond_Strangers", "Strangers");
			}
		}

		template <class T>
		T* FormOf(const std::string& a_key)  // "Plugin.esp|0x0ABCDE"
		{
			const auto bar = a_key.find('|');
			auto*      dh = RE::TESDataHandler::GetSingleton();
			if (bar == std::string::npos || !dh) return nullptr;
			try {
				return dh->LookupForm<T>(static_cast<RE::FormID>(std::stoul(a_key.substr(bar + 1), nullptr, 16)), a_key.substr(0, bar));
			} catch (...) { return nullptr; }
		}

		template <class T>
		std::vector<T*> FormsOf(const nlohmann::json& a_list)
		{
			std::vector<T*> out;
			if (a_list.is_array())
				for (auto& k : a_list)
					if (auto* f = FormOf<T>(k.get<std::string>())) out.push_back(f);
			return out;
		}

		bool InAny(RE::Actor* a_actor, const std::vector<RE::TESFaction*>& a_factions)
		{
			return std::ranges::any_of(a_factions, [&](auto* f) { return a_actor->IsInFaction(f); });
		}

		bool IsVampire(RE::Actor* a_actor)
		{
			auto* race = a_actor->GetRace();
			return race && std::ranges::any_of(g_tcfg.vampireKw, [&](auto* k) { return race->HasKeyword(k); });
		}

		bool IsWerewolf(RE::Actor* a_actor)
		{
			if (a_actor->IsPlayerRef() && std::ranges::any_of(g_tcfg.werewolfGlobals, [](auto* g) { return g->value >= 1.0f; })) return true;
			if (auto* race = a_actor->GetRace(); race && std::string_view(race->GetFormEditorID()).contains("Werewolf")) return true;  // transformed
			return InAny(a_actor, g_tcfg.werewolfFactions);
		}

		// A Nord vampire is a Nord: vanilla vampire races are "<Race>Vampire".
		std::string BaseRace(RE::Actor* a_actor)
		{
			auto* race = a_actor->GetRace();
			std::string id = race ? race->GetFormEditorID() : "";
			if (id.empty() && race) id = std::format("{:08X}", race->GetFormID());
			if (id.ends_with("Vampire")) id.resize(id.size() - 7);
			return id;
		}

		bool Female(RE::Actor* a_actor)
		{
			auto* base = a_actor->GetActorBase();
			return base && base->GetSex() == RE::SEX::kFemale;
		}

		Skills Read(RE::Actor* a_actor)
		{
			Skills s{};
			if (auto* av = a_actor ? a_actor->AsActorValueOwner() : nullptr)
				for (std::size_t i = 0; i < kSkills.size(); ++i) s[i] = static_cast<int>(std::round(av->GetBaseActorValue(kSkills[i])));
			return s;
		}

		// Active members with the player now: alive, a player teammate (recruited, not dismissed) and 3D loaded. No
		// distance test: a follower who lags, is stuck on a rock or fights up the road is still with the player, and the
		// game only keeps the area around the player loaded anyway. Bond only grows, and the party's deeds only count,
		// while at least one is. (No lock held: this touches game state.)
		std::vector<std::pair<std::string, RE::Actor*>> Present()
		{
			std::vector<std::string> keys;
			{
				std::lock_guard l(g_lock);
				auto* p = ActiveLocked();
				if (!p) return {};
				for (auto& m : p->members)
					if (m.status == "active") keys.push_back(m.key);
			}
			auto* pc = RE::PlayerCharacter::GetSingleton();
			std::vector<std::pair<std::string, RE::Actor*>> out;
			if (!pc) return out;
			for (auto& k : keys) {
				auto* a = Resolve(k);
				if (a && Following(a) && a->Is3DLoaded()) out.emplace_back(k, a);
			}
			return out;
		}

		// Bond for the members present (diminishing as it rises); announces a new highest party tier.
		void Gain(const std::vector<std::pair<std::string, RE::Actor*>>& a_present, float a_amount, bool a_kill)
		{
			if (a_present.empty() || a_amount <= 0.0f) return;
			std::string party;
			int         tier = -1;
			{
				std::lock_guard l(g_lock);
				auto* p = ActiveLocked();
				if (!p) return;
				const int today = static_cast<int>(Guild::Day());
				if (a_kill && today != g_killDay) { g_killBond.clear(); g_killDay = today; }
				for (auto& [key, actor] : a_present) {
					float add = a_amount;
					if (a_kill) {
						auto& used = g_killBond[key];
						add = std::min(add, std::max(0.0f, g_cfg.killDailyCap - used));
						used += add;
					}
					const float b = BondLocked(key);
					g_bonds[key] = std::clamp(b + add * std::max(0.2f, 1.0f - b / g_cfg.diminish), 0.0f, 100.0f);
				}
				const int now = TierOf(MeanLocked(*p));
				if (now > p->stats.bestTier) {
					p->stats.bestTier = tier = now;
					p->stats.tierDay = Guild::Day();
					party = p->name;
				}
			}
			if (tier > 0) {
				Guild::Record(Loc::F("$AG_Log_BondTier", "The bond of \"{}\" deepened: {}.", party, TierWord(tier)));
				Guild::Notify("AG_PartyBondTier", party, static_cast<float>(tier));
				Hud(Loc::F("$AG_Hud_BondTier", "Your party's bond deepens: {}.", TierWord(tier)));
			}
		}

		void SetGlobal(RE::TESGlobal* a_g, float a_v)
		{
			if (a_g) a_g->value = a_v;
		}

		void Give(RE::Actor* a_actor, bool a_on)
		{
			if (!a_actor || !g_blessing) return;
			const bool has = a_actor->HasSpell(g_blessing);
			if (a_on && !has) a_actor->AddSpell(g_blessing);
			else if (!a_on && has) a_actor->RemoveSpell(g_blessing);
		}

		// What the traits look at, per person. Read from the actor whenever it can be reached; the last reading is kept in
		// the co-save, so a member who is far away or whose reference is not loaded still counts on the roster.
		struct Facts
		{
			std::string name, race, raceName;
			bool        female = false, vampire = false, werewolf = false, housecarl = false, hireling = false, college = false, dawnguard = false,
						spouse = false;
		};
		std::unordered_map<std::string, Facts> g_facts;  // member key -> last reading

		nlohmann::json FactsJson(const Facts& f)
		{
			return { { "name", f.name }, { "race", f.race }, { "raceName", f.raceName }, { "female", f.female }, { "vampire", f.vampire },
				{ "werewolf", f.werewolf }, { "housecarl", f.housecarl }, { "hireling", f.hireling }, { "college", f.college },
				{ "dawnguard", f.dawnguard }, { "spouse", f.spouse } };
		}

		Facts FactsFrom(const nlohmann::json& j)
		{
			Facts f;
			f.name = j.value("name", std::string());
			f.race = j.value("race", std::string());
			f.raceName = j.value("raceName", std::string());
			f.female = j.value("female", false);
			f.vampire = j.value("vampire", false);
			f.werewolf = j.value("werewolf", false);
			f.housecarl = j.value("housecarl", false);
			f.hireling = j.value("hireling", false);
			f.college = j.value("college", false);
			f.dawnguard = j.value("dawnguard", false);
			f.spouse = j.value("spouse", false);
			return f;
		}

		Facts FactsOf(RE::Actor* a_actor)
		{
			Facts f;
			const bool player = a_actor->IsPlayerRef();
			auto*      race = a_actor->GetRace();
			f.name = player ? Loc::T("$AG_Party_You", "you") : std::string(a_actor->GetDisplayFullName());
			f.race = BaseRace(a_actor);
			f.raceName = race && race->GetFullName() ? race->GetFullName() : "?";
			f.female = Female(a_actor);
			f.vampire = IsVampire(a_actor);
			f.werewolf = IsWerewolf(a_actor);
			f.college = InAny(a_actor, g_tcfg.collegeFactions);
			f.dawnguard = InAny(a_actor, g_tcfg.dawnguardFactions);
			if (!player) {  // the player is nobody's housecarl, hireling or spouse
				f.housecarl = InAny(a_actor, g_tcfg.housecarlFactions);
				f.hireling = InAny(a_actor, g_tcfg.hirelingFactions);
				f.spouse = InAny(a_actor, g_tcfg.spouseFactions);
			}
			return f;
		}

		struct Fit
		{
			std::unordered_set<std::string>              ids;
			std::unordered_map<std::string, std::string> why;  // shown on the counter, so the system explains itself
		};

		// Which traits a group fits. a_group[0] is the player, the rest are companions; nobody but the player fits nothing.
		Fit Fits(const std::vector<Facts>& a_group, float a_fieldDays, const std::string& a_fallen)
		{
			Fit        f;
			const auto n = a_group.size();
			if (n < 2) return f;
			auto any = [&](bool Facts::*m) { return std::ranges::any_of(a_group, [&](auto& x) { return x.*m; }); };
			auto companions = [&](bool Facts::*m, bool a_all) {
				const auto rest = std::ranges::subrange(a_group.begin() + 1, a_group.end());
				return a_all ? std::ranges::all_of(rest, [&](auto& x) { return x.*m; }) : std::ranges::any_of(rest, [&](auto& x) { return x.*m; });
			};
			auto list = [&](auto pred) {
				std::string s;
				for (std::size_t i = 0; i < n; ++i)
					if (pred(a_group[i], i)) s += (s.empty() ? "" : ", ") + a_group[i].name;
				return s;
			};
			auto listOf = [&](bool Facts::*m) { return list([&](auto& x, std::size_t) { return x.*m; }); };
			auto everyone = [&] { return list([](auto&, std::size_t) { return true; }); };
			const bool vamp = any(&Facts::vampire), wolf = any(&Facts::werewolf);
			std::unordered_set<std::string> races;
			for (auto& x : a_group) races.insert(x.race);
			const bool allMen = !any(&Facts::female), allWomen = std::ranges::all_of(a_group, [](auto& x) { return x.female; });

			if (vamp && wolf) {
				f.ids.insert("beast");
				f.why["beast"] = Loc::F("$AG_Why_Beast", "Vampire: {}. Werewolf: {}.", listOf(&Facts::vampire), listOf(&Facts::werewolf));
			} else if (vamp || wolf) {
				f.ids.insert("night");
				f.why["night"] = vamp ? Loc::F("$AG_Why_Vampire", "{}: of the vampire's blood", listOf(&Facts::vampire))
									  : Loc::F("$AG_Why_Werewolf", "{}: a werewolf", listOf(&Facts::werewolf));
			}
			if (n >= 4 && races.size() == n) {
				f.ids.insert("diversity");
				std::string rs;
				for (auto& x : a_group) rs += (rs.empty() ? "" : ", ") + x.raceName;
				f.why["diversity"] = Loc::F("$AG_Why_Diversity", "{} of you, {} races: {}", n, n, rs);
			}
			if (n >= 3 && allMen) { f.ids.insert("brothers"); f.why["brothers"] = Loc::F("$AG_Why_Men", "All men: {}", everyone()); }
			if (n >= 3 && allWomen) { f.ids.insert("sisters"); f.why["sisters"] = Loc::F("$AG_Why_Women", "All women: {}", everyone()); }
			if (companions(&Facts::housecarl, false)) {
				f.ids.insert("carry");
				f.why["carry"] = Loc::F("$AG_Why_Housecarl", "{}: sworn to carry your burdens", listOf(&Facts::housecarl));
			}
			if (n >= 3 && races.size() == 1) { f.ids.insert("kindred"); f.why["kindred"] = Loc::F("$AG_Why_Kindred", "All {}: {}", a_group[0].raceName, everyone()); }
			if (n == 2) { f.ids.insert("duo"); f.why["duo"] = Loc::F("$AG_Why_Duo", "Just you and {}", a_group[1].name); }
			if (companions(&Facts::hireling, true)) {
				f.ids.insert("coin");
				f.why["coin"] = Loc::F("$AG_Why_Coin", "Sellswords all: {}", list([](auto&, std::size_t i) { return i > 0; }));
			}
			if (std::ranges::count_if(a_group, [](auto& x) { return x.college; }) >= 2) {
				f.ids.insert("study");
				f.why["study"] = Loc::F("$AG_Why_Study", "Of the College: {}", listOf(&Facts::college));
			}
			if (vamp && any(&Facts::dawnguard)) {
				f.ids.insert("allies");
				f.why["allies"] = Loc::F("$AG_Why_Allies", "Vampire: {}. Dawnguard: {}.", listOf(&Facts::vampire), listOf(&Facts::dawnguard));
			}
			if (companions(&Facts::spouse, false)) { f.ids.insert("honeymoon"); f.why["honeymoon"] = Loc::F("$AG_Why_Spouse", "{}: your spouse", listOf(&Facts::spouse)); }
			// from the party's own record: days in the field together, and its fallen
			const auto  nobody = std::ranges::find(g_tcfg.traits, std::string("nobody"), &TraitDef::id);
			const float needDays = nobody != g_tcfg.traits.end() && nobody->days > 0.0f ? nobody->days : 30.0f;
			if (!a_fallen.empty()) {
				f.ids.insert("memory");
				f.why["memory"] = Loc::F("$AG_Why_Memory", "In memory of {}", a_fallen);
			} else if (a_fieldDays >= needDays) {
				f.ids.insert("nobody");
				f.why["nobody"] = Loc::F("$AG_Why_Nobody", "{} days in the field, and no one lost", static_cast<int>(a_fieldDays));
			}
			return f;
		}

		// The roster decides which traits can be chosen; who is present decides which chosen ones are in effect; the Bond
		// tier and head count set the blessing. The engine applies the ability's effects from the globals (and each
		// member's distance to the player). Game thread. a_quiet: no HUD line for a trait pausing or resuming (the
		// player is at the counter, changing things on purpose).
		void Evaluate(bool a_quiet = false)
		{
			auto* pc = RE::PlayerCharacter::GetSingleton();
			if (!pc) return;
			if (Guild::Dormant()) { StripForUninstall(); return; }  // prepared for uninstall: never re-grant
			const auto present = Present();
			// the roster (every active member: read now if reachable, else as last seen) and the people present
			std::vector<Facts> roster{ FactsOf(pc) }, here{ roster[0] };
			bool               rosterKnown = true;
			float              fieldDays = 0.0f;
			std::string        fallen;
			{
				std::vector<std::string> keys;
				{
					std::lock_guard l(g_lock);
					if (auto* p = ActiveLocked()) {
						fieldDays = p->stats.hours / 24.0f;
						for (auto& m : p->members) {
							if (m.status == "active") keys.push_back(m.key);
							if (m.status == "fallen") fallen += (fallen.empty() ? "" : ", ") + m.name;
						}
					}
				}
				for (auto& k : keys) {
					auto* a = Resolve(k);
					if (a && a->IsDead()) continue;  // dead, not yet marked fallen: no longer counts
					if (a) {
						roster.push_back(FactsOf(a));
						std::lock_guard l(g_lock);
						g_facts[k] = roster.back();
					} else {
						std::lock_guard l(g_lock);
						if (auto it = g_facts.find(k); it != g_facts.end()) roster.push_back(it->second);
						else rosterKnown = false;  // never read: say nothing about this roster rather than guess
					}
				}
			}
			for (auto& [k, a] : present) here.push_back(FactsOf(a));
			auto       eligible = Fits(roster, fieldDays, fallen);
			auto       met = Fits(here, fieldDays, fallen);
			// What the party earned from its own record - a fallen member remembered, days in the field with no one lost -
			// does not depend on who is standing next to the player: it holds for as long as the roster fits it.
			for (const char* id : { "memory", "nobody" })
				if (eligible.ids.contains(id)) met.ids.insert(id);
			auto&      unlocked = eligible.ids;
			auto&      why = eligible.why;
			std::vector<RE::Actor*> members;  // active members, resolved (loaded or not)
			std::vector<std::string> formerKeys;
			std::vector<std::string> discovered;  // trait names unlocked for the first time
			std::vector<std::pair<std::string, bool>> changed;  // chosen traits that just resumed (true) or paused (false)
			int                      freeSlots = 0;
			bool   hasParty;
			int    tier = -1;
			std::unordered_set<std::string> active;
			{
				std::lock_guard l(g_lock);
				auto* p = ActiveLocked();
				hasParty = p != nullptr;
				for (auto& id : unlocked) {
					if (!g_traitSeen.insert(id).second) continue;
					// Discovered. Not switched on: the player chooses on the counter (Beast Buds alone takes over the slot of
					// Creatures of the Night, which it supersedes)
					if (id == "beast")
						if (auto it = std::ranges::find(g_traitOn, std::string("night")); it != g_traitOn.end()) *it = "beast";
					g_traitNew.insert(id);
					if (auto d = std::ranges::find(g_tcfg.traits, id, &TraitDef::id); d != g_tcfg.traits.end()) discovered.push_back(d->name);
				}
				freeSlots = g_tcfg.maxActive - static_cast<int>(g_traitOn.size());
				g_unlocked = unlocked;
				g_why = std::move(why);
				g_rosterKnown = rosterKnown;
				{
					const auto now = std::chrono::steady_clock::now();
					for (auto& id : g_traitOn) {
						if (!unlocked.contains(id)) { g_unmetSince.erase(id); continue; }
						if (met.ids.contains(id)) {
							g_unmetSince.erase(id);
							active.insert(id);
						} else if (!a_quiet && g_haveLast && g_lastActive.contains(id)) {
							// was active a moment ago: those present may just be catching up - hold it for kGrace
							if (now - g_unmetSince.try_emplace(id, now).first->second < kGrace) active.insert(id);
						}
					}
				}
				g_active = active;
				// a chosen trait that paused or resumed since the last look (not one just chosen or unselected)
				if (g_haveLast && !a_quiet) {
					const auto now = std::chrono::steady_clock::now();
					for (auto& id : g_traitOn) {
						if (!g_lastOn.contains(id) || g_lastActive.contains(id) == active.contains(id)) continue;
						auto& said = g_lastSaid[id];
						if (said.time_since_epoch().count() != 0 && now - said < std::chrono::seconds(20)) continue;  // a member hovering at the edge of range
						said = now;
						if (auto d = std::ranges::find(g_tcfg.traits, id, &TraitDef::id); d != g_tcfg.traits.end())
							changed.emplace_back(d->name, active.contains(id));
					}
				}
				g_lastOn = { g_traitOn.begin(), g_traitOn.end() };
				g_lastActive = active;
				g_haveLast = true;
				if (p && !present.empty()) tier = TierOf(MeanLocked(*p));
				if (p)
					for (auto& m : p->members)
						if (m.status != "active") formerKeys.push_back(m.key);
			}
			if (hasParty) {
				std::vector<std::string> keys;
				{
					std::lock_guard l(g_lock);
					for (auto& m : ActiveLocked()->members)
						if (m.status == "active") keys.push_back(m.key);
				}
				for (auto& k : keys)
					if (auto* a = Resolve(k)) { members.push_back(a); std::lock_guard l(g_lock); g_blessed.insert(k); }
			}
			SetGlobal(g_gTier, static_cast<float>(tier));
			SetGlobal(g_gPresent, static_cast<float>(present.size()));
			for (auto& [id, g] : g_gTrait) SetGlobal(g, active.contains(id) ? 1.0f : 0.0f);
			Give(pc, hasParty);
			for (auto* a : members) Give(a, !a->IsDead());
			// ... and the faction dialogue asks about ("I'm in a real adventuring party")
			if (g_partyFaction)
				for (auto* a : members)
					if (!a->IsInFaction(g_partyFaction)) a->AddToFaction(g_partyFaction, 0);
			// take it back from anyone no longer an active member
			std::vector<std::string> stale;
			{
				std::lock_guard l(g_lock);
				for (auto& k : g_blessed)
					if (!hasParty || std::ranges::find(formerKeys, k) != formerKeys.end()) stale.push_back(k);
				for (auto& k : stale) g_blessed.erase(k);
			}
			for (auto& k : stale) {
				auto* gone = Resolve(k);
				Give(gone, false);
				if (gone && g_partyFaction && gone->IsInFaction(g_partyFaction)) gone->AddToFaction(g_partyFaction, -1);  // rank -1 = out
			}
			for (auto& [name, on] : changed)
				Hud(on ? Loc::F("$AG_Hud_TraitActive", "Affinity active: {}", name) : Loc::F("$AG_Hud_TraitInactive", "Affinity inactive: {}", name));
			for (auto& name : discovered) {
				Guild::Record(Loc::F("$AG_Log_TraitFound", "Party affinity discovered: {}.", name));
				Hud(freeSlots > 0 ? Loc::F("$AG_Hud_TraitFound", "Affinity discovered: {}. Select your Affinity Bonuses at any Adventurers Guild counter.", name)
								  : Loc::F("$AG_Hud_TraitFoundFull", "Affinity discovered: {}. Swap it in at any Adventurers Guild counter.", name));
			}
		}

		void Tick()
		{
			auto* cal = RE::Calendar::GetSingleton();
			auto* pc = RE::PlayerCharacter::GetSingleton();
			if (!cal || !pc || !pc->Is3DLoaded() || Guild::Dormant()) return;
			const float hours = cal->GetDaysPassed() * 24.0f;
			float       delta;
			{
				std::lock_guard l(g_lock);
				delta = g_lastHours < 0.0f ? 0.0f : hours - g_lastHours;
				g_lastHours = hours;
			}
			const auto present = Present();
			{
				std::lock_guard l(g_lock);
				for (auto& [key, actor] : present) g_skills[key] = Read(actor);  // keep the Analysis tab current
			}
			Evaluate();
			if (present.empty() || delta <= 0.0f || delta > g_cfg.maxTickHours) return;  // a time skip is not field time
			{
				std::lock_guard l(g_lock);
				if (auto* p = ActiveLocked()) p->stats.hours += delta;
			}
			Gain(present, g_cfg.perFieldHour * delta, false);
		}
	}

	void Register()
	{
		// Field time: sampled every few seconds on the game thread; no Papyrus, no polling of any actor's AI.
		std::thread([] {
			for (;;) {
				std::this_thread::sleep_for(std::chrono::seconds(5));
				SKSE::GetTaskInterface()->AddTask([] {
					Tick();
					Guild::ConductTick();  // the player's bounties, on the same beat
				});
			}
		}).detach();
	}

	void OnKill(RE::Actor* a_victim, RE::Actor* a_killer, int a_rank, bool a_big)
	{
		const auto present = Present();
		if (present.empty() || !a_victim) return;
		const std::string killer = a_killer && !a_killer->IsPlayerRef() ? Adventurers::StableKey(a_killer) : std::string();
		float amount;
		{
			std::lock_guard l(g_lock);
			auto* p = ActiveLocked();
			if (!p) return;
			++p->stats.kills;
			if (a_big) ++p->stats.bigKills;
			if (!killer.empty())
				if (auto* m = FindLocked(*p, killer); m && m->status == "active") ++m->kills;
			amount = g_cfg.kill[std::clamp(a_rank, 0, 5)] * (a_big ? g_cfg.bigKill : 1.0f);
		}
		Gain(present, amount, true);
	}

	void OnDungeonCleared(int a_rank)
	{
		const auto present = Present();
		if (present.empty()) return;
		float amount;
		{
			std::lock_guard l(g_lock);
			auto* p = ActiveLocked();
			if (!p) return;
			++p->stats.dungeons;
			amount = g_cfg.dungeon[std::clamp(a_rank, 0, 5)];
		}
		Gain(present, amount, false);
	}

	void OnMissiveCompleted(int a_rank)
	{
		const auto present = Present();
		if (present.empty()) return;
		float amount;
		{
			std::lock_guard l(g_lock);
			auto* p = ActiveLocked();
			if (!p) return;
			++p->stats.missives;
			amount = g_cfg.missive[std::clamp(a_rank, 0, 5)];
		}
		Gain(present, amount, false);
	}

	void LoadConfig()
	{
		Config c;
		try {
			std::ifstream f("Data/SKSE/Plugins/AdventurersGuild/guild.json");
			if (f) {
				auto j = nlohmann::json::parse(f, nullptr, true, true);
				if (j.contains("party")) {
					const auto& p = j.at("party");
					c.fee = std::max(0, p.value("fee", c.fee));
					c.maxMembers = std::clamp(p.value("maxMembers", c.maxMembers), 1, 9);  // hard cap: follower mods allow dozens
					c.nameMax = std::clamp(p.value("nameMaxLength", c.nameMax), 8, 64);
					if (p.contains("bondTiers") && p.at("bondTiers").is_array() && p.at("bondTiers").size() == 5)
						for (int i = 0; i < 5; ++i) c.tiers[i] = p.at("bondTiers")[i].get<float>();
					if (p.contains("bond")) {
						const auto& b = p.at("bond");
						auto six = [&](const char* k, std::array<float, 6>& out) {
							if (b.contains(k) && b.at(k).is_array() && b.at(k).size() == 6)
								for (int i = 0; i < 6; ++i) out[i] = b.at(k)[i].get<float>();
						};
						c.perFieldHour = b.value("perFieldHour", c.perFieldHour);
						c.maxTickHours = b.value("maxTickHours", c.maxTickHours);
						six("kill", c.kill);
						c.bigKill = b.value("bigKill", c.bigKill);
						c.killDailyCap = b.value("killDailyCap", c.killDailyCap);
						six("dungeon", c.dungeon);
						six("missive", c.missive);
						c.diminish = std::max(1.0f, b.value("diminish", c.diminish));
					}
					if (p.contains("renown") && p.at("renown").is_array() && p.at("renown").size() == 2)
						for (int i = 0; i < 2; ++i) c.renown[i] = p.at("renown")[i].get<float>();
				}
			}
		} catch (const std::exception& e) {
			SKSE::log::error("Party: guild.json error: {} - using defaults", e.what());
			c = {};
		}
		TraitCfg t;
		try {
			std::ifstream f("Data/SKSE/Plugins/AdventurersGuild/traits.resolved.json");
			if (f) {
				auto j = nlohmann::json::parse(f, nullptr, true, true);
				t.range = j.value("range", t.range);
				t.maxActive = std::clamp(j.value("maxActive", t.maxActive), 0, 8);
				if (j.contains("blessing")) {
					const auto& b = j.at("blessing");
					t.healPerTier = b.value("healRatePerTier", t.healPerTier);
					t.staminaPerTier = b.value("staminaRatePerTier", t.staminaPerTier);
					t.armor = b.value("armor", t.armor);  // flat, while anyone is present
				}
				const auto& d = j.value("detect", nlohmann::json::object());
				t.vampireKw = FormsOf<RE::BGSKeyword>(d.value("vampire", nlohmann::json::object()).value("keywords", nlohmann::json::array()));
				t.werewolfFactions = FormsOf<RE::TESFaction>(d.value("werewolf", nlohmann::json::object()).value("factions", nlohmann::json::array()));
				t.werewolfGlobals = FormsOf<RE::TESGlobal>(d.value("werewolf", nlohmann::json::object()).value("globals", nlohmann::json::array()));
				t.housecarlFactions = FormsOf<RE::TESFaction>(d.value("housecarl", nlohmann::json::object()).value("factions", nlohmann::json::array()));
				auto factions = [&](const char* a_key) { return FormsOf<RE::TESFaction>(d.value(a_key, nlohmann::json::object()).value("factions", nlohmann::json::array())); };
				t.hirelingFactions = factions("hireling");
				t.collegeFactions = factions("college");
				t.dawnguardFactions = factions("dawnguard");
				t.spouseFactions = factions("spouse");
				for (auto& x : j.value("traits", nlohmann::json::array()))
					t.traits.push_back({ x.value("id", ""), x.value("name", ""), x.value("unlock", ""), x.value("effect", ""),
						x.value("days", 0.0f), x.value("goldRewards", 0.0f) });
			} else {
				SKSE::log::warn("Party: traits.resolved.json missing - no traits");
			}
		} catch (const std::exception& e) {
			SKSE::log::error("Party: traits.resolved.json error: {}", e.what());
		}
		auto* dh = RE::TESDataHandler::GetSingleton();
		auto  own = [&](RE::FormID a_id) { return dh ? dh->LookupForm(a_id, "AdventurersGuild.esp") : nullptr; };
		g_blessing = own(0x8D0) ? own(0x8D0)->As<RE::SpellItem>() : nullptr;
		g_gTier = own(0x8D1) ? own(0x8D1)->As<RE::TESGlobal>() : nullptr;
		g_partyFaction = own(0x81F) ? own(0x81F)->As<RE::TESFaction>() : nullptr;
		g_gPresent = own(0x8D2) ? own(0x8D2)->As<RE::TESGlobal>() : nullptr;
		g_gTrait.clear();
		for (std::size_t i = 0; i < t.traits.size(); ++i)
			if (auto* g = own(TraitGlobalId(i)); g && g->As<RE::TESGlobal>()) g_gTrait[t.traits[i].id] = g->As<RE::TESGlobal>();
		std::lock_guard l(g_lock);
		g_cfg = c;
		g_tcfg = std::move(t);
		SKSE::log::info("Party: fee {}, up to {} members; blessing {}, {} traits, {} trait globals ({} vampire keywords; factions: {} werewolf, {} housecarl, {} hireling, {} college, {} dawnguard, {} spouse)",
			c.fee, c.maxMembers, g_blessing ? "ok" : "MISSING", g_tcfg.traits.size(), g_gTrait.size(), g_tcfg.vampireKw.size(), g_tcfg.werewolfFactions.size(),
			g_tcfg.housecarlFactions.size(), g_tcfg.hirelingFactions.size(), g_tcfg.collegeFactions.size(), g_tcfg.dawnguardFactions.size(), g_tcfg.spouseFactions.size());
	}

	int GoldRewardPercent()
	{
		std::lock_guard l(g_lock);
		float pct = 0.0f;
		for (auto& d : g_tcfg.traits)
			if (d.goldRewards > 0.0f && g_active.contains(d.id)) pct += d.goldRewards;
		return static_cast<int>(pct);
	}

	void TraitsViewed()
	{
		std::lock_guard l(g_lock);
		g_traitNew.clear();
	}

	std::string ToggleTrait(const std::string& a_id)
	{
		std::string name;
		bool        on;
		{
			std::lock_guard l(g_lock);
			auto def = std::ranges::find(g_tcfg.traits, a_id, &TraitDef::id);
			if (def == g_tcfg.traits.end() || !g_traitSeen.contains(a_id)) return {};
			name = def->name;
			if (auto it = std::ranges::find(g_traitOn, a_id); it != g_traitOn.end()) {
				g_traitOn.erase(it);
				on = false;
			} else {
				if (static_cast<int>(g_traitOn.size()) >= g_tcfg.maxActive)
					return Loc::F("$AG_Party_TraitsFull", "Only {} affinities can be selected at once: unselect one first.", g_tcfg.maxActive);
				if (!g_unlocked.contains(a_id)) return Loc::F("$AG_Party_TraitNoFit", "{} does not fit this party.", name);
				g_traitOn.push_back(a_id);
				on = true;
			}
		}
		Evaluate(true);
		return on ? Loc::F("$AG_Party_TraitOn", "{} is selected.", name) : Loc::F("$AG_Party_TraitOff", "{} is unselected.", name);
	}

	std::string Found(std::string a_name, const std::vector<RE::Actor*>& a_founders)
	{
		if (!Guild::Registered()) return Loc::T("$AG_Party_NeedRegistered", "Register with the Adventurers Guild before founding a party.");
		// a party of one is not a party: at least one follower adventurer at your side joins at the founding
		std::vector<RE::Actor*> founders;
		for (auto* a : a_founders)
			if (a && Following(a) && Adventurers::Of(a).kind == Adventurers::Kind::kMember && std::ranges::find(founders, a) == founders.end()) founders.push_back(a);
		if (founders.empty()) return Loc::T("$AG_Party_NeedFounder", "A party needs at least one companion: bring a follower who is a Guild adventurer.");
		std::string name;
		{
			std::lock_guard l(g_lock);
			if (ActiveLocked()) return Loc::T("$AG_Party_AlreadyLead", "You already lead a party. Disband it before founding another.");
			if (static_cast<int>(founders.size()) > g_cfg.maxMembers) return Loc::F("$AG_Party_Full", "Your party is full ({} members).", g_cfg.maxMembers);
			name = Clean(std::move(a_name));
		}
		if (name.empty()) return Loc::T("$AG_Party_NeedName", "Your party needs a name.");
		if (!Guild::PayGold(g_cfg.fee))
			return Loc::F("$AG_Party_FeeNeeded", "The Guild's party registration fee is {} gold.", g_cfg.fee);
		std::vector<std::string> names;
		{
			std::lock_guard l(g_lock);
			Record r;
			r.id = g_parties.empty() ? 1 : g_parties.back().id + 1;
			r.name = name;
			r.founded = Guild::Day();
			for (auto* a : founders) {
				r.members.push_back({ Adventurers::StableKey(a), a->GetDisplayFullName(), "active", r.founded });
				names.push_back(a->GetDisplayFullName());
			}
			g_parties.push_back(std::move(r));
		}
		Guild::Record(Loc::F("$AG_Log_PartyFounded", "Founded the party \"{}\".", name));
		for (auto& n : names) {
			Guild::Record(Loc::F("$AG_Log_PartyJoined", "{} joined the party \"{}\".", n, name));
			Guild::Notify("AG_PartyMemberJoined", n, 0.0f);
		}
		Guild::Notify("AG_PartyFounded", name, 0.0f);
		SKSE::log::info("Party: founded '{}'", name);
		return Loc::F("$AG_Party_Founded", "Your party, {}, is registered with the Adventurers Guild.", name);
	}

	std::string Rename(std::string a_name)
	{
		std::string from, to;
		{
			std::lock_guard l(g_lock);
			auto* p = ActiveLocked();
			if (!p) return Loc::T("$AG_Party_NoParty", "You do not lead a party.");
			to = Clean(std::move(a_name));
			if (to.empty()) return Loc::T("$AG_Party_NeedName", "Your party needs a name.");
			if (to == p->name) return {};
			from = std::exchange(p->name, to);
		}
		Guild::Record(Loc::F("$AG_Log_PartyRenamed", "Renamed the party \"{}\" to \"{}\".", from, to));
		Guild::Notify("AG_PartyRenamed", to, 0.0f);
		return Loc::F("$AG_Party_Renamed", "Your party is now called {}.", to);
	}

	std::string Disband()
	{
		std::string name;
		{
			std::lock_guard l(g_lock);
			auto* p = ActiveLocked();
			if (!p) return Loc::T("$AG_Party_NoParty", "You do not lead a party.");
			const float today = Guild::Day();
			p->disbanded = today;
			for (auto& m : p->members)
				if (m.status == "active") { m.status = "former"; m.left = today; }
			name = p->name;
		}
		Guild::Record(Loc::F("$AG_Log_PartyDisbanded", "Disbanded the party \"{}\".", name));
		Guild::Notify("AG_PartyDisbanded", name, 0.0f);
		SKSE::log::info("Party: disbanded '{}'", name);
		return Loc::F("$AG_Party_Disbanded", "{} is disbanded. The Guild keeps its page in the ledger.", name);
	}

	std::string Add(RE::Actor* a_actor)
	{
		if (!a_actor || a_actor->IsPlayerRef() || a_actor->IsDead()) return {};
		if (!Following(a_actor)) return Loc::F("$AG_Party_NotFollowing", "{} must be travelling with you to join your party.", a_actor->GetDisplayFullName());
		if (Adventurers::Of(a_actor).kind != Adventurers::Kind::kMember)
			return Loc::F("$AG_Party_NotMember", "{} is not an adventurer of the Guild.", a_actor->GetDisplayFullName());
		const std::string key = Adventurers::StableKey(a_actor), name = a_actor->GetDisplayFullName();
		std::string party;
		{
			std::lock_guard l(g_lock);
			auto* p = ActiveLocked();
			if (!p) return Loc::T("$AG_Party_NoParty", "You do not lead a party.");
			const auto active = std::ranges::count_if(p->members, [](auto& m) { return m.status == "active"; });
			auto* m = FindLocked(*p, key);
			if (m && m->status == "active") return Loc::F("$AG_Party_Already", "{} is already in your party.", name);
			if (m && m->status == "fallen") return {};
			if (active >= g_cfg.maxMembers) return Loc::F("$AG_Party_Full", "Your party is full ({} members).", g_cfg.maxMembers);
			if (m) {  // a former member rejoining (their Bond is theirs, kept in g_bonds either way)
				m->status = "active";
				m->joined = Guild::Day();
				m->left = -1.0f;
				m->name = name;
			} else {
				p->members.push_back({ key, name, "active", Guild::Day() });
			}
			party = p->name;
		}
		Guild::Record(Loc::F("$AG_Log_PartyJoined", "{} joined the party \"{}\".", name, party));
		Guild::Notify("AG_PartyMemberJoined", name, 0.0f);
		return Loc::F("$AG_Party_Joined", "{} joins {}.", name, party);
	}

	std::string Remove(const std::string& a_key)
	{
		std::string name, party;
		{
			std::lock_guard l(g_lock);
			auto* p = ActiveLocked();
			if (!p) return Loc::T("$AG_Party_NoParty", "You do not lead a party.");
			auto* m = FindLocked(*p, a_key);
			if (!m || m->status != "active") return {};
			m->status = "former";
			m->left = Guild::Day();
			name = m->name;
			party = p->name;
		}
		Guild::Record(Loc::F("$AG_Log_PartyLeft", "{} left the party \"{}\".", name, party));
		Guild::Notify("AG_PartyMemberLeft", name, 0.0f);
		return Loc::F("$AG_Party_Left", "{} leaves {}.", name, party);
	}

	void OnDeath(RE::Actor* a_actor)
	{
		if (!a_actor || a_actor->IsPlayerRef()) return;
		const auto key = Adventurers::StableKey(a_actor);
		std::string name, party, where = WhereOf(a_actor);
		{
			std::lock_guard l(g_lock);
			auto* p = ActiveLocked();
			auto* m = p ? FindLocked(*p, key) : nullptr;
			if (!m || m->status != "active") return;  // TESDeathEvent fires twice; the second finds them fallen
			m->status = "fallen";
			m->left = Guild::Day();
			m->where = where;
			m->name = a_actor->GetDisplayFullName();
			name = m->name;
			party = p->name;
		}
		Guild::Record(where.empty() ? Loc::F("$AG_Log_PartyFell", "{} of {} fell.", name, party)
		                            : Loc::F("$AG_Log_PartyFellAt", "{} of {} fell at {}.", name, party, where));
		Guild::Notify("AG_PartyMemberFell", where.empty() ? name + " fell" : name + " fell at " + where, 0.0f);  // SkyrimNet memory
		Hud(Loc::F("$AG_Hud_PartyFell", "{} has fallen. The Guild will remember.", name));
		SKSE::log::info("Party: {} fell ({})", name, where);
	}

	bool HasParty()
	{
		std::lock_guard l(g_lock);
		return ActiveLocked() != nullptr;
	}

	std::string Name()
	{
		std::lock_guard l(g_lock);
		auto* p = ActiveLocked();
		return p ? p->name : std::string();
	}

	bool IsActiveMember(RE::Actor* a_actor)
	{
		if (!a_actor) return false;
		const auto key = Adventurers::StableKey(a_actor);
		std::lock_guard l(g_lock);
		auto* p = ActiveLocked();
		auto* m = p ? FindLocked(*p, key) : nullptr;
		return m && m->status == "active";
	}

	float BondOf(RE::Actor* a_actor)
	{
		if (!a_actor) return 0.0f;
		const auto key = Adventurers::StableKey(a_actor);
		std::lock_guard l(g_lock);
		return BondLocked(key);
	}

	float PartyBond()
	{
		std::lock_guard l(g_lock);
		auto* p = ActiveLocked();
		return p ? MeanLocked(*p) : 0.0f;
	}

	int BondTier(float a_bond)
	{
		std::lock_guard l(g_lock);
		return TierOf(a_bond);
	}

	void AddBond(RE::Actor* a_actor, float a_amount)
	{
		if (!a_actor) return;
		const auto key = Adventurers::StableKey(a_actor);
		std::lock_guard l(g_lock);
		auto* p = ActiveLocked();
		auto* m = p ? FindLocked(*p, key) : nullptr;
		if (m && m->status == "active") g_bonds[key] = std::clamp(BondLocked(key) + a_amount, 0.0f, 100.0f);
	}

	nlohmann::json CounterData()
	{
		// actors first (no lock held while touching game state)
		const auto nearby = NearbyAdventurers();
		// "With you" means what the blessing means: a teammate, alive and loaded (Present()), so the
		// counter never shows a blessing, or a member at your side, that the engine is not applying.
		std::unordered_set<std::string> here;
		for (auto& [k, a] : Present()) here.insert(k);
		auto*      pc = RE::PlayerCharacter::GetSingleton();
		const auto mine = pc ? Read(pc) : Skills{};
		std::vector<std::pair<std::string, RE::Actor*>> live;  // active members, resolved
		{
			std::lock_guard l(g_lock);
			if (auto* p = ActiveLocked())
				for (auto& m : p->members)
					if (m.status == "active") live.emplace_back(m.key, nullptr);
		}
		for (auto& [k, a] : live) a = Resolve(k);

		nlohmann::json j;
		std::lock_guard l(g_lock);
		j["registered"] = Guild::Registered();
		j["fee"] = g_cfg.fee;
		j["max"] = g_cfg.maxMembers;
		j["nameMax"] = g_cfg.nameMax;
		auto* p = ActiveLocked();
		auto row = [&](const Member& m, bool a_live) {
			nlohmann::json r{ { "key", m.key }, { "name", m.name }, { "status", m.status }, { "joined", m.joined }, { "left", m.left },
				{ "where", m.where }, { "bond", std::round(BondLocked(m.key)) }, { "tier", TierOf(BondLocked(m.key)) } };
			if (a_live) {
				auto* a = Resolve(m.key);
				const auto info = a ? Adventurers::Of(a) : Adventurers::Info{};
				r["letter"] = info.rank >= 0 ? LetterStr(info.rank) : "?";
				r["following"] = here.contains(m.key);
			}
			return r;
		};
		if (p) {
			const float bond = MeanLocked(*p);
			auto& a = j["active"] = { { "id", p->id }, { "name", p->name }, { "founded", p->founded }, { "bond", std::round(bond) }, { "tier", TierOf(bond) },
				{ "members", nlohmann::json::array() } };
			int present = 0;
			for (auto& m : p->members)
				if (m.status == "active") {
					auto r = row(m, true);
					present += r["following"].get<bool>() ? 1 : 0;
					a["members"].push_back(std::move(r));
				}
			a["present"] = present;  // Bond and its blessing sleep while no member is at the player's side
			// Analysis: raw skills (base values, no gear) for the player and each active member, live when loaded
			auto& an = j["analysis"] = nlohmann::json::array();
			an.push_back({ { "name", pc ? pc->GetDisplayFullName() : "" }, { "player", true }, { "following", true }, { "skills", mine } });
			for (auto& [k, actor] : live) {
				auto* m = FindLocked(*p, k);
				if (!m) continue;
				if (actor && actor->Is3DLoaded()) g_skills[k] = Read(actor);
				auto it = g_skills.find(k);
				an.push_back({ { "name", m->name }, { "player", false }, { "following", here.contains(k) },
					{ "skills", it != g_skills.end() ? it->second : (actor ? Read(actor) : Skills{}) } });
			}
			// Party Traits and the Bond blessing, as the engine applies them now
			auto& tr = a["traits"] = nlohmann::json::array();
			for (auto& d : g_tcfg.traits) {
				const bool on = std::ranges::find(g_traitOn, d.id) != g_traitOn.end();
				auto w = g_why.find(d.id);
				tr.push_back({ { "id", d.id }, { "name", d.name }, { "unlock", d.unlock }, { "effect", d.effect }, { "on", on },
					{ "seen", g_traitSeen.contains(d.id) }, { "new", g_traitNew.contains(d.id) }, { "unlocked", g_unlocked.contains(d.id) }, { "active", g_active.contains(d.id) },
					{ "why", w != g_why.end() ? w->second : "" } });
			}
			a["maxTraits"] = g_tcfg.maxActive;
			const int btier = present ? TierOf(MeanLocked(*p)) : -1;
			a["blessing"] = { { "heal", btier > 0 ? btier * g_tcfg.healPerTier : 0.0f }, { "stamina", btier > 0 ? btier * g_tcfg.staminaPerTier : 0.0f },
				{ "armor", present ? g_tcfg.armor : 0.0f } };
			// the party's record together
			a["stats"] = { { "days", p->stats.hours / 24.0f }, { "kills", p->stats.kills }, { "bigKills", p->stats.bigKills },
				{ "dungeons", p->stats.dungeons }, { "missives", p->stats.missives },
				{ "former", std::ranges::count_if(p->members, [](auto& m) { return m.status == "former"; }) },
				{ "fallen", std::ranges::count_if(p->members, [](auto& m) { return m.status == "fallen"; }) },
				{ "bestTier", p->stats.bestTier }, { "tierDay", p->stats.tierDay } };
		} else {
			j["active"] = nullptr;
		}
		// followers who could join now (founding needs at least one of them)
		auto& e = j["eligible"] = nlohmann::json::array();
		for (auto* x : nearby) {
			const auto key = Adventurers::StableKey(x);
			auto* m = p ? FindLocked(*p, key) : nullptr;
			if (m && m->status != "former") continue;  // active already, or fallen
			const auto info = Adventurers::Of(x);
			const float bond = BondLocked(key);
			e.push_back({ { "id", std::format("{:08X}", x->GetFormID()) }, { "name", x->GetDisplayFullName() }, { "letter", LetterStr(info.rank) },
				{ "level", x->GetLevel() }, { "rejoin", m != nullptr }, { "bond", std::round(bond) }, { "tier", TierOf(bond) } });
		}
		auto& ledger = j["ledger"] = nlohmann::json::array();
		for (auto it = g_parties.rbegin(); it != g_parties.rend(); ++it) {
			nlohmann::json roll = nlohmann::json::array();
			for (auto& m : it->members) roll.push_back(row(m, false));
			const float bond = MeanLocked(*it);
			ledger.push_back({ { "id", it->id }, { "name", it->name }, { "founded", it->founded }, { "disbanded", it->disbanded },
				{ "bond", std::round(bond) }, { "tier", TierOf(bond) }, { "roll", std::move(roll) } });
		}
		return j;
	}

	// Renown: how far the party's name has travelled. Deeds that people talk about: cleared dungeons and missives,
	// great beasts, and time on the road together. 0 unknown, 1 talked about in the holds, 2 famous across Skyrim.
	namespace
	{
		float RenownPoints(const Record& a_p)
		{
			const auto& s = a_p.stats;
			return s.dungeons * 3.0f + s.missives * 3.0f + s.bigKills * 5.0f + s.kills * 0.2f + s.hours / 24.0f;
		}
		int RenownLevel(float a_points) { return a_points >= g_cfg.renown[1] ? 2 : a_points >= g_cfg.renown[0] ? 1 : 0; }
	}

	std::string SkyrimNetJson(RE::Actor* a_actor)
	{
		const std::string key = a_actor && !a_actor->IsPlayerRef() ? Adventurers::StableKey(a_actor) : std::string();
		std::lock_guard l(g_lock);
		auto* p = ActiveLocked();
		nlohmann::json j;
		j["party"] = p != nullptr;
		// the actor's own tie to a party (current or past), for their bio
		j["member"] = false;
		if (!key.empty())
			for (auto it = g_parties.rbegin(); it != g_parties.rend(); ++it)
				if (auto* m = FindLocked(*it, key)) {
					j["member"] = m->status == "active" && it->disbanded < 0.0f;
					j["former"] = !j["member"].get<bool>();
					j["memberOf"] = it->name;
					j["bond"] = TierWord(TierOf(BondLocked(key)));
					break;
				}
		if (!p) return j.dump();
		const float pts = RenownPoints(*p);
		const int   level = RenownLevel(pts);
		std::vector<std::string> active, fallen;
		for (auto& m : p->members) {
			if (m.status == "active") active.push_back(m.name);
			if (m.status == "fallen") fallen.push_back(m.name + (m.where.empty() ? "" : " (at " + m.where + ")"));
		}
		// ready-made phrases for the prompts ("Jenassa, Lydia and Faendal")
		auto phrase = [](const std::vector<std::string>& v) {
			std::string s;
			const std::size_t shown = v.size() > 5 ? 4 : v.size();  // a long roster: four names, then how many more
			for (std::size_t i = 0; i < shown; ++i) s += (i == 0 ? "" : i + 1 == v.size() ? " and " : ", ") + v[i];
			if (shown < v.size()) s = Loc::F("$AG_Party_AndOthers", "{} and {} others", s, v.size() - shown);
			return s;
		};
		j["name"] = p->name;
		j["members"] = active;
		j["membersText"] = phrase(active);
		j["fallen"] = fallen;
		j["fallenText"] = phrase(fallen);
		j["bondTier"] = TierWord(TierOf(MeanLocked(*p)));
		j["days"] = static_cast<int>(p->stats.hours / 24.0f);
		j["dungeons"] = p->stats.dungeons;
		j["missives"] = p->stats.missives;
		j["greatBeasts"] = p->stats.bigKills;
		j["renown"] = level;  // 0 unknown, 1 talked about in the holds, 2 famous across Skyrim
		j["renownWord"] = level == 2 ? "famous across Skyrim" : level == 1 ? "talked about in the holds" : "not yet known";
		return j.dump();
	}

	std::string Dump()
	{
		std::lock_guard l(g_lock);
		std::string s = std::format("parties {}", g_parties.size());
		for (auto& p : g_parties) {
			s += std::format(" | #{} '{}' founded {:.1f} {} bond {:.0f}:", p.id, p.name, p.founded,
				p.disbanded < 0.0f ? "ACTIVE" : std::format("disbanded {:.1f}", p.disbanded), MeanLocked(p));
			for (auto& m : p.members) s += std::format(" {} ({}, bond {:.0f})", m.name, m.status, BondLocked(m.key));
		}
		return s;
	}

	nlohmann::json Save()
	{
		std::lock_guard l(g_lock);
		auto a = nlohmann::json::array();
		for (auto& p : g_parties) {
			auto ms = nlohmann::json::array();
			for (auto& m : p.members)
				ms.push_back({ { "key", m.key }, { "name", m.name }, { "status", m.status }, { "joined", m.joined }, { "left", m.left }, { "where", m.where },
					{ "kills", m.kills } });
			const auto& st = p.stats;
			a.push_back({ { "id", p.id }, { "name", p.name }, { "founded", p.founded }, { "disbanded", p.disbanded }, { "members", std::move(ms) },
				{ "stats", { { "hours", st.hours }, { "kills", st.kills }, { "bigKills", st.bigKills }, { "dungeons", st.dungeons }, { "missives", st.missives },
								{ "bestTier", st.bestTier }, { "tierDay", st.tierDay } } } });
		}
		auto facts = nlohmann::json::object();
		for (auto& [k, f] : g_facts) facts[k] = FactsJson(f);
		return { { "parties", std::move(a) }, { "bonds", g_bonds }, { "skills", g_skills }, { "traitsOn", g_traitOn },
			{ "traitsSeen", std::vector<std::string>(g_traitSeen.begin(), g_traitSeen.end()) },
			{ "traitsNew", std::vector<std::string>(g_traitNew.begin(), g_traitNew.end()) },
			{ "blessed", std::vector<std::string>(g_blessed.begin(), g_blessed.end()) }, { "facts", std::move(facts) } };
	}

	void Load(const nlohmann::json& a_j)
	{
		std::lock_guard l(g_lock);
		g_parties.clear();
		g_bonds.clear();
		g_skills.clear();
		g_killBond.clear();
		g_lastHours = -1.0f;
		g_traitOn.clear();
		g_traitSeen.clear();
		g_traitNew.clear();
		g_unlocked.clear();
		g_active.clear();
		g_facts.clear();
		g_haveLast = false;
		g_lastSaid.clear();
		g_unmetSince.clear();
		g_blessed.clear();
		if (a_j.is_object()) {
			g_traitOn = a_j.value("traitsOn", std::vector<std::string>{});
			for (auto& s : a_j.value("traitsSeen", std::vector<std::string>{})) g_traitSeen.insert(s);
			for (auto& s : a_j.value("traitsNew", std::vector<std::string>{})) g_traitNew.insert(s);
			for (auto& s : a_j.value("blessed", std::vector<std::string>{})) g_blessed.insert(Adventurers::CanonicalKey(s));
			if (a_j.contains("facts") && a_j.at("facts").is_object())
				for (auto& [k, v] : a_j.at("facts").items()) g_facts[Adventurers::CanonicalKey(k)] = FactsFrom(v);
		}
		if (a_j.is_object() && a_j.contains("skills") && a_j.at("skills").is_object())
			for (auto& [k, v] : a_j.at("skills").items())
				if (v.is_array() && v.size() == kSkills.size()) g_skills[Adventurers::CanonicalKey(k)] = v.get<Skills>();
		// {"parties":[...],"bonds":{key:bond}}; the first build saved a bare array with a bond per member
		const nlohmann::json list = a_j.is_array() ? a_j : a_j.value("parties", nlohmann::json::array());
		if (a_j.is_object() && a_j.contains("bonds") && a_j.at("bonds").is_object())
			for (auto& [k, v] : a_j.at("bonds").items()) {
				auto& b = g_bonds[Adventurers::CanonicalKey(k)];  // keys from before 1.1.0 are corrected; two keys for one actor keep the higher Bond
				b = std::max(b, v.get<float>());
			}
		if (!list.is_array()) return;
		for (auto& jp : list) {
			Record p;
			p.id = jp.value("id", 0);
			p.name = jp.value("name", std::string());
			p.founded = jp.value("founded", -1.0f);
			p.disbanded = jp.value("disbanded", -1.0f);
			for (auto& jm : jp.value("members", nlohmann::json::array()))
			{
				p.members.push_back({ Adventurers::CanonicalKey(jm.value("key", std::string())), jm.value("name", std::string()), jm.value("status", std::string("former")),
					jm.value("joined", -1.0f), jm.value("left", -1.0f), jm.value("where", std::string()), jm.value("kills", 0) });
				if (jm.contains("bond")) g_bonds[p.members.back().key] = std::max(BondLocked(p.members.back().key), jm.value("bond", 0.0f));
			}
			if (jp.contains("stats")) {
				const auto& st = jp.at("stats");
				p.stats = { st.value("hours", 0.0f), st.value("kills", 0), st.value("bigKills", 0), st.value("dungeons", 0), st.value("missives", 0),
					st.value("bestTier", 0), st.value("tierDay", -1.0f) };
			}
			g_parties.push_back(std::move(p));
		}
		// at most one active party: any extra (should not happen) is closed on its founding day
		bool seen = false;
		for (auto it = g_parties.rbegin(); it != g_parties.rend(); ++it)
			if (it->disbanded < 0.0f && std::exchange(seen, true)) it->disbanded = it->founded;
		SKSE::log::info("Party: loaded {} parties", g_parties.size());
	}

	void Revert()
	{
		std::lock_guard l(g_lock);
		g_parties.clear();
		g_bonds.clear();
		g_skills.clear();
		g_killBond.clear();
		g_lastHours = -1.0f;
		g_traitOn.clear();
		g_traitSeen.clear();
		g_traitNew.clear();
		g_unlocked.clear();
		g_active.clear();
		g_facts.clear();
		g_haveLast = false;
		g_lastSaid.clear();
		g_unmetSince.clear();
		g_blessed.clear();
	}

	void Refresh() { Evaluate(); }

	void AtCounter()
	{
		Evaluate(true);
		std::vector<std::string> dropped;
		{
			std::lock_guard l(g_lock);
			if (!g_rosterKnown) return;  // a member we have never been able to read: leave the player's choices alone
			// Beast Buds supersedes Creatures of the Night: a party that grew into it keeps the slot
			if (g_unlocked.contains("beast") && std::ranges::find(g_traitOn, std::string("beast")) == g_traitOn.end())
				if (auto it = std::ranges::find(g_traitOn, std::string("night")); it != g_traitOn.end()) *it = "beast";
			std::erase_if(g_traitOn, [&](auto& id) {
				if (g_unlocked.contains(id)) return false;
				dropped.push_back(id);
				return true;
			});
		}
		if (dropped.empty()) return;
		for (auto& id : dropped) SKSE::log::info("Party: affinity '{}' no longer fits the party - unselected at the counter", id);
		Evaluate(true);
	}

	int StripForUninstall()
	{
		std::vector<std::string> keys;
		{
			std::lock_guard l(g_lock);
			for (auto& p : g_parties)
				for (auto& m : p.members) keys.push_back(m.key);
			keys.insert(keys.end(), g_blessed.begin(), g_blessed.end());
			g_blessed.clear();
		}
		std::ranges::sort(keys);
		keys.erase(std::unique(keys.begin(), keys.end()), keys.end());
		SetGlobal(g_gTier, -1.0f);
		SetGlobal(g_gPresent, 0.0f);
		for (auto& [id, g] : g_gTrait) SetGlobal(g, 0.0f);
		int n = 0;
		if (!g_blessing) return 0;
		if (auto* pc = RE::PlayerCharacter::GetSingleton(); pc && pc->HasSpell(g_blessing)) pc->RemoveSpell(g_blessing);
		for (auto& k : keys)
			if (auto* a = Resolve(k); a && a->HasSpell(g_blessing)) { a->RemoveSpell(g_blessing); ++n; }
		return n;
	}
}
