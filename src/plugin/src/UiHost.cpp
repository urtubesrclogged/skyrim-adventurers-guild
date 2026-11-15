// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "UiHost.h"

#include "MagelightUI_API.h"
#include "PrismaUI_API.h"

#include <SimpleIni.h>

#include <array>
#include <atomic>
#include <filesystem>
#include <memory>
#include <utility>

namespace AG::UiHost
{
	namespace
	{
		namespace ML = MAGELIGHT_API;

		constexpr const char*   kFolder = "Data\\PrismaUI\\views\\AdventurersGuild\\";  // the pages: one copy for both hosts
		constexpr std::uint32_t kMagelightMin = ML::PackVersion(1, 8, 0);              // the version the spike is built against

		Kind                          g_kind{ Kind::kNone };
		PRISMA_UI_API::IVPrismaUI1*   g_prisma{ nullptr };
		const ML::MagelightApi4*      g_ml{ nullptr };
		ML::ModId                     g_mod{ 0 };

		// VR placement of Magelight UI's quads ([UI] in the ini; 0 = the host's own default for the layer)
		struct Placement { int mode = -1; float width = 0, distance = 0, height = 0; };
		Placement g_vrPanel, g_vrNotice;

		struct Entry
		{
			std::string      name;
			bool             textEntry{ false };
			PrismaView       pv{ 0 };
			ML::ViewId       mv{ 0 };
			Closed           closed{ nullptr };
			std::atomic<int> releases{ 0 };  // UI-mode exits of our own asking still to come (Magelight UI)
		};
		std::array<Entry, 8> g_views;  // filled at kDataLoaded on the game thread, never moved
		std::uint32_t        g_count = 0;

		Entry* Get(Handle a_view) { return a_view > 0 && a_view <= g_count ? &g_views[a_view - 1] : nullptr; }

		Entry* ByMagelight(ML::ViewId a_mv)
		{
			for (std::uint32_t i = 0; i < g_count; ++i)
				if (g_views[i].mv == a_mv) return &g_views[i];
			return nullptr;
		}

		// ---- calls from a page, delivered on the game thread ----
		struct Slot { Listener fn{ nullptr }; std::string view, name; };
		std::array<Slot, 8> g_slots;
		std::uint32_t       g_slotCount = 0;

		// Prisma UI calls a listener on its own thread with no context pointer: one trampoline per slot.
		template <std::size_t N>
		void PrismaTramp(const char* a_arg)
		{
			const auto fn = g_slots[N].fn;
			std::string arg = a_arg ? a_arg : "";
			if (fn) SKSE::GetTaskInterface()->AddTask([fn, arg] { fn(arg); });
		}
		template <std::size_t... I>
		constexpr std::array<PRISMA_UI_API::JSListenerCallback, sizeof...(I)> PrismaTramps(std::index_sequence<I...>) { return { &PrismaTramp<I>... }; }
		constexpr auto kPrismaTramps = PrismaTramps(std::make_index_sequence<8>{});

		// Magelight UI calls a listener inside the game's frame: copy the argument and post with its PostGameTask (an
		// AddTask from here can hang Skyrim VR; MagelightUI_API.h, threading contract).
		struct Call { std::uint32_t slot; std::string arg; };
		void RunCall(void* a_user)
		{
			std::unique_ptr<Call> c(static_cast<Call*>(a_user));
			if (c->slot < g_slotCount && g_slots[c->slot].fn) g_slots[c->slot].fn(c->arg);
		}
		void MagelightTramp(ML::ViewId, const char* a_arg, void* a_user)
		{
			auto* c = new Call{ static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(a_user)), a_arg ? a_arg : "" };
			if (g_ml->PostGameTask(&RunCall, c) != ML::Result::Ok) {
				const auto& s = g_slots[c->slot];
				SKSE::log::error("UiHost: a call from the {} page ({}) could not be passed to the game", s.view, s.name);
				delete c;
			}
		}

		// ---- Magelight UI's events (game thread) ----
		void OnEvent(const ML::EventData* a_ev, void*)
		{
			if (!a_ev) return;
			auto*       e = ByMagelight(a_ev->view);
			const char* name = e ? e->name.c_str() : "?";
			const char* detail = a_ev->detail ? a_ev->detail : "";
			switch (a_ev->type) {
			case ML::Event::UIModeExited:
				if (!e) return;
				if (e->releases.load() > 0) {  // one we asked for
					--e->releases;
					return;
				}
				SKSE::log::info("UiHost: Magelight UI closed the {} page (Escape, B/Y or a load)", name);
				if (e->closed) e->closed();
				return;
			case ML::Event::UIModeRefused:
				SKSE::log::warn("UiHost: Magelight UI did not give the {} page input ({})", name, detail);
				if (e && e->closed) e->closed();
				return;
			case ML::Event::FocusDenied:
				SKSE::log::info("UiHost: another mod's page ({}) asked for input while the {} page had it", detail, name);
				return;
			case ML::Event::ViewLoadFailed:
				SKSE::log::error("UiHost: the {} page did not load: {}", name, detail);
				return;
			case ML::Event::ConsoleMessage:
				if (a_ev->x >= 2) SKSE::log::warn("UiHost: script error in the {} page (line {}): {}", name, a_ev->y, detail);
				return;
			case ML::Event::RenderDead:
				SKSE::log::error("UiHost: Magelight UI turned itself off for this session - the Guild's pages are gone until the game restarts");
				return;
			default:
				return;
			}
		}

