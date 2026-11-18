"""Does anything come up through a roof? Rays straight down every 3 units over the roofs: where the first thing a ray meets
is a level face of the building (a beam's top, a ledge) standing 0.5 to 30 over the roof right under it, that face has come up
through the slope. Ridge caps sit on their ridges by design: a face over a ridge (the roof falls away to both sides of it,
along x or along y) is not counted, nor a cap's last few units where it butts into the roof its ridge runs into (its end
standing its own 10 over that roof, as a ridge meets a roof). The fault this was written for: the storeys' wall plates stood 10 proud of the wall at
the top of the wall, where the roof's top meets it, and so came up through every eave by 10 * tan(pitch) (8-14 units: a dark
line along the eaves under snow).
    blender -b -P roof_poke_check.py -- <export dir>        a FAIL line for each face, exit 1 on any"""
import sys, os, json
from mathutils import Vector
from mathutils.bvhtree import BVHTree
a = sys.argv[sys.argv.index("--") + 1:]; ex = a[0]
H = lambda p: Vector((p[1], -p[0], p[2]))                      # layout frame (the parts) -> hall frame
SKIP = ("glead", "gpane", "gcoat", "crest3d", "metal", "moss", "mosswall")   # glass, the crest, ironwork, decals: not the frame

def faces(part, keys=None):
    d = json.load(open(os.path.join(ex, part + ".json"))); V, F, K = [], [], []
    for k, sh in d["shapes"].items():
        if keys is not None and k not in keys: continue
        if k in SKIP: continue
        for f in sh["f"]:
            b0 = len(V); V += [H(sh["v"][i]) for i in f]; F.append(list(range(b0, b0 + len(f)))); K.append(k)
    return V, F, K

RV, RF, _ = faces("hall2_roof", ("roof",))
BV, BF, BK = faces("hall2_body")
if not RF or not BF: print("FAIL ROOF POKE read nothing:", len(RF), "roof faces,", len(BF), "body faces"); sys.exit(1)
R = BVHTree.FromPolygons(RV, RF); B = BVHTree.FromPolygons(BV, BF)
DOWN = Vector((0, 0, -1))
def roof_z(x, y):
    h = R.ray_cast(Vector((x, y, 9000.0)), DOWN, 20000.0)
    return h[0].z if h[0] is not None else None
xs = [v.x for v in RV]; ys = [v.y for v in RV]
STEP, OX, OY = 3.0, 0.37, 0.71
found, rays = {}, 0
i = int((min(xs) - OX) // STEP)
while i * STEP + OX <= max(xs):
    x = i * STEP + OX; i += 1
    j = int((min(ys) - OY) // STEP)
    while j * STEP + OY <= max(ys):
        y = j * STEP + OY; j += 1
        hr = R.ray_cast(Vector((x, y, 9000.0)), DOWN, 20000.0)
        if hr[0] is None: continue
        rays += 1
        hb = B.ray_cast(Vector((x, y, 9000.0)), DOWN, 20000.0)
        if hb[0] is None: continue
        d = hb[0].z - hr[0].z
        if not (0.5 < d < 30) or hb[1].z < 0.9: continue       # a level face, a little over the roof under it
        P = [BV[k] for k in BF[hb[2]]]
        if max(p.z for p in P) - min(p.z for p in P) > 2: continue
        ridge = False                                          # the roof across it, -24..24 along x and along y: highest inside
        for ux, uy in ((1, 0), (0, 1)):
            zs = [roof_z(x + ux * t, y + uy * t) for t in range(-24, 25, 4)]
            if None in zs: continue
            m = max(zs)
            if zs[0] < m - 0.5 and zs[-1] < m - 0.5: ridge = True
        if ridge: continue
        fx0, fx1 = min(p.x for p in P), max(p.x for p in P); fy0, fy1 = min(p.y for p in P), max(p.y for p in P)
        if d <= 12.5 and ((fx1 - fx0 <= 22 and fy1 - fy0 >= 60 and min(y - fy0, fy1 - y) < 4) or
                          (fy1 - fy0 <= 22 and fx1 - fx0 >= 60 and min(x - fx0, fx1 - x) < 4)):
            continue                                           # a ridge cap's end, butting into the roof its ridge runs into
        key =(BK[hb[2]], round(min(p.x for p in P)), round(max(p.x for p in P)), round(min(p.y for p in P)), round(max(p.y for p in P)), round(P[0].z))
        c = found.setdefault(key, [0, 0.0]); c[0] += 1; c[1] = max(c[1], d)
for (k, x0, x1, y0, y1, z), (n, d) in sorted(found.items(), key=lambda kv: -kv[1][1]):
    print(f"FAIL ROOF POKE {k} x {x0}..{x1} y {y0}..{y1} top {z}: up to {d:.0f} over the roof under it")
print("ROOF POKE", rays, "rays over the roofs,", len(found), "face(s) through a roof")
sys.exit(1 if found else 0)
