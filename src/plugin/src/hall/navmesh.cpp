// The Guild Hall's navmesh work in AG's DLL, and the hall's natives (the Papyrus class AGHallNative).
// The hall's navmesh patches (Data/SKSE/Plugins/AdventurersGuild/Hall/navmesh) are stitched into the loaded navmeshes, in
// memory only; nothing is written to any file the game reads, and a cell reload restores the navmesh from its plugin.
// For testing over DevBench: Dump and Here write the loaded navmeshes to JSON for plot_navmesh.py, Inject and Revert put a
// patch in and take it out again by hand, Followers tells where the player's followers stand on the navmesh.
#include "hall.h"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <cmath>
#include <fstream>
#include <mutex>
#include <optional>
#include <set>

namespace
{
	using Tag = RE::StaticFunctionTag;
	using Json = nlohmann::ordered_json;
	using TriFlag = RE::BSNavmeshTriangle::TriangleFlag;

	constexpr float         kCellSize = 4096.0f;
	constexpr std::uint16_t kNone = 0xFFFF;
	constexpr std::size_t   kMaxPlausible = 200000;  // an array bigger than this means we are not reading what we think

	std::mutex  g_lastLock;
	std::string g_last = "no dump yet";

	void SetLast(std::string a_line)
	{
		SKSE::log::info("{}", a_line);
		std::scoped_lock l(g_lastLock);
		g_last = std::move(a_line);
	}

	const char* Runtime() { return REL::Module::IsVR() ? "VR" : REL::Module::IsAE() ? "AE" : "SE"; }

	std::string Hex(std::uint32_t a_v) { return std::format("{:08X}", a_v); }

	template <class A>
	bool Plausible(const A& a_arr)
	{
		return a_arr.size() < kMaxPlausible && (a_arr.empty() || a_arr.data());
	}

	Json Files(const RE::TESForm* a_form)
	{
		Json out = Json::array();
		if (const auto* arr = a_form ? a_form->sourceFiles.array : nullptr)
			for (const auto* f : *arr) out.push_back(f ? std::string(f->GetFilename()) : std::string("?"));
		return out;
	}

	std::string FileChain(const RE::TESForm* a_form)
	{
		std::string s;
		for (const auto& f : Files(a_form)) s += (s.empty() ? "" : " > ") + f.get<std::string>();
		return s;
	}

	float Round1(float a_v) { return std::round(a_v * 10.0f) / 10.0f; }

	// What the dump found wrong with the data as CommonLibVR lays it out. All zero (but the "fine" ones) = the layout
	// reads right on this runtime.
	struct Checks
	{
		int   meshes = 0, verts = 0, tris = 0, links = 0, deleted = 0;
		int   implausible = 0;         // an array size or pointer that cannot be right
		int   vertBad = 0;             // not finite, or more than 64 units outside its cell
		float vertExcess = 0;          // the farthest any vertex lies outside its cell (fine when small)
		int   vertIndexBad = 0;        // a triangle naming a vertex that does not exist
		int   neighbourBad = 0;        // an edge naming a triangle that does not exist
		int   linkIndexBad = 0;        // an edge flagged as a link to another navmesh, naming a link that does not exist
		int   gridBad = 0;             // the lookup grid's cell count, or a triangle index in it, cannot be right
		int   linkTargetBad = 0;       // a link to a form that is not a navmesh
		int   linkTargetUnloaded = 0;  // a link to a navmesh not in memory, its cell not loaded (fine)
		int   infoMissing = 0;         // no entry in the navmesh info map (fine for some)
		int   infoMismatch = 0;        // the info map's entry is for another navmesh

		bool LayoutOK() const
		{
			return !implausible && !vertBad && !vertIndexBad && !neighbourBad && !linkIndexBad && !gridBad && !linkTargetBad && !infoMismatch;
		}

		Json ToJson() const
		{
			return { { "layoutOK", LayoutOK() }, { "meshes", meshes }, { "verts", verts }, { "tris", tris }, { "links", links },
				{ "deleted", deleted }, { "implausible", implausible }, { "vertBad", vertBad }, { "vertExcess", Round1(vertExcess) },
				{ "vertIndexBad", vertIndexBad }, { "neighbourBad", neighbourBad }, { "linkIndexBad", linkIndexBad }, { "gridBad", gridBad },
				{ "linkTargetBad", linkTargetBad }, { "linkTargetUnloaded", linkTargetUnloaded }, { "infoMissing", infoMissing },
				{ "infoMismatch", infoMismatch } };
		}
	};

