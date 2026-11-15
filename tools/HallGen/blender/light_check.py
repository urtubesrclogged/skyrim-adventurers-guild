"""Are a cell's lights placed for its rooms? (light placement judged for realism and for how well each room is lit.)
For each room given, on a 32 grid of its floor: how much lies within reach (0.75 of a light's radius, on that level), the worst
dark spot, and how the fixtures sit: bunched (closest pair under a quarter of the room's long side) or not. A light with no
fixture near it is named: a lit fixture has to answer for each one.
    python light_check.py <hall2_part.json> [--rooms name:x0,y0,x1,y1,floorz ...]     exit 1 on any FAIL"""
import json, math, sys
BASE = {"lamp": 512, "fire_small": 512, "fire": 768, "candle": 128, "candle_small": 128, "candle_night": 128, "window": 250, "bounce": 500}
FIX = ("candle", "lantern", "sconce", "chandel", "brazier", "fxfire", "fireplace", "torch", "cookingfire")
a = sys.argv[1:]; path = a[0]; d = json.load(open(path)); rooms = []; allow = []
if "--allow" in a:                                    # a light left without a fixture of its own, said why at the call: x,y
    i = a.index("--allow"); allow = [tuple(map(float, v.split(","))) for v in a[i + 1].split(";")]; del a[i:i + 2]
if "--rooms" in a:
    for r in a[a.index("--rooms") + 1:]:
        n, v = r.split(":"); x0, y0, x1, y1, z = map(float, v.split(",")); rooms.append((n, x0, y0, x1, y1, z))
H = lambda p: (p[1], -p[0], p[2])
fx = [H(p["pos"]) for p in d["pieces"] if any(k in (str(p.get("ed") or "") + p["model"]).lower() for k in FIX)]
ls = []
for l in d["lights"]:
    if len(l) < 4: continue
    x, y, z = H(l[0]); k = l[3]; r = BASE.get(k, 128) + (l[4] if len(l) > 4 else 0); ls.append((x, y, z, r, k))
bad = 0
for x, y, z, r, k in ls:
    if k in ("window", "bounce"): continue           # (a window's daylight has the window for its fixture; bounce light is that same daylight, deep in the room: an accepted exception)
    near = min((math.dist((x, y, z), f) for f in fx), default=1e9)
    under = any(math.hypot(x - f[0], y - f[1]) <= 60 and abs(z - f[2]) <= 180 for f in fx)   # (a room's light hangs under its fixture, to reach the floor)
    if near > (140 if k.startswith("fire") else 90) and not under and not any(math.hypot(x - q[0], y - q[1]) < 5 for q in allow):
        print(f"FAIL FIXTURE  {k} r{r:.0f} at ({x:.0f}, {y:.0f}, {z:.0f}): nearest fixture {near:.0f} away"); bad += 1
# rule 5's other half (a white-out in the tavern, a candle under a window adding to its daylight): lights
# that pile up on one patch of wall: within 130 of each other, windows' daylight fills too, are reported as stacked
every = ls   # (a light with no kind is the renders' only: it never reaches the game)
for i, p in enumerate(every):
    for q in every[i + 1:]:
        g = math.dist(p[:3], q[:3])
        kinds_ = {p[4], q[4]}
        if "bounce" in kinds_: continue                                   # (mid-room, on no patch of wall)
        if "candle_night" in kinds_ and "window" in kinds_: continue      # (the candle's region is black by day, when the fill is bright; by night the fill is a dim blue)
        if kinds_ & {"lamp", "fire", "fire_small"} and kinds_ & {"candle", "candle_small", "candle_night"}: continue   # (a candle on a desk under a room's own light)
        # (2026-11-06: the cellar's sconce and Henriette's, back to back on the wall between their rooms, 101 apart: one lights each
        # room, a wall between; two lights in two of the rooms given are never one patch of wall)
        rp_ = [n_ for n_, x0_, y0_, x1_, y1_, _ in rooms if x0_ - 40 <= p[0] <= x1_ + 40 and y0_ - 40 <= p[1] <= y1_ + 40]
        rq_ = [n_ for n_, x0_, y0_, x1_, y1_, _ in rooms if x0_ - 40 <= q[0] <= x1_ + 40 and y0_ - 40 <= q[1] <= y1_ + 40]
        if rp_ and rq_ and not set(rp_) & set(rq_) and len(rp_) == 1 and len(rq_) == 1: continue
        if g < 130: print(f"FAIL STACKED  {p[4]} ({p[0]:.0f}, {p[1]:.0f}, {p[2]:.0f}) and {q[4]} ({q[0]:.0f}, {q[1]:.0f}, {q[2]:.0f}): {g:.0f} apart"); bad += 1
for n, x0, y0, x1, y1, fz in rooms:
    here = [(x, y, z, r) for x, y, z, r, k in ls if x0 - 40 <= x <= x1 + 40 and y0 - 40 <= y <= y1 + 40 and fz - 40 <= z <= fz + 330]
    tot = lit = 0; worst = (0, None); yy = y0 + 16
    while yy < y1:
        xx = x0 + 16
        while xx < x1:
            tot += 1
            gap = min((math.hypot(x - xx, y - yy) - 0.75 * math.sqrt(max(0, r * r - (z - fz - 60) ** 2)) for x, y, z, r in here), default=1e9)
            lit += gap <= 0
            if gap > worst[0]: worst = (gap, (round(xx), round(yy)))
            xx += 32
        yy += 32
    side = max(x1 - x0, y1 - y0); pts = [(x, y) for x, y, z, r in here if r > 128]   # (bunched is of a room's main lights: table candles are not)
    close = min((math.dist(p, q) for i, p in enumerate(pts) for q in pts[i + 1:]), default=None)
    bunched = close is not None and close < side / 4
    cov = 100 * lit / max(1, tot); ok = cov >= 75 and not bunched
    print(f"{'ok  ' if ok else 'FAIL'} ROOM {n:18} {len(here)} lights, {cov:3.0f}% of the floor in reach, worst gap {worst[0] if here else 0:4.0f} at {worst[1]}, closest pair {close and round(close)}{' BUNCHED' if bunched else ''}")
    bad += not ok
print("LIGHTS", path.replace(chr(92), "/").split("/")[-1], len(ls), "lights,", bad, "failures"); sys.exit(1 if bad else 0)
