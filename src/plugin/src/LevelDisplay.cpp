// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "LevelDisplay.h"

#include "Guild.h"
#include "RankCore.h"

#include <SimpleIni.h>
#include <cmath>
#include <functional>
#include <limits>
#include <thread>

namespace AG::LevelDisplay
{
	namespace
	{
		struct Target
		{
			const char*       menu;
			const char*       label;  // GFx path of the level-number TextField (nullptr = find it, see Locate)
			const char*       shift;  // optional clip to slide right by the label's growth (nullptr = none)
			std::atomic<bool> open{ false };
			double            origX{ std::numeric_limits<double>::quiet_NaN() };  // shift clip's untouched _x, per menu open
			std::string       foundLabel, foundShift;  // for label == nullptr: the paths Locate found
			// the label's untouched scale and position, per menu open (shrink mode puts them back before measuring)
			double            origXs{ std::numeric_limits<double>::quiet_NaN() }, origYs{ 100.0 }, origY{ 0.0 }, origW{ 0.0 };
			std::string       geom;                     // what Apply measured last (AG_Native.DebugLevelLabel)
			std::string       dump;                     // the strip's clips and their bounds (AG_Native.DebugLevelDump)
			bool              logged{ false };          // the first measurement of this menu has gone to the log
			int               tries{ 0 };               // Locate attempts this open (the bar may load a moment late)
		};

		// Paths taken from in-game GFx dumps on Skyrim VR 1.4.15 with SkyUI-VR. The Journal (System tab and the rest)
		// has the same bottom bar as the Tween menu, but its path was never dumped, so it is found by name at runtime.
		Target g_targets[]{
			{ "StatsMenu", "_root.StatsMenuBaseInstance.TopPlayerInfo.LevelNumberLabel", nullptr },
			{ "TweenMenu", "_root.TweenMenu_mc.BottomBarTweener_mc.BottomBar_mc.LevelNumberLabel",
				"_root.TweenMenu_mc.BottomBarTweener_mc.BottomBar_mc.LevelProgressBar" },
			{ "Journal Menu", nullptr, nullptr },
		};

		// Depth-first over the movie's display objects for one named "LevelNumberLabel". Records every text field
		// showing the bare level number as well, to name in the log if the name search fails.
		void Walk(const RE::GFxValue& a_obj, const std::string& a_path, const std::string& a_level, int a_depth, int& a_budget,
			std::string& a_named, std::vector<std::string>& a_byText)
		{
			if (a_depth > 10 || a_budget <= 0 || !a_named.empty()) return;
			std::vector<std::pair<std::string, RE::GFxValue>> kids;
			a_obj.VisitMembers([&](const char* a_name, const RE::GFxValue& a_val) {
				if (a_name && a_val.IsDisplayObject()) kids.emplace_back(a_name, a_val);
			});
			for (auto& [name, val] : kids) {
				if (--a_budget <= 0) return;
				if (name == "_parent" || name == "_root" || name.starts_with("_level")) continue;
				const auto path = a_path + "." + name;
				if (name == "LevelNumberLabel") { a_named = path; return; }
				RE::GFxValue text;
				if (a_byText.size() < 8 && val.GetMember("text", &text) && text.IsString() && a_level == text.GetString()) a_byText.push_back(path);
				Walk(val, path, a_level, a_depth + 1, a_budget, a_named, a_byText);
				if (!a_named.empty()) return;
			}
		}

		// Finds a target's label (and the progress bar beside it) once; logs what it found or the candidates.
		bool Locate(RE::GFxMovieView* a_mv, Target& a_t)
		{
			if (!a_t.foundLabel.empty()) return true;
			if (a_t.tries++ >= 8) return false;  // give up for this open; the log says why
			RE::GFxValue root;
			if (!a_mv->GetVariable(&root, "_root") || !root.IsObject()) return false;
			const auto level = std::to_string(RE::PlayerCharacter::GetSingleton()->GetLevel());
			int budget = 4000;
			std::string named;
			std::vector<std::string> byText;
			Walk(root, "_root", level, 0, budget, named, byText);
			if (named.empty()) {
				if (a_t.tries == 8) {
					std::string list;
					for (auto& p : byText) list += (list.empty() ? "" : ", ") + p;
					SKSE::log::warn("LevelDisplay: no LevelNumberLabel in {}; text fields showing the level: {}", a_t.menu, list.empty() ? "none" : list);
				}
				return false;
			}
			a_t.foundLabel = named;
			const auto parent = named.substr(0, named.rfind('.'));
			RE::GFxValue bar;
			if (a_mv->GetVariable(&bar, (parent + ".LevelProgressBar").c_str()) && bar.IsObject()) a_t.foundShift = parent + ".LevelProgressBar";
			SKSE::log::info("LevelDisplay: {} level label at {}{}", a_t.menu, named, a_t.foundShift.empty() ? "" : " (with LevelProgressBar)");
			return true;
		}

