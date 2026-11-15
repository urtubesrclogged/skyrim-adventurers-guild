"""Headless Blender: the Guild Board as a Skyrim SE NIF. The game mesh (the blockout's design, board_gen.py, built for
the game: chamfered oak, the carved sign board and its dragon heads, the hall's relief crest, the rank badges, iron) in
four kinds of shape, each wearing one texture set (board_textures.py), plus one shape per notice (so the mod can show or
hide each one), and a box for collision. Shader settings, the root and the collision come from vanilla NIFs (a Whiterun
castle piece for the opaque shapes and the box, Jorrvaskr's banner for the notices' alpha test), as the hall's do.
    blender -b --factory-startup -P board_build.py -- <out nif> <template dir: holds meshes/...> [ao=1]
Frame: x right, the wall at y 0, front toward -y, z up from the board's bottom (the NIF's origin: on the wall plane at
the board's bottom middle)."""
import sys, os, math, json, random, bpy, bmesh, addon_utils
from mathutils import Vector, Matrix
addon_utils.enable("io_scene_nifly", default_set=True, persistent=True)
HERE = os.path.dirname(os.path.abspath(__file__))
PRIV = os.path.join(HERE, "..", "..", "hall-private", "board")   # (its inputs made from the game's files or not ours to publish: tools/hall-private)
sys.path.insert(0, HERE)
import board_layout as BL
args = sys.argv[sys.argv.index("--") + 1:]
DST, TPL = os.path.abspath(args[0]), args[1]
OPT = dict(a.split("=", 1) for a in args[2:] if "=" in a)
BS = chr(92)
TEXP = "textures" + BS + "AdventurersGuild" + BS + "Board" + BS
random.seed(11)

# ---------------------------------------------------------------- the design (DESIGN.md; board_gen.py's numbers)
W = 240.0; SW, SD = 9.0, 4.5; RB0, RB1 = 0.0, 10.0; RT0, FH = 118.0, 130.0; PD = 2.5; MW = 3.0
YB = -10.0                             # the body's back plane: the stub (12 proud) runs into the boards' backs, hidden
                                       # (v2: v1 stood too far off the wall, with hidden clipping in the back)
STUB = (-18.5, 22.5); SURR = (-20.0, -18.5)
FX0, FX1 = -W / 2 + SW, W / 2 - SW
SECW = (FX1 - FX0 - 2 * MW) / 3
SECTIONS = [(FX0 + k * (SECW + MW), FX0 + k * (SECW + MW) + SECW, lo, hi) for k, (lo, hi) in enumerate((("E", "D"), ("C", "B"), ("A", "S")))]
BADGE_R = 8.5; HW = 62.0
CZ = FH + 9; CR = 15.5                 # the crest's roundel: centre, radius (v2: smaller; then down a hair)
TILE = 96.0                            # a tiling wood texture's repeat, in units (21 texels a unit at 2K)

for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene

# ---------------------------------------------------------------- building blocks: bmesh per shape
class Shape:
    def __init__(self, name):
        self.name = name; self.bm = bmesh.new(); self.uv = self.bm.loops.layers.uv.new("UVMap")
SH = {k: Shape(k) for k in ("Oak", "Planks", "Detail")}

def add_box(sh, lo, hi, grain="z", bevel=0.6, uvmode="tile", rect=None):
    """a chamfered box; tiling UVs with the grain along `grain`, or fitted into an atlas rect"""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector([lo[i] + (v.co[i] + 0.5) * (hi[i] - lo[i]) for i in range(3)])
    if bevel: bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, profile=0.5, affect='EDGES', clamp_overlap=True)
    _merge(sh, bm, grain, uvmode, rect, (lo, hi))

