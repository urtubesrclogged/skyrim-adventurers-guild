"""Where can the terrain or its grass come up through a walking surface? Samples the up-facing faces of the given shapes
of an exported part (guildhall_gen.py AG_EXPORT JSON, layout frame) every STEP units and compares them with the terrain
(mapdata) and with the grass that grows there.
What grows where: the grass map (LandGrid.cs, hall frame, 64-unit cells, each texture's weight in "texs") and the grass
heights (grass_heights.json: per landscape texture its GRAS records with slope band, density and mesh top). A grass counts
where its texture weighs >= 0.2 at one of the four cells around the point and the terrain's slope there is inside its
band; its height is the mesh top x (1 + height range). Grasses thinner than density 10 are reported apart ("rare").
The engine uses only the first iMaxGrassTypesPerTexure grasses of each texture's list (--types; 3 on the SE test install, 16 on the VR one).
--interp blends the texture weights at the point itself instead of taking the grassiest of the four cells around it.
Without --heights, every grass-growing cell (summed weight >= 0.3) needs --clear units (default 80).
    python grass_check.py <part.json> <grass.json> <x,y,floor,yaw> <mapdata.json> [shapes, default steps,floor]
                          [--heights grass_heights.json] [--types N] [--interp] [--clear 80] [--top N] [--grid 100]
--grid N reports the worst point of every N x N area (hall frame) instead of every face: one big paving face can hold a
visible walk AND hidden paving under the building, and per face only its worst point (often the hidden one) is shown."""
import sys, json, math, struct, base64
a = sys.argv[1:]; opt = {}
INTERP = "--interp" in a; a = [x for x in a if x != "--interp"]
for k in ("--clear", "--heights", "--top", "--types", "--grid"):
    if k in a: i = a.index(k); opt[k] = a[i + 1]; del a[i:i + 2]
CLEAR = float(opt.get("--clear", 80)); TOP = int(opt.get("--top", 60)); TYPES = int(opt.get("--types", 99)); GRID = float(opt.get("--grid", 0))
AREAS = {}
part, grassf, site, mapf = a[:4]; SHAPES = (a[4] if len(a) > 4 else "steps,floor").split(",")
STEP, WMIN, DMIN = 16.0, 0.2, 10
SITE = [float(v) for v in site.split(",")]; M = json.load(open(mapf))
X0, Y0, NX = M["box"][0] * 4096, M["box"][1] * 4096, M["nx"]
H = struct.unpack("<%dh" % (NX * M["ny"]), base64.b64decode(M["heights"])); A = math.radians(SITE[3])
def ground_w(wx, wy):
    fx, fy = (wx - X0) / 128, (wy - Y0) / 128; i, j = int(fx), int(fy); u, v = fx - i, fy - j
    h = lambda p, q: H[q * NX + p]
    return h(i, j) * (1 - u) * (1 - v) + h(i + 1, j) * u * (1 - v) + h(i, j + 1) * (1 - u) * v + h(i + 1, j + 1) * u * v - SITE[2]
def to_w(lx, ly): return SITE[0] + lx * math.cos(A) + ly * math.sin(A), SITE[1] - lx * math.sin(A) + ly * math.cos(A)
def ground_l(lx, ly): return ground_w(*to_w(lx, ly))
def slope_l(lx, ly):
    wx, wy = to_w(lx, ly); d = 64.0
    gx = (ground_w(wx + d, wy) - ground_w(wx - d, wy)) / (2 * d); gy = (ground_w(wx, wy + d) - ground_w(wx, wy - d)) / (2 * d)
    return math.degrees(math.atan(math.hypot(gx, gy)))
G = json.load(open(grassf)); CELLS = {(round(c["x"]), round(c["y"])): c for c in G["cells"]}
gx0 = min(c["x"] for c in G["cells"]); gy0 = min(c["y"] for c in G["cells"])
HT = json.load(open(opt["--heights"])) if "--heights" in opt else None
def around(hx, hy):
    i, j = math.floor((hx - gx0) / 64), math.floor((hy - gy0) / 64)
    return [c for c in (CELLS.get((round(gx0 + (i + di) * 64), round(gy0 + (j + dj) * 64))) for di in (0, 1) for dj in (0, 1)) if c]
