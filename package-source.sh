#!/usr/bin/env bash
# Zips the published source of Adventurers Guild into release/Adventurers Guild <version> - Source.zip.
# An explicit include list (not "everything minus ignores"), so nothing new slips in by accident, followed by a
# privacy gate: the zip is refused if any file in it names this machine's paths or the author's personal details.
#   bash package-source.sh     (version from project(VERSION) in src/plugin/CMakeLists.txt; or pass one)
set -e
R="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$R/local.env" ] && while IFS= read -r line || [ -n "$line" ]; do   # PRIVATE_WORDS lives there, unpublished
	case "$line" in PRIVATE_WORDS=*) export "PRIVATE_WORDS=${line#*=}" ;; esac
done < "$R/local.env"
V="${1:-$(sed -n 's/^project(AdventurersGuild VERSION \([0-9.]*\).*/\1/p' "$R/src/plugin/CMakeLists.txt")}"
mkdir -p "$R/release"
python - "$R" "$R/release/Adventurers Guild $V - Source.zip" <<'PY'
import fnmatch, os, re, sys, zipfile
root, out = sys.argv[1], sys.argv[2]

INCLUDE = [
    "LICENSE", "EXCEPTIONS.md", "CHANGELOG.md", "README.md", "ASSETS.md", "THIRD_PARTY_NOTICES.md", ".gitignore", "local.env.example",
    "build.ps1", "deploy.sh", "package.sh", "package-source.sh",
    "src/plugin/CMakeLists.txt", "src/plugin/vcpkg.json", "src/plugin/src/*",
    "src/papyrus/*.psc", "src/papyrus/headers/*.psc",
    "tools/EspGen/*.cs", "tools/EspGen/*.csproj",
    "config/*",
    "docs/*",
]
EXCLUDE = ["docs/images/*", "docs/SCREENSHOTS.md", "config/Sound/*", "*/__pycache__/*", "*.pyc", "local.env", "*/bin/*", "*/obj/*", "*/build/*"]
# The author's machine and identity: none of this may be published. Machine paths are listed here; the author's own
# words to refuse (name, mail domain...) come from PRIVATE_WORDS in local.env, comma-separated, never listed here.
words = [w.strip() for w in os.environ.get("PRIVATE_WORDS", "").split(",") if w.strip()]
PRIVATE = re.compile("|".join([r"C:[/\\]mods", r"C:[/\\]Users", r"/c/Users", r"C:[/\\]dev[/\\]", r"FUS v5", r"Librum"]
                              + [r"\b" + re.escape(w) + r"\b" for w in words]), re.I)
if not words:
    print("note: PRIVATE_WORDS is not set in local.env - only machine paths are checked")

files = []
for dp, dns, fs in os.walk(root):
    rel_dir = os.path.relpath(dp, root).replace("\\", "/")
    if rel_dir.split("/")[0] in ("build", "release", "snapshots", ".git"):
        continue
    for f in fs:
        rel = f if rel_dir == "." else f"{rel_dir}/{f}"
        if any(fnmatch.fnmatch(rel, p) for p in INCLUDE) and not any(fnmatch.fnmatch(rel, p) for p in EXCLUDE):
            files.append(rel)
files.sort()

leaks = []
for rel in files:
    if rel == "package-source.sh":
        continue  # holds the path patterns themselves
    data = open(os.path.join(root, rel), "rb").read()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = data.decode("utf-16")
        except UnicodeDecodeError:
            continue  # binary (textures)
    for n, line in enumerate(text.splitlines(), 1):
        if PRIVATE.search(line):
            leaks.append(f"{rel}:{n}: {line.strip()[:120]}")
if leaks:
    print("REFUSED - private details in the source:", *leaks, sep="\n  ")
    sys.exit(1)

top = os.path.splitext(os.path.basename(out))[0]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for rel in files:
        z.write(os.path.join(root, rel), f"{top}/{rel}")
print(f"{out}: {len(files)} files, {os.path.getsize(out) / 1e6:.1f} MB (privacy gate passed)")
PY
