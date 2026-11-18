// The Guild Hall's map marker: a MapMarker reference made at run time in Tamriel's persistent cell, as the hall's pieces are,
// so no record of the vanilla world is edited. It starts unseen, as a vanilla location does: the registration quest puts it on
// the map (AG_QuestHelper.MarkRegistrationHall, AddToMap), and the game's own discovery, walking near it, makes it a place to
// fast travel to.
// - The reference's map data is the ExtraMapMarker a plugin's marker carries (XMRK), built from a vanilla marker's (its name
//   holds a game vtable, so it cannot be made from nothing) with the hall's name and icon.
// - The marker is added to the player's list of map markers, which the map and the discovery check walk.
// - The reference and its flags (seen, can travel to) are kept in AG's co-save (its HMRK record). After a load the reference is
//   found again or made anew, its map data put back if the save dropped it, its flags restored and its place on the list
//   checked; the list is checked again whenever cells load.
#include "hall.h"

#include "../Guild.h"
#include "../GuildHall.h"
#include "../Loc.h"

#include <mutex>

namespace Hall
{
	namespace
	{
		constexpr std::uint32_t kMarkerRecord = 'HMRK', kMarkerVersion = 1;
		constexpr RE::FormID    kTamriel = 0x3C;
		constexpr RE::FormID    kMapMarkerBase = 0x10;  // MapMarker, Skyrim.esm
		// on the forecourt before the front doors, where fast travel lands, facing the doors: the installed site's (its layout, from
		// sites.json); Riverwood's for a layout from before 2026-11-17, which names none
		RE::NiPoint3 Spot()
		{
			if (const auto m = MarkerSpot()) return m->first;
			return { 15834.0f, -48962.0f, 568.4f };
		}
		float FacingDeg()
		{
			if (const auto m = MarkerSpot()) return m->second;
			return 156.3f;
		}
		constexpr auto         kIcon = RE::MARKER_TYPE::kSettlement;
		constexpr std::uint8_t kKeptFlags = static_cast<std::uint8_t>(RE::MapMarkerData::Flag::kVisible) |
		                                    static_cast<std::uint8_t>(RE::MapMarkerData::Flag::kCanTravelTo);

		std::mutex   g_mlock;
		RE::FormID   g_marker = 0;  // the created reference; 0: none yet in this game
		std::uint8_t g_flags = 0;   // its seen / can-travel-to flags, as last saved or read

		RE::TESObjectREFR* MarkerRef(RE::FormID a_id)
		{
			auto* r = a_id ? RE::TESForm::LookupByID<RE::TESObjectREFR>(a_id) : nullptr;
			if (!r || r->IsDeleted()) return nullptr;
			auto* base = r->GetBaseObject();
			return base && base->GetFormID() == kMapMarkerBase ? r : nullptr;
		}

		RE::MapMarkerData* Data(RE::TESObjectREFR* a_ref)
		{
			auto* x = a_ref ? a_ref->extraList.GetByType<RE::ExtraMapMarker>() : nullptr;
			return x ? x->mapData : nullptr;
		}

		// a vanilla marker's map data in Tamriel's persistent cell, the pattern for ours
		RE::MapMarkerData* Pattern(RE::TESObjectREFR* a_not)
		{
			auto*              ws = RE::TESForm::LookupByID<RE::TESWorldSpace>(kTamriel);
			RE::MapMarkerData* found = nullptr;
			if (ws && ws->persistentCell) ws->persistentCell->ForEachReference([&](RE::TESObjectREFR* r) {
				if (r && r != a_not && !r->IsDeleted())
					if (auto* d = Data(r); d && d->locationName.fullName.c_str()) {
						found = d;
						return RE::BSContainer::ForEachResult::kStop;
					}
				return RE::BSContainer::ForEachResult::kContinue;
			});
			return found;
		}

		std::string FlagText(std::uint8_t a_flags)
		{
			if (a_flags & static_cast<std::uint8_t>(RE::MapMarkerData::Flag::kCanTravelTo)) return "discovered";
			if (a_flags & static_cast<std::uint8_t>(RE::MapMarkerData::Flag::kVisible)) return "on the map, not discovered";
			return "unseen";
		}

		// the bytes can be read (a structured exception caught: no C++ object in this function to unwind)
		bool Readable(const void* a_p, std::size_t a_n)
		{
			__try {
				volatile auto first = *static_cast<const volatile std::uint8_t*>(a_p);
				volatile auto last = *(static_cast<const volatile std::uint8_t*>(a_p) + a_n - 1);
				(void)first;
				(void)last;
				return true;
			} __except (1) {
				return false;
			}
		}

