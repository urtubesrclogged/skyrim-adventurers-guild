"""Split the hall's roof (hall2_roof.json, exported by guildhall_gen.py) into a snowed part and a bare part, so the roof can
carry vanilla's heavy snow (a directional material on its record) with the slate showing through in places: the bare part
goes on its own record, without the material. (Site B, 2026-11-17: one directional material on the whole roof is either all
snow or all slate, and a partial one draws as an even grey film: a split is the only way to keep the heavy snow's look.)

The cut follows a smooth noise field of the position alone (3D): patches of roughly even shape on every face, their edges
ragged at two finer scales, melted back round the chimneys. Faces the cut runs through are cut on a world grid first (the same
planes for every face, so neighbours cut their shared edges at the same points: no cracks), each grid piece then split
along the field's zero line, uvs and vertex colours carried along every cut. Faces the cut misses stay whole, fanned from
their middle through every grid point on their edges (so a cut neighbour's points on a shared edge are matched there too).

    python roof_snow_split.py <hall2_roof.json> <out_snow.json> <out_bare.json> <snow share 0-1> [seed] [feature size]"""
import json, math, sys, random

src, out_s, out_b = sys.argv[1:4]
SHARE = float(sys.argv[4]); SEED = sys.argv[5] if len(sys.argv) > 5 else "roof snow"; FEAT = float(sys.argv[6]) if len(sys.argv) > 6 else 170.0
GRID = 16.0
# the chimneys' centres (the stacks standing out of the roof, measured from the body's stonework with their caps)
CHIMNEYS = [(-1035.0, 0.0), (-710.0, -1090.0), (-710.0, 1090.0)]

D = json.load(open(src))
R = D["shapes"]["roof"]; V = R["v"]

rnd = random.Random(SEED); PERM = list(range(512)); rnd.shuffle(PERM); VAL = [rnd.random() * 2 - 1 for _ in range(512)]
def lat(ix, iy): return VAL[PERM[(PERM[ix & 511] + iy) & 511]]
def vnoise(x, y):
    ix, iy = math.floor(x), math.floor(y); fx, fy = x - ix, y - iy
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b, c, d = lat(ix, iy), lat(ix + 1, iy), lat(ix, iy + 1), lat(ix + 1, iy + 1)
    return (a + (b - a) * sx) + ((c + (d - c) * sx) - (a + (b - a) * sx)) * sy
def lat3(ix, iy, iz): return VAL[PERM[(PERM[(PERM[ix & 511] + iy) & 511] + iz) & 511]]
def vnoise3(x, y, z):
    ix, iy, iz = math.floor(x), math.floor(y), math.floor(z); fx, fy, fz = x - ix, y - iy, z - iz
    sx, sy, sz = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy), fz * fz * (3 - 2 * fz)
    def l(a, b, t): return a + (b - a) * t
    c = [[[lat3(ix + i, iy + j, iz + k) for k in (0, 1)] for j in (0, 1)] for i in (0, 1)]
    return l(l(l(c[0][0][0], c[1][0][0], sx), l(c[0][1][0], c[1][1][0], sx), sy), l(l(c[0][0][1], c[1][0][1], sx), l(c[0][1][1], c[1][1][1], sx), sy), sz)
def field(p, up=None, mirror=None):
    # (2026-11-17, in game: straight stripes ridge to eave) a function of the position alone, in 3D: the same on every face
    # and at every edge, so no face's mapping can run along its slope and no two faces can disagree where they meet. (A 2D
    # mapping with z in it runs flat along some slope; one that also used the face's own slope split at shared edges)
    x, y, z = p[0] / FEAT, p[1] / FEAT, p[2] / FEAT
    n = vnoise3(x, y, z) + 0.5 * vnoise3(2.03 * x + 17.1, 2.03 * y + 5.3, 2.03 * z + 9.9) + 0.25 * vnoise3(4.1 * x + 3.7, 4.1 * y + 41.0, 4.1 * z + 2.2)         + 0.12 * vnoise3(9.7 * x + 71.0, 9.7 * y + 9.0, 9.7 * z + 13.0) + 0.06 * vnoise3(21.0 * x + 5.0, 21.0 * y + 33.0, 21.0 * z + 7.0)
    warm = sum(math.exp(-((p[0] - cx) ** 2 + (p[1] - cy) ** 2) / 120.0 ** 2) for cx, cy in CHIMNEYS)
    return n * 1.6 - 1.5 * warm                            # (3D value noise has a narrower range: scaled to the 2D one's)

