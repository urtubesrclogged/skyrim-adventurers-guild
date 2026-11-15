"""The interior's shell cut by room (2026-10-28, the performance pass): hall2_interior.json's faces, until now one NIF in
512-unit cells for the whole cell, go to the room each faces (the room 4 in front of it, blender/rooms.py), one NIF per
room pivoted inside it (hall2_interior_room_<Room>.json, its points relative to the room's origin), so the engine's room
bounds can leave a room undrawn, shell and all. In each room a material's faces are one shape, halved along its longest
side while more than rooms.LIMIT lights touch its bounding sphere (the vanilla renderer's per-shape light limit) and
while it is over 1024 across. The hall's lights are portal-strict, so a piece counts its own room's lights. Measured on
hall2bg's export: one shape per room and material is 106 shapes (the 512 cells were 267) with 3 lights on a shape at the
median and 12 at the 90th percentile; halving down to 1024 across, 181 shapes; to 512, 719 shapes and still 7 at the
90th (vanilla: 2 and 3-4, with pieces 257-362 across at the median, in Jorrvaskr, Dragonsreach, the Bannered Mare, the
Blue Palace and the Winking Skeever). The hall's lights are what is dense (14 in the great hall, 12 in the tavern), so
the geometry is split only as far as it pays; rooms.json (blender/rooms_check.py's) is read for the rooms' portals. The collision goes to the room its triangle's middle is in. hall_nif.py builds each file as
it built the whole interior.
    python split_rooms.py <hall2_interior.json> <rooms.json> <out dir>
Writes the room files and rooms_parts.json (each room's origin, file, shapes, triangles and the most lights on a shape)."""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rooms as R

src, roomsp, out = sys.argv[1], sys.argv[2], sys.argv[3]
D = json.load(open(src))
MIN_SIZE = 1024.0
ALL = [(L, (R.room_of(L[0]) or [None])[0]) for L in R.lights_of(D)]
LIGHTS = {r: [L for L, lr in ALL if lr == r] for r in R.ROOMS}


def nearest_room(p):
    best = None
    for r, _, b in R.boxes():
        d = math.sqrt(sum(max(b[2 * k] - p[k], 0, p[k] - b[2 * k + 1]) ** 2 for k in range(3)))
        if best is None or d < best[0]: best = (d, r)
    return best[1]


def room_for(c, n):
    for s in (4.0, 1.0, 12.0):
        rs = R.room_of([c[k] + s * n[k] for k in range(3)])
        if len(rs) == 1: return rs[0], False
    return nearest_room(c), True


# every face cut along the rooms' sides that cross it, each piece then given to the room it faces (in
# hall2bi the clerks' office's floor vanished on turning the head: it was one face with the services' floor,
# given whole to the services, which the engine leaves undrawn when its doorway is out of view; 566 faces spanned two rooms).
# A cut corner's UV, colour and alpha are interpolated along its edge
FACES = []            # {"v", "uv", "c", "a", "mat"}: the faces as cut
faces = {}            # (room, material) -> [(face index, its middle)]
stray = 0


def cut(face, ax, at):
    """a convex face split by the plane (axis ax) = at: the parts below and above (either may be None)"""
    halves = ([], []); keys = [k_ for k_ in ("v", "uv", "c", "a") if face.get(k_) is not None]
    n_ = len(face["v"])
    for i in range(n_):
        j = (i + 1) % n_
        pa, pb = face["v"][i][ax], face["v"][j][ax]
        sa, sb = pa >= at, pb >= at
        halves[sa].append({k_: face[k_][i] for k_ in keys})
        if sa != sb:
            s_ = (at - pa) / (pb - pa)
            mid = {k_: [face[k_][i][m] + s_ * (face[k_][j][m] - face[k_][i][m]) for m in range(len(face[k_][i]))] for k_ in keys}
            mid["v"][ax] = at
            halves[0].append(mid); halves[1].append(dict(mid))
    out_ = []
    for h_ in halves:
        if len(h_) < 3: out_.append(None); continue
        out_.append(dict({k_: [q[k_] for q in h_] for k_ in keys}, mat=face["mat"]))
    return out_


