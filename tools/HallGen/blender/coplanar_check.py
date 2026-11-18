"""Flicker check for exported hall parts (guildhall_gen.py AG_EXPORT JSON): faces that lie in the same plane, face the
same way and overlap draw on top of each other (z-fighting). Faces of every part given are checked against each other
(a terrace tile against the building's plinth counts). A pair is only reported when the overlap can be seen: a point
just in front of it must not be underground (with --site/--map), inside another solid, nor shut in by the building's
shell (it is hidden when no ray from it, in nine directions about its normal, reaches open sky).
    python coplanar_check.py <part.json> [part.json ...] [--min AREA] [--site x,y,floor,yaw --map mapdata.json] [--all] [--interior]
Prints hall-frame positions (x across the front, y negative in front, z from the floor)."""
import sys, json, math, itertools, struct, base64
import numpy as np
args = sys.argv[1:]; opt = {}
for k in ("--min", "--site", "--map", "--top"):
    if k in args: i = args.index(k); opt[k] = args[i + 1]; del args[i:i + 2]
SHOW_ALL = "--all" in args; args = [a for a in args if a != "--all"]
AS_GATE = "--fail" in args; args = [a for a in args if a != "--fail"]
# --interior: a cell with no sky (the basement, the interior): an overlap is seen when a standing point sees it (a grid over
# the drawn floors, at eye height 120, under a ceiling, as seal_check.py's), hidden when none does (2026-10-28, the basement's
# first walk: flicker in four rooms the sky test called "enclosed")
INTERIOR = "--interior" in args; args = [a for a in args if a != "--interior"]
MIN = float(opt.get("--min", 4))
ground = None
if "--site" in opt and "--map" in opt:
    SITE = [float(v) for v in opt["--site"].split(",")]; M = json.load(open(opt["--map"]))
    X0, Y0, NX, NY = M["box"][0] * 4096, M["box"][1] * 4096, M["nx"], M["ny"]
    H = struct.unpack("<%dh" % (NX * NY), base64.b64decode(M["heights"])); A_ = math.radians(SITE[3])
    def ground(lx, ly):                                    # layout frame in, height relative to the floor out
        wx, wy = SITE[0] + lx * math.cos(A_) + ly * math.sin(A_), SITE[1] - lx * math.sin(A_) + ly * math.cos(A_)
        fx, fy = (wx - X0) / 128, (wy - Y0) / 128; i, j = int(fx), int(fy); u, v = fx - i, fy - j
        h = lambda a, b: H[b * NX + a]
        return h(i, j) * (1 - u) * (1 - v) + h(i + 1, j) * u * (1 - v) + h(i, j + 1) * (1 - u) * v + h(i + 1, j + 1) * u * v - SITE[2]
faces, tris = [], []
for path in args:
    d = json.load(open(path)); part = path.replace("\\", "/").split("/")[-1].replace(".json", "").replace("hall2_", "")
    for key, sh in d["shapes"].items():
        if key in ("moss", "mosswall", "wearcrack", "wearstain", "spill"): continue                          # a decal: its Decal shader flags keep it off the paving's depth
        V = sh["v"]
        for fi, f in enumerate(sh["f"]):
            P = [V[i] for i in f]
            if len(P) < 3: continue
            ax = [P[1][k] - P[0][k] for k in range(3)]; bx = [P[2][k] - P[0][k] for k in range(3)]
            n = [ax[1] * bx[2] - ax[2] * bx[1], ax[2] * bx[0] - ax[0] * bx[2], ax[0] * bx[1] - ax[1] * bx[0]]
            L = math.sqrt(sum(c * c for c in n))
            if L < 1e-6: continue
            n = [c / L for c in n]; dd = sum(n[k] * P[0][k] for k in range(3))
            fid = len(faces); faces.append((part + ":" + key, fid, n, dd, P))
            for k in range(1, len(P) - 1): tris.append((P[0], P[k], P[k + 1], fid))
