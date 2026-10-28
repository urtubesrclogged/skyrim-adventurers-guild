#!/usr/bin/env bash
# Zips the deployed Adventurers Guild mod folder into release/Adventurers Guild <version>.zip, ready to install in
# any mod manager (the archive root is the Data folder: AdventurersGuild.esp, SKSE/, Scripts/, ...).
# Run deploy.sh first: this packages exactly what was deployed and tested, minus MO2's own meta.ini.
#   bash package.sh            (version from project(VERSION) in src/plugin/CMakeLists.txt; or pass one)
set -e
R="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$R/local.env" ] || { echo "local.env not found: copy local.env.example to local.env and set your paths" >&2; exit 1; }
while IFS= read -r line || [ -n "$line" ]; do   # KEY=VALUE lines (values may contain spaces); # comments skipped
	case "$line" in '#'*|'') continue ;; esac
	export "${line%%=*}=${line#*=}"
done < "$R/local.env"
# AG_MOD_DIR (environment) overrides local.env for one run, e.g. to stage a test build outside the mod manager
M="${AG_MOD_DIR:-${MOD_DIR:?local.env: MOD_DIR is not set}}"
V="${1:-$(sed -n 's/^project(AdventurersGuild VERSION \([0-9.]*\).*/\1/p' "$R/src/plugin/CMakeLists.txt")}"
cmp -s "$R/src/plugin/build/AdventurersGuild.dll" "$M/SKSE/Plugins/AdventurersGuild.dll" || { echo "deployed DLL differs from the build - run deploy.sh first" >&2; exit 1; }
cmp -s "$R/build/esp/AdventurersGuild.esp" "$M/AdventurersGuild.esp" || { echo "deployed ESP differs from the build - run deploy.sh first" >&2; exit 1; }
mkdir -p "$R/release"
python - "$M" "$R/release/Adventurers Guild $V.zip" "$R" <<'PY'
import os, sys, zipfile
src, out, root = sys.argv[1], sys.argv[2], sys.argv[3]
n = 0
# A compiled script's header records where and by whom it was compiled: the source path, the user name and the computer
# name. None of that may be published, so each .pex goes in with the script's own file name and neutral names instead.
# (Skyrim .pex: big-endian; magic, version, game, compile time, then three strings of a 16-bit length and the bytes.)
def scrubbed(path):
    import struct
    d = open(path, "rb").read()
    if d[:4] != bytes.fromhex("fa57c0de"):
        sys.exit(f"{path}: not a Skyrim .pex")
    pos = 16
    for _ in range(3):
        (k,) = struct.unpack(">H", d[pos:pos + 2])
        pos += 2 + k
    name = os.path.basename(path)[:-4].encode() + b".psc"
    head = b"".join(struct.pack(">H", len(x)) + x for x in (name, b"author", b"build"))
    return d[:16] + head + d[pos:]

with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for dp, _, fs in os.walk(src):
        for f in sorted(fs):
            rel = os.path.relpath(os.path.join(dp, f), src).replace("\\", "/")
            # docs/ comes from the repository below: a mod folder that was itself installed from a release zip holds an
            # older copy, which went into the 1.4.0 archive twice before this line (once stale)
            if rel == "meta.ini" or rel.startswith("docs/"):
                continue
            if rel.lower().endswith(".pex"):
                z.writestr(rel, scrubbed(os.path.join(dp, f)))
            else:
                z.write(os.path.join(dp, f), rel)
            n += 1
    # the translator's guide, the licenses and credits travel with the mod (docs/ at the archive root; not in Data)
    for f, arc in [("docs/TRANSLATING.md", "docs/TRANSLATING.md"), ("LICENSE", "docs/LICENSE.txt"),
                   ("EXCEPTIONS.md", "docs/EXCEPTIONS.md"), ("CHANGELOG.md", "docs/CHANGELOG.md"), ("docs/DOWNLOAD_README.txt", "docs/README.txt"),
                   ("ASSETS.md", "docs/ASSETS.md"), ("docs/CHIM_LORE.md", "docs/CHIM_LORE.md"), ("THIRD_PARTY_NOTICES.md", "docs/THIRD_PARTY_NOTICES.md")]:
        z.write(os.path.join(root, f), arc)
        n += 1
print(f"{out}: {n} files, {os.path.getsize(out) / 1e6:.1f} MB")
PY
