"""The hall's paintings (the maps on the front gallery's and the lobby's walls replaced with a
painting that makes sense in the guild: the hall itself, painted). Vanilla has no framed paintings
to borrow, so these are our own: renders of the hall from outside (guildhall_gen.py's road_axis and sign views), the
render's flat sky replaced by a painted one, then laid in oils: a smooth Kuwahara filter (flat strokes that keep edges),
a warm varnish, canvas weave and a darkened edge. BC7 with mips, as the hall's other textures. (Since hall2bd,
blocky up close: the box Kuwahara's square quadrants and a posterising step tiled it in
squares at 1024; now the generalised one, Gaussian-weighted sectors blended by their variance, at the render's own
1360 x 1000 and 2048 on the board)

    python make_paintings.py <render dir> <out dir: .../textures/AdventurersGuild/Hall2> [--preview <png dir>]"""
import os, sys, subprocess, tempfile
import numpy as np
from PIL import Image, ImageFilter

TEXCONV = "C:/Games/steamapps/common/SkyrimVR/tools/texconv/texconv.exe"
SKY = np.array([181, 187, 194], float)                     # the render's flat background
PAINTINGS = {"AGH2Painting1": "road_axis", "AGH2Painting2": "sign"}


def noise(h, w, seed, octaves=5):
    rng = np.random.default_rng(seed); out = np.zeros((h, w))
    for o in range(octaves):
        s = 2 ** (o + 2)
        g = rng.random((s, int(s * w / h) + 1))
        out += np.asarray(Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), float) / 255 / (2 ** o)
    return out / out.max()


def sky(h, w, seed):
    t = np.linspace(0, 1, h)[:, None]
    top, hor = np.array([92, 112, 138], float), np.array([214, 196, 168], float)   # a late, warm northern sky
    base = top * (1 - t[..., None] ** 0.8) + hor * t[..., None] ** 0.8
    c = noise(h, w, seed)[..., None]
    clouds = np.clip((c - 0.45) * 2.2, 0, 1) * (1 - t[..., None] * 0.6)
    return base * (1 - clouds * 0.55) + np.array([236, 228, 214]) * clouds * 0.55


def kuwahara(a, r, q=8.0):
    """the generalised Kuwahara: the mean and spread of eight Gaussian-weighted sectors round each pixel, blended by
    1 / spread^q (the least varied sectors win, but softly, so no square edges as the box filter's argmin leaves)"""
    from scipy.ndimage import gaussian_filter, shift
    s_ = r / 2.0; g = a.mean(axis=2)
    m1 = np.stack([gaussian_filter(a[..., c], s_) for c in range(3)], -1); g1 = gaussian_filter(g, s_); g2 = gaussian_filter(g * g, s_)
    num = np.zeros_like(a); den = np.zeros(g.shape)
    for k in range(8):
        dy, dx = r * 0.7 * np.sin(k * np.pi / 4), r * 0.7 * np.cos(k * np.pi / 4)
        m = np.stack([shift(m1[..., c], (dy, dx), order=1, mode="nearest") for c in range(3)], -1)
        v = shift(g2, (dy, dx), order=1, mode="nearest") - shift(g1, (dy, dx), order=1, mode="nearest") ** 2
        w = 1.0 / (1.0 + np.maximum(v, 0) / 25.0) ** q
        num += m * w[..., None]; den += w
    return num / den[..., None]


def paint(src, seed):
    im = Image.open(src).convert("RGB")
    a = np.asarray(im, float)
    m = (np.abs(a - SKY).sum(axis=2) < 6).astype(float)       # the flat sky
    m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5)), float)[..., None] / 255
    a = a * (1 - m) + sky(*a.shape[:2], seed) * m
    a = kuwahara(a, 6)
    a = kuwahara(a, 3)
    a = a * np.array([1.06, 1.0, 0.86]) + np.array([10, 4, -6]) # warm varnish
    lum = a.mean(axis=2, keepdims=True); a = lum + (a - lum) * 0.85
    H, W = a.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W]
    weave = (np.sin(xx * 1.9) * np.sin(yy * 1.9)) * 4 + (noise(H, W, seed + 7, 3)[...] - 0.5) * 10
    a = a + weave[..., None]
    r = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
    a = a * (1 - np.clip(r - 0.55, 0, 1) ** 1.6 * 0.55)[..., None]   # darkened edge, as old varnish yellows and soot settles
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def main():
    src, out = sys.argv[1], sys.argv[2]
    prev = sys.argv[sys.argv.index("--preview") + 1] if "--preview" in sys.argv else None
    os.makedirs(out, exist_ok=True)
    for k, (name, view) in enumerate(PAINTINGS.items()):
        im = paint(os.path.join(src, f"hall_tex_ext2_{view}.png"), 11 + k)
        im = im.resize((2048, 2048), Image.LANCZOS)             # (the frame's board stretches it back to its own 68:50)
        if prev: os.makedirs(prev, exist_ok=True); paint_prev = im.resize((1360, 1000)); paint_prev.save(os.path.join(prev, name + ".png"))
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, name + ".png"); im.save(p)
            subprocess.run([TEXCONV, "-nologo", "-y", "-f", "BC7_UNORM", "-m", "0", "-o", out, p], check=True, capture_output=True)
            flat = Image.new("RGB", (64, 64), (128, 128, 255)); pn = os.path.join(td, name + "_n.png"); flat.save(pn)
            subprocess.run([TEXCONV, "-nologo", "-y", "-f", "BC1_UNORM", "-m", "0", "-o", out, pn], check=True, capture_output=True)
        print("painted", name, "from", view)


if __name__ == "__main__":
    main()
