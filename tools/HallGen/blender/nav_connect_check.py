"""Is each cell's navmesh one piece? (2026-11-11, the navmesh rebuild: the landing at the foot of the basement stair, where the door down
stands, had been a piece of its own since the stair became a ramp, cut off from the stair: no one could walk to that door. nav_routes.py
passed it, because it routes from every load door's landing, and that landing was one.) The triangles joined through their shared edges,
twice: every edge, and only edges at least WIDE long (an edge narrower than an actor is a way the hand-made meshes never rely on: 553
vanilla interiors and 913 of 37 mods', navsurvey, stay 99% one piece at 40). Every piece but the largest must be one a load door lands on
and named with --allow (a loft reached only by its ladder), or one that holds no one's spot (no marker, no bed: nav_routes.py's places,
each held by the triangle it stands on or else the nearest at its floor) and is smaller than ROOM (a corner nook behind a narrow gap; named, not failed: no route needs it).
At WIDE a sliver under SCRAP with no landing passes even holding a spot: it is a piece only because its own edges are short, and the
first pass (every edge) has already judged whether it is joined.
    python nav_connect_check.py <nav_*.json> <hall2_*.json> [--allow <load door name> ...]
exit 1 on any other piece, and when it read no triangles or no spots"""
import sys, json, math
from collections import defaultdict

WIDE, SCRAP, ROOM = 40.0, 2000.0, 10000.0   # (floor areas: SCRAP about 45 x 45, a sliver not named; ROOM 100 x 100)
a = sys.argv[1:]
allow = set()
if "--allow" in a:
    i = a.index("--allow"); allow = set(a[i + 1:]); a = a[:i]
nav = json.load(open(a[0])); V = nav.get("verts", []); T = [t["v"] for t in nav.get("tris", [])]
src = json.load(open(a[1]))
H = lambda p: (p[1], -p[0], p[2])                                   # (the export's frame to the navmesh's, as nav_routes.py)
spots = [(n, H(pos)) for n, ed, pos, *_ in src.get("markers", []) if n and n.startswith("AGHall") and not any(k_ in n for k_ in ("Rotator", "Target"))]
spots += [(p.get("name") or p.get("ed"), H(p["pos"])) for p in src.get("pieces", [])
          if "bed" in (p.get("ed") or "").lower() and not any(k_ in (p.get("ed") or "").lower() for k_ in ("bedroll", "bedside"))]
name = a[0].replace("\\", "/").split("/")[-1]
if not T or not spots: print(f"FAIL CONNECT {name}: read {len(T)} triangles and {len(spots)} spots"); sys.exit(1)
def holder(q):
    """the triangle a spot stands on (within 60 of its floor), else the nearest one at its floor by centroid"""
    best = None
    for j, t in enumerate(T):
        A, B, C = (V[v] for v in t)
        if abs((A[2] + B[2] + C[2]) / 3 - q[2]) > 60: continue
        d = (B[0] - A[0]) * (C[1] - A[1]) - (B[1] - A[1]) * (C[0] - A[0])
        if abs(d) > 1e-9:
            l1 = ((B[0] - q[0]) * (C[1] - q[1]) - (B[1] - q[1]) * (C[0] - q[0])) / d; l2 = ((C[0] - q[0]) * (A[1] - q[1]) - (C[1] - q[1]) * (A[0] - q[0])) / d
            if min(l1, l2, 1 - l1 - l2) >= -1e-6: return j
        dd = math.dist([(A[k] + B[k] + C[k]) / 3 for k in range(2)], q[:2])
        if best is None or dd < best[0]: best = (dd, j)
    return best[1] if best else None
area = [abs((V[b_][0] - V[a_][0]) * (V[c][1] - V[a_][1]) - (V[b_][1] - V[a_][1]) * (V[c][0] - V[a_][0])) / 2 for a_, b_, c in T]
held_by = defaultdict(list)
for n, q in spots:
    h = holder(q)
    if h is not None: held_by[h].append(n)
em = defaultdict(list)
for j, t in enumerate(T):
    for k in range(3): em[(min(t[k], t[(k + 1) % 3]), max(t[k], t[(k + 1) % 3]))].append(j)
landing = defaultdict(list)                                         # triangle -> the load doors that land on it
for d in nav.get("doors", []):
    if d.get("tri") is not None: landing[d["tri"]].append(d["name"])
unknown = allow - {n for ns in landing.values() for n in ns}
bad = 0
for n in sorted(unknown): print(f"FAIL CONNECT {name}: --allow {n}: no load door of that name lands on this navmesh"); bad += 1
for wide in (0.0, WIDE):
    par = list(range(len(T)))
    def f(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    for (p, q), ts in em.items():
        if len(ts) == 2 and math.dist(V[p][:2], V[q][:2]) >= wide: par[f(ts[0])] = f(ts[1])
    pieces = defaultdict(list)
    for j in range(len(T)): pieces[f(j)].append(j)
    tot = sum(area); order = sorted(pieces.values(), key=lambda js: -sum(area[j] for j in js))
    print(f"{name}, edges {'all' if not wide else f'>= {wide:.0f}'}: {len(order)} pieces, the largest {100 * sum(area[j] for j in order[0]) / tot:.1f}% of {tot:.0f}")
    for js in order[1:]:
        ar = sum(area[j] for j in js); doors = sorted({n for j in js for n in landing.get(j, [])})
        cen = [round(sum(V[v][k] for j in js for v in T[j]) / (3 * len(js))) for k in range(3)]
        if doors and set(doors) <= allow: print(f"  piece of {len(js)} triangles, {ar:.0f} at {cen}: {', '.join(doors)} (allowed)"); continue
        held = sorted({n for j in js for n in held_by.get(j, [])})
        if wide and ar < SCRAP and not doors: continue      # (a sliver joined at every edge: on the way, not a way of its own; the pass above judged it)
        if not doors and not held:
            if ar >= ROOM: pass
            elif ar < SCRAP: continue
            else: print(f"  piece of {len(js)} triangles, {ar:.0f} at {cen}: no one's spot, under {ROOM:.0f} (named, not failed)"); continue
        if held: doors = doors + [f"spots {', '.join(held[:6])}"]
        print(f"  FAIL CONNECT piece of {len(js)} triangles, {ar:.0f} at {cen}{': landing of ' + ', '.join(doors) if doors else ''}: cut off from the rest"); bad += 1
print(f"CONNECT {name}: {len(spots)} spots, {bad} failures"); sys.exit(1 if bad else 0)
