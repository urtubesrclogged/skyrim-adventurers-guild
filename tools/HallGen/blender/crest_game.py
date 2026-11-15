"""The Guild crest as a game mesh for the hall's roundel: the approved emblem (tools/blender_crest.py: the four-dragon
ring, the shield, the sword) rebuilt to a budget per part, its fine detail (body scales, rivets, the grip's wrap, the
heads' sculpting) baked into a normal map and its cast-metal colouring into a colour map, flattened into a relief.
Vanilla's sculpted pieces work this way (Mara 2.5k triangles, Talos 3.2k, the castle gargoyle 6.4k, each one mesh
with a baked normal map); the relief it replaces was an extruded picture (stepped "Minecraft" sides, stretched).
    blender -b --factory-startup -P crest_game.py -- <tools dir> <out dir> [texture size 2048] [samples 16] [gpu]
-> <out>/crest_low.json  {"v": [[x, y, z]], "f": [[i, j, k]], "uv": [[[u, v] x3]]} in the crest's own frame, game units:
                         x right, y up, z out of the wall, its back plane at z 0 (on the roundel's face)
   <out>/crest_c.png (the game's colour: the cast colour, partly lit as the approved renders show it), crest_n.png
   (tangent-space normal, Blender's +Y convention), crest_s.png (specular); crest_d.png and crest_o.png (plain colour,
   object-space normals) are what crest_c is made from
   <out>/review_*.png (the full model against the game mesh with its maps: front, 45 degrees, side)"""
import bpy, bmesh, sys, os, math, json, time
from mathutils import Vector, Matrix
a = sys.argv[sys.argv.index("--") + 1:]
TOOLS, OUT = a[0], a[1]
TEX = int(a[2]) if len(a) > 2 else 2048
SAMP = int(a[3]) if len(a) > 3 else 16
os.makedirs(OUT, exist_ok=True)
t0 = time.time()
def log(*x): print("CREST", f"{time.time() - t0:6.1f}s", *x, flush=True)

# ---------------------------------------------------------------- the approved model, as blender_crest.py builds it
src = open(os.path.join(TOOLS, "blender_crest.py"), encoding="utf-8").read()
src = src[:src.rstrip().rfind("main()")]                        # everything but the final call
sys.argv = ["blender", "--", OUT, "900", "24"]
ns = {"__file__": os.path.join(TOOLS, "blender_crest.py"), "__name__": "crest_game"}
exec(compile(src, "blender_crest.py", "exec"), ns)
rm = ns["load_ring"](); ns["RING"] = rm; rm.SIZE, rm.SAMPLES = 900, 24
sc = rm.reset(); rm.build_ring(); rm.lights_and_camera(sc)
slots = ns["record_bronze_slots"](); metal = ns["metal"]
bz = ('GuildBronze', (0.34, 0.22, 0.10), (0.17, 0.11, 0.05), (0.03, 0.018, 0.007), 0.34, 0.62, 1.0, (0.07, 0.13, 0.10), 1.4)
bronze_m = metal(*bz); bronze_p = metal(bz[0], (0.46, 0.32, 0.16), *bz[2:8], 0.0, polished=True)
ns["recast"](slots, bronze_m, bronze_p)
iron_m = metal('ShieldIron', (0.125, 0.105, 0.085), (0.052, 0.044, 0.035), (0.015, 0.012, 0.009), 0.50, 0.75, 1.0, (0.20, 0.10, 0.04), 1.0, wear=0.2, hammer=True)
iron_p = metal('ShieldIron', (0.20, 0.17, 0.135), (0.08, 0.068, 0.054), (0.015, 0.012, 0.009), 0.42, 0.62, 1.0, (0.1, 0.1, 0.1), 0.0, polished=True, wear=0.4)
steel_p = metal('BladeSteel', (0.30, 0.28, 0.245), (0.14, 0.125, 0.105), (0.03, 0.025, 0.02), 0.34, 0.52, 1.0, (0.1, 0.1, 0.1), 0.0, wear=0.6)
ns["shield"](rm, iron_m, iron_p); ns["sword"](rm, steel_p, bronze_p)
log("built", len([o for o in sc.objects if o.type == 'MESH']), "meshes")

