"""Headless Blender: the party leader board as a Skyrim SE NIF. A small pinned board in the Guild Board's own wood (its
organic timber, pegs, planks and iron, from board/board_build.py's definitions, and its texture sets): an oak frame round
a field of planks, the standings sheet pinned in the middle, two scraps pinned over the sheet's left edge (the
sheet is the focus; 128 x 120; the scraps may overlap; the top scrap small), and a box for collision.
Paper in its own alpha-tested set (make_lb_textures.py). Shader settings, root and collision from the same vanilla
templates the Guild Board uses.
    blender -b --factory-startup -P lb_build.py -- <out nif> <template dir: holds meshes/...>
The worked board: the Guild Board's wear on the planks, two older sheets under the
current one, the sheet's bottom-right corner curled off its lost tack. LB_PART=slip or strike builds a story piece
instead (AGLeaderSlip.nif, AGLeaderStrike.nif): its own NIF on the board's origin, placed on the board's spot, which
the DLL enables when the story calls for it (LeaderBoard.cpp).
Frame: x right, the wall at y 0, front toward -y, z up from the board's bottom (the NIF's origin: on the wall plane at
the board's bottom middle), as the Guild Board's."""
import sys, os, math, random, json, bpy, bmesh
from mathutils import Vector, Matrix
HERE = os.path.dirname(os.path.abspath(__file__))
PRIV = os.path.join(HERE, "..", "..", "hall-private", "leaderboard")   # (its inputs made from the game's files or not ours to publish: tools/hall-private)
BOARD = os.path.join(HERE, "..", "board", "board_build.py")
src = open(BOARD, encoding="utf-8").read()
g = {"__file__": BOARD, "__name__": "board_build_defs"}
# the Guild Board's script up to its own board (its args, helpers, timber and pegs), then its templates and materials
exec(src[:src.index("def body():")], g)
exec(src[src.index("# ---------------------------------------------------------------- the templates"):src.index("made = []")], g)
exec(src[src.index("def alpha_test(stem):"):src.index("nmat = alpha_test(")], g)      # defined after its own shapes
DST = g["DST"]; Shape, timber, peg, add_disc, BL = g["Shape"], g["timber"], g["peg"], g["add_disc"], g["BL"]
SH = g["SH"]; material, make_obj, alpha_test, coll, root, proto = g["material"], g["make_obj"], g["alpha_test"], g["coll"], g["root"], g["proto"]
random.seed(23)

# ---------------------------------------------------------------- the design (mock-up G7)
W, H = 128.0, 120.0                     # the board
SW, SD = 7.0, 4.0                       # the frame's stiles and rails: width, depth
RB1, RT0 = 7.0, H - 7.0                 # the bottom rail's top, the top rail's bottom
PD = 2.2                                # the planks' depth (their front stands back from the frame's)
YB = -0.6                               # the board's back, a hair off the wall
SHEET_W, SHEET_H, SHEET_Z = 96.7, 79.2, H / 2
SCRAPS = [(-43.0, SHEET_Z + 12.0, 19.0, 20.0, -5.0), (-43.0, SHEET_Z - 24.0, 26.0, 22.0, 3.0)]   # x, z, w, h, tilt
TEXL = "textures" + chr(92) + "AdventurersGuild" + chr(92) + "LeaderBoard" + chr(92)
ATL = 2048.0
SHEET_R = (0, 0, 2048, 1677); SCRAP_R = [(0, 1690, 300, 2006), (330, 1690, 750, 2045)]   # make_lb_textures.py

