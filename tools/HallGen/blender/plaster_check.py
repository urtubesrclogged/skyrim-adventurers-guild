"""Light on pale plaster, from the plugin and the meshes (pale plaster under fixture lights, the textures plan). One light's peak on visible plaster =
albedo x fade x brightest channel x (1-(d/r)^2) x N.L, the measure Lux was read by (median 0.27, p90 0.45, p99 0.84). No single light over 0.45, a fire over 0.84, and the night's sum on the great hearth's
cheeks 1.0 or less, in every cell. No shadows and no post: an engine sum, not the picture. It fails if a cell reads no plaster or no lights: a gate that read nothing has passed nothing.
    python plaster_check.py <plugin.esp> <meshes dir> [Data dir]        FAIL lines, exit 1"""
import math, os, struct, sys, zlib
import numpy as np
sys.path.insert(0, os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "scripts", "addons", "io_scene_nifly"))
from pyn import pynifly
PLUGIN, MD = sys.argv[1:3]; DATA = sys.argv[3] if len(sys.argv) > 3 else "C:/Games/steamapps/common/SkyrimVR/Data"
pynifly.NifFile.Load(os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "scripts", "addons", "io_scene_nifly", "pyn", "NiflyDLL.dll"))
ALB, CAP, FIRE, CHEEK, SLACK = 0.74, 0.45, 0.84, 1.0, 0.01      # (SLACK: the list's fades are rounded to 0.01, and the points are a sample)
CELLS = {"AGHall2InteriorCell": True, "AGHall2BasementCell": False, "AGHall2LookoutCell": False}   # the cells, and which holds the great hearth
def subs(b):
    i = 0; o = {}
    while i + 6 <= len(b):
        t = b[i:i + 4]; n = struct.unpack_from("<H", b, i + 4)[0]; o.setdefault(t, b[i + 6:i + 6 + n]); i += 6 + n
    return o
def read(path, want):
    d = open(path, "rb").read(); out = []; hs = struct.unpack_from("<I", d, 4)[0]; head = subs(d[24:24 + hs])
    masters = []; h = d[24:24 + hs]; i = 0
    while i + 6 <= len(h):
        t = h[i:i + 4]; n = struct.unpack_from("<H", h, i + 4)[0]
        if t == b"MAST": masters.append(h[i + 6:i + 5 + n].decode("latin1"))
        i += 6 + n
    def walk(a, z, cell):
        while a < z:
            t = d[a:a + 4]; size = struct.unpack_from("<I", d, a + 4)[0]
            if t == b"GRUP":
                gt = struct.unpack_from("<i", d, a + 12)[0]
                walk(a + 24, a + size, struct.unpack_from("<I", d, a + 8)[0] if gt in (6, 8, 9, 10) else cell); a += size; continue
            fl, fid = struct.unpack_from("<II", d, a + 8); body = d[a + 24:a + 24 + size]; a += 24 + size
            if t not in want: continue
            if fl & 0x40000: body = zlib.decompress(body[4:])
            out.append((t, fid, fl, subs(body), cell))
    walk(24 + hs, len(d), None); return masters, out
masters, recs = read(PLUGIN, {b"REFR", b"LIGH", b"STAT", b"CELL"})
me = len(masters)
ed = lambda s: s.get(b"EDID", b"")[:-1].decode("latin1")
def light(s):
    D = s[b"DATA"]; return dict(ed=ed(s), r=struct.unpack_from("<I", D, 4)[0], rgb=tuple(D[8:11]), fade=struct.unpack("<f", s[b"FNAM"])[0] if b"FNAM" in s else 1.0)
LIGHTS = {}
for mi, m in enumerate(masters):
    p = os.path.join(DATA, m)
    if os.path.exists(p) and not m.lower().startswith("adventurersguild"):
        for t, f, fl, s, c in read(p, {b"LIGH"})[1]:
            if f >> 24 == 0: LIGHTS[(mi << 24) | (f & 0xFFFFFF)] = light(s)
for t, f, fl, s, c in recs:
    if t == b"LIGH": LIGHTS[f] = light(s)
