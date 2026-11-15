"""The board's notices as one 2K atlas: twelve cells (4 x 3, each 512 x 682, the notices' 3:4), every one a guild request
written by a clerk on one of vanilla's papers. No words (the mod is translated: a baked word cannot be): the rank stamped
in its badge's colour, an ink sketch of the quarry (sketch.py, from vanilla's own creature meshes), lines of illegible
hand, the reward as a septim and a figure, and the guild's wax seal on the high ranks. Torn and deckled edges in alpha.
    python make_notices.py <vanilla cache: holds textures/clutter/...> <AG tex dir: seal.png> <out dir>
-> <out>/AGBoardNotices.png (RGBA, alpha = the paper's edge), AGBoardNotices_n.png (normal, green up; spec in alpha),
   <out>/notices.json (each cell's rect in UV and what it is), <out>/preview.jpg"""
import sys, os, json, math, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

VAN, AGTEX, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)
ATLAS = 2048
CW, CH = 512, 682                       # a cell
SS = 2                                  # drawn at twice the size, then reduced
W, H = CW * SS, CH * SS
INK = (52, 34, 22)
FONT = "C:/Windows/Fonts/palab.ttf"
RANK_INK = {"E": (64, 62, 60), "D": (48, 66, 92), "C": (150, 102, 28), "B": (46, 96, 58), "A": (24, 20, 20), "S": (148, 22, 26)}

def paper_src(name):
    return Image.open(os.path.join(VAN, "textures", "clutter", "books", name + ".dds")).convert("RGB")

def nine_slice(im, w, h, b):
    """resize keeping a border of b pixels unstretched across it (edges stretched along their length only)"""
    sw, sh = im.size
    out = Image.new("RGB", (w, h))
    xs = [(0, b, 0, b), (b, sw - b, b, w - b), (sw - b, sw, w - b, w)]
    ys = [(0, b, 0, b), (b, sh - b, b, h - b), (sh - b, sh, h - b, h)]
    for sx0, sx1, dx0, dx1 in xs:
        for sy0, sy1, dy0, dy1 in ys:
            out.paste(im.crop((sx0, sy0, sx1, sy1)).resize((dx1 - dx0, dy1 - dy0), Image.LANCZOS), (dx0, dy0))
    return out

def paper(name, tint=(1.0, 1.0, 1.0), border=None, seed=0):
    src = paper_src(name)
    if name == "largetornpage":       # the torn page sits on brown: its paper only
        src = src.crop((40, 20, 984, 1004))
    if not border and name != "largetornpage": src = src.crop((14, 14, src.size[0] - 14, src.size[1] - 14))
    im = nine_slice(src, W, H, border) if border else src.resize((W, H), Image.LANCZOS)
    a = np.asarray(im, np.float32) * np.array(tint)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

def deckle(seed, torn=False):
    """the sheet's outline: slightly uneven edges, rounded worn corners; torn: a ragged bottom and side"""
    rnd = np.random.default_rng(seed)
    m = Image.new("L", (W, H), 0); d = ImageDraw.Draw(m)
    def edge(n, amp, rough):
        base = np.cumsum(rnd.normal(0, rough, n)); base -= np.linspace(base[0], base[-1], n)
        return base * amp
    n = 160; m_ = 6 * SS
    top = edge(n, 0.6, 0.6); bot = edge(n, 4.0 if torn else 0.8, 1.6 if torn else 0.6)
    lef = edge(n, 0.7, 0.6); rig = edge(n, 3.0 if torn else 0.7, 1.3 if torn else 0.6)
    pts = [(m_ + i * (W - 2 * m_) / (n - 1), m_ + top[i]) for i in range(n)]
    pts += [(W - m_ + rig[i], m_ + i * (H - 2 * m_) / (n - 1)) for i in range(n)]
    pts += [(W - m_ - i * (W - 2 * m_) / (n - 1), H - m_ + bot[i]) for i in range(n)]
    pts += [(m_ + lef[i], H - m_ - i * (H - 2 * m_) / (n - 1)) for i in range(n)]
    d.polygon(pts, fill=255)
    if torn:                                   # a corner torn away
        c = [(W - m_, H * 0.72), (W - m_, H), (W * 0.62, H)]
        jag = [(W * 0.62 + t * (W * 0.38) + rnd.normal(0, 6 * SS), H - t * H * 0.28 + rnd.normal(0, 6 * SS)) for t in np.linspace(0, 1, 18)]
        d.polygon([(W, H)] + jag, fill=0)
    for (cx, cy) in ((m_, m_), (W - m_, m_), (m_, H - m_), (W - m_, H - m_)):
        d.ellipse((cx - 5 * SS, cy - 5 * SS, cx + 5 * SS, cy + 5 * SS), fill=None)
    return m.filter(ImageFilter.GaussianBlur(0.7 * SS))

