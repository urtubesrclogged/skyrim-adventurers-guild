// No grass through the hall's ground (2026-11-17). Grass grows from the terrain: the hall's paving, low treads and the pieces set
// on the ground (a brazier) stand on it at run time, with no LAND record of ours to paint (a plugin LAND edit is a hard conflict),
// so grass a few units long came up through them. The game builds each loaded cell's grass in AddCellGrass and hands each grass
// type's instances to its shape at the end (the instances: 16 halfwords each, the position relative to a 12-cell block's corner,
// the size factor at halfword 13, as No Grass In Objects NG writes them for the same shader). Here, just before that hand-over, an
// instance whose root stands on the hall's ground is given size zero.
// - The hall's ground: the outdoor navmesh's blocked outlines (outdoor_nav.json: the hall's footprint and every surface of ours,
//   the open span under a bridge left out), 8 more all round; and the footprint of each small piece the layout sets down (its
//   object bounds, turned and scaled), 40 more all round (a blade's length: a clump beside a brazier leaned into its bowl).
// - Three call sites, each checked to be exactly what is expected before anything is written (the hand-over, and the two calls into
//   AddCellGrass that tell which cell it is building); on a game laid out otherwise, nothing is changed. The hand-over is the
//   shape's virtual DoneAddingInstances on SE 1.5.97 (call [rax + 0x1D0], read from the running game 2026-11-17: the first
//   build expected an indirect call through a pointer, call [rip + x], and stood down there): either form is taken, the
//   original reached the same way it was (the shape's own vtable slot, or the pointer)
// - With No Grass In Objects (GrassControl.dll) loaded, nothing: it rewrites the same sites, and with its cache grass is not built
//   in play at all. Before the first change, every instance of a cell is checked to lie in that cell; if they do not, the layout
//   was not as read and the fix stands down for the session.
#include "hall.h"

#include "../GuildHall.h"

#include <nlohmann/json.hpp>

#include <atomic>
#include <cmath>
#include <fstream>
#include <mutex>
#include <set>

namespace Hall
{
	namespace
	{
		constexpr const char* kOutdoorPath = "Data/SKSE/Plugins/AdventurersGuild/Hall/outdoor/outdoor_nav.json";
		constexpr const char* kLayoutPath = "Data/SKSE/Plugins/AdventurersGuild/Hall/hall2.json";
		// kMargin round the outlines (a blade at the paving's edge); kPieceMargin round a small piece set on the ground: a clump rooted
		// beside a brazier leaned its blades through the bowl (2026-11-17), so a blade's length (~40) all round
		constexpr float       kCell = 4096.0f, kRes = 8.0f, kMargin = 8.0f, kPieceMargin = 40.0f, kSmallPiece = 600.0f;
		constexpr int         kCellsPerBlock = 12;
		constexpr std::uint16_t kSizeZero = 0xBC00;   // -1.0 as a half: the size factor (1 + v) zero

		// the hall's ground as a raster over its bounds, kRes a square
		struct Mask
		{
			bool                      ok = false;
			float                     x0 = 0, y0 = 0;
			int                       w = 0, h = 0;
			std::vector<std::uint8_t> bits;
			bool At(float a_x, float a_y) const
			{
				const int i = static_cast<int>(std::floor((a_x - x0) / kRes)), j = static_cast<int>(std::floor((a_y - y0) / kRes));
				return i >= 0 && j >= 0 && i < w && j < h && bits[static_cast<std::size_t>(j) * w + i];
			}
		};
		Mask              g_mask;
		std::atomic<bool> g_off{ false };   // stood down: the instances were not laid out as read
		std::mutex        g_logLock;
		std::set<std::pair<int, int>> g_logged;   // cells already reported this session

		using AddCellFn = void (*)(void*, RE::TESObjectCELL*, bool*);
		using DoneFn = void (*)(void*, RE::BSTArray<std::uint32_t>&);
		AddCellFn     g_addNow = nullptr, g_addTask = nullptr;
		DoneFn        g_done = nullptr;   // the hand-over's target when it is a call through a pointer
		std::int32_t  g_doneSlot = -1;    // ... or its vtable slot's offset, when it is the shape's virtual call
		thread_local RE::TESObjectCELL* t_cell = nullptr;

