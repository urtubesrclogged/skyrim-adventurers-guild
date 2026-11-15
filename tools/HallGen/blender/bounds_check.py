"""The bounds gate (in hall2bl, walls went missing on turning the head and through open doors).
The engine leaves a shape undrawn when its bounding sphere is out of view, so every shape's stored sphere (in its own frame)
must hold all of its vertices. Read with PyNifly's own reader, every shape of every NIF given.
    python bounds_check.py <nif> [...]
Exits 1 when a sphere misses a vertex by more than 1."""
import sys, os, math
sys.path.insert(0, os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "scripts", "addons", "io_scene_nifly"))
from pyn.pynifly import NifFile
NifFile.Load(os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "scripts", "addons", "io_scene_nifly", "pyn", "NiflyDLL.dll"))
bad = shapes = 0
for p in sys.argv[1:]:
    f = NifFile(p)
    for s in f.shapes:
        shapes += 1
        c, r = list(s.properties.boundingSphereCenter), s.properties.boundingSphereRadius
        far = max(math.dist(c, v) for v in s.verts) if s.verts else 0.0
        if far > r + 1:
            bad += 1
            lo = [min(v[k] for v in s.verts) for k in range(3)]; hi = [max(v[k] for v in s.verts) for k in range(3)]
            print(f"  BAD {os.path.basename(p)} {s.name}: sphere at {[round(x) for x in c]} r {r:.0f}, a vertex {far:.0f} away; "
                  f"verts {[round(x) for x in lo]}..{[round(x) for x in hi]}")
print(f"BOUNDS {len(sys.argv) - 1} NIFs, {shapes} shapes, {bad} whose sphere misses vertices")
sys.exit(1 if bad else 0)
