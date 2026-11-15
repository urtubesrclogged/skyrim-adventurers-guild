"""Every NAVM in a plugin read as the game reads it, field by field, to the last byte (2026-10-28: hall2be's navmesh crashed
the game at the main menu, in its navmesh reader, which ran off the end of the record. The grid's per-cell counts were
written as uint16 since hall2ba, where the game reads uint32; nothing checked the bytes, and hall2ba-bd loaded by luck).

The layout, version 12 as Skyrim.esm's are (all 3000 of its first navmeshes parse exactly so; `--calibrate` re-checks):
version, CRC, parent (worldspace, then cell or grid), vertices (count, 3 floats each), triangles (count, 16 bytes each:
3 vertex and 3 edge int16, flags, cover flags), edge links (count, 10 bytes each), door triangles (count, 10 each),
cover triangles (count, uint16 each), the grid: divisor, max distance x and y, min and max (6 floats), then divisor
squared cells, each a uint32 count and that many uint16 triangle indices. Every index is also checked in range.
    python check_navmesh.py <plugin.esp> [--calibrate <Skyrim.esm>]"""
import sys, struct, zlib


def navms(path, limit=None):
    d = open(path, "rb").read(); out = []
    def walk(o, end):
        while o < end and (limit is None or len(out) < limit):
            sig = d[o:o + 4]; size = struct.unpack_from("<I", d, o + 4)[0]
            if sig == b"GRUP":
                label = d[o + 8:o + 12]; gt = struct.unpack_from("<i", d, o + 12)[0]
                if gt == 0 and label not in (b"CELL", b"WRLD"): o += size; continue
                walk(o + 24, o + size); o += size; continue
            if sig == b"NAVM":
                flags, fid = struct.unpack_from("<II", d, o + 8); body = d[o + 24:o + 24 + size]
                if flags & 0x40000: body = zlib.decompress(body[4:])
                i = 0; big = None
                while i < len(body):
                    t = body[i:i + 4]; n = struct.unpack_from("<H", body, i + 4)[0]
                    if t == b"XXXX": big = struct.unpack_from("<I", body, i + 6)[0]; i += 10; continue
                    ln = big if big is not None else n
                    if t == b"NVNM": out.append((fid, body[i + 6:i + 6 + ln]))
                    i += 6 + ln; big = None
            o += 24 + size
    walk(0, len(d))
    return out


def check(nv):
    """problems with one NVNM, [] when the game would read it whole"""
    try:
        p = 16
        nV = struct.unpack_from("<I", nv, p)[0]; p += 4 + nV * 12
        nT = struct.unpack_from("<I", nv, p)[0]; p += 4
        tris = [struct.unpack_from("<hhhhhhHH", nv, p + k * 16) for k in range(nT)]; p += nT * 16
        nE = struct.unpack_from("<I", nv, p)[0]; p += 4 + nE * 10
        nD = struct.unpack_from("<I", nv, p)[0]
        doors = [struct.unpack_from("<h", nv, p + 4 + k * 10)[0] for k in range(nD)]; p += 4 + nD * 10
        nC = struct.unpack_from("<I", nv, p)[0]; p += 4 + nC * 2
        div = struct.unpack_from("<I", nv, p)[0]; p += 4 + 8 + 24
        bad_grid = 0
        for _ in range(div * div):
            cnt = struct.unpack_from("<I", nv, p)[0]; p += 4
            if p + 2 * cnt > len(nv): return [f"grid cell count {cnt} runs past the record"]
            bad_grid += sum(1 for i in struct.unpack_from("<%dH" % cnt, nv, p) if i >= nT); p += 2 * cnt
    except struct.error as e:
        return [f"runs off the record: {e}"]
    probs = []
    if p != len(nv): probs.append(f"{len(nv) - p} bytes left over after the grid (the layout is off)")
    if any(not 0 <= v < nV for t in tris for v in t[:3]): probs.append("a triangle names a vertex out of range")
    # (an edge whose flag bit is set, 1 2 4 for edges 0-1 1-2 2-0, names an entry of the edge links, another navmesh's)
    if any(not ((0 <= t[3 + e] < nE) if t[6] & (1 << e) else (-1 <= t[3 + e] < nT)) for t in tris for e in range(3)):
        probs.append("an edge links a triangle out of range")
    if any(not 0 <= dt < nT for dt in doors): probs.append("a door triangle out of range")
    if bad_grid: probs.append(f"{bad_grid} grid entries out of range")
    return probs


if __name__ == "__main__":
    if "--calibrate" in sys.argv:
        ref = navms(sys.argv[sys.argv.index("--calibrate") + 1], limit=3000)
        bad = sum(1 for _, nv in ref if check(nv))
        print(f"CALIBRATION {len(ref)} vanilla navmeshes, {bad} the reader disagrees with")
        if bad: sys.exit(2)
    ms = navms(sys.argv[1]); bad = 0
    for fid, nv in ms:
        pr = check(nv); bad += bool(pr)
        if pr: print(f"  BAD NAVM {fid:08X}: " + "; ".join(pr))
    print(f"NAVMESH CHECK {sys.argv[1].split('/')[-1]}: {len(ms)} navmeshes, {bad} the game would misread")
    sys.exit(1 if bad else 0)
