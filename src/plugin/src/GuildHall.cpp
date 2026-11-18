// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "GuildHall.h"

#include "BountyWatch.h"
#include "Guild.h"
#include "Loc.h"
#include "MissiveWatch.h"
#include "hall/hall.h"

#include <array>
#include <filesystem>
#include <fstream>
#include <atomic>
#include <vector>


namespace AG::GuildHall
{
	namespace
	{
		// the hall's plugin
		constexpr std::array<std::string_view, 1> kPlugins{ "AdventurersGuild - Guild Hall.esp" };
		// the clerks: Margot Belleau (day) and Elise Varnier (evening), their actor bases. Fixed IDs: the hall's merge step
		// gives every NPC record its NPC-build ID + 0x7800 (the NPC session, 2026-10-27). They are kept OUT of
		// AG_GuildLiaisonFaction (Guild's load watcher asks IsClerk): the core plugin's shared ask/nofee lines take anyone in
		// it, and the answers that follow are the innkeepers' own, so register, promote and card replacement would dead-end
		// with a clerk. Their own business topic (the hall's plugin, kBusinessTopic) opens the counter the way the
		// innkeepers' does: Guild's line watcher sees it begin (IsBusinessTopic). Its lines' fragment
		// (AG_Native.ActionOpenCounter) is SkyrimNet's way in, as on the innkeepers' lines; in the Dialogue Menu it opened
		// nothing (the SE test install, 2026-10-27).
		constexpr std::array<RE::FormID, 2> kClerks{ 0x8000, 0x800E };
		// the promotion trials' records, at fixed IDs of their block (0x9800-0x99FF, the hall session's grant, 2026-11-05;
		// npcgen's "Promotion trials" section makes them first, in this order): the global that conditions their dialogue,
		// the five quests (D ... S) and the five creatures' actor bases
		constexpr RE::FormID kTrialGlobal = 0x9800, kTrialQuests = 0x9802, kTrialCreatures = 0x9807;
		constexpr std::string_view          kBusinessTopic = "AGHallClerkTopicBusiness";

		template <class T>
		T* HallForm(RE::FormID a_local)
		{
			auto* dh = RE::TESDataHandler::GetSingleton();
			if (!dh) return nullptr;
			for (auto p : kPlugins)
				if (dh->LookupModByName(p))
					if (auto* f = dh->LookupForm<T>(a_local, p)) return f;
			return nullptr;
		}

		// Missives' hold names, in the order the picker lists them, and the town of each hold's counter
		struct Hold { const char* key; const char* city; };
		constexpr std::array<Hold, 10> kHolds{ { { "Whiterun", "Whiterun" }, { "Haafingar", "Solitude" }, { "Eastmarch", "Windhelm" },
			{ "Rift", "Riften" }, { "Reach", "Markarth" }, { "Falkreath", "Falkreath" }, { "Hjaalmarch", "Morthal" },
			{ "Pale", "Dawnstar" }, { "Winterhold", "Winterhold" }, { "Solstheim", "Raven Rock" } } };

		// a hold's name in the player's language (each key written out: tools/make_translations.py reads them from here)
		std::string HoldName(const Hold& a_h)
		{
			const std::string_view k = a_h.key;
			if (k == "Whiterun") return Loc::T("$AG_Hold_Whiterun", "Whiterun");
			if (k == "Haafingar") return Loc::T("$AG_Hold_Haafingar", "Haafingar");
			if (k == "Eastmarch") return Loc::T("$AG_Hold_Eastmarch", "Eastmarch");
			if (k == "Rift") return Loc::T("$AG_Hold_Rift", "The Rift");
			if (k == "Reach") return Loc::T("$AG_Hold_Reach", "The Reach");
			if (k == "Falkreath") return Loc::T("$AG_Hold_Falkreath", "Falkreath");
			if (k == "Hjaalmarch") return Loc::T("$AG_Hold_Hjaalmarch", "Hjaalmarch");
			if (k == "Pale") return Loc::T("$AG_Hold_Pale", "The Pale");
			if (k == "Winterhold") return Loc::T("$AG_Hold_Winterhold", "Winterhold");
			return Loc::T("$AG_Hold_Solstheim", "Solstheim");
		}
		const Hold* HoldByKey(const std::string& a_key)
		{
			for (auto& h : kHolds)
				if (a_key == h.key) return &h;
			return nullptr;
		}
		const Hold* HoldByCity(const std::string& a_city)
		{
			for (auto& h : kHolds)
				if (a_city == h.city) return &h;
			return nullptr;
		}
	}

