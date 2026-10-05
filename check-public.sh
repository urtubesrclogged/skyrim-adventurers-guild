#!/usr/bin/env bash
# Refuses a push that would publish something private. Run by .git/hooks/pre-push (install: bash check-public.sh --install)
# and by hand at any time: bash check-public.sh
#   1. No private path may be tracked (the private tools, the backlog, audio, screenshots, local settings).
#   2. No tracked text file may name this machine's paths or the author's own words (PRIVATE_WORDS in local.env).
set -e
R="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$R"
if [ "$1" = "--install" ]; then
	printf '#!/usr/bin/env bash\nexec bash "$(git rev-parse --show-toplevel)/check-public.sh"\n' > .git/hooks/pre-push
	chmod +x .git/hooks/pre-push
	echo "pre-push hook installed"
	exit 0
fi
[ -f local.env ] && while IFS= read -r line || [ -n "$line" ]; do
	case "$line" in PRIVATE_WORDS=*) export "PRIVATE_WORDS=${line#*=}" ;; esac
done < local.env

git ls-files -z | python -c '
import os, re, sys
files = [f for f in sys.stdin.buffer.read().decode("utf-8").split("\0") if f]
bad = []
private_path = re.compile(r"^(BACKLOG\.md$|local\.env$|tools/(?!EspGen/)|config/Sound/|docs/images/|docs/SCREENSHOTS\.md$|snapshots/|release/|build/)|\.(wav|lip|fuz|xwm)$", re.I)
for f in files:
    if private_path.search(f):
        bad.append(f"private path is tracked: {f}")
words = [w.strip() for w in os.environ.get("PRIVATE_WORDS", "").split(",") if w.strip()]
if not words:
    bad.append("PRIVATE_WORDS is not set in local.env: the personal-word check cannot run")
leak = re.compile("|".join([r"C:[/\\]mods", r"C:[/\\]Users", r"/c/Users", r"C:[/\\]dev[/\\]", r"FUS v5", r"Librum"]
                           + [r"\b" + re.escape(w) + r"\b" for w in words]), re.I)
for f in files:
    if f in ("check-public.sh", "package-source.sh"):
        continue  # hold the path patterns themselves
    data = open(f, "rb").read()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = data.decode("utf-16")
        except UnicodeDecodeError:
            continue  # binary
    for n, line in enumerate(text.splitlines(), 1):
        if leak.search(line):
            bad.append(f"{f}:{n}: {line.strip()[:100]}")
if bad:
    print("PUSH REFUSED - this would publish something private:", *bad, sep="\n  ")
    sys.exit(1)
print(f"check-public: {len(files)} tracked files, nothing private")
'
