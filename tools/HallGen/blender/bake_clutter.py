"""Headless Blender: the interior's baked clutter (pieces marked bake="name" in interior_gen.py; hall2_interior.json's "bake")
merged into one static per room, AGHall2Bake<Room>.nif, as vanilla's bookcases carry their books in their own mesh
(WinterholdBookCase01): the clutter pass, for the library's 530 shelf books as references (two draw
calls each). Each source mesh is the vanilla piece's own (its shapes, UVs, normals, colours and
shader), set where the layout put it and merged with the others wearing the same textures in the same room: one shape
per texture set and room. (2026-10-28, the performance pass) By room, not by name: each room's static is pivoted inside
it (blender/rooms.py's origin), so the room bounds draw it only with its room. And the books lose the faces no one can
see (the library's 520 books were 282,000 triangles): a face whose every sample (its middle, its corners and the middles
of its edges, each 3% in) meets a book, a shelf, the hall's own shell or anything else of the room's within AG_BOOK_GAP (default
0.5) along its normal (the bottoms on the boards, what truly touches); and a face no eye is in front of (the backs
and page edges against the shelf, the tops above every eye), the eyes being every standing spot (navmesh vertex) of its
room and of the rooms it has portals to (rooms.json), from 30 to 140 over it (a crouch in VR to a tall race). The shelves
and furniture standing within reach are read in for it. AG_BOOK_SURVEY=1 prints how far each book face is from what
covers it, and writes nothing.
Measured on hall2bg's books, rendered against the bake before (seven views of the library and the loft): within 3 cut
52% of the books' triangles and changed 31,000 pixels, the thin side covers that show between books stood 0.3 apart
and turned up to 2.5 degrees; within 0.5, 6% and 2,500 pixels (shading). The rows' look is the books' gaps; pressing
them together is a layout decision, not this script's.
The root is the hall's own template's (the Bryling house, as hall_nif.py's), with no collision: nothing here is to be
touched or to stop anyone.
    blender --background --python bake_clutter.py -- <hall2_interior.json> <data root (meshes/, textures/)> <out dir>
(nav_interior.json and rooms.json are read from beside hall2_interior.json)"""
import sys, os, json, math, bpy, bmesh, addon_utils, mathutils
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
addon_utils.enable("io_scene_nifly", default_set=True, persistent=True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rooms as R
args = sys.argv[sys.argv.index("--") + 1:]
src, root, out = args[:3]
D = json.load(open(src))
BAKE = D.get("bake", {})
if not BAKE: print("BAKE nothing to bake"); sys.exit(0)
SKIP = ("bhk", "MultiBound")
GAP = float(os.environ.get("AG_BOOK_GAP", 0.5))
SURVEY = bool(os.environ.get("AG_BOOK_SURVEY"))
NAV = json.load(open(os.path.join(os.path.dirname(src), "nav_interior.json")))["verts"]
NEXT = {r: {r} for r in R.ROOMS}
for p_ in json.load(open(os.path.join(os.path.dirname(src), "rooms.json")))["portals"]:
    a_, b_ = p_["rooms"]; NEXT[a_].add(b_); NEXT[b_].add(a_)
EYES = {r: [Vector((v[0], v[1], v[2] + h)) for v in NAV if (R.room_of([v[0], v[1], v[2] + 20]) or [None])[0] in NEXT[r]
            for h in (30, 85, 140)] for r in R.ROOMS}


def clear():
    for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes):
        if m.users == 0: bpy.data.meshes.remove(m)


def import_nif(rel):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.pynifly(filepath=os.path.join(root, *rel.split("/")))
    return [o for o in bpy.data.objects if o not in before]


def matkey(mat):
    """the shader a shape wears: its textures and its flags (shapes merge only when the game would draw them alike)"""
    return tuple(sorted((k, str(v)) for k, v in mat.items() if k.startswith(("BSShaderTextureSet_", "BS_", "Shader", "SLSF", "Emissive", "Alpha", "Glossiness", "Specular", "UV_"))))


PARTS = {}
def parts_of(rel):
    """a source piece's shapes and their matrices in the piece's own frame (its root's transform dropped, as the game
    drops it and the render does), read once"""
    if rel in PARTS: return PARTS[rel]
    new = import_nif(rel)
    roots_ = [o for o in new if o.parent is None and o.type == 'EMPTY' and o.name.endswith(":ROOT")]
    R_ = roots_[0].matrix_world.inverted() if len(roots_) == 1 else Matrix.Identity(4)
    PARTS[rel] = []
    for o in new:
        if o.type != 'MESH' or any(s in o.name for s in SKIP) or not o.active_material: continue
        o.active_material.use_fake_user = True
        PARTS[rel].append((o.data, R_ @ o.matrix_world, o.active_material, {k: v for k, v in o.items()}))
        o.data.use_fake_user = True
    for o in new: bpy.data.objects.remove(o, do_unlink=True)
    return PARTS[rel]