	bool IsBranch(const std::string& a_branch) { return a_branch == kBranch; }

	bool Loaded()
	{
		auto* dh = RE::TESDataHandler::GetSingleton();
		if (!dh) return false;
		for (auto p : kPlugins)
			if (dh->LookupModByName(p)) return true;
		return false;
	}

	namespace
	{
		// the toggles as the MCM set them; until it does (a game's first seconds), the 2.0 default: all on
		std::array<std::atomic<bool>, static_cast<std::size_t>(Only::kCount)> g_only{ true, true, true, true, true, true, true, true };
		std::atomic<bool> g_followersByHand{ true };
		std::atomic<bool> g_trials{ true };  // MCM > Guild Hall > Promotion Trials, on by default

		// each one in effect, as a global of the core plugin: registration and promotion for the innkeepers' lines
		// (AG_HallRegistrationGlobal 0xFD2, AG_HallPromotionGlobal 0xFD3), every one for SkyrimNet's actions and knowledge
		// (the rest 0xFD5-0xFDA), in GuildHall::Only's order
		constexpr std::array<RE::FormID, static_cast<std::size_t>(Only::kCount)> kGlobals{ 0xFD2, 0xFD3, 0xFD5, 0xFD6, 0xFD7, 0xFD8, 0xFD9, 0xFDA };
		void SyncGlobal(Only a_what)
		{
			const auto i = static_cast<std::size_t>(a_what);
			auto*      dh = RE::TESDataHandler::GetSingleton();
			auto*      g = dh && i < kGlobals.size() ? dh->LookupForm<RE::TESGlobal>(kGlobals[i], "AdventurersGuild.esp") : nullptr;
			if (!g) {
				SKSE::log::warn("GuildHall: the hall-only global {:03X} is missing (AdventurersGuild.esp) - dialogue and SkyrimNet will not follow toggle {}",
					i < kGlobals.size() ? kGlobals[i] : 0, i);
				return;
			}
			g->value = OnlyAtHall(a_what) ? 1.0f : 0.0f;
		}
	}

	void SetOnly(Only a_what, bool a_on)
	{
		const auto i = static_cast<std::size_t>(a_what);
		if (i >= g_only.size()) return;
		if (g_only[i].exchange(a_on) != a_on)
			SKSE::log::info("GuildHall: hall-only toggle {} {}{}", i, a_on ? "on" : "off", a_on && !Loaded() ? " (no effect: the hall's plugin is not loaded)" : "");
		SyncGlobal(a_what);
		if (a_what == Only::kRegistration) Guild::RegistrationRouteChanged();
	}

	bool OnlyAtHall(Only a_what)
	{
		const auto i = static_cast<std::size_t>(a_what);
		if (a_what == Only::kPromotion && TrialsOn()) return true;  // a trial is set by the Guild Master, at the hall
		return i < g_only.size() && g_only[i].load() && Loaded();
	}

	RE::TESQuest* TrialQuest(int a_rank)
	{
		return a_rank >= 1 && a_rank <= 5 ? HallForm<RE::TESQuest>(kTrialQuests + static_cast<RE::FormID>(a_rank - 1)) : nullptr;
	}

	bool TrialsOn() { return g_trials.load() && TrialQuest(1) != nullptr; }

	void SetTrials(bool a_on)
	{
		const bool was = TrialsOn();
		if (g_trials.exchange(a_on) != a_on)
			SKSE::log::info("GuildHall: promotion trials {}{}", a_on ? "on" : "off", a_on && !TrialQuest(1) ? " (no effect: the hall's trial quests are not loaded)" : "");
		if (auto* g = HallForm<RE::TESGlobal>(kTrialGlobal)) g->value = TrialsOn() ? 1.0f : 0.0f;
		SyncGlobal(Only::kPromotion);
		// a trial under way ends with the toggle (its quest script's Cancel): the player may promote at once
		if (was && !TrialsOn())
			for (int r = 1; r <= 5; ++r)
				if (auto* q = TrialQuest(r); q && q->IsRunning()) CallTrial(q, "Cancel");
	}

	int TrialCreatureRank(RE::TESNPC* a_base)
	{
		if (!a_base) return -1;
		for (int r = 1; r <= 5; ++r)
			if (auto* npc = HallForm<RE::TESNPC>(kTrialCreatures + static_cast<RE::FormID>(r - 1)); npc && npc == a_base) return r;
		return -1;
	}

