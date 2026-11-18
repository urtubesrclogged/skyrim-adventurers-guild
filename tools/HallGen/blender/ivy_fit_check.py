"""Does every ivy patch lie on its wall? For each Ivy01-03 the generator placed (hall2_checks.json), rays from its leaves
along its own local +y (the wall side, as vanilla hangs them) into the hall's geometry give how far each leaf stands off
the wall. Vanilla, measured on 29 of Riverwood's (KNOWLEDGEBASE.local.md): half the leaves within about 12, nine in ten
within about 20 on log walls; flat stone shows a gap sooner. A patch fails at a median over 12, a 90th percentile over 22,
or when under 80% of its leaves find a wall behind them, or a median below -2 (hung backwards, its wall side out).
    blender -b -P ivy_fit_check.py -- <export dir> <mesh root (meshes/)>        exit 1 on any failure
    blender -b -P ivy_fit_check.py -- <cell export .json> <mesh root>          an interior cell: its shapes and its ivy, both in its own frame
(the tavern's ivy hung 28 off its wall and 30 under the gallery, neither against the wall nor up against
the bottom of the gallery. This gate had looked at the site's ivy only, and the interior's went out unchecked.)"""
import bpy, sys, os, json, math, addon_utils, logging
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
a = sys.argv[sys.argv.index("--") + 1:]; ex, root = a[0], a[1]
addon_utils.enable("io_scene_nifly", default_set=True, persistent=True)
H = lambda p: Vector((p[1], -p[0], p[2]))                      # layout frame (the parts) -> hall frame
CELL = ex.lower().endswith(".json")                            # an interior cell: one file, one frame (the game's)
if CELL: H = lambda p: Vector(p)
V, F = [], []
for part in ((ex,) if CELL else ("hall2_body", "hall2_roof", "hall2_site_1")):
    d = json.load(open(part if CELL else os.path.join(ex, part + ".json")))
    for key, sh in d["shapes"].items():
        if key.split("@")[0] in ("moss", "mosswall", "wearcrack", "wearstain", "spill", "gpane", "gcoat", "glead"): continue
        for f in sh["f"]:
            b0 = len(V); V += [H(sh["v"][i]) for i in f]; F.append(list(range(b0, b0 + len(f))))
bvh = BVHTree.FromPolygons(V, F)
pieces = [p for p in json.load(open(ex if CELL else os.path.join(ex, "hall2_checks.json")))["pieces"] if "/ivy0" in p["model"].lower()]
cache, bad = {}, 0
for p in pieces:
    rel = p["model"].lower()
    if rel not in cache:
        for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
        logging.disable(logging.CRITICAL)                             # (the importer's missing-texture warnings, a traceback in
        bpy.ops.import_scene.pynifly(filepath=os.path.join(root, *rel.split("/")))   # them, read as a crash to gates_all)
        logging.disable(logging.NOTSET)
        cache[rel] = [(o.matrix_world @ pl.center, pl.area) for o in bpy.data.objects if o.type == 'MESH' and "bhk" not in o.name for pl in o.data.polygons]
    M = Matrix.Translation(p["pos"]) @ Matrix.Rotation(math.radians(-p["yaw"]), 4, 'Z') @ Matrix.Scale(p["scale"], 4)
    d = (M.to_3x3() @ Vector((0, 1, 0))).normalized()
    gaps, tot = [], 0.0
    for c, ar in cache[rel]:
        w = M @ c; tot += ar
        h = bvh.ray_cast(w - d * 40.0, d, 100.0)
        if h[0] is not None: gaps.append(((h[0] - w).dot(d), ar))
    gaps.sort(); cum, pct = 0.0, {}
    for g, ar in gaps:
        cum += ar
        for q in (50, 90):
            if q not in pct and cum >= sum(a_ for _, a_ in gaps) * q / 100: pct[q] = g
    hit = sum(a_ for _, a_ in gaps) / tot if tot else 0
    fail = not gaps or hit < 0.8 or pct.get(50, 99) > 12 or pct.get(90, 99) > 22 or pct.get(50, 0) < -2   # (below 0: hung backwards)
    bad += fail
    print("IVY", os.path.basename(rel), [round(x) for x in p["pos"]], "yaw", p["yaw"], "| leaves on a wall", f"{100 * hit:.0f}%",
          "| off it: median", round(pct.get(50, float("nan")), 1), "90%", round(pct.get(90, float("nan")), 1), "| FAIL" if fail else "| ok")
print("IVY CHECK", len(pieces), "patches,", bad, "failing")
sys.exit(1 if bad else 0)
