"""The guild's banner as vanilla's hall banners are made (theirs have more texture and move like natural cloth, animated, where ours sat there like
static paper). Those are one skinned, animated mesh, GenericBannerRed01, each with its own picture on a 512 x 1024 canvas: the cloth over u 0.16..1, its hem and tail cut by alpha, on
GenericBanner01_n. So: vanilla's own hem (CityBannerRiften01's alpha), its own weave and wear (CityBannerMarkarth01's, the plain one, by brightness), its stripes' places (Riften's), in the
guild's red and gold, and the guild's crest where a hold has its arms. Riften's alpha is moth-eaten: the holes stay out of ours (in game they read as heavily overwritten and
damaged), the tabs, the hem and the tail are kept. Its normal map is a copy, so a banner replacer's does not lie over our picture.
    python make_cloth_banner.py <clean textures root> <hall crest .dds> <out dir>       -> AGH2BannerCloth.dds, AGH2BannerCloth_n.dds"""
import os, shutil, subprocess, sys
import numpy as np
from PIL import Image, ImageFilter
ROOT, CREST, OUT = sys.argv[1:4]
GAME = "C:/Games/steamapps/common/SkyrimVR"; TEXCONV = GAME + "/tools/texconv/texconv.exe"
RED = np.array((122, 26, 28), float); GOLD = np.array((196, 150, 66), float)
rift = np.asarray(Image.open(os.path.join(ROOT, "clutter", "citybannerriften01.dds")).convert("RGBA"), float)
plain = np.asarray(Image.open(os.path.join(ROOT, "clutter", "citybannermarkarth01.dds")).convert("RGBA"), float)
H, W = rift.shape[:2]; assert (W, H) == (512, 1024), (W, H)
# the outline without the holes: each row closed between its edges, the edges a running median (a hole biting in from the side is no edge), the tabs' gaps kept: the columns open at row 10
solid = rift[:, :, 3] > 128; rows = np.flatnonzero(solid.sum(1) > 4); x0, x1 = np.flatnonzero(solid[H // 3])[[0, -1]]; gaps = ~solid[10]
top = next(y for y in range(10, H) if solid[y, x0:x1 + 1][gaps[x0:x1 + 1]].mean() > 0.9)
lo = np.array([np.flatnonzero(solid[y])[0] for y in rows], float); hi = np.array([np.flatnonzero(solid[y])[-1] for y in rows], float)
med = lambda a: np.array([np.median(a[max(i - 14, 0):i + 15]) for i in range(len(a))])
alpha = rift[:, :, 3].copy()
for y, a_, b_ in zip(rows, med(lo), med(hi)):
    keep = alpha[y].copy(); alpha[y, int(a_) + 2:int(b_) - 1] = 255
    if y < top: alpha[y, gaps] = keep[gaps]
holes = (alpha > 128) & ~solid
assert holes.sum() > 500, "no holes closed: the source's alpha is not the one this was written for"
# the weave and wear: the plain banner's brightness round its own mean, inside the cloth (its canvas's corner holds three small swatches, left out with the alpha)
cloth = rift[:, :, 3] > 128
lum = plain[:, :, :3].mean(2); weave = lum / max(lum[cloth].mean(), 1.0); weave = np.clip(weave, 0.45, 1.6)
# the stripes: where Riften's gold runs, column by column, over the head of the banner (its arms lower down left out)
r, g, b = rift[:, :, 0], rift[:, :, 1], rift[:, :, 2]
goldish = ((r > 95) & (b < r * 0.78)).astype(float)
head = cloth[:int(H * 0.28)]; col = (goldish[:int(H * 0.28)] * head).sum(0) / np.maximum(head.sum(0), 1)
stripe = np.asarray(Image.fromarray((np.clip(col, 0, 1)[None, :] * 255).astype("uint8")).resize((W, H)).filter(ImageFilter.GaussianBlur(1.2)), float) / 255
stripe = np.clip((stripe - 0.35) / 0.3, 0, 1)
img = RED[None, None, :] * (1 - stripe[..., None]) + GOLD[None, None, :] * stripe[..., None]
img = img * weave[..., None]
# the crest, where a hold has its arms: the middle of the cloth's width, a little below its middle
crest = Image.open(CREST).convert("RGBA"); cw = 300; crest = crest.resize((cw, cw), Image.LANCZOS); c = np.asarray(crest, float) / 255
cx = int(W * 0.58) - cw // 2; cy = int(H * 0.60) - cw // 2
a = c[:, :, 3][..., None]; L = c[:, :, :3].mean(2)[..., None]
thread = GOLD[None, None, :] * (0.55 + 0.75 * L) * weave[cy:cy + cw, cx:cx + cw, None]
img[cy:cy + cw, cx:cx + cw] = img[cy:cy + cw, cx:cx + cw] * (1 - a) + thread * a
out = np.dstack([np.clip(img, 0, 255), alpha]).astype("uint8")
png = os.path.join(OUT, "AGH2BannerCloth.png"); Image.fromarray(out, "RGBA").save(png)
subprocess.run([TEXCONV, "-nologo", "-y", "-f", "BC3_UNORM", "-m", "0", "-o", OUT, png], check=True, stdout=subprocess.DEVNULL)
os.remove(png)
shutil.copyfile(os.path.join(ROOT, "clutter", "genericbanner01_n.dds"), os.path.join(OUT, "AGH2BannerCloth_n.dds"))
print("CLOTH", os.path.getsize(os.path.join(OUT, "AGH2BannerCloth.dds")), "stripe columns", int((stripe[0] > 0.5).sum()))