		float Half(std::uint16_t a_h)
		{
			const std::uint32_t s = (a_h & 0x8000u) << 16, e = (a_h >> 10) & 0x1Fu, m = a_h & 0x3FFu;
			std::uint32_t       f;
			if (e == 0) {
				if (m == 0) f = s;
				else {   // subnormal
					int e2 = -1;
					std::uint32_t m2 = m;
					do { ++e2; m2 <<= 1; } while (!(m2 & 0x400u));
					f = s | (static_cast<std::uint32_t>(127 - 15 - e2) << 23) | ((m2 & 0x3FFu) << 13);
				}
			} else if (e == 31) f = s | 0x7F800000u | (m << 13);
			else f = s | ((e + 127 - 15) << 23) | (m << 13);
			float r;
			std::memcpy(&r, &f, 4);
			return r;
		}

		// the 12-cell block a cell's grass is placed from (as the game rounds: toward zero)
		float BlockCorner(int a_cell) { return static_cast<float>(kCellsPerBlock * (a_cell / kCellsPerBlock)) * kCell; }

		// once a session, after kDiagCalls hand-overs: what the fix saw (2026-11-17: the first SE test cleared nothing and said nothing,
		// so where it stops is counted, not guessed). One line, then silent
		constexpr int                 kDiagCalls = 100;
		std::atomic<int>              g_calls{ 0 }, g_withCell{ 0 }, g_withBlock{ 0 }, g_near{ 0 }, g_hiddenAll{ 0 }, g_skipped{ 0 }, g_otherShape{ 0 };
		std::atomic<std::int64_t>     g_instNear{ 0 };
		std::atomic<bool>             g_diagDone{ false };
		std::mutex                    g_diagLock;
		std::string                   g_diagSample;   // the first hand-over near the hall: its block, as the shape and the cell give it

		// The 12-cell block a hand-over's instances are placed from: the shape's own place, which the game sets to the block's corner
		// (a multiple of 12 cells), or else the cell being built's block (as the game rounds: toward zero)
		bool BlockOf(void* a_shape, float& a_bx, float& a_by)
		{
			const auto& t = static_cast<RE::NiAVObject*>(a_shape)->local.translate;
			const float blk = kCellsPerBlock * kCell;
			if (std::abs(t.x - std::round(t.x / blk) * blk) < 1.0f && std::abs(t.y - std::round(t.y / blk) * blk) < 1.0f && (t.x != 0.0f || t.y != 0.0f)) {
				a_bx = t.x, a_by = t.y;
				++g_withBlock;
				return true;
			}
			if (auto* cell = t_cell) {
				if (const auto* c = cell->GetCoordinates(); c && cell->IsExteriorCell()) {
					a_bx = BlockCorner(c->cellX), a_by = BlockCorner(c->cellY);
					return true;
				}
			}
			return false;
		}

		void Diag()
		{
			if (g_diagDone || ++g_calls < kDiagCalls || g_diagDone.exchange(true)) return;
			std::scoped_lock l(g_diagLock);
			SKSE::log::info("Hall grass: {} hand-overs seen: {} with the cell known, {} with the block from the shape, {} of another shape class, {} batches left alone; {} near the hall ({} clumps), {} given size zero{}",
				g_calls.load(), g_withCell.load(), g_withBlock.load(), g_otherShape.load(), g_skipped.load(), g_near.load(), g_instNear.load(), g_hiddenAll.load(),
				g_diagSample.empty() ? "" : "; first near the hall: " + g_diagSample);
		}

