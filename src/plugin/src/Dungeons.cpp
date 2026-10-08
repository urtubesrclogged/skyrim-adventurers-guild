// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "Dungeons.h"

#include "Adventurers.h"
#include "Counter.h"
#include "Guild.h"
#include "Party.h"
#include "Loc.h"
#include "PrismaToast.h"
#include "RankCore.h"

#include <mutex>
#include <unordered_map>
#include <unordered_set>

namespace AG::Dungeons
{
	namespace
	{
		std::mutex                           g_lock;
		std::unordered_map<std::string, int> g_visited;   // StableKey(location) -> threat rank at first entry
		std::unordered_set<std::string>      g_reported;  // cleared locations already paid / announced
		RE::BGSLocation*                     g_current{ nullptr };  // not saved: just suppresses repeat notices

		// guild.json "notDungeons": places the game marks clearable that are no dungeon (Stendarr's Beacon and the Hall
		// of the Vigilant are held by the Vigilants). Keys are kept as written and looked up once the forms exist.
		std::vector<std::string>       g_notDungeonKeys;
		std::unordered_set<RE::FormID> g_notDungeons;
		bool                           g_notDungeonsResolved{ false };

		bool Excluded(const RE::BGSLocation* a_loc)
		{
			if (!g_notDungeonsResolved) {
				if (!RE::TESDataHandler::GetSingleton()) return false;
				g_notDungeons.clear();
				for (auto& k : g_notDungeonKeys)
					if (auto* f = Adventurers::FormOfKey(k)) g_notDungeons.insert(f->GetFormID());
				g_notDungeonsResolved = true;
				SKSE::log::info("Dungeons: {} of {} places listed as not dungeons were found", g_notDungeons.size(), g_notDungeonKeys.size());
			}
			return g_notDungeons.contains(a_loc->GetFormID());
		}

		bool Clearable(const RE::BGSLocation* a_loc)
		{
			// Civil War camps (LocTypeMilitaryCamp) carry LocTypeDungeon but are faction headquarters, not places to
			// clear: no dungeon notice on entry, no intel for sale.
			if (!a_loc || a_loc->HasKeywordString("LocTypeMilitaryCamp")) return false;
			if (Excluded(a_loc)) return false;
			return a_loc->HasKeywordString("LocTypeClearable") || a_loc->HasKeywordString("LocTypeDungeon");
		}

		// The dungeon the player is in: the nearest clearable location walking up from the current one
		// (e.g. Bleak Falls Sanctum -> Bleak Falls Barrow). Settlements stop the walk.
		RE::BGSLocation* DungeonOf(RE::BGSLocation* a_loc)
		{
			for (auto* l = a_loc; l; l = l->parentLoc) {
				if (l->HasKeywordString("LocTypeCity") || l->HasKeywordString("LocTypeTown") || l->HasKeywordString("LocTypeHabitation")) return nullptr;
				if (Clearable(l)) return l;
			}
			return nullptr;
		}

		std::string Name(const RE::BGSLocation* a_loc)
		{
			const char* n = a_loc ? a_loc->GetFullName() : nullptr;
			return n && *n ? n : "an unnamed ruin";
		}

		RE::BGSEncounterZone* ZoneHere()
		{
			auto* pc = RE::PlayerCharacter::GetSingleton();
			auto* cell = pc ? pc->GetParentCell() : nullptr;
			if (!cell) return nullptr;
			if (auto* ld = cell->GetRuntimeData().loadedData; ld && ld->encounterZone) return ld->encounterZone;
			return cell->extraList.GetEncounterZone();
		}

		// Level a zone runs at: its locked level once set, else the player's level clamped to the zone's range
		// (with Match PC Below Min honoured); no zone -> the player's level.
		int LevelFor(const RE::BGSEncounterZone* z)
		{
			auto* pc = RE::PlayerCharacter::GetSingleton();
			const int pl = pc ? pc->GetLevel() : 1;
			if (!z) return pl;
			if (z->gameData.zoneLevel > 0) return z->gameData.zoneLevel;
			int lvl = pl;
			const int lo = z->data.minLevel, hi = z->data.maxLevel;
			const bool matchBelow = z->data.flags.any(RE::ENCOUNTER_ZONE_DATA::Flag::kMatchPCBelowMinimumLevel);
			if (lo > 0 && lvl < lo && !matchBelow) lvl = lo;
			if (hi > 0 && lvl > hi) lvl = hi;
			return lvl;
		}

		int LevelHere() { return LevelFor(ZoneHere()); }

		// ---- intel: every dungeon's encounter zone (from its interior cells) and its map marker
		std::unordered_map<const RE::BGSLocation*, RE::BGSEncounterZone*> g_zoneOf;
		// Markers that start switched off in the game's records (the Katariah, the Wreck of the Icerunner, a civil war
		// camp): a quest puts them on the map, the Guild does not. Noted at kDataLoaded, before a save can change them.
		std::unordered_set<RE::FormID> g_questMarkers;
		bool g_zonesBuilt{ false };

