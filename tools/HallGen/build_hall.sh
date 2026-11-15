#!/bin/bash
# Builds the Guild Hall into build/hall, then runs every gate on it (one build and deploy for every session,
# out of any session's scratch folder). Steps, each logged in build/hall-work/logs:
#   export   the hall's shell, site and cells from blender/guildhall_gen.py (exterior and interior at once)
#   first    the export's own checks (gates_export.sh: placement, seal, coplanar faces, the site's pieces)
#   meshes   rooms, basement, bake, pool seat, banners, sign, site, shell, lookout (each only if what it is made from changed:
#            mesh_cache.py), then the NIF checks and the door check
#   plugin   navmeshes, the plugin (Hall2.cs, IDs carried from the ledger), the NPCs merged in (npcs/merge_npcs.sh), verify
#   scripts  the hall's own Papyrus, compiled and scrubbed into the build
#   gates    gates_all.sh against the gates' baseline (build/hall-work/gates-base): a failure not in gates/accepted.tsv stops it
#   bash tools/HallGen/build_hall.sh        exit 0 only when every step and gate passed; nothing is deployed here (build.sh)
# Inputs: AG's local.env (env.sh), tools/hall-private (assets made from the game's files, the site's map data, the full Papyrus
# headers), build/hall-work (the extracted data root the meshes are built against, the mesh cache, the ledger, the baseline).
set -uo pipefail
HG="$(cd "$(dirname "$0")" && { pwd -W 2>/dev/null || pwd; })"; source "$HG/env.sh"
source "$HG/status/hook.sh"; status_step "hall build" "$(git -C "$AG_ROOT" log -1 --format=%h)"
B="$HG/blender"; BL="$BLENDER"; W="$HALL_WORK"; C="$W/data-root"; E="$W/export"; L="$W/logs"; K="$W/meshkeys"; PRIV="$HALL_PRIVATE"
O="$HALL_BUILD/meshes/AdventurersGuild/Hall2"; TX="$HALL_BUILD/textures/AdventurersGuild/Hall2"; TD="$C/textures/adventurersguild/hall2"
ESP="AdventurersGuild - Guild Hall.esp"; HN="$B/hall_nif.py"
mkdir -p "$L" "$K" "$O" "$TX"
for d in "$C" "$W/ledger" "$W/gates-base" "$PRIV"; do [ -e "$d" ] || { echo "missing $d (see the header)"; exit 1; }; done
t0=$SECONDS; stamp() { echo "-- $1, $((SECONDS - t0))s"; }
fail() { echo "BUILD FAILED: $1"; exit 1; }

# ---- the prebuilt assets first (tools/hall-private/prebuilt: textures and meshes their own generators make, such as
# make_hall_textures.py's upscaled copies, the paintings, the chains, the Guild Board and the leader board): laid as they are
[ -d "$PRIV/prebuilt" ] || fail "no $PRIV/prebuilt"
cp -r "$PRIV/prebuilt/." "$HALL_BUILD/"

# ---- the builder, the banner's cloth and the glass (the meshes name them)
(cd "$HG" && dotnet build -c Release -v q > "$L/dotnet.log" 2>&1) || { grep -E " error " "$L/dotnet.log" | sort -u | head -5; fail "the plugin builder does not compile"; }
python "$HG/textures/make_cloth_banner.py" "$C/textures" "$PRIV/assets/textures/AdventurersGuild/Hall/AGHallCrest.dds" "$TX" > "$L/cloth_banner.log" 2>&1 || fail "the banner's cloth"
cp "$TX"/AGH2BannerCloth*.dds "$TD/"
# the tavern's panelling (textures/make_wainscot.py, from the bar's AGH2Bar): in the data root before the meshes are made, which check every texture
[ -f "$W/materials/built/AGH2Wainscot.dds" ] || python "$HG/textures/make_wainscot.py" "$W/materials/built" "$W/materials/built" > "$L/wainscot.log" 2>&1 || fail "the panelling's textures"
cp "$W/materials/built/"AGH2Wainscot*.dds "$TD/"
cp "$W/materials/glass/"* "$TD/"; cp "$W/materials/glass/"* "$TX/"