		// The player's list of map markers. VR keeps it in its own block of the player (GetVRPlayerRuntimeData); read through
		// the flat runtime's block it is garbage and the game crashes. A list that does not look like one is left alone.
		RE::BSTArray<RE::ObjectRefHandle>* PlayersList()
		{
			auto* pc = RE::PlayerCharacter::GetSingleton();
			if (!pc) return nullptr;
			RE::BSTArray<RE::ObjectRefHandle>* list = nullptr;
			if (REL::Module::IsVR()) {
				if (auto* vr = pc->GetVRPlayerRuntimeData()) list = &vr->currentMapMarkers;
			} else
				list = &pc->GetPlayerRuntimeData().currentMapMarkers;
			// a list: a sane size, its entries readable, and its first entry a map marker (every entry is one)
			const auto first = [&] {
				RE::NiPointer<RE::TESObjectREFR> r;
				const RE::RefHandle h = list->empty() ? 0 : list->front().native_handle();
				return list->empty() || (RE::LookupReferenceByHandle(h, r) && r && Data(r.get()));
			};
			if (list && (list->size() > list->capacity() || list->size() > 20000 || (list->size() && (!list->data() ||
				!Readable(list->data(), list->size() * sizeof(RE::ObjectRefHandle)))) || !first())) {
				static bool told = false;
				if (!told) SKSE::log::warn("Hall: the player's list of map markers does not look like one ({} of {}); the marker is not put on it", list->size(), list->capacity());
				told = true;
				return nullptr;
			}
			return list;
		}

		bool OnPlayersList(RE::TESObjectREFR* a_ref, bool a_add)
		{
			auto* list = PlayersList();
			if (!list) return true;   // (nothing to add it to: not reported again as put on)
			for (auto& h : *list)
				if (h.get().get() == a_ref) return true;
			if (a_add) list->push_back(a_ref->GetHandle());
			return false;
		}

		void TakeOffPlayersList(RE::TESObjectREFR* a_ref)
		{
			auto* l = PlayersList();
			if (!l) return;
			auto& list = *l;
			for (std::uint32_t i = 0; i < list.size();)
				if (list[i].get().get() == a_ref) list.erase(list.begin() + i);
				else ++i;
		}
	}