		void BuildZones()
		{
			if (g_zonesBuilt) return;
			g_zonesBuilt = true;
			auto* dh = RE::TESDataHandler::GetSingleton();
			if (!dh) return;
			for (auto* cell : dh->interiorCells) {
				if (!cell) continue;
				auto* z = cell->extraList.GetEncounterZone();
				auto* d = z ? DungeonOf(cell->GetLocation()) : nullptr;
				if (d && !g_zoneOf.contains(d)) g_zoneOf[d] = z;
			}
			SKSE::log::info("Dungeons: {} dungeon encounter zones indexed for intel", g_zoneOf.size());
		}

		// The region a counter's intel covers: the hold, or all of Solstheim for the counter in Raven Rock (the island is
		// not a hold; its dungeons sit under DLC2SolstheimLocation).
		RE::BGSLocation* HoldOf(RE::BGSLocation* a_loc)
		{
			static RE::BGSLocation* solstheim = [] {
				auto* dh = RE::TESDataHandler::GetSingleton();
				return dh ? dh->LookupForm<RE::BGSLocation>(0x016E2A, "Dragonborn.esm") : nullptr;
			}();
			for (auto* l = a_loc; l; l = l->parentLoc) {
				if (l->HasKeywordString("LocTypeHold") || (solstheim && l == solstheim)) return l;
			}
			return nullptr;
		}

		bool Under(const RE::BGSLocation* a_loc, const RE::BGSLocation* a_area)
		{
			for (auto* l = a_loc; l; l = l->parentLoc) {
				if (l == a_area) return true;
			}
			return false;
		}

		// The location's map marker (special ref of type Skyrim.esm MapMarkerRefType 0x10F63C).
		RE::TESObjectREFR* MarkerOf(const RE::BGSLocation* a_loc)
		{
			static const auto* kMapMarkerType = RE::TESForm::LookupByID(0x0010F63C);
			for (auto& sr : a_loc->specialRefs) {
				if (sr.type && sr.type == kMapMarkerType) return RE::TESForm::LookupByID<RE::TESObjectREFR>(sr.refData.refID);
			}
			return nullptr;
		}

		RE::MapMarkerData* MapData(RE::TESObjectREFR* a_marker)
		{
			auto* x = a_marker ? a_marker->extraList.GetByType<RE::ExtraMapMarker>() : nullptr;
			return x ? x->mapData : nullptr;
		}

		// What the scouts say a place is, from its location keywords: architecture (LocSet*) plus who holds it
		// (LocType*), e.g. "Cave · vampires", "Nordic ruin · draugr"; outdoor places keep their natural name
		// ("Bandit camp"). Hamvir's Rest has only LocSetNordicRuin -> "Nordic ruin".
		std::string Kind(const RE::BGSLocation* a_loc)
		{
			static const std::pair<const char*, const char*> arches[] = {
				{ "LocSetCaveIce", "Ice cave" }, { "LocSetCave", "Cave" }, { "LocSetNordicRuin", "Nordic ruin" },
				{ "LocSetDwarvenRuin", "Dwemer ruin" }, { "LocSetMilitaryFort", "Fort" },
			};
			// occupant: plural for "<architecture> · <who>", and the name used for an outdoor place
			static const std::tuple<const char*, const char*, const char*> who[] = {
				{ "LocTypeDragonPriestLair", "a dragon priest", "Dragon priest lair" }, { "LocTypeDragonLair", "a dragon", "Dragon lair" },
				{ "LocTypeDraugrCrypt", "draugr", "Draugr crypt" }, { "LocTypeFalmerHive", "Falmer", "Falmer hive" },
				{ "LocTypeDwarvenAutomatons", "automatons", "Dwemer ruin" }, { "LocTypeVampireLair", "vampires", "Vampire lair" },
				{ "LocTypeWerewolfLair", "werewolves", "Werewolf lair" }, { "LocTypeWerebearLair", "werebears", "Werebear lair" },
				{ "LocTypeWarlockLair", "warlocks", "Warlock lair" }, { "LocTypeHagravenNest", "hagravens", "Hagraven nest" },
				{ "LocTypeForswornCamp", "Forsworn", "Forsworn camp" }, { "LocTypeBanditCamp", "bandits", "Bandit camp" },
				{ "LocTypeGiantCamp", "giants", "Giant camp" }, { "LocTypeSprigganGrove", "spriggans", "Spriggan grove" },
				{ "LocTypeAnimalDen", "beasts", "Beast den" },
			};
			static const std::pair<const char*, const char*> places[] = {
				{ "LocTypeShipwreck", "Shipwreck" }, { "LocTypeMine", "Mine" }, { "LocTypeCastle", "Castle" }, { "LocTypeMilitaryFort", "Fort" },
			};
			// labels translate by keyword: $AG_Kind_<keyword> (a place or architecture), $AG_Who_<keyword> (occupants)
			auto kind = [](std::string_view kw, const char* en) { return Loc::T(std::format("$AG_Kind_{}", kw), en); };
			const char* archKw = nullptr;
			const char* arch = nullptr;
			for (auto& [kw, label] : arches) {
				if (a_loc->HasKeywordString(kw)) { archKw = kw; arch = label; break; }
			}
			for (auto& [kw, plural, name] : who) {
				if (!a_loc->HasKeywordString(kw)) continue;
				if (arch && std::string_view(arch) != name)
					return Loc::F("$AG_Kind_ArchWho", "{} · {}", kind(archKw, arch), Loc::T(std::format("$AG_Who_{}", kw), plural));
				return kind(kw, name);
			}
			if (arch) return kind(archKw, arch);
			for (auto& [kw, label] : places) {
				if (a_loc->HasKeywordString(kw)) return kind(kw, label);
			}
			return Loc::T("$AG_Kind_Unknown", "Occupants unknown");   // nothing in the game data says what holds it
		}