def ink_layer():
    return Image.new("L", (W, H), 0)

def _letter(kind, x, y, w, xh, rnd):
    """one cursive letter's path, upright (the caller slants it): x at its entry, y the baseline, xh the x-height"""
    t = np.linspace(0, 1, 9)
    if kind == "n":    # a hump
        return [(x + w * u, y - xh * math.sin(math.pi * u) ** 0.7) for u in t]
    if kind == "m":
        return [(x + w * 1.5 * u, y - xh * abs(math.sin(2 * math.pi * u)) ** 0.7) for u in t]
    if kind == "u":    # a cup
        return [(x + w * u, y - xh * (1 - math.sin(math.pi * u) ** 0.8)) for u in t]
    if kind == "o":    # a loop
        return [(x + w * 0.5 - w * 0.45 * math.cos(2 * math.pi * u + 0.6), y - xh * 0.5 - xh * 0.5 * math.sin(2 * math.pi * u + 0.6)) for u in t] + [(x + w, y - xh * 0.7)]
    if kind == "e":
        return [(x, y - xh * 0.3), (x + w * 0.7, y - xh * 0.8), (x + w * 0.3, y - xh), (x + w * 0.05, y - xh * 0.4), (x + w * 0.4, y), (x + w, y - xh * 0.25)]
    if kind == "l":    # an ascender loop
        a_ = xh * rnd.uniform(1.9, 2.4)
        return [(x, y - xh * 0.2), (x + w * 0.6, y - a_ * 0.75), (x + w * 0.45, y - a_), (x + w * 0.2, y - a_ * 0.7), (x + w * 0.35, y), (x + w, y - xh * 0.3)]
    if kind == "g":    # a descender loop
        d_ = xh * rnd.uniform(0.9, 1.3)
        return [(x + w * 0.8, y - xh), (x + w * 0.2, y - xh * 0.8), (x + w * 0.3, y - xh * 0.1), (x + w * 0.8, y - xh * 0.8), (x + w * 0.7, y + d_), (x + w * 0.2, y + d_ * 0.6), (x + w, y - xh * 0.2)]
    if kind == "t":
        a_ = xh * 1.7
        return [(x, y - xh * 0.2), (x + w * 0.45, y - a_), (x + w * 0.3, y), (x + w, y - xh * 0.3)]
    return [(x + w * u, y - xh * 0.35 * u) for u in t]          # a joining stroke