# ---------------------------------------------------------------- the relief frame
GU = 29.0                  # game units per ring unit: the fins' tips at 121 (the roundel's face is 130), the sword 147
ZBACK = -0.68              # the shield's back: the relief's back plane, laid on the roundel's face
ZK = 14.0 / GU             # depth kept: 14 game units per ring unit in depth against 29 across (a relief, 21 deep)

def realize(o):
    """modifiers applied and the transform baked in, so every part is plain mesh in world space"""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg)
    me.transform(o.matrix_world)
    o.modifiers.clear(); old = o.data; o.data = me; o.matrix_world = Matrix.Identity(4)
    if old.users == 0: bpy.data.meshes.remove(old)
def squash(me):
    for v in me.vertices: v.co.z = ZBACK + (v.co.z - ZBACK) * ZK
    me.update()

HIGH = [o for o in sc.objects if o.type == 'MESH']
for o in HIGH: realize(o); squash(o.data)
for mat in bpy.data.materials:                               # the AO reach was set for the unsquashed model
    if mat.use_nodes:
        for nd in mat.node_tree.nodes:
            if nd.type == 'AMBIENT_OCCLUSION': nd.inputs['Distance'].default_value *= 0.75
def group_of(name):
    if name.startswith("Shield"): return "shield"
    if name in ("Blade", "Guard", "GuardGem", "Grip", "Pommel"): return "sword"
    if "_b." in name: return "head" + name.rsplit(".", 1)[1]
    return "ring"
G = {}
for o in HIGH: G.setdefault(group_of(o.name), []).append(o)
# The scales are open plates, wound by recalc_face_normals, which turns many of them inward. A render shades both sides
# of a plate the same, so the approved images never showed it; a normal bake records the inward normal, and an inward
# normal in a normal map shades black (the dark band at every neck, where the collar's big plates sit). Each plate is
# turned to face the way the surface it lies on faces: the body tube for the body's scales, its head for a head's.
from mathutils.bvhtree import BVHTree
def orient_plates(plates, bases):
    V, F = [], []
    for o in bases:
        b0 = len(V); V += [v.co.copy() for v in o.data.vertices]; F += [[b0 + i for i in q.vertices] for q in o.data.polygons]
    bvh = BVHTree.FromPolygons(V, F); flipped = 0
    for o in plates:
        bm = bmesh.new(); bm.from_mesh(o.data); bm.normal_update()
        for f in bm.faces:
            hit = bvh.find_nearest(f.calc_center_median())
            if hit[0] is not None and f.normal.dot(hit[1]) < 0: f.normal_flip(); flipped += 1
        bm.to_mesh(o.data); bm.free(); o.data.update()
    return flipped
nf = orient_plates([o for o in G["ring"] if o.name == "Scales"], [o for o in G["ring"] if o.name == "Bodies"])
for k, objs in G.items():
    if k.startswith("head"):
        nf += orient_plates([o for o in objs if o.name.startswith("Scales")], [o for o in objs if not o.name.startswith("Scales")])
log("scale plates turned outward:", nf)
log("groups", {k: (len(v), sum(len(o.data.polygons) for o in v)) for k, v in G.items()})

# ---------------------------------------------------------------- the game mesh, part by part
def dup(o, name):
    me = o.data.copy(); ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob); return ob
def tris(o):
    o.data.calc_loop_triangles(); return len(o.data.loop_triangles)
def decimate(o, target):
    n = tris(o)
    if n <= target: return
    m = o.modifiers.new("dec", 'DECIMATE'); m.ratio = target / n; m.use_collapse_triangulate = True
    realize(o)
def remesh(o, voxel):
    m = o.modifiers.new("rm", 'REMESH'); m.mode = 'VOXEL'; m.voxel_size = voxel; m.adaptivity = 0.0; m.use_smooth_shade = True
    realize(o)
