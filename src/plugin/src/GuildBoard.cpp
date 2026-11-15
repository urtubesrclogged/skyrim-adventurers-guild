// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "GuildBoard.h"

#include "BountyWatch.h"
#include "ControlsGuard.h"
#include "Counter.h"
#include "Guild.h"
#include "GuildHall.h"
#include "Loc.h"
#include "MissiveWatch.h"
#include "NoticeWatch.h"
#include "RankCore.h"
#include "UiHost.h"

#include <filesystem>

namespace AG::GuildBoard
{
	namespace
	{
		// the board is known by its model, not a FormID: the hall's builds give the record a new ID when it changes kind,
		// and the model is what makes it the Guild Board wherever it is placed
		constexpr std::string_view kModel = "adventurersguild\\board\\agguildboard";

		UiHost::Handle              g_view{ 0 };
		std::atomic<bool>           g_open{ false };

		bool Valid() { return g_view && UiHost::Valid(g_view); }

		std::string Esc(std::string_view a_s)
		{
			std::string out;
			for (unsigned char c : a_s) {
				switch (c) {
				case '"': out += "\\\""; break;
				case '\\': out += "\\\\"; break;
				case '\n': out += "\\n"; break;
				case '\r': break;
				default: out += static_cast<char>(c);
				}
			}
			return out;
		}

		void Status(const std::string& a_msg)
		{
			if (Valid()) UiHost::Js(g_view, std::format("window.agStatus(\"{}\")", Esc(a_msg)));
		}

		void Refresh()
		{
			if (!g_open.load() || !Valid()) return;
			nlohmann::json data;
			data["registered"] = Guild::Registered();
			data["regHallOnly"] = GuildHall::OnlyAtHall(GuildHall::Only::kRegistration);  // who signs the unregistered up: the hall alone, or the inns too
			data["letter"] = Guild::Registered() ? LetterStr(Guild::Rank()) : std::string("-");
			GuildHall::CounterData(data);
			data["notices"] = NoticeWatch::Active() ? NoticeWatch::Postings() : nlohmann::json(nullptr);
			data["boards"] = { { "missives", MissiveWatch::Active() }, { "notices", NoticeWatch::Active() } };
			UiHost::Js(g_view, "window.agSetData(" + data.dump() + ")");
		}

		// calls from the page arrive on the game thread (UiHost)
		void OnClose(const std::string&) { Close(); }

		void OnAction(const std::string& arg)
		{
			{
				if (arg.starts_with("details:")) {  // read-only: the note's text to the page
					const auto id = arg.substr(8);
					const auto details = BountyWatch::Owns(id) ? BountyWatch::Details(id) : NoticeWatch::Owns(id) ? NoticeWatch::Details(id) : MissiveWatch::Details(id);
					if (Valid()) UiHost::Js(g_view, "window.agDetails(" + details.dump() + ")");
					return;
				}
				if (arg == "newbounty") {  // "A new bounty?", as at the hall counter: Papyrus answers later
					BountyWatch::NewBounty([](const std::string& a_msg) {
						SKSE::log::debug("GuildBoard: action 'newbounty' -> '{}'", a_msg);
						Refresh();
						Status(a_msg);
					});
					return;
				}
				if (!arg.starts_with("take:")) {
					SKSE::log::debug("GuildBoard: action '{}' is not one the DLL knows", arg);
					return;
				}
				const auto id = arg.substr(5);
				const auto msg = BountyWatch::Owns(id) ? BountyWatch::Accept(id) : NoticeWatch::Owns(id) ? NoticeWatch::Accept(id) : MissiveWatch::Accept(id);
				SKSE::log::debug("GuildBoard: action '{}' -> '{}'", arg, msg);
				Refresh();
				Status(msg);
			}
		}

		bool IsBoard(RE::TESObjectREFR* a_ref)
		{
			auto* base = a_ref ? a_ref->GetBaseObject() : nullptr;
			auto* model = base ? base->As<RE::TESModel>() : nullptr;
			const char* path = model ? model->GetModel() : nullptr;
			if (!path || !base->Is(RE::FormType::Activator)) return false;
			std::string p(path);
			std::ranges::transform(p, p.begin(), [](unsigned char c) { return static_cast<char>(c == '/' ? '\\' : std::tolower(c)); });
			return p.find(kModel) != std::string::npos;
		}