		std::atomic<bool> g_enabled{ true };
		// How "12 (D)" is given room. kShift: widen the field and slide the progress bar right (SkyUI's own bottom bar,
		// where the bar simply follows the number). kShrink: scale the text down to end before the bar, moving nothing
		// (menu skins that draw a fixed box around the level, where a wider text runs under the next box).
		enum : int { kAuto = 0, kShift = 1, kShrink = 2 };
		std::atomic<int>    g_fit{ kAuto };
		std::atomic<double> g_margin{ 10.0 };  // shrink: the gap kept between the text and the bar
		std::atomic<double> g_avail{ -1.0 };   // shrink, DevBench only: the room for the text, overriding what is measured

		void Apply(Target& a_t)
		{
			if (!g_enabled.load()) return;
			const int rank = Guild::Rank();  // earned guild rank; nothing to show before registering
			if (rank < 0) return;
			auto* ui = RE::UI::GetSingleton();
			auto* pc = RE::PlayerCharacter::GetSingleton();
			if (!ui || !pc) return;
			auto mv = ui->GetMovieView(a_t.menu);
			if (!mv) return;
			if (!a_t.label && !Locate(mv.get(), a_t)) return;
			const char* labelPath = a_t.label ? a_t.label : a_t.foundLabel.c_str();
			const char* shiftPath = a_t.label ? a_t.shift : (a_t.foundShift.empty() ? nullptr : a_t.foundShift.c_str());

			RE::GFxValue label;
			if (!mv->GetVariable(&label, labelPath) || !label.IsObject()) return;

			RE::GFxValue text;
			if (!label.GetMember("text", &text) || !text.IsString()) return;
			const std::string cur = text.GetString();
			if (cur.empty() || cur.find('(') != std::string::npos) return;  // nothing to show yet, or already done

			auto num = [](RE::GFxValue& a_obj, const char* a_member, double a_default) {
				RE::GFxValue v;
				return a_obj.GetMember(a_member, &v) && v.IsNumber() ? v.GetNumber() : a_default;
			};
			// The label and the bar as the menu made them. Some menus keep their movie between opens (the VR Journal
			// does), so "what it is now" may already carry our changes: the untouched values are written onto the clips
			// the first time we see them and read back from there. A rebuilt movie has no such members and is measured anew.
			auto orig = [&](RE::GFxValue& a_obj, const char* a_key, const char* a_member, double a_default) {
				RE::GFxValue v;
				if (a_obj.GetMember(a_key, &v) && v.IsNumber()) return v.GetNumber();
				const double now = num(a_obj, a_member, a_default);
				a_obj.SetMember(a_key, RE::GFxValue(now));
				return now;
			};
			a_t.origXs = orig(label, "agXs", "_xscale", 100.0);
			a_t.origYs = orig(label, "agYs", "_yscale", 100.0);
			a_t.origY = orig(label, "agY", "_y", 0.0);
			a_t.origW = orig(label, "agW", "_width", 0.0);
			RE::GFxValue bar;
			const bool   haveBar = shiftPath && mv->GetVariable(&bar, shiftPath) && bar.IsObject();
			if (haveBar) a_t.origX = orig(bar, "agX", "_x", 0.0);
			// the height as the menu made it, not as it is now: on a reopen (or when the menu rewrites the number) the field
			// still carries our scale, and centring on that shrunk height lifts the number off the caption's line
			const double labelX = orig(label, "agLX", "_x", 0.0), before = num(label, "textWidth", 0.0), height = orig(label, "agH", "_height", 0.0);
			const std::string labelStr = labelPath;
			RE::GFxValue      parent;
			const bool        haveParent = mv->GetVariable(&parent, labelStr.substr(0, labelStr.rfind('.')).c_str()) && parent.IsObject();
			// the caption beside the number ("LEVEL"): the text fields left of the label in the same strip
			std::vector<RE::GFxValue> captions;
			if (haveParent)
				parent.VisitMembers([&](const char* a_name, const RE::GFxValue& a_val) {
					RE::GFxValue t, x;
					if (a_name && a_val.IsDisplayObject() && std::string_view(a_name) != "LevelNumberLabel" && a_val.GetMember("text", &t) && t.IsString() &&
						a_val.GetMember("_x", &x) && x.IsNumber() && x.GetNumber() < labelX)
						captions.push_back(a_val);
				});
			// caption and number move together by a_dx from where the menu put them
			auto place = [&](double a_dx) {
				label.SetMember("_x", RE::GFxValue(labelX + a_dx));
				for (auto& c : captions) c.SetMember("_x", RE::GFxValue(orig(c, "agCX", "_x", 0.0) + a_dx));
			};

			// the field is sized for a bare number; make room so "12 (E)" is not clipped by the field itself
			if (a_t.origW < 90.0) label.SetMember("_width", RE::GFxValue(90.0));
			const auto out = std::format("{} ({})", cur, Letter(rank));
			label.SetMember("text", RE::GFxValue(out.c_str()));
			const double after = num(label, "textWidth", 0.0);

			// Where the bar's artwork really starts, in the strip's coordinates, with the bar at its untouched position
			// (a clip's _x is only its origin: measured on a "paper journal" skin, the bar clip's art starts 180 units
			// LEFT of the label, because the clip carries the whole framed meter).
			double barLeft = std::numeric_limits<double>::quiet_NaN();
			if (haveBar && haveParent) {
				RE::GFxValue b, arg[1]{ parent };
				if (bar.Invoke("getBounds", &b, arg, 1) && b.IsObject()) barLeft = num(b, "xMin", barLeft) - (num(bar, "_x", a_t.origX) - a_t.origX);
			}
			// auto: a bar whose art starts after the number follows it and can be slid aside (SkyUI's bottom bar); one
			// whose art starts at or behind the label sits in a frame of its own, so the text has to fit the field the
			// skin made - sliding that bar only pushes the meter out of its frame.
			const bool framed = haveBar && !std::isnan(barLeft) && barLeft < labelX + before;
			const int  mode = g_fit.load() == kAuto ? (framed ? kShrink : kShift) : g_fit.load();
			double     scale = 1.0;
			if (mode == kShrink) {
				// scale the text to end where there is room, and move nothing: up to a bar that follows the number, else
				// the skin's own field plus its gutters (measured: a 31-unit field shows text for 36 units)
				const double need = after + 6.0;
				const double avail = g_avail.load() > 0.0 ? g_avail.load()
									: haveBar && !std::isnan(barLeft) && barLeft > labelX + 8.0 ? barLeft - labelX - g_margin.load() : a_t.origW + 5.0;
				label.SetMember("_width", RE::GFxValue(std::max(need, a_t.origW)));
				if (avail > 8.0 && need > avail) scale = std::clamp(avail / need, 0.55, 1.0);
				label.SetMember("_xscale", RE::GFxValue(a_t.origXs * scale));
				label.SetMember("_yscale", RE::GFxValue(a_t.origYs * scale));
				label.SetMember("_y", RE::GFxValue(a_t.origY + height * (1.0 - scale) * 0.5));  // keep it on the same line
				if (haveBar) bar.SetMember("_x", RE::GFxValue(a_t.origX));
				// The skin centred "LEVEL 12" in its box; the number grew to the right only. Move the caption and the
				// number left together by half of what was added, so the pair is centred again (measured: 42 px of
				// margin on the left against 17 on the right without this).
				place(-std::max(0.0, after * scale - before) * 0.5);
			} else {
				place(0.0);
				if (haveBar) {
					double delta = after - before;
					if (delta < 1.0) delta = 30.0;  // layout not refreshed yet: fall back to a typical "(X)" width
					bar.SetMember("_x", RE::GFxValue(a_t.origX + delta));
				}
			}
			a_t.geom = std::format("{}: mode {} label x {:.1f} width {:.1f} height {:.1f} text {:.1f}->{:.1f} scale {:.2f}; bar {} x {:.1f} art from {:.1f}", a_t.menu,
				mode == kShrink ? "shrink" : "shift", labelX, a_t.origW, height, before, after, scale, haveBar ? "yes" : "no", haveBar ? a_t.origX : 0.0, barLeft);
			if (!a_t.logged) {  // once per menu per session: which way this menu's layout went
				a_t.logged = true;
				SKSE::log::info("LevelDisplay: {}", a_t.geom);
			}
		}

