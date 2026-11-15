"""The board's textures, as the game reads them (textures/AdventurersGuild/Board/, BC7 with a full mip chain; normals
in the game's convention, green down as vanilla's, the specular mask in alpha):
  AGBoardOak      the frame's oak: the hall's beam (AGH2Beam, Solitude's swoodbeam01 warmed), graded to aged oak; tiles
  AGBoardPlanks   the field's boards: the hall's floorboards (AGH2Boards, Whiterun's), darker so the paper reads; tiles
  AGBoardDetail   one atlas (board_layout.py): the hall's relief crest, the six rank badges (badge_maps.py), hammered
                  iron, Whiterun's carved knotwork band for the sign board, the dragon head (head_bake.py), the roundel
  AGBoardNotices  the notices (notices/make_notices.py), alpha-tested; its mips keep their alpha coverage
    python board_textures.py <out dir: .../textures/AdventurersGuild/Board> [preview dir] [crest=wood|cast]"""
import os, sys, subprocess, tempfile, shutil, json
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__))
PRIV = os.path.join(HERE, "..", "..", "hall-private", "board")   # (its inputs made from the game's files or not ours to publish: tools/hall-private)
sys.path.insert(0, HERE)
import board_layout as BL
POS = [a for a in sys.argv[1:] if "=" not in a]; OPT = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
OUT = POS[0]; PV = POS[1] if len(POS) > 1 else os.path.join(PRIV, "maps", "atlas")
os.makedirs(OUT, exist_ok=True); os.makedirs(PV, exist_ok=True)
# (the AI disclosure audit: the asset packs' textures replace the upscaled ones, which did not look
# good) the board's wood and iron from the textures session's re-sourced set (Vanilla Remastered Ultimate's colour, the 10-27 grade matched to
# the old files' mean, HallSpike 1f2b84c), not assets/...Hall2, which is make_hall_textures.py's Real-ESRGAN output and is not to be used again
HALL = os.path.join(HERE, "..", "..", "..", "build", "materials-c", "board-src")
CREST = os.path.join(HERE, "..", "..", "hall-private", "assets", "crest3d", "textures")
TEXCONV = "C:/Games/steamapps/common/SkyrimVR/tools/texconv/texconv.exe"

def load(path, mode="RGB"):
    return Image.open(path).convert(mode)

def f32(im): return np.asarray(im, np.float32) / 255.0

def rs(im, size):
    """resize; RGB and alpha apart (PIL resizes RGBA premultiplied, so a map keeping specular in alpha loses its RGB
    wherever the alpha is 0)"""
    if im.mode != "RGBA": return im.resize(size, Image.LANCZOS)
    rgb = im.convert("RGB").resize(size, Image.LANCZOS); a = im.getchannel("A").resize(size, Image.LANCZOS)
    rgb.putalpha(a); return rgb
def u8(a): return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))

def grade(a, tint=(1, 1, 1), bright=1.0, flat=0.0):
    """in linear light: flatten toward the mean (flat), tint, brighten"""
    lin = a ** 2.2
    m = lin.reshape(-1, 3).mean(0)
    lin = lin * (1 - flat) + m * flat
    lin = lin * np.array(tint) * bright
    return np.clip(lin, 0, 1) ** (1 / 2.2)

def dds(png, fmt="BC7_UNORM", coverage=None):
    args = [TEXCONV, "-nologo", "-y", "-f", fmt, "-m", "0", "-o", OUT]
    if coverage is not None: args += ["--keep-coverage", str(coverage)]
    r = subprocess.run(args + [png], capture_output=True, text=True)
    if r.returncode: sys.exit(r.stdout + r.stderr)
    print("dds", os.path.basename(png), fmt)

def normal_out(n, spec):
    """n: unit normals (x right, y up: Blender's convention) -> the game's (green down), spec in alpha"""
    n = n / np.maximum(1e-6, np.linalg.norm(n, axis=-1, keepdims=True))
    rgb = n * 0.5 + 0.5; rgb[..., 1] = 1 - rgb[..., 1]
    return np.concatenate([rgb, spec[..., None]], axis=-1)

def game_n(path, size=None):
    """a game-convention normal map (vanilla's, green down) as Blender-convention unit normals + its spec"""
    im = load(path, "RGBA")
    if size: im = rs(im, size)
    a = f32(im); n = a[..., :3] * 2 - 1; n[..., 1] *= -1
    return n, a[..., 3]

