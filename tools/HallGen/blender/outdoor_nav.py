"""The Guild Hall's outdoor navmesh, for the DLL to fit into the loaded ground navmesh at run time (2026-11-13; the plan:
tools/hall-private/plans/OUTDOOR_NAVMESH.md). The hall's terrace, porch, walks, forecourt and stairs have no navmesh of their own:
followers who come out of the front door dropped to the vanilla ground navmesh under the terrace, inside the podium, and NPCs
pathed through the walls on the ground under the hall.

    python outdoor_nav.py <export dir> <out.json> [--plot out.png]

Reshaped to vanilla's shape (far fewer, larger triangles, as vanilla's outdoor navmesh is built;
measured: our 1154 triangles had a median area of 32 where vanilla's outdoor ones have 8192, 868 had an edge under 10, and vertices
stood up to 288 past their cell; then the run-time carve made 3021 ground triangles out of 165):
1. The site export with the building's footprint blocked solid (the interior export's ground floors, closed, widened by the
   walls: an exterior shell's hollows otherwise read as floors), the walls' outward corners cut at 45 degrees, and the load
   doors as walls, through navgen.py.
2. Each stair laid as vanilla meshes one: a ramp on its walking surface (guildhall_gen's RAMPS, rows across it foot to top), the
   rows kept only where its slope or curve turns. navgen's triangles over it are clipped away; an end that meets our mesh shares
   its vertices, an end on the ground (a foot) is left open for the DLL to join to the ground there.
3. The pieces that hold an anchor (the front and rear doors' outside landings) kept; the rest (hollows, wall tops, the road
   under the grand stair's foot) dropped.
4. Into the world (the DLL's own transform, hall.cpp, inverted), cut along the cells' borders so no triangle leaves its cell (as
   vanilla's never do), with its neighbours. Every triangle preferred, as vanilla's roads (Frontier 1.16's roads too).
5. Where the ground navmesh must go: the hall's footprint (its highest surface 30..900 over the land, 12 out from it) and ours,
   as outline polygons. The DLL keeps a ground triangle clear of them, takes out one inside them, and clips one across them on
   the outline (no lattice), as Frontier cuts "holes where your buildings stand (using each building's real outline)".
6. The stair feet, where our mesh is joined to the ground (nowhere else: a parapet stands between).
7. The gate: vanilla-sized triangles (median area, short edges), no vertex past its cell."""
import base64, json, math, os, struct, subprocess, sys
from collections import defaultdict
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.interpolate import LinearNDInterpolator
import shapely
from shapely.geometry import Polygon, box as sbox
from shapely.ops import unary_union

args = sys.argv[1:]
PLOT = None
if "--plot" in args: i = args.index("--plot"); PLOT = args[i + 1]; del args[i:i + 2]
E, OUT = args[0], args[1]
HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(E, "hall2_site_1.json")))
I = json.load(open(os.path.join(E, "hall2_interior.json")))
SX, SY, SZ, YAW = S["site"]; C_, S_ = math.cos(math.radians(YAW)), math.sin(math.radians(YAW))
def e2w(p): return (SX + p[0] * C_ + p[1] * S_, SY - p[0] * S_ + p[1] * C_, SZ + p[2])

def box(x0, x1, y0, y1, z0, z1):
    v = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    out = []
    for f in ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (3, 2, 6, 7), (2, 0, 4, 6), (1, 3, 7, 5)):
        q = [v[i] for i in f]; out += [[list(q[0]), list(q[1]), list(q[2])], [list(q[0]), list(q[2]), list(q[3])]]
    return out
def upright(a, b, z0, z1): return [[[a[0], a[1], z0], [b[0], b[1], z0], [b[0], b[1], z1]], [[a[0], a[1], z0], [b[0], b[1], z1], [a[0], a[1], z1]]]

# the land under the site (export frame): guildhall_gen's grid of the map's heights
GV = np.array([p for t in S["ground"] for p in t], float)
_land = LinearNDInterpolator(GV[:, :2], GV[:, 2])
def land(x, y):
    z = float(_land(x, y)); return z if math.isfinite(z) else None

# ---- 1. the building blocked solid; the walls' outward corners cut; the load doors as walls (export frame)
X0, X1, Y0, Y1, G = -2200, 2200, -2200, 2200, 4.0
NX, NY = int((X1 - X0) / G), int((Y1 - Y0) / G)
im = Image.new("1", (NX, NY), 0); dr = ImageDraw.Draw(im)
for k, s in I["shapes"].items():
    if not k.startswith(("floor", "planks", "steps")): continue
    V = np.array(s["v"])
    for f in s["f"]:
        P = V[f]; n = np.cross(P[1] - P[0], P[2] - P[0]); nn = np.linalg.norm(n)
        if nn < 1e-9 or abs(n[2]) / nn < 0.9 or not (-20 <= P[:, 2].mean() <= 40): continue
        dr.polygon([((p[0] - X0) / G, (p[1] - Y0) / G) for p in P], fill=1)