STATS = {f: s for t, f, fl, s, c in recs if t == b"STAT" and ed(s).startswith("AGHall2") and b"MODL" in s}
CELLOF = {ed(s): f for t, f, fl, s, c in recs if t == b"CELL"}
rng = np.random.default_rng(2); shapes = {}
def closest(p, A, B, C):
    """the nearest point of each triangle (A, B, C: (n, 3)) to the point p (Ericson's regions, vectorised)"""
    ab, ac, ap = B - A, C - A, p - A; d1, d2 = (ab * ap).sum(1), (ac * ap).sum(1); bp = p - B; d3, d4 = (ab * bp).sum(1), (ac * bp).sum(1)
    cp = p - C; d5, d6 = (ab * cp).sum(1), (ac * cp).sum(1); va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2
    den = np.maximum(va + vb + vc, 1e-12); v = vb / den; w = vc / den; Q = A + ab * v[:, None] + ac * w[:, None]          # (inside the face)
    sab = (vc <= 0) & (d1 >= 0) & (d3 <= 0); t_ = d1 / np.where(d1 - d3 == 0, 1, d1 - d3); Q = np.where(sab[:, None], A + ab * t_[:, None], Q)
    sac = (vb <= 0) & (d2 >= 0) & (d6 <= 0); t_ = d2 / np.where(d2 - d6 == 0, 1, d2 - d6); Q = np.where(sac[:, None], A + ac * t_[:, None], Q)
    sbc = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0); t_ = (d4 - d3) / np.where((d4 - d3) + (d5 - d6) == 0, 1, (d4 - d3) + (d5 - d6)); Q = np.where(sbc[:, None], B + (C - B) * t_[:, None], Q)
    Q = np.where(((d1 <= 0) & (d2 <= 0))[:, None], A, Q); Q = np.where(((d3 >= 0) & (d4 <= d3))[:, None], B, Q); Q = np.where(((d6 >= 0) & (d5 <= d6))[:, None], C, Q)
    return Q
def plaster(f):
    """a static's plaster triangles, in its own frame"""
    m = STATS[f][b"MODL"][:-1].decode("latin1").replace(chr(92), "/"); p = os.path.join(MD, os.path.basename(m))
    if p not in shapes:
        shapes[p] = []
        if os.path.exists(p):
            nf = pynifly.NifFile(p)
            for sh in nf.shapes:
                if "agh2plaster" not in " ".join(v for v in (sh.textures or {}).values() if v).lower(): continue
                tr = sh.transform; R = np.array([[tr.rotation[i_][j_] for j_ in range(3)] for i_ in range(3)], float)
                shapes[p].append(((np.array(sh.verts, float) * tr.scale) @ R.T + np.array(tr.translation), np.array(sh.tris, int)))
    return shapes[p]
bad = 0
def fail(m):
    global bad; bad += 1; print("FAIL PLASTER", m)