T0 = np.array([t[0] for t in tris], float); T1 = np.array([t[1] for t in tris], float); T2 = np.array([t[2] for t in tris], float)
TF = np.array([t[3] for t in tris]); E1, E2 = T1 - T0, T2 - T0; TN = np.cross(E1, E2)
def first_hit(o, dirv, skip):
    """Moller-Trumbore against every triangle: (distance, does the hit face point along the ray = a back face)"""
    p = np.cross(dirv, E2); det = (E1 * p).sum(1); ok = np.abs(det) > 1e-9; inv = np.where(ok, 1 / np.where(ok, det, 1), 0)
    s = o - T0; u = (s * p).sum(1) * inv; q = np.cross(s, E1); v = (q * dirv).sum(1) * inv; t = (q * E2).sum(1) * inv
    m = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-3) & ~np.isin(TF, skip)
    if not m.any(): return None
    i = np.argmin(np.where(m, t, np.inf)); return t[i], float((TN[i] * dirv).sum()) > 0
EYES = None
def eyes():
    global EYES
    if EYES is not None: return EYES
    up = TN[:, 2] / np.maximum(np.linalg.norm(TN, axis=1), 1e-9) > 0.95; out = {}
    for i in np.nonzero(up)[0]:
        a, b, c = T0[i], T1[i], T2[i]; lo, hi = np.minimum(np.minimum(a, b), c), np.maximum(np.maximum(a, b), c)
        for x in np.arange(math.floor(lo[0] / 48) * 48 + 24, hi[0], 48):
            for y in np.arange(math.floor(lo[1] / 48) * 48 + 24, hi[1], 48):
                v0, v1, v2 = b - a, c - a, np.array([x, y, 0]) - a; den = v0[0] * v1[1] - v1[0] * v0[1]
                if abs(den) < 1e-9: continue
                uu = (v2[0] * v1[1] - v1[0] * v2[1]) / den; ww = (v0[0] * v2[1] - v2[0] * v0[1]) / den
                if uu < 0 or ww < 0 or uu + ww > 1: continue
                z = a[2] + uu * (b[2] - a[2]) + ww * (c[2] - a[2])
                h = first_hit(np.array([x, y, z + 2.0]), np.array([0, 0, 1.0]), [])
                if h is None or h[1] or h[0] < 130: continue
                out[(round(x), round(y), round(z))] = np.array([x, y, z + 120.0])
    EYES = np.array(list(out.values())); return EYES
def seen_from_eye(pt, n):
    E = eyes(); o = np.array(pt) + np.array(n) * 0.5; dvs = E - o; ds = np.linalg.norm(dvs, axis=1)
    front = (dvs @ np.array(n)) > 0
    for k in np.argsort(np.where(front, ds, np.inf))[:80]:
        if not front[k]: break
        dv = dvs[k] / ds[k]; h = first_hit(o, dv, [])
        if h is None or h[0] >= ds[k] - 0.5: return True
    return False
def hidden(pt, n, skip):
    if ground and pt[2] < ground(pt[0], pt[1]) - 2: return "underground"
    o = np.array(pt) + np.array(n) * 0.5; nn = np.array(n)
    a = np.cross(nn, [0, 0, 1] if abs(n[2]) < 0.9 else [1, 0, 0]); a /= np.linalg.norm(a); b = np.cross(nn, a)
    back = True
    for dv in (nn, nn + a, nn - a, nn + b, nn - b, a, -a, b, -b):
        dv = dv / np.linalg.norm(dv); h = first_hit(o, dv, skip)
        if h is None: return None                        # this way it sees open sky: visible
        back &= h[1]
    if INTERIOR: return "inside" if back else (None if seen_from_eye(pt, n) else "unseen")
    return "inside" if back else "enclosed"             # inside a solid, or shut in by the building's shell
def key_of(n, dd):
    s = 1 if (n[0], n[1], n[2]) > (0, 0, 0) else -1
    return (round(n[0] * s, 2), round(n[1] * s, 2), round(n[2] * s, 2), round(dd * s, 0))
groups = {}
for f in faces: groups.setdefault(key_of(f[2], f[3]), []).append(f)
def axes(n):
    a = max(range(3), key=lambda k: abs(n[k])); return [k for k in range(3) if k != a], a
def area(poly):
    return abs(sum(poly[k][0] * poly[(k + 1) % len(poly)][1] - poly[(k + 1) % len(poly)][0] * poly[k][1] for k in range(len(poly)))) / 2