	Json DumpMesh(RE::NavMesh* a_mesh, std::int32_t a_cx, std::int32_t a_cy, RE::BSNavmeshInfoMap* a_infoMap, Checks& c)
	{
		auto& m = *static_cast<RE::BSNavmesh*>(a_mesh);
		Json  j;
		j["id"] = Hex(a_mesh->GetFormID());
		j["files"] = Files(a_mesh);
		if (!Plausible(m.vertices) || !Plausible(m.triangles) || !Plausible(m.extraEdgeInfo) || !Plausible(m.doorPortals) ||
			!Plausible(m.closedDoors) || !Plausible(m.coverArray) || !Plausible(m.obstacles)) {
			++c.implausible;
			j["implausible"] = true;
			return j;
		}
		++c.meshes;
		const auto  nv = m.vertices.size(), nt = m.triangles.size(), nl = m.extraEdgeInfo.size();
		const float x0 = a_cx * kCellSize, y0 = a_cy * kCellSize;

		Json verts = Json::array();
		for (const auto& v : m.vertices) {
			const auto& p = v.location;
			if (!std::isfinite(p.x) || !std::isfinite(p.y) || !std::isfinite(p.z)) {
				++c.vertBad;
				verts.push_back({ 0, 0, 0 });
				continue;
			}
			const float ex = std::max({ x0 - p.x, p.x - (x0 + kCellSize), y0 - p.y, p.y - (y0 + kCellSize), 0.0f });
			c.vertExcess = std::max(c.vertExcess, ex);
			if (ex > 64.0f) ++c.vertBad;
			verts.push_back({ Round1(p.x), Round1(p.y), Round1(p.z) });
		}
		c.verts += static_cast<int>(nv);

		// an edge holds a neighbouring triangle, kNone, or (when its link flag is set) an index into extraEdgeInfo
		Json tris = Json::array();
		for (const auto& t : m.triangles) {
			for (const auto vi : t.vertices)
				if (vi >= nv) ++c.vertIndexBad;
			for (int e = 0; e < 3; ++e) {
				const auto n = t.triangles[e];
				if (t.triangleFlags.any(static_cast<TriFlag>(1 << e))) {
					if (n >= nl) ++c.linkIndexBad;
				} else if (n != kNone && n >= nt) {
					++c.neighbourBad;
				}
			}
			if (t.triangleFlags.any(TriFlag::kDeleted)) ++c.deleted;
			tris.push_back({ t.vertices[0], t.vertices[1], t.vertices[2], t.triangles[0], t.triangles[1], t.triangles[2],
				t.triangleFlags.underlying(), t.traversalFlags.underlying() });
		}
		c.tris += static_cast<int>(nt);

		Json links = Json::array();
		for (const auto& l : m.extraEdgeInfo) {
			const auto id = l.portal.otherMeshID;
			if (auto* f = RE::TESForm::LookupByID(id)) {
				if (!f->Is(RE::FormType::NavMesh)) ++c.linkTargetBad;
			} else {
				++c.linkTargetUnloaded;
			}
			links.push_back({ l.type.underlying(), Hex(id), l.portal.triangle, l.portal.edgeIndex });
		}
		c.links += static_cast<int>(nl);

		const auto& g = m.meshGrid;
		const auto  gridCells = g.gridData.size();
		if (static_cast<std::size_t>(g.gridSize) * g.gridSize != gridCells || gridCells > 4096) {
			++c.gridBad;
		} else {
			for (std::size_t i = 0; i < gridCells; ++i) {
				const auto& cell = g.gridData[i];
				if (!Plausible(cell)) {
					++c.gridBad;
					break;
				}
				for (const auto ti : cell)
					if (ti >= nt) {
						++c.gridBad;
						break;
					}
			}
		}

		j["verts"] = std::move(verts);
		j["tris"] = std::move(tris);
		j["links"] = std::move(links);
		j["doorPortals"] = m.doorPortals.size();
		j["closedDoors"] = m.closedDoors.size();
		j["cover"] = m.coverArray.size();
		j["obstacles"] = m.obstacles.size();
		j["obstacleMap"] = m.triangleToObstacleMap ? m.triangleToObstacleMap->size() : 0;
		j["grid"] = { { "size", g.gridSize }, { "col", g.columnSectionLen }, { "row", g.rowSectionLen },
			{ "min", { g.gridBoundsMin.x, g.gridBoundsMin.y, g.gridBoundsMin.z } }, { "max", { g.gridBoundsMax.x, g.gridBoundsMax.y, g.gridBoundsMax.z } },
			{ "cells", gridCells } };

		if (a_infoMap) {
			if (auto* info = a_infoMap->GetNavmeshInfo(a_mesh->GetFormID())) {
				if (info->navMeshID != a_mesh->GetFormID()) ++c.infoMismatch;
				Json adj = Json::array();
				if (info->adjacentMeshesArray && info->adjacentMeshCount < 1000)
					for (std::uint16_t i = 0; i < info->adjacentMeshCount; ++i) adj.push_back(Hex(info->adjacentMeshesArray[i]));
				j["info"] = { { "approx", { Round1(info->approxLocation.x), Round1(info->approxLocation.y), Round1(info->approxLocation.z) } },
					{ "adjacent", std::move(adj) }, { "doors", info->connectedDoorCount }, { "preferred", info->preferredPercent },
					{ "flags", info->uiFlags }, { "pointsHere", info->navMesh == &m } };
			} else {
				++c.infoMissing;
			}
		}
		return j;
	}

