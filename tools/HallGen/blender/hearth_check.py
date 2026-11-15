"""Can anyone see into a manor fireplace except through its mouth? (the broken fireplace still showed a gap: a
render from one angle had passed it.) SMdCFirePlace01 is a sheet with notches in its outline, made for a recess. From each spot on the navmesh near it, at a character's eye heights,
sightlines to points inside the firebox, against the shell's faces and the facade's, both sides: a line that arrives must have crossed the facade's plane inside the mouth.
    python hearth_check.py <export .json> <its nav .json> <clean Data root>        FAIL GAP per fireplace with a line through, exit 1"""
import json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "scripts", "addons", "io_scene_nifly"))
from pyn.pynifly import NifFile
NifFile.Load(os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "scripts", "addons", "io_scene_nifly", "pyn", "NiflyDLL.dll"))
path, nav, root = sys.argv[1:4]
MOUTH_X, MOUTH_Z, PLANE = 82.0, 108.0, 127.0                # (local: the mouth's half width and height, and the plane of the stone behind the facade)
d = json.load(open(path)); N = json.load(open(nav))
shell = []
for s in d["shapes"].values():
    v = s["v"]
    for f in s["f"]:
        f = f[0] if f and isinstance(f[0], (list, tuple)) else f
        shell += [[v[f[0]], v[f[k]], v[f[k + 1]]] for k in range(1, len(f) - 1)]
shell = np.array(shell, float)
n = NifFile(os.path.join(root, "meshes", "architecture", "solitude", "interiors", "smdcfireplace01.nif"))
fv = []; ff = []
for s in n.shapes:
    t = s.transform; o = len(fv); fv += [tuple(np.array(p) * t.scale + np.array(t.translation)) for p in s.verts]; ff += [(a + o, b + o, c + o) for a, b, c in s.tris]
fv = np.array(fv, float); ff = np.array(ff, int)
V = np.array(N["verts"], float); F = [t["v"] for t in N["tris"]]
spots = []
for t in F:
    a, b, c = V[t]
    k = int(max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b)) / 20) + 1
    for i in range(k + 1):
        for j in range(k + 1 - i): spots.append(a + (b - a) * i / k + (c - a) * j / k)
spots = np.unique(np.round(np.array(spots) / 4) * 4, axis=0)

def blocked(o, e, T):
    """the segment o-e through any of T, either side"""
    dr = e - o; L = np.linalg.norm(dr); dr = dr / L
    a = T[:, 0]; e1 = T[:, 1] - a; e2 = T[:, 2] - a; h = np.cross(dr, e2); det = (e1 * h).sum(1); ok = np.abs(det) > 1e-9
    if not ok.any(): return False
    a, e1, e2, h, det = a[ok], e1[ok], e2[ok], h[ok], det[ok]
    s = o - a; u = (s * h).sum(1) / det; q = np.cross(s, e1); v = (dr * q).sum(1) / det; t = (e2 * q).sum(1) / det
    return bool(((u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6) & (t > 0.5) & (t < L - 0.5)).any())

bad = 0; seen = 0
for p in d["pieces"]:
    if "smdcfireplace01" not in p["model"].lower(): continue
    sc = p.get("scale", 1.0); yaw = math.radians(p["yaw"]); c, s = math.cos(yaw), math.sin(yaw); pos = np.array(p["pos"], float)
    W = lambda q: np.c_[q[:, 0] * c + q[:, 1] * s, -q[:, 0] * s + q[:, 1] * c, q[:, 2]] * sc + pos
    L = lambda q: np.array([(q - pos)[0] * c - (q - pos)[1] * s, (q - pos)[0] * s + (q - pos)[1] * c, (q - pos)[2]]) / sc   # (world to the piece's own frame)
    wv = W(fv); facade = wv[ff]
    centre = W(np.array([[0.0, 160.0, 60.0]]))[0]
    m = (np.abs(shell.reshape(len(shell), 9)[:, ::3].mean(1) - centre[0]) < 330) & (np.abs(shell[:, :, 1].mean(1) - centre[1]) < 330) & (np.abs(shell[:, :, 2].mean(1) - centre[2]) < 330)
    T = np.vstack([shell[m], facade])
    near = spots[(np.hypot(spots[:, 0] - centre[0], spots[:, 1] - centre[1]) < 420) & (np.abs(spots[:, 2] - p["pos"][2]) < 40)]
    tg = W(np.array([[x, y, z] for x in (-55.0, -20.0, 20.0, 55.0) for y in (150.0, 185.0) for z in (25.0, 60.0, 90.0)]))
    lines = 0; through = []
    for sp in near:
        for h in (70.0, 120.0, 165.0):
            eye = sp + (0, 0, h)
            for e in tg:
                if blocked(eye, e, T): continue
                lines += 1
                a_, b_ = L(eye), L(e)
                if a_[1] >= PLANE: continue               # (an eye behind the plane is a wall's other side's business)
                k_ = (PLANE - a_[1]) / (b_[1] - a_[1]); cross = a_ + (b_ - a_) * k_
                if abs(cross[0]) > MOUTH_X or cross[2] > MOUTH_Z: through.append((eye, cross))
    seen += 1
    print(f"  {[round(x) for x in (pos[1], -pos[0], pos[2])]} scale {sc:.2f}: {len(near)} spots, {lines} lines reach the firebox, {len(through)} not through the mouth")
    if through:
        bad += 1; e_, c_ = through[0]
        print(f"  FAIL GAP fireplace at hall ({pos[1]:.0f}, {-pos[0]:.0f}): from hall ({e_[1]:.0f}, {-e_[0]:.0f}, {e_[2]:.0f}) into the firebox, crossing its plane {c_[0]:.0f} across and {c_[2]:.0f} up")
    if not lines: print(f"  FAIL GAP fireplace at hall ({pos[1]:.0f}, {-pos[0]:.0f}): no line reached the firebox at all: this gate read nothing"); bad += 1
print(f"HEARTH {path.split('/')[-1]}: {seen} fireplaces, {bad} with a gap")
if not seen: print("  FAIL GAP no fireplace found: this gate read nothing")
sys.exit(1 if bad or not seen else 0)
