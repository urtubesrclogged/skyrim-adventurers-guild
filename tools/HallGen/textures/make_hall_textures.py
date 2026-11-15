"""The hall's own textures (shipped with the hall, at a raised resolution,
exterior too): our copies of vanilla's, under textures/AdventurersGuild/Hall2, so no modlist's replacers can
repaint them (the SE test install's turned the beams to copper bands and the plaster to marble).

  ai    vanilla's diffuse through Real-ESRGAN x4 (wrap-padded, so it still tiles), Lanczos to 2048 wide: the compression
        blocks gone, the 1K ones (dirt, dragon tile, roof slate) raised to 2K; then graded; BC7 with a full mip chain
  copy  vanilla's file as it is (the windows', door's and moss' pictures: the upscaler would invent detail in them)
Every texture's normal (and glow) map is vanilla's, copied beside it under the same name.

Grades (the interior, from the palette study: mostly palette 1, with some of the woods
from palette 2 for variety, only where it makes sense): Whiterun's interior plaster cleaned and creamed, Solitude's beam
warmed toward the Bannered Mare's bar, Whiterun's floorboards, dressed blocks, carved trims and panelling; palette 2's
woods (Solitude's nailed beam and boards, warmed) for the working rooms, the attic and the lookout.

    python make_hall_textures.py <out dir: .../textures/AdventurersGuild/Hall2> [name ...]"""
import os, sys, struct, subprocess, tempfile, shutil, glob
import numpy as np
from PIL import Image, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "blender"))
import bsa

GAME = "C:/Games/steamapps/common/SkyrimVR"
TEXCONV = GAME + "/tools/texconv/texconv.exe"
RE = GAME + "/tools/realesrgan"
BSAS = sorted(glob.glob(GAME + "/Data/Skyrim - Textures*.bsa")) + [GAME + "/Data/Skyrim - Patch.bsa", GAME + "/Data/Skyrim_VR - Main.bsa"]
SOL, WR = "architecture\\solitude\\", "architecture\\whiterun\\"

WARM = dict(tint=(1.16, 0.96, 0.84), bright=1.1)               # toward bar01's brown (its mean 1.24 : 0.98 : 0.78)
P2WOOD = dict(flat=0.3, tint=(1.2, 0.97, 0.8))
SPEC = [  # name, vanilla (under textures\), mode, grade
    # the interior
    ("AGH2Plaster", WR + "wrplasterint01", "ai", dict(flat=0.9, contrast=0.5, tint=(1.0, 0.96, 0.86), bright=1.02)),   # (cracks softened: cleaner)
    ("AGH2Beam", SOL + "swoodbeam01", "ai", dict(flat=0.4, **WARM)),
    ("AGH2Boards", WR + "wrfloorboards01", "ai", dict(bright=1.15)),
    ("AGH2Blocks", WR + "wrstoneblocks01", "ai", dict(flat=0.4, tint=(1.04, 1.0, 0.94), bright=1.15)),
    ("AGH2Trim", WR + "wrtrims01", "ai", dict(bright=1.05)),
    ("AGH2Panel", WR + "wrcastlewoodpanel01", "ai", dict(flat=0.3, tint=(1.12, 0.97, 0.84), bright=0.85)),
    ("AGH2Beam2", SOL + "swoodbeam02", "ai", dict(bright=1.2, **P2WOOD)),
    ("AGH2Planks2", SOL + "swoodfloor01", "ai", dict(bright=1.15, **P2WOOD)),
    # the exterior: vanilla's look, our copies
    ("AGH2XStone", SOL + "sstonewall02", "ai", {}), ("AGH2XBase", SOL + "sstonebase01", "ai", {}),
    ("AGH2XTrim", SOL + "strims01", "ai", {}), ("AGH2XStucco", SOL + "sstuccowall", "ai", {}),
    ("AGH2XWood", SOL + "swoodbeam01", "ai", {}), ("AGH2XPlanks", SOL + "swoodplanks01", "ai", {}),
    ("AGH2XSteps", SOL + "ssteps01", "ai", {}), ("AGH2XFloor", SOL + "sstonefloor01", "ai", {}),
    ("AGH2XMetal", SOL + "smetaldet01", "ai", {}), ("AGH2XTile", SOL + "sdragontile01", "ai", {}),
    ("AGH2XDirt", SOL + "sdirt01", "ai", {}),
    # (2026-11-03) a chip's broken face (the gate pier's read as a perfectly round hole, not a real break): Bethesda's broken stone is a
    # second texture beside the face's (Fallout 3's broken edges), and vanilla's freshly split stone is Windhelm's rough surface (hackly, granular, no
    # blocks, no moss). Toned to AGH2XStone's own grey (its blocks' median 73,81,78 from this one's 74,76,69), lifted a third: fresh, unweathered, as a break shows pale on weathered stone (an eighth read too little, 2026-11-04)
    ("AGH2XStoneBreak", "architecture\\windhelm\\whstoneroughsurface", "ai", dict(contrast=0.6, tint=(0.99, 1.07, 1.02), bright=1.35)),
    ("AGH2XWin1", SOL + "swindow01", "copy", {}), ("AGH2XWin3", SOL + "swindow03", "copy", {}),
    ("AGH2XDoor", SOL + "sdoor02", "copy", {}), ("AGH2XMoss", SOL + "smoss01", "copy", {}),
    ("AGH2XMossWall", SOL + "smoss02walls", "copy", {}),
    # the roof's own slate (make_roof_dds.py's blue-grey, until now 1K DXT1): its normal stays vanilla's (hall_nif's OWN)
    ("AGRoofSlate01", SOL + "sroofslate01", "ai", dict(tint=(0.55, 0.66, 0.85)), ),
]
# a borrowed normal whose specular (its alpha) is another kit's: set to the stone's it sits in. Windhelm's rough surface carries 255
# everywhere, under Solitude's wall shader a wet sheen that washed the chip's scar pale; AGH2XStone_n's alpha is 0 over half its area, 66 at most
SPEC_OF = {"AGH2XStoneBreak": 16}

