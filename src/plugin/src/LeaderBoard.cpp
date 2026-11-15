// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "LeaderBoard.h"

#include "ControlsGuard.h"
#include "Counter.h"
#include "Guild.h"
#include "GuildHall.h"
#include "Loc.h"
#include "Party.h"
#include "UiHost.h"

#include <filesystem>
#include <fstream>

namespace AG::LeaderBoard
{
	namespace
	{
		constexpr std::string_view kModel = "adventurersguild\\leaderboard\\agleaderboard";   // known by its model, as the Guild Board
		constexpr RE::FormID kPassedGlobal = 0xFDD;                                          // AG_LB_PassedRival, AdventurersGuild.esp
		constexpr RE::FormID kRenownGlobal = 0xFDE;                                          // AG_LB_PartyRenownGlobal: the player's best party's Renown
		constexpr RE::FormID kPlaceGlobal = 0xFDF;                                           // AG_LB_PlayerPlaceGlobal: its place on the board, 0 with none

		UiHost::Handle              g_view{ 0 };
		std::atomic<bool>           g_open{ false };

		bool Valid() { return g_view && UiHost::Valid(g_view); }

		// ---- the Guild's other parties (names, years, scores and endings; the scores spaced along
		// the player's Renown, about 8.4 an hour, so the Frostbitten falls near the end of a 100-hour playthrough) ----
		struct Old { std::string name; int from, to; float renown; std::string note; };
		std::vector<Old> OldParties()
		{
			const auto war = Loc::T("$AG_LB_NoteWar", "Disbanded (Great War)");
			const auto civil = Loc::T("$AG_LB_NoteCivilWar", "Disbanded (Civil War)");
			const auto gone = Loc::T("$AG_LB_NoteDisbanded", "disbanded");
			return { { Loc::T("$AG_LB_Frostbitten", "The Frostbitten"), 172, 174, 698.0f, war },
			         { Loc::T("$AG_LB_HorkerCompany", "The Horker Company"), 172, 174, 587.0f, war },
			         { Loc::T("$AG_LB_ColdHearth", "The Cold Hearth"), 171, 174, 433.0f, war },
			         { Loc::T("$AG_LB_BaneOfTheRift", "Bane of the Rift"), 196, 200, 341.0f, gone },
			         { Loc::T("$AG_LB_StendarrsMercenaries", "Stendarr's Mercenaries"), 193, 201, 262.0f, civil },
			         { Loc::T("$AG_LB_CurvedSwords", "Curved Swords"), 197, 199, 193.0f, gone },
			         { Loc::T("$AG_LB_DraugrBait", "Draugr Bait"), 199, 200, 157.0f, Loc::T("$AG_LB_NoteMIA", "MIA") },
			         { Loc::T("$AG_LB_WinterholdFour", "The Winterhold Four"), 197, 201, 129.0f, civil },
			         { Loc::T("$AG_LB_SecondDawn", "Second Dawn"), 200, 201, 96.0f, Loc::T("$AG_LB_NoteKIA", "KIA") },
			         { Loc::T("$AG_LB_ThreeTankards", "The Three Tankards"), 199, 200, 58.0f, gone },
			         { Loc::T("$AG_LB_MadMudcrabs", "The Mad Mudcrabs"), 200, 201, 23.0f, gone } };
		}