def blended(hx, hy):
    """the texture weights at the point itself, blended from the four cells around it (the engine blends between vertices)"""
    i, j = math.floor((hx - gx0) / 64), math.floor((hy - gy0) / 64); fu, fv = (hx - gx0) / 64 - i, (hy - gy0) / 64 - j
    w = {}
    for di, dj, k in ((0, 0, (1 - fu) * (1 - fv)), (1, 0, fu * (1 - fv)), (0, 1, (1 - fu) * fv), (1, 1, fu * fv)):
        c = CELLS.get((round(gx0 + (i + di) * 64), round(gy0 + (j + dj) * 64)))
        if c:
            for t, wt in c.get("texs", []): w[t] = w.get(t, 0) + wt * k
    return {"texs": list(w.items())}
def need_at(hx, hy, sl):
    """(the tallest common grass, the tallest rare one, what it is) that can grow at a point of the hall frame"""
    cs = [blended(hx, hy)] if INTERP else around(hx, hy)
    if not cs or not cs[0]["texs"]: return None
    if HT is None:
        return (CLEAR if max(c["grass"] for c in cs) >= 0.3 else 0), 0, ""
    best, rare, what = 0.0, 0.0, ""
    for c in cs:
        for t, w in c.get("texs", []):
            if w < WMIN: continue
            for gr in HT.get(t, [])[:TYPES]:
                if gr["top"] is None or not gr["slope"][0] <= sl <= gr["slope"][1]: continue
                h = gr["top"] * (1 + gr["hr"])
                if gr["density"] >= DMIN:
                    if h > best: best, what = h, f"{gr['ed']} on {t}"
                elif h > rare: rare = h
    return best, rare, what
def inside(p, P):
    s = None
    for k in range(len(P)):
        a_, b_ = P[k], P[(k + 1) % len(P)]
        c = (b_[0] - a_[0]) * (p[1] - a_[1]) - (b_[1] - a_[1]) * (p[0] - a_[0])
        if abs(c) < 1e-9: continue
        if s is None: s = c > 0
        elif (c > 0) != s: return False
    return True
d = json.load(open(part)); rows = []; nofield = 0; nrare = 0
for key in SHAPES:
    sh = d["shapes"].get(key)
    if not sh: continue
    V = sh["v"]
    for f in sh["f"]:
        P = [V[i] for i in f]
        ax = [P[1][k] - P[0][k] for k in range(3)]; bx = [P[2][k] - P[0][k] for k in range(3)]
        nz = ax[0] * bx[1] - ax[1] * bx[0]; L = math.sqrt(sum(c * c for c in (ax[1] * bx[2] - ax[2] * bx[1], ax[2] * bx[0] - ax[0] * bx[2], nz)))
        if L < 1e-9 or nz / L < 0.99: continue                       # up-facing, level only
        z = sum(p[2] for p in P) / len(P)
        xs, ys = [p[0] for p in P], [p[1] for p in P]
        worst = None; rare_short = 0
        x = min(xs) + STEP / 2
        while x < max(xs):
            y = min(ys) + STEP / 2
            while y < max(ys):
                if inside((x, y), P):
                    g = ground_l(x, y); hx, hy = y, -x                                # layout -> hall
                    sl = slope_l(x, y); n = need_at(hx, hy, sl)
                    if n is None: nofield += 1; n = (0, 0, "")
                    short = (g + n[0]) - z                                            # > 0: something comes through
                    rare_short = max(rare_short, (g + n[1]) - z)
                    if worst is None or short > worst[0]: worst = (round(short), round(hx), round(hy), round(z), round(g), round(sl), n[2])
                    if GRID and short > 0:
                        ak = (key, math.floor(hx / GRID), math.floor(hy / GRID))
                        if ak not in AREAS or short > AREAS[ak][1]: AREAS[ak] = (key, round(short), round(hx), round(hy), round(z), round(g), round(sl), n[2])
                y += STEP
            x += STEP
        if worst and worst[0] > 0: rows.append((key,) + worst)
        elif rare_short > 0: nrare += 1
if GRID: rows = list(AREAS.values())
rows.sort(key=lambda r: -r[1])
print(len(rows), "walking faces where terrain or common grass comes through;", nrare, "more where only a rare plant (density < 10) can;",
      nofield, "sample points outside the grass map")
print("   (shape, by how much, hall x, y, surface z, ground z, slope deg, tallest grass there)")
for r in rows[:TOP]: print("  ", r)
