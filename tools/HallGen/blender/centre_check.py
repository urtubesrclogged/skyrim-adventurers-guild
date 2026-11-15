"""Is a wall fixture centred on its panel? (one sconce sat misaligned on its wall, another pushed to the side instead of
centred.) For every sconce and wall lantern: along its wall, at its height and just off the wall, how far each way to what stands proud of it (a post, a frame,
a corner). Fixed by the mesh's own turn: a sconce's plate lies along its local y. Reported when the plate runs into what stands beside it, or sits off its panel's
middle by more than --off on a panel under --panel wide (on a long wall nothing asks for a middle).
    python centre_check.py <part.json> --mesh <mesh_info.json> [--off 10] [--panel 320]     exit 1 on any"""
import json, math, sys
import numpy as np
a = sys.argv[1:]
def opt(k, d):
    if k in a: i = a.index(k); v = a[i + 1]; del a[i:i + 2]; return v
    return d
MI = json.load(open(opt("--mesh", None))); OFF = float(opt("--off", 10)); PANEL = float(opt("--panel", 320))
part = json.load(open(a[0])); H = lambda p: (p[1], -p[0], p[2])
T = np.array([[H(p) for p in t] for t in part["coll"]], float)
E1, E2 = T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
def ray(o, d, far=400):
    """the nearest face along o + t d, 0 < t < far"""
    h = np.cross(d, E2); det = np.einsum("ij,ij->i", E1, h); ok = np.abs(det) > 1e-9
    e1, e2, a0, h, det = E1[ok], E2[ok], T[ok, 0], h[ok], det[ok]
    s = o - a0; u = np.einsum("ij,ij->i", s, h) / det; q = np.cross(s, e1)
    v = np.einsum("j,ij->i", d, q) / det; t = np.einsum("ij,ij->i", e2, q) / det
    m = (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6) & (t > 0.5) & (t < far)
    return float(t[m].min()) if m.any() else None
bad = n = 0
for p in part["pieces"]:
    m = p["model"].lower().replace(chr(92), "/")
    if not ("sconce" in m or "walllantern" in m) or "candlehorn" in m: continue
    mi = MI.get(m)
    if not mi or not mi.get("box"): continue
    (x0, y0, z0), (x1, y1, z1) = mi["box"]; hw = (y1 - y0) / 2
    if hw < 20: continue                                  # (a single candle's bracket has no plate to centre)
    n += 1; x, y, z = H(p["pos"]); a_ = math.radians(p["yaw"] + 90)
    ex, ey = np.array((math.cos(a_), -math.sin(a_), 0)), np.array((math.sin(a_), math.cos(a_), 0))
    o = np.array((x, y, z)) + ex * -6                     # (its plate's on local x 0, the room toward -x)
    l, r = ray(o, ey), ray(o, -ey)
    if l is None or r is None: print(f"  --   {p.get('ed') or m.split('/')[-1]} at {[round(v) for v in (x, y, z)]}: {l} / {r}: open on a side"); continue
    w = l + r; off = abs(l - r) / 2
    fault = "runs into what stands beside it" if min(l, r) < hw else (f"{off:.0f} off the middle of a {w:.0f} panel" if off > OFF and w < PANEL else "")
    if fault:
        c_ = np.array((x, y, z)) + ey * (l - r) / 2
        print(f"  FAIL CENTRE {p.get('ed') or m.split('/')[-1]} at {[round(v) for v in (x, y, z)]}: {l:.0f} one way, {r:.0f} the other: {fault}; its middle ({c_[0]:.0f}, {c_[1]:.0f})"); bad += 1
# (the dragon skull must be mounted, not floating) a wall mount's back on its wall: its plate's back at local y, from the mesh, within 4 of a face
MOUNTS = {"wrdragonskullmounted01": -20.0}
for p in part["pieces"]:
    k = p["model"].lower().replace(chr(92), "/").split("/")[-1].replace(".nif", "")
    if k not in MOUNTS: continue
    n += 1; x, y, z = H(p["pos"]); a_ = math.radians(p["yaw"] + 90); s_ = p.get("scale", 1.0)
    ey = np.array((math.sin(a_), math.cos(a_), 0)); back = -ey; t_ = ray(np.array((x, y, z)), back, 200); want = -MOUNTS[k] * s_
    if t_ is None or abs(t_ - want) > 12:   # (within a rail's depth: the tavern's stands on the wall's timbers, 10 proud of the plaster)
        print(f"  FAIL MOUNT  {k} at {[round(v) for v in (x, y, z)]}: its back {want:.0f} behind it, the wall {t_ if t_ is None else round(t_)}: not on the wall"); bad += 1
print(f"CENTRE {a[0].replace(chr(92), '/').split('/')[-1]}: {n} wall fixtures, {bad} off their panels"); sys.exit(1 if bad else 0)
