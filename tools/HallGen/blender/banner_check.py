"""Every moving banner holds what a vanilla moving banner holds (2026-11-02: the wings' banners were still; blender/banner_nif.py rigs them, GenericBannerRed01 the pattern): BSX 1, one looping
SpecialIdle with start and end text keys, a manager and multi-target controller with vanilla's flags and times, every keyed bone a target and in the palette, each bone's last key its first (no
jump at the loop), the cloth skinned and flagged so, never nearer the wall than the banner's clearance, and no two banners on one loop length (copies start together and stay in step for good).
    python banner_check.py <meshes dir>        FAIL lines, exit 1; a gate that read no banner fails too"""
import glob, os, struct, sys
CLEAR = 8.0                                                 # (the wall at y 0 and its timbers 10 out sit behind the cloth, which hangs 20 out)
def rd(p):
    b = open(p, "rb").read(); i = b.index(b"\n") + 1 + 4 + 1 + 4
    nb = struct.unpack_from("<I", b, i)[0]; i += 4; uv2 = struct.unpack_from("<I", b, i)[0]; i += 4
    for _ in range(3): i += 1 + b[i]
    nt = struct.unpack_from("<H", b, i)[0]; i += 2; T = []
    for _ in range(nt):
        l = struct.unpack_from("<I", b, i)[0]; T.append(b[i + 4:i + 4 + l].decode("latin1")); i += 4 + l
    idx = struct.unpack_from(f"<{nb}H", b, i); i += 2 * nb
    sz = struct.unpack_from(f"<{nb}I", b, i); i += 4 * nb
    ns, _ = struct.unpack_from("<II", b, i); i += 8; St = []
    for _ in range(ns):
        l = struct.unpack_from("<I", b, i)[0]; St.append(b[i + 4:i + 4 + l].decode("latin1")); i += 4 + l
    ng = struct.unpack_from("<I", b, i)[0]; i += 4 + 4 * ng; B = []
    for k in range(nb): B.append((T[idx[k] & 0x7FFF], b[i:i + sz[k]])); i += sz[k]
    return B, St
def node_rotation(B, St, name):
    """an NiNode's nine rotation floats, by its name"""
    for t, d in B:
        if t != "NiNode" or St[struct.unpack_from("<i", d, 0)[0]] != name: continue
        ne = struct.unpack_from("<I", d, 4)[0]; o = 8 + 4 * ne + 4 + 4 + 12
        return struct.unpack_from("<9f", d, o)
def held_rotation(B, ip):
    """the quaternion of a bone's one rotation key, w x y z"""
    dd = B[struct.unpack_from("<i", B[ip][1], 32)[0]][1]
    return struct.unpack_from("<4f", dd, 12) if struct.unpack_from("<I", dd, 0)[0] else None
def keys(B, ip):
    d = B[ip][1]; dd = B[struct.unpack_from("<i", d, 32)[0]][1]; o = 0
    nr = struct.unpack_from("<I", dd, o)[0]; o += 4
    if nr: o += 4 + nr * 20                                 # (one held rotation, linear: time and a quaternion)
    n = struct.unpack_from("<I", dd, o)[0]; o += 4
    if not n: return []
    o += 4; return [struct.unpack_from("<4f", dd, o + j * 16) for j in range(n)]
files = sorted(f for f in glob.glob(os.path.join(sys.argv[1], "*.nif")) if os.path.basename(f).lower().startswith("aghall2banner") and os.path.basename(f).lower()[:-4][-1] in "abcdef")
bad = 0; lengths = {}
def fail(p, m):
    global bad; bad += 1; print(f"FAIL BANNER {os.path.basename(p)}: {m}")