		// ---- the parties still climbing: guild.json "leaderBoard". Paced by the player's own party, not the calendar:
		// none moves until the player has registered a party, so none can be on top before the player
		// starts; each then gains a share of what the player's party gains, up to a cap below the top three. The Golden
		// Hand's share is set so the player catches him at exactly "catchAt" Renown, whatever their pace; the two unseen
		// parties climb more slowly ----
		struct Pace { float start, share, cap; };
		struct Unseen { std::string name, leader; int since; Pace pace; };
		// the share that has a party starting at a_start caught by the player's party at exactly a_at Renown
		constexpr float CatchShare(float a_start, float a_at) { return (a_at - a_start) / a_at; }
		struct Config
		{
			Pace              rival{ 121.0f, CatchShare(121.0f, 300.0f), 419.0f };
			std::vector<Pace> unseen{ { 289.0f, 0.25f, 407.0f }, { 143.0f, 0.2f, 331.0f } };
		};
		std::vector<Unseen> UnseenParties(const std::vector<Pace>& a_pace)
		{
			std::vector<Unseen> u{ { Loc::T("$AG_LB_GreyLanterns", "The Grey Lanterns"), Loc::T("$AG_LB_GreyLanternsLeader", "Sigrun Halfhand"), 196, {} },
			                       { Loc::T("$AG_LB_Stormbringers", "Stormbringers"), Loc::T("$AG_LB_StormbringersLeader", "J'zahri"), 198, {} } };
			for (std::size_t i = 0; i < u.size(); ++i) u[i].pace = i < a_pace.size() ? a_pace[i] : Pace{ 0.0f, 0.0f, 0.0f };
			return u;
		}
		float Paced(const Pace& a_p, float a_player) { return std::floor(std::min(a_p.cap, a_p.start + a_p.share * std::max(0.0f, a_player))); }

		std::mutex g_lock;
		Config     g_cfg;
		// co-save
		bool  g_passed{ false };
		int   g_endHow{ 0 };       // 0 still on the board; 1 he fell, 2 he left Skyrim (both after his treachery); 3 he died before his quest
		float g_endDay{ -1.0f };
		float g_endScore{ -1.0f }; // his Renown frozen the day he was done (-1: not taken yet, a save from before it was kept)

		// the Renown of the player's best party, active or disbanded (0 with none)
		float PlayerRenown(const nlohmann::json& a_standings)
		{
			float best = 0.0f;
			for (auto& p : a_standings) best = std::max(best, p.value("renown", 0.0f));
			return best;
		}

		// caller holds g_lock. The Golden Hand's Renown: paced by the player's party, frozen the day he is done
		float RivalScore(float a_player)
		{
			if (g_endHow && g_endScore >= 0.0f) return g_endScore;
			const float s = Paced(g_cfg.rival, a_player);
			if (g_endHow) g_endScore = s;
			return s;
		}

		// ---- the calendar ----
		constexpr std::array<int, 12> kMonthDays{ 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 };
		int DayOfYear(RE::Calendar* a_cal)
		{
			int n = 0;
			for (std::uint32_t m = 0; m < a_cal->GetMonth() && m < 12; ++m) n += kMonthDays[m];
			return n + static_cast<int>(a_cal->GetDay()) - 1;
		}
		int YearOf(float a_day)  // the year (of the Fourth Era) a day passed fell in
		{
			auto* cal = RE::Calendar::GetSingleton();
			if (!cal) return 201;
			const int   y = static_cast<int>(cal->GetYear());
			const float back = Guild::Day() - a_day;
			const int   doy = DayOfYear(cal);
			if (back <= static_cast<float>(doy)) return y;
			return y - 1 - static_cast<int>((back - static_cast<float>(doy) - 1.0f) / 365.0f);
		}
		std::string Ord(int a_n)
		{
			const int t = a_n % 100;
			const char* sfx = (t >= 11 && t <= 13) ? "th" : a_n % 10 == 1 ? "st" : a_n % 10 == 2 ? "nd" : a_n % 10 == 3 ? "rd" : "th";
			return Loc::F("$AG_LB_Ordinal", "{0}{1}", a_n, sfx);
		}
		std::string MonthName(std::uint32_t a_m)
		{
			switch (a_m) {
			case 0: return Loc::T("$AG_LB_Month0", "Morning Star");
			case 1: return Loc::T("$AG_LB_Month1", "Sun's Dawn");
			case 2: return Loc::T("$AG_LB_Month2", "First Seed");
			case 3: return Loc::T("$AG_LB_Month3", "Rain's Hand");
			case 4: return Loc::T("$AG_LB_Month4", "Second Seed");
			case 5: return Loc::T("$AG_LB_Month5", "Midyear");
			case 6: return Loc::T("$AG_LB_Month6", "Sun's Height");
			case 7: return Loc::T("$AG_LB_Month7", "Last Seed");
			case 8: return Loc::T("$AG_LB_Month8", "Hearthfire");
			case 9: return Loc::T("$AG_LB_Month9", "Frostfall");
			case 10: return Loc::T("$AG_LB_Month10", "Sun's Dusk");
			default: return Loc::T("$AG_LB_Month11", "Evening Star");
			}
		}