def join(objs, name):
    bm = bmesh.new()
    for o in objs: bm.from_mesh(o.data)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    for o in objs: bpy.data.objects.remove(o, do_unlink=True)
    return ob
def cull(o, nz=-0.35):
    """faces nobody can see on a wall: those turned toward it, and those wholly behind the back plane"""
    bm = bmesh.new(); bm.from_mesh(o.data); bm.normal_update()
    dead = [f for f in bm.faces if f.normal.z < nz or all(v.co.z < ZBACK + 0.004 for v in f.verts)]
    bmesh.ops.delete(bm, geom=dead, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(o.data); bm.free(); o.data.update()
    for p in o.data.polygons: p.use_smooth = True

BUDGET = {"Bodies": 3400, "Fins": 2400, "ShieldWood": 400, "ShieldRim": 700, "ShieldBoss": 500, "ShieldStraps": 500,
          "Blade": 300, "Guard": 500, "Pommel": 300, "Grip": 260, "GuardGem": 40}
HEAD = 1500
LOW = {}
for gname, objs in G.items():
    parts = []
    if gname.startswith("head"):
        h = join([dup(o, o.name + "_lo") for o in objs], gname + "_low")
        remesh(h, 0.0075); n0 = tris(h)
        decimate(h, HEAD); parts.append(h)
        log(gname, "remeshed", n0, "->", tris(h))
    else:
        for o in objs:
            if o.name not in BUDGET: continue                   # the body scales, the rivets: carried by the maps
            d = dup(o, o.name + "_lo"); decimate(d, BUDGET[o.name]); parts.append(d)
    lo = join(parts, gname + "_low"); cull(lo)
    for p in lo.data.polygons: p.use_smooth = True
    LOW[gname] = lo
    log(gname, "game mesh", tris(lo), "triangles")
total = sum(tris(o) for o in LOW.values())
log("TOTAL game triangles", total)

# ---------------------------------------------------------------- one atlas for all of it
bake_img = {k: bpy.data.images.new("crest_" + k, TEX, TEX, alpha=False, float_buffer=(k in ("n", "o"))) for k in ("d", "n", "s", "o", "c")}
for k in ("n", "s", "o"): bake_img[k].colorspace_settings.name = "Non-Color"
lowmat = bpy.data.materials.new("CrestLow"); lowmat.use_nodes = True
img_node = lowmat.node_tree.nodes.new("ShaderNodeTexImage")
lowmat.node_tree.nodes.active = img_node
for o in LOW.values():
    o.data.materials.clear(); o.data.materials.append(lowmat)
    o.data.uv_layers.new(name="UVMap")
bpy.ops.object.select_all(action='DESELECT')
for o in LOW.values(): o.select_set(True)
bpy.context.view_layer.objects.active = next(iter(LOW.values()))
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(80), island_margin=0.001, scale_to_bounds=False)   # few, large islands: a
bpy.ops.uv.pack_islands(rotate=True, margin=0.004)                                                   # relief is seen from the front
bpy.ops.object.mode_set(mode='OBJECT')
log("unwrapped")

# ---------------------------------------------------------------- bakes: each group from its own high parts only
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = SAMP
if len(a) > 4 and a[4] == "gpu":
  try:                                                       # the GPU when there is one (HIP here): bakes go from minutes to seconds
    # On this machine (RX 9070 XT, HIP) a test bake runs in a second, but the crest's first bake never finished, with or
    # without the integrated GPU (2026-10-24): CPU by default, the GPU only on request.
    cp = bpy.context.preferences.addons['cycles'].preferences
    for kind in ('OPTIX', 'CUDA', 'HIP', 'ONEAPI', 'METAL'):
        try: cp.compute_device_type = kind
        except Exception: continue
        cp.get_devices()
        gpus = [d for d in cp.devices if d.type == kind]
        if gpus:
            solo = [d for d in gpus if "(TM) Graphics" not in d.name] or gpus
            for d in cp.devices: d.use = d in solo
            sc.cycles.device = 'GPU'; log('baking on', kind, [d.name for d in solo]); break
  except Exception as ex: log('GPU unavailable, CPU bakes:', ex)
