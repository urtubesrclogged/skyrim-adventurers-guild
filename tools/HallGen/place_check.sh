#!/bin/bash
# The placement gates on the working tree, right after something is placed or moved (run whenever an
# object is placed, ideally before a build is run, rather than with every build). No meshes,
# no plugin, no build lock: the layout's export (both parts), the records and measures the gates read, the cells' navmeshes, then only
# the placement gates of gates_all.sh (GATE_SET below), each failure held to gates/accepted.tsv as the build holds it.
# Uncommitted edits are checked (the build checks only the last commit). The results go to the shared gate cache by keys that name
# the export's files from the export, so the next build of the same layout reuses them instead of running them again.
#   bash tools/HallGen/place_check.sh        exit 0 when every placement gate passes or is listed; the failures print
set -uo pipefail
HG="$(cd "$(dirname "$0")" && { pwd -W 2>/dev/null || pwd; })"; source "$HG/env.sh"
B="$HG/blender"; BL="$BLENDER"; W="$HALL_WORK"; C="$W/data-root"; PRIV="$HALL_PRIVATE"
E="$W/place-check/export"; L="$W/place-check/logs"; rm -rf "$E"; mkdir -p "$E" "$L"
t0=$SECONDS; stamp() { echo "-- $1, $((SECONDS - t0))s"; }
COMMON=(AG_GLAZE=all AG_TAG=1 AG_STAIR=approach AG_APPROACH="$B/variants/site5_v4/approach_curve.json" AG_SITE=16014,-49358,568,245 AG_MAP="$PRIV/site/mapdata.json")
(cd "$B" && env AG_EXPORT="$E" "${COMMON[@]}" timeout 1800 "$BL" -b -P guildhall_gen.py -- "$C" "$E" > "$L/export.log" 2>&1) &
(cd "$B" && env AG_INTERIOR=1 AG_STAIRS=W AG_EXPORT="$E" "${COMMON[@]}" timeout 1800 "$BL" -b -P guildhall_gen.py -- "$C" "$E" > "$L/export_int.log" 2>&1) &
wait
if grep -q Traceback "$L/export.log" "$L/export_int.log" || [ ! -f "$E/hall2_interior.json" ] || [ ! -f "$E/hall2_site_1.json" ]; then
  grep -A6 Traceback "$L/export.log" "$L/export_int.log" | head; echo "PLACE CHECK STOPPED: the export"; exit 1; fi
stamp export
bash "$HG/gates_export.sh" "$E" > "$L/gates_export.log" 2>&1 || { tail -3 "$L/gates_export.log"; echo "PLACE CHECK STOPPED: the records and measures"; exit 1; }
stamp "records and measures"
cd "$B"
for c_ in interior lookout basement; do python navgen.py "$E/hall2_$c_.json" "$E/nav_$c_.json" --records "$E/records.json" > "$L/nav_$c_.log" 2>&1 & done
wait
for c_ in interior lookout basement; do [ -s "$E/nav_$c_.json" ] || { tail -3 "$L/nav_$c_.log"; echo "PLACE CHECK STOPPED: navgen $c_"; exit 1; }; done
stamp navmeshes
# the placement gates: where pieces stand, what they cut, reach and block, the navmesh round them, lights, seams, flicker
GATE_SET="place_* through_* centre_* contact_* furniture_* hang physics inside_* hearth light_* seams_* coplanar" \
  bash "$HG/gates_all.sh" "$E" "$C" > "$L/gates.log" 2>&1; g=$?
grep -E "^(gates reused|slowest|listed ok|OPEN|NEW FAILURES|  )" "$L/gates.log" | grep -v "^OPEN FAIL STRIP" | cut -c1-170
stamp gates
[ $g -eq 0 ] && echo "PLACE CHECK OK (log: $L/gates.log)" || echo "PLACE CHECK FAILED: a placement gate (log: $L/gates.log)"
exit $g
