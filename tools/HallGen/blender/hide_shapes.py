"""Hides named shapes in a copy of a NIF by its NiAVObject Hidden flag (bit 0), the blocks left in place (2026-11-03, the overmantel's
display: a weapon's world mesh carries its scabbard, Scb, and its blood edges, EdgeBlood*, which the game hides on a weapon and a static
would draw). SSE only (20.2.0.7, BS 100: the flags a uint32 after the name, the extra
data list and the controller). Checked after: every named shape hidden, nothing else changed but those flags.
    python hide_shapes.py <src.nif> <dst.nif> <shape name> [...]        exit 1 unless every name was found and hidden"""
import struct, sys
src, dst, names = sys.argv[1], sys.argv[2], set(sys.argv[3:])
b = bytearray(open(src, "rb").read())
i = b.index(b"\n") + 1
ver, = struct.unpack_from("<I", b, i); i += 4 + 1; uv, = struct.unpack_from("<I", b, i); i += 4
assert ver == 0x14020007 and uv == 12, f"not an SSE NIF: version {ver:#x} user {uv}"
nb = struct.unpack_from("<I", b, i)[0]; i += 4; uv2 = struct.unpack_from("<I", b, i)[0]; i += 4
assert uv2 == 100, f"BS version {uv2}, not SSE's 100"
for _ in range(3): i += 1 + b[i]
nt = struct.unpack_from("<H", b, i)[0]; i += 2; T = []
for _ in range(nt):
    l = struct.unpack_from("<I", b, i)[0]; T.append(b[i + 4:i + 4 + l].decode("latin1")); i += 4 + l
idx = struct.unpack_from(f"<{nb}H", b, i); i += 2 * nb
sz = struct.unpack_from(f"<{nb}I", b, i); i += 4 * nb
ns, _ = struct.unpack_from("<II", b, i); i += 8
S = []
for _ in range(ns):
    l = struct.unpack_from("<I", b, i)[0]; S.append(b[i + 4:i + 4 + l].decode("latin1")); i += 4 + l
ng = struct.unpack_from("<I", b, i)[0]; i += 4 + 4 * ng
done = set()
for k in range(nb):
    at = i; i += sz[k]
    if T[idx[k] & 0x7FFF] not in ("BSTriShape", "BSSubIndexTriShape", "NiTriShape"): continue
    si, = struct.unpack_from("<i", b, at)
    if si < 0 or S[si] not in names: continue
    ne, = struct.unpack_from("<I", b, at + 4); fo = at + 4 + 4 + 4 * ne + 4      # name, extra data count and refs, controller
    fl, = struct.unpack_from("<I", b, fo); struct.pack_into("<I", b, fo, fl | 1); done.add(S[si])
    print(f"{S[si]}: flags {fl:#x} -> {fl | 1:#x}")
assert i == len(b) or len(b) - i < 64, f"read {i} of {len(b)} bytes: the block table did not add up"
missing = names - done
if missing: print("NOT FOUND:", sorted(missing)); sys.exit(1)
open(dst, "wb").write(b); print(f"HIDDEN {len(done)} shapes in {dst}")
