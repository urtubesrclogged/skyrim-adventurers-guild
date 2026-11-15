#!/bin/bash
# Every gate on an exported build, in one place (fixes were causing knock-on problems; the audit: hang_check.py, leak_check.py
# and furniture_check.py had fallen out of the chain when it was reorganised, and 9 fixtures went out over the height rule). Writes each log beside the export, then every FAIL
# against the build before it: a failure that was not there before stops the build.
#   bash gates_all.sh <export dir> <clean Data root> [<previous export dir>]        exit 1 on any new failure
# With BUILD=<build dir> set, also every file the plugin and meshes name (models_check.py).
# Not here, for the shell and site only when those change: clearance_check, decal_support_check, roof_cover_check, ivy_fit_check, the clip check.
E="${1:?export dir}"; C="${2:?clean Data root}"; P="${3:-}"; here="$(cd "$(dirname "$0")" && pwd)"; B="$here/blender"
source "$here/status/hook.sh"; status_step "hall gates" "$(basename "$E")${BUILD:+ on $(basename "$BUILD")}"   # (the status page: build/status/index.html)
BL="${BL:-/c/Program Files/Blender Foundation/Blender 5.2/blender.exe}"; L="$E/gates"; mkdir -p "$L"; cd "$B"
# (the build was too slow) each gate through gate(): its log kept and reused while nothing it reads has
# changed (blender/gate_cache.py: the command, every file and folder it names, by content, and all the gates' code); one that fell
# over is never kept. The cache: build/hall-work/gate-cache. GATE_CACHE=0 runs every gate afresh
GC="${HALL_WORK:-$here/../../build/hall-work}/gate-cache"; FP="$L/.gatefp.json"; : > "$L/.cached"
python gate_cache.py prepare "$FP" "$GC" "$C" ${BUILD:+"$BUILD"} "$E"
# (placement gates run whenever an object is placed, ideally before a build is run) GATE_SET: names (globs) of the
# gates to run, the rest skipped: place_check.sh runs the placement ones this way on a layout export. Keys name the export's files
# relative to it (GATE_EXPORT), so a run on another folder's identical export is reused by the build. Each gate's time: $L/.times
gate_in_set() { [ -z "${GATE_SET:-}" ] && return 0; local p ps_; read -ra ps_ <<< "$GATE_SET"   # (read: never globbed against this folder's files,
  for p in "${ps_[@]}"; do [[ "$1" == $p ]] && return 0; done; return 1; }                         # where through_* named through_check.py)
: > "$L/.times"; export GATE_EXPORT="$E"
gate() {   # gate <log> <command ...>
  local log="$1"; shift; local k="" name_; name_="$(basename "$log" .log)"
  gate_in_set "$name_" || return 0
  local t0_; t0_=$(date +%s%N)
  [ "${GATE_CACHE:-1}" = 0 ] || k="$(python gate_cache.py key "$FP" "$@" "$E/mesh_info.json" "$E/records.json")"   # (nav_routes.py reads mesh_info.json beside the export unnamed: every key takes both)
  if [ -n "$k" ] && [ -f "$GC/$k" ]; then cp "$GC/$k" "$log"; echo "$(basename "$log")" >> "$L/.cached"; echo "$name_ $(( ($(date +%s%N) - t0_) / 1000000 )) reused" >> "$L/.times"; return 0; fi
  "$@" > "$log" 2>&1; [ -n "$k" ] && python gate_cache.py put "$log" "$GC/$k"
  echo "$name_ $(( ($(date +%s%N) - t0_) / 1000000 )) ran" >> "$L/.times"; return 0
}
for c_ in basement lookout interior; do
  # (the build's time: each gate reads the export and writes its own log, nothing waits on another: all at once, on 16 cores; the `wait` below holds the verdict for the last)
  gate "$L/place_$c_.log" python placement_check.py "$E/hall2_$c_.json" --mesh "$E/mesh_info.json" --records "$E/records.json" &
  gate "$L/through_$c_.log" timeout 280 python through_check.py "$E/hall2_$c_.json" --mesh "$E/mesh_info.json" --data "$C" --nav "$E/nav_$c_.json" &
  gate "$L/centre_$c_.log" python centre_check.py "$E/hall2_$c_.json" --mesh "$E/mesh_info.json" &
