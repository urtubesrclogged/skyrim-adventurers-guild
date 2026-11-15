"""Headless Blender: the sign board's carved dragon head. A Nordic head in profile (open jaws, a horn sweeping back, a
scroll on the cheek), carved in oak: the full model (the outline extruded, its edges rounded, the carving displaced into
its sides) baked onto the game's head (the same outline, chamfered, a few hundred triangles).
    python head_carve.py <out dir>      (the carving's height map, first)
    blender -b --factory-startup -P head_bake.py -- <out dir> <oak diffuse png/dds> [size 1024] [samples 64]
-> <out>/head_low.json   the game head: {"v", "f", "uv"} in the head's frame (x along the snout, z up, y through it:
                         the right side faces -y), game units; its neck's end at x 0
   <out>/head_c_full.png, head_n_full.png (1024 x 768: its sides in the top two thirds, its rim in the bottom third;
   board_layout's "head" + "headcap" regions, one block)"""
import bpy, bmesh, sys, os, math, json
from mathutils import Vector
a = sys.argv[sys.argv.index("--") + 1:]
OUT, OAK = os.path.abspath(a[0]), a[1]
TEX = int(a[2]) if len(a) > 2 else 1024
SAMP = int(a[3]) if len(a) > 3 else 64
os.makedirs(OUT, exist_ok=True)
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene

# ---------------------------------------------------------------- the outline (x along the snout, z up), game units
KEY = [(0, 0), (5, 0.4), (9, 1.1), (13, 1.0), (16.5, 1.4), (19.5, 2.4), (21, 3.7), (19.6, 4.0),            # 0-7: jaw, its tip
       (18.6, 3.75), (18.0, 4.7), (17.3, 3.6), (15.9, 3.45), (15.3, 4.4), (14.7, 3.45), (13.4, 3.5), (12.8, 4.3),  # 8-15: lower teeth
       (12.2, 3.65), (10.4, 4.6),                                                                               # 16-17: the mouth's corner
       (11.6, 5.2), (12.3, 4.25), (13.0, 5.3), (14.6, 5.2), (15.3, 4.2), (16.0, 5.15), (17.6, 5.2), (18.3, 4.3),   # 18-25: upper teeth
       (19.0, 5.35), (20.5, 5.6), (23.2, 6.7), (23.4, 7.9), (21.8, 8.7), (18.2, 8.6), (15, 9.1),                 # 26-32: snout
       (12.4, 10.5), (10.2, 10.3), (8.8, 11.6), (6.8, 14.0), (4.0, 16.4), (1.0, 17.4), (-1.4, 16.8),              # 33-39: brow, horn
       (-2.4, 15.4), (-1.6, 14.2), (-0.3, 14.6), (0.5, 15.3), (1.6, 14.6),                                      # 40-44: its curl
       (3.0, 13.2), (3.6, 12.0), (2.9, 10.8), (1.4, 9.4), (0.0, 8.0)]                                           # 45-49: the mane, the neck
SHARP = {6, 9, 12, 15, 17, 19, 22, 25, 28, 29, 39}   # the jaw's tip, the teeth, the mouth's corner, the snout, the horn

def chaikin(pts, n, sharp):
    for _ in range(n):
        out = []; m = len(pts); keep = set()
        for i in range(m):
            p, q = Vector(pts[i]), Vector(pts[(i + 1) % m])
            if i in sharp:
                keep.add(len(out)); out.append(tuple(p))
            out += [tuple(p * 0.75 + q * 0.25), tuple(p * 0.25 + q * 0.75)]
        pts = out; sharp = keep
    return pts

HI = chaikin(KEY, 3, SHARP)
LO = chaikin(KEY, 1, SHARP)
T = 5.2                                   # thickness (y)
XMIN, XMAX, ZMIN, ZMAX = -3.0, 25.0, -1.0, 18.5   # the side's UV frame: 27 x 19.5 units on the 1024 x 512 region... (scaled to fit)
SW_ = max(XMAX - XMIN, (ZMAX - ZMIN) * 2)          # one scale for both axes: the region is 2:1

def side_uv(x, z):
    return ((x - XMIN) / SW_, (z - ZMIN) / (SW_ / 2))

