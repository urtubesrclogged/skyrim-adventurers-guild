"""The hall's materials, palette C (an Isekai-style adventure guild in Skyrim, a balance of the two): limewash, near-black
timber, honey floors, warm stone, blue slate. Same names as make_hall_textures.py's AGH2*, so the NIFs need no change to take them.

  colour  Vanilla Remastered Ultimate (Nexus 138164, WaqasTopNotch), graded. 4K where it has 4K, else 2K
  normal  The New Normal 4.0.3 (Nexus 140662, disitinerant), down to 2048 on the right sums: averaged as vectors, renormalised
  alpha   its alpha is nearly black (0.01-0.04), so without Community Shaders nothing would catch the light: specular comes from Ultimate's alpha, by SPEC's gain
Both authors allow asset use with credit, not in paid mods. Keep what this makes out of the public repository: they bar other sites.

    python make_materials.py <Ultimate textures dir> <New Normal textures dir> <out dir> [--4k|--built|--board] [name ...]
--4k: colour at the source's own size (only those with a 4K source). Without it, 2048.
--built: the built-in pieces' sets (the hall session's own copies of the bar kit, doors, fireplace, hatches and the wall iron, so they match on every install), by BUILT's sizes: a set's height, as the iron is two by one."""
import os, shutil, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageFilter

TEXCONV = "C:/Games/steamapps/common/SkyrimVR/tools/texconv/texconv.exe"
SOL, WR = "architecture/solitude/", "architecture/whiterun/"

DARK = dict(sat=0.35, tint=(0.66, 0.46, 0.31), bright=0.86, flat=0.3)          # near-black timber
HONEY = dict(sat=0.7, tint=(1.3, 0.96, 0.62), bright=1.12)                     # the floors
WSTONE = dict(sat=0.45, tint=(1.14, 1.0, 0.84), bright=1.14, flat=0.3)         # warm sandstone
SPEC = [  # name, source, grade, specular gain
    ("AGH2Plaster", WR + "wrplasterint01", dict(flat=0.55, contrast=0.8, sat=0.25, tint=(1.1, 1.05, 0.95), bright=1.06), 0.6),   # (2026-11-02: 1.3 made it 0.90 where vanilla's Whiterun plaster is 0.73 and Solitude's stucco 0.53, under window lights of Lux's and vanilla's strength or less: white walls from 10:30 to 15:30)
    ("AGH2Beam", SOL + "swoodbeam01", DARK, 1.0), ("AGH2Beam2", SOL + "swoodbeam02", DARK, 1.0),
    ("AGH2Boards", WR + "wrfloorboards01", HONEY, 1.3), ("AGH2Planks2", SOL + "swoodfloor01", HONEY, 1.3),
    ("AGH2Blocks", WR + "wrstoneblocks01", WSTONE, 0.9), ("AGH2Trim", WR + "wrtrims01", dict(sat=0.6, tint=(1.1, 0.92, 0.7), bright=0.95), 1.0),
    ("AGH2Panel", WR + "wrcastlewoodpanel01", dict(sat=0.6, tint=(0.92, 0.62, 0.44), bright=0.8), 1.1),
    ("AGH2XStucco", SOL + "sstuccowall", dict(flat=0.7, contrast=0.7, sat=0.12, tint=(1.1, 1.05, 0.95), bright=1.3), 0.6),
    ("AGH2XWood", SOL + "swoodbeam01", DARK, 1.0), ("AGH2XPlanks", SOL + "swoodplanks01", DARK, 1.0),
    ("AGH2XStone", SOL + "sstonewall02", WSTONE, 0.9), ("AGH2XBase", SOL + "sstonebase01", WSTONE, 0.9), ("AGH2XTrim", SOL + "strims01", WSTONE, 0.9),
    ("AGH2XFloor", SOL + "sstonefloor01", WSTONE, 0.9), ("AGH2XSteps", SOL + "ssteps01", WSTONE, 0.9),
    ("AGRoofSlate01", SOL + "sroofslate01", dict(sat=0.9, tint=(0.46, 0.6, 0.92), bright=0.95), None),    # (colour only: its normal stays vanilla's, hall_nif's OWN)
    # (2026-11-03, the art audit: these three were still make_hall_textures' Real-ESRGAN set) ungraded, as they were; The New Normal has no
    # sdirt01, so the dirt's normal is Ultimate's own
    ("AGH2XMetal", SOL + "smetaldet01", {}, 1.0), ("AGH2XTile", SOL + "sdragontile01", {}, 0.9), ("AGH2XDirt", SOL + "sdirt01", {}, 0.9),
]
# --board: the Guild Board's sources (board/board_textures.py reads these four by name and crops them by pixel), as they stood on 2026-10-27
# when the board was approved: make_hall_textures' grades, on Ultimate's colour instead of Real-ESRGAN's, each matched to the old file's mean
# colour so the board keeps its look; their normals were vanilla's then and are copied over unchanged
BOARD = [("AGH2Beam", SOL + "swoodbeam01", dict(flat=0.4, tint=(1.16, 0.96, 0.84), bright=1.1)), ("AGH2Boards", WR + "wrfloorboards01", dict(bright=1.15)),
         ("AGH2Trim", WR + "wrtrims01", dict(bright=1.05)), ("AGH2XMetal", SOL + "smetaldet01", {})]