done
[ -n "$BUILD" ] && { gate "$L/models.log" python models_check.py "$BUILD" "$C"; tail -1 "$L/models.log"; } &
gate "$L/hang.log" python hang_check.py "$E/hall2_interior.json" "$E/hall2_basement.json" "$E/hall2_lookout.json" &
gate "$L/physics.log" python physics_check.py "$E/hall2_interior.json" "$E/hall2_basement.json" "$E/hall2_lookout.json" --data "$C" &
gate "$L/seal.log" python seal_check.py "$E/hall2_basement.json" &
gate "$L/coplanar.log" python coplanar_check.py "$E/hall2_basement.json" --interior --top 5 --fail &
# (2026-11-05: the site's pieces were checked only in gates_export.sh, whose exit the build ignored, and without the building or the
# ground, so 1418 reports nobody read) the site, its pieces against the body's collision and the ground; the flora reported apart
PLANTS_RE='flora|fern|clover|lavender|leaves|ivy|tree|bush|shrub|jazbay|juniper|snowberry|dragonstongue|nirnroot|thistle'
gate "$L/place_site.log" python placement_check.py "$E/hall2_site_1.json" --mesh "$E/mesh_info_site.json" --records "$E/records_site.json" --shell "$E/hall2_body.json" --ground "$E/hall2_site_1.json" --plants "$PLANTS_RE" &
(gate "$L/furniture_interior.log" python furniture_check.py "$E/hall2_interior.json" "$L/furn"; gate "$L/furniture_lookout.log" python furniture_check.py "$E/hall2_lookout.json" "$L/furn" --levels lookout) &
for c_ in interior basement; do gate "$L/routes_$c_.log" timeout 900 python nav_routes.py "$E/nav_$c_.json" "$E/hall2_$c_.json" --doors & done
# (2026-11-03, the NPC session: Willem's and Merila's routines go up the ladder to the strongroom; its own cell was never routed) the lookout too, no beds
gate "$L/routes_lookout.log" timeout 600 python nav_routes.py "$E/nav_lookout.json" "$E/hall2_lookout.json" --doors --no-beds &
# (2026-11-04: Henriette found standing on the dining table; navgen had skipped every piece missing from its footprint table, so the navmesh
# ran inside 20 of them) no navmesh inside a solid piece, in each cell
for c_ in interior basement lookout; do gate "$L/inside_$c_.log" python nav_inside_check.py "$E/nav_$c_.json" "$E/hall2_$c_.json" & done
# (2026-11-11, the navmesh rebuild: the foot of the basement stair, with the door down, was cut off from the stair, and nav_routes passed it,
# routing from that landing as from every other) each cell's navmesh one piece, at every edge and at edges an actor fits; the library loft
# is reached only by its ladder hatch
for c_ in interior basement lookout; do al_=(); [ $c_ = interior ] && al_=(--allow AGHall2LibraryHatch); gate "$L/connect_$c_.log" python nav_connect_check.py "$E/nav_$c_.json" "$E/hall2_$c_.json" "${al_[@]}" & done
gate "$L/hearth.log" timeout 280 python hearth_check.py "$E/hall2_interior.json" "$E/nav_interior.json" "$C" &
for c_ in interior basement lookout; do gate "$L/contact_$c_.log" timeout 280 python contact_check.py "$E/hall2_$c_.json" "$E/nav_$c_.json" & done
gate "$L/frame.log" python frame_check.py "$E/hall2_interior.json" &
# (baseboards that did not meet, bright seams beside the posts throughout the hall) the seam
# gate: upright strips of plaster or stone left showing beside a timber, and the baseboards' ends (interior_gen.py baseboards())
gate "$L/seams_interior.log" "$BL" -b -P seam_check.py -- "$E/hall2_interior.json" "$E/baseboards_W.json" &
for c_ in basement lookout; do gate "$L/seams_$c_.log" "$BL" -b -P seam_check.py -- "$E/hall2_$c_.json" & done
[ -n "${BUILD:-}" ] && gate "$L/fresh.log" python fresh_check.py "$E" "$BUILD/meshes/AdventurersGuild/Hall2" &
[ -n "${BUILD:-}" ] && gate "$L/door_body.log" python door_body_check.py "$BUILD/meshes/AdventurersGuild/Hall2" &
[ -n "${BUILD:-}" ] && gate "$L/banner.log" python banner_check.py "$BUILD/meshes/AdventurersGuild/Hall2" &
[ -n "${BUILD:-}" ] && gate "$L/window_emit.log" python window_emit_check.py "$BUILD/AdventurersGuild - Guild Hall.esp" "$BUILD/meshes/AdventurersGuild/Hall2" &
[ -n "${BUILD:-}" ] && gate "$L/plaster.log" python plaster_check.py "$BUILD/AdventurersGuild - Guild Hall.esp" "$BUILD/meshes/AdventurersGuild/Hall2" &
[ -n "${BUILD:-}" ] && gate "$L/lock.log" python lock_check.py "$BUILD/AdventurersGuild - Guild Hall.esp" "$E" ../npcs/schedules.json &
gate "$L/light_basement.log" python light_check.py "$E/hall2_basement.json" --rooms training:-280,51,336,759,-304 range:336,215,1400,759,-304 cellar:-1465,200,-1100,940,-256 henriette:-1465,-60,-1060,168,-272 &
# (allowed without a fixture of their own: the hearth's soft glow out before it; the tavern's fill, between its two chandeliers; the board's light, by design: a chandelier there hung between the board and its readers)
gate "$L/light_interior.log" python light_check.py "$E/hall2_interior.json" --allow "-760,530;432,640;0,775" --rooms tavern:-1080,190,-420,860,0 &
gate "$L/light_lookout.log" python light_check.py "$E/hall2_lookout.json" &   # (2026-11-05: the strongroom had no light gate; its lights went in unchecked)
gate "$L/leak_interior.log" "$BL" -b -P leak_check.py -- "$E/hall2_interior.json" --seed 0,500,0 --json "$L/leak_int.json" &
gate "$L/leak_lookout.log" "$BL" -b -P leak_check.py -- "$E/hall2_lookout.json" --seed 510,950,1080 &
# (2026-11-06: Henriette's room's first cut left a slot under the cellar's wall into the void; the basement had no leak gate, and the
# seal check's rays missed it) the basement too, from the main hallway
gate "$L/leak_basement.log" "$BL" -b -P leak_check.py -- "$E/hall2_basement.json" --seed -600,860,-256 &
# (the tavern's ivy stood 34 off its wall; the ivy gate had looked at the site's alone) every cell's ivy on its wall
for c_ in interior basement lookout; do gate "$L/ivy_$c_.log" "$BL" -b -P ivy_fit_check.py -- "$E/hall2_$c_.json" "$C" & done
wait
echo "gates reused unchanged: $(sort -u "$L/.cached" | wc -l)"
echo "slowest gates (ms): $(sort -k2 -n -r "$L/.times" | head -5 | awk '{printf "%s %s %s; ", $1, $2, $3}')"
# (2026-11-06) the leak checks as FAIL lines: their old pattern ("[1-9] leak") matched nothing they print, so a gap into the void or a
# rise in faces seen from behind (61 -> 163 with the posts' change of 2026-11-05) passed every build. Any gap fails; the count of faces
# seen from behind is held to gates/accepted.tsv like any line, so a new count stops the build until looked at
python - "$L" > "$L/leak_summary.log" <<'PY'
import glob, os, re, sys
for f in sorted(glob.glob(os.path.join(sys.argv[1], "leak_*.log"))):
    for l in open(f, encoding="utf-8", errors="replace"):
        m = re.match(r"LEAK (\S+): .*?(\d+) faces seen from behind.*?(\d+) gaps into the void", l)
        if not m: continue
        if int(m.group(3)): print(f"FAIL LEAK {m.group(1)}: {m.group(3)} gaps into the void")
        if int(m.group(2)): print(f"FAIL LEAK {m.group(1)}: {m.group(2)} faces seen from behind")
