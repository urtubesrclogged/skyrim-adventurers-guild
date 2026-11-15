"""List every shape of the given NIFs with its block type, vertex/triangle count, bounds and texture paths (PyNifly's
reader, outside Blender).
    python nif_textures.py <nif> [...]"""
import sys, os
ADDON = os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "scripts", "addons", "io_scene_nifly")
sys.path.insert(0, ADDON)
from pyn.pynifly import NifFile
NifFile.Load(os.path.join(ADDON, "pyn", "NiflyDLL.dll"))
for p in sys.argv[1:]:
    f = NifFile(p)
    print("##", p)
    for s in f.shapes:
        vs = s.verts
        lo = [min(v[i] for v in vs) for i in range(3)]; hi = [max(v[i] for v in vs) for i in range(3)]
        t = s.transform
        print(f"  {s.name[:34]:34s} {s.blockname:12s} v{len(vs):6d} t{len(s.tris):6d} lo {[round(x) for x in lo]} hi {[round(x) for x in hi]} xf {[round(x,1) for x in t.translation]} s{round(t.scale,2)}")
        for k, v in s.textures.items():
            if v: print(f"      {k:10s} {v}")