	bool CallTrial(RE::TESQuest* a_quest, const char* a_function)
	{
		auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton();
		if (!vm || !a_quest) return false;
		const auto handle = vm->GetObjectHandlePolicy()->GetHandleForObject(static_cast<RE::VMTypeID>(RE::TESQuest::FORMTYPE), a_quest);
		RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> cb;
		auto* args = RE::MakeFunctionArguments();
		const bool ok = vm->DispatchMethodCall(handle, "AGHallTrialQuestScript", a_function, args, cb);
		delete args;
		SKSE::log::info("GuildHall: {} on trial quest {:08X}{}", a_function, a_quest->GetFormID(), ok ? "" : " - not called");
		return ok;
	}

	bool Allows(Only a_what, const std::string& a_branch) { return IsBranch(a_branch) || !OnlyAtHall(a_what); }

	std::string AtHallNote() { return Loc::T("$AG_UI_AtGuildHall", "At the Guild Hall"); }

	std::string RefusedHere() { return Loc::T("$AG_Hall_OnlyThere", "Only the Guild Hall offers that."); }

	std::optional<Only> ServiceFeature(std::string_view a_id)
	{
		if (a_id == "appraisal" || a_id == "perk" || a_id.starts_with("train:")) return Only::kTraining;
		if (a_id.starts_with("ware:")) return Only::kBoxes;
		if (a_id.starts_with("lib:")) return Only::kLibrary;
		if (a_id.starts_with("tome:")) return Only::kTomes;
		if (a_id.starts_with("augment:")) return Only::kAugments;
		return std::nullopt;
	}

	void GreyServices(nlohmann::json& a_services, const std::string& a_branch)
	{
		if (!a_services.is_array()) return;
		for (auto& row : a_services) {
			const auto f = ServiceFeature(row.value("id", ""));
			if (!f || Allows(*f, a_branch)) continue;
			row["available"] = false;
			row["note"] = AtHallNote();
		}
	}

	void SetFollowersByHand(bool a_on)
	{
		if (g_followersByHand.exchange(a_on) != a_on) SKSE::log::info("GuildHall: followers registered {}", a_on ? "by hand" : "on recruitment");
	}

	bool FollowersByHand() { return g_followersByHand.load(); }

	std::vector<RE::FormID> ClerkBases()
	{
		std::vector<RE::FormID> out;
		for (const auto id : kClerks)
			if (auto* npc = HallForm<RE::TESNPC>(id)) out.push_back(npc->GetFormID());
		return out;
	}

	bool IsClerk(RE::Actor* a_actor)
	{
		auto* base = a_actor ? a_actor->GetActorBase() : nullptr;
		if (!base) return false;
		const auto clerks = ClerkBases();
		return std::ranges::find(clerks, base->GetFormID()) != clerks.end();
	}

	bool IsBusinessTopic(std::string_view a_editorID) { return a_editorID == kBusinessTopic; }

	std::string_view ClerkTopic(std::string_view a_editorID)
	{
		constexpr std::string_view kPrefix = "AGHallClerkTopic";
		if (!a_editorID.starts_with(kPrefix)) return {};
		const auto rest = a_editorID.substr(kPrefix.size());
		for (std::string_view k : { "RegisterPay", "PromotePay", "Replace", "CardHandIn" })
			if (rest == k) return k;
		return {};
	}

	void CounterData(nlohmann::json& a_data)
	{
		a_data["hall"] = true;
		auto holds = nlohmann::json::array();
		for (auto& h : kHolds) holds.push_back({ { "key", h.key }, { "name", HoldName(h) } });
		a_data["holds"] = std::move(holds);

		auto posts = MissiveWatch::AllPostings();
		for (auto& p : posts) {
			const auto* h = HoldByKey(p.value("hold", ""));
			p["holdName"] = h ? HoldName(*h) : p.value("hold", "");
			p["city"] = Guild::CityName(p.value("city", h ? h->city : ""));
		}
		a_data["postings"] = std::move(posts);

		// the hall posts no bounty above the rank of work the player may take, as the missives' gate does; the
		// player's own (taken or slain) is always listed, as a town counter lists it
		static constexpr std::string_view kRanks = "EDCBAS";
		const int rank = Guild::WorkRank();
		auto      bounties = nlohmann::json::array();
		for (auto& b : BountyWatch::All()) {
			const auto tier = b.value("tier", "E");
			if (const auto r = kRanks.find(tier.empty() ? 'E' : tier[0]);
				b.value("state", "offer") == "offer" && r != std::string_view::npos && static_cast<int>(r) > rank) continue;
			const auto* h = HoldByCity(b.value("city", ""));
			if (!h) continue;
			b["hold"] = h->key;
			b["holdName"] = HoldName(*h);
			b["city"] = Guild::CityName(h->city);
			bounties.push_back(std::move(b));
		}
		a_data["bounties"] = std::move(bounties);
		// "A new bounty?": a bounty for a hold with none, its target unseen until it is taken
		a_data["newBounty"] = BountyWatch::NewBountyPossible();
	}

