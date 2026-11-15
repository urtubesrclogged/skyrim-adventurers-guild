"""Headless Blender: the Guild Board, built from parameters, on a mock of its wall (the tower foot's front face in the great
hall, from REQUIREMENTS.md), rendered from a standing player's eye and closer.
    blender -b -P board_gen.py -- <out dir> <tag> [views=front,34,close,hall] [blend=1]

Units are game units. The board's frame: x right, the wall plane at y 0, its front toward -y, z up from its bottom (the
origin the NIF will have). The scene puts that origin on the wall at the board's height above the great hall's floor."""
import sys, os, math, random, bpy, bmesh
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[sys.argv.index("--") + 1:]
OUT, TAG = os.path.abspath(args[0]), args[1]
OPT = dict(a.split("=", 1) for a in args[2:] if "=" in a)
VIEWS = OPT.get("views", "front,34,close,hall").split(",")
HALLTEX = os.path.join(HERE, "..", "..", "hall-private", "assets", "textures", "AdventurersGuild", "Hall2")
SP = os.environ.get("BOARD_CACHE", os.path.join(HERE, "cache"))      # vanilla textures pulled from the BSAs
AGTEX = os.environ.get("AG_TEX", os.path.join(HERE, "..", "..", "..", "config", "PrismaUI", "views", "AdventurersGuild", "tex"))  # AG's own UI art, in the checkout this sits in
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- the design's numbers (DESIGN.md)
# Landscape, at the planned size (about 240 x 170, hall
# x 237..480, across the stone stub at the arcade's last arch): three rank sections side by side, low ranks on the left.
# The board stands off the wall on oak battens; the stub (40 wide, 12 proud) runs behind it in the gap.
W = float(OPT.get("w", 240))           # the frame's width
YB = -12.5                             # the board body's back plane: 0.5 in front of the stub's face (12 proud)
STUB = (-18.5, 22.5, 12.0)             # the stub across the board's back (local x), and how proud it is
SURR = (-20.0, -18.5, 1.5)             # its arch surround on the stub's left corner
SW, SD = 9.0, 5.0                      # stile width, frame depth (proud of the wall)
RB0, RB1 = 0.0, 10.0                   # bottom rail
RT0, FH = 112.0, 128.0                 # top rail (tall enough for the rank badges), the frame's top
PD = 2.5                               # field boards' depth
MID_Z = 125.0                          # the notices' middle above the floor (not REQUIREMENTS' 150)
Z0 = float(OPT.get("z0", MID_Z - (RB1 + RT0) / 2))   # the board's bottom above the great hall's floor
FX0, FX1 = -W / 2 + SW, W / 2 - SW     # the field
MW = 3.0                               # a mullion's width
SECW = (FX1 - FX0 - 2 * MW) / 3        # a section's width
SECTIONS = [(FX0 + k * (SECW + MW), FX0 + k * (SECW + MW) + SECW, lo, hi) for k, (lo, hi) in enumerate((("E", "D"), ("C", "B"), ("A", "S")))]
BADGE_R = 6.0                          # a rank badge's radius, on the top rail

random.seed(7)
scene = bpy.context.scene
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)

# ---------------------------------------------------------------- materials
def img(path, non_color=False):
    if not os.path.exists(path): print("NO IMAGE", path); return None
    im = bpy.data.images.load(path, check_existing=True)
    if non_color: im.colorspace_settings.name = "Non-Color"
    return im