def body():
    """the frame: stiles full height, the rails between them, pegged at the joints; the field's planks, each its own board"""
    yc, yf = YB - SD / 2, YB - SD
    for s in (-1, 1):
        timber(SH["Oak"], "z", 0.0, H, s * (W / 2 - SW / 2), yc, SW, SD, 100 + s, r=(0.45, 1.0), tilt=(0.04 * s, -0.03 * s))
    for (z0, z1), sd in (((0.0, RB1), 7), ((RT0, H), 9)):
        h = z1 - z0; zc = (z0 + z1) / 2
        timber(SH["Oak"], "x", -W / 2 + SW - 0.2, W / 2 - SW + 0.2, zc, yc + 0.25, h, SD - 0.5, 200 + sd, r=(0.4, 1.0), caps=(False, False))
        for s in (-1, 1):
            for dz in (-h * 0.2, h * 0.2):
                peg(SH["Oak"], s * (W / 2 - SW / 2), zc + dz, yf - 0.02, 400 + sd * 10 + s + int(dz))
    rnd = random.Random(31); widths = []; fx0, fx1 = -W / 2 + SW, W / 2 - SW; left = fx1 - fx0
    while left > 0.1:
        wv = rnd.uniform(17.0, 22.0); wv = left if left - wv < 11 else wv; widths.append(wv); left -= wv
    # a backing board behind the planks, so their gaps show wood, not the wall (the first render showed plaster)
    timber(SH["Oak"], "x", fx0 - 0.5, fx1 + 0.5, (RB1 + RT0) / 2, YB - 0.25, RT0 - RB1 + 2.0, 0.5, 690, r=(0.05, 0.1), seg=1,
           step=40, bow=0.0, wander=0.0, edge=0.0, dings=0, caps=(False, False))
    x = fx0
    for i, wv in enumerate(widths):
        gap = rnd.uniform(0.25, 0.5); x0, x1 = x + gap / 2, x + wv - gap / 2; x += wv
        d = PD + rnd.uniform(-0.2, 0.2)
        timber(SH["Planks"], "z", RB1 - 1.0, RT0 + 1.0, (x0 + x1) / 2, YB - d / 2, x1 - x0, d, 700 + i, r=(0.2, 0.5), seg=2,
               step=12, bow=0.12, wander=0.2, edge=0.08, dings=1, caps=(False, False), uv="plank", board=rnd.randrange(8),
               split_front=2, cup=0.15)

PAPER = Shape("Paper")
CURL = 4.0                              # the sheet's bottom-right corner, its tack gone, curled off the board (the worked sheet)
def lift_at(fu, fv, bulge, curl=0.0):
    """how far a sheet stands off its plane at (fu, fv): bowed out in the middle, and the curled corner"""
    c = max(0.0, (fu - 0.72) / 0.28) * max(0.0, (0.28 - fv) / 0.28)
    return bulge * math.sin(math.pi * fu) * math.sin(math.pi * fv) + curl * c * c
def sheet_quad(cx, cz, w, h, y, rect, tilt=0.0, bulge=0.3, nu=8, nv=6, seed=0, curl=0.0):
    """a sheet of paper on the board: a grid lying a hair off the wood, bowed out a little in the middle (pinned at its
    corners), turned by tilt degrees in the board's plane; its UVs into the paper atlas' rect"""
    rnd = random.Random(seed); a = math.radians(tilt); ca, sa = math.cos(a), math.sin(a)
    u0, v0, u1, v1 = rect[0] / ATL, 1 - rect[3] / ATL, rect[2] / ATL, 1 - rect[1] / ATL
    vs = {}
    for i in range(nu + 1):
        for j in range(nv + 1):
            fu, fv = i / nu, j / nv
            px, pz = (fu - 0.5) * w, (fv - 0.5) * h
            lift = lift_at(fu, fv, bulge, curl) + rnd.uniform(0, 0.04)
            vs[i, j] = PAPER.bm.verts.new((cx + px * ca - pz * sa, y - lift, cz + px * sa + pz * ca))
    for i in range(nu):
        for j in range(nv):
            f = PAPER.bm.faces.new((vs[i, j], vs[i + 1, j], vs[i + 1, j + 1], vs[i, j + 1]))   # right then up: facing -y, the front
            for l, (ii, jj) in zip(f.loops, ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))):
                l[PAPER.uv].uv = (u0 + (u1 - u0) * ii / nu, v0 + (v1 - v0) * jj / nv)

