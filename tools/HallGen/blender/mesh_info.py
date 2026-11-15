"""Every placed piece's mesh as the game draws it, for the placement gate (placement_check.py): the box of its geometry in its
own frame (every shape's vertices through its node chain) and, for furniture, its sit markers. Measured from the mesh, not
the record: a record's bounds can describe another pose (SSingleDoorInt01L's are its leaf swung open: x 0..8, y -95..0,
while its mesh hangs closed along +x 0..96; 2026-10-28, the basement's first walk, the bath door).
    python mesh_info.py <part.json> [part.json ...] --data <extracted data root> [--extra <root> ...] --out <mesh_info.json>"""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "scripts", "addons", "io_scene_nifly"))
from pyn.pynifly import NifFile
NifFile.Load(os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "scripts", "addons", "io_scene_nifly", "pyn", "NiflyDLL.dll"))

args = sys.argv[1:]; roots = []; out = None; parts = []
while args:
    a = args.pop(0)
    if a in ("--data", "--extra"): roots.append(args.pop(0))
    elif a == "--out": out = args.pop(0)
    else: parts.append(a)
models = sorted({p["model"].replace("\\", "/").lower() for f in parts for p in json.load(open(f))["pieces"]})


def chain(n):
    """the node's transform to the root: (R 3x3, t, s), applied as R v s + t"""
    R, t, s = [[1, 0, 0], [0, 1, 0], [0, 0, 1]], [0, 0, 0], 1.0
    while n is not None and n.parent is not None:   # (not the root's: the game sets a placed reference's root to the
        x = n.transform; r = x.rotation                 # reference's own transform; KNOWLEDGEBASE.local.md, 2026-10-26)
        # p_parent = r (R v s + t) x.s + x.t
        R = [[sum(r[i][k] * R[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
        t = [sum(r[i][k] * t[k] for k in range(3)) * x.scale + x.translation[i] for i in range(3)]
        s *= x.scale; n = n.parent
    return R, t, s


info = {}
for m in models:
    path = next((os.path.join(r, m) for r in roots if os.path.exists(os.path.join(r, m))), None)
    if not path: info[m] = {"missing": True}; continue
    f = NifFile(path); lo, hi = [1e9] * 3, [-1e9] * 3; ups = []
    for sh in f.shapes:
        R, t, s = chain(sh)
        W = [[sum(R[i][j] * v[j] for j in range(3)) * s + t[i] for i in range(3)] for v in sh.verts]
        for w in W: lo = [min(lo[i], w[i]) for i in range(3)]; hi = [max(hi[i], w[i]) for i in range(3)]
        # (the faces that look up, 2+ across: what a thing can stand on, shelves' inner boards included; the placement gate)
        for tri in sh.tris:
            a, b, c = (W[k] for k in tri)
            n = [(b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]), (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]),
                 (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])]
            L = math.sqrt(sum(x * x for x in n))
            if L > 4 and n[2] / L > 0.9: ups.append([[round(x, 1) for x in p] for p in (a, b, c)])
    marks = []
    ed = f.rootNode.extra_data() if hasattr(f.rootNode, "extra_data") else []
    for x in (ed.values() if isinstance(ed, dict) else ed):
        if hasattr(x, "furniture_markers"):
            for k in x.furniture_markers:
                marks.append([k.offset[0], k.offset[1], k.offset[2], math.degrees(k.heading), k.animation_type_name, k.entry_points])
    # (whether any node carries collision: a player can activate only what the crosshair hits; the placement gate's SEAT)
    coll = any(getattr(nd, "collision_object", None) for nd in f.nodes.values())
    info[m] = {"box": [lo, hi] if lo[0] < 1e8 else None, "markers": marks, "up": ups, "coll": bool(coll)}
json.dump(info, open(out, "w"), indent=0)
print("MESH INFO", len(info), "models;", sum(1 for v in info.values() if v.get("missing")), "missing:",
      [k for k, v in info.items() if v.get("missing")][:20])
