"""The Guild's hanging sign (a guild version of the others, with the same physics as the signs on MGO): vanilla's own SignGeneralGoods01, block for block, so its hinge,
bodies and shapes stay vanilla's and only these change: the board's mass 50, its body flag 1 = respond to wind, the hinge free to swing right round, the board's material wood so arrows stick
(what Skyking Signs changes, read by diffing; nothing of theirs is used), and the textures ours. PyNifly does not carry a hinge through, so the file is edited in place, block sizes rewritten.
    python sign_nif.py <clean data root> <out.nif>"""
import os, struct, sys
root, dst = sys.argv[1:3]
b = open(os.path.join(root, "meshes", "clutter", "signage", "generic", "signgeneralgoods01.nif"), "rb").read()
BS = chr(92); OWN = "textures" + BS + "AdventurersGuild" + BS + "Hall2" + BS + "AGH2SignGuild"
i = b.index(b"\n") + 1 + 4 + 1 + 4; nb = struct.unpack_from("<I", b, i)[0]; i += 4 + 4
for _ in range(3): i += 1 + b[i]
nt = struct.unpack_from("<H", b, i)[0]; i += 2; T = []
for _ in range(nt):
    l = struct.unpack_from("<I", b, i)[0]; T.append(b[i + 4:i + 4 + l].decode("latin1")); i += 4 + l
idx = struct.unpack_from(f"<{nb}H", b, i); i += 2 * nb; size_at = i; sz = list(struct.unpack_from(f"<{nb}I", b, i)); i += 4 * nb
ns, _ = struct.unpack_from("<II", b, i); i += 8
for _ in range(ns): i += 4 + struct.unpack_from("<I", b, i)[0]
ng = struct.unpack_from("<I", b, i)[0]; i += 4 + 4 * ng; start = i
B = []
for k in range(nb): B.append(bytearray(b[i:i + sz[k]])); i += sz[k]
foot = b[i:]; kinds = [T[x & 0x7FFF] for x in idx]; done = {"body": 0, "hinge": 0, "shape": 0, "tex": 0}
for k, t in enumerate(kinds):
    d = B[k]
    if t == "bhkRigidBody" and d[4] == 4:                     # (layer 4, clutter: the board; the bar is layer 1, mass 0)
        m = struct.unpack_from("<f", d, 180)[0]
        if m != 5.0: raise SystemExit(f"the board's mass reads {m}, not 5: not the mesh this was measured on")
        struct.pack_into("<f", d, 180, 50.0); struct.pack_into("<H", d, len(d) - 2, 1); done["body"] += 1
        shape = struct.unpack_from("<i", d, 0)[0]
        if kinds[shape] != "bhkConvexVerticesShape": raise SystemExit("the board's shape is " + kinds[shape])
        struct.pack_into("<I", B[shape], 0, 0x1DD9C611); done["shape"] += 1
    elif t == "bhkLimitedHingeConstraint":
        na = struct.unpack_from("<I", d, 0)[0]; o = 4 + 4 * na + 4 + 128; mn, mx = struct.unpack_from("<2f", d, o)
        if abs(mx - 1.396) > 0.01: raise SystemExit(f"the hinge's limits read {mn} {mx}")
        struct.pack_into("<2f", d, o, -1000000.0, 1000000.0); done["hinge"] += 1
    elif t == "BSShaderTextureSet":
        n = struct.unpack_from("<i", d, 0)[0]; o = 4; S = []
        for _ in range(n):
            l = struct.unpack_from("<I", d, o)[0]; S.append(d[o + 4:o + 4 + l].decode("latin1")); o += 4 + l
        low = [s.lower() for s in S]
        if not any(s.endswith("signgeneralgoods01.dds") for s in low): continue
        S = [OWN + ".dds" if s.lower().endswith("signgeneralgoods01.dds") else OWN + "_n.dds" if s.lower().endswith("signgeneralgoods01_n.dds") else s for s in S]
        B[k] = bytearray(struct.pack("<i", n) + b"".join(struct.pack("<I", len(s)) + s.encode("latin1") for s in S)); done["tex"] += 1
if done["body"] != 1 or done["hinge"] != 1 or done["shape"] != 1 or not done["tex"]: raise SystemExit(f"expected one of each, read {done}")
os.makedirs(os.path.dirname(dst), exist_ok=True)
open(dst, "wb").write(b[:size_at] + struct.pack(f"<{nb}I", *[len(x) for x in B]) + b[size_at + 4 * nb:start] + b"".join(bytes(x) for x in B) + foot)
print("SIGN", dst, done)
