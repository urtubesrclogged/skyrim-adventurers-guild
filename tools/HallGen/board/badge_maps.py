"""Headless Blender: the six rank badges as the board's plates wear them, from the mod's own badge model
(tools/blender_crest.py, the Guild Card's art): each rendered straight on, in colour and as its surface normals, so a flat
plate on the board can carry the badge's relief in a normal map.
    blender -b --factory-startup -P badge_maps.py -- <AG tools dir> <out dir> [size 512] [samples 64]
-> <out>/badge_<R>_c.png (colour, alpha = the badge's outline), badge_<R>_n.png (tangent-space normal: x right, y up,
   z out of the plate; Blender's +Y convention)"""
import sys, os, bpy
a = sys.argv[sys.argv.index("--") + 1:]
TOOLS, OUT = a[0], os.path.abspath(a[1])
SIZE = int(a[2]) if len(a) > 2 else 512
SAMP = int(a[3]) if len(a) > 3 else 64
os.makedirs(OUT, exist_ok=True)
src = open(os.path.join(TOOLS, "blender_crest.py"), encoding="utf-8").read()
src = src[:src.rstrip().rfind("main()")]                        # everything but the final call
sys.argv = ["blender", "--", OUT, str(SIZE), str(SAMP)]
ns = {"__file__": os.path.join(TOOLS, "blender_crest.py"), "__name__": "badge_maps"}
exec(compile(src, "blender_crest.py", "exec"), ns)
rm = ns["load_ring"](); ns["RING"] = rm; rm.SIZE, rm.SAMPLES = SIZE, SAMP
sc = rm.reset(); rm.build_ring(); rm.lights_and_camera(sc)
slots = ns["record_bronze_slots"]()
sc.render.resolution_x = sc.render.resolution_y = SIZE
sc.render.film_transparent = True

nrm = bpy.data.materials.new("normal_out"); nrm.use_nodes = True
nt = nrm.node_tree; nt.nodes.clear()
geo = nt.nodes.new("ShaderNodeNewGeometry"); vm = nt.nodes.new("ShaderNodeVectorMath"); vm.operation = 'MULTIPLY_ADD'
vm.inputs[1].default_value = (0.5, 0.5, 0.5); vm.inputs[2].default_value = (0.5, 0.5, 0.5)
em = nt.nodes.new("ShaderNodeEmission"); out = nt.nodes.new("ShaderNodeOutputMaterial")
nt.links.new(geo.outputs["Normal"], vm.inputs[0]); nt.links.new(vm.outputs[0], em.inputs[0]); nt.links.new(em.outputs[0], out.inputs[0])

def shot(path, ortho, override=None):
    cam = sc.camera; cam.data.ortho_scale = ortho; cam.location = (0.0, 0.0, 20.0)
    vl = sc.view_layers[0]; vl.material_override = override
    vt = sc.view_settings.view_transform; look = sc.view_settings.look
    if override is not None:
        sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'
        sc.render.image_settings.color_depth = '16'
    sc.render.filepath = path; bpy.ops.render.render(write_still=True)
    sc.view_settings.view_transform = vt; sc.view_settings.look = look; vl.material_override = None
    sc.render.image_settings.color_depth = '8'

for rank in "EDCBAS":
    m, mp, mf = ns["metal_pair"](rank)
    ns["recast"](slots, m, mp)
    props = ns["medallion"](rm, rank, m, mp, mf)
    ortho = 2 * (rm.R + 1.55)                                    # the framing the Guild Card's badges use
    shot(os.path.join(OUT, f"badge_{rank}_c.png"), ortho)
    shot(os.path.join(OUT, f"badge_{rank}_n.png"), ortho, nrm)
    for ob in props: bpy.data.objects.remove(ob)
    print("BADGE", rank)
