"""Headless Blender: the whole basement as a textured mock-up for review before it is built into the generator
(every room in place, the ceilings chosen by room, the doorways, the tower door and the
kitchen ladder, rendered from a few spots in each room). Hall frame (x right, y back), z up. From plans/BASEMENT.md:
the overlay's rooms (basement_overlay.py), the training room as decided (one floor at -304, timber over the main area,
the range's plain vault, the entrance's pillars and rib across), ceilings mixed by room (timber in the training room's
main area and the hallway; stone vaults in the cellar, the bath and the secret room), the bath's pool with real water,
the secret room's door big, obvious and locked, the kitchen hatch at the barrel's spot (-1372, 391).
Where the overlay's rooms meet with walls under 32 (the VR rule), the mock-up moves the overlay's own derived lines, never
the plan's drawn ones: the hallway's south side 780 -> 791 (the main area's back wall 759..791), the bath's east side
-420 -> -444 (the steps' strip's west wall -444..-412). A cell has one water height, under every floor but the pool's:
the training room is at -304, so the pool's water is at -316 and the bath goes down the same three steps (shown).
Not the build: boxes in the hall's textures, vanilla fittings, 128-tall figures, flat light.
    blender -b -P basement_mock.py -- <data root (meshes/, textures/)> <out dir>"""
import sys, os, math, bpy, bmesh, addon_utils, mathutils
addon_utils.enable("io_scene_nifly", default_set=True, persistent=True)
args = sys.argv[sys.argv.index("--") + 1:]
root, out = args[0], args[1]
os.makedirs(out, exist_ok=True)
F0, F1, CEIL, WATER = -256.0, -304.0, -12.0, -316.0
RISE, TREAD, T = 16.0, 32.0, 32.0
TEX = os.path.join(root, "textures", "adventurersguild", "hall2")
scene = bpy.context.scene
ids = {i.identifier for i in scene.render.bl_rna.properties['engine'].enum_items}
scene.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in ids else 'BLENDER_EEVEE'
scene.view_settings.view_transform = 'Standard'
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
MATS = {}
CEILINGS = []          # (hidden for the plan from above)


def mat(name, tex, scale=256.0, rgba=None):
    if name in MATS: return MATS[name]
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bsdf = nt.nodes["Principled BSDF"]
    if tex:
        img = nt.nodes.new("ShaderNodeTexImage"); img.image = bpy.data.images.load(os.path.join(TEX, tex))
        nt.links.new(img.outputs[0], bsdf.inputs[0])
    if rgba:
        bsdf.inputs[0].default_value = rgba; m.diffuse_color = rgba
        if rgba[3] < 1: bsdf.inputs["Alpha"].default_value = rgba[3]; m.blend_method = 'BLEND' if hasattr(m, "blend_method") else None
    bsdf.inputs["Roughness"].default_value = 0.9 if not rgba else 0.1
    MATS[name] = (m, scale); return MATS[name]


def box(lo, hi, m, name="b", ceiling=False):
    if any(hi[k] - lo[k] <= 0.01 for k in range(3)): return None
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = mathutils.Vector([lo[k] + (v.co[k] + 0.5) * (hi[k] - lo[k]) for k in range(3)])
    uv = bm.loops.layers.uv.new(); mt, sc = m
    for f in bm.faces:
        n = f.normal; ax = max(range(3), key=lambda k: abs(n[k])); a, b = [k for k in range(3) if k != ax]
        for l in f.loops: l[uv].uv = (l.vert.co[a] / sc, l.vert.co[b] / sc)
    bm.to_mesh(me); bm.free(); me.materials.append(mt)
    o = bpy.data.objects.new(name, me); scene.collection.objects.link(o)
    if ceiling: CEILINGS.append(o)
    return o


