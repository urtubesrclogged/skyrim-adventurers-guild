#!/usr/bin/env bash
# Builds Adventurers Guild with its Guild Hall and deploys them to the test installs: one command, the same for every session.
#   bash build.sh [--package] [--no-deploy] [--ag-only | --hall-only] [--force] [<install> ...]   build the newest commit, deploy
#   bash build.sh --check [<file> ...]                                                          build and gate only, no lock
# (no install: every one in HALL_INSTALLS, local.env)
#   --package  the release too, in the same build: everything built fresh plus the Solitude hall, every gate, then package.sh's zip
#              and installer check from that one commit, then the deploy.
#   --check    the newest commit, plus the named files as they are in this checkout (uncommitted work), built and run through every
#              gate in this session's own folder (build/check-<AG_SESSION>): no lock, nothing deployed, the shared build untouched.
#              Run it after changing the hall's meshes, placing objects, or any code that needs validating.
# The build (not --check):
#   1. One build at a time. A plain build.sh while a deploying build runs does not start another: that build ends only once the
#      installs have the newest commit, so this one's is in it. Other calls wait for the lock (tools/HallGen/lock.sh).
#   2. Builds the last COMMIT, never the working tree: build/build-src is a second checkout of this repository, moved to HEAD, with
#      the ignored inputs (voice sources, tools/hall-private, the textures made from the game's files, local.env...) linked in from
#      here. Uncommitted edits never reach it.
#   3. Builds only what changed since its last good build: AG (build.ps1) if AG's committed files or its ignored inputs changed; the
#      hall (tools/HallGen/build_hall.sh: export, meshes, plugin, every gate) if the hall's did, or AG's plugin did (the hall masters
#      it). --force builds both.
#   4. Deploys to each install as soon as its own game is closed (MO2 locks its files while it runs), AG (deploy.sh) then the hall
#      (deploy_hall.sh), checks each against the build, and stamps the install on the status page.
#   5. A commit (or a change to the ignored inputs) made while it ran is built and deployed before it ends.
# A failed build or gate stops before anything is deployed. Set AG_SESSION to name yourself on the status page.
set -uo pipefail
R="$(cd "$(dirname "${BASH_SOURCE[0]}")" && { pwd -W 2>/dev/null || pwd; })"; source "$R/tools/HallGen/env.sh"
deploy=1; ag=1; hall=1; force=0; pkg=0; check=0; args=()
for a in "$@"; do case "$a" in --no-deploy) deploy=0 ;; --ag-only) hall=0 ;; --hall-only) ag=0 ;; --force) force=1 ;; --package) pkg=1; force=1 ;;
  --check) check=1; deploy=0; force=1 ;; -*) echo "unknown option $a"; exit 2 ;; *) args+=("$a") ;; esac; done
[ $pkg -eq 1 ] && { [ $ag -eq 0 ] || [ $hall -eq 0 ] || [ $check -eq 1 ]; } && { echo "build.sh: --package builds everything; not with --ag-only, --hall-only or --check" >&2; exit 2; }
# (2026-11-17) test builds and deploys are the Riverwood hall's; another site's hall (sites.json) is built only for the release, never deployed
if [ "$HALL_SITE" != riverwood ] && { [ "${AG_PACKAGE_BUILD:-}" != 1 ] || [ $deploy -eq 1 ]; }; then
  echo "build.sh: HALL_SITE=$HALL_SITE is built only for the release (--package), never deployed" >&2; exit 2
fi
targets=(); paths=()
if [ $check -eq 1 ]; then
  for p in "${args[@]+"${args[@]}"}"; do [ -f "$R/$p" ] || { echo "--check: $p is not a file in this checkout"; exit 2; }; paths+=("$p"); done