	void DoDump(std::int32_t a_x, std::int32_t a_y, std::int32_t a_r)
	{
		Checks c;
		Json   out;
		out["runtime"] = Runtime();
		out["game"] = REL::Module::get().version().string(".");
		out["center"] = { a_x, a_y };
		out["radius"] = a_r;

		// the navmesh info map is not in the data handler's form arrays; TES holds it (built on first use)
		auto*                 tes = RE::TES::GetSingleton();
		RE::BSNavmeshInfoMap* infoMap = nullptr;
		if (tes)
			if (auto* map = tes->GetRuntimeData2().navMeshInfoMap) {
				infoMap = map;
				out["infoMapFiles"] = Files(map);
			}
		out["infoMap"] = infoMap != nullptr;

		Json cells = Json::array();
		auto* grid = tes ? tes->gridCells : nullptr;
		if (grid && grid->cells && grid->length < 64) {
			for (std::uint32_t gx = 0; gx < grid->length; ++gx) {
				for (std::uint32_t gy = 0; gy < grid->length; ++gy) {
					auto* cell = grid->GetCell(gx, gy);
					if (!cell || !cell->IsExteriorCell()) continue;
					const auto* xy = cell->GetCoordinates();
					if (!xy || std::abs(xy->cellX - a_x) > a_r || std::abs(xy->cellY - a_y) > a_r) continue;
					auto& rd = cell->GetRuntimeData();
					Json  jc;
					jc["cell"] = { xy->cellX, xy->cellY };
					jc["id"] = Hex(cell->GetFormID());
					jc["files"] = Files(cell);
					jc["attached"] = cell->IsAttached();
					jc["world"] = rd.worldSpace ? rd.worldSpace->GetFormEditorID() : "";
					Json meshes = Json::array();
					if (rd.navMeshes) {
						if (Plausible(rd.navMeshes->navMeshes)) {
							for (auto& sp : rd.navMeshes->navMeshes)
								if (auto* nm = sp.get()) meshes.push_back(DumpMesh(nm, xy->cellX, xy->cellY, infoMap, c));
						} else {
							++c.implausible;
						}
					}
					SKSE::log::info("cell {},{} ({}): {} navmesh(es), cell record from {}", xy->cellX, xy->cellY, Hex(cell->GetFormID()), meshes.size(), FileChain(cell));
					jc["navmeshes"] = std::move(meshes);
					cells.push_back(std::move(jc));
				}
			}
		}
		const auto found = cells.size();
		out["cells"] = std::move(cells);
		out["checks"] = c.ToJson();

		std::string where = "(no log directory)";
		if (auto dir = SKSE::log::log_directory()) {
			*dir /= "AdventurersGuildHall";
			std::filesystem::create_directories(*dir);
			*dir /= std::format("navmesh_{}_{}_{}.json", Runtime(), a_x, a_y);
			std::ofstream(*dir) << out.dump();
			where = dir->string();
		}
		SetLast(std::format("{} {}: {} cell(s), {} navmesh(es), {} triangles, {} links; layout {} (vertex excess {:.1f}, deleted {}, links to unloaded {}, no info {}) -> {}",
			Runtime(), REL::Module::get().version().string("."), found, c.meshes, c.tris, c.links, c.LayoutOK() ? "OK" : "WRONG", c.vertExcess,
			c.deleted, c.linkTargetUnloaded, c.infoMissing, where));
		if (!c.LayoutOK()) SKSE::log::info("checks: {}", c.ToJson().dump());
	}

	void NoteFault() { SetLast("access fault while reading the navmesh: CommonLibVR's layout does not match this runtime"); }

	void DumpGuarded(std::int32_t a_x, std::int32_t a_y, std::int32_t a_r)
	{
		__try {
			DoDump(a_x, a_y, a_r);
		} __except (EXCEPTION_EXECUTE_HANDLER) {
			NoteFault();
		}
	}

	std::string Dump(Tag*, std::int32_t a_x, std::int32_t a_y, std::int32_t a_r)
	{
		SetLast("dump queued");
		SKSE::GetTaskInterface()->AddTask([a_x, a_y, a_r] {
			try {
				DumpGuarded(a_x, a_y, a_r);
			} catch (const std::exception& e) {
				SetLast(std::format("dump failed: {}", e.what()));
			}
		});
		return std::format("queued: navmesh_{}_{}_{}.json (LastDump() for the result)", Runtime(), a_x, a_y);
	}

	std::string LastDump(Tag*)
	{
		std::scoped_lock l(g_lastLock);
		return g_last;
	}

	// ---------------------------------------------------------------- where an actor stands on the navmesh

	struct Under
	{
		RE::NavMesh* mesh = nullptr;
		std::size_t  tri = 0;
		float        z = 0;
	};

	// The triangle under a point: among the loaded cells' triangles containing it (seen from above), the one whose
	// plane is nearest the point's height.
	std::optional<Under> FindUnder(const RE::NiPoint3& p)
	{
		auto* tes = RE::TES::GetSingleton();
		auto* grid = tes ? tes->gridCells : nullptr;
		if (!grid || !grid->cells || grid->length >= 64) return std::nullopt;
		std::optional<Under> best;
		float                bestDz = 1e9f;
		for (std::uint32_t gx = 0; gx < grid->length; ++gx) {
			for (std::uint32_t gy = 0; gy < grid->length; ++gy) {
				auto* cell = grid->GetCell(gx, gy);
				if (!cell) continue;
				auto& rd = cell->GetRuntimeData();
				if (!rd.navMeshes || !Plausible(rd.navMeshes->navMeshes)) continue;
				for (auto& sp : rd.navMeshes->navMeshes) {
					auto* nm = sp.get();
					if (!nm) continue;
					auto& m = *static_cast<RE::BSNavmesh*>(nm);
					if (!Plausible(m.vertices) || !Plausible(m.triangles)) continue;
					const auto nv = m.vertices.size();
					for (std::size_t i = 0; i < m.triangles.size(); ++i) {
						const auto& t = m.triangles[i];
						if (t.vertices[0] >= nv || t.vertices[1] >= nv || t.vertices[2] >= nv) continue;
						const auto& a = m.vertices[t.vertices[0]].location;
						const auto& b = m.vertices[t.vertices[1]].location;
						const auto& q = m.vertices[t.vertices[2]].location;
						const float d = (b.y - q.y) * (a.x - q.x) + (q.x - b.x) * (a.y - q.y);
						if (std::abs(d) < 1e-6f) continue;
						const float w1 = ((b.y - q.y) * (p.x - q.x) + (q.x - b.x) * (p.y - q.y)) / d;
						const float w2 = ((q.y - a.y) * (p.x - q.x) + (a.x - q.x) * (p.y - q.y)) / d;
						const float w3 = 1.0f - w1 - w2;
						if (w1 < -1e-4f || w2 < -1e-4f || w3 < -1e-4f) continue;
						const float z = w1 * a.z + w2 * b.z + w3 * q.z;
						if (std::abs(p.z - z) < bestDz) {
							best = Under{ nm, i, z };
							bestDz = std::abs(p.z - z);
						}
					}
				}
			}
		}
		return best;
	}

