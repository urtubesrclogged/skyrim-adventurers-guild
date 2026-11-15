"""Can an actor walk the hall's navmesh to where its people go? (a valid navmesh can still break path-finding:
Elise struggled to get behind the counter, round through the back office and on to the stairs, and Willem was
blocked by his bedroom door; the game warps an actor after three path failures, and keeps an actor's radius off the mesh's edge itself.)
The mesh rasterised every G by triangle, stairs and floors apart; each column's clearance to the mesh's edge; from the load doors' landings the
widest way to every marker, bed and load door: the narrowest width on it, and where. Twice: doors shut, then each inner door's leaf open and cut
out of the mesh as the engine cuts it (bCutDoors): a leaf that shuts a way a person needs is found here.
    python nav_routes.py <nav_*.json> <hall2_*.json> [--min 40]     exit 1 on a way under --min, or none
A width is the mesh's, by columns, not the gap's: the gap is 16 more (the mesh stops 8 from what blocks it). 36 holds an actor 28 thick (GetLength; GetWidth 44
is across the arms), a radius of 14 kept from each edge with 8 to spare."""
import sys, json, math, heapq, os
from collections import defaultdict, deque
a = sys.argv[1:]; MINW = 36.0
if "--min" in a: i = a.index("--min"); MINW = float(a[i + 1]); del a[i:i + 2]
# (2026-11-03) --no-beds: a cell with no bed (the strongroom) is checked for its ways alone; elsewhere a cell that reads no bed fails
NO_BEDS = "--no-beds" in a; a = [x for x in a if x != "--no-beds"]
nav, src = json.load(open(a[0])), json.load(open(a[1])); G = 6.0
H = lambda p: (p[1], -p[0], p[2])
V = [H(p) for p in nav["verts"]]; T = nav["tris"]
node_z = {}; node_tri = defaultdict(list)                 # (i, j, tri) -> z
for t_i, t in enumerate(T):
    A, B, C = (V[v] for v in t["v"])
    d = (B[1] - C[1]) * (A[0] - C[0]) + (C[0] - B[0]) * (A[1] - C[1])
    if abs(d) < 1e-9: continue
    for i in range(int(min(A[0], B[0], C[0]) // G), int(max(A[0], B[0], C[0]) // G) + 1):
        for j in range(int(min(A[1], B[1], C[1]) // G), int(max(A[1], B[1], C[1]) // G) + 1):
            x, y = (i + 0.5) * G, (j + 0.5) * G
            l1 = ((B[1] - C[1]) * (x - C[0]) + (C[0] - B[0]) * (y - C[1])) / d; l2 = ((C[1] - A[1]) * (x - C[0]) + (A[0] - C[0]) * (y - C[1])) / d; l3 = 1 - l1 - l2
            if min(l1, l2, l3) < -1e-6: continue
            z = l1 * A[2] + l2 * B[2] + l3 * C[2]
            node_tri[(i, j)].append((z, t_i))
# a column's surfaces: one node a height (triangles sharing a column at one height are one surface)
cols = defaultdict(list)
for k, zs in node_tri.items():
    for z, t_i in sorted(zs):
        if cols[k] and abs(cols[k][-1][0] - z) < 12: cols[k][-1][1].add(t_i)
        else: cols[k].append([z, {t_i}])
nodes = {(i, j, n): c[0] for (i, j), l in cols.items() for n, c in enumerate(l)}
tris_of = {(i, j, n): c[1] for (i, j), l in cols.items() for n, c in enumerate(l)}
near = []                                                 # (a triangle too thin to hold a column's centre is skipped by the raster: three hops)
for t_i, t in enumerate(T):
    seen = {t_i}; front = {t_i}
    for _ in range(3):
        front = {l for f in front for l in T[f]["links"] if l >= 0} - seen; seen |= front
    near.append(seen)
def linked(p, q):
    tp, tq = tris_of[p], tris_of[q]
    return any(near[t_] & tq for t_ in tp)
NB = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414))
adj = {}
for p in nodes:
    i, j, _ = p; adj[p] = []
    for di, dj, w in NB:
        for n, c in enumerate(cols.get((i + di, j + dj), ())):
            q = (i + di, j + dj, n)
            if abs(c[0] - nodes[p]) < 24 and linked(p, q): adj[p].append((q, w))
def clearance(dead):
    d = {}; hq = []
    for p in nodes:
        if p in dead: continue
        if len([q for q, w in adj[p] if q not in dead and w == 1.0]) < 4: d[p] = 0.0; hq.append((0.0, p))
    heapq.heapify(hq)
    while hq:
        g, p = heapq.heappop(hq)
        if g > d.get(p, 1e9): continue
        for q, w in adj[p]:
            if q in dead: continue
            g2 = g + w * G
            if g2 < d.get(q, 1e9): d[q] = g2; heapq.heappush(hq, (g2, q))
    return d
def snap(x, y, z, reach=150):
    best = None
    for p, zp in nodes.items():
        d_ = math.hypot((p[0] + .5) * G - x, (p[1] + .5) * G - y)
        if d_ < reach and abs(zp - z) < 45 and (best is None or d_ < best[0]): best = (d_, p)
    return best[1] if best else None
free = set()
def pinch(s, w, clr):
    """the true narrow place: what the wider ways from the landings and from the place both meet (a widest way wanders, so its own lowest column may not be it)"""
    def flood(seeds):
        got = set(seeds); st = list(seeds)
        while st:
            for q, _ in adj[st.pop()]:
                if q in clr and q not in got and (clr[q] > w or q in free): got.add(q); st.append(q)
        return got
    a_ = flood([x for x in starts if x in clr]); b_ = flood([s])
    best = None
    for p in clr:
        if clr[p] <= w and p not in free:
            n_ = [q for q, _ in adj[p]]
            if any(q in a_ for q in n_) and any(q in b_ for q in n_): best = (clr[p], p); break
    return best or (w, s)
def widest(starts, clr):
    best = {}; hq = []
    for s in starts:
        if s in clr: best[s] = 1e9; hq.append((-1e9, s))   # (a landing and what it reaches stand by a wall: only the way between them counts)
    heapq.heapify(hq); prev = {}
    while hq:
        w, p = heapq.heappop(hq); w = -w
        if w < best.get(p, 0): continue
        for q, _ in adj[p]:
            if q not in clr: continue
            w2 = min(w, clr[q] if q not in free else 1e9)
            if w2 > best.get(q, -1): best[q] = w2; prev[q] = p; heapq.heappush(hq, (-w2, q))
    return best, prev
targets = []
for n, ed, pos, *_ in src.get("markers", []):
    if n.startswith("AGHall") and not any(k_ in n for k_ in ("Rotator", "Target")): targets.append((n, H(pos)))   # (a Target is aimed at, not walked to)
for p in src["pieces"]:
    e = (p.get("ed") or "").lower()
    if "bed" in e and "bedroll" not in e and "bedside" not in e: targets.append((p.get("name") or p.get("ed"), H(p["pos"])))
starts = []
for p in src["pieces"]:
    if p.get("arrive"):
        q = H(p["arrive"]); s = snap(*q, reach=96)
        targets.append((p.get("name") or p.get("role") or "door", q))
        if s: starts.append(s)
print(f"ROUTES {a[0].replace(chr(92), '/').split('/')[-1]}: {len(T)} triangles, {len(nodes)} columns, {len(starts)} landings, {len(targets)} places")
# doors: hinged at the origin, 96 along local +x, swinging to local -y (furniture_check's reckoning)
def leaf_nodes(p):
    x, y, z = H(p["pos"]); yaw = math.radians(p["yaw"] + 90); ex, ey = (math.cos(yaw), -math.sin(yaw)), (math.sin(yaw), math.cos(yaw)); out = set()
    for t in range(0, 97, 3):
        for w in (-6, 0, 6):
            lx, ly = w, (t if p.get("ed", "").endswith("R") else -t); wx, wy = x + lx * ex[0] + ly * ey[0], y + lx * ex[1] + ly * ey[1]
            i, j = int(wx // G), int(wy // G)
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    for n, c in enumerate(cols.get((i + di, j + dj), ())):
                        if abs(c[0] - z) < 40: out.add((i + di, j + dj, n))
    return out
doors = [p for p in src["pieces"] if (p.get("ed") or "") in ("SSingleDoorInt01L", "SSingleDoorInt01R")]
def bed_sides(best):
    """(Ghrulek could not get round his trunk and the chimney stack to his bed: a bed counted as reached anywhere within 120 of it, and the single beds' sleep markers enter
    from the long sides only, so a mesh that passed his foot end passed him) a bed needs one long side a person can stand at: the widest way to a column within 48 of it, along its length"""
    mi = json.load(open(os.path.join(os.path.dirname(a[1]) or ".", "mesh_info.json"))); fails = 0; n_ = 0; rows_ = []
    for p in src["pieces"]:
        e = (p.get("ed") or "").lower()
        if "bed" not in e or "bedroll" in e or "bedside" in e: continue
        m = mi.get(p["model"].lower())
        if not m or "box" not in m: print(f"FAIL BEDSIDE {p.get('name') or e}: its mesh is unmeasured"); fails += 1; continue
        (x0, y0, _), (x1, y1, _) = m["box"]; sc = p.get("scale", 1.0); x, y, z = H(p["pos"]); yaw = math.radians(p["yaw"] + 90)
        ex, ey = (math.cos(yaw), -math.sin(yaw)), (math.sin(yaw), math.cos(yaw)); n_ += 1
        if x1 - x0 < y1 - y0: la, lb, sa, sb, al, ac = y0 * sc, y1 * sc, x0 * sc, x1 * sc, ey, ex      # (long along local y: its sides at x0, x1)
        else: la, lb, sa, sb, al, ac = x0 * sc, x1 * sc, y0 * sc, y1 * sc, ex, ey
        w_ = 0.0
        for q, zq in nodes.items():
            if abs(zq - z) > 30 or q not in best: continue
            dx, dy = (q[0] + .5) * G - x, (q[1] + .5) * G - y
            u, v = dx * al[0] + dy * al[1], dx * ac[0] + dy * ac[1]
            if la + 6 <= u <= lb - 6 and (sb < v <= sb + 48 or sa - 48 <= v < sa): w_ = max(w_, 2 * min(best[q], 1e4) + 2 * G)
        rows_.append((w_, p.get("name") or e))
        if w_ < MINW: print(f"FAIL BEDSIDE {p.get('name') or e} at ({x:.0f}, {y:.0f}, {z:.0f}): widest way to a long side {w_:.0f}, under {MINW:.0f}"); fails += 1
    rows_.sort(); print(f"BEDSIDES {n_} beds, {fails} with no long side to stand at; narrowest: " + "; ".join(f"{n} {min(w, 999):.0f}" for w, n in rows_[:5]))
    if not n_ and not NO_BEDS: print("FAIL BEDSIDE read no bed"); fails = 1
    return fails
def run(tag, dead):
    clr = clearance(dead); free.clear()
    for s0 in starts:
        free.update(p for p in nodes if abs(nodes[p] - nodes[s0]) < 30 and math.hypot(p[0] - s0[0], p[1] - s0[1]) * G <= 66)
    best, prev = widest(starts, clr); bad = 0; rows = []
    if tag == "doors shut" and "basement" not in a[1]: bad += bed_sides(best)
    for n, q in targets:
        s = snap(*q)
        while s is not None and s in dead: s = None
        if s is None: rows.append((-1, n, "no mesh near it", q)); bad += 1; continue
        around = [p for p in nodes if p in best and abs(nodes[p] - nodes[s]) < 30 and math.hypot(p[0] - s[0], p[1] - s[1]) * G <= (120 if "bed" in n.lower() or "bunk" in n.lower() else 66)]
        if not around: rows.append((0, n, "no way to it", q)); bad += 1; continue
        s = max(around, key=lambda p: best[p]); w = best[s]      # (the last steps to a bed or a marker hug what it stands by)
        m = pinch(s, w, clr)
        rows.append((2 * w + 2 * G, n, f"narrowest at ({(m[1][0] + .5) * G:.0f}, {(m[1][1] + .5) * G:.0f}, {nodes[m[1]]:.0f})", q))
        bad += 2 * w + 2 * G < MINW
    rows.sort(key=lambda r: r[0])
    print(f"  {tag}: {bad} under {MINW:.0f}; narrowest: " + "; ".join(f"{r[1]} {min(r[0], 999):.0f} {r[2]}" for r in rows[:int(__import__("os").environ.get("ROWS", 5))]))
    return bad
bad = run("doors shut", set())
if "--doors" in a:
    for p in doors:
        nm = p.get("name") or "door"; rest = run(f"{nm} open", leaf_nodes(p)); bad += rest
print("ROUTES", "FAIL" if bad else "ok", bad); sys.exit(1 if bad else 0)
