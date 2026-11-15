// The Guild Hall's outdoor navmesh, fitted into the loaded ground navmesh at run time (2026-11-13; the plan:
// tools/hall-private/plans/OUTDOOR_NAVMESH.md). The hall's terrace, porch, walks, forecourt and stairs had no navmesh: followers
// who came out of the front door dropped to the vanilla ground under the terrace, inside the podium, and NPCs pathed through the
// hall's walls on the ground under it. blender/outdoor_nav.py writes outdoor_nav.json: our mesh in world coordinates with its
// neighbours, cut on the cells' borders; the outline the ground must keep out of (the hall's footprint and ours); the stair feet.
// Here, once the hall's cells are loaded:
//   1. cut: every loaded ground triangle inside the outline is deleted, unlinked from its neighbours (within its navmesh and through
//      other navmeshes' portals) and taken out of its lookup grid; one across it is clipped on its line (Clipper2, earcut);
//   2. hosts: one navmesh per cell (the one with the most cut triangles, else the largest) takes our triangles in that cell; our
//      edges between hosts become portals (extraEdgeInfo);
//   3. feet: our open edges at each stair foot linked to the nearest ground edge, and back (nowhere else: parapets stand between);
//   4. the info map: hosts our portals join that it does not list as neighbours become neighbours (vanilla's hill under the hall
//      reaches the road only round by the east, so the grand stair joins two navmeshes it does not pair);
//   5. each host's lookup grid rebuilt over its new extent.
// Everything is recorded and taken out again when a cell reloads (the game gives back the plugin's navmesh) or on Revert. Nothing
// is written to any file the game reads, nor to the save.
#include "hall.h"

#include <clipper2/clipper.h>
#include <mapbox/earcut.hpp>
#include <nlohmann/json.hpp>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <functional>
#include <map>
#include <set>

namespace
{
	using Json = nlohmann::json;
	using TriFlag = RE::BSNavmeshTriangle::TriangleFlag;
	constexpr std::uint16_t kNone = 0xFFFF;
	constexpr const char*   kFile = "Data/SKSE/Plugins/AdventurersGuild/Hall/outdoor/outdoor_nav.json";

	std::string Hex(std::uint32_t a_v) { return std::format("{:08X}", a_v); }

	struct Ours
	{
		std::vector<RE::NiPoint3>          verts;
		std::vector<std::array<int, 6>>    tris;   // v0 v1 v2, neighbour per edge (ours) or -1
		double                             sx = 0, sy = 0, sz = 0, c = 1, s = 0;
		Clipper2Lib::PathsD                blocked;      // the hall's footprint and ours, outline rings (even-odd): no ground inside
		Clipper2Lib::RectD                 blockedBox{};
		bool                               preferred = false;
		std::vector<std::array<double, 4>> feet;   // x y z radius (world)
		std::set<std::pair<int, int>>      cells;  // the world cells our triangles stand in
		std::vector<RE::NiPoint3>          anchors;  // the doors' outside landings (world)
		bool                               ok = false;
		std::string                        why = "not read yet";
	};
	Ours g_ours;
	bool g_infoLinks = true;   // step 4 (OutdoorSettings)

	void Load()
	{
		if (g_ours.ok) return;
		std::ifstream in(kFile);
		if (!in) { g_ours.why = std::format("no {}", kFile); return; }
		try {
			const auto j = Json::parse(in);
			Ours o;
			const auto& st = j["site"];
			o.sx = st[0]; o.sy = st[1]; o.sz = st[2];
			const double a = st[3].get<double>() * 3.14159265358979323846 / 180.0;
			o.c = std::cos(a); o.s = std::sin(a);
			for (const auto& v : j["verts"]) o.verts.emplace_back(v[0].get<float>(), v[1].get<float>(), v[2].get<float>());
			for (const auto& t : j["tris"]) {
				std::array<int, 6> a6{};
				for (int k = 0; k < 6; ++k) a6[k] = t[k].get<int>();
				o.tris.push_back(a6);
			}
			// (version 2: the hall's footprint as outline polygons, not a raster sampled every 8, to keep the triangle count down:
			// the raster's carve had made 3021 ground triangles out of 165)
			if (j.value("version", 1) < 2) { g_ours.why = "an outdoor_nav.json older than version 2"; return; }
			o.preferred = j.value("preferred", false);
			for (const auto& p : j["blocked"]) {
				auto ring = [&](const Json& a_r) { Clipper2Lib::PathD q; for (const auto& v : a_r) q.emplace_back(v[0].get<double>(), v[1].get<double>()); return q; };
				o.blocked.push_back(ring(p["outer"]));
				for (const auto& h : p["holes"]) o.blocked.push_back(ring(h));
			}
			if (o.blocked.empty()) { g_ours.why = "no blocked outline"; return; }
			o.blockedBox = Clipper2Lib::GetBounds(o.blocked);
			for (const auto& f : j["feet"]) o.feet.push_back({ f[0].get<double>(), f[1].get<double>(), f[2].get<double>(), f[3].get<double>() });
			if (j.contains("anchors"))
				for (const auto& a : j["anchors"]) o.anchors.emplace_back(a[0].get<float>(), a[1].get<float>(), a[2].get<float>());
			for (const auto& t : o.tris) {
				const auto& p = o.verts[t[0]]; const auto& q = o.verts[t[1]]; const auto& w = o.verts[t[2]];
				o.cells.insert({ static_cast<int>(std::floor((p.x + q.x + w.x) / 3 / 4096.0)), static_cast<int>(std::floor((p.y + q.y + w.y) / 3 / 4096.0)) });
			}
			o.ok = true; o.why = "";
			g_ours = std::move(o);
		} catch (const std::exception& e) {
			g_ours.why = std::format("unreadable: {}", e.what());
		}
	}

	// is a world point inside the outline (the hall's footprint or ours: even-odd over the rings)?
	bool InBlocked(double a_x, double a_y)
	{
		const auto& b = g_ours.blockedBox;
		if (a_x < b.left || a_x > b.right || a_y < b.top || a_y > b.bottom) return false;
		bool in = false;
		const Clipper2Lib::PointD q{ a_x, a_y };
		for (const auto& r : g_ours.blocked)
			if (Clipper2Lib::PointInPolygon(q, r) == Clipper2Lib::PointInPolygonResult::IsInside) in = !in;
		return in;
	}

	struct Mesh
	{
		RE::NavMesh*   nm = nullptr;
		RE::BSNavmesh* m = nullptr;
		RE::FormID     id = 0;
		int            cx = 0, cy = 0;
	};

	// ---- what the fit changed, to take it out again
	struct TriEdit { RE::NavMesh* nm; std::uint16_t idx; RE::BSNavmeshTriangle was; };
	struct GridBackup
	{
		RE::NavMesh*                            nm;
		RE::NiPoint3                            mn, mx;
		float                                   cl, rl;
		std::vector<std::vector<std::uint16_t>> cells;
	};
	struct HostBackup { RE::NavMesh* nm; RE::FormID id; std::size_t nv, nt, ne, addV, addT, addE; };
	struct InfoEdit { RE::BSNavmeshInfo* info; std::uint32_t* oldArr; std::uint16_t oldCount; std::uint32_t* newArr; };
	struct Applied
	{
		bool                    in = false;
		std::vector<Mesh>       meshes;   // every navmesh the fit read or changed, to tell a reload
		std::vector<TriEdit>    tris;
		std::vector<GridBackup> grids;
		std::vector<HostBackup> hosts;
		std::vector<InfoEdit>   infos;
		std::string             summary;
	};
	Applied g_app;

	std::vector<Mesh> LoadedMeshes()
	{
		std::vector<Mesh> out;
		auto*             tes = RE::TES::GetSingleton();
		auto*             grid = tes ? tes->gridCells : nullptr;
		if (!grid || !grid->cells || grid->length >= 64) return out;
		for (std::uint32_t gx = 0; gx < grid->length; ++gx)
			for (std::uint32_t gy = 0; gy < grid->length; ++gy) {
				auto* cell = grid->GetCell(gx, gy);
				if (!cell || !cell->IsExteriorCell()) continue;
				const auto* xy = cell->GetCoordinates();
				auto&       rd = cell->GetRuntimeData();
				if (!xy || !rd.navMeshes || rd.navMeshes->navMeshes.size() > 4096) continue;
				for (auto& sp : rd.navMeshes->navMeshes)
					if (auto* nm = sp.get())
						out.push_back({ nm, static_cast<RE::BSNavmesh*>(nm), nm->GetFormID(), xy->cellX, xy->cellY });
			}
		return out;
	}

	bool StillIn()
	{
		if (!g_app.in) return false;
		// (2026-11-13: every loaded navmesh was checked, so one unloading at the grid's edge made the fit stale) only the navmeshes
		// the fit changed, each looked up before it is read
		std::set<RE::NavMesh*> changed;
		for (const auto& h : g_app.hosts) changed.insert(h.nm);
		for (const auto& g : g_app.grids) changed.insert(g.nm);
		for (const auto& t : g_app.tris) changed.insert(t.nm);
		for (const auto& m : g_app.meshes)
			if (changed.contains(m.nm) && RE::TESForm::LookupByID<RE::NavMesh>(m.id) != m.nm) return false;
		for (const auto& h : g_app.hosts) {
			auto& m = *static_cast<RE::BSNavmesh*>(h.nm);
			if (m.vertices.size() != h.nv + h.addV || m.triangles.size() != h.nt + h.addT || m.extraEdgeInfo.size() != h.ne + h.addE) return false;
		}
		return true;
	}