for p in files:
    B, St = rd(p); ty = [t for t, _ in B]
    bsx = [struct.unpack_from("<I", d, 4)[0] for t, d in B if t == "BSXFlags"]
    if bsx != [1]: fail(p, f"BSX {bsx}, not one block of 1")
    for t, want in (("NiControllerManager", 76), ("NiMultiTargetTransformController", 108)):
        if ty.count(t) != 1: fail(p, f"{ty.count(t)} {t}"); continue
        d = B[ty.index(t)][1]; fl = struct.unpack_from("<H", d, 4)[0]; st, sp = struct.unpack_from("<2f", d, 14)
        if fl != want or st != 3.4028234663852886e+38 or sp != -3.4028234663852886e+38: fail(p, f"{t} flags {fl}, times {st} {sp}")
    if ty.count("NiControllerSequence") != 1: fail(p, "not one sequence"); continue
    d = B[ty.index("NiControllerSequence")][1]; nm = St[struct.unpack_from("<i", d, 0)[0]]; n = struct.unpack_from("<I", d, 4)[0]; o = 12; L = []
    for _ in range(n):
        ip = struct.unpack_from("<i", d, o)[0]; o += 9; nd = struct.unpack_from("<i", d, o)[0]; o += 20; L.append((St[nd], ip))
    w_, tk, cyc, fr, st, sp = struct.unpack_from("<fiIfff", d, o)
    if nm != "SpecialIdle" or cyc != 0 or st != 0 or sp <= 0 or fr != 1: fail(p, f"sequence {nm}, cycle {cyc}, frequency {fr}, {st}..{sp}")
    if tk < 0 or B[tk][0] != "NiTextKeyExtraData": fail(p, "no text keys")
    else:
        dk = B[tk][1]; names = [St[struct.unpack_from("<i", dk, 12 + 8 * j)[0]] for j in range(struct.unpack_from("<I", dk, 4)[0])]
        if names != ["start", "end"]: fail(p, f"text keys {names}")
    mt = B[ty.index("NiMultiTargetTransformController")][1]; ne = struct.unpack_from("<H", mt, 26)[0]
    if ne != len(L): fail(p, f"{ne} extra targets for {len(L)} keyed bones")
    d = B[ty.index("NiDefaultAVObjectPalette")][1]; c = struct.unpack_from("<I", d, 4)[0]; o = 8; pal = set()
    for _ in range(c):
        l = struct.unpack_from("<I", d, o)[0]; pal.add(d[o + 4:o + 4 + l].decode("latin1")); o += 8 + l
    near = 1e9
    for node, ip in L:
        K = keys(B, ip)
        if node not in pal: fail(p, f"{node} is not in the palette")
        if len(K) < 2: fail(p, f"{node} has {len(K)} keys"); continue
        if K[0][1:] != K[-1][1:] or K[-1][0] != sp: fail(p, f"{node} does not close its loop: {K[0]} to {K[-1]}")
        near = min(near, min(-q[2] for q in K))
        # (the key's rotation must be the node's, or the skin turns about the bone: 2026-11-02, the cloth stepped at the head's row, unseen in Blender's pose)
        R = node_rotation(B, St, node); Q = held_rotation(B, ip)
        if R is None or Q is None or max(abs(a - b) for a, b in zip(R, (1, 0, 0, 0, 1, 0, 0, 0, 1))) > 1e-3 or max(abs(a - b) for a, b in zip(Q, (1, 0, 0, 0))) > 1e-3: fail(p, f"{node}: its node's rotation {R and tuple(round(x, 2) for x in R)} and its key's {Q} are not both identity")
    if near < CLEAR: fail(p, f"a bone comes within {near:.1f} of the wall")
    skinned = [struct.unpack_from("<I", d, 16)[0] & 2 for t, d in B if t == "BSLightingShaderProperty"]
    if ty.count("NiSkinInstance") != 2 or sum(1 for x in skinned if x) != 2: fail(p, f"{ty.count('NiSkinInstance')} skins, {sum(1 for x in skinned if x)} skinned shaders")
    if sp in lengths: fail(p, f"its loop, {sp} s, is {lengths[sp]}'s: they would move in step")
    lengths[sp] = os.path.basename(p)
    print(f"  {os.path.basename(p)}: {len(L)} bones, {sp} s, nearest the wall {near:.1f}")
if not files: print("FAIL BANNER: read no moving banner in", sys.argv[1]); bad += 1
print(f"BANNERS {len(files)} moving, {bad} failures"); sys.exit(1 if bad else 0)
