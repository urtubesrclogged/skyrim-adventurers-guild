"""Headless Blender: an ink sketch of a vanilla creature for the board's notices, the way a guild clerk would draw one.
Two renders of the same framing: Freestyle ink lines on transparency (lines.png), and the plain shading of a white model
under one light (shade.png, with the model's mask in alpha). make_notices.py turns the shading into hatching.
    blender -b -P sketch.py -- <nif> <out dir> <yaw degrees> <pitch degrees> [size 1024]
Yaw turns the camera round the model (0: looking along +y at the model's left side as Skyrim's creatures face +y...);
pitch raises it."""
import sys, os, math, bpy, addon_utils, mathutils
addon_utils.enable("io_scene_nifly", default_set=True, persistent=True)
a = sys.argv[sys.argv.index("--") + 1:]
nif, out, yaw, pitch = a[0], a[1], float(a[2]), float(a[3])
SIZE = int(a[4]) if len(a) > 4 else 1024
os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
try:
    bpy.ops.import_scene.pynifly(filepath=nif)
except Exception as e:
    print("IMPORT WARN", e)
skip = ("bhk", "fx", "eye", "blood", "glow", "collision", "marker")
meshes = []
for o in list(bpy.data.objects):
    if o.type != 'MESH': continue
    if any(k in o.name.lower() for k in skip) or o.hide_render: bpy.data.objects.remove(o, do_unlink=True); continue
    meshes.append(o)
print("SHAPES", [(o.name, len(o.data.polygons)) for o in meshes])
dg = bpy.context.evaluated_depsgraph_get()
lo = mathutils.Vector((1e18,) * 3); hi = -lo
for o in meshes:
    ev = o.evaluated_get(dg); me = ev.to_mesh()
    for v in me.vertices:
        p = o.matrix_world @ v.co
        for k in range(3): lo[k] = min(lo[k], p[k]); hi[k] = max(hi[k], p[k])
    ev.to_mesh_clear()
ctr = (lo + hi) / 2; span = (hi - lo).length
print("BOUNDS", [round(x) for x in lo], [round(x) for x in hi])

cd = bpy.data.cameras.new("cam"); cd.type = 'ORTHO'; cd.clip_start = 1; cd.clip_end = span * 10
cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam); sc.camera = cam
y, p = math.radians(yaw), math.radians(pitch)
d = mathutils.Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p)))
cam.location = ctr + d * span * 2
cam.rotation_euler = (ctr - cam.location).to_track_quat('-Z', 'Y').to_euler()
# frame: the model's extent across the view
bpy.context.view_layer.update()
inv = cam.matrix_world.inverted(); xs, ys = [], []
for o in meshes:
    ev = o.evaluated_get(dg); me = ev.to_mesh()
    for v in list(me.vertices)[::7]:
        q = inv @ (o.matrix_world @ v.co); xs.append(q.x); ys.append(q.y)
    ev.to_mesh_clear()
cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
cam.location = cam.matrix_world @ mathutils.Vector((cx, cy, 0))
cd.ortho_scale = max(max(xs) - min(xs), max(ys) - min(ys)) * 1.06

sc.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in {i.identifier for i in sc.render.bl_rna.properties['engine'].enum_items} else 'BLENDER_EEVEE'
sc.render.resolution_x = sc.render.resolution_y = SIZE
sc.render.film_transparent = True
sc.view_settings.view_transform = 'Standard'
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 0.25
sd = bpy.data.lights.new("sun", 'SUN'); sd.energy = 4.0; sd.angle = math.radians(20)
sun = bpy.data.objects.new("sun", sd); sc.collection.objects.link(sun)
sun.rotation_euler = (d.to_track_quat('Z', 'Y') @ mathutils.Quaternion((0, 1, 0), math.radians(-35)) @ mathutils.Quaternion((1, 0, 0), math.radians(-30))).to_euler()

white = bpy.data.materials.new("white"); white.use_nodes = True
b = white.node_tree.nodes["Principled BSDF"]; b.inputs["Base Color"].default_value = (0.9, 0.9, 0.9, 1); b.inputs["Roughness"].default_value = 1.0
try: b.inputs["Specular IOR Level"].default_value = 0.0
except Exception: pass
hold = bpy.data.materials.new("hold"); hold.use_nodes = True
nt = hold.node_tree; nt.nodes.clear(); ho = nt.nodes.new("ShaderNodeHoldout"); mo = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(ho.outputs[0], mo.inputs["Surface"])

# pass 1: the shading
vl = sc.view_layers[0]
vl.material_override = white; sc.render.use_freestyle = False
sc.render.filepath = os.path.join(out, "shade.png"); bpy.ops.render.render(write_still=True)
# pass 2: the ink, alone
vl.material_override = hold; sc.render.use_freestyle = True
sc.render.line_thickness_mode = 'ABSOLUTE'; sc.render.line_thickness = 1.0
fs = vl.freestyle_settings; fs.crease_angle = math.radians(128); fs.use_smoothness = True
ls = fs.linesets[0] if fs.linesets else fs.linesets.new("ink")
ls.select_by_visibility = True; ls.visibility = 'VISIBLE'
ls.select_silhouette = ls.select_border = ls.select_crease = True; ls.select_contour = True; ls.select_external_contour = True
st = ls.linestyle; st.color = (0.10, 0.065, 0.04); st.thickness = SIZE / 520.0
st.thickness_position = 'CENTER'
tm = st.thickness_modifiers.new("taper", 'ALONG_STROKE'); tm.mapping = 'CURVE'; tm.value_min = 0.25; tm.value_max = 1.4
c = tm.curve.curves[0]; c.points[0].location = (0, 0.15); c.points[1].location = (1, 0.2); c.points.new(0.45, 1.0); tm.curve.update()
cm = st.thickness_modifiers.new("pen", 'CALLIGRAPHY'); cm.orientation = math.radians(60); cm.thickness_min = st.thickness * 0.35; cm.thickness_max = st.thickness * 1.25
st.geometry_modifiers.new("wobble", 'PERLIN_NOISE_1D').amplitude = SIZE / 900.0
st.use_chaining = True; st.chaining = 'PLAIN'
sc.render.filepath = os.path.join(out, "lines.png"); bpy.ops.render.render(write_still=True)
print("SKETCHED", out)
