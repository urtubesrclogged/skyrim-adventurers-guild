"""A door's collision body sits on its node with no offset of its own (the Open prompt showed on the floor, away from the door). Better Third Person Selection (on the SE test install) places its prompt from the
collision body: Util::GetBoundingBox takes rigidBody->GetPosition and adds a bhkRigidBodyT's local translation again, and turns it by the local rotation again. The room doors, plain bhkRigidBody with neither,
come out at the door (0 off); vanilla's double door, a bhkRigidBodyT with both, came out 94 from it, in the room near the floor; the basement's pair, translation only, 42 low. So each such body's translation
and rotation move up into its node, and the node's children take the inverse: nothing in the world moves. Only for a mesh with no animation left (strip_door_anim.py): the sequences key those nodes.
    python flatten_door_bodies.py <door.nif>        exit 1 unless every body ends with neither, or the root still has its controller"""
import math, struct, sys
import numpy as np
K = 69.99125; p = sys.argv[1]; b = bytearray(open(p, "rb").read())
i = b.index(b"\n") + 1 + 4 + 1 + 4
nb = struct.unpack_from("<I", b, i)[0]; i += 4; uv2 = struct.unpack_from("<I", b, i)[0]; i += 4
for _ in range(3): i += 1 + b[i]
if uv2 >= 130: i += 1 + b[i]
nt = struct.unpack_from("<H", b, i)[0]; i += 2; T = []
for _ in range(nt):
    l = struct.unpack_from("<I", b, i)[0]; T.append(b[i + 4:i + 4 + l].decode("latin1")); i += 4 + l
idx = struct.unpack_from(f"<{nb}H", b, i); i += 2 * nb
sz = struct.unpack_from(f"<{nb}I", b, i); i += 4 * nb
ns, _ = struct.unpack_from("<II", b, i); i += 8
for _ in range(ns): i += 4 + struct.unpack_from("<I", b, i)[0]
ng = struct.unpack_from("<I", b, i)[0]; i += 4 + 4 * ng
at = []
for k in range(nb): at.append(i); i += sz[k]
kind = lambda k: T[idx[k] & 0x7FFF]
def xform(k):
    """where an AV object's translation starts (name, extra list, controller, flags come first)"""
    o = at[k] + 4; ne = struct.unpack_from("<I", b, o)[0]; return o + 4 + 4 * ne + 4 + 4
def getx(k):
    o = xform(k); return np.array(struct.unpack_from("<3f", b, o)), np.array(struct.unpack_from("<9f", b, o + 12)).reshape(3, 3)
def setx(k, t, R):
    o = xform(k); struct.pack_into("<3f", b, o, *map(float, t)); struct.pack_into("<9f", b, o + 12, *map(float, R.reshape(9)))
def qmat(x, y, z, w):
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
o = at[0] + 4; ne = struct.unpack_from("<I", b, o)[0]; o += 4 + 4 * ne
if struct.unpack_from("<i", b, o)[0] >= 0: sys.exit(f"{p}: the root still has its controller: run strip_door_anim.py first")
moved = 0
for k in range(nb):
    if not kind(k).endswith("Node"): continue
    o = xform(k) + 12 + 36 + 4; col = struct.unpack_from("<i", b, o)[0]; nc = struct.unpack_from("<I", b, o + 4)[0]; ch = struct.unpack_from(f"<{nc}i", b, o + 8)
    if col < 0: continue
    body = struct.unpack_from("<i", b, at[col] + 6)[0]
    if kind(body) != "bhkRigidBodyT": continue
    bt, bq = at[body] + 52, at[body] + 68
    Tb = np.array(struct.unpack_from("<3f", b, bt)) * K; Rb = qmat(*struct.unpack_from("<4f", b, bq))
    tn, Rn = getx(k); setx(k, tn + Rn @ Tb, Rn @ Rb)
    for c in ch:
        if c < 0: continue
        tc, Rc = getx(c); setx(c, Rb.T @ (tc - Tb), Rb.T @ Rc)
    struct.pack_into("<3f", b, bt, 0.0, 0.0, 0.0); struct.pack_into("<4f", b, bq, 0.0, 0.0, 0.0, 1.0); moved += 1
if not moved: sys.exit(f"{p}: no bhkRigidBodyT to flatten")
open(p, "wb").write(b)
print(f"FLAT {p.replace(chr(92), '/').split('/')[-1]}: {moved} collision bodies with no offset of their own")