		// ---- the rows ----
		struct Row
		{
			std::string name, leader, note;
			int         from{ 0 }, to{ 0 };
			float       renown{ 0 };
			bool        gone{ false }, yours{ false }, rival{ false }, struck{ false };
		};
		std::vector<Row> Rows(const nlohmann::json& a_standings)   // a_standings: Party::Standings()
		{
			const float today = Guild::Day();
			std::vector<Row> rows;
			auto* player = RE::PlayerCharacter::GetSingleton();
			const std::string you = player ? player->GetDisplayFullName() : std::string();
			const auto& standings = a_standings;
			const float mine = PlayerRenown(standings);
			for (auto& p : standings) {
				Row r; r.name = p.value("name", std::string()); r.yours = true;
				r.from = YearOf(p.value("founded", today)); r.renown = p.value("renown", 0.0f);
				const float dis = p.value("disbanded", -1.0f);
				if (dis >= 0.0f) { r.gone = true; r.to = YearOf(dis); r.note = Loc::T("$AG_LB_NoteDisbanded", "disbanded"); }
				else r.leader = you;
				rows.push_back(std::move(r));
			}
			for (auto& o : OldParties()) rows.push_back({ o.name, "", o.note, o.from, o.to, o.renown, true, false, false, false });
			std::lock_guard l(g_lock);
			for (auto& u : UnseenParties(g_cfg.unseen)) rows.push_back({ u.name, u.leader, "", u.since, 0, Paced(u.pace, mine), false, false, false, false });
			Row r; r.rival = true; r.name = Loc::T("$AG_LB_GoldenHand", "The Golden Hand"); r.from = 200;
			r.renown = RivalScore(mine);
			if (g_endHow) {
				// after his treachery the Guild strikes his party out, name and Renown, where it stands;
				// dead before his quest it is simply disbanded. Either way it stays on the sheet and sinks as others pass it
				r.gone = true; r.to = YearOf(g_endDay);
				r.struck = g_endHow != 3;
				r.note = r.struck ? Loc::T("$AG_LB_NoteDishonored", "dishonored") : Loc::T("$AG_LB_NoteDisbanded", "disbanded");
			} else r.leader = Loc::T("$AG_LB_GoldenHandLeader", "Caralion of Cloudrest");
			rows.push_back(std::move(r));
			std::ranges::stable_sort(rows, [](const Row& a, const Row& b) { return std::floor(a.renown) > std::floor(b.renown); });
			return rows;
		}
		std::vector<Row> Rows() { return Rows(Party::Standings()); }

		// the place of the player's active party (a_rival false) or of the Golden Hand while he is on the board: 0 with none
		int PlaceOf(const std::vector<Row>& a_rows, bool a_rival)
		{
			for (std::size_t i = 0; i < a_rows.size(); ++i)
				if (a_rival ? (a_rows[i].rival && !a_rows[i].gone) : (a_rows[i].yours && !a_rows[i].gone)) return static_cast<int>(i) + 1;
			return 0;
		}
		// the place of the player's best party, active or disbanded, the one PlayerRenown reads (the rows are ranked, so it is
		// the first of theirs): 0 with none
		int BestPlaceOf(const std::vector<Row>& a_rows)
		{
			for (std::size_t i = 0; i < a_rows.size(); ++i)
				if (a_rows[i].yours) return static_cast<int>(i) + 1;
			return 0;
		}