M = ndimage.binary_fill_holes(ndimage.binary_closing(np.array(im, bool), iterations=6))
M = ndimage.binary_erosion(ndimage.binary_dilation(M, iterations=12), iterations=10)   # (to 8 inside the walls' outer faces)
site = dict(S); site["coll"] = list(S["coll"])
for j in range(0, M.shape[0], 4):
    row = M[j:j + 4].any(axis=0); i = 0
    while i < len(row):
        if row[i]:
            k = i
            while k < len(row) and row[k]: k += 1
            site["coll"] += box(X0 + i * G, X0 + k * G, Y0 + j * G, Y0 + (j + 4) * G, -60, 700); i = k
        else: i += 1
# the walls' outward corners (followers cut the pillar at the top of the curving steps, the navmesh wrapping ~8 from its
# corner, under an actor's radius): first a ring of 12 faces round each corner; now one 45-degree cut across it,
# CORNER_CUT out from the corner on its bisector, as a solid wedge between the two walls' lines carried on past the corner: the
# navmesh's outline turns there in one straight edge instead of ~10 short ones. A corner: an end of an upright face's footprint
# met by exactly one other face's end, not in line with it
CORNER_CUT = float(os.environ.get("CORNER_CUT", "16"))
if CORNER_CUT:
    ends = {}
    for t in S["coll"]:
        P = np.array(t, float); a, b, c = P[:, :2]
        if abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) > 1e-3: continue
        e = max(((0, 1), (1, 2), (2, 0)), key=lambda q: np.hypot(*(P[q[1], :2] - P[q[0], :2])))
        A, B = P[e[0], :2], P[e[1], :2]; L = np.hypot(*(B - A))
        if L < 1: continue
        d = (B - A) / L
        for q, dd in ((A, d), (B, -d)):
            ends.setdefault((round(q[0]), round(q[1])), []).append((dd, P[:, 2].min(), P[:, 2].max()))
    cuts = skipped = 0
    for (x, y), lst in ends.items():
        dirs = []
        for d, _, _ in lst:                                          # (a face split in two along its length ends twice in one direction)
            if not any(np.dot(d, e_) > 0.999 for e_ in dirs): dirs.append(d)
        if len(dirs) == 2 and np.dot(dirs[0], dirs[1]) < -0.99: continue   # a wall carried on in line: not a corner
        z0, z1 = min(z for _, z, _ in lst), max(z for _, _, z in lst)
        if z1 - z0 < 30: continue
        if len(dirs) != 2: skipped += 1; continue
        th = math.acos(max(-1.0, min(1.0, float(np.dot(dirs[0], dirs[1])))))   # the angle between the two walls
        k = CORNER_CUT / max(0.2, math.cos(th / 2))
        Cc = np.array([x, y], float); A = Cc - dirs[0] * k; B = Cc - dirs[1] * k
        for p, q in ((Cc, A), (A, B), (B, Cc)): site["coll"] += upright(p, q, z0, z1)
        cuts += 1
    print("CORNERS cut:", cuts, "at", CORNER_CUT, "| left (not two faces):", skipped)
DOORS = []
for p in S["pieces"]:
    if "sdoubledoorint01" in p["model"].lower():
        x, y, z = p["pos"]; DOORS.append((x, y, z, p.get("yaw", 0)))
        site["coll"] += box(x - 12, x + 12, y - 140, y + 140, z - 2, z + 240) if abs(math.sin(math.radians(p.get("yaw", 0)))) > 0.7 else box(x - 140, x + 140, y - 12, y + 12, z - 2, z + 240)
tmp_site, tmp_nav = OUT + ".site.json", OUT + ".navgen.json"
json.dump(site, open(tmp_site, "w"))
r = subprocess.run([sys.executable, os.path.join(HERE, "navgen.py"), tmp_site, tmp_nav, "--records", os.path.join(E, "records_site.json")], capture_output=True, text=True)
if r.returncode: sys.exit("navgen failed:\n" + r.stdout[-2000:] + r.stderr[-2000:])
N = json.load(open(tmp_nav)); os.remove(tmp_site); os.remove(tmp_nav)
VX = [list(map(float, v)) for v in N["verts"]]                  # the mesh, export frame: vertices and triangles (vertex indices)
TX = [list(t["v"]) for t in N["tris"]]
print(f"navgen: {len(TX)} triangles")

def area2(a, b, c): return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
def plane_z(t, x, y):
    a, b, c = (VX[i] for i in t); d = area2(a, b, c)
    if abs(d) < 1e-9: return (a[2] + b[2] + c[2]) / 3
    l1 = area2((x, y), b, c) / d; l2 = area2(a, (x, y), c) / d
    return l1 * a[2] + l2 * b[2] + (1 - l1 - l2) * c[2]
SIGN = 1 if sum(1 if area2(*(VX[i] for i in t)) > 0 else -1 for t in TX) >= 0 else -1   # navgen's winding, kept for every triangle