		std::string Lower(std::string a_s)
		{
			for (auto& c : a_s) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
			return a_s;
		}

		Placement ReadPlacement(CSimpleIniA& a_ini, const char* a_prefix, Placement a_p)
		{
			const auto key = [&](const char* a_k) { return std::string(a_prefix) + a_k; };
			a_p.mode = static_cast<int>(a_ini.GetLongValue("UI", key("Mode").c_str(), a_p.mode));
			a_p.width = static_cast<float>(a_ini.GetDoubleValue("UI", key("Width").c_str(), a_p.width));
			a_p.distance = static_cast<float>(a_ini.GetDoubleValue("UI", key("Distance").c_str(), a_p.distance));
			a_p.height = static_cast<float>(a_ini.GetDoubleValue("UI", key("Height").c_str(), a_p.height));
			return a_p;
		}

		std::string PagePath(const char* a_file)  // absolute, UTF-8: Magelight UI loads a file:/// URL
		{
			wchar_t buf[MAX_PATH]{};
			GetModuleFileNameW(nullptr, buf, MAX_PATH);
			const auto p = std::filesystem::path(buf).parent_path() / L"Data" / L"PrismaUI" / L"views" / L"AdventurersGuild" / std::filesystem::path(a_file);
			const auto u = p.u8string();
			return std::string(reinterpret_cast<const char*>(u.data()), u.size());
		}

		bool RegisterMagelight()
		{
			ML::ModDesc d{};
			d.size = sizeof(d);
			d.modId = "AdventurersGuild";
			d.displayName = "Adventurers Guild";
			d.modVersion = ML::PackVersion(AG_VERSION_MAJOR, AG_VERSION_MINOR, AG_VERSION_PATCH);
			d.minHostVersion = kMagelightMin;
			d.callbackThread = ML::CallbackThread::GameThread;
			d.onEvent = &OnEvent;
			const auto r = g_ml->RegisterMod(&d, &g_mod);
			if (r != ML::Result::Ok) {
				SKSE::log::error("UiHost: Magelight UI refused the Guild (result {})", static_cast<int>(r));
				g_mod = 0;
				return false;
			}
			return true;
		}