else
  targets=("${args[@]+"${args[@]}"}"); [ ${#targets[@]} -eq 0 ] && targets=("${INSTALL_NAMES[@]}")
  for t in "${targets[@]}"; do [ -n "${INSTALL_DIR[$t]:-}" ] || { echo "$t: not an install in HALL_INSTALLS"; exit 2; }; done
fi
w() { cygpath -w "$1"; }
if [ $check -eq 1 ]; then
  # (2026-11-18) the gates without the build's lock: this session's own snapshot, work folder and status, the shared work folder's
  # inputs copied in (the extracted data root, the ID ledger, the gates' baseline, the materials, the caches; only what changed after
  # the first time)
  me="$(printf %s "${AG_SESSION:-$(basename "$PWD")}" | tr -c 'A-Za-z0-9_-' '_')"; CK="$R/build/check-$me"
  export HALL_STATUS_DIR="$CK/status" HALL_BUILD="$CK/hall" HALL_WORK="$CK/work" HALL_PRIVATE="$R/tools/hall-private"
  S="$CK/src"; mkdir -p "$HALL_WORK" "$HALL_STATUS_DIR"
  echo "== check in $CK"
  for d in data-root ledger gates-base materials gate-cache meshkeys dotnet; do
    [ -d "$R/build/hall-work/$d" ] || continue
    MSYS2_ARG_CONV_EXCL='*' robocopy "$(w "$R/build/hall-work/$d")" "$(w "$HALL_WORK/$d")" /E /NFL /NDL /NJH /NJS /NP /R:1 /W:1 > /dev/null; [ $? -lt 8 ] || { echo "CHECK STOPPED: copying $d"; exit 1; }
  done
else
  export HALL_STATUS_DIR="$R/build/status" HALL_BUILD="$R/build/hall$([ "${HALL_SITE:-riverwood}" != riverwood ] && echo "-$HALL_SITE")" HALL_WORK="$R/build/hall-work" HALL_PRIVATE="$R/tools/hall-private"
  S="$R/build/build-src"   # (its ignored folders are junctions into this checkout: never delete it with rm -r, which would follow them; git worktree remove)
  source "$R/tools/HallGen/lock.sh"
  if [ $# -eq 0 ] && h_="$(build_running)"; then
    echo "== a build is already running ($h_): it builds and deploys the newest commit before it ends, so this one's is in it"; exit 0
  fi
  build_lock "build.sh $*"
  # (2026-11-18: a stopped build's gates ran on and failed the next build against its fresh export) what is left of an earlier build,
  # anything running from the build's snapshot or on its export, is stopped before this one starts
  [ "${AG_PACKAGE_BUILD:-}" = 1 ] || powershell -NoProfile -ExecutionPolicy Bypass -File "$(w "$R/tools/HallGen/leftovers.ps1")" "$(echo "$S/" | tr 'A-Z' 'a-z')" "$(echo "$HALL_WORK/export" | tr 'A-Z' 'a-z')"
fi
ST() { python "$R/tools/HallGen/status/status.py" "$@" > /dev/null 2>&1 || true; }
source "$R/tools/HallGen/status/hook.sh"; status_step "build.sh" "${*:-everything}"
if [ $check -eq 1 ]; then trap 'status_end' EXIT; else trap 'status_end; build_unlock' EXIT; fi
L="$HALL_WORK/logs"; mkdir -p "$L"

# ---- the ignored inputs, by a fingerprint of their names, sizes and times
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
moved() { [ "$(git -C "$R" rev-parse HEAD)" != "$commit" ] || [ "$(fp "${AG_IN[@]}")" != "$ag_fp" ] || [ "$(fp "${HALL_IN[@]}")" != "$hall_fp" ]; }

# ---- build (and deploy) the newest commit, again while the checkout moves on, at most 5 times
for pass in 1 2 3 4 5; do
commit="$(git -C "$R" rev-parse HEAD)"; short="${commit:0:7}"
echo "== building $short $(git -C "$R" log -1 --format=%s | cut -c1-80)"
n="$(git -C "$R" status --porcelain --untracked-files=no | wc -l)"
if [ $check -eq 1 ]; then echo "   with ${#paths[@]} file(s) from this checkout: ${paths[*]:-none}"
elif [ "$n" -gt 0 ]; then echo "   ($n changed files in this checkout are not committed: they are not in this build)"; fi

# the snapshot: a checkout of the commit, its ignored inputs linked in from here
if [ ! -e "$S/.git" ]; then git -C "$R" worktree add --detach "$S" "$commit" > "$L/build-src.log" 2>&1 || { tail -3 "$L/build-src.log"; echo "BUILD STOPPED: the snapshot checkout"; exit 1; }
else git -C "$S" checkout --detach --force "$commit" > "$L/build-src.log" 2>&1 || { tail -3 "$L/build-src.log"; echo "BUILD STOPPED: the snapshot checkout"; exit 1; }; git -C "$S" clean -fdq; fi
while IFS= read -r p; do
  p="${p%/}"; case "$p" in build|build/*|src/plugin/build|*__pycache__*|*/bin|*/obj) continue ;; esac
  if [ -d "$R/$p" ]; then [ -e "$S/$p" ] || { mkdir -p "$(dirname "$S/$p")"; powershell -NoProfile -Command "New-Item -ItemType Junction -Path '$(w "$S/$p")' -Target '$(w "$R/$p")' | Out-Null"; }
  else mkdir -p "$(dirname "$S/$p")"; cp -p "$R/$p" "$S/$p"; fi
done < <(git -C "$R" ls-files --others --ignored --exclude-standard --directory)
# (2026-11-14, package.sh's check) the core's voices: this checkout has no voice pipeline, and its build/Sound (the 2.0 set, brought in
# from the main checkout's voice work) is what deploy.sh ships. Skipped with the rest of build/ above, the snapshot had none, so every
# deploy left the installs' voices alone and they kept a 1.6 set (23 2.0 lines silent, 371 older takes).
[ -d "$R/build/Sound" ] && [ ! -e "$S/build/Sound" ] && { mkdir -p "$S/build"; powershell -NoProfile -Command "New-Item -ItemType Junction -Path '$(w "$S/build/Sound")' -Target '$(w "$R/build/Sound")' | Out-Null"; }
for p in "${paths[@]+"${paths[@]}"}"; do mkdir -p "$(dirname "$S/$p")"; cp -p "$R/$p" "$S/$p"; done   # (--check: the named files as they are here)

ag_fp="$(fp "${AG_IN[@]}")"; hall_fp="$(fp "${HALL_IN[@]}")"
changed() {   # changed <part> <fingerprint> <paths...>: 0 if that part must be built
  local was; was="$(state "$1")"; { [ $force -eq 1 ] || [ -z "$was" ]; } && return 0
  [ "$(state "$1_fp")" = "$2" ] || return 0
  shift 2; ! git -C "$R" diff --quiet "$was" "$commit" -- "$@"
}
do_ag=0; do_hall=0
# (2026-11-17) each site's hall its own part: a hall built for one site is never taken as up to date for another
HP=hall; [ "$HALL_SITE" != riverwood ] && HP="hall_$HALL_SITE"
[ $ag -eq 1 ] && changed ag "$ag_fp" . ':!tools/HallGen' ':!src/hall' && do_ag=1
if [ $do_ag -eq 1 ]; then
  echo "== AG: building"
  powershell -NoProfile -ExecutionPolicy Bypass -File "$S/build.ps1" > "$L/ag_build.log" 2>&1 || { tail -5 "$L/ag_build.log"; echo "BUILD STOPPED: AG's build (log: $L/ag_build.log)"; exit 1; }
  ST built ag="$commit" ag_fp="$ag_fp" root="$S"
elif [ $ag -eq 1 ]; then echo "== AG: unchanged since $(state ag | cut -c1-7)"; fi
agesp="$S/build/esp/AdventurersGuild.esp"; agesp_h="$(md5sum "$agesp" 2>/dev/null | cut -c1-32)"
if [ $hall -eq 1 ]; then
  { changed "$HP" "$hall_fp" tools/HallGen src/hall src/papyrus config/dialogue.json || [ "$(state ${HP}_agesp)" != "$agesp_h" ]; } && do_hall=1
fi
if [ $do_hall -eq 1 ]; then
  echo "== hall ($HALL_SITE): building"
  bash "$S/tools/HallGen/build_hall.sh" | tee "$L/hall_build.out" | grep -E "^(EXPORT|-- |BUILD|listed ok|OPEN|NEW FAILURES|  )" | cut -c1-170
  [ "${PIPESTATUS[0]}" -eq 0 ] || { echo "BUILD STOPPED: the hall's build or a gate (log: $L/hall_build.out)"; exit 1; }
  ST built "$HP=$commit" "${HP}_fp=$hall_fp" "${HP}_agesp=$agesp_h" root="$S"
elif [ $hall -eq 1 ]; then echo "== hall ($HALL_SITE): unchanged since $(state $HP | cut -c1-7)"; fi
[ $check -eq 1 ] && { echo "CHECK OK: $short with ${paths[*]:-no other files}: built, every gate passed, nothing deployed"; exit 0; }
[ $deploy -eq 1 ] && [ "$pass" -lt 5 ] && moved && { echo "== $(git -C "$R" rev-parse --short HEAD) came in while building: building it before deploying"; continue; }
if [ $pkg -eq 1 ]; then   # (the release from this build's commit: the Solitude hall, then package.sh's staging, zip and installer check)
  echo "== hall (solitude): building for the release"
  env -u HALL_BUILD HALL_SITE=solitude AG_PACKAGE_BUILD=1 bash "$R/build.sh" --no-deploy --force --hall-only | sed 's/^/   /' || { echo "BUILD STOPPED: the Solitude hall's build or a gate (nothing deployed, nothing packaged)"; exit 1; }
  AG_PACKAGE_SKIP_BUILD=1 bash "$R/package.sh" || { echo "BUILD STOPPED: packaging (nothing deployed)"; exit 1; }
  pkg=0   # (a pass after this one, for a commit come in meanwhile, deploys it without another release)
fi
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
      # (2026-11-18) the ID ledger is the hall a save can hold: the plugin just deployed (unmerged). The next build keeps every ID it
      # gives a piece, and its renumbering gate (RefDiff) stops on any that would name another piece (the ledger had stood at
      # 2026-11-04's plugin, so each build numbered every piece added since by list order, and the lived-in pass shifted dozens)
      cp "$HALL_BUILD/$ESP.unmerged" "$HALL_WORK/ledger/$ESP" || { echo "DEPLOY STOPPED: refreshing the ID ledger"; exit 1; }
    fi
    ST deployed "$t" "$commit" "$parts"; echo "$t: $parts in ($short)"
  done
  pending=("${left[@]+"${left[@]}"}"); [ ${#pending[@]} -eq 0 ] && break
  sleep 30
done
[ ${#pending[@]} -eq 0 ] || { echo "NOT DEPLOYED to ${pending[*]}: its game stayed open"; exit 1; }
echo "DEPLOYED $short to ${targets[*]}"
[ "$pass" -lt 5 ] && moved && { echo "== $(git -C "$R" rev-parse --short HEAD) came in while deploying: building and deploying it too"; continue; }
break
done
# (the lock is let go on exit; a commit made in the moment between the check above and then would have found the lock held and left
# its build to this one: one more look after letting go, and a new build if so)
if [ $deploy -eq 1 ] && [ "${AG_PACKAGE_BUILD:-}" != 1 ] && [ ${#args[@]} -eq 0 ]; then
  build_unlock; trap 'status_end' EXIT
  [ "$(git -C "$R" rev-parse HEAD)" = "$commit" ] || { echo "== $(git -C "$R" rev-parse --short HEAD) came in as this build ended: building it"; exec bash "$R/build.sh"; }
fi