# ---- export
rm -rf "$E"; mkdir -p "$E"
COMMON=(AG_GLAZE=all AG_TAG=1 AG_STAIR=approach AG_APPROACH="$B/variants/site5_v4/approach_curve.json" AG_SITE=16014,-49358,568,245 AG_MAP="$PRIV/site/mapdata.json")
(cd "$B" && env AG_EXPORT="$E" "${COMMON[@]}" timeout 1800 "$BL" -b -P guildhall_gen.py -- "$C" "$E" > "$L/export.log" 2>&1) &
(cd "$B" && env AG_INTERIOR=1 AG_STAIRS=W AG_EXPORT="$E" "${COMMON[@]}" timeout 1800 "$BL" -b -P guildhall_gen.py -- "$C" "$E" > "$L/export_int.log" 2>&1) &
wait
if grep -q Traceback "$L/export.log" "$L/export_int.log" || [ ! -f "$E/hall2_basement.json" ] || [ ! -f "$E/hall2_interior.json" ] || [ ! -f "$E/hall2_site_1.json" ]; then
  grep -A6 Traceback "$L/export.log" "$L/export_int.log" | head; fail "export"; fi
echo "EXPORT OK"; stamp export
bash "$HG/gates_export.sh" "$E" > "$L/gates_export.log" 2>&1 & GX=$!   # (alongside the meshes: it reads only the export)