		// Rough direction and distance from the settlement the player is standing in (its map marker), e.g.
		// "half a day's walk northeast". Empty when there is no common worldspace to measure in.
		std::string Bearing(RE::TESObjectREFR* a_marker)
		{
			auto* pc = RE::PlayerCharacter::GetSingleton();
			auto* here = pc ? pc->GetCurrentLocation() : nullptr;
			RE::TESObjectREFR* from = nullptr;
			for (auto* l = here; l && !from; l = l->parentLoc) {
				if (auto* m = MarkerOf(l)) from = m;
			}
			// City worldspaces (WhiterunWorld, ...) sit on Tamriel's coordinates, so compare root worldspaces.
			auto root = [](RE::TESWorldSpace* w) {
				while (w && w->parentWorld) w = w->parentWorld;
				return w;
			};
			if (!from || !a_marker || !a_marker->GetWorldspace() || root(from->GetWorldspace()) != root(a_marker->GetWorldspace())) return {};
			const auto d = a_marker->GetPosition() - from->GetPosition();
			const float dist = std::sqrt(d.x * d.x + d.y * d.y);
			static const char* dirs[] = { "east", "northeast", "north", "northwest", "west", "southwest", "south", "southeast" };
			static const char* dirKeys[] = { "$AG_Dir_E", "$AG_Dir_NE", "$AG_Dir_N", "$AG_Dir_NW", "$AG_Dir_W", "$AG_Dir_SW", "$AG_Dir_S", "$AG_Dir_SE" };
			const float deg = std::atan2(d.y, d.x) * 57.29578f;   // +x east, +y north
			const int   di = static_cast<int>(std::lround((deg < 0 ? deg + 360.0f : deg) / 45.0f)) % 8;
			const auto  dir = Loc::T(dirKeys[di], dirs[di]);
			const auto  how = dist < 15000.0f ? Loc::T("$AG_Dist_Near", "close by to the") : dist < 40000.0f ? Loc::T("$AG_Dist_Hours", "a few hours' walk")
			                  : dist < 80000.0f ? Loc::T("$AG_Dist_HalfDay", "half a day's walk") : Loc::T("$AG_Dist_Day", "a long day's walk");
			return Loc::F("$AG_Bearing", "{0} {1}", how, dir);   // {0} = distance, {1} = direction
		}

		struct IntelLead
		{
			RE::BGSLocation*   loc;
			RE::TESObjectREFR* marker;
			int                rank;
		};

		std::vector<IntelLead> Leads()
		{
			std::vector<IntelLead> out;
			auto* pc = RE::PlayerCharacter::GetSingleton();
			auto* hold = HoldOf(pc ? pc->GetCurrentLocation() : nullptr);
			auto* dh = RE::TESDataHandler::GetSingleton();
			if (!hold || !dh) return out;
			BuildZones();
			for (auto* l : dh->GetFormArray<RE::BGSLocation>()) {
				if (!l || DungeonOf(l) != l || l->IsCleared() || !Under(l, hold)) continue;
				auto* m = MarkerOf(l);
				auto* md = MapData(m);
				if (!md || md->flags.any(RE::MapMarkerData::Flag::kVisible)) continue;   // already on the map
				if (m->IsDisabled()) continue;   // switched off (a quest has yet to put it there): the map cannot show it
				auto z = g_zoneOf.find(l);
				out.push_back({ l, m, FromLevel(LevelFor(z != g_zoneOf.end() ? z->second : nullptr)) });
			}
			std::sort(out.begin(), out.end(), [](auto& a, auto& b) { return a.rank != b.rank ? a.rank < b.rank : Name(a.loc) < Name(b.loc); });
			return out;
		}

		void Toast(std::string_view a_title, std::string_view a_sub, int a_rank, PrismaToast::Priority a_p = PrismaToast::Priority::kImportant)
		{
			PrismaToast::Show(a_title, a_sub, a_rank >= 0 ? std::format("tex/rank_{}.png", Letter(a_rank)) : std::string{}, a_p);
		}

