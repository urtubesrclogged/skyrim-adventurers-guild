"""The leader board's paper, as the game reads it (textures/AdventurersGuild/LeaderBoard/, BC7 with a full mip chain,
alpha-tested, mips keeping their coverage; the normal green down with specular in alpha, as vanilla's).
One 2K atlas: the standings sheet across the top (2048 x 1677, the sheet's 96.7 x 79.2); along the foot the two
scraps, two older sheets (only their edges show, behind the current one), the fresh slip and the strike strokes (the
story pieces, their own NIFs).
The sheet is drawn the way the leader board's page lays it out (leaderboard.html): a dated line at the head, eleven rows
ruled across (a numeral, the party, its leader, the years, the renown), the first three rubricated in red with a red rule
under the third, the disbanded ones fainter. Its rows are the board as it stands before the player has a party, and
it is a worked sheet: the Great War's entries in old,
faded brown ink and this year's in fresh black, an old figure struck and the new one written beside it, a name begun,
struck out and written again, an ink blot, the guild's wax seal and the keeper's mark at the foot. No words: the mod is
translated and a baked word cannot be, so the hand is the Guild Board's illegible scrawl (board/notices/make_notices.py,
whose paper, deckle, scrawl, ink and seal are reused here); only numerals are written as numerals.
    python make_lb_textures.py <vanilla cache: holds textures/clutter/books/largenote01.dds> <AG view tex dir> <out dir>
-> <out>/AGLeaderPaper.dds, AGLeaderPaper_n.dds; previews, the PNGs and maps/lb_layout.json (where the Golden Hand's row
lies on the sheet, for the strike piece) in maps/"""
import sys, os, math, random, shutil, subprocess, tempfile, json
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

VAN, AGTEX, OUT = sys.argv[1], sys.argv[2], os.path.abspath(sys.argv[3])
HERE = os.path.dirname(os.path.abspath(__file__))
PRIV = os.path.join(HERE, "..", "..", "hall-private", "leaderboard")   # (its inputs made from the game's files or not ours to publish: tools/hall-private)
MAPS = os.path.join(PRIV, "maps"); os.makedirs(MAPS, exist_ok=True); os.makedirs(OUT, exist_ok=True)
TEXCONV = "C:/Games/steamapps/common/SkyrimVR/tools/texconv/texconv.exe"
# the notices' helpers, as they are (their module runs a build on import: only its definitions are taken)
src = open(os.path.join(HERE, "..", "board", "notices", "make_notices.py"), encoding="utf-8").read()
g = {"__file__": os.path.join(HERE, "..", "board", "notices", "make_notices.py")}
sys_argv = sys.argv; sys.argv = ["make_notices.py", VAN, AGTEX, tempfile.mkdtemp(prefix="aglb_")]
exec(src[:src.index("DESIGNS = [")], g)
sys.argv = sys_argv
_src = g["paper_src"]
g["paper_src"] = lambda name: _src(name).crop((44, 10, 1012, 1012)) if name == "largenote01" else _src(name)   # its grey left edge off
SS = g["SS"]; INK = g["INK"]
RED = (122, 36, 22)                     # the page's rubric (leaderboard.html tr.top td.no)
OLD = (92, 66, 40)                      # iron-gall ink thirty years on: browned and faded
ATLAS = 2048
SHEET = (0, 0, 2048, 1677)              # 96.7 x 79.2 at 21.2 px a unit
SCRAPS = [(0, 1690, 300, 2006), (330, 1690, 750, 2045)]   # the top scrap (19 x 20) and the bottom one (26 x 22)
OLDS = [(770, 1690, 1180, 2040), (1190, 1690, 1600, 2040)]  # the older sheets under the current one (only edges show)
SLIP = (1610, 1690, 1900, 1930)         # the fresh slip pinned up once the player has a party (16 x 13)
STROKES = [(1610, 1945, 2040, 1985), (1610, 1995, 2040, 2035)]   # a clerk's strike through a name, through a figure
FONT = ImageFont.truetype("C:/Windows/Fonts/palai.ttf", 30 * SS)     # numerals only
FONT_B = ImageFont.truetype("C:/Windows/Fonts/palabi.ttf", 32 * SS)

def sized(w, h):
    """point the notices' helpers at a sheet of w x h (they read W, H as globals)"""
    g["W"], g["H"] = w * SS, h * SS

def numeral(d, x, y, text, font, anchor="ls"):
    d.text((x, y), text, fill=255, font=font, anchor=anchor)

