"""The crest's maps as the game reads them (crest_game.py bakes them as PNG):
  AGCrest.dds    the colour (crest_c.png: the cast colour partly lit as the approved renders show it), DXT1
  AGCrest_n.dds  the normal map in the game's convention (green down, as vanilla's: the generator's preview flips vanilla's
                 the same way back) with the specular mask in alpha, DXT5
Both with a full mip chain; the normals renormalised at every level.
    python crest_dds.py <bake dir> <out dir>"""
import sys, io, os, struct
import numpy as np
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]
os.makedirs(dst, exist_ok=True)

def write_dds(levels, fmt, path):
    blocks = []
    for im in levels:
        b = io.BytesIO(); im.save(b, "DDS", pixel_format=fmt); data = b.getvalue()
        assert data[:4] == b"DDS " and data[84:88] == fmt.encode(), "unexpected DDS header"
        blocks.append(data[128:])
    b = io.BytesIO(); levels[0].save(b, "DDS", pixel_format=fmt); hdr = bytearray(b.getvalue()[:128])
    struct.pack_into("<I", hdr, 8, struct.unpack_from("<I", hdr, 8)[0] | 0x20000)       # DDSD_MIPMAPCOUNT
    struct.pack_into("<I", hdr, 28, len(levels))                                         # dwMipMapCount
    struct.pack_into("<I", hdr, 108, struct.unpack_from("<I", hdr, 108)[0] | 0x400008)   # DDSCAPS_COMPLEX | DDSCAPS_MIPMAP
    open(path, "wb").write(bytes(hdr) + b"".join(blocks))
    chk = Image.open(path); print("wrote", path, chk.size, chk.mode, fmt, "mips", len(levels))

def rgb(name):
    return np.asarray(Image.open(os.path.join(src, name)).convert("RGB"), dtype=np.float32) / 255.0

# Which texels the mesh uses (its UV triangles, drawn): everything else is pushed full of the islands' own colours, or the
# mip levels pull the background into the islands' edges. (A bake writes every texel opaque, so its alpha cannot say.)
import json
from PIL import ImageDraw
mesh = json.load(open(os.path.join(src, "crest_low.json")))
SZ = Image.open(os.path.join(src, "crest_c.png")).size[0]
mk = Image.new("L", (SZ, SZ), 0); dr = ImageDraw.Draw(mk)
for tri in mesh["uv"]: dr.polygon([(u * SZ, (1 - v) * SZ) for u, v in tri], fill=255, outline=255)
USED = np.asarray(mk) > 0
print(f"the mesh uses {100 * USED.mean():.1f}% of the texture")
def dilate(a_, rounds=32):
    c_ = a_ * USED[..., None]; w = USED.astype(np.float32)
    for _ in range(rounds):
        cs = sum(np.roll(c_, sh, axis=ax) for ax in (0, 1) for sh in (1, -1)); ws = sum(np.roll(w, sh, axis=ax) for ax in (0, 1) for sh in (1, -1))
        grow = (w == 0) & (ws > 0)
        c_[grow] = cs[grow] / ws[grow][..., None]; w = np.where(grow, 1.0, w)
    left = w == 0
    if left.any(): c_[left] = a_[USED].mean(axis=0)            # far from every island: its mean
    return c_

# colour, its bronze matched to the approved emblem's gold: the mean of AGHallCrest.dds's gold (the render the relief wore,
# which read well at a distance) is sRGB 0.491, 0.397, 0.263 (measured 2026-10-24); the bake's cast-bronze ramp came out
# paler (0.49, 0.433, 0.323), cream in the hall's preview. Gains in linear light on the bronze only (by its specular mask:
# bronze 0.75, polished 0.95), so the steel, iron and wood keep theirs.
REF_GOLD = np.array([0.491, 0.397, 0.263])
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crest_lit
spec0 = np.asarray(Image.open(os.path.join(src, "crest_s.png")).convert("L"), dtype=np.float32) / 255.0
c = dilate(crest_lit.lit_colour(rgb("crest_d.png"), rgb("crest_o.png") * 2 - 1, spec0, rgb("crest_n.png") * 2 - 1)) ** 2.2
spec = dilate(np.asarray(Image.open(os.path.join(src, "crest_s.png")).convert("L"), dtype=np.float32)[..., None] / 255.0)[..., 0]
w = np.clip(np.exp(-((spec - 0.75) / 0.04) ** 2) + np.exp(-((spec - 0.95) / 0.04) ** 2), 0, 1)[..., None]
bronze = w[..., 0] > 0.8
gain = REF_GOLD ** 2.2 / np.maximum(1e-4, c[bronze].mean(axis=0))
print("bronze texels", int(bronze.sum()), "mean before", np.round(c[bronze].mean(axis=0) ** (1 / 2.2), 3), "gains (linear)", np.round(gain, 3))
c = c * (1 + w * (gain - 1))
col = Image.fromarray((np.clip(c, 0, 1) ** (1 / 2.2) * 255 + 0.5).astype(np.uint8), "RGB")
levels = [col]
while min(levels[-1].size) > 1:
    levels.append(levels[-1].resize((max(1, levels[-1].size[0] // 2), max(1, levels[-1].size[1] // 2)), Image.LANCZOS))
write_dds(levels, "DXT1", os.path.join(dst, "AGCrest.dds"))

# normal (+ specular in alpha)
n = dilate(rgb("crest_n.png")) * 2 - 1
inward = crest_lit.inward(n)                             # a plate hit from behind: its normal points into the surface
print(f"normals pointing inward, turned: {int((inward & USED).sum())} of the {int(USED.sum())} texels in use")
n[inward] *= -1
n[..., 1] *= -1                                          # Blender bakes green up; the game reads green down
s = spec
def enc(nv, sv):
    nv = nv / np.maximum(1e-6, np.linalg.norm(nv, axis=2, keepdims=True))
    return Image.fromarray(np.concatenate([(nv * 0.5 + 0.5) * 255 + 0.5, sv[..., None] * 255 + 0.5], axis=2).clip(0, 255).astype(np.uint8), "RGBA")
levels = [enc(n, s)]
while min(n.shape[:2]) > 1:
    h, w = n.shape[0] // 2, n.shape[1] // 2
    n = n[:h * 2, :w * 2].reshape(h, 2, w, 2, 3).mean(axis=(1, 3)); s = s[:h * 2, :w * 2].reshape(h, 2, w, 2).mean(axis=(1, 3))
    levels.append(enc(n, s))
write_dds(levels, "DXT5", os.path.join(dst, "AGCrest_n.dds"))
