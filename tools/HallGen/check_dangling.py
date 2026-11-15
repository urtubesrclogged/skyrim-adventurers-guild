"""The deploy gate for a placed reference whose base is missing (2026-10-27: hall2au-hall2ax crashed the game on loading the
hall's cell, the board session's find: three retired board refs, initially disabled, still pointed at STATs the build no
longer wrote; the engine does not skip a disabled ref with a missing base). Read-only.
    python check_dangling.py <plugin.esp>     exit 1 if any REFR/ACHR/PHZD names a base in this plugin's own index that it lacks"""
import struct, sys, zlib


def subs(b):
    i, big = 0, None
    while i + 6 <= len(b):
        t = b[i:i + 4].decode("latin-1"); n = struct.unpack_from("<H", b, i + 4)[0]; i += 6
        if t == "XXXX": big = struct.unpack_from("<I", b, i)[0]; i += n; continue
        if big is not None: n, big = big, None
        yield t, b[i:i + n]; i += n


def walk(data, a, z, recs):
    while a < z:
        t = data[a:a + 4].decode("latin-1"); size = struct.unpack_from("<I", data, a + 4)[0]
        if t == "GRUP":
            walk(data, a + 24, a + size, recs); a += size; continue
        flags, fid = struct.unpack_from("<II", data, a + 8)
        body = data[a + 24:a + 24 + size]
        if flags & 0x40000: body = zlib.decompress(body[4:])
        recs[fid] = (t, flags, body); a += 24 + size


data = open(sys.argv[1], "rb").read()
hsize = struct.unpack_from("<I", data, 4)[0]
own = sum(1 for t, _ in subs(data[24:24 + hsize]) if t == "MAST")
recs = {}
walk(data, 24 + hsize, len(data), recs)
bad = 0
for fid, (t, flags, body) in sorted(recs.items()):
    if t not in ("REFR", "ACHR", "PHZD"): continue
    d = {}
    for st, sd in subs(body): d.setdefault(st, sd)
    if "NAME" not in d: continue
    b = struct.unpack("<I", d["NAME"][:4])[0]
    if b >> 24 == own and b not in recs:
        bad += 1
        print(f"DANGLING {t} {fid:08X} flags {flags:08X} {d.get('EDID', b'').rstrip(b'\\0').decode('latin-1')} -> base {b:08X} missing")
print(f"DANGLING CHECK {sys.argv[1]}: {len(recs)} records, {bad} placed refs with a missing base")
sys.exit(1 if bad else 0)