	// take back what is still there: a navmesh the game loaded again holds none of it
	void RevertNow(const char* a_why)
	{
		if (!g_app.in && g_app.tris.empty() && g_app.infos.empty()) return;
		auto same = [](RE::NavMesh* a_nm, RE::FormID a_id) { return RE::TESForm::LookupByID<RE::NavMesh>(a_id) == a_nm; };
		std::map<RE::NavMesh*, RE::FormID> ids;
		for (const auto& m : g_app.meshes) ids[m.nm] = m.id;
		int restored = 0;
		if (!g_app.infos.empty()) {   // (the new arrays are left: a few bytes, and nothing can still be reading them)
			auto* tes = RE::TES::GetSingleton();
			auto* map = tes ? tes->GetRuntimeData2().navMeshInfoMap : nullptr;
			if (map) map->mapLock.LockForWrite();
			for (auto it = g_app.infos.rbegin(); it != g_app.infos.rend(); ++it)
				if (it->info->adjacentMeshesArray == it->newArr) { it->info->adjacentMeshesArray = it->oldArr; it->info->adjacentMeshCount = it->oldCount; }
			if (map) map->mapLock.UnlockForWrite();
		}
		for (const auto& h : g_app.hosts) {
			if (!same(h.nm, h.id)) continue;
			auto& m = *static_cast<RE::BSNavmesh*>(h.nm);
			if (m.triangles.size() == h.nt + h.addT) m.triangles.resize(h.nt);
			if (m.vertices.size() == h.nv + h.addV) m.vertices.resize(h.nv);
			if (m.extraEdgeInfo.size() == h.ne + h.addE) m.extraEdgeInfo.resize(h.ne);
		}
		for (auto it = g_app.tris.rbegin(); it != g_app.tris.rend(); ++it) {
			auto f = ids.find(it->nm);
			if (f == ids.end() || !same(it->nm, f->second)) continue;
			auto& m = *static_cast<RE::BSNavmesh*>(it->nm);
			if (it->idx < m.triangles.size()) { m.triangles[it->idx] = it->was; ++restored; }
		}
		for (const auto& g : g_app.grids) {
			auto f = ids.find(g.nm);
			if (f == ids.end() || !same(g.nm, f->second)) continue;
			auto& gr = static_cast<RE::BSNavmesh*>(g.nm)->meshGrid;
			gr.gridBoundsMin = g.mn; gr.gridBoundsMax = g.mx; gr.columnSectionLen = g.cl; gr.rowSectionLen = g.rl;
			for (std::size_t c = 0; c < g.cells.size(); ++c) {
				auto& a = gr.gridData[c];
				a.clear();
				for (auto v : g.cells[c]) a.push_back(v);
			}
		}
		SKSE::log::info("outdoor navmesh taken out ({}): {} triangle(s) restored", a_why, restored);
		g_app = Applied{};
	}

	void BackupGrid(RE::NavMesh* a_nm)
	{
		for (const auto& g : g_app.grids)
			if (g.nm == a_nm) return;
		auto&      gr = static_cast<RE::BSNavmesh*>(a_nm)->meshGrid;
		GridBackup b{ a_nm, gr.gridBoundsMin, gr.gridBoundsMax, gr.columnSectionLen, gr.rowSectionLen, {} };
		const auto n = static_cast<std::size_t>(gr.gridSize) * gr.gridSize;
		b.cells.resize(n);
		for (std::size_t c = 0; c < n; ++c) b.cells[c].assign(gr.gridData[c].begin(), gr.gridData[c].end());
		g_app.grids.push_back(std::move(b));
	}

	std::set<std::pair<RE::NavMesh*, std::uint16_t>> g_editedTris;
	void Touch(RE::NavMesh* a_nm, std::uint16_t a_i)
	{
		if (g_editedTris.insert({ a_nm, a_i }).second) g_app.tris.push_back({ a_nm, a_i, static_cast<RE::BSNavmesh*>(a_nm)->triangles[a_i] });
	}

	// does the grid number its cells row by row? (as main.cpp's GridRowMajor: by where its own triangles' centres are listed)
	bool RowMajor(const RE::BSNavmesh& m)
	{
		const auto& g = m.meshGrid; const auto n = g.gridSize;
		int row = 0, col = 0;
		for (std::size_t c = 0; c < static_cast<std::size_t>(n) * n; ++c)
			for (auto ti : g.gridData[c]) {
				if (ti >= m.triangles.size()) continue;
				const auto& t = m.triangles[ti];
				RE::NiPoint3 p{};
				for (auto vi : t.vertices) p += m.vertices[vi].location;
				p /= 3.0f;
				const auto ix = std::min<std::uint32_t>(n - 1, static_cast<std::uint32_t>(std::max(0.0f, (p.x - g.gridBoundsMin.x) / g.columnSectionLen)));
				const auto iy = std::min<std::uint32_t>(n - 1, static_cast<std::uint32_t>(std::max(0.0f, (p.y - g.gridBoundsMin.y) / g.rowSectionLen)));
				row += c == static_cast<std::size_t>(iy) * n + ix; col += c == static_cast<std::size_t>(ix) * n + iy;
			}
		return row >= col;
	}

	// rebuild a navmesh's lookup grid over all its live triangles (bounds from them; the same number of cells, the same numbering)
	void RebuildGrid(RE::NavMesh* a_nm)
	{
		auto&      m = *static_cast<RE::BSNavmesh*>(a_nm);
		auto&      g = m.meshGrid;
		const bool rowMajor = RowMajor(m);
		const auto n = g.gridSize;
		RE::NiPoint3 mn{ 1e9f, 1e9f, 1e9f }, mx{ -1e9f, -1e9f, -1e9f };
		for (const auto& t : m.triangles) {
			if (t.triangleFlags.any(TriFlag::kDeleted)) continue;
			for (auto vi : t.vertices) {
				const auto& v = m.vertices[vi].location;
				mn.x = std::min(mn.x, v.x); mn.y = std::min(mn.y, v.y); mn.z = std::min(mn.z, v.z);
				mx.x = std::max(mx.x, v.x); mx.y = std::max(mx.y, v.y); mx.z = std::max(mx.z, v.z);
			}
		}
		if (mn.x > mx.x) return;
		g.gridBoundsMin = mn; g.gridBoundsMax = mx;
		g.columnSectionLen = std::max(1.0f, (mx.x - mn.x) / n); g.rowSectionLen = std::max(1.0f, (mx.y - mn.y) / n);
		for (std::size_t c = 0; c < static_cast<std::size_t>(n) * n; ++c) g.gridData[c].clear();
		auto ix = [&](float v, float lo, float len) { return std::min<std::uint32_t>(n - 1, static_cast<std::uint32_t>(std::max(0.0f, (v - lo) / len))); };
		for (std::size_t t = 0; t < m.triangles.size(); ++t) {
			const auto& tr = m.triangles[t];
			if (tr.triangleFlags.any(TriFlag::kDeleted)) continue;
			float x0 = 1e9f, y0 = 1e9f, x1 = -1e9f, y1 = -1e9f;
			for (auto vi : tr.vertices) { const auto& v = m.vertices[vi].location; x0 = std::min(x0, v.x); x1 = std::max(x1, v.x); y0 = std::min(y0, v.y); y1 = std::max(y1, v.y); }
			for (auto a = ix(x0, mn.x, g.columnSectionLen); a <= ix(x1, mn.x, g.columnSectionLen); ++a)
				for (auto b = ix(y0, mn.y, g.rowSectionLen); b <= ix(y1, mn.y, g.rowSectionLen); ++b)
					g.gridData[rowMajor ? static_cast<std::size_t>(b) * n + a : static_cast<std::size_t>(a) * n + b].push_back(static_cast<std::uint16_t>(t));
		}
	}

	RE::BSNavmeshInfo* InfoOf(RE::FormID a_id)
	{
		auto* tes = RE::TES::GetSingleton();
		auto* map = tes ? tes->GetRuntimeData2().navMeshInfoMap : nullptr;
		return map ? map->GetNavmeshInfo(a_id) : nullptr;
	}
	void AddNeighbour(RE::FormID a_a, RE::FormID a_b)
	{
		auto* ia = InfoOf(a_a);
		if (!ia) return;
		for (std::uint16_t i = 0; i < ia->adjacentMeshCount; ++i)
			if (ia->adjacentMeshesArray[i] == a_b) return;
		auto* arr = static_cast<std::uint32_t*>(RE::malloc(sizeof(std::uint32_t) * (ia->adjacentMeshCount + 1u)));
		if (!arr) return;
		for (std::uint16_t i = 0; i < ia->adjacentMeshCount; ++i) arr[i] = ia->adjacentMeshesArray[i];
		arr[ia->adjacentMeshCount] = a_b;
		g_app.infos.push_back({ ia, ia->adjacentMeshesArray, ia->adjacentMeshCount, arr });
		auto* map = RE::TES::GetSingleton()->GetRuntimeData2().navMeshInfoMap;   // (the info looked up first: the lookup may lock it)
		map->mapLock.LockForWrite();
		ia->adjacentMeshesArray = arr; ia->adjacentMeshCount = static_cast<std::uint16_t>(ia->adjacentMeshCount + 1);
		map->mapLock.UnlockForWrite();
	}