		// Every clip in the label's strip, and inside the bar clip, with where its artwork really sits (getBounds in the
		// strip's own coordinates): a clip's _x is only its origin, and a skin's box may live anywhere.
		void Dump(Target& a_t)
		{
			auto* ui = RE::UI::GetSingleton();
			auto  mv = ui ? ui->GetMovieView(a_t.menu) : nullptr;
			const std::string labelPath = a_t.label ? a_t.label : a_t.foundLabel;
			if (!mv || labelPath.empty()) return;
			const auto   parentPath = labelPath.substr(0, labelPath.rfind('.'));
			RE::GFxValue parent;
			if (!mv->GetVariable(&parent, parentPath.c_str()) || !parent.IsObject()) return;
			auto num = [](const RE::GFxValue& a_obj, const char* a_member) {
				RE::GFxValue v;
				return a_obj.GetMember(a_member, &v) && v.IsNumber() ? v.GetNumber() : std::numeric_limits<double>::quiet_NaN();
			};
			std::string out = std::string(a_t.menu) + " " + parentPath + ":";
			std::function<void(RE::GFxValue&, const std::string&, int)> walk = [&](RE::GFxValue& a_obj, const std::string& a_prefix, int a_depth) {
				std::vector<std::pair<std::string, RE::GFxValue>> kids;
				a_obj.VisitMembers([&](const char* a_name, const RE::GFxValue& a_val) {
					if (a_name && a_val.IsDisplayObject() && std::string_view(a_name) != "_parent" && std::string_view(a_name) != "_root") kids.emplace_back(a_name, a_val);
				});
				for (auto& [name, val] : kids) {
					RE::GFxValue b, arg[1]{ parent };
					double       x0 = std::numeric_limits<double>::quiet_NaN(), x1 = x0;
					if (val.Invoke("getBounds", &b, arg, 1) && b.IsObject()) { x0 = num(b, "xMin"); x1 = num(b, "xMax"); }
					out += std::format(" [{}{} x {:.1f} w {:.1f} bounds {:.1f}..{:.1f} vis {}]", a_prefix, name, num(val, "_x"), num(val, "_width"), x0, x1,
						num(val, "_alpha") > 0.0 ? 1 : 0);
					if (a_depth < 2 && out.size() < 3000) walk(val, a_prefix + name + ".", a_depth + 1);
				}
			};
			walk(parent, "", 0);
			a_t.dump = out;
		}

