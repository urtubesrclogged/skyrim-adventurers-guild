"""A door that teleports never needs to swing (the Open prompt sat in the wrong place and an invisible wall stood at the doors; the front doors now as the basement's). Those doors are
animated meshes: each leaf and its collision hang on a node the Open and Close sequences turn, and vanilla's own animated cell doors can stick in their open state (UESP, Skyrim:Glitches). So: the root's
controller goes, as Get On With It does for every vanilla load door (NifSkope, Block > Remove on the NiControllerManager: 115,000 users, Skyrim VR among them). The leaves and their collision stay in the
bind pose. Only the root's controller reference changes; no block moves, so the file stays the same size.
    python strip_door_anim.py <door.nif>        exit 1 unless the root held a NiControllerManager"""
import struct, sys
p = sys.argv[1]; b = bytearray(open(p, "rb").read())
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
if not kind(0).endswith("Node"): sys.exit(f"{p}: the root is a {kind(0)}")
o = at[0] + 4; ne = struct.unpack_from("<I", b, o)[0]; o += 4 + 4 * ne
c = struct.unpack_from("<i", b, o)[0]
if c < 0 or kind(c) != "NiControllerManager": sys.exit(f"{p}: the root has no NiControllerManager (controller {c})")
struct.pack_into("<i", b, o, -1)
open(p, "wb").write(b)
print(f"STRIP {p.replace(chr(92), '/').split('/')[-1]}: NiControllerManager off the root, {nb} blocks kept")