def save_pair(name, col, nrm, coverage=None, alpha=None):
    pc = os.path.join(TMP, name + ".png"); pn = os.path.join(TMP, name + "_n.png")
    if alpha is not None: col = np.concatenate([col, alpha[..., None]], axis=-1)
    Image.fromarray((np.clip(col, 0, 1) * 255 + 0.5).astype(np.uint8)).save(pc)
    Image.fromarray((np.clip(nrm, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(pn)
    for p in (pc, pn): shutil.copy(p, PV)
    dds(pc, coverage=coverage); dds(pn)

TMP = tempfile.mkdtemp(prefix="agboard_")

# ---------------------------------------------------------------- the tiling woods
OAK_CLEAN = (1432, 2000)          # AGH2Beam's rows with no plank seam or end-grain square: one clean block of oak
OAK_GRADE = dict(tint=(1.12, 0.93, 0.74), bright=0.62, flat=0.35)   # darker, warmer: the crest's gold reads on it
oak = grade(f32(load(os.path.join(HALL, "AGH2Beam.dds"))), **OAK_GRADE)
n, sp = game_n(os.path.join(HALL, "AGH2Beam_n.dds"))
save_pair("AGBoardOak", oak, normal_out(n, sp))
planks = grade(f32(load(os.path.join(HALL, "AGH2Boards.dds"))), tint=(1.06, 0.95, 0.84), bright=0.72, flat=0.15)
n, sp = game_n(os.path.join(HALL, "AGH2Boards_n.dds"))
save_pair("AGBoardPlanks", planks, normal_out(n, sp))

# ---------------------------------------------------------------- the detail atlas
S = BL.SIZE
col = np.zeros((S, S, 3), np.float32); nrm = np.zeros((S, S, 3), np.float32); nrm[..., 2] = 1; spec = np.full((S, S), 0.2, np.float32)
def put(rect, c, n=None, s=None):
    x0, y0, x1, y1 = rect
    col[y0:y1, x0:x1] = c
    if n is not None: nrm[y0:y1, x0:x1] = n
    if s is not None: spec[y0:y1, x0:x1] = s
def size(rect): return (rect[2] - rect[0], rect[3] - rect[1])

def crest_carved(w, h, n_):
    """v5: the crest carved in the board's oak, as the dragon heads are, so it all reads as carved wood. The oak
    laid flat across the whole crest as one block, its grain running across like the sign board's; darkened in the
    hollows (occlusion from the relief's height seen from the front, cavity from its normal map); the cast colours gone.
    -> colour (h, w, 3), with the texels no triangle uses left black (filled from their neighbours below); and the relief's
       height seen from the front (grid G: column (x + 125) / G, row (150 - y) / G, crest units), for the roundel's field"""
    from scipy import ndimage
    cr = json.load(open(os.path.join(HERE, "..", "..", "hall-private", "assets", "crest3d", "crest_low.json")))
    V = np.array(cr["v"], np.float32); F = np.array(cr["f"]); UV = np.array(cr["uv"], np.float32)
    pos = np.zeros((h, w, 3), np.float32); used = np.zeros((h, w), bool)
    for f, t in zip(F, UV):                                  # each UV triangle rasterised: the crest point at each texel
        P = np.stack([t[:, 0] * w, (1 - t[:, 1]) * h], -1)
        x0, y0 = np.maximum(np.floor(P.min(0)).astype(int) - 1, 0); x1, y1 = np.minimum(np.ceil(P.max(0)).astype(int) + 1, (w, h))
        if x1 <= x0 or y1 <= y0: continue
        ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32) + 0.5
        (ax, ay), (bx, by), (cx, cy) = P
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-9: continue
        l0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d
        l1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
        l2 = 1 - l0 - l1
        ins = (l0 > -0.02) & (l1 > -0.02) & (l2 > -0.02)
        p = l0[..., None] * V[f[0]] + l1[..., None] * V[f[1]] + l2[..., None] * V[f[2]]
        pos[y0:y1, x0:x1][ins] = p[ins]; used[y0:y1, x0:x1] |= ins
    # occlusion: the relief's height from the front (a grid of 0.5 crest units), its blur above a texel = how sunk it is
    G = 0.5; gx = ((pos[..., 0] + 125) / G).astype(int); gy = ((150 - pos[..., 1]) / G).astype(int)
    Hf = np.zeros((int(300 / G), int(250 / G)), np.float32)
    np.maximum.at(Hf, (gy[used], gx[used]), pos[..., 2][used])
    Hf = ndimage.grey_closing(Hf, size=5)
    Hb = ndimage.gaussian_filter(Hf, 8)
    sunk = np.clip(Hb[gy, gx] - pos[..., 2], 0, None)
    ao = np.clip(1 - 0.06 * sunk, 0.62, 1.0) * np.clip(0.72 + 0.4 * pos[..., 2] / 21.3, 0, 1.08)
    # cavity: the normal map's curvature, inside the islands only
    div = np.gradient(n_[..., 0], axis=1) - np.gradient(n_[..., 1], axis=0)
    div = ndimage.gaussian_filter(div, 1.0) * ndimage.binary_erosion(used, iterations=2)
    cav = np.clip(1 + 2.5 * np.minimum(div, 0) + 0.6 * np.maximum(div, 0), 0.55, 1.12)
    # the oak, bilinear, laid across: u along x (the beam's grain runs along u), its rows centred on OAK_CLEAN (the
    # beam's widest plank: its seams would cross the crest as dark bands), a little finer than the tiling's 96
    k = 27.0 / 242.0; TILE = 120.0; S2 = oak.shape[0]
    u = (pos[..., 0] * k / TILE + 0.31) % 1 * S2; v = sum(OAK_CLEAN) / 2 - pos[..., 1] * k / TILE * S2
    u0 = np.floor(u).astype(int); v0 = np.floor(v).astype(int); fu = (u - u0)[..., None]; fv = (v - v0)[..., None]
    at = lambda yy, xx: oak[yy % S2, xx % S2]
    wood = (at(v0, u0) * (1 - fu) + at(v0, u0 + 1) * fu) * (1 - fv) + (at(v0 + 1, u0) * (1 - fu) + at(v0 + 1, u0 + 1) * fu) * fv
    wood = (wood * 0.7 + wood.reshape(-1, 3).mean(0) * 0.3) * 1.12        # the grain quieter than the carving, the figures
    c = wood * (ao * cav)[..., None]                                        # standing light off the darker ground
    c[~used] = 0
    return c, Hf, G

# the crest: the hall's approved relief (its own maps, resampled; crest_low.json's UVs are scaled into this rect), its
# colour the cast metal's (crest=cast) or carved in the board's oak (crest=wood, v5)
r = BL.DETAIL["crest"]
n_, s_ = game_n(os.path.join(CREST, "AGCrest_n.dds"), size(r))
CREST_H = None
if OPT.get("crest", "wood") == "wood":
    c, CREST_H, CREST_G = crest_carved(*size(r), n_)
    put(r, c, n_, np.full(size(r)[::-1], 0.2, np.float32))
else:
    put(r, f32(load(os.path.join(CREST, "AGCrest.dds")).resize(size(r), Image.LANCZOS)), n_, s_)

# iron: the hall's metal (its plain hammered half), darkened to wrought iron
r = BL.DETAIL["iron"]
met = load(os.path.join(HALL, "AGH2XMetal.dds")); W_, H_ = met.size
iron_src = met.crop((0, H_ * 6 // 10, W_ // 2, H_)).resize(size(r), Image.LANCZOS)
iron = grade(f32(iron_src), tint=(0.62, 0.6, 0.6), bright=0.55, flat=0.2)
mn = load(os.path.join(HALL, "AGH2XMetal_n.dds"), "RGBA"); w2, h2 = mn.size
a = f32(rs(mn.crop((0, h2 * 6 // 10, w2 // 2, h2)), size(r))); n_ = a[..., :3] * 2 - 1; n_[..., 1] *= -1
put(r, iron, n_, np.full(size(r)[::-1], 0.45, np.float32))
IRON_MEAN = iron.reshape(-1, 3).mean(0)

# the badges: each on a disc of iron behind its fins
for rk in BL.BADGE_ORDER:
    r = BL.badge_rect(rk)
    bc = rs(load(os.path.join(PRIV, "maps", "badges", f"badge_{rk}_c.png"), "RGBA"), size(r))
    bn = rs(load(os.path.join(PRIV, "maps", "badges", f"badge_{rk}_n.png"), "RGBA"), size(r))
    a = f32(bc); al = a[..., 3:4]
    c = a[..., :3] * al + (IRON_MEAN * 0.8) * (1 - al)
    nb = f32(bn)[..., :3] * 2 - 1
    nb = nb * al + np.array([0, 0, 1.0]) * (1 - al)
    put(r, c, nb, (0.55 * al + 0.35 * (1 - al))[..., 0])

# the sign board's face: Whiterun's carved knotwork band, graded to the oak, tiled along
r = BL.DETAIL["knot"]
trim = load(os.path.join(HALL, "AGH2Trim.dds")); tn = load(os.path.join(HALL, "AGH2Trim_n.dds"), "RGBA")
Y0, Y1 = 1212, 1776                                  # the band's rows in the 2048 trim sheet
band = trim.crop((0, Y0, 2048, Y1)); k = tn.size[0] / 2048
bandn = tn.crop((0, int(Y0 * k), tn.size[0], int(Y1 * k)))
h = r[3] - r[1]; w = int(2048 * h / (Y1 - Y0))
band = band.resize((w, h), Image.LANCZOS); bandn = rs(bandn, (w, h))
bc = grade(f32(band), tint=(1.12, 0.98, 0.84), bright=1.25, flat=0.1)
bnf = f32(bandn); bn_ = bnf[..., :3] * 2 - 1; bn_[..., 1] *= -1
for x in range(r[0], r[2], w):
    ww = min(w, r[2] - x)
    put((x, r[1], x + ww, r[3]), bc[:, :ww], bn_[:, :ww], bnf[:, :ww, 3] * 0.6)

# the dragon head: its sides and its rim (head_bake.py), one block over head + headcap
r = (BL.DETAIL["head"][0], BL.DETAIL["head"][1], BL.DETAIL["headcap"][2], BL.DETAIL["headcap"][3])
hc = load(os.path.join(PRIV, "maps", "head", "head_c_full.png")).resize(size(r), Image.LANCZOS)
hn = load(os.path.join(PRIV, "maps", "head", "head_n_full.png")).resize(size(r), Image.LANCZOS)
hcol = grade(f32(hc), **OAK_GRADE)
put(r, hcol, f32(hn) * 2 - 1, np.full(size(r)[::-1], 0.2, np.float32))

# the roundel: oak, a bead and a groove turned round its edge
r = BL.DETAIL["roundel"]; W2 = size(r)[0]
rc = f32(u8(oak[OAK_CLEAN[0]:OAK_CLEAN[1], 600:600 + OAK_CLEAN[1] - OAK_CLEAN[0]]).resize((W2, W2), Image.LANCZOS))
yy, xx = np.mgrid[0:W2, 0:W2].astype(np.float32); cx = cy = (W2 - 1) / 2
rr = np.hypot(xx - cx, yy - cy) / (W2 / 2)
hgt = np.zeros_like(rr)
for r0, wdt, amp in ((0.93, 0.025, 1.0), (0.86, 0.012, -0.8), (0.80, 0.02, 0.7)):
    hgt += amp * np.exp(-((rr - r0) / wdt) ** 2)
gy, gx = np.gradient(hgt * 6.0)
rn = np.stack([-gx, gy, np.ones_like(hgt)], -1)
rc = rc * (1 - 0.25 * np.clip(-hgt, 0, 1)[..., None]) * (1 + 0.08 * np.clip(hgt, 0, 1)[..., None])
if CREST_H is not None:
    # v5, the crest carved: the field it stands out of is the carving's ground, sunk and darker, and shadowed close round
    # the figures, which is how a relief reads in one wood (the face maps x, z onto the rect: board_build.add_disc)
    from scipy import ndimage
    k_, CR_ = 27.0 / 242.0, 15.5
    gx_ = ((((xx - 2) / (W2 - 4) - 0.5) * 2 * CR_ / k_ + 125) / CREST_G).astype(int)
    gy_ = ((150 - (0.5 - (yy - 2) / (W2 - 4)) * 2 * CR_ / k_) / CREST_G).astype(int)
    ok = (gx_ >= 0) & (gy_ >= 0) & (gx_ < CREST_H.shape[1]) & (gy_ < CREST_H.shape[0])
    near = ndimage.gaussian_filter(np.minimum(CREST_H, 8.0), 6) / 8.0       # the figures' height round about, 0..1
    sh_ = np.zeros_like(rr); sh_[ok] = near[gy_[ok], gx_[ok]]
    field = np.clip((0.80 - rr) / 0.02, 0, 1)                                # inside the turned bead
    rc = rc * (1 - field * (0.42 + 0.35 * np.clip(sh_ * 1.6, 0, 1)))[..., None]
put(r, rc, rn, np.full(rr.shape, 0.25, np.float32))

# fill what no part uses with the oak's mean (no black under the islands' edges at small mips)
used = np.zeros((S, S), bool)
for k_, rr_ in BL.DETAIL.items(): used[rr_[1]:rr_[3], rr_[0]:rr_[2]] = True
col[~used] = oak.reshape(-1, 3).mean(0)
# the head's bake has black outside its outline: fill it from its neighbours
blk = (col.sum(-1) < 0.02)
if blk.any():
    fill = np.asarray(Image.fromarray((col * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(24)), np.float32) / 255.0
    for _ in range(3):
        col[blk] = fill[blk]
        blk = (col.sum(-1) < 0.02)
        fill = np.asarray(Image.fromarray((col * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(24)), np.float32) / 255.0
# the wear from past notices (v2), alpha-tested by its own shape (AGBoardWear); every other texel is opaque
alpha = np.ones((S, S), np.float32)
rng = np.random.default_rng(5)
SS4 = 4
def decal(rect, draw):
    """draw(c, a, n) on a 4x canvas: colour (h, w, 3), alpha (h, w), height (h, w); reduced into rect"""
    w, h = size(rect); W4, H4 = w * SS4, h * SS4
    c = np.zeros((H4, W4, 3), np.float32); a = np.zeros((H4, W4), np.float32); hh = np.zeros((H4, W4), np.float32)
    draw(c, a, hh, W4, H4)
    small = lambda x: np.asarray(Image.fromarray((np.clip(x, 0, 1) * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS), np.float32) / 255.0
    cs = np.stack([small(c[..., i]) for i in range(3)], -1); as_ = small(a); hs = small(hh)
    x0, y0, x1, y1 = rect
    col[y0:y1, x0:x1] = np.where(as_[..., None] > 0.02, cs / np.maximum(as_[..., None], 0.02) * np.clip(as_[..., None], 0, 1) + col[y0:y1, x0:x1] * 0, col[y0:y1, x0:x1])
    alpha[y0:y1, x0:x1] = as_
    gy, gx = np.gradient(hs * 3.0); nrm[y0:y1, x0:x1] = np.stack([-gx, gy, np.ones_like(hs)], -1)
    spec[y0:y1, x0:x1] = 0.12
yy4 = lambda H4, W4: np.mgrid[0:H4, 0:W4].astype(np.float32)
WOOD_DARK = np.array([0.10, 0.07, 0.05])
def hole(c, a, hh, W4, H4):
    y, x = yy4(H4, W4); r = np.hypot(x - W4 / 2 + rng.normal(0, 3), y - H4 / 2 + rng.normal(0, 3)) / (W4 / 2)
    ring = np.clip(1 - (r - 0.32) / 0.25, 0, 1) * (rng.random((H4, W4)) > 0.35)     # crushed fibres round it
    core = r < rng.uniform(0.17, 0.24)
    a[:] = np.clip(np.maximum(core, ring * 0.8), 0, 1)
    c[:] = np.where(core[..., None], WOOD_DARK * 0.6, np.array([0.24, 0.17, 0.11]))
    hh[:] = 0.5 - 0.5 * core
def pins(c, a, hh, W4, H4):
    y, x = yy4(H4, W4)
    for _ in range(rng.integers(3, 7)):
        px, py = rng.uniform(0.15, 0.85) * W4, rng.uniform(0.15, 0.85) * H4
        core = np.hypot(x - px, y - py) < W4 * 0.035
        a[core] = 1; c[core] = WOOD_DARK * 0.7; hh[core] = 0
def rust(c, a, hh, W4, H4):
    """rust run down from an old nail: widest under the nail, thinning to a ragged point, blotchy"""
    y, x = yy4(H4, W4); t = y / H4                          # 0 at the nail, 1 at the streak's end
    end = rng.uniform(0.55, 0.95)
    wid = np.clip(1 - t / end, 0, 1) ** 0.7 * W4 * rng.uniform(0.16, 0.24)
    wob = np.sin(y / (H4 / 7) + rng.uniform(0, 6)) * W4 * 0.04 + np.sin(y / (H4 / 23)) * W4 * 0.015
    noise = np.asarray(Image.effect_noise((W4, H4), 90).filter(ImageFilter.GaussianBlur(3)), np.float32) / 255.0
    edge = np.abs(x - W4 / 2 - wob) / np.maximum(wid, 1e-3)              # 0 on the streak's line, 1 at its edge
    m = (edge < 0.6 + 0.8 * (noise - 0.5)) & (t < end)
    a[:] = m
    c[:] = np.array([0.34, 0.16, 0.06]) * (1.05 - 0.45 * t[..., None]) * (0.85 + 0.3 * noise[..., None]); hh[:] = 0.5
def scrap(c, a, hh, W4, H4):
    """the top of a notice torn away below its nail: a strip of parchment, its lower edge ragged (the nail is geometry)"""
    src = f32(load(os.path.join(PRIV, "notices", "out", "AGBoardNotices.png")).crop((1560, 1390, 1560 + W4 // 3, 1390 + H4 // 3)).resize((W4, H4)))
    y, x = yy4(H4, W4); cx, cy = W4 / 2, H4 * 0.32
    top = cy - H4 * 0.12; half = W4 * rng.uniform(0.28, 0.42)
    xs = np.arange(W4, dtype=np.float32)
    rag = np.cumsum(rng.normal(0, 2.2, W4)); rag -= np.linspace(rag[0], rag[-1], W4)
    bottom = cy + H4 * rng.uniform(0.12, 0.3) + rag + (xs - cx) * rng.uniform(-0.35, 0.35)   # torn on a slant
    m = (y > top) & (y < bottom[None, :]) & (np.abs(x - cx) < half)
    a[:] = m; c[:] = src * 0.95
    hole_ = np.hypot(x - cx, y - cy) < W4 * 0.05
    c[hole_] = WOOD_DARK; hh[:] = 0.5 + 0.1 * m
for kind, fn in (("hole", hole), ("pins", pins), ("rust", rust), ("scrap", scrap)):
    for rect in BL.wear_cells()[kind]: decal(rect, fn)
# under the cut-out texels, the marks' own colour spread out (a smaller mip must not pull black into their edges)
x0, y0, x1, y1 = BL.DETAIL["wear"]
wa = alpha[y0:y1, x0:x1]; wc = col[y0:y1, x0:x1].copy(); have = wa > 0.5
for _ in range(24):
    if have.all(): break
    acc = np.zeros_like(wc); cnt = np.zeros(wa.shape, np.float32)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        acc += np.roll(np.roll(wc * have[..., None], dy, 0), dx, 1); cnt += np.roll(np.roll(have.astype(np.float32), dy, 0), dx, 1)
    grow = (~have) & (cnt > 0)
    wc[grow] = acc[grow] / cnt[grow][..., None]; have = have | grow
wc[~have] = np.array([0.24, 0.17, 0.11])
col[y0:y1, x0:x1] = wc
save_pair("AGBoardDetail", col, normal_out(nrm, spec), alpha=alpha)

# ---------------------------------------------------------------- the notices
NT = os.path.join(PRIV, "notices", "out")
nc = load(os.path.join(NT, "AGBoardNotices.png"), "RGBA"); nn = f32(load(os.path.join(NT, "AGBoardNotices_n.png"), "RGBA"))
pc = os.path.join(TMP, "AGBoardNotices.png"); nc.save(pc); shutil.copy(pc, PV)
nn_ = nn[..., :3] * 2 - 1
pn = os.path.join(TMP, "AGBoardNotices_n.png")
Image.fromarray((np.clip(normal_out(nn_, nn[..., 3]), 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(pn)
dds(pc, coverage=0.5); dds(pn)
shutil.rmtree(TMP)
print("textures in", OUT)