		// Puts an already-labelled field back to the bare number so Apply measures and writes it afresh.
		void Reset(Target& a_t)
		{
			auto* ui = RE::UI::GetSingleton();
			auto  mv = ui ? ui->GetMovieView(a_t.menu) : nullptr;
			const char* labelPath = a_t.label ? a_t.label : a_t.foundLabel.c_str();
			RE::GFxValue label, text;
			if (!mv || !*labelPath || !mv->GetVariable(&label, labelPath) || !label.IsObject()) return;
			if (!label.GetMember("text", &text) || !text.IsString()) return;
			std::string cur = text.GetString();
			if (const auto at = cur.find(" ("); at != std::string::npos) label.SetMember("text", RE::GFxValue(cur.substr(0, at).c_str()));
			RE::GFxValue v;
			if (label.GetMember("agXs", &v) && v.IsNumber()) label.SetMember("_xscale", v);
			if (label.GetMember("agYs", &v) && v.IsNumber()) label.SetMember("_yscale", v);
			if (label.GetMember("agY", &v) && v.IsNumber()) label.SetMember("_y", v);
			if (label.GetMember("agLX", &v) && v.IsNumber()) label.SetMember("_x", v);
			const std::string labelStr = labelPath;
			RE::GFxValue      parent;
			if (mv->GetVariable(&parent, labelStr.substr(0, labelStr.rfind('.')).c_str()) && parent.IsObject()) {
				std::vector<RE::GFxValue> moved;
				parent.VisitMembers([&](const char* a_name, const RE::GFxValue& a_val) {
					RE::GFxValue cx;
					if (a_name && a_val.IsDisplayObject() && a_val.GetMember("agCX", &cx) && cx.IsNumber()) moved.push_back(a_val);
				});
				for (auto& c : moved) {
					RE::GFxValue cx;
					if (c.GetMember("agCX", &cx)) c.SetMember("_x", cx);
				}
			}
			const char*  shiftPath = a_t.label ? a_t.shift : (a_t.foundShift.empty() ? nullptr : a_t.foundShift.c_str());
			RE::GFxValue bar;
			if (shiftPath && mv->GetVariable(&bar, shiftPath) && bar.IsObject() && bar.GetMember("agX", &v) && v.IsNumber()) bar.SetMember("_x", v);
		}