	std::string Describe(const RE::NiPoint3& p)
	{
		const auto u = FindUnder(p);
		if (!u) return std::format("no navmesh triangle under ({:.0f}, {:.0f}, {:.0f})", p.x, p.y, p.z);
		const auto& t = static_cast<RE::BSNavmesh*>(u->mesh)->triangles[u->tri];
		return std::format("navmesh {} [{}] triangle {} flags 0x{:X}, its plane at z {:.0f} ({:+.0f})", Hex(u->mesh->GetFormID()), FileChain(u->mesh),
			u->tri, t.triangleFlags.underlying(), u->z, p.z - u->z);
	}

	std::string Here(Tag*)
	{
		auto* pc = RE::PlayerCharacter::GetSingleton();
		return pc ? std::format("player at ({:.0f}, {:.0f}, {:.0f}): {}", pc->GetPosition().x, pc->GetPosition().y, pc->GetPosition().z,
						Describe(pc->GetPosition())) :
		            "no player";
	}

	// ---------------------------------------------------------------- what the ENGINE resolves (stage 2b)

	std::uint32_t MeshID(RE::BSNavmesh* a_mesh) { return a_mesh ? a_mesh->QNavmeshID() : 0; }

	// The game's own answer for a point: the pathing cell it belongs to, the navmesh and triangle the game's
	// lookup resolves (BSPathingLocation, the same filter the game uses for actors when none is given), the closest
	// point on the navmesh, and the navmeshes the game even considers within a radius of it.
	std::string EngineAt(Tag*, float a_x, float a_y, float a_z)
	{
		auto* pathing = RE::Pathing::GetSingleton();
		auto* pc = RE::PlayerCharacter::GetSingleton();
		auto* tes = RE::TES::GetSingleton();
		if (!pathing || !pc || !tes || !tes->gridCells) return "no pathing / player / grid";
		const RE::NiPoint3 pos(a_x, a_y, a_z);
		RE::TESObjectCELL* cell = nullptr;
		const auto         cx = static_cast<std::int32_t>(std::floor(a_x / kCellSize)), cy = static_cast<std::int32_t>(std::floor(a_y / kCellSize));
		for (std::uint32_t gx = 0; gx < tes->gridCells->length && !cell; ++gx)
			for (std::uint32_t gy = 0; gy < tes->gridCells->length && !cell; ++gy)
				if (auto* c = tes->gridCells->GetCell(gx, gy); c && c->IsExteriorCell() && c->GetCoordinates() && c->GetCoordinates()->cellX == cx &&
															   c->GetCoordinates()->cellY == cy)
					cell = c;
		if (!cell) return std::format("cell {},{} is not loaded", cx, cy);

		RE::BSTSmartPointer<RE::BSPathingCell> pcell;
		if (!pathing->GetPathingCell(pos, cell, pc->GetWorldspace(), pcell) || !pcell) return std::format("no pathing cell for cell {},{}", cx, cy);

		std::string out = std::format("({:.0f}, {:.0f}, {:.0f}) in cell {},{}:", a_x, a_y, a_z, cx, cy);
		// the game's resolve with an open filter (any height) and with a tight one (64 above or below)
		for (const float dz : { std::numeric_limits<float>::max(), 64.0f }) {
			RE::BSPathingLocation                        loc(pos, pcell);
			RE::FindTriangleForLocationFilterCheckDeltaZ filter;
			filter.maxDistAbove = dz;
			filter.maxDistBelow = dz;
			const auto label = dz > 1e9f ? "open filter" : "64-unit filter";
			if (loc.ResolveToClosestNavmeshAndTriangle(filter)) {
				RE::BSTSmartPointer<RE::BSNavmesh> nav;
				std::uint16_t                      tri = 0;
				if (loc.GetNavMeshAndTriangle(nav, tri) && nav) {
					const auto& t = nav->triangles[tri];
					float       z = 0;
					for (auto vi : t.vertices) z += nav->vertices[vi].location.z / 3.0f;
					out += std::format(" {}: navmesh {} triangle {} (of {}, centre z {:.0f});", label, Hex(MeshID(nav.get())), tri, nav->triangles.size(), z);
				} else {
					out += std::format(" {}: resolved, but no navmesh/triangle came back;", label);
				}
			} else {
				out += std::format(" {}: NO triangle;", label);
			}
		}
		RE::NiPoint3 closest;
		if (pathing->FindClosestPointOnNavmesh(pcell, pos, closest)) out += std::format(" closest point on navmesh ({:.0f}, {:.0f}, {:.0f});", closest.x, closest.y, closest.z);
		RE::BSPathingLocation                     loc2(pos, pcell);
		RE::BSTArray<RE::BSTSmartPointer<RE::BSNavmesh>> cands;
		static_cast<RE::BSPathingCellManager*>(pathing)->FindPotentialNavmeshesForLocation2(loc2, 64.0f, cands);
		out += " navmeshes it considers within 64:";
		for (auto& n : cands) out += " " + Hex(MeshID(n.get()));
		return out;
	}

	std::string EngineHere(Tag* a_tag)
	{
		auto* pc = RE::PlayerCharacter::GetSingleton();
		if (!pc) return "no player";
		const auto p = pc->GetPosition();
		return "player " + EngineAt(a_tag, p.x, p.y, p.z);
	}

