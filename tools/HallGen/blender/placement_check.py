"""The placement gate (the basement's first build, hall2bi, went out unvalidated: load doors stood in walls, the bath
door outside its doorway, benches nobody could sit on, a keg floating in the air).
Every placed piece of an exported part, measured by its mesh (mesh_info.py) and turned and scaled as the game places it,
against the part's collision and every other piece:
  SUPPORT  it stands on a floor or on another piece (within 3), or is a piece that hangs (sconces, banners, racks ...);
           a piece whose feet are under the floor it stands over is SUNK, one with nothing within 3 under it FLOATS
  WALL     its box cuts into the shell's collision by more than 3 (a load door's back, its handle, 10)
  PIECE    its box overlaps another piece's by more than 3 (a piece wholly inside another, a book in a case, is listed apart)
  SEAT     furniture: every sit marker has one entry (its record's entry points: front, left, right) with floor under it at
           the piece's feet and room to stand (radius 16, 10..120 over the floor) clear of walls and pieces
  DOOR     a door's record bounds (its leaf swung open, for a hinged one) clear of walls and pieces
  REACH    herbs and game (Hanging*) hung with their top within REACH (160) of the floor under them
  WATER    a water plane's surface shows only inside its pool: every point of it not under a floor within 12 lies in one open
           area, which the report gives
    python placement_check.py <part.json> --mesh <mesh_info.json> --records <records.json> [--all] [--hall]
records.json: {ed: {type, obnd}} (dotnet run -- bounds --json <eds file>). Prints hall-frame positions (x right, y back).
Exits 1 on any failure."""
import sys, json, math, re
import numpy as np

args = sys.argv[1:]; opt = {}
for k in ("--mesh", "--records", "--shell", "--ground", "--plants"):
    if k in args: i = args.index(k); opt[k] = args[i + 1]; del args[i:i + 2]
SHOW_ALL = "--all" in args; args = [a for a in args if a != "--all"]
part = json.load(open(args[0])); MI = json.load(open(opt["--mesh"])); REC = json.load(open(opt["--records"]))
TOL = 3.0
LOOSE, LOOSE_SINK = {"MiscItem", "Ingestible", "Ingredient", "Book", "Weapon", "Armor", "Ammunition", "Scroll", "SoulGem", "Key"}, 0.5
HANGS = re.compile(r"AGHall2Chain|^hanging|/hanging|sconce|banner|tapestry|shield|plaque|painting|trophy|mount|display|wallrack|weaponrack|bowrack|shelf|lantern|"
                   r"chandelier|hook|map|wallshelf|candelabra.*wall|wall|guildboard|leaderboard", re.I)   # (2026-11-03: the guild's boards
                   # by name: until then a board on a wall was judged as standing; not "board", which is every sideboard)
SKIP = re.compile(r"^meshes/(effects|water|marker)", re.I)
# how far vanilla itself sinks a mesh under the floor it stands on (measured: each placement's height over the floor-standing
# pieces beside it in Skyrim.esm's interiors, BenchRefs): the dummies' posts, the hay of a hay bedroll, a ladder's feet
SINKS = {"PracticeDummy01": 33, "PracticeDummy02": 33, "PracticeDummy03": 33, "BedrollHay01L": 21, "TrapdoorLadder02": 6}
# how far a piece may reach into the shell, as vanilla's do: a hay pile's edges under a cell's walls (Windhelm's jail)
EMBEDS = {"BedrollHay01L": 12}
# pieces vanilla places one inside the other, at one origin and turn (every jail cell of Windhelm's and Riften's)
PAIRS = {("ImpJailDoorframe01", "ImpJailDoor01")}
# sets vanilla places at fixed offsets from each other, overlapping and held by each other (HallSpike `pairs` over Skyrim.esm,
# 2026-10-29): Whiterun's wall fireplace with its pot and the pot's spit (all four houses that use it), a quill standing in its
# inkwell (19.7..20.6 over the well's foot). Within SET_R of each other they may overlap, and the held one needs no floor
SETS = {frozenset(("WRIntWallStrChimney02", "CraftingCookingPotSm")), frozenset(("WRIntWallStrChimney02", "CookingSpitSm01")),
        frozenset(("CraftingCookingPotSm", "CookingSpitSm01")), frozenset(("Quill01", "Inkwell01"))}
