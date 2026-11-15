"""The chandeliers' extensions: the ring's own chain carried on up (the old extensions neither matched the chain nor lined up with it:
a square iron bar, 4 thick and 2 off the chain's line). ImpChandellierCandle01's chain above its cap is four alpha cards, 66..281 over its origin, on its axis; the same cards at the
length wanted, the texture tiling at the same rate, with the same shader and alpha.
    python chain_nif.py <clean Data root> <out dir> <length> ...      writes AGHall2Chain<length>.nif, its foot at its origin"""
import os, sys, ctypes
import numpy as np
sys.path.insert(0, os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "scripts", "addons", "io_scene_nifly"))
from pyn.pynifly import NifFile
NifFile.Load(os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "scripts", "addons", "io_scene_nifly", "pyn", "NiflyDLL.dll"))
root, out = sys.argv[1:3]; lengths = [int(a) for a in sys.argv[3:]]
src = NifFile(os.path.join(root, "meshes", "clutter", "imperial", "impchandelliercandle01.nif"))
sh = [s for s in src.shapes if s.name.endswith(":12")][0]
v = np.array(sh.verts, float); uv = np.array(sh.uvs, float); nr = np.array(sh.normals, float); f = np.array(sh.tris, int)
keep = sorted({int(i) for t in f for i in t if v[t, 2].max() > 200 and v[t, 2].min() > 60})      # the cards over the cap, not the four chains down to the ring
ids = {o: n for n, o in enumerate(keep)}; tris = [tuple(ids[int(i)] for i in t) for t in f if all(int(i) in ids for i in t)]
lo, hi = v[keep, 2].min(), v[keep, 2].max(); span = hi - lo
assert len(keep) == 16 and len(tris) == 8, (len(keep), len(tris))
for L in lengths:
    name = f"AGHall2Chain{L}"; path = os.path.join(out, name + ".nif")
    V = []; U = []
    for o in keep:
        top = v[o, 2] > (lo + hi) / 2
        V.append((float(v[o, 0]), float(v[o, 1]), float(L if top else 0.0)))
        rate = (1.0 - uv[keep, 0].min()) / span                                                  # (tiles per unit along it, as the ring's)
        U.append((float(1.0 if top else 1.0 - rate * L), float(uv[o, 1])))
    dst = NifFile(); dst.initialize("SKYRIMSE", path, "BSFadeNode", name)
    new = dst.createShapeFromData(name, V, tris, U, [tuple(float(q) for q in nr[o]) for o in keep], use_type=sh.properties.bufType)
    ctypes.memmove(ctypes.byref(new.shader.properties), ctypes.byref(sh.shader.properties), ctypes.sizeof(sh.shader.properties))
    for slot, tx in sh.textures.items():
        if tx: new.set_texture(slot, tx)
    new.save_shader_attributes()
    if sh.has_alpha_property:
        new.has_alpha_property = True
        ctypes.memmove(ctypes.byref(new.alpha_property.properties), ctypes.byref(sh.alpha_property.properties), ctypes.sizeof(sh.alpha_property.properties))
        new.alpha_property.properties.threshold = sh.alpha_property.properties.threshold
        new.save_alpha_property()
    dst.save()
    r = NifFile(path); s_ = r.shapes[0]; w = np.array(s_.verts, float)
    print(name, "verts", len(w), "tris", len(s_.tris), "z", w[:, 2].min(), w[:, 2].max(), "alpha", s_.has_alpha_property, "tex", s_.textures.get("Diffuse", "")[-30:], "u", round(min(u for u, _ in s_.uvs), 2))