		nlohmann::json Data(const std::vector<Row>& a_rows)
		{
			nlohmann::json j;
			auto& out = j["rows"] = nlohmann::json::array();
			for (auto& r : a_rows) {
				nlohmann::json x{ { "name", r.name }, { "renown", static_cast<int>(std::floor(r.renown)) }, { "from", r.from }, { "gone", r.gone }, { "yours", r.yours } };
				if (r.gone) { x["to"] = r.to; x["note"] = r.note; }
				else x["leader"] = r.leader;
				if (r.struck) x["struck"] = true;
				out.push_back(std::move(x));
			}
			j["yours"] = PlaceOf(a_rows, false);
			if (auto* cal = RE::Calendar::GetSingleton())
				j["asOf"] = Loc::F("$AG_LB_AsOf", "as it stood on the {0} of {1}, 4E {2} · kept by {3}", Ord(static_cast<int>(cal->GetDay())),
				                   MonthName(cal->GetMonth()), cal->GetYear(), Loc::T("$AG_LB_Keeper", "M. Andalen"));
			return j;
		}
		nlohmann::json Data() { return Data(Rows()); }

		void Refresh(const std::vector<Row>& a_rows)
		{
			if (g_open.load() && Valid()) UiHost::Js(g_view, "window.agSetData(" + Data(a_rows).dump() + ")");
		}
		void Refresh()
		{
			if (g_open.load() && Valid()) Refresh(Rows());
		}

		void SendModEvent(const char* a_name, const std::string& a_str, float a_num)
		{
			SKSE::ModCallbackEvent ev{ a_name, a_str.c_str(), a_num, RE::PlayerCharacter::GetSingleton() };
			if (auto* src = SKSE::GetModCallbackEventSource()) src->SendEvent(&ev);
		}

		void SetGlobal(RE::FormID a_id, float a_value)
		{
			auto* dh = RE::TESDataHandler::GetSingleton();
			if (auto* g = dh ? dh->LookupForm<RE::TESGlobal>(a_id, "AdventurersGuild.esp") : nullptr) g->value = a_value;
		}

		// ---- the board's story pieces: the hall places two NIFs on the board's own spot, and
		// they are shown when the story calls for them, as the Guild Board's day arrangements are: a fresh slip pinned up
		// once the player has a party (AGLeaderSlip.nif), the Golden Hand's row struck through once Caralion is dishonored
		// (AGLeaderStrike.nif). Known by their models; nothing stored in the save: the state decides each time ----
		constexpr std::string_view kSlipModel = "adventurersguild\\leaderboard\\agleaderslip";
		constexpr std::string_view kStrikeModel = "adventurersguild\\leaderboard\\agleaderstrike";

		// whether a form's model path holds a_needle (written lower case, with backslashes), blind to case and slashes and
		// without copying the path: the load sink asks it of every Activator the game loads
		bool ModelHas(RE::TESBoundObject* a_base, std::string_view a_needle)
		{
			auto* model = a_base ? a_base->As<RE::TESModel>() : nullptr;
			const char* path = model ? model->GetModel() : nullptr;
			if (!path) return false;
			const std::string_view p(path);
			auto norm = [](char c) { return c == '/' ? '\\' : static_cast<char>(std::tolower(static_cast<unsigned char>(c))); };
			for (std::size_t i = 0; i + a_needle.size() <= p.size(); ++i) {
				std::size_t k = 0;
				while (k < a_needle.size() && norm(p[i + k]) == a_needle[k]) ++k;
				if (k == a_needle.size()) return true;
			}
			return false;
		}
		bool IsBoard(RE::TESObjectREFR* a_ref)
		{
			auto* base = a_ref ? a_ref->GetBaseObject() : nullptr;
			return base && base->Is(RE::FormType::Activator) && ModelHas(base, kModel);
		}
		int PieceOf(RE::TESObjectREFR* a_ref)  // 1 the slip, 2 the strike, 0 neither (the hall makes them statics)
		{
			auto* base = a_ref ? a_ref->GetBaseObject() : nullptr;
			if (!base || base->Is(RE::FormType::Activator)) return 0;
			return ModelHas(base, kSlipModel) ? 1 : ModelHas(base, kStrikeModel) ? 2 : 0;
		}