LETTERS = "nnmuuooeeelltgr"
def scrawl(d, x0, x1, y, h, rnd, width=2.0, bold=False, words=True):
    """a line of illegible hand: joined letters in words, slanted, the baseline drifting a little"""
    x = x0; xh = h * SS * 0.62; slant = 0.32
    base = y + rnd.uniform(-1.5, 1.5) * SS
    while x < x1 - 20 * SS:
        nl = int(rnd.integers(2, 9))
        pts = []
        for k in range(nl):
            kind = LETTERS[int(rnd.integers(0, len(LETTERS)))]
            w = xh * rnd.uniform(0.75, 1.1) * (1.5 if kind == "m" else 1)
            for (px, py) in _letter(kind, x, base, w, xh, rnd):
                pts.append((px + (base - py) * slant, py))
            x += w
            if x > x1: break
        if len(pts) > 1:
            d.line(pts, fill=255, width=max(1, int(width * SS * (1.5 if bold else 1))), joint="curve")
            if rnd.random() < 0.25:            # a crossed t or a dot
                cx = pts[len(pts) // 2][0]; d.line([(cx - 5 * SS, base - xh * 1.3), (cx + 6 * SS, base - xh * 1.4)], fill=255, width=max(1, int(width * SS * 0.8)))
        x += rnd.uniform(0.9, 1.6) * xh
        base += rnd.uniform(-0.6, 0.6) * SS

def body_text(d, x0, x1, y0, lines, rnd, h=13, gap=27):
    for i in range(lines):
        end = x1 if i < lines - 1 else x0 + (x1 - x0) * rnd.uniform(0.35, 0.7)
        scrawl(d, x0 + (rnd.uniform(0, 12) if i == 0 else 0) * SS, end, y0 + i * gap * SS, h, rnd)

def headline(d, cx, y, w, rnd):
    scrawl(d, cx - w / 2 * SS, cx + w / 2 * SS, y, 22, rnd, width=2.6, bold=True)
    d.line([(cx - w * 0.42 * SS, y + 14 * SS), (cx + w * 0.42 * SS, y + 12 * SS)], fill=200, width=int(1.6 * SS))   # underline

def coin(d, x, y, r, rnd):
    """the reward: a little stack of septims and a figure"""
    r *= SS
    for k in range(3):
        yy = y + r * 0.55 - k * r * 0.32
        d.ellipse((x - r, yy - r * 0.42, x + r, yy + r * 0.42), outline=255, width=int(2.0 * SS))
        if k < 2: d.line([(x - r, yy), (x - r, yy - r * 0.32)], fill=255, width=int(2.0 * SS)); d.line([(x + r, yy), (x + r, yy - r * 0.32)], fill=255, width=int(2.0 * SS))
    nx = x + r * 1.7
    for k in range(int(rnd.integers(2, 5))):        # figures: short strokes and loops
        kind = int(rnd.integers(0, 3))
        if kind == 0: d.line([(nx, y + r * 0.8), (nx + 4 * SS, y - r * 0.8)], fill=255, width=int(2.4 * SS))
        elif kind == 1: d.ellipse((nx - 2 * SS, y - r * 0.8, nx + 9 * SS, y + r * 0.8), outline=255, width=int(2.2 * SS))
        else: d.arc((nx - 2 * SS, y - r * 0.8, nx + 10 * SS, y + r * 0.2), 180, 30, fill=255, width=int(2.2 * SS)); d.line([(nx + 9 * SS, y - r * 0.2), (nx, y + r * 0.8), (nx + 11 * SS, y + r * 0.8)], fill=255, width=int(2.2 * SS))
        nx += 15 * SS

def sketch(name, box, rnd, hatch=1.0):
    """the quarry, as a clerk's pen sketch: ink outline, hatching where the model is dark"""
    sd = os.path.join(HERE, "sketches", name)
    ln = Image.open(os.path.join(sd, "lines.png")).convert("RGBA")
    sh = Image.open(os.path.join(sd, "shade.png")).convert("RGBA")
    a = np.asarray(sh.getchannel("A"), np.float32) / 255.0
    ys, xs = np.nonzero(a > 0.05)
    la = np.asarray(ln.getchannel("A"), np.float32) / 255.0
    ly, lx = np.nonzero(la > 0.05)
    x0, x1 = min(xs.min(), lx.min()), max(xs.max(), lx.max()); y0, y1 = min(ys.min(), ly.min()), max(ys.max(), ly.max())
    pad = 8
    crop = (max(0, x0 - pad), max(0, y0 - pad), min(a.shape[1], x1 + pad), min(a.shape[0], y1 + pad))
    ln, sh = ln.crop(crop), sh.crop(crop)
    bw, bh = box[2] - box[0], box[3] - box[1]
    k = min(bw / ln.size[0], bh / ln.size[1])
    size = (max(1, int(ln.size[0] * k)), max(1, int(ln.size[1] * k)))
    ln = ln.resize(size, Image.LANCZOS); sh = sh.resize(size, Image.LANCZOS)
    L = np.asarray(sh.convert("L"), np.float32) / 255.0; A = np.asarray(sh.getchannel("A"), np.float32) / 255.0
    dark = np.clip((0.86 - L) / 0.5, 0, 1) * A
    yy, xx = np.mgrid[0:size[1], 0:size[0]].astype(np.float32)
    wob = 2.0 * SS * np.sin(yy / (37.0 * SS)) + 1.5 * SS * np.sin(xx / (23.0 * SS) + 1.3)
    sp = 6.0 * SS
    def lines_at(u):
        dist = np.abs(((u + wob) / sp) % 1.0 - 0.5) * 2           # 0 on a line's centre
        return np.clip((0.35 - dist) / 0.12, 0, 1)
    h1 = lines_at(xx + yy) * np.clip((dark - 0.18) / 0.12, 0, 1)
    h2 = lines_at(xx - yy) * np.clip((dark - 0.5) / 0.12, 0, 1)
    h3 = lines_at(xx * 0.3 + yy * 1.2) * np.clip((dark - 0.78) / 0.1, 0, 1)
    hatch_a = np.clip(h1 + h2 + h3, 0, 1) * 0.8 * hatch
    wash = dark * 0.14
    outline = np.asarray(ln.getchannel("A").filter(ImageFilter.MaxFilter(3)), np.float32) / 255.0
    ink = np.clip(np.maximum(outline, hatch_a) + wash, 0, 1)
    m = Image.fromarray((ink * 255).astype(np.uint8), "L")
    out = Image.new("L", (W, H), 0)
    out.paste(m, (box[0] + (bw - size[0]) // 2, box[1] + (bh - size[1]) // 2))
    return out

def stamp(rank, cx, cy, r, rot, rnd):
    """the rank stamped in its badge's colour: a double ring, a dotted ring, the letter; the ink uneven"""
    S = int(r * 2.4 * SS); im = Image.new("L", (S, S), 0); d = ImageDraw.Draw(im); c = S / 2; R = r * SS
    d.ellipse((c - R, c - R, c + R, c + R), outline=255, width=int(4.5 * SS))
    d.ellipse((c - R * 0.86, c - R * 0.86, c + R * 0.86, c + R * 0.86), outline=255, width=int(1.6 * SS))
    for k in range(36):
        t = 2 * math.pi * k / 36; rr = R * 0.93
        d.ellipse((c + rr * math.cos(t) - 1.4 * SS, c + rr * math.sin(t) - 1.4 * SS, c + rr * math.cos(t) + 1.4 * SS, c + rr * math.sin(t) + 1.4 * SS), fill=255)
    f = ImageFont.truetype(FONT, int(R * 1.15))
    bb = d.textbbox((0, 0), rank, font=f)
    d.text((c - (bb[0] + bb[2]) / 2, c - (bb[1] + bb[3]) / 2 - R * 0.02), rank, font=f, fill=255)
    for sx in (-1, 1):   # little laurels
        d.line([(c + sx * R * 0.55, c + R * 0.52), (c + sx * R * 0.25, c + R * 0.66)], fill=255, width=int(1.6 * SS))
    im = im.rotate(rot, resample=Image.BICUBIC)
    noise = np.asarray(Image.effect_noise((S, S), 70).filter(ImageFilter.GaussianBlur(2.5 * SS)), np.float32) / 255.0
    press = np.clip((noise - 0.1) * 2.5, 0.55, 1.0)
    a = np.asarray(im, np.float32) / 255.0 * press
    return Image.fromarray((a * 255).astype(np.uint8), "L"), (int(cx * SS - S / 2), int(cy * SS - S / 2))

def blend_ink(base, mask, colour, strength=1.0, bleed=0.6):
    """ink soaked into the paper: multiplied, the paper's grain showing through"""
    m = mask.filter(ImageFilter.GaussianBlur(bleed * SS))
    a = np.asarray(m, np.float32)[..., None] / 255.0 * strength
    b = np.asarray(base, np.float32)
    col = np.array(colour, np.float32)
    lum = b.mean(axis=2, keepdims=True) / 200.0
    out = b * (1 - a) + (col * np.clip(lum, 0.7, 1.15)) * a
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))

SEAL = Image.open(os.path.join(AGTEX, "seal.png")).convert("RGBA")
def seal(base, alpha_spec, cx, cy, size, rot):
    s = SEAL.resize((int(size * SS), int(size * SS)), Image.LANCZOS).rotate(rot, resample=Image.BICUBIC)
    sh = Image.new("RGBA", s.size, (40, 20, 10, 0)); sh.putalpha(s.getchannel("A").filter(ImageFilter.GaussianBlur(4 * SS)).point(lambda v: v * 0.55))
    pos = (int(cx * SS - s.size[0] / 2), int(cy * SS - s.size[1] / 2))
    rgba = base.convert("RGBA"); rgba.alpha_composite(sh, (pos[0] + 3 * SS, pos[1] + 5 * SS)); rgba.alpha_composite(s, pos)
    alpha_spec.paste(s.getchannel("A"), pos, s.getchannel("A"))
    return rgba.convert("RGB")

def jarl_seal(base, alpha_spec, cx, cy, size, rot, rnd):
    """the jarl's own seal (not the guild's): a blob of crimson wax, a ring pressed in it, a crown over a star"""
    S = int(size * SS); c = S / 2
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    ang = np.arctan2(yy - c, xx - c); r = np.hypot(xx - c, yy - c) / (S / 2)
    edge = 0.86 + 0.06 * np.sin(ang * 7 + rnd.uniform(0, 6)) + 0.03 * np.sin(ang * 13)
    blob = np.clip((edge - r) * 30, 0, 1)
    h = np.clip(1 - (r / edge) ** 2, 0, 1) ** 0.5                                     # domed
    ring = np.exp(-((r - 0.6) / 0.035) ** 2)
    m = Image.new("L", (S, S), 0); d = ImageDraw.Draw(m)
    k = S / 100.0
    d.polygon([(c - 18 * k, c + 2 * k), (c - 18 * k, c - 14 * k), (c - 9 * k, c - 5 * k), (c, c - 18 * k), (c + 9 * k, c - 5 * k),
               (c + 18 * k, c - 14 * k), (c + 18 * k, c + 2 * k)], fill=255)                 # a crown
    for t in range(5):                                                                  # a star under it
        a0 = math.pi / 2 + t * 2 * math.pi / 5
        d.line([(c, c + 16 * k), (c + 10 * k * math.cos(a0), c + 16 * k + 10 * k * math.sin(a0))], fill=255, width=max(1, int(2.5 * k)))
    glyph = np.asarray(m.filter(ImageFilter.GaussianBlur(1.2 * k)), np.float32) / 255.0
    h = h - 0.35 * ring - 0.3 * glyph
    gy, gx = np.gradient(h * 6)
    light = np.clip(0.55 + 0.6 * (-gx * 0.6 - gy * 0.8), 0.2, 1.4)
    col = np.array([150, 22, 26], np.float32) * light[..., None]
    col = np.where((h > 0.75)[..., None], col * 1.15, col)
    img = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)); img.putalpha(Image.fromarray((blob * 255).astype(np.uint8)))
    img = img.rotate(rot, resample=Image.BICUBIC)
    sh = Image.new("RGBA", img.size, (40, 20, 10, 0)); sh.putalpha(img.getchannel("A").filter(ImageFilter.GaussianBlur(4 * SS)).point(lambda v: v * 0.55))
    pos = (int(cx * SS - S / 2), int(cy * SS - S / 2))
    rgba = base.convert("RGBA"); rgba.alpha_composite(sh, (pos[0] + 3 * SS, pos[1] + 5 * SS)); rgba.alpha_composite(img, pos)
    alpha_spec.paste(img.getchannel("A"), pos, img.getchannel("A"))
    return rgba.convert("RGB")

