"""Every file the build's plugin and meshes name is in the build (2026-10-30: a texture made after the rooms' meshes failed 15 of 17 of them and the chain carried on, because each
step only reported on what existed). The plugin's own models, then each own mesh's own textures.
    python models_check.py <build dir>        FAIL MODEL / FAIL TEXTURE per missing file, exit 1"""
import glob, os, re, sys
sys.path.insert(0, os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "scripts", "addons", "io_scene_nifly"))
from pyn.pynifly import NifFile
NifFile.Load(os.path.join(os.environ["APPDATA"], "Blender Foundation", "Blender", "5.2", "scripts", "addons", "io_scene_nifly", "pyn", "NiflyDLL.dll"))
OWN = rb"(?i)adventurersguild.hall2.[a-z0-9_ ]+[.]nif"
B = sys.argv[1]; have = {os.path.relpath(os.path.join(d, f), B).replace("\\", "/").lower() for d, _, fs in os.walk(B) for f in fs}
esp = [p for p in glob.glob(os.path.join(B, "*.esp"))][0]; want = {m.decode().replace("\\", "/").lower() for m in re.findall(OWN, open(esp, "rb").read())}
bad = 0
for m in sorted(want):
    if "meshes/" + m not in have: print(f"  FAIL MODEL {m}: named by the plugin, not in the build"); bad += 1
nifs = sorted(glob.glob(os.path.join(B, "meshes", "AdventurersGuild", "Hall2", "*.nif"))); tex = set()
for p in nifs:
    for sh in NifFile(p).shapes:
        for t in sh.textures.values():
            t = t.replace("\\", "/").lower()
            if "adventurersguild/hall2/" in t: tex.add((t[t.index("textures/"):] if "textures/" in t else "textures/" + t, os.path.basename(p)))
for t in sorted({t for t, _ in tex}):
    if t not in have: print(f"  FAIL TEXTURE {t}: in {sorted(n for x, n in tex if x == t)[:3]}, not in the build"); bad += 1
if not want: print("  FAIL MODEL the plugin names no models of ours: this gate read nothing"); bad += 1
# (2026-11-01, "a gap at the bottom... should be caught from now on") an alpha-cut strip must be solid where it meets what it hangs from: the banner's fringe, top edge against its texture
for p in nifs:
    if "banner330" not in p.lower(): continue
    for sh in NifFile(p).shapes:
        if "fringe" not in sh.name.lower(): continue
        uv = sh.uvs; top = max(u for u, v in uv); dds = [f for f in (os.path.join(sys.argv[2] if len(sys.argv) > 2 else "", "textures", "architecture", "whiterun", "wrcarpetdetails01.dds"),) if os.path.exists(f)]
        if not dds: print("  FAIL MODEL fringe: its texture not found: this check read nothing"); bad += 1; continue
        from PIL import Image
        a = Image.open(dds[0]).convert("RGBA"); w, h = a.size; i = int(top * w)
        cover = sum(1 for j in range(0, h, 7) if a.getpixel((max(i - 1, 0), j))[3] > 128) / len(range(0, h, 7))
        print(f"  fringe top u {top:.4f}: {cover:.0%} solid")
        if cover < 0.5: print(f"  FAIL MODEL {os.path.basename(p)}: the fringe's top edge is only {cover:.0%} solid: a gap under the hem"); bad += 1
print(f"MODELS {len(want)} models the plugin names, {len(nifs)} own meshes, {len({t for t, _ in tex})} own textures: {bad} missing")
sys.exit(1 if bad else 0)
