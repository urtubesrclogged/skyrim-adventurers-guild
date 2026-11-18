// The Guild Hall's outside, placed and kept by AG's DLL, only when the hall's plugin is loaded (AG::GuildHall::Loaded()).
// A new hall build needs no manual steps: deploy, launch, load.
// - The hall comes from Data/SKSE/Plugins/AdventurersGuild/Hall/hall2.json (written by the hall's build with the plugin): every
//   piece's record, position, angle and scale, and the boxes round each site where trees and rocks are hidden.
// - What it placed and what it hid are kept in AG's co-save (its HALL record), with the layout's version. On load, a save holding an
//   older version (or none) is rebuilt: old pieces deleted, hidden refs shown again, the new hall placed and hidden round.
//   So is one whose hall lacks pieces the layout can place now, or has any anywhere but outdoors in Tamriel.
// - It is placed only with the player in Tamriel and every cell a piece stands in attached (a save made indoors waits).
// - (2026-11-17) The site is the installed hall's (its layout's "sites": place, map marker, window glow, Helios region): one hall
//   build per site, chosen in the installer. A save whose hall stood at another site has it taken down there, every piece of
//   ours found even when the co-save no longer lists it, and what that site hid shown again as its cells load. With no hall
//   installed, a save that had one gets its hidden references and map marker back the same way.
// - Once the hall stands, the navmesh patches are stitched in (Nav::AutoApply), and again whenever its cells load.
#include "hall.h"

#include "../Guild.h"
#include "../GuildHall.h"
#include "../Loc.h"

#include <nlohmann/json.hpp>

#include <cmath>
#include <fstream>
#include <mutex>
#include <unordered_set>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <set>
#include <thread>
#include <unordered_map>

namespace Hall
{
	namespace
	{
		using Json = nlohmann::json;

		constexpr std::uint32_t kRecord = 'HALL', kVersion = 3;  // a record in AG's co-save (2: one DLL, no AGHall2 takeover. 3: the site, and what is still to show)
		constexpr const char*   kLayoutPath = "Data/SKSE/Plugins/AdventurersGuild/Hall/hall2.json";
		constexpr const char*   kPlugin = "AdventurersGuild - Guild Hall.esp";
		constexpr RE::FormID    kNightGlow = 0x0008277B;  // FXLightRegionInvertWindowWhiterun, the region vanilla's window glow follows, in Skyrim.esm
		constexpr RE::FormID    kTamriel = 0x3C;    // the worldspace every site stands in
		constexpr float         kPi = 3.14159265358979f, kCellSize = 4096.0f;
		// The version a save's hall is checked against is the layout's plus this: changing how the hall is placed or
		// hidden rebuilds it on load, like a new layout does. 2: rocks sized by their object bounds, as Papyrus does.
		constexpr const char* kRules = "rules4";  // 3: persistent references searched too. 4: flora on a hidden host goes too

		struct Piece
		{
			RE::FormID   base = 0;
			std::string  rec;
			RE::NiPoint3 pos;
			float        angle = 0, scale = 1;
			int          site = 0;
		};
		struct Box
		{
			float x0, x1, y0, y1;
			int   site, kind;
		};
		struct Site
		{
			int   id;
			float x, y, yaw;
			float z = 0.0f;   // the floor: the height of the site's first piece (the hall's body), where the searches round it centre
			int          place = 1;      // AG_GuildHallSiteGlobal: 1 Riverwood, 2 Solitude (a layout from before 2026-11-17: Riverwood)
			bool         hasMarker = false;
			RE::NiPoint3 marker;
			float        markerFacing = 0.0f;
			std::string  glow, helios;   // "plugin|0xID": the light region the windows' glow follows; the Helios sky region
		};
		struct Layout
		{
			bool              ok = false;
			std::string       error, version;
			std::vector<Site> sites;
			std::vector<Piece> pieces;
			std::vector<Box>  boxes;
		};

		// the co-save's part: what stands in the world because of us
		std::mutex                 g_lock;
		std::string                g_version;  // the layout the placed hall was built from; empty: none placed
		std::vector<RE::FormID>    g_placed;   // the pieces (created references)
		std::vector<RE::FormID>    g_hidden;   // vanilla references we disabled
		std::vector<RE::FormID>    g_toShow;   // hidden by a hall that no longer stands there: shown again when their cells load
		float                      g_siteX = 0, g_siteY = 0;   // where the placed hall stands (its layout's first site)
		bool                       g_swept = false;   // this game's sweep for pieces of ours the co-save does not list is done
		bool                       g_active = false;  // the hall's plugin is loaded: everything here waits on it
		bool                       g_inGame = false;  // a save is loaded (or a new game started) and the co-save read
		bool                       g_pending = false;  // the hall still has to be checked against the layout

		std::string Hex(std::uint32_t a_v) { return std::format("{:08X}", a_v); }

		RE::FormID Resolve(const std::string& a_rec)
		{
			const auto bar = a_rec.find('|');
			if (bar == std::string::npos) return 0;
			auto* dh = RE::TESDataHandler::GetSingleton();
			auto* f = dh ? dh->LookupForm(static_cast<RE::FormID>(std::stoul(a_rec.substr(bar + 1), nullptr, 16)), a_rec.substr(0, bar)) : nullptr;
			return f ? f->GetFormID() : 0;
		}

		Layout Load()
		{
			Layout        L;
			std::ifstream in(kLayoutPath);
			if (!in) {
				L.error = std::format("no layout at {}", kLayoutPath);
				return L;
			}
			try {
				const auto j = Json::parse(in);
				L.version = j["version"].get<std::string>() + "+" + kRules;
				for (const auto& s : j["sites"]) {
					Site t{ s["site"].get<int>(), s["x"].get<float>(), s["y"].get<float>(), s["yaw"].get<float>() };
					t.place = s.value("place", 1);
					if (s.contains("marker") && s["marker"].is_array() && s["marker"].size() == 4) {
						t.hasMarker = true;
						t.marker = { s["marker"][0].get<float>(), s["marker"][1].get<float>(), s["marker"][2].get<float>() };
						t.markerFacing = s["marker"][3].get<float>();
					}
					t.glow = s.value("glow", std::string());
					t.helios = s.value("helios", std::string());
					L.sites.push_back(std::move(t));
				}
				for (const auto& p : j["pieces"]) {
					Piece q;
					q.rec = p["b"].get<std::string>();
					q.base = Resolve(q.rec);
					q.pos = { p["x"].get<float>(), p["y"].get<float>(), p["z"].get<float>() };
					q.angle = p["a"].get<float>();
					q.scale = p["s"].get<float>();
					q.site = p["site"].get<int>();
					L.pieces.push_back(std::move(q));
				}
				for (const auto& b : j["clear"])
					L.boxes.push_back({ b["x0"].get<float>(), b["x1"].get<float>(), b["y0"].get<float>(), b["y1"].get<float>(), b["site"].get<int>(), b["kind"].get<int>() });
				// each site's height: its first piece's (the searches round a site measure in 3D: centred at 0 they missed every
				// reference of a site whose floor is far from 0, as site A's at -4144)
				for (auto& s : L.sites)
					for (const auto& q : L.pieces)
						if (q.site == s.id) {
							s.z = q.pos.z;
							break;
						}
				L.ok = true;
			} catch (const std::exception& e) {
				L.error = std::format("layout unreadable: {}", e.what());
			}
			return L;
		}