	// is a point inside a triangle seen from above, the triangle's surface within a_dz of it
	bool Inside(const RE::BSNavmesh& m, const RE::BSNavmeshTriangle& t, const RE::NiPoint3& q, double a_dz)
	{
		const auto& a = m.vertices[t.vertices[0]].location; const auto& b = m.vertices[t.vertices[1]].location; const auto& c = m.vertices[t.vertices[2]].location;
		const double d = double(b.x - a.x) * (c.y - a.y) - double(b.y - a.y) * (c.x - a.x);
		if (std::abs(d) < 1e-6) return false;
		const double l1 = (double(b.x - q.x) * (c.y - q.y) - double(b.y - q.y) * (c.x - q.x)) / d, l2 = (double(c.x - q.x) * (a.y - q.y) - double(c.y - q.y) * (a.x - q.x)) / d;
		if (std::min({ l1, l2, 1 - l1 - l2 }) < 1e-4) return false;
		return std::abs(l1 * a.z + l2 * b.z + (1 - l1 - l2) * c.z - q.z) < a_dz;
	}
	std::size_t FootOf(const RE::NiPoint3& p)
	{
		std::size_t best = 0;
		for (std::size_t f = 1; f < g_ours.feet.size(); ++f)
			if (std::hypot(p.x - g_ours.feet[f][0], p.y - g_ours.feet[f][1]) < std::hypot(p.x - g_ours.feet[best][0], p.y - g_ours.feet[best][1])) best = f;
		return best;
	}

	RE::NiPoint3 Centre(const RE::BSNavmesh& m, const RE::BSNavmeshTriangle& t)
	{
		RE::NiPoint3 p{};
		for (auto vi : t.vertices) p += m.vertices[vi].location;
		return p / 3.0f;
	}

	std::map<RE::NavMesh*, std::pair<std::size_t, std::size_t>> g_oursRange;   // where our triangles sit in each host

	// the fit's own check, in the log: can the ground at each stair foot path to each door's landing, and back? Over the links and
	// portals as the fitted navmesh holds them (a breadth-first search, not the engine's pathing: what it shows is the graph)
	void Reachability(const std::map<RE::FormID, Mesh*>& a_byId)
	{
		using Node = std::pair<Mesh*, std::uint16_t>;
		auto next = [&](const Node& n, auto&& a_visit) {
			const auto& m = *n.first->m;
			const auto& t = m.triangles[n.second];
			for (int e = 0; e < 3; ++e) {
				const auto nb = t.triangles[e];
				if (nb == kNone) continue;
				if (t.triangleFlags.any(static_cast<TriFlag>(1 << e))) {
					if (nb >= m.extraEdgeInfo.size() || m.extraEdgeInfo[nb].type.get() != RE::EDGE_EXTRA_INFO_TYPE::kPortal) continue;
					const auto& pe = m.extraEdgeInfo[nb].portal;
					auto        o = a_byId.find(pe.otherMeshID);
					if (o != a_byId.end() && pe.triangle < o->second->m->triangles.size()) a_visit(Node{ o->second, pe.triangle });
				} else if (nb < m.triangles.size()) a_visit(Node{ n.first, nb });
			}
		};
		auto reach = [&](const std::vector<Node>& a_from, const std::set<Node>& a_to) {
			std::set<Node>    seen(a_from.begin(), a_from.end());
			std::vector<Node> q(a_from.begin(), a_from.end());
			for (std::size_t h = 0; h < q.size() && q.size() < 200000; ++h) {
				if (a_to.contains(q[h])) return true;
				next(q[h], [&](const Node& x) {
					if (!x.first->m->triangles[x.second].triangleFlags.any(TriFlag::kDeleted) && seen.insert(x).second) q.push_back(x);
				});
			}
			return false;
		};
		auto at = [&](const RE::NiPoint3& p, double r, bool ours) {   // the triangles near a point (ours, or the ground's own)
			std::vector<Node> out;
			for (auto& mm : g_app.meshes) {
				const auto& m = *mm.m;
				const auto  r_ = g_oursRange.find(mm.nm);   // (the carved ground's parts are appended too: ours is its own range)
				if (ours && r_ == g_oursRange.end()) continue;
				const std::size_t lo = ours ? r_->second.first : 0, hi = ours ? r_->second.second : m.triangles.size();
				for (std::size_t i = lo; i < hi; ++i) {
					if (!ours && r_ != g_oursRange.end() && i >= r_->second.first && i < r_->second.second) continue;
					const auto& t = m.triangles[i];
					if (t.triangleFlags.any(TriFlag::kDeleted)) continue;
					const auto c = Centre(m, t);
					if (std::hypot(c.x - p.x, c.y - p.y) <= r && std::abs(c.z - p.z) < 120) out.push_back({ &mm, static_cast<std::uint16_t>(i) });
				}
			}
			return out;
		};
		std::string line;
		for (std::size_t d = 0; d < g_ours.anchors.size(); ++d) {
			const auto door = at(g_ours.anchors[d], 60, true);
			const std::set<Node> doorSet(door.begin(), door.end());
			for (std::size_t f = 0; f < g_ours.feet.size(); ++f) {
				const auto&        ft = g_ours.feet[f];
				const RE::NiPoint3 F{ static_cast<float>(ft[0]), static_cast<float>(ft[1]), static_cast<float>(ft[2]) };
				auto ground = at(F, ft[3] + 200, false);
				std::erase_if(ground, [&](const Node& n) { return std::hypot(Centre(*n.first->m, n.first->m->triangles[n.second]).x - F.x, Centre(*n.first->m, n.first->m->triangles[n.second]).y - F.y) < ft[3]; });   // a ring beyond the foot
				const std::set<Node> groundSet(ground.begin(), ground.end());
				line += std::format("door {} <- foot {}: {}, -> {}; ", d, f, door.empty() || ground.empty() ? "?" : (reach(ground, doorSet) ? "yes" : "NO"),
					door.empty() || ground.empty() ? "?" : (reach(door, groundSet) ? "yes" : "NO"));
			}
		}
		SKSE::log::info("outdoor navmesh reach (the ground round each stair foot to each door's landing, and back): {}", line.empty() ? "no anchors" : line);
	}