		// Game thread only (the load sink's task, Check, EndRival's task): the pieces found in the board's cell when its 3D
		// last loaded. Kept so the half-minute check touches two references, not every one in the player's cell
		std::vector<std::pair<RE::FormID, int>> g_pieces;

		void SetPieces(bool a_slip)  // a_slip: the player has a party (Party::Standings() not empty)
		{
			if (g_pieces.empty() || Guild::Dormant()) return;
			bool strike;
			{
				std::lock_guard l(g_lock);
				strike = g_endHow == 1 || g_endHow == 2;
			}
			for (auto& [id, k] : g_pieces) {
				auto* ref = RE::TESForm::LookupByID<RE::TESObjectREFR>(id);
				if (!ref || ref->IsDeleted()) continue;
				const bool want = k == 1 ? a_slip : strike;
				if (want && ref->IsDisabled()) ref->Enable(false);
				else if (!want && !ref->IsDisabled()) ref->Disable();
			}
		}
		// the board's cell has loaded: find its pieces (a hidden piece loads no 3D of its own, so the board's load is the cue),
		// then show or hide each before the player sees the wall
		void ScanPieces(RE::TESObjectCELL* a_cell)
		{
			if (!a_cell) return;
			g_pieces.clear();
			a_cell->ForEachReference([](RE::TESObjectREFR* a_ref) {
				if (const int k = PieceOf(a_ref)) g_pieces.emplace_back(a_ref->GetFormID(), k);
				return RE::BSContainer::ForEachResult::kContinue;
			});
			SetPieces(!Party::Standings().empty());
		}

		class LoadSink : public RE::BSTEventSink<RE::TESObjectLoadedEvent>
		{
		public:
			static LoadSink* Get()
			{
				static LoadSink s;
				return &s;
			}
			RE::BSEventNotifyControl ProcessEvent(const RE::TESObjectLoadedEvent* a_e, RE::BSTEventSource<RE::TESObjectLoadedEvent>*) override
			{
				if (!a_e || !a_e->loaded || !IsBoard(RE::TESForm::LookupByID<RE::TESObjectREFR>(a_e->formID))) return RE::BSEventNotifyControl::kContinue;
				const auto id = a_e->formID;
				SKSE::GetTaskInterface()->AddTask([id] {   // (enabling and disabling from inside the load event: deferred)
					if (auto* ref = RE::TESForm::LookupByID<RE::TESObjectREFR>(id)) ScanPieces(ref->GetParentCell());
				});
				return RE::BSEventNotifyControl::kContinue;
			}
		};

		// The standings for the NPCs' lines (dialogue conditions read globals, not natives), the board's story pieces, and
		// the day the player's party passed him. One look at the standings and one ranking serve all of it
		void Check()
		{
			if (Guild::Dormant()) return;
			const auto standings = Party::Standings();
			const auto rows = Rows(standings);
			SetGlobal(kRenownGlobal, std::floor(PlayerRenown(standings)));
			SetGlobal(kPlaceGlobal, static_cast<float>(BestPlaceOf(rows)));
			SetPieces(!standings.empty());
			bool passedNow = false;
			{
				std::lock_guard l(g_lock);
				passedNow = !g_passed && !g_endHow;
			}
			if (passedNow) {
				const int mine = PlaceOf(rows, false), his = PlaceOf(rows, true);
				if (mine > 0 && his > 0 && mine < his) {
					{
						std::lock_guard l(g_lock);
						g_passed = true;
					}
					SetGlobal(kPassedGlobal, 1.0f);
					SKSE::log::info("LeaderBoard: the player's party ({}) passed the Golden Hand ({})", mine, his);
					SendModEvent("AG_LeaderBoard_PassedRival", "", static_cast<float>(mine));
				}
			}
			Refresh(rows);
		}

		void OnClose(const std::string&) { Close(); }  // on the game thread (UiHost)