	// The navmesh info map's entry for a navmesh, with the raw bytes of its compressed bounds (layout not known yet).
	std::string Info(Tag*, std::string a_id)
	{
		auto* tes = RE::TES::GetSingleton();
		auto* map = tes ? tes->GetRuntimeData2().navMeshInfoMap : nullptr;
		if (!map) return "no navmesh info map";
		const auto id = static_cast<RE::FormID>(std::stoul(a_id, nullptr, 16));
		auto*      info = static_cast<RE::BSNavmeshInfoMap*>(map)->GetNavmeshInfo(id);
		if (!info) return std::format("no info for {}", Hex(id));
		std::string adj;
		if (info->adjacentMeshesArray && info->adjacentMeshCount < 1000)
			for (std::uint16_t i = 0; i < info->adjacentMeshCount; ++i) adj += " " + Hex(info->adjacentMeshesArray[i]);
		std::string raw;
		if (info->bounds) {
			const auto* f = reinterpret_cast<const float*>(info->bounds);
			const auto* h = reinterpret_cast<const std::int16_t*>(info->bounds);
			raw = " | bounds as floats:";
			for (int i = 0; i < 12; ++i) raw += std::format(" {:.1f}", f[i]);
			raw += " | as int16:";
			for (int i = 0; i < 16; ++i) raw += std::format(" {}", h[i]);
		}
		auto* nm = RE::TESForm::LookupByID<RE::NavMesh>(id);
		return std::format("{}: id {} approx ({:.0f}, {:.0f}, {:.0f}), {} adjacent:{}, {} doors, preferred {:.2f}, flags 0x{:X}, points at the loaded navmesh: {}{}", Hex(id),
			Hex(info->navMeshID), info->approxLocation.x, info->approxLocation.y, info->approxLocation.z, info->adjacentMeshCount, adj,
			info->connectedDoorCount, info->preferredPercent, info->uiFlags,
			nm ? (info->navMesh == static_cast<RE::BSNavmesh*>(nm) ? "yes" : "no") : "not loaded", raw);
	}

	std::string Followers(Tag*)
	{
		std::string out;
		if (auto* pl = RE::ProcessLists::GetSingleton())
			pl->ForEachHighActor([&](RE::Actor* a) {
				if (a && a->IsPlayerTeammate() && !a->IsDead()) {
					const auto p = a->GetPosition();
					out += std::format("{} ({}) at ({:.0f}, {:.0f}, {:.0f}): {}. ", a->GetName(), Hex(a->GetFormID()), p.x, p.y, p.z, Describe(p));
				}
				return RE::BSContainer::ForEachResult::kContinue;
			});
		return out.empty() ? "no followers in the loaded area" : out;
	}

	// The player's teammates, alive, in the loaded area or a cell just left (high and middle-high processes): a scripted move
	// (AGHallTravel.Travel) takes them along. The parent cell alone missed them (2026-11-11: two followers a cell over outside
	// were left to catch-up, which put them behind the player, outside the hall's front wall). Waiting ones the script skips.
	std::vector<RE::Actor*> Teammates(Tag*)
	{
		std::vector<RE::Actor*> out;
		auto* player = RE::PlayerCharacter::GetSingleton();
		auto* pl = RE::ProcessLists::GetSingleton();
		if (!pl) return out;
		const auto take = [&](RE::BSTArray<RE::ActorHandle>& a_list) {
			for (auto& h : a_list) {
				auto a = h.get();
				if (a && a.get() != player && a->IsPlayerTeammate() && !a->IsDead() &&
					std::find(out.begin(), out.end(), a.get()) == out.end())
					out.push_back(a.get());
			}
		};
		take(pl->highActorHandles);
		take(pl->middleHighActorHandles);
		return out;
	}

	// ---------------------------------------------------------------- stage 2: a patch stitched in, and taken out

	struct Backup
	{
		RE::FormID                                       id = 0;
		RE::NavMesh*                                     mesh = nullptr;
		std::size_t                                      nv = 0, nt = 0, addV = 0, addT = 0;
		std::uint16_t                                    j = 0;
		RE::BSNavmeshTriangle                            jWas{};
		std::int32_t                                     backTri = -1;
		RE::BSNavmeshTriangle                            backWas{};
		std::vector<std::pair<std::size_t, std::size_t>> gridSizes;  // grid cell, its size before
		float                                            zmaxWas = 0;
		struct Aside
		{
			RE::FormID    mesh;
			std::uint16_t tri;
			std::uint16_t flagsWas;
		};
		std::vector<Aside> asides;  // other navmeshes' triangles set aside (0x20) while the patch is in
	};
	constexpr std::uint16_t kSetAside = 0x20;  // what the game's own run-time cutting puts on the triangles it replaces
	std::map<std::string, Backup> g_backups;   // by patch name: what each stitched patch changed, to take it out again
	constexpr const char*         kPatchDir = "Data/SKSE/Plugins/AdventurersGuild/Hall/navmesh";

	RE::BSNavmeshTriangle MakeTri(const Json& a)
	{
		RE::BSNavmeshTriangle t{};
		for (int k = 0; k < 3; ++k) {
			t.vertices[k] = a[k].get<std::uint16_t>();
			t.triangles[k] = a[3 + k].get<std::uint16_t>();
		}
		t.triangleFlags = REX::EnumSet<TriFlag, std::uint16_t>(static_cast<TriFlag>(a[6].get<std::uint16_t>()));
		return t;
	}

