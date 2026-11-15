"""The dragon head's carving as a height map over its side (head_bake.py displaces it into the full model): the eye,
the nostril, the lips and teeth, a scroll on the cheek, the horn's ridges, the mane, scales on the neck. Mid grey is the
surface; darker is cut in, lighter stands proud. Its frame matches head_bake.py's side UVs.
    python head_carve.py <out dir>   -> <out>/head_height.png"""
import os, sys, math
from PIL import Image, ImageDraw, ImageFilter
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
XMIN, XMAX, ZMIN, ZMAX = -3.0, 25.0, -1.0, 18.5        # as head_bake.py
SW_ = max(XMAX - XMIN, (ZMAX - ZMIN) * 2)
HPX = 2048
def P(x, z): return ((x - XMIN) / SW_ * HPX, (1 - (z - ZMIN) / (SW_ / 2)) * HPX / 2)
hm = Image.new("L", (HPX, HPX // 2), 128); d = ImageDraw.Draw(hm)
def groove(pts, w, depth=60):
    d.line([P(*p) for p in pts], fill=128 - depth, width=int(w * HPX / SW_), joint="curve")
def ridge(pts, w, h=50):
    d.line([P(*p) for p in pts], fill=128 + h, width=int(w * HPX / SW_), joint="curve")
# the eye: a socket, a raised ball, a lid line
ex, ez = 12.6, 8.6
d.ellipse([P(ex - 1.7, ez + 1.2), P(ex + 1.7, ez - 1.2)], fill=70)
d.ellipse([P(ex - 1.1, ez + 0.75), P(ex + 1.1, ez - 0.75)], fill=200)
groove([(ex - 2.6, ez + 0.4), (ex - 1, ez + 1.9), (ex + 1.5, ez + 1.7), (ex + 3.2, ez + 0.6)], 0.35)
# the nostril, the lips, the teeth
d.ellipse([P(21.2, 7.9), P(22.2, 7.2)], fill=60)
groove([(10.8, 4.6), (13, 5.0), (16.8, 4.85), (20.5, 5.35), (22.5, 6.2)], 0.3)
groove([(11, 4.3), (13, 3.75), (16.5, 3.45), (19.4, 3.75)], 0.3)
# the cheek's scroll (a spiral) and the jaw's line
sp = [(7.0 + 2.6 * (1 - t) * math.cos(t * 9.5), 6.4 + 2.6 * (1 - t) * math.sin(t * 9.5)) for t in [i / 60 for i in range(60)]]
groove(sp, 0.4)
groove([(3, 2.2), (6.5, 2.9), (9.6, 4.0)], 0.35)
# the horn's ridges, the mane's strands
for k in range(4):
    off = k * 0.75
    groove([(3.3 - off * 0.3, 11.2 + off), (5.4 - off * 0.2, 13.4 + off * 0.6), (3.0 - off * 0.4, 16.0 + off * 0.2)], 0.25, 45)
for k in range(5):
    groove([(0.6 + k * 0.9, 8.6 - k * 0.15), (2.4 + k * 1.1, 10.4 - k * 0.5), (2.2 + k * 1.3, 12.2 - k * 0.9)], 0.22, 40)
# scales on the neck
for r in range(3):
    for c in range(3):
        cx, cz = 1.3 + c * 1.9 + (r % 2) * 0.9, 1.9 + r * 1.9
        d.arc([P(cx - 0.9, cz + 0.9), P(cx + 0.9, cz - 0.9)], 200, 340, fill=80, width=int(0.25 * HPX / SW_))
hm = hm.filter(ImageFilter.GaussianBlur(3))
hpath = os.path.join(OUT, "head_height.png"); hm.save(hpath)