		std::atomic<bool> g_pending{ false };  // asked for in a conversation: opens as the Dialogue Menu closes
		class MenuSink : public RE::BSTEventSink<RE::MenuOpenCloseEvent>
		{
		public:
			static MenuSink* Get()
			{
				static MenuSink s;
				return &s;
			}
			RE::BSEventNotifyControl ProcessEvent(const RE::MenuOpenCloseEvent* a_e, RE::BSTEventSource<RE::MenuOpenCloseEvent>*) override
			{
				if (a_e && !a_e->opening && a_e->menuName == RE::DialogueMenu::MENU_NAME && g_pending.exchange(false))
					SKSE::GetTaskInterface()->AddTask([] { Open(); });
				return RE::BSEventNotifyControl::kContinue;
			}
		};

		class ActivateSink : public RE::BSTEventSink<RE::TESActivateEvent>
		{
		public:
			static ActivateSink* Get()
			{
				static ActivateSink s;
				return &s;
			}
			RE::BSEventNotifyControl ProcessEvent(const RE::TESActivateEvent* a_e, RE::BSTEventSource<RE::TESActivateEvent>*) override
			{
				if (!a_e || !a_e->actionRef || !a_e->actionRef->IsPlayerRef() || !IsBoard(a_e->objectActivated.get())) return RE::BSEventNotifyControl::kContinue;
				SKSE::GetTaskInterface()->AddTask([] { Open(); });
				return RE::BSEventNotifyControl::kContinue;
			}
		};
	}

	void LoadConfig()
	{
		Config c;
		try {
			std::ifstream f("Data/SKSE/Plugins/AdventurersGuild/guild.json");
			if (f) {
				auto j = nlohmann::json::parse(f, nullptr, true, true);
				if (j.contains("leaderBoard")) {
					const auto& b = j.at("leaderBoard");
					auto pace = [](const nlohmann::json& a_j, Pace a_p) {
						a_p.start = std::max(0.0f, a_j.value("start", a_p.start));
						a_p.cap = std::max(a_p.start, a_j.value("cap", a_p.cap));
						if (a_j.contains("catchAt")) {   // the player's party catches it at exactly this Renown
							const float at = std::max(a_p.start + 1.0f, a_j.at("catchAt").get<float>());
							a_p.share = CatchShare(a_p.start, at);
						} else a_p.share = std::clamp(a_j.value("share", a_p.share), 0.0f, 0.99f);
						return a_p;
					};
					if (b.contains("rival")) c.rival = pace(b.at("rival"), c.rival);
					if (b.contains("unseen") && b.at("unseen").is_array())
						for (std::size_t i = 0; i < b.at("unseen").size() && i < c.unseen.size(); ++i) c.unseen[i] = pace(b.at("unseen")[i], c.unseen[i]);
				}
			}
		} catch (const std::exception& e) {
			SKSE::log::error("LeaderBoard: guild.json: {}", e.what());
		}
		std::lock_guard l(g_lock);
		g_cfg = std::move(c);
	}

	void Install()
	{
		if (auto* events = RE::ScriptEventSourceHolder::GetSingleton()) {
			events->AddEventSink<RE::TESActivateEvent>(ActivateSink::Get());
			events->AddEventSink<RE::TESObjectLoadedEvent>(LoadSink::Get());
		}
		if (auto* ui = RE::UI::GetSingleton()) ui->AddEventSink<RE::MenuOpenCloseEvent>(MenuSink::Get());
		g_view = UiHost::Create({ "leaderboard", "leaderboard.html", UiHost::Layer::kPanel, false, false });
		if (!g_view) return;  // UiHost says why in the log
		UiHost::Listen(g_view, "agClose", OnClose);
		UiHost::OnHostClosed(g_view, [] { Close(); });
	}

	void Register()
	{
		std::thread([] {
			for (;;) {
				std::this_thread::sleep_for(std::chrono::seconds(30));
				SKSE::GetTaskInterface()->AddTask([] { Check(); });
			}
		}).detach();
	}