def slab(name, pts, bevel_w, bevel_seg):
    bm = bmesh.new()
    vb = [bm.verts.new((x, T / 2, z)) for x, z in pts]
    vf = [bm.verts.new((x, -T / 2, z)) for x, z in pts]
    ff = bm.faces.new(vf); fb = bm.faces.new(list(reversed(vb)))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n; bm.faces.new((vb[i], vb[j], vf[j], vf[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o)
    bpy.context.view_layer.objects.active = o
    if bevel_w:
        bv = o.modifiers.new("bevel", 'BEVEL'); bv.width = bevel_w; bv.segments = bevel_seg; bv.limit_method = 'ANGLE'
        bv.angle_limit = math.radians(60); bv.profile = 0.6
        bpy.ops.object.modifier_apply(modifier="bevel")
    return o

# ---------------------------------------------------------------- the carving: head_carve.py draws it (Blender has no PIL)
hpath = os.path.join(OUT, "head_height.png")
if not os.path.exists(hpath): sys.exit("run head_carve.py <out dir> first")

# ---------------------------------------------------------------- the full model
hi = slab("head_hi", HI, 1.5, 6)
# an even, dense surface first (a voxel remesh): the side is one n-gon, and subdividing it fans out from its middle
rem = hi.modifiers.new("remesh", 'REMESH'); rem.mode = 'VOXEL'; rem.voxel_size = 0.07; rem.use_smooth_shade = True
bpy.ops.object.modifier_apply(modifier="remesh")
# the carving, mapped side on through an empty: a legacy texture spans -1..1 of the empty's x and y (y turned to z)
emp = bpy.data.objects.new("carve_frame", None); sc.collection.objects.link(emp)
emp.location = (XMIN + SW_ / 2, 0, ZMIN + SW_ / 4); emp.rotation_euler = (math.radians(90), 0, 0); emp.scale = (SW_ / 2, SW_ / 4, 1)
tex = bpy.data.textures.new("carve", 'IMAGE'); tex.image = bpy.data.images.load(hpath); tex.extension = 'EXTEND'
dp = hi.modifiers.new("carve", 'DISPLACE'); dp.texture = tex; dp.texture_coords = 'OBJECT'; dp.texture_coords_object = emp
dp.strength = 1.1; dp.mid_level = 0.5
for p_ in hi.data.polygons: p_.use_smooth = True
print("HI", len(hi.data.polygons), "faces", flush=True)

# ---------------------------------------------------------------- the game head: sides mapped side on; the rim a strip
lo = slab("head_lo", LO, 0.7, 1)
bm = bmesh.new(); bm.from_mesh(lo.data)
tri = bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
bmesh.ops.beautify_fill(bm, faces=bm.faces[:], edges=bm.edges[:])
uvl = bm.loops.layers.uv.new("UVMap")
per = 0.0; rim_len = sum((Vector(LO[(i + 1) % len(LO)]) - Vector(LO[i])).length for i in range(len(LO)))
for f in bm.faces:
    side = abs(f.normal.y) > 0.7
    for l in f.loops:
        co = l.vert.co
        if side:
            u, v = side_uv(co.x, co.z); l[uvl].uv = (u, 1 / 3 + v * 2 / 3)      # the top two thirds: its sides
        else:
            # the rim: around the outline (by the nearest outline point's arc length) x across the thickness
            best, acc, s_at = 1e9, 0.0, 0.0
            for i in range(len(LO)):
                p0, p1 = Vector(LO[i]), Vector(LO[(i + 1) % len(LO)]); seg = p1 - p0; L = seg.length
                t = max(0.0, min(1.0, (Vector((co.x, co.z)) - p0).dot(seg) / (L * L))) if L else 0
                dd = (p0 + seg * t - Vector((co.x, co.z))).length
                if dd < best: best, s_at = dd, acc + t * L
                acc += L
            l[uvl].uv = (0.94 * s_at / rim_len, 0.01 + 0.31 * (co.y + T / 2) / T)   # the bottom third: the rim
bm.to_mesh(lo.data); bm.free()
# the rim's strip wraps at the outline's start: a face straddling it takes the far end
for poly in lo.data.polygons:
    us = [lo.data.uv_layers[0].data[li].uv.x for li in poly.loop_indices]
    if max(us) - min(us) > 0.5:
        for li in poly.loop_indices:
            if lo.data.uv_layers[0].data[li].uv.x < 0.5: lo.data.uv_layers[0].data[li].uv.x += 0.94

# ---------------------------------------------------------------- materials for the bake
def oak_mat():
    m = bpy.data.materials.new("oak"); m.use_nodes = True; nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(OAK)
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / 60.0, 1 / 60.0, 1 / 60.0)            # 60 units a tile: the grain along the head
    sepr = nt.nodes.new("ShaderNodeSeparateXYZ"); comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(tc.outputs["Object"], mp.inputs[0]); nt.links.new(mp.outputs[0], sepr.inputs[0])
    nt.links.new(sepr.outputs["X"], comb.inputs["X"]); nt.links.new(sepr.outputs["Z"], comb.inputs["Y"])
    nt.links.new(comb.outputs[0], t.inputs[0])
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion"); ao.inputs["Distance"].default_value = 1.2; ao.samples = 16
    mul = nt.nodes.new("ShaderNodeMixRGB"); mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 0.85
    nt.links.new(t.outputs["Color"], mul.inputs[1]); nt.links.new(ao.outputs["AO"], mul.inputs[2])
    ct = nt.nodes.new("ShaderNodeTexImage"); ct.image = bpy.data.images.load(hpath); ct.image.colorspace_settings.name = "Non-Color"
    ct.extension = 'EXTEND'
    tco = nt.nodes.new("ShaderNodeTexCoord"); tco.object = emp                    # the carving's own frame (-1..1)
    tm = nt.nodes.new("ShaderNodeMapping"); tm.inputs["Location"].default_value = (0.5, 0.5, 0); tm.inputs["Scale"].default_value = (0.5, 0.5, 1)
    nt.links.new(tco.outputs["Object"], tm.inputs[0]); nt.links.new(tm.outputs[0], ct.inputs[0])
    cav = nt.nodes.new("ShaderNodeMapRange"); cav.inputs["From Min"].default_value = 0.25; cav.inputs["From Max"].default_value = 0.5
    cav.inputs["To Min"].default_value = 0.45; cav.inputs["To Max"].default_value = 1.0
    nt.links.new(ct.outputs["Color"], cav.inputs["Value"])
    mul2 = nt.nodes.new("ShaderNodeMixRGB"); mul2.blend_type = 'MULTIPLY'; mul2.inputs[0].default_value = 1.0
    nt.links.new(mul.outputs[0], mul2.inputs[1]); nt.links.new(cav.outputs["Result"], mul2.inputs[2])
    em = nt.nodes.new("ShaderNodeEmission"); nt.links.new(mul2.outputs[0], em.inputs[0])
    nt.links.new(mul.outputs[0], b.inputs["Base Color"]); b.inputs["Roughness"].default_value = 0.7
    m["_emit"] = True
    return m, nt, em, b
hm_, nt_, em_, bsdf_ = oak_mat()
hi.data.materials.append(hm_)
bake_img = {k: bpy.data.images.new("head_" + k, TEX, TEX * 3 // 4, alpha=False, float_buffer=(k == "n")) for k in ("c", "n")}
bake_img["n"].colorspace_settings.name = "Non-Color"
lm = bpy.data.materials.new("lo"); lm.use_nodes = True
node = lm.node_tree.nodes.new("ShaderNodeTexImage"); lm.node_tree.nodes.active = node
lo.data.materials.append(lm)

sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = SAMP
bk = sc.render.bake; bk.use_selected_to_active = True; bk.cage_extrusion = 0.6; bk.max_ray_distance = 1.5
bk.margin = 6
bpy.ops.object.select_all(action='DESELECT'); hi.select_set(True); lo.select_set(True)
bpy.context.view_layer.objects.active = lo
def bake(kind, btype, **kw):
    node.image = bake_img[kind]; bk.use_clear = True
    bpy.ops.object.bake(type=btype, **kw); print("BAKED", kind, flush=True)
bake("n", 'NORMAL', normal_space='TANGENT')
out_link = [l for l in nt_.links if l.to_node.type == 'OUTPUT_MATERIAL'][0]
outn = out_link.to_node; nt_.links.remove(out_link); nt_.links.new(em_.outputs[0], outn.inputs["Surface"])
sc.cycles.samples = max(16, SAMP // 2)
bake("c", 'EMIT')
for k, im in bake_img.items():
    im.filepath_raw = os.path.join(OUT, f"head_{k}_full.png"); im.file_format = 'PNG'; im.save()

# the game head, for board_build.py
me = lo.data
json.dump({"v": [list(v.co) for v in me.vertices], "f": [list(p.vertices) for p in me.polygons],
           "uv": [[list(me.uv_layers[0].data[li].uv) for li in p.loop_indices] for p in me.polygons]},
          open(os.path.join(OUT, "head_low.json"), "w"))
print("HEAD", len(me.polygons), "triangles", len(HI), "outline points (full)", len(LO), "(game)")
