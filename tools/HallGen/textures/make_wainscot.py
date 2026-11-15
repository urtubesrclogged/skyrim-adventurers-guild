"""The tavern's panelling (in the table tops' and bar tops' wood tone, which suits the room): its wood cut from the bar's own texture, AGH2Bar (make_materials.py --built), the counter top's boards, so the
panels match the bar on every install. AGH2Wainscot: the boards as they are; AGH2WainscotFrame: the same, a step darker (the frame
reads as the same wood, low contrast: dark frames read too thick and too dark). Their normals from AGH2Bar_n the same way.
    python make_wainscot.py <dir holding AGH2Bar.dds and AGH2Bar_n.dds> <out dir>"""
import os, subprocess, sys, tempfile
import numpy as np
from PIL import Image
TEXCONV = "C:/Games/steamapps/common/SkyrimVR/tools/texconv/texconv.exe"
SRC, OUT = sys.argv[1], sys.argv[2]; os.makedirs(OUT, exist_ok=True); work = tempfile.mkdtemp()
def read(name):
    subprocess.run([TEXCONV, "-nologo", "-y", "-ft", "png", "-f", "R8G8B8A8_UNORM", "-m", "1", "-o", work, os.path.join(SRC, name + ".dds")], check=True, capture_output=True)
    return np.asarray(Image.open(os.path.join(work, name + ".png")).convert("RGBA")).astype(np.float32) / 255
def write(a, name):
    png = os.path.join(work, name + ".png"); Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(png)
    subprocess.run([TEXCONV, "-nologo", "-y", "-f", "BC7_UNORM", "-m", "0", "-sepalpha", "-o", OUT, png], check=True, capture_output=True)
c, n = read("AGH2Bar"), read("AGH2Bar_n")
H = c.shape[0]; s = H / 2048
X0, Y0, SZ = int(0 * s), int(900 * s), int(1024 * s)              # the counter top's boards (AGH2Bar's lower left quarter)
cc, nn = c[Y0:Y0 + SZ, X0:X0 + SZ].copy(), n[Y0:Y0 + SZ, X0:X0 + SZ].copy()
def tile(a):
    """seamless both ways: near its edges the crop gives way to itself rolled by half (whose middle is the old edges, met)"""
    h_, w_ = a.shape[:2]; r_ = np.roll(np.roll(a, h_ // 2, 0), w_ // 2, 1)
    ramp = lambda k_: np.clip(np.minimum(np.arange(k_), k_ - 1 - np.arange(k_)) / (k_ * 0.18), 0, 1)
    w2 = np.minimum.outer(ramp(h_), ramp(w_))[..., None]
    return a * w2 + r_ * (1 - w2)
cc = tile(cc); nn = tile(nn)
v_ = nn[..., :3] * 2 - 1; v_ /= np.maximum(np.linalg.norm(v_, axis=2, keepdims=True), 1e-4); nn[..., :3] = (v_ + 1) / 2
write(cc, "AGH2Wainscot"); write(nn, "AGH2Wainscot_n")
fr = cc.copy(); fr[..., :3] *= 0.8
write(fr, "AGH2WainscotFrame"); write(nn, "AGH2WainscotFrame_n")
print("made AGH2Wainscot, AGH2WainscotFrame from AGH2Bar", cc.shape, "mean", cc[..., :3].reshape(-1, 3).mean(0).round(3))
