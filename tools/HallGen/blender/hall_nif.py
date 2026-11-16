"""Headless Blender: one part of the guild hall (JSON from guildhall_gen.py, AG_EXPORT) as a Skyrim SE NIF, made from the
vanilla Bryling House so every shape carries Solitude's own shader settings; the template's collision shell gets our
triangles (none: no collision block). roof=tile dresses the roof in sdragontile01 instead of our slate.
    blender --background --python hall_nif.py -- <part.json> <data root (meshes/, textures/)> <out.nif> [roof=slate|tile]"""
import sys, os, json, math, bpy, bmesh, addon_utils, mathutils
addon_utils.enable("io_scene_nifly", default_set=True, persistent=True)
args = sys.argv[sys.argv.index("--") + 1:]
src, root, dst = args[:3]
ROOF = next((a.split("=", 1)[1] for a in args[3:] if a.startswith("roof=")), "slate")
D = json.load(open(src))
BS = chr(92)
GLASSROOT = os.environ.get("AG_GLASSROOT") or root
SOL = "textures" + BS + "architecture" + BS + "solitude" + BS

# material key -> (the Bryling shape whose shader it borrows, the texture it wears instead; None = that shape's own).
# Since the hall2t build every one is our own copy under
# textures/adventurersguild/hall2 (textures/make_hall_textures.py): a modlist's replacers repaint only vanilla's paths
OWN = "textures" + BS + "adventurersguild" + BS + "hall2" + BS
MAP = {"stone": ("sstonewall", OWN + "AGH2XStone"), "base": ("sstonebase01", OWN + "AGH2XBase"), "trim": ("strims01", OWN + "AGH2XTrim"),
       "stucco": ("sstuccowall", OWN + "AGH2XStucco"), "wood": ("swoodbeam01", OWN + "AGH2XWood"), "win1": ("swindow01", OWN + "AGH2XWin1"),
       "win3": ("swindow01", OWN + "AGH2XWin3"), "win1i": ("swindow01", OWN + "AGH2XWinDim1"), "win3i": ("swindow01", OWN + "AGH2XWinDim3"),
       "win1d": ("swindow01", OWN + "AGH2XWinDay1"), "win3d": ("swindow01", OWN + "AGH2XWinDay3"), "door": ("sdoor01", OWN + "AGH2XDoor"), "steps": ("sstonewall", OWN + "AGH2XSteps"),
       "floor": ("sfloorhouse01", OWN + "AGH2XFloor"), "metal": ("strims01", OWN + "AGH2XMetal"), "pipe": ("strims01", OWN + "AGH2XMetal"),
       # (2026-11-03) the stonework's wear decals, wearcrack and wearstain: moss's decal shader (alpha test, vertex alpha) on their own textures;
       # break, a chip's broken face: the stone's shader on freshly split stone (make_hall_textures' AGH2XStoneBreak)
       "crest3d": ("sstonewall", OWN + "agcrest"), "planks": ("swoodbeam01", OWN + "AGH2XPlanks"), "crest": ("sstonewall", "textures" + BS + "adventurersguild" + BS + "hall" + BS + "aghallcrest"), "moss": ("smoss01", OWN + "AGH2XMoss"), "mosswall": ("smoss01", OWN + "AGH2XMossWall"), "wearcrack": ("smoss01", OWN + "AGH2XWearCrack"), "wearstain": ("smoss01", OWN + "AGH2XWearStain"), "break": ("sstonewall", OWN + "AGH2XStoneBreak"), "tile": ("sdragontile01", OWN + "AGH2XTile"), "dirt": ("sdirt01", OWN + "AGH2XDirt"),
       "roof": ("sroofslate01", OWN + "AGH2XTile") if ROOF == "tile" else ("sroofslate01", "OWN"),
       # the interior's (interior_gen.py): its iron work and the candle stand-ins until the real fittings (phase 7)
       "iron": ("strims01", OWN + "AGH2XMetal"), "candle": ("strims01", OWN + "AGH2XTrim"), "cork": ("swoodbeam01", OWN + "AGH2XWood"), "paper": ("strims01", OWN + "AGH2XTrim")}