	void DoApply()
	{
		const auto t0 = std::chrono::steady_clock::now();
		Load();
		if (!g_ours.ok) return;
		if (StillIn()) return;
		if (g_app.in) RevertNow("a navmesh was loaded again");
		auto meshes = LoadedMeshes();
		std::set<std::pair<int, int>> have;
		for (const auto& m : meshes) have.insert({ m.cx, m.cy });
		for (const auto& c : g_ours.cells)
			if (!have.contains(c)) return;   // later, when all the hall's cells are loaded
		g_editedTris.clear();
		g_oursRange.clear();
		g_app = Applied{};
		g_app.meshes = meshes;
		std::map<RE::NavMesh*, Mesh*> byNm;
		std::map<RE::FormID, Mesh*>   byId;
		for (auto& m : g_app.meshes) { byNm[m.nm] = &m; byId[m.id] = &m; }

		// what the fit adds to a navmesh is recorded (its sizes, its grid) before the first addition, to take it out again
		auto record = [&](Mesh* a_m) {
			for (const auto& h : g_app.hosts)
				if (h.nm == a_m->nm) return;
			BackupGrid(a_m->nm);
			g_app.hosts.push_back({ a_m->nm, a_m->id, a_m->m->vertices.size(), a_m->m->triangles.size(), a_m->m->extraEdgeInfo.size(), 0, 0, 0 });
		};
		std::set<std::pair<RE::FormID, RE::FormID>> joined;   // navmesh pairs our portals join
		auto linkTo = [&](Mesh* a_from, std::uint16_t a_tri, int a_edge, Mesh* a_to, std::uint16_t a_toTri, int a_toEdge) {
			auto& tr = a_from->m->triangles[a_tri];
			if (a_from == a_to) { tr.triangles[a_edge] = a_toTri; tr.triangleFlags.reset(static_cast<TriFlag>(1 << a_edge)); return; }
			record(a_from);
			RE::BSNavmeshEdgeExtraInfo x{};
			x.type = RE::EDGE_EXTRA_INFO_TYPE::kPortal;
			x.portal.otherMeshID = a_to->id; x.portal.triangle = a_toTri; x.portal.edgeIndex = static_cast<std::int8_t>(a_toEdge);
			a_from->m->extraEdgeInfo.push_back(x);
			tr.triangles[a_edge] = static_cast<std::uint16_t>(a_from->m->extraEdgeInfo.size() - 1);
			tr.triangleFlags.set(static_cast<TriFlag>(1 << a_edge));
			joined.insert({ std::min(a_from->id, a_to->id), std::max(a_from->id, a_to->id) });
		};

		// ---- 1. the ground the hall blocks: inside the outline (outdoor_nav.py: the hall's footprint, where its highest surface stands 30..900
		//      over the land, 12 out from it; and ours, 2026-11-13: the hillside over the grand stair's cutting stalled the followers).
		//      Each ground triangle against it, exactly (Clipper2): clear of it, kept; inside it, cut; across it (2026-11-13: the piers at
		//      the grand stair's foot stand on one road triangle, and followers walked into them), carved on its line, below.
		//      (Until 2026-11-13 sampled every 8 and carved on a 32 lattice: 3021 ground triangles out of 165.)
		auto blocked = [&](const RE::NiPoint3& p) { return InBlocked(p.x, p.y); };
		auto planeZ = [](const std::array<RE::NiPoint3, 3>& P, double x, double y, double& z) {   // inside (by a margin), and the plane there
			const auto& a = P[0]; const auto& b = P[1]; const auto& c = P[2];
			const double d = double(b.x - a.x) * (c.y - a.y) - double(b.y - a.y) * (c.x - a.x);
			if (std::abs(d) < 1e-9) return -1.0;
			const double l1 = (double(b.x - x) * (c.y - y) - double(b.y - y) * (c.x - x)) / d, l2 = (double(c.x - x) * (a.y - y) - double(c.y - y) * (a.x - x)) / d;
			z = l1 * a.z + l2 * b.z + (1 - l1 - l2) * c.z;
			return std::min({ l1, l2, 1 - l1 - l2 });
		};
		auto corners = [](const RE::BSNavmesh& m, const RE::BSNavmeshTriangle& t) {
			return std::array<RE::NiPoint3, 3>{ m.vertices[t.vertices[0]].location, m.vertices[t.vertices[1]].location, m.vertices[t.vertices[2]].location };
		};
		auto pathOf = [](const std::array<RE::NiPoint3, 3>& P) { return Clipper2Lib::PathD{ { P[0].x, P[0].y }, { P[1].x, P[1].y }, { P[2].x, P[2].y } }; };
		auto blockedArea = [&](const Clipper2Lib::PathD& a_p) {   // how much of a ring lies inside the outline
			const auto  r = Clipper2Lib::GetBounds(a_p);
			const auto& b = g_ours.blockedBox;
			if (r.right < b.left || r.left > b.right || r.bottom < b.top || r.top > b.bottom) return 0.0;
			return std::abs(Clipper2Lib::Area(Clipper2Lib::Intersect(Clipper2Lib::PathsD{ a_p }, g_ours.blocked, Clipper2Lib::FillRule::EvenOdd, 3)));
		};
		auto crossesOn = [&](const RE::NiPoint3& A, const RE::NiPoint3& B) {   // does the outline's line cross a segment (between its ends)?
			for (const auto& r : g_ours.blocked)
				for (std::size_t q = 0; q < r.size(); ++q) {
					const auto& P = r[q]; const auto& Q = r[(q + 1) % r.size()];
					const double d = (B.x - A.x) * (Q.y - P.y) - (B.y - A.y) * (Q.x - P.x);
					if (std::abs(d) < 1e-9) continue;
					const double u = ((P.x - A.x) * (Q.y - P.y) - (P.y - A.y) * (Q.x - P.x)) / d, v = ((P.x - A.x) * (B.y - A.y) - (P.y - A.y) * (B.x - A.x)) / d;
					if (u > 1e-4 && u < 1 - 1e-4 && v >= 0 && v <= 1) return true;
				}
			return false;
		};
		const RE::NiPoint3 site{ static_cast<float>(g_ours.sx), static_cast<float>(g_ours.sy), 0 };
		std::set<std::pair<RE::NavMesh*, std::uint16_t>>                               cut;
		std::map<RE::NavMesh*, int>                                                     cutCount;
		std::map<std::pair<RE::NavMesh*, std::uint16_t>, std::vector<RE::NiPoint3>>     touched;   // carved
		int portalWhole = 0;
		for (auto& mm : g_app.meshes) {
			auto& m = *mm.m;
			for (std::size_t i = 0; i < m.triangles.size(); ++i) {
				const auto& t = m.triangles[i];
				if (t.triangleFlags.any(TriFlag::kDeleted)) continue;
				const auto P = corners(m, t);
				if (std::max({ std::hypot(P[0].x - site.x, P[0].y - site.y), std::hypot(P[1].x - site.x, P[1].y - site.y), std::hypot(P[2].x - site.x, P[2].y - site.y) }) > 4000) continue;
				const auto   T = pathOf(P);
				const double at = std::abs(Clipper2Lib::Area(T)), ab = blockedArea(T);
				if (ab < std::max(1.0, at * 0.005)) continue;
				const std::pair<RE::NavMesh*, std::uint16_t> key{ mm.nm, static_cast<std::uint16_t>(i) };
				if (ab > at - std::max(1.0, at * 0.005)) { cut.insert(key); ++cutCount[mm.nm]; continue; }
				// a cell-border (portal) edge is never split (the two navmeshes' ends differ a little): one the outline crosses goes whole,
				// by where its middle lies
				bool portalCrossed = false;
				for (int e = 0; e < 3 && !portalCrossed; ++e)
					if (t.triangleFlags.any(static_cast<TriFlag>(1 << e)) && crossesOn(P[e], P[(e + 1) % 3])) portalCrossed = true;
				if (portalCrossed) {
					++portalWhole;
					if (blocked((P[0] + P[1] + P[2]) / 3.0f)) { cut.insert(key); ++cutCount[mm.nm]; }
					continue;
				}
				touched[key] = {};
			}
		}
		for (auto& mm : g_app.meshes) {
			auto& m = *mm.m;
			for (std::size_t i = 0; i < m.triangles.size(); ++i) {
				auto&      t = m.triangles[i];
				const bool isCut = cut.contains({ mm.nm, static_cast<std::uint16_t>(i) });
				for (int e = 0; e < 3; ++e) {
					const auto nb = t.triangles[e];
					if (nb == kNone) continue;
					bool drop = isCut;
					if (!drop) {
						if (t.triangleFlags.any(static_cast<TriFlag>(1 << e))) {
							if (nb < m.extraEdgeInfo.size()) {
								const auto& p = m.extraEdgeInfo[nb].portal;
								if (auto o = byId.find(p.otherMeshID); o != byId.end()) drop = cut.contains({ o->second->nm, p.triangle });
							}
						} else drop = cut.contains({ mm.nm, nb });
					}
					if (drop) {
						Touch(mm.nm, static_cast<std::uint16_t>(i));
						t.triangles[e] = kNone;
						t.triangleFlags.reset(static_cast<TriFlag>(1 << e));
					}
				}
				if (isCut) { Touch(mm.nm, static_cast<std::uint16_t>(i)); t.triangleFlags.set(TriFlag::kDeleted); }
			}
		}
		for (const auto& [nm, n] : cutCount) {   // out of their lookup grids
			BackupGrid(nm);
			auto& m = *static_cast<RE::BSNavmesh*>(nm); auto& g = m.meshGrid;
			for (std::size_t c = 0; c < static_cast<std::size_t>(g.gridSize) * g.gridSize; ++c) {
				std::vector<std::uint16_t> keep;
				for (auto ti : g.gridData[c]) if (!cut.contains({ nm, ti })) keep.push_back(ti);
				if (keep.size() != g.gridData[c].size()) { g.gridData[c].clear(); for (auto v : keep) g.gridData[c].push_back(v); }
			}
		}

		// ---- 1b. the carve, on the outline's own line (2026-11-13; it was a 32 lattice). Each carved triangle's edges are split where the
		//      outline crosses them (from the edge itself, lower vertex to higher, so both sides agree; a cell-border edge never: step 1
		//      took such a triangle whole); the triangle across a split edge is re-cut with the same points. Each: its part outside the
		//      outline (Clipper2), triangulated (earcut) on its corners, the split points and the outline's corners inside it. Its first
		//      part takes its index; whole edges are linked by the game's own link, split ones segment by segment.
		using TriKey = std::pair<RE::NavMesh*, std::uint16_t>;
		using EdgeKey = std::tuple<RE::NavMesh*, std::uint16_t, std::uint16_t>;   // (navmesh, lower vertex, higher vertex)
		auto ekey = [](RE::NavMesh* nm, std::uint16_t a, std::uint16_t b) { return EdgeKey{ nm, std::min(a, b), std::max(a, b) }; };
		std::map<EdgeKey, std::vector<RE::NiPoint3>> split;   // points from the lower vertex to the higher
		std::set<TriKey>                             retri;
		auto edgePoints = [&](const RE::NiPoint3& A, const RE::NiPoint3& B) {
			std::vector<RE::NiPoint3> out;
			const double L = std::hypot(B.x - A.x, B.y - A.y);
			if (L < 1e-6) return out;
			std::vector<double> us;
			for (const auto& r : g_ours.blocked)
				for (std::size_t q = 0; q < r.size(); ++q) {
					const auto& P = r[q]; const auto& Q = r[(q + 1) % r.size()];
					const double d = (B.x - A.x) * (Q.y - P.y) - (B.y - A.y) * (Q.x - P.x);
					if (std::abs(d) < 1e-9) continue;
					const double u = ((P.x - A.x) * (Q.y - P.y) - (P.y - A.y) * (Q.x - P.x)) / d, v = ((P.x - A.x) * (B.y - A.y) - (P.y - A.y) * (B.x - A.x)) / d;
					if (u * L > 0.5 && (1 - u) * L > 0.5 && v >= 0 && v <= 1) us.push_back(u);
				}
			std::sort(us.begin(), us.end());
			for (double u : us)
				if (out.empty() || (u - (std::hypot(out.back().x - A.x, out.back().y - A.y) / L)) * L > 0.5) out.push_back(A + (B - A) * static_cast<float>(u));
			return out;
		};
		for (const auto& [key, unused_] : touched) {
			auto&       m = *byNm[key.first]->m;
			const auto& t = m.triangles[key.second];
			retri.insert(key);
			for (int k = 0; k < 3; ++k) {
				const auto a = t.vertices[k], b = t.vertices[(k + 1) % 3];
				const auto ek = ekey(key.first, a, b);
				const bool portal = t.triangleFlags.any(static_cast<TriFlag>(1 << k));
				if (!split.contains(ek)) split[ek] = portal ? std::vector<RE::NiPoint3>{} : edgePoints(m.vertices[std::min(a, b)].location, m.vertices[std::max(a, b)].location);
				const auto nb = t.triangles[k];
				if (portal || nb == kNone || nb >= m.triangles.size() || split[ek].empty()) continue;
				if (!cut.contains({ key.first, nb }) && !m.triangles[nb].triangleFlags.any(TriFlag::kDeleted)) retri.insert({ key.first, nb });
			}
		}
		struct Re
		{
			Mesh*                                    mm = nullptr;
			std::uint16_t                            orig = 0;
			RE::BSNavmeshTriangle                    G{};
			std::vector<std::array<std::uint16_t, 3>> parts;   // mesh vertex indices
			std::vector<std::uint16_t>               idx;     // mesh triangle indices
		};
		std::map<TriKey, Re>                          res;
		std::map<std::pair<EdgeKey, int>, std::uint16_t> splitVert;   // the vertex made for a split point, shared by both sides
		int dropped = 0, keptParts = 0;
		for (const auto& key : retri) {
			Mesh* mm = byNm[key.first];
			auto& m = *mm->m;
			if (m.vertices.size() + 2000 >= kNone || m.triangles.size() + 1500 >= kNone) continue;
			Re r;
			r.mm = mm; r.orig = key.second; r.G = m.triangles[key.second];
			const auto P = corners(m, r.G);
			std::vector<RE::NiPoint3> X;
			for (int k = 0; k < 3; ++k) {
				const auto a = r.G.vertices[k], b = r.G.vertices[(k + 1) % 3];
				const auto ek = ekey(key.first, a, b);
				X.push_back(P[k]);
				const auto pts = split.contains(ek) ? split[ek] : std::vector<RE::NiPoint3>{};
				for (std::size_t q = 0; q < pts.size(); ++q) X.push_back(pts[a > b ? pts.size() - 1 - q : q]);   // (from a to b)
			}
			const int nb = static_cast<int>(X.size());
			// the part outside the outline (collinear points kept: the split points stay shared with the triangles across), each piece with
			// its holes triangulated
			auto         cr = [](const RE::NiPoint3& o, const RE::NiPoint3& p, const RE::NiPoint3& q) { return double(p.x - o.x) * (q.y - o.y) - double(p.y - o.y) * (q.x - o.x); };
			const double sgn = cr(P[0], P[1], P[2]) >= 0 ? 1.0 : -1.0;
			Clipper2Lib::PathD subj;
			for (const auto& x : X) subj.emplace_back(x.x, x.y);
			Clipper2Lib::ClipperD cl(3);
			cl.PreserveCollinear(true);
			cl.AddSubject(Clipper2Lib::PathsD{ subj });
			cl.AddClip(g_ours.blocked);
			Clipper2Lib::PolyTreeD tree;
			cl.Execute(Clipper2Lib::ClipType::Difference, Clipper2Lib::FillRule::EvenOdd, tree);
			auto pointIdx = [&](const Clipper2Lib::PointD& q) {
				for (std::size_t k = 0; k < X.size(); ++k)
					if (std::abs(X[k].x - q.x) < 0.05 && std::abs(X[k].y - q.y) < 0.05) return static_cast<int>(k);
				double z = 0;
				planeZ(P, q.x, q.y, z);
				X.emplace_back(static_cast<float>(q.x), static_cast<float>(q.y), static_cast<float>(z));
				return static_cast<int>(X.size() - 1);
			};
			std::vector<std::array<int, 3>> keep;
			std::function<void(const Clipper2Lib::PolyPathD&)> pieces = [&](const Clipper2Lib::PolyPathD& a_node) {
				for (const auto& outer : a_node) {   // an outer ring; its children are its holes, theirs outer rings again
					std::vector<std::vector<std::array<double, 2>>> poly;
					std::vector<int>                                ids;
					auto ring = [&](const Clipper2Lib::PathD& a_r) {   // (the boundary's own points put back on it wherever they lie on a side:
						poly.emplace_back();                            //  the joins never rest on the clipper keeping collinear points)
						for (std::size_t q = 0; q < a_r.size(); ++q) {
							const auto& A = a_r[q]; const auto& B = a_r[(q + 1) % a_r.size()];
							poly.back().push_back({ A.x, A.y }); ids.push_back(pointIdx(A));
							const double L2 = (B.x - A.x) * (B.x - A.x) + (B.y - A.y) * (B.y - A.y);
							if (L2 < 1e-12) continue;
							std::vector<std::pair<double, int>> on;
							for (int k = 0; k < nb; ++k) {
								const double u = ((X[k].x - A.x) * (B.x - A.x) + (X[k].y - A.y) * (B.y - A.y)) / L2;
								const double d = std::abs((B.x - A.x) * (X[k].y - A.y) - (B.y - A.y) * (X[k].x - A.x)) / std::sqrt(L2);
								if (u > 1e-6 && u < 1 - 1e-6 && d < 0.05) on.emplace_back(u, k);
							}
							std::sort(on.begin(), on.end());
							for (const auto& [u, k] : on) { poly.back().push_back({ X[k].x, X[k].y }); ids.push_back(k); }
						}
					};
					ring(outer->Polygon());
					for (const auto& hole : *outer) ring(hole->Polygon());
					const auto tri = mapbox::earcut<std::uint32_t>(poly);
					for (std::size_t q = 0; q + 2 < tri.size(); q += 3) {
						std::array<int, 3> t3{ ids[tri[q]], ids[tri[q + 1]], ids[tri[q + 2]] };
						const double       a2 = cr(X[t3[0]], X[t3[1]], X[t3[2]]);
						if (t3[0] == t3[1] || t3[1] == t3[2] || t3[0] == t3[2] || std::abs(a2) < 0.5) { ++dropped; continue; }
						if (a2 * sgn < 0) std::swap(t3[1], t3[2]);
						keep.push_back(t3);
					}
					for (const auto& hole : *outer) pieces(*hole);
				}
			};
			pieces(tree);
			// the mesh's vertices: corners are its own; split points shared by both sides of their edge; the rest new
			record(mm);
			std::vector<std::uint16_t> vx(X.size(), kNone);
			{
				int bi = 0;
				for (int k = 0; k < 3; ++k) {
					const auto a = r.G.vertices[k], b = r.G.vertices[(k + 1) % 3];
					const auto ek = ekey(key.first, a, b);
					vx[bi++] = a;
					const auto n = split.contains(ek) ? split[ek].size() : 0;
					for (std::size_t q = 0; q < n; ++q, ++bi) {
						const int j = a > b ? static_cast<int>(n - 1 - q) : static_cast<int>(q);
						auto      f = splitVert.find({ ek, j });
						if (f == splitVert.end()) {
							m.vertices.push_back(RE::BSNavmeshVertex{ X[bi] });
							f = splitVert.emplace(std::make_pair(ek, j), static_cast<std::uint16_t>(m.vertices.size() - 1)).first;
						}
						vx[bi] = f->second;
					}
				}
			}
			for (const auto& t3 : keep)
				for (int c = 0; c < 3; ++c)
					if (vx[t3[c]] == kNone) { m.vertices.push_back(RE::BSNavmeshVertex{ X[t3[c]] }); vx[t3[c]] = static_cast<std::uint16_t>(m.vertices.size() - 1); }
			for (const auto& t3 : keep) r.parts.push_back({ vx[t3[0]], vx[t3[1]], vx[t3[2]] });
			keptParts += static_cast<int>(keep.size());
			res[key] = std::move(r);
		}
		// write the parts: the first takes the original's index (or, none kept, the original goes as cut)
		for (auto& [key, r] : res) {
			auto& m = *r.mm->m;
			Touch(key.first, key.second);
			for (std::size_t q = 0; q < r.parts.size(); ++q) {
				std::uint16_t i = key.second;
				if (q > 0) { i = static_cast<std::uint16_t>(m.triangles.size()); m.triangles.push_back(RE::BSNavmeshTriangle{}); }
				auto& tr = m.triangles[i];
				tr = RE::BSNavmeshTriangle{};
				tr.triangleFlags = r.G.triangleFlags;
				for (int c = 0; c < 3; ++c) { tr.vertices[c] = r.parts[q][c]; tr.triangles[c] = kNone; tr.triangleFlags.reset(static_cast<TriFlag>(1 << c)); }
				tr.triangleFlags.reset(TriFlag::kDeleted);
				r.idx.push_back(i);
			}
			if (r.parts.empty()) {
				auto& tr = m.triangles[key.second];
				for (int c = 0; c < 3; ++c) { tr.triangles[c] = kNone; tr.triangleFlags.reset(static_cast<TriFlag>(1 << c)); }
				tr.triangleFlags.set(TriFlag::kDeleted);
				cut.insert(key); ++cutCount[key.first];
			}
		}
		// which triangle (and edge) now holds original edge k of a ground triangle whole; none: cut, or its part there dropped
		auto holder = [&](const TriKey& key, int k, std::uint16_t& a_tri, int& a_edge) {
			if (cut.contains(key)) return false;
			auto f = res.find(key);
			if (f == res.end()) { a_tri = key.second; a_edge = k; return true; }
			const auto a = f->second.G.vertices[k], b = f->second.G.vertices[(k + 1) % 3];
			for (std::size_t q = 0; q < f->second.parts.size(); ++q)
				for (int c = 0; c < 3; ++c)
					if (f->second.parts[q][c] == a && f->second.parts[q][(c + 1) % 3] == b) { a_tri = f->second.idx[q]; a_edge = c; return true; }
			return false;
		};
		auto origOf = [&](const TriKey& key) -> const RE::BSNavmeshTriangle& {
			auto f = res.find(key);
			return f != res.end() ? f->second.G : static_cast<RE::BSNavmesh*>(key.first)->triangles[key.second];
		};
		for (auto& [key, r] : res) {
			auto& m = *r.mm->m;
			std::map<std::pair<std::uint16_t, std::uint16_t>, std::pair<std::uint16_t, int>> emap;   // part edge -> (triangle, edge)
			for (std::size_t q = 0; q < r.parts.size(); ++q)
				for (int c = 0; c < 3; ++c) emap[{ r.parts[q][c], r.parts[q][(c + 1) % 3] }] = { r.idx[q], c };
			for (const auto& [e, te] : emap)   // inside
				if (auto o = emap.find({ e.second, e.first }); o != emap.end()) m.triangles[te.first].triangles[te.second] = o->second.first;
			for (int k = 0; k < 3; ++k) {
				const auto  a = r.G.vertices[k], b = r.G.vertices[(k + 1) % 3];
				const bool  portal = r.G.triangleFlags.any(static_cast<TriFlag>(1 << k));
				const auto  nbv = r.G.triangles[k];
				const auto  ek = ekey(key.first, a, b);
				const bool  whole = !split.contains(ek) || split[ek].empty();
				// the triangle across, as it was
				Mesh*         om = nullptr;
				std::uint16_t ot = 0;
				int           oe = -1;
				if (nbv != kNone) {
					if (portal) {
						if (nbv < m.extraEdgeInfo.size()) {
							const auto pe = m.extraEdgeInfo[nbv].portal;
							if (auto f = byId.find(pe.otherMeshID); f != byId.end() && pe.triangle < f->second->m->triangles.size() && pe.edgeIndex >= 0 && pe.edgeIndex <= 2) { om = f->second; ot = pe.triangle; oe = pe.edgeIndex; }
						}
					} else if (nbv < m.triangles.size()) {
						om = r.mm; ot = nbv;
						const auto& O = origOf({ key.first, nbv });
						for (int k2 = 0; k2 < 3; ++k2)
							if (O.triangles[k2] == key.second && !O.triangleFlags.any(static_cast<TriFlag>(1 << k2))) oe = k2;
					}
				}
				const bool live = om && oe >= 0 && !cut.contains({ om->nm, ot });
				if (whole) {
					std::uint16_t mt; int mc;
					const bool    mine = holder(key, k, mt, mc);
					std::uint16_t tt; int tc;
					const bool    theirs = live && holder({ om->nm, ot }, oe, tt, tc);
					if (mine && theirs) linkTo(r.mm, mt, mc, om, tt, tc);
					if (live && !res.contains({ om->nm, ot })) {   // the untouched side: pointed at the part now holding the edge, or let go
						Touch(om->nm, ot);
						auto& T_ = om->m->triangles[ot];
						if (mine) linkTo(om, ot, oe, r.mm, mt, mc);
						else { T_.triangles[oe] = kNone; T_.triangleFlags.reset(static_cast<TriFlag>(1 << oe)); }
					}
					continue;
				}
				// split (same navmesh): segment by segment, against the parts across
				auto o = live ? res.find({ om->nm, ot }) : res.end();
				for (const auto& [e, te] : emap) {
					if (emap.contains({ e.second, e.first })) continue;   // inside
					bool on = false;   // both ends on this edge: its corners or its split points
					auto isOn = [&](std::uint16_t v) {
						if (v == a || v == b) return true;
						const auto n = split[ek].size();
						for (std::size_t j = 0; j < n; ++j) if (auto f = splitVert.find({ ek, static_cast<int>(j) }); f != splitVert.end() && f->second == v) return true;
						return false;
					};
					on = isOn(e.first) && isOn(e.second);
					if (!on || o == res.end()) continue;
					for (std::size_t q = 0; q < o->second.parts.size(); ++q)
						for (int c = 0; c < 3; ++c)
							if (o->second.parts[q][c] == e.second && o->second.parts[q][(c + 1) % 3] == e.first) m.triangles[te.first].triangles[te.second] = o->second.idx[q];
				}
			}
		}
		if (!touched.empty())
			SKSE::log::info("outdoor navmesh carve: {} ground triangle(s) carved, {} re-triangulated beside them; {} part(s) kept, {} dropped",
				touched.size(), res.size() - touched.size(), keptParts, dropped);

		// ---- 2. hosts: one per cell
		std::map<std::pair<int, int>, Mesh*> host;
		for (auto& mm : g_app.meshes) {
			const std::pair<int, int> cl{ mm.cx, mm.cy };
			if (!g_ours.cells.contains(cl)) continue;
			auto score = [&](Mesh* a) { return std::make_pair(cutCount[a->nm], a->m->triangles.size()); };
			if (!host.contains(cl) || score(&mm) > score(host[cl])) host[cl] = &mm;
		}
		const auto        nOurs = g_ours.tris.size();
		std::vector<Mesh*> hostOf(nOurs);
		std::map<Mesh*, std::vector<int>> members;
		for (std::size_t i = 0; i < nOurs; ++i) {
			const auto& t = g_ours.tris[i];
			const auto  p = (g_ours.verts[t[0]] + g_ours.verts[t[1]] + g_ours.verts[t[2]]) / 3.0f;
			hostOf[i] = host[{ static_cast<int>(std::floor(p.x / 4096.0)), static_cast<int>(std::floor(p.y / 4096.0)) }];
			if (!hostOf[i]) { g_app.summary = "a cell of ours has no navmesh"; RevertNow("no host"); return; }
			members[hostOf[i]].push_back(static_cast<int>(i));
		}
		std::vector<std::uint16_t> local(nOurs);
		std::map<Mesh*, std::size_t> base;
		for (auto& [h, mem] : members) {
			base[h] = h->m->triangles.size();
			if (base[h] + mem.size() + 64 >= kNone) { g_app.summary = "a host would overflow"; RevertNow("overflow"); return; }
			for (std::size_t k = 0; k < mem.size(); ++k) local[mem[k]] = static_cast<std::uint16_t>(base[h] + k);
			record(h);
			g_oursRange[h->nm] = { base[h], base[h] + mem.size() };
		}
		auto edgeOf = [&](int a_tri, int a_u, int a_v) {      // which edge of our triangle a_tri runs a_u..a_v
			const auto& t = g_ours.tris[a_tri];
			for (int e = 0; e < 3; ++e)
				if ((t[e] == a_u && t[(e + 1) % 3] == a_v) || (t[e] == a_v && t[(e + 1) % 3] == a_u)) return e;
			return -1;
		};
		for (auto& [h, mem] : members) {
			auto&                    m = *h->m;
			std::map<int, std::uint16_t> vmap;
			auto vid = [&](int a_v) {
				if (auto f = vmap.find(a_v); f != vmap.end()) return f->second;
				m.vertices.push_back(RE::BSNavmeshVertex{ g_ours.verts[a_v] });
				return vmap[a_v] = static_cast<std::uint16_t>(m.vertices.size() - 1);
			};
			for (int i : mem) {
				const auto&           t = g_ours.tris[i];
				RE::BSNavmeshTriangle tr{};
				for (int k = 0; k < 3; ++k) tr.vertices[k] = vid(t[k]);
				tr.triangleFlags.set(static_cast<TriFlag>(1 << 11));                  // Found, as vanilla's are (Hall2.cs writes it on ours inside)
				if (g_ours.preferred) tr.triangleFlags.set(TriFlag::kPreferred);       // as vanilla's roads (the whole outdoor mesh)
				for (int e = 0; e < 3; ++e) {
					const int nb = t[3 + e];
					if (nb < 0) { tr.triangles[e] = kNone; continue; }
					if (hostOf[nb] == h) { tr.triangles[e] = local[nb]; continue; }
					const int oe = edgeOf(nb, t[e], t[(e + 1) % 3]);
					RE::BSNavmeshEdgeExtraInfo x{};
					x.type = RE::EDGE_EXTRA_INFO_TYPE::kPortal;
					x.portal.otherMeshID = hostOf[nb]->id; x.portal.triangle = local[nb]; x.portal.edgeIndex = static_cast<std::int8_t>(std::max(0, oe));
					m.extraEdgeInfo.push_back(x);
					tr.triangles[e] = static_cast<std::uint16_t>(m.extraEdgeInfo.size() - 1);
					tr.triangleFlags.set(static_cast<TriFlag>(1 << e));
					joined.insert({ std::min(h->id, hostOf[nb]->id), std::max(h->id, hostOf[nb]->id) });
				}
				m.triangles.push_back(tr);
			}
		}

		// ---- 3. the feet: each open edge of ours near a stair foot is linked to the nearest ground edge (within 24 across and 40 up
		//      or down: the dry run's rule, stitch_dry.py); that ground edge, when open, is linked back to the nearest of ours
		auto& recorded = record;   // (a navmesh outside the hosts that gets portals of ours: its additions recorded too)
		auto link = [&](Mesh* a_from, std::uint16_t a_tri, int a_edge, Mesh* a_to, std::uint16_t a_toTri, int a_toEdge) {
			auto& tr = a_from->m->triangles[a_tri];
			if (a_from == a_to) { tr.triangles[a_edge] = a_toTri; return; }
			recorded(a_from);
			RE::BSNavmeshEdgeExtraInfo x{};
			x.type = RE::EDGE_EXTRA_INFO_TYPE::kPortal;
			x.portal.otherMeshID = a_to->id; x.portal.triangle = a_toTri; x.portal.edgeIndex = static_cast<std::int8_t>(a_toEdge);
			a_from->m->extraEdgeInfo.push_back(x);
			tr.triangles[a_edge] = static_cast<std::uint16_t>(a_from->m->extraEdgeInfo.size() - 1);
			tr.triangleFlags.set(static_cast<TriFlag>(1 << a_edge));
			joined.insert({ std::min(a_from->id, a_to->id), std::max(a_from->id, a_to->id) });
		};
		auto segD = [](const RE::NiPoint3& p, const RE::NiPoint3& a, const RE::NiPoint3& b, double& a_dz) {
			const double L = double(b.x - a.x) * (b.x - a.x) + double(b.y - a.y) * (b.y - a.y);
			const double u = L < 1e-9 ? 0.0 : std::clamp(((p.x - a.x) * double(b.x - a.x) + (p.y - a.y) * double(b.y - a.y)) / L, 0.0, 1.0);
			const double qx = a.x + u * (b.x - a.x), qy = a.y + u * (b.y - a.y), qz = a.z + u * (b.z - a.z);
			a_dz = p.z - qz;
			return std::hypot(p.x - qx, p.y - qy);
		};
		struct Near { double d = 1e9; Mesh* mesh = nullptr; std::uint16_t tri = 0; int edge = 0; };
		std::map<std::tuple<Mesh*, std::uint16_t, int>, std::pair<double, std::pair<int, int>>> backTo;   // a ground edge -> the nearest of ours
		int bridged = 0;
		for (std::size_t i = 0; i < nOurs; ++i) {
			const auto& t = g_ours.tris[i];
			for (int e = 0; e < 3; ++e) {
				if (t[3 + e] >= 0) continue;
				const auto mid = (g_ours.verts[t[e]] + g_ours.verts[t[(e + 1) % 3]]) / 2.0f;
				if (std::none_of(g_ours.feet.begin(), g_ours.feet.end(), [&](const auto& f) { return std::hypot(mid.x - f[0], mid.y - f[1]) <= f[3]; })) continue;
				// (2026-11-13: the back stair's bottom step runs 25 from the open edge the cut leaves beside it, and joined only a
				// linked ground edge, so nothing joined back) an open ground edge within 48 (60 up or down) first: it can join back
				Near best, open;
				for (auto& mm : g_app.meshes) {
					auto&             m = *mm.m;
					const std::size_t lim = base.contains(&mm) ? base[&mm] : m.triangles.size();   // the ground's own, not ours
					for (std::size_t g = 0; g < lim; ++g) {
						const auto& gt = m.triangles[g];
						if (gt.triangleFlags.any(TriFlag::kDeleted)) continue;
						for (int k = 0; k < 3; ++k) {
							double     dz = 0;
							const auto d = segD(mid, m.vertices[gt.vertices[k]].location, m.vertices[gt.vertices[(k + 1) % 3]].location, dz);
							if (d < 24 && std::abs(dz) < 40 && d < best.d) best = { d, &mm, static_cast<std::uint16_t>(g), k };
							if (d < 48 && std::abs(dz) < 60 && d < open.d && gt.triangles[k] == kNone && !gt.triangleFlags.any(static_cast<TriFlag>(1 << k)))
								open = { d, &mm, static_cast<std::uint16_t>(g), k };
						}
					}
				}
				if (open.mesh) best = open;
				if (!best.mesh) continue;
				link(hostOf[i], local[i], e, best.mesh, best.tri, best.edge);
				++bridged;
				const auto key = std::make_tuple(best.mesh, best.tri, best.edge);
				if (auto f = backTo.find(key); f == backTo.end() || best.d < f->second.first) backTo[key] = { best.d, { static_cast<int>(i), e } };
			}
		}
		int              backs = 0;
		std::vector<int> backsAt(g_ours.feet.size());
		for (const auto& [key, v] : backTo) {
			const auto [gm, gtri, ge] = key;
			auto& gt = gm->m->triangles[gtri];
			if (gt.triangles[ge] != kNone || gt.triangleFlags.any(static_cast<TriFlag>(1 << ge))) continue;   // still joined to the ground
			const int i = v.second.first;
			Touch(gm->nm, gtri);
			link(gm, gtri, ge, hostOf[i], local[i], v.second.second);
			++backs; ++backsAt[FootOf(g_ours.verts[g_ours.tris[i][v.second.second]])];
		}
		SKSE::log::info("outdoor navmesh: {} edge(s) of ours joined to the ground at the stair feet, {} joined back", bridged, backs);

		// ---- 3b. a foot the ground could not be joined back to (the back stair, 2026-11-13: its bottom step lands across two large
		//      ground triangles, every edge of them joined to more ground): the step's edge made the ground's too, its two ends
		//      inserted as points (each splits the triangle holding it in three) and, when they fall in two neighbouring triangles,
		//      the edge between those flipped onto the step's edge; the ground on its far side then joined to it, both ways
		int splits = 0;
		for (std::size_t f = 0; f < g_ours.feet.size(); ++f) {
			if (backsAt[f]) continue;
			const auto& ft = g_ours.feet[f];
			auto holder = [&](const RE::NiPoint3& p, Mesh*& a_m, std::uint16_t& a_t) {   // the kept ground triangle holding a point
				for (auto& mm : g_app.meshes) {
					const std::size_t lim = base.contains(&mm) ? base[&mm] : mm.m->triangles.size();
					for (std::size_t g = 0; g < lim; ++g) {
						const auto& gt = mm.m->triangles[g];
						if (!gt.triangleFlags.any(TriFlag::kDeleted) && Inside(*mm.m, gt, p, 60)) { a_m = &mm; a_t = static_cast<std::uint16_t>(g); return true; }
					}
				}
				return false;
			};
			struct Cand { double len = 0; int i = -1, e = 0; Mesh* gm = nullptr; std::uint16_t g1 = 0, g2 = 0; };
			Cand best;
			for (std::size_t i = 0; i < nOurs; ++i) {
				const auto& t = g_ours.tris[i];
				for (int e = 0; e < 3; ++e) {
					if (t[3 + e] >= 0) continue;
					const auto& a = g_ours.verts[t[e]]; const auto& b = g_ours.verts[t[(e + 1) % 3]];
					if (std::hypot((a.x + b.x) / 2 - ft[0], (a.y + b.y) / 2 - ft[1]) > ft[3]) continue;
					const double len = std::hypot(b.x - a.x, b.y - a.y);
					if (len <= best.len) continue;
					Mesh* ma = nullptr; Mesh* mb = nullptr; std::uint16_t ta = 0, tb = 0;
					if (!holder(a, ma, ta) || !holder(b, mb, tb) || ma != mb) continue;
					if (ta != tb) {   // two triangles: neighbours by a plain link
						const auto& A3 = ma->m->triangles[ta];
						bool        nb = false;
						for (int c = 0; c < 3; ++c) nb |= A3.triangles[c] == tb && !A3.triangleFlags.any(static_cast<TriFlag>(1 << c));
						if (!nb) continue;
					}
					best = { len, static_cast<int>(i), e, ma, ta, tb };
				}
			}
			if (!best.gm) { SKSE::log::info("outdoor navmesh: foot {}: no ground under our foot's edges to split - joined one way only", f); continue; }
			auto& m = *best.gm->m;
			if (m.triangles.size() + 6 >= kNone) continue;
			const auto&        t = g_ours.tris[best.i];
			const RE::NiPoint3 A = g_ours.verts[t[best.e]], B = g_ours.verts[t[(best.e + 1) % 3]], Cv = g_ours.verts[t[(best.e + 2) % 3]];
			auto cr = [](const RE::NiPoint3& o, const RE::NiPoint3& p, const RE::NiPoint3& q) { return double(p.x - o.x) * (q.y - o.y) - double(p.y - o.y) * (q.x - o.x); };
			// the region, its boundary (each outer edge's neighbour as it was), and the new triangles over it
			std::vector<std::uint16_t> region{ best.g1 };
			if (best.g2 != best.g1) region.push_back(best.g2);
			struct Edge { std::uint16_t nb; bool portal; };
			std::map<std::pair<std::uint16_t, std::uint16_t>, Edge> outer;
			for (auto r : region) {
				const auto& tr = m.triangles[r];
				for (int c = 0; c < 3; ++c) {
					const bool portal = tr.triangleFlags.any(static_cast<TriFlag>(1 << c));
					if (!portal && std::find(region.begin(), region.end(), tr.triangles[c]) != region.end()) continue;
					outer[{ tr.vertices[c], tr.vertices[(c + 1) % 3] }] = { tr.triangles[c], portal };
				}
			}
			const auto ia = static_cast<std::uint16_t>(m.vertices.size()), ib = static_cast<std::uint16_t>(m.vertices.size() + 1);
			std::vector<std::array<std::uint16_t, 3>> parts;
			if (region.size() == 1) {
				const auto&                        G = m.triangles[best.g1];
				const std::array<std::uint16_t, 3> P{ G.vertices[0], G.vertices[1], G.vertices[2] };
				int                                k = 0;
				for (; k < 3; ++k) {   // which of a's three parts holds b
					const RE::NiPoint3 p = m.vertices[P[k]].location, q = m.vertices[P[(k + 1) % 3]].location;
					const double       s = cr(p, q, A);
					if (cr(p, q, B) * s > 0 && cr(q, A, B) * s > 0 && cr(A, p, B) * s > 0) break;
				}
				if (k == 3) continue;
				for (int j = 0; j < 3; ++j) parts.push_back({ P[j], P[(j + 1) % 3], j == k ? ib : ia });
				parts.push_back({ P[(k + 1) % 3], ia, ib });
				parts.push_back({ ia, P[k], ib });
			} else {
				const auto& G1 = m.triangles[best.g1];
				const auto& G2 = m.triangles[best.g2];
				int         s1 = 0;   // G1's edge to G2, u -> v
				for (; s1 < 3; ++s1)
					if (G1.triangles[s1] == best.g2 && !G1.triangleFlags.any(static_cast<TriFlag>(1 << s1))) break;
				if (s1 == 3) continue;
				const auto  u = G1.vertices[s1], v = G1.vertices[(s1 + 1) % 3];
				const auto& U = m.vertices[u].location;
				const auto& Vv = m.vertices[v].location;
				if (!(cr(U, Vv, A) * cr(U, Vv, B) < 0 && cr(A, B, U) * cr(A, B, Vv) < 0)) continue;   // ab must cross uv inside it, or the flip folds
				for (int c = 0; c < 3; ++c)
					if (c != s1) parts.push_back({ G1.vertices[c], G1.vertices[(c + 1) % 3], ia });
				for (int c = 0; c < 3; ++c)
					if (!(G2.vertices[c] == v && G2.vertices[(c + 1) % 3] == u)) parts.push_back({ G2.vertices[c], G2.vertices[(c + 1) % 3], ib });
				if (parts.size() != 4) continue;
				parts.push_back({ u, ib, ia });   // the flipped pair, ab between them
				parts.push_back({ v, ia, ib });
			}
			recorded(best.gm);
			for (auto r : region) Touch(best.gm->nm, r);
			m.vertices.push_back(RE::BSNavmeshVertex{ A });
			m.vertices.push_back(RE::BSNavmeshVertex{ B });
			const auto                 flags = m.triangles[best.g1].triangleFlags;
			const auto                 trav = m.triangles[best.g1].traversalFlags;
			std::vector<std::uint16_t> idx(parts.size());
			for (std::size_t q = 0; q < parts.size(); ++q) {
				if (q < region.size()) idx[q] = region[q];
				else {
					idx[q] = static_cast<std::uint16_t>(m.triangles.size());
					m.triangles.push_back(RE::BSNavmeshTriangle{});
				}
				auto& tr = m.triangles[idx[q]];
				tr = RE::BSNavmeshTriangle{};
				tr.triangleFlags = flags;
				tr.traversalFlags = trav;
				for (int c = 0; c < 3; ++c) {
					tr.vertices[c] = parts[q][c];
					tr.triangles[c] = kNone;
					tr.triangleFlags.reset(static_cast<TriFlag>(1 << c));
				}
			}
			auto old = [&](std::uint16_t x) { return std::find(region.begin(), region.end(), x) != region.end(); };
			for (std::size_t q = 0; q < parts.size(); ++q)
				for (int c = 0; c < 3; ++c) {
					auto&      tr = m.triangles[idx[q]];
					const auto x = parts[q][c], y = parts[q][(c + 1) % 3];
					if (auto o = outer.find({ x, y }); o != outer.end()) {   // an outer edge: its old neighbour, pointed back here
						tr.triangles[c] = o->second.nb;
						if (o->second.nb == kNone) continue;
						if (o->second.portal) {
							tr.triangleFlags.set(static_cast<TriFlag>(1 << c));
							if (o->second.nb >= m.extraEdgeInfo.size()) continue;
							const auto pe = m.extraEdgeInfo[o->second.nb].portal;
							auto       om = byId.find(pe.otherMeshID);
							if (om == byId.end() || pe.edgeIndex < 0 || pe.edgeIndex > 2 || pe.triangle >= om->second->m->triangles.size()) continue;
							Touch(om->second->nm, pe.triangle);
							link(om->second, pe.triangle, pe.edgeIndex, best.gm, idx[q], c);
						} else if (o->second.nb < m.triangles.size()) {
							Touch(best.gm->nm, o->second.nb);
							auto& nt = m.triangles[o->second.nb];
							for (int d = 0; d < 3; ++d)
								if (!nt.triangleFlags.any(static_cast<TriFlag>(1 << d)) && old(nt.triangles[d]) && nt.vertices[d] == y && nt.vertices[(d + 1) % 3] == x) nt.triangles[d] = idx[q];
						}
						continue;
					}
					for (std::size_t r = 0; r < parts.size(); ++r)   // an inner edge
						for (int d = 0; d < 3; ++d)
							if (r != q && parts[r][d] == y && parts[r][(d + 1) % 3] == x) tr.triangles[c] = idx[r];
				}
			// ab: the part on the far side from our stair joins our edge, both ways; the near part (under the step) lets ab go
			auto         side = [&](const RE::NiPoint3& q) { return double(B.x - A.x) * (q.y - A.y) - double(B.y - A.y) * (q.x - A.x); };
			const double oursSide = side(Cv);
			int          joinedAb = 0;
			for (std::size_t q = 0; q < parts.size(); ++q) {
				auto& tr = m.triangles[idx[q]];
				for (int c = 0; c < 3; ++c) {
					if (!((tr.vertices[c] == ia && tr.vertices[(c + 1) % 3] == ib) || (tr.vertices[c] == ib && tr.vertices[(c + 1) % 3] == ia))) continue;
					tr.triangles[c] = kNone;
					const auto third = m.vertices[tr.vertices[(c + 2) % 3]].location;
					if ((side(third) > 0) != (oursSide > 0)) {
						link(best.gm, idx[q], c, hostOf[best.i], local[best.i], best.e);
						link(hostOf[best.i], local[best.i], best.e, best.gm, idx[q], c);
						++joinedAb;
					}
				}
			}
			++splits;
			SKSE::log::info("outdoor navmesh: foot {}: ground {} triangle(s) {}{} rebuilt round our edge ({:.0f} long) as {}, joined both ways: {}", f, Hex(best.gm->id), best.g1,
				region.size() > 1 ? std::format(" and {}", best.g2) : std::string(), best.len, parts.size(), joinedAb);
		}

		// ---- 4. the info map: the pairs our portals join become neighbours
		int added = 0;
		if (g_infoLinks)
			for (const auto& [a, b] : joined) {
				const auto before = g_app.infos.size();
				AddNeighbour(a, b); AddNeighbour(b, a);
				added += static_cast<int>(g_app.infos.size() - before);
			}

		// ---- 5. the hosts' grids over their new extent; what each host now holds beyond its own
		for (auto& h : g_app.hosts) {
			auto& m = *static_cast<RE::BSNavmesh*>(h.nm);
			h.addV = m.vertices.size() - h.nv; h.addT = m.triangles.size() - h.nt; h.addE = m.extraEdgeInfo.size() - h.ne;
			if (h.addT || std::any_of(res.begin(), res.end(), [&](const auto& x) { return x.first.first == h.nm; })) RebuildGrid(h.nm);
		}
		g_app.in = true;
		std::string hs;
		for (auto& [h, mem] : members) hs += std::format("{} {}, ", Hex(h->id), mem.size());
		g_app.summary = std::format("outdoor navmesh in: {} ground triangle(s) cut in {} navmesh(es); ours in {}{} edge(s) joined at the feet ({} back, {} split); {} portal pair(s); {} info neighbour(s) added",
			cut.size(), cutCount.size(), hs, bridged, backs, splits, joined.size(), added);
		SKSE::log::info("{} ({} ms)", g_app.summary, std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - t0).count());
		Reachability(byId);
	}
}

namespace Nav
{
	void OutdoorApply()
	{
		__try { DoApply(); } __except (EXCEPTION_EXECUTE_HANDLER) { g_app.summary = "access fault while fitting the outdoor navmesh"; }
	}
	void OutdoorRevert() { RevertNow("asked"); }
	std::string OutdoorStatus()
	{
		Load();
		if (!g_ours.ok) return "outdoor navmesh: " + g_ours.why;
		return g_app.in ? (StillIn() ? g_app.summary : "outdoor navmesh: stale (a cell reloaded), refit on the next cell load") :
		                  std::format("outdoor navmesh: not in ({} triangles read; waiting for the hall's {} cells){}", g_ours.tris.size(), g_ours.cells.size(), g_app.summary.empty() ? "" : " - " + g_app.summary);
	}
	void OutdoorSetInfoLinks(bool a_on) { g_infoLinks = a_on; }
}
