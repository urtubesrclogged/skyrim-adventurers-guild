"""Which of the landscape's own objects pass through the hall: every vanilla or modded reference near the site that the
hide pass leaves standing (rocks, logs, trees, plants) is loaded with its real mesh and tested against the hall's
geometry (BVH overlap). A log through the overlook's walls, lupines through the back stair's treads (2026-10-24) are
exactly what it reports. The hide pass is replicated as guildhall_gen.py renders it (the export's clear boxes, big
statics only in the everything boxes, what stands on a hidden ledge).
    blender -b -P landscape_clip_check.py -- <data root> <export dir> <map objects JSON> <allforms.tsv> <x,y,floor,yaw> <mapdata.json>
Prints hall-frame positions (x across the front, y negative in front, z from the floor). Exit 1 if anything clips."""
import bpy, sys, os, json, math, struct, base64, addon_utils
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
a = sys.argv[sys.argv.index("--") + 1:]
root, exdir, rawp, formsp, site_s, mapp = a[:6]
SITE = [float(v) for v in site_s.split(",")]
_M = json.load(open(mapp)); _X0, _Y0 = _M["box"][0] * 4096, _M["box"][1] * 4096; _NX, _NY = _M["nx"], _M["ny"]
_H = struct.unpack("<%dh" % (_NX * _NY), base64.b64decode(_M["heights"]))
_A = math.radians(SITE[3]); _C, _S = math.cos(_A), math.sin(_A)
def hall_to_world(hx, hy):
    lx, ly = -hy, hx
    return SITE[0] + lx * _C + ly * _S, SITE[1] - lx * _S + ly * _C
def world_to_hall(wx, wy):
    dx, dy = wx - SITE[0], wy - SITE[1]; lx, ly = dx * _C - dy * _S, dx * _S + dy * _C
    return ly, -lx
def ground(hx, hy):
    wx, wy = hall_to_world(hx, hy)
    fx, fy = (wx - _X0) / 128, (wy - _Y0) / 128; i, j = int(fx), int(fy); u, v = fx - i, fy - j
    i = min(max(i, 0), _NX - 2); j = min(max(j, 0), _NY - 2); h = lambda p, q: _H[q * _NX + p]
    return h(i, j) * (1 - u) * (1 - v) + h(i + 1, j) * u * (1 - v) + h(i, j + 1) * (1 - u) * v + h(i + 1, j + 1) * u * v - SITE[2]

# the hall: every face of the export but the decals, in the hall frame
V, F, FK = [], [], []
for fn in ("hall2_body.json", "hall2_roof.json", "hall2_site_1.json"):
    j = json.load(open(os.path.join(exdir, fn)))
    for key, sh in j["shapes"].items():
        if key in ("moss", "mosswall", "wearcrack", "wearstain", "spill"): continue
        for f in sh["f"]:
            F.append(list(range(len(V), len(V) + len(f)))); FK.append(key)
            V += [Vector((sh["v"][i][1], -sh["v"][i][0], sh["v"][i][2])) for i in f]
hall = BVHTree.FromPolygons(V, F)
site = json.load(open(os.path.join(exdir, "hall2_site_1.json")))
CLEAR = [(c[2], c[3], -c[1], -c[0]) for c in site["clear"] if c[4] == 0]         # layout (lx0, lx1, ly0, ly1) -> hall
CLEAR_ALL = [(c[2], c[3], -c[1], -c[0]) for c in site["clear"] if c[4] == 1]

# the landscape's references, and the hide pass as the generator replays it
R = 2600
bigt = ("pine", "alder", "beech", "aspen", "birch", "oak", "maple", "willow", "fir", "spruce")
smallt = ("shrub", "stump", "fern", "clover", "thistle", "thicket", "flora", "typha", "dwarf", "low", "vine", "ivy")
LAND = ("landscape\\rocks", "landscape\\boulder", "landscape\\trees", "landscape\\dirtcliffs")
models = {}
for line in open(formsp, encoding="utf-8", errors="replace"):
    f = line.rstrip("\n").split("\t")
    if len(f) > 3 and f[3]: models.setdefault(f[0].lower(), (f[3], [float(v) for v in f[1].split("x")] if "x" in f[1] else None))
inbox = lambda x, y, boxes: any(c0 <= x <= c1 and d0 <= y <= d1 for c0, c1, d0, d1 in boxes)
objs = []
for ob in json.load(open(rawp))["objects"]:
    hx, hy = world_to_hall(ob[0], ob[1])
    if abs(hx) > R or abs(hy) > R or ob[7] not in ("Tree", "Static", "MoveableStatic"): continue
    ed = str(ob[8]); el = ed.lower()
    if any(k in el for k in ("marker", "fx", "dyndolod", "lod")): continue
    m = models.get(el, (None, None))
    kind = "tree" if ob[7] == "Tree" and any(b in el for b in bigt) and not any(t in el for t in smallt) else ("plant" if ob[7] == "Tree" else "static")
    landish = kind != "static" or (m[0] and any(k in m[0].lower() for k in LAND))
    objs.append({"hx": hx, "hy": hy, "z": ob[2] - SITE[2], "rot": ob[3], "tilt": (ob[10], ob[11]) if len(ob) > 11 else (0, 0),
                 "w": ob[4], "l": ob[5], "ed": ed, "kind": kind, "model": m[0], "bd": m[1], "land": landish, "src": ob[9]})