def run(*a): subprocess.run([str(x) for x in a], check=True, capture_output=True)

def upscale(im, tw):
    """wrap-padded through Real-ESRGAN x4, the pad cropped off, Lanczos to tw wide"""
    w, h = im.size; P = max(16, w // 32)
    pad = Image.new("RGB", (w + 2 * P, h + 2 * P))
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1): pad.paste(im, (P + dx * w, P + dy * h))
    d = tempfile.mkdtemp(); a, b = os.path.join(d, "a.png"), os.path.join(d, "b.png"); pad.save(a)
    run(RE + "/realesrgan-ncnn-vulkan.exe", "-i", a, "-o", b, "-n", "realesrgan-x4plus", "-m", RE + "/models", "-t", "256")
    up = Image.open(b).convert("RGB").crop((4 * P, 4 * P, 4 * P + 4 * w, 4 * P + 4 * h))
    shutil.rmtree(d, ignore_errors=True)
    return up.resize((tw, round(h * tw / w)), Image.LANCZOS)

def grade(im, flat=0.0, radius=None, contrast=1.0, sat=1.0, tint=(1, 1, 1), bright=1.0):
    """large stains flattened (the detail over a wrapped blur, laid on the mean colour: it still tiles), then graded"""
    a = np.asarray(im).astype(np.float32) / 255; h, w, _ = a.shape
    if flat > 0:
        big = Image.fromarray((np.tile(a, (3, 3, 1)) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius or max(8, w // 24)))
        b = (np.asarray(big).astype(np.float32) / 255)[h:2 * h, w:2 * w]
        a = a - flat * (b - b.reshape(-1, 3).mean(0))
    m = a.mean(); a = (a - m) * contrast + m
    lum = (a * [0.299, 0.587, 0.114]).sum(2, keepdims=True); a = lum + (a - lum) * sat
    a = a * np.array(tint) * bright
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))

def main():
    out = sys.argv[1]; only = set(sys.argv[2:])
    os.makedirs(out, exist_ok=True)
    work = tempfile.mkdtemp()
    want = []
    for name, src, mode, g in SPEC:
        if only and name not in only: continue
        want += [f"textures\\{src}{s}.dds" for s in ("", "_n", "_g")]
    lst = os.path.join(work, "want.txt"); open(lst, "w").write("\n".join(want) + "\n")
    subprocess.run([sys.executable, "-I", os.path.join(HERE, "..", "blender", "bsa.py"), work, lst] + BSAS, check=True, capture_output=True)
    for name, src, mode, g in SPEC:
        if only and name not in only: continue
        dds = os.path.join(work, "textures", *src.split("\\")) + ".dds"
        if mode == "copy":
            shutil.copyfile(dds, os.path.join(out, name + ".dds"))
        else:
            run(TEXCONV, "-nologo", "-y", "-ft", "png", "-m", "1", "-o", work, dds)
            im = Image.open(os.path.join(work, os.path.basename(src) + ".png")).convert("RGB")
            im = grade(upscale(im, 2048), **g)
            png = os.path.join(work, name + ".png"); im.save(png)
            run(TEXCONV, "-nologo", "-y", "-f", "BC7_UNORM", "-m", "0", "-o", out, png)
        for s in ("_n", "_g"):                                  # vanilla's normal and glow beside it
            p = os.path.join(work, "textures", *src.split("\\")) + s + ".dds"
            if not os.path.exists(p) or name == "AGRoofSlate01": continue
            if s == "_n" and name in SPEC_OF:                   # its specular (the normal's alpha) set to the stone it sits in
                run(TEXCONV, "-nologo", "-y", "-ft", "png", "-o", work, p)
                nm = Image.open(os.path.join(work, os.path.basename(p)[:-4] + ".png")).convert("RGBA")
                nm.putalpha(SPEC_OF[name]); npng = os.path.join(work, name + s + ".png"); nm.save(npng)
                run(TEXCONV, "-nologo", "-y", "-f", "BC7_UNORM", "-m", "0", "-o", out, npng)
            else: shutil.copyfile(p, os.path.join(out, name + s + ".dds"))
        print("made", name, mode)
    shutil.rmtree(work, ignore_errors=True)

if __name__ == "__main__":
    main()