	// On the main thread: the marker stands, carries its map data and flags, and is on the player's list. Logs what it changed.
	void MarkerEnsure(const char* a_why)
	{
		if (!AG::GuildHall::Loaded()) return;
		std::scoped_lock l(g_mlock);
		std::vector<std::string> did;
		auto*                    ref = MarkerRef(g_marker);
		if (!ref) {
			auto* dh = RE::TESDataHandler::GetSingleton();
			auto* ws = RE::TESForm::LookupByID<RE::TESWorldSpace>(kTamriel);
			auto* base = RE::TESForm::LookupByID<RE::TESBoundObject>(kMapMarkerBase);
			if (!dh || !ws || !ws->persistentCell || !base) {
				SKSE::log::warn("Hall: map marker not made ({}): no Tamriel persistent cell or no MapMarker record", a_why);
				return;
			}
			ref = dh->CreateReferenceAtLocation(base, Spot(), RE::NiPoint3(0.0f, 0.0f, FacingDeg() * 3.14159265f / 180.0f), ws->persistentCell, ws,
				nullptr, nullptr, RE::ObjectRefHandle(), true, true).get().get();
			if (!ref) {
				SKSE::log::warn("Hall: map marker not made ({}): the reference was not created", a_why);
				return;
			}
			did.push_back(g_marker ? std::format("made anew (the save's {:08X} is gone)", g_marker) : "made");
			g_marker = ref->GetFormID();
		} else if (ref->GetPosition().GetDistance(Spot()) > 64.0f) {
			// a save's marker from where the hall stood before (the hall itself is rebuilt from the layout): moved to the
			// forecourt. A marker has no 3D and lives in the persistent cell, so its stored position is what the map reads. A hall
			// at another site (the installer's other choice) is a place not yet been to: it stays on the map, but fast travel to
			// it waits until the player has found it, as a vanilla location's does
			const auto was = ref->GetPosition();
			ref->data.location = Spot();
			ref->data.angle = RE::NiPoint3(0.0f, 0.0f, FacingDeg() * 3.14159265f / 180.0f);
			if (was.GetDistance(Spot()) > 8192.0f) {
				g_flags &= static_cast<std::uint8_t>(~static_cast<std::uint8_t>(RE::MapMarkerData::Flag::kCanTravelTo));
				if (auto* d = Data(ref)) d->flags.reset(RE::MapMarkerData::Flag::kCanTravelTo);
			}
			did.push_back(std::format("moved from {:.0f}, {:.0f} to the forecourt", was.x, was.y));
		}
		auto* data = Data(ref);
		if (!data) {
			auto* from = Pattern(ref);
			if (!from) {
				SKSE::log::warn("Hall: map marker {:08X} has no map data and no vanilla marker to copy it from ({})", g_marker, a_why);
				return;
			}
			data = RE::malloc<RE::MapMarkerData>();
			std::memcpy(static_cast<void*>(data), from, sizeof(RE::MapMarkerData));
			new (&data->locationName.fullName) RE::BSFixedString(AG::Loc::T("$AG_Hall_MapName", "Adventurers Guild Hall").c_str());
			data->flags.reset(RE::MapMarkerData::Flag::kVisible, RE::MapMarkerData::Flag::kCanTravelTo, RE::MapMarkerData::Flag::kShowAllHidden);
			data->type = kIcon;
			auto* extra = RE::BSExtraData::Create<RE::ExtraMapMarker>();
			extra->mapData = data;
			ref->extraList.Add(extra);
			did.push_back("map data given");
		}
		// the save's flags back (a save that kept the map data keeps them anyway), and the game's own as they are now
		const auto now = static_cast<std::uint8_t>(data->flags.underlying() & kKeptFlags);
		if (const auto lost = static_cast<std::uint8_t>(g_flags & ~now)) {
			data->flags.set(static_cast<RE::MapMarkerData::Flag>(lost));
			did.push_back(std::format("flags restored ({})", FlagText(g_flags)));
		}
		g_flags = static_cast<std::uint8_t>(data->flags.underlying() & kKeptFlags);
		if (!OnPlayersList(ref, true)) did.push_back("put on the player's list of map markers");
		if (!did.empty()) {
			std::string what;
			for (const auto& d : did) what += (what.empty() ? "" : ", ") + d;
			SKSE::log::info("Hall: map marker {:08X} {} ({}): {}", g_marker, what, a_why, FlagText(g_flags));
		}
	}

	RE::TESObjectREFR* MapMarker()
	{
		std::scoped_lock l(g_mlock);
		return MarkerRef(g_marker);
	}

	// the hall taken away (HallRemove): the marker goes too
	void MarkerRemove()
	{
		std::scoped_lock l(g_mlock);
		if (auto* ref = MarkerRef(g_marker)) {
			TakeOffPlayersList(ref);
			ref->Disable();
			ref->SetDelete(true);
			SKSE::log::info("Hall: map marker {:08X} taken down", g_marker);
		}
		g_marker = 0;
		g_flags = 0;
	}

	void MarkerSave(SKSE::SerializationInterface* a)
	{
		std::scoped_lock l(g_mlock);
		auto* ref = MarkerRef(g_marker);
		if (!ref) return;
		if (auto* data = Data(ref)) {
			const auto now = static_cast<std::uint8_t>(data->flags.underlying() & kKeptFlags);
			if (now != g_flags) SKSE::log::info("Hall: map marker {:08X} now {}", g_marker, FlagText(now));
			g_flags = now;
		}
		if (!a->OpenRecord(kMarkerRecord, kMarkerVersion)) return;
		a->WriteRecordData(g_marker);
		a->WriteRecordData(g_flags);
	}

	void MarkerLoad(SKSE::SerializationInterface* a, std::uint32_t a_type, std::uint32_t a_version)
	{
		if (a_type != kMarkerRecord || a_version != kMarkerVersion) return;
		std::scoped_lock l(g_mlock);
		RE::FormID id = 0, now = 0;
		std::uint8_t flags = 0;
		a->ReadRecordData(id);
		a->ReadRecordData(flags);
		g_marker = a->ResolveFormID(id, now) ? now : 0;
		g_flags = flags & kKeptFlags;
	}

	void MarkerRevert()
	{
		std::scoped_lock l(g_mlock);
		g_marker = 0;
		g_flags = 0;
	}
}