	void NameHold(nlohmann::json& a_row)
	{
		if (const auto* h = HoldByCity(a_row.value("city", ""))) {
			a_row["hold"] = h->key;
			a_row["holdName"] = HoldName(*h);
		}
	}

	namespace
	{
		bool ScreenSpaceGIOn()
		{
			if (!REX::W32::GetModuleHandleW(L"CommunityShaders.dll") || !std::filesystem::exists("Data/Shaders/Features/ScreenSpaceGI.ini")) return false;
			std::ifstream in("Data/SKSE/Plugins/CommunityShaders/SettingsUser.json");
			if (!in) return true;  // (its default: on)
			const auto j = nlohmann::json::parse(in, nullptr, false);
			if (j.is_discarded()) return true;
			if (const auto boot = j.find("Disable at Boot"); boot != j.end() && boot->is_object() && boot->value("ScreenSpaceGI", false)) return false;
			if (const auto gi = j.find("Screen Space GI"); gi != j.end() && gi->is_object()) return gi->value("EnableGI", true);
			return true;
		}

		RE::Color Grey(std::uint8_t a_r, std::uint8_t a_g, std::uint8_t a_b) { return RE::Color(a_r, a_g, a_b, 0); }

		// Community Shaders' Light Limit Fix, which lifts the vanilla renderer's few lights a shape: its DLL, its feature file,
		// and not switched off at boot (the same test as the screen-space GI's)
		bool LightLimitFixOn()
		{
			if (!REX::W32::GetModuleHandleW(L"CommunityShaders.dll") || !std::filesystem::exists("Data/Shaders/Features/LightLimitFix.ini")) return false;
			std::ifstream in("Data/SKSE/Plugins/CommunityShaders/SettingsUser.json");
			if (!in) return true;
			const auto j = nlohmann::json::parse(in, nullptr, false);
			if (j.is_discarded()) return true;
			if (const auto boot = j.find("Disable at Boot"); boot != j.end() && boot->is_object() && boot->value("LightLimitFix", false)) return false;
			return true;
		}

		bool vanillaLighting = false;   // set at data load: no Light Limit Fix, so only the hall's chandeliers burn

		// the ambient raised where lights are switched off, so the rooms stay as easy to see: higher by day, when the window
		// lights would have carried the daylight, than at night
		constexpr float kNightAmbient = 2.0f, kDayAmbient = 2.4f;
		constexpr float kDayFrom = 6.0f, kDayTo = 20.0f;   // game hours
		RE::Color Scaled(RE::Color a_c, float a_f)
		{
			const auto up = [a_f](std::uint8_t v) { return static_cast<std::uint8_t>(std::min(255.0f, std::round(v * a_f))); };
			return RE::Color(up(a_c.red), up(a_c.green), up(a_c.blue), a_c.alpha);
		}
		// what is raised: the ambient and directional ambient of the hall's own template, or of a cell's own lighting, each with
		// its values as loaded, so every change scales from them
		struct Ambient
		{
			RE::Color*                                ambient;
			RE::BGSDirectionalAmbientLightingColors* dalc;
			RE::Color                                 ambient0;
			RE::BGSDirectionalAmbientLightingColors  dalc0;
		};
		std::vector<Ambient> ambients;
		float                ambientNow = 0.0f;

		void ApplyAmbient(float a_f)
		{
			if (a_f == ambientNow) return;
			for (auto& a : ambients) {
				*a.ambient = Scaled(a.ambient0, a_f);
				*a.dalc = a.dalc0;
				for (auto* mm : { &a.dalc->directional.x, &a.dalc->directional.y, &a.dalc->directional.z }) {
					mm->max = Scaled(mm->max, a_f);
					mm->min = Scaled(mm->min, a_f);
				}
			}
			ambientNow = a_f;
			SKSE::log::info("GuildHall: no Light Limit Fix: the hall's ambient x{}", a_f);
		}