hid = set()
for k, o in enumerate(objs):
    if not o["land"]: continue
    big = o["kind"] == "static" and max(o["w"], o["l"]) > 1000
    if inbox(o["hx"], o["hy"], CLEAR_ALL) or (not big and inbox(o["hx"], o["hy"], CLEAR)): hid.add(k)
deps = set()
for k in list(hid):
    o = objs[k]
    if o["kind"] != "static": continue
    rad = max(o["w"], o["l"]) / 2
    for q, d in enumerate(objs):
        if q in hid or q == k: continue
        if d["kind"] == "static" and max(d["w"], d["l"]) > 600: continue
        if math.hypot(d["hx"] - o["hx"], d["hy"] - o["hy"]) <= rad and d["z"] > ground(d["hx"], d["hy"]) + 40: deps.add(q)
hid |= deps
print("HIDE replayed:", len(hid), "hidden of", len(objs), "objects within", R)

addon_utils.enable("io_scene_nifly", default_set=True, persistent=True)
e0 = Vector(world_to_hall(SITE[0], SITE[1]) + (0,)); ex = Vector(world_to_hall(SITE[0] + 1, SITE[1]) + (0,)) - e0
rot = math.atan2(ex.y, ex.x)
hmin = Vector((min(v.x for v in V), min(v.y for v in V), min(v.z for v in V))); hmax = Vector((max(v.x for v in V), max(v.y for v in V), max(v.z for v in V)))
cache, hits, tested = {}, [], 0
for k, o in enumerate(objs):
    if k in hid or not o["model"]: continue
    r_ = max(o["w"], o["l"]) * 0.75 + 50                 # far from the hall's box: cannot touch it
    if not (hmin.x - r_ < o["hx"] < hmax.x + r_ and hmin.y - r_ < o["hy"] < hmax.y + r_): continue
    rel = o["model"].lower().replace("\\", "/"); rel = rel if rel.startswith("meshes/") else "meshes/" + rel
    if rel not in cache:
        path = os.path.join(root, *rel.split("/"))
        if not os.path.exists(path): cache[rel] = None
        else:
            before = set(bpy.data.objects)
            try: bpy.ops.import_scene.pynifly(filepath=path)
            except Exception as e: print("IMPORT FAILED", rel, e); cache[rel] = None; continue
            new = [x for x in bpy.data.objects if x not in before]
            tri = []
            for x in new:
                if x.type != 'MESH' or "bhk" in x.name or "MultiBound" in x.name: continue
                me = x.data; me.calc_loop_triangles(); mw = x.matrix_world.copy()
                tri += [[mw @ me.vertices[i].co for i in t.vertices] for t in me.loop_triangles]
            for x in new: bpy.data.objects.remove(x, do_unlink=True)
            cache[rel] = tri
    tri = cache[rel]
    if not tri: continue
    sc = 1.0
    if o["bd"] and max(o["bd"]) > 0 and max(o["w"], o["l"]) > 0: sc = max(o["w"], o["l"]) / max(o["bd"][:2])
    if not 0.2 < sc < 6: sc = 1.0
    M = (Matrix.Translation((o["hx"], o["hy"], o["z"])) @ Matrix.Rotation(rot, 4, 'Z') @ Matrix.Rotation(-o["tilt"][0], 4, 'X')
         @ Matrix.Rotation(-o["tilt"][1], 4, 'Y') @ Matrix.Rotation(-o["rot"], 4, 'Z') @ Matrix.Scale(sc, 4))
    PV = [M @ p for t in tri for p in t]
    ob_bvh = BVHTree.FromPolygons(PV, [[3 * i, 3 * i + 1, 3 * i + 2] for i in range(len(tri))])
    tested += 1
    pairs = hall.overlap(ob_bvh)
    if pairs:
        pts = [sum((V[i] for i in F[hf]), Vector()) / len(F[hf]) for hf, _ in pairs]
        keys = sorted(set(FK[hf] for hf, _ in pairs))
        lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        hits.append((len(pairs), o["kind"], o["ed"], (round(o["hx"]), round(o["hy"]), round(o["z"])), keys,
                     ((round(lo.x), round(hi.x)), (round(lo.y), round(hi.y)), (round(lo.z), round(hi.z))), o["src"]))
hits.sort(key=lambda h: -h[0])
print(tested, "standing references near the hall tested:", len(hits), "pass through it")
for h in hits:
    print("  CLIP", h[1], h[2], "at", h[3], "| hall faces hit:", h[0], h[4], "| where (x, y, z ranges):", h[5], "|", h[6])
sys.exit(1 if hits else 0)