# ---- 2. the stairs as ramps
RAMPS = S.get("ramps", [])
def coarsen(rows, txy=4.0, tz=3.0):
    """the rows a ramp needs: from each kept row, as far on as every row between lies on the straight sides (xy within txy, z tz)"""
    keep = [0]; a = 0
    while a < len(rows) - 1:
        b = a + 1
        while b + 1 < len(rows):
            ok = True
            for m in range(a + 1, b + 2):
                u = (m - a) / (b + 1 - a)
                for s in (0, 1):
                    P0, P1, Pm = np.array(rows[a][s]), np.array(rows[b + 1][s]), np.array(rows[m][s])
                    q = P0 + u * (P1 - P0)
                    if np.hypot(*(q[:2] - Pm[:2])) > txy or abs(q[2] - Pm[2]) > tz: ok = False
            if not ok: break
            b += 1
        keep.append(b); a = b
    return [rows[k] for k in keep]
ramps = []
for rows in RAMPS:
    rows = [[list(map(float, l)), list(map(float, r_))] for l, r_ in rows]
    fp = Polygon([r_[0][:2] for r_ in rows] + [r_[1][:2] for r_ in rows[::-1]]).buffer(0)
    ends = []
    for k in (0, len(rows) - 1):                                     # a foot: an end on the land (the DLL joins it there)
        mz = (rows[k][0][2] + rows[k][1][2]) / 2; mx, my = ((rows[k][0][0] + rows[k][1][0]) / 2, (rows[k][0][1] + rows[k][1][1]) / 2)
        g = land(mx, my); ends.append(g is not None and abs(mz - g) < 60)   # (the back stair ends 33 over the map's land: its yard is set 220 out)
    kept = coarsen(rows)
    ramps.append(dict(rows=kept, all=rows, fp=fp, foot=ends))
    print(f"RAMP {len(rows)} rows -> {len(kept)}; ends on the land (feet): {ends}; z {rows[0][0][2]:.0f}..{rows[-1][0][2]:.0f}")
def ramp_z(rp, x, y):
    """the ramp's surface under (x, y): the nearest strip between its rows, on its plane"""
    best = None
    for a, b in zip(rp["all"], rp["all"][1:]):
        for tri in ((a[0], a[1], b[1]), (a[0], b[1], b[0])):
            d = area2(*tri)
            if abs(d) < 1e-9: continue
            l1 = area2((x, y), tri[1], tri[2]) / d; l2 = area2(tri[0], (x, y), tri[2]) / d; l3 = 1 - l1 - l2
            out = -min(l1, l2, l3)
            z = l1 * tri[0][2] + l2 * tri[1][2] + l3 * tri[2][2]
            if best is None or out < best[0]: best = (out, z)
    return best[1]
# clip navgen's triangles over each ramp (within its riser of the ramp's surface: nothing of ours lies over or under a stair but its
# own treads) to the outside of its footprint
newV, newT = list(VX), []
vkey = defaultdict(list)                                         # (x, y to a tenth) -> vertices there; one within 30 up or down is the same
def vadd(p):
    k = (round(p[0], 1), round(p[1], 1))
    for i in vkey[k]:
        if abs(newV[i][2] - p[2]) < 30: return i
    vkey[k].append(len(newV)); newV.append([p[0], p[1], p[2]]); return len(newV) - 1
for i, p in enumerate(VX): vkey[(round(p[0], 1), round(p[1], 1))].append(i)
clipped = dropped = 0
for t in TX:
    tri = [VX[i] for i in t]; tp = Polygon([q[:2] for q in tri])
    hit = [rp for rp in ramps if tp.intersects(rp["fp"]) and tp.intersection(rp["fp"]).area > 1e-3
           and abs(plane_z(t, *tp.intersection(rp["fp"]).representative_point().coords[0]) - ramp_z(rp, *tp.intersection(rp["fp"]).representative_point().coords[0])) < 60]
    if not hit: newT.append(list(t)); continue
    rest = tp
    for rp in hit: rest = rest.difference(rp["fp"])
    if rest.is_empty or rest.area < 1: dropped += 1; continue
    clipped += 1
    for g in getattr(rest, "geoms", [rest]):
        if g.geom_type != "Polygon" or g.area < 1: continue
        for tr in shapely.constrained_delaunay_triangles(g).geoms:
            q = list(tr.exterior.coords)[:3]
            if abs(area2(*q)) < 0.5: continue
            ids = [vadd((x, y, plane_z(t, x, y))) for x, y in q]
            if len(set(ids)) < 3: continue
            if area2(*(newV[i] for i in ids)) * SIGN < 0: ids = [ids[0], ids[2], ids[1]]
            newT.append(ids)
print(f"STAIRS: {dropped} navgen triangles over the ramps dropped, {clipped} clipped to their outline")
# lay each ramp: its end rows take the vertices our clipped mesh has along them (a foot keeps only its two corners: left open)
def on_row(p0, p1, z, tol=0.6):
    out = []
    for i, v in enumerate(newV):
        L = np.hypot(p1[0] - p0[0], p1[1] - p0[1]); u = ((v[0] - p0[0]) * (p1[0] - p0[0]) + (v[1] - p0[1]) * (p1[1] - p0[1])) / L / L
        if -1e-3 <= u <= 1 + 1e-3 and abs(area2(p0, p1, v)) / L < tol and abs(v[2] - z) < 40: out.append((u, i))
    return out