PY
grep -h -E "FAIL|BAD |UNUSABLE|DOORWAY|SWING|POCKET|PINCH|FACING|UNKNOWN " "$L"/*.log | sed 's/[[:space:]]\+/ /g' | sort -u > "$L/fails.txt"
# (a gate that fell over is no pass: hall2bz's placement gate died on an empty file and 90 failures left this list without a word)
for f_ in "$L"/*.log; do grep -q -E "^Traceback|Error: |Error.*No such file" "$f_" && echo "FAIL GATE DID NOT RUN $(basename "$f_"): $(tail -1 "$f_" | cut -c1-120)" >> "$L/fails.txt"; done
for f_ in ${BUILD:+door_body} ${BUILD:+banner} ${BUILD:+window_emit} ${BUILD:+plaster} ${BUILD:+lock} ${BUILD:+fresh} frame hearth place_interior place_basement place_lookout through_interior through_basement through_lookout centre_interior centre_basement hang contact_interior contact_basement contact_lookout inside_interior inside_basement inside_lookout connect_interior connect_basement connect_lookout routes_interior routes_basement routes_lookout seams_interior seams_basement seams_lookout place_site coplanar leak_interior leak_lookout leak_basement ivy_interior ivy_basement ivy_lookout; do gate_in_set "$f_" || continue; [ -s "$L/$f_.log" ] || echo "FAIL GATE DID NOT RUN $f_: no log" >> "$L/fails.txt"; done
sort -u -o "$L/fails.txt" "$L/fails.txt"
grep -h "^HANG" "$L/hang.log" | cut -c1-90
for f in hearth seams_interior contact_interior contact_basement contact_lookout through_interior through_lookout through_basement centre_interior centre_basement physics routes_interior routes_basement routes_lookout light_interior light_basement light_lookout; do
  [ -f "$L/$f.log" ] && tail -1 "$L/$f.log" | cut -c1-120 | sed "s/^/$f: /"
done
grep -h "^LEAK" "$L"/leak_*.log 2>/dev/null | cut -c1-120
echo "failures in all: $(wc -l < "$L/fails.txt")"
[ -n "$P" ] && [ -f "$P/gates/fails.txt" ] && { gone_="$(comm -23 "$P/gates/fails.txt" "$L/fails.txt")"; [ -n "$gone_" ] && { echo "gone since the build before:"; echo "$gone_" | cut -c1-150; }; }
# (2026-11-03: every failure must be listed in gates/accepted.tsv, ok with its reason or open as a known fault; the open ones print every build.
# Until then a failure passed once it had been in the build before: the tower hatch's sat there unread until an in-game test found it)
python - "$here/gates/accepted.tsv" "$L/fails.txt" <<'PY' || exit 1
import sys
acc = {}
for l in open(sys.argv[1], encoding="utf-8"):
    if l.startswith("#") or not l.strip(): continue
    st, line, why = l.rstrip("\n").split("\t", 2); acc[line] = (st, why)
fails = [l.rstrip("\n") for l in open(sys.argv[2], encoding="utf-8") if l.strip()]
unl = [f for f in fails if f not in acc]; opn = [f for f in fails if acc.get(f, ("",))[0] == "open"]
print(f"listed ok {sum(1 for f in fails if acc.get(f, ('',))[0] == 'ok')}, open {len(opn)}, unlisted {len(unl)} of {len(fails)}; stale entries {sum(1 for k in acc if k not in fails)}")
for f in opn: print("OPEN", f.strip()[:150], "|", acc[f][1][:80])
if unl:
    print("NEW FAILURES (not in gates/accepted.tsv):")
    for f in unl: print(" ", f.strip()[:170])
    sys.exit(1)
print("no new failures")
PY
