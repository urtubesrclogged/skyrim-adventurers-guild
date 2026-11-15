"""The hall's own roof slate: vanilla sroofslate01 multiplied by a blue-grey, written as DXT1 with a full mip chain.
    python make_roof_dds.py <vanilla sroofslate01.dds> <out.dds> [r g b]"""
import sys, io, struct
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]
tint = tuple(float(v) for v in sys.argv[3:6]) if len(sys.argv) > 5 else (0.55, 0.66, 0.85)
im = Image.open(src).convert("RGB")
im = Image.merge("RGB", [ch.point(lambda v, t=t: int(min(255, v * t + 0.5))) for ch, t in zip(im.split(), tint)])
levels = []
w, h = im.size
cur = im
while True:
    b = io.BytesIO(); cur.save(b, "DDS", pixel_format="DXT1"); data = b.getvalue()
    assert data[:4] == b"DDS ", "not a DDS"
    levels.append(data[128:])                        # the block data after the 128-byte header
    if cur.size == (1, 1) or min(cur.size) <= 1: break
    cur = cur.resize((max(1, cur.size[0] // 2), max(1, cur.size[1] // 2)), Image.LANCZOS)
# header: Pillow's first-level header with the mip count and the MIPMAP/COMPLEX caps added
b = io.BytesIO(); im.save(b, "DDS", pixel_format="DXT1"); hdr = bytearray(b.getvalue()[:128])
flags = struct.unpack_from("<I", hdr, 8)[0] | 0x20000          # DDSD_MIPMAPCOUNT
struct.pack_into("<I", hdr, 8, flags)
struct.pack_into("<I", hdr, 28, len(levels))                    # dwMipMapCount
caps = struct.unpack_from("<I", hdr, 108)[0] | 0x400008         # DDSCAPS_COMPLEX | DDSCAPS_MIPMAP
struct.pack_into("<I", hdr, 108, caps)
open(dst, "wb").write(bytes(hdr) + b"".join(levels))
chk = Image.open(dst); print("wrote", dst, chk.size, chk.mode, "mips", len(levels))