	// The lookup grid numbers its cells either row by row (y * size + x) or column by column (x * size + y): count
	// which numbering finds the navmesh's own triangles (by their centres) in the cells that list them.
	bool GridRowMajor(const RE::BSNavmesh& m, int& a_rowHits, int& a_colHits)
	{
		const auto& g = m.meshGrid;
		const auto  n = g.gridSize;
		const auto  nv = m.vertices.size();
		for (std::size_t t = 0; t < std::min<std::size_t>(m.triangles.size(), 400); ++t) {
			const auto& tr = m.triangles[t];
			if (tr.vertices[0] >= nv || tr.vertices[1] >= nv || tr.vertices[2] >= nv) continue;
			float cx = 0, cy = 0;
			for (auto vi : tr.vertices) {
				cx += m.vertices[vi].location.x / 3.0f;
				cy += m.vertices[vi].location.y / 3.0f;
			}
			const auto ix = std::min<std::uint32_t>(n - 1, static_cast<std::uint32_t>(std::max(0.0f, (cx - g.gridBoundsMin.x) / g.columnSectionLen)));
			const auto iy = std::min<std::uint32_t>(n - 1, static_cast<std::uint32_t>(std::max(0.0f, (cy - g.gridBoundsMin.y) / g.rowSectionLen)));
			auto has = [&](std::size_t a_cell) {
				const auto& c = g.gridData[a_cell];
				return std::find(c.begin(), c.end(), static_cast<std::uint16_t>(t)) != c.end();
			};
			a_rowHits += has(static_cast<std::size_t>(iy) * n + ix);
			a_colHits += has(static_cast<std::size_t>(ix) * n + iy);
		}
		return a_rowHits >= a_colHits;
	}

	void DoInject(const std::string& a_name, const std::filesystem::path& a_path)
	{
		if (g_backups.contains(a_name)) return SetLast(std::format("patch {} is already in: Revert first", a_name));
		std::ifstream in(a_path);
		if (!in) return SetLast(std::format("no patch file at {}", a_path.string()));
		const Json p = Json::parse(in);

		const auto id = static_cast<RE::FormID>(std::stoul(p["navmesh"].get<std::string>(), nullptr, 16));
		auto*      nm = RE::TESForm::LookupByID<RE::NavMesh>(id);
		if (!nm) return SetLast(std::format("navmesh {} is not loaded (stand near the hall)", Hex(id)));
		auto&       m = *static_cast<RE::BSNavmesh*>(nm);
		const auto& ex = p["expect"];
		const auto  nv = m.vertices.size(), nt = m.triangles.size();

		// everything is checked before anything is changed: the navmesh must be the one the patch was made for
		if (nv != ex["verts"].get<std::size_t>() || nt != ex["tris"].get<std::size_t>())
			return SetLast(std::format("navmesh {} has {} vertices and {} triangles, the patch expects {} and {}: not changed", Hex(id), nv, nt,
				ex["verts"].get<std::size_t>(), ex["tris"].get<std::size_t>()));
		const auto j = ex["J"].get<std::uint16_t>();
		const auto jt = ex["J_tri"];
		for (int k = 0; k < 3; ++k)
			if (m.triangles[j].vertices[k] != jt[k].get<std::uint16_t>() || m.triangles[j].triangles[k] != jt[3 + k].get<std::uint16_t>())
				return SetLast(std::format("triangle {} is not the one the patch was made for: not changed", j));
		for (const char* key : { "A", "B", "C" }) {
			const auto& q = ex[key];
			bool        found = false;
			for (auto vi : m.triangles[j].vertices) {
				const auto& v = m.vertices[vi].location;
				found |= std::abs(v.x - q[0].get<float>()) < 0.6f && std::abs(v.y - q[1].get<float>()) < 0.6f && std::abs(v.z - q[2].get<float>()) < 0.6f;
			}
			if (!found) return SetLast(std::format("triangle {}'s corner {} is not where the patch expects it: not changed", j, key));
		}
		const auto& bl = p["backlink"];
		if (!bl.is_null() && m.triangles[bl["tri"].get<std::size_t>()].triangles[bl["edge"].get<int>()] != bl["was"].get<std::uint16_t>())
			return SetLast("the back link is not what the patch expects: not changed");
		std::vector<std::pair<RE::BSNavmesh*, std::uint16_t>> aside;
		if (p.contains("hide")) {
			for (const auto& h : p["hide"]) {
				const auto hid = static_cast<RE::FormID>(std::stoul(h["navmesh"].get<std::string>(), nullptr, 16));
				auto*      hm = RE::TESForm::LookupByID<RE::NavMesh>(hid);
				if (!hm) return SetLast(std::format("navmesh {} (ground to set aside) is not loaded: not changed", Hex(hid)));
				auto& hb = *static_cast<RE::BSNavmesh*>(hm);
				for (const auto& t : h["tris"]) {
					const auto ti = t.get<std::uint16_t>();
					if (ti >= hb.triangles.size()) return SetLast(std::format("navmesh {} has no triangle {}: not changed", Hex(hid), ti));
					aside.emplace_back(&hb, ti);
				}
			}
		}
		int rowHits = 0, colHits = 0;
		const bool rowMajor = GridRowMajor(m, rowHits, colHits);
		if (std::max(rowHits, colHits) < 50 || std::min(rowHits, colHits) * 2 > std::max(rowHits, colHits))
			return SetLast(std::format("cannot tell how the lookup grid is numbered (row {} / column {} hits): not changed", rowHits, colHits));

		Backup b;
		b.id = id;
		b.mesh = nm;
		b.nv = nv;
		b.nt = nt;
		b.j = j;
		b.jWas = m.triangles[j];
		b.zmaxWas = m.meshGrid.gridBoundsMax.z;
		if (!bl.is_null()) {
			b.backTri = bl["tri"].get<std::int32_t>();
			b.backWas = m.triangles[b.backTri];
		}

		for (const auto& v : p["verts"]) m.vertices.push_back(RE::BSNavmeshVertex{ RE::NiPoint3(v[0].get<float>(), v[1].get<float>(), v[2].get<float>()) });
		for (const auto& [k, t] : p["replace"].items()) m.triangles[static_cast<std::size_t>(std::stoul(k))] = MakeTri(t);
		for (const auto& t : p["append"]) m.triangles.push_back(MakeTri(t));
		if (!bl.is_null()) m.triangles[b.backTri].triangles[bl["edge"].get<int>()] = bl["now"].get<std::uint16_t>();
		b.addV = m.vertices.size() - nv;
		b.addT = m.triangles.size() - nt;

		// the new triangles go into every lookup-grid cell their footprint touches
		auto&      g = m.meshGrid;
		const auto n = g.gridSize;
		std::set<std::size_t> touched;
		for (std::size_t t = nt; t < m.triangles.size(); ++t) {
			const auto& tr = m.triangles[t];
			float       x0 = 1e9f, y0 = 1e9f, x1 = -1e9f, y1 = -1e9f;
			for (auto vi : tr.vertices) {
				const auto& v = m.vertices[vi].location;
				x0 = std::min(x0, v.x), x1 = std::max(x1, v.x), y0 = std::min(y0, v.y), y1 = std::max(y1, v.y);
			}
			auto cellIx = [&](float a_v, float a_min, float a_len) { return std::min<std::uint32_t>(n - 1, static_cast<std::uint32_t>(std::max(0.0f, (a_v - a_min) / a_len))); };
			for (auto ix = cellIx(x0, g.gridBoundsMin.x, g.columnSectionLen); ix <= cellIx(x1, g.gridBoundsMin.x, g.columnSectionLen); ++ix) {
				for (auto iy = cellIx(y0, g.gridBoundsMin.y, g.rowSectionLen); iy <= cellIx(y1, g.gridBoundsMin.y, g.rowSectionLen); ++iy) {
					const std::size_t c = rowMajor ? static_cast<std::size_t>(iy) * n + ix : static_cast<std::size_t>(ix) * n + iy;
					if (touched.insert(c).second) b.gridSizes.emplace_back(c, g.gridData[c].size());
					g.gridData[c].push_back(static_cast<std::uint16_t>(t));
				}
			}
		}
		g.gridBoundsMax.z = std::max(g.gridBoundsMax.z, p["zmax"].get<float>());
		for (auto& [hb, ti] : aside) {
			auto& tr = hb->triangles[ti];
			b.asides.push_back({ hb->QNavmeshID(), ti, tr.triangleFlags.underlying() });
			tr.triangleFlags.set(static_cast<TriFlag>(kSetAside));
		}
		const auto addV = b.addV, addT = b.addT, asides = b.asides.size();
		const auto zWas = b.zmaxWas;
		g_backups[a_name] = std::move(b);
		SetLast(std::format("{} injected into {}: {} vertices and {} triangles added ({} / {} now), triangle {} split, {} grid cells extended "
							"(grid numbered {}: {} / {} hits), grid top z {:.0f} -> {:.0f}, {} ground triangle(s) set aside",
			a_name, Hex(id), addV, addT, m.vertices.size(), m.triangles.size(), j, touched.size(), rowMajor ? "by row" : "by column", rowHits, colHits, zWas,
			g.gridBoundsMax.z, asides));
	}