LAYOUT = json.load(open(os.path.join(PRIV, "maps", "lb_layout.json")))    # make_lb_textures.py: the atlas' cells, the rows
OLD_R = [tuple(r) for r in LAYOUT["OLDS"]]; SLIP_R = tuple(LAYOUT["SLIP"]); STROKE_R = [tuple(r) for r in LAYOUT["STROKES"]]
PART = os.environ.get("LB_PART", "board")   # board, or a story piece: slip (the player has a party), strike (the Golden Hand struck out)
y_sheet = YB - PD - 0.7                  # (0.4 forward of the first build: the two older sheets lie between it and the planks)
SHEET_TILT, SHEET_BULGE = -0.4, 0.35
def on_sheet(px, py, ahead):
    """a point of the standings sheet's texture (px, py: its pixels) on the sheet as built, a little ahead of it"""
    fu, fv = px / LAYOUT["sheet"]["w"], 1 - py / LAYOUT["sheet"]["h"]
    a = math.radians(SHEET_TILT); ca, sa = math.cos(a), math.sin(a)
    x_, z_ = (fu - 0.5) * SHEET_W, (fv - 0.5) * SHEET_H
    return Vector((x_ * ca - z_ * sa, y_sheet - lift_at(fu, fv, SHEET_BULGE, CURL) - 0.04 - ahead, SHEET_Z + x_ * sa + z_ * ca))
ir = BL.DETAIL["iron"]