def mat_tex(name, diffuse, normal=None, rough=0.75, tint=None, metal=0.0, alpha=False, scale=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metal
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img(diffuse)
    col = t.outputs["Color"]
    if tint:
        mix = nt.nodes.new("ShaderNodeMixRGB"); mix.blend_type = 'MULTIPLY'; mix.inputs[0].default_value = 1.0
        mix.inputs[2].default_value = (*tint, 1); nt.links.new(col, mix.inputs[1]); col = mix.outputs[0]
    nt.links.new(col, b.inputs["Base Color"])
    if alpha:
        nt.links.new(t.outputs["Alpha"], b.inputs["Alpha"])
        try: m.blend_method = 'CLIP'
        except Exception: pass
    if normal and os.path.exists(normal):
        tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = img(normal, True)
        sep = nt.nodes.new("ShaderNodeSeparateColor"); comb = nt.nodes.new("ShaderNodeCombineColor")   # the game's green is down
        inv = nt.nodes.new("ShaderNodeMath"); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
        nt.links.new(tn.outputs["Color"], sep.inputs[0]); nt.links.new(sep.outputs[1], inv.inputs[1])
        nt.links.new(sep.outputs[0], comb.inputs[0]); nt.links.new(inv.outputs[0], comb.inputs[1]); nt.links.new(sep.outputs[2], comb.inputs[2])
        nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = 0.8
        nt.links.new(comb.outputs[0], nm.inputs["Color"]); nt.links.new(nm.outputs[0], b.inputs["Normal"])
    return m

def H(n): return os.path.join(HALLTEX, n)
M = {
    "oak":     mat_tex("oak", H("AGH2Beam.dds"), H("AGH2Beam_n.dds"), 0.7, tint=(0.82, 0.74, 0.66)),
    "board":   mat_tex("board", H("AGH2Boards.dds"), H("AGH2Boards_n.dds"), 0.75, tint=(0.9, 0.82, 0.74)),
    "iron":    mat_tex("iron", H("AGH2XMetal.dds"), H("AGH2XMetal_n.dds"), 0.4, tint=(0.8, 0.78, 0.75), metal=0.85),
    "plaster": mat_tex("plaster", H("AGH2Plaster.dds"), H("AGH2Plaster_n.dds"), 0.9),
    "panel":   mat_tex("panel", H("AGH2Panel.dds"), H("AGH2Panel_n.dds"), 0.8),
    "stone":   mat_tex("stone", H("AGH2Blocks.dds"), H("AGH2Blocks_n.dds"), 0.85),
    "floor":   mat_tex("floor", H("AGH2Blocks.dds"), H("AGH2Blocks_n.dds"), 0.85, tint=(0.8, 0.78, 0.75)),
    "shingle": mat_tex("shingle", H("AGH2Planks2.dds"), H("AGH2Planks2_n.dds"), 0.8, tint=(0.7, 0.62, 0.55)),
    "emblem":  mat_tex("emblem", os.path.join(AGTEX, "emblem.png"), None, 0.4, alpha=True),
}
for r in "EDCBAS":
    M["rank" + r] = mat_tex("rank" + r, os.path.join(AGTEX, f"rank_{r}.png"), None, 0.4, alpha=True)
PAPERS = ["largenote01", "largenote02", "largenote03", "largenote04", "largetornpage"]
for p in PAPERS:
    M[p] = mat_tex(p, os.path.join(SP, "textures", "clutter", "books", p + ".dds"), None, 0.85)

# ---------------------------------------------------------------- geometry helpers
COLL = bpy.data.collections.new("board"); scene.collection.children.link(COLL)
CTX = bpy.data.collections.new("context"); scene.collection.children.link(CTX)

def obj(name, bm, mat, coll=COLL, bevel=0.0, smooth=False):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    if smooth:
        for p in me.polygons: p.use_smooth = True
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me); coll.objects.link(o)
    if bevel:
        bv = o.modifiers.new("bevel", 'BEVEL'); bv.width = bevel; bv.segments = 2; bv.limit_method = 'ANGLE'
    return o

def box_uv(bm, scale=1 / 128.0, grain="z", off=(0, 0)):
    """planar UVs per face from world position: wood grain runs along `grain` (the texture's v)"""
    uvl = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal; ax = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            c = l.vert.co
            if ax == 0: u, v = c.y, c.z
            elif ax == 1: u, v = c.x, c.z
            else: u, v = c.x, c.y
            if grain == "x": u, v = v, u
            if grain == "z" and ax == 2: u, v = c.x, c.y
            l[uvl].uv = (u * scale + off[0], v * scale + off[1])