def is_book(mat):
    return "\\books\\" in str(mat.get("BSShaderTextureSet_Diffuse", "")).lower().replace("/", "\\")


# the baked pieces by room (each piece's origin is in exactly one: blender/rooms_check.py checks it)
by_room = {}
for name, items in BAKE.items():
    for it in items:
        p = [it["m"][0][3], it["m"][1][3], it["m"][2][3]]
        by_room.setdefault(R.room_of(p)[0], []).append(it)

report = {}
for room, items in sorted(by_room.items()):
    clear(); PARTS.clear()
    # the template's root and its node (hall_nif.py's: vanilla's own building, so the game takes it as it takes the hall)
    tmpl = import_nif("meshes/architecture/solitude/sbryling house.nif")
    rootobj = next(o for o in tmpl if o.get("pynRoot"))
    holder = next(o for o in tmpl if o.type == 'EMPTY' and o.name == "SBryling HouseMesh")
    for o in tmpl:
        if o in (rootobj, holder) or o.name.startswith("BSXFlags"): continue
        bpy.data.objects.remove(o, do_unlink=True)
    rootobj.matrix_world = Matrix.Identity(4)
    groups = {}
    for it in items:
        M = Matrix(it["m"])
        for data, mw, mat, props in parts_of(it["model"]):
            groups.setdefault(matkey(mat), []).append((data, M @ mw, mat, props))
    # a NIF shape's vertex indices are 16-bit: a group over 60000 vertices goes in batches, each its own shape (one more
    # draw call per 60000 vertices: a book's paper alone is about 320)
    batched = {}
    for mk, lst in groups.items():
        b_, n_, k_ = [], 0, 0
        for e in lst:
            nv = len(e[0].vertices)
            if b_ and n_ + nv > 60000:
                batched[(mk, k_)] = b_; b_, n_, k_ = [], 0, k_ + 1
            b_.append(e); n_ += nv
        if b_: batched[(mk, k_)] = b_
    coll_ = rootobj.users_collection[0]
    joined = []
    for gi, ((mk, _), lst) in enumerate(sorted(batched.items(), key=lambda kv: (str(kv[0][0]), kv[0][1]))):
        objs = []
        for k_, (data, M, mat, props) in enumerate(lst):
            o = bpy.data.objects.new("bk", data.copy() if k_ == 0 else data); coll_.objects.link(o)
            o.matrix_world = M; objs.append(o)
        bpy.ops.object.select_all(action='DESELECT')
        for o in objs: o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.object.join()
        o = bpy.context.view_layer.objects.active
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        joined.append((gi, o, lst[0], len(lst)))

    # the books' hidden faces: everything of the room's bake, and the pieces standing within reach of a book, as blockers
    books = [(gi, o) for gi, o, (_, _, mat, _), _ in joined if is_book(mat)]
    cut = 0; total = 0
    if books:
        V, P = [], []
        def add_mesh(me, M):
            b0 = len(V); V.extend(M @ v.co for v in me.vertices); P.extend([b0 + i for i in poly.vertices] for poly in me.polygons)
        for _, o, _, _ in joined: add_mesh(o.data, Matrix.Identity(4))
        lo = [min((o.matrix_world @ Vector(c))[k] for _, o in books for c in o.bound_box) - 64 for k in range(3)]
        hi = [max((o.matrix_world @ Vector(c))[k] for _, o in books for c in o.bound_box) + 64 for k in range(3)]
        for sh in D["shapes"].values():     # (the hall's own shell: the loft's shelving is built into it)
            for f in sh["f"]:
                if any(all(lo[k] <= sh["v"][i][k] <= hi[k] for k in range(3)) for i in f):
                    b0 = len(V); V.extend(Vector(sh["v"][i]) for i in f); P.append(list(range(b0, b0 + len(f))))
        near = [pc for pc in D["pieces"] if all(lo[k] <= pc["pos"][k] <= hi[k] for k in range(3)) and "markers" not in pc["model"]]
        for pc in near:
            M = (Matrix.Translation(pc["pos"]) @ Matrix.Rotation(math.radians(-pc["yaw"]), 4, 'Z')
                 @ Matrix.Rotation(math.radians(-pc.get("rx", 0)), 4, 'X') @ Matrix.Scale(pc["scale"], 4))
            try:
                for data, mw, _, _ in parts_of(pc["model"]): add_mesh(data, M @ mw)
            except Exception as e:   # (a piece Blender cannot read blocks nothing: a face stays rather than going wrongly)
                print("BOOKS cannot read", pc["model"], e)
        T = BVHTree.FromPolygons(V, P, all_triangles=False, epsilon=0.0)
        hist = {}; behind = 0
        eyes = EYES[room]
        for gi, o in books:
            me = o.data
            bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
            gone = []
            for f in bm.faces:
                total += 1
                n = f.normal
                if n.length < 1e-6: continue
                c = f.calc_center_median()
                if not SURVEY and not any((e - c).dot(n) > 0 for e in eyes):
                    gone.append(f); behind += 1; continue
                far = 0.0
                for s in [c] + [c + (v.co - c) * 0.97 for v in f.verts] + [c + ((l.vert.co + l.link_loop_next.vert.co) / 2 - c) * 0.97 for l in f.loops]:
                    h = T.ray_cast(s + n * 0.02, n, 64)
                    if h[0] is None: far = math.inf; break
                    far = max(far, h[3])
                if SURVEY:
                    b_ = next((x for x in (1, 2, 3, 4, 6, 8, 12, 16, 32, 64) if far <= x), "open")
                    hist[b_] = hist.get(b_, 0) + 1
                elif far <= GAP: gone.append(f)
            if gone:
                bmesh.ops.delete(bm, geom=gone, context='FACES_ONLY')
                bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
                cut += len(gone)
            bm.to_mesh(me); bm.free(); me.update()
        if SURVEY: print("BOOK SURVEY", room, "faces by the distance to what covers them (all samples):", hist)
        print("BOOKS", room, "%d of %d book faces hidden (%d no eye is in front of, the rest covered within %g), %d pieces round them read"
              % (cut, total, behind, GAP, len(near)))

    # each shape as a NIF shape, its points relative to the room's origin
    org = Vector(R.origin(room))
    shapes = []
    for gi, o, (data, M, mat, props), npieces in joined:
        o.data.transform(Matrix.Translation(-org))
        # vanilla's books are skinned (their own skin, for the book's opening) and their shader says so; merged they carry no
        # skin, and a Skinned shader on an unskinned shape draws nothing in game (KNOWLEDGEBASE.local.md): the flag goes
        mat = mat.copy(); fl_ = getattr(mat.pyn_shader, "Shader_Flags_1", "")
        if "SKINNED" in fl_.upper():
            mat.pyn_shader.Shader_Flags_1 = " | ".join(f for f in (x.strip() for x in fl_.split("|")) if f and f.upper() != "SKINNED")
        o.data.materials.clear(); o.data.materials.append(mat)
        for vg in list(o.vertex_groups): o.vertex_groups.remove(vg)      # (and the skin's bone weights with it)
        for md in list(o.modifiers): o.modifiers.remove(md)
        for k, v in props.items():
            if k != "pynNodeName": o[k] = v
        sname = "AGHall2Bake%s_%02d" % (room, gi)
        o.name = sname; o["pynNodeName"] = sname; o.data.name = sname
        o.parent = holder; o.matrix_parent_inverse = Matrix.Identity(4); o.matrix_world = Matrix.Identity(4)
        shapes.append((sname, npieces, len(o.data.polygons), mat.get("BSShaderTextureSet_Diffuse")))
    rootobj["pynNodeName"] = "AGHall2Bake" + room
    rootobj.name = rootobj["pynNodeName"] + ":ROOT"
    dst = os.path.join(out, "AGHall2Bake%s.nif" % room)
    if not SURVEY:
        os.makedirs(out, exist_ok=True)
        bpy.ops.object.select_all(action='SELECT')
        bpy.context.view_layer.objects.active = rootobj
        bpy.ops.export_scene.pynifly(filepath=dst)
    tris = sum(len(p.vertices) - 2 for gi, o, _, _ in joined for p in o.data.polygons)
    for sh in shapes: print("SHAPE", *sh)
    print("BAKED", dst, len(items), "pieces into", len(shapes), "shapes,", tris, "triangles")
    report[room] = {"pieces": len(items), "shapes": len(shapes), "tris": tris, "book_faces_cut": cut}
print("BAKE REPORT", json.dumps(report))
