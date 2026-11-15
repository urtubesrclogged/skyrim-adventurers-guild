"""A vanilla mesh copied under our own path, its textures pointed at our own (the built-in pieces: the doors, bar kit, fireplace and hatches should look the same on every
install). Doors carry controllers and sequences a Blender export would lose or reorder, so this changes only the paths in the BSShaderTextureSet blocks and the header's block sizes that
follow from them: every other byte of the file is the original's.
    python retarget_nif.py <vanilla .nif> <out .nif> <map .json>         the map: {"old texture path, lower case": "new path"}; a path the map does not name stays, and is reported
Exit 1 if nothing was retargeted, or the copy does not read back with the same block count."""
import json, os, struct, sys
src, dst, mp = sys.argv[1:4]
MAP = {k.lower().replace("/", chr(92)): v.replace("/", chr(92)) for k, v in json.load(open(mp, encoding="utf-8")).items()}
b = open(src, "rb").read()
i = b.index(b"\n") + 1; i += 4 + 1 + 4                       # (version, endian, user version)
nb = struct.unpack("<I", b[i:i + 4])[0]; i += 4; uv2 = struct.unpack("<I", b[i:i + 4])[0]; i += 4
for _ in range(3):
    i += 1 + b[i]
if uv2 >= 130: i += 1 + b[i]
if uv2 >= 151: i += 1 + b[i]
nt = struct.unpack("<H", b[i:i + 2])[0]; i += 2; T = []
for _ in range(nt):
    l = struct.unpack("<I", b[i:i + 4])[0]; T.append(b[i + 4:i + 4 + l].decode("latin1")); i += 4 + l
idx = list(struct.unpack(f"<{nb}H", b[i:i + 2 * nb])); i += 2 * nb
sizes_at = i; sizes = list(struct.unpack(f"<{nb}I", b[i:i + 4 * nb])); i += 4 * nb
ns, mx = struct.unpack("<II", b[i:i + 8]); i += 8
for _ in range(ns):
    l = struct.unpack("<I", b[i:i + 4])[0]; i += 4 + l
ng = struct.unpack("<I", b[i:i + 4])[0]; i += 4 + 4 * ng
body = i; out = [b[:body]]; p = body; changed = 0; left = set()
for k in range(nb):
    blk = b[p:p + sizes[k]]; p += sizes[k]
    if T[idx[k] & 0x7FFF] == "BSShaderTextureSet":
        n = struct.unpack("<i", blk[:4])[0]; q = 4; new = [blk[:4]]
        for _ in range(n):
            l = struct.unpack("<I", blk[q:q + 4])[0]; t = blk[q + 4:q + 4 + l].decode("latin1"); q += 4 + l
            key = t.lower().replace("/", chr(92))
            r = MAP.get(key)
            if r is None and key.startswith("textures" + chr(92)): r = MAP.get(key[9:])
            if r is None: r = MAP.get(key.split(chr(92))[-1])      # (by the file's own name: a mesh's folder may differ from the texture's)
            if r is not None and r != t: changed += 1; t = r
            elif t: left.add(t)
            e = t.encode("latin1"); new.append(struct.pack("<I", len(e)) + e)
        blk = b"".join(new); sizes[k] = len(blk)
    out.append(blk)
out.append(b[p:])
head = bytearray(out[0]); head[sizes_at:sizes_at + 4 * nb] = struct.pack(f"<{nb}I", *sizes)
os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
open(dst, "wb").write(bytes(head) + b"".join(out[1:]))
print(f"RETARGET {os.path.basename(src)} -> {os.path.basename(dst)}: {nb} blocks, {changed} paths changed; left as they were: {sorted(left)[:6]}")
sys.exit(0 if changed else 1)
