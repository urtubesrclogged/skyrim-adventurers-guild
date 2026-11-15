"""Does anything come out the far side of a wall? (the kitchen's fire clipped through the wall into the tavern: its ember bed is
96 deep, its firebox 48, the wall behind 4; the placement gate skips effects, and a piece's cut into the shell says nothing of where it comes out.)
Every piece, effects too, by its mesh's box turned and scaled as the game places it: a grid of points through the box, a line from the box's middle to each.
Two walls' faces crossed on the way means the point went in one side of a wall and out the other: it shows in the next room. Reported by how far out it reaches.
Shell and big architecture are left out (they are the walls); a box is a mesh's outer limit, so a hit on a large piece wants a look before it is believed.
    python through_check.py <part.json> --mesh <mesh_info.json> --data <extracted Data> --nav <nav_part.json> [--min 3] [--all]     exit 1 on any effect or small piece through a wall"""
import json, math, re, sys
import numpy as np
a = sys.argv[1:]
def opt(k, d):
    if k in a: i = a.index(k); v = a[i + 1]; del a[i:i + 2]; return v
    return d
MI = json.load(open(opt("--mesh", None))); MIN = float(opt("--min", 3)); SHOW_ALL = "--all" in a; DATA = opt("--data", None); NAV = opt("--nav", None)
if SHOW_ALL: a.remove("--all")
part = json.load(open(a[0])); H = lambda p: (p[1], -p[0], p[2])
T = np.array([[H(p) for p in t] for t in part["coll"]], float)
A_, E1, E2 = T[:, 0], T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
LO, HI = T.min(axis=1), T.max(axis=1)
VERTS = {}
def mesh_verts(model):
    """an effect's own vertices through its node chain (a flame does not fill its box): as mesh_info.py reads them"""
    if model in VERTS: return VERTS[model]
    import os
    k = os.path.join(DATA, model); out = None
    if os.path.exists(k):
        if "NifFile" not in globals():
            sys.path.insert(0, os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "scripts", "addons", "io_scene_nifly"))
            from pyn.pynifly import NifFile as NF
            NF.Load(os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "scripts", "addons", "io_scene_nifly", "pyn", "NiflyDLL.dll")); globals()["NifFile"] = NF
        pts = []
        for sh in NifFile(k).shapes:
            n = sh; v = np.array(sh.verts, float)
            while n is not None and n.parent is not None:
                x = n.transform; v = (v @ np.array(x.rotation, float).T) * x.scale + np.array(x.translation, float); n = n.parent
            pts.append(v)
        out = np.vstack(pts) if pts else None
    VERTS[model] = out; return out
NT = None
if NAV:
    nv = json.load(open(NAV)); V_ = np.array([H(p) for p in nv["verts"]], float); NT = V_[[t["v"] for t in nv["tris"]]]