		void OnEntered(RE::BGSLocation* a_dungeon)
		{
			// Reading a dungeon's threat rank is Appraisal (the Guild skill bought at the counter), as it is for the ranks
			// on names and health bars: a player who has not registered, or a member without Appraisal I, is told nothing.
			// The dungeon is not marked as visited either, so its first-visit notice comes on the first visit with it.
			if (!Guild::Registered() || Guild::AppraisalLevel() < 1) return;
			const auto key = Adventurers::StableKey(a_dungeon);
			int  rank;
			bool first = false;
			{
				std::lock_guard l(g_lock);
				auto it = g_visited.find(key);
				if (it == g_visited.end()) {
					rank = FromLevel(LevelHere());
					g_visited[key] = rank;
					first = true;
				} else {
					rank = it->second;
				}
			}
			const auto name = Name(a_dungeon);
			const bool cleared = a_dungeon->IsCleared();
			const int  guild = Guild::Rank();
			if (first) {
				std::string sub = Loc::F("$AG_Toast_DungeonSub", "{} · Threat Rank {}", name, Letter(rank));
				if (guild >= 0 && rank > guild) sub += Loc::T("$AG_Toast_BeyondRank", " · beyond your guild rank");
				Toast(cleared ? Loc::T("$AG_Toast_DungeonCleared2", "DUNGEON (CLEARED)") : Loc::T("$AG_Toast_Dungeon", "DUNGEON"), sub, rank);
			} else {
				RE::SendHUDMessage::ShowHUDMessage((cleared ? Loc::F("$AG_Hud_DungeonCleared", "{} - Threat Rank {} (cleared)", name, Letter(rank))
				                                             : Loc::F("$AG_Hud_Dungeon", "{} - Threat Rank {}", name, Letter(rank))).c_str());
			}
			SKSE::log::info("Dungeons: entered {} [{}] rank {} (level {}){}", name, key, Letter(rank), LevelHere(), first ? " - first visit" : "");
		}

		void OnCleared(RE::BGSLocation* a_dungeon)
		{
			if (!a_dungeon) return;
			const auto key = Adventurers::StableKey(a_dungeon);
			int rank;
			{
				std::lock_guard l(g_lock);
				if (!g_reported.insert(key).second) return;  // paid once per save
				auto it = g_visited.find(key);
				rank = it != g_visited.end() ? it->second : FromLevel(LevelHere());
				g_visited[key] = rank;
			}
			const auto name = Name(a_dungeon);
			if (Guild::Registered()) {
				const int gold = Guild::DungeonGold(rank), merit = Guild::DungeonMerit(rank), rep = Guild::DungeonRep(rank);
				Guild::AddReport("dungeon", Loc::F("$AG_Report_Cleared", "Cleared {}", name), Loc::F("$AG_Report_DungeonDetail", "Threat Rank {} dungeon", Letter(rank)), gold, merit, rep);
				// a member is always told to report it; the rank (and its badge) only with Appraisal
				if (Guild::AppraisalLevel() >= 1)
					Toast(Loc::T("$AG_Toast_Cleared", "DUNGEON CLEARED"), Loc::F("$AG_Toast_ClearedReport", "{} · Rank {} · report to the Guild for your reward", name, Letter(rank)), rank);
				else
					Toast(Loc::T("$AG_Toast_Cleared", "DUNGEON CLEARED"), Loc::F("$AG_Toast_ClearedReportPlain", "{} · report to the Guild for your reward", name), -1);
				Guild::Notify("AG_DungeonCleared", name, static_cast<float>(rank));
				Party::OnDungeonCleared(rank);
				if (Counter::IsOpen()) Counter::Refresh();
			}
			// not registered: no notice (1.1.0; it used to show the rank and that the Guild pays for clears)
			SKSE::log::info("Dungeons: cleared {} [{}] rank {}", name, key, Letter(rank));
		}

		// The location the "Dungeons Cleared" stat is about: the dungeon the player stands in (walking up to the
		// first one flagged cleared, since a boss chamber may be a child location), else the last one entered.
		RE::BGSLocation* ClearedHere()
		{
			auto* pc = RE::PlayerCharacter::GetSingleton();
			for (auto* l = pc ? pc->GetCurrentLocation() : nullptr; l; l = l->parentLoc) {
				if (Clearable(l) && l->IsCleared()) return l;
			}
			if (auto* d = DungeonOf(pc ? pc->GetCurrentLocation() : nullptr)) return d;
			return g_current;
		}

