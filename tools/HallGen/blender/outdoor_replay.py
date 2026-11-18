"""The outdoor navmesh fit (src/plugin/src/hall/outdoor.cpp) replayed on a clean install dump, before it goes in game (2026-11-13).
  Dumps: tools/hall-private/navdumps/ (one test install's Navmesh_Merge ground, one vanilla), taken by AGHallNative.Dump and the old stair patch
  stripped out.
  blocked(p): inside the outline polygons (outdoor_nav.py v2: the hall's footprint and ours).
  a ground triangle clear of the outline: kept; inside: cut; across: carved. Its edges are split where the outline crosses them,
  deterministically from the edge itself, so the triangle across is re-cut with the same points (a portal edge never: such a triangle
  goes whole, by its middle). Each re-cut triangle: its part outside the outline, its boundary points put back, triangulated.
  ours added; each of our open edges near a foot joined to the nearest open ground edge within 48 (60 up/down); back where open.
  checks: reach both ways between each foot's ground ring and each door; no kept ground piece with a blocked centre; part counts.
    python replay4.py <clean dump> <outdoor_nav.json> [--feet x,y,z,r;x,y,z,r] [--debug]"""
import json, sys, math, base64, collections
import numpy as np
dump, onav = sys.argv[1:3]
OUT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "outdoor_replay_out.json"
D = json.load(open(dump)); O = json.load(open(onav))
if "--feet" in sys.argv: O["feet"] = [[float(v) for v in f.split(",")] for f in sys.argv[sys.argv.index("--feet") + 1].split(";")]
SX, SY, SZ, YAW = O["site"]; C_, S_ = math.cos(math.radians(YAW)), math.sin(math.radians(YAW))
# (2026-11-13, version 2: the outline polygons, as the DLL now carves: exactly, on the outline's line, no lattice)
import shapely
from shapely.geometry import Polygon as SPoly, Point as SPt, LineString as SLine
from shapely.prepared import prep
assert O.get("version", 1) >= 2, "an outdoor_nav.json older than version 2"
BL = shapely.unary_union([SPoly(p["outer"], p["holes"]) for p in O["blocked"]]); BLp = prep(BL); BLb = BL.boundary
V, T = O["verts"], O["tris"]
cols = collections.defaultdict(list)
for t in T:
    P = [V[v] for v in t[:3]]
    for gx in range(int(min(p[0] for p in P) // 256), int(max(p[0] for p in P) // 256) + 1):
        for gy in range(int(min(p[1] for p in P) // 256), int(max(p[1] for p in P) // 256) + 1): cols[(gx, gy)].append(P)
def bary(P, q):
    a, b, c = P; d = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if abs(d) < 1e-9: return None
    l1 = ((b[0] - q[0]) * (c[1] - q[1]) - (b[1] - q[1]) * (c[0] - q[0])) / d; l2 = ((c[0] - q[0]) * (a[1] - q[1]) - (c[1] - q[1]) * (a[0] - q[0])) / d
    return l1, l2, 1 - l1 - l2
def blocked(p): return BLp.contains(SPt(p[0], p[1]))
M = {m["id"]: m for c in D["cells"] for m in c["navmeshes"]}
cr = lambda o, p, q: (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
K3 = lambda p: (round(p[0], 3), round(p[1], 3), round(p[2], 3))

def tri_verts(mid, ti): return [tuple(M[mid]["verts"][v]) for v in M[mid]["tris"][ti][:3]]
def gneigh(mid, ti, k):
    t = M[mid]["tris"][ti]; nb = t[3 + k]
    if nb in (-1, 65535): return None
    if t[6] & (1 << k):
        L = M[mid]["links"][nb]; return (L[1], L[2]) if isinstance(L, list) and L[1] in M else None
    return (mid, nb)

# ---- 1. classify: clear of the outline kept; inside it cut; across it carved (a portal edge it crosses: whole, by its middle)
def crosses(a, b):
    g = SLine([a[:2], b[:2]]).intersection(BLb)
    if g.is_empty: return False
    L = math.dist(a[:2], b[:2])
    pts = [g] if g.geom_type == "Point" else [q for q in getattr(g, "geoms", []) if q.geom_type == "Point"]
    return any(0.5 < math.dist(a[:2], (q.x, q.y)) < L - 0.5 for q in pts) or any(q.geom_type != "Point" for q in getattr(g, "geoms", [g]))
cut, touched = set(), set(); portal_whole = 0
for mid, m in M.items():
    for ti, t in enumerate(m["tris"]):
        if t[6] & 8: continue
        P = tri_verts(mid, ti)
        if max(math.hypot(p[0] - SX, p[1] - SY) for p in P) > 4000: continue
        tp = SPoly([p[:2] for p in P]); at = tp.area
        if at < 1e-6: continue
        ab = tp.intersection(BL).area
        if ab < max(1.0, at * 0.005): continue
        if ab > at - max(1.0, at * 0.005): cut.add((mid, ti)); continue
        if any(t[6] & (1 << k) and crosses(P[k], P[(k + 1) % 3]) for k in range(3)):
            portal_whole += 1
            if blocked(tuple(sum(p[c] for p in P) / 3 for c in range(3))): cut.add((mid, ti))
            continue
        touched.add((mid, ti))
print("portal-edged triangles taken whole:", portal_whole)
# ---- 2. edge splits where the outline crosses an edge, deterministic from the edge (sorted ends); the triangle across joins the re-cut set
def edge_points(a, b):
    A_, B_ = sorted([a, b])
    L = math.hypot(B_[0] - A_[0], B_[1] - A_[1])
    if L < 1e-6: return []
    g = SLine([A_[:2], B_[:2]]).intersection(BLb)
    us = sorted({math.dist(A_[:2], (q.x, q.y)) / L for q in ([g] if g.geom_type == "Point" else [q for q in getattr(g, "geoms", []) if q.geom_type == "Point"])})
    out = []
    for u in us:
        if u * L <= 0.5 or (1 - u) * L <= 0.5: continue
        if out and (u - out[-1][3]) * L <= 0.5: continue
        out.append((A_[0] + (B_[0] - A_[0]) * u, A_[1] + (B_[1] - A_[1]) * u, A_[2] + (B_[2] - A_[2]) * u, u))
    return [q[:3] for q in out]
retri = set(touched); split = {}
for key in touched:
    P = tri_verts(*key)
    for k in range(3):
        a, b = P[k], P[(k + 1) % 3]
        ek = (K3(min(a, b)), K3(max(a, b)))
        portal = bool(M[key[0]]["tris"][key[1]][6] & (1 << k))
        if ek not in split: split[ek] = [] if portal else edge_points(a, b)
        n = gneigh(*key, k)
        if n and n not in cut and not M[n[0]]["tris"][n[1]][6] & 8 and split[ek]: retri.add(n)

# ---- 3. re-triangulate
parts = {}   # key -> (X, kept triples, boundary segments: list of (point a, point b, original edge k))
stats = collections.Counter()
for key in retri:
    P = tri_verts(*key)
    if cr(P[0], P[1], P[2]) < 0: print("clockwise ground triangle", key)
    boundary = []
    for k in range(3):
        a, b = P[k], P[(k + 1) % 3]
        ek = (K3(min(a, b)), K3(max(a, b)))
        pts = split.get(ek, [])
        if K3(a) > K3(b): pts = list(reversed(pts))
        boundary += [a] + pts
    # the part outside the outline; the boundary's own points put back on its rings (shared with the triangles across), triangulated
    X = list(boundary); keep = []
    sg = 1 if cr(P[0], P[1], P[2]) >= 0 else -1
    def pid(q):
        for i_, x in enumerate(X):
            if abs(x[0] - q[0]) < 0.05 and abs(x[1] - q[1]) < 0.05: return i_
        b_ = bary(P, q); X.append((q[0], q[1], b_[0] * P[0][2] + b_[1] * P[1][2] + b_[2] * P[2][2])); return len(X) - 1
    def with_points(ring):
        out = []
        for a, b in zip(ring, ring[1:] + ring[:1]):
            out.append(a); L = math.dist(a, b)
            if L < 1e-9: continue
            on = []
            for x in X[:len(boundary)]:
                u = ((x[0] - a[0]) * (b[0] - a[0]) + (x[1] - a[1]) * (b[1] - a[1])) / L / L
                if 1e-6 < u < 1 - 1e-6 and abs(cr(a, b, x)) / L < 0.05: on.append((u, (x[0], x[1])))
            out += [q for _, q in sorted(on)]
        return out
    rest = SPoly([p[:2] for p in boundary]).difference(BL)
    for g in getattr(rest, "geoms", [rest]):
        if g.geom_type != "Polygon" or g.area < 0.5: continue
        g2 = SPoly(with_points(list(g.exterior.coords)[:-1]), [with_points(list(h.coords)[:-1]) for h in g.interiors])
        for tr_ in shapely.constrained_delaunay_triangles(g2).geoms:
            q3 = [pid(c) for c in list(tr_.exterior.coords)[:3]]
            Q = [X[k_] for k_ in q3]
            if len(set(q3)) < 3 or abs(cr(*Q)) < 0.5: stats["degenerate"] += 1; continue
            if cr(*Q) * sg < 0: q3 = [q3[0], q3[2], q3[1]]
            keep.append(q3)
    parts[key] = (X, keep, len(boundary))
    stats["parts"] += len(keep)
print(f"ground: cut {len(cut)}, carved {len(touched)}, re-cut beside them {len(retri) - len(touched)}; parts {stats['parts']} kept, {stats['degenerate']} degenerate")

# ---- 4. the graph
adj = collections.defaultdict(set)
def segs_of(key):
    """boundary segments of a (re-triangulated or whole) ground triangle: (a, b, node)"""
    if key in parts:
        X, keep, nb = parts[key]
        out = []
        for j, t3 in enumerate(keep):
            for c in range(3):
                u, v = t3[c], t3[(c + 1) % 3]
                if u < nb and v < nb and ((v - u) % nb == 1): out.append((X[u], X[v], key + (j,)))
        return out
    P = tri_verts(*key); return [(P[k], P[(k + 1) % 3], key) for k in range(3)]
def holder_of(key, k):
    """the node holding original edge k of a ground triangle whole (None: dropped)"""
    if key in cut or M[key[0]]["tris"][key[1]][6] & 8: return None
    if key not in parts: return key
    X, keep, nb = parts[key]
    P = tri_verts(*key); a, b = K3(P[k]), K3(P[(k + 1) % 3])
    for j, t3 in enumerate(keep):
        for c in range(3):
            if K3(X[t3[c]]) == a and K3(X[t3[(c + 1) % 3]]) == b: return key + (j,)
    return None
opens = []
for mid, m in M.items():
    for ti, t in enumerate(m["tris"]):
        key = (mid, ti)
        if t[6] & 8 or key in cut: continue
        if key in parts:   # inside
            X, keep, nb = parts[key]
            emap = {}
            for j, t3 in enumerate(keep):
                for c in range(3): emap[(t3[c], t3[(c + 1) % 3])] = j
            for (u, v), j in emap.items():
                if (v, u) in emap: adj[key + (j,)].add(key + (emap[(v, u)],))
                elif not (u < nb and v < nb and (v - u) % nb == 1): opens.append((key + (j,), X[u], X[v]))
        # across its original edges: segment by segment
        P = tri_verts(mid, ti)
        mine = segs_of(key)
        for k in range(3):
            a, b = P[k], P[(k + 1) % 3]
            n = gneigh(mid, ti, k)
            on_edge = [s for s in mine if abs(cr(a, b, s[0])) < 1e-3 * max(1, math.hypot(b[0] - a[0], b[1] - a[1])) and abs(cr(a, b, s[1])) < 1e-3 * max(1, math.hypot(b[0] - a[0], b[1] - a[1]))]
            live = n and n not in cut and not M[n[0]]["tris"][n[1]][6] & 8
            whole = not split.get((K3(min(a, b)), K3(max(a, b))))
            if whole:
                me = holder_of(key, k)
                if me is None: continue
                back = next((k2 for k2 in range(3) if gneigh(n[0], n[1], k2) == key), None) if live else None
                them = holder_of(n, back) if back is not None else None
                if them is not None: adj[me].add(them)
                else: opens.append((me, a, b))
                continue
            theirs = {} if not live else {(K3(s[1]), K3(s[0])): s[2] for s in segs_of(n)}
            for s in on_edge:
                o = theirs.get((K3(s[0]), K3(s[1])))
                if o is not None: adj[s[2]].add(o)
                else: opens.append((s[2], s[0], s[1]))
        if key not in parts:
            pass
for i, t in enumerate(T):
    for e in range(3):
        if t[3 + e] >= 0: adj[("o", i)].add(("o", t[3 + e]))
def segd(p, a, b):
    L = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2
    u = 0 if L < 1e-9 else max(0, min(1, ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / L))
    q = [a[k] + u * (b[k] - a[k]) for k in range(3)]; return math.hypot(p[0] - q[0], p[1] - q[1]), p[2] - q[2]
joins = collections.Counter(); backs = collections.Counter(); taken = {}
for i, t in enumerate(T):
    for e in range(3):
        if t[3 + e] >= 0: continue
        a, b = V[t[e]], V[t[(e + 1) % 3]]; mp = [(a[k] + b[k]) / 2 for k in range(3)]
        f = next((fi for fi, F in enumerate(O["feet"]) if math.hypot(mp[0] - F[0], mp[1] - F[1]) <= F[3]), None)
        if f is None: continue
        best = None
        for node, ga, gb in opens:
            d, dz = segd(mp, ga, gb)
            if d < 48 and abs(dz) < 60 and (best is None or d < best[0]): best = (d, node, K3(ga), K3(gb))
        if best:
            adj[("o", i)].add(best[1]); joins[f] += 1
            if best[1:] not in taken or best[0] < taken[best[1:]][0]: taken[best[1:]] = (best[0], i, f)
for k_, (d, i, f) in taken.items(): adj[k_[0]].add(("o", i)); backs[f] += 1
print("joins per foot", dict(joins), "backs per foot", dict(backs))
def centre(n):
    if n[0] == "o": P = [V[v] for v in T[n[1]][:3]]
    elif len(n) == 3: X, keep, _ = parts[(n[0], n[1])]; P = [X[k] for k in keep[n[2]]]
    else: P = tri_verts(*n)
    return [sum(p[q] for p in P) / 3 for q in range(3)]
nodes = {n for n in adj} | {x for s in adj.values() for x in s}
ground_nodes = [n for n in nodes if n[0] != "o"]
FAILS = []
nb_ = sum(1 for n in ground_nodes if blocked(centre(n)))
print("kept ground pieces with a blocked centre:", nb_)
if nb_: FAILS.append(f"{nb_} kept ground pieces under the hall")
def comp(src):
    seen = set(src); q = list(src)
    for x in q:
        for y in adj.get(x, ()):
            if y not in seen: seen.add(y); q.append(y)
    return seen
# (O["cross"], the site file's nav_cross: true where the ground runs round the hall, so every foot reaches every door outside, as
# at Riverwood; false where the hall stands across the only ground between its back and front, as at site B: each door is then
# joined both ways to a foot of its own side, and each foot to a door)
CROSS = O.get("cross", True); joined = set()
for d, an in enumerate(O["anchors"]):
    door = {("o", i) for i in range(len(T)) if (c := centre(("o", i))) and math.hypot(c[0] - an[0], c[1] - an[1]) <= 60 and abs(c[2] - an[2]) < 120}
    out_ = comp(door)
    for f, F in enumerate(O["feet"]):
        ring = {n for n in ground_nodes if (c := centre(n)) and F[3] + 50 <= math.hypot(c[0] - F[0], c[1] - F[1]) <= F[3] + 400 and abs(c[2] - F[2]) < 150}
        ok_ = bool(comp(ring) & door and out_ & ring)
        print(f"door {d} ({'rear' if an[2] > SZ + 200 else 'front'}) <- foot {f}: {bool(comp(ring) & door)}, -> {bool(out_ & ring)}   (ring {len(ring)})")
        if ok_: joined.add((d, f))
        elif CROSS: FAILS.append(f"door {d} and foot {f} not joined both ways")
if not CROSS:
    for d in range(len(O["anchors"])):
        if not any(d_ == d for d_, _ in joined): FAILS.append(f"door {d} joined both ways to no foot")
    for f in range(len(O["feet"])):
        if not any(f_ == f for _, f_ in joined): FAILS.append(f"foot {f} joined both ways to no door")
    print(f"(nav_cross false: each door joined to a foot of its own, each foot to a door: {sorted(joined)})")
json.dump(dict(parts={f"{k[0]}:{k[1]}": [v[0], v[1], v[2]] for k, v in parts.items()}, cut=[list(c) for c in cut], touched=[list(t) for t in touched]), open(OUT, "w"))
if "--debug" in sys.argv:
    bad = collections.Counter(); ex = []
    for key in retri:
        P = tri_verts(*key); mine = segs_of(key)
        for k in range(3):
            n = gneigh(*key, k)
            if not n or n in cut or M[n[0]]["tris"][n[1]][6] & 8: continue
            a, b = P[k], P[(k + 1) % 3]
            on = [s for s in mine if abs(cr(a, b, s[0])) < 1e-3 * max(1, math.hypot(b[0] - a[0], b[1] - a[1])) and abs(cr(a, b, s[1])) < 1e-3 * max(1, math.hypot(b[0] - a[0], b[1] - a[1]))]
            theirs = {(K3(s[1]), K3(s[0])) for s in segs_of(n)}
            miss = [s for s in on if (K3(s[0]), K3(s[1])) not in theirs]
            portal = bool(M[key[0]]["tris"][key[1]][6] & (1 << k))
            if miss:
                bad[("portal" if portal else "same mesh", "neighbour re-triangulated" if n in parts else "neighbour whole", "edge split" if split.get((K3(min(a, b)), K3(max(a, b)))) else "edge whole")] += 1
                if len(ex) < 4: ex.append((key, k, n, [K3(a), K3(b)], tri_verts(*n), len(on), len(miss)))
    print("unmatched original edges:", dict(bad))
    for e in ex: print("  ", e)
if "--bad" in sys.argv:
    for n in ground_nodes:
        c = centre(n)
        if blocked(c):
            area = None
            if len(n) == 3: X, keep, _ = parts[(n[0], n[1])]; Q = [X[k] for k in keep[n[2]]]; area = abs(cr(Q[0], Q[1], Q[2])) / 2
            else: Q = tri_verts(*n); area = abs(cr(Q[0], Q[1], Q[2])) / 2
            print(n, "in parts" if (n[0], n[1]) in parts else "whole", "touched" if (n[0], n[1]) in touched else "", "centre", [round(x) for x in c], "area", round(area))
if FAILS: sys.exit("OUTDOOR REPLAY FAILED: " + "; ".join(FAILS))
print("OUTDOOR REPLAY OK")