bk = sc.render.bake; bk.use_selected_to_active = True
bk.cage_extrusion = 0.05; bk.max_ray_distance = 0.12
bk.margin = max(1, int(TEX * 0.0015))                     # under half the islands' gap: a later group's margin must not
                                                           # paint over an earlier group's islands (dark blotches); crest_dds.py fills the rest
for o in LOW.values():                                     # the game mesh must not shade the model it is baked from
    o.visible_camera = o.visible_diffuse = o.visible_glossy = o.visible_shadow = o.visible_transmission = o.visible_volume_scatter = False
def bake(kind, btype, **kw):
    img_node.image = bake_img[kind]
    first = True
    for gname, lo in LOW.items():
        bpy.ops.object.select_all(action='DESELECT')
        for o in HIGH: o.hide_render = o not in G[gname]    # each part baked as if it stood alone: a head's game mesh ends a
        for o in G[gname]: o.select_set(True)               # little short of its neck, and the strip of body it uncovers was
                                                            # shaded by the real head (a dark band at every neck)
        lo.select_set(True); bpy.context.view_layer.objects.active = lo
        bk.use_clear = first; first = False
        bpy.ops.object.bake(type=btype, **kw)
    for o in HIGH: o.hide_render = False
    log("baked", kind)
sc.cycles.samples = 2; bake("n", 'NORMAL', normal_space='TANGENT')
sc.cycles.samples = 1; bake("o", 'NORMAL', normal_space='OBJECT')     # for the lit colour, below
for mat in bpy.data.materials:                             # the cast-metal ramps read ambient occlusion: fewer rays each
    if mat.use_nodes:
        for nd in mat.node_tree.nodes:
            if nd.type == 'AMBIENT_OCCLUSION': nd.samples = 8
sc.cycles.samples = SAMP
# colour and specular: each material made to emit its base colour (its AO-driven cast-metal ramp included), then its gloss
SPEC = {"GuildBronze": 0.75, "GuildBronzePolished": 0.95, "ShieldIron": 0.40, "ShieldIronPolished": 0.65, "BladeSteel": 0.85,
        "ShieldWood": 0.06, "Wrap": 0.12, "Gem": 1.0, "EyeMat": 0.9, "Pupil": 0.3, "Maw": 0.05, "NostrilDark": 0.05}
saved = {}
def emit(mode):
    for mat in bpy.data.materials:
        if mat is lowmat or not mat.use_nodes: continue
        nt = mat.node_tree
        out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None) or next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None)
        if out is None: continue
        if mat.name not in saved: saved[mat.name] = [(l.from_socket, l.to_socket) for l in nt.links if l.to_node == out]
        for l in [l for l in nt.links if l.to_node == out]: nt.links.remove(l)
        em = nt.nodes.get("BakeEmit") or nt.nodes.new("ShaderNodeEmission"); em.name = "BakeEmit"
        for l in [l for l in nt.links if l.to_node == em]: nt.links.remove(l)
        if mode == "colour":
            pb = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if pb is not None and pb.inputs["Base Color"].is_linked: nt.links.new(pb.inputs["Base Color"].links[0].from_socket, em.inputs["Color"])
            elif pb is not None: em.inputs["Color"].default_value = pb.inputs["Base Color"].default_value
            else: em.inputs["Color"].default_value = (0.2, 0.2, 0.2, 1)
        else:
            base = mat.name.split(".")[0]
            s = next((v for k, v in SPEC.items() if base.startswith(k)), 0.5)
            em.inputs["Color"].default_value = (s, s, s, 1)
        em.inputs["Strength"].default_value = 1.0
        nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