		class Sink : public RE::BSTEventSink<RE::MenuOpenCloseEvent>
		{
		public:
			static Sink* Get()
			{
				static Sink s;
				return std::addressof(s);
			}

			RE::BSEventNotifyControl ProcessEvent(const RE::MenuOpenCloseEvent* e, RE::BSTEventSource<RE::MenuOpenCloseEvent>*) override
			{
				if (!e) return RE::BSEventNotifyControl::kContinue;
				for (auto& t : g_targets) {
					if (e->menuName == t.menu) {
						t.open = e->opening;
						if (e->opening) {
							t.origX = std::numeric_limits<double>::quiet_NaN();
							t.origXs = std::numeric_limits<double>::quiet_NaN();
							t.tries = 0;
						}
					}
				}
				return RE::BSEventNotifyControl::kContinue;
			}
		};
	}

	bool Enabled() { return g_enabled.load(); }

	std::string DebugDump(float a_avail)
	{
		g_avail = a_avail;
		std::string out = std::format("avail override {:.1f}", g_avail.load());
		for (auto& t : g_targets) {
			if (!t.open.load()) continue;
			out += " | " + (t.dump.empty() ? std::string(t.menu) + ": call again for the dump" : t.dump);  // the dump made by the previous call
			SKSE::GetTaskInterface()->AddUITask([&t] { Dump(t); Reset(t); Apply(t); });
		}
		return out;
	}

	std::string DebugFit(int a_mode, float a_margin)
	{
		if (a_mode >= kAuto && a_mode <= kShrink) g_fit = a_mode;
		if (a_margin >= 0.0f) g_margin = a_margin;
		std::string out = std::format("fit mode {} margin {:.0f}", g_fit.load(), g_margin.load());
		for (auto& t : g_targets) {
			if (!t.open.load()) continue;
			out += " | " + (t.geom.empty() ? std::string(t.menu) + ": not measured yet" : t.geom);  // the measurement before this call
			SKSE::GetTaskInterface()->AddUITask([&t] { Reset(t); Apply(t); });
		}
		return out;
	}

	void SetEnabled(bool a_on)
	{
		g_enabled = a_on;
		if (!a_on) {
			for (auto& t : g_targets)
				if (t.open.load()) SKSE::GetTaskInterface()->AddUITask([&t] { Reset(t); });  // the bare level, the bar where the menu put it
		}
		if (a_on) {
			// re-apply on the next open rather than immediately: Apply() only writes an untouched
			// (no "(" yet) label, and toggling back on while a menu is open would otherwise wait for it
			// to reopen. Nudge every currently-open target once.
			for (auto& t : g_targets) {
				if (t.open.load()) SKSE::GetTaskInterface()->AddUITask([&t] { Apply(t); });
			}
		}
	}

	void Register()
	{
		CSimpleIniA ini;
		ini.SetUnicode();
		if (ini.LoadFile("Data/SKSE/Plugins/AdventurersGuild.ini") >= 0) {
			g_enabled = ini.GetBoolValue("System", "ShowRankLabels", true);
			const std::string fit = ini.GetValue("Debug", "LevelRankFit", "auto");
			g_fit = fit == "shrink" ? kShrink : fit == "shift" ? kShift : kAuto;
		}
		if (auto* ui = RE::UI::GetSingleton()) ui->AddEventSink<RE::MenuOpenCloseEvent>(Sink::Get());

		// Menus rewrite their level label on open / level-up, so keep re-applying while one is open.
		std::thread([] {
			for (;;) {
				std::this_thread::sleep_for(std::chrono::milliseconds(250));
				for (auto& t : g_targets) {
					if (t.open.load()) SKSE::GetTaskInterface()->AddUITask([&t] { Apply(t); });
				}
			}
		}).detach();
		SKSE::log::info("LevelDisplay active");
	}
}
