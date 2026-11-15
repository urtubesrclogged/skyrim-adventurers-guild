"""Leak check for an exported interior part (guildhall_gen.py AG_EXPORT JSON): what a player can see that they should
not. Walks the floor from a seed the way a player does (a step up to 30, a fall of any height, never through a face the
part collides with, 100 of headroom), then from the spots reached (a 24 grid, eyes 64 and 120 above the floor) casts
rays all round. Every shape is one-sided in game (hall_nif.py keeps Bryling House's shaders, none double-sided), so a
ray goes on through a face it meets from behind, as the eye does. Three findings:
  BEHIND  a face the eye meets from behind: the player sees through it (on to the void, or to what lies beyond); each
          such face with its corners, facing and the rays that met it.
  GAP     a ray that meets no face at all: the player sees the void through a gap, placed where the ray last passed
          close to a face before leaving for good, grouped by place.
  INSIDE  an eye that meets more back faces than front ones: it stands inside a solid, so the walk got in (a face
          missing from the collision, or a gap in it); printed with the walk's last steps to it. No eye is placed within
          8 of a face (a head pressed into a timber sees its inside).
The pieces placed in the cell (doors, the fire, the ladder) are not in the part, so an opening a door fills shows as a
VOID: read the positions.
    blender -b -P leak_check.py -- <part.json> --seed x,y,z [--rays N] [--eye-grid G] [--top N] [--json out.json]
Takes and prints hall-frame positions (x across the front, y negative in front, z from the floor)."""
import sys, json, math, collections
from mathutils import Vector
from mathutils.bvhtree import BVHTree
args = sys.argv[sys.argv.index("--") + 1:]; opt = {}
for k in ("--seed", "--rays", "--eye-grid", "--top", "--json"):
    if k in args: i = args.index(k); opt[k] = args[i + 1]; del args[i:i + 2]
NR, TOP = int(opt.get("--rays", 384)), int(opt.get("--top", 25))
G = 12.0; EG = max(1, int(round(float(opt.get("--eye-grid", 24)) / G)))      # the walk's grid, the eyes' (in walk cells)
OX, OY = 0.37, 0.23          # the grid off the round numbers walls stand on: a spot in a face's plane let the walk through it
XY = lambda i, j: (i * G + OX, j * G + OY)
STEP, HEAD, EYES, CELL = 30.0, 100.0, (64.0, 120.0), 24.0
L = lambda p: Vector((-p[1], p[0], p[2])); H = lambda p: (round(p[1]), round(-p[0]), round(p[2]))   # hall <-> layout
d = json.load(open(args[0]))
V, P, K = [], [], []
for key, sh in d["shapes"].items():
    o = len(V); V += [Vector(v) for v in sh["v"]]
    for f in sh["f"]:
        if len(f) >= 3: P.append([o + i for i in f]); K.append(key)
vis = BVHTree.FromPolygons(V, P)
CV = [Vector(p) for t in d["coll"] for p in t]
col = BVHTree.FromPolygons(CV, [[3 * i, 3 * i + 1, 3 * i + 2] for i in range(len(d["coll"]))])
lo = Vector([min(v[k] for v in V) for k in range(3)]); hi = Vector([max(v[k] for v in V) for k in range(3)])
DOWN = Vector((0, 0, -1))

_cols = {}
def column(i, j):
    """every collision face over the column, top down: [(z, one can stand there, room over it)]: within 50 degrees of
    level, with HEAD of room"""
    if (i, j) in _cols: return _cols[(i, j)]
    out, z, above = [], hi.z + 10, hi.z + 1000
    while True:
        loc, nrm, idx, dist = col.ray_cast(Vector((*XY(i, j), z)), DOWN)
        if loc is None: break
        out.append((loc.z, abs(nrm.z) > 0.64 and above - loc.z >= HEAD, above - loc.z))
        above = loc.z; z = loc.z - 0.05
    _cols[(i, j)] = out; return out
