"""The Guild's sign board (chosen from a sheet of vanilla's signs): vanilla's own general goods board with its picture scraped off and the Guild's device painted as vanilla paints a
sign: one colour worn into the wood along its grain, not a picture laid on it. The crest reduced to its ring and sword, the name in Cyrodiil, the Guild's own face, all but vanilla's sign lettering.
    python make_sign_texture.py <clean textures root> <hall crest .dds> <out dir> <Cyrodiil .otf>        -> AGH2SignGuild.dds, AGH2SignGuild_n.dds"""
import math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
ROOT, CREST, OUT, FONT = sys.argv[1:5]; TEXCONV = "C:/Games/steamapps/common/SkyrimVR/tools/texconv/texconv.exe"
rng = np.random.default_rng(4182); W, H = 512, 512
INK = (0.10, 0.075, 0.06); POLY = [(50, 84), (120, 74), (212, 68), (300, 74), (392, 84), (396, 240), (350, 350), (285, 425), (212, 470), (140, 425), (72, 350), (46, 240)]
def emblem(size):
    a = np.asarray(Image.open(CREST).convert("RGBA").resize((512, 512), Image.LANCZOS)).astype(float); al = a[:, :, 3] / 255; L = a[:, :, :3].mean(2) / 255
    yy, xx = np.mgrid[0:512, 0:512]; inside = ((xx - 255) / 166.0) ** 2 + ((yy - 245) / 122.0) ** 2 < 1      # (the shield goes: the ring and the sword stay)
    sword = (np.abs(xx - 256) < 15) | ((np.abs(xx - 256) < 84) & (np.abs(yy - 113) < 16))
    m = ((al > 0.5) & (~inside | (sword & (L > 0.05)))).astype(float)
    lines = np.asarray(Image.fromarray((L * 255).astype("uint8")).filter(ImageFilter.GaussianBlur(1.2))).astype(float) / 255
    m *= np.where(lines < 0.22, 0.0, 1.0)                     # (the dark of the scales falls out as stencil gaps)
    im = Image.fromarray((m * 255).astype("uint8")).filter(ImageFilter.GaussianBlur(0.7)).resize((size, size), Image.LANCZOS)
    return im.point(lambda v: 255 if v > 118 else 0).filter(ImageFilter.GaussianBlur(0.6))
def lettering(s, size, cx, base, rad):
    F = ImageFont.truetype(FONT, size); im = Image.new("L", (W, H), 0); wd = [F.getlength(c) * 1.02 for c in s]
    if not rad:
        ImageDraw.Draw(im).text((cx, base), s, font=F, fill=255, anchor="ms"); return im
    ang = -sum(wd) / rad / 2
    for c, w in zip(s, wd):
        t = ang + w / 2 / rad; px, py = cx + rad * math.sin(t), base + rad - rad * math.cos(t)
        g = Image.new("L", (size * 3, size * 3), 0); ImageDraw.Draw(g).text((size * 1.5, size * 1.5), c, font=F, fill=255, anchor="ms"); g = g.rotate(-math.degrees(t), Image.BICUBIC)
        im.paste(255, (int(px - size * 1.5), int(py - size * 1.5)), g); ang += w / rad
    return im
def wear(amount):
    n = rng.random((H // 2, W // 8)); n = np.asarray(Image.fromarray((n * 255).astype("uint8")).resize((W, H), Image.BICUBIC)).astype(float) / 255
    return np.clip(1 - ((n * 0.7 + rng.random((H, W)) * 0.3) < amount) * 1.0, 0, 1)
def paint(base, mask, amount):
    m = np.asarray(mask).astype(float)[:, :, None] / 255 * wear(amount)[:, :, None]; lum = base.mean(2, keepdims=True); lum = lum / max(lum.mean(), 1e-3)
    return base * (1 - m) + np.clip(np.array(INK) * (0.55 + 0.45 * lum), 0, 1) * m
def feather(r):
    m = Image.new("L", (W, H), 0); ImageDraw.Draw(m).polygon(POLY, fill=255); return np.asarray(m.filter(ImageFilter.GaussianBlur(r))).astype(float)[:, :, None] / 255
sheet = np.asarray(Image.open(os.path.join(ROOT, "clutter", "signgeneralgoods01.dds")).convert("RGBA")).astype(float) / 255
x0, y0, x1, y1 = 56, 120, 96, 320; t = sheet[y0:y1, x0:x1, :3]; tw = x1 - x0; rows = np.arange(H) % (y1 - y0); wood = np.zeros((H, W, 3))
for x in range(W):
    wood[:, x] = t[(rows + (x // tw) * 37) % (y1 - y0), (x % tw) if (x // tw) % 2 == 0 else tw - 1 - (x % tw)]
m = feather(5); out = sheet[:, :, :3] * (1 - m) + wood * m
mk = Image.new("L", (W, H), 0); mk.paste(emblem(200), (221 - 100, 142)); out = paint(out, mk, 0.18)
out = paint(out, lettering("Adventurers", 50, 221, 128, 440), 0.12); out = paint(out, lettering("Guild", 52, 221, 400, 0), 0.12)
nrm = np.asarray(Image.open(os.path.join(ROOT, "clutter", "signgeneralgoods01_n.dds")).convert("RGBA")).astype(float) / 255
m = feather(4); g = rng.normal(0, 0.012, (H, W)); fl = np.dstack([0.5 + g, 0.5 + g * 0.4, np.ones((H, W))])   # (the old picture's relief gone from the panel)
n3 = nrm[:, :, :3] * (1 - m) + fl * m
for name, arr, alpha, fmt in (("AGH2SignGuild", out, sheet[:, :, 3], "BC3_UNORM"), ("AGH2SignGuild_n", n3, nrm[:, :, 3], "BC3_UNORM")):
    png = os.path.join(OUT, name + ".png"); Image.fromarray((np.clip(np.dstack([arr, alpha]), 0, 1) * 255).astype("uint8"), "RGBA").save(png)
    subprocess.run([TEXCONV, "-nologo", "-y", "-f", fmt, "-m", "0", "-o", OUT, png], check=True, stdout=subprocess.DEVNULL); os.remove(png)
print("SIGN TEXTURE", os.path.getsize(os.path.join(OUT, "AGH2SignGuild.dds")))