		std::string Version(std::uint32_t a_packed) { return std::format("{}.{}.{}", a_packed / 10000, a_packed / 100 % 100, a_packed % 100); }
	}

	void Init()
	{
		// the choice: the ini, then the test override (each read if it is there)
		std::string want = "auto";
		std::string from = "default";
		for (const char* file : { "Data/SKSE/Plugins/AdventurersGuild.ini", "Data/SKSE/Plugins/AdventurersGuild/UIHost.ini" }) {
			CSimpleIniA ini;
			ini.SetUnicode();
			if (ini.LoadFile(file) < 0) continue;
			if (const char* h = ini.GetValue("UI", "Host", nullptr); h && *h) {
				want = Lower(h);
				from = file;
			}
			g_vrPanel = ReadPlacement(ini, "VRPanel", g_vrPanel);
			g_vrNotice = ReadPlacement(ini, "VRNotice", g_vrNotice);
		}
		if (want != "prisma" && want != "magelight" && want != "auto") {
			SKSE::log::warn("UiHost: [UI] Host = {} is not auto, prisma or magelight - using auto", want);
			want = "auto";
		}

		g_prisma = PRISMA_UI_API::RequestPluginAPI<PRISMA_UI_API::IVPrismaUI1>();
		g_ml = ML::RequestApi4();
		const bool mlOk = g_ml && g_ml->hostVersionNumber >= kMagelightMin;
		if (g_ml && !mlOk) SKSE::log::info("UiHost: Magelight UI {} is installed, older than the {} the Guild needs - not used", Version(g_ml->hostVersionNumber), Version(kMagelightMin));

		const bool preferMl = want == "magelight" || want == "auto";
		if (preferMl && mlOk && RegisterMagelight()) g_kind = Kind::kMagelight;
		else if (g_prisma) g_kind = Kind::kPrisma;
		else if (want == "prisma" && mlOk && RegisterMagelight()) g_kind = Kind::kMagelight;  // asked for Prisma UI, only Magelight UI is there

		const auto installed = std::format("installed: Prisma UI {}, Magelight UI {}", g_prisma ? "yes" : "no", g_ml ? Version(g_ml->hostVersionNumber) : std::string("no"));
		if (g_kind == Kind::kNone) SKSE::log::info("UiHost: no page host ({}) - the counter, boards and notices are off", installed);
		else SKSE::log::info("UiHost: pages on {} (Host = {}, from {}; {})", Name(), want, from, installed);
		if (g_kind == Kind::kMagelight && want == "prisma") SKSE::log::info("UiHost: Prisma UI was asked for but is not installed");
		if (g_kind == Kind::kPrisma && want == "magelight") SKSE::log::info("UiHost: Magelight UI was asked for but is not usable");
	}

	Kind Active() { return g_kind; }

	const char* Name()
	{
		switch (g_kind) {
		case Kind::kPrisma: return "Prisma UI";
		case Kind::kMagelight: return "Magelight UI";
		default: return "none";
		}
	}

	bool ManagesControls() { return g_kind == Kind::kMagelight; }
	bool NativeVRText() { return g_kind == Kind::kMagelight; }

	Handle Create(const Spec& a_spec)
	{
		if (g_kind == Kind::kNone) return 0;
		if (g_count >= g_views.size()) {
			SKSE::log::error("UiHost: too many pages ({})", a_spec.name);
			return 0;
		}
		std::error_code ec;
		if (!std::filesystem::exists(std::string(kFolder) + a_spec.file, ec)) {
			SKSE::log::info("UiHost: {}{} missing - the {} page is off", kFolder, a_spec.file, a_spec.name);
			return 0;
		}
		auto& e = g_views[g_count];
		e.name = a_spec.name;
		e.textEntry = a_spec.textEntry;
		if (g_kind == Kind::kPrisma) {
			e.pv = g_prisma->CreateView((std::string("AdventurersGuild/") + a_spec.file).c_str());
			if (!g_prisma->IsValid(e.pv)) {
				SKSE::log::error("UiHost: Prisma UI could not make the {} page", a_spec.name);
				return 0;
			}
			g_prisma->Hide(e.pv);
			SKSE::log::info("UiHost: {} page on Prisma UI (view {}, order {})", a_spec.name, e.pv, g_prisma->GetOrder(e.pv));
		} else {
			const bool notice = a_spec.layer == Layer::kNotice;
			const auto path = PagePath(a_spec.file);
			ML::ViewDesc vd{};
			vd.size = sizeof(vd);
			vd.name = a_spec.name;
			vd.htmlPath = path.c_str();
			vd.anchor = ML::Anchor::TopLeft;
			vd.fullscreen = true;  // the pages lay themselves out and scale to the screen, as on Prisma UI
			vd.clickThrough = notice;
			vd.startVisible = false;
			vd.layer = notice ? ML::Layer::Popup : ML::Layer::Panel;  // a notice draws over an open panel
			if (const auto r = g_ml->CreateViewEx(g_mod, &vd, &e.mv); r != ML::Result::Ok) {
				SKSE::log::error("UiHost: Magelight UI could not make the {} page ({}: {})", a_spec.name, static_cast<int>(r), g_ml->GetLastErrorMessage(g_mod));
				e.mv = 0;
				return 0;
			}
			if (!notice) g_ml->SetEscapeCapture(e.mv, true);  // the page decides what Escape does (leave a text field, step back, close)
			if (a_spec.prepaint && g_ml->QueryCapability("prepaint") == 1) g_ml->SetViewPrepaint(e.mv, true);
			const auto& p = notice ? g_vrNotice : g_vrPanel;
			if (p.mode >= 0 || p.width > 0 || p.distance > 0 || p.height != 0) {
				ML::VRPlacementDesc vr{};
				vr.size = sizeof(vr);
				vr.mode = static_cast<std::uint8_t>(p.mode >= 0 ? p.mode : (notice ? 0 : 3));
				vr.widthMeters = p.width;
				vr.distanceMeters = p.distance;
				vr.heightOffset = p.height;
				const auto r = g_ml->SetViewVRPlacement(e.mv, &vr);
				SKSE::log::info("UiHost: VR placement of the {} page: mode {}, {} m wide, {} m away, {} m up ({})", a_spec.name, vr.mode, p.width, p.distance, p.height,
					r == ML::Result::Ok ? "ok" : std::to_string(static_cast<int>(r)));
			}
			SKSE::log::info("UiHost: {} page on Magelight UI (view {}, {})", a_spec.name, e.mv, path);
		}
		return ++g_count;
	}

	bool Valid(Handle a_view)
	{
		const auto* e = Get(a_view);
		if (!e) return false;
		if (g_kind == Kind::kPrisma) return e->pv && g_prisma->IsValid(e->pv);
		if (g_kind == Kind::kMagelight) return e->mv && g_ml->IsViewValid(e->mv);
		return false;
	}

	void Listen(Handle a_view, const char* a_name, Listener a_fn)
	{
		auto* e = Get(a_view);
		if (!e || !a_fn) return;
		if (g_slotCount >= g_slots.size()) {
			SKSE::log::error("UiHost: too many page calls ({}.{})", e->name, a_name);
			return;
		}
		const auto slot = g_slotCount++;
		g_slots[slot] = { a_fn, e->name, a_name };
		if (g_kind == Kind::kPrisma) g_prisma->RegisterJSListener(e->pv, a_name, kPrismaTramps[slot]);
		else if (const auto r = g_ml->RegisterJSListenerEx(e->mv, a_name, &MagelightTramp, reinterpret_cast<void*>(static_cast<std::uintptr_t>(slot))); r != ML::Result::Ok)
			SKSE::log::error("UiHost: Magelight UI refused the {} page's {} ({})", e->name, a_name, static_cast<int>(r));
	}

	void OnHostClosed(Handle a_view, Closed a_fn)
	{
		if (auto* e = Get(a_view)) e->closed = a_fn;
	}

	void Js(Handle a_view, std::string_view a_script)
	{
		auto* e = Get(a_view);
		if (!e) return;
		const std::string s(a_script);
		if (g_kind == Kind::kPrisma) g_prisma->Invoke(e->pv, s.c_str());
		else if (g_kind == Kind::kMagelight) g_ml->InvokeJS(e->mv, s.c_str());
	}

	void Show(Handle a_view)
	{
		auto* e = Get(a_view);
		if (!e) return;
		if (g_kind == Kind::kPrisma) g_prisma->Show(e->pv);
		else if (g_kind == Kind::kMagelight) g_ml->ShowView(e->mv, true);
	}

	void Hide(Handle a_view)
	{
		auto* e = Get(a_view);
		if (!e) return;
		if (g_kind == Kind::kPrisma) g_prisma->Hide(e->pv);
		else if (g_kind == Kind::kMagelight) g_ml->ShowView(e->mv, false);
	}

	bool Focus(Handle a_view)
	{
		auto* e = Get(a_view);
		if (!e) return false;
		if (g_kind == Kind::kPrisma) {
			if (!g_prisma->Focus(e->pv, true)) SKSE::log::info("UiHost: Prisma UI reported no focus for the {} page", e->name);
			return true;  // as before: the page stays open whatever Prisma UI answers
		}
		// Pause, as on Prisma UI. The engine's text-entry gate only where it is wanted: in VR it raises OpenComposite's
		// own keyboard on every open, and Magelight UI raises its keyboard for a focused field without it.
		std::uint32_t flags = ML::kUIModeFlagPause;
		if (!e->textEntry || REL::Module::IsVR()) flags |= ML::kUIModeFlagNoTextEntry;
		const auto r = g_ml->RequestUIMode(e->mv, flags);
		if (r != ML::Result::Ok) {
			SKSE::log::warn("UiHost: Magelight UI did not give the {} page input ({}{}{})", e->name, static_cast<int>(r), r == ML::Result::Busy ? ": another mod's page has it" : "",
				*g_ml->GetLastErrorMessage(g_mod) ? std::string(", ") + g_ml->GetLastErrorMessage(g_mod) : std::string());
			return false;
		}
		return true;
	}

	void Unfocus(Handle a_view)
	{
		auto* e = Get(a_view);
		if (!e) return;
		if (g_kind == Kind::kPrisma) {
			g_prisma->Unfocus(e->pv);
			return;
		}
		if (g_kind != Kind::kMagelight) return;
		// an entry still waiting is withdrawn (no events follow); one that ran is released, and its exit is ours
		if (g_ml->QueryCapability("uiModeCancel") == 1 && g_ml->CancelUIModeRequest(g_mod) == ML::Result::Ok) return;
		++e->releases;
		if (g_ml->ReleaseUIMode(g_mod) != ML::Result::Ok) --e->releases;  // it had none (Magelight UI already ended it)
	}

	void KeepAbove(Handle a_top, Handle a_below)
	{
		if (g_kind != Kind::kPrisma) return;  // Magelight UI: the notice layer is above the panels
		const auto* t = Get(a_top);
		const auto* b = Get(a_below);
		if (!t || !b || !g_prisma->IsValid(b->pv)) return;
		if (const int bo = g_prisma->GetOrder(b->pv); g_prisma->GetOrder(t->pv) <= bo) {
			g_prisma->SetOrder(t->pv, bo + 1);
			SKSE::log::info("UiHost: the {} page raised above the {} page ({} -> {})", t->name, b->name, bo, g_prisma->GetOrder(t->pv));
		}
	}
}