# ---- meshes: the interior's rooms (checked and cut by room, a NIF and a bake each), the basement
cd "$B"
python navgen.py "$E/hall2_interior.json" "$E/nav_interior.json" > "$L/nav_pre.log" 2>&1 || fail "navgen"
"$BL" -b --factory-startup --python-exit-code 1 -P rooms_check.py -- "$E/hall2_interior.json" "$E/nav_interior.json" "$E/rooms.json" > "$L/rooms.log" 2>&1; echo "rooms check exit $?"
[ -f "$E/rooms.json" ] || fail "no rooms.json"
python split_rooms.py "$E/hall2_interior.json" "$E/rooms.json" "$E" > "$L/split.log" 2>&1 || fail "split_rooms"
python "$HG/textures/make_window_glass.py" "$TX" > "$L/window_glass.log" 2>&1 || fail "window glass"
cp "$TX/"AGH2XWinD*.dds "$TD/"
rm -f "$O/AGHall2Interior.nif" "$O"/AGHall2Bake*.nif
python "$HG/textures/make_wear_textures.py" "$TX" "$TD" > "$L/wear.log" 2>&1 || fail "wear textures"
# the banner's and sign's textures (the meshes name them) before any mesh, then the textures' print once for every mesh's key
python "$HG/textures/make_banner_texture.py" "$TX" A > "$L/banner_tex.log" 2>&1 || fail "banner texture"
rm -f "$TX"/AGH2Banner*.png; cp "$TX/AGH2Banner.dds" "$TX/AGH2Banner_n.dds" "$TD/"
python "$HG/textures/make_sign_texture.py" "$C/textures" "$PRIV/assets/textures/AdventurersGuild/Hall/AGHallCrest.dds" "$TX" "$AG_ROOT/config/PrismaUI/views/AdventurersGuild/fonts/Cyrodiil.otf" > "$L/sign_tex.log" 2>&1 || fail "sign texture"
cp "$TX"/AGH2SignGuild*.dds "$TD/"
export MESH_TEX_FP="$(python "$B/gate_cache.py" fp "$W/gate-cache" "$TD")"
cached() { out="$1"; shift; python "$B/mesh_cache.py" hit "$K" "$out" "$TD" "$HN" "$@"; }
stamp_() { out="$1"; shift; python "$B/mesh_cache.py" put "$K" "$out" "$TD" "$HN" "$@"; }
nif() {   # nif <export json> <out nif> [extra]: the mesh, unless what it is made from is unchanged
  local j="$1" o="$2"; shift 2
  if cached "$o" "$j" "$@"; then echo "$(basename "$o"): unchanged"; return 0; fi
  timeout 1500 "$BL" -b -P hall_nif.py -- "$j" "$C" "$o" "$@" > "$L/nif_$(basename "$o").log" 2>&1; local r=$?
  [ $r -eq 0 ] && stamp_ "$o" "$j" "$@"; echo "$(basename "$o"): exit $r"; return $r
}
ROOMS=$(python -c "import json; print(' '.join(json.load(open(r'$E/rooms_parts.json'))))")
set -- $ROOMS; bad=0
while [ $# -gt 0 ]; do RP=(); for k in 1 2 3 4 5 6; do [ $# -gt 0 ] && { nif "$E/hall2_interior_room_$1.json" "$O/AGHall2Room$1.nif" & RP+=($!); shift; }; done; wait "${RP[@]}"; done   # (its own six: not GX)
nif "$E/hall2_basement.json" "$O/AGHall2Basement.nif" || bad=1
timeout 1800 "$BL" -b -P bake_clutter.py -- "$E/hall2_interior.json" "$C" "$O" > "$L/bake.log" 2>&1 || bad=1
"$BL" -b --python-exit-code 1 -P pool_seat_nif.py -- "$C" "$O/AGHall2PoolSeat.nif" > "$L/pool_seat.log" 2>&1 || bad=1
python pool_seat_check.py "$O/AGHall2PoolSeat.nif" >> "$L/pool_seat.log" 2>&1 || fail "pool seat check"
"$BL" -b --python-exit-code 1 -P banner_nif.py -- "$C" "$O/AGHall2Banner330.nif" 330 90 20 > "$L/banner.log" 2>&1 || bad=1
for v_ in A B C D; do "$BL" -b --python-exit-code 1 -P banner_nif.py -- "$C" "$O/AGHall2Banner330$v_.nif" 330 90 20 $v_ > "$L/banner_$v_.log" 2>&1 || bad=1
  cp "$O/AGHall2Banner330$v_.nif" "$C/meshes/adventurersguild/hall2/aghall2banner330$(echo $v_ | tr A-D a-d).nif"; done
for v_ in E F; do "$BL" -b --python-exit-code 1 -P banner_nif.py -- "$C" "$O/AGHall2Banner160$v_.nif" 160 44 12 $v_ > "$L/banner_$v_.log" 2>&1 || bad=1
  cp "$O/AGHall2Banner160$v_.nif" "$C/meshes/adventurersguild/hall2/aghall2banner160$(echo $v_ | tr A-F a-f).nif"; done
python sign_nif.py "$C" "$O/AGHall2Sign.nif" > "$L/sign.log" 2>&1 || fail "sign"; cp "$O/AGHall2Sign.nif" "$C/meshes/adventurersguild/hall2/aghall2sign.nif"
nif "$E/hall2_site_1.json" "$O/AGHall2Site1.nif" || bad=1
nif "$E/hall2_body.json" "$O/AGHall2Body.nif" & N1=$!; nif "$E/hall2_roof.json" "$O/AGHall2RoofSlate.nif" roof=slate & N2=$!; nif "$E/hall2_roof.json" "$O/AGHall2RoofTile.nif" roof=tile & N3=$!
wait $N1 $N2 $N3   # (its own three only: a bare wait also waited on the export checks, GX, and reaped them before their own wait)
nif "$E/hall2_lookout.json" "$O/AGHall2Lookout.nif" || bad=1
grep -h -E "exit [1-9]" "$L"/nif_*.log 2>/dev/null | head -3
[ $bad -eq 0 ] || fail "meshes (logs: nif_*, bake, banner_*, pool_seat)"
python check_hall_nif.py "$O"/*.nif > "$L/check_nif.log" 2>&1; grep -E "BAD [1-9]" "$L/check_nif.log" | head -3 && fail "a NIF check"
cp "$W/materials/built/"*.dds "$TX/"; cp "$W/materials/built/"*.dds "$TD/"
python own_copies.py "$C" "$O" > "$L/own_copies.log" 2>&1 || fail "own copies"
python door_nif_check.py "$O" > "$L/doors.log" 2>&1 || fail "the load doors' meshes"
stamp meshes

wait $GX || fail "the export checks could not make the gates' records and measures (log: gates_export.log)"

# ---- the plugin: navmeshes, the plugin (IDs carried by number from the ledger), the NPCs merged in, verified
cd "$HG"; export HALL2_DIR="$E" HALL2_PREV_ESP="$W/ledger/$ESP"; unset EXTRA_PLUGINS
rm -f "$HALL_BUILD/$ESP" "$HALL_BUILD/$ESP.unmerged"
for c_ in interior lookout basement; do python blender/navgen.py "$E/hall2_$c_.json" "$E/nav_$c_.json" --plot "$L/nav_$c_.png" --records "$E/records.json" > "$L/nav_$c_.log" 2>&1 || fail "navgen $c_"; done
timeout 910 dotnet run -c Release --no-build -- build "$HALL_BUILD" blender/variants/hill.json > "$L/plugin.log" 2>&1 || { grep -E "rror|xception" "$L/plugin.log" | head -3; fail "plugin"; }
timeout 600 dotnet run -c Release --no-build -- refdiff "$W/ledger/$ESP" "$HALL_BUILD/$ESP" --all > "$L/refdiff.log" 2>&1; tail -1 "$L/refdiff.log"
rm -rf "$HALL_BUILD/Sound"; bash npcs/merge_npcs.sh "$HALL_BUILD" > "$L/merge.log" 2>&1 || { tail -5 "$L/merge.log"; fail "NPC merge"; }
timeout 600 dotnet run -c Release --no-build -- verify "$HALL_BUILD/$ESP" > "$L/verify.log" 2>&1 || { tail -5 "$L/verify.log"; fail "verify"; }
stamp plugin
# (2026-11-13) the outdoor navmesh: the terrace, porch, walks, forecourt and stairs, which the DLL fits into the loaded ground navmesh
# (src/plugin/src/hall/outdoor.cpp; plan: hall-private/plans/OUTDOOR_NAVMESH.md). It replaces the old navmesh/patch_stair.json
mkdir -p "$HALL_BUILD/SKSE/Plugins/AdventurersGuild/Hall/outdoor"
python blender/outdoor_nav.py "$E" "$HALL_BUILD/SKSE/Plugins/AdventurersGuild/Hall/outdoor/outdoor_nav.json" --plot "$L/nav_outdoor.png" > "$L/nav_outdoor.log" 2>&1 || { tail -3 "$L/nav_outdoor.log"; fail "outdoor navmesh"; }
tail -1 "$L/nav_outdoor.log"
# (2026-11-13) the fit replayed on each test install's ground (clean dumps in hall-private/navdumps): both feet joined to both doors, both
# ways, and no ground left under the hall
for d_ in "$PRIV"/navdumps/*_clean.json; do
  python blender/outdoor_replay.py "$d_" "$HALL_BUILD/SKSE/Plugins/AdventurersGuild/Hall/outdoor/outdoor_nav.json" --out "$L/replay_$(basename "$d_")" > "$L/replay_$(basename "$d_" .json).log" 2>&1 || { tail -3 "$L/replay_$(basename "$d_" .json).log"; fail "outdoor navmesh replay on $(basename "$d_")"; }
done

# ---- the hall's own scripts, from a folder of their own (Caprica also searches the compiled file's folder, where other stubs would
# shadow the full headers), each .pex header scrubbed (a compiled script records the source path, user and computer: none may ship)
pap="$AG_ROOT/src/hall/papyrus"; stage="$W/pex-stage"; rm -rf "$stage"; mkdir -p "$stage/src" "$W/pex"
cp "$pap"/AGHallTravel.psc "$pap"/AGHallDoor.psc "$pap"/AGHallBackOfficeDoor.psc "$pap"/AGHallBannerLock.psc "$pap"/AGHallNative.psc "$stage/src/"
(cd "$stage/src" && "$CAPRICA" --game skyrim --import "$PRIV/papyrus/headers-full" --import "$AG_ROOT/src/papyrus" --import "$pap/headers" --flags "$PAPYRUS_FLAGS" --output "$W/pex" \
  AGHallTravel.psc AGHallDoor.psc AGHallBackOfficeDoor.psc AGHallBannerLock.psc AGHallNative.psc > "$L/papyrus.log" 2>&1) || { tail -3 "$L/papyrus.log"; fail "the hall's scripts"; }
mkdir -p "$HALL_BUILD/Scripts"
python - "$W/pex" "$HALL_BUILD/Scripts" <<'PY' || fail "script scrub"
import os, struct, sys
for f in ("AGHallBackOfficeDoor.pex", "AGHallDoor.pex", "AGHallTravel.pex", "AGHallBannerLock.pex", "AGHallNative.pex"):
    d = open(os.path.join(sys.argv[1], f), "rb").read(); assert d[:4] == bytes.fromhex("fa57c0de"), f
    pos = 16
    for _ in range(3): pos += 2 + struct.unpack(">H", d[pos:pos + 2])[0]
    head = b"".join(struct.pack(">H", len(x)) + x for x in (f[:-4].encode() + b".psc", b"author", b"build"))
    open(os.path.join(sys.argv[2], f), "wb").write(d[:16] + head + d[pos:])
PY
# the NPCs' and quests' scripts (Caralion, the trials, the followers...), compiled from this commit's sources over the copies the
# NPC merge took from npcs/build/Scripts: those were compiled by hand, and a script change never reached a build without it (the
# Cloudrest armor's script sat uncompiled until an in-game test found it)
rm -rf "$W/npc-pex"; bash "$HG/npcs/build_scripts.sh" "$W/npc-pex" > "$L/npc_scripts.log" 2>&1 || { tail -3 "$L/npc_scripts.log"; fail "the NPCs' scripts"; }
cp "$W/npc-pex/"*.pex "$HALL_BUILD/Scripts/"
stamp scripts

# ---- every gate, against the baseline
cd "$B"; BUILD="$HALL_BUILD" bash "$HG/gates_all.sh" "$E" "$C" "$W/gates-base" > "$L/gates.log" 2>&1; g=$?
grep -E "^(listed ok|NEW FAILURES|  )" "$L/gates.log" | cut -c1-170   # (2026-11-13: new failures in full and first; behind a head -20 the
grep -E "^OPEN" "$L/gates.log" | cut -c1-170 | head -8                    # 17 open lines hid 11 of 12 new ones)
[ $g -eq 0 ] || fail "a gate (log: gates.log)"
stamp done
echo "BUILD OK: $HALL_BUILD"