used = set(i for t in newT for i in t)
nramp = 0
for rp in ramps:
    rows = rp["rows"]; R = []
    for k, (l, r_) in enumerate(rows):
        row = [(0.0, vadd(l)), (1.0, vadd(r_))]
        if k in (0, len(rows) - 1) and not rp["foot"][0 if k == 0 else 1]:
            for u, i in on_row(l, r_, (l[2] + r_[2]) / 2):
                if i in used and all(abs(u - u2) > 1e-3 for u2, _ in row): row.append((u, i))
        R.append(sorted(row))
    for A_, B_ in zip(R, R[1:]):                                     # a strip between two rows: zipped along both by where on the row
        A, B = [i for _, i in A_], [i for _, i in B_]; uA, uB = [u for u, _ in A_], [u for u, _ in B_]
        i = j = 0
        while i < len(A) - 1 or j < len(B) - 1:
            if j == len(B) - 1 or (i < len(A) - 1 and uA[i + 1] <= uB[j + 1]): tri = [A[i], A[i + 1], B[j]]; i += 1
            else: tri = [A[i], B[j + 1], B[j]]; j += 1
            if abs(area2(*(newV[q] for q in tri))) < 0.5: continue
            if area2(*(newV[q] for q in tri)) * SIGN < 0: tri = [tri[0], tri[2], tri[1]]
            newT.append(tri); nramp += 1
print(f"RAMPS laid: {nramp} triangles over {len(ramps)} stairs")

# ---- 2b. weld: vertices within WELD across (and 30 up or down) are one, so a stair's end row and the surface it meets share
#      their seam (their vertices can stand a unit or two apart, which the tenth-rounded key above misses); a triangle that
#      collapses is dropped
WELD = 1.5
_rep = list(range(len(newV)))
def _root(i):
    while _rep[i] != i: _rep[i] = _rep[_rep[i]]; i = _rep[i]
    return i