if ROOF == "tile": MAP["roof"] = ("sdragontile01", OWN + "AGH2XTile")
# the hall's two paintings of itself (2026-10-27, textures/make_paintings.py): plain lit canvases, the stone's shader
MAP.update({"painting1": ("sstonewall", OWN + "AGH2Painting1"), "painting2": ("sstonewall", OWN + "AGH2Painting2")})
# the interior's cells (hall2_interior, hall2_lookout) wear Solitude's interior kit (the fit-out, palette C
# of the palette study): its plaster, timber, floorboards, trims and slate base; the house floor's own flags; dressed
# column stone for the arches, piers, hearths and the tower's foot. Same shaders: only the textures differ (its meshes
# measured: the Winking Skeever, Proudspire, the Bards College). The windows' and doors' pictures stay as outside.
INT_MAP = {"stucco": ("sstuccowall", SOL + "sstuccowallint01"), "wood": ("swoodbeam01", SOL + "swoodbeam02"),
           "planks": ("swoodbeam01", SOL + "swoodfloor01"), "floor": ("sfloorhouse01", None),
           "stone": ("sstonewall", SOL + "sintcoloumn01"), "trim": ("strims01", SOL + "strims02"),
           "base": ("sstonebase01", SOL + "sslatebaseint01")}
# ... and since the hall2t build our own copies, graded: mostly palette 1 of the palette study, with some of
# palette 2's woods mixed in for variety where it makes sense: Whiterun's plaster, a warmed beam, Whiterun's boards, dressed blocks, carved trims, panelling under the plaster;
# palette 2's nailed beam and boards (wood2, planks2) in the working rooms, the staff rooms' floors, the attic, the lookout
INT_MAP = {"stucco": ("sstuccowall", OWN + "AGH2Plaster"), "wood": ("swoodbeam01", OWN + "AGH2Beam"),
           "planks": ("swoodbeam01", OWN + "AGH2Boards"), "floor": ("sfloorhouse01", OWN + "AGH2Blocks"),
           "stone": ("sstonewall", OWN + "AGH2Blocks"), "trim": ("strims01", OWN + "AGH2Trim"),
           "base": ("sstonebase01", OWN + "AGH2Panel"), "wood2": ("swoodbeam01", OWN + "AGH2Beam2"),
           "planks2": ("swoodbeam01", OWN + "AGH2Planks2"),
           "wainpanel": ("swoodbeam01", OWN + "AGH2Wainscot"), "wainframe": ("swoodbeam01", OWN + "AGH2WainscotFrame")}   # (the tavern's panelling, 2026-11-12: textures/make_wainscot.py)
if any(k in os.path.basename(src).lower() for k in ("hall2_interior", "hall2_lookout", "hall2_basement")) or "palette=interior" in args[3:]:
    MAP.update(INT_MAP)
# the windows (2026-11-01, window_parts.py): the frame on the timber's or the stone's texture; the panes on Glow, as the old pictures; the reflection on vanilla's own recipe, glass01.nif
MAP.update({"wframe": MAP["wood"], "sframe": MAP["stone"], "glead": ("strims01", OWN + "AGH2XMetal")})
IS_IN = any(k in os.path.basename(src).lower() for k in ("hall2_interior", "hall2_lookout", "hall2_basement", "hall2_winday", "hall2_room"))
GLASS = {"gpane": ("swindow01", dict(Diffuse="AGH2GlassWhite", Normal="AGH2GlassFlat_n", Glow="AGH2GlassDay_g")) if IS_IN else ("swindow01", dict(Diffuse="AGH2GlassOut", Normal="AGH2GlassFlat_n", Glow="AGH2GlassOut_g")),   # (outside: the DLL gives the body vanilla's window region: dark by day, warm after dark)
         "gcoat": ("white_em", dict(Diffuse="AGH2GlassCoat", Normal="AGH2GlassDiamond_n", EnvMap="AGH2GlassRoom_e" if IS_IN else "AGH2GlassSky_e"))}
# inside, a highlight can't tell a candle from an unseen fill light: none. Each cube is the light the pane receives by this much: outside that is the sun. The lit panes'
# (the daylight plan) the panes keep EXTERNAL_EMITTANCE: their references carry vanilla's region, FXLightRegionSunlightWhite (Hall2.cs), as vanilla's windows do
GLASS_SET = {"gcoat": dict(Spec_Str=0.0 if IS_IN else 3.0, Env_Map_Scale=0.3 if IS_IN else 0.75)}
OWN_DIFFUSE = "textures" + BS + "adventurersguild" + BS + "hall2" + BS + "agroofslate01.dds"

