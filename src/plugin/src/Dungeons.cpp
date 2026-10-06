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

		bool Clearable(const RE::BGSLocation* a_loc)
		{
			// Civil War camps (LocTypeMilitaryCamp) carry LocTypeDungeon but are faction headquarters, not places to
			// clear: no dungeon notice on entry, no intel for sale.
			if (!a_loc || a_loc->HasKeywordString("LocTypeMilitaryCamp")) return false;
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

		RE::BGSLocation* HoldOf(RE::BGSLocation* a_loc)
		{
			for (auto* l = a_loc; l; l = l->parentLoc) {
				if (l->HasKeywordString("LocTypeHold")) return l;
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
	}

	int ClearedCount()
	{
		std::lock_guard l(g_lock);
		return static_cast<int>(g_reported.size());
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
				{ "name", Name(lead.loc) }, { "tier", std::string(1, Letter(lead.rank)) },
				{ "desc", where.empty() ? Kind(lead.loc) : Loc::F("$AG_Intel_Desc", "{} · {}", Kind(lead.loc), where) },
				{ "cost", cost }, { "available", note.empty() }, { "note", note } });
		}
		return rows;
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
		if (!md) return Loc::T("$AG_Intel_Nothing", "The Guild has nothing on that place.");
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