		class Sink :
			public RE::BSTEventSink<RE::BGSActorCellEvent>,
			public RE::BSTEventSink<RE::TESTrackedStatsEvent>
		{
		public:
			static Sink* Get()
			{
				static Sink s;
				return &s;
			}

			RE::BSEventNotifyControl ProcessEvent(const RE::BGSActorCellEvent* a_e, RE::BSTEventSource<RE::BGSActorCellEvent>*) override
			{
				if (a_e && a_e->flags.all(RE::BGSActorCellEvent::CellFlag::kEnter)) {
					SKSE::GetTaskInterface()->AddTask([] {
						Guild::SyncGlobals();  // time-based globals (recent-promotion gossip) catch up on every cell change
						auto* pc = RE::PlayerCharacter::GetSingleton();
						auto* d = DungeonOf(pc ? pc->GetCurrentLocation() : nullptr);
						if (d == g_current) return;
						g_current = d;
						if (d) OnEntered(d);
					});
				}
				return RE::BSEventNotifyControl::kContinue;
			}

			RE::BSEventNotifyControl ProcessEvent(const RE::TESTrackedStatsEvent* a_e, RE::BSTEventSource<RE::TESTrackedStatsEvent>*) override
			{
				if (a_e && a_e->stat == "Dungeons Cleared") {
					SKSE::GetTaskInterface()->AddTask([] { OnCleared(ClearedHere()); });
				}
				return RE::BSEventNotifyControl::kContinue;
			}
		};
	}

	void Install()
	{
		if (auto* pc = RE::PlayerCharacter::GetSingleton()) pc->AsBGSActorCellEventSource()->AddEventSink(Sink::Get());
		RE::ScriptEventSourceHolder::GetSingleton()->AddEventSink<RE::TESTrackedStatsEvent>(Sink::Get());
		SKSE::log::info("Dungeons: watching location changes and Dungeons Cleared");
		// which map markers start switched off, read now: after a save loads, a marker only says whether it is off today
		const auto t0 = std::chrono::steady_clock::now();
		g_questMarkers.clear();
		int markers = 0;
		{
			const auto& [map, lock] = RE::TESForm::GetAllForms();
			RE::BSReadLockGuard l{ lock };
			if (map)
				for (auto& [id, form] : *map) {
					auto* ref = form ? form->As<RE::TESObjectREFR>() : nullptr;
					if (!ref || !ref->extraList.HasType(RE::ExtraDataType::kMapMarker)) continue;
					++markers;
					if (ref->IsDisabled()) g_questMarkers.insert(id);
				}
		}
		const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
		SKSE::log::info("Dungeons: {} of {} map markers start switched off (a quest puts them on the map, never sold as intel), read in {} ms",
			static_cast<int>(g_questMarkers.size()), markers, static_cast<int>(ms));
	}

	int ClearedCount()
	{
		std::lock_guard l(g_lock);
		return static_cast<int>(g_reported.size());
	}

	void SetNotDungeons(std::vector<std::string> a_keys)
	{
		g_notDungeonKeys = std::move(a_keys);
		g_notDungeonsResolved = false;
	}

	nlohmann::json Save()
	{
		std::lock_guard l(g_lock);
		return { { "visited", g_visited }, { "reported", std::vector<std::string>(g_reported.begin(), g_reported.end()) } };
	}

	void Load(const nlohmann::json& a_j)
	{
		std::lock_guard l(g_lock);
		g_visited.clear();
		g_reported.clear();
		g_current = nullptr;
		try {
			// keys from before 1.1.0 are corrected (Adventurers::StableKey), so a dungeon keeps its record
			if (a_j.contains("visited"))
				for (auto& [k, v] : a_j.at("visited").get<std::unordered_map<std::string, int>>()) g_visited[Adventurers::CanonicalKey(k)] = v;
			for (auto& k : a_j.value("reported", nlohmann::json::array())) g_reported.insert(Adventurers::CanonicalKey(k.get<std::string>()));
		} catch (const std::exception& e) {
			SKSE::log::error("Dungeons: co-save parse error: {}", e.what());
		}
	}

	void Revert()
	{
		std::lock_guard l(g_lock);
		g_visited.clear();
		g_reported.clear();
		g_current = nullptr;
	}

	nlohmann::json IntelServices(int a_merit, bool a_registered)
	{
		auto rows = nlohmann::json::array();
		const int guild = Guild::Rank();   // like missives: only work at or below the player's rank (none before registering)
		for (auto& lead : Leads()) {
			if (lead.rank > guild) continue;
			const int cost = Guild::IntelMerit(lead.rank);
			std::string note = !a_registered ? Loc::T("$AG_Note_RegisterFirst", "Register first") : (a_merit < cost ? Loc::T("$AG_Note_NoMerit", "Not enough Merit") : "");
			const auto where = Bearing(lead.marker);
			rows.push_back({ { "section", Loc::T("$AG_Sec_Intel", "Intel") }, { "sectionId", "Intel" }, { "id", std::format("intel:{:08X}", lead.loc->GetFormID()) },
				{ "group", "dungeon" }, { "name", Name(lead.loc) }, { "tier", std::string(1, Letter(lead.rank)) },
				{ "desc", where.empty() ? Kind(lead.loc) : Loc::F("$AG_Intel_Desc", "{} · {}", Kind(lead.loc), where) },
				{ "cost", cost }, { "available", note.empty() }, { "note", note } });
		}
		return rows;
	}