	// Is this patch still in? Its navmesh must be the very object it went into, and hold what it left.
	bool StillIn(const Backup& b)
	{
		auto* nm = RE::TESForm::LookupByID<RE::NavMesh>(b.id);
		if (nm != b.mesh) return false;
		auto& m = *static_cast<RE::BSNavmesh*>(nm);
		return m.vertices.size() == b.nv + b.addV && m.triangles.size() == b.nt + b.addT;
	}

	void DoRevertOne(const std::string& a_name)
	{
		auto it = g_backups.find(a_name);
		if (it == g_backups.end()) return;
		auto& b = it->second;
		auto* nm = RE::TESForm::LookupByID<RE::NavMesh>(b.id);
		if (nm != b.mesh) {
			g_backups.erase(it);
			return SetLast(std::format("{}: the navmesh was loaded again since the inject (cell reload): the patch is already gone", a_name));
		}
		auto& m = *static_cast<RE::BSNavmesh*>(nm);
		if (m.vertices.size() != b.nv + b.addV || m.triangles.size() != b.nt + b.addT)
			return SetLast(std::format("{}: the navmesh changed since the inject ({} vertices, {} triangles): not reverted", a_name, m.vertices.size(), m.triangles.size()));
		m.triangles.resize(b.nt);
		m.vertices.resize(b.nv);
		m.triangles[b.j] = b.jWas;
		if (b.backTri >= 0) m.triangles[b.backTri] = b.backWas;
		for (const auto& [c, size] : b.gridSizes) m.meshGrid.gridData[c].resize(size);
		m.meshGrid.gridBoundsMax.z = b.zmaxWas;
		int restored = 0;
		for (const auto& a : b.asides)
			if (auto* hm = RE::TESForm::LookupByID<RE::NavMesh>(a.mesh); hm && a.tri < static_cast<RE::BSNavmesh*>(hm)->triangles.size()) {
				static_cast<RE::BSNavmesh*>(hm)->triangles[a.tri].triangleFlags = REX::EnumSet<TriFlag, std::uint16_t>(static_cast<TriFlag>(a.flagsWas));
				++restored;
			}
		SetLast(std::format("{} reverted from {}: back to {} vertices and {} triangles, {} ground triangle(s) restored", a_name, Hex(b.id), b.nv, b.nt, restored));
		g_backups.erase(it);
	}

	void InjectGuarded(const std::string& a_name, const std::filesystem::path& a_path)
	{
		try {
			DoInject(a_name, a_path);
		} catch (const std::exception& e) {
			SetLast(std::format("{}: inject failed: {}", a_name, e.what()));
		}
	}

