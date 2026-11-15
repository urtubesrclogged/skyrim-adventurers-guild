"""The guild's own banner (used by the doors and inside as well; the wings'
four at 330 x 90): a still cloth with soft folds and a pointed tail, front and back, on a timber rod with iron finials held
out from the wall by two iron brackets. Made as hall_nif.py makes the hall's meshes (the vanilla Bryling House as the
template, its shapes' shader settings kept, our textures swapped in), so it carries settings the game already draws.
Its frame: the wall's face at y 0, the banner out along -y (STANDOFF to the cloth), the rod's top at z 0, the cloth hanging
to -LENGTH at its tail's point, centred on x. No collision (a banner is hung out of reach or is cloth to brush past).
    blender -b -P banner_nif.py -- <data root> <out.nif> <length> <width> [standoff=20] [<variant>]
With a variant (so the large banners move with the wind like other banners): the cloth and fringe are skinned to a bone grid and a looping SpecialIdle moves
it, the way every moving banner is built (GenericBannerRed01: an MSTT, a skinned shape, one looping sequence, BSX 1); the rod and iron stay still. A variant is its own loop and phases: copies of
one mesh start together and would stay in step for good."""
import sys, os, math, bpy, bmesh, addon_utils, mathutils
addon_utils.enable("io_scene_nifly", default_set=True, persistent=True)
args = sys.argv[sys.argv.index("--") + 1:]
root, dst = args[0], args[1]; LEN, WID = float(args[2]), float(args[3]); SO = float(args[4]) if len(args) > 4 else 20.0
BS = chr(92); OWN = "textures" + BS + "adventurersguild" + BS + "hall2" + BS
TAIL = 30 / 330 * LEN                                      # (the tail's depth, in step with the texture's TAIL_V)
VARIANT = args[5] if len(args) > 5 else None

for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.import_scene.pynifly(filepath=os.path.join(root, "meshes", "architecture", "solitude", "sbryling house.nif"))
objs = list(bpy.data.objects)
rootobj = next(o for o in objs if o.get("pynRoot"))
holder = next(o for o in objs if o.type == 'EMPTY' and o.name == "SBryling HouseMesh")
protos = {}
for o in objs:
    if o.type != 'MESH' or o.name.startswith("bhk") or not o.active_material: continue
    stem = os.path.splitext(os.path.basename(o.active_material.get("BSShaderTextureSet_Diffuse", "").replace(BS, "/")))[0].lower()
    if stem and stem not in protos:
        o.active_material.use_fake_user = True; protos[stem] = (dict(o.items()), o.active_material)
for o in objs:
    if o in (rootobj, holder) or o.name.startswith("BSXFlags"): continue
    bpy.data.objects.remove(o, do_unlink=True)

def retex(mat, stem_path):
    m = mat.copy()
    for k, v in list(m.items()):
        if not (k.startswith("BSShaderTextureSet_") and v): continue
        d, base = v.rsplit(BS, 1); s, ext = os.path.splitext(base)
        suffix = s[s.lower().rfind("_"):].lower() if "_" in s else ""
        if suffix in ("", "_n"): m[k] = stem_path + suffix + ".dds"
        elif suffix == "_g": m[k] = ""
    for n in m.node_tree.nodes:
        if n.type != 'TEX_IMAGE' or not n.image: continue
        s = os.path.splitext(os.path.basename(n.image.filepath))[0]
        suffix = s[s.lower().rfind("_"):].lower() if "_" in s else ""
        if suffix not in ("", "_n"): continue
        path = os.path.join(root, *(stem_path + suffix + ".dds").split(BS))
        if not os.path.exists(path): raise SystemExit("missing texture " + path)
        cs = n.image.colorspace_settings.name; n.image = bpy.data.images.load(path, check_existing=True); n.image.colorspace_settings.name = cs
    return m