# ------------------------------------------------------------------ the twelve notices
# (cell, rank or None, paper, its border px (nine-slice), tint, sketch(es), torn, seal, plain). A sketch is a name, or a
# list of (name, (x0, y0, x1, y1) of the sketch box, 0..1). plain: an ordinary posting (most
# missives are mining, delivering, gathering), its sketch smaller and its hand longer, as Missives' own notes read.
DESIGNS = [
    ("ore", "E", "largenote01", None, (1.02, 1.0, 0.96), [("pickaxe", (0.0, 0.0, 1.0, 0.42)), ("ore", (0.2, 0.36, 0.8, 1.0))], False, False, True),
    ("mudcrab", "E", "largetornpage", None, (1.0, 0.97, 0.9), "mudcrab", True, False, False),
    ("delivery", "D", "largenote01", None, (0.97, 0.94, 0.86), "crate", False, False, True),
    ("bear", "D", "largenote04", 70, (1.0, 0.98, 0.94), "bear", False, False, False),
    ("troll", "C", "largenote02", 70, (1.0, 0.97, 0.9), "troll", False, False, False),
    ("draugr", "A", "largenote01", None, (0.95, 0.9, 0.8), "draugr", False, True, False),       # a deathlord
    ("spider", "D", "largenote04", 70, (1.0, 1.0, 0.97), "spider", False, False, False),        # D, not B
    ("spriggan", "B", "largenote02", 70, (0.98, 0.94, 0.86), "spriggan", False, False, False),
    ("hagraven", "A", "largenote02", 70, (1.0, 0.98, 0.93), "hagraven", False, True, False),
    ("dragon", "S", "largenote02", 70, (1.02, 0.99, 0.94), "dragon", False, True, False),
    ("jarl", "B", "largenote02", 70, (1.03, 0.99, 0.92), "helmet", False, False, True),            # the jarl's bounty: a sealed decree
    ("halves", None, "largenote01", None, (0.98, 0.95, 0.88), None, False, False, True),
]
# the halves' cell: two half-sheets, each its own small posting
HALVES = [("ingredients", "E", [("bearclaws", (0.0, 0.05, 0.62, 0.7)), ("taproot", (0.45, 0.3, 1.0, 1.0))]),
          ("soulgems", "C", [("soulgem", (0.15, 0.0, 0.85, 1.0))])]