	// ---------------------------------------------------------------- points of interest
	namespace
	{
		struct PoiCategory
		{
			std::string                   id, name;
			int                           merit{ 5 };
			std::unordered_set<int>       types;   // map marker icons (RE::MARKER_TYPE)
			std::vector<std::string>      placeKeys;
			std::unordered_set<RE::FormID> places;  // marker references named outright
		};
		struct Poi
		{
			RE::TESObjectREFR* marker{ nullptr };
			int                category{ -1 };
			RE::BGSLocation*   hold{ nullptr };
		};
		bool                           g_poiEnabled{ true };
		std::vector<PoiCategory>       g_poiCats;
		std::vector<std::string>       g_poiNeverKeys;
		std::vector<Poi>               g_pois;
		bool                           g_poisBuilt{ false };

		int MarkerType(std::string_view a_name)
		{
			static const std::unordered_map<std::string_view, int> m{
				{ "Camp", 5 }, { "Shipwreck", 9 }, { "Grove", 10 }, { "Landmark", 11 }, { "Farm", 13 }, { "WoodMill", 14 }, { "Mine", 15 },
				{ "Doomstone", 18 }, { "WheatMill", 19 }, { "Smelter", 20 }, { "Stable", 21 }, { "ImperialTower", 22 }, { "Clearing", 23 },
				{ "Pass", 24 }, { "Altar", 25 }, { "Rock", 26 }, { "Lighthouse", 27 }, { "OrcStronghold", 28 }, { "GiantCamp", 29 },
				{ "Shack", 30 }, { "NordicTower", 31 }, { "NordicDwelling", 32 }, { "Docks", 33 }, { "Shrine", 34 }, { "Settlement", 3 },
			};
			auto it = m.find(a_name);
			return it == m.end() ? -1 : it->second;
		}

		// Every map marker in the game (other mods' too), sorted into the categories once per session. A marker whose
		// location is a dungeon is the Dungeons tab's business. A marker with no location takes the hold of the
		// nearest marker that has one.
		void BuildPois()
		{
			if (g_poisBuilt) return;
			g_poisBuilt = true;
			g_pois.clear();
			auto* dh = RE::TESDataHandler::GetSingleton();
			if (!dh || !g_poiEnabled || g_poiCats.empty()) return;
			for (auto& c : g_poiCats) {
				c.places.clear();
				for (auto& k : c.placeKeys)
					if (auto* f = Adventurers::FormOfKey(k)) c.places.insert(f->GetFormID());
			}
			std::unordered_set<RE::FormID> never;
			for (auto& k : g_poiNeverKeys)
				if (auto* f = Adventurers::FormOfKey(k)) never.insert(f->GetFormID());
			std::unordered_map<RE::FormID, RE::BGSLocation*> locOf;   // marker reference -> its location
			for (auto* l : dh->GetFormArray<RE::BGSLocation>())
				if (l)
					if (auto* m = MarkerOf(l)) locOf.emplace(m->GetFormID(), l);

			std::vector<RE::TESObjectREFR*> markers;
			{
				const auto& [map, lock] = RE::TESForm::GetAllForms();
				RE::BSReadLockGuard l{ lock };
				if (map)
					for (auto& [id, form] : *map) {
						auto* ref = form ? form->As<RE::TESObjectREFR>() : nullptr;
						if (ref && ref->extraList.HasType(RE::ExtraDataType::kMapMarker)) markers.push_back(ref);
					}
			}
			auto root = [](RE::TESWorldSpace* w) {
				while (w && w->parentWorld) w = w->parentWorld;
				return w;
			};
			struct Anchor { RE::TESWorldSpace* world; RE::NiPoint3 pos; RE::BGSLocation* hold; };
			std::vector<Anchor> anchors;
			for (auto* m : markers) {
				auto it = locOf.find(m->GetFormID());
				if (auto* h = it != locOf.end() ? HoldOf(it->second) : nullptr) anchors.push_back({ root(m->GetWorldspace()), m->GetPosition(), h });
			}
			int quest = 0;
			for (auto* m : markers) {
				auto* md = MapData(m);
				if (!md || never.contains(m->GetFormID())) continue;
				const char* nm = md->locationName.GetFullName();
				if (!nm || !*nm) continue;
				auto  lit = locOf.find(m->GetFormID());
				auto* loc = lit != locOf.end() ? lit->second : nullptr;
				int   cat = -1;
				for (int i = 0; i < static_cast<int>(g_poiCats.size()) && cat < 0; ++i)
					if (g_poiCats[i].places.contains(m->GetFormID())) cat = i;
				const bool named = cat >= 0;
				const int  type = static_cast<int>(md->type.underlying());
				for (int i = 0; i < static_cast<int>(g_poiCats.size()) && cat < 0; ++i)
					if (g_poiCats[i].types.contains(type)) cat = i;
				if (cat < 0) continue;
				if (!named && loc && DungeonOf(loc)) continue;   // a dungeon (or inside a town): not ours
				// a place a quest unlocks: it starts switched off, or something else switches it on (an enable parent:
				// every airship mooring of Legacy of the Dragonborn). Never sold, even once the quest has run.
				if (!named && (g_questMarkers.contains(m->GetFormID()) || m->extraList.HasType(RE::ExtraDataType::kEnableStateParent))) {
					++quest;
					continue;
				}
				RE::BGSLocation* hold = loc ? HoldOf(loc) : nullptr;
				if (!hold) {
					float best = 0.0f;
					for (auto& a : anchors) {
						if (a.world != root(m->GetWorldspace())) continue;
						const auto  d = a.pos - m->GetPosition();
						const float dd = d.x * d.x + d.y * d.y;
						if (!hold || dd < best) { hold = a.hold; best = dd; }
					}
				}
				if (hold) g_pois.push_back({ m, cat, hold });
			}
			SKSE::log::info("Dungeons: {} points of interest in {} categories (of {} map markers; {} more are unlocked by quests and left out)",
				g_pois.size(), g_poiCats.size(), markers.size(), quest);
		}