made = []
def shape(name, proto, stem_path, faces, uvs):
    """faces: lists of 3 or 4 points; uvs: one (u, v) per corner, or None (a box-ish part's own planar map)"""
    props, mat = protos[proto]; mat = retex(mat, stem_path)
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    for k, f in enumerate(faces):
        try: face = bm.faces.new([bm.verts.new(mathutils.Vector(p)) for p in f])
        except ValueError: continue
        for j, lp in enumerate(face.loops):
            lp[uvl].uv = uvs[k][j] if uvs else ((lp.vert.co.x + lp.vert.co.y) / 64.0, lp.vert.co.z / 64.0)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.01)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:]) if name.endswith(("Rod", "Iron")) else None
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(mat)
    for p in me.polygons: p.use_smooth = True
    o = bpy.data.objects.new(name, me); rootobj.users_collection[0].objects.link(o)
    for k, v in props.items():
        if k not in ("pynNodeName",): o[k] = v
    o["pynNodeName"] = name; o.parent = holder; o.matrix_parent_inverse = mathutils.Matrix.Identity(4)
    made.append((name, len(me.polygons)))

# the cloth: a grid in its own (u, v), the tail's rows narrowing to the point; folds out from the wall, deeper lower down
NU, NV = 10, 30
def cloth_pt(u, v, side):
    k = max(0.0, (v * LEN - (LEN - TAIL)) / TAIL)          # (0 above the tail, 1 at its point)
    uu = 0.5 + (u - 0.5) * (1 - k)
    x = (uu - 0.5) * WID
    fold = 2.4 * math.sin(2 * math.pi * 2.5 * uu + 0.6) * (0.35 + 0.65 * v) + 1.2 * math.sin(2 * math.pi * 5.5 * uu) * v
    y = -SO - fold - side * 0.25                            # (the back 0.5 behind the front)
    z = -2.0 - v * (LEN - 2.0)
    return (x, y, z), (uu, v)
faces, uvs = [], []
for side in (1, -1):                                       # (front, wound to face -y; back, wound to face +y)
    for j in range(NV):
        for i in range(NU):
            q = [cloth_pt(i / NU, j / NV, side), cloth_pt((i + 1) / NU, j / NV, side), cloth_pt((i + 1) / NU, (j + 1) / NV, side), cloth_pt(i / NU, (j + 1) / NV, side)]
            P = [p for p, _ in q]; T = [(t[0], 1 - t[1]) for _, t in q]   # (texture v runs down the cloth; Blender's up)
            if side == 1: P, T = P[::-1], T[::-1]
            faces.append(P); uvs.append(T)
shape("AGH2BannerCloth", "sstuccowall", OWN + "AGH2Banner", faces, uvs)
# (cloth has no sheen: vanilla's banner cloth, WRCHBanner01, carries the plaster's flags but SPECULAR; matched in render, the
# plaster's specular washed the red to rose)
cm_ = bpy.data.objects["AGH2BannerCloth"].active_material
cm_.pyn_shader.Shader_Flags_1 = "RECEIVE_SHADOWS | CAST_SHADOWS | OWN_EMIT | REMAPPABLE_TEXTURES | ZBUFFER_TEST"

# the fringe (the plain cloth looked bare beside the Companions banner's embellishments): along both of
# the tail's edges, hanging FRINGE straight down, vanilla's own fringe as the Companions' banner hangs it under its hem
# (WRCarpetDetails01's strip u 0..0.081, its strands along u: the woven edge at 0.081 above, their ends at 0 below; one
# strip 40 along v, as theirs), cut out by its alpha as theirs is (NiAlphaProperty 4844, threshold 128), front and back
FRINGE = 12.0
# (a gap showed at the bottom of the fringe: the strip's woven edge is clear for its first part, so the strands began short of the hem. Measured: where the
# strip's alpha passes its threshold across most of its length, and the quad begins there)
FU = 0.0898   # (WRCarpetDetails01: the strip is solid across most of its length up to here: models_check.py reads the mesh against the texture)
def edge_pts(left):
    v0 = 1 - TAIL / LEN
    return [cloth_pt(0.0 if left else 1.0, v0 + (1 - v0) * k / 8, 1)[0] for k in range(9)]
