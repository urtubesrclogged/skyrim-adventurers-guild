"""Headless Blender: the main cell's rooms (blender/rooms.py) against the exported hall, and its portals (2026-10-28, the
performance pass). On every side two rooms share, a grid of points (every 8 units), each looked at along the side's
normal both ways through the hall's own shapes (a ray-cast tree of hall2_interior.json's faces):
- in a solid: a ray first meets the back of a face (it leaves the solid);
- open: neither does: a gap the two rooms see each other through, which a portal must cover.
The open points of a side, gathered into connected patches, become its portals (each patch's bounding rectangle,
2 larger all round; a patch under 24 across, a joist bay or a wall's hollow, is left). And every face of the hall's own
must be seen from its own room: 4 and 24 in front of it in the same room (a side running just in front of a wall's face
would give the face to the room behind it, and it would vanish whenever that room is not drawn). Then: boxes overlapping, every placed piece's origin, every light and baked piece in exactly
one room, every navmesh vertex in a room (so nowhere one can stand is outside them all).
    blender --background --python rooms_check.py -- <hall2_interior.json> <nav_interior.json> <out rooms.json>
Writes the boxes, links and portals for Hall2.cs; exits 1 on a side in front of faces (over 400 sq) or anything outside the rooms."""
import sys, os, json, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rooms as R

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
src, navp, outp = args[:3]
D = json.load(open(src))
V, P = [], []
for key, sh in D["shapes"].items():
    base = len(V); V += [Vector(v) for v in sh["v"]]
    P += [[base + i for i in f] for f in sh["f"]]
T = BVHTree.FromPolygons(V, P, all_triangles=False, epsilon=0.0)
STEP, REACH = 8.0, 64.0


def first(o, d):
    """(distance, leaving a solid?) of the first face along o + t d, t <= REACH, or None"""
    loc, nor, idx, dist = T.ray_cast(o, d, REACH)
    if loc is None: return None
    return dist, nor.dot(d) > 0


def in_air(p, o):
    for m in (o if k == 2 else [2]):
        for s in (1.0, -1.0):
            d = Vector([s if q == m else 0.0 for q in range(3)])
            h = T.ray_cast(p, d, 3000)
            if h[0] is None or h[1].dot(d) > 0: return False
    return True


