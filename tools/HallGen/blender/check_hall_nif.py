"""Read hall NIFs back with PyNifly's own reader (not Blender's import): blocks, shapes, textures, vertex counts, collision.
    python check_hall_nif.py <nif> [...]"""
import sys, os
sys.path.insert(0, os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "scripts", "addons", "io_scene_nifly"))
from pyn.pynifly import NifFile
from pyn import pynifly
dll = os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "scripts", "addons", "io_scene_nifly", "pyn", "NiflyDLL.dll")
NifFile.Load(dll)
bad = 0
for p in sys.argv[1:]:
    f = NifFile(p)
    print("##", os.path.basename(p), "game", f.game, "root", f.rootName, type(f.rootNode).__name__ if hasattr(f, "rootNode") else "")
    for s in f.shapes:
        tex = s.textures
        nv, nt = len(s.verts), len(s.tris)
        uv = s.uvs; uvr = (min(u for u, v in uv), max(u for u, v in uv), min(v for u, v in uv), max(v for u, v in uv)) if uv else None
        print(f"   {s.name:22s} {s.blockname:12s} verts {nv:6d} tris {nt:6d} diffuse {tex.get('Diffuse')} normal {tex.get('Normal')} glow {tex.get('Glow', '')} uv {tuple(round(x, 2) for x in uvr) if uvr else None}")
        if nv > 65535 or nt == 0 or not tex.get("Diffuse"): bad += 1; print("   !! bad shape")
    co = f.rootNode.collision_object if hasattr(f.rootNode, "collision_object") else None
    print("   collision:", type(co).__name__ if co else None, (co.body.shape.blockname if co and co.body and co.body.shape else ""))
print("BAD", bad)