_grid = defaultdict(list)
for i, v in enumerate(newV): _grid[(int(v[0] // 4), int(v[1] // 4))].append(i)
nweld = 0
for (gx_, gy_), ids_ in list(_grid.items()):
    cand = [j for dx_ in (-1, 0, 1) for dy_ in (-1, 0, 1) for j in _grid.get((gx_ + dx_, gy_ + dy_), [])]
    for i in ids_:
        for j in cand:
            if j <= i: continue
            a_, b_ = newV[i], newV[j]
            if math.hypot(a_[0] - b_[0], a_[1] - b_[1]) < WELD and abs(a_[2] - b_[2]) < 30:
                ri, rj = _root(i), _root(j)
                if ri != rj: _rep[max(ri, rj)] = min(ri, rj); nweld += 1
_T2 = []
for t in newT:
    q = [_root(i) for i in t]
    if len(set(q)) == 3 and abs(area2(*(newV[k] for k in q))) >= 0.5: _T2.append(q)
print(f"WELD: {nweld} vertices joined to a neighbour within {WELD}; {len(newT) - len(_T2)} triangles collapsed")
newT = _T2
# ---- 3. the pieces that hold an anchor: each door's outside landing (60 out from the door, on its outer side)
def adjacency(T):
    em = defaultdict(list)
    for ti, t in enumerate(T):
        for k in range(3): em[frozenset((t[k], t[(k + 1) % 3]))].append((ti, k))
    links = [[-1, -1, -1] for _ in T]; nonman = 0
    for e, lst in em.items():
        if len(lst) == 2: (a, ka), (b, kb) = lst; links[a][ka] = b; links[b][kb] = a
        elif len(lst) > 2: nonman += 1
    return links, nonman
links, nonman = adjacency(newT)
par = list(range(len(newT)))
def f(i):
    while par[i] != i: par[i] = par[par[i]]; i = par[i]
    return i
for i, ls in enumerate(links):
    for nb in ls:
        if nb >= 0: par[f(i)] = f(nb)
def inside(q, t):
    a, b, c = (newV[i] for i in t); d = area2(a, b, c)
    if abs(d) < 1e-9: return None
    l1 = area2(q, b, c) / d; l2 = area2(a, q, c) / d
    return None if min(l1, l2, 1 - l1 - l2) < -1e-6 else l1 * a[2] + l2 * b[2] + (1 - l1 - l2) * c[2]
keep_roots = set(); anchors = []
for x, y, z, yaw in DOORS:
    for sgn in (1, -1):                       # whichever side of the door holds our mesh at the door's height (the outside;
        q = (x + sgn * 60, y, z)              # both doors face along the export's x)
        hit = [i for i, t in enumerate(newT) if (zz := inside(q, t)) is not None and abs(zz - z) < 40]
        if hit: keep_roots.add(f(hit[0])); anchors.append(q); break
if len(keep_roots) < len(DOORS): sys.exit(f"outdoor navmesh: {len(keep_roots)} of {len(DOORS)} doors have our mesh at their outside landing")
K = [t for i, t in enumerate(newT) if f(i) in keep_roots]
print(f"kept {len(K)} of {len(newT)} triangles ({len(set(f(i) for i in range(len(newT))))} pieces, {len(keep_roots)} with a door)")
# a stair whose foot row is not in a kept piece is loose: nothing joins it to a door's landing (an obstacle at its top, a seam that
# did not close). Said by name; its foot is not offered to the DLL to join (it would join the ground to nothing)
_kv = {i for t in K for i in t}
for rp in ramps:
    ids_ = {_root(vadd(rp["rows"][k][s_])) for k in (0, len(rp["rows"]) - 1) for s_ in (0, 1) if rp["foot"][0 if k == 0 else 1]}
    rp["kept"] = not ids_ or bool(ids_ & _kv)
    if not rp["kept"]:
        m_ = rp["rows"][0][0]; print(f"LOOSE STAIR: the stair whose foot is at export ({m_[0]:.0f}, {m_[1]:.0f}, {m_[2]:.0f}) is joined to no door's landing: left out")

# ---- 3b. clean-up, as a mesh is cleaned before it ships: each edge under MIN_EDGE collapsed into one of its ends (one on the outline
#      only along the outline, a foot's corners never moved, never where a triangle would turn over or fold), then on level ground
#      each pair of triangles flipped to the shorter diagonal where both stay sound (no slivers left between the joins)
MIN_EDGE = 10.0
locked = set()
for rp in ramps:
    for k, isfoot in zip((0, len(rp["rows"]) - 1), rp["foot"]):
        if isfoot: locked |= {vadd(rp["rows"][k][0]), vadd(rp["rows"][k][1])}
def tri_ok(t):
    a, b, c = (newV[i] for i in t); A = area2(a, b, c) * SIGN
    if A <= 1.0: return False
    L = max(math.dist(a[:2], b[:2]), math.dist(b[:2], c[:2]), math.dist(c[:2], a[:2]))
    return A / L >= 0.5                                          # (twice the height over the longest side: no needle under a quarter)
def boundary_edges(T):
    cnt = defaultdict(int)
    for t in T:
        for k in range(3): cnt[frozenset((t[k], t[(k + 1) % 3]))] += 1
    return {e for e, n in cnt.items() if n == 1}
def collapse(T):
    n_done = 0
    for _ in range(50):
        bnd = boundary_edges(T); bverts = {v for e in bnd for v in e}
        vt = defaultdict(set)
        for ti, t in enumerate(T):
            for v in t: vt[v].add(ti)
        edges = sorted({frozenset((t[k], t[(k + 1) % 3])) for t in T for k in range(3)}, key=lambda e: math.dist(*(newV[v][:2] for v in e)))
        dead = set(); changed = 0
        for e in edges:
            a, b = tuple(e)
            if math.dist(newV[a][:2], newV[b][:2]) >= MIN_EDGE: break
            if any(ti in dead for ti in vt[a] | vt[b]): continue
            for keep, gone in ((a, b), (b, a)):
                if gone in locked: continue
                if gone in bverts and e not in bnd: continue                     # (an outline vertex slides only along the outline)
                if abs(newV[keep][2] - newV[gone][2]) > 24: continue
                shared = vt[keep] & vt[gone]
                # the link condition: the two ends' common neighbours are the third corners of the triangles on the edge only
                nk = {v for ti in vt[keep] for v in T[ti]} - {keep}; ng = {v for ti in vt[gone] for v in T[ti]} - {gone}
                thirds = {v for ti in shared for v in T[ti]} - {keep, gone}
                if (nk & ng) - thirds: continue
                new = {ti: [keep if v == gone else v for v in T[ti]] for ti in vt[gone] - shared}
                if not all(tri_ok(t) for t in new.values()): continue
                for ti, t in new.items(): T[ti] = t
                dead |= shared | vt[keep] | vt[gone]
                for ti in shared: T[ti] = None
                changed += 1; break
        T[:] = [t for t in T if t is not None]
        n_done += changed
        if not changed: break
    return n_done
def flips(T):
    n = 0
    for _ in range(20):
        em = {}
        for ti, t in enumerate(T):
            for k in range(3): em[(t[k], t[(k + 1) % 3])] = ti
        bnd = boundary_edges(T); changed = 0; touched = set()
        for (u, v), t1 in list(em.items()):
            t2 = em.get((v, u))
            if t2 is None or t1 in touched or t2 in touched or u > v: continue
            w1 = next(x for x in T[t1] if x not in (u, v)); w2 = next(x for x in T[t2] if x not in (u, v))
            P = [newV[x] for x in (u, v, w1, w2)]
            if max(p[2] for p in P) - min(p[2] for p in P) > 2: continue                       # level ground only
            if math.dist(newV[w1][:2], newV[w2][:2]) >= math.dist(newV[u][:2], newV[v][:2]) - 1e-3: continue
            n1, n2 = [u, w2, w1], [w2, v, w1]
            if not (tri_ok(n1) and tri_ok(n2)): continue
            q1 = min(area2(*(newV[x] for x in T[t1])) * SIGN, area2(*(newV[x] for x in T[t2])) * SIGN)
            if min(area2(*(newV[x] for x in n1)) * SIGN, area2(*(newV[x] for x in n2)) * SIGN) < q1 * 0.5: continue
            T[t1], T[t2] = n1, n2; touched |= {t1, t2}; changed += 1
        n += changed
        if not changed: break
    return n
nc = collapse(K); nf = flips(K); nc += collapse(K)
print(f"CLEAN-UP: {nc} short edges collapsed, {nf} flips; {len(K)} triangles")

# ---- 4. into the world; cut along the cells' borders (each edge cut once, its point shared by both sides)
W = [list(e2w(p)) for p in newV]
T = [list(t) for t in K]
def cut_line(axis, c):
    global T
    mid = {}
    def mpt(a, b):
        k = (min(a, b), max(a, b))
        if k not in mid:
            A, B = W[a], W[b]; u = (c - A[axis]) / (B[axis] - A[axis])
            W.append([A[k_] + u * (B[k_] - A[k_]) for k_ in range(3)]); W[-1][axis] = c; mid[k] = len(W) - 1
        return mid[k]
    out = []; n = 0
    for t in T:
        s = [W[i][axis] - c for i in t]
        if all(v >= -1e-6 for v in s) or all(v <= 1e-6 for v in s): out.append(t); continue
        n += 1
        # the vertex alone on its side, and the two edges from it cut
        for k in range(3):
            a, b, cc = t[k], t[(k + 1) % 3], t[(k + 2) % 3]
            sa, sb, sc = s[k], s[(k + 1) % 3], s[(k + 2) % 3]
            if abs(sa) > 1e-6 and (sa > 0) != (sb > 0) and (sa > 0) != (sc > 0) and abs(sb) > 1e-6 and abs(sc) > 1e-6:
                p, q = mpt(a, b), mpt(cc, a)
                out += [[a, p, q], [p, b, cc], [p, cc, q]]; break
            if abs(sb) <= 1e-6 and (sa > 0) != (sc > 0) and abs(sa) > 1e-6 and abs(sc) > 1e-6:   # through vertex b
                p = mpt(cc, a); out += [[a, b, p], [p, b, cc]]; break
        else: out.append(t)
    T = out; return n
xs = [W[i][0] for t in T for i in t]; ys = [W[i][1] for t in T for i in t]
splits = 0
for axis, lo, hi in ((0, min(xs), max(xs)), (1, min(ys), max(ys))):
    for k in range(math.floor(lo / 4096) + 1, math.floor(hi / 4096) + 1): splits += cut_line(axis, k * 4096.0)
# compact; weld (the cut points are shared by construction); neighbours
idx = {}; verts = []
for t in T:
    for i in t:
        if i not in idx: idx[i] = len(verts); verts.append([round(c, 2) for c in W[i]])
T = [[idx[i] for i in t] for t in T]
T = [t for t in T if abs(area2(*(verts[i] for i in t))) >= 0.05]
links, nonman = adjacency(T)
tris = [t + links[i] for i, t in enumerate(T)]
cellof = lambda p: (math.floor(p[0] / 4096), math.floor(p[1] / 4096))
cells = sorted({cellof([sum(verts[i][k] for i in t[:3]) / 3 for k in range(2)]) for t in tris})
print(f"cells: {cells}; {splits} triangles cut on their borders; non-manifold edges {nonman}")

# ---- 5. where the ground navmesh must go: the hall's footprint and ours, as outline polygons (world)
RG = 16.0; RX0, RX1, RY0, RY1 = -2400.0, 2600.0, -2400.0, 2400.0
RNX, RNY = int((RX1 - RX0) / RG), int((RY1 - RY0) / RG)
top = np.full((RNY, RNX), -32768, dtype=np.int32)
for t in S["coll"]:                                             # the hall's highest surface over each column (its own collision)
    P = np.array(t, float); lo, hi = P.min(0), P.max(0)
    i0, i1 = max(0, int((lo[0] - RX0) // RG)), min(RNX - 1, int((hi[0] - RX0) // RG)); j0, j1 = max(0, int((lo[1] - RY0) // RG)), min(RNY - 1, int((hi[1] - RY0) // RG))
    if i1 < i0 or j1 < j0: continue
    a, b, c = P[:, :2]; dd = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if abs(dd) < 1e-6:                                           # upright: its footprint, sampled every quarter column
        e_ = max(((a, b), (b, c), (c, a)), key=lambda q: np.hypot(*(q[1] - q[0])))
        n_ = max(2, int(np.hypot(*(e_[1] - e_[0])) / (RG / 4)) + 1)
        for u in np.linspace(0, 1, n_):
            q = e_[0] + u * (e_[1] - e_[0]); i, j = int((q[0] - RX0) // RG), int((q[1] - RY0) // RG)
            if 0 <= i < RNX and 0 <= j < RNY: top[j, i] = max(top[j, i], int(math.ceil(hi[2])))
        continue
    Ii, Jj = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1)); qx, qy = RX0 + (Ii + .5) * RG, RY0 + (Jj + .5) * RG
    l1 = ((b[0] - qx) * (c[1] - qy) - (b[1] - qy) * (c[0] - qx)) / dd; l2 = ((c[0] - qx) * (a[1] - qy) - (c[1] - qy) * (a[0] - qx)) / dd
    m_ = np.minimum(np.minimum(l1, l2), 1 - l1 - l2) >= -1e-6
    if not m_.any(): continue
    z_ = np.ceil(l1 * P[0, 2] + l2 * P[1, 2] + (1 - l1 - l2) * P[2, 2]).astype(np.int32)
    blk = top[j0:j1 + 1, i0:i1 + 1]; blk[m_] = np.maximum(blk[m_], z_[m_])
cx_ = RX0 + (np.arange(RNX) + .5) * RG; cy_ = RY0 + (np.arange(RNY) + .5) * RG
CXg, CYg = np.meshgrid(cx_, cy_); LZ = _land(CXg, CYg)
over = top - LZ
# (the land is the map's heights, as the ground navmesh lies on; a column past the land grid counts where the hall stands at all)
hallmask = (top != -32768) & (np.where(np.isfinite(over), (over >= 30) & (over <= 900), True))
rects = []
for j in range(RNY):
    row = hallmask[j]; i = 0
    while i < RNX:
        if row[i]:
            k = i
            while k < RNX and row[k]: k += 1
            rects.append(sbox(RX0 + i * RG, RY0 + j * RG, RX0 + k * RG, RY0 + (j + 1) * RG)); i = k
        else: i += 1
hall_fp = unary_union(rects).buffer(12, join_style=2).simplify(12)   # (12: past the raster's 16-unit steps on a diagonal)
for rp in ramps:                                                # (in front of a foot the ground stays, up to our edge: the DLL joins there)
    for k, isfoot in zip((0, len(rp["rows"]) - 1), rp["foot"]):
        if not isfoot: continue
        l, r_ = (np.array(p[:2]) for p in rp["rows"][k]); inn = (np.array(rp["rows"][1 if k == 0 else -2][0][:2]) + np.array(rp["rows"][1 if k == 0 else -2][1][:2])) / 2
        out_ = (l + r_) / 2 - inn; out_ = out_ / np.linalg.norm(out_)
        hall_fp = hall_fp.difference(Polygon([l, r_, r_ + out_ * 96, l + out_ * 96]))
ours_fp = unary_union([Polygon([newV[i][:2] for i in t]) for t in K if abs(area2(*(newV[i] for i in t))) > 1e-6]).buffer(0.5, join_style=2).buffer(-0.5, join_style=2)
SPANS = [Polygon(sp) for sp in S.get("spans", [])]           # a bridge's open span (guildhall_gen's d["spans"]): the ground under it
if SPANS:                                                    # keeps its navmesh, so the road under a bridge stays walkable
    sp_ = unary_union(SPANS); hall_fp = hall_fp.difference(sp_); ours_fp = ours_fp.difference(sp_)
    print(f"SPANS: {len(SPANS)} open span(s) left to the ground, {sp_.area:.0f} square")
blocked = unary_union([hall_fp, ours_fp]).simplify(2)
# (2026-11-17) the road under a bridge must join the road outside it: an open span left as a hole in the blocked area is an island
# of ground navmesh that pathing can reach from nowhere (followers could not route under site B's bridge)
for sp_ in SPANS:
    for g_ in getattr(blocked, "geoms", [blocked]):
        for h_ in getattr(g_, "interiors", []):
            if Polygon(h_).buffer(1).intersects(sp_):
                sys.exit(f"FAIL BRIDGE SPAN SHUT IN: the ground under a bridge ({sp_.bounds[0]:.0f}, {sp_.bounds[1]:.0f})-({sp_.bounds[2]:.0f}, {sp_.bounds[3]:.0f}) "
                         f"is a hole in the blocked area, cut off from the road outside: the span must reach past what overhangs it")
polys = []
for g in getattr(blocked, "geoms", [blocked]):
    if g.geom_type != "Polygon" or g.area < 64: continue
    W2 = lambda cs: [[round(c, 1) for c in e2w((x, y, 0))[:2]] for x, y in list(cs)[:-1]]
    polys.append({"outer": W2(g.exterior.coords), "holes": [W2(h.coords) for h in g.interiors if Polygon(h).area >= 64]})
nbv = sum(len(p["outer"]) + sum(len(h) for h in p["holes"]) for p in polys)
print(f"BLOCKED: {len(polys)} outline polygon(s), {nbv} vertices (the hall's footprint 12 out, and ours)")

# ---- 6. the stair feet (world): each ramp's end on the land, the middle of its end row, its reach half the row + 80
feet = []
for rp in ramps:
    if not rp.get("kept", True): continue
    for k, isfoot in zip((0, len(rp["rows"]) - 1), rp["foot"]):
        if not isfoot: continue
        l, r_ = rp["rows"][k]; m = [(l[c] + r_[c]) / 2 for c in range(3)]
        feet.append([round(c, 1) for c in e2w(m)] + [round(max(200.0, math.hypot(l[0] - r_[0], l[1] - r_[1]) / 2 + 80), 1)])

out = dict(version=2, site=S["site"], cross=S.get("nav_cross", True), verts=verts, tris=tris, preferred=True, blocked=polys, feet=feet,
           anchors=[[round(c, 1) for c in e2w(a)] for a in anchors])
json.dump(out, open(OUT, "w"))

# ---- 7. the gate: vanilla-sized triangles (vanilla's outdoor ones round the hall: median 8192, a tenth under 2048), no vertex past
#      its cell, every triangle with neighbours or an open edge (no edge used three times)
A_ = sorted(abs(area2(*(verts[i] for i in t[:3]))) / 2 for t in tris)
E_ = [min(math.dist(verts[t[a]][:2], verts[t[b]][:2]) for a, b in ((0, 1), (1, 2), (2, 0))) for t in tris]
past = 0
for t in tris:
    cc = cellof([sum(verts[i][k] for i in t[:3]) / 3 for k in range(2)])
    for i in t[:3]:
        v = verts[i]
        if not (cc[0] * 4096 - 0.5 <= v[0] <= (cc[0] + 1) * 4096 + 0.5 and cc[1] * 4096 - 0.5 <= v[1] <= (cc[1] + 1) * 4096 + 0.5): past += 1
med = A_[len(A_) // 2]; short = sum(e < 10 for e in E_)
print(f"OUTDOOR NAVMESH {len(tris)} triangles, {len(verts)} vertices, area median {med:.0f} (10% {A_[len(A_) // 10]:.0f}), "
      f"{short} with an edge under 10, {past} vertices past their cell, feet {len(feet)}, cells {cells} -> {OUT}")
if PLOT:
    S2 = 0.3; W_, H_ = int(4000 * S2), int(4000 * S2); img = Image.new("RGB", (W_, H_), (25, 25, 25)); d = ImageDraw.Draw(img)
    Lp = lambda p: (p[1], -p[0], p[2]); Pp = lambda x, y: ((x + 2000) * S2, (2000 - y) * S2)
    for g in getattr(blocked, "geoms", [blocked]):
        if g.geom_type == "Polygon": d.polygon([Pp(*Lp((x, y, 0))[:2]) for x, y in g.exterior.coords], outline=(160, 60, 60))
    for t in K:
        q = [Lp(newV[i]) for i in t]; z = sum(p[2] for p in q) / 3; c = int(max(0, min(255, (z + 700) / 1150 * 255)))
        d.polygon([Pp(p[0], p[1]) for p in q], fill=(c, 150, 255 - c), outline=(20, 20, 20))
    img.save(PLOT)
# every foot reaches a door's landing over our own mesh (its triangles' neighbours)
def tri_at(q, dz=40):
    for ti, t in enumerate(tris):
        a, b, c = (verts[i] for i in t[:3]); d = area2(a, b, c)
        if abs(d) < 1e-9: continue
        l1 = area2(q, b, c) / d; l2 = area2(a, q, c) / d
        if min(l1, l2, 1 - l1 - l2) >= -1e-4 and abs(l1 * a[2] + l2 * b[2] + (1 - l1 - l2) * c[2] - q[2]) < dz: return ti
    return None
def reach(t0):
    seen = {t0}; st = [t0]
    while st:
        u = st.pop()
        for nb in tris[u][3:]:
            if nb >= 0 and nb not in seen: seen.add(nb); st.append(nb)
    return seen
door_t = [tri_at(e2w(a_)) for a_ in anchors]
unreached = []
for ft in feet:
    # (the foot's own triangle, under it within 60: the nearest one by its middle passed a stair that had no mesh at all)
    t0 = None                                                  # (a foot lies on its strip's outer edge: within a hundredth of it)
    for ti, t in enumerate(tris):
        a, b, c = (verts[i] for i in t[:3]); d = area2(a, b, c)
        if abs(d) < 1e-9: continue
        l1 = area2(ft[:3], b, c) / d; l2 = area2(a, ft[:3], c) / d
        if min(l1, l2, 1 - l1 - l2) >= -1e-2 and abs(l1 * a[2] + l2 * b[2] + (1 - l1 - l2) * c[2] - ft[2]) < 60: t0 = ti; break
    if t0 is None: unreached.append(ft[:3]); continue
    R_ = reach(t0)
    if not any(dt in R_ for dt in door_t if dt is not None): unreached.append(ft[:3])
print(f"REACH: {len(feet) - len(unreached)} of {len(feet)} feet reach a door's landing over our mesh; door landings found {sum(d is not None for d in door_t)} of {len(door_t)}")
fails = []
if unreached: fails.append(f"feet that reach no door: {unreached}")
if None in door_t: fails.append("a door's landing is on none of our triangles")
if len(tris) > 400: fails.append(f"{len(tris)} triangles (budget 400)")
if med < 2048: fails.append(f"median area {med:.0f} under 2048")
if short > len(tris) // 10: fails.append(f"{short} triangles with an edge under 10 (over a tenth)")
if past: fails.append(f"{past} vertices past their cell")
if nonman: fails.append(f"{nonman} edges used by three or more triangles")
if fails: sys.exit("OUTDOOR NAVMESH GATE FAILED: " + "; ".join(fails))
