"""Is every roof whole? Over each roof's own plan (gable_roof, abut_gable_roof and pyramid record it in
hall2_checks.json "roofs"), rays come straight down every 2 units: the first thing each meets must stand at or above
that roof's eave (the roof, a dormer, the tower, a chimney), never what is under it. A ray that reaches a wall top, a
jetty, the patio or the ground has gone through a hole. The holes this was written for: where a wing's eave was stopped
for a cross gable or the porch and the gable's valley ran below the wall line, sky showed through from below
(2026-10-24, seen on the SE and the VR test installs).
    blender -b -P roof_cover_check.py -- <export dir>        exit 1 on any hole of 2 rays or more"""
import sys, os, json
from mathutils import Vector
from mathutils.bvhtree import BVHTree
a = sys.argv[sys.argv.index("--") + 1:]; ex = a[0]
H = lambda p: Vector((p[1], -p[0], p[2]))                      # layout frame (the parts) -> hall frame
V, F = [], []
for part in ("hall2_body", "hall2_roof", "hall2_site_1"):
    d = json.load(open(os.path.join(ex, part + ".json")))
    for key, sh in d["shapes"].items():
        if key in ("moss", "mosswall"): continue               # decals: a hole they cover is still a hole
        for f in sh["f"]:
            b0 = len(V); V += [H(sh["v"][i]) for i in f]; F.append(list(range(b0, b0 + len(f))))
bvh = BVHTree.FromPolygons(V, F)
roofs = json.load(open(os.path.join(ex, "hall2_checks.json")))["roofs"]

def inside(x, y, pg):                                          # even-odd rule
    c = False
    for (x0, y0), (x1, y1) in zip(pg, pg[1:] + pg[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0): c = not c
    return c

STEP, OX, OY = 2.0, 0.37, 0.71                                 # one grid for every roof (off the round numbers edges sit on)
bad, rays = {}, 0                                              # (i, j) -> (x, y, what the ray met first, roof's eave)
for r in roofs:
    pg, zl = [tuple(q) for q in r["plan"]], r["z"]
    xs, ys = [q[0] for q in pg], [q[1] for q in pg]
    for i in range(int((min(xs) - OX) // STEP), int((max(xs) - OX) // STEP) + 2):
        for j in range(int((min(ys) - OY) // STEP), int((max(ys) - OY) // STEP) + 2):
            x, y = i * STEP + OX, j * STEP + OY
            if not inside(x, y, pg): continue
            rays += 1
            hit = bvh.ray_cast(Vector((x, y, 9000.0)), Vector((0, 0, -1)), 20000.0)
            z = hit[0].z if hit[0] is not None else None
            if z is None or z < zl - 20: bad.setdefault((i, j), (x, y, z, zl))

spots, seen = [], set()                                        # neighbouring misses make one hole
for k in bad:
    if k in seen: continue
    todo, spot = [k], []
    seen.add(k)
    while todo:
        c = todo.pop(); spot.append(c)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                n = (c[0] + di, c[1] + dj)
                if n in bad and n not in seen: seen.add(n); todo.append(n)
    spots.append(spot)
holes = [s for s in spots if len(s) >= 2]
for s in sorted(holes, key=len, reverse=True):
    P = [bad[c] for c in s]
    zs = [p[2] for p in P if p[2] is not None]
    print("HOLE", len(s), "rays", f"~{4 * len(s)} sq units", "x", round(min(p[0] for p in P)), "-", round(max(p[0] for p in P)),
          "y", round(min(p[1] for p in P)), "-", round(max(p[1] for p in P)), "| roof eave", round(P[0][3]),
          "| rays met", f"z {round(min(zs))}-{round(max(zs))}" if zs else "nothing", "" if len(zs) == len(P) else "(some nothing)")
singles = [s for s in spots if len(s) == 1]
if singles: print("single misses (a ray through a seam, or a hole under 4 sq units):", [tuple(round(v) for v in bad[s[0]][:2]) for s in singles])
print("ROOF CHECK", len(roofs), "roofs,", rays, "rays,", len(holes), "hole(s)")
sys.exit(1 if holes else 0)