def land(i, j, top):
    """where one moving into the column with feet at `top` comes to rest: the highest face at or below it, (z, room) if
    one can stand there; a fall stops on whatever it meets first (the walk fell through solids' tops, 2026-10-25)"""
    for zz, ok, room in column(i, j):
        if zz <= top: return (zz, room) if ok else None
    return None
def clear(a, b, z0, z1):
    """no collision face across the way from a to b between z0 and z1 (three heights)"""
    d_ = Vector((b[0] - a[0], b[1] - a[1], 0)); n_ = d_.length; d_.normalize()
    for z in (z0, (z0 + z1) / 2, z1):
        if col.ray_cast(Vector((a[0], a[1], z)), d_, n_ + 6)[0] is not None: return False
    return True

seed = L([float(v) for v in opt["--seed"].split(",")])
si, sj = int(round((seed.x - OX) / G)), int(round((seed.y - OY) / G))
start = land(si, sj, seed.z + STEP)
if start is None: sys.exit("LEAK: no floor under the seed %s" % opt["--seed"])
seen = {(si, sj, round(start[0]))}; todo = collections.deque([(si, sj, start[0], start[1])]); nodes = []
came = {(si, sj, round(start[0])): None}                 # each spot: the one the walk reached it from
while todo:
    i, j, z, room = todo.popleft(); nodes.append((i, j, z, room))
    for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
        ni, nj = i + di, j + dj
        if not (lo.x - G <= ni * G <= hi.x + G and lo.y - G <= nj * G <= hi.y + G): continue
        l_ = land(ni, nj, z + STEP)
        if l_ is None: continue
        top = max(z, l_[0])
        if not clear(XY(i, j), XY(ni, nj), top + 34, top + 86): continue
        k_ = (ni, nj, round(l_[0]))
        if k_ not in seen: seen.add(k_); todo.append((ni, nj, l_[0], l_[1])); came[k_] = (i, j, round(z))
gold = math.pi * (3 - math.sqrt(5))
DIRS = [Vector((math.cos(gold * k) * math.sqrt(1 - (1 - 2 * (k + .5) / NR) ** 2), math.sin(gold * k) * math.sqrt(1 - (1 - 2 * (k + .5) / NR) ** 2),
                1 - 2 * (k + .5) / NR)) for k in range(NR)]
def look(o, dv):
    """along dv from o: ('void'|'face', the first face met from behind as (index, point) or None)"""
    back, p = None, o
    for _ in range(64):
        loc, nrm, idx, dist = vis.ray_cast(p, dv)
        if loc is None: return "void", back
        if nrm.dot(dv) < 0: return "face", back
        if back is None: back = (idx, loc.copy())
        p = loc + dv * 0.05
    return "face", back
def way_out(o, dv):
    """where a ray that met nothing last passed close to a face before it left the part's bounds: (point, gap, index)"""
    t, hist, best = 0.0, [], None
    while True:
        p = o + dv * t
        if any(p[k] < lo[k] - 60 or p[k] > hi[k] + 60 for k in range(3)): break
        loc, nrm, idx, dist = vis.find_nearest(p)
        if loc is None: break
        hist.append((p.copy(), dist, idx))
        if len(hist) >= 3 and hist[-3][1] >= hist[-2][1] < hist[-1][1] and hist[-2][1] < 40: best = hist[-2]
        t += max(dist * 0.8, 1.0)                      # (nothing nearer than dist: a sphere's step)
    return best or (hist[-1] if hist else (o, 0.0, 0))