def clip(subject, clipper):                                          # Sutherland-Hodgman (both convex)
    def inside(p, a, b, s): return s * ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) >= -1e-9
    def inter(p, q, a, b):
        x1, y1, x2, y2, x3, y3, x4, y4 = *p, *q, *a, *b
        den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(den) < 1e-12: return q
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    sgn = 1 if sum(clipper[k][0] * clipper[(k + 1) % len(clipper)][1] - clipper[(k + 1) % len(clipper)][0] * clipper[k][1] for k in range(len(clipper))) > 0 else -1
    out = subject
    for k in range(len(clipper)):
        a, b = clipper[k], clipper[(k + 1) % len(clipper)]; inp = out; out = []
        if not inp: break
        s_ = inp[-1]
        for e in inp:
            if inside(e, a, b, sgn):
                if not inside(s_, a, b, sgn): out.append(inter(s_, e, a, b))
                out.append(e)
            elif inside(s_, a, b, sgn): out.append(inter(s_, e, a, b))
            s_ = e
    return out
hits, nhid = [], {"underground": 0, "inside": 0, "enclosed": 0, "unseen": 0}
for g in groups.values():
    if len(g) < 2: continue
    for A, Bf in itertools.combinations(g, 2):
        if sum(A[2][k] * Bf[2][k] for k in range(3)) < 0.99: continue     # back to back: one is always culled, no flicker
        if abs(A[3] - Bf[3]) > 0.25: continue                             # grouped by rounding (1191.5 and 1192.5 both round
                                                                          # to 1192): a unit apart does not fight
        (i, j), ax = axes(A[2])
        ov = clip([(p[i], p[j]) for p in A[4]], [(p[i], p[j]) for p in Bf[4]])
        if len(ov) < 3 or area(ov) < MIN: continue
        cx, cy = sum(p[0] for p in ov) / len(ov), sum(p[1] for p in ov) / len(ov)
        n = A[2]
        def on_plane(u, v):
            q = [0, 0, 0]; q[i], q[j] = u, v; q[ax] = (A[3] - n[i] * u - n[j] * v) / n[ax]; return q   # back onto the plane
        pt = on_plane(cx, cy)
        # hidden only if its centre AND points all round its edge (every 16, at most 48, 1.5 inside) are: one sample at
        # the centre called a doorway's threshold hidden (the middle of a long overlap sat under the wall) and corners
        # pulled toward the centre missed a plinth's rim standing out past a wall (2026-10-23)
        per = sum(math.dist(ov[k], ov[(k + 1) % len(ov)]) for k in range(len(ov))); stp = max(16.0, per / 48)
        ring = []
        for k in range(len(ov)):
            p0, p1 = ov[k], ov[(k + 1) % len(ov)]; m_ = max(1, int(math.dist(p0, p1) // stp))
            for t in range(m_):
                u, v = p0[0] + (p1[0] - p0[0]) * (t + 0.5) / m_, p0[1] + (p1[1] - p0[1]) * (t + 0.5) / m_
                dl = math.hypot(cx - u, cy - v)
                if dl > 1.5: u, v = u + (cx - u) * 1.5 / dl, v + (cy - v) * 1.5 / dl
                ring.append((u, v))
        why = None
        for u, v in [(cx, cy)] + ring:
            why = hidden(on_plane(u, v), n, [A[1], Bf[1]])
            if not why: pt = on_plane(u, v); break
        if why and not SHOW_ALL: nhid[why] += 1; continue
        bb = lambda P_: [[round(min(p[k] for p in P_)) for k in range(3)], [round(max(p[k] for p in P_)) for k in range(3)]]
        hits.append((round(area(ov)), A[0], Bf[0], [round(pt[1]), round(-pt[0]), round(pt[2])], [round(c, 2) for c in n], why or "SEEN",
                     "faces (layout)", bb(A[4]), bb(Bf[4])))
hits.sort(reverse=True)
print(len(hits), "visible overlapping coplanar face pairs; hidden:", nhid, "(hall frame x, y, z; layout normal)")
nd = sum(1 for h in hits if h[1].split(":")[1] != h[2].split(":")[1])
print("   of them", nd, "between different materials (these flicker as soon as they are seen); the rest share one texture,"
      " and flicker only as far as their vertex colours differ")
for h in hits[:int(opt.get("--top", 60))]: print("  ", h)
if AS_GATE:   # (2026-11-05: as a gate, each seen pair a FAIL line, which gates_all.sh holds to gates/accepted.tsv; until then
    for h in hits:          # the basement's 6 only set gates_export.sh's exit code, which the build ignored)
        if h[5] == "SEEN": print(f"FAIL COPLANAR {h[1].split(':')[0]}: {h[1].split(':')[1].split('@')[0]} and {h[2].split(':')[1].split('@')[0]} in one plane at {h[3]}, {h[0]} square")
