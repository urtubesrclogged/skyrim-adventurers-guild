#!/bin/bash
# The ink sketches the notices use (sketch.py), from vanilla's meshes: which mesh, from where. Pulls each mesh from the
# game's BSAs into <cache>, renders it, and copies lines.png + shade.png to notices/sketches/<subject>/.
#   bash make_sketches.sh <cache dir>
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
CACHE="$1"; B="/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"
BL="$HERE/../../blender"
# subject | mesh (under meshes/) | camera yaw | pitch
LIST='skeever|actors/skeever/skeeverstatic.nif|70|15
mudcrab|actors/mudcrab/character assets/mcrab1.nif|60|30
wolf|actors/canine/character assets wolf/wolf.nif|70|12
bear|_byoh/architecture/byohhouse/trophy/byohhousetrophybear4ft01.nif|150|10
troll|_byoh/architecture/byohhouse/trophy/byohhousetrophytrollfrost01.nif|150|10
draugr|_byoh/architecture/byohhouse/trophy/byohhousetrophydraugrm01.nif|150|10
spider|_byoh/architecture/byohhouse/trophy/byohhousetrophyfrstspider01.nif|150|10
hagraven|_byoh/architecture/byohhouse/trophy/byohhousetrophyhagraven01.nif|150|10
spriggan|_byoh/architecture/byohhouse/trophy/byohhousetrophyspriggan01.nif|150|10
sabrecat|actors/sabrecat/sabrecatstatic.nif|70|12
dragon|actors/dragon/character assets/parthurnax.nif|120|30
pickaxe|dlc02/clutter/dlc02pickaxenordic.nif|90|25
ore|dungeons/mines/ore/oreiron01.nif|35|30
crate|clutter/quest/firebrandwinecrate01.nif|35|25
taproot|clutter/ingredients/spriggantaproot.nif|30|35
bearclaws|clutter/ingredients/bearclaws.nif|30|40
soulgem|clutter/soulgem/soulgemcommon01.nif|30|20
helmet|armor/steel/helmetsteelgo.nif|200|10'
echo "$LIST" | while IFS='|' read -r name mesh yaw pitch; do
  (cd "$BL" && PYTHONPATH=. python - "$CACHE" "meshes/$mesh" <<'PY'
import sys, os, glob, bsa
B = chr(92); out, want = sys.argv[1], sys.argv[2].replace("/", B)
if os.path.exists(os.path.join(out, *want.split(B))): sys.exit(0)
for b in sorted(glob.glob("C:/Games/steamapps/common/SkyrimVR/Data/Skyrim - Meshes*.bsa")):
    f, v, c, e, idx = bsa.read_index(b)
    if want in idx:
        p = os.path.join(out, *want.split(B)); os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(bsa.extract(f, v, c, e, *idx[want])); sys.exit(0)
sys.exit("not found: " + want)
PY
  )
  "$B" -b -P "$HERE/sketch.py" -- "$CACHE/meshes/$mesh" "$CACHE/sk/$name" "$yaw" "$pitch" 1024 >/dev/null 2>&1
  mkdir -p "$HERE/sketches/$name"; cp "$CACHE/sk/$name/lines.png" "$CACHE/sk/$name/shade.png" "$HERE/sketches/$name/"
  echo "sketched $name"
done