		std::string PoiName(RE::TESObjectREFR* a_marker)
		{
			auto*       md = MapData(a_marker);
			const char* n = md ? md->locationName.GetFullName() : nullptr;
			return n && *n ? n : "";
		}
		std::string CategoryName(const PoiCategory& a_c) { return Loc::T("$AG_Poi_" + a_c.id, a_c.name); }
	}

	void SetPointsOfInterest(const nlohmann::json& a_cfg)
	{
		g_poiEnabled = a_cfg.value("enabled", true);
		g_poiCats.clear();
		g_poiNeverKeys = a_cfg.value("never", std::vector<std::string>{});
		for (auto& c : a_cfg.value("categories", nlohmann::json::array())) {
			PoiCategory pc;
			pc.id = c.value("id", "");
			pc.name = c.value("name", pc.id);
			pc.merit = std::max(0, c.value("merit", 5));
			for (auto& t : c.value("markers", nlohmann::json::array()))
				if (const int v = t.is_number_integer() ? t.get<int>() : MarkerType(t.get<std::string>()); v >= 0) pc.types.insert(v);
				else SKSE::log::warn("Dungeons: pointsOfInterest '{}': unknown map marker type {}", pc.id, t.dump());
			pc.placeKeys = c.value("places", std::vector<std::string>{});
			if (!pc.id.empty()) g_poiCats.push_back(std::move(pc));
		}
		g_poisBuilt = false;
	}

	nlohmann::json PoiServices(int a_merit, bool a_registered)
	{
		auto rows = nlohmann::json::array();
		auto* pc = RE::PlayerCharacter::GetSingleton();
		auto* hold = HoldOf(pc ? pc->GetCurrentLocation() : nullptr);
		if (!hold) return rows;
		BuildPois();
		std::vector<const Poi*> here;
		for (auto& p : g_pois) {
			auto* md = MapData(p.marker);
			if (p.hold != hold || !md || md->flags.any(RE::MapMarkerData::Flag::kVisible)) continue;   // elsewhere, or already on the map
			if (p.marker->IsDisabled()) continue;   // switched off: the map cannot show it
			here.push_back(&p);
		}
		std::sort(here.begin(), here.end(), [](auto* a, auto* b) { return a->category != b->category ? a->category < b->category : PoiName(a->marker) < PoiName(b->marker); });
		for (auto* p : here) {
			auto&      cat = g_poiCats[p->category];
			const auto note = !a_registered ? Loc::T("$AG_Note_RegisterFirst", "Register first") : (a_merit < cat.merit ? Loc::T("$AG_Note_NoMerit", "Not enough Merit") : "");
			const auto where = Bearing(p->marker);
			rows.push_back({ { "section", Loc::T("$AG_Sec_Intel", "Intel") }, { "sectionId", "Intel" }, { "group", "poi" },
				{ "id", std::format("poi:{:08X}", p->marker->GetFormID()) }, { "name", PoiName(p->marker) },
				{ "desc", where.empty() ? CategoryName(cat) : Loc::F("$AG_Intel_Desc", "{} · {}", CategoryName(cat), where) },
				{ "cost", cat.merit }, { "available", note.empty() }, { "note", note } });
		}
		return rows;
	}