		float WantedAmbient()
		{
			const auto* cal = RE::Calendar::GetSingleton();
			const float h = cal ? cal->GetHour() : 12.0f;
			return h >= kDayFrom && h < kDayTo ? kDayAmbient : kNightAmbient;
		}
	}

	void TuneLighting()
	{
		if (!ScreenSpaceGIOn()) return;
		const auto handler = RE::TESDataHandler::GetSingleton();
		if (!handler) return;
		constexpr std::string_view hall = "AdventurersGuild - Guild Hall.esp";
		const auto ours = [&](const RE::TESForm* a_form) {
			const auto file = a_form ? a_form->GetFile(0) : nullptr;
			return file && file->GetFilename() == hall;
		};
		for (const auto t : handler->GetFormArray<RE::BGSLightingTemplate>()) {
			if (!ours(t)) continue;
			t->data.ambient = Grey(51, 51, 51);
			auto& d = t->directionalAmbientLightingColors.directional;
			d.x.max = d.x.min = d.y.max = d.y.min = Grey(23, 21, 19);
			d.z.max = Grey(47, 46, 45);
			d.z.min = Grey(51, 51, 51);
		}
		for (const auto i : handler->GetFormArray<RE::TESImageSpace>()) {
			if (ours(i)) i->data.hdr.eyeAdaptStrength = 0.4f;
		}
		SKSE::log::info("GuildHall: Community Shaders' screen-space GI is on: the hall's lighting set for it");
	}

	namespace
	{
		// the hall's cells by the plugin's own IDs (carried build to build by its ledger)
		constexpr RE::FormID kMainCell = 0x000908, kStrongroomCell = 0x000924, kBasementCell = 0x000D14;   // AGHall2InteriorCell, AGHall2LookoutCell, AGHall2BasementCell

		RE::TESObjectCELL* HallCell(RE::TESDataHandler* a_dh, RE::FormID a_id)
		{
			for (const auto name : kPlugins)
				if (a_dh->LookupModByName(name))
					if (auto* c = a_dh->LookupForm<RE::TESObjectCELL>(a_id, name)) return c;
			return nullptr;
		}
	}

	bool PlayerInHall()
	{
		auto* dh = RE::TESDataHandler::GetSingleton();
		auto* pc = RE::PlayerCharacter::GetSingleton();
		auto* here = pc ? pc->GetParentCell() : nullptr;
		if (!dh || !here || !Loaded()) return false;
		for (const auto id : { kMainCell, kStrongroomCell, kBasementCell })
			if (HallCell(dh, id) == here) return true;
		return false;
	}

	std::pair<int, int> PrepareUninstall()
	{
		int trials = 0, followers = 0;
		if (!Loaded()) return { 0, 0 };
		for (int r = 1; r <= 5; ++r)
			if (auto* q = TrialQuest(r); q && q->IsRunning() && CallTrial(q, "Cancel")) ++trials;
		// vanilla's follower: DialogueFollower (Skyrim.esm 0x0750BA), its Follower alias, DismissFollower(0, 0) as the hall folk's own line
		auto* dh = RE::TESDataHandler::GetSingleton();
		auto* quest = dh ? dh->LookupForm<RE::TESQuest>(0x0750BA, "Skyrim.esm") : nullptr;
		RE::Actor* follower = nullptr;
		if (quest)
			for (auto* alias : quest->aliases)
				if (alias && alias->aliasName == "Follower")
					if (auto* ra = skyrim_cast<RE::BGSRefAlias*>(alias))
						if (auto* ref = ra->GetReference()) follower = ref->As<RE::Actor>();
		const auto* base = follower ? follower->GetActorBase() : nullptr;
		const auto* file = base ? base->GetFile(0) : nullptr;
		const bool  ours = file && std::find(kPlugins.begin(), kPlugins.end(), std::string_view(file->GetFilename())) != kPlugins.end();
		if (ours) {
			auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton();
			const auto handle = vm ? vm->GetObjectHandlePolicy()->GetHandleForObject(static_cast<RE::VMTypeID>(RE::TESQuest::FORMTYPE), quest) : 0;
			RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> cb;
			auto* args = RE::MakeFunctionArguments(static_cast<std::int32_t>(0), static_cast<std::int32_t>(0));
			if (vm && handle && vm->DispatchMethodCall(handle, "DialogueFollowerScript", "DismissFollower", args, cb)) ++followers;
			delete args;
			SKSE::log::info("GuildHall: Prepare to Uninstall dismisses {} ({:08X}){}", follower->GetDisplayFullName(), follower->GetFormID(), followers ? "" : " - not called");
		}
		SKSE::log::info("GuildHall: Prepare to Uninstall: {} trial(s) cancelled, {} follower(s) dismissed", trials, followers);
		return { trials, followers };
	}