# a vertex is (pos, uv, col)
def lerp(a, b, t): return [a[i] + (b[i] - a[i]) * t for i in range(len(a))]
def lerpv(A, B, t): return (lerp(A[0], B[0], t), lerp(A[1], B[1], t), lerp(A[2], B[2], t))
def clip(poly, key, keep_pos):                               # Sutherland-Hodgman on a scalar per vertex
    out = []
    for i in range(len(poly)):
        A, B = poly[i], poly[(i + 1) % len(poly)]; ka, kb = key(A), key(B)
        ina, inb = (ka >= 0) == keep_pos, (kb >= 0) == keep_pos
        if ina: out.append(A)
        if ina != inb: out.append(lerpv(A, B, ka / (ka - kb)))
    return out
def normal(P):
    nx = ny = nz = 0.0
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]
        nx += (a[1] - b[1]) * (a[2] + b[2]); ny += (a[2] - b[2]) * (a[0] + b[0]); nz += (a[0] - b[0]) * (a[1] + b[1])
    L = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return (nx / L, ny / L, nz / L)
def area(P):
    n = normal(P); s = [0.0, 0.0, 0.0]
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]
        s[0] += a[1] * b[2] - a[2] * b[1]; s[1] += a[2] * b[0] - a[0] * b[2]; s[2] += a[0] * b[1] - a[1] * b[0]
    return abs(n[0] * s[0] + n[1] * s[1] + n[2] * s[2]) / 2
def grid_cut(poly):                                          # a convex polygon cut on the world grid: convex pieces
    xs = [v[0][0] for v in poly]; ys = [v[0][1] for v in poly]; cells = [poly]
    for ax, lo, hi in ((0, min(xs), max(xs)), (1, min(ys), max(ys))):
        k0, k1 = math.floor(lo / GRID) + 1, math.ceil(hi / GRID) - 1; nxt = []
        for c in cells:
            rest = c
            for k in range(k0, k1 + 1):
                if len(rest) < 3: break
                g = k * GRID
                below = clip(rest, lambda v: g - v[0][ax], True); rest = clip(rest, lambda v: g - v[0][ax], False)
                if len(below) >= 3: nxt.append(below)
            if len(rest) >= 3: nxt.append(rest)
        cells = nxt
    return cells
def grid_ring(poly):                                         # the polygon's outline with every grid crossing on its edges
    out = []
    for i in range(len(poly)):
        A, B = poly[i], poly[(i + 1) % len(poly)]; out.append(A); ts = []
        for ax in (0, 1):
            a, b = A[0][ax], B[0][ax]
            if abs(b - a) < 1e-9: continue
            for k in range(math.floor(min(a, b) / GRID) + 1, math.ceil(max(a, b) / GRID)):
                t = (k * GRID - a) / (b - a)
                if 1e-6 < t < 1 - 1e-6: ts.append(t)
        for t in sorted(set(round(t, 9) for t in ts)): out.append(lerpv(A, B, t))
    return out

faces = []
nonconvex = 0
for fi, f in enumerate(R["f"]):
    poly = [(V[i], R["uv"][fi][k], R["c"][fi][k]) for k, i in enumerate(f)]
    P = [v[0] for v in poly]; n = normal(P); sg = set()
    for i in range(len(P)):
        a, b, c = P[i], P[(i + 1) % len(P)], P[(i + 2) % len(P)]
        u = [b[j] - a[j] for j in range(3)]; w = [c[j] - b[j] for j in range(3)]
        cr = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
        d_ = cr[0] * n[0] + cr[1] * n[1] + cr[2] * n[2]
        if abs(d_) > 1e-6: sg.add(d_ > 0)
    if len(sg) > 1: nonconvex += 1
    faces.append((poly, n[2], grid_cut(poly), n[1] > 0.2))