for cname, hearth in CELLS.items():
    c_ = CELLOF.get(cname)
    if c_ is None: fail(f"no cell {cname}"); continue
    P = []; N = []; L = []; placed = set(); TA, TB, TC = [], [], []
    for t, f, fl, s, cell in recs:
        if t != b"REFR" or cell != c_ or fl & 0x800 or b"NAME" not in s or b"DATA" not in s: continue
        b_ = struct.unpack("<I", s[b"NAME"][:4])[0]; d = struct.unpack("<6f", s[b"DATA"][:24])
        if b_ in LIGHTS:
            l = dict(LIGHTS[b_]); l.update(pos=np.array(d[:3], float), id=f)
            if b"XRDS" in s: l["r"] = max(1.0, l["r"] + struct.unpack("<f", s[b"XRDS"][:4])[0])
            if b"XLIG" in s: l["fade"] += struct.unpack_from("<f", s[b"XLIG"], 4)[0]
            L.append(l)
        elif b_ in STATS:
            a = d[5]; cc, ss = math.cos(a), math.sin(a); Rz = np.array([[cc, ss, 0], [-ss, cc, 0], [0, 0, 1]]); tris_ = plaster(b_)
            placed.add(os.path.join(MD, os.path.basename(STATS[b_][b"MODL"][:-1].decode("latin1").replace(chr(92), "/"))))
            for v, tr in tris_:
                w = v @ Rz.T + np.array(d[:3], float); A, B, C = w[tr[:, 0]], w[tr[:, 1]], w[tr[:, 2]]
                cr = np.cross(B - A, C - A); ar = np.linalg.norm(cr, axis=1) / 2; k = ar > 1; A, B, C, cr, ar = A[k], B[k], C[k], cr[k], ar[k]
                if not len(ar): continue
                n = rng.poisson(ar / 100.0) + 1; i = np.repeat(np.arange(len(ar)), n); r1, r2 = rng.random(len(i)), rng.random(len(i)); fx = r1 + r2 > 1; r1[fx] = 1 - r1[fx]; r2[fx] = 1 - r2[fx]
                P.append(A[i] + (B[i] - A[i]) * r1[:, None] + (C[i] - A[i]) * r2[:, None]); N.append((cr / (2 * ar[:, None]))[i]); TA.append(A); TB.append(B); TC.append(C)
    # (the basement and the lookout are block and board, none of it plaster: a cell may hold none, but not while a mesh placed in it names plaster, and the great hall's must have some)
    named = sorted(os.path.basename(p) for p, v in shapes.items() if not v and os.path.exists(p) and b"agh2plaster" in open(p, "rb").read().lower() and p in placed)
    if named or not L or (hearth and not P): fail(f"{cname}: read {len(P)} plaster sets, {len(L)} lights, plaster named and unread in {named}"); continue
    if not P: print(f"{cname}: no plaster, {len(L)} lights"); continue
    P = np.vstack(P); N = np.vstack(N)
    if hearth:      # (the plaster behind the great hearth's firebox: the piece stands in front of it, and nobody sees it)
        k = ~((P[:, 0] < -1050) & (np.abs(P[:, 1]) < 230) & (P[:, 2] < 340)); P, N = P[k], N[k]
    TA, TB, TC = np.vstack(TA), np.vstack(TB), np.vstack(TC); TN = np.cross(TB - TA, TC - TA); TN /= np.linalg.norm(TN, axis=1)[:, None]
    if hearth:
        G_ = (TA + TB + TC) / 3; k = ~((G_[:, 0] < -1050) & (np.abs(G_[:, 1]) < 230) & (G_[:, 2] < 340)); TA, TB, TC, TN = TA[k], TB[k], TC[k], TN[k]
    U = []; peaks = []
    for l in L:
        d = l["pos"] - P; le = np.linalg.norm(d, axis=1); u = np.clip(1 - (le / l["r"]) ** 2, 0, 1) * np.clip((d * N).sum(1) / np.maximum(le, 1e-3), 0, 1); U.append(u)
        # (2026-11-03: and at each plaster triangle's nearest point to the light, where a flat face is lit most: the random sample alone missed it, and
        # any change elsewhere in the hall reshuffled the sample: three candles at 0.46..0.55 passed until the spandrels and door heads moved it)
        Q_ = closest(l["pos"], TA, TB, TC); dq = l["pos"] - Q_; lq = np.linalg.norm(dq, axis=1)
        uq = np.clip(1 - (lq / l["r"]) ** 2, 0, 1) * np.clip((dq * TN).sum(1) / np.maximum(lq, 1e-3), 0, 1)
        pk = float(max(u.max(), uq.max() if len(uq) else 0) * l["fade"] * max(l["rgb"]) / 255 * ALB); peaks.append(pk); cap = FIRE if "Fire" in l["ed"] else CAP
        if pk > cap + SLACK: fail(f"{cname} {l['ed']} r{l['r']:.0f} fade {l['fade']:.2f} at ({l['pos'][0]:.0f}, {l['pos'][1]:.0f}, {l['pos'][2]:.0f}) {l['id']:08X}: peak {pk:.2f} on plaster, the cap {cap}")
    peaks = np.array(peaks); on = peaks[peaks > 0.05]; extra = ""
    if hearth:
        ch = (np.abs(P[:, 0] + 910) < 200) & (np.abs(np.abs(P[:, 1]) - 216) < 8) & (P[:, 2] < 340)
        if not ch.any(): fail("the hearth's cheeks: no plaster read")
        else:
            night = sum(u * l["fade"] * l["rgb"][0] / 255 for u, l in zip(U, L) if l["ed"] not in ("AGHall2LightWindow", "AGHall2LightBounce")) * ALB; m = float(night[ch].max()); extra = f", the hearth's cheeks {m:.2f}"
            if m > CHEEK + SLACK: fail(f"the great hearth's cheeks: {m:.2f} red at night, the cap {CHEEK}")
    print(f"{cname}: {len(P)} points of plaster, {len(L)} lights, {len(on)} reach it, peak median {np.median(on) if len(on) else 0:.2f} max {peaks.max():.2f}{extra}")
print(f"PLASTER {bad} failures"); sys.exit(1 if bad else 0)