	std::string BuyPoi(const std::string& a_id)
	{
		RE::FormID id = 0;
		try {
			id = static_cast<RE::FormID>(std::stoul(a_id.substr(4), nullptr, 16));
		} catch (...) {}
		BuildPois();
		const Poi* poi = nullptr;
		for (auto& p : g_pois)
			if (p.marker->GetFormID() == id) poi = &p;
		auto* md = poi ? MapData(poi->marker) : nullptr;
		if (!md) return Loc::T("$AG_Intel_Nothing", "The Guild has nothing on that place.");
		if (poi->marker->IsDisabled()) return Loc::T("$AG_Intel_Nothing", "The Guild has nothing on that place.");
		const auto name = PoiName(poi->marker);
		if (md->flags.any(RE::MapMarkerData::Flag::kVisible)) return Loc::F("$AG_Intel_Known", "{} is already on your map.", name);
		const int cost = g_poiCats[poi->category].merit;
		if (!Guild::TrySpendMerit(cost, Loc::F("$AG_Log_Poi", "Bought intel on {} for {} Merit.", name, cost)))
			return Loc::F("$AG_Intel_Cost", "Intel on {} costs {} Merit.", name, cost);
		md->SetVisible(true);
		if (auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton()) {
			RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> cb;
			vm->DispatchStaticCall("AG_QuestHelper", "RevealMarker", RE::MakeFunctionArguments(static_cast<RE::TESObjectREFR*>(poi->marker)), cb);
		}
		SKSE::log::info("Dungeons: point of interest bought - {} ({}, {} merit)", name, g_poiCats[poi->category].id, cost);
		return Loc::F("$AG_Poi_Bought", "{} is marked on your map. {} Merit spent.", name, cost);
	}

	std::string BuyIntel(const std::string& a_id)
	{
		RE::BGSLocation* loc = nullptr;
		try {
			loc = RE::TESForm::LookupByID<RE::BGSLocation>(static_cast<RE::FormID>(std::stoul(a_id.substr(6), nullptr, 16)));
		} catch (...) {}
		if (!loc) return Loc::T("$AG_Intel_Nothing", "The Guild has nothing on that place.");
		auto* marker = MarkerOf(loc);
		auto* md = MapData(marker);
		if (!md || marker->IsDisabled()) return Loc::T("$AG_Intel_Nothing", "The Guild has nothing on that place.");
		if (md->flags.any(RE::MapMarkerData::Flag::kVisible)) return Loc::F("$AG_Intel_Known", "{} is already on your map.", Name(loc));
		BuildZones();
		auto z = g_zoneOf.find(loc);
		const int rank = FromLevel(LevelFor(z != g_zoneOf.end() ? z->second : nullptr));
		if (rank > Guild::Rank()) return Loc::F("$AG_Intel_RankGate", "The Guild only shares Rank {0} intel with Rank {0} adventurers.", Letter(rank));
		const int cost = Guild::IntelMerit(rank);
		const auto name = Name(loc);
		if (!Guild::TrySpendMerit(cost, Loc::F("$AG_Log_Intel", "Bought intel on {} (Threat Rank {}) for {} Merit.", name, Letter(rank), cost))) {
			return Loc::F("$AG_Intel_Cost", "Intel on {} costs {} Merit.", name, cost);
		}
		md->SetVisible(true);   // at once: the counter's list refreshes before the Papyrus call below runs
		// Papyrus ObjectReference.AddToMap(false): exactly what a rumour does (visible, no fast travel)
		if (auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton()) {
			RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> cb;
			vm->DispatchStaticCall("AG_QuestHelper", "RevealMarker", RE::MakeFunctionArguments(static_cast<RE::TESObjectREFR*>(marker)), cb);
		}
		// no toast: bought on the counter, whose status line already confirms it
		SKSE::log::info("Dungeons: intel bought on {} (rank {}, {} merit)", name, Letter(rank), cost);
		Guild::Notify("AG_IntelBought", name, static_cast<float>(rank));
		return Loc::F("$AG_Intel_Bought", "{} is marked on your map (Threat Rank {}). {} Merit spent.", name, Letter(rank), cost);
	}

	std::string DebugInfo()
	{
		auto* pc = RE::PlayerCharacter::GetSingleton();
		auto* loc = pc ? pc->GetCurrentLocation() : nullptr;
		auto* d = DungeonOf(loc);
		auto* z = ZoneHere();
		std::string key = d ? Adventurers::StableKey(d) : "";
		std::lock_guard l(g_lock);
		return std::format("location={} dungeon={} [{}] zone={} min={} max={} zoneLevel={} level={} rank={} cleared={} visited={} reported={}",
			loc ? Name(loc) : "none", d ? Name(d) : "none", key,
			z ? std::format("{:08X}", z->GetFormID()) : "none", z ? z->data.minLevel : 0, z ? z->data.maxLevel : 0, z ? z->gameData.zoneLevel : 0,
			LevelHere(), Letter(FromLevel(LevelHere())), d && d->IsCleared(), g_visited.contains(key), g_reported.contains(key));
	}

	std::string DebugClear()
	{
		auto* pc = RE::PlayerCharacter::GetSingleton();
		auto* d = DungeonOf(pc ? pc->GetCurrentLocation() : nullptr);
		if (!d) return "not in a dungeon";
		OnCleared(d);
		return "cleared " + Name(d);
	}
}