OLD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "hall-private", "assets", "textures", "AdventurersGuild", "Hall2")


WALNUT = dict(sat=0.8, tint=(1.0, 0.8, 0.62), bright=0.92)                      # the bar: warm, a step lighter than the timber
IRONWOOD = dict(sat=0.55, tint=(0.82, 0.64, 0.5), bright=0.92)                  # doors: dark wood without browning their iron much
BUILT = [  # name, source, grade, specular gain, height, the set whose mean colour it must land on (the fireplace meets the shell's stone)
    ("AGH2Bar", "clutter/barset/bar01", WALNUT, 1.2, 2048, None),
    ("AGH2Door3", SOL + "sdoor03", IRONWOOD, 1.0, 2048, None), ("AGH2Door2", SOL + "sdoor02", IRONWOOD, 1.0, 2048, None),
    ("AGH2FireColumn", SOL + "sintcoloumn01", WSTONE, 0.9, 2048, WR + "wrstoneblocks01"), ("AGH2FireTop", SOL + "sintwalltop01", WSTONE, 0.9, 2048, WR + "wrstoneblocks01"),
    ("AGH2Farm", "architecture/farmhouse/farmhouse01", DARK, 1.0, 1024, None), ("AGH2Post", "architecture/farmhouse/woodpost02", DARK, 1.0, 1024, None),
    ("AGH2Sconce", "clutter/imperial/imperialwallsconce01", {}, 1.0, 1024, None),   # the iron of the torches, sconces and Imperial chandeliers, ungraded: vanilla's is 512 x 256, the torch's wood is 2K already
]


def read(path, work):
    """every channel as stored: texconv straight to PNG, no resize (WIC's resize spoils RGB where alpha is near 0)"""
    d = tempfile.mkdtemp(dir=work)
    subprocess.run([TEXCONV, "-nologo", "-y", "-ft", "png", "-f", "R8G8B8A8_UNORM", "-m", "1", "-o", d, path], check=True, capture_output=True)
    return np.asarray(Image.open(os.path.join(d, os.path.splitext(os.path.basename(path))[0] + ".png")).convert("RGBA")).astype(np.float32) / 255