behind = collections.defaultdict(lambda: [0, 0, set()])   # face: [rays on to the void, rays on to a face beyond, eyes]
gaps, inside = collections.defaultdict(list), []
eyes = 0; rays = 0
for i, j, z, room in nodes:
    if i % EG or j % EG: continue
    for e in EYES:
        if e > room - 6: continue
        o = Vector((*XY(i, j), z + e))
        if vis.find_nearest(o)[3] < 8: continue                                        # a head pressed into a face: no eye
        eyes += 1; seen_ = []
        for dv in DIRS:
            rays += 1; seen_.append((dv, *look(o, dv)))
        if sum(1 for _, _, b in seen_ if b) > NR / 2: inside.append((H(o), (i, j, round(z)))); continue   # shut in a solid
        for dv, what, back in seen_:
            if back:
                b_ = behind[back[0]]; b_[0 if what == "void" else 1] += 1; b_[2].add(H(o))
            elif what == "void":
                pt, gap, idx = way_out(o, dv)
                gaps[tuple(int(c // CELL) for c in H(pt))].append((H(pt), H(o), K[idx], round(gap, 1)))
zs = [n_[2] for n_ in nodes]
print("LEAK %s: %d spots walked from the seed (z %d..%d), %d eyes, %d rays: %d faces seen from behind (%d rays, %d on to the void), "
      "%d gaps into the void (%d rays), %d eyes shut in a solid"
      % (args[0].replace("\\", "/").split("/")[-1], len(nodes), min(zs), max(zs), eyes, rays, len(behind),
         sum(b[0] + b[1] for b in behind.values()), sum(b[0] for b in behind.values()), len(gaps), sum(map(len, gaps.values())), len(inside)))
def near(es, c): return min(es, key=lambda e: sum((e[k] - c[k]) ** 2 for k in range(3)))
rows = sorted(behind.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))
for idx, (nv, nf, es) in rows[:TOP]:
    pts = [H(V[i]) for i in P[idx]]; a_ = V[P[idx][0]]; n_ = (V[P[idx][1]] - a_).cross(V[P[idx][2]] - a_).normalized()
    lo_ = tuple(min(q[k] for q in pts) for k in range(3)); hi_ = tuple(max(q[k] for q in pts) for k in range(3))
    c = tuple((lo_[k] + hi_[k]) / 2 for k in range(3))
    print("  BEHIND %-6s %s..%s facing (%.2f,%.2f,%.2f): %4d rays (%d on to the void) from %3d eyes, e.g. %s"
          % (K[idx], lo_, hi_, n_.y, -n_.x, n_.z, nv + nf, nv, len(es), near(es, c)))
if len(rows) > TOP: print("  BEHIND ... %d more faces, %d rays" % (len(rows) - TOP, sum(b[0] + b[1] for _, b in rows[TOP:])))
grows = sorted(gaps.values(), key=len, reverse=True)
for g in grows[:TOP]:
    pts = [r[0] for r in g]; c = tuple(round(sum(p[k] for p in pts) / len(pts)) for k in range(3))
    span = tuple(max(p[k] for p in pts) - min(p[k] for p in pts) for k in range(3))
    keys = collections.Counter(r[2] for r in g).most_common(2)
    print("  GAP    %4d rays from %3d eyes at %s span %s near %s, closest pass %.0f, e.g. eye %s"
          % (len(g), len({r[1] for r in g}), c, span, ",".join(k for k, _ in keys), min(r[3] for r in g), near({r[1] for r in g}, c)))
if len(grows) > TOP: print("  GAP ... %d more places, %d rays" % (len(grows) - TOP, sum(len(g) for g in grows[TOP:])))
def path(k_, n=8):
    out = []
    while k_ is not None and len(out) < n: out.append(H(Vector((*XY(k_[0], k_[1]), k_[2])))); k_ = came[k_]
    return out[::-1]
for e, k_ in inside[:TOP]: print("  INSIDE eye %s, the walk's last steps there: %s" % (e, " ".join(map(str, path(k_)))))
if "--json" in opt:
    json.dump({"behind": [[K[i], [H(V[v]) for v in P[i]], b[0], b[1], sorted(b[2])] for i, b in behind.items()],
               "gaps": list(gaps.values()), "inside": [e for e, _ in inside], "nodes": len(nodes), "eyes": eyes}, open(opt["--json"], "w"))
