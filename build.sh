#!/usr/bin/env bash
# Builds Adventurers Guild with its Guild Hall and deploys them to the test installs: the one command every session uses.
# It publishes nothing; releases are package.sh's.
#   bash build.sh [--no-deploy] [--ag-only | --hall-only] [--force] [<install> ...]   (no install: every one in HALL_INSTALLS, local.env)
# What it does, in order:
#   1. Takes the build lock (tools/HallGen/lock.sh): one build or deploy at a time across sessions; others wait their turn, shown on
#      the status page.
#   2. Builds the last COMMIT, never the working tree: build/build-src is a second checkout of this repository, moved to HEAD, with
#      the ignored inputs (voice sources, tools/hall-private, the textures made from the game's files, local.env...) linked in from
#      here. A session's uncommitted edits never reach a build. Commit, then build.
#   3. Builds only what changed since its last good build: AG (build.ps1) if AG's committed files or its ignored inputs changed; the
#      hall (tools/HallGen/build_hall.sh: export, meshes, plugin, every gate) if the hall's did, or AG's plugin did (the hall masters
#      it). --force builds both.
#   4. Deploys to each install as soon as its own game is closed (MO2 locks its files while it runs), AG (deploy.sh) then the hall
#      (deploy_hall.sh), checks each against the build, and stamps the install on the status page (what it runs, what to test).
# A failed build or gate stops before anything is deployed. Set AG_SESSION to name yourself on the status page.
set -uo pipefail
R="$(cd "$(dirname "${BASH_SOURCE[0]}")" && { pwd -W 2>/dev/null || pwd; })"; source "$R/tools/HallGen/env.sh"
deploy=1; ag=1; hall=1; force=0; targets=()
for a in "$@"; do case "$a" in --no-deploy) deploy=0 ;; --ag-only) hall=0 ;; --hall-only) ag=0 ;; --force) force=1 ;; -*) echo "unknown option $a"; exit 2 ;; *) targets+=("$a") ;; esac; done
[ ${#targets[@]} -eq 0 ] && targets=("${INSTALL_NAMES[@]}")
for t in "${targets[@]}"; do [ -n "${INSTALL_DIR[$t]:-}" ] || { echo "$t: not an install in HALL_INSTALLS"; exit 2; }; done
export HALL_STATUS_DIR="$R/build/status" HALL_BUILD="$R/build/hall" HALL_WORK="$R/build/hall-work" HALL_PRIVATE="$R/tools/hall-private"
ST() { python "$R/tools/HallGen/status/status.py" "$@" > /dev/null 2>&1 || true; }
source "$R/tools/HallGen/lock.sh"; build_lock "build.sh $*"
source "$R/tools/HallGen/status/hook.sh"; status_step "build.sh" "${*:-everything}"
trap 'status_end; build_unlock' EXIT
L="$HALL_WORK/logs"; mkdir -p "$L"
commit="$(git -C "$R" rev-parse HEAD)"; short="${commit:0:7}"
echo "== building $short $(git -C "$R" log -1 --format=%s | cut -c1-80)"
n="$(git -C "$R" status --porcelain --untracked-files=no | wc -l)"; [ "$n" -gt 0 ] && echo "   ($n changed files in this checkout are not committed: they are not in this build)"

# ---- the snapshot: a checkout of the commit, its ignored inputs linked in from here
S="$R/build/build-src"   # (its ignored folders are junctions into this checkout: never delete it with rm -r, which would follow them; git worktree remove)
if [ ! -e "$S/.git" ]; then git -C "$R" worktree add --detach "$S" "$commit" > "$L/build-src.log" 2>&1 || { tail -3 "$L/build-src.log"; echo "BUILD STOPPED: the snapshot checkout"; exit 1; }
else git -C "$S" checkout --detach --force "$commit" > "$L/build-src.log" 2>&1 || { tail -3 "$L/build-src.log"; echo "BUILD STOPPED: the snapshot checkout"; exit 1; }; git -C "$S" clean -fdq; fi
w() { cygpath -w "$1"; }
while IFS= read -r p; do
  p="${p%/}"; case "$p" in build|build/*|src/plugin/build|*__pycache__*|*/bin|*/obj) continue ;; esac
  if [ -d "$R/$p" ]; then [ -e "$S/$p" ] || { mkdir -p "$(dirname "$S/$p")"; powershell -NoProfile -Command "New-Item -ItemType Junction -Path '$(w "$S/$p")' -Target '$(w "$R/$p")' | Out-Null"; }
  else mkdir -p "$(dirname "$S/$p")"; cp -p "$R/$p" "$S/$p"; fi
done < <(git -C "$R" ls-files --others --ignored --exclude-standard --directory)
# (2026-11-14, package.sh's check) the core's voices: this checkout has no voice pipeline, and its build/Sound (the 2.0 set, brought in
# from the main checkout's voice work) is what deploy.sh ships. Skipped with the rest of build/ above, the snapshot had none, so every
# deploy left the installs' voices alone and they kept a 1.6 set (23 2.0 lines silent, 371 older takes).
[ -d "$R/build/Sound" ] && [ ! -e "$S/build/Sound" ] && { mkdir -p "$S/build"; powershell -NoProfile -Command "New-Item -ItemType Junction -Path '$(w "$S/build/Sound")' -Target '$(w "$R/build/Sound")' | Out-Null"; }

# ---- what changed since the last good build (committed files by git; ignored inputs by a fingerprint of their names, sizes and times)
fp() { python - "$@" <<'PY'
import hashlib, os, sys
h = hashlib.blake2b(digest_size=12)
for d in sys.argv[1:]:
    if os.path.isfile(d): s = os.stat(d); h.update(f"{os.path.basename(d)}|{s.st_size}|{int(s.st_mtime)}".encode()); continue
    for root, dirs, files in os.walk(d):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(root, f); s = os.stat(p); h.update(f"{os.path.relpath(p, d)}|{s.st_size}|{int(s.st_mtime)}".encode())
print(h.hexdigest())
PY
}
state() { python -c "import json,sys; print(json.load(open(sys.argv[1])).get('built', {}).get(sys.argv[2], ''))" "$HALL_STATUS_DIR/state.json" "$1" 2>/dev/null; }
AG_IN=("$R/config/Sound" "$R/config/textures" "$R/config/PrismaUI/views/AdventurersGuild/tex/skin" "$R/config/PrismaUI/views/AdventurersGuild/tex/chest")
# (of the NPCs' build folder only what the merge takes in: the voices and the compiled scripts; the build writes the rest there (its
# *_lines.json too, npcgen's own), and fingerprinting those rebuilt the hall every time)
HALL_IN=("$HALL_PRIVATE/prebuilt" "$HALL_PRIVATE/papyrus" "$HALL_PRIVATE/npcs/hair" "$HALL_PRIVATE/site" "$HALL_PRIVATE/assets" "$R/tools/HallGen/npcs/build/Sound" "$R/tools/HallGen/npcs/build/Scripts")
ag_fp="$(fp "${AG_IN[@]}")"; hall_fp="$(fp "${HALL_IN[@]}")"
changed() {   # changed <part> <fingerprint> <paths...>: 0 if that part must be built
  local was; was="$(state "$1")"; { [ $force -eq 1 ] || [ -z "$was" ]; } && return 0
  [ "$(state "$1_fp")" = "$2" ] || return 0
  shift 2; ! git -C "$R" diff --quiet "$was" "$commit" -- "$@"
}
do_ag=0; do_hall=0
[ $ag -eq 1 ] && changed ag "$ag_fp" . ':!tools/HallGen' ':!src/hall' && do_ag=1
if [ $do_ag -eq 1 ]; then
  echo "== AG: building"
  powershell -NoProfile -ExecutionPolicy Bypass -File "$S/build.ps1" > "$L/ag_build.log" 2>&1 || { tail -5 "$L/ag_build.log"; echo "BUILD STOPPED: AG's build (log: $L/ag_build.log)"; exit 1; }
  ST built ag="$commit" ag_fp="$ag_fp" root="$S"
elif [ $ag -eq 1 ]; then echo "== AG: unchanged since $(state ag | cut -c1-7)"; fi
agesp="$S/build/esp/AdventurersGuild.esp"; agesp_h="$(md5sum "$agesp" 2>/dev/null | cut -c1-32)"
if [ $hall -eq 1 ]; then
  { changed hall "$hall_fp" tools/HallGen src/hall src/papyrus config/dialogue.json || [ "$(state hall_agesp)" != "$agesp_h" ]; } && do_hall=1
fi
if [ $do_hall -eq 1 ]; then
  echo "== hall: building"
  bash "$S/tools/HallGen/build_hall.sh" | tee "$L/hall_build.out" | grep -E "^(EXPORT|-- |BUILD|listed ok|OPEN|NEW FAILURES|  )" | cut -c1-170
  [ "${PIPESTATUS[0]}" -eq 0 ] || { echo "BUILD STOPPED: the hall's build or a gate (log: $L/hall_build.out)"; exit 1; }
  ST built hall="$commit" hall_fp="$hall_fp" hall_agesp="$agesp_h" root="$S"
elif [ $hall -eq 1 ]; then echo "== hall: unchanged since $(state hall | cut -c1-7)"; fi
[ $deploy -eq 1 ] || { echo "BUILT $short (not deployed)"; exit 0; }

# ---- deploy: each install as soon as its own game is closed
ESP="AdventurersGuild - Guild Hall.esp"; parts="$([ $ag -eq 1 ] && echo ag)$([ $ag -eq 1 ] && [ $hall -eq 1 ] && echo +)$([ $hall -eq 1 ] && echo hall)"
pending=("${targets[@]}"); said=()
for round in $(seq 1 960); do
  left=()
  for t in "${pending[@]}"; do
    d="${INSTALL_DIR[$t]}"
    if game_running "$t"; then left+=("$t"); [[ " ${said[*]:-} " == *" $t "* ]] || { echo "$t: ${INSTALL_EXE[$t]} is running; deploying there once it closes"; said+=("$t"); }; continue; fi
    if [ $ag -eq 1 ]; then
      AG_MOD_DIR="$d" AG_DEPLOY_EXE="${INSTALL_EXE[$t]}" bash "$S/deploy.sh" > "$L/ag_deploy_$t.log" 2>&1 || { tail -3 "$L/ag_deploy_$t.log"; echo "DEPLOY STOPPED: AG's deploy to $t"; exit 1; }
      cmp -s "$S/src/plugin/build/AdventurersGuild.dll" "$d/SKSE/Plugins/AdventurersGuild.dll" && cmp -s "$agesp" "$d/AdventurersGuild.esp" \
        || { echo "DEPLOY STOPPED: $t's AG files differ from the build after its deploy"; exit 1; }
    fi
    if [ $hall -eq 1 ]; then
      out="$(bash "$S/tools/HallGen/deploy_hall.sh" "$HALL_BUILD" "$t" 2>&1)"
      echo "$out" | grep -q -E "NOT DEPLOYED|refusing|not deployed" && { echo "$out" | tail -3; echo "DEPLOY STOPPED: the hall's deploy to $t"; exit 1; }
      cmp -s "$HALL_BUILD/$ESP" "$d/$ESP" || { echo "DEPLOY STOPPED: $t's hall plugin differs from the build after its deploy"; exit 1; }
    fi
    ST deployed "$t" "$commit" "$parts"; echo "$t: $parts in ($short)"
  done
  pending=("${left[@]+"${left[@]}"}"); [ ${#pending[@]} -eq 0 ] && break
  sleep 30
done
[ ${#pending[@]} -eq 0 ] || { echo "NOT DEPLOYED to ${pending[*]}: its game stayed open"; exit 1; }
echo "DEPLOYED $short to ${targets[*]}"