		// The clumps are in the SHAPE, not in what the hand-over is passed (read from the running game 2026-11-17, SE 1.5.97): each
		// batch is added by the shape's AddInstances (vfunc 0x1C8: count, data) into its own buffer, a pointer at +0x188, the
		// count at +0x190, the halfwords per clump at +0x194 (16); the hand-over (0x1D0) splits that buffer into chunks, uploads
		// them, and frees it; its second argument is the array it puts the new chunk shapes in (empty when it is called, which is
		// why every earlier build found nothing). So the buffer is cleared here, before the hand-over reads it. A clump, as the game's
		// generator (AddCellGrass's 15212) writes it: position x, y, z (halfwords 0-2, from the block's corner), its scale clamped
		// (3), a 3x3 rotation (4-12), a random variance times the grass's own factor (13), 0, 0. Hidden: scale 0 and the variance -1.
		void Filter(void* a_shape)
		{
			if (t_cell) ++g_withCell;
			Diag();
			if (!g_mask.ok || g_off || !a_shape) return;
			static const std::uintptr_t vtMulti = RE::VTABLE_BSMultiStreamInstanceTriShape[0].address();
			const auto* sb = static_cast<const std::uint8_t*>(a_shape);
			if (*reinterpret_cast<const std::uintptr_t*>(sb) != vtMulti) { ++g_otherShape; return; }
			auto*       h = *reinterpret_cast<std::uint16_t* const*>(sb + 0x188);
			const auto  n = *reinterpret_cast<const std::uint32_t*>(sb + 0x190);
			const auto  stride = *reinterpret_cast<const std::uint32_t*>(sb + 0x194);
			if (!h || n == 0) return;
			if (stride != 16) {
				g_off = true;
				SKSE::log::warn("Hall grass: a grass shape holds {} halfwords per clump, not 16: the fix stands down", stride);
				return;
			}
			float bx = 0, by = 0;
			if (!BlockOf(a_shape, bx, by)) return;
			// (each clump judged by where it stands: the game rounds a block's corner toward zero, so west or south of 0 a block's cells
			// lie on the far side of its corner; a test of the block's square as east and north of it threw out every batch at Solitude)
			float cx0 = 0, cy0 = 0;
			bool  cellOk = false;
			if (auto* cell = t_cell)
				if (const auto* c = cell->GetCoordinates(); c && cell->IsExteriorCell()) cx0 = c->cellX * kCell, cy0 = c->cellY * kCell, cellOk = true;
			std::size_t near3 = 0, inMask = 0;
			float       mx0 = 1e30f, my0 = 1e30f, mx1 = -1e30f, my1 = -1e30f;
			for (std::uint32_t i = 0; i < n; ++i) {   // the check: the clumps decode into the cells round the one being built
				const float x = bx + Half(h[i * 16]), y = by + Half(h[i * 16 + 1]);
				near3 += !cellOk || (x >= cx0 - kCell - 64 && x <= cx0 + 2 * kCell + 64 && y >= cy0 - kCell - 64 && y <= cy0 + 2 * kCell + 64);
				mx0 = std::min(mx0, x), my0 = std::min(my0, y), mx1 = std::max(mx1, x), my1 = std::max(my1, y);
			}
			if (near3 * 10 < n * 9) {   // not as read: this batch is left alone, and the first such is logged
				if (++g_skipped == 1)
					SKSE::log::warn("Hall grass: a batch of {} clumps decoded outside the cells round cell ({:.0f}, {:.0f}) (block ({:.0f}, {:.0f}), over ({:.0f}, {:.0f})-({:.0f}, {:.0f})): such batches are left alone",
						n, cx0 / kCell, cy0 / kCell, bx, by, mx0, my0, mx1, my1);
				return;
			}
			const bool atHall = mx1 >= g_mask.x0 && mx0 <= g_mask.x0 + g_mask.w * kRes && my1 >= g_mask.y0 && my0 <= g_mask.y0 + g_mask.h * kRes;
			if (!atHall) return;
			++g_near, g_instNear += n;
			{
				std::scoped_lock l(g_diagLock);
				if (g_diagSample.empty())
					g_diagSample = std::format("block ({:.0f}, {:.0f}), {} clumps over ({:.0f}, {:.0f})-({:.0f}, {:.0f})", bx, by, n, mx0, my0, mx1, my1);
			}
			for (std::uint32_t i = 0; i < n; ++i) {
				const float x = bx + Half(h[i * 16]), y = by + Half(h[i * 16 + 1]);
				if (g_mask.At(x, y)) h[i * 16 + 3] = 0, h[i * 16 + 13] = kSizeZero, ++inMask;
			}
			g_hiddenAll += static_cast<int>(inMask);
			if (inMask) {
				std::scoped_lock l(g_logLock);
				if (g_logged.insert({ static_cast<int>(std::floor(mx0 / kCell)), static_cast<int>(std::floor(my0 / kCell)) }).second)
					SKSE::log::info("Hall grass: {} of {} clumps on the hall's ground given size zero (over ({:.0f}, {:.0f})-({:.0f}, {:.0f}))", inMask, n, mx0, my0, mx1, my1);
			}
		}