		// ---------------------------------------------------------------- the world side

		RE::TESObjectREFR* Ref(RE::FormID a_id)
		{
			auto* r = RE::TESForm::LookupByID<RE::TESObjectREFR>(a_id);
			return r && !r->IsDeleted() ? r : nullptr;
		}

		void DeletePiece(RE::TESObjectREFR* a_ref)
		{
			a_ref->Disable();
			a_ref->SetDelete(true);
		}

		// The attached exterior cell of Tamriel that holds a point, from the loaded grid (as Nav's EngineAt finds one). Not
		// TES::GetCell: with the player indoors it answered with the interior for the hall's position (MGO, 2026-10-24: a
		// save in the Bannered Mare had all 202 pieces built inside the inn, where the hall then counted as standing).
		RE::TESObjectCELL* OutdoorCell(const RE::NiPoint3& a_pos)
		{
			auto* tes = RE::TES::GetSingleton();
			auto* pc = RE::PlayerCharacter::GetSingleton();
			auto* ws = pc ? pc->GetWorldspace() : nullptr;
			if (!tes || !tes->gridCells || !ws || ws->GetFormID() != kTamriel) return nullptr;
			const auto cx = static_cast<std::int32_t>(std::floor(a_pos.x / kCellSize)), cy = static_cast<std::int32_t>(std::floor(a_pos.y / kCellSize));
			for (std::uint32_t gx = 0; gx < tes->gridCells->length; ++gx)
				for (std::uint32_t gy = 0; gy < tes->gridCells->length; ++gy)
					if (auto* c = tes->gridCells->GetCell(gx, gy); c && c->IsAttached() && c->IsExteriorCell() && c->GetCoordinates() &&
																   c->GetCoordinates()->cellX == cx && c->GetCoordinates()->cellY == cy)
						return c;
			return nullptr;
		}

		// the hall is placed only with every cell a piece stands in attached, in Tamriel, around the player
		bool Loaded(const Layout& a_l)
		{
			for (const auto& p : a_l.pieces)
				if (!OutdoorCell(p.pos)) return false;
			return !a_l.pieces.empty();
		}

		// as Papyrus GetWidth/GetLength measure it: the base record's object bounds (OBND) times the reference's scale.
		// (The reference's GetBoundMin/Max read larger: the big rock ledge at the stair's foot failed the "small pieces"
		// test with them and stayed, where AGHall2 had hidden it.)
		float Size(RE::TESObjectREFR* a_ref)
		{
			auto* base = a_ref->GetBaseObject();
			auto* bo = base ? base->As<RE::TESBoundObject>() : nullptr;
			if (!bo) return 0.0f;
			const auto& b = bo->boundData;
			return std::max(static_cast<float>(b.boundMax.x - b.boundMin.x), static_cast<float>(b.boundMax.y - b.boundMin.y)) * a_ref->GetScale();
		}

		std::string ModelOf(RE::TESObjectREFR* a_ref)
		{
			auto* base = a_ref->GetBaseObject();
			auto* model = base ? base->As<RE::TESModel>() : nullptr;
			return model && model->GetModel() ? model->GetModel() : "?";
		}