def write(rgba, name, fmt, out, work):
    png = os.path.join(work, name + ".png"); Image.fromarray((np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA" if rgba.shape[2] == 4 else "RGB").save(png)
    subprocess.run([TEXCONV, "-nologo", "-y", "-f", fmt, "-m", "0", "-sepalpha", "-o", out, png], check=True, capture_output=True)


def grade(a, flat=0.0, contrast=1.0, sat=1.0, tint=(1, 1, 1), bright=1.0):
    """make_hall_textures' grade: large stains flattened (wrapped, so it still tiles), then graded"""
    h, w, _ = a.shape
    if flat > 0:
        big = Image.fromarray((np.tile(a, (3, 3, 1)) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(max(8, w // 24)))
        b = (np.asarray(big).astype(np.float32) / 255)[h:2 * h, w:2 * w]
        a = a - flat * (b - b.reshape(-1, 3).mean(0))
    m = a.mean(); a = (a - m) * contrast + m
    lum = (a * [0.299, 0.587, 0.114]).sum(2, keepdims=True); a = lum + (a - lum) * sat
    return a * np.array(tint) * bright


def box(a, size):
    """down to size by halves, each a 2x2 average"""
    while a.shape[0] > size:
        h, w = a.shape[:2]
        a = (a[0:h:2, 0:w:2] + a[1:h:2, 0:w:2] + a[0:h:2, 1:w:2] + a[1:h:2, 1:w:2]) / 4
    return a


def fit(a, size):
    """colour or a channel to size: halves when it is larger; Lanczos when a source is smaller (a 1K normal stays calm)"""
    if a.shape[0] >= size: return box(a, size)
    u = (np.clip(a, 0, 1) * 65535).astype(np.uint16)
    wide = a.shape[1] * size // a.shape[0]
    ch = [np.asarray(Image.fromarray(u[..., k].astype(np.int32), "I").resize((wide, size), Image.BICUBIC), np.float32) / 65535 for k in range(a.shape[2])]
    return np.stack(ch, 2)


def normal(tnn, ult_alpha, gain, size):
    n = tnn[..., :3] * 2 - 1
    v = box(n, size) if n.shape[0] >= size else fit(tnn[..., :3], size) * 2 - 1
    L = np.maximum(np.linalg.norm(v, axis=2, keepdims=True), 1e-4)
    # the shorter the average, the rougher the patch: specular eased by it (Toksvig), which is what stops distant shimmer
    tok = np.clip(L, 0, 1) ** 2
    s = fit(ult_alpha[..., None], size)[..., 0] * gain * tok[..., 0]
    return np.dstack([(v / L + 1) / 2, np.clip(s, 0, 1)])


def main():
    a = sys.argv[1:]; big = "--4k" in a; built = "--built" in a; board = "--board" in a
    for f in ("--4k", "--built", "--board"):
        if f in a: a.remove(f)
    ult, tnn, out = a[:3]; only = set(a[3:]); os.makedirs(out, exist_ok=True); work = tempfile.mkdtemp()
    if board:
        for name, src, g in BOARD:
            if only and name not in only: continue
            c = grade(box(read(os.path.join(ult, src + ".dds"), work)[..., :3], 2048), **g)
            old = read(os.path.join(OLD, name + ".dds"), work)[..., :3]
            k = old.reshape(-1, 3).mean(0) / c.reshape(-1, 3).mean(0); c = c * k
            write(c, name, "BC7_UNORM", out, work); shutil.copyfile(os.path.join(OLD, name + "_n.dds"), os.path.join(out, name + "_n.dds"))
            print("made", name, "matched by", k.round(3), flush=True); shutil.rmtree(work, ignore_errors=True); os.makedirs(work, exist_ok=True)
        return
    if built:
        for name, src, g, gain, size, like in BUILT:
            if only and name not in only: continue
            u = read(os.path.join(ult, src + ".dds"), work); c = grade(fit(u[..., :3], size), **g)
            if like:
                ref = grade(box(read(os.path.join(ult, like + ".dds"), work)[..., :3], 512), **g)
                c = c * ref.reshape(-1, 3).mean(0) / c.reshape(-1, 3).mean(0)
            cut = fit(u[..., 3:], size)
            if cut.min() < 0.5: c = np.dstack([c, cut])                                # (a source whose alpha cuts: the Imperial chandelier's chains are alpha tested on the wall iron)
            write(c, name, "BC7_UNORM", out, work)
            ua = read(os.path.join(ult, src + "_n.dds"), work)[..., 3]; t = read(os.path.join(tnn, src + "_n.dds"), work)
            write(normal(t, ua, gain, size), name + "_n", "BC7_UNORM", out, work)
            print("made", name, size, flush=True); shutil.rmtree(work, ignore_errors=True); os.makedirs(work, exist_ok=True)
        return
    for name, src, g, gain in SPEC:
        if only and name not in only: continue
        u = read(os.path.join(ult, src + ".dds"), work); size = u.shape[0] if big else 2048
        if big and size < 4096: continue
        write(grade(box(u[..., :3], size), **g), name, "BC7_UNORM", out, work)
        if gain is not None and not big:
            un = read(os.path.join(ult, src + "_n.dds"), work); tp = os.path.join(tnn, src + "_n.dds")
            t = read(tp, work) if os.path.exists(tp) else un                         # (no New Normal for it: Ultimate's own)
            write(normal(t, un[..., 3], gain, 2048), name + "_n", "BC7_UNORM", out, work)
        print("made", name, size, flush=True); shutil.rmtree(work, ignore_errors=True); os.makedirs(work, exist_ok=True)


if __name__ == "__main__":
    main()