def add_prism(sh, pts, y0, y1, grain="x", bevel=0.4, uvmode="tile", rect=None, front_rect=None):
    """an outline (x, z) extruded from y0 (back) to y1 (front, more negative)"""
    bm = bmesh.new()
    vb = [bm.verts.new((x, y0, z)) for x, z in pts]; vf = [bm.verts.new((x, y1, z)) for x, z in pts]
    bm.faces.new(vf); bm.faces.new(list(reversed(vb)))
    for i in range(len(pts)):
        j = (i + 1) % len(pts); bm.faces.new((vb[i], vb[j], vf[j], vf[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if bevel: bmesh.ops.bevel(bm, geom=[e for e in bm.edges if e.calc_face_angle(0) > 0.5], offset=bevel, segments=1, profile=0.5, affect='EDGES', clamp_overlap=True)
    xs = [p[0] for p in pts]; zs = [p[1] for p in pts]
    _merge(sh, bm, grain, uvmode, rect, ((min(xs), y1, min(zs)), (max(xs), y0, max(zs))), front_rect)

def add_disc(sh, c, r, y0, y1, rect_face, rect_side=None, n=40):
    """a round plate facing -y: its face fitted to rect_face, its edge to rect_side (or the face's)"""
    bm = bmesh.new()
    rb = [bm.verts.new((c[0] + r * math.cos(2 * math.pi * k / n), y0, c[1] + r * math.sin(2 * math.pi * k / n))) for k in range(n)]
    rf = [bm.verts.new((c[0] + r * math.cos(2 * math.pi * k / n), y1, c[1] + r * math.sin(2 * math.pi * k / n))) for k in range(n)]
    face = bm.faces.new(rf)
    for k in range(n):
        j = (k + 1) % n; bm.faces.new((rb[k], rb[j], rf[j], rf[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    uvl = bm.loops.layers.uv.new("UVMap")
    u0, v0, u1, v1 = BL.uv(rect_face, 2)
    s0, t0, s1, t1 = BL.uv(rect_side or rect_face, 2)
    for f in bm.faces:
        for l in f.loops:
            p = l.vert.co
            if f.normal.y < -0.5:
                l[uvl].uv = (u0 + (u1 - u0) * ((p.x - c[0]) / (2 * r) + 0.5), v0 + (v1 - v0) * ((p.z - c[1]) / (2 * r) + 0.5))
            else:
                a = (math.atan2(p.z - c[1], p.x - c[0]) / (2 * math.pi)) % 1.0
                l[uvl].uv = (s0 + (s1 - s0) * a, t0 + (t1 - t0) * (0.5 if p.y == y0 else 0.4))
    _append(sh, bm, uvl)

def _merge(sh, bm, grain, uvmode, rect, bounds, front_rect=None):
    bm.normal_update()
    uvl = bm.loops.layers.uv.new("UVMap")
    lo, hi = Vector(bounds[0]), Vector(bounds[1]); ext = hi - lo
    off = (random.random(), random.random())
    for f in bm.faces:
        n = f.normal; ax = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            c = l.vert.co
            if ax == 0: u, v = c.y, c.z
            elif ax == 1: u, v = c.x, c.z
            else: u, v = c.x, c.y
            if uvmode == "tile":
                if grain == "x": u, v = v, u
                if ax == 2 and grain == "z": u, v = c.y, c.x          # a top/bottom face: the grain along the member
                l[uvl].uv = (u / TILE + off[0], v / TILE + off[1])
            else:                                                      # fitted: the part's extent into the rect
                r = front_rect if (front_rect and ax == 1 and n.y < 0) else rect
                u0, v0, u1, v1 = BL.uv(r, 2)
                if ax == 0: fu, fv = (c.y - lo.y) / max(ext.y, 1e-6), (c.z - lo.z) / max(ext.z, 1e-6)
                elif ax == 1: fu, fv = (c.x - lo.x) / max(ext.x, 1e-6), (c.z - lo.z) / max(ext.z, 1e-6)
                else: fu, fv = (c.x - lo.x) / max(ext.x, 1e-6), (c.y - lo.y) / max(ext.y, 1e-6)
                if front_rect and not (ax == 1 and n.y < 0):           # the sides of a fitted front: a thin strip of it
                    fv = 0.5 + 0.05 * fv
                l[uvl].uv = (u0 + (u1 - u0) * fu, v0 + (v1 - v0) * fv)
    _append(sh, bm, uvl)

def _append(sh, bm, uvl):
    """copy bm's geometry and UVs into the shape's bmesh"""
    vmap = {v: sh.bm.verts.new(v.co) for v in bm.verts}
    for f in bm.faces:
        try: nf = sh.bm.faces.new([vmap[v] for v in f.verts])
        except ValueError: continue
        for l, nl in zip(f.loops, nf.loops): nl[sh.uv].uv = l[uvl].uv
    bm.free()

def add_mesh_json(sh, data, xf, rect_uv, flip=False):
    """a mesh from JSON (v, f, uv per face corner), placed by xf (a function of a Vector), its UVs by rect_uv"""
    vs = [sh.bm.verts.new(xf(Vector(v))) for v in data["v"]]
    for f, uvs in zip(data["f"], data["uv"]):
        idx = list(reversed(f)) if flip else f
        uu = list(reversed(uvs)) if flip else uvs
        try: nf = sh.bm.faces.new([vs[i] for i in idx])
        except ValueError: continue
        for l, uv in zip(nf.loops, uu): l[sh.uv].uv = rect_uv(uv)

# ---------------------------------------------------------------- the board
# ---------------------------------------------------------------- organic timber (v3: organic pieces of wood with natural
# flowing imperfections, rough edges sanded down, and separate pieces joined together)
END_GRAIN = [(0.006, 0.308, 0.129, 0.421), (0.139, 0.308, 0.268, 0.421)]   # the oak texture's two end-grain squares (UV)
SIDE_V = (0.45, 0.98)                  # the oak's grain rows clear of those squares: a member's sides stay in them
PLANK_SEAMS = [5, 250, 506, 773, 1018, 1273, 1538, 1798, 2053]   # the plank texture's board seams (px): one board a plank

class Wobble:
    """smooth noise along a member: a few sines of random phase, 0 mean"""
    def __init__(self, rnd, amp, waves=(1.0, 2.3, 4.1)):
        self.t = [(amp * rnd.uniform(0.4, 1.0) / (1 + i), rnd.uniform(0.6, 1.4) * w, rnd.uniform(0, 6.28)) for i, w in enumerate(waves)]
    def __call__(self, t):
        return sum(a * math.sin(w * math.pi * t + p) for a, w, p in self.t)

def _profile(w, d, r, seg, split_front=0):
    """a rounded rectangle centred on 0, w across (a) by d deep (b; -b is the front), corner radii r[4]; the front edge
    split into split_front + 1 (so a plank can cup). Points anticlockwise from the front-right corner; the corners'
    points first (4 x (seg + 1)), the front's split points last"""
    corners = ((w / 2 - r[0], -d / 2 + r[0], -90), (w / 2 - r[1], d / 2 - r[1], 0), (-w / 2 + r[2], d / 2 - r[2], 90), (-w / 2 + r[3], -d / 2 + r[3], 180))
    pts = []
    for i, (cx, cy, a0) in enumerate(corners):
        for k in range(seg + 1):
            t = math.radians(a0 + 90 * k / seg); pts.append((cx + r[i] * math.cos(t), cy + r[i] * math.sin(t)))
    if split_front:                     # the front edge runs from the front-left corner's end to the front-right's start
        a, b = Vector(pts[-1]), Vector(pts[0])
        pts += [tuple(a + (b - a) * (k / (split_front + 1))) for k in range(1, split_front + 1)]
    return pts

def timber(sh, axis, s0, s1, ca, cb, w, d, seed, r=(0.5, 1.1), seg=2, step=9.0, bow=0.35, wander=0.18, edge=0.1,
           dings=2, caps=(True, True), tilt=(0.0, 0.0), uv="oak", board=0, split_front=0, cup=0.0):
    """one piece of wood along axis ('x' or 'z') from s0 to s1; its cross-section w across (in the board's plane) by d deep,
    centred at ca (across) and cb (y). Bowed a little, its width wandering, every arris sanded round to its own radius,
    a few dings; its sawn ends (caps) in end grain, cut a touch off square (tilt: along the member per unit across)"""
    rnd = random.Random(seed)
    L = s1 - s0; n = max(2, int(math.ceil(L / step)))
    bowA, bowB = Wobble(rnd, bow), Wobble(rnd, bow * 0.4)
    wid = Wobble(rnd, wander); dep = Wobble(rnd, wander * 0.4)
    rad = [Wobble(rnd, (r[1] - r[0]) / 2, (1.3, 3.1)) for _ in range(4)]
    eno = [Wobble(rnd, edge, (5.0, 9.0, 13.0)) for _ in range(4)]
    NC = 4 * (seg + 1)                                      # the corners' points in a ring
    ding = [(rnd.randrange(1, n), rnd.randrange(4), rnd.uniform(0.25, 0.6)) for _ in range(dings)] if n > 2 else []
    ou = rnd.random(); ov = rnd.uniform(SIDE_V[0], max(SIDE_V[0], SIDE_V[1] - 2 * (w + d) / TILE))
    nominal = _profile(w, d, [(r[0] + r[1]) / 2] * 4, seg, split_front)
    order = list(range(NC)) + list(range(NC, len(nominal)))
    if split_front:                                         # walk the ring in order round the outline: the split points
        order = list(range(NC)) + list(range(NC, len(nominal)))   # sit between the last corner and the first
    arc = [0.0]
    for i in range(1, len(order) + 1):
        arc.append(arc[-1] + (Vector(nominal[order[i % len(order)]]) - Vector(nominal[order[i - 1]])).length)
    def place(a, b, s):
        return Vector((ca + a, cb + b, s)) if axis == "z" else Vector((s, cb + b, ca + a))
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    rings = []
    for i in range(n + 1):
        t = i / n
        ww = w + 2 * wid(t); dd = d + 2 * dep(t)
        rr = [max(0.15, min(min(ww, dd) / 2 - 0.05, (r[0] + r[1]) / 2 + rad[k](t))) for k in range(4)]
        prof = _profile(ww, dd, rr, seg, split_front)
        s = s0 + L * t
        ring = []
        for j in order:
            a, b = prof[j]; a2, b2 = a, b
            if j < NC:                                      # the arris' own small irregularity, and the dings
                c = j // (seg + 1); ln = math.hypot(a, b) or 1
                a2 += a / ln * eno[c](t); b2 += b / ln * eno[c](t)
                for (di, dc, dv) in ding:
                    if i == di and c == dc: a2 -= a / ln * dv; b2 -= b / ln * dv
            if cup and b < -dd / 2 + 0.01:                  # a plank's face cupping a little
                b2 -= cup * (1 - (2 * a / ww) ** 2)
            ss = s + (tilt[0] * a if i == 0 else tilt[1] * a if i == n else 0.0)
            ring.append(bm.verts.new(place(a2 + bowA(t), b2 + bowB(t), ss)))
        rings.append((ring, s))
    m = len(order)
    for i in range(n):
        (ra, sa), (rb, sb) = rings[i], rings[i + 1]
        for j in range(m):
            k = (j + 1) % m
            f = bm.faces.new((ra[j], ra[k], rb[k], rb[j]))
            for l, (av, ss) in zip(f.loops, ((arc[j], sa), (arc[j + 1], sa), (arc[j + 1], sb), (arc[j], sb))):
                l[uvl].uv = (ss / TILE + ou, ov + av / TILE)
    if uv == "plank":                                       # the front onto one board of the texture, between its seams;
        nb = len(PLANK_SEAMS) - 1                           # the grain runs along the plank (the texture's v)
        px0, px1 = PLANK_SEAMS[board % nb] + 8, PLANK_SEAMS[board % nb + 1] - 8
        ku = ((px1 - px0) / 2048) / w; uc = (px0 + px1) / 2 / 2048; ov2 = rnd.random()
        for f in bm.faces:
            for l in f.loops:
                p = l.vert.co
                a_ = (p.x - ca) if axis == "z" else (p.z - ca)
                along = p.z if axis == "z" else p.x
                l[uvl].uv = (uc + a_ * ku * (1.0 if f.normal.y < -0.5 else 0.3), along / TILE + ov2)
    for which, (ring, s) in ((0, rings[0]), (1, rings[-1])):
        if not caps[which]: continue
        f = bm.faces.new(list(reversed(ring)) if which == 0 else ring)
        u0, v0, u1, v1 = END_GRAIN[rnd.randrange(2)]
        for l in f.loops:
            p = l.vert.co; a_ = (p.x - ca) if axis == "z" else (p.z - ca); b_ = p.y - cb
            l[uvl].uv = (u0 + (u1 - u0) * (a_ / (w + 0.6) + 0.5), v0 + (v1 - v0) * (b_ / (max(w, d) + 0.6) + 0.5))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    _append(sh, bm, uvl)

def peg(sh, x, z, yface, seed, r=0.62):
    """an oak peg through a joint, its end standing a hair proud, end grain on it"""
    rnd = random.Random(seed); n = 8
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    out = yface - rnd.uniform(0.12, 0.3)
    back = [bm.verts.new((x + r * math.cos(2 * math.pi * k / n), yface + 1.5, z + r * math.sin(2 * math.pi * k / n))) for k in range(n)]
    front = [bm.verts.new((x + r * math.cos(2 * math.pi * k / n) * (0.92 + 0.08 * rnd.random()), out, z + r * math.sin(2 * math.pi * k / n))) for k in range(n)]
    cap = bm.faces.new(front)
    u0, v0, u1, v1 = END_GRAIN[rnd.randrange(2)]; cu, cv = rnd.uniform(0.3, 0.7), rnd.uniform(0.3, 0.7)
    for l in cap.loops:
        p = l.vert.co; l[uvl].uv = (u0 + (u1 - u0) * (cu + (p.x - x) * 0.04), v0 + (v1 - v0) * (cv + (p.z - z) * 0.04))
    for k in range(n):
        j = (k + 1) % n; f = bm.faces.new((back[k], back[j], front[j], front[k]))
        for l, (kk, yy) in zip(f.loops, ((k, 1), (j, 1), (j, 0), (k, 0))): l[uvl].uv = (0.5 + kk * 0.01, 0.6 + yy * 0.02)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    _append(sh, bm, uvl)

def body():
    """the frame: stiles full height, the rails tenoned through them (their tenons' ends showing past the stiles' outer
    faces), two pegs a joint; the mullions housed in the rails and pegged; the field's planks each its own board"""
    yc, yf = YB - SD / 2, YB - SD
    for s in (-1, 1):                                       # stiles
        timber(SH["Oak"], "z", 0.0, FH, s * (W / 2 - SW / 2), yc, SW, SD, 100 + s, r=(0.5, 1.2), tilt=(0.04 * s, -0.03 * s))
    for (z0, z1), sd in (((RB0, RB1), 7), ((RT0, FH), 9)):  # rails, between the stiles
        h = z1 - z0; zc = (z0 + z1) / 2
        timber(SH["Oak"], "x", -W / 2 + SW - 0.2, W / 2 - SW + 0.2, zc, yc + 0.25, h, SD - 0.5, 200 + sd, r=(0.45, 1.1), caps=(False, False))
        for s in (-1, 1):
            # its tenon through the stile, 1.4 proud of the stile's outer face
            x0, x1 = sorted((s * (W / 2 - SW * 0.6), s * (W / 2 + 1.4)))
            timber(SH["Oak"], "x", x0, x1, zc, yc, h * 0.55, SD * 0.55, 300 + sd + s, r=(0.25, 0.45), step=4, bow=0.05,
                   wander=0.05, dings=0, caps=(s < 0, s > 0))
            for dz in (-h * 0.22, h * 0.22):
                peg(SH["Oak"], s * (W / 2 - SW / 2), zc + dz, yf - 0.02, 400 + sd * 10 + s + int(dz))
    for k in (1, 2):                                        # mullions, housed in the rails
        x = SECTIONS[k][0] - MW / 2
        timber(SH["Oak"], "z", RB1 - 0.6, RT0 + 0.6, x, YB - PD - 1.0, MW, 2.6, 500 + k, r=(0.35, 0.8), step=10, caps=(False, False))
        peg(SH["Oak"], x, (RB0 + RB1) / 2, yf - 0.02, 600 + k); peg(SH["Oak"], x, (RT0 + FH) / 2, yf - 0.02, 610 + k)
    # the field's planks: widths a little uneven, small gaps, each cupped a hair
    rnd = random.Random(31); widths = []; left = FX1 - FX0
    while left > 0.1:
        wv = rnd.uniform(17.5, 23.0); wv = left if left - wv < 12 else wv; widths.append(wv); left -= wv
    x = FX0
    for i, wv in enumerate(widths):
        gap = rnd.uniform(0.25, 0.55); x0, x1 = x + gap / 2, x + wv - gap / 2; x += wv
        d = PD + rnd.uniform(-0.25, 0.25)
        PLANKS.append((x0, x1, d))
        timber(SH["Planks"], "z", RB1 - 1.0, RT0 + 1.0, (x0 + x1) / 2, YB - d / 2, x1 - x0, d, 700 + i, r=(0.2, 0.55), seg=2,
               step=12, bow=0.15, wander=0.25, edge=0.08, dings=1, caps=(False, False), uv="plank", board=rnd.randrange(8),
               split_front=2, cup=0.18)
PLANKS = []
def plank_front(x):
    return YB - next((d for x0, x1, d in PLANKS if x0 - 0.3 <= x <= x1 + 0.3), PD)

def iron_bits(nails):
    ir = BL.DETAIL["iron"]; yf = YB - SD
    L, T = 15.0, 4.0
    for sx in (-1, 1) if OPT.get("plates") == "1" else ():   # v3: off by default, the pegged joints show instead
        for sz, zc in ((-1, 0.0), (1, FH)):
            xo, zo = sx * W / 2, zc
            pts = [(xo - sx * px, zo - sz * pz) for px, pz in ((0, 0), (L, 0), (L, T), (T, T), (T, L), (0, L))]
            add_prism(SH["Detail"], pts, yf + 0.01, yf - 0.7, "x", 0.2, "fit", ir)
            for px, pz in ((L - 2.2, T / 2), (T / 2, L - 2.2), (T / 2, T / 2)):
                add_disc(SH["Detail"], (xo - sx * px, zo - sz * pz), 0.8, yf - 0.7, yf - 1.3, ir, n=8)
    for sx in (-1, 1):                                     # the straps over the top rail, into the wall
        x = sx * (W / 2 - 26)
        add_box(SH["Detail"], (x - 2.2, yf - 0.8, FH), (x + 2.2, 0, FH + 0.9), "x", 0.2, "fit", ir)
        add_box(SH["Detail"], (x - 2.2, yf - 0.8, FH - 11), (x + 2.2, yf, FH + 0.9), "x", 0.2, "fit", ir)
        add_disc(SH["Detail"], (x, FH - 7), 0.9, yf - 0.8, yf - 1.5, ir, n=8)
    for (x, z) in nails:                                   # the notices' nails (they stay when a notice is taken down)
        add_disc(SH["Detail"], (x, z), 0.75, YB - PD - 0.2, YB - PD - 1.5, ir, n=8)

def cleats():
    """the stand-off: oak cleats on the wall behind the body, their sawn ends showing past its sides; notched round the stub"""
    nx0, nx1 = SURR[0] - 0.5, STUB[1] + 0.5
    for n_, (z0, z1) in enumerate(((14.0, 24.0), (RT0 - 14.0, RT0 - 4.0))):
        for m_, (x0, x1) in enumerate(((-W / 2 - 4, nx0), (nx1, W / 2 + 4))):
            timber(SH["Oak"], "x", x0, x1, (z0 + z1) / 2, YB / 2, z1 - z0, -YB, 800 + n_ * 2 + m_, r=(0.4, 0.9), step=12,
                   tilt=(0.06, -0.05))

def badges():
    zc = (RT0 + FH) / 2; yf = YB - SD
    for x0, x1, lo, hi in SECTIONS:
        for xc, r in ((x0 + (x1 - x0) * 0.3, lo), (x0 + (x1 - x0) * 0.7, hi)):
            add_disc(SH["Detail"], (xc, zc), BADGE_R + 0.7, yf + 0.1, yf - 0.5, BL.DETAIL["iron"], n=32)
            add_disc(SH["Detail"], (xc, zc), BADGE_R, yf - 0.5, yf - 1.1, BL.badge_rect(r), BL.DETAIL["iron"], n=40)

def header():
    z0, z1 = FH - 2, FH + 13; y0, y1 = YB, YB - SD - 1.0
    pts = [(-HW, z0), (HW, z0), (HW, z0 + 4), (HW - 4, z1 - 2), (18, z1), (-18, z1), (-HW + 4, z1 - 2), (-HW, z0 + 4)]
    # its front wears the knotwork band (the detail atlas), its edges the oak: two prisms sharing the outline
    add_prism(SH["Detail"], pts, y1 + 0.02, y1, "x", 0.0, "fit", BL.DETAIL["knot"], BL.DETAIL["knot"])
    add_prism(SH["Oak"], pts, y0, y1 + 0.02, "x", 0.5)
    add_box(SH["Oak"], (-HW + 2, y1 - 1.2, z0 + 1.0), (HW - 2, y1 + 0.2, z0 + 3.0), "x", 0.4)      # the moulding under it
    head = json.load(open(os.path.join(PRIV, "maps", "head", "head_low.json")))
    hsc = float(OPT.get("head", 1.2)); hy = (y0 + y1) / 2    # 0.85 too small, 1.45 too large: 1.2
    def huv(uv): return (uv[0] * 0.5, uv[1] * 768 / 2048)
    for s in (-1, 1):
        base = Vector((s * (HW - 3), 0, z0 + 3))
        add_mesh_json(SH["Detail"], head, lambda v, s=s, base=base: Vector((base.x + s * v.x * hsc, hy + v.y * hsc, base.z + v.z * hsc)), huv, flip=(s < 0))
    # the roundel and the hall's relief crest on it
    add_disc(SH["Detail"], (0, CZ), CR, YB - 0.5, YB - SD - 2.0, BL.DETAIL["roundel"], BL.DETAIL["roundel"], n=64)
    crest = json.load(open(os.path.join(HERE, "..", "..", "hall-private", "assets", "crest3d", "crest_low.json")))
    k = 27.0 / 242.0; yface = YB - SD - 2.0
    cu0, cv0, cu1, cv1 = BL.uv(BL.DETAIL["crest"])
    # its 9669 triangles are for 242 across; at 40 a third of them carry the same shape (a collapse keeping the UVs)
    tmp = Shape("crest")
    add_mesh_json(tmp, crest, lambda v: Vector((v.x * k, yface - v.z * k, CZ + v.y * k)),
                  lambda uv: (cu0 + uv[0] * (cu1 - cu0), cv0 + uv[1] * (cv1 - cv0)))      # a turn, not a mirror
    me = bpy.data.meshes.new("crest_tmp"); tmp.bm.to_mesh(me); tmp.bm.free()
    o = bpy.data.objects.new("crest_tmp", me); sc.collection.objects.link(o)
    dm = o.modifiers.new("dec", 'DECIMATE'); dm.ratio = float(OPT.get("crest", 0.33)); dm.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier="dec")
    bm = bmesh.new(); bm.from_mesh(o.data); uvl = bm.loops.layers.uv.active
    _append(SH["Detail"], bm, uvl); bpy.data.objects.remove(o, do_unlink=True)

# ---------------------------------------------------------------- the notices: (design cell, section, x across 0..1, top, width, rotation)
NJ = json.load(open(os.path.join(PRIV, "notices", "out", "notices.json")))
CELL = {n["name"]: n for n in NJ["notices"]}
# the board in three variants (a few variations of the postings, so they look like they rotate): each
# pins its own selection, by rank (E-D left, C-B middle, A-S right). (name, section, x across 0..1, top, width, rotation);
# section "drape": nailed by its top-left corner at (x, top), absolute, lying out over the frame and past its edge (v5);
# tops on v1's 98-tall field (scaled to the field). Pinned in order: a later one lies over an earlier one where they meet.
PLANS = {
    "A": [   # a working day: gathering and deliveries
        ("ore", 0, 0.20, 105, 27, -3), ("delivery", 0, 0.55, 106.5, 28, 2.5), ("ingredients", 0, 0.85, 103, 21, 4),
        ("mudcrab", 0, 0.22, 54, 26, 2.5), ("bear", 0, 0.57, 56, 28, -2), ("spider", 0, 0.85, 70, 23, -3),
        ("troll", 1, 0.26, 106, 28, 2), ("jarl", 1, 0.74, 104.5, 28, -1.5), ("soulgems", 1, 0.25, 50, 22, -2), ("spriggan", 1, 0.68, 56, 27, 2),
        ("hagraven", 2, 0.30, 102, 30, -1), ("dragon", 2, 0.71, 94, 31, 1.5),
        ("stub", 2, 0.28, 48, 10, 6), ("stub", 2, 0.66, 40, 9, -8), ("stub", 1, 0.50, 26, 9, 3)],
    "B": [   # the jarl's bounty up, a deathlord to hunt
        ("stub", 0, 0.22, 104, 10, -7), ("spider", 0, 0.52, 106, 27, 2), ("delivery", 0, 0.82, 100, 25, -2),   # v5: its top-left taken
        ("mudcrab", 0, 0.30, 56, 26, 3), ("soulgems", 1, 0.72, 48, 21, -3),
        ("jarl", 1, 0.48, 106, 31, -1), ("troll", 1, 0.25, 52, 26, -2.5),
        ("draugr", 2, 0.28, 104, 28, 1.5), ("hagraven", 2, 0.70, 96, 29, -1.5),
        ("stub", 0, 0.82, 52, 9, 5), ("stub", 1, 0.80, 92, 10, -6), ("stub", 1, 0.45, 28, 9, 4), ("stub", 2, 0.50, 40, 9, 7),
        ("stub", 0, 0.60, 30, 9, -5)],
    "C": [   # a quiet day
        ("ore", 0, 0.25, 104, 27, 2), ("mudcrab", 0, 0.72, 106, 26, -2), ("bear", 0, 0.30, 54, 28, 1.5),
        ("delivery", 0, 0.70, 58, 25, -2), ("ingredients", 0, 0.86, 34, 20, 5),
        ("spriggan", 1, 0.30, 105, 27, -2), ("soulgems", 1, 0.76, 100, 22, 3), ("troll", 1, 0.62, 54, 27, -1.5),
        ("draugr", 2, 0.30, 100, 28, -1), ("dragon", 2, 0.72, 105, 31, 2),
        ("stub", 1, 0.22, 42, 9, -5), ("stub", 2, 0.50, 36, 10, 6), ("stub", 0, 0.15, 30, 9, -4),
        ("spider", "drape", 95.7, 36.6, 27, 6)],   # v5: on the board, its corner out over the frame's edge
}
VARIANT = OPT.get("variant", "A")
PLAN = PLANS[VARIANT]
def notice_shapes():
    out, nails = [], []
    for k, (name, si, u, top, w, rot) in enumerate(PLAN):
        if name == "stub":                     # the torn foot of a half-sheet (the halves' cell, its lower one's ragged bottom)
            cell = CELL["halves"]; u0, v0, u1, v1 = cell["uv"]
            uvr = (u0 + (u1 - u0) * (0.1 + 0.4 * (k % 2)), v0 + (v1 - v0) * 0.0, u0 + (u1 - u0) * (0.5 + 0.4 * (k % 2)), v0 + (v1 - v0) * 0.12)
            h = w * 0.55
        elif name in ("ingredients", "soulgems"):   # the halves' cell: ingredients on top, soul gems below
            cell = CELL["halves"]; u0, v0, u1, v1 = cell["uv"]; vm = (v0 + v1) / 2
            uvr = (u0, vm, u1, v1) if name == "ingredients" else (u0, v0, u1, vm)
            h = w * (CH_ / 2) / CW_
        else:
            cell = CELL[name]; uvr = cell["uv"]; h = w * CH_ / CW_
        frame = si == "drape"                  # nailed by its top-left corner (u, top: absolute), out over the frame's edge
        if not frame:
            x0, x1 = SECTIONS[si][:2]; cx = x0 + (x1 - x0) * u
            top = RB1 + (top - RB1) * (RT0 - RB1) / 98.0     # the plan was laid on v1's 98-tall field
        else: cx = u
        bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
        nx, nz = (12, 16) if frame else (6, 8); vs = {}
        for i in range(nx + 1):
            for j in range(nz + 1):
                a, b = i / nx, j / nz
                x = (a - (0.0 if frame else 0.5)) * w; z = -(1 - b) * h
                lift = 1.6 * ((abs(a - 0.5) * 2) ** 2) * ((1 - b) ** 2) + 0.25 * math.sin(math.pi * a) * (1 - b)
                vs[i, j] = bm.verts.new((x, -lift, z))
        for i in range(nx):
            for j in range(nz):
                f = bm.faces.new((vs[i, j], vs[i + 1, j], vs[i + 1, j + 1], vs[i, j + 1]))   # anticlockwise seen from -y: facing it
                for l, (a, b) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                    l[uvl].uv = (uvr[0] + (uvr[2] - uvr[0]) * a / nx, uvr[1] + (uvr[3] - uvr[1]) * b / nz)
        R = Matrix.Rotation(math.radians(rot), 4, 'Y'); T = Matrix.Translation((cx, YB - PD - 0.4 - k * 0.03, top))   # clear of the proudest board
        bmesh.ops.transform(bm, matrix=T @ R, verts=bm.verts[:])
        if frame:                              # the sheet lies on the planks and over the frame (2 proud) where it crosses it: each
            from mathutils.bvhtree import BVHTree      # point clear of the oak in front of it, the step eased over a few cells;
            tree = BVHTree.FromBMesh(SH["Oak"].bm)     # past the board's edge it stays at the frame's height, in the air
            g = {key: v for key, v in vs.items()}
            for v in bm.verts:
                hit = tree.ray_cast(Vector((v.co.x, -60.0, v.co.z)), Vector((0, 1, 0)), 60.0)[0]
                if hit is not None: v.co.y = min(v.co.y, hit.y - 0.3)
            out_x = [v for (i, j), v in g.items() if v.co.x > W / 2 + 0.5 or v.co.z < -0.5]
            for v in out_x: v.co.y = min(v.co.y, YB - SD - 0.6)
            for _ in range(4):
                ys = {key: v.co.y for key, v in g.items()}
                for (i, j), v in g.items():
                    nb = [ys[i + di, j + dj] for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)) if (i + di, j + dj) in ys]
                    v.co.y = min(v.co.y, sum(nb) / len(nb))
        me = bpy.data.meshes.new(f"Notice{k:02d}"); bm.to_mesh(me); bm.free()
        out.append((f"AGBoardNotice{k:02d}_{name}", me))
        p = T @ R @ Vector((1.6 if frame else 0, 0, -1.6)); nails.append((p.x, p.z))
    return out, nails
CW_, CH_ = NJ["cell"]

# v5: 0.75 of v4's size, mounted on the top rail's front face, the sign board centred on the rail
HDR = float(OPT.get("hdr", 0.75))     # the whole header (sign board, heads, roundel, crest) scaled as one about its foot
HFOOT = float(OPT.get("hfoot", 118.4))    # where the sign board's foot lands (v4: on top of the top rail, FH - 2)
HBACK = float(OPT.get("hback", -14.0))    # its back's plane: the rail's face (v4: YB, in line with the frame)
def scaled_header():                   # v5: v4's header out of proportion, so scaled and mounted on the top rail's front face
    before = {k: set(SH[k].bm.verts) for k in ("Oak", "Detail")}
    header()
    piv = Vector((0, YB, FH - 2)); to = Vector((0, HBACK, HFOOT))
    for k in before:
        for v in SH[k].bm.verts:
            if v not in before[k]: v.co = to + (v.co - piv) * HDR
body(); cleats(); scaled_header()
notices, nails = notice_shapes()

WEAR = Shape("Wear")
def wear():
    """what earlier notices left (v2): nail holes, pin
    pricks, rust run down from old nails, torn scraps still under theirs; decals a hair off the boards, alpha-tested"""
    rnd = random.Random(23); cells = BL.wear_cells(); old_nails = []
    def quad(kind, i, x, z, w, h, rot=0.0):
        u0, v0, u1, v1 = BL.uv(cells[kind][i % len(cells[kind])], 1)
        y = plank_front(x) - 0.04
        R = Matrix.Rotation(math.radians(rot), 2)
        cs = [(-w / 2, -h), (w / 2, -h), (w / 2, 0), (-w / 2, 0)] if kind == "rust" else [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
        vs = [WEAR.bm.verts.new((x + (R @ Vector(c)).x, y, z + (R @ Vector(c)).y)) for c in cs]
        f = WEAR.bm.faces.new(vs)
        for l, (a, b) in zip(f.loops, ((u0, v0), (u1, v0), (u1, v1), (u0, v1))): l[WEAR.uv].uv = (a, b)
    def spot():
        while True:
            x = rnd.uniform(FX0 + 2, FX1 - 2); z = rnd.uniform(RB1 + 3, RT0 - 3)
            if all(abs(x - (SECTIONS[k][0] - MW / 2)) > 3 for k in (1, 2)): return x, z
    for i in range(46): x, z = spot(); quad("hole", i, x, z, 1.3, 1.3, rnd.uniform(0, 360))
    for i in range(10): x, z = spot(); quad("pins", i, x, z, 2.2, 2.2, rnd.uniform(0, 360))
    for i in range(7):
        x, z = spot(); quad("rust", i, x, z - 0.3, 1.4, 4.2); old_nails.append((x, z))
    for i in range(6):
        x, z = spot(); quad("scrap", i, x, z - 1.2, 4.2, 4.2, rnd.uniform(-25, 25)); old_nails.append((x, z))
    return old_nails
old = wear()
iron_bits(nails + old)

# ---------------------------------------------------------------- the templates: shader settings, root, collision
bpy.ops.import_scene.pynifly(filepath=os.path.join(TPL, "meshes", "architecture", "whiterun", "wrinteriors", "wrcastle", "wrintcastleroofflatstr01quad.nif"))
objs = list(bpy.data.objects)
root = next(o for o in objs if o.get("pynRoot"))
proto = next(o for o in objs if o.type == 'MESH' and o.get("pynBlockName") == "BSTriShape")
coll = next(o for o in objs if o.type == 'MESH' and o.name.startswith("bhk"))
opaque = proto.active_material
bpy.ops.import_scene.pynifly(filepath=os.path.join(TPL, "meshes", "architecture", "whiterun", "wrclutter", "wrjovaskrbanner02.nif"))
banner = [o for o in bpy.data.objects if o not in objs]
alpha_mat = next(o.active_material for o in banner if o.type == 'MESH' and o.active_material and "NiAlphaProperty_flags" in o.active_material)
alpha_mat.use_fake_user = True; opaque.use_fake_user = True
for o in banner: bpy.data.objects.remove(o, do_unlink=True)

def material(base, stem):
    m = base.copy(); m.name = stem
    m["BSShaderTextureSet_Diffuse"] = TEXP + stem + ".dds"
    m["BSShaderTextureSet_Normal"] = TEXP + stem + "_n.dds"
    for k in list(m.keys()):
        if k.startswith("BSShaderTextureSet_") and k not in ("BSShaderTextureSet_Diffuse", "BSShaderTextureSet_Normal"): m[k] = ""
    for n in m.node_tree.nodes:                     # the preview images (Blender's own render of the import)
        if n.type == 'TEX_IMAGE' and n.image:
            nm = n.image.filepath.lower()
            p = os.path.join(PRIV, "maps", "atlas", stem + ("_n.png" if nm.endswith("_n.dds") else ".png"))
            if os.path.exists(p): n.image = bpy.data.images.load(p, check_existing=True)
    return m

def make_obj(name, me, mat):
    me.materials.clear(); me.materials.append(mat)
    for p in me.polygons: p.use_smooth = True
    me.set_sharp_from_angle(angle=math.radians(40))       # chamfers and box edges crisp, the carving and paper smooth
    o = bpy.data.objects.new(name, me); proto.users_collection[0].objects.link(o)
    for k in proto.keys():
        if k != "pynNodeName": o[k] = proto[k]
    o["pynNodeName"] = name; o.parent = root
    return o

made = []
for key, stem in (("Oak", "AGBoardOak"), ("Planks", "AGBoardPlanks"), ("Detail", "AGBoardDetail")):
    sh = SH[key]
    bmesh.ops.remove_doubles(sh.bm, verts=sh.bm.verts[:], dist=0.0001)
    bmesh.ops.triangulate(sh.bm, faces=sh.bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    me = bpy.data.meshes.new("AGBoard" + key); sh.bm.to_mesh(me); sh.bm.free()
    made.append(make_obj("AGBoard" + key, me, material(opaque, stem)))
def alpha_test(stem):
    """the banner's material for its alpha test (PyNifly writes a NiAlphaProperty only from a wired alpha node), with the
    opaque template's shader flags. v1 kept the banner's own: SKINNED (and VERTEX_ALPHA, VERTEX_COLORS, for its cloth),
    and the game draws nothing of an unskinned shape flagged skinned: the notices were missing in game"""
    m = material(alpha_mat, stem)
    m.pyn_shader.Shader_Flags_1 = opaque.pyn_shader.Shader_Flags_1
    m.pyn_shader.Shader_Flags_2 = opaque.pyn_shader.Shader_Flags_2
    return m
nmat = alpha_test("AGBoardNotices")
for name, me in notices:
    made.append(make_obj(name, me, nmat))
bmesh.ops.triangulate(WEAR.bm, faces=WEAR.bm.faces[:])
me = bpy.data.meshes.new("AGBoardWear"); WEAR.bm.to_mesh(me); WEAR.bm.free()
made.append(make_obj("AGBoardWear", me, alpha_test("AGBoardDetail")))
# the grime (v3): occlusion baked into vertex colours, so the joints, the corners and the wood under the rails darken as
# handled, aged wood does; and every piece of timber its own shade, a little (separate boards never quite match)
from mathutils.bvhtree import BVHTree
def grime(targets, blockers, reach=3.0, rays=16):
    vs, ps = [], []
    for o in blockers:
        base = len(vs); vs += [o.matrix_world @ v.co for v in o.data.vertices]
        ps += [[base + i for i in p.vertices] for p in o.data.polygons]
    tree = BVHTree.FromPolygons(vs, ps)
    gold = math.pi * (3 - math.sqrt(5))
    dirs = [Vector((math.cos(gold * i) * math.sqrt(1 - ((i + 0.5) / rays)), math.sin(gold * i) * math.sqrt(1 - ((i + 0.5) / rays)), math.sqrt((i + 0.5) / rays))) for i in range(rays)]
    for o in targets:
        me = o.data
        bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
        tint = [1.0] * len(me.vertices); seen = set(); rnd = random.Random(77)
        for v in bm.verts:                                  # each island (one piece of wood): its own shade
            if v.index in seen: continue
            t = rnd.uniform(0.86, 1.06); stack = [v]; seen.add(v.index)
            while stack:
                u = stack.pop(); tint[u.index] = t
                for e in u.link_edges:
                    w_ = e.other_vert(u)
                    if w_.index not in seen: seen.add(w_.index); stack.append(w_)
        bm.free()
        attr = me.color_attributes.new("VERTEX_COLOR", 'FLOAT_COLOR', 'POINT')
        for v in me.vertices:
            n = v.normal.normalized(); q = n.to_track_quat('Z', 'Y')
            p = o.matrix_world @ v.co + n * 0.03; occ = 0.0
            for d in dirs:
                hit = tree.ray_cast(p, q @ d, reach)
                if hit[0] is not None: occ += 1 - hit[3] / reach
            ao = 1 - 0.75 * occ / rays
            c = max(0.25, min(1.0, ao)) * tint[v.index]
            attr.data[v.index].color = (c, c * 0.985, c * 0.965, 1.0)
        me.color_attributes.active_color = attr
        m = me.materials[0]
        if "VERTEX_COLORS" not in m.pyn_shader.Shader_Flags_2:
            m.pyn_shader.Shader_Flags_2 = m.pyn_shader.Shader_Flags_2 + " | VERTEX_COLORS"
    print("GRIME", [o.name for o in targets])
wood = [o for o in made if o.name in ("AGBoardOak", "AGBoardPlanks")]
grime(wood, [o for o in made if o.name in ("AGBoardOak", "AGBoardPlanks", "AGBoardDetail")])

# the collision: one box round the body and the cleats (y 0 .. the body's front), up to the sign board's top
lo = Vector((-W / 2 - 4, YB - SD, 0)); hi = Vector((W / 2 + 4, 0, max(FH, HFOOT + 15 * HDR)))
ctr = (lo + hi) / 2; half = (hi - lo) / 2
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=2.0)
for v in bm.verts: v.co = ctr + Vector((v.co.x * half.x, v.co.y * half.y, v.co.z * half.z))
bm.to_mesh(coll.data); bm.free(); coll.location = (0, 0, 0)

# the template's own shape goes; ours stay
bpy.data.objects.remove(proto, do_unlink=True)
root["pynNodeName"] = "AGGuildBoard"; root.name = "AGGuildBoard"
os.makedirs(os.path.dirname(DST), exist_ok=True)
bpy.ops.object.select_all(action='SELECT'); bpy.context.view_layer.objects.active = root
bpy.ops.export_scene.pynifly(filepath=DST)
tri = {o.name: len(o.data.polygons) for o in made}
print("EXPORTED", DST); print("SHAPES", tri); print("TOTAL TRIANGLES", sum(tri.values()))
