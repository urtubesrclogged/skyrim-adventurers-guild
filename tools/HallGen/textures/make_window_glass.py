"""The hall's window glass, lit by day and dark at night (glass that lets light through, as the Bannered
Mare's does, where ours looked closed). Vanilla's Solitude glow maps, our copies, are dim grey patches at 512; the Mare's look (Rustic Windows) is a glow map of cool
glass bright to every pane's edge with black leading. From our own glow maps: the same panes, lifted, cool, at 1024, so the leading stays where the picture has it.
  AGH2XWinDay1 / 3   the panes by day (a layer of its own, enabled with the daylight marker)
  AGH2XWinDim1 / 3   the panes the interior's windows keep at night: barely there
Each is the picture's diffuse and normal under a new name, and the new glow.
    python make_window_glass.py <out dir: .../textures/AdventurersGuild/Hall2> [preview.png]"""
import os, shutil, subprocess, sys
import numpy as np
from PIL import Image, ImageFilter
GAME = "C:/Games/steamapps/common/SkyrimVR"; TEXCONV = GAME + "/tools/texconv/texconv.exe"
OUT = sys.argv[1]; COOL = np.array((0.74, 0.90, 0.95)); DIM = np.array((0.05, 0.07, 0.10))
sheet = []
for n in ("1", "3"):
    src = np.asarray(Image.open(os.path.join(OUT, f"AGH2XWin{n}_g.dds")).convert("L").resize((1024, 1024), Image.LANCZOS), float) / 255
    # the pane: what glows at all; its own soft shading kept a little, so it reads as glass and not a lit card
    pane = np.clip((src - 0.06) / 0.20, 0, 1)
    pane = np.asarray(Image.fromarray((pane * 255).astype("uint8")).filter(ImageFilter.GaussianBlur(0.7)), float) / 255
    # the old map's dark blotches (the panes' middle in places, its edges) lifted: 0.72 to 1 across a pane
    body = np.clip(0.72 + 0.6 * src, 0, 1)
    day = (pane * body)[..., None] * COOL
    dim = (pane * body)[..., None] * DIM
    for kind, a in (("Day", day), ("Dim", dim)):
        base = f"AGH2XWin{kind}{n}"
        png = os.path.join(OUT, base + "_g.png"); Image.fromarray((np.clip(a, 0, 1) * 255).astype("uint8")).save(png)
        subprocess.run([TEXCONV, "-nologo", "-y", "-f", "BC1_UNORM", "-m", "0", "-o", OUT, png], check=True, stdout=subprocess.DEVNULL); os.remove(png)
        shutil.copyfile(os.path.join(OUT, f"AGH2XWin{n}.dds"), os.path.join(OUT, base + ".dds"))
        shutil.copyfile(os.path.join(OUT, f"AGH2XWin{n}_n.dds"), os.path.join(OUT, base + "_n.dds"))
    sheet.append(Image.fromarray((np.clip(day, 0, 1) * 255).astype("uint8")).resize((512, 512)))
if len(sys.argv) > 2:
    s = Image.new("RGB", (1024, 512)); s.paste(sheet[0], (0, 0)); s.paste(sheet[1], (512, 0)); s.save(sys.argv[2])
print("GLASS", sorted(f for f in os.listdir(OUT) if "WinDay" in f or "WinDim" in f))
