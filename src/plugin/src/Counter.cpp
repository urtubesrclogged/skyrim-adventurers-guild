// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "Counter.h"

#include "ControlsGuard.h"
#include "Dungeons.h"
#include "Guild.h"
#include "Party.h"
#include "Loc.h"
#include "MissiveWatch.h"
#include "NoticeWatch.h"
#include "PrismaUI_API.h"
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
		constexpr const char* kView = "AdventurersGuild/counter.html";
		constexpr const char* kFile = "Data\\PrismaUI\\views\\AdventurersGuild\\counter.html";

		PRISMA_UI_API::IVPrismaUI1* g_api{ nullptr };
		PrismaView                  g_view{ 0 };
		std::atomic<bool>           g_open{ false };
		std::atomic<bool>           g_pending{ false };
		std::mutex                  g_branchLock;
		std::string                 g_branch;

		bool Valid() { return g_api && g_view && g_api->IsValid(g_view); }

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
			if (Valid()) g_api->Invoke(g_view, std::format("window.agStatus(\"{}\")", Esc(a_msg)).c_str());
		}

		// JS -> C++ listeners run on PrismaUI's side; hop to the game thread before touching game state.
		void OnClose(const char*)
		{
			SKSE::GetTaskInterface()->AddTask([] { Close(); });
		}

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
			if (a_arg.starts_with("add:")) {
				RE::FormID id = 0;
				try { id = static_cast<RE::FormID>(std::stoul(a_arg.substr(4), nullptr, 16)); } catch (...) { return {}; }
				return Party::Add(RE::TESForm::LookupByID<RE::Actor>(id));
			}
			return {};
		}

		void OnAction(const char* a_arg)
		{
			std::string arg = a_arg ? a_arg : "";
			SKSE::GetTaskInterface()->AddTask([arg] {
				if (arg.starts_with("details:")) {   // read-only: send the note's text to the view
					SKSE::log::debug("Counter: action '{}'", arg);
					const auto id = arg.substr(8);  // a missive or a notice: each watch knows its own quests
					if (Valid()) g_api->Invoke(g_view, ("window.agDetails(" + (NoticeWatch::Owns(id) ? NoticeWatch::Details(id) : MissiveWatch::Details(id)).dump() + ")").c_str());
					return;
				}
				std::string msg;
				if (arg == "claim") msg = Guild::ClaimAll();
				else if (arg.starts_with("service:")) msg = Guild::BuyService(arg.substr(8));
				else if (arg.starts_with("turnin:")) msg = Shop::TurnIn(arg.substr(7));
				else if (arg.starts_with("accept:")) msg = NoticeWatch::Owns(arg.substr(7)) ? NoticeWatch::Accept(arg.substr(7)) : MissiveWatch::Accept(arg.substr(7));
				else if (arg.starts_with("party:")) { msg = PartyAction(arg.substr(6)); Party::AtCounter(); }  // the blessing follows at once; choices the roster no longer fits go
				else {
					SKSE::log::debug("Counter: action '{}' is not one the DLL knows", arg);
					return;
				}
				SKSE::log::debug("Counter: action '{}' -> '{}'", arg, msg);  // detailed log: for "I clicked and nothing happened"
				Refresh();
				Status(msg);
			});
		}

		// ---- controller ----
		// PrismaUI gives a view the mouse and keyboard but not a controller, so the pad's buttons are forwarded to the
		// page (window.agPad), which moves a highlight between its buttons. The last device used decides whether the
		// page shows that highlight and the button hints (window.agInputMode), the way vanilla menus swap prompts.
		// VR controllers are other device types, so none of this happens in VR.
		std::atomic<bool> g_padMode{ false };

		void Js(const std::string& a_script)
		{
			if (g_open.load() && Valid()) g_api->Invoke(g_view, a_script.c_str());
		}

		void SetPadMode(bool a_pad)
		{
			if (g_padMode.exchange(a_pad) != a_pad) Js(std::format("window.agInputMode({})", a_pad));
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
					if (!name || !g_open.load()) continue;
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

			static void Send(const char* a_name) { Js(std::format("window.agPad(\"{}\")", a_name)); }

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
					if (dir && g_open.load()) Send(dir);
					m_stickNext = now + std::chrono::milliseconds(350);
				} else if (dir && g_open.load() && now >= m_stickNext) {
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
		g_api = PRISMA_UI_API::RequestPluginAPI<PRISMA_UI_API::IVPrismaUI1>();
		if (!g_api) {
			SKSE::log::info("Counter: PrismaUI not loaded - counter window disabled");
			return;
		}
		std::error_code ec;
		if (!std::filesystem::exists(kFile, ec)) {
			SKSE::log::info("Counter: {} missing - counter window disabled", kFile);
			g_api = nullptr;
			return;
		}
		g_view = g_api->CreateView(kView);
		if (!Valid()) {
			SKSE::log::error("Counter: CreateView failed");
			g_api = nullptr;
			return;
		}
		g_api->Hide(g_view);
		g_api->RegisterJSListener(g_view, "agClose", OnClose);
		g_api->RegisterJSListener(g_view, "agAction", OnAction);
		SKSE::log::info("Counter: view active (view {}, order {})", g_view, g_api->GetOrder(g_view));
	}

	std::string Branch()
	{
		std::lock_guard l(g_branchLock);
		return g_branch;
	}

	void OpenAfterDialogue(std::string a_branch)
	{
		{
			std::lock_guard l(g_branchLock);
			g_branch = std::move(a_branch);
		}
		g_pending = true;
		// If the Dialogue Menu is somehow already gone, open right away.
		SKSE::GetTaskInterface()->AddTask([] {
			auto* ui = RE::UI::GetSingleton();
			if (ui && !ui->IsMenuOpen(RE::DialogueMenu::MENU_NAME) && g_pending.exchange(false)) Open();
		});
	}

	void Open()
	{
		if (!Guild::Registered() || Guild::Dormant()) return;  // prepared for uninstall: the counter stays shut
		if (!Valid()) {
			RE::SendHUDMessage::ShowHUDMessage(Loc::F("$AG_Hud_NoPrisma", "Adventurers Guild: Rank {}, {} Merit (install PrismaUI for the counter window)",
				LetterStr(Guild::Rank()), Guild::Merit()).c_str());
			return;
		}
		g_open = true;
		Party::AtCounter();  // chosen affinities the roster no longer fits are unselected on every visit
		NoticeWatch::Post();  // newly allowed notices go up here as they would at a board
		// the page's text in the player's language (it keeps English fallbacks for anything missing)
		g_api->Invoke(g_view, ("window.agStrings(" + Loc::UiStrings().dump() + ")").c_str());
		// the headset keyboard is ours only under real SteamVR (see ShowKeyboard); flat and OpenComposite keep the text field
		g_api->Invoke(g_view, REL::Module::IsVR() && !OpenComposite() ? "window.agVR && window.agVR(true)" : "window.agVR && window.agVR(false)");
		Refresh();
		// after the data (tasks run in order): controller users open with the first button highlighted
		SKSE::GetTaskInterface()->AddTask([] { Js(std::format("window.agInputMode({})", g_padMode.load())); });
		ControlsGuard::Shown();
		ControlsGuard::Mask();  // VR: a trigger pull on the counter must not ready the weapon
		g_api->Show(g_view);
		g_api->Focus(g_view, true);
		SKSE::log::info("Counter: opened");
	}

	void Close()
	{
		if (!g_open.exchange(false) || !Valid()) return;
		g_api->Unfocus(g_view);
		g_api->Hide(g_view);
		ControlsGuard::Unmask();
		ControlsGuard::Hidden();
	}

	bool IsOpen() { return g_open.load(); }

	bool IsOpenComposite() { return OpenComposite(); }

	int ViewOrder() { return Valid() ? g_api->GetOrder(g_view) : -1; }

	void Refresh()
	{
		if (!g_open.load() || !Valid()) return;
		SKSE::GetTaskInterface()->AddTask([] {
			if (!g_open.load() || !Valid()) return;
			auto data = Guild::CounterData();
			data["branch"] = Branch();
			data["trophies"] = Shop::TrophiesData();
			data["postings"] = MissiveWatch::Postings(Branch());
			data["notices"] = NoticeWatch::Postings();
			data["boards"] = { { "missives", MissiveWatch::Active() }, { "notices", NoticeWatch::Active() } };  // which sub-tabs the Quests tab has
			data["party"] = Party::CounterData();
			for (auto& row : Dungeons::IntelServices(Guild::Merit(), Guild::Registered())) data["services"].push_back(row);
			const auto json = data.dump();
			g_api->Invoke(g_view, ("window.agSetData(" + json + ")").c_str());
		});
	}
}