HELD = {"CookingSpitSm01": "WRIntWallStrChimney02", "CraftingCookingPotSm": "CookingSpitSm01", "Quill01": "Inkwell01"}
SET_R = 260
# (no one can reach 12 feet up to hang herbs from a ceiling) herbs and game hang where a
# hand puts them: the top within REACH of the floor under them (about 7.5 feet; a peg under a wall shelf's board, 147)
REACH, HUNG_BY_HAND = 160, re.compile(r"^Hanging(?!.*(Lantern|Chandelier|Light|Banner))", re.I)


def H(p):                                                # the cell's frame to the hall's (x right, y back)
    return [round(p[1]), round(-p[0]), round(p[2])]


# ---------------------------------------------------------------- the shell's collision
# (2026-11-05: the site's part has no building and no ground in its collision, so its torches on the front "floated" and the
# yard's pieces had "nothing under" them, 1418 reports nobody read) --shell: other parts' collision, as walls and floors (the
# body's); --ground: triangles that are only ground to stand on (the site's terrain, "ground" in its export), never a wall
_sh = [t_ for f_ in opt.get("--shell", "").split(",") if f_ for t_ in json.load(open(f_))["coll"]]
_gr = json.load(open(opt["--ground"])).get("ground", []) if "--ground" in opt else []
if _gr:   # only where nothing of the hall's own is laid over it (under the podium, the beds and the paving the terrain is buried)
    _F = np.array([t_ for t_ in list(part["coll"]) + _sh], float)
    _FN = np.cross(_F[:, 1] - _F[:, 0], _F[:, 2] - _F[:, 0]); _FL = np.linalg.norm(_FN, axis=1)
    _F = _F[(_FL > 1e-9) & (np.abs(_FN[:, 2]) > 0.7 * np.maximum(_FL, 1e-9))]
    _G = np.array(_gr, float); _gc = _G.mean(1)[:, :2]; _keep = np.ones(len(_G), bool)
    for _a in range(0, len(_F), 256):
        _f = _F[_a:_a + 256]; a_, b_, c_ = _f[:, 0, :2], _f[:, 1, :2], _f[:, 2, :2]
        def _s(p_, q_, r_): return (p_[:, None, 0] - r_[None, :, 0]) * (q_[None, :, 1] - r_[None, :, 1]) - (q_[None, :, 0] - r_[None, :, 0]) * (p_[:, None, 1] - r_[None, :, 1])
        d1_, d2_, d3_ = _s(_gc, a_, b_), _s(_gc, b_, c_), _s(_gc, c_, a_)
        inside_ = ~(((d1_ < 0) | (d2_ < 0) | (d3_ < 0)) & ((d1_ > 0) | (d2_ > 0) | (d3_ > 0)))
        _keep &= ~inside_.any(1)
    _gr = _G[_keep].tolist()
T = np.array(list(part["coll"]) + _sh + _gr, float)    # (n, 3, 3)
GROUND = np.zeros(len(T), bool); GROUND[len(T) - len(_gr):] = True
TN = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); L = np.linalg.norm(TN, axis=1); ok = L > 1e-9
T, TN, GROUND = T[ok], TN[ok] / L[ok][:, None], GROUND[ok]
TLO, THI = T.min(1), T.max(1)
UP = np.abs(TN[:, 2]) > 0.7                             # (level faces, either winding: the collision's is not to be trusted)


# ---------------------------------------------------------------- the pieces as oriented boxes
class Box:
    def __init__(s, c, ax, half, z0, z1):            # centre (x, y), unit axes (2, 2), half sizes (2), z range
        s.c, s.ax, s.half, s.z0, s.z1 = np.array(c, float), np.array(ax, float), np.array(half, float), z0, z1

    def corners(s):
        out = []
        for i in (-1, 1):
            for j in (-1, 1):
                q = s.c + s.ax[0] * s.half[0] * i + s.ax[1] * s.half[1] * j
                out += [[q[0], q[1], s.z0], [q[0], q[1], s.z1]]
        return np.array(out)

    def aabb(s):
        k = s.corners(); return k.min(0), k.max(0)

    def to_local(s, P):                              # world points -> (u, v, z) along the axes from the centre
        d = P[..., :2] - s.c
        return np.stack([d @ s.ax[0], d @ s.ax[1], P[..., 2]], -1)


