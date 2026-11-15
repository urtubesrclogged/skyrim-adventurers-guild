"""The seal gate (2026-10-28: the basement's prison cell, its east wall stopping at 1060 with the cell running to 1260, open on
nothing; no check saw it). From standing points over every floor of an exported part (its collision's upward faces, every
48, at eye height), rays in 64 directions against the shell as drawn: one that meets nothing leaves the cell, one whose first
face is seen from behind looks through a face Skyrim draws one-sided. Either is a hole. Reports each hole once per 64-unit
cell of where the ray leaves, with the standing points that see it.
    python seal_check.py <part.json> [--eye 120] [--step 48]
Exits 1 on any hole."""
import sys, json, math
import numpy as np

args = sys.argv[1:]; opt = {}
for k in ("--eye", "--step"):
    if k in args: i = args.index(k); opt[k] = float(args[i + 1]); del args[i:i + 2]
EYE, STEP = opt.get("--eye", 120.0), opt.get("--step", 48.0)
d = json.load(open(args[0]))

tris = []
for key, sh in d["shapes"].items():
    V = sh["v"]
    for f in sh["f"]:
        for k in range(1, len(f) - 1): tris.append((V[f[0]], V[f[k]], V[f[k + 1]]))
T = np.array(tris, float); T0, E1, E2 = T[:, 0], T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]; TN = np.cross(E1, E2)

# the floors: the drawn faces looking up (their winding is how Skyrim culls them, so it is right; the collision's is not)
Ln = np.linalg.norm(TN, axis=1); up = (Ln > 1e-9) & (TN[:, 2] / np.maximum(Ln, 1e-9) > 0.95); C = T


def first_hit(o, dv):
    p = np.cross(dv, E2); det = (E1 * p).sum(1); ok = np.abs(det) > 1e-9; inv = np.where(ok, 1 / np.where(ok, det, 1), 0)
    s = o - T0; u = (s * p).sum(1) * inv; q = np.cross(s, E1); v = (q * dv).sum(1) * inv; t = (q * E2).sum(1) * inv
    m = ok & (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6) & (t > 0.5)
    if not m.any(): return None
    i = int(np.argmin(np.where(m, t, np.inf))); return float(t[i]), float(TN[i] @ dv) > 0


# the standing points: a grid over the floors' faces, kept where a ceiling faces down over them with room to stand
eyes = []
for i in np.nonzero(up)[0]:
    a, b, c = C[i]; lo, hi = C[i].min(0), C[i].max(0)
    for x in np.arange(math.floor(lo[0] / STEP) * STEP + STEP / 2, hi[0], STEP):
        for y in np.arange(math.floor(lo[1] / STEP) * STEP + STEP / 2, hi[1], STEP):
            v0, v1, v2 = b - a, c - a, np.array([x, y, 0]) - a
            den = v0[0] * v1[1] - v1[0] * v0[1]
            if abs(den) < 1e-9: continue
            uu = (v2[0] * v1[1] - v1[0] * v2[1]) / den; ww = (v0[0] * v2[1] - v2[0] * v0[1]) / den
            if uu < 0 or ww < 0 or uu + ww > 1: continue
            z = a[2] + uu * (b[2] - a[2]) + ww * (c[2] - a[2])
            o = np.array([x, y, z + EYE])
            h = first_hit(np.array([x, y, z + 2.0]), np.array([0, 0, 1.0]))    # a floor someone stands on has a ceiling over it,
            if h is None or h[1] or h[0] < EYE + 10: continue                    # and room to stand (not inside a solid)
            eyes.append(o)
eyes = list({(round(e[0]), round(e[1]), round(e[2])): e for e in eyes}.values())

n = 64; dirs = []
for k in range(n):                                       # a Fibonacci sphere
    z = 1 - 2 * (k + 0.5) / n; r = math.sqrt(1 - z * z); a = k * math.pi * (3 - math.sqrt(5))
    dirs.append(np.array([r * math.cos(a), r * math.sin(a), z]))
holes = {}
for o in eyes:
    for dv in dirs:
        h = first_hit(o, dv)
        if h is None: where, why = o + dv * 400, "leaves"
        elif h[1]: where, why = o + dv * h[0], "back face"
        else: continue
        key = (why, int(where[0] // 64), int(where[1] // 64), int(where[2] // 64))
        holes.setdefault(key, []).append(o)


def H(p): return [round(p[1]), round(-p[0]), round(p[2])]   # the cell's frame to the hall's (x right, y back)


name = args[0].replace("\\", "/").split("/")[-1]
print(f"SEAL {name}: {len(eyes)} standing points, {len(eyes) * n} rays; {len(holes)} holes")
for (why, *_), seen in sorted(holes.items(), key=lambda kv: -len(kv[1]))[:40]:
    k = next(k for k, v in holes.items() if v is seen)
    print(f"  HOLE ({why}) near {H([k[1] * 64 + 32, k[2] * 64 + 32, k[3] * 64 + 32])}: seen from {len(seen)} rays, e.g. from {H(seen[0])}")
sys.exit(1 if holes else 0)