bad, warn = [], []
portals = []
DEBUG = []
slots = [0]
sides = R.shared_faces()
for (ra, ia), (rb, ib), k, plane, o, lo, hi in sides:
    if ra == rb: continue
    n = Vector([1.0 if m == k else 0.0 for m in range(3)])
    nu = max(1, int((hi[0] - lo[0]) // STEP)); nv = max(1, int((hi[1] - lo[1]) // STEP))
    grid = {}
    counts = {"wall": 0, "open": 0}
    for i in range(nu):
        for j in range(nv):
            u = lo[0] + (i + 0.5) * (hi[0] - lo[0]) / nu; v = lo[1] + (j + 0.5) * (hi[1] - lo[1]) / nv
            p = [0.0, 0.0, 0.0]; p[k] = plane; p[o[0]] = u; p[o[1]] = v; p = Vector(p)
            a, b = first(p, n), first(p, -n)
            # in a solid if either ray leaves one (a wall whose far face is missing is still a wall); open only in the hall's
            # air, between surfaces that face the point across the side (a floor under it and a ceiling or lintel over it;
            # for a floor's side, walls all round): under a floor, out past the outer walls or up in a roof's void, nothing
            # is seen through
            c = "wall" if (a is not None and a[1]) or (b is not None and b[1]) else ("open" if in_air(p, o) else "wall")
            counts[c] += 1; grid[(i, j)] = c
    # the open points in patches (4-connected), each patch a portal; first the open points with open all round (a 3 x 3
    # block, 24 across) are kept, so a thin strip (the hollow of a wall, a joist bay, the slab's edge) is no way through
    # and cannot join two openings into one patch spanning the side
    core = {q for q, c in grid.items() if c == "open" and all(grid.get((q[0] + a, q[1] + b)) == "open" for a in (-1, 0, 1) for b in (-1, 0, 1))}
    slots[0] += sum(1 for c in grid.values() if c == "open") - len(core)
    grid = {q: ("open" if q in core else "wall") for q in grid}
    seen = set()
    for key, c in grid.items():
        if c != "open" or key in seen: continue
        stack, cells = [key], []
        seen.add(key)
        while stack:
            q = stack.pop(); cells.append(q)
            for dq in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                w = (q[0] + dq[0], q[1] + dq[1])
                if grid.get(w) == "open" and w not in seen: seen.add(w); stack.append(w)
        du = (hi[0] - lo[0]) / nu; dv = (hi[1] - lo[1]) / nv
        # (the patch's rectangle, given back the rim the 3 x 3 test took, and 2 more all round)
        u0 = lo[0] + (min(c_[0] for c_ in cells) - 1) * du - 2; u1 = lo[0] + (max(c_[0] for c_ in cells) + 2) * du + 2
        v0 = lo[1] + (min(c_[1] for c_ in cells) - 1) * dv - 2; v1 = lo[1] + (max(c_[1] for c_ in cells) + 2) * dv + 2
        u0, u1 = max(u0, lo[0]), min(u1, hi[0]); v0, v1 = max(v0, lo[1]), min(v1, hi[1])
        portals.append({"rooms": [ra, rb], "boxes": [[ra, ia], [rb, ib]], "axis": k, "plane": plane, "o": o,
                        "u": [round(u0, 1), round(u1, 1)], "v": [round(v0, 1), round(v1, 1)], "points": len(cells)})
    tag = "%s[%d]|%s[%d] %s=%g" % (ra, ia, rb, ib, "xyz"[k], plane)
    DEBUG.append({"tag": tag, "lo": lo, "hi": hi, "nu": nu, "nv": nv, "o": o, "grid": [[i, j, c] for (i, j), c in grid.items() if c != "wall"]})
    print("SIDE", tag, counts, "portals", sum(1 for p_ in portals if p_["boxes"] == [[ra, ia], [rb, ib]] and p_["plane"] == plane))
print("SLOTS", slots[0], "open points in strips under 24 across left without a portal")

for a, b in R.overlaps(): bad.append("boxes overlap: %s and %s" % (a, b))

# a face matters only if someone sees it: a clear line from just in front of it to a standing spot's eye height (60 over
# a navmesh vertex) in front of it (the hollows between two walls, the tower's and the hall's, face only each other)
NAV = json.load(open(navp))
EYES = [Vector((v[0], v[1], v[2] + 60)) for v in NAV["verts"]]
def seen(p, nn):
    for e in EYES:
        d = e - p
        if d.dot(nn) <= 0 or d.length > 2500: continue
        if T.ray_cast(p, d.normalized(), d.length)[0] is None: return True
    return False

# every face of the hall's own seen from the room it belongs to: 4 and 24 in front of it in the same room (a side running
# closer in front of a face than 24 would give the face to the room behind it, where it vanishes when that room is not
# drawn; a face in no room at 4 is outside every box, which the pieces' check catches for what stands there)
front = {}
for key, sh in D["shapes"].items():
    for f in sh["f"]:
        pts = [Vector(sh["v"][i]) for i in f]
        nn = Vector((0, 0, 0))
        for i in range(len(pts)): nn += pts[i - 1].cross(pts[i])
        if nn.length < 1e-6: continue
        area = nn.length / 2; nn.normalize()
        c = sum(pts, Vector((0, 0, 0))) / len(pts)
        # what it faces: a face looking into a solid (the first face its normal meets is a back) is hidden in it; one that
        # faces another surface sooner than 24 is seen only from the air between
        hit = T.ray_cast(c + 0.5 * nn, nn, 24)
        if hit[0] is not None and hit[1].dot(nn) > 0: continue
        far = min(24.0, hit[3] - 1) if hit[0] is not None else 24.0
        if far < 5: continue
        r4, r24 = R.room_of(c + 4 * nn), R.room_of(c + far * nn)
        if len(r4) == 1 and len(r24) == 1 and r4 != r24 and seen(c + 2 * nn, nn):
            e = front.setdefault((r4[0], r24[0]), [0, 0.0, []]); e[0] += 1; e[1] += area
            if len(e[2]) < 4: e[2].append((key.split("@")[0], [round(x) for x in c], [round(x, 2) for x in nn]))
for (a, b), (n_, ar, ex) in sorted(front.items(), key=lambda kv: -kv[1][1]):
    msg = "%d faces (%d sq) of %s are within 24 of %s, e.g. %s" % (n_, ar, a, b, ex)
    (bad if ar > 400 else warn).append(msg)
for w_ in warn: print("WARN", w_)

# everything placed in exactly one room
def where(p, what):
    rs = R.room_of(p)
    if len(rs) != 1: bad.append("%s at %s in %s" % (what, [round(c) for c in p], rs or "no room"))
for pc in D["pieces"]: where(pc["pos"], pc["model"].split("/")[-1])
for l in D["lights"]: where(l[0], "light " + str(l[3] if len(l) > 3 else l[1]))
# (markers are never drawn: vanilla leaves its XMarkers outside the rooms, as Dragonsreach's)
for name, items in D["bake"].items():
    for it in items: where([it["m"][0][3], it["m"][1][3], it["m"][2][3]], "baked " + it["model"].split("/")[-1])
lost = [v for v in NAV["verts"] if not R.room_of([v[0], v[1], v[2] + 20])]
if lost: bad.append("%d navmesh vertices in no room, e.g. %s" % (len(lost), [[round(c) for c in v] for v in lost[:8]]))

links = [[r, i, j] for r, bs in R.ROOMS.items() for i in range(len(bs)) for j in range(i + 1, len(bs))]
json.dump({"rooms": R.ROOMS, "origins": {r: R.origin(r) for r in R.ROOMS}, "links": links, "portals": portals}, open(outp, "w"), indent=1)
print("ROOMS %d rooms, %d boxes, %d portals" % (len(R.ROOMS), len(R.boxes()), len(portals)))
for p_ in portals: print("PORTAL", p_["rooms"], "xyz"[p_["axis"]], p_["plane"], "u", p_["u"], "v", p_["v"])
for b_ in bad: print("BAD", b_)
if os.environ.get("AG_ROOMS_DEBUG"): json.dump(DEBUG, open(os.environ["AG_ROOMS_DEBUG"], "w"))
print("ROOMS CHECK", "FAILED %d" % len(bad) if bad else "OK")
sys.exit(1 if bad else 0)
