"""The culling gate (in hall2bl, looking through open doors into Room5 and the common room, their
walls and ceilings were missing: culling too aggressive, all over the guild hall). The engine
draws a room only through the portals that lead to it: from where the player stands, a sight line passes from room to room
only through a portal's opening. So from standing points in every room (a grid over the drawn floors at eye height 120,
under a ceiling, as seal_check.py's), rays in 64 directions against the shell as split by room (split_rooms.py's files),
each walked through the portals it crosses (rooms.json): the face it meets must belong to the room the ray has reached.
A face that belongs to another room is CULLED there: the player sees through where it should be.
    python portal_check.py <export dir> [--step 48]
Exits 1 on any culled face."""
import sys, os, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rooms as R

args = sys.argv[1:]; STEP = 48.0
if "--step" in args: i = args.index("--step"); STEP = float(args[i + 1]); del args[i:i + 2]
E = args[0]
parts = json.load(open(os.path.join(E, "rooms_parts.json"))); RJ = json.load(open(os.path.join(E, "rooms.json")))
tris, owner = [], []
for room, p in parts.items():
    o = p["origin"]; d = json.load(open(os.path.join(E, p["file"])))
    for sh in d["shapes"].values():
        V = [[v[k] + o[k] for k in range(3)] for v in sh["v"]]
        for f in sh["f"]:
            for k in range(1, len(f) - 1): tris.append((V[f[0]], V[f[k]], V[f[k + 1]])); owner.append(room)
T = np.array(tris, float); OWN = np.array(owner); T0, E1, E2 = T[:, 0], T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]; TN = np.cross(E1, E2)


def hit(o, dv):
    p = np.cross(dv, E2); det = (E1 * p).sum(1); ok = np.abs(det) > 1e-9; inv = np.where(ok, 1 / np.where(ok, det, 1), 0)
    s = o - T0; u = (s * p).sum(1) * inv; q = np.cross(s, E1); v = (q * dv).sum(1) * inv; t = (q * E2).sum(1) * inv
    m = ok & (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6) & (t > 0.5)
    if not m.any(): return None
    i = int(np.argmin(np.where(m, t, np.inf))); return float(t[i]), i


PORTALS = []
for p in RJ["portals"]:
    ax = p["axis"]; ua, va = p["o"]
    PORTALS.append((tuple(p["rooms"]), ax, p["plane"], ua, p["u"], va, p["v"]))


def walk(o, dv, dist, start):
    """the room a sight line reaches: through every portal opening it crosses, in order"""
    cross = []
    for rs, ax, pl, ua, ur, va, vr in PORTALS:
        if abs(dv[ax]) < 1e-9: continue
        t = (pl - o[ax]) / dv[ax]
        if not 0 < t < dist: continue
        q = o + dv * t
        if ur[0] - 1 <= q[ua] <= ur[1] + 1 and vr[0] - 1 <= q[va] <= vr[1] + 1: cross.append((t, rs))
    room = start
    for t, rs in sorted(cross):
        if room in rs: room = rs[1] if rs[0] == room else rs[0]
    return room


# standing points: up-facing drawn faces, a ceiling (front face) over them with room to stand
up = TN[:, 2] / np.maximum(np.linalg.norm(TN, axis=1), 1e-9) > 0.95; eyes = {}
for i in np.nonzero(up)[0]:
    a, b, c = T[i]; lo, hi = T[i].min(0), T[i].max(0)
    for x in np.arange(math.floor(lo[0] / STEP) * STEP + STEP / 2, hi[0], STEP):
        for y in np.arange(math.floor(lo[1] / STEP) * STEP + STEP / 2, hi[1], STEP):
            v0, v1, v2 = b - a, c - a, np.array([x, y, 0]) - a; den = v0[0] * v1[1] - v1[0] * v0[1]
            if abs(den) < 1e-9: continue
            uu = (v2[0] * v1[1] - v1[0] * v2[1]) / den; ww = (v0[0] * v2[1] - v2[0] * v0[1]) / den
            if uu < 0 or ww < 0 or uu + ww > 1: continue
            z = a[2] + uu * (b[2] - a[2]) + ww * (c[2] - a[2])
            h = hit(np.array([x, y, z + 2.0]), np.array([0, 0, 1.0]))
            if h is None or float(TN[h[1]] @ np.array([0, 0, 1.0])) > 0 or h[0] < 130: continue
            e = np.array([x, y, z + 120.0]); rs = R.room_of(list(e))
            if len(rs) == 1: eyes[(round(x), round(y), round(z))] = (e, rs[0])
n = 64; dirs = []
for k in range(n):
    zz = 1 - 2 * (k + 0.5) / n; r = math.sqrt(1 - zz * zz); a = k * math.pi * (3 - math.sqrt(5)); dirs.append(np.array([r * math.cos(a), r * math.sin(a), zz]))

bad = {}; rays = 0
for e, room in eyes.values():
    for dv in dirs:
        h = hit(e, dv)
        if h is None: continue
        rays += 1; reached = walk(e, dv, h[0], room); own = OWN[h[1]]
        if own != reached:
            q = e + dv * h[0]
            key = (room, reached, own)
            bad.setdefault(key, []).append((q, e))


def Hh(p): return [round(p[1]), round(-p[0]), round(p[2])]


print(f"PORTALS {len(eyes)} standing points in {len({r for _, r in eyes.values()})} rooms, {rays} sight lines; "
      f"{sum(len(v) for v in bad.values())} meet a face of another room than they reach")
for (room, reached, own), v in sorted(bad.items(), key=lambda kv: -len(kv[1]))[:60]:
    q, e = v[0]
    print(f"  from {room:10s} reaching {reached:10s} sees {own:10s}'s face: {len(v):4d} lines, e.g. at {Hh(q)} from {Hh(e)}")
sys.exit(1 if bad else 0)
