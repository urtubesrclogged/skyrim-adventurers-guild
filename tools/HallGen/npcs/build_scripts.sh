#!/bin/bash
# Compiles the hall NPCs' Papyrus (src/hall/papyrus: package fragments, dialogue and quest scripts) into build/Scripts, which merge_npcs.sh ships beside
# the merged plugin. Caprica and the flags file come from AG's local.env. Each .pex header is scrubbed as package.sh does
# (a compiled script records the source path, user and computer name, none of which may ship).
#   bash npcs/build_scripts.sh [<output folder>]   (default build/Scripts; build_hall.sh compiles into its own work folder, so a build
#   never touches build/Scripts, whose times build.sh fingerprints)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; ag="$(cd "$here/../../.." && pwd)"; pap="$ag/src/hall/papyrus"; full="$ag/tools/hall-private/papyrus/headers-full"
get() { grep -E "^$1=" "$ag/local.env" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*$//'; }
caprica="$(get CAPRICA)"; flags="$(get PAPYRUS_FLAGS)"
[ -n "$caprica" ] && [ -n "$flags" ] || { echo "local.env: CAPRICA and PAPYRUS_FLAGS must be set"; exit 1; }
out="${1:-$here/build/Scripts}"; mkdir -p "$out"
# (each set compiled from a folder of its own: Caprica also searches the compiled file's folder and below, where one set's header
# stubs would shadow the other's)
stage="$(mktemp -d)"; trap 'rm -rf "${stage:?}"' EXIT; mkdir -p "$stage/npcs" "$stage/caralion" "$stage/natives"
cp "$pap"/PF_*.psc "$pap"/AG_TIF_*.psc "$stage/npcs/"; cp "$pap"/AGHallCaralion*.psc "$pap"/AGHallTrial*.psc "$pap"/AGHallTrainer*.psc "$pap"/AGHallBarter*.psc "$pap"/AGHallWelcomeTIF.psc "$pap"/AGHallBedroomDoor.psc "$pap"/AGHallAway*.psc "$pap"/AGHallFollower*.psc "$stage/caralion/"
# (the hall's natives, compiled by build_hall.sh, only declared here: the away quest stops stuck scenes through AGHallNative)
cp "$pap"/AGHallNative.psc "$stage/natives/"
(cd "$stage/npcs" && "$caprica" --game skyrim --import "$pap/headers-npcs" --flags "$flags" --output "$out" *.psc)
# Caralion's quest (2026-11-04) and the promotion trials (2026-11-05): against headers-full (tools/hall-private: SKSE's and the game's own sources, not ours to publish) with AG's and these headers filling the gaps, and AG's
# AG_Native; the small stubs in headers/ lack most of Quest, ReferenceAlias and Scene
(cd "$stage/caralion" && "$caprica" --game skyrim --import "$full" --import "$ag/src/papyrus" --import "$stage/natives" --flags "$flags" --output "$out" *.psc)
python - "$out" <<'PY'
import os, struct, sys
for f in os.listdir(sys.argv[1]):
    if not f.endswith(".pex"): continue
    p = os.path.join(sys.argv[1], f); d = open(p, "rb").read()
    assert d[:4] == bytes.fromhex("fa57c0de"), f
    pos = 16
    for _ in range(3): pos += 2 + struct.unpack(">H", d[pos:pos + 2])[0]
    head = b"".join(struct.pack(">H", len(x)) + x for x in (f[:-4].encode() + b".psc", b"author", b"build"))
    open(p, "wb").write(d[:16] + head + d[pos:])
    print("built", f)
PY
