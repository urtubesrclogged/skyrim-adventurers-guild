"""pool_seat_nif.py's check, by PyNifly's own reader (an independent read of what Blender wrote): BSX flags 130 (as vanilla's
CommonBench01 and CommonChair01), vanilla's three sit markers where they were (x -46, 0, 46, 33.84 up, heading 0), entered
from the front, the ends from their open side too (bits 1 front, 2 behind, 4 right, 8 left, 16 up), and a collision object
on the static layer whose shape is a compressed mesh. Fails on any difference.
    python pool_seat_check.py <seat.nif>"""
import sys, os
sys.path.insert(0, os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "scripts", "addons", "io_scene_nifly"))
from pyn.pynifly import NifFile
ENTRY = {-46: 1 | 8, 0: 1, 46: 1 | 4}
n = NifFile(sys.argv[1]); got = {"coll": []}
for e in n.rootNode.extra_data():
    if e.blockname == "BSXFlags": got["bsx"] = e.properties.integerData
    if e.blockname == "BSFurnitureMarkerNode":
        got["seats"] = sorted((round(m.offset[0]), round(m.offset[2], 1), round(m.heading, 3), m.entry_points) for m in e.furniture_markers)
for nm, nd in n.nodes.items():
    co = nd.collision_object
    if co:
        sh = co.body.shape; ch = getattr(sh, "child", None)
        got["coll"].append((co.body.properties.collisionFilter_layer, sh.blockname, ch and ch.blockname))
want = {"bsx": 130, "seats": sorted((x, 33.8, 0.0, ENTRY[x]) for x in ENTRY), "coll": [(1, "bhkMoppBvTreeShape", "bhkCompressedMeshShape")]}
bad = {k: (got.get(k), v) for k, v in want.items() if got.get(k) != v}
print("POOL SEAT", got, "OK" if not bad else f"MISMATCH (got, wanted): {bad}")
sys.exit(1 if bad else 0)
