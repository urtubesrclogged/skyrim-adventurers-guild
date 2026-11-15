"""Is anything standing in front of a window, door, shutter or the crest? For every opening guildhall_gen.py registered
(AG_EXPORT writes hall2_checks.json), rays leave a grid of points on it, straight out along its normal, for REACH units;
anything they hit (a roof, a wall, a post, a bracket, a placed piece such as a banner) is reported with what it is and
how far. A second test looks back behind each opening: there must be wall within 4 units (a window or a shutter leaf
past the end of its wall floats). Exit 1 if anything is blocked.
    python clearance_check.py <export dir> <allforms.tsv> [--reach 60] [--all] [--site x,y,floor,yaw --map mapdata.json]
With --site and --map, a third test: the terrain in front of each opening (12 to 60 out) must stay 20 below its foot, or
the hill is up against the glass (a window half in the ground).
The hall frame: x across the front, y into the hill, z up. Placed pieces are tested as their bounding boxes."""
import sys, os, json, math
import numpy as np
a = sys.argv[1:]; ex, formsf = a[0], a[1]
REACH = float(a[a.index("--reach") + 1]) if "--reach" in a else 60.0
SHOW_ALL = "--all" in a
SITE = [float(v) for v in a[a.index("--site") + 1].split(",")] if "--site" in a else None
GROUND = None
if SITE and "--map" in a:
    import struct, base64
    M = json.load(open(a[a.index("--map") + 1])); X0, Y0, NX = M["box"][0] * 4096, M["box"][1] * 4096, M["nx"]
    HG = struct.unpack("<%dh" % (NX * M["ny"]), base64.b64decode(M["heights"])); AN = math.radians(SITE[3])
    def GROUND(hx, hy):                                   # terrain under a point of the hall frame, relative to the floor
        lx, ly = -hy, hx; wx = SITE[0] + lx * math.cos(AN) + ly * math.sin(AN); wy = SITE[1] - lx * math.sin(AN) + ly * math.cos(AN)
        fx, fy = (wx - X0) / 128, (wy - Y0) / 128; i, j = int(fx), int(fy); u, v = fx - i, fy - j
        h = lambda p_, q_: HG[q_ * NX + p_]
        return h(i, j) * (1 - u) * (1 - v) + h(i + 1, j) * u * (1 - v) + h(i, j + 1) * (1 - u) * v + h(i + 1, j + 1) * u * v - SITE[2]
H = lambda p: (p[1], -p[0], p[2])                         # layout frame (the parts) -> hall frame
tris, owner = [], []
for part in ("hall2_body", "hall2_roof", "hall2_site_1"):
    d = json.load(open(os.path.join(ex, part + ".json")))
    for key, sh in d["shapes"].items():
        V = [H(v) for v in sh["v"]]
        for f in sh["f"]:
            for i in range(1, len(f) - 1):
                tris.append((V[f[0]], V[f[i]], V[f[i + 1]])); owner.append(f"{part[6:]}:{key}")
bounds = {}
for line in open(formsf, encoding="utf-8", errors="replace"):
    f = line.rstrip("\n").split("\t")
    if len(f) > 3 and "x" in f[1]:
        bounds.setdefault(f[3].lower().replace("\\", "/").removeprefix("meshes/"), [float(v) for v in f[1].split("x")])
chk = json.load(open(os.path.join(ex, "hall2_checks.json")))
for pc in chk["pieces"]:                                    # placed pieces as boxes (bounds w x d x h, standing on pos)
    m = pc["model"].lower().removeprefix("meshes/")
    if m not in bounds or "/plants/" in m or "/trees/" in m: continue    # plants in the beds are below every sill
    if "sdoubledoorint01" in m: continue                     # a door is what fills its own doorway
    w, dd, h = (v * pc["scale"] for v in bounds[m]); x, y, z = pc["pos"]; t = math.radians(-pc["yaw"])
    if any(k in m for k in ("ivy0", "aghallcrest")): z -= h / 2          # these meshes are centred on their origin
    c, s = math.cos(t), math.sin(t)
    P = [(x + c * u - s * v, y + s * u + c * v, z + zz) for zz in (0, h) for v in (-dd / 2, dd / 2) for u in (-w / 2, w / 2)]
    for f in ((0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)):
        tris += [(P[f[0]], P[f[1]], P[f[2]]), (P[f[0]], P[f[2]], P[f[3]])]; owner += ["piece:" + os.path.basename(m)] * 2
T = np.array(tris, dtype=np.float64); V0, E1, E2 = T[:, 0], T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
def cast(O, D, tmax):
    """nearest hit (t, triangle) of each ray O + t D (0.5 < t <= tmax); Moller-Trumbore over all triangles at once"""
    out = []
    for o, d in zip(O, D):
        p = np.cross(d, E2); det = np.einsum("ij,ij->i", E1, p)
        ok = np.abs(det) > 1e-9; inv = np.where(ok, 1.0 / np.where(ok, det, 1), 0)
        tv = o - V0; u = np.einsum("ij,ij->i", tv, p) * inv
        q = np.cross(tv, E1); v = (q @ d) * inv; t = np.einsum("ij,ij->i", E2, q) * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0.5) & (t <= tmax)
        if hit.any():
            i = np.argmin(np.where(hit, t, np.inf)); out.append((float(t[i]), int(i)))
        else: out.append(None)
    return out