for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.import_scene.pynifly(filepath=os.path.join(root, "meshes", "architecture", "solitude", "sbryling house.nif"))
objs = list(bpy.data.objects)
rootobj = next(o for o in objs if o.get("pynRoot"))
coll = next((o for o in objs if o.type == 'MESH' and o.name.startswith("bhk")), None)
protos = {}
for o in objs:
    if o.type != 'MESH' or o is coll or not o.active_material: continue
    stem = os.path.splitext(os.path.basename(o.active_material.get("BSShaderTextureSet_Diffuse", "").replace(BS, "/")))[0].lower()
    if stem and stem not in protos:
        o.active_material.use_fake_user = True
        protos[stem] = (dict(o.items()), o.active_material)
print("PROTOS", sorted(protos))
# the node that owns the collision (vanilla hangs it on "SBryling HouseMesh"): kept, and our shapes hang from it
holder = next(o for o in objs if o.type == 'EMPTY' and o.name == "SBryling HouseMesh")
for o in objs:   # everything of the template but its root, that node, the flags and the collision shell
    if o in (rootobj, coll, holder) or o.name.startswith("BSXFlags"): continue
    bpy.data.objects.remove(o, do_unlink=True)

before_ = set(bpy.data.objects)   # vanilla's reflection layer: its shader, with its additive alpha, brought in beside Bryling's
bpy.ops.import_scene.pynifly(filepath=os.path.join(root, "meshes", "_byoh", "clutter", "resources", "glass01.nif"), import_collisions=False, import_animations=False)
glass_ = [o for o in bpy.data.objects if o not in before_]
for o in glass_:
    if o.type == 'MESH' and o.active_material and "white_em" in o.active_material.get("BSShaderTextureSet_Diffuse", "").lower() and "white_em" not in protos:
        o.active_material.use_fake_user = True
        protos["white_em"] = ({k: v for k, v in o.items() if k not in ("pynVertexDesc", "vertexDesc")}, o.active_material)
for o in glass_: bpy.data.objects.remove(o, do_unlink=True)

def glass_mat(mat, tex, key_):
    """the material with each slot on our glass textures, by name: suffixes don't say which is which here"""
    m = mat.copy()
    for k_, v_ in GLASS_SET.get(key_, {}).items(): setattr(m.pyn_shader, k_, v_)
    for slot, stem in tex.items():
        m["BSShaderTextureSet_" + slot] = OWN + stem + ".dds"
    for n in m.node_tree.nodes:
        slot = n.name.split("_")[0] if n.type == 'TEX_IMAGE' else None
        if slot in tex:
            path = os.path.join(GLASSROOT, *(OWN + tex[slot] + ".dds").split(BS)); cs = n.image.colorspace_settings.name if n.image else 'sRGB'
            n.image = bpy.data.images.load(path, check_existing=True); n.image.colorspace_settings.name = cs
    return m

def retex(mat, new_stem_path, own_diffuse=False):
    """the material with its diffuse (and normal, glow) moved to another texture of the same kind"""
    m = mat.copy()
    for k, v in list(m.items()):
        if not (k.startswith("BSShaderTextureSet_") and v): continue
        d, base = v.rsplit(BS, 1); stem, ext = os.path.splitext(base)
        suffix = stem[stem.lower().rfind("_"):] if "_" in stem else ""
        if suffix.lower() not in ("", "_n", "_g"): continue
        if own_diffuse:
            if suffix == "": m[k] = OWN_DIFFUSE
        else:
            m[k] = new_stem_path + suffix.lower() + ".dds"
    for n in m.node_tree.nodes:
        if n.type != 'TEX_IMAGE' or not n.image: continue
        stem = os.path.splitext(os.path.basename(n.image.filepath))[0]
        suffix = stem[stem.lower().rfind("_"):].lower() if "_" in stem else ""
        if suffix not in ("", "_n", "_g"): continue
        if own_diffuse:
            if suffix != "": continue
            rel = OWN_DIFFUSE
        else:
            rel = new_stem_path + suffix + ".dds"
        path = os.path.join(root, *rel.split(BS))
        if not os.path.exists(path): raise SystemExit("missing texture " + path)
        cs = n.image.colorspace_settings.name
        n.image = bpy.data.images.load(path, check_existing=True); n.image.colorspace_settings.name = cs
    return m