def sketches(spec, box, rnd):
    """one sketch in the box, or several, each in its part of it"""
    if isinstance(spec, str): return sketch(spec, box, rnd)
    out = ink_layer()
    bx0, by0, bx1, by1 = box
    for name, (fx0, fy0, fx1, fy1) in spec:
        sub = (int(bx0 + (bx1 - bx0) * fx0), int(by0 + (by1 - by0) * fy0), int(bx0 + (bx1 - bx0) * fx1), int(by0 + (by1 - by0) * fy1))
        out = ImageChops.lighter(out, sketch(name, sub, rnd))
    return out

SINGLE = os.path.join(OUT, "single"); LAYERS = os.path.join(OUT, "layers")
for d_ in (SINGLE, os.path.join(LAYERS, "sketches"), os.path.join(LAYERS, "stamps"), os.path.join(LAYERS, "hand")): os.makedirs(d_, exist_ok=True)
def save_ink(mask, colour, path):
    """an ink layer alone, on transparency, cropped to what it holds"""
    bb = mask.getbbox()
    if not bb: return
    m = mask.crop(bb); im = Image.new("RGBA", m.size, (*colour, 0)); im.putalpha(m); im.save(path)
for r_, col_ in RANK_INK.items():
    st_, _ = stamp(r_, 0, 0, 60, 0, np.random.default_rng(7)); save_ink(st_, col_, os.path.join(LAYERS, "stamps", f"rank_{r_}.png"))
