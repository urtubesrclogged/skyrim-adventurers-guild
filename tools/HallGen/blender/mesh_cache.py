"""Rebuild a mesh only when what it is made from changed (the build took too long). By content, never by date: the mesh's export, the script that builds it,
the arguments, and every file in the render root's own texture folder, whose hall_nif.py may read. A hit touches the mesh, so fresh_check.py passes it: the hash has just proved it belongs to this
export. A miss costs a rebuild; a false hit would be the stale mesh that kept the windows' outside from the game, so anything in doubt goes in the key.
    python mesh_cache.py hit <keys dir> <out.nif> <texture dir> <inputs and arguments...>    exit 0: the mesh is current, skip it; 1: build it
    python mesh_cache.py put <keys dir> <out.nif> <texture dir> <inputs and arguments...>    after a good build"""
import glob, hashlib, json, os, sys
mode, keys, out, tex = sys.argv[1:5]; rest = sys.argv[5:]
def add(h, p):
    with open(p, "rb") as f:
        while (b := f.read(1 << 20)): h.update(b)
h = hashlib.blake2b(digest_size=20)
for a in rest:
    h.update(a.encode())
    if os.path.isfile(a): add(h, a)
if os.environ.get("MESH_TEX_FP"):   # (build_hall.sh: the folder's print, by content, made once per build; hashing it for every mesh
    h.update(os.environ["MESH_TEX_FP"].encode())   # was most of the meshes' time when nothing had changed)
else:
    for p in sorted(glob.glob(os.path.join(tex, "*"))):
        if os.path.isfile(p): h.update(os.path.basename(p).lower().encode()); add(h, p)
key = h.hexdigest(); name = os.path.basename(out).lower(); os.makedirs(keys, exist_ok=True); k = os.path.join(keys, name + ".key")
if mode == "put":
    open(k, "w").write(key + "\n" + hashlib.blake2b(open(out, "rb").read(), digest_size=20).hexdigest()); sys.exit(0)
try:
    was, mesh = open(k).read().split()
    ok = os.path.isfile(out) and was == key and hashlib.blake2b(open(out, "rb").read(), digest_size=20).hexdigest() == mesh
except (OSError, ValueError): ok = False
if ok: os.utime(out)
sys.exit(0 if ok else 1)
