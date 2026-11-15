"""Read-only BSA (v104 Skyrim LE/VR, v105 SSE) extractor: pulls the named files, nothing else.
   python bsa.py <out dir> <list file of paths, one per line> <bsa> [<bsa> ...]"""
import struct, sys, os, zlib

def read_index(path):
    f = open(path, 'rb')
    magic, ver, off, flags, nfold, nfile, lfold, lfile, ftypes = struct.unpack('<4sIIIIIIII', f.read(36))
    assert magic == b'BSA\x00' and ver in (104, 105), (path, ver)
    has_names = bool(flags & 2); compressed_default = bool(flags & 4); embed = bool(flags & 0x100)
    folders = []
    for _ in range(nfold):
        if ver == 105:
            h, cnt, _pad, o = struct.unpack('<QIIQ', f.read(24))
        else:
            h, cnt, o = struct.unpack('<QII', f.read(16))
        folders.append(cnt)
    entries = []
    for cnt in folders:
        ln = f.read(1)[0]; name = f.read(ln)[:-1].decode('latin-1')
        for _ in range(cnt):
            h, size, o = struct.unpack('<QII', f.read(16))
            entries.append([name, size, o])
    names = f.read(lfile).split(b'\x00') if has_names else []
    idx = {}
    for e, n in zip(entries, names):
        idx[(e[0] + '\\' + n.decode('latin-1')).lower()] = (e[1], e[2])
    return f, ver, compressed_default, embed, idx

def extract(f, ver, compdef, embed, size, off):
    comp = compdef ^ bool(size & 0x40000000); size &= 0x3FFFFFFF
    f.seek(off); data = f.read(size)
    if embed:
        ln = data[0]; data = data[1 + ln:]
    if not comp: return data
    orig = struct.unpack('<I', data[:4])[0]; body = data[4:]
    if ver == 104: return zlib.decompress(body)
    return lz4_frame(body)

def lz4_block(src, out):
    i, n = 0, len(src)
    while i < n:
        tok = src[i]; i += 1
        lit = tok >> 4
        if lit == 15:
            while True:
                b = src[i]; i += 1; lit += b
                if b != 255: break
        out += src[i:i + lit]; i += lit
        if i >= n: break
        off = src[i] | (src[i + 1] << 8); i += 2
        ml = tok & 15
        if ml == 15:
            while True:
                b = src[i]; i += 1; ml += b
                if b != 255: break
        ml += 4
        start = len(out) - off
        if off >= ml: out += out[start:start + ml]
        else:
            for k in range(ml): out.append(out[start + k])
    return out

def lz4_frame(data):
    assert data[:4] == b'\x04\x22\x4d\x18', 'not an LZ4 frame'
    flg = data[4]; i = 6
    if flg & 0x08: i += 8          # content size
    if flg & 0x01: i += 4          # dictionary id
    i += 1                          # header checksum
    block_checksum = bool(flg & 0x10)
    out = bytearray()
    while True:
        size = struct.unpack_from('<I', data, i)[0]; i += 4
        if size == 0: break
        raw = bool(size & 0x80000000); size &= 0x7FFFFFFF
        blk = data[i:i + size]; i += size
        if raw: out += blk
        else: lz4_block(blk, out)
        if block_checksum: i += 4
    return bytes(out)

if __name__ == '__main__':
    out, listfile, bsas = sys.argv[1], sys.argv[2], sys.argv[3:]
    want = {l.strip().replace('/', '\\').lower() for l in open(listfile) if l.strip()}
    got = 0
    for b in bsas:
        f, ver, cd, em, idx = read_index(b)
        for k in list(want):
            if k in idx:
                data = extract(f, ver, cd, em, *idx[k])
                p = os.path.join(out, *k.split('\\')); os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, 'wb').write(data); want.discard(k); got += 1
    print(f'extracted {got}; not found {len(want)}')
    for k in sorted(want)[:20]: print('  missing', k)