def boundaries(face):
    """the rooms' box sides that cross a face (planes strictly inside its extent, of the boxes it overlaps)"""
    lo = [min(p[k] for p in face["v"]) for k in range(3)]; hi = [max(p[k] for p in face["v"]) for k in range(3)]
    planes = set()
    for _, _, b in R.boxes():
        if any(lo[k] > b[2 * k + 1] or hi[k] < b[2 * k] for k in range(3)): continue
        for k in range(3):
            for at in (b[2 * k], b[2 * k + 1]):
                if lo[k] + 0.5 < at < hi[k] - 0.5: planes.add((k, at))
    return sorted(planes)


cut_n = 0
for key, sh in D["shapes"].items():
    mat = key.split("@")[0]
    for fi, f in enumerate(sh["f"]):
        face = {"v": [list(sh["v"][i]) for i in f], "uv": [list(q) for q in sh["uv"][fi]], "mat": mat,
                "c": [list(q) for q in sh["c"][fi]] if "c" in sh else None, "a": [list(q) if isinstance(q, list) else [q] for q in sh["a"][fi]] if "a" in sh else None}
        pieces_ = [face]
        for ax, at in boundaries(face):
            nxt_ = []
            for p_ in pieces_: nxt_ += [h for h in cut(p_, ax, at) if h is not None]
            pieces_ = nxt_
        cut_n += len(pieces_) > 1
        for p_ in pieces_:
            P = p_["v"]
            n = [0.0, 0.0, 0.0]
            for i in range(len(P)):
                a, b = P[i - 1], P[i]
                n[0] += (a[1] - b[1]) * (a[2] + b[2]); n[1] += (a[2] - b[2]) * (a[0] + b[0]); n[2] += (a[0] - b[0]) * (a[1] + b[1])
            L = math.sqrt(sum(x * x for x in n))
            if L < 1e-3: continue                                   # (a sliver the cut left)
            n = [x / L for x in n]
            c = [sum(p[k] for p in P) / len(P) for k in range(3)]
            room, guessed = room_for(c, n)
            stray += guessed
            FACES.append(p_); faces.setdefault((room, mat), []).append((len(FACES) - 1, c))
print("CUT %d faces along the rooms' sides" % cut_n)


def bounds(items):
    lo = [1e9] * 3; hi = [-1e9] * 3
    for fi, _ in items:
        for p in FACES[fi]["v"]:
            for k in range(3): lo[k] = min(lo[k], p[k]); hi[k] = max(hi[k], p[k])
    return lo, hi


def split(items, room):
    """halves along the longest side, at the faces' middles' median, until few enough lights touch each piece"""
    lo, hi = bounds(items)
    size = max(hi[k] - lo[k] for k in range(3))
    if len(items) < 2 or size <= MIN_SIZE or len(R.lights_on(lo, hi, LIGHTS[room])) <= R.LIMIT: return [items]
    ax = max(range(3), key=lambda k: hi[k] - lo[k])
    s = sorted(items, key=lambda t: t[1][ax])
    m = len(s) // 2
    return split(s[:m], room) + split(s[m:], room)


parts = {}
ALLN = []
os.makedirs(out, exist_ok=True)
by_room = {}
for (room, mat), items in sorted(faces.items()):
    for k_, piece in enumerate(split(items, room)):
        by_room.setdefault(room, []).append(("%s@%s_%d" % (mat, room, k_), piece))
coll_by_room = {}
for t in D["coll"]:
    c = [sum(p[k] for p in t) / 3 for k in range(3)]
    rs = R.room_of(c)
    coll_by_room.setdefault(rs[0] if len(rs) == 1 else nearest_room(c), []).append(t)