ff, fu = [], []
for left in (True, False):
    P = edge_pts(left); along = 0.0
    for a, b in zip(P, P[1:]):
        L_ = math.dist(a, b); v_a, v_b = along / 40.0, (along + L_) / 40.0; along += L_
        a2, b2 = (a[0], a[1], a[2] - FRINGE), (b[0], b[1], b[2] - FRINGE)
        q = [a, b, b2, a2]; t = [(FU, v_a), (FU, v_b), (0.0, v_b), (0.0, v_a)]
        qb = [(p[0], p[1] + 0.3, p[2]) for p in q][::-1]          # (its back 0.3 behind: at one place the merge kept one face)
        ff += [q, qb]; fu += [t, t[::-1]]
# (its material is vanilla's own fringe's, with its alpha node: the exporter writes a NiAlphaProperty only from one; taken
# from the Companions' banner, its SKINNED flag off, as this mesh is still)
before_ = set(bpy.data.objects)
bpy.ops.import_scene.pynifly(filepath=os.path.join(root, "meshes", "architecture", "whiterun", "wrclutter", "wrjovaskrbanner02.nif"))
src_ = next(o for o in bpy.data.objects if o not in before_ and o.type == 'MESH' and o.active_material
            and "wrcarpetdetails01" in o.active_material.get("BSShaderTextureSet_Diffuse", "").lower())
fm_ = src_.active_material.copy(); fm_.use_fake_user = True
for o in [o for o in bpy.data.objects if o not in before_]: bpy.data.objects.remove(o, do_unlink=True)
props_ = protos["sstuccowall"][0]
fm_.pyn_shader.Shader_Flags_1 = "RECEIVE_SHADOWS | CAST_SHADOWS | OWN_EMIT | REMAPPABLE_TEXTURES | ZBUFFER_TEST"
protos["_fringe"] = (props_, fm_)
_retex = retex; retex = lambda mat, stem: mat if mat is fm_ else _retex(mat, stem)
shape("AGH2BannerFringe", "_fringe", "", ff, fu)
retex = _retex

# the rod: an octagonal bar along x over the cloth's head, 1.6 round, the width and 5 each side; iron finials at its ends
def bar(a, b, r, n=8):
    a, b = mathutils.Vector(a), mathutils.Vector(b); d = (b - a).normalized()
    s = d.cross(mathutils.Vector((0, 0, 1)) if abs(d.z) < 0.9 else mathutils.Vector((1, 0, 0))).normalized(); t = d.cross(s)
    ring = lambda c: [c + (s * math.cos(2 * math.pi * k / n) + t * math.sin(2 * math.pi * k / n)) * r for k in range(n)]
    A, B = ring(a), ring(b); F = [[A[k], A[(k + 1) % n], B[(k + 1) % n], B[k]] for k in range(n)]
    return F + [A[::-1], B]
rod = bar((-WID / 2 - 5, -SO, 0), (WID / 2 + 5, -SO, 0), 1.6)
shape("AGH2BannerRod", "swoodbeam01", OWN + "AGH2Beam", rod, None)
iron = []
for sx in (-1, 1):
    c = WID / 2 + 5
    iron += bar((sx * c, -SO, 0), (sx * (c + 3.5), -SO, 0), 2.6, 6)                         # (a finial's collar)
    iron += bar((sx * (c + 3.5), -SO, 0), (sx * (c + 6), -SO, 0), 1.4, 6)                     # (its knob)
    bx = sx * (WID / 2 - 9)                                                                   # (the brackets, inside the cloth's edges)
    iron += bar((bx, 0, 7), (bx, -SO, 1.8), 1.0, 6)                                           # (an arm from the wall to the rod)
    iron += bar((bx, -SO + 1.8, 1.8), (bx, -SO - 1.8, 1.8), 2.0, 6)                           # (its hook under the rod)
    iron += [[(bx - 3, 0.01, 2), (bx + 3, 0.01, 2), (bx + 3, 0.01, 12), (bx - 3, 0.01, 12)]]   # (its plate on the wall)
