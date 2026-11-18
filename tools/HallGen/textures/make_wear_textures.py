"""The stonework's wear decals (the grand stair had no small details: a random crack along the
top of the stair wall, a stain; the piers a chipped corner block and a hairline crack; from the wearopt
mock-ups). Drawn, seeded, the same every build, as vanilla's own wear strips are pictures laid over its walls (Whiterun's
wrplasterdecals, Windhelm's whbrickdecal1): no vanilla picture is a hairline crack or a run-off stain.

  AGH2XWearCrack   1024 x 128: a hairline crack along u, kept to a joint's line (rows 50..78, the strip maps 38..90), one step through a block,
                   a short branch; a thin dark core in a faint grime halo; its normal a shallow groove
  AGH2XWearStain   128 x 512: a run-off stain down v from a coping joint, darker and wider under it, narrowing and fading as it runs; a
                   little bolder than the mock-up as rendered; its normal flat
  AGH2XSpill       256 x 256: a drink spilled on the tavern's floorboards long ago and never scrubbed: a dark amber-brown pool soaked into the
                   wood, its outline uneven, darker at its dried rim (what dries last leaves its ring), a few splash drops off one side;
                   its normal flat
Diffuse BC3 (its alpha the decal's), normals BC7, full mip chains, texconv from the toolkit.
    python make_wear_textures.py <out dir> [<copy to> ...]        (the build's textures/AdventurersGuild/Hall2, then the render root's)"""
import math, os, random, shutil, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
TEXCONV = "C:/Games/steamapps/common/SkyrimVR/tools/texconv/texconv.exe"


def crack():
    R = random.Random("wear 2026-11-03"); W, H = 1024, 128
    core = Image.new("L", (W, H), 0); g = ImageDraw.Draw(core)
    pts, y = [], 64.0
    for x in range(0, W + 8, 8):
        if 430 < x < 450: y += 4                                     # the step through a block: off the joint's line and back lower
        y += R.uniform(-1.6, 1.6) + (64 - y) * 0.12; y = max(50, min(78, y)); pts.append((x, y))
    for a, b in zip(pts, pts[1:]): g.line([a, b], fill=255, width=R.choice((3, 3, 4)))
    bx, by = 660, pts[660 // 8][1]                                   # a short branch
    for _ in range(14): nx, ny = bx + 7, by + R.uniform(-3, 5); g.line([(bx, by), (nx, ny)], fill=200, width=2); bx, by = nx, ny
    halo = core.filter(ImageFilter.GaussianBlur(5)).point(lambda v: min(255, int(v * 1.6)))
    c, h = np.asarray(core, float), np.asarray(halo, float)
    a = np.maximum(c, h * 0.5)
    rgb = np.where((c > 40)[..., None], np.array([18, 16, 14], float), np.array([40, 38, 32], float))
    img = np.dstack([rgb, a]).astype(np.uint8)
    # the groove: height from the core, blurred, its slope into a tangent-space normal (green up, as the game reads them)
    ht = np.asarray(core.filter(ImageFilter.GaussianBlur(1.5)), float) / 255.0
    gy, gx = np.gradient(-ht * 2.5)
    n = np.dstack([-gx, gy, np.ones_like(gx)]); n /= np.linalg.norm(n, axis=2, keepdims=True)
    return Image.fromarray(img, "RGBA"), Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8), "RGB")


def stain():
    R = random.Random("wear 2026-11-03"); SW, SH = 128, 512
    cols = np.array([R.uniform(0.6, 1.0) for _ in range(SW)])
    j = np.arange(SH)[:, None] / SH; i = np.arange(SW)[None, :]
    width = 0.5 - 0.22 * j; u = np.abs(i / SW - 0.5)
    edge = np.clip(1 - u / width, 0, 1) ** 0.7
    a = edge * (1 - j) ** 1.15 * (0.55 + 0.45 * cols[None, :]) * (0.8 + 0.2 * np.sin(np.arange(SH)[:, None] * 0.07 + i * 0.3))
    a = np.clip(a * 1.0, 0, 1) * 255                                 # (0.75 in the mock-up: a little bolder here)
    rgb = np.broadcast_to(np.array([22, 23, 19], float), (SH, SW, 3))
    img = Image.fromarray(np.dstack([rgb, a]).astype(np.uint8), "RGBA").filter(ImageFilter.GaussianBlur(1.2))
    return img, Image.new("RGB", (SW, SH), (128, 128, 255))