if nonconvex: sys.exit(f"ROOF SNOW SPLIT: {nonconvex} faces are not convex (the grid cut assumes convex faces)")

# the threshold that gives the asked snow share of the roof's area
samples = []
for poly, up, cells, _ in faces:                            # (the threshold from the first mapping on every face: the faces it
    for c in cells:                                          # served keep their patches exactly)
        cen = [sum(v[0][j] for v in c) / len(c) for j in range(3)]; samples.append((field(cen, up), area([v[0] for v in c])))
samples.sort(key=lambda s: -s[0]); tot = sum(a for _, a in samples); acc = 0.0; TH = samples[-1][0]
for fv_, a in samples:
    acc += a
    if acc >= SHARE * tot: TH = fv_; break

fcache = {}
def fval(v, up, mir):                                        # (one value per position: faces meeting at a vertex agree)
    k = (round(v[0][0], 3), round(v[0][1], 3), round(v[0][2], 3))
    if k not in fcache: fcache[k] = field(v[0], up, mir) - TH
    return fcache[k]
snow, bare = [], []; whole = cut = 0
for poly, up, cells, mir in faces:
    signs = {fval(v, up, mir) >= 0 for c in cells for v in c}
    if len(signs) == 1:                                      # the cut misses it: whole, fanned from its middle
        whole += 1; ring = grid_ring(poly); m = len(poly)
        mid = ([sum(v[0][j] for v in poly) / m for j in range(3)], [sum(v[1][j] for v in poly) / m for j in range(2)],
               [sum(v[2][j] for v in poly) / m for j in range(len(poly[0][2]))])
        dst = snow if signs.pop() else bare
        for i in range(len(ring)):
            t_ = [mid, ring[i], ring[(i + 1) % len(ring)]]
            if area([v[0] for v in t_]) > 0.01: dst.append(t_)
        continue
    cut += 1
    for c in cells:
        for i in range(1, len(c) - 1):
            tri = [c[0], c[i], c[i + 1]]; key = lambda v: fval(v, up, mir)
            s_ = clip(tri, key, True); b_ = clip(tri, key, False)
            if len(s_) >= 3 and area([v[0] for v in s_]) > 0.01: snow.append(s_)
            if len(b_) >= 3 and area([v[0] for v in b_]) > 0.01: bare.append(b_)

def shape(polys):                                            # corners welded by position (a NIF shape holds 65535 vertices at
    v, f, uv, c, at = [], [], [], [], {}                     # most; the uvs and colours stay per corner, so seams still split)
    for p in polys:
        ix = []
        for x in p:
            k = (round(x[0][0], 3), round(x[0][1], 3), round(x[0][2], 3))
            if k not in at: at[k] = len(v); v.append(x[0])
            ix.append(at[k])
        f.append(ix); uv.append([x[1] for x in p]); c.append([x[2] for x in p])
    return {"v": v, "f": f, "uv": uv, "c": c}
for path, polys in ((out_s, snow), (out_b, bare)):
    o = dict(D); o["shapes"] = {"roof": shape(polys)}; o["coll"] = []; o["coll_mat"] = []
    json.dump(o, open(path, "w"))
As, Ab = sum(area([v[0] for v in p]) for p in snow), sum(area([v[0] for v in p]) for p in bare)
A0 = sum(area([V[i] for i in f]) for f in R["f"]); tris = sum(len(p) - 2 for p in snow + bare)
print(f"ROOF SNOW SPLIT share asked {SHARE:.2f}, got {As / (As + Ab):.3f}: {len(R['f'])} faces ({whole} whole, {cut} cut), "
      f"snow {len(snow)} polys, bare {len(bare)} polys, {tris} triangles; area kept {100 * (As + Ab) / A0:.3f}%")
if abs((As + Ab) / A0 - 1) > 1e-3: sys.exit("ROOF SNOW SPLIT: the two parts do not add up to the roof")
