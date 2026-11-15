"""Where each part sits in the board's detail atlas (AGBoardDetail, 2048 square), shared by board_textures.py (which
paints it) and board_build.py (which maps the mesh into it). Rects in pixels, (x0, y0, x1, y1), y down from the image's
top; uv() turns one into Blender's UV (v up)."""
SIZE = 2048
DETAIL = {
    "crest":   (0, 0, 1024, 1024),         # the hall's relief crest, its maps resampled (crest_low.json's UVs land here)
    "badges":  (1024, 0, 1792, 512),       # six badges, 3 x 2 cells of 256: E D C / B A S (off the board since v2)
    "wear":    (1024, 512, 2048, 768),     # wear from past notices, alpha-tested: nail holes, pin pricks, rust, paper scraps
    "iron":    (1792, 0, 2048, 512),       # hammered iron: corner plates, straps, rivets, bezels, nails
    "knot":    (0, 1024, 2048, 1280),      # the sign board's carved face: Whiterun's knotwork band
    "head":    (0, 1280, 1024, 1792),      # a dragon head, side on (both heads share it, mirrored)
    "roundel": (1024, 1280, 1792, 2048),   # the crest's oak roundel, its face
    "headcap": (0, 1792, 1024, 2048),      # the head's top and underside (the extrusion's sides)
}
BADGE_ORDER = "EDCBAS"

def badge_rect(rank):
    i = BADGE_ORDER.index(rank); x0, y0, _, _ = DETAIL["badges"]
    return (x0 + (i % 3) * 256, y0 + (i // 3) * 256, x0 + (i % 3) * 256 + 256, y0 + (i // 3) * 256 + 256)

def uv(rect, pad=0):
    """(u0, v0, u1, v1) in Blender's UV space, inset by pad pixels"""
    x0, y0, x1, y1 = rect
    return ((x0 + pad) / SIZE, 1 - (y1 - pad) / SIZE, (x1 - pad) / SIZE, 1 - (y0 + pad) / SIZE)

def wear_cells():
    """the wear decals' cells in the "wear" rect: {kind: [rect, ...]}"""
    x0, y0 = DETAIL["wear"][:2]
    return {"hole": [(x0 + 64 * i, y0, x0 + 64 * i + 64, y0 + 64) for i in range(8)],
            "pins": [(x0 + 512 + 64 * i, y0, x0 + 512 + 64 * i + 64, y0 + 64) for i in range(8)],
            "rust": [(x0 + 64 * i, y0 + 64, x0 + 64 * i + 64, y0 + 256) for i in range(4)],
            "scrap": [(x0 + 256 + 128 * i, y0 + 64, x0 + 256 + 128 * i + 128, y0 + 192) for i in range(6)]}