def spill():
    R = random.Random("spill 2026-11-17"); N = 256; c = N / 2
    yy, xx = np.mgrid[0:N, 0:N].astype(float)
    # the pool: a few overlapping lobes, its outline wobbled by low harmonics of the angle
    ang = np.arctan2(yy - c, xx - c)
    wob = sum(R.uniform(0.03, 0.09) * np.cos(k * ang + R.uniform(0, 2 * math.pi)) for k in (2, 3, 5, 7))
    pool = np.zeros((N, N))
    for _ in range(4):
        ox, oy, r = c + R.uniform(-22, 22), c + R.uniform(-16, 16), R.uniform(38, 62)
        pool = np.maximum(pool, 1 - np.hypot(xx - ox, (yy - oy) * 1.15) / (r * (1 + wob)))
    inside = np.clip(pool * 6, 0, 1)                                 # (a soft edge a few pixels wide)
    rim = np.clip(1 - np.abs(pool - 0.07) / 0.07, 0, 1) * 0.45       # (the dried ring just inside the edge)
    soak = np.asarray(Image.fromarray((np.array([[R.random() for _ in range(N)] for _ in range(N)]) * 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(9)), float) / 255.0
    soak = (soak - soak.min()) / max(1e-6, soak.max() - soak.min())  # (soaked in unevenly: blotches lighter and darker)
    a = inside * (0.36 + 0.3 * soak) + rim
    for _ in range(5):                                               # splash drops off one side, smaller as they go
        d_ = R.uniform(70, 108); t_ = R.uniform(-0.6, 0.6) + 0.4; r_ = R.uniform(4, 8) * (1.3 - d_ / 140)
        dx_, dy_ = c + d_ * math.cos(t_), c + d_ * math.sin(t_)
        a = np.maximum(a, np.clip(1 - np.hypot(xx - dx_, yy - dy_) / r_, 0, 1) ** 0.5 * 0.6)
    a = np.clip(a, 0, 1) * 255
    rgb = np.dstack([26 + 12 * soak, 15 + 7 * soak, 8 + 3 * soak])  # (dark amber, browner where it soaked deepest)
    img = Image.fromarray(np.dstack([rgb, a]).astype(np.uint8), "RGBA").filter(ImageFilter.GaussianBlur(0.8))
    return img, Image.new("RGB", (N, N), (128, 128, 255))


def main():
    out = sys.argv[1]; copies = sys.argv[2:]; os.makedirs(out, exist_ok=True); work = tempfile.mkdtemp()
    made = []
    for name, (dif, nrm) in (("AGH2XWearCrack", crack()), ("AGH2XWearStain", stain()), ("AGH2XSpill", spill())):
        for suf, im, fmt in (("", dif, "BC3_UNORM"), ("_n", nrm, "BC7_UNORM")):
            png = os.path.join(work, name + suf + ".png"); im.save(png)
            subprocess.run([TEXCONV, "-nologo", "-y", "-f", fmt, "-m", "0", "-o", out, png], check=True, capture_output=True)
            d = os.path.join(out, name + suf + ".dds")
            if not os.path.exists(d) or os.path.getsize(d) < 1000: raise SystemExit("texconv made nothing for " + d)
            made.append(d)
    for c in copies:
        os.makedirs(c, exist_ok=True)
        for d in made: shutil.copyfile(d, os.path.join(c, os.path.basename(d)))
    shutil.rmtree(work, ignore_errors=True)
    print("WEAR TEXTURES", len(made), "made:", ", ".join(os.path.basename(d) for d in made))


if __name__ == "__main__":
    main()