made = []
BAD_TRI = []
for name_, sh in D["shapes"].items():
    key = name_.split("@")[0]                   # (the interior's shapes come in cells, "key@i_j_level": 2026-10-26)
    if key in GLASS:
        props, mat = protos[GLASS[key][0]]; mat = glass_mat(mat, GLASS[key][1], key)
    else:
        proto_stem, new = MAP[key]
        props, mat = protos[proto_stem]
        if new == "OWN": mat = retex(mat, None, own_diffuse=True)
        elif new: mat = retex(mat, new)
        if key in ("wearcrack", "wearstain"):          # (2026-11-03) the wear decals blend: moss's shader only tests its alpha, which drew the stain's
            for n_ in mat.node_tree.nodes:                  # soft run and the crack's grime halo solid (their own copy of the material: retex's)
                if "Alpha Blend" in n_.inputs: n_.inputs["Alpha Blend"].default_value = True
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    # float layers: PyNifly writes a layer's linear value, and a byte layer reads back gamma-decoded (0.3 became 0.07);
    # vanilla's colours come in raw as float layers, so these must go out raw the same way
    cl = bm.loops.layers.float_color.new("VERTEX_COLOR") if "c" in sh else None   # the baked age (shade, grime, damp): vanilla's way
    al = bm.loops.layers.float_color.new("VERTEX_ALPHA") if "a" in sh else None   # the moss decal's fade (PyNifly: alpha = its grey)
    vs = [bm.verts.new(v) for v in sh["v"]]
    # each face as a fan from its first corner, as the collision is built (guildhall_gen's dump): bmesh's triangulation
    # filled concave faces across their hollows (an arch's spandrels, a quarter circle's
    # hollow side, came out as straight chords, and the round arches read pointed in game). A face whose fan would turn
    # back on itself (its first corner cannot see all the others) keeps bmesh's triangulation
    def fan_ok(f):
        P = [mathutils.Vector(sh["v"][i]) for i in f]
        n = mathutils.Vector((0, 0, 0))
        for k in range(len(P)): n += P[k - 1].cross(P[k])
        return all((P[k] - P[0]).cross(P[k + 1] - P[0]).dot(n) > -1e-6 for k in range(1, len(P) - 1))
    def add(idx, uvs, cols, alps):
        try: face = bm.faces.new([vs[i] for i in idx])
        except ValueError: return
        for l, uv in zip(face.loops, uvs): l[uvl].uv = uv
        if cols is not None:
            for l, c in zip(face.loops, cols): l[cl] = c
        if alps is not None:
            for l, a_ in zip(face.loops, alps): l[al] = (a_, a_, a_, 1.0)
    def ear_clip(f):
        """triangles (as positions in f) of a flat simple polygon by ear clipping in its own plane: what bmesh got wrong"""
        P = [mathutils.Vector(sh["v"][i]) for i in f]
        n = mathutils.Vector((0, 0, 0))
        for k in range(len(P)): n += P[k - 1].cross(P[k])
        n.normalize(); t = (P[1] - P[0]).normalized(); b = n.cross(t)
        Q = [((p - P[0]).dot(t), (p - P[0]).dot(b)) for p in P]
        cross = lambda o, a, c: (a[0] - o[0]) * (c[1] - o[1]) - (a[1] - o[1]) * (c[0] - o[0])
        idx, tris = list(range(len(Q))), []
        ext_ = max(max(abs(q[0]) for q in Q), max(abs(q[1]) for q in Q), 1.0)
        again_ = True
        while again_ and len(idx) > 3:                                    # corners on a straight edge (a clipped decal has
            again_ = False                                                # them) add no shape and stall the clipping
            for j in range(len(idx)):
                if abs(cross(Q[idx[j - 1]], Q[idx[j]], Q[idx[(j + 1) % len(idx)]])) < 1e-6 * ext_ * ext_:
                    idx.pop(j); again_ = True; break
        while len(idx) > 3:
            for j in range(len(idx)):
                i0, i1, i2 = idx[j - 1], idx[j], idx[(j + 1) % len(idx)]
                if cross(Q[i0], Q[i1], Q[i2]) <= 1e-9: continue           # reflex (or flat): not an ear
                if any(cross(Q[i0], Q[i1], Q[m]) >= 0 and cross(Q[i1], Q[i2], Q[m]) >= 0 and cross(Q[i2], Q[i0], Q[m]) >= 0
                       for m in idx if m not in (i0, i1, i2)): continue
                tris.append((i0, i1, i2)); idx.pop(j); break
            else: return None                                             # not simple: leave it to bmesh
        tris.append(tuple(idx)); return tris
    def flat(f):
        P = [mathutils.Vector(sh["v"][i]) for i in f]
        n = mathutils.Vector((0, 0, 0))
        for k in range(len(P)): n += P[k - 1].cross(P[k])
        return n.length > 1e-9 and max(abs((p - P[0]).dot(n.normalized())) for p in P) < 0.5
    UNTWISTED = 0
    for fi in range(len(sh["f"])):                                        # a twisted (bow-tie) quad: its corners put back
        f = sh["f"][fi]                                                   # in order round its middle (5 moss decals on the
        if len(f) != 4 or not flat(f): continue                           # site, 2026-10-26)
        P = [mathutils.Vector(sh["v"][i]) for i in f]; c_ = sum(P, mathutils.Vector()) / 4
        n = mathutils.Vector((0, 0, 0))
        for k in range(4): n += P[k - 1].cross(P[k])
        if n.length < 1e-9: continue
        nn = n.normalized(); t = (P[0] - c_).normalized(); b2 = nn.cross(t)
        ang = [math.atan2((p - c_).dot(b2), (p - c_).dot(t)) for p in P]
        order = sorted(range(4), key=lambda k: ang[k])
        Q2 = [((p - c_).dot(t), (p - c_).dot(b2)) for p in P]
        x_ = lambda o, a2, c2: (a2[0] - o[0]) * (c2[1] - o[1]) - (a2[1] - o[1]) * (c2[0] - o[0])
        meet = lambda a2, b3, c2, d2: x_(a2, b3, c2) * x_(a2, b3, d2) < 0 and x_(c2, d2, a2) * x_(c2, d2, b3) < 0
        if meet(Q2[0], Q2[1], Q2[2], Q2[3]) or meet(Q2[1], Q2[2], Q2[3], Q2[0]):
            sh["f"][fi] = [f[k] for k in order]; sh["uv"][fi] = [sh["uv"][fi][k] for k in order]
            if cl: sh["c"][fi] = [sh["c"][fi][k] for k in order]
            if al: sh["a"][fi] = [sh["a"][fi][k] for k in order]
            UNTWISTED += 1
    if UNTWISTED: print("UNTWISTED", name_, UNTWISTED, "twisted quads")
    for fi, (f, uvs) in enumerate(zip(sh["f"], sh["uv"])):
        cols = sh["c"][fi] if cl else None; alps = sh["a"][fi] if al else None
        pick = lambda seq, t: seq and [seq[t[0]], seq[t[1]], seq[t[2]]]
        tris = None
        if len(f) > 3:                                                    # (a bent face, which no plane holds: its fan, as
            tris = ear_clip(f) if (flat(f) and not fan_ok(f)) else [(0, k, k + 1) for k in range(1, len(f) - 1)]   # collision)
        if tris:
            for t in tris: add([f[t[0]], f[t[1]], f[t[2]]], pick(uvs, t), pick(cols, t), pick(alps, t))
        else: add(f, uvs, cols, alps)
    if key in ("crest3d", "pipe"):
        # The export gives every face its own corners, so a shape comes out faceted. The crest's normal map was baked
        # against its smooth normals (crest_game.py) and the pipe is round: weld them and shade smooth; the pipe's boxes
        # (hopper, holderbats) keep their corners.
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.001)
        if key == "pipe":
            bm.normal_update()
            bmesh.ops.split_edges(bm, edges=[e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(40)])
        for f in bm.faces: f.smooth = True
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    # the check: the triangles must cover exactly the faces' own area (a wrong triangulation of a concave face adds the
    # hollow it bridges); a shape off by more than 0.1% is named, and the run fails at the end
    def area_of(P):
        # (about its own first corner: mathutils is single precision, and corners ~1800 from the origin summed over a chip's 528
        # small triangles drifted 3 units in 505 (2026-11-03), a false alarm where the triangles were exact)
        P = [p - P[0] for p in P]; n = mathutils.Vector((0, 0, 0))
        for k in range(len(P)): n += P[k - 1].cross(P[k])
        return n.length / 2
    want_ = sum(area_of([mathutils.Vector(sh["v"][i]) for i in f]) if (len(f) == 3 or flat(f)) else
                sum(area_of([mathutils.Vector(sh["v"][f[0]]), mathutils.Vector(sh["v"][f[k]]), mathutils.Vector(sh["v"][f[k + 1]])])
                    for k in range(1, len(f) - 1)) for f in sh["f"])   # (a bent face: its fan's own area)
    got_ = sum(f.calc_area() for f in bm.faces)
    if want_ > 0 and abs(got_ - want_) / want_ > 1e-3:
        print("TRIANGULATION OFF", name_, "faces", round(want_), "triangles", round(got_)); BAD_TRI.append(name_)
    name = "AGHall2_" + name_.replace("@", "_")
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    if "VERTEX_COLOR" in me.color_attributes: me.color_attributes.active_color = me.color_attributes["VERTEX_COLOR"]
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me); rootobj.users_collection[0].objects.link(o)
    for k, v in props.items():
        if k not in ("pynNodeName",): o[k] = v
    o["pynNodeName"] = name
    o.parent = holder; o.matrix_parent_inverse = mathutils.Matrix.Identity(4); o.matrix_world = mathutils.Matrix.Identity(4)
    made.append((name, len(me.polygons), mat.get("BSShaderTextureSet_Diffuse")))