shape("AGH2BannerIron", "strims01", OWN + "AGH2XMetal", iron, None)

ROWS = 6                                                   # (the head's row is held still by the rod, the rest move, left and right apart so the cloth can twist)
if VARIANT:
    arm_ = bpy.data.armatures.new("AGH2BannerRig"); arma = bpy.data.objects.new("AGH2BannerRig", arm_); rootobj.users_collection[0].objects.link(arma); arma.parent = rootobj
    bpy.context.view_layer.objects.active = arma; bpy.ops.object.mode_set(mode='EDIT')
    BONES = {"BannerHead": (0, -SO, 0)}
    for r_ in range(1, ROWS + 1):
        for k_, sx_ in (("L", -1), ("R", 1)): BONES[f"Banner{r_}{k_}"] = (sx_ * WID / 2, -SO, -r_ / ROWS * LEN)
    for n_, p_ in BONES.items():
        # (along +y, so each node's rotation is identity, as its keys' one held rotation says. The cloth hung unnaturally with tails along +z: turned every node 90 degrees, the keys
        # turned all but the unkeyed head back, and the cloth stepped at the head's row. Blender's pose never showed it: it does not read the skin the game reads)
        b_ = arm_.edit_bones.new(n_); b_.head = p_; b_.tail = (p_[0], p_[1] + 5, p_[2])
    bpy.ops.object.mode_set(mode='OBJECT')
    def rig(o):
        for n_ in BONES: o.vertex_groups.new(name=n_)
        for v_ in o.data.vertices:
            t_ = min(1.0, max(0.0, -v_.co.z / LEN)) * ROWS; i_ = min(int(t_), ROWS - 1); w_ = t_ - i_; u_ = min(1.0, max(0.0, (v_.co.x + WID / 2) / WID))
            for r_, wr_ in ((i_, 1 - w_), (i_ + 1, w_)):
                if wr_ <= 0: continue
                for n_, wn_ in (("BannerHead", wr_),) if r_ == 0 else ((f"Banner{r_}L", wr_ * (1 - u_)), (f"Banner{r_}R", wr_ * u_)):
                    if wn_ > 0: o.vertex_groups[n_].add([v_.index], wn_, 'REPLACE')
        o.parent = rootobj; o.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        o.modifiers.new("Armature", 'ARMATURE').object = arma
        o.active_material.pyn_shader.Shader_Flags_1 += " | SKINNED"
    for n_ in ("AGH2BannerCloth", "AGH2BannerFringe"): rig(bpy.data.objects[n_])
    for o_ in [o for o in bpy.data.objects if o.name.startswith("BSXFlags")]: bpy.data.objects.remove(o_, do_unlink=True)