	void Open()
	{
		if (g_open.load() || Guild::Dormant()) return;
		if (!Valid()) {
			RE::SendHUDMessage::ShowHUDMessage(Loc::T("$AG_Hud_LeaderBoardNoPrisma", "The leader board needs PrismaUI to be read.").c_str());
			return;
		}
		g_open = true;
		UiHost::Js(g_view, "window.agStrings(" + Loc::UiStrings().dump() + ")");
		UiHost::Js(g_view, "window.agOpened && window.agOpened()");
		UiHost::Js(g_view, REL::Module::IsVR() ? "window.agFlat && window.agFlat(false)" : "window.agFlat && window.agFlat(true)");
		UiHost::Js(g_view, GuildHall::Loaded() ? "window.agHall && window.agHall(true)" : "window.agHall && window.agHall(false)");
		Check();   // the standings as of now, then the data
		SKSE::GetTaskInterface()->AddTask([] { Invoke(std::format("window.agInputMode({})", Counter::PadMode())); });
		if (!UiHost::ManagesControls()) {  // Prisma UI only: Magelight UI suspends the player's controls itself
			ControlsGuard::Shown();
			ControlsGuard::Mask();
		}
		UiHost::Show(g_view);
		if (!UiHost::Focus(g_view)) {  // another mod's page has the input
			Close();
			return;
		}
		SKSE::log::info("LeaderBoard: opened");
	}

	void OpenAfterDialogue()
	{
		g_pending = true;
		// if the Dialogue Menu is somehow already gone, open right away (as Counter::OpenAfterDialogue)
		SKSE::GetTaskInterface()->AddTask([] {
			auto* ui = RE::UI::GetSingleton();
			if (ui && !ui->IsMenuOpen(RE::DialogueMenu::MENU_NAME) && g_pending.exchange(false)) Open();
		});
	}

	void Close()
	{
		if (!g_open.exchange(false) || !Valid()) return;
		UiHost::Unfocus(g_view);
		UiHost::Hide(g_view);
		if (!UiHost::ManagesControls()) {
			ControlsGuard::Unmask();
			ControlsGuard::Hidden();
		}
	}

	bool IsOpen() { return g_open.load(); }

	void Invoke(const std::string& a_script)
	{
		if (g_open.load() && Valid()) UiHost::Js(g_view, a_script);
	}

	int Rank() { return PlaceOf(Rows(), false); }
	int RivalRank() { return PlaceOf(Rows(), true); }

	void EndRival(int a_how)
	{
		if (a_how < 1 || a_how > 3) return;
		const float mine = PlayerRenown(Party::Standings());
		float       at;
		{
			std::lock_guard l(g_lock);
			if (g_endHow) return;
			at = g_endScore = Paced(g_cfg.rival, mine);
			g_endHow = a_how; g_endDay = Guild::Day();
		}
		SKSE::log::info("LeaderBoard: the Golden Hand is done ({}) at {}", a_how == 1 ? "he fell" : a_how == 2 ? "he left Skyrim" : "he died before his quest", at);
		SKSE::GetTaskInterface()->AddTask([] { SetPieces(!Party::Standings().empty()); });   // (a native call: the pieces are touched on the game's thread)
		Refresh();
	}

	std::string Dump()
	{
		nlohmann::json j = Data();
		std::lock_guard l(g_lock);
		j["rival"] = { { "passed", g_passed }, { "endHow", g_endHow }, { "endDay", g_endDay }, { "endScore", g_endScore } };
		return j.dump(1);
	}

	nlohmann::json Save()
	{
		std::lock_guard l(g_lock);
		return { { "passed", g_passed }, { "endHow", g_endHow }, { "endDay", g_endDay }, { "endScore", g_endScore } };
	}

	void Load(const nlohmann::json& a_j)
	{
		std::lock_guard l(g_lock);
		g_passed = a_j.value("passed", false);
		g_endHow = a_j.value("endHow", 0);
		g_endDay = a_j.value("endDay", -1.0f);
		g_endScore = a_j.value("endScore", -1.0f);   // (missing: taken at the next look, from the player's Renown then)
	}

	void Revert()
	{
		std::lock_guard l(g_lock);
		g_passed = false; g_endHow = 0; g_endDay = -1.0f; g_endScore = -1.0f;
	}
}