def box(name, lo, hi, mat, bevel=0.6, grain="z", coll=COLL, uvoff=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector([lo[i] + (v.co[i] + 0.5) * (hi[i] - lo[i]) for i in range(3)])
    bm.normal_update()
    box_uv(bm, grain=grain, off=uvoff or (random.random(), random.random()))
    return obj(name, bm, mat, coll, bevel)

def prism(name, pts, y0, y1, mat, bevel=0.4, grain="z", coll=COLL):
    """a flat outline (x, z) extruded from y0 to y1 (y1 nearer the viewer: more negative)"""
    bm = bmesh.new()
    back = [bm.verts.new((x, y0, z)) for x, z in pts]
    front = [bm.verts.new((x, y1, z)) for x, z in pts]
    bm.faces.new(front); bm.faces.new(list(reversed(back)))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((back[i], back[j], front[j], front[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    box_uv(bm, grain=grain, off=(random.random(), random.random()))
    return obj(name, bm, mat, coll, bevel)

def disc(name, c, r, y0, y1, mat, n=40, coll=COLL, picture=True):
    """a round plate facing -y, the picture over its face"""
    bm = bmesh.new(); uvl = bm.loops.layers.uv.verify()
    ring_b = [bm.verts.new((c[0] + r * math.cos(2 * math.pi * k / n), y0, c[1] + r * math.sin(2 * math.pi * k / n))) for k in range(n)]
    ring_f = [bm.verts.new((c[0] + r * math.cos(2 * math.pi * k / n), y1, c[1] + r * math.sin(2 * math.pi * k / n))) for k in range(n)]
    f = bm.faces.new(ring_f)
    for k in range(n):
        j = (k + 1) % n; bm.faces.new((ring_b[k], ring_b[j], ring_f[j], ring_f[k]))
    bm.faces.new(list(reversed(ring_b)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for fc in bm.faces:
        for l in fc.loops:
            l[uvl].uv = ((l.vert.co.x - c[0]) / (2 * r) + 0.5, (l.vert.co.z - c[1]) / (2 * r) + 0.5)
    return obj(name, bm, mat, coll, 0.0, smooth=False)

# ---------------------------------------------------------------- the board
def frame():
    for s in (-1, 1):
        x0, x1 = sorted((s * (W / 2 - SW), s * W / 2))
        box(f"stile{s}", (x0, -SD, 0), (x1, 0, FH), M["oak"], 0.8, "z")
    box("rail_bottom", (FX0, -SD + 0.5, RB0), (FX1, 0, RB1), M["oak"], 0.8, "x")
    box("rail_top", (FX0, -SD, RT0), (FX1, 0, FH), M["oak"], 0.8, "x")
    for k in (1, 2):                                                    # mullions between the sections
        x0 = SECTIONS[k][0] - MW
        box(f"mullion{k}", (x0, -PD - 2.0, RB1), (x0 + MW, -PD + 0.2, RT0), M["oak"], 0.5, "z")
    # the field: vertical boards, each a little different
    n = int(round((FX1 - FX0) / 19)); fw = (FX1 - FX0) / n
    for i in range(n):
        x0 = FX0 + i * fw + 0.25; x1 = x0 + fw - 0.5
        d = PD + random.uniform(-0.25, 0.25)
        box(f"fieldboard{i}", (x0, -d, RB1 - 1), (x1, 0, RT0 + 1), M["board"], 0.3, "z")
    # iron corner plates (L) with rivets, on the frame's face
    L, T = 15.0, 4.0
    for sx in (-1, 1):
        for sz, zc in ((-1, 0.0), (1, FH)):
            xo = sx * W / 2; zo = zc                      # the frame's corner; the arms run inward from it
            pts = [(xo - sx * px, zo - sz * pz) for px, pz in ((0, 0), (L, 0), (L, T), (T, T), (T, L), (0, L))]
            prism(f"corner{sx}{sz}", pts, -SD + 0.01, -SD - 0.7, M["iron"], 0.2)
            for px, pz in ((L - 2.2, T / 2), (T / 2, L - 2.2), (T / 2, T / 2)):
                disc(f"rivet{sx}{sz}{px}", (xo - sx * px, zo - sz * pz), 0.8, -SD - 0.7, -SD - 1.3, M["iron"], 10)

def badges():
    """each section's two ranks on the top rail over it: the lower left, the higher right"""
    zc = (RT0 + FH) / 2
    for x0, x1, lo, hi in SECTIONS:
        for xc, r in ((x0 + (x1 - x0) * 0.3, lo), (x0 + (x1 - x0) * 0.7, hi)):
            disc(f"badge{r}_bezel", (xc, zc), BADGE_R + 0.7, -SD + 0.1, -SD - 0.5, M["iron"], 32)
            disc(f"badge{r}", (xc, zc), BADGE_R, -SD - 0.5, -SD - 1.1, M["rank" + r], 40)

def dragon_head(name, base, ang, facing, scale, y0, y1, mat):
    """a carved Nordic dragon head in profile (blockout): its neck at `base`, its snout along `ang`; facing +1/-1 mirrors it"""
    h = [(0, 0), (6, 1.2), (11, 0.2), (15, 0.6), (17.5, 1.8), (13.5, 3.0), (18.5, 4.2), (17.5, 5.8), (14, 6.6), (10.5, 7.4),
         (8.5, 9.8), (5, 12.5), (2.2, 12.8), (3.8, 10.6), (2.2, 8.4), (0, 6.5)]
    R = Matrix.Rotation(ang, 2)
    pts = [base + R @ Vector((hx * scale * facing, hz * scale)) for hx, hz in h]
    return prism(name, [(q.x, q.y) for q in pts], y0, y1, mat, 0.5, "x")

HW = float(OPT.get("hw", 62))          # the sign board's half width

def header():
    """a carved sign board on the top rail, its ends rolled into dragon heads looking outward, the crest rising in the middle"""
    z0, z1 = FH - 2, FH + 13
    pts = [(-HW, z0), (HW, z0), (HW, z0 + 4), (HW - 4, z1 - 2), (18, z1), (-18, z1), (-HW + 4, z1 - 2), (-HW, z0 + 4)]
    prism("signboard", pts, 0, -SD - 1.0, M["oak"], 0.6, "x")
    box("sign_moulding", (-HW + 2, -SD - 2.2, z0 + 1.5), (HW - 2, -SD - 0.8, z0 + 3.5), M["oak"], 0.4, "x")
    for s in (-1, 1):
        dragon_head(f"head{s}", Vector((s * (HW - 4), z0 + 5)), 0.0, s, 0.85, -0.6, -SD - 0.6, M["oak"])
    cz = FH + 19
    disc("crest_back", (0, cz), 23.0, -0.5, -SD - 2.0, M["oak"], 64)
    disc("crest_ring", (0, cz), 21.0, -SD - 2.0, -SD - 2.8, M["iron"], 64)
    disc("crest", (0, cz), 20.2, -SD - 2.8, -SD - 3.6, M["emblem"], 64)

def notice(name, cx, ztop, w, h, mat, rot=0.0, curl=1.5, torn=False):
    """a sheet nailed at its top middle, hanging, its lower corners curling off the board"""
    bm = bmesh.new(); uvl = bm.loops.layers.uv.verify()
    nx, nz = 8, 10
    vs = {}
    for i in range(nx + 1):
        for j in range(nz + 1):
            u, v = i / nx, j / nz
            x = (u - 0.5) * w; z = -(1 - v) * h
            lift = curl * ((abs(u - 0.5) * 2) ** 2) * ((1 - v) ** 2) + 0.25 * math.sin(math.pi * u) * (1 - v)
            vs[i, j] = bm.verts.new((x, -lift, z))
    for i in range(nx):
        for j in range(nz):
            f = bm.faces.new((vs[i, j], vs[i + 1, j], vs[i + 1, j + 1], vs[i, j + 1]))
            for l, (a, b) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                l[uvl].uv = (a / nx, b / nz)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        if f.normal.y > 0: f.normal_flip()
    o = obj(name, bm, mat, COLL, 0.0, smooth=True)
    o.location = (cx, -PD - 0.15, ztop); o.rotation_euler = (0, math.radians(rot), 0)
    disc(name + "_nail", (cx, ztop - 1.5), 0.8, -PD - 0.2, -PD - 1.1, M["iron"], 10)
    return o

def notices():
    """crowded low ranks, sparse high ones: (section, x across it 0..1, top, w, h, paper, rotation)"""
    plan = [
        (0, 0.20, 108, 22, 29, "largenote01", -3), (0, 0.55, 105, 20, 26, "largetornpage", 2.5), (0, 0.85, 108.5, 17, 22, "largenote04", 5),
        (0, 0.16, 75, 20, 27, "largenote02", 2.5), (0, 0.47, 78, 23, 30, "largenote01", -2), (0, 0.80, 71, 19, 15, "largenote01", 1),
        (0, 0.84, 52, 18, 24, "largetornpage", -4), (0, 0.24, 41, 21, 27, "largenote04", -1.5), (0, 0.55, 44, 16, 12, "largenote02", 3),
        (1, 0.28, 107, 24, 32, "largenote02", 2), (1, 0.74, 106, 21, 28, "largenote01", -1.5),
        (1, 0.30, 66, 20, 26, "largenote04", 3), (1, 0.72, 68, 22, 29, "largenote01", -2.5),
        (2, 0.30, 106, 24, 32, "largenote03", -1), (2, 0.74, 99, 21, 28, "largenote02", 1.5),
    ]
    for k, (si, u, top, w, h, p, rot) in enumerate(plan):
        x0, x1 = SECTIONS[si][:2]
        notice(f"notice{k:02d}", x0 + (x1 - x0) * u, top, w, h, M[p], rot)

def standoff():
    """the board body hangs YB off the wall: two oak cleats on the wall behind it, their ends showing past its sides, notched
    round the stone stub (which runs up behind the board in the gap); iron straps over the top rail into the wall"""
    nx0, nx1 = SURR[0] - 0.5, STUB[1] + 0.5
    for z0, z1 in ((14.0, 24.0), (RT0 - 14.0, RT0 - 4.0)):
        for x0, x1 in ((-W / 2 - 4, nx0), (nx1, W / 2 + 4)):
            box(f"cleat{z0:.0f}_{x0:.0f}", (x0, YB, z0), (x1, 0, z1), M["oak"], 0.6, "x")
    for sx in (-1, 1):
        x = sx * (W / 2 - 26)
        for (lo, hi) in (((x - 2.2, YB - SD - 0.8, FH), (x + 2.2, 0, FH + 0.9)),            # over the top rail, wall to front
                         ((x - 2.2, YB - SD - 0.8, FH - 11), (x + 2.2, YB - SD, FH + 0.9))):   # down its face
            box(f"strap{sx}_{lo[2]:.0f}", lo, hi, M["iron"], 0.2, "x")
        disc(f"strapnail{sx}", (x, FH - 7), 0.9, YB - SD - 0.8, YB - SD - 1.5, M["iron"], 10)

frame(); badges(); header(); notices()
for o in COLL.objects:                      # the body off the wall
    o.location.y += YB
standoff()
COLL_ROOT = bpy.data.objects.new("BoardRoot", None); scene.collection.objects.link(COLL_ROOT)
for o in COLL.objects:
    if o.parent is None: o.parent = COLL_ROOT
COLL_ROOT.location = (0, 0, Z0)

# ---------------------------------------------------------------- the wall around it (hall frame, shifted: board centre at x 0)
WX0, WX1 = -142.5, 157.5                # hall x 216 (the outside corner) .. 516 (the services door's frame)
box("base", (WX0, -0.2, 0), (WX1, 0.0, 44), M["panel"], 0, "x", CTX)
box("plaster", (WX0, 0, 44), (WX1, 4, 372), M["plaster"], 0, "z", CTX)
box("course", (WX0 - 8, -8, 372), (STUB[0], 4, 399), M["stone"], 0.5, "x", CTX)
box("plaster_up", (WX0, 0, 399), (WX1, 4, 460), M["plaster"], 0, "z", CTX)
box("foot_side", (WX0 - 4, 0, 0), (WX0, 300, 460), M["plaster"], 0, "z", CTX)        # the outside corner turns back
box("stub", (STUB[0], -STUB[2], 0), (STUB[1], 0, 275), M["stone"], 0.4, "z", CTX)    # the arcade's last respond
box("surround", (SURR[0], -STUB[2], 0), (SURR[1], 0, 275), M["stone"], 0.2, "z", CTX)   # 1.5 proud in x, along the stub's corner (not out of the wall)
for k in range(10):                                                                   # the last arch, springing at 275
    t0, t1 = k / 10 * math.pi / 2, (k + 1) / 10 * math.pi / 2; R = 120.0
    box(f"arch{k}", (STUB[0], -STUB[2] - R * math.sin(t1), 275 + R * (1 - math.cos(t0))), (STUB[1], -STUB[2] - R * math.sin(t0) + 0.01, 400), M["stone"], 0, "z", CTX)
box("doorframe", (WX1, -6, 0), (WX1 + 10, 0, 240), M["oak"], 0.5, "z", CTX)
box("floor", (-600, -800, -2), (600, 400, 0), M["floor"], 0, "x", CTX)

# ---------------------------------------------------------------- light and cameras
ids = {i.identifier for i in scene.render.bl_rna.properties['engine'].enum_items}
scene.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in ids else 'BLENDER_EEVEE'
scene.view_settings.view_transform = 'AgX' if 'AgX' in [i.identifier for i in scene.view_settings.bl_rna.properties['view_transform'].enum_items] else 'Filmic'
try: scene.eevee.use_shadows = True
except Exception: pass
w = bpy.data.worlds.new("hall"); scene.world = w; w.use_nodes = True
bg = w.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.32, 0.26, 0.2, 1); bg.inputs[1].default_value = 0.35
def light(name, kind, loc, energy, color, size=50, rot=None):
    ld = bpy.data.lights.new(name, kind); ld.energy = energy; ld.color = color
    if kind == 'AREA': ld.size = size
    if kind == 'POINT': ld.shadow_soft_size = size
    o = bpy.data.objects.new(name, ld); scene.collection.objects.link(o); o.location = loc
    if rot: o.rotation_euler = rot
    return o
k = light("key", 'AREA', (-260, -420, 420), 2.4e6, (1.0, 0.86, 0.68), 160)          # the great hearth, front left, high
k.rotation_euler = (Vector((0, 0, 200)) - k.location).to_track_quat('-Z', 'Y').to_euler()
f = light("fill", 'AREA', (300, -500, 260), 7e5, (0.85, 0.9, 1.0), 220)              # the windows' daylight, front right
f.rotation_euler = (Vector((0, 0, 160)) - f.location).to_track_quat('-Z', 'Y').to_euler()
light("candle", 'POINT', (-90, -150, 230), 1.2e5, (1.0, 0.7, 0.4), 6)

cd = bpy.data.cameras.new("cam"); cd.lens = 35; cd.clip_start = 2; cd.clip_end = 5000
cam = bpy.data.objects.new("cam", cd); scene.collection.objects.link(cam); scene.camera = cam
MID = Z0 + (RB1 + RT0) / 2
VIEW = {   # name: (camera location, look-at, lens, resolution)
    "front": ((0, -330, 125), (0, 0, 150), 32, (1600, 1200)),
    "34":    ((-230, -250, 125), (0, 0, 145), 30, (1600, 1200)),
    "below": ((-60, -110, 60), (0, -6, Z0 + 10), 32, (1600, 1200)),
    "close": ((-60, -70, 118), (-70, 0, 112), 40, (1600, 1200)),
    "hall":  ((-60, -700, 120), (0, 0, 190), 28, (1600, 1200)),
    "side":  ((-300, -30, 140), (0, -5, Z0 + 100), 50, (1200, 1600)),
}
for v in VIEWS:
    loc, at, lens, res = VIEW[v]
    cam.location = loc; cd.lens = lens
    cam.rotation_euler = (Vector(at) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.filepath = os.path.join(OUT, f"{TAG}_{v}.png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", scene.render.filepath)
if OPT.get("blend") == "1":
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, f"{TAG}.blend"))