	// Lux (in the DLL, as all of the mod's support for other mods is): with Lux.esp
	// loaded, the hall's cells are lit Lux's way, as Lux's own patches light a house: Jorrvaskr's cell on Lux_LTHouseBrighterLowSouth
	// with Lux_ISHouses, every lighting value inherited. All three cells, the basement and strongroom too (the basement
	// had stayed on the hall's own template, a brighter cellar under a darker hall). Lux's Show Sky and sky region are
	// not copied. No plugin, master or load order; without Lux nothing changes.
	void ApplyLux()
	{
		auto* dh = RE::TESDataHandler::GetSingleton();
		if (!dh || !dh->LookupModByName("Lux.esp")) return;
		constexpr RE::FormID kLuxTemplate = 0x3D58D5, kLuxImageSpace = 0x0924B3;   // Lux_LTHouseBrighterLowSouth, Lux_ISHouses
		auto* tmpl = dh->LookupForm<RE::BGSLightingTemplate>(kLuxTemplate, "Lux.esp");
		auto* isp = dh->LookupForm<RE::TESImageSpace>(kLuxImageSpace, "Lux.esp");
		if (!tmpl || !isp) {
			SKSE::log::warn("GuildHall: Lux is loaded but its house template ({:06X}) or image space ({:06X}) is not where it was: the hall keeps its own lighting", kLuxTemplate, kLuxImageSpace);
			return;
		}
		int n = 0;
		for (const auto id : { kMainCell, kStrongroomCell, kBasementCell }) {
			auto* cell = HallCell(dh, id);
			if (!cell) continue;
			cell->GetRuntimeData().lightingTemplate = tmpl;
			if (auto* li = cell->GetLighting()) {
				li->lightingTemplateInheritanceFlags.reset();
				li->lightingTemplateInheritanceFlags.set(static_cast<RE::INTERIOR_DATA::Inherit>(0x7FF));
			}
			if (auto* x = cell->extraList.GetByType<RE::ExtraCellImageSpace>()) x->imageSpace = isp;
			++n;
		}
		SKSE::log::info("GuildHall: Lux loaded: {} of the hall's cells on Lux's house template and image space", n);
	}

	// Helios (through the DLL, as Lux): Helios makes an interior's ambient follow the outside weather
	// and hour by giving the cell Show Sky + Use Sky Lighting and a sky region of its own interior weathers (its Luma Utility files,
	// one per vanilla cell). The hall takes the region Helios gives the nearest vanilla houses: the installed site's (its layout,
	// from sites.json: Helios_WeatherPineForest at Riverwood, Helios_WeatherSnow at site B by Solitude). The two cells with
	// windows only (Helios is for interiors with windows; the basement keeps a steady cellar light).
	void ApplyHelios()
	{
		auto* dh = RE::TESDataHandler::GetSingleton();
		if (!dh || !dh->LookupModByName("Helios.esp")) return;
		constexpr RE::FormID kPineForest = 0x000E4F;   // Helios_WeatherPineForest: a layout from before 2026-11-17 names none
		const RE::FormID     site = Hall::HeliosRegion();
		auto* region = site ? RE::TESForm::LookupByID<RE::TESRegion>(site) : dh->LookupForm<RE::TESRegion>(kPineForest, "Helios.esp");
		if (!region) {
			SKSE::log::warn("GuildHall: Helios is loaded but the site's region ({:08X}) is not where it was: the hall's ambient stays fixed", site ? site : kPineForest);
			return;
		}
		int n = 0;
		for (const auto id : { kMainCell, kStrongroomCell }) {
			auto* cell = HallCell(dh, id);
			if (!cell) continue;
			cell->cellFlags.set(RE::TESObjectCELL::Flag::kShowSky, RE::TESObjectCELL::Flag::kUseSkyLighting);
			if (auto* x = cell->extraList.GetByType<RE::ExtraCellSkyRegion>()) x->skyRegion = region;
			else if (auto* nx = RE::BSExtraData::Create<RE::ExtraCellSkyRegion>()) { nx->skyRegion = region; cell->extraList.Add(nx); }
			++n;
		}
		SKSE::log::info("GuildHall: Helios loaded: {} of the hall's cells follow the sky ({})", n, region->GetFormEditorID());
	}

