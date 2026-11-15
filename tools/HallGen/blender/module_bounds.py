"""House-space bounds of each Hearthfire piece (all pieces share the house origin).
   blender --background --python module_bounds.py -- <pieces.tsv: folder, editorID, dims, formkey, model> <root>"""
import sys, os, bpy, addon_utils, mathutils
addon_utils.enable("io_scene_nifly", default_set=True, persistent=True)
tsv, root = sys.argv[-2], sys.argv[-1]
BS = chr(92)
for line in open(tsv, encoding="utf-8"):
    f = line.rstrip("\n").split("\t"); ed, model = f[1], f[4]
    for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
    try: bpy.ops.import_scene.pynifly(filepath=os.path.join(root, *model.lower().replace("/", BS).split(BS)))
    except Exception as e: print("FAIL", ed); continue
    lo = [1e18] * 3; hi = [-1e18] * 3
    for o in bpy.data.objects:
        if o.type != 'MESH' or "bhk" in o.name or "MultiBound" in o.name: continue
        for v in o.data.vertices:
            p = o.matrix_world @ v.co
            for k in range(3): lo[k] = min(lo[k], p[k]); hi[k] = max(hi[k], p[k])
    if lo[0] > 1e17: print("EMPTY", ed); continue
    print(f"BOUNDS\t{ed}\t{lo[0]:.0f}\t{lo[1]:.0f}\t{lo[2]:.0f}\t{hi[0]:.0f}\t{hi[1]:.0f}\t{hi[2]:.0f}")