	// by hand, from SKSE/AdventurersGuildHall/<file> in the log folder (a patch being tried out, no restart needed)
	std::string Inject(Tag*, std::string a_file)
	{
		SetLast("inject queued");
		auto dir = SKSE::log::log_directory();
		if (!dir) return "no log directory";
		*dir /= "AdventurersGuildHall";
		*dir /= a_file;
		SKSE::GetTaskInterface()->AddTask([a_file, path = *dir] { InjectGuarded(a_file, path); });
		return std::format("queued: {} (LastDump() for the result)", a_file);
	}

	std::string Outdoor(Tag*) { return Nav::OutdoorStatus(); }
	std::string OutdoorNav(Tag*, std::string a_step) { return Nav::OutdoorNavStep(a_step); }
	std::string OutdoorInfoLinks(Tag*, bool a_on)
	{
		Nav::OutdoorSetInfoLinks(a_on);
		return std::format("info neighbours {} (from the next fit: Revert, then the cells reload or AutoApply runs)", a_on ? "on" : "off");
	}

	std::string Revert(Tag*)
	{
		SetLast("revert queued");
		SKSE::GetTaskInterface()->AddTask([] { Nav::RevertAll(); });
		return "queued (LastDump() for the result)";
	}

	void HallMessage(SKSE::MessagingInterface::Message* a_msg)
	{
		switch (a_msg->type) {
		case SKSE::MessagingInterface::kDataLoaded:
			Hall::OnDataLoaded();
			break;
		case SKSE::MessagingInterface::kPreLoadGame:
			Nav::OutdoorPreLoad();
			break;
		case SKSE::MessagingInterface::kPostLoadGame:
			Hall::OnGameLoaded(false);
			break;
		case SKSE::MessagingInterface::kNewGame:
			Hall::OnGameLoaded(true);
			break;
		default:
			break;
		}
	}

	bool RegisterNatives(RE::BSScript::IVirtualMachine* a_vm)
	{
		Hall::RegisterPapyrus(a_vm);
		constexpr auto kClass = "AGHallNative";
		a_vm->RegisterFunction("Dump", kClass, Dump);
		a_vm->RegisterFunction("LastDump", kClass, LastDump);
		a_vm->RegisterFunction("Here", kClass, Here);
		a_vm->RegisterFunction("Followers", kClass, Followers);
		a_vm->RegisterFunction("Teammates", kClass, Teammates);
		a_vm->RegisterFunction("Inject", kClass, Inject);
		a_vm->RegisterFunction("Revert", kClass, Revert);
		a_vm->RegisterFunction("EngineAt", kClass, EngineAt);
		a_vm->RegisterFunction("EngineHere", kClass, EngineHere);
		a_vm->RegisterFunction("Info", kClass, Info);
		a_vm->RegisterFunction("Outdoor", kClass, Outdoor);
		a_vm->RegisterFunction("OutdoorInfoLinks", kClass, OutdoorInfoLinks);
		a_vm->RegisterFunction("OutdoorNav", kClass, OutdoorNav);
		return true;
	}
}

namespace Nav
{
	void OnMessage(SKSE::MessagingInterface::Message* a_msg) { HallMessage(a_msg); }
	bool RegisterPapyrus(RE::BSScript::IVirtualMachine* a_vm) { return RegisterNatives(a_vm); }

	// The hall's patches ship in the mod's data (Data/SKSE/Plugins/AdventurersGuild/Hall/navmesh/*.json). Each goes in where its
	// navmesh is loaded and does not hold it yet; a patch whose navmesh was loaded again (a cell reload gives back the
	// plugin's navmesh) is stale and goes in again. Quiet when there is nothing to do.
	// A patch the loaded navmesh refused (another install's mods changed it): not tried, nor logged, again until that
	// navmesh changes, or every cell load would log the same refusal.
	std::map<std::string, std::tuple<RE::NavMesh*, std::size_t, std::size_t>> g_refused;

	void AutoApply()
	{
		HallPassTimer timer("navmesh patches + outdoor navmesh");
		OutdoorApply();   // the outdoor navmesh (outdoor.cpp): its own file, its own wait for the hall's cells
		std::error_code ec;
		if (!std::filesystem::is_directory(kPatchDir, ec)) return;
		for (const auto& f : std::filesystem::directory_iterator(kPatchDir, ec)) {
			if (f.path().extension() != ".json") continue;
			const auto name = "data:" + f.path().filename().string();
			if (auto it = g_backups.find(name); it != g_backups.end()) {
				if (StillIn(it->second)) continue;
				g_backups.erase(it);  // its navmesh came back from the plugin: stitch it in again
			}
			RE::NavMesh* nm = nullptr;
			try {
				std::ifstream in(f.path());
				const auto    head = Json::parse(in);
				const auto    id = static_cast<RE::FormID>(std::stoul(head["navmesh"].get<std::string>(), nullptr, 16));
				nm = RE::TESForm::LookupByID<RE::NavMesh>(id);
				if (!nm) continue;  // not loaded: later, when its cell loads
			} catch (const std::exception& e) {
				SetLast(std::format("{}: unreadable: {}", name, e.what()));
				continue;
			}
			const auto& m = *static_cast<RE::BSNavmesh*>(nm);
			const auto  state = std::make_tuple(nm, m.vertices.size(), m.triangles.size());
			if (auto r = g_refused.find(name); r != g_refused.end() && r->second == state) continue;
			InjectGuarded(name, f.path());
			if (g_backups.contains(name)) g_refused.erase(name);
			else g_refused[name] = state;
		}
	}

	void RevertAll()
	{
		std::vector<std::string> names;
		for (const auto& [n, b] : g_backups) names.push_back(n);
		for (const auto& n : names) DoRevertOne(n);
		OutdoorRevert();
		if (names.empty()) SetLast("nothing to revert");
	}
}