def box_of(pc, lo, hi, scale=None):
    x, y, z = pc["pos"]; a = math.radians(pc.get("yaw", 0)); c_, s_ = math.cos(a), math.sin(a); sc = scale or pc.get("scale", 1.0)
    lo = [v * sc for v in lo]; hi = [v * sc for v in hi]
    # the game turns a placed reference clockwise by its Z: local (lx, ly) -> (lx c + ly s, -lx s + ly c)
    ex, ey = np.array([c_, -s_]), np.array([s_, c_])
    mid = np.array([x, y]) + ex * (lo[0] + hi[0]) / 2 + ey * (lo[1] + hi[1]) / 2
    return Box(mid, [ex, ey], [(hi[0] - lo[0]) / 2, (hi[1] - lo[1]) / 2], z + lo[2], z + hi[2])


def local_pt(pc, p):
    x, y, z = pc["pos"]; a = math.radians(pc.get("yaw", 0)); c_, s_ = math.cos(a), math.sin(a); sc = pc.get("scale", 1.0)
    return np.array([x + (p[0] * c_ + p[1] * s_) * sc, y + (-p[0] * s_ + p[1] * c_) * sc, z + p[2] * sc])


def local_dir(pc, d):
    a = math.radians(pc.get("yaw", 0)); c_, s_ = math.cos(a), math.sin(a)
    return np.array([d[0] * c_ + d[1] * s_, -d[0] * s_ + d[1] * c_])


def tri_box(box, tri):
    """separating-axis test of a triangle against a box (the box's frame); the triangle's own normal and the 9 cross axes"""
    P = box.to_local(tri)                              # (3, 3) in the box's frame, its centre at u = v = 0
    zc, zh = (box.z0 + box.z1) / 2, (box.z1 - box.z0) / 2
    P = P - np.array([0, 0, zc]); h = np.array([box.half[0], box.half[1], zh]) - 0.5   # (touching is not cutting)
    if (P.min(0) > h).any() or (P.max(0) < -h).any(): return False
    e = [P[1] - P[0], P[2] - P[1], P[0] - P[2]]; n = np.cross(e[0], e[1])
    axes = [n] + [np.cross(np.eye(3)[i], ej) for i in range(3) for ej in e]
    for a in axes:
        if np.linalg.norm(a) < 1e-9: continue
        p = P @ a; r = np.abs(a) @ h
        if p.min() > r or p.max() < -r: return False
    return True


def wall_depth(box, skip_up=False):
    """how far the box reaches through the shell's faces it cuts: the least move along a face's normal, either way, that
    clears the box of its plane (the collision's winding is not to be trusted); the deepest, and the face's centre"""
    lo, hi = box.aabb()
    m = ~((TLO > hi + 0.01).any(1) | (THI < lo - 0.01).any(1))
    m &= ~GROUND                                         # (ground is stood on, never cut into: plants and posts sit in it)
    if skip_up: m &= ~UP
    best, where = 0.0, None
    K = box.corners()
    for i in np.nonzero(m)[0]:
        if not tri_box(box, T[i]): continue
        pk = K @ TN[i]; pd = float(TN[i] @ T[i, 0])
        d = min(pd - float(pk.min()), float(pk.max()) - pd)
        if d > best: best, where = d, T[i].mean(0)
    return best, where


def surfaces_at(x, y):
    """the heights of the shell's upward faces over the point"""
    m = UP & (TLO[:, 0] <= x) & (THI[:, 0] >= x) & (TLO[:, 1] <= y) & (THI[:, 1] >= y)
    out = []
    for i in np.nonzero(m)[0]:
        a, b, c = T[i]; v0, v1, v2 = b - a, c - a, np.array([x, y, 0]) - a
        d = v0[0] * v1[1] - v1[0] * v0[1]
        if abs(d) < 1e-9: continue
        u = (v2[0] * v1[1] - v1[0] * v2[1]) / d; w = (v0[0] * v2[1] - v2[0] * v0[1]) / d
        if u < -1e-6 or w < -1e-6 or u + w > 1 + 1e-6: continue
        n = TN[i]; out.append(float(a[2] - (n[0] * (x - a[0]) + n[1] * (y - a[1])) / n[2]))
    return out