rootobj["pynNodeName"] = os.path.splitext(os.path.basename(dst))[0]
rootobj.name = rootobj["pynNodeName"] + ":ROOT"

if coll is not None:
    if D["coll"]:
        Mi = coll.matrix_world.inverted()
        # each triangle's havok material (the export's coll_mat; footstep and impact sounds come from it, none is silent) goes to
        # PyNifly as a SKY_HAV_MAT_<name> vertex group, which it reads off a face's first corner: so corners are welded only
        # within one material, and a corner is never shared by two
        mats_ = D.get("coll_mat") or []
        if len(mats_) != len(D["coll"]) or not all(mats_): raise SystemExit("COLLISION MATERIAL: the export gives no havok material for every collision triangle")
        for vg_ in list(coll.vertex_groups): coll.vertex_groups.remove(vg_)
        gi_ = {m_: coll.vertex_groups.new(name="SKY_HAV_MAT_" + m_).index for m_ in sorted(set(mats_))}
        cbm = bmesh.new(); dl_ = cbm.verts.layers.deform.verify()
        by_ = {}
        for t, m_ in zip(D["coll"], mats_):
            try: f_ = cbm.faces.new([cbm.verts.new(Mi @ mathutils.Vector(p)) for p in t])
            except ValueError: continue
            for v_ in f_.verts: v_[dl_][gi_[m_]] = 1.0
            by_.setdefault(m_, []).extend(f_.verts)
        for m_, vs_ in by_.items(): bmesh.ops.remove_doubles(cbm, verts=list(set(vs_)), dist=0.5)
        cbm.to_mesh(coll.data); cbm.free(); coll.data.update()
        main_ = max(set(mats_), key=mats_.count)
        coll.pyn_collshape.bhkMaterial = main_                     # the default, for a face PyNifly finds in no group
        print("COLLISION MATERIALS", {m_: mats_.count(m_) for m_ in sorted(set(mats_))})
    else:
        bpy.data.objects.remove(coll, do_unlink=True); coll = None

os.makedirs(os.path.dirname(dst), exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.context.view_layer.objects.active = rootobj
bpy.ops.export_scene.pynifly(filepath=dst)
for m in made: print("SHAPE", *m)
print("EXPORTED", dst, "collision tris", len(coll.data.polygons) if coll else 0)
if BAD_TRI: print("TRIANGULATION CHECK FAILED:", len(BAD_TRI), "shapes"); sys.exit(1)