WEAR = Shape("Wear")
def wear():
    """what earlier sheets left on the planks round the standings (the Guild Board's own
    wear, its decals and counts scaled to this board's field): nail holes, pin pricks, rust run down from old nails,
    torn scraps still under theirs. Only where it shows: outside the sheets"""
    rnd = random.Random(29); cells = BL.wear_cells(); old_nails = []
    fx0, fx1, y = -W / 2 + SW + 1.5, W / 2 - SW - 1.5, YB - PD - 0.3
    def quad(kind, i, x, z, w, h, rot=0.0):
        u0, v0, u1, v1 = BL.uv(cells[kind][i % len(cells[kind])], 1)
        R = Matrix.Rotation(math.radians(rot), 2)
        cs = [(-w / 2, -h), (w / 2, -h), (w / 2, 0), (-w / 2, 0)] if kind == "rust" else [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
        vs = [WEAR.bm.verts.new((x + (R @ Vector(c)).x, y, z + (R @ Vector(c)).y)) for c in cs]
        f = WEAR.bm.faces.new(vs)
        for l, (a, b) in zip(f.loops, ((u0, v0), (u1, v0), (u1, v1), (u0, v1))): l[WEAR.uv].uv = (a, b)
    def spot():
        while True:
            x = rnd.uniform(fx0, fx1); z = rnd.uniform(RB1 + 2.5, RT0 - 2.5)
            if abs(x) > SHEET_W / 2 + 5.5 or abs(z - SHEET_Z) > SHEET_H / 2 + 5.5: return x, z
    for i in range(22): x, z = spot(); quad("hole", i, x, z, 1.3, 1.3, rnd.uniform(0, 360))
    for i in range(5): x, z = spot(); quad("pins", i, x, z, 2.2, 2.2, rnd.uniform(0, 360))
    for i in range(4):
        x, z = spot(); quad("rust", i, x, z - 0.3, 1.4, 4.2); old_nails.append((x, z))
    for i in range(3):
        x, z = spot(); quad("scrap", i, x, z - 1.2, 4.2, 4.2, rnd.uniform(-25, 25)); old_nails.append((x, z))
    for (x, z) in old_nails: add_disc(SH["Detail"], (x, z), 0.65, y - 0.05, y - 0.9, ir, n=8)

if PART == "board":
    body()
    wear()
    # two older sheets under the current one, browned, their edges showing past it: the top right of one, the bottom
    # left of the other (years of standings pinned over each other)
    sheet_quad(4.0, SHEET_Z + 5.0, 96.0, 80.0, YB - PD - 0.5, OLD_R[0], tilt=1.8, bulge=0.1, nu=4, nv=4, seed=11)
    sheet_quad(-3.0, SHEET_Z - 4.5, 94.0, 78.0, YB - PD - 0.35, OLD_R[1], tilt=-1.2, bulge=0.08, nu=4, nv=4, seed=13)
    sheet_quad(0.0, SHEET_Z, SHEET_W, SHEET_H, y_sheet, SHEET_R, tilt=SHEET_TILT, bulge=SHEET_BULGE, nu=18, nv=14, seed=1, curl=CURL)
    for k, (x, z, w, h, t) in enumerate(SCRAPS):
        sheet_quad(x, z, w, h, y_sheet - 0.35 - 0.1 * k, SCRAP_R[k], tilt=t, bulge=0.15, nu=3, nv=3, seed=5 + k)
    # the tacks: three of the sheet's corners (the bottom right's has gone: that corner curls), each scrap's top
    nails = [(sx * (SHEET_W / 2 - 3.5), SHEET_Z + sz * (SHEET_H / 2 - 3.5)) for sx in (-1, 1) for sz in (-1, 1)]
    nails = [n for n in nails if not (n[0] < 0 and n[1] > SHEET_Z) and not (n[0] > 0 and n[1] < SHEET_Z)]   # (top left: under the scrap's)
    nails += [(x - math.sin(math.radians(t)) * (h / 2 - 3), z + h / 2 - 3) for x, z, w, h, t in SCRAPS]
    for (x, z) in nails:
        add_disc(SH["Detail"], (x, z), 0.75, y_sheet - 0.5, y_sheet - 1.6, ir, n=8)
elif PART == "slip":
    # pinned up once the player has a party (the DLL enables it): a fresh slip over the sheet's right edge, below its
    # middle, as a clerk pins up a new entry before the next fair copy. On the board's own origin and spot
    # seen in game: the sheet's curled corner showed through the slip's lower left (the first build was flat, 34
    # high). A bit of both: 3 higher, and the slip rides over what is left of the curl under it
    sx, sz, sw, sh = 49.5, 37.0, 14.0, 12.0       # (clear of the renown column, which ends at x 39.8)
    n0 = len(PAPER.bm.verts)
    sheet_quad(sx, sz, sw, sh, y_sheet - 0.9, SLIP_R, tilt=3.5, bulge=0.12, nu=6, nv=6, seed=21)
    a = math.radians(-SHEET_TILT); ca, sa = math.cos(a), math.sin(a)
    PAPER.bm.verts.ensure_lookup_table()
    for v in PAPER.bm.verts[n0:]:
        x_, z_ = v.co.x * ca - (v.co.z - SHEET_Z) * sa, v.co.x * sa + (v.co.z - SHEET_Z) * ca   # into the sheet's own frame
        fu = min(1.0, max(0.0, x_ / SHEET_W + 0.5)); fv = min(1.0, max(0.0, z_ / SHEET_H + 0.5))   # (past its edge: the edge's)
        front = y_sheet - lift_at(fu, fv, SHEET_BULGE, CURL) - 0.04      # the sheet's front there, its noise included
        v.co.y = min(v.co.y, front - 0.3)                                # the slip stays 0.3 in front of it
    add_disc(SH["Detail"], (sx - math.sin(math.radians(3.5)) * (sh / 2 - 2.5), sz + sh / 2 - 2.5), 0.75, y_sheet - 1.1, y_sheet - 2.2, ir, n=8)
elif PART == "strike":
    # the Guild strikes the Golden Hand out once Caralion is dishonored (the DLL enables it): a line of the keeper's ink
    # through his party's name and its Renown, on the sheet's last row, where the sheet as drawn has it
    gl = LAYOUT["golden"]
    for (x0, x1), cell in ((gl["name"], STROKE_R[0]), (gl["renown"], STROKE_R[1])):
        u0, v0, u1, v1 = cell[0] / ATL, 1 - cell[3] / ATL, cell[2] / ATL, 1 - cell[1] / ATL
        hh = (cell[3] - cell[1]) / 2; n = 6; row = []
        for k in range(n + 1):
            px = x0 + (x1 - x0) * k / n
            row.append([PAPER.bm.verts.new(on_sheet(px, gl["y"] + dy, 0.06)) for dy in (hh, -hh)])   # (its bottom, its top)
        for k in range(n):
            f = PAPER.bm.faces.new((row[k][0], row[k + 1][0], row[k + 1][1], row[k][1]))
            for l, (a, b) in zip(f.loops, ((u0 + (u1 - u0) * k / n, v0), (u0 + (u1 - u0) * (k + 1) / n, v0),
                                           (u0 + (u1 - u0) * (k + 1) / n, v1), (u0 + (u1 - u0) * k / n, v1))):
                l[PAPER.uv].uv = (a, b)
else:
    sys.exit("LB_PART: board, slip or strike")

# ---------------------------------------------------------------- the shapes
made = []
for key, stem in (("Oak", "AGBoardOak"), ("Planks", "AGBoardPlanks"), ("Detail", "AGBoardDetail")):
    sh = SH[key]
    if not sh.bm.faces: continue
    bmesh.ops.remove_doubles(sh.bm, verts=sh.bm.verts[:], dist=0.0001)
    bmesh.ops.triangulate(sh.bm, faces=sh.bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    me = bpy.data.meshes.new("AGLeader" + key); sh.bm.to_mesh(me); sh.bm.free()
    made.append(make_obj("AGLeader" + key, me, material(g["opaque"], stem)))       # the Guild Board's own texture sets
pm = alpha_test("AGBoardNotices")
pm.name = "AGLeaderPaper"; pm["BSShaderTextureSet_Diffuse"] = TEXL + "AGLeaderPaper.dds"; pm["BSShaderTextureSet_Normal"] = TEXL + "AGLeaderPaper_n.dds"
for n in pm.node_tree.nodes:                        # the preview images, for Blender's own renders
    if n.type == 'TEX_IMAGE' and n.image:
        nm = n.image.filepath.lower(); p = os.path.join(PRIV, "maps", "AGLeaderPaper" + ("_n.png" if "_n." in nm else ".png"))
        if os.path.exists(p): n.image = bpy.data.images.load(p, check_existing=True)
bmesh.ops.triangulate(PAPER.bm, faces=PAPER.bm.faces[:])
me = bpy.data.meshes.new("AGLeaderPaper"); PAPER.bm.to_mesh(me); PAPER.bm.free()
for p in me.polygons: p.use_smooth = True
made.append(make_obj("AGLeaderPaper", me, pm))
if WEAR.bm.faces:                                    # the Guild Board's wear decals, on its detail atlas, alpha-tested as its own
    bmesh.ops.triangulate(WEAR.bm, faces=WEAR.bm.faces[:])
    me = bpy.data.meshes.new("AGLeaderWear"); WEAR.bm.to_mesh(me); WEAR.bm.free()
    made.append(make_obj("AGLeaderWear", me, alpha_test("AGBoardDetail")))

# every image node onto its DDS under an assets textures tree: PyNifly writes the path from the image when it lies under a
# 'textures' folder (as textures\...), and the absolute path of a preview PNG otherwise (the first build did)
TREES = {"AGBoard": os.path.join(HERE, "..", "..", "hall-private", "board", "assets"), "AGLeader": os.path.join(PRIV, "assets")}
for o in made:
    for n in o.active_material.node_tree.nodes:
        if n.type != 'TEX_IMAGE' or not n.image: continue
        normal = "_n." in n.image.filepath.lower() or n.image.filepath.lower().endswith("_n.png")
        key = o.active_material.get("BSShaderTextureSet_Normal" if normal else "BSShaderTextureSet_Diffuse", "")
        stem = os.path.basename(key.replace(chr(92), "/"))
        tree = TREES["AGLeader" if stem.startswith("AGLeader") else "AGBoard"]
        p = os.path.normpath(os.path.join(tree, *key.split(chr(92))))
        if not os.path.exists(p): sys.exit("no texture at " + p)
        n.image = bpy.data.images.load(p, check_existing=True)

# the collision: one box round the board; a story piece keeps the template's collision as a thin box round itself
# (the template's whole collision chain stays as it is: only the box's size changes)
if PART == "board":
    lo = Vector((-W / 2, YB - SD, 0)); hi = Vector((W / 2, 0, H))
else:
    pts = [v.co for o in made for v in o.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts) + 0.2, max(p.z for p in pts)))
ctr = (lo + hi) / 2; half = (hi - lo) / 2
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=2.0)
for v in bm.verts: v.co = ctr + Vector((v.co.x * half.x, v.co.y * half.y, v.co.z * half.z))
bm.to_mesh(coll.data); bm.free(); coll.location = (0, 0, 0)

bpy.data.objects.remove(proto, do_unlink=True)
NAME = {"board": "AGLeaderBoard", "slip": "AGLeaderSlip", "strike": "AGLeaderStrike"}[PART]
root["pynNodeName"] = NAME; root.name = NAME
os.makedirs(os.path.dirname(DST), exist_ok=True)
bpy.ops.object.select_all(action='SELECT'); bpy.context.view_layer.objects.active = root
bpy.ops.export_scene.pynifly(filepath=DST)
tri = {o.name: len(o.data.polygons) for o in made}
print("EXPORTED", DST); print("SHAPES", tri); print("TOTAL TRIANGLES", sum(tri.values()))