bad = 0; rows = []
for op in chk["openings"]:
    if op["kind"] == "crest": continue                      # the crest is a placed piece: it is tested as an obstacle
    C = np.array(op["c"], dtype=np.float64); n = np.array(op["n"], dtype=np.float64)
    if op["kind"] == "shutter": C = C + n * 3.5               # a leaf's ledges and brace stand 3 proud of its face
    ua, za = C[1] - C[0], C[3] - C[0]
    w_, h_ = np.linalg.norm(ua), np.linalg.norm(za); spring = 1 - (w_ / 2) / h_
    def on_glass(fu, fz):                                   # an arched opening: only points under its arch are glass
        if op["kind"] not in ("arched", "gothic", "fan") or fz <= spring: return True
        return ((fu - 0.5) * w_) ** 2 + ((fz - spring) * h_) ** 2 <= (w_ / 2 * 0.97) ** 2
    pts = [C[0] + ua * fu + za * fz for fu in (0.08, 0.3, 0.5, 0.7, 0.92) for fz in (0.06, 0.3, 0.55, 0.8, 0.95) if on_glass(fu, fz)]
    hits = [h for h in cast([p + n * 0.2 for p in pts], [n] * len(pts), REACH) if h]
    if op["kind"] == "shutter": back = cast([p - n * 7.7 for p in pts[::6]], [-n] * len(pts[::6]), 2.0)   # from between leaf and wall
    else: back = cast([p + n * 0.2 for p in pts[::6]], [-n] * len(pts[::6]), 4.0)
    floating = sum(1 for h in back if h is None)
    what = {}
    for t, i in hits: what[owner[i]] = min(what.get(owner[i], 1e9), t)
    buried = None
    if GROUND and abs(n[2]) < 0.3 and op["kind"] != "shutter":
        foot = min(c_[2] for c_ in C)
        worst = max(GROUND(*(C[0] + ua * fu + n * dd)[:2]) for fu in (0.1, 0.5, 0.9) for dd in (12, 36, 60))
        if worst > foot - 20: buried = f"BURIED: the ground in front reaches {round(worst)}, its foot is at {round(foot)}"
    blocked = len(hits) > 0 or floating > 0 or buried is not None
    if blocked: bad += 1
    if blocked or SHOW_ALL:
        rows.append((op["what"], buried or "", f"{len(hits)}/{len(pts)} rays blocked" if hits else "clear",
                     ", ".join(f"{k} at {round(v)}" for k, v in sorted(what.items(), key=lambda kv: kv[1])),
                     f"FLOATS ({floating} of {len(back)} points have no wall behind)" if floating else ""))
print(f"{len(chk['openings'])} openings tested against {len(tris)} triangles, reach {REACH}: {bad} blocked or floating")
# placed pieces must not stand in one another (a barrel in a chair): their boxes, shrunk 2 all round, may only touch
boxes = []
for pc in chk["pieces"]:
    m = pc["model"].lower().removeprefix("meshes/")
    if m not in bounds or any(k in m for k in ("/plants/", "/trees/", "ivy0", "aghallcrest", "sdoubledoorint01", "banner")): continue
    w, dd, h = (v * pc["scale"] for v in bounds[m]); x, y, z = pc["pos"]; t = math.radians(-pc["yaw"])
    if any(k in m for k in ("cratesmall",)): z -= h / 2
    if "barrel" in m: t = 0.0                                # round: turning it does not widen it
    c, s_ = abs(math.cos(t)), abs(math.sin(t)); hx, hy = (c * w + s_ * dd) / 2 - 2, (s_ * w + c * dd) / 2 - 2
    boxes.append((os.path.basename(m), (x - hx, x + hx, y - hy, y + hy, z + 2, z + h - 2)))
clash = []
for i in range(len(boxes)):
    for j in range(i + 1, len(boxes)):
        a_, b_ = boxes[i][1], boxes[j][1]
        if a_[0] < b_[1] and b_[0] < a_[1] and a_[2] < b_[3] and b_[2] < a_[3] and a_[4] < b_[5] and b_[4] < a_[5]:
            clash.append(f"{boxes[i][0]} at {round((a_[0] + a_[1]) / 2)},{round((a_[2] + a_[3]) / 2)} and {boxes[j][0]} at {round((b_[0] + b_[1]) / 2)},{round((b_[2] + b_[3]) / 2)}")
print(f"{len(boxes)} placed pieces tested against each other: {len(clash)} overlapping")
for c_ in clash: print("   OVERLAP", c_)
bad += len(clash)
for r in rows: print("  ", " | ".join(x for x in r if x))
sys.exit(1 if bad else 0)