import numpy as np
emit("colour"); bake("d", 'EMIT')
sc.cycles.samples = 1; emit("spec"); bake("s", 'EMIT')
# The colour the game gets (crest_lit.py: the cast colour partly lit as the approved renders show it, thin plates hit
# from behind turned round); crest_dds.py makes the game's texture with the same function
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd())
import numpy as np
import crest_lit
def px(img): return np.array(img.pixels[:], dtype=np.float32).reshape(TEX, TEX, 4)[..., :3]
col = crest_lit.lit_colour(px(bake_img["d"]), px(bake_img["o"]) * 2 - 1, px(bake_img["s"])[..., 0], px(bake_img["n"]) * 2 - 1)
bake_img["c"].pixels[:] = np.concatenate([col.astype(np.float32), np.ones((TEX, TEX, 1), np.float32)], axis=2).ravel()
log("lit colour made")
for name, links in saved.items():                          # the model's own shading back, for the review renders
    nt = bpy.data.materials[name].node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    for l in [l for l in nt.links if l.to_node == out]: nt.links.remove(l)
    for fs, ts in links: nt.links.new(fs, ts)
for k, img in bake_img.items():
    img.filepath_raw = os.path.join(OUT, f"crest_{k}.png"); img.file_format = 'PNG'; img.save()
log("saved maps")

# ---------------------------------------------------------------- the game mesh out, in game units
V, F, UV = [], [], []
for o in LOW.values():
    me = o.data; me.calc_loop_triangles(); uvl = me.uv_layers.active.data; base = len(V)
    V += [[round(v.co.x * GU, 3), round(v.co.y * GU, 3), round((v.co.z - ZBACK) * GU, 3)] for v in me.vertices]
    for t in me.loop_triangles:
        F.append([base + i for i in t.vertices]); UV.append([[round(uvl[l].uv[0], 5), round(uvl[l].uv[1], 5)] for l in t.loops])
json.dump({"v": V, "f": F, "uv": UV, "tris": len(F), "gu": GU, "zk": ZK}, open(os.path.join(OUT, "crest_low.json"), "w"))
ext = [(min(p[k] for p in V), max(p[k] for p in V)) for k in range(3)]
log("wrote crest_low.json", len(F), "triangles | extent x", [round(e, 1) for e in ext[0]], "y", [round(e, 1) for e in ext[1]], "z", [round(e, 1) for e in ext[2]])

# ---------------------------------------------------------------- review: the model beside the game mesh with its maps
nt = lowmat.node_tree; pb = nt.nodes["Principled BSDF"]
td = nt.nodes.new("ShaderNodeTexImage"); td.image = bake_img["c"]
tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = bake_img["n"]
ts_ = nt.nodes.new("ShaderNodeTexImage"); ts_.image = bake_img["s"]
nm = nt.nodes.new("ShaderNodeNormalMap")
nt.links.new(td.outputs["Color"], pb.inputs["Base Color"]); nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
nt.links.new(nm.outputs["Normal"], pb.inputs["Normal"])
inv = nt.nodes.new("ShaderNodeMath"); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
nt.links.new(ts_.outputs["Color"], inv.inputs[1]); nt.links.new(inv.outputs["Value"], pb.inputs["Roughness"])
pb.inputs["Metallic"].default_value = 0.0
for o in LOW.values(): o.visible_camera = o.visible_diffuse = o.visible_glossy = o.visible_shadow = True
cam = sc.camera; cam.data.type = 'ORTHO'; cam.data.ortho_scale = 2 * 5.3
sc.cycles.samples = 48; sc.render.resolution_x = sc.render.resolution_y = 900
def shot(name, angle, show_low):
    for o in HIGH: o.hide_render = show_low
    for o in LOW.values(): o.hide_render = not show_low
    a_ = math.radians(angle); r_ = 30.0
    cam.location = (r_ * math.sin(a_), 0.0, ZBACK + r_ * math.cos(a_)); cam.rotation_euler = (0.0, a_, 0.0)
    sc.render.filepath = os.path.join(OUT, name); bpy.ops.render.render(write_still=True)
for ang in (0, 45, 80):
    shot(f"review_model_{ang:02d}.png", ang, False); shot(f"review_game_{ang:02d}.png", ang, True)
log("review renders done")