		void AddNow(void* a_mgr, RE::TESObjectCELL* a_cell, bool* a_abort)
		{
			auto* prev = t_cell;
			t_cell = a_cell;
			g_addNow(a_mgr, a_cell, a_abort);
			t_cell = prev;
		}
		void AddTask(void* a_mgr, RE::TESObjectCELL* a_cell, bool* a_abort)
		{
			auto* prev = t_cell;
			t_cell = a_cell;
			g_addTask(a_mgr, a_cell, a_abort);
			t_cell = prev;
		}
		void Done(void* a_shape, RE::BSTArray<std::uint32_t>& a_inst)
		{
			Filter(a_shape);
			if (g_doneSlot >= 0) {   // (as the game called it: through the shape's own vtable)
				auto* vt = *reinterpret_cast<std::uintptr_t**>(a_shape);
				reinterpret_cast<DoneFn>(vt[g_doneSlot / 8])(a_shape, a_inst);
			} else g_done(a_shape, a_inst);
		}

		// where a rel32 call or jump at a_site goes (its opcode a_op), or 0
		std::uintptr_t Rel32Target(std::uintptr_t a_site, std::uint8_t a_op)
		{
			const auto* p = reinterpret_cast<const std::uint8_t*>(a_site);
			if (p[0] != a_op) return 0;
			std::int32_t rel;
			std::memcpy(&rel, p + 1, 4);
			return a_site + 5 + static_cast<std::intptr_t>(rel);
		}

		void Rasterize(const std::vector<std::vector<std::array<float, 2>>>& a_rings, std::vector<std::uint8_t>& a_bits)
		{
			// even-odd scanline fill: an outline and its holes together, per row at the squares' middles
			for (int j = 0; j < g_mask.h; ++j) {
				const float        y = g_mask.y0 + (j + 0.5f) * kRes;
				std::vector<float> xs;
				for (const auto& r : a_rings)
					for (std::size_t k = 0; k < r.size(); ++k) {
						const auto& a = r[k];
						const auto& b = r[(k + 1) % r.size()];
						if ((a[1] <= y) != (b[1] <= y)) xs.push_back(a[0] + (y - a[1]) / (b[1] - a[1]) * (b[0] - a[0]));
					}
				std::sort(xs.begin(), xs.end());
				for (std::size_t k = 0; k + 1 < xs.size(); k += 2) {
					const int i0 = std::max(0, static_cast<int>(std::ceil((xs[k] - g_mask.x0) / kRes - 0.5f)));
					const int i1 = std::min(g_mask.w - 1, static_cast<int>(std::floor((xs[k + 1] - g_mask.x0) / kRes - 0.5f)));
					for (int i = i0; i <= i1; ++i) a_bits[static_cast<std::size_t>(j) * g_mask.w + i] = 1;
				}
			}
		}
	}

