"""Openings cut from an atlas (window and door trim sheets) must not show the sheet's background: count, for every kind,
the background pixels inside the outline guildhall_gen.py cuts, in the vanilla sheet and in every replacement the
installs use (texture mods keep the layout but repaint it). A round arch on a pointed painting left a crescent of
light-grey background on each shoulder of the ground-storey windows, which read as snow on the SE test install (2026-10-24).
    python atlas_fit_check.py <generator.py> <vanilla textures dir> [replacement textures dir ...] [--trace]
With --trace it prints, per kind, an outline traced from the vanilla painting (inset 2 px) to paste into the generator.
Exit 1 when any kind leaves more than 0.3% of its outline's area showing background."""
import sys, os, re, math, ast
from PIL import Image, ImageDraw
args = [a for a in sys.argv[1:] if not a.startswith("--")]; TRACE = "--trace" in sys.argv
gen, dirs = args[0], args[1:]
src = open(gen, encoding="utf-8").read()
atlas = ast.literal_eval(re.search(r"ATLAS = (\{.*?\n\})", src, re.S).group(1))
files = ast.literal_eval(re.search(r"FILES = (\{.*?\})", src, re.S).group(1))
ns = {"math": math}
exec(re.search(r"(def outline\(kind, w, h\):.*?return \[\(0, 0\), \(1, 0\), \(1, 1\), \(0, 1\)\])", src, re.S).group(1), ns)
outline = ns["outline"]
TRACED = ns.get("TRACED", {})
m = re.search(r"(TRACED = \{.*?\n\})", src, re.S)
if m: TRACED = ast.literal_eval(m.group(1)[len("TRACED = "):])
SHEET = {"win1": "swindow01", "win3": "swindow03", "door": "sdoor02"}
def background(im):
    """the sheet's background colour: the commonest colour of the border rows (the paintings never touch the edge)"""
    from collections import Counter
    W, H = im.size; px = [im.getpixel((x, y)) for x in range(0, W, 7) for y in (2, H - 3)] + [im.getpixel((x, y)) for y in range(0, H, 7) for x in (2, W - 3)]
    return Counter((p[0] // 8, p[1] // 8, p[2] // 8) for p in px).most_common(1)[0][0]
bad = 0
for kind, (key, (u0, v0, u1, v1)) in atlas.items():
    sheet = SHEET.get(key)
    if not sheet: continue
    w = 120.0; h = w * (v1 - v0) / (u1 - u0)
    poly = TRACED.get(kind) or outline(kind, w, h)
    for d in dirs:
        path = os.path.join(d, sheet + ".dds")
        if not os.path.exists(path): continue
        im = Image.open(path).convert("RGB"); W, H = im.size; bg = background(im)
        box = (u0 * W, v0 * H, u1 * W, v1 * H)
        pts = [(box[0] + x * (box[2] - box[0]), box[3] - y * (box[3] - box[1])) for x, y in poly]   # outline v up = image row up
        mask = Image.new("L", (W, H), 0); ImageDraw.Draw(mask).polygon(pts, fill=255)
        n_in = n_bg = 0
        x0, y0, x1, y1 = [int(v) for v in mask.getbbox()]
        for yy in range(y0, y1):
            for xx in range(x0, x1):
                if mask.getpixel((xx, yy)):
                    n_in += 1; p = im.getpixel((xx, yy))
                    if (p[0] // 8, p[1] // 8, p[2] // 8) == bg: n_bg += 1
        share = n_bg / max(1, n_in)
        flag = "FAIL" if share > 0.003 else "ok"
        if flag == "FAIL": bad += 1
        print(f"{flag:4s} {kind:9s} {sheet:10s} {share * 100:5.2f}% background inside the outline | {os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path)))) or d}")
    if TRACE and dirs:
        im = Image.open(os.path.join(dirs[0], sheet + ".dds")).convert("RGB"); W, H = im.size; bg = background(im)
        bx0, by0, bx1, by1 = int(u0 * W), int(v0 * H), int(u1 * W), int(v1 * H)
        rows = []
        for yy in range(by0, by1):
            xs = [xx for xx in range(bx0, bx1) if (lambda p: (p[0] // 8, p[1] // 8, p[2] // 8))(im.getpixel((xx, yy))) != bg]
            if xs: rows.append((yy, min(xs) + 2, max(xs) - 2))
        top = rows[0][0] + 2
        rows = [r for r in rows if r[0] >= top and r[2] > r[1]]
        step = max(1, len(rows) // 24)
        L = [((r[1] - bx0) / (bx1 - bx0), (by1 - r[0]) / (by1 - by0)) for r in rows[::step]] + [((rows[-1][1] - bx0) / (bx1 - bx0), 0.0)]
        R = [((r[2] - bx0) / (bx1 - bx0), (by1 - r[0]) / (by1 - by0)) for r in rows[::step]] + [((rows[-1][2] - bx0) / (bx1 - bx0), 0.0)]
        traced = [L[-1], R[-1]] + R[::-1][1:] + L[:-1]            # counter-clockwise from the bottom left
        print("   TRACED", kind, [(round(x, 4), round(y, 4)) for x, y in traced])
sys.exit(1 if bad else 0)