	namespace
	{
		// each cell's switch for the lights that burn only with Light Limit Fix (the hall build's AGHall2VanillaLights* X markers, the
		// enable parent of those lights)
		constexpr std::array<RE::FormID, 3> kVanillaSwitches{ 0x007F26, 0x007F27, 0x007F28 };   // interior, basement, lookout
	}

	void VanillaLighting()
	{
		vanillaLighting = !LightLimitFixOn();
		auto* dh = RE::TESDataHandler::GetSingleton();
		if (!dh || !Loaded()) return;
		if (!vanillaLighting) {
			SKSE::log::info("GuildHall: Light Limit Fix found: every hall light burns");
			return;
		}
		// the ambient raised on the hall's own template, which only its cells use, or, where a cell is on another's (Lux's house
		// template, shared with every house), on that cell's own lighting, the template's values copied to it first
		std::vector<RE::BGSLightingTemplate*> seen;
		int cells = 0;
		for (const auto id : { kMainCell, kStrongroomCell, kBasementCell }) {
			auto* cell = HallCell(dh, id);
			auto* li = cell ? cell->GetLighting() : nullptr;
			if (!li) continue;
			auto* t = cell->GetRuntimeData().lightingTemplate;
			const bool inherits = t && li->lightingTemplateInheritanceFlags.all(RE::INTERIOR_DATA::Inherit::kAmbientColor);
			if (inherits && t->GetFile(0) && std::find(kPlugins.begin(), kPlugins.end(), std::string_view(t->GetFile(0)->GetFilename())) != kPlugins.end()) {
				if (std::find(seen.begin(), seen.end(), t) == seen.end()) {
					ambients.push_back({ &t->data.ambient, &t->directionalAmbientLightingColors, t->data.ambient, t->directionalAmbientLightingColors });
					seen.push_back(t);
				}
			} else {
				if (inherits) {
					li->ambient = t->data.ambient;
					li->directionalAmbientLightingColors = t->directionalAmbientLightingColors;
					li->lightingTemplateInheritanceFlags.reset(RE::INTERIOR_DATA::Inherit::kAmbientColor);
				}
				ambients.push_back({ &li->ambient, &li->directionalAmbientLightingColors, li->ambient, li->directionalAmbientLightingColors });
			}
			++cells;
		}
		ApplyAmbient(kNightAmbient);
		SKSE::log::info("GuildHall: no Light Limit Fix: only the hall's chandeliers burn; ambient x{} by day ({}:00-{}:00), x{} at night, in {} cells",
			kDayAmbient, static_cast<int>(kDayFrom), static_cast<int>(kDayTo), kNightAmbient, cells);
		// day or night, followed while the game runs: checked every few seconds on the game's own thread
		std::thread([] {
			for (;;) {
				std::this_thread::sleep_for(std::chrono::seconds(5));
				SKSE::GetTaskInterface()->AddTask([] {
					if (RE::PlayerCharacter::GetSingleton() && RE::PlayerCharacter::GetSingleton()->Is3DLoaded()) ApplyAmbient(WantedAmbient());
				});
			}
		}).detach();
	}

	void SwitchVanillaLights()
	{
		auto* dh = RE::TESDataHandler::GetSingleton();
		if (!dh || !Loaded()) return;
		int found = 0, changed = 0;
		for (const auto id : kVanillaSwitches)
			for (const auto name : kPlugins)
				if (auto* r = dh->LookupForm<RE::TESObjectREFR>(id, name)) {
					++found;
					if (vanillaLighting && !r->IsDisabled()) r->Disable(), ++changed;
					else if (!vanillaLighting && r->IsDisabled()) r->Enable(false), ++changed;
				}
		if (found != static_cast<int>(kVanillaSwitches.size()))
			SKSE::log::warn("GuildHall: {} of the hall's {} light switches found", found, kVanillaSwitches.size());
		if (changed) SKSE::log::info("GuildHall: the lights that need Light Limit Fix switched {}", vanillaLighting ? "off" : "on");
		if (vanillaLighting) ApplyAmbient(WantedAmbient());
	}

