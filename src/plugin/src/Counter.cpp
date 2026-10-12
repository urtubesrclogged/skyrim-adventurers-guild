// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "Counter.h"

#include "ControlsGuard.h"
#include "Dungeons.h"
#include "GuildCard.h"
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
		std::atomic<bool>           g_cardOnly{ false };  // opened from the physical card: the Guild Card page alone
		std::mutex                  g_branchLock;
		std::string                 g_branch;
		RE::ObjectRefHandle         g_keeper;            // the representative this counter was opened through (g_branchLock)
		std::atomic<bool>           g_stamped{ false };  // the card was stamped while the counter was open
		nlohmann::json              g_member;            // another adventurer's card being shown (null: the player's own page); game thread
		std::atomic<bool>           g_stampedFirst{ false };  // ... and for the first time by this hold

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
				if (arg == "claim") msg = Guild::ClaimAll(g_cardOnly.load() ? std::string() : Branch());
				// a lost guild card, replaced at the counter as the liaison's dialogue line does (same fee, this branch's seal).
				// Not from the card itself: read from the inventory, there is one, and no branch to issue another.
				else if (arg == "replacecard") { if (g_cardOnly.load()) return; msg = GuildCard::Replace(Branch()); }
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
		g_api->Invoke(g_view, ("window.agStrings(" + Loc::UiStrings().dump() + ")").c_str());
		// the headset keyboard is ours only under real SteamVR (see ShowKeyboard); flat and OpenComposite keep the text field
		g_api->Invoke(g_view, REL::Module::IsVR() && !OpenComposite() ? "window.agVR && window.agVR(true)" : "window.agVR && window.agVR(false)");
		// a flat screen above 1080p scales the panel up (a 4K monitor showed it at a third of the width); VR never does
		g_api->Invoke(g_view, REL::Module::IsVR() ? "window.agFlat && window.agFlat(false)" : "window.agFlat && window.agFlat(true)");
		Refresh();
		// after the data (tasks run in order): controller users open with the first button highlighted
		SKSE::GetTaskInterface()->AddTask([] { Js(std::format("window.agInputMode({})", g_padMode.load())); });
		ControlsGuard::Shown();
		ControlsGuard::Mask();  // VR: a trigger pull on the counter must not ready the weapon
		g_api->Show(g_view);
		g_api->Focus(g_view, true);
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
		g_api->Unfocus(g_view);
		g_api->Hide(g_view);
		g_cardOnly = false;
		ControlsGuard::Unmask();
		ControlsGuard::Hidden();
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

	bool IsOpenComposite() { return OpenComposite(); }

	int ViewOrder() { return Valid() ? g_api->GetOrder(g_view) : -1; }

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
			if (auto* pc = RE::PlayerCharacter::GetSingleton()) data["cardAfford"] = pc->GetGoldAmount() >= Guild::CardFee();
			// the hold stamps on the card, in the order they were stamped (the page lays them out), and at a counter how
			// far this hold's is from being earned
			{
				auto stamps = nlohmann::json::array();
				const auto have = GuildCard::HoldStamps();
				for (auto& c : have) stamps.push_back(GuildCard::StampFile(c));
				data["stamps"] = std::move(stamps);
				const auto here = Branch();
				if (const int cleared = here.empty() ? -1 : Dungeons::ClearedIn(here); cleared >= 0 && std::find(have.begin(), have.end(), here) == have.end())
					data["stampProgress"] = { { "city", Guild::CityName(here) }, { "have", cleared }, { "need", Guild::StampDungeons() }, { "waiting", Dungeons::WaitingIn(here) } };
			}
			data["inProgress"] = MissiveWatch::InProgress() + NoticeWatch::InProgress();  // the card's "to do" note
			data["trophies"] = Shop::TrophiesData();
			data["postings"] = MissiveWatch::Postings(Branch());
			data["notices"] = NoticeWatch::Postings();
			data["boards"] = { { "missives", MissiveWatch::Active() }, { "notices", NoticeWatch::Active() } };  // which sub-tabs the Quests tab has
			data["party"] = Party::CounterData();
			for (auto& row : Dungeons::IntelServices(Guild::Merit(), Guild::Registered())) data["services"].push_back(row);
			for (auto& row : Dungeons::PoiServices(Guild::Merit(), Guild::Registered())) data["services"].push_back(row);
			const auto json = data.dump();
			g_api->Invoke(g_view, ("window.agSetData(" + json + ")").c_str());
		});
	}
}
