#!/bin/bash
# Deploys a Guild Hall build to the test installs (every approved hall build goes to all of them; the installs are
# HALL_INSTALLS in local.env, tools/HallGen/env.sh). The build only: AG's DLL, which places the hall and patches its navmesh,
# goes in with AG's own deploy.sh, so the installs always hold the same files.
#   bash deploy_hall.sh [<build dir>] [<install> ...]        (no build dir: build/hall; no install: every one in HALL_INSTALLS)
# Refuses while that install's game runs (MO2 is locked then). The files it replaces are copied to
# build/deploy-backups/<target>-<time>/ first. Since 2026-10-27 the target is each install's "Adventurers Guild 2.0"
# folder (AG's deploy.sh makes it); new folders and plugin ticks are done by hand in MO2.
set -euo pipefail
here="$(cd "$(dirname "$0")" && { pwd -W 2>/dev/null || pwd; })"; source "$here/env.sh"; ag="$AG_ROOT"
build="$HALL_BUILD"; [ $# -gt 0 ] && [ -d "$1" ] && { build="$1"; shift; }
targets=("$@"); [ ${#targets[@]} -eq 0 ] && targets=("${INSTALL_NAMES[@]}")
source "$here/lock.sh"; build_lock "deploy_hall.sh"   # (one build or deploy at a time: build.sh holds it already when it runs this)
source "$here/status/hook.sh"; status_step "hall deploy" "$(basename "$build") to ${targets[*]}"; trap 'status_end; build_unlock' EXIT   # (the status page: build/status/index.html)
# (one MO2 folder per AG version, "Adventurers Guild 2.0" holding the Guild Hall too, so picking 2.0
# is one checkbox) the hall's files go into that folder; AG's own deploy.sh owns the rest of it, and nothing here
# removes a file this script did not put there (only what earlier builds left behind, in $gone below)
# (2026-10-27) the hall's plugin is "AdventurersGuild - Guild Hall.esp", a full plugin with the NPCs merged in
# (npcs/merge_npcs.sh, run on the build first); the old AGHallSpike.esp goes from the package and from every install, or
# the hall would load twice
esp="AdventurersGuild - Guild Hall.esp"; old="AGHallSpike.esp"
for f in "$build/$esp" "$build/SKSE/Plugins/AdventurersGuild/Hall/hall2.json" "$build/SKSE/Plugins/AdventurersGuild/Hall/outdoor/outdoor_nav.json" "$build/Scripts/AGHallNative.pex"; do [ -f "$f" ] || { echo "missing $f"; exit 1; }; done
# (2026-10-27) no placed reference may name a base the plugin lacks: hall2au-hall2ax crashed the game on loading the hall's
# cell with three retired board refs on STATs no longer written (a disabled ref with a missing base still crashes)
python "$(dirname "$0")/check_dangling.py" "$build/$esp" || { echo "refusing to deploy: placed refs with a missing base"; exit 1; }
# (2026-10-28) every navmesh read as the game reads it, to the last byte, the reader calibrated on vanilla's: hall2be's
# grid (uint16 counts where the game reads uint32) crashed the game at the main menu, and hall2ba-bd had carried it by luck
python "$(dirname "$0")/check_navmesh.py" "$build/$esp" --calibrate "${SKYRIM_DATA:?local.env: SKYRIM_DATA}/Skyrim.esm" || { echo "refusing to deploy: a navmesh the game would misread"; exit 1; }

# (the deploy was too slow) deploy_sync.py lays the layers in this order, later wins: the build
# (plugin, meshes, textures, layout, the NPCs' hair, the hall's scripts). Every file compared byte for byte by hash, only what differs copied, backed up to
# build/deploy-backups/<target>-<time>/ first and compared again
# (2026-11-13, the spike clean-up) what earlier builds put there and nothing ships now: the hall's own DLL (AGNavSpike.dll, folded into
# AdventurersGuild.dll; left in place it would place the hall a second time), its script, the old names of the travel and door scripts,
# the layout's old folder, the stair patch, and retired scripts and meshes
gone=("$old" "SKSE/Plugins/AGNavSpike.dll" "Scripts/AGNavSpike.pex" "Scripts/AGHallSpike.pex" "Scripts/AGHallSpikeDoor.pex"
  "SKSE/Plugins/AGHallSpike/hall2.json" "SKSE/Plugins/AGHallSpike/outdoor/outdoor_nav.json" "SKSE/Plugins/AGHallSpike/navmesh/patch_stair.json"
  "Scripts/AGHall2.pex" "Scripts/AGHallBoardRotate.pex" "Scripts/AGHallDayNight.pex" "meshes/AdventurersGuild/Hall2/AGHall2WindowsDay.nif")
targs=()
for t in "${targets[@]}"; do
  d="${INSTALL_DIR[$t]:-}"; [ -n "$d" ] || { echo "$t: not an install in HALL_INSTALLS"; exit 1; }
  if game_running "$t"; then echo "$t: ${INSTALL_EXE[$t]} is running - not deployed"; continue; fi
  [ -d "$d" ] || { echo "$t: $d does not exist (AG 2.0 is deployed first, by deploy.sh) - not deployed"; continue; }
  for g in "${gone[@]}"; do rm -f "$d/$g"; done
  for g_ in navmesh outdoor ""; do [ -d "$d/SKSE/Plugins/AGHallSpike/$g_" ] && rmdir "$d/SKSE/Plugins/AGHallSpike/$g_" 2>/dev/null; done; true
  left=0; for g in "${gone[@]}"; do [ -e "$d/$g" ] && { echo "$t: $g still there - not deployed"; left=1; }; done; [ $left -eq 0 ] || continue
  targs+=(--target "$t" "$d")
done
[ ${#targs[@]} -gt 0 ] || { echo "nothing to deploy to"; exit 0; }
# (2026-11-13) the stair patch is gone: the outdoor navmesh (SKSE/Plugins/AdventurersGuild/Hall/outdoor/, in the build) covers the grand stair
extra=()
python "$here/deploy_sync.py" "$ag/build/deploy-backups" "$(date +%Y%m%d-%H%M%S)" --layer "$build" \
  "${extra[@]}" $(for g in "${gone[@]}"; do printf -- '--drop %q ' "$g"; done) --drop "hall-owners.json" --manifest "$ag/build/deploy-manifests" "${targs[@]}" || { echo "NOT DEPLOYED CLEANLY"; exit 1; }
