// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "Counter.h"

#include "BountyWatch.h"

#include "ControlsGuard.h"
#include "Dungeons.h"
#include "GuildCard.h"
#include "Guild.h"
#include "GuildBoard.h"
#include "LeaderBoard.h"
#include "GuildHall.h"
#include "Party.h"
#include "Loc.h"
#include "MissiveWatch.h"
#include "NoticeWatch.h"
#include "UiHost.h"
#include "RankCore.h"
#include "Shop.h"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <thread>

#include <openvr.h>

namespace AG::Counter
{
	namespace
	{
		UiHost::Handle              g_view{ 0 };
		std::atomic<bool>           g_open{ false };
		std::atomic<bool>           g_pending{ false };
		std::atomic<bool>           g_cardOnly{ false };  // opened from the physical card: the Guild Card page alone
		std::mutex                  g_branchLock;
		std::string                 g_branch;
		RE::ObjectRefHandle         g_keeper;            // the representative this counter was opened through (g_branchLock)
		std::atomic<bool>           g_stamped{ false };  // the card was stamped while the counter was open
		nlohmann::json              g_member;            // another adventurer's card being shown (null: the player's own page); game thread
		std::atomic<bool>           g_stampedFirst{ false };  // ... and for the first time by this hold

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
				default:
					if (c >= 0x20) out += static_cast<char>(c);
				}
			}
			return out;
		}

		void Status(const std::string& a_msg)
		{
			if (Valid()) UiHost::Js(g_view, std::format("window.agStatus(\"{}\")", Esc(a_msg)));
		}

		// calls from the page arrive on the game thread (UiHost)
		void OnClose(const std::string&) { Close(); }

		// ---- VR text entry (party names) ----
		// PrismaVR opens the SteamVR keyboard for a focused <input> but only routes the typed text under OpenComposite
		// (WM_OC_CHAR); under SteamVR the text never reaches the page and the keyboard re-opens empty while the field
		// keeps focus. So in VR the page shows a button instead, and the DLL runs the keyboard itself: it is shown for a
		// small overlay of our own (never displayed), whose event queue receives VREvent_KeyboardDone, and the text is
		// read back with GetKeyboardText and handed to the page (window.agKeyboardText). IVROverlay_018 (SteamVR keeps
		// serving older interface versions).
		vr::IVROverlay*        g_ovl{ nullptr };
		vr::VROverlayHandle_t  g_kbOverlay{ vr::k_ulOverlayHandleInvalid };
		std::atomic<bool>      g_kbOpen{ false };
		std::once_flag         g_kbPoll;

		void Js(const std::string& a_script);

		// OpenComposite replaces openvr_api.dll; there PrismaVR's own route (WM_OC_CHAR into a focused <input>) is the one
		// that works, so the page keeps its text field. Only real SteamVR gets the DLL-driven keyboard.
		bool OpenComposite()
		{
			static const bool oc = [] {
				char path[MAX_PATH]{};
				auto* dll = GetModuleHandleA("openvr_api.dll");
				if (!dll || !GetModuleFileNameA(dll, path, MAX_PATH)) return false;
				std::ifstream f(path, std::ios::binary);
				const std::string bytes((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
				const bool found = bytes.find("OpenComposite") != std::string::npos || bytes.find("opencomposite") != std::string::npos;
				SKSE::log::info("Counter: VR runtime {} ({})", found ? "OpenComposite" : "SteamVR", path);
				return found;
			}();
			return oc;
		}

		bool KbInit()
		{
			if (g_ovl) return true;
			auto* dll = GetModuleHandleA("openvr_api.dll");
			using GetIface = void* (*)(const char*, vr::EVRInitError*);
			auto* get = dll ? reinterpret_cast<GetIface>(GetProcAddress(dll, "VR_GetGenericInterface")) : nullptr;
			if (!get) { SKSE::log::warn("Counter: VR keyboard unavailable (no openvr_api.dll)"); return false; }
			vr::EVRInitError err = vr::VRInitError_None;
			auto*            ovl = static_cast<vr::IVROverlay*>(get(vr::IVROverlay_Version, &err));
			if (!ovl || err != vr::VRInitError_None) { SKSE::log::warn("Counter: VR keyboard unavailable ({} error {})", vr::IVROverlay_Version, static_cast<int>(err)); return false; }
			const auto e = ovl->CreateOverlay("adventurersguild.keyboard", "Adventurers Guild", &g_kbOverlay);
			if (e != vr::VROverlayError_None && e != vr::VROverlayError_KeyInUse) { SKSE::log::warn("Counter: VR keyboard overlay failed ({})", static_cast<int>(e)); return false; }
			if (e == vr::VROverlayError_KeyInUse) ovl->FindOverlay("adventurersguild.keyboard", &g_kbOverlay);
			g_ovl = ovl;
			return true;
		}

		std::string ShowKeyboard(const std::string& a_existing)
		{
			if (!KbInit()) return Loc::T("$AG_UI_NoKeyboard", "The headset keyboard could not be opened.");
			const auto e = g_ovl->ShowKeyboardForOverlay(g_kbOverlay, vr::k_EGamepadTextInputModeNormal, vr::k_EGamepadTextInputLineModeSingleLine,
				Loc::T("$AG_UI_PartyNameHint", "Name your party").c_str(), 32, a_existing.c_str(), false, 0);
			if (e != vr::VROverlayError_None) {
				SKSE::log::warn("Counter: ShowKeyboardForOverlay failed ({})", static_cast<int>(e));
				return Loc::T("$AG_UI_NoKeyboard", "The headset keyboard could not be opened.");
			}
			g_kbOpen = true;
			std::call_once(g_kbPoll, [] {
				std::thread([] {
					for (;;) {
						std::this_thread::sleep_for(std::chrono::milliseconds(50));
						if (!g_kbOpen.load()) continue;
						vr::VREvent_t ev{};
						while (g_ovl->PollNextOverlayEvent(g_kbOverlay, &ev, sizeof(ev))) {
							if (ev.eventType == vr::VREvent_KeyboardDone) {
								char buf[256]{};
								g_ovl->GetKeyboardText(buf, sizeof(buf));
								g_kbOpen = false;
								const auto text = nlohmann::json(std::string(buf)).dump();
								SKSE::log::info("Counter: VR keyboard done ({} bytes)", std::strlen(buf));
								SKSE::GetTaskInterface()->AddTask([text] { Js("window.agKeyboardText(" + text + ")"); });
							} else if (ev.eventType == vr::VREvent_KeyboardClosed) {
								g_kbOpen = false;
								SKSE::GetTaskInterface()->AddTask([] { Js("window.agKeyboardText(null)"); });
							}
						}
					}
				}).detach();
			});
			return {};
		}

		// The page sends typed names percent-encoded (encodeURIComponent), so any character survives the "verb:arg" line.
		std::string Unescape(const std::string& a_s)
		{
			std::string out;
			for (std::size_t i = 0; i < a_s.size(); ++i) {
				if (a_s[i] == '%' && i + 2 < a_s.size() && std::isxdigit(static_cast<unsigned char>(a_s[i + 1])) && std::isxdigit(static_cast<unsigned char>(a_s[i + 2]))) {
					out += static_cast<char>(std::stoi(a_s.substr(i + 1, 2), nullptr, 16));
					i += 2;
				} else {
					out += a_s[i];
				}
			}
			return out;
		}

		// "found:<name>" "rename:<name>" "disband" "add:<ref FormID hex>" "remove:<StableKey>"
		std::string PartyAction(const std::string& a_arg)
		{
			if (a_arg.starts_with("found:")) {  // "found:<name>|<FormID hex>,<FormID hex>..." (the name is percent-encoded)
				const auto rest = a_arg.substr(6);
				const auto bar = rest.rfind('|');
				std::vector<RE::Actor*> founders;
				if (bar != std::string::npos) {
					std::stringstream ids(rest.substr(bar + 1));
					for (std::string id; std::getline(ids, id, ',');) {
						try { founders.push_back(RE::TESForm::LookupByID<RE::Actor>(static_cast<RE::FormID>(std::stoul(id, nullptr, 16)))); } catch (...) {}
					}
				}
				return Party::Found(Unescape(rest.substr(0, bar)), founders);
			}
			if (a_arg.starts_with("rename:")) return Party::Rename(Unescape(a_arg.substr(7)));
			if (a_arg == "disband") return Party::Disband();
			if (a_arg.starts_with("trait:")) return Party::ToggleTrait(a_arg.substr(6));
			if (a_arg == "traitsviewed") { Party::TraitsViewed(); return {}; }
			if (a_arg.starts_with("keyboard:")) return ShowKeyboard(Unescape(a_arg.substr(9)));  // VR: the name, typed on the headset
			if (a_arg.starts_with("remove:")) return Party::Remove(a_arg.substr(7));
			if (a_arg.starts_with("register:")) {  // a follower registered by hand (2.0)
				RE::FormID id = 0;
				try { id = static_cast<RE::FormID>(std::stoul(a_arg.substr(9), nullptr, 16)); } catch (...) { return {}; }
				return Party::RegisterFollower(RE::TESForm::LookupByID<RE::Actor>(id));
			}
			if (a_arg.starts_with("add:")) {
				RE::FormID id = 0;
				try { id = static_cast<RE::FormID>(std::stoul(a_arg.substr(4), nullptr, 16)); } catch (...) { return {}; }
				return Party::Add(RE::TESForm::LookupByID<RE::Actor>(id));
			}
			return {};
		}

		void OnAction(const std::string& arg)
		{
			{
				if (arg.starts_with("details:")) {   // read-only: send the note's text to the view
					SKSE::log::debug("Counter: action '{}'", arg);
					const auto id = arg.substr(8);  // a missive or a notice: each watch knows its own quests
					const auto details = BountyWatch::Owns(id) ? BountyWatch::Details(id) : NoticeWatch::Owns(id) ? NoticeWatch::Details(id) : MissiveWatch::Details(id);
					if (Valid()) UiHost::Js(g_view, "window.agDetails(" + details.dump() + ")");
					return;
				}
				if (arg == "newbounty") {  // the Guild Hall's "A new bounty?": Papyrus answers later, the page waits for it
					if (!GuildHall::IsBranch(Branch())) return;
					BountyWatch::NewBounty([](const std::string& a_msg) {
						SKSE::log::debug("Counter: action 'newbounty' -> '{}'", a_msg);
						Refresh();
						Status(a_msg);
					});
					return;
				}
				std::string msg;
				if (arg == "claim") msg = Guild::ClaimAll(g_cardOnly.load() ? std::string() : Branch());
				// a lost guild card, replaced at the counter as the liaison's dialogue line does (same fee, this branch's seal).
				// Not from the card itself: read from the inventory, there is one, and no branch to issue another.
				else if (arg == "replacecard") { if (g_cardOnly.load()) return; msg = GuildCard::Replace(Branch()); }
				else if (arg.starts_with("service:")) {
					// what only the Guild Hall sells (MCM > Guild Hall): the page greys it at an inn; refused here too
					const auto id = arg.substr(8);
					const auto only = GuildHall::ServiceFeature(id);
					msg = only && !GuildHall::Allows(*only, Branch()) ? GuildHall::RefusedHere() : Guild::BuyService(id);
				}
				else if (arg.starts_with("turnin:")) msg = Shop::TurnIn(arg.substr(7));
				else if (arg.starts_with("accept:")) {
					const auto id = arg.substr(7);
					msg = BountyWatch::Owns(id) ? BountyWatch::Accept(id) : NoticeWatch::Owns(id) ? NoticeWatch::Accept(id) : MissiveWatch::Accept(id);
				}
				else if (arg.starts_with("party:")) {
					// the party registry (founding, renaming, disbanding) is the Guild Hall's alone while MCM > Guild Hall says so
					const auto sub = arg.substr(6);
					const bool registry = sub.starts_with("found:") || sub.starts_with("rename:") || sub == "disband";
					if (registry && !GuildHall::Allows(GuildHall::Only::kParties, Branch())) msg = GuildHall::RefusedHere();
					// a follower is registered where the player would be (MCM > Guild Hall > Registration)
					else if (sub.starts_with("register:") && (g_cardOnly.load() || !GuildHall::Allows(GuildHall::Only::kRegistration, Branch()))) msg = GuildHall::RefusedHere();
					else { msg = PartyAction(sub); Party::AtCounter(); }  // the blessing follows at once; choices the roster no longer fits go
				}
				else {
					SKSE::log::debug("Counter: action '{}' is not one the DLL knows", arg);
					return;
				}
				SKSE::log::debug("Counter: action '{}' -> '{}'", arg, msg);  // detailed log: for "I clicked and nothing happened"
				Refresh();
				Status(msg);
			}
		}

		// ---- controller ----
		// PrismaUI gives a view the mouse and keyboard but not a controller, so the pad's buttons are forwarded to the
		// page (window.agPad), which moves a highlight between its buttons. The last device used decides whether the
		// page shows that highlight and the button hints (window.agInputMode), the way vanilla menus swap prompts.
		// VR controllers are other device types, so none of this happens in VR. The Guild Board's page (GuildBoard) takes
		// the same buttons while it is open: one reader of the pad, for whichever page is up.
		std::atomic<bool> g_padMode{ false };

		void Js(const std::string& a_script)
		{
			if (g_open.load() && Valid()) UiHost::Js(g_view, a_script);
		}

		bool PadTarget() { return g_open.load() || GuildBoard::IsOpen() || LeaderBoard::IsOpen(); }

		void PadJs(const std::string& a_script)
		{
			if (g_open.load()) Js(a_script);
			else if (LeaderBoard::IsOpen()) LeaderBoard::Invoke(a_script);
			else GuildBoard::Invoke(a_script);
		}

		void SetPadMode(bool a_pad)
		{
			if (g_padMode.exchange(a_pad) != a_pad) PadJs(std::format("window.agInputMode({})", a_pad));
		}

		// XInput button masks, as the engine reports gamepad ButtonEvents; triggers are 0x9 / 0xA
		const char* PadName(std::uint32_t a_code)
		{
			switch (a_code) {
			case 0x0001: return "up";
			case 0x0002: return "down";
			case 0x0004: return "left";
			case 0x0008: return "right";
			case 0x1000: return "a";
			case 0x2000: return "b";
			case 0x0100: return "lb";
			case 0x0200: return "rb";
			case 0x0009: return "lt";
			case 0x000A: return "rt";
			default: return nullptr;
			}
		}

		class PadSink : public RE::BSTEventSink<RE::InputEvent*>
		{
		public:
			static PadSink* Get()
			{
				static PadSink s;
				return &s;
			}

			RE::BSEventNotifyControl ProcessEvent(RE::InputEvent* const* a_events, RE::BSTEventSource<RE::InputEvent*>*) override
			{
				for (auto* e = a_events ? *a_events : nullptr; e; e = e->next) {
					const auto dev = e->GetDevice();
					if (dev == RE::INPUT_DEVICE::kKeyboard || dev == RE::INPUT_DEVICE::kMouse) {
						const auto* b = e->AsButtonEvent();
						const auto* m = e->AsMouseMoveEvent();
						if ((b && b->IsDown()) || (m && std::abs(m->mouseInputX) + std::abs(m->mouseInputY) > 3)) SetPadMode(false);
						continue;
					}
					if (dev != RE::INPUT_DEVICE::kGamepad) continue;
					if (e->GetEventType() == RE::INPUT_EVENT_TYPE::kThumbstick) {
						Stick(static_cast<RE::ThumbstickEvent*>(e));
						continue;
					}
					const auto* b = e->AsButtonEvent();
					if (!b || !b->IsPressed()) continue;
					SetPadMode(true);
					const char* name = PadName(b->GetIDCode());
					if (!name || !PadTarget()) continue;
					const bool dir = b->GetIDCode() <= 0x0008;
					// a held D-pad direction repeats after 0.35 s, every 0.1 s
					if (b->IsDown()) Send(name);
					else if (dir && b->HeldDuration() >= 0.35f) {
						const int step = static_cast<int>((b->HeldDuration() - 0.35f) / 0.1f);
						if (step != m_lastStep[b->GetIDCode()]) {
							m_lastStep[b->GetIDCode()] = step;
							Send(name);
						}
					}
					if (b->IsDown()) m_lastStep[b->GetIDCode()] = -1;
				}
				return RE::BSEventNotifyControl::kContinue;
			}

		private:
			using Clock = std::chrono::steady_clock;

			static void Send(const char* a_name) { PadJs(std::format("window.agPad(\"{}\")", a_name)); }

			// the left stick moves the highlight like the D-pad: once on a push, then repeating while held
			void Stick(const RE::ThumbstickEvent* a_t)
			{
				if (!a_t->IsLeft()) return;
				const float x = a_t->xValue, y = a_t->yValue;
				const char* dir = nullptr;
				if (std::max(std::abs(x), std::abs(y)) >= 0.6f) dir = std::abs(x) > std::abs(y) ? (x > 0 ? "right" : "left") : (y > 0 ? "up" : "down");
				if (std::max(std::abs(x), std::abs(y)) >= 0.3f) SetPadMode(true);
				const auto now = Clock::now();
				if (dir != m_stickDir) {
					m_stickDir = dir;
					if (dir && PadTarget()) Send(dir);
					m_stickNext = now + std::chrono::milliseconds(350);
				} else if (dir && PadTarget() && now >= m_stickNext) {
					Send(dir);
					m_stickNext = now + std::chrono::milliseconds(100);
				}
			}

			std::unordered_map<std::uint32_t, int> m_lastStep;
			const char*                            m_stickDir{ nullptr };
			Clock::time_point                      m_stickNext{};
		};

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
				if (a_e && !a_e->opening && a_e->menuName == RE::DialogueMenu::MENU_NAME && g_pending.exchange(false)) {
					SKSE::GetTaskInterface()->AddTask([] { Open(); });
				}
				return RE::BSEventNotifyControl::kContinue;
			}
		};
	}

	void Install()
	{
		if (auto* ui = RE::UI::GetSingleton()) ui->AddEventSink<RE::MenuOpenCloseEvent>(MenuSink::Get());
		if (auto* input = RE::BSInputDeviceManager::GetSingleton()) input->AddEventSink(PadSink::Get());
		g_view = UiHost::Create({ "counter", "counter.html", UiHost::Layer::kPanel, true, true });
		if (!g_view) {
			SKSE::log::info("Counter: no page - counter window disabled");
			return;
		}
		UiHost::Listen(g_view, "agClose", OnClose);
		UiHost::Listen(g_view, "agAction", OnAction);
		UiHost::OnHostClosed(g_view, [] { Close(); });
	}

	std::string Branch()
	{
		std::lock_guard l(g_branchLock);
		return g_branch;
	}

	void OpenAfterDialogue(std::string a_branch, RE::TESObjectREFR* a_keeper)
	{
		{
			std::lock_guard l(g_branchLock);
			g_branch = std::move(a_branch);
			g_keeper = a_keeper ? a_keeper->GetHandle() : RE::ObjectRefHandle{};
		}
		g_pending = true;
		g_cardOnly = false;
		// If the Dialogue Menu is somehow already gone, open right away.
		SKSE::GetTaskInterface()->AddTask([] {
			auto* ui = RE::UI::GetSingleton();
			if (ui && !ui->IsMenuOpen(RE::DialogueMenu::MENU_NAME) && g_pending.exchange(false)) Open();
		});
	}

	void Open()
	{
		if (g_member.is_null() && (!Guild::Registered() || Guild::Dormant())) return;  // prepared for uninstall: the counter stays shut
		if (!Valid()) {
			RE::SendHUDMessage::ShowHUDMessage(Loc::F("$AG_Hud_NoPrisma", "Adventurers Guild: Rank {}, {} Merit (install PrismaUI for the counter window)",
				LetterStr(Guild::Rank()), Guild::Merit()).c_str());
			return;
		}
		g_open = true;
		StampLineStarted();  // a line asked for and never said must not stay unlocked
		if (!g_cardOnly.load()) {  // only a real visit to a counter does counter business
			Party::AtCounter();  // chosen affinities the roster no longer fits are unselected on every visit
			GuildCard::CollectHoldStamp(Branch());  // this hold's stamp goes on the card here, and only here, once it is earned
			NoticeWatch::Post();  // newly allowed notices go up here as they would at a board
		}
		// the page's text in the player's language (it keeps English fallbacks for anything missing)
		UiHost::Js(g_view, "window.agStrings(" + Loc::UiStrings().dump() + ")");
		// the page stays loaded between visits: its lists' filters start over (a hold picked at one clerk's counter
		// left the other's list empty, in game 2026-10-28)
		UiHost::Js(g_view, "window.agOpened && window.agOpened()");
		// the headset keyboard is the DLL's only on Prisma UI under real SteamVR (see ShowKeyboard); flat, OpenComposite and
		// Magelight UI (its own headset keyboard) keep the text field
		UiHost::Js(g_view, REL::Module::IsVR() && !OpenComposite() && !UiHost::NativeVRText() ? "window.agVR && window.agVR(true)" : "window.agVR && window.agVR(false)");
		UiHost::Js(g_view, UiHost::Active() == UiHost::Kind::kMagelight ? "window.agHost && window.agHost(\"magelight\")" : "window.agHost && window.agHost(\"prisma\")");
		// a flat screen above 1080p scales the panel up (a 4K monitor showed it at a third of the width); VR never does
		UiHost::Js(g_view, REL::Module::IsVR() ? "window.agFlat && window.agFlat(false)" : "window.agFlat && window.agFlat(true)");
		Refresh();
		// after the data (tasks run in order): controller users open with the first button highlighted
		SKSE::GetTaskInterface()->AddTask([] { Js(std::format("window.agInputMode({})", g_padMode.load())); });
		if (!UiHost::ManagesControls()) {  // Prisma UI only: Magelight UI suspends the player's controls itself
			ControlsGuard::Shown();
			ControlsGuard::Mask();  // VR: a trigger pull on the counter must not ready the weapon
		}
		UiHost::Show(g_view);
		if (!UiHost::Focus(g_view)) {  // another mod's page has the input: the counter does not open under it
			Close();
			return;
		}
		if (g_cardOnly.load()) SKSE::log::info("Counter: opened as the guild card");
		else SKSE::log::info("Counter: opened");
	}

	bool IsCardOnly() { return g_open.load() && g_cardOnly.load(); }

	void OpenCard()
	{
		if (g_open.load()) return;
		{
			std::lock_guard l(g_branchLock);
			g_branch.clear();  // not at any branch
		}
		g_cardOnly = true;
		Open();
		if (!g_open.load()) g_cardOnly = false;  // could not open (not registered, no PrismaUI)
	}

	void OpenMemberCard(const nlohmann::json& a_member)
	{
		if (g_open.load() || a_member.is_null()) return;
		{
			std::lock_guard l(g_branchLock);
			g_branch.clear();
		}
		g_member = a_member;
		g_cardOnly = true;
		Open();
		if (!g_open.load()) {
			g_cardOnly = false;
			g_member = nullptr;
		} else {
			SKSE::log::info("Counter: opened as {}'s guild card", a_member.value("name", "?"));
		}
	}

	void Close()
	{
		if (!g_open.exchange(false) || !Valid()) return;
		g_member = nullptr;
		UiHost::Unfocus(g_view);
		UiHost::Hide(g_view);
		g_cardOnly = false;
		if (!UiHost::ManagesControls()) {
			ControlsGuard::Unmask();
			ControlsGuard::Hidden();
		}
		if (g_stamped.exchange(false)) SayStampLine(0, 0, g_stampedFirst.exchange(false));  // "There. Riften's mark, on your card."
	}

	void StampLineStarted()
	{
		auto* dh = RE::TESDataHandler::GetSingleton();
		if (auto* lock = dh ? dh->LookupForm<RE::TESGlobal>(0xCE9, "AdventurersGuild.esp") : nullptr) lock->value = 0.0f;
	}

	void Stamped(bool a_first)
	{
		if (g_open.load() && !g_cardOnly.load()) {
			g_stamped = true;
			if (a_first) g_stampedFirst = true;
		}
	}

	std::string SayStampLine(std::uint32_t a_topic, int a_attempt, bool a_first)
	{
		RE::NiPointer<RE::TESObjectREFR> keeper;
		{
			std::lock_guard l(g_branchLock);
			keeper = g_keeper.get();
		}
		auto* dh = RE::TESDataHandler::GetSingleton();
		auto* topic = dh ? dh->LookupForm<RE::TESTopic>(a_topic ? a_topic : 0xCE6, "AdventurersGuild.esp") : nullptr;
		auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton();
		if (!keeper) return "no representative: open a counter through her first";
		if (!topic || !vm) return "the topic is not in the plugin";
		if (!keeper->Is3DLoaded() || keeper->IsDead()) return "she is not here to say it";
		// the line is an idle line, locked so that it is never idle chatter: open for this one asking
		auto* lock = dh->LookupForm<RE::TESGlobal>(0xCE9, "AdventurersGuild.esp");
		if (lock) lock->value = a_first ? 2.0f : 1.0f;  // 2: her first-time line, with its word about the merchants
		// the game remembers a line as said; nothing of ours is to be refused for that
		for (std::uint32_t i = 0; topic->topicInfos && i < topic->numTopicInfos; ++i)
			if (auto* line = topic->topicInfos[i]) line->saidOnce = false;
		// She may still be finishing the sentence that opened the counter, and a character who is speaking takes no new
		// line. The lock closes when she starts (StampLineStarted); while it is still open, ask again, a few times.
		if (lock && a_attempt < 3)
			std::thread([a_topic, a_attempt, a_first] {
				std::this_thread::sleep_for(std::chrono::milliseconds(2500));
				SKSE::GetTaskInterface()->AddTask([a_topic, a_attempt, a_first] {
					auto* d = RE::TESDataHandler::GetSingleton();
					auto* l = d ? d->LookupForm<RE::TESGlobal>(0xCE9, "AdventurersGuild.esp") : nullptr;
					if (!l || l->value < 0.5f) return;  // she said it
					if (a_attempt + 1 < 3) SayStampLine(a_topic, a_attempt + 1, a_first);
					else {
						l->value = 0.0f;  // never left open: an open lock would make it idle chatter
						SKSE::log::warn("Counter: the stamp line was asked for three times and not said");
					}
				});
			}).detach();
		RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor> cb;
		vm->DispatchStaticCall("AG_QuestHelper", "SayLine", RE::MakeFunctionArguments(static_cast<RE::TESObjectREFR*>(keeper.get()), static_cast<RE::TESTopic*>(topic)), cb);
		SKSE::log::info("Counter: {} is asked to say {} ({:08X}){}", keeper->GetDisplayFullName(), topic->GetFormEditorID() ? topic->GetFormEditorID() : "", topic->GetFormID(),
			a_attempt ? std::format(", again ({})", a_attempt + 1) : std::string());
		return std::format("{} asked to say {:08X}", keeper->GetDisplayFullName(), topic->GetFormID());
	}

	bool IsOpen() { return g_open.load(); }

	bool PadMode() { return g_padMode.load(); }

	bool IsOpenComposite() { return OpenComposite(); }

	std::uint32_t View() { return g_view; }

	void Refresh()
	{
		if (!g_open.load() || !Valid()) return;
		SKSE::GetTaskInterface()->AddTask([] {
			if (!g_open.load() || !Valid()) return;
			auto data = Guild::CounterData();
			{
				// the branch city in the player's language: $AG_City_<Name>, optional for translators (English otherwise).
				// Branch() itself stays English: it is also the key the postings are filtered by.
				const auto city = Branch();
				std::string key = "$AG_City_";
				for (const char c : city)
					if (std::isalnum(static_cast<unsigned char>(c))) key += c;
				data["branch"] = city.empty() ? city : Loc::T(key, city);
				// Solstheim belongs to Morrowind: the counter there, and the Guild Card read on the island, say so
				bool morrowind = city == "Raven Rock";
				if (!morrowind && city.empty()) {
					static auto* solstheim = [] {
						auto* dh = RE::TESDataHandler::GetSingleton();
						return dh ? dh->LookupForm<RE::BGSLocation>(0x016E2A, "Dragonborn.esm") : nullptr;
					}();
					auto* pc = RE::PlayerCharacter::GetSingleton();
					for (auto* l = pc ? pc->GetCurrentLocation() : nullptr; l && solstheim && !morrowind; l = l->parentLoc) morrowind = l == solstheim;
				}
				data["region"] = morrowind ? "Morrowind" : "Skyrim";
			}
			data["cardOnly"] = g_cardOnly.load();
			if (!g_member.is_null()) data["member"] = g_member;  // someone else's card: the page draws that and nothing of the player's
			// a member without their card: the Guild Card page shows it masked, with a replacement for sale
			data["hasCard"] = GuildCard::Has();
			data["cardFee"] = Guild::CardFee();
			data["cardAfford"] = Guild::Gold() >= Guild::CardFee();
			// the hold stamps on the card, in the order they were stamped (the page lays them out), and at a counter how
			// far this hold's is from being earned
			{
				auto stamps = nlohmann::json::array();
				const auto have = GuildCard::HoldStamps();
				for (auto& c : have) stamps.push_back(GuildCard::StampFile(c));
				data["stamps"] = std::move(stamps);
				const auto here = Branch();
				if (const int cleared = here.empty() || GuildHall::IsBranch(here) ? -1 : Dungeons::ClearedIn(here); cleared >= 0 && std::find(have.begin(), have.end(), here) == have.end())
					data["stampProgress"] = { { "city", Guild::CityName(here) }, { "have", cleared }, { "need", Guild::StampDungeons() }, { "waiting", Dungeons::WaitingIn(here) } };
			}
			data["inProgress"] = MissiveWatch::InProgress() + NoticeWatch::InProgress() + BountyWatch::InProgress();  // the card's "to do" note
			data["trophies"] = Shop::TrophiesData();
			if (GuildHall::IsBranch(Branch()) && !g_cardOnly.load()) {
				GuildHall::CounterData(data);  // the Guild Hall (2.0): every hold's missives and bounties, and the holds to filter them by
			} else {
				data["postings"] = MissiveWatch::Postings(Branch());
				data["boardStatus"] = MissiveWatch::BoardStatus();  // this town's board: due a refresh, or how long until it is
				data["bounty"] = g_cardOnly.load() ? nlohmann::json(nullptr) : BountyWatch::Posting(Branch());  // this hold's one bounty, or null
			}
			data["notices"] = NoticeWatch::Postings();
			data["boards"] = { { "missives", MissiveWatch::Active() }, { "notices", NoticeWatch::Active() } };  // which sub-tabs the Quests tab has
			data["party"] = Party::CounterData();
			// the Guild Hall's counter sells every hold's Intel, as it lists every hold's work
			const bool everyHold = GuildHall::IsBranch(Branch()) && !g_cardOnly.load();
			for (auto rows : { Dungeons::IntelServices(Guild::Merit(), Guild::Registered(), everyHold), Dungeons::PoiServices(Guild::Merit(), Guild::Registered(), everyHold) })
				for (auto& row : rows) {
					if (everyHold) GuildHall::NameHold(row);
					data["services"].push_back(row);
				}
			// what only the Guild Hall does (MCM > Guild Hall, 2.0): greyed here at an inn, and what the page says instead
			GuildHall::GreyServices(data["services"], Branch());
			data["partyRegistry"] = g_cardOnly.load() || GuildHall::Allows(GuildHall::Only::kParties, Branch());
			data["promotionAtHall"] = GuildHall::OnlyAtHall(GuildHall::Only::kPromotion);
			data["followerRegister"] = !g_cardOnly.load() && GuildHall::Allows(GuildHall::Only::kRegistration, Branch());
			const auto json = data.dump();
			UiHost::Js(g_view, "window.agSetData(" + json + ")");
		});
	}
}
