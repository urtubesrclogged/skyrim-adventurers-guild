"""A decal must lie on something: every point of a moss decal that shows (vertex alpha above the cut) has to have a
surface of the hall, the site or the terrain right behind it (within 2 units along the decal's own normal). A point
with nothing behind it hangs in the air (seen 2026-10-24: a ribbon laid past the terrace's back edge stuck out from the
wall top, flat, invisible from below).
    python decal_support_check.py <export dir> --site x,y,floor,yaw --map mapdata.json
Prints hall-frame positions (x across the front, y negative in front, z from the floor). Exit 1 on any unsupported point."""
import sys, os, json, math, struct, base64
import numpy as np
args = sys.argv[1:]; opt = {}
for k in ("--site", "--map"):
    if k in args: i = args.index(k); opt[k] = args[i + 1]; del args[i:i + 2]
d = args[0]
tris, dec = [], []                                       # (a, b, c) layout frame; decal points (p, n, alpha, key)
for fn in ("hall2_body.json", "hall2_roof.json", "hall2_site_1.json"):
    j = json.load(open(os.path.join(d, fn)))
    for key, sh in j["shapes"].items():
        V = sh["v"]
        for fi, f in enumerate(sh["f"]):
            P = [V[i] for i in f]
            if key in ("moss", "mosswall", "wearcrack", "wearstain", "spill"):
                a = [P[1][k] - P[0][k] for k in range(3)]; b = [P[2][k] - P[0][k] for k in range(3)]
                n = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
                L = math.sqrt(sum(c * c for c in n)) or 1.0; n = [c / L for c in n]
                al = sh["a"][fi]
                cen = [sum(p[m] for p in P) / len(P) for m in range(3)]
                for p, aa in zip(P, al):                     # 1.5 inside the quad: a corner on a tread's nosing line
                    dv = [cen[m] - p[m] for m in range(3)]; dl = math.sqrt(sum(c * c for c in dv)) or 1.0
                    dec.append(([p[m] + dv[m] * min(1.0, 1.5 / dl) for m in range(3)], n, aa, key))   # grazes the edge
                dec.append((cen, n, sum(al) / len(al), key))
                continue
            for k in range(1, len(P) - 1): tris.append((P[0], P[k], P[k + 1]))
if "--site" in opt:                                      # the terrain round the hall, as triangles (layout frame)
    SITE = [float(v) for v in opt["--site"].split(",")]; M = json.load(open(opt["--map"]))
    X0, Y0, NX, NY = M["box"][0] * 4096, M["box"][1] * 4096, M["nx"], M["ny"]
    H = struct.unpack("<%dh" % (NX * NY), base64.b64decode(M["heights"])); A_ = math.radians(SITE[3])
    def ground(lx, ly):
        wx, wy = SITE[0] + lx * math.cos(A_) + ly * math.sin(A_), SITE[1] - lx * math.sin(A_) + ly * math.cos(A_)
        fx, fy = (wx - X0) / 128, (wy - Y0) / 128; i, j = int(fx), int(fy); u, v = fx - i, fy - j
        h = lambda a, b: H[b * NX + a]
        return h(i, j) * (1 - u) * (1 - v) + h(i + 1, j) * u * (1 - v) + h(i, j + 1) * (1 - u) * v + h(i + 1, j + 1) * u * v - SITE[2]
    xs = list(range(-2600, 2601, 48)); ys = list(range(-2600, 2601, 48))
    G = {(x, y): ground(x, y) for x in xs for y in ys}
    for x0, x1 in zip(xs, xs[1:]):
        for y0, y1 in zip(ys, ys[1:]):
            a, b, c, e = (x0, y0, G[(x0, y0)]), (x1, y0, G[(x1, y0)]), (x1, y1, G[(x1, y1)]), (x0, y1, G[(x0, y1)])
            tris += [(a, b, c), (a, c, e)]
T0 = np.array([t[0] for t in tris], float); E1 = np.array([t[1] for t in tris], float) - T0; E2 = np.array([t[2] for t in tris], float) - T0
def hit(o, dv, far):
    p = np.cross(dv, E2); det = (E1 * p).sum(1); ok = np.abs(det) > 1e-9; inv = np.where(ok, 1 / np.where(ok, det, 1), 0)
    s = o - T0; u = (s * p).sum(1) * inv; q = np.cross(s, E1); v = (q * dv).sum(1) * inv; t = (q * E2).sum(1) * inv
    m = ok & (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6) & (t > -1e-3) & (t < far)
    return m.any()
CUT = 19 / 255.0
bad, n_seen = [], 0
for p, n, aa, key in dec:
    if aa <= CUT: continue                               # cut away by the alpha test: never drawn
    n_seen += 1
    o = np.array(p, float) + np.array(n) * 1.0           # from 1 in front of the decal, back through it
    if not hit(o, -np.array(n, float), 3.0): bad.append((key, [round(p[1]), round(-p[0]), round(p[2], 1)], round(aa, 2)))
print(n_seen, "decal points that show:", len(bad), "with nothing behind them (material, hall x y z, alpha)")
for b in bad[:40]: print("  ", b)
sys.exit(1 if bad else 0)
