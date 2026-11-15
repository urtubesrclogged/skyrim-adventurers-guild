"""Every door's collision body sits on its node with no offset of its own (2026-11-01, the Open prompt on the floor away from the door: flatten_door_bodies.py says why). A mesh that keeps a local translation or
rotation on a body sends Better Third Person Selection's prompt off the door: this is what let the vanilla double door through.
    python door_body_check.py <meshes dir>        FAIL lines, exit 1; a gate that read no door fails too"""
import glob, math, os, struct, sys
d_ = sys.argv[1]; files = sorted(f for f in glob.glob(os.path.join(d_, "*.nif")) if "door" in os.path.basename(f).lower()); bad = 0; bodies = 0
for p in files:
    b = open(p, "rb").read(); i = b.index(b"\n") + 1 + 4 + 1 + 4
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
    for k in range(nb):
        kind = T[idx[k] & 0x7FFF]
        if kind in ("bhkRigidBody", "bhkRigidBodyT"):
            bodies += 1
            t = struct.unpack_from("<3f", b, i + 52); q = struct.unpack_from("<4f", b, i + 68)
            off = math.sqrt(sum(x * x for x in t)) * 69.99; turn = abs(abs(q[3]) - 1)
            if off > 0.5 or turn > 1e-3:
                bad += 1; print(f"FAIL DOOR BODY {os.path.basename(p)} block {k}: {kind} is {off:.1f} off its node, rotation {tuple(round(x, 3) for x in q)}")
        i += sz[k]
if not files or not bodies: print(f"FAIL DOOR BODY: read {len(files)} door meshes, {bodies} bodies in {d_}"); bad += 1
print(f"DOOR BODIES {len(files)} door meshes, {bodies} bodies, {bad} with an offset of their own"); sys.exit(1 if bad else 0)
