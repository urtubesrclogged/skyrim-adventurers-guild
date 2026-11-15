# Sourced by the hall's scripts: AG's local.env as variables (one already set in the environment wins), the test installs as
# arrays, and the hall's folders. The installs come from HALL_INSTALLS in local.env: name|mod folder|game exe, separated by ";"
# (the "Adventurers Guild 2.0" folder of each install); HALL_INSTALLS_OPTIONAL adds installs a script deploys to only when named.
AG_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && { pwd -W 2>/dev/null || pwd; })"   # (C:/... on Windows: Python and Blender given /c/... in their own text cannot read it)
if [ -f "$AG_ROOT/local.env" ]; then
  while IFS= read -r _l || [ -n "$_l" ]; do
    _l="${_l%$'\r'}"; case "$_l" in '#'*|'') continue ;; esac
    _k="${_l%%=*}"; [ -z "${!_k+x}" ] && export "$_k=${_l#*=}"
  done < "$AG_ROOT/local.env"
fi
HALL_GEN="$AG_ROOT/tools/HallGen"
HALL_PRIVATE="${HALL_PRIVATE:-$AG_ROOT/tools/hall-private}"   # (ignored: voice takes, research, the binaries made from the game's files)
HALL_WORK="${HALL_WORK:-$AG_ROOT/build/hall-work}"              # (ignored: exports, the extracted data root, caches, logs)
HALL_BUILD="${HALL_BUILD:-$AG_ROOT/build/hall}"                 # (ignored: the built hall, what the deploy copies)
BLENDER="${BLENDER:-blender}"
declare -A INSTALL_DIR INSTALL_EXE; INSTALL_NAMES=()
_hall_installs() {
  local e n d x; IFS=';' read -ra _e <<< "$1"
  for e in "${_e[@]}"; do [ -n "$e" ] || continue; IFS='|' read -r n d x <<< "$e"; INSTALL_DIR[$n]="$d"; INSTALL_EXE[$n]="$x"; if [ "$2" = main ]; then INSTALL_NAMES+=("$n"); fi; done
  return 0   # (2026-11-04: it ended on a failed test for an optional install, so a set -e script sourcing this, deploy_hall.sh, exited silently)
}
_hall_installs "${HALL_INSTALLS:-}" main; _hall_installs "${HALL_INSTALLS_OPTIONAL:-}" optional
game_running() { tasklist 2>/dev/null | grep -qi "^${INSTALL_EXE[$1]}"; }   # (that install's game: MO2 locks its files while it runs)
