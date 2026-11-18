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
HALL_BUILD="${HALL_BUILD:-$AG_ROOT/build/hall}"                 # (ignored: the built hall, what the deploy copies; another site's below)
BLENDER="${BLENDER:-blender}"
# (2026-11-17) the site a hall build is for (sites.json): HALL_SITE=riverwood (when unset) | solitude, each an installer option.
# Its values as HALL_SITE_*. Test installs get the Riverwood hall only; another site's is built by package.sh for the release and
# never deployed (build.sh refuses it otherwise)
HALL_SITE="${HALL_SITE:-riverwood}"
eval "$(python -c "
import json, sys
d = json.load(open(r'$HALL_GEN/sites.json')).get('$HALL_SITE')
if d is None: print('echo \"no site $HALL_SITE in sites.json\" >&2; exit 2'); sys.exit()
print('HALL_SITE_PLACE=%d HALL_SITE_APPROACH=%s HALL_SITE_AG=%s HALL_SITE_MAP=%s HALL_SITE_NAVDUMPS=%s HALL_SITE_MARKER=%s HALL_SITE_DOOR=%s HALL_SITE_GLOW=%s HALL_SITE_HELIOS=%s' % (
    d['place'], d['approach'], d['site'], d['map'], d['navdumps'], ','.join(str(v) for v in d['marker']), d['door'], repr(d['glow']), repr(d['helios'])))
")"
# each site's build its own folder (riverwood's build/hall, as before; solitude's build/hall-solitude), so package.sh has both
[ "$HALL_SITE" != riverwood ] && [ "$HALL_BUILD" = "$AG_ROOT/build/hall" ] && HALL_BUILD="$AG_ROOT/build/hall-$HALL_SITE"
[ "$HALL_SITE" != riverwood ] && { HALL_INSTALLS=""; HALL_INSTALLS_OPTIONAL=""; }   # (another site's hall: no installs at all)
declare -A INSTALL_DIR INSTALL_EXE; INSTALL_NAMES=()
_hall_installs() {
  local e n d x; IFS=';' read -ra _e <<< "$1"
  for e in "${_e[@]}"; do [ -n "$e" ] || continue; IFS='|' read -r n d x <<< "$e"; INSTALL_DIR[$n]="$d"; INSTALL_EXE[$n]="$x"; if [ "$2" = main ]; then INSTALL_NAMES+=("$n"); fi; done
  return 0   # (2026-11-04: it ended on a failed test for an optional install, so a set -e script sourcing this, deploy_hall.sh, exited silently)
}
_hall_installs "${HALL_INSTALLS:-}" main; _hall_installs "${HALL_INSTALLS_OPTIONAL:-}" optional
game_running() { tasklist 2>/dev/null | grep -qi "^${INSTALL_EXE[$1]}"; }   # (that install's game: MO2 locks its files while it runs)