def piece_up_at(pc, x, y):
    """the heights of a piece's own upward faces over the point (mesh_info.py's "up", placed as the game places it)"""
    mi = MI.get(pc["model"].replace("\\", "/").lower(), {}); out = []
    a_ = math.radians(pc.get("yaw", 0)); c_, s_ = math.cos(a_), math.sin(a_); sc = pc.get("scale", 1.0); px, py, pz = pc["pos"]
    dx, dy = (x - px) / sc, (y - py) / sc
    lx, ly = dx * c_ - dy * s_, dx * s_ + dy * c_                 # (the point in the piece's own frame)
    for a, b, c in mi.get("up", []):
        d = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
        if abs(d) < 1e-9: continue
        u = ((lx - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (ly - a[1])) / d; w = ((b[0] - a[0]) * (ly - a[1]) - (lx - a[0]) * (b[1] - a[1])) / d
        if u < -1e-6 or w < -1e-6 or u + w > 1 + 1e-6: continue
        out.append(pz + (a[2] + u * (b[2] - a[2]) + w * (c[2] - a[2])) * sc)
    return out


def box_box(A, B):
    """overlap depth of two upright boxes (0: apart): the least overlap over their four plan axes and z"""
    oz = min(A.z1, B.z1) - max(A.z0, B.z0)
    if oz <= 0: return 0.0
    best = oz
    for ax in list(A.ax) + list(B.ax):
        pa = [float(k @ ax) for k in A.corners()[:, :2]]; pb = [float(k @ ax) for k in B.corners()[:, :2]]
        o = min(max(pa), max(pb)) - max(min(pa), min(pb))
        if o <= 0: return 0.0
        best = min(best, o)
    return best


def inside(A, B, tol=1.0):                             # A wholly inside B
    k = B.to_local(A.corners()); return (np.abs(k[:, 0]) <= B.half[0] + tol).all() and (np.abs(k[:, 1]) <= B.half[1] + tol).all() \
        and A.z0 >= B.z0 - tol and A.z1 <= B.z1 + tol


def circle_clear(x, y, z0, z1, r, boxes, skip):
    """a standing space (radius r, z0..z1) clear of the shell and of the pieces' boxes"""
    b = Box([x, y], [[1, 0], [0, 1]], [r, r], z0, z1)
    d, _ = wall_depth(b)
    if d > 0.5: return "the shell"
    for j, (pc, B) in enumerate(boxes):
        if j in skip or B is None: continue
        if box_box(b, B) > 0.5: return pc["ed"]
    return None


pieces = part["pieces"]
for pc in pieces: pc.setdefault("ed", pc["model"].replace("\\", "/").split("/")[-1])   # (a piece placed by its mesh alone)
boxes = []
for pc in pieces:
    mi = MI.get(pc["model"].replace("\\", "/").lower(), {})
    ob_ = REC.get(pc["ed"], {}).get("obnd")
    if not mi.get("box") and mi.get("markers") and ob_:          # (invisible furniture, no shape to measure: its record's bounds)
        mi["box"] = [ob_[:3], ob_[3:]]
    if SKIP.match(pc["model"].replace("\\", "/")) or not mi.get("box") or (pc.get("rx") and not pc.get("ga")): boxes.append((pc, None)); continue
    if pc.get("ga"):                                             # (2026-11-03) a piece by the game's own angles: the upright box round its
        X_, Y_, Z_ = (math.radians(-v) for v in pc["ga"])          # turned box's corners (the overmantel's swords lie in the breast's plane: it
        Rx_ = np.array([[1, 0, 0], [0, math.cos(X_), -math.sin(X_)], [0, math.sin(X_), math.cos(X_)]])   # widens them along the wall, not into it)
        Ry_ = np.array([[math.cos(Y_), 0, math.sin(Y_)], [0, 1, 0], [-math.sin(Y_), 0, math.cos(Y_)]])
        Rz_ = np.array([[math.cos(Z_), -math.sin(Z_), 0], [math.sin(Z_), math.cos(Z_), 0], [0, 0, 1]])
        lo_, hi_ = mi["box"]; sc_ = pc.get("scale", 1.0)
        K_ = np.array([[x_, y_, z_] for x_ in (lo_[0], hi_[0]) for y_ in (lo_[1], hi_[1]) for z_ in (lo_[2], hi_[2])]) * sc_ @ (Rx_ @ Ry_ @ Rz_).T + np.array(pc["pos"], float)
        a_, b_ = K_.min(0), K_.max(0)
        boxes.append((pc, Box((a_[:2] + b_[:2]) / 2, [np.array([1.0, 0.0]), np.array([0.0, 1.0])], (b_[:2] - a_[:2]) / 2, a_[2], b_[2]))); continue
    boxes.append((pc, box_of(pc, *mi["box"])))

fails, notes = [], []
def fail(kind, i, msg): fails.append((kind, i, msg))
def note(kind, i, msg): notes.append((kind, i, msg))


for i, (pc, B) in enumerate(boxes):
    if B is None: continue
    ed = pc["ed"]; typ = REC.get(ed, {}).get("type", "?"); load = "load" in ed.lower() or pc.get("role")
    # (a weapon stored on a rack: the rack's script hangs it on attach; it is placed only near it)
    if typ == "Weapon" and pc.get("name", "").endswith("Weapon"): note("RACKED", i, "hung by its rack's script"); continue
    # ---- WALL
    d, w = wall_depth(B)
    allow = 10.0 if (typ == "Door" and load) else max(TOL, EMBEDS.get(ed, 0), SINKS.get(ed, 0))
    if d > allow: fail("WALL", i, f"cuts {d:.0f} into the shell at {H(w)}")
    # ---- SUPPORT
    inset = [B.c + B.ax[0] * B.half[0] * u * 0.6 + B.ax[1] * B.half[1] * v * 0.6 for u, v in ((0, 0), (1, 1), (1, -1), (-1, 1), (-1, -1))]
    rest, under, over, sunk_loose = False, [], [], None
    loose = typ in LOOSE
    held_by = next((pj["ed"] for pj, Bj in boxes if pj is not pc and pj["ed"] == HELD.get(ed) and math.dist(pc["pos"], pj["pos"]) < SET_R), None)
    if held_by: note("SET", i, f"held by {held_by}, as vanilla sets them"); inset = []; rest = True
    for k, q in enumerate(inset):
        zs = surfaces_at(q[0], q[1])
        for j, (pj, Bj) in enumerate(boxes):                       # the faces of other pieces that look up, under it (their
            if j == i or Bj is None: continue                       # mesh's own: a shelf's inner boards, a table's top)
            lq = Bj.to_local(np.array([[q[0], q[1], 0.0]]))[0]
            if abs(lq[0]) > Bj.half[0] or abs(lq[1]) > Bj.half[1]: continue
            zs += piece_up_at(pj, q[0], q[1])
        # (a surface carries it from TOL under its feet, 6 more for a door's leaf over its sill, to vanilla's own sink over them;
        # a loose thing, which physics moves, may sink only LOOSE_SINK: started inside what holds it, the game pushes it out
        # and it falls (a quill 0.9 into a desk ended leaning on the wall, floating))
        if loose and any(B.z0 + LOOSE_SINK < z <= B.z0 + TOL for z in zs):
            sunk_loose = max(z for z in zs if B.z0 + LOOSE_SINK < z <= B.z0 + TOL) - B.z0
        if any(B.z0 - TOL - (6 if typ == "Door" else 0) <= z <= B.z0 + (LOOSE_SINK if loose else SINKS.get(ed, 0) + TOL) for z in zs): rest = True; break
        if k == 0:
            under = [z for z in zs if z < B.z0 - TOL]; over = [z for z in zs if B.z0 + TOL < z < B.z1 - TOL]
    if not rest:
        hung = HANGS.search(ed) or HANGS.search(pc["model"])
        if sunk_loose is not None: fail("SUPPORT", i, f"SUNK: a loose thing {sunk_loose:.1f} into what holds it (physics will push it out)")
        elif over: fail("SUPPORT", i, f"SUNK: its feet {max(over) - B.z0:.0f} under the surface at {max(over):.0f}")
        elif hung:                                                # (a hanging piece must touch the shell: grown by 3, it cuts it)
            Bg = Box(B.c, B.ax, B.half + 3, B.z0 - 3, B.z1 + 3)
            by_ = next((pj["ed"] for j, (pj, Bj) in enumerate(boxes) if j != i and Bj is not None and HANGS.search(pj["ed"] + pj["model"])
                        and box_box(Bg, Bj) > 0), None)                # (or from a piece made to hang things: a shelf's board, a rack)
            if wall_depth(Bg)[0] > 0.5: note("HUNG", i, "hangs, against the shell")
            elif by_: note("HUNG", i, f"hangs from {by_}")
            else: fail("SUPPORT", i, "hangs in the air: nothing within 3 of it")
        elif under: fail("SUPPORT", i, f"FLOATS {B.z0 - max(under):.0f} over the surface at {max(under):.0f}")
        else: fail("SUPPORT", i, "nothing under it")
    # ---- REACH (herbs and game are hung by a hand standing on the floor under them)
    if HUNG_BY_HAND.search(ed):
        fl_ = [z for z in surfaces_at(B.c[0], B.c[1]) if z < B.z0]
        if fl_ and B.z1 - max(fl_) > REACH: fail("REACH", i, f"hung {B.z1 - max(fl_):.0f} over the floor: out of a hand's reach ({REACH})")
    # ---- PIECE
    for j in range(i + 1, len(boxes)):
        pj, Bj = boxes[j]
        if Bj is None or (REC.get(pj["ed"], {}).get("type") == "Weapon" and pj.get("name", "").endswith("Weapon")): continue
        o = box_box(B, Bj)
        if o <= TOL: continue
        if frozenset((ed, pj["ed"])) in SETS and math.dist(pc["pos"], pj["pos"]) < SET_R:
            note("SET", i, f"with {pj['ed']}, as vanilla sets them"); continue
        # (herbs or game hung from a shelf's board: their tops just under its top, inside its box below the board, which is air)
        hp_ = [(x_, Bx_, y_) for x_, Bx_, y_ in ((pc, B, Bj), (pj, Bj, B)) if HUNG_BY_HAND.search(x_["ed"])]
        if hp_ and HANGS.search((pj if hp_[0][0] is pc else pc)["ed"]) and 0 <= hp_[0][2].z1 - hp_[0][1].z1 < 8:
            note("HUNGON", i, f"with {pj['ed']}: hung from it"); continue
        if inside(B, Bj) or inside(Bj, B): note("INSIDE", i, f"with {pj['ed']} at {H(list(Bj.c) + [Bj.z0])}"); continue
        # (one standing on the other's own surface, a keg on a shelf's board, a sack on a crate: on it, not in it)
        if any(abs(z - Bj.z0) <= TOL for z in piece_up_at(pc, *Bj.c)) or any(abs(z - B.z0) <= TOL for z in piece_up_at(pj, *B.c)):
            note("ON", i, f"with {pj['ed']}"); continue
        # (a low ground cover, hay, a rug, a bedroll: its box is not its pile; it clashes only where its mesh lies under the other)
        for gc_, other_, Bo_ in ((pc, pj, Bj), (pj, pc, B)):
            Bg_ = B if gc_ is pc else Bj
            if Bg_.z1 - Bg_.z0 < 30 and not any(piece_up_at(gc_, *q) for q in
                                                [Bo_.c + Bo_.ax[0] * Bo_.half[0] * u * 0.7 + Bo_.ax[1] * Bo_.half[1] * v * 0.7
                                                 for u, v in ((0, 0), (1, 1), (1, -1), (-1, 1), (-1, -1))]):
                note("BESIDE", i, f"{other_['ed']} beside {gc_['ed']}'s pile"); break
        else:
            gc_ = None
        if gc_ is not None: continue
        if (ed, pj["ed"]) in PAIRS or (pj["ed"], ed) in PAIRS:
            if math.dist(pc["pos"], pj["pos"]) < 1 and abs((pc.get("yaw", 0) - pj.get("yaw", 0)) % 360) < 0.5:
                note("PAIR", i, f"with {pj['ed']}, as vanilla pairs them"); continue
        fail("PIECE", i, f"overlaps {pj['ed']} at {H(list(Bj.c) + [Bj.z0])} by {o:.0f}")
    # ---- SEAT
    mi = MI.get(pc["model"].replace("\\", "/").lower(), {})
    if typ == "Furniture" and mi.get("markers"):
        dis_ = REC.get(ed, {}).get("disabled") or []                  # (the record's own disabled entry points, by marker: CommonChair01L)
        for k_mk, mk in enumerate(mi["markers"]):
            h = math.radians(mk[3]); f_ = np.array([math.sin(h), math.cos(h)]); r_ = np.array([f_[1], -f_[0]])
            ent = mk[5] & ~(dis_[k_mk] if k_mk < len(dis_) else 0); dirs = [("front", f_)] * bool(ent & 1) + [("right", r_)] * bool(ent & 4) + [("left", -r_)] * bool(ent & 8) + [("behind", -f_)] * bool(ent & 2)
            mp = local_pt(pc, mk[:3]); good, why = None, []
            for nm, dv in dirs:
                wd = local_dir(pc, dv); ex, ey = mp[0] + wd[0] * 45, mp[1] + wd[1] * 45
                z0 = pc["pos"][2]                                        # (the floor it is placed on: its origin)
                fl = [z for z in surfaces_at(ex, ey) if abs(z - z0) <= TOL + 3]
                if not fl: why.append(f"{nm}: no floor"); continue
                blk = circle_clear(ex, ey, z0 + 10, z0 + 120, 16, boxes, {i})
                if blk: why.append(f"{nm}: {blk} in the way"); continue
                good = nm; break
            if not good: fail("SEAT", i, f"seat at {H(mp)} can't be entered ({'; '.join(why)})")
        # (a seat in the bath's water: vanilla's InvisibleChairPlayerTriple passed the entry test
        # above and was never usable: a player activates only what the crosshair hits (its mesh's collision) and what has a
        # name. NPC-only furniture, reached by package, carries "npc_only")
        if not pc.get("npc_only"):
            if not mi.get("coll"): fail("SEAT", i, "the player can't target it: its mesh has no collision")
            if not REC.get(ed, {}).get("name"): fail("SEAT", i, "the player gets no prompt: its record has no name")
    # ---- DOOR
    # (only where the record's bounds are another pose than the mesh: a hinged leaf's swung open, SSingleDoorInt01L's; a door
    # whose bounds are its mesh's, ImpDoorSingle01's stone doorway, has no other pose to test)
    ob = REC.get(ed, {}).get("obnd")
    if typ == "Door" and ob and not load and max(abs(a - b) for a, b in zip(ob, mi["box"][0] + mi["box"][1])) > 4:
        Bo = box_of(pc, ob[:3], ob[3:])
        d2, w2 = wall_depth(Bo, skip_up=True)
        if d2 > TOL: fail("DOOR", i, f"its open leaf cuts {d2:.0f} into the shell at {H(w2)}")
        for j, (pj, Bj) in enumerate(boxes):
            if j == i or Bj is None or "frame" in pj["ed"].lower(): continue
            if box_box(Bo, Bj) > TOL: fail("DOOR", i, f"its open leaf hits {pj['ed']}")

# ---- WATER: shown where a standing point sees it (a grid over the drawn floors at eye height 120, under a ceiling, as
# seal_check.py's), the sight lines over the drawn faces
DT = []
for sh in part["shapes"].values():
    for f in sh["f"]:
        for k in range(1, len(f) - 1): DT.append((sh["v"][f[0]], sh["v"][f[k]], sh["v"][f[k + 1]]))
DT = np.array(DT, float); D0, DE1, DE2 = DT[:, 0], DT[:, 1] - DT[:, 0], DT[:, 2] - DT[:, 0]; DN = np.cross(DE1, DE2)


def ray(o, dv):
    p = np.cross(dv, DE2); det = (DE1 * p).sum(1); ok = np.abs(det) > 1e-9; inv = np.where(ok, 1 / np.where(ok, det, 1), 0)
    s = o - D0; u = (s * p).sum(1) * inv; q = np.cross(s, DE1); v = (q * dv).sum(1) * inv; t_ = (q * DE2).sum(1) * inv
    m = ok & (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6) & (t_ > 0.5)
    if not m.any(): return None
    i = int(np.argmin(np.where(m, t_, np.inf))); return float(t_[i]), float(DN[i] @ dv) > 0


def standing():
    up = DN[:, 2] / np.maximum(np.linalg.norm(DN, axis=1), 1e-9) > 0.95; out = {}
    for i in np.nonzero(up)[0]:
        a, b, c = DT[i]; lo, hi = DT[i].min(0), DT[i].max(0)
        for x in np.arange(math.floor(lo[0] / 48) * 48 + 24, hi[0], 48):
            for y in np.arange(math.floor(lo[1] / 48) * 48 + 24, hi[1], 48):
                v0, v1, v2 = b - a, c - a, np.array([x, y, 0]) - a; den = v0[0] * v1[1] - v1[0] * v0[1]
                if abs(den) < 1e-9: continue
                uu = (v2[0] * v1[1] - v1[0] * v2[1]) / den; ww = (v0[0] * v2[1] - v2[0] * v0[1]) / den
                if uu < 0 or ww < 0 or uu + ww > 1: continue
                z = a[2] + uu * (b[2] - a[2]) + ww * (c[2] - a[2])
                h = ray(np.array([x, y, z + 2.0]), np.array([0, 0, 1.0]))
                if h is None or h[1] or h[0] < 130: continue
                out[(round(x), round(y), round(z))] = np.array([x, y, z + 120.0])
    return np.array(list(out.values()))
for pc in pieces:
    if not pc["model"].lower().replace("\\", "/").startswith("meshes/water/"): continue
    mi = MI.get(pc["model"].replace("\\", "/").lower(), {}); B = box_of(pc, *mi["box"])
    zw = B.z0; shown = []; EY = standing()
    for u in np.linspace(-1, 1, 33):
        for v in np.linspace(-1, 1, 33):
            q = B.c + B.ax[0] * B.half[0] * u * 0.99 + B.ax[1] * B.half[1] * v * 0.99; o = np.array([q[0], q[1], zw + 0.5])
            ds = np.linalg.norm(EY - o, axis=1)
            for k in np.argsort(ds)[:60]:
                if EY[k][2] <= o[2]: continue
                dv = (EY[k] - o) / ds[k]; h = ray(o, dv)
                if h is None or h[0] >= ds[k] - 0.5: shown.append(H([q[0], q[1], zw])); break
    if not shown: fail("WATER", -1, f"{pc['ed']}: no part of it shows"); continue
    xs, ys = [p[0] for p in shown], [p[1] for p in shown]
    note("WATER", -1, f"{pc['ed']} at z {zw:.0f}: shows over x {min(xs)}..{max(xs)}, y {min(ys)}..{max(ys)} ({len(shown)} of 1089 samples)")

name = args[0].replace("\\", "/").split("/")[-1]
print(f"PLACEMENT {name}: {len([b for b in boxes if b[1] is not None])} pieces checked, {sum(1 for b in boxes if b[1] is None)} skipped "
      f"(effects, water, tilted); {len(fails)} failures")
# --plants <regex>: pieces whose name matches are planted on purpose in and over each other and the beds (the site's flora): their
# findings print as "plant", not FAIL, and count apart (2026-11-05: the site's 1393 plant reports buried its 20 others)
PLANTS = re.compile(opt["--plants"], re.I) if "--plants" in opt else None
nplant = 0
for kind, i, msg in sorted(fails, key=lambda f: f[0]):
    pc = pieces[i] if i >= 0 else {"ed": "", "pos": [0, 0, 0], "yaw": 0}
    tag = "FAIL"
    if PLANTS and (PLANTS.search(pc["ed"]) or (kind == "PIECE" and PLANTS.search(msg.split(" at ")[0]))): tag = "plant"; nplant += 1
    print(f"  {tag} {kind:8s} {pc['ed']:32s} at {H(pc['pos'])} yaw {(pc.get('yaw', 0) + 90) % 360:.0f}: {msg}")
if PLANTS: print(f"PLANTS {nplant} of the failures are plants', not counted; {len(fails) - nplant} others")
for kind, i, msg in notes:
    if kind == "WATER" or SHOW_ALL:
        pc = pieces[i] if i >= 0 else {"ed": "", "pos": [0, 0, 0]}
        print(f"  note {kind:8s} {pc['ed']:32s} {msg}")
print("NOTES", {k: sum(1 for n in notes if n[0] == k) for k in sorted({n[0] for n in notes})})
sys.exit(1 if len(fails) - (nplant if PLANTS else 0) else 0)