TALL = {"draugr", "hagraven", "spriggan", "troll"}
atlas = Image.new("RGBA", (ATLAS, ATLAS), (0, 0, 0, 0))
atlas_spec = Image.new("L", (ATLAS, ATLAS), 0)
atlas_h = Image.new("L", (ATLAS, ATLAS), 0)
meta = []
for idx, (name, rank, pap, border, tint, sk, torn, has_seal, plain) in enumerate(DESIGNS):
    rnd = np.random.default_rng(100 + idx); random.seed(100 + idx)
    base = paper(pap, tint, border * SS // 2 if border else None, idx)
    mg = (78 if border else 44)                      # margins inside a border
    ink = ink_layer(); d = ImageDraw.Draw(ink)
    spec = Image.new("L", (W, H), 0)
    if name == "halves":
        # two half-sheets, each a small ordinary posting: a headline, its rank, a small sketch, a few lines, the reward
        ink_sk = ink_layer(); stamps = []
        for k, (hname, hrank, hsk) in enumerate(HALVES):
            y0 = k * H // 2
            headline(d, W // 2 - 40 * SS, y0 + 52 * SS, 190, rnd)
            box = (40 * SS, y0 + 86 * SS, 215 * SS, y0 + 290 * SS)
            ink_sk = ImageChops.lighter(ink_sk, sketches(hsk, box, rnd))
            for i_ in range(6):
                scrawl(d, 232 * SS, (CW - 40) * SS if i_ < 5 else 380 * SS, y0 + (112 + i_ * 27) * SS, 12, rnd)
            coin(d, 250 * SS, y0 + 300 * SS, 12, rnd)
            stamps.append((hrank, CW - 70, k * CH // 2 + 54))
        base = blend_ink(base, ink, INK, 0.9)
        base = blend_ink(base, ink_sk, (40, 28, 20), 0.95, 0.4)
        for hrank, sx, sy in stamps:
            st, pos = stamp(hrank, sx + rnd.uniform(-5, 5), sy, 34, rnd.uniform(-16, 16), rnd)
            m = Image.new("L", (W, H), 0); m.paste(st, pos); base = blend_ink(base, m, RANK_INK[hrank], 1.0, 0.3)
        alpha = Image.new("L", (W, H), 0)
        for k in range(2):
            a_ = deckle(500 + k, torn=(k == 1)).resize((W, H // 2))
            alpha.paste(a_, (0, k * H // 2))
        ink = ImageChops.lighter(ink, ink_sk)
    else:
        top = mg   # the decree's paper has a wax seal at its head: the hand starts below it
        headline(d, W // 2 - (30 * SS if rank else 0), (top + 40) * SS, 250, rnd)
        tall = isinstance(sk, str) and sk in TALL     # upright subjects get a taller sketch and fewer lines
        sh = 175 if plain else (330 if tall else 270)
        box = ((mg + (40 if plain else 0)) * SS, (top + 80) * SS, (CW - mg - (40 if plain else 0)) * SS, (top + 80 + sh) * SS)
        ink_sk = sketches(sk, box, rnd) if sk else ink_layer()
        lines = (6 if not border else 4) if plain else ((2 if tall else 4) if border else (3 if tall else 5))
        if name == "jarl": lines = 3
        body_text(d, mg * SS, (CW - mg) * SS, (top + 80 + sh + 45) * SS, lines, rnd)
        coin(d, (mg + 22) * SS, (CH - mg - 34) * SS, 14, rnd)
        base = blend_ink(base, ink, INK, 0.92)
        base = blend_ink(base, ink_sk, (40, 28, 20), 0.95, 0.4)
        if rank:
            st, pos = stamp(rank, CW - mg - 52 + rnd.uniform(-6, 6), top + 50 + rnd.uniform(-4, 4), 50, rnd.uniform(-16, 16), rnd)
            m = Image.new("L", (W, H), 0); m.paste(st, pos)
            base = blend_ink(base, m, RANK_INK[rank], 1.0, 0.3)
        if has_seal:
            base = seal(base, spec, CW - mg - 50, CH - mg - 52, 112, rnd.uniform(-20, 20))
        if name == "jarl":                               # the jarl's seal at its foot, below the hand
            base = jarl_seal(base, spec, CW / 2 + 40, CH - mg - 70, 118, rnd.uniform(-15, 15), rnd)
        alpha = deckle(idx, torn)
        if isinstance(sk, str): save_ink(ink_sk, (40, 28, 20), os.path.join(LAYERS, "sketches", f"{sk}.png"))
        ink = ImageChops.lighter(ink, ink_sk)
    # age: darker toward the edges, a few stains
    a = np.asarray(base, np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    vign = 1 - 0.12 * (np.abs(xx / W - 0.5) * 2) ** 3 - 0.12 * (np.abs(yy / H - 0.5) * 2) ** 3
    a *= vign[..., None]
    base = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    rgba = base.convert("RGBA"); rgba.putalpha(alpha)
    rgba.save(os.path.join(SINGLE, f"{idx:02d}_{(rank or 'x')}_{name}.png"))
    col, row = idx % 4, idx // 4
    ox, oy = col * CW, row * CH
    atlas.paste(rgba.resize((CW, CH), Image.LANCZOS), (ox, oy))
    atlas_spec.paste(spec.resize((CW, CH), Image.LANCZOS), (ox, oy))
    # height for the normal map: the paper's own grain, the ink a touch raised, the seal domed
    lum = base.convert("L").filter(ImageFilter.GaussianBlur(1.2 * SS))
    hgt = ImageChops.add(lum.point(lambda v: v * 0.5), ink.point(lambda v: v * 0.15))
    hgt = ImageChops.lighter(hgt, spec.filter(ImageFilter.GaussianBlur(6 * SS)))
    atlas_h.paste(hgt.resize((CW, CH), Image.LANCZOS), (ox, oy))
    u0, v0, u1, v1 = ox / ATLAS, 1 - (oy + CH) / ATLAS, (ox + CW) / ATLAS, 1 - oy / ATLAS
    meta.append({"cell": idx, "name": name, "rank": rank, "uv": [u0, v0, u1, v1], "paper": pap, "seal": has_seal, "torn": torn})
    print("notice", idx, name, rank)

# dilate colour under the transparent edges (mips must not pull black in)
arr = np.asarray(atlas, np.float32)
rgb, al = arr[..., :3], arr[..., 3] / 255.0
blur_rgb = np.asarray(Image.fromarray(rgb.astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), np.float32)
blur_a = np.asarray(Image.fromarray((al * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), np.float32)[..., None] / 255.0
fill = np.where(blur_a > 0.01, blur_rgb / np.maximum(blur_a, 0.01), 200)
rgb = np.where(al[..., None] > 0.5, rgb, fill)
out = np.concatenate([np.clip(rgb, 0, 255), arr[..., 3:4]], axis=2).astype(np.uint8)
Image.fromarray(out, "RGBA").save(os.path.join(OUT, "AGBoardNotices.png"))
# normal from height (Blender's/our convention here: green up; the DDS step flips it for the game)
h = np.asarray(atlas_h, np.float32) / 255.0
gx = np.roll(h, -1, 1) - np.roll(h, 1, 1); gy = np.roll(h, -1, 0) - np.roll(h, 1, 0)
k = 2.2
n = np.stack([-gx * k, gy * k, np.ones_like(h)], axis=2); n /= np.linalg.norm(n, axis=2, keepdims=True)
spec = np.asarray(atlas_spec, np.float32) / 255.0 * 0.7 + 0.08
nimg = np.concatenate([(n * 0.5 + 0.5) * 255, spec[..., None] * 255], axis=2)
Image.fromarray(np.clip(nimg, 0, 255).astype(np.uint8), "RGBA").save(os.path.join(OUT, "AGBoardNotices_n.png"))
for k in range(4):
    hm = Image.new("L", (W, 200 * SS), 0); hd = ImageDraw.Draw(hm)
    body_text(hd, 20 * SS, (CW - 20) * SS, 30 * SS, 6, np.random.default_rng(900 + k))
    save_ink(hm, INK, os.path.join(LAYERS, "hand", f"hand_{k}.png"))
json.dump({"atlas": ATLAS, "cell": [CW, CH], "notices": meta}, open(os.path.join(OUT, "notices.json"), "w"), indent=1)
pv = Image.new("RGB", (ATLAS, ATLAS), (70, 50, 35)); pv.paste(Image.fromarray(out, "RGBA"), (0, 0), Image.fromarray(out, "RGBA"))
pv.resize((1024, 1024), Image.LANCZOS).save(os.path.join(OUT, "preview.jpg"), quality=88)
print("wrote", OUT)