def roman(n):
    out = ""
    for v, r in ((10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v: out += r; n -= v
    return out

def blot(d, x, y, r, rnd):
    """an ink blot: an uneven drop and a few spatters"""
    pts = [(x + r * (1 + rnd.normal(0, 0.18)) * math.cos(a), y + r * (1 + rnd.normal(0, 0.18)) * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 22)]
    d.polygon(pts, fill=255)
    for _ in range(6):
        a = rnd.uniform(0, 2 * math.pi); dd = r * rnd.uniform(1.4, 2.6); s = r * rnd.uniform(0.08, 0.22)
        d.ellipse((x + dd * math.cos(a) - s, y + dd * math.sin(a) - s, x + dd * math.cos(a) + s, y + dd * math.sin(a) + s), fill=255)

# the rows as the board stands before the player has a party (LeaderBoard.cpp: the old parties' scores, the climbing
# parties at their start): (renown, years, active, ink: "old" Great War / "mid" / "new" this year)
ROWS = [(698, "172\u2013174", False, "old"), (587, "172\u2013174", False, "old"), (433, "171\u2013174", False, "old"),
        (341, "196\u2013200", False, "mid"), (289, "196 \u2013", True, "new"), (262, "193\u2013201", False, "new"),
        (193, "197\u2013199", False, "mid"), (157, "199\u2013200", False, "mid"), (143, "198 \u2013", True, "new"),
        (129, "197\u2013201", False, "new"), (121, "200 \u2013", True, "new")]
GOLDEN = 10                              # the Golden Hand's row (the last): the strike piece lies over it
CORRECTED = 4                            # the Grey Lanterns: an old figure struck, the new one beside it
RESTRUCK = 6                             # Curved Swords: the name begun, struck out, written again
LAYOUT = {}

def sheet():
    w, h = SHEET[2] - SHEET[0], SHEET[3] - SHEET[1]; sized(w, h)
    base = g["paper"]("largenote01", (1.0, 0.97, 0.9), None, 0)   # the plain one: 02 and 04 carry printed borders
    rnd = np.random.default_rng(41); random.seed(41)
    fresh = g["ink_layer"](); red = g["ink_layer"](); faint = g["ink_layer"](); old = g["ink_layer"](); oldred = g["ink_layer"]()
    dn, dr, df, do, dor = (ImageDraw.Draw(x) for x in (fresh, red, faint, old, oldred))
    S = SS; mx0, mx1 = 350 * S, (w - 180) * S      # the left 315 px lie under the scraps (lb_build.py SCRAPS)
    # the head: the clerk's dated line, centred, and a short rule under it
    g["scrawl"](df, (w / 2 - 230) * S, (w / 2 + 430) * S, 150 * S, 26, rnd, width=2.2)
    df.line([((w / 2 - 160) * S, 182 * S), ((w / 2 + 360) * S, 179 * S)], fill=170, width=int(1.6 * S))
    # the columns, as the page's: numeral, party, led by, active, renown
    cx = [mx0, mx0 + 105 * S, mx0 + 720 * S, mx0 + 1110 * S, mx1]
    for x0, x1 in ((cx[1], cx[1] + 120 * S), (cx[2], cx[2] + 110 * S), (cx[3], cx[3] + 100 * S)):
        g["scrawl"](df, x0, x1, 242 * S, 15, rnd, width=1.3)
    g["scrawl"](df, cx[4] - 130 * S, cx[4], 242 * S, 15, rnd, width=1.3)
    y = 330; gap = 112
    for i, (score, years, active, ink) in enumerate(ROWS):
        yy = y * S; top = i < 3
        d_ = do if ink == "old" else dn if ink == "new" else df           # the party and its figures, in that row's ink
        dred = dor if ink == "old" else dr
        numeral(dred if top else df, cx[0], yy, roman(i + 1) + ".", FONT_B if top else FONT)
        name_end = cx[1] + rnd.uniform(330, 540) * S
        if i == RESTRUCK:                                                  # begun, struck out, written again after it
            x_ = cx[1] + 150 * S
            g["scrawl"](d_, cx[1], x_, yy, 26, rnd, width=2.6, bold=True)
            d_.line([(cx[1] - 6 * S, yy - 11 * S), (x_ + 6 * S, yy - 13 * S)], fill=255, width=int(2.6 * S))
            name_end = x_ + 30 * S + rnd.uniform(300, 420) * S
            g["scrawl"](d_, x_ + 30 * S, name_end, yy, 26, rnd, width=2.6, bold=True)
        else:
            g["scrawl"](d_, cx[1], name_end, yy, 26, rnd, width=2.6, bold=True)   # the party, in a bolder hand
        if not active: g["scrawl"](do if ink == "old" else df, cx[2], cx[2] + rnd.uniform(200, 280) * S, yy, 17, rnd, width=1.6)   # how it ended, small
        else: g["scrawl"](dn, cx[2], cx[2] + rnd.uniform(210, 300) * S, yy, 22, rnd, width=2.2)          # its leader
        numeral(d_, cx[3], yy, years, FONT)
        numeral(dred if top else d_, cx[4], yy, str(score), FONT_B if top else FONT, anchor="rs")
        if i == CORRECTED:                           # the old figure struck through by hand, the new one beside it
            sx = cx[4] - 150 * S
            numeral(df, sx, yy, str(score - 12), FONT, anchor="rs")
            dn.line([(sx - 60 * S, yy - 8 * S), (sx + 4 * S, yy - 20 * S)], fill=255, width=int(2.4 * S))
        if i == 8:                                   # a blot where the pen was set down, past the leader's name
            blot(dn, cx[2] + 330 * S, yy - 30 * S, 9 * S, rnd)
        if i == GOLDEN:
            LAYOUT["golden"] = {"y": y - 10, "name": [cx[1] / S - 8, name_end / S + 8], "renown": [cx[4] / S - 80, cx[4] / S + 6]}
        rule = dred if i == 2 else df
        rule.line([(mx0, yy + 34 * S), (mx1, yy + 32 * S + rnd.uniform(-2, 2) * S)], fill=200 if i == 2 else 70, width=int((2.0 if i == 2 else 1.1) * S))
        y += gap
    # the foot: the keeper's mark and the guild's wax seal beside it
    g["scrawl"](dn, (w - 760) * S, (w - 420) * S, (y + 40) * S, 22, rnd, width=2.2, bold=True)
    base = g["blend_ink"](base, faint, INK, 0.62)
    base = g["blend_ink"](base, old, OLD, 0.7)
    base = g["blend_ink"](base, oldred, RED, 0.55)
    base = g["blend_ink"](base, fresh, INK, 0.97)
    base = g["blend_ink"](base, red, RED, 0.92)
    spec = Image.new("L", (w * SS, h * SS), 0)
    base = g["seal"](base, spec, w - 300, min(h - 110, y + 30), 120, -14)
    ink_all = ImageChops.lighter(ImageChops.lighter(ImageChops.lighter(fresh, red), faint.point(lambda v: v * 0.6)), old.point(lambda v: v * 0.6))
    LAYOUT["sheet"] = {"w": w, "h": h}
    return age(base, w, h, 0.12), g["deckle"](7), ImageChops.lighter(ink_all, spec)

def scrap(rect, seed, lines, tint=(1.03, 1.0, 0.94), colour=INK, strength=0.9, aged=0.12, torn=None):
    w, h = rect[2] - rect[0], rect[3] - rect[1]; sized(w, h)
    base = g["paper"]("largenote01", tint, None, seed)
    rnd = np.random.default_rng(seed); random.seed(seed)
    ink = g["ink_layer"](); d = ImageDraw.Draw(ink)
    step = max(40, (h - 100) / max(1, lines))
    for k in range(lines):
        end = w - 40 if k < lines - 1 else w * rnd.uniform(0.4, 0.7)
        g["scrawl"](d, 36 * SS, end * SS, (70 + k * step) * SS, 20, rnd, width=2.0)
    base = g["blend_ink"](base, ink, colour, strength)
    return age(base, w, h, aged), g["deckle"](seed, torn=(seed % 2 == 0) if torn is None else torn), ink

def stroke(rect, seed):
    """a clerk's line through an entry: one quick stroke of the pen, heavier where it starts, lifting at the end, on
    nothing (transparent round it)"""
    w, h = rect[2] - rect[0], rect[3] - rect[1]; W, H = w * SS, h * SS
    rnd = np.random.default_rng(seed)
    m = Image.new("L", (W, H), 0); d = ImageDraw.Draw(m)
    n = 40; xs = np.linspace(10 * SS, W - 10 * SS, n)
    ys = H / 2 + np.cumsum(rnd.normal(0, 0.35 * SS, n)) + np.linspace(2 * SS, -2 * SS, n)
    for k in range(n - 1):
        t = k / (n - 1); wd = (4.2 - 2.0 * t) * SS
        d.line([(xs[k], ys[k]), (xs[k + 1], ys[k + 1])], fill=255, width=max(1, int(wd)))
    m = m.filter(ImageFilter.GaussianBlur(0.6 * SS))
    col = Image.new("RGB", (W, H), INK)
    return col, m, m

def age(base, w, h, k=0.12):
    a = np.asarray(base, np.float32); W, H = w * SS, h * SS
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    a *= (1 - k * (np.abs(xx / W - 0.5) * 2) ** 3 - k * (np.abs(yy / H - 0.5) * 2) ** 3)[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

atlas = Image.new("RGBA", (ATLAS, ATLAS), (0, 0, 0, 0)); atlas_h = Image.new("L", (ATLAS, ATLAS), 0)
parts = [(SHEET, sheet())] + [(r, scrap(r, 60 + i, (4, 3)[i])) for i, r in enumerate(SCRAPS)]
parts += [(OLDS[0], scrap(OLDS[0], 81, 5, (0.95, 0.87, 0.72), OLD, 0.55, 0.3, False)),            # browned, its hand faded
          (OLDS[1], scrap(OLDS[1], 83, 5, (0.92, 0.84, 0.69), OLD, 0.5, 0.35, True))]
parts += [(SLIP, scrap(SLIP, 91, 3, (1.05, 1.04, 1.0), INK, 0.97, 0.05, False))]                    # new paper, fresh ink
parts += [(r, stroke(r, 95 + i)) for i, r in enumerate(STROKES)]
for rect, (base, alpha, ink) in parts:
    w, h = rect[2] - rect[0], rect[3] - rect[1]
    rgba = base.convert("RGBA"); rgba.putalpha(alpha)
    atlas.paste(rgba.resize((w, h), Image.LANCZOS), rect[:2])
    lum = base.convert("L").filter(ImageFilter.GaussianBlur(1.2 * SS))
    hgt = ImageChops.add(lum.point(lambda v: v * 0.5), ink.point(lambda v: v * 0.15))
    atlas_h.paste(hgt.resize((w, h), Image.LANCZOS), rect[:2])
# colour under the transparent edges, so the mips pull no black in (as the notices')
arr = np.asarray(atlas, np.float32); rgb, al = arr[..., :3], arr[..., 3] / 255.0
blur_rgb = np.asarray(Image.fromarray(rgb.astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), np.float32)
blur_a = np.asarray(Image.fromarray((al * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), np.float32)[..., None] / 255.0
rgb = np.where(al[..., None] > 0.5, rgb, np.where(blur_a > 0.01, blur_rgb / np.maximum(blur_a, 0.01), 200))
col = np.concatenate([np.clip(rgb, 0, 255), arr[..., 3:4]], axis=2).astype(np.uint8)
# the normal from the height, in the game's convention (green down), the paper's dull specular in alpha
hh = np.asarray(atlas_h, np.float32) / 255.0
gx = np.roll(hh, -1, 1) - np.roll(hh, 1, 1); gy = np.roll(hh, -1, 0) - np.roll(hh, 1, 0)
n = np.stack([-gx * 2.2, gy * 2.2, np.ones_like(hh)], axis=2); n /= np.linalg.norm(n, axis=2, keepdims=True)
rgbn = n * 0.5 + 0.5; rgbn[..., 1] = 1 - rgbn[..., 1]
nrm = np.concatenate([rgbn * 255, np.full(hh.shape + (1,), 0.08 * 255)], axis=2)
pc, pn = os.path.join(MAPS, "AGLeaderPaper.png"), os.path.join(MAPS, "AGLeaderPaper_n.png")
Image.fromarray(col, "RGBA").save(pc); Image.fromarray(np.clip(nrm, 0, 255).astype(np.uint8), "RGBA").save(pn)
pv = Image.new("RGB", (ATLAS, ATLAS), (70, 50, 35)); pv.paste(Image.fromarray(col, "RGBA"), (0, 0), Image.fromarray(col, "RGBA"))
pv.resize((1024, 1024), Image.LANCZOS).save(os.path.join(MAPS, "preview.jpg"), quality=88)
LAYOUT.update({"atlas": ATLAS, "SHEET": SHEET, "SCRAPS": SCRAPS, "OLDS": OLDS, "SLIP": SLIP, "STROKES": STROKES})
json.dump(LAYOUT, open(os.path.join(MAPS, "lb_layout.json"), "w"), indent=1)
for p, cov in ((pc, 0.5), (pn, None)):
    args = [TEXCONV, "-nologo", "-y", "-f", "BC7_UNORM", "-m", "0", "-o", OUT] + (["--keep-coverage", str(cov)] if cov else [])
    r = subprocess.run(args + [p], capture_output=True, text=True)
    if r.returncode: sys.exit(r.stdout + r.stderr)
print("textures in", OUT)
