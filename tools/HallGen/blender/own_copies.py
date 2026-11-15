"""The built-in pieces under our own paths (so the pieces that read as part of the building stop changing per install). Vanilla's meshes, never a replacer's, retargeted by
retarget_nif.py to palette C's textures (textures/make_materials.py --built; the textures session's MAP.txt). Hall2.cs's OwnCopies gives each a record that keeps the original's behaviour.
    python own_copies.py <clean Data root> <out meshes dir>           exit 1 if a mesh keeps a texture this table does not name"""
import json, os, re, subprocess, sys, tempfile
ROOT, OUT = sys.argv[1:3]; HERE = os.path.dirname(os.path.abspath(__file__)); BS = chr(92)
P = "textures" + BS + "AdventurersGuild" + BS + "Hall2" + BS
TEX = {"bar01": "AGH2Bar", "sdoor03": "AGH2Door3", "sdoor02": "AGH2Door2", "sstuccowallint01": "AGH2Plaster", "sintwalltop01": "AGH2FireTop", "sintcoloumn01": "AGH2FireColumn",
       "farmhouse01": "AGH2Farm", "woodpost02": "AGH2Post", "imperialwallsconce01": "AGH2Sconce"}
MESH = ("clutter/barset/barstraight01", "clutter/barset/barleft01", "clutter/barset/barright01", "architecture/solitude/doors/ssingledoorint01l", "architecture/solitude/doors/ssingledoorint01r", "architecture/solitude/doors/sdoubledoorint01",
        "architecture/solitude/doors/shouseintdoor02load", "architecture/solitude/interiors/smdcfireplace01", "architecture/farmhouse/interior/basement/farmbtrapdoor01",
        "architecture/farmhouse/interior/basement/farmbtrapdoor02", "clutter/common/torchpermanent01", "clutter/imperial/impwallsconcecandle01",
        "clutter/imperial/impwallsconce02candleon01", "clutter/imperial/impchandelliercandle01")
STILL = ("sdoubledoorint01", "shouseintdoor02load")          # the front and patio doors (activators), the basement's pair (load doors)
mp = {}
for k, v in TEX.items():
    mp[k + ".dds"] = P + v + ".dds"; mp[k + "_n.dds"] = P + v + "_n.dds"
f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8"); json.dump(mp, f); f.close()
bad = 0
for m in MESH:
    src = os.path.join(ROOT, "meshes", *m.split("/")) + ".nif"; name = m.split("/")[-1]
    dst = os.path.join(OUT, "AGH2C" + name + ".nif")
    r = subprocess.run([sys.executable, os.path.join(HERE, "retarget_nif.py"), src, dst, f.name], capture_output=True, text=True); line = r.stdout.strip()
    print(line[:170])
    left = re.search(r"left as they were: (.*)", line)
    kept = [t for t in re.findall(r"'([^']+)'", left.group(1) if left else "") if not re.search(r"(?i)cubemaps|_em\.dds|glow|torch_|candles01|textures.+effects.+", t)]
    if r.returncode or kept: print(f"  FAIL COPY {name}: {kept or r.stderr[-200:]}"); bad += 1
    if name in STILL:                                        # (teleport doors: they never swing, and the swing is what sticks: strip_door_anim.py)
        r = subprocess.run([sys.executable, os.path.join(HERE, "strip_door_anim.py"), dst], capture_output=True, text=True); print(r.stdout.strip()[:170] or r.stderr[-170:])
        if r.returncode: print(f"  FAIL COPY {name}: its animation could not be taken off"); bad += 1
        r = subprocess.run([sys.executable, os.path.join(HERE, "flatten_door_bodies.py"), dst], capture_output=True, text=True); print(r.stdout.strip()[:170] or r.stderr[-170:])   # (and the prompt stays on the door)
        if r.returncode: print(f"  FAIL COPY {name}: its collision bodies could not be flattened"); bad += 1
# (2026-11-03, the overmantel's display) the dragonbone sword as a static: vanilla's mesh, its own textures, its scabbard (Scb) hidden, as a
# weapon's world reference hides it and a static would not (hide_shapes.py); the blood edges are hidden in vanilla's file already
r = subprocess.run([sys.executable, os.path.join(HERE, "hide_shapes.py"), os.path.join(ROOT, "meshes", "dlc01", "weapons", "dragonbone", "sword.nif"),
                    os.path.join(OUT, "AGH2DisplaySword.nif"), "Scb"], capture_output=True, text=True); print(r.stdout.strip()[-170:] or r.stderr[-170:])
if r.returncode: print("  FAIL COPY the display sword: its scabbard could not be hidden"); bad += 1
os.unlink(f.name); print(f"COPIES {len(MESH)} meshes, {bad} with a vanilla texture left"); sys.exit(1 if bad else 0)
