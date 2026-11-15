"""The hall's two load doors, built from vanilla's animated doors (own_copies.py): each must keep its shapes, its collision
on both its nodes and no controller on its root, or it will not open in game. python door_nif_check.py <meshes/AdventurersGuild/Hall2>"""
import os, sys
A = os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "scripts", "addons", "io_scene_nifly"); sys.path.insert(0, A)
from pyn.pynifly import NifFile
NifFile.Load(os.path.join(A, "pyn", "NiflyDLL.dll"))
bad = 0
for f in ("AGH2Csdoubledoorint01.nif", "AGH2Cshouseintdoor02load.nif"):
    p = os.path.join(sys.argv[1], f); n = NifFile(p); r = n.rootNode
    cn = sum(1 for k in n.nodes.values() if getattr(k, "collision_object", None))
    print("DOOR", f, len(n.shapes), "shapes,", cn, "nodes with collision, root controller", getattr(r, "controller", None))
    if len(n.shapes) < 2 or cn < 2 or getattr(r, "controller", None): bad += 1; print("  FAIL DOOR", f)
sys.exit(1 if bad else 0)
