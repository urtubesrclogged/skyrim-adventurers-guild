#!/bin/bash
# Adds the Guild Hall's people to a freshly built hall plugin (the hall folk ship WITH THE HALL, in
# its own plugin). The hall session's deploy_hall.sh runs it as its last build step, before deploying:
#   bash npcs/merge_npcs.sh <hall build dir>     e.g. ../../build/hall
# npcgen's merge mode reads the plugin in that folder ("AdventurersGuild - Guild Hall.esp"), adds the NPC records (IDs 0x8000-0x99FF, 0x9800 on the promotion trials, which the hall's build never uses) to the hall's own cell, and
# writes the plugin back under the same name; the unmerged plugin is kept beside it as <name>.unmerged. The hair the
# NPCs wear (tools/hall-private/npcs/hair/.../KS: KS Hairdos, see CREDITS.md; third-party files, not in the repository) is copied into the folder, so the hall's
# deploy ships it. Exits non-zero, with the folder untouched, if anything fails.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
dir="$(cd "${1:?usage: merge_npcs.sh <hall build dir>}" && pwd)"
# the build status page (status/status.py); its EXIT trap is replaced by the one below, which ends it first
source "$here/../status/hook.sh"; status_step "NPC merge" "$(basename "$dir")"
esp="$(find "$dir" -maxdepth 1 -iname "AdventurersGuild - Guild Hall.esp" | head -1)"
[ -n "$esp" ] || { echo "merge_npcs: no hall plugin in $dir"; exit 1; }
name="$(basename "$esp")"
[ -f "$esp.unmerged" ] && { echo "merge_npcs: $name in $dir is already merged ($name.unmerged exists)"; exit 1; }

mkdir -p "$here/build"
(cd "$here/npcgen" && dotnet build -c Release -v q > "$here/build/npcgen-build.log" 2>&1) || { grep -E " error " "$here/build/npcgen-build.log" | sort -u; echo "merge_npcs: npcgen did not compile; nothing merged"; exit 1; }
tmp="$(mktemp -d)"; trap 'status_end; rm -rf "${tmp:?}"' EXIT
out="$tmp/$name"
(cd "$here/npcgen" && timeout 280 ./bin/Release/net9.0/npcgen.exe merge "$esp" "$out" > "$tmp/npcgen.out" 2>&1) || { grep -E "WARNING|Exception" "$tmp/npcgen.out" | head; echo "merge_npcs: npcgen failed; nothing merged"; exit 1; }
grep -E "WARNING|wrote|ownership|Exception|NOT PLACED|^merge|^clerks|^routines|^shops" "$tmp/npcgen.out" || true
[ -s "$out" ] || { echo "merge_npcs: npcgen wrote nothing; nothing merged"; exit 1; }
# THE HOLD GATE: a set of lines npcgen holds out ("WARNING <set> held out ...") stops the merge, so
# nothing deploys, unless held_out_ok.txt names it. The build of 2026-11-06 16:10 printed eight such warnings (one wrong
# file count dropped every staff voice to vanilla and held out nearly all their talk) and deployed anyway.
# AG_ALLOW_HOLD=1 lets one build through.
held="$(grep -oE '^WARNING .*held out' "$tmp/npcgen.out" | sed -E 's/^WARNING //; s/ held out$//; s/:.*$//' | sort -u || true)"
ok="$(grep -vE '^[[:space:]]*(#|$)' "$here/held_out_ok.txt" 2>/dev/null | cut -f1 | sort -u || true)"
new="$(comm -23 <(printf '%s\n' "$held" | sed '/^$/d') <(printf '%s\n' "$ok" | sed '/^$/d'))"
if [ -n "$new" ]; then
  echo "merge_npcs: held out of this build and not in npcs/held_out_ok.txt:"; printf '%s\n' "$new" | sed 's/^/   /'
  if [ "${AG_ALLOW_HOLD:-}" = "1" ]; then echo "merge_npcs: AG_ALLOW_HOLD=1: merging anyway"
  else echo "merge_npcs: HOLD GATE: lines meant to ship are missing; nothing merged (fix the cause, list the set in held_out_ok.txt with its reason, or AG_ALLOW_HOLD=1 once)"; exit 1; fi
fi

seq="$here/build/SEQ/${name%.esp}.seq"
[ -s "$seq" ] || { echo "merge_npcs: npcgen wrote no $seq; nothing merged"; exit 1; }
mv "$esp" "$esp.unmerged"
cp "$out" "$esp"
mkdir -p "$dir/SEQ"; cp "$seq" "$dir/SEQ/"   # the clerks' dialogue quest is start-game-enabled: listed in SEQ, or its topic can fail to appear
# the clerks' voice files (voice_clerks.py packs them into build/Sound): named from the merged INFO IDs, so they ship as they are
[ -d "$here/build/Sound" ] && cp -r "$here/build/Sound" "$dir/" || echo "merge_npcs: WARNING no build/Sound yet: the clerks' lines ship silent (run voice_clerks.py)"
# the routines' package fragments (build_scripts.sh compiles npcs/papyrus into build/Scripts): the archery practice's bow
[ -f "$here/build/Scripts/PF_AGHallPracticeBow.pex" ] && { mkdir -p "$dir/Scripts"; cp "$here/build/Scripts/"*.pex "$dir/Scripts/"; } || echo "merge_npcs: WARNING no build/Scripts yet: archery practice runs without its bow (run build_scripts.sh)"
# only the hair someone wears: KS Hairdos' three styles (Vanilla hair remake's four are no longer worn, CREDITS.md)
for sub in meshes textures; do mkdir -p "$dir/$sub/AdventurersGuild/Hair"; cp -r "$here/../../hall-private/npcs/hair/$sub/AdventurersGuild/Hair/KS" "$dir/$sub/AdventurersGuild/Hair/"; done
echo "merge_npcs: $name merged ($(sha256sum "$esp" | cut -c1-12), unmerged $(sha256sum "$esp.unmerged" | cut -c1-12)); hair copied into $(basename "$dir")"