def in_room(q):
    """a point over a walkable floor, between the floor and head height: somewhere a person sees it. Past an outer wall nothing does"""
    if NT is None: return True
    A, B, C = NT[:, 0], NT[:, 1], NT[:, 2]
    d = (B[:, 1] - C[:, 1]) * (A[:, 0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (A[:, 1] - C[:, 1]); d[np.abs(d) < 1e-9] = 1e-9
    l1 = ((B[:, 1] - C[:, 1]) * (q[0] - C[:, 0]) + (C[:, 0] - B[:, 0]) * (q[1] - C[:, 1])) / d
    l2 = ((C[:, 1] - A[:, 1]) * (q[0] - C[:, 0]) + (A[:, 0] - C[:, 0]) * (q[1] - C[:, 1])) / d
    # (the mesh stops short of what blocks it: within 24 of it counts, so a wall's own foot does)
    m = (l1 > -0.02) & (l2 > -0.02) & (l1 + l2 < 1.02)
    if not m.any():
        c_ = NT.mean(axis=1); r_ = np.hypot(c_[:, 0] - q[0], c_[:, 1] - q[1]); m = r_ < 60
    return bool(m.any() and np.any((q[2] > NT[m].mean(axis=1)[:, 2] - 10) & (q[2] < NT[m].mean(axis=1)[:, 2] + 260)))
SKIP = re.compile(r"^meshes/(water|marker)|architecture|/hall2/|dungeons/imperial/(door|jail)|trapdoor|fxcobweb", re.I)   # (a cobweb is hung into corners)
GRID = np.linspace(0.04, 0.96, 6)
def crossings(c, p):
    """distances along c->p (0..1) at which the segment passes through a collision face, near-duplicates (a shared edge) merged"""
    lo, hi = np.minimum(c, p) - 1, np.maximum(c, p) + 1
    m = np.all(HI >= lo, axis=1) & np.all(LO <= hi, axis=1)
    if not m.any(): return []
    d = p - c; e1, e2, a0 = E1[m], E2[m], A_[m]
    h = np.cross(d, e2); det = np.einsum("ij,ij->i", e1, h); ok = np.abs(det) > 1e-9
    if not ok.any(): return []
    e1, e2, a0, h, det = e1[ok], e2[ok], a0[ok], h[ok], det[ok]
    s = c - a0; u = np.einsum("ij,ij->i", s, h) / det
    q = np.cross(s, e1); v = np.einsum("j,ij->i", d, q) / det; t = np.einsum("ij,ij->i", e2, q) / det
    hit = (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6) & (t > 1e-6) & (t < 1 - 1e-6)
    ts = sorted(t[hit]); out = []
    for x in ts:
        if not out or (x - out[-1]) * np.linalg.norm(d) > 0.5: out.append(x)
    return out
fails = []; checked = 0
for p in part["pieces"]:
    m = p["model"].lower().replace(chr(92), "/"); mi = MI.get(m) or MI.get(p["model"]); e = p.get("ed") or m.split("/")[-1]
    if not mi or not mi.get("box") or SKIP.search(m) or p.get("rx"): continue
    (x0, y0, z0), (x1, y1, z1) = mi["box"]
    if max(x1 - x0, y1 - y0) > 500: continue
    checked += 1; x, y, z = H(p["pos"]); s = p.get("scale", 1.0); yaw = math.radians(p["yaw"] + 90)
    ex, ey = (math.cos(yaw), -math.sin(yaw)), (math.sin(yaw), math.cos(yaw))
    def W(lx, ly, lz): return np.array([x + (lx * ex[0] + ly * ey[0]) * s, y + (lx * ex[1] + ly * ey[1]) * s, z + lz * s])
    c = W((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2); best = None
    lv = mesh_verts(m) if DATA and "effects" in m else None
    if lv is not None:
        c = W(0, 0, 8 / s); pts = [W(*v_) for v_ in lv[:: max(1, len(lv) // 800)]]
    else: pts = [W(x0 + u * (x1 - x0), y0 + v * (y1 - y0), z0 + w * (z1 - z0)) for u in GRID for v in GRID for w in GRID]
    past = []
    for q in pts:
        ts = crossings(c, q)
        if len(ts) >= 2:
            out = (1 - ts[1]) * float(np.linalg.norm(q - c))
            if out > MIN and in_room(q): past.append((out, q, c + (q - c) * ts[0], c + (q - c) * ts[1]))
    # (an effect's few far points are sparks: it counts from eight vertices past the wall, reported by the eighth farthest; a box's corner is one point)
    if len(past) >= (8 if lv is not None else 1): best = sorted(past, key=lambda f: -f[0])[7 if lv is not None else 0]
    if best: fails.append((best[0], e, [round(v) for v in (x, y, z)], [round(float(v)) for v in best[2]], [round(float(v)) for v in best[3]], "effects" in m))
fails.sort(key=lambda f: (not f[5], -f[0]))
for f in fails:
    if f[5] or SHOW_ALL or f[0] > 12: print(f"  {'FAIL' if f[5] else 'LOOK'} THROUGH {f[1]:32} at {f[2]}: {f[0]:.0f} out past the wall, in at {f[3]}, out at {f[4]}")
n = sum(1 for f in fails if f[5])
print(f"THROUGH {a[0].replace(chr(92), '/').split('/')[-1]}: {checked} pieces checked, {n} effects through a wall, {len(fails) - n} other boxes to look at"); sys.exit(1 if n else 0)