	// Which vanilla lists each of the hall folk's voices joins (the followers Ghrulek, Ylva and
	// Zhasim; the marriageable Margot, Nessa, Brynja and Ylva; Nessa a follower for her own quest). Vanilla's marriage and
	// combat lines test GetIsVoiceType against these lists, so a custom voice is in none of them until added: the lists
	// are the ones the vanilla lines recorded in these voices were picked by (plans/vanilla-follower-marriage-lines.md).
	// NOT the Orc/Rough/Neutral follower lists (2026-11-08): the followers' follower dialogue is the hall's own quest
	// (npcgen AGHallFollowerQuest), as Sofia's, Inigo's and Lucien's are, and those lists would show vanilla's same choices
	// beside ours wherever no dialogue mod ties them to exact voices. VoicesFollowerAll gates no vanilla line and stays.
	// Each NPC by its fixed actor base ID in the hall's plugin; its voice is read from the record, so the list gets the voice
	// the NPC really has, and nothing while that is still a vanilla one.
	void JoinVoiceLists()
	{
		auto* dh = RE::TESDataHandler::GetSingleton();
		if (!dh || !Loaded()) return;
		struct List { RE::FormID id; std::string_view file; };
		constexpr List FollowerAll{ 0x0C78E7, "Skyrim.esm" }, Favor{ 0x03B98A, "Skyrim.esm" }, Combatant{ 0x06D062, "Skyrim.esm" },
			MarriageNeutral{ 0x0CCD78, "Skyrim.esm" }, MarriageRough{ 0x0CCE4D, "Skyrim.esm" }, MarriageArrogant{ 0x0CCE3F, "Skyrim.esm" },
			MarriageAll{ 0x047A00, "Skyrim.esm" }, AdoptNeutral{ 0x004D8C, "HearthFires.esm" }, AdoptRough{ 0x017FDE, "HearthFires.esm" },
			AdoptArrogant{ 0x004D8B, "HearthFires.esm" }, AdoptAll{ 0x004D8A, "HearthFires.esm" };
		struct Who { const char* name; RE::FormID npc; std::vector<List> lists; };
		const std::array<Who, 6> folk{ {
			{ "Ghrulek", 0x803A, { FollowerAll, Favor, Combatant } },
			{ "Ylva", 0x803C, { FollowerAll, Favor, Combatant, MarriageRough, MarriageAll, AdoptRough, AdoptAll } },
			{ "Zhasim", 0x803E, { FollowerAll, Favor, Combatant } },
			{ "Margot", 0x8000, { MarriageNeutral, MarriageAll, AdoptNeutral, AdoptAll } },
			{ "Nessa", 0x800E, { MarriageNeutral, MarriageAll, AdoptNeutral, AdoptAll, FollowerAll, Favor, Combatant } },
			{ "Brynja", 0x8038, { MarriageArrogant, MarriageAll, AdoptArrogant, AdoptAll } },
		} };
		const auto ours = [](const RE::TESForm* a_form) {
			const auto* file = a_form ? a_form->GetFile(0) : nullptr;
			if (!file) return false;
			for (auto p : kPlugins)
				if (file->GetFilename() == p) return true;
			return false;
		};
		int joined = 0;
		for (const auto& w : folk) {
			auto* npc = HallForm<RE::TESNPC>(w.npc);
			auto* vt = npc ? npc->voiceType : nullptr;
			if (!vt || !ours(vt)) {
				SKSE::log::info("GuildHall: {} has no voice of the hall's own yet: vanilla's voice lists left as they are", w.name);
				continue;
			}
			for (const auto& l : w.lists) {
				auto* list = dh->LookupForm<RE::BGSListForm>(l.id, l.file);
				if (!list) {
					SKSE::log::warn("GuildHall: voice list {:06X} in {} not found: {} not joined to it", l.id, l.file, w.name);
					continue;
				}
				// into the list's own forms, as if a plugin listed the voice: NOT AddForm, whose script-added part a save
				// replaces with its own on load wherever the save has a change record for the list (measured on a test save,
				// 2026-11-07: VoicesFollowerAll has one, so Ylva's voice vanished from it and the followers lost "Follow me";
				// VoicesFollowerRough has none and kept it)
				if (!list->HasForm(vt)) { list->forms.push_back(vt); ++joined; }
			}
		}
		SKSE::log::info("GuildHall: the hall folk's voices joined to {} of vanilla's voice lists", joined);
	}
}