		// The board's postings rotate a day at a time: the hall places its
		// three arrangements on one spot (AGGuildBoard.nif, _B, _C) and the day's one is enabled when the board loads. The
		// rotation was a Papyrus script on a marker until hall2ay, whose properties a save kept: an older save's named board
		// references a later build had dropped, and the live boards stopped rotating. Here nothing is stored: the day picks.
		int Variant(RE::TESObjectREFR* a_ref)  // 0, 1, 2 for A, B, C; -1 if not a board
		{
			if (!IsBoard(a_ref)) return -1;
			std::string p(a_ref->GetBaseObject()->As<RE::TESModel>()->GetModel());
			std::ranges::transform(p, p.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
			if (p.ends_with("_b.nif")) return 1;
			if (p.ends_with("_c.nif")) return 2;
			return 0;
		}

		void Rotate(RE::TESObjectCELL* a_cell)
		{
			auto* cal = RE::Calendar::GetSingleton();
			if (!a_cell || !cal || Guild::Dormant()) return;
			std::array<RE::TESObjectREFR*, 3> boards{};
			a_cell->ForEachReference([&](RE::TESObjectREFR* a_ref) {
				if (const auto v = Variant(a_ref); v >= 0 && !a_ref->IsDeleted()) boards[v] = a_ref;
				return RE::BSContainer::ForEachResult::kContinue;
			});
			if (!boards[0] || !boards[1] || !boards[2]) return;  // a hall without all three: left as placed
			const auto today = static_cast<std::size_t>(static_cast<long long>(cal->GetDaysPassed()) % 3);
			for (std::size_t v = 0; v < boards.size(); ++v) {
				if (v == today && boards[v]->IsDisabled()) boards[v]->Enable(false);
				else if (v != today && !boards[v]->IsDisabled()) boards[v]->Disable();
			}
			SKSE::log::info("GuildBoard: day {}, postings {}", static_cast<long long>(cal->GetDaysPassed()), "ABC"[today]);
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
				if (!a_e || !a_e->loaded) return RE::BSEventNotifyControl::kContinue;
				if (Variant(RE::TESForm::LookupByID<RE::TESObjectREFR>(a_e->formID)) < 0) return RE::BSEventNotifyControl::kContinue;
				const auto id = a_e->formID;
				SKSE::GetTaskInterface()->AddTask([id] {   // (enabling and disabling from inside the load event: deferred)
					if (auto* ref = RE::TESForm::LookupByID<RE::TESObjectREFR>(id)) Rotate(ref->GetParentCell());
				});
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

	void Install()
	{
		if (auto* events = RE::ScriptEventSourceHolder::GetSingleton()) {
			events->AddEventSink<RE::TESActivateEvent>(ActivateSink::Get());
			events->AddEventSink<RE::TESObjectLoadedEvent>(LoadSink::Get());  // the postings' daily rotation, with or without PrismaUI
		}
		g_view = UiHost::Create({ "board", "board.html", UiHost::Layer::kPanel, false, true });
		if (!g_view) return;  // UiHost says why in the log
		UiHost::Listen(g_view, "agClose", OnClose);
		UiHost::Listen(g_view, "agAction", OnAction);
		UiHost::OnHostClosed(g_view, [] { Close(); });
	}

	void Open()
	{
		if (g_open.load() || Guild::Dormant()) return;  // prepared for uninstall: the board says nothing
		if (!Valid()) {
			RE::SendHUDMessage::ShowHUDMessage(Loc::T("$AG_Hud_BoardNoPrisma", "The Guild Board needs PrismaUI to be read.").c_str());
			return;
		}
		g_open = true;
		NoticeWatch::Post();  // newly allowed notices go up here as they would at any board
		UiHost::Js(g_view, "window.agStrings(" + Loc::UiStrings().dump() + ")");
		UiHost::Js(g_view, "window.agOpened && window.agOpened()");  // the filters start over, as at the counter
		UiHost::Js(g_view, REL::Module::IsVR() ? "window.agFlat && window.agFlat(false)" : "window.agFlat && window.agFlat(true)");
		Refresh();
		// after the data (tasks run in order, as the counter): controller users open with the first button highlighted
		SKSE::GetTaskInterface()->AddTask([] { Invoke(std::format("window.agInputMode({})", Counter::PadMode())); });
		if (!UiHost::ManagesControls()) {  // Prisma UI only: Magelight UI suspends the player's controls itself
			ControlsGuard::Shown();
			ControlsGuard::Mask();  // VR: a trigger pull on the board must not ready the weapon (as at the counter)
		}
		UiHost::Show(g_view);
		if (!UiHost::Focus(g_view)) {  // another mod's page has the input
			Close();
			return;
		}
		SKSE::log::info("GuildBoard: opened");
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
}