rootobj["pynNodeName"] = os.path.splitext(os.path.basename(dst))[0]; rootobj.name = rootobj["pynNodeName"] + ":ROOT"
os.makedirs(os.path.dirname(dst), exist_ok=True)
bpy.ops.object.select_all(action='SELECT'); bpy.context.view_layer.objects.active = rootobj
bpy.ops.export_scene.pynifly(filepath=dst)
if VARIANT:
    import random
    from io_scene_nifly.pyn import pynifly as PN
    rv_ = random.Random("banner " + VARIANT)
    T_ = {"A": 11.0, "B": 12.5, "C": 13.5, "D": 15.0, "E": 9.5, "F": 10.5}[VARIANT]; FPS = 20; N_ = int(T_ * FPS)
    w_ = [2 * math.pi * n_ / T_ for n_ in (3, 5, 2, 4)]; ph_ = [rv_.uniform(0, 2 * math.pi) for _ in range(5)]
    A_, B_, C_ = 0.08 * LEN, 0.02 * LEN, 0.025 * LEN      # (out from the wall, the twist, along the wall: vanilla's calm banners travel about 7.5% of their length at the tail)
    def offset(r_, sx_, t_):
        f_ = r_ / ROWS; env_ = f_ ** 1.4; lag_ = -2 * math.pi * 0.5 * f_  # (it grows down the cloth, and the wave runs down it)
        y_ = -A_ * env_ * (0.55 + 0.45 * (0.7 * math.sin(w_[0] * t_ + lag_ + ph_[0]) + 0.3 * math.sin(w_[1] * t_ + 1.7 * lag_ + ph_[1])))  # (out from the wall only: never through it)
        y_ += sx_ * B_ * env_ * math.sin(w_[2] * t_ + lag_ + ph_[2])
        x_ = C_ * env_ * math.sin(w_[3] * t_ + 0.6 * lag_ + ph_[3])
        return x_, y_, (x_ * x_ + y_ * y_) / (2 * f_ * LEN)  # (a cloth that swings out rises, its length kept)
    nif = PN.NifFile(dst); rn_ = nif.rootNode
    PN.BSXFlags.New(nif, name="BSX", flags=1, parent=rn_)  # (Animated, and nothing else, as vanilla's banners: the template's hall flags went with its object, above)
    # (built as their New() does, with vanilla's own start and stop: PyNifly's default is a double's limit, written as infinity)
    FM_ = 3.4028234663852886e+38
    p_ = PN.NiMultiTargetTransformController.getbuf(); p_.flags = 108; p_.targetID = rn_.id; p_.startTime = FM_; p_.stopTime = -FM_
    mt_ = nif.add_block(None, p_, None); mt_._target = rn_
    p_ = PN.NiControllerManager.getbuf(); p_.targetID = rn_.id; p_.nextControllerID = mt_.id; p_.flags = PN.TimeControllerFlags(cycle_type=PN.CycleType.CLAMP).flags; p_.startTime = FM_; p_.stopTime = -FM_
    cm_ = nif.add_block(None, p_, rn_); cm_._controller_manager_sequences = {}
    pal_ = PN.NiDefaultAVObjectPalette.New(nif, rn_, parent=cm_)
    cs_ = PN.NiControllerSequence.New(file=nif, name="SpecialIdle", accum_root_name=nif.rootName, start_time=0.0, stop_time=T_, cycle_type=PN.CycleType.LOOP, frequency=1.0, parent=cm_)
    PN.NiTextKeyExtraData.New(file=nif, keys=((0.0, "start"), (T_, "end")), parent=cs_)
    FMAX = -3.4028234663852886e+38
    for n_, p_ in BONES.items():
        if n_ == "BannerHead": continue
        node_ = nif.nodes[n_]; base_ = node_.transform.translation; r_ = int(n_[6]); sx_ = -1 if n_[7] == "L" else 1
        ti_ = PN.NiTransformInterpolator.New(file=nif, translation=(FMAX, FMAX, FMAX), rotation=(FMAX, FMAX, FMAX, FMAX), scale=FMAX)
        td_ = PN.NiTransformData.New(file=nif, parent=ti_); td_.add_qrotation_key(0.0, (1.0, 0.0, 0.0, 0.0))  # (one held rotation, as vanilla's bones have)
        for k_ in range(N_ + 1):
            t_ = k_ / FPS * (T_ * FPS / N_) if k_ < N_ else T_
            o_ = offset(r_, sx_, t_ % T_); td_.add_translation_key(t_, (base_[0] + o_[0], base_[1] + o_[1], base_[2] + o_[2]))
        cs_.add_controlled_block(name=n_, interpolator=ti_, controller=mt_, controller_type="NiTransformController")
    for n_ in BONES: pal_.add_object(n_, nif.nodes[n_])
    for s_ in nif.shapes: pal_.add_object(s_.name, s_)
    nif.save()
    print("ANIMATED", VARIANT, T_, "s", N_ + 1, "keys a bone")
for m in made: print("SHAPE", *m)
print("EXPORTED", dst, LEN, "x", WID, "standoff", SO)
