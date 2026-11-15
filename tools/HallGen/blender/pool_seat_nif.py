"""The bath's in-water seat (sitting in the water, as other bath mods allow): vanilla's
InvisibleChairPlayerTriple has no collision at all (374 bytes: its markers and BSX only), and a player can only activate what
the crosshair can hit, so it was never usable by the player (the research: "meshes need collision to be activatable and
secondly ... activatable objects need a name"; NPCs reach it by package). This is that chair's mesh with a collision added:
vanilla's three sit markers (46 apart, 33.84 over its origin, facing +y), the hall's proven collision (the Bryling House
template's shell, layer static, as hall_nif.py writes every room) holding one slab on the seat's line, 150 x 32 x 4 from the
seat's height up, so the crosshair finds the ledge's seat and nothing blocks the sitter.
    blender -b -P pool_seat_nif.py -- <data root (meshes/)> <out.nif>
Then pool_seat_check.py reads it back with PyNifly and fails on any difference from what it should hold."""
import sys, os, bpy, bmesh, addon_utils, mathutils
addon_utils.enable("io_scene_nifly", default_set=True, persistent=True)
root, dst = sys.argv[sys.argv.index("--") + 1:][:2]
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.import_scene.pynifly(filepath=os.path.join(root, "meshes", "furniture", "chairinvisibletriple.nif"))
chair = next(o for o in bpy.data.objects if o.get("pynRoot"))
mine = set(bpy.data.objects)
bpy.ops.import_scene.pynifly(filepath=os.path.join(root, "meshes", "architecture", "solitude", "sbryling house.nif"))
theirs = [o for o in bpy.data.objects if o not in mine]
coll = next(o for o in theirs if o.type == 'MESH' and o.name.startswith("bhk"))
holder = next(o for o in theirs if o.type == 'EMPTY' and o.name == "SBryling HouseMesh")
keep, p_ = {holder, coll}, coll.parent                   # the collision mesh and its chain up to the node that owns it
while p_ is not None and p_ is not holder: keep.add(p_); p_ = p_.parent
for o in theirs:
    if o not in keep: bpy.data.objects.remove(o, do_unlink=True)
holder.parent = chair; holder.matrix_world = mathutils.Matrix.Identity(4)
holder["pynNodeName"] = "AGHall2PoolSeatCollision"; holder.name = "AGHall2PoolSeatCollision"
# the slab: along the seats' line (local x -75..75), across it -16..16, from the seat's height (33.84) up 4
Mi = coll.matrix_world.inverted(); bm = bmesh.new()
x0, x1, y0, y1, z0, z1 = -75, 75, -16, 16, 33.84, 37.84
v = [bm.verts.new(Mi @ mathutils.Vector(p)) for p in
     ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
    bm.faces.new([v[i] for i in f])
bmesh.ops.triangulate(bm, faces=bm.faces[:]); bm.to_mesh(coll.data); bm.free(); coll.data.update()
chair["pynNodeName"] = "AGHall2PoolSeat"; chair.name = "AGHall2PoolSeat:ROOT"
# its BSX flags as vanilla's benches and chairs (130: its collision live; the invisible chair's are 0), and its seats entered
# from the front (the pool; the wall is behind), the ends from their open sides too (vanilla's: FRONT|BEHIND, LEFT|UP,
# FRONT|BEHIND|RIGHT). PyNifly's own marker setter fails (it writes through the wrong block), so set here, before export
for o in bpy.data.objects:
    if o.name.startswith("BSXFlags"): o.pyn_bsxflags.value = "HAVOC|ARTICULATED"
    if o.name.startswith("BSFurnitureMarkerNode"):
        x_ = o.location.x
        o.pyn_furniture.entry_points = "FRONT|LEFT" if x_ < -1 else "FRONT|RIGHT" if x_ > 1 else "FRONT"
for o in bpy.data.objects: print("OBJ", o.name, o.type, o.parent and o.parent.name)
os.makedirs(os.path.dirname(dst), exist_ok=True)
bpy.ops.object.select_all(action='SELECT'); bpy.context.view_layer.objects.active = chair
bpy.ops.export_scene.pynifly(filepath=dst)
print("EXPORTED", dst, "collision tris", len(coll.data.polygons))
