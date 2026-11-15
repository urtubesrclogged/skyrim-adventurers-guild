"""The Guild Board page's textures (board.html), cut from the 3D board's own maps so the page and the board on the wall
are the same wood and the same paper.
    python make_ui_tex.py [out dir]      (default: ui/tex/board beside this script)

- planks.jpg   the board's face (AGBoardPlanks), the field the notices are pinned to
- oak.jpg      the frame's oak, from its seam-free rows (board_textures.py OAK_CLEAN)
- knot.png     the sign board's carved knotwork band (the detail atlas' "knot" rect)
- notice.png   the counter's note leaf (tex/skin/note.png) stood on end: a notice is the same paper as the counter's documents
- strip.png    a row of the list: a strip of that note leaf with its torn edges top and bottom
- sk_<name>.png  the notices' ink sketches (notices/out/layers/sketches), smaller
- rank_<R>.png   the clerk's rank stamps (notices/out/layers/stamps)
"""
import os, sys, glob
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.dirname(HERE)
AG = os.path.normpath(os.path.join(BOARD, "..", "..", ".."))
sys.path.insert(0, BOARD)
from board_layout import DETAIL

OUT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(HERE, "tex", "board")
OAK_CLEAN = (1432, 2000)
os.makedirs(OUT, exist_ok=True)

def fit(im, w):
    return im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)

Image.open(os.path.join(BOARD, "maps", "atlas", "AGBoardPlanks.png")).convert("RGB").resize((1024, 1024), Image.LANCZOS) \
    .save(os.path.join(OUT, "planks.jpg"), quality=86)
oak = Image.open(os.path.join(BOARD, "maps", "atlas", "AGBoardOak.png")).convert("RGB")
oak.crop((0, OAK_CLEAN[0], 2048, OAK_CLEAN[1])).resize((1024, (OAK_CLEAN[1] - OAK_CLEAN[0]) // 2), Image.LANCZOS) \
    .save(os.path.join(OUT, "oak.jpg"), quality=86)
det = Image.open(os.path.join(BOARD, "maps", "atlas", "AGBoardDetail.png")).convert("RGB")
fit(det.crop(DETAIL["knot"]), 1024).save(os.path.join(OUT, "knot.png"))
fit(Image.open(os.path.join(AG, "config", "PrismaUI", "views", "AdventurersGuild", "tex", "skin", "note.png")).convert("RGBA")
    .transpose(Image.ROTATE_90), 420).save(os.path.join(OUT, "notice.png"))
# the list's rows: a strip with the note leaf's torn, deckled edges (rougher edges, in the style
# of the reader's note). Its top band twice: as it is, and turned end over end for the bottom edge
# (the note's own bottom edge has a dark tear notch that would repeat down every row), blended through the plain paper
# between them. 1240 x 120, as the counter's strip.png (1240 x 110).
import numpy as np
note = np.asarray(Image.open(os.path.join(AG, "config", "PrismaUI", "views", "AdventurersGuild", "tex", "skin", "note.png")).convert("RGBA")).astype(np.float32)
H, B, BLEND = 120, 75, 30                      # strip height, the band taken from the note's top, the rows blended
top = note[:B]; bot = top[::-1, ::-1]           # bot row k = the note's row B-1-k, mirrored: its last row is the torn edge
strip = np.zeros((H, note.shape[1], 4), np.float32)
for y in range(H):
    j = y - (H - B)                             # this row in bot (counted from bot's first row)
    if y < H - B: strip[y] = top[y]
    elif y >= B: strip[y] = bot[j]
    else:
        w = (y - (H - B)) / BLEND
        strip[y] = top[y] * (1 - w) + bot[j] * w
Image.fromarray(np.clip(strip, 0, 255).astype(np.uint8), "RGBA").save(os.path.join(OUT, "strip.png"))
LAY = os.path.join(BOARD, "notices", "out", "layers")
for f in sorted(glob.glob(os.path.join(LAY, "sketches", "*.png"))):
    im = Image.open(f).convert("RGBA")
    (fit(im, 300) if im.width > 300 else im).save(os.path.join(OUT, "sk_" + os.path.basename(f)))
for f in sorted(glob.glob(os.path.join(LAY, "stamps", "*.png"))):
    fit(Image.open(f).convert("RGBA"), 128).save(os.path.join(OUT, os.path.basename(f)))
print("ui tex ->", OUT, len(os.listdir(OUT)), "files")