		bool IsLandscapeClutter(RE::TESObjectREFR* a_ref)
		{
			auto* base = a_ref->GetBaseObject();
			auto* model = base ? base->As<RE::TESModel>() : nullptr;
			if (!model || !model->GetModel()) return false;
			std::string m = model->GetModel();
			std::transform(m.begin(), m.end(), m.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
			for (const char* k : { "landscape\\rocks", "landscape\\boulder", "landscape\\trees", "landscape\\dirtcliffs" })
				if (m.find(k) != std::string::npos) return true;
			return false;
		}

		// Every reference within a radius: the attached cells' own, and the worldspace's persistent cell, which holds
		// persistent references wherever they stand (PO3's search, which AGHall2 used, sees those too; a grid-only search
		// missed the dirt cliff cap at the stair's foot).
		template <class F>
		void ForEachLoadedRef(const RE::NiPoint3& a_origin, float a_radius, F&& a_fn)
		{
			auto* tes = RE::TES::GetSingleton();
			auto* grid = tes ? tes->gridCells : nullptr;
			if (!grid || !grid->cells) return;
			std::unordered_set<RE::FormID> seen;  // the two lists can both hold a reference: each is visited once
			auto visit = [&](RE::TESObjectREFR* r) {
				if (r && seen.insert(r->GetFormID()).second) a_fn(r);
				return RE::BSContainer::ForEachResult::kContinue;
			};
			for (std::uint32_t gx = 0; gx < grid->length; ++gx)
				for (std::uint32_t gy = 0; gy < grid->length; ++gy)
					if (auto* cell = grid->GetCell(gx, gy); cell && cell->IsAttached()) cell->ForEachReferenceInRange(a_origin, a_radius, visit);
			auto* pc = RE::PlayerCharacter::GetSingleton();
			if (auto* ws = pc ? pc->GetWorldspace() : nullptr; ws && ws->persistentCell) ws->persistentCell->ForEachReferenceInRange(a_origin, a_radius, visit);
		}

		// ---- the hide pass. AGHall2.HideTrees, natively: trees in the site's boxes; landscape rocks, boulders, stumps and logs in
		// them (only small ones in a "trees and small pieces" box); whatever stood more than 40 above the land on a hidden rock; and
		// what a mod set on any hidden support. One sweep of the loaded references near the site answers every question from a list
		// (walking the cells again for each support and rider took about 110 ms a pass on MGO; the sweep, about 4 ms).
		struct NearRef
		{
			RE::TESObjectREFR*  r;
			RE::FormID          id;
			RE::NiPoint3        p;
			RE::TESBoundObject* base;
			bool                off;   // disabled when swept
		};
		int Hide(const Layout& a_l, const Site& a_s)
		{
			// (in testing, the dirt cliff at the stair's foot and a stump on the terrace stood again after a rebuild,
			// though the save had them hidden: a rebuild re-enabled every hidden ref and hid them again at once, and the queued enable
			// landed after the disable. Rebuilds no longer re-show anything; and a ref the save says is hidden but stands enabled is
			// disabled again here, on every pass, which mends a save that rebuild left so)
			int         mended = 0;
			std::string which;
			for (auto id : g_hidden)
				if (auto* r = Ref(id); r && !r->IsDisabled()) {
					auto*       base = r->GetBaseObject();
					const auto  p = r->GetPosition();
					const auto* file = r->GetFile(0);
					which += std::format("{}{:08X} ({}, base {:08X}{}, {}, at {:.0f} {:.0f} {:.0f})", which.empty() ? "" : "; ", id,
						file ? file->GetFilename() : std::string_view("created"), base ? base->GetFormID() : 0u,
						base && (base->GetFormFlags() & 0x02000000) ? " obstacle" : "", base ? RE::FormTypeToString(base->GetFormType()) : std::string_view("?"), p.x, p.y, p.z);
					r->Disable(), ++mended;
				}
			if (mended) SKSE::log::info("Hall: {} ref(s) the save had hidden stood enabled: hidden again: {}", mended, which);
			std::unordered_set<RE::FormID> ours(g_placed.begin(), g_placed.end());
			std::unordered_set<RE::FormID> hidden(g_hidden.begin(), g_hidden.end());
			// one sweep: everything the searches below reach (the site's 3500, a support's half-size, a rider's 64), the attached
			// cells' references and the worldspace's persistent ones
			std::vector<NearRef> swept;
			ForEachLoadedRef(RE::NiPoint3(a_s.x, a_s.y, a_s.z), 6000.0f, [&](RE::TESObjectREFR* r) {
				auto* b = r->GetBaseObject();
				swept.push_back({ r, r->GetFormID(), r->GetPosition(), b ? b->As<RE::TESBoundObject>() : nullptr, r->IsDisabled() });
			});
			auto within = [&](const RE::NiPoint3& a_o, float a_radius, auto&& a_fn) {   // (as ForEachReferenceInRange: by distance in 3D)
				const float r2 = a_radius * a_radius;
				for (auto& w : swept)
					if (a_o.GetSquaredDistance(w.p) <= r2) a_fn(w);
			};
			std::unordered_map<RE::TESBoundObject*, bool> clutterOf, markerOf;
			auto clutter = [&](NearRef& w) {
				auto it = clutterOf.find(w.base);
				if (it != clutterOf.end()) return it->second;
				return clutterOf[w.base] = IsLandscapeClutter(w.r);
			};
			auto marker = [&](NearRef& w) {
				auto it = markerOf.find(w.base);
				if (it != markerOf.end()) return it->second;
				auto* m = w.base->As<RE::TESModel>();
				bool  is = !m || !m->GetModel() || !*m->GetModel();
				if (!is) {
					std::string path = m->GetModel();
					std::ranges::transform(path, path.begin(), [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
					is = path.starts_with("marker") || path.find("\\marker") != std::string::npos || path.find("/marker") != std::string::npos;
				}
				return markerOf[w.base] = is;
			};
			auto off = [&](const NearRef& w) { return w.off || ours.contains(w.id) || hidden.contains(w.id); };
			auto hide = [&](NearRef& w) {
				if (!hidden.insert(w.id).second) return false;
				w.r->Disable();
				g_hidden.push_back(w.id);
				return true;
			};
			const float a = a_s.yaw * kPi / 180.0f, c = std::cos(a), s = std::sin(a);
			// the box a reference stands in (-1: none); a rock in a "trees and small pieces" box (kind 0) only if small
			auto boxOf = [&](const RE::NiPoint3& p) {
				const float dx = p.x - a_s.x, dy = p.y - a_s.y, lx = dx * c - dy * s, ly = dx * s + dy * c;  // world -> layout frame
				int         best = -1;
				for (const auto& b : a_l.boxes)
					if (b.site == a_s.id && lx >= b.x0 && lx <= b.x1 && ly >= b.y0 && ly <= b.y1) best = std::max(best, b.kind);
				return best;
			};
			std::vector<NearRef*> trees, rocks;
			int                   kept = 0;
			within(RE::NiPoint3(a_s.x, a_s.y, a_s.z), 3500.0f, [&](NearRef& w) {
				if (!w.base || off(w)) return;
				if (w.base->Is(RE::FormType::Tree)) {
					if (boxOf(w.p) >= 0) trees.push_back(&w);
				} else if (w.base->Is(RE::FormType::Static) && clutter(w)) {
					const int k = boxOf(w.p);
					if (k < 0) return;
					if (k == 1 || Size(w.r) <= 1000.0f) rocks.push_back(&w);
					else ++kept;                                // too big for a "trees and small pieces" box: ground
				}
			});
			// Vanilla lays the fungus on a log or a stump as its own FLOR reference at the host's origin
			// (TreePineForestLog01 + TreePineForestLog01MoraTapinella): left behind, it hangs where the log was.
			auto companions = [&](const NearRef& h) {
				std::vector<NearRef*> with;
				within(h.p, 64.0f, [&](NearRef& d) {
					if (!d.base || d.id == h.id || !d.base->Is(RE::FormType::Flora) || off(d)) return;
					if (std::hypot(d.p.x - h.p.x, d.p.y - h.p.y) < 8.0f && std::abs(d.p.z - h.p.z) < 64.0f) with.push_back(&d);
				});
				int k = 0;
				for (auto* d : with) k += hide(*d);
				return k;
			};
			auto* tes = RE::TES::GetSingleton();
			auto  aboveLand = [&](const NearRef& d) {
				float land = 0.0f;
				return tes && tes->GetLandHeight(d.p, land) && d.p.z > land + 40.0f;
			};
			int n = 0, onTop = 0, flora = 0;
			for (auto* t : trees) {
				n += hide(*t);
				flora += companions(*t);
			}
			for (auto* rock : rocks) {
				n += hide(*rock);
				flora += companions(*rock);
				std::vector<NearRef*> riders;     // what stood on it: trees, flora, small rocks over 40 above the land
				within(rock->p, Size(rock->r) / 2.0f, [&](NearRef& d) {
					if (!d.base || d.id == rock->id || off(d)) return;
					if (!(d.base->Is(RE::FormType::Tree) || d.base->Is(RE::FormType::Flora) || (d.base->Is(RE::FormType::Static) && clutter(d) && Size(d.r) <= 600.0f))) return;
					if (aboveLand(d)) riders.push_back(&d);
				});
				for (auto* d : riders) onTop += hide(*d);
			}
			// What a mod set on a hidden support (a brazier bowl on a rock, with its fire and its light at the same spot) would be
			// left floating: anything placed (not an actor, a door, a light or a marker) standing over 40 above the land within a
			// hidden rock's or stump's footprint, or on a hidden tree's trunk, goes too, with the effects and lights within 64 of
			// it. Every pass looks at every hidden support, so a save that hid the support before this rule is mended as well.
			int         stranded = 0;
			std::string strandedLog;
			auto        describe = [](const NearRef& d) {
				const auto* file = d.r->GetFile(0);
				return std::format("{:08X} {} {} ({}) at {:.0f} {:.0f} {:.0f}", d.id, file ? file->GetFilename() : std::string_view("created"),
					d.base ? RE::FormTypeToString(d.base->GetFormType()) : std::string_view("?"), d.base ? d.base->GetFormEditorID() : "", d.p.x, d.p.y, d.p.z);
			};
			std::unordered_map<RE::FormID, NearRef*> byId;
			for (auto& w : swept) byId.emplace(w.id, &w);
			const std::vector<RE::FormID> supports(g_hidden.begin(), g_hidden.end());
			for (auto sid : supports) {
				auto it = byId.find(sid);
				if (it == byId.end()) continue;   // (not loaded near the site)
				auto& sp = *it->second;
				if (!sp.base || !sp.r->GetParentCell() || !sp.r->GetParentCell()->IsAttached()) continue;
				const bool tree = sp.base->Is(RE::FormType::Tree);
				if (!tree && !(sp.base->Is(RE::FormType::Static) && clutter(sp))) continue;
				const float           reach = tree ? 64.0f : std::max(64.0f, Size(sp.r) / 2.0f);
				std::vector<NearRef*> on;
				within(sp.p, reach, [&](NearRef& d) {
					if (!d.base || d.id == sid || off(d)) return;
					if (d.r->Is(RE::FormType::ActorCharacter) || d.base->Is(RE::FormType::Door) || d.base->Is(RE::FormType::Light)) return;
					if (!(d.base->Is(RE::FormType::Static) || d.base->Is(RE::FormType::MovableStatic) || d.base->Is(RE::FormType::Furniture) ||
					        d.base->Is(RE::FormType::Container) || d.base->Is(RE::FormType::Activator) || d.base->Is(RE::FormType::Misc) ||
					        d.base->Is(RE::FormType::Tree) || d.base->Is(RE::FormType::Flora)))
						return;
					if (marker(d)) return;
					if (aboveLand(d)) on.push_back(&d);
				});
				for (auto* d : on) {
					if (!hide(*d)) continue;
					++stranded;
					strandedLog += (strandedLog.empty() ? "" : "; ") + describe(*d) + std::format(" on {:08X}", sid);
					std::vector<NearRef*> with;   // its fire, its light
					within(d->p, 64.0f, [&](NearRef& w) {
						if (!w.base || w.id == d->id || off(w)) return;
						if (w.base->Is(RE::FormType::MovableStatic) || w.base->Is(RE::FormType::Light)) with.push_back(&w);
					});
					for (auto* w : with)
						if (hide(*w)) ++stranded, strandedLog += "; with it " + describe(*w);
				}
			}
			if (stranded) SKSE::log::info("Hall: site {}: hid {} ref(s) left standing on hidden supports: {}", a_s.id, stranded, strandedLog);
			onTop += stranded;
			n += onTop + flora;
			if (n || mended) Nav::OutdoorGroundChanged();   // (a hidden tree can be a navmesh obstacle: the game redoes its cut)
			if (n)  // silent when there was nothing (new) to hide
				SKSE::log::info("Hall: site {}: hid {} tree(s), {} rock(s), {} standing on them, {} flora growing on them; kept {} big rock(s)", a_s.id,
					trees.size(), rocks.size(), onTop, flora, kept);
			return n;
		}

		int Place(const Layout& a_l, int& a_missing)
		{
			auto* dh = RE::TESDataHandler::GetSingleton();
			auto* pc = RE::PlayerCharacter::GetSingleton();
			int   n = 0;
			for (const auto& p : a_l.pieces) {
				auto* base = p.base ? RE::TESForm::LookupByID<RE::TESBoundObject>(p.base) : nullptr;
				auto* cell = OutdoorCell(p.pos);
				if (!base || !cell) {
					++a_missing;
					SKSE::log::warn("Hall: piece {} at ({:.0f}, {:.0f}, {:.0f}) not placed: {}", p.rec, p.pos.x, p.pos.y, p.pos.z, base ? "its cell is not loaded" : "no such record");
					continue;
				}
				const auto h = dh->CreateReferenceAtLocation(base, p.pos, RE::NiPoint3(0.0f, 0.0f, p.angle * kPi / 180.0f), cell, pc->GetWorldspace(), nullptr, nullptr,
					RE::ObjectRefHandle(), true, true);
				auto ref = h.get();
				if (!ref) {
					++a_missing;
					continue;
				}
				if (p.scale != 1.0f) ref->SetScale(p.scale);
				g_placed.push_back(ref->GetFormID());
				++n;
			}
			return n;
		}

		// (a warm glow, as if the lights inside were on) the windows' outside panes follow an emittance source, as vanilla's towns' do; the hall's body is
		// placed at run time, so the plugin has no reference to give an XEMI: the extra, on the piece whose model is the body, each load in case a save did not keep it
		void GiveBodyItsGlow(const Layout& a_l)
		{
			// the site's own town's glow (Solitude's at site B), vanilla's Whiterun one for a layout that names none
			const RE::FormID glow = !a_l.sites.empty() && !a_l.sites.front().glow.empty() ? Resolve(a_l.sites.front().glow) : 0;
			auto*            src = RE::TESForm::LookupByID(glow ? glow : kNightGlow);
			if (!src) return;
			for (auto id : g_placed) {
				auto* r = Ref(id);
				auto* base = r ? r->GetBaseObject() : nullptr;
				auto* model = base ? base->As<RE::TESModel>() : nullptr;
				if (!model) continue;
				std::string path = model->GetModel();
				if (path.size() < 15 || _stricmp(path.c_str() + path.size() - 15, "AGHall2Body.nif") != 0) continue;
				if (r->extraList.HasType(RE::ExtraDataType::kEmittanceSource)) return;
				auto* x = RE::BSExtraData::Create<RE::ExtraEmittanceSource>();
				x->source = src;
				r->extraList.Add(x);
				SKSE::log::info("Hall: the body's windows follow the night's light (emittance source {:08X})", src->GetFormID());
				return;
			}
		}

		// (2026-11-01, the Open prompt in the wrong place at the front doors) SetScale leaves a reference's collision at the size its 3D was built at (the CK wiki), and the doors come through
		// CreateReferenceAtLocation at 1, then 1.3: taken away and given back, so their 3D, and its collision, are built at the size they stand at
		void RebuildScaledDoors()
		{
			for (auto id : g_placed) {
				auto* r = Ref(id);
				auto* base = r ? r->GetBaseObject() : nullptr;
				auto* model = base ? base->As<RE::TESModel>() : nullptr;
				if (!model || r->GetScale() == 1.0f) continue;
				std::string path = model->GetModel();
				if (path.size() < 25 || _stricmp(path.c_str() + path.size() - 25, "AGH2Csdoubledoorint01.nif") != 0) continue;
				r->Disable();
				r->Enable(false);
			}
		}

		// a_show: the hidden refs shown again too (Remove: the hall taken away). A rebuild keeps them hidden (2026-11-07: re-enabling
		// them and hiding them again in one pass left them enabled, the enable landing after the disable)
		void TakeDown(bool a_show = true)
		{
			int deleted = 0, shown = 0;
			for (auto id : g_placed)
				if (auto* r = Ref(id)) DeletePiece(r), ++deleted;
			if (a_show) {
				// (a reference in a cell that is not loaded is not there to enable: it waits on the to-show list, kept in the
				// co-save, until its cell loads; a hall moved to another site leaves its old site's cells unloaded)
				for (auto id : g_hidden)
					if (auto* r = Ref(id)) r->Enable(false), ++shown;
					else g_toShow.push_back(id);
				g_hidden.clear();
			}
			g_placed.clear();
			g_version.clear();
			if (deleted || shown || !g_toShow.empty())
				SKSE::log::info("Hall: took down {} piece(s), showed {} hidden ref(s) again{}", deleted, shown,
					g_toShow.empty() ? "" : std::format(", {} to show as their cells load", g_toShow.size()));
		}

		// The hidden references of a hall that no longer stands where they are: each shown once its cell has loaded it. On the main thread
		void ShowWaiting(const char* a_why)
		{
			if (g_toShow.empty()) return;
			int  shown = 0;
			auto keep = std::ranges::remove_if(g_toShow, [&](RE::FormID id) {
				auto* r = Ref(id);
				if (!r || !r->GetParentCell() || !r->GetParentCell()->IsAttached()) return false;
				if (r->IsDisabled()) r->Enable(false);
				++shown;
				return true;
			});
			g_toShow.erase(keep.begin(), keep.end());
			if (shown) SKSE::log::info("Hall: showed {} ref(s) a hall no longer here had hidden ({}); {} still to show", shown, a_why, g_toShow.size());
		}

		// Where the save's hall stood: its site as the co-save has it; a save from before that, one of its pieces still there.
		// None: nothing tells.
		std::optional<RE::NiPoint3> SavedSite()
		{
			if (g_siteX != 0.0f || g_siteY != 0.0f) return RE::NiPoint3(g_siteX, g_siteY, 0.0f);
			for (auto id : g_placed)
				if (auto* r = Ref(id)) return r->GetPosition();
			return std::nullopt;
		}

		// Pieces of ours standing in Tamriel though the co-save does not list them (a save whose record was lost, or written by the
		// hall's spike DLL, when the hall moved): every created, persistent reference of a base from the hall's plugin that is
		// placed, not carried (no book or potion a player dropped), and not one this hall placed. Once a game, on the main thread
		int SweepStrays()
		{
			auto* ws = RE::TESForm::LookupByID<RE::TESWorldSpace>(kTamriel);
			if (!ws || !ws->persistentCell) return 0;
			std::unordered_set<RE::FormID>  ours(g_placed.begin(), g_placed.end());
			std::vector<RE::TESObjectREFR*> stray;
			ws->persistentCell->ForEachReference([&](RE::TESObjectREFR* r) {
				if (!r || r->IsDeleted() || (r->GetFormID() >> 24) != 0xFF || ours.contains(r->GetFormID())) return RE::BSContainer::ForEachResult::kContinue;
				auto*       base = r->GetBaseObject();
				const auto* file = base ? base->GetFile(0) : nullptr;
				if (!file || _stricmp(std::string(file->GetFilename()).c_str(), kPlugin) != 0) return RE::BSContainer::ForEachResult::kContinue;
				using T = RE::FormType;
				for (auto t : { T::Static, T::MovableStatic, T::Activator, T::Furniture, T::Door, T::Container, T::Tree, T::Flora, T::Light, T::IdleMarker })
					if (base->Is(t)) {
						stray.push_back(r);
						break;
					}
				return RE::BSContainer::ForEachResult::kContinue;
			});
			std::string which;
			for (auto* r : stray) {
				const auto p = r->GetPosition();
				which += std::format("{}{:08X} ({}) at {:.0f} {:.0f}", which.empty() ? "" : "; ", r->GetFormID(), r->GetBaseObject()->GetFormEditorID(), p.x, p.y);
				DeletePiece(r);
			}
			if (!stray.empty()) SKSE::log::info("Hall: took down {} piece(s) of ours the save no longer listed: {}", stray.size(), which);
			return static_cast<int>(stray.size());
		}

		// Bring the world in line with the layout: on the main thread, once the hall's cells are loaded.
		void Reconcile(const char* a_why, bool a_force)
		{
			HallPassTimer timer("hall reconcile");
			std::scoped_lock l(g_lock);
			if (!g_inGame) return;
			const auto L = Load();
			if (!L.ok) {
				SKSE::log::warn("Hall: {} ({})", L.error, a_why);
				g_pending = false;
				return;
			}
			// (2026-11-17) the save's hall stood at another site (the installer's other choice): taken down at once, its hidden references
			// given back, without waiting for the installed site's cells. The rebuild below waited for those, so a game loaded at the old
			// site kept the old hall standing there, its pieces drawn with the new build's models, until the player went to the new one
			if (!L.sites.empty() && (!g_placed.empty() || !g_hidden.empty())) {
				const auto was = SavedSite();
				if (was && std::hypot(was->x - L.sites.front().x, was->y - L.sites.front().y) > 8192.0f) {
					SKSE::log::info("Hall: the save's hall stood at ({:.0f}, {:.0f}); the installed one stands at ({:.0f}, {:.0f}): taken down there now ({})",
						was->x, was->y, L.sites.front().x, L.sites.front().y, a_why);
					TakeDown(true);
					g_siteX = g_siteY = 0.0f;
				}
			}
			if (!Loaded(L)) {
				g_pending = true;  // again when its cells load
				return;
			}
			g_pending = false;
			// standing: every piece the save placed is still there, outdoors in Tamriel (an older build could land in the
			// interior the save was made in), and as many as the layout can place now (a build made while the plugin was
			// unticked lacks the building, and ticking it later must still bring the building)
			const auto placeable = std::ranges::count_if(L.pieces, [](const Piece& p) { return p.base != 0; });
			int        gone = 0, astray = 0;
			for (auto id : g_placed)
				if (auto* r = Ref(id); !r) ++gone;
				else if (auto* ws = r->GetWorldspace(); !ws || ws->GetFormID() != kTamriel) ++astray;
			const bool fewer = std::cmp_less(g_placed.size(), placeable);
			const bool whole = !g_placed.empty() && !gone && !astray && !fewer;
			if (a_force || !whole || g_version != L.version) {  // (a hall that stands as the layout says: nothing to log)
				if (!g_version.empty() || !g_placed.empty())
					SKSE::log::info("Hall: rebuilding ({}): the save holds layout '{}', {} pieces{}{}{}; the layout file is {}", a_why, g_version, g_placed.size(),
						gone ? std::format(", {} gone", gone) : "", astray ? std::format(", {} not outdoors in Tamriel", astray) : "",
						fewer ? std::format(", {} can be placed now", placeable) : "", L.version);
				// (2026-11-17) the save's hall stood at another site (the installer's other choice): its hidden references are given back
				// there, as their cells load; at the same site they stay hidden (Hide below adds what the new layout's boxes take)
				const auto was = SavedSite();
				const bool moved = was && !L.sites.empty() && std::hypot(was->x - L.sites.front().x, was->y - L.sites.front().y) > 8192.0f;
				if (moved)
					SKSE::log::info("Hall: the save's hall stood at ({:.0f}, {:.0f}); the installed one stands at ({:.0f}, {:.0f}): taken down there, its {} hidden ref(s) shown again",
						was->x, was->y, L.sites.front().x, L.sites.front().y, g_hidden.size());
				TakeDown(moved);
				int missing = 0;
				const int placed = Place(L, missing);
				int hiddenN = 0;
				for (const auto& s : L.sites) hiddenN += Hide(L, s);
				g_version = L.version;
				SKSE::log::info("Hall: placed {} piece(s) ({} not), hid {} ref(s): layout {} ({})", placed, missing, hiddenN, g_version, a_why);
			}
			if (!L.sites.empty()) g_siteX = L.sites.front().x, g_siteY = L.sites.front().y;
			ShowWaiting("hall reconciled");
			GiveBodyItsGlow(L);
			RebuildScaledDoors();
			SKSE::GetTaskInterface()->AddTask([] { Nav::AutoApply(); });
		}

		// ---------------------------------------------------------------- co-save

		void OnSave(SKSE::SerializationInterface* a)
		{
			std::scoped_lock l(g_lock);
			if (!a->OpenRecord(kRecord, kVersion)) return;
			const auto len = static_cast<std::uint32_t>(g_version.size());
			a->WriteRecordData(len);
			a->WriteRecordData(g_version.data(), len);
			for (const auto* list : { &g_placed, &g_hidden }) {
				const auto n = static_cast<std::uint32_t>(list->size());
				a->WriteRecordData(n);
				for (auto id : *list) a->WriteRecordData(id);
			}
			a->WriteRecordData(g_siteX);   // (3)
			a->WriteRecordData(g_siteY);
			const auto nShow = static_cast<std::uint32_t>(g_toShow.size());
			a->WriteRecordData(nShow);
			for (auto id : g_toShow) a->WriteRecordData(id);
		}

		void OnLoad(SKSE::SerializationInterface* a, std::uint32_t a_ver)
		{
			std::scoped_lock l(g_lock);
			{
				if (a_ver != 2 && a_ver != kVersion) return;  // (a save from the hall's own spike DLL: new saves only)
				std::uint32_t n = 0;
				a->ReadRecordData(n);
				g_version.resize(n);
				a->ReadRecordData(g_version.data(), n);
				for (auto* list : { &g_placed, &g_hidden }) {
					list->clear();
					a->ReadRecordData(n);
					for (std::uint32_t i = 0; i < n; ++i) {
						RE::FormID id = 0, now = 0;
						a->ReadRecordData(id);
						if (a->ResolveFormID(id, now)) list->push_back(now);
					}
				}
				g_toShow.clear();
				if (a_ver >= 3) {
					a->ReadRecordData(g_siteX);
					a->ReadRecordData(g_siteY);
					a->ReadRecordData(n);
					for (std::uint32_t i = 0; i < n; ++i) {
						RE::FormID id = 0, now = 0;
						a->ReadRecordData(id);
						if (a->ResolveFormID(id, now)) g_toShow.push_back(now);
					}
				}
			}
		}

		void OnRevert(SKSE::SerializationInterface*)
		{
			std::scoped_lock l(g_lock);
			g_version.clear();
			g_placed.clear();
			g_hidden.clear();
			g_toShow.clear();
			g_siteX = g_siteY = 0.0f;
			g_swept = false;
			g_inGame = false;
			g_pending = false;
		}

		// A cell attaches after the first of the hall's cells has loaded: whatever in the boxes it brings is hidden now
		// (a pass only sees attached cells, so one run at the first cell missed the rest). Cheap, and idempotent.
		void HideMore(const char* a_why)
		{
			HallPassTimer timer("hall hide pass");
			std::scoped_lock l(g_lock);
			if (!g_inGame || g_version.empty()) return;
			const auto L = Load();
			if (!L.ok || L.version != g_version) return;
			int n = 0;
			for (const auto& s : L.sites) n += Hide(L, s);
			if (n) SKSE::log::info("Hall: hid {} more ref(s) ({}); {} hidden in all", n, a_why, g_hidden.size());
		}

		// One hide pass per burst of cell loads: a load beside the hall finishes some 25 cells at once, and a pass for each held the
		// main thread for seconds (a black screen, then dead controls, in VR). A cell load sets the pass kHideSettleMs ahead; it runs
		// once cells stop arriving, and kHideMaxMs after the burst's first at the latest.
		constexpr long long kHideSettleMs = 250, kHideMaxMs = 1000;
		std::atomic<long long> g_hideDueMs{ 0 };
		std::atomic_bool       g_hideQueued{ false };
		long long              NowMs() { return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
		void                   ScheduleHideMore()
		{
			const auto now = NowMs();
			g_hideDueMs = now + kHideSettleMs;
			if (g_hideQueued.exchange(true)) return;
			std::thread([first = now] {
				for (;;) {
					std::this_thread::sleep_for(std::chrono::milliseconds(50));
					const auto t = NowMs();
					if (t >= g_hideDueMs || t - first >= kHideMaxMs) break;
				}
				g_hideQueued = false;   // (a cell load from here on schedules another pass)
				SKSE::GetTaskInterface()->AddTask([] { HideMore("cells loaded"); });
			}).detach();
		}

		// the hall's cells loading (arriving near it, or a reload) brings a waiting rebuild, more hiding, the navmesh
		class CellSink : public RE::BSTEventSink<RE::TESCellFullyLoadedEvent>
		{
		public:
			RE::BSEventNotifyControl ProcessEvent(const RE::TESCellFullyLoadedEvent* a_event, RE::BSTEventSource<RE::TESCellFullyLoadedEvent>*) override
			{
				if (a_event && a_event->cell && a_event->cell->IsExteriorCell())
					SKSE::GetTaskInterface()->AddTask([] {
						bool pending;
						{
							std::scoped_lock l(g_lock);
							pending = g_inGame && g_pending;
						}
						{
							std::scoped_lock l(g_lock);
							ShowWaiting("cells loaded");
						}
						if (!g_active) return;   // (no hall installed: only an old hall's hidden refs to give back)
						if (pending) Reconcile("its cells loaded", false);
						else ScheduleHideMore();
						Nav::AutoApply();
						MarkerEnsure("cells loaded");  // (still on the player's list after a worldspace change)
					});
				return RE::BSEventNotifyControl::kContinue;
			}
		};
		CellSink g_cellSink;

		std::string Status(RE::StaticFunctionTag*)
		{
			std::scoped_lock l(g_lock);
			const auto L = Load();
			int        standing = 0, hiddenNow = 0;
			for (auto id : g_placed) standing += Ref(id) != nullptr;
			for (auto id : g_hidden)
				if (auto* r = Ref(id)) hiddenNow += r->IsDisabled();
			return std::format("layout file {} | the save's hall: layout '{}', {} of {} pieces standing, {} of {} refs hidden{}",
				L.ok ? L.version : L.error, g_version, standing, g_placed.size(), hiddenNow, g_hidden.size(), g_pending ? " | waiting for its cells" : "");
		}

		std::string Rebuild(RE::StaticFunctionTag*)
		{
			SKSE::GetTaskInterface()->AddTask([] { Reconcile("asked", true); });
			return "rebuild queued (HallStatus for the result)";
		}

		std::string Remove(RE::StaticFunctionTag*)
		{
			SKSE::GetTaskInterface()->AddTask([] {
				Nav::RevertAll();
				MarkerRemove();
				std::scoped_lock l(g_lock);
				TakeDown();
			});
			return "removal queued: the hall, its hidden refs, its map marker and the navmesh patches";
		}

		// The placed piece of this record (the first, if the layout has more), or None: an inside door's way out to its
		// outside door (the hall's back door, 2026-10-26). Placed refs are persistent, so this answers from inside too.
		RE::TESObjectREFR* PlacedRef(RE::StaticFunctionTag*, RE::TESForm* a_base)
		{
			if (!a_base) return nullptr;
			std::scoped_lock l(g_lock);
			for (auto id : g_placed)
				if (auto* r = Ref(id); r && r->GetBaseObject() == a_base) return r;
			return nullptr;
		}

		// An inside door's way out when its outside door is not placed (a save that never built the hall, the player brought in
		// by a teleport): the foot of the stair that door's landing leads down to, on the land, facing the door: x, y, z, angle.
		// From the layout and the outdoor navmesh file alone. Neither has the answer: the player is told, and gets nothing back.
		std::vector<float> WayOut(RE::StaticFunctionTag*, RE::TESForm* a_doorBase)
		{
			std::string why;
			if (!a_doorBase) why = "no door given";
			else if (const auto L = Load(); !L.ok) why = L.error;
			else {
				const auto door = std::ranges::find(L.pieces, a_doorBase->GetFormID(), &Piece::base);
				if (door == L.pieces.end()) why = std::format("the layout places no {}", Hex(a_doorBase->GetFormID()));
				else {
					const float        a = door->angle * kPi / 180.0f;   // (a door's outside is its local -y)
					const RE::NiPoint3 out{ door->pos.x - 120.0f * std::sin(a), door->pos.y - 120.0f * std::cos(a), door->pos.z };
					if (const auto f = Nav::StairFoot(out, why)) {
						const float face = std::atan2(door->pos.x - (*f)[0], door->pos.y - (*f)[1]) * 180.0f / kPi;
						SKSE::log::info("Hall: the way out by {} with no hall standing: its stair foot ({:.0f}, {:.0f}, {:.0f}), facing {:.0f}",
							Hex(a_doorBase->GetFormID()), (*f)[0], (*f)[1], (*f)[2], face);
						return { (*f)[0], (*f)[1], (*f)[2], face };
					}
				}
			}
			SKSE::log::warn("Hall: an inside door has no way out ({}): its outside door is not placed and {}", a_doorBase ? Hex(a_doorBase->GetFormID()) : "?", why);
			RE::SendHUDMessage::ShowHUDMessage(AG::Loc::T("$AG_Hall_NoWayOut", "The door does not open: the Guild Hall's outside is missing from this game.").c_str());
			return {};
		}

		// A persistent reference of Tamriel's, the nearest to a point that stays put (no actor, nothing disabled): Papyrus' MoveTo
		// needs a reference to move to, and a cell that is not loaded holds none but these.
		RE::TESObjectREFR* Anchor(RE::StaticFunctionTag*, float a_x, float a_y)
		{
			auto*              ws = RE::TESForm::LookupByID<RE::TESWorldSpace>(kTamriel);
			RE::TESObjectREFR* best = nullptr;
			float              bd = 0;
			if (ws && ws->persistentCell) ws->persistentCell->ForEachReference([&](RE::TESObjectREFR* r) {
				if (r && !r->IsDeleted() && !r->IsDisabled() && !r->As<RE::Actor>() && r->GetBaseObject()) {
					const auto& p = r->GetPosition();
					if (const float d = std::hypot(p.x - a_x, p.y - a_y); !best || d < bd) { best = r; bd = d; }
				}
				return RE::BSContainer::ForEachResult::kContinue;
			});
			if (best) SKSE::log::info("Hall: anchor {} for ({:.0f}, {:.0f}), {:.0f} away", Hex(best->GetFormID()), a_x, a_y, bd);
			else {
				SKSE::log::warn("Hall: no persistent reference in Tamriel to move to ({:.0f}, {:.0f}) by", a_x, a_y);
				RE::SendHUDMessage::ShowHUDMessage(AG::Loc::T("$AG_Hall_NoWayOut", "The door does not open: the Guild Hall's outside is missing from this game.").c_str());
			}
			return best;
		}
	}

	// AG's co-save (Guild.cpp) carries the hall's record: written on every save, read when a save has one
	void Save(SKSE::SerializationInterface* a_intfc)
	{
		if (!g_active) {
			// (no hall installed: only what an old hall hid and is still to show is kept, until its cells load)
			bool waiting;
			{
				std::scoped_lock l(g_lock);
				waiting = !g_toShow.empty();
			}
			if (waiting) OnSave(a_intfc);
			return;
		}
		OnSave(a_intfc);
		MarkerSave(a_intfc);
	}
	void Load(SKSE::SerializationInterface* a_intfc, std::uint32_t a_type, std::uint32_t a_version)
	{
		// (read with no hall installed too: a save that had one gets its hidden references and its map marker back)
		if (a_type == kRecord) OnLoad(a_intfc, a_version);
		else MarkerLoad(a_intfc, a_type, a_version);
	}
	void Revert()
	{
		OnRevert(nullptr);
		MarkerRevert();
	}

	namespace
	{
		struct Installed
		{
			bool         ok = false;
			int          place = 0;
			RE::NiPoint3 pos;
			bool         hasMarker = false;
			RE::NiPoint3 marker;
			float        markerFacing = 0.0f;
			RE::FormID   helios = 0;
		};
		// the installed hall's site, read once (the layout file does not change in a game), when first asked: at data load, before
		// this file's OnDataLoaded runs (GuildHall::ApplyHelios asks first)
		const Installed& Inst()
		{
			static std::once_flag once;
			static Installed      in;
			std::call_once(once, [] {
				if (!AG::GuildHall::Loaded()) return;
				const auto L = Load();
				if (!L.ok || L.sites.empty()) return;
				const auto& s = L.sites.front();
				in = { true, s.place, RE::NiPoint3(s.x, s.y, s.z), s.hasMarker, s.marker, s.markerFacing, s.helios.empty() ? 0 : Resolve(s.helios) };
				SKSE::log::info("Hall: the installed hall's site: place {} at ({:.0f}, {:.0f}){}", s.place, s.x, s.y, s.hasMarker ? "" : " (its layout names no map marker)");
			});
			return in;
		}
	}

	int                         SitePlace() { return Inst().ok ? Inst().place : 0; }
	std::optional<RE::NiPoint3> SitePos() { return Inst().ok ? std::optional(Inst().pos) : std::nullopt; }
	std::optional<std::pair<RE::NiPoint3, float>> MarkerSpot()
	{
		if (!Inst().hasMarker) return std::nullopt;
		return std::pair{ Inst().marker, Inst().markerFacing };
	}
	RE::FormID HeliosRegion() { return Inst().helios; }

	void OnDataLoaded()
	{
		g_active = AG::GuildHall::Loaded();
		// (registered with no hall too: an old hall's hidden references are shown as their cells load)
		if (auto* src = RE::ScriptEventSourceHolder::GetSingleton()) src->AddEventSink<RE::TESCellFullyLoadedEvent>(&g_cellSink);
		if (!g_active) return;  // no hall installed: nothing placed, hidden or patched, and nothing logged
		const auto L = Load();
		Inst();
		GrassOnDataLoaded();
		SKSE::log::info("Hall: {}", L.ok ? std::format("layout {}: {} pieces over {} site(s), {} hide boxes", L.version, L.pieces.size(), L.sites.size(), L.boxes.size()) : L.error);
		for (const auto& p : L.pieces)
			if (!p.base) SKSE::log::warn("Hall: layout piece {} names no loaded record", p.rec);
	}

	void OnGameLoaded(bool a_newGame)
	{
		if (!g_active) {
			// no hall installed: a save that had one (the installer's "none" chosen later) gets back what it hid and loses the map
			// marker; its pieces went with the hall's plugin
			bool had;
			{
				std::scoped_lock l(g_lock);
				had = !g_hidden.empty() || !g_toShow.empty() || !g_placed.empty();
			}
			if (had || MapMarker())
				SKSE::GetTaskInterface()->AddTask([] {
					MarkerRemove();
					std::scoped_lock l(g_lock);
					SKSE::log::info("Hall: no hall installed, but this save had one: its hidden refs are shown again and its map marker taken down");
					TakeDown(true);
					g_siteX = g_siteY = 0.0f;
				});
			return;
		}
		{
			std::scoped_lock l(g_lock);
			g_inGame = true;
			g_pending = true;
		}
		SKSE::GetTaskInterface()->AddTask([a_newGame] {
			{
				std::scoped_lock l(g_lock);
				if (!g_swept) {   // (once a game: pieces of an earlier hall the co-save lost track of)
					g_swept = true;
					SweepStrays();
				}
				ShowWaiting(a_newGame ? "new game" : "game loaded");
			}
			MarkerEnsure(a_newGame ? "new game" : "game loaded");
			AG::Guild::MarkRegistrationHall();  // a registration quest already sending the player here points at the marker
			Reconcile(a_newGame ? "new game" : "game loaded", false);
		});
	}

	bool Standing()
	{
		std::scoped_lock l(g_lock);
		return g_active && g_inGame && !g_placed.empty();
	}

	bool RegisterPapyrus(RE::BSScript::IVirtualMachine* a_vm)
	{
		constexpr auto kClass = "AGHallNative";
		a_vm->RegisterFunction("HallStatus", kClass, Status);
		a_vm->RegisterFunction("HallRebuild", kClass, Rebuild);
		a_vm->RegisterFunction("HallRemove", kClass, Remove);
		a_vm->RegisterFunction("HallRef", kClass, PlacedRef);
		a_vm->RegisterFunction("HallWayOut", kClass, WayOut);
		a_vm->RegisterFunction("HallAnchor", kClass, Anchor);
		return true;
	}
}