	// At kPostLoad, with every SKSE plugin loaded: the three sites, each checked, or nothing
	void GrassInstall()
	{
		if (GetModuleHandleA("GrassControl.dll")) {
			SKSE::log::info("Hall grass: No Grass In Objects is loaded: the hall's own grass fix stays off (it rewrites the same code, and caches its grass)");
			return;
		}
		const bool     ae17 = REL::Module::IsAE() && REL::Module::get().version() >= REL::Version(1, 6, 1130, 0);
		const auto     add = REL::RelocationID(15204, 15372).address();
		const auto     doneSite = add + (ae17 ? 0x5EC : REL::Relocate<std::uintptr_t>(0x5E0, 0x5DC, 0x5E0));
		const auto     nowSite = REL::RelocationID(13148, 13288).address() + (ae17 ? 0x9D9 : REL::Relocate<std::uintptr_t>(0x905, 0xB29, 0x905));
		const auto     taskSite = REL::RelocationID(13138, 13278).address() + 0xF;
		const auto*    d = reinterpret_cast<const std::uint8_t*>(doneSite);
		std::int32_t   disp = 0;
		std::memcpy(&disp, d + 2, 4);
		const bool     viaPtr = d[0] == 0xFF && d[1] == 0x15;                                   // call [rip + disp]
		const bool     viaVt = d[0] == 0xFF && d[1] == 0x90 && disp >= 0 && disp < 0x800 && !(disp & 7);   // call [rax + disp]: a vtable slot
		const bool     doneOk = viaPtr || viaVt;
		const bool     nowOk = Rel32Target(nowSite, 0xE8) == add;
		const bool     taskOk = Rel32Target(taskSite, 0xE9) == add;
		const auto     base = REL::Module::get().base();
		if (!doneOk || !nowOk || !taskOk) {
			SKSE::log::warn("Hall grass: this game version is not laid out as expected (AddCellGrass base+0x{:X}: hand-over {}, AddCellGrassNow {}, task {}): the grass fix stays off",
				add - base, doneOk ? "ok" : std::format("{:02X} {:02X} {:02X} {:02X} {:02X} {:02X}, neither form", d[0], d[1], d[2], d[3], d[4], d[5]),
				nowOk ? "ok" : "not a call to it", taskOk ? "ok" : "not a jump to it");
			return;
		}
		auto& tr = SKSE::GetTrampoline();
		// the hand-over: its 6 bytes become call [rip + x] to a slot of ours holding Done (written here, not by write_call<6>, which
		// reads the old target as a call [rip + x]'s, wrong for the virtual form)
		if (viaPtr) g_done = *reinterpret_cast<DoneFn*>(doneSite + 6 + disp);
		else g_doneSlot = disp;
		auto* slot = static_cast<std::uintptr_t*>(tr.allocate(sizeof(std::uintptr_t)));
		*slot = reinterpret_cast<std::uintptr_t>(&Done);
		const auto rel = reinterpret_cast<std::intptr_t>(slot) - static_cast<std::intptr_t>(doneSite + 6);
		if (rel < INT32_MIN || rel > INT32_MAX) {
			SKSE::log::warn("Hall grass: the trampoline is out of a call's reach of AddCellGrass: the grass fix stays off");
			return;
		}
		std::uint8_t patch[6]{ 0xFF, 0x15 };
		const auto   rel32 = static_cast<std::int32_t>(rel);
		std::memcpy(patch + 2, &rel32, 4);
		REL::safe_write(doneSite, patch, sizeof(patch));
		g_addNow = reinterpret_cast<AddCellFn>(tr.write_call<5>(nowSite, reinterpret_cast<std::uintptr_t>(&AddNow)));
		g_addTask = reinterpret_cast<AddCellFn>(tr.write_branch<5>(taskSite, reinterpret_cast<std::uintptr_t>(&AddTask)));
		SKSE::log::info("Hall grass: in place (AddCellGrass base+0x{:X}{}; the hand-over {})", add - base, ae17 ? ", AE 1.6.1130+" : "",
			viaVt ? std::format("the shape's virtual call, slot +0x{:X}", disp) : "a call through a pointer");
	}

