#!/usr/bin/env bash
# Packages Adventurers Guild as one FOMOD archive, release/Adventurers Guild <label>.zip in the main checkout, for any mod manager:
#   fomod/          the installer (packaging/fomod: info.xml with the label filled in, and ModuleConfig.xml)
#   00 Core/        always installed: exactly what deploy.sh puts in an install
#   01 Guild Hall/  the one option, ticked by default: the hall's build (build/hall), less its build-only files
#   docs/           installed to Data/docs/Adventurers Guild/: the README, changelog, licences, notices and translator's guide
# It packages what build.sh last built and deployed (its snapshot, build/build-src, and build/hall), and refuses unless core + hall
# match the deployed folder you tested (MOD_DIR in local.env, or AG_MOD_DIR) file for file. So: commit, bash build.sh, test, then
#   bash package.sh [<label>]    (no label: the built version with its pre-release label, project(VERSION) + AG_VERSION_LABEL in
#                                 CMakeLists.txt, e.g. 2.0.0-alpha.1; a label given must be that, or that and "-<more>" for a test)
# After packaging, packaging/fomod_check.py reads the archive's installer, works out what each choice installs and checks it.
set -euo pipefail
R="$(cd "$(dirname "${BASH_SOURCE[0]}")" && { pwd -W 2>/dev/null || pwd; })"
source "$R/tools/HallGen/env.sh"   # local.env (the environment wins), HALL_BUILD
S="$R/build/build-src"
[ -e "$S/.git" ] || { echo "no build snapshot (build/build-src): run bash build.sh first" >&2; exit 1; }
M="${AG_MOD_DIR:-${MOD_DIR:?local.env: MOD_DIR is not set}}"
[ -d "$M" ] || { echo "the deployed folder $M does not exist" >&2; exit 1; }
num="$(sed -n 's/^project(AdventurersGuild VERSION \([0-9.]*\).*/\1/p' "$S/src/plugin/CMakeLists.txt")"
pre="$(sed -n 's/^set(AG_VERSION_LABEL "\(.*\)")$/\1/p' "$S/src/plugin/CMakeLists.txt")"   # (the DLL says $num$pre in its log)
built="$num$pre"; label="${1:-$built}"
case "$label" in "$built"|"$built"-*) ;; *) echo "the label $label does not start with the built version $built (src/plugin/CMakeLists.txt)" >&2; exit 1 ;; esac
source "$R/tools/HallGen/lock.sh"; build_lock "package.sh $label"; trap build_unlock EXIT   # (no build may change the outputs meanwhile)
commit="$(git -C "$S" rev-parse --short HEAD)"
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
python "$R/packaging/package.py" --stage "$st" --hall "$HALL_BUILD" --deployed "$M" --src "$S" --fomod "$R/packaging/fomod" \
	--label "$label" --version "$num" --out "$out" || { echo "PACKAGING STOPPED" >&2; rm -f "$out"; exit 1; }
python "$R/packaging/fomod_check.py" "$out" "$st" || { echo "PACKAGED, BUT THE INSTALLER CHECK FAILED: $out" >&2; exit 1; }
echo "PACKAGED $out ($commit)"
