#!/usr/bin/env bash
# Builds and packages an Adventurers Guild release: one FOMOD archive, release/Adventurers Guild <label>.zip in the main checkout:
#   fomod/          the installer (packaging/fomod: info.xml with the label filled in, and ModuleConfig.xml)
#   00 Core/        always installed: exactly what deploy.sh puts in an install
#   01 Guild Hall/  the hall near Riverwood, ticked by default: its build (build/hall), less its build-only files
#   02 Guild Hall Solitude/  the hall near Solitude, the other choice: its build (build/hall-solitude)
#   docs/           installed to Data/docs/Adventurers Guild/: the README, changelog, licences, notices and translator's guide
# One command, from the last COMMIT: everything is built fresh first (build.sh --no-deploy --force: the core and the Riverwood hall,
# then the Solitude hall), every gate on both halls, nothing deployed anywhere; then the parts are staged and zipped. It refuses unless
# the core and both halls were built from that one commit. So: commit, then
#   bash package.sh [<label>]    (no label: the built version with its pre-release label, project(VERSION) + AG_VERSION_LABEL in
#                                 CMakeLists.txt, e.g. 2.0.0-alpha.4; a label given must be that, or that and "-<more>" for a test)
# After packaging, packaging/fomod_check.py reads the archive's installer, works out what each choice installs and checks it.
# bash build.sh --package does all of this inside the one build and then deploys (AG_PACKAGE_SKIP_BUILD=1: it has just built the core
# and both halls fresh from its commit, under its lock; the check below still refuses unless all three are from HEAD).
set -euo pipefail
R="$(cd "$(dirname "${BASH_SOURCE[0]}")" && { pwd -W 2>/dev/null || pwd; })"
source "$R/tools/HallGen/env.sh"   # local.env (the environment wins), HALL_BUILD
S="$R/build/build-src"
# ---- the release build: the commit at HEAD, the core and both halls built fresh from it, every gate, nothing deployed
want="$(git -C "$R" rev-parse HEAD)"
n_="$(git -C "$R" status --porcelain --untracked-files=no | wc -l)"; [ "$n_" -gt 0 ] && echo "   ($n_ changed files in this checkout are not committed: they are not in this release)"
if [ "${AG_PACKAGE_SKIP_BUILD:-}" != 1 ]; then
env -u HALL_SITE -u HALL_BUILD bash "$R/build.sh" --no-deploy --force || { echo "PACKAGING STOPPED: the core or the Riverwood hall did not build" >&2; exit 1; }
env -u HALL_BUILD HALL_SITE=solitude AG_PACKAGE_BUILD=1 bash "$R/build.sh" --no-deploy --force --hall-only || { echo "PACKAGING STOPPED: the Solitude hall did not build" >&2; exit 1; }
fi
H2="$R/build/hall-solitude"   # (HALL_SITE=solitude's build: tools/HallGen/env.sh)
[ -f "$H2/AdventurersGuild - Guild Hall.esp" ] || { echo "no Solitude hall build in $H2" >&2; exit 1; }
num="$(sed -n 's/^project(AdventurersGuild VERSION \([0-9.]*\).*/\1/p' "$S/src/plugin/CMakeLists.txt")"
pre="$(sed -n 's/^set(AG_VERSION_LABEL "\(.*\)")$/\1/p' "$S/src/plugin/CMakeLists.txt")"   # (the DLL says $num$pre in its log)
built="$num$pre"; label="${1:-$built}"
case "$label" in "$built"|"$built"-*) ;; *) echo "the label $label does not start with the built version $built (src/plugin/CMakeLists.txt)" >&2; exit 1 ;; esac
source "$R/tools/HallGen/lock.sh"; build_lock "package.sh $label"; trap build_unlock EXIT   # (no build may change the outputs meanwhile)
commit="$(git -C "$S" rev-parse --short HEAD)"
# (one commit: the snapshot, and the core and each hall as build.sh last recorded them; a build by another session meanwhile refuses)
for part in ag hall hall_solitude; do
  got="$(python -c "import json,sys; print(json.load(open(sys.argv[1])).get('built', {}).get(sys.argv[2], ''))" "$R/build/status/state.json" "$part" 2>/dev/null)"
  [ "$got" = "$want" ] && [ "$(git -C "$S" rev-parse HEAD)" = "$want" ] || { echo "PACKAGING STOPPED: $part was built from ${got:0:7}, not ${want:0:7} (another build meanwhile?)" >&2; exit 1; }
done
echo "== packaging $label from the build of $commit ($(git -C "$S" log -1 --format=%s | cut -c1-70))"
st="$R/build/package"; rm -rf "$st"; mkdir -p "$st"
# the core: deploy.sh itself, run on the snapshot's outputs into a staging folder, so the core is what an install gets
AG_STAGE=1 AG_SRC="$S" AG_MOD_DIR="$st/00 Core" bash "$R/deploy.sh" > "$st/deploy.log" 2>&1 \
	|| { tail -5 "$st/deploy.log"; echo "PACKAGING STOPPED: staging the core (log: $st/deploy.log)" >&2; exit 1; }
# the zip goes in the MAIN checkout's release/, whichever folder this runs from: AG is one project, and its releases
# live in one release folder
main="$(cd "$(git -C "$R" rev-parse --git-common-dir)/.." && { pwd -W 2>/dev/null || pwd; })"
mkdir -p "$main/release"
out="$main/release/Adventurers Guild $label.zip"
python "$R/packaging/package.py" --stage "$st" --hall "$R/build/hall" --hall2 "$H2" --src "$S" --fomod "$R/packaging/fomod" \
	--label "$label" --version "$num" --out "$out" || { echo "PACKAGING STOPPED" >&2; rm -f "$out"; exit 1; }
python "$R/packaging/fomod_check.py" "$out" "$st" || { echo "PACKAGED, BUT THE INSTALLER CHECK FAILED: $out" >&2; exit 1; }
echo "PACKAGED $out ($commit)"