	// At data load, with the hall installed: its ground, from its files
	void GrassOnDataLoaded()
	{
		if (!AG::GuildHall::Loaded()) return;
		std::vector<std::vector<std::array<float, 2>>> rings;
		try {
			std::ifstream in(kOutdoorPath);
			if (!in) {
				SKSE::log::warn("Hall grass: no {}: the grass fix has no ground to clear", kOutdoorPath);
				return;
			}
			const auto j = nlohmann::json::parse(in);
			for (const auto& p : j["blocked"]) {
				auto ring = [](const nlohmann::json& a_pts) {
					std::vector<std::array<float, 2>> r;
					for (const auto& q : a_pts) r.push_back({ q[0].get<float>(), q[1].get<float>() });
					return r;
				};
				rings.push_back(ring(p["outer"]));
				for (const auto& hole : p["holes"]) rings.push_back(ring(hole));
			}
		} catch (const std::exception& e) {
			SKSE::log::warn("Hall grass: {} unreadable ({}): the grass fix has no ground to clear", kOutdoorPath, e.what());
			return;
		}
		// the small pieces set on the ground: their bounds, turned and scaled (the big ones, the body, roof and site, are the outlines' already)
		std::vector<std::vector<std::array<float, 2>>> pieces;
		try {
			std::ifstream in(kLayoutPath);
			const auto    j = nlohmann::json::parse(in);
			auto*         dh = RE::TESDataHandler::GetSingleton();
			for (const auto& p : j["pieces"]) {
				const auto rec = p["b"].get<std::string>();
				const auto bar = rec.find('|');
				if (bar == std::string::npos) continue;
				auto* f = dh->LookupForm(static_cast<RE::FormID>(std::stoul(rec.substr(bar + 1), nullptr, 16)), rec.substr(0, bar));
				auto* bo = f ? f->As<RE::TESBoundObject>() : nullptr;
				if (!bo) continue;
				const auto&  b = bo->boundData;
				const float  s = p["s"].get<float>();
				if ((b.boundMax.x - b.boundMin.x) * s > kSmallPiece || (b.boundMax.y - b.boundMin.y) * s > kSmallPiece) continue;
				const float  lx0 = b.boundMin.x * s - kPieceMargin, lx1 = b.boundMax.x * s + kPieceMargin, ly0 = b.boundMin.y * s - kPieceMargin, ly1 = b.boundMax.y * s + kPieceMargin;
				const float a = p["a"].get<float>() * 3.14159265f / 180.0f, c = std::cos(a), sn = std::sin(a);
				const float px = p["x"].get<float>(), py = p["y"].get<float>();
				std::vector<std::array<float, 2>> r;   // (as the game turns a reference by its z angle: clockwise seen from above)
				for (auto [lx, ly] : { std::pair{ lx0, ly0 }, { lx1, ly0 }, { lx1, ly1 }, { lx0, ly1 } })
					r.push_back({ px + lx * c + ly * sn, py - lx * sn + ly * c });
				pieces.push_back(std::move(r));
			}
		} catch (const std::exception& e) {
			SKSE::log::warn("Hall grass: the layout's pieces unreadable ({}): only the outlines are cleared", e.what());
		}
		float x0 = 1e30f, y0 = 1e30f, x1 = -1e30f, y1 = -1e30f;
		for (const auto* set : { &rings, &pieces })
			for (const auto& r : *set)
				for (const auto& q : r) x0 = std::min(x0, q[0]), y0 = std::min(y0, q[1]), x1 = std::max(x1, q[0]), y1 = std::max(y1, q[1]);
		if (x0 > x1) return;
		g_mask.x0 = x0 - kRes * 2, g_mask.y0 = y0 - kRes * 2;
		g_mask.w = static_cast<int>((x1 - g_mask.x0) / kRes) + 3, g_mask.h = static_cast<int>((y1 - g_mask.y0) / kRes) + 3;
		g_mask.bits.assign(static_cast<std::size_t>(g_mask.w) * g_mask.h, 0);
		Rasterize(rings, g_mask.bits);
		for (const auto& r : pieces) Rasterize({ r }, g_mask.bits);
		// the outlines a margin wider too (the pieces have theirs): a blade rooted at the paving's very edge leans over it
		const int m = static_cast<int>(kMargin / kRes);
		auto      grown = g_mask.bits;
		for (int j = 0; j < g_mask.h; ++j)
			for (int i = 0; i < g_mask.w; ++i)
				if (g_mask.bits[static_cast<std::size_t>(j) * g_mask.w + i])
					for (int dj = -m; dj <= m; ++dj)
						for (int di = -m; di <= m; ++di)
							if (const int ii = i + di, jj = j + dj; ii >= 0 && jj >= 0 && ii < g_mask.w && jj < g_mask.h) grown[static_cast<std::size_t>(jj) * g_mask.w + ii] = 1;
		g_mask.bits = std::move(grown);
		std::size_t on = 0;
		for (auto b : g_mask.bits) on += b;
		g_mask.ok = true;
		SKSE::log::info("Hall grass: the hall's ground: {} outline ring(s), {} small piece(s), {:.0f} square units over ({:.0f}, {:.0f})-({:.0f}, {:.0f})",
			rings.size(), pieces.size(), on * kRes * kRes, x0, y0, x1, y1);
	}
}