for room in sorted(set(by_room) | set(coll_by_room)):
    o = R.origin(room)
    shapes, tris, worst = {}, 0, 0
    for name, piece in by_room.get(room, []):
        V, F, U, C, A = [], [], [], [], []
        have_c = all(FACES[fi].get("c") is not None for fi, _ in piece); have_a = all(FACES[fi].get("a") is not None for fi, _ in piece)
        for fi, _ in piece:
            fc = FACES[fi]
            F.append(list(range(len(V), len(V) + len(fc["v"]))))
            V += [[p[k] - o[k] for k in range(3)] for p in fc["v"]]
            U.append(fc["uv"])
            if have_c: C.append(fc["c"])
            if have_a: A.append([q[0] if len(q) == 1 else q for q in fc["a"]])
            tris += len(fc["v"]) - 2
        shapes[name] = {"v": V, "f": F, "uv": U}
        if have_c: shapes[name]["c"] = C
        if have_a: shapes[name]["a"] = A
        lo, hi = bounds(piece)
        n_ = len(R.lights_on(lo, hi, LIGHTS[room])); worst = max(worst, n_); ALLN.append(n_)
    coll = [[[p[k] - o[k] for k in range(3)] for p in t] for t in coll_by_room.get(room, [])]
    fn = "hall2_interior_room_%s.json" % room
    json.dump({"shapes": shapes, "coll": coll}, open(os.path.join(out, fn), "w"))
    parts[room] = {"origin": o, "file": fn, "nif": "AGHall2Room%s.nif" % room, "shapes": len(shapes), "tris": tris,
                   "coll": len(coll), "max_lights": worst}
    print("ROOM %-11s %3d shapes %6d tris %5d collision, at most %d lights on a shape" % (room, len(shapes), tris, len(coll), worst))
json.dump(parts, open(os.path.join(out, "rooms_parts.json"), "w"), indent=1)
# (the check: every piece inside one room's boxes, within 1)
across = 0
for fc in FACES:
    lo = [min(p[k] for p in fc["v"]) for k in range(3)]; hi = [max(p[k] for p in fc["v"]) for k in range(3)]
    hit = {r for r, _, b in R.boxes() if all(min(hi[k], b[2 * k + 1]) - max(lo[k], b[2 * k]) > 1 for k in range(3) if hi[k] - lo[k] > 1)
           and all(lo[k] <= b[2 * k + 1] - 1 and hi[k] >= b[2 * k] + 1 for k in range(3))}
    across += len(hit) > 1
print("ACROSS %d pieces still span two rooms" % across)
if across: sys.exit(1)
# the baked clutter by room (blender/bake_clutter.py makes AGHall2Bake<Room>.nif the same way): each room's origin, and the
# bounds round its pieces' origins relative to it (none is 35 across), for Hall2.cs
bakes = {}
for name, items in D.get("bake", {}).items():
    for it in items:
        p = [it["m"][0][3], it["m"][1][3], it["m"][2][3]]
        room = R.room_of(p)[0]; o = R.origin(room)
        b = bakes.setdefault(room, {"origin": o, "lo": [1e9] * 3, "hi": [-1e9] * 3, "pieces": 0})
        b["pieces"] += 1
        for k in range(3): b["lo"][k] = min(b["lo"][k], p[k] - o[k] - 35); b["hi"][k] = max(b["hi"][k], p[k] - o[k] + 35)
json.dump(bakes, open(os.path.join(out, "rooms_bakes.json"), "w"), indent=1)
print("BAKES by room:", {r: b["pieces"] for r, b in sorted(bakes.items())})
ALLN.sort(); q_ = lambda f: ALLN[min(len(ALLN) - 1, int(f * len(ALLN)))]
print("LIGHTS per shape: median %d, p75 %d, p90 %d, most %d (vanilla: 2, 3, 3-4, 7-24)" % (q_(.5), q_(.75), q_(.9), ALLN[-1]))
print("SPLIT %d rooms, %d shapes (was %d), %d faces by their nearest room (none in front of them)"
      % (len(parts), sum(p["shapes"] for p in parts.values()), len(D["shapes"]), stray))
