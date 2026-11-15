"""The guild's own banner cloth (by the doors and inside as well, the
wings' four at 330 x 90; the first was plain beside the embellishments on the Companions banner). Worked as vanilla's
Companions banner (WRCHBanner01) is: red wool, its weave showing, worn darker toward its edges and hem with a little grime;
a faint pattern woven into the field, red on red; twisted-rope bands of gold thread across its head and above its tail;
gold woven borders down its sides; the guild's crest (textures/AdventurersGuild/Hall/AGHallCrest.dds: the facade's dragon
ring round the shield and the sword) worked in gold thread, outlined and shaded in dark thread so it reads as embroidery; a
knotwork diamond below it; its pointed tail edged in gold (its fringe is the mesh's: banner_nif.py). One texture for every
size: the mesh maps its whole cloth onto it, the tail starting at TAIL_V.
    python make_banner_texture.py <out dir>      -> AGH2Banner.dds, AGH2Banner_n.dds (BC7, mipmapped; pngs beside them)"""
import os, sys, math, subprocess
import numpy as np
from PIL import Image, ImageFilter, ImageDraw
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
GAME = "C:/Games/steamapps/common/SkyrimVR"; TEXCONV = GAME + "/tools/texconv/texconv.exe"
W, H = 512, 2048
TAIL_V = 1 - 30 / 330                                     # (where the tail's point begins, as a fraction of the length)
rng = np.random.default_rng(29102026)
U, V = np.meshgrid((np.arange(W) + 0.5) / W, (np.arange(H) + 0.5) / H)
X, Y = U * W, V * H                                        # (pixels)
def noise(cells_x, cells_y):
    return np.array(Image.fromarray((rng.random((cells_y, cells_x)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)) / 255.0

# ---- the field: wool, its weave, a woven pattern red on red, wear and grime
warp = 0.5 + 0.5 * np.sin(X * math.pi / 2.2)
weft = 0.5 + 0.5 * np.sin(Y * math.pi / 2.2 + 0.7 * np.sin(U * 31))
weave = 0.55 * warp * (1 - weft) + 0.45 * weft * (1 - warp)
slub, mottle, grime = noise(W // 8, H // 8), noise(W // 64, H // 64), noise(W // 12, H // 12)
# (the woven pattern: an ogee lattice with a dot in each cell, as a damask's, a few shades darker than the field)
lx, ly = (X / 64.0) % 1.0, (Y / 96.0) % 1.0
ogee = np.abs(np.abs(lx - 0.5) * 2 - (0.5 + 0.35 * np.sin(ly * 2 * math.pi)))
pattern = np.clip(1 - ogee / 0.07, 0, 1) + np.clip(1 - np.hypot(lx - 0.5, ly - 0.5) / 0.07, 0, 1)
# (wear: darker toward the sides and the hem, a little lighter where the sun took it near the head; grime in blotches)
edge = np.clip(np.minimum(U, 1 - U) / 0.12, 0, 1)
wear = (0.80 + 0.20 * edge) * (1.0 - 0.10 * V) * (1.0 + 0.04 * np.clip(1 - V / 0.25, 0, 1))
shade = (0.86 + 0.10 * weave + 0.05 * (slub - 0.5) + 0.07 * (mottle - 0.5)) * wear * (1 - 0.10 * pattern) * (1 - 0.06 * np.clip((grime - 0.62) / 0.2, 0, 1))
RED = np.array([108, 44, 37]) / 255.0                     # (matched in render, side by side under one light, to the door's Jorrvaskr banner)
rgb = RED[None, None, :] * shade[..., None]
height = 0.35 * weave + 0.1 * slub - 0.08 * pattern
DARK = np.array([52, 30, 14]) / 255.0                      # (the dark thread that outlines and shades the gold)

def gold(lum):
    lo, hi = np.array([92, 62, 20]) / 255.0, np.array([236, 200, 116]) / 255.0
    return lo + (hi - lo) * np.clip(lum, 0, 1)[..., None]
def paint(mask, lum, raise_=0.6, outline=1.5):
    """gold thread over the mask, with a dark outline round it (the mask dilated, less itself)"""
    global rgb, height
    m = np.clip(mask, 0, 1)
    if outline:
        im = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(outline * 0.6))
        o = np.clip(np.asarray(im) / 255.0 - m, 0, 1)[..., None] * 0.85
        rgb = rgb * (1 - o) + DARK * o
    rgb = rgb * (1 - m[..., None]) + gold(lum) * m[..., None]
    height = height + raise_ * m
satin = 0.55 + 0.45 * (0.5 + 0.5 * np.sin((X + Y) * math.pi / 1.6))   # (satin stitch, laid on the diagonal)

STYLE = (sys.argv[2] if len(sys.argv) > 2 else "A").upper()
# (the first embellished one: the circle round the crest looked off, and so did the pattern on the
# lines and the way the horizontal and vertical lines came together; vanilla's banners, studied:
# bold one-tone emblems with no ring; borders plain and continuous, mitred, following the tail (the Imperial banner), or full
# length stripes that meet nothing (Riften's); a pattern kept apart near the hem (Whiterun's lattice))
px = 1.0 / W
def outline_mask(inset, width):
    """the banner's own outline (its sides, its head and its pointed tail) drawn `inset` px in, `width` px wide: one
    continuous band, mitred at every corner"""
    img_ = Image.new("L", (W, H), 0); d_ = ImageDraw.Draw(img_)
    tv = TAIL_V * H
    P = [(0, 0), (W, 0), (W, tv), (W / 2, H), (0, tv)]          # (the outline, clockwise on the image)
    lines = []
    for (x1, y1), (x2, y2) in zip(P, P[1:] + P[:1]):            # (each edge moved `inset` toward the inside)
        dx, dy = x2 - x1, y2 - y1; L_ = math.hypot(dx, dy); nx, ny = -dy / L_, dx / L_
        lines.append(((x1 + nx * inset, y1 + ny * inset), (dx, dy)))
    pts = []
    for (p1, d1), (p2, d2) in zip(lines[-1:] + lines[:-1], lines):   # (consecutive edges meet: the mitred corner)
        den = d1[0] * d2[1] - d1[1] * d2[0]; s = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
        pts.append((p1[0] + d1[0] * s, p1[1] + d1[1] * s))
    d_.line(pts + [pts[0]], fill=255, width=int(width), joint="curve")
    return np.asarray(img_.filter(ImageFilter.GaussianBlur(0.6))) / 255.0
if STYLE == "A":                                           # the Imperial banner's: one gold frame round the whole shape
    paint(outline_mask(20, 12), satin * 0.85 + 0.15 * weave, outline=1.5)
    paint(outline_mask(32, 2), 0.6 * satin, outline=0)     # (a fine line inside it)
elif STYLE == "B":                                         # Riften's: two gold stripes down the full length, nothing across
    for a_ in (30, W - 30 - 22):
        paint(((X >= a_) & (X < a_ + 22) & (V < TAIL_V + (1 - TAIL_V) * (1 - np.abs(X - W / 2) / (W / 2)))).astype(float),
              satin * 0.85 + 0.15 * weave, outline=1.5)
elif STYLE == "C":                                         # Whiterun's: no border; a lattice band of gold above the tail
    img_ = Image.new("L", (W, H), 0); d_ = ImageDraw.Draw(img_)
    y0, y1 = TAIL_V * H - 300, TAIL_V * H - 40
    for k_ in range(-4, 6):
        x0 = k_ * 110
        d_.line([(x0, y0), (x0 + (y1 - y0) * 0.6, y1)], fill=255, width=10); d_.line([(x0 + (y1 - y0) * 0.6, y0), (x0, y1)], fill=255, width=10)
    d_.line([(0, y0), (W, y0)], fill=255, width=10); d_.line([(0, y1), (W, y1)], fill=255, width=10)
    paint(np.asarray(img_.filter(ImageFilter.GaussianBlur(0.6))) / 255.0, satin * 0.85, outline=1.5)
# the tail's edges in gold, for B and C (A's frame already follows them)
if STYLE in ("B", "C"):
    k = np.clip((V - TAIL_V) / (1 - TAIL_V), 0, 1); edge_d = 0.5 * (1 - k) - np.abs(U - 0.5)
    paint(((V >= TAIL_V) & (edge_d > 8 * px) & (edge_d < 20 * px)).astype(float), satin * 0.85, outline=1.5)

# the crest: gold thread by its brightness, outlined and shaded in dark thread, on a roundel a shade darker than the field
crest = Image.open(os.path.join(HERE, "..", "..", "hall-private", "assets", "textures", "AdventurersGuild", "Hall", "AGHallCrest.dds")).convert("RGBA")
cw = int(W * 0.84); crest = crest.resize((cw, cw), Image.LANCZOS)
c = np.asarray(crest).astype(float) / 255.0
lum = 0.3 * c[..., 0] + 0.59 * c[..., 1] + 0.11 * c[..., 2]; inside = c[..., 3] > 0.5
lum = (lum - lum[inside].min()) / max(1e-6, np.ptp(lum[inside]))
cy = int(H * 0.29); cx0, cy0 = (W - cw) // 2, cy - cw // 2
mask = np.zeros((H, W)); L = np.zeros((H, W))
mask[cy0:cy0 + cw, cx0:cx0 + cw] = c[..., 3]; L[cy0:cy0 + cw, cx0:cx0 + cw] = lum
gy_, gx_ = np.gradient(L)                                   # (the crest's own detail lines darkened, as stitched shading)
detail = np.clip(np.hypot(gx_, gy_) * 6, 0, 1)
paint(mask, (0.55 + 0.35 * L * (0.8 + 0.2 * satin)) * (1 - 0.6 * detail), raise_=0.9, outline=2.5)   # (bold: nearly one gold)

img = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8), "RGB")
img.save(os.path.join(OUT, f"AGH2Banner{'' if STYLE == 'A' else STYLE}.png"))
# the normal map from the relief (Skyrim's: green up; the weave's and the stitching's)
hgt = np.asarray(Image.fromarray((np.clip((height - height.min()) / np.ptp(height), 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))).astype(float) / 255.0
gy, gx = np.gradient(hgt * 6.0)
n = np.dstack([-gx, gy, np.ones_like(gx)]); n /= np.linalg.norm(n, axis=2, keepdims=True)
Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8), "RGB").save(os.path.join(OUT, "AGH2Banner_n.png"))
for f in (f"AGH2Banner{'' if STYLE == 'A' else STYLE}.png", "AGH2Banner_n.png"):
    subprocess.run([TEXCONV, "-nologo", "-y", "-f", "BC7_UNORM", "-m", "0", "-o", OUT, os.path.join(OUT, f)], check=True,
                   stdout=subprocess.DEVNULL)
print("BANNER TEXTURE", OUT, [f for f in os.listdir(OUT) if f.startswith("AGH2Banner")])