CACHE = {}
def piece(rel, x, y, z, yaw, s=1.0):
    if rel not in CACHE:
        before = set(bpy.data.objects)
        try: bpy.ops.import_scene.pynifly(filepath=os.path.join(root, "meshes", *rel.split("/")))
        except Exception as e: print("IMPORT FAILED", rel, e); CACHE[rel] = []; return
        new = [o for o in bpy.data.objects if o not in before]
        CACHE[rel] = [(o.data, o.matrix_world.copy()) for o in new if o.type == 'MESH' and "bhk" not in o.name]
        for o in new: bpy.data.objects.remove(o, do_unlink=True)
    M = mathutils.Matrix.Translation((x, y, z)) @ mathutils.Matrix.Rotation(math.radians(-yaw), 4, 'Z') @ mathutils.Matrix.Scale(s, 4)
    for me, local in CACHE[rel]:
        o = bpy.data.objects.new("p", me); scene.collection.objects.link(o); o.matrix_world = M @ local


STONE = mat("stone", "AGH2Blocks.dds"); PLASTER = mat("plaster", "AGH2Plaster.dds"); BEAM = mat("beam", "AGH2Beam.dds", 128.0)
BOARDS = mat("boards", "AGH2Boards.dds"); PANEL = mat("panel", "AGH2Panel.dds", 128.0); PLANKS = mat("planks", "AGH2Planks2.dds")
WATERM = mat("water", None, rgba=(0.18, 0.35, 0.45, 0.35)); FIGM = mat("fig", None, rgba=(0.8, 0.25, 0.18, 1.0))


def figure(x, y, z):
    bpy.ops.mesh.primitive_cylinder_add(radius=18, depth=104, location=(x, y, z + 52)); bpy.context.object.data.materials.append(FIGM[0])
    bpy.ops.mesh.primitive_uv_sphere_add(radius=12, location=(x, y, z + 116)); bpy.context.object.data.materials.append(FIGM[0])


def floor(x0, y0, x1, y1, z, m=STONE): box((x0, y0, z - 12), (x1, y1, z), m, "floor")


def wall(axis, at, a0, a1, z0, z1, gaps=(), finish="plaster", th=T):
    """a wall along y (axis 'x': its plane x = at) or along x (axis 'y'), centred on the line, th thick, with openings
    (a, b, head height over z0); plaster over a panelled base, or stone"""
    def seg(s0, s1, zz0, zz1):
        if s1 - s0 < 0.5 or zz1 - zz0 < 0.5: return
        lo = [0, 0, zz0]; hi = [0, 0, zz1]
        if axis == "x": lo[0], hi[0], lo[1], hi[1] = at - th / 2, at + th / 2, s0, s1
        else: lo[1], hi[1], lo[0], hi[0] = at - th / 2, at + th / 2, s0, s1
        if finish == "stone": box(lo, hi, STONE, "wall")
        else:
            box(lo, (hi[0], hi[1], min(zz1, max(zz0, z0 + 64))), PANEL, "base")
            if zz1 > z0 + 64: box((lo[0], lo[1], max(zz0, z0 + 64)), hi, PLASTER, "wall")
    cuts = sorted(gaps); s = a0
    for g0, g1, head in cuts:
        seg(s, g0, z0, z1); seg(g0, g1, z0 + head, z1); s = g1
    seg(s, a1, z0, z1)


def timber(x0, y0, x1, y1, along="x"):
    """boards under the ground floor and joists every 64, 14 deep, across the short way"""
    box((x0, y0, CEIL), (x1, y1, CEIL + 4), BOARDS, "boards", True)
    if along == "x":
        for x in range(int(x0) + 8, int(x1) - 8, 64): box((x, y0, CEIL - 14), (x + 12, y1, CEIL), BEAM, "joist", True)
    else:
        for y in range(int(y0) + 8, int(y1) - 8, 64): box((x0, y, CEIL - 14), (x1, y + 12, CEIL), BEAM, "joist", True)


