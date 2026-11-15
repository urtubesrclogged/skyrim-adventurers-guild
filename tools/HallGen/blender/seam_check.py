"""Seam gate (on the MGO install the baseboards did not line up anywhere in the guild hall, and
bright seams ran down the plaster beside the posts). Two checks on an exported part (guildhall_gen.py AG_EXPORT JSON):
  STRIP     an upright strip of plaster or stone under 1.5 wide left showing beside a timber that stands in front of the
            rest of that face: until this day every post stood 0.5 short of its place (1 narrower than its slot), and the
            strip of plaster by each doorpost and corner showed as a bright line in game. One line per place.
  BASEBOARD the upper floors' baseboards (interior_gen.py baseboards(), its log baseboards_<variant>.json beside the part):
            an end left open in the room (it should meet a board, a wall's board, a post or an opening), a mitre with no
            board on its other side, or a piece under 12 kept on its own.
A strip is looked for along every upright edge of a plaster or stone face, every 6: just inside the edge the face must be
seen from the room (nothing in front of it for 40), and 1.5 and 2.5 in it must be covered (a face in front within 15).
    blender -b -P seam_check.py -- <part.json> [<baseboards.json>]        FAIL lines; the last line counts them
Prints hall-frame positions (x across the front, y negative in front, z from the floor)."""
import sys, json, math, collections
from mathutils import Vector
from mathutils.bvhtree import BVHTree
args = sys.argv[sys.argv.index("--") + 1:]
KEYS = ("stucco", "stone")
d = json.load(open(args[0]))
name = args[0].replace("\\", "/").split("/")[-1]
V, P, K = [], [], []
for key, sh in d["shapes"].items():
    o = len(V); V += [Vector(v) for v in sh["v"]]
    for f in sh["f"]:
        if len(f) >= 3: P.append([o + i for i in f]); K.append(key.split("@")[0])
if not P: print(f"FAIL GATE seam_check {name}: no faces read"); sys.exit(1)
bvh = BVHTree.FromPolygons(V, P, epsilon=0.0)
H = lambda p: (round(p[1], 1), round(-p[0], 1), round(p[2], 1))    # layout -> hall frame (as leak_check prints)
def hit(p, n, far):
    return bvh.ray_cast(p + n * 0.02, n, far)
fails = []
strips = collections.defaultdict(list)
edges = 0
for pi, poly in enumerate(P):
    if K[pi] not in KEYS: continue
    pts = [V[i] for i in poly]
    n = Vector((0, 0, 0))
    for i in range(len(pts)): n += pts[i - 1].cross(pts[i])
    if n.length < 1e-6 or abs(n.normalized().z) > 0.2: continue       # walls only
    n.normalize(); c = sum(pts, Vector()) / len(pts)
    for k in range(len(pts)):
        a, b = pts[k - 1], pts[k]; e = b - a; L = e.length
        if L < 12 or abs(e.z) / L < 0.95: continue                     # upright edges
        edges += 1
        e /= L; t = n.cross(e)
        if t.dot(c - a) < 0: t = -t                                    # into the face
        for s in range(max(1, int(L / 6))):
            p = a + e * (L * (s + 0.5) / max(1, int(L / 6)))
            if hit(p + t * 0.25, n, 40)[0] is not None: continue       # the strip by the edge is seen from the room
            covers = [hit(p + t * w, n, 16) for w in (1.5, 2.5)]
            if all(h[0] is not None and h[3] < 15 for h in covers):
                w_ = next(w * 0.25 for w in range(2, 7) if (lambda h: h[0] is not None and h[3] < 15)(hit(p + t * w * 0.25, n, 16)))
                strips[(K[pi], K[covers[0][2]], H(a)[:2], H(n))].append((H(p)[2], w_))
for (k_, cover_, at_, nn_), zs in sorted(strips.items()):
    if len(zs) < 3: continue                                           # (a corner's point, not a strip)
    z_ = [z for z, w in zs]
    fails.append(f"FAIL STRIP {name}: {k_} at {at_} z {round(min(z_))}..{round(max(z_))} facing {nn_}, "
                 f"{min(w for z, w in zs)}..{max(w for z, w in zs)} wide beside {cover_}")
if len(args) > 1:
    B = json.load(open(args[1]))
    if not B: fails.append(f"FAIL GATE seam_check {name}: no baseboards read from {args[1]}")
    joins = collections.Counter()
    for b in B:
        for w_, e_ in zip(("a", "b"), b["ends"]):
            if e_ == "joined": joins[tuple(round(x) for x in b[w_]) + (b.get("z"),)] += 1   # (by height too: the ceiling rails, 2026-11-06)
    for b in B:
        if b["dropped"]: continue
        at_ = f"({round(b['a'][0])}, {round(b['a'][1])})..({round(b['b'][0])}, {round(b['b'][1])})"
        for w_, e_ in zip(("a", "b"), b["ends"]):
            if e_ == "free": fails.append(f"FAIL BASEBOARD {name}: the board {at_} ends open in the room at its {w_} end")
            if e_ == "joined" and joins[tuple(round(x) for x in b[w_]) + (b.get("z"),)] < 2:
                fails.append(f"FAIL BASEBOARD {name}: the board {at_} is mitred at its {w_} end with no board on the other side")
        if b["len"] < 12 and "joined" not in b["ends"]:
            fails.append(f"FAIL BASEBOARD {name}: the board {at_} is {b['len']} long on its own")
for f in fails: print(f)
print(f"SEAMS {name}: {edges} upright edges looked along, {len(fails)} failures")