def vault(x0, y0, x1, y1, fl, along, spring=150.0, crown=CEIL - 16, cut=None):
    """a segmental stone barrel vault over a rectangle, its axis along x or y, springing `spring` over the floor; cut: a
    rectangle (x0, y0, x1, y1) left open (a shaft through it)"""
    if along == "x": s0, s1, l0, l1 = y0, y1, x0, x1
    else: s0, s1, l0, l1 = x0, x1, y0, y1
    zs = fl + spring; h = crown - zs; w = s1 - s0
    R = (h * h + (w / 2) ** 2) / (2 * h); c = (s0 + s1) / 2; zc0 = crown - R; a0 = math.asin((w / 2) / R); N = 20; M_ = max(2, int((l1 - l0) // 32))
    pts = [(c + R * math.sin(-a0 + 2 * a0 * i / N), zc0 + R * math.cos(-a0 + 2 * a0 * i / N)) for i in range(N + 1)]
    me = bpy.data.meshes.new("vault"); bm = bmesh.new(); uvl = bm.loops.layers.uv.new()
    arc = [0.0]
    for i in range(N): arc.append(arc[-1] + math.dist(pts[i], pts[i + 1]))
    for j in range(M_):
        la, lb = l0 + (l1 - l0) * j / M_, l0 + (l1 - l0) * (j + 1) / M_
        for i in range(N):
            (sa, za), (sb, zb) = pts[i], pts[i + 1]
            def P(l, s_, z_): return (l, s_, z_) if along == "x" else (s_, l, z_)
            q = [P(la, sa, za), P(lb, sa, za), P(lb, sb, zb), P(la, sb, zb)]
            if cut:
                cx, cy = sum(p[0] for p in q) / 4, sum(p[1] for p in q) / 4
                if cut[0] <= cx <= cut[2] and cut[1] <= cy <= cut[3]: continue
            f = bm.faces.new([bm.verts.new(p) for p in q])
            for l_, (u, v) in zip(f.loops, ((la, arc[i]), (lb, arc[i]), (lb, arc[i + 1]), (la, arc[i + 1]))): l_[uvl].uv = (u / 256, v / 256)
    bm.to_mesh(me); bm.free(); me.materials.append(STONE[0])
    o = bpy.data.objects.new("vault", me); scene.collection.objects.link(o); CEILINGS.append(o)
    return pts


# ---------------------------------------------------------------- the rooms
HY0, HY1 = 791.0, 940.0                                      # the main hallway (the overlay's 780 -> 791: a 32 wall to the training room)
floor(-1100, HY0, 256, HY1, F0); timber(-1100, HY0, 256, HY1, "x")
floor(0, HY1, 256, 1060, F0); timber(0, HY1, 256, 1060, "x")                     # the entry: an alcove off the hallway's east end
floor(-1400, 200, -1100, 940, F0)                            # the cellar, under the kitchen
floor(-260, HY1, 0, HY1 + 320, F0)                           # the prison cell
floor(-760, HY1, -420, 1260, F0)                             # the secret room, into the hill
# (the bath, the overlay's -420 -> -444, down three steps: its deck is laid round the pool below)
floor(-412, 318, -280, 791, F1)                              # the steps' strip
floor(-280, 51, 336, 759, F1); floor(336, 215, 1400, 759, F1)   # the training room: the main area and the range
timber(-412, 51, 336, 791, "x")

# walls (centred on the rooms' shared lines; doorways 112 wide, 176 high under the 230 clear)
DH = 176
wall("y", HY1 + T / 2, -1100, 256, F0, CEIL, gaps=[(-188, -72, DH), (-650, -530, 224), (0, 256, 999)])   # hallway north: cell, secret door, the entry
wall("y", HY0 - T / 2, -1100, 256, F1, CEIL, gaps=[(-910, -798, DH + 48), (-412, -280, DH + 48)])     # hallway south: the bath's door, the strip
wall("x", -1100 - T / 2, HY0, HY1, F0, CEIL, gaps=[(812, 920, DH)], finish="stone")                  # hallway west: the cellar's door
wall("x", 256 + T / 2, HY0, 1060, F0, CEIL, gaps=[(802, 898, DH)])                                    # hallway east: the tower's door
wall("y", 1060 + T / 2, 0, 256, F0, CEIL); wall("x", -T / 2, HY1, 1060, F0, CEIL)                      # the entry's sides
# the cellar (stone, a vault along y with a shaft through its haunch over the ladder)
wall("x", -1400 - T / 2, 200, 940, F0, CEIL, finish="stone"); wall("y", 200 - T / 2, -1400, -1100, F0, CEIL, finish="stone")
wall("y", 940 + T / 2, -1400, -1100, F0, CEIL, finish="stone"); wall("x", -1100 + T / 2, 200, HY0, F1, CEIL, finish="stone")
SHAFT = (-1400, 341, -1320, 441)
vault(-1400, 200, -1100, 940, F0, "y", cut=SHAFT)
for lo_, hi_ in (((SHAFT[0], SHAFT[1] - 8, -150), (SHAFT[2], SHAFT[1], CEIL)), ((SHAFT[0], SHAFT[3], -150), (SHAFT[2], SHAFT[3] + 8, CEIL)),
                 ((SHAFT[2], SHAFT[1] - 8, -150), (SHAFT[2] + 8, SHAFT[3] + 8, CEIL))):
    box(lo_, hi_, PLANKS, "shaft")                           # the shaft's timber lining up to the kitchen's floor
box((-1400, 200, CEIL), (-1100, 940, CEIL + 4), STONE, "cellar_top", True)
piece("dungeons/imperial/door/trapdoorladder02.nif", -1372, 391, F0, 90, (CEIL - 2 - F0) / 197.0)
for i, y in enumerate((260, 430, 600)):
    piece("clutter/brewerycasklargeclosed01.nif", -1180, y, F0, 270)
for y in (720, 780, 840):
    piece("clutter/barrel02.nif", -1370, y, F0, 0); piece("clutter/meadery/meadbarrel01.nif", -1330, y, F0 + 80, 90)
# the prison cell, like other prison cells: as the town jails' (measured: Windhelm's and Riften's cells
# are one jail-kit module, 256, wide and over 300 deep, the bars on the corridor): the Imperial kit's door frame and door at
# 0.9 (255 tall under the hallway's 230), a hay bedroll from the bars to the back wall (Windhelm's: 156 in, at right angles
# to the bars), a bucket by the bars, hay on the floor, stone round it and a flat stone ceiling
CY1 = HY1 + 320
wall("x", -260 - T / 2, HY1, CY1, F0, CEIL, finish="stone"); wall("y", CY1 + T / 2, -260, 0, F0, CEIL, finish="stone")
box((-260, HY1, CEIL), (0, CY1, CEIL + 8), STONE, "cell_top", True)
# (the frame's run is its local +x from its origin; its inside is its local -y: yaw 180 puts the inside to +y, origin at x -13)
piece("dungeons/imperial/jail/impjaildoorframe01.nif", -13, HY1 + 8, F0, 180, 0.9)
piece("dungeons/imperial/jail/impjaildoor01.nif", -13, HY1 + 8, F0, 180, 0.9)
piece("furniture/bedroll/bedrollhay01.nif", -150, HY1 + 8 + 156, F0, 0)
piece("clutter/bucket01.nif", -40, HY1 + 40, F0, 0); piece("clutter/hay/hayscatter02.nif", -80, HY1 + 230, F0 + 0.5, 30)
# the secret room: the big door (vanilla's dungeon door, 303 tall, scaled to the hallway's 230), stone, a vault along y
wall("x", -760 - T / 2, HY1, 1260, F0, CEIL, finish="stone"); wall("x", -420 + T / 2, HY1, 1260, F0, CEIL, finish="stone")
wall("y", 1260 + T / 2, -760, -420, F0, CEIL, finish="stone")
vault(-760, HY1 + T, -420, 1260, F0, "y")
piece("dungeons/imperial/door/impwooddoorsingle01.nif", -590, HY1 + 4, F0, 0, 0.74)
# the bath: stone, a vault along y; the three steps down from the hallway's door; the pool, its water at -316
wall("x", -1060 - T / 2, 200, HY0 - T, F1, CEIL, finish="stone"); wall("y", 200 - T / 2, -1060, -444, F1, CEIL, finish="stone")
wall("x", -444 + T / 2, 200, HY0 - T, F1, CEIL, finish="stone")
vault(-1060, 200, -444, HY0 - T, F1, "y", spring=170)
for k in range(3):
    y1 = HY0 - T - k * TREAD
    box((-910, y1 - TREAD, F1), (-798, y1, F0 - k * RISE), STONE, "bstep")
# the pool, based on the pools of other mods: the bathhouse mods'
# common form (Riften Bathhouse, Underground Spa, Northern Bathhouses): a rectangular sunken stone pool flush with a flagged
# floor, real water (bathing mods ask the engine's water: Papyrus Extender's IsPointSubmergedMoreThan), about 72 deep
# (waist to chest standing), a sitting ledge 32 wide along the long sides with its seat 33 under the water, steps down at
# the end by the door, benches along the walls, braziers. 416 x 288 here (seats about six; the room is 616 x 559)
PX0, PY0, PX1, PY1 = -960, 270, -544, 558
PFL, LEDGE = WATER - 72, WATER - 33
box((PX0, PY0, PFL - 12), (PX1, PY1, PFL), STONE, "pool_floor")
for lo_, hi_ in (((PX0 - 12, PY0 - 12, PFL - 12), (PX0, PY1 + 12, F1)), ((PX1, PY0 - 12, PFL - 12), (PX1 + 12, PY1 + 12, F1)),
                 ((PX0, PY0 - 12, PFL - 12), (PX1, PY0, F1)), ((PX0, PY1, PFL - 12), (PX1, PY1 + 12, F1))):
    box(lo_, hi_, STONE, "pool_wall")
for y0_, y1_ in ((PY0, PY0 + 32), (PY1 - 32, PY1)): box((PX0 + 48, y0_, PFL), (PX1 - 48, y1_, LEDGE), STONE, "ledge")   # the ledges
for k in range(4):                                           # the steps down at the end by the door (x = PX1 side)
    box((PX1 - 32 * (k + 1), PY0 + 64, PFL), (PX1 - 32 * k, PY1 - 64, F1 - (k + 1) * (F1 - PFL) / 5), STONE, "pstep")
box((PX0, PY0, WATER - 1), (PX1, PY1, WATER), WATERM, "water")
for x0_, y0_, x1_, y1_ in ((-1060, 200, -444, PY0 - 12), (-1060, PY1 + 12, -444, 759), (-1060, PY0 - 12, PX0 - 12, PY1 + 12), (PX1 + 12, PY0 - 12, -444, PY1 + 12)):
    floor(x0_, y0_, x1_, y1_, F1)                            # the deck round the pool, flush with its edge
piece("furniture/common/commonbench01.nif", -760, 225, F1, 0); piece("furniture/common/commonbench01.nif", -1000, 640, F1, 0)
for bx_, by_ in ((-1025, 235), (-480, 235), (-480, 620)): piece("architecture/whiterun/wrclutter/wrbrazier01.nif", bx_, by_, F1, 0)
# the bath's door: the hall's own interior door in the hallway's wall
piece("architecture/solitude/doors/ssingledoorint01l.nif", -854, HY0 - T / 2, F0, 90)
# the training room, as decided
wall("x", -412 - T / 2, 318, HY0, F1, CEIL)                  # the strip's west wall (the bath behind)
wall("y", 318 - T / 2, -412, -280, F1, CEIL)                 # its south end
for k in range(3):                                           # its steps down from the hallway
    y1 = HY0 - k * TREAD
    box((-412, y1 - TREAD, F1), (-280, y1, F0 - k * RISE), STONE, "hstep")
wall("x", -280 + 0, 51, 318, F1, CEIL, th=28)                # the main area's west wall, below the strip
wall("y", 51 - T / 2, -280, 1400, F1, CEIL)                  # the front
box((336, 51, F1), (1400, 215, CEIL), STONE, "range_front")  # (no room under the range's front: marked out on the plan)
wall("x", 1400 + T / 2, 215, 759, F1, CEIL)
wall("y", 759 + T / 2, 256, 1400, F1, CEIL)                  # the range's back wall (east of the hallway's end)
box((336, 215, CEIL), (1400, 759, CEIL + 4), STONE, "range_top", True)
pts = vault(336, 215, 1400, 759, F1, "x")
for y0_, y1_ in ((215, 215 + 96), (759 - 96, 759)): box((336 - 16, y0_, F1), (336 + 16, y1_, CEIL), STONE, "entry_pillar")
for i in range(len(pts) - 1):
    (ya, za), (yb, zb) = pts[i], pts[i + 1]
    box((336 - 16, min(ya, yb), min(za, zb) - 18), (336 + 16, max(ya, yb), CEIL), STONE, "entry_rib", True)
# (the target's painted face is its mesh's local -x, rendered from both sides: yaw 0 faces the shooters at lower x)
for ty in (334, 494, 654): piece("clutter/common/archerytarget01.nif", 1361, ty, F1, 0)
for i, dx in enumerate((-150, 0, 150)): piece(f"clutter/practicedummy/practicedummy0{i + 1}.nif", 40 + dx, 110, F1, 0)
piece("architecture/solitude/doors/ssingledoorint01l.nif", 256 + T / 2, 850, F0, 0)   # the tower's door (a load door back up)

# people for scale
for p in ((-300, 865, F0), (-1250, 700, F0), (-750, 650, F1), (-590, 1150, F0), (-130, 1020, F0), (60, 420, F1), (350, 489, F1), (128, 1000, F0)):
    figure(*p)

# ---------------------------------------------------------------- light and views
w = bpy.data.worlds.new("amb"); scene.world = w; w.use_nodes = True
bg = w.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.75, 0.72, 0.66, 1); bg.inputs[1].default_value = 1.6
sd = bpy.data.lights.new("sun", 'SUN'); sd.energy = 1.5; sd.use_shadow = False
sun = bpy.data.objects.new("sun", sd); scene.collection.objects.link(sun); sun.rotation_euler = (math.radians(30), 0, math.radians(40))
cd = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cd); scene.collection.objects.link(cam); scene.camera = cam
cd.clip_end = 40000
VIEWS = {
    "plan": None,
    "hallway_from_tower": ((220, 865, F0 + 120), (-1000, 865, F0 + 80)),
    "hallway_from_cellar": ((-1080, 860, F0 + 120), (200, 870, F0 + 80)),
    "cellar": ((-1130, 880, F0 + 120), (-1330, 280, F0 + 70)),
    "cellar_ladder": ((-1250, 880, F0 + 120), (-1380, 391, F0 + 140)),
    "bath_from_door": ((-855, 690, F1 + 130), (-740, 360, F1 - 40)),
    "bath_corner": ((-1030, 230, F1 + 120), (-600, 600, F1 + 40)),
    "secret_door": ((-590, 815, F0 + 120), (-590, 1000, F0 + 100)),
    "secret_room": ((-590, 975, F0 + 120), (-590, 1250, F0 + 70)),
    "prison_cell": ((-130, 815, F0 + 120), (-130, 1100, F0 + 50)),
    "pool": ((-470, 640, F1 + 150), (-760, 410, PFL)),
    "entry": ((-150, 860, F0 + 120), (180, 1020, F0 + 90)),
    "training_steps": ((-346, 785, F0 + 120), (100, 300, F1 + 60)),
    "range": ((360, 489, F1 + 110), (1400, 489, F1 + 60)),
}
for name, v in VIEWS.items():
    for o in CEILINGS: o.hide_render = (v is None)
    if v is None:
        cd.type = 'ORTHO'; cd.ortho_scale = 2950; cd.clip_start = 1
        cam.location = (0, 655, 2000); cam.rotation_euler = (0, 0, 0)
        scene.render.resolution_x, scene.render.resolution_y = 1600, 1000
    else:
        cd.type = 'PERSP'; cd.lens = 14; cd.clip_start = 2
        scene.render.resolution_x, scene.render.resolution_y = 1280, 720
        eye, look = v; cam.location = eye
        cam.rotation_euler = (mathutils.Vector(look) - mathutils.Vector(eye)).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = os.path.join(out, f"{name}.png"); bpy.ops.render.render(write_still=True); print("RENDERED", name)
