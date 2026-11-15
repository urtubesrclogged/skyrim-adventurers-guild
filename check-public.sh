#!/usr/bin/env bash
# Refuses a push that would publish something private. Run by .git/hooks/pre-push (install: bash check-public.sh --install)
# and by hand at any time: bash check-public.sh
#   1. No private path may be tracked (the private tools, the backlog, audio, screenshots, local settings, and any
#      .claude/ folder: Claude Code's settings.local.json keeps approved commands verbatim, secrets included).
#   2. No tracked text file may name this machine's paths or a private word (PRIVATE_WORDS in local.env).
#   3. Comments and notes are about the code only: no tracked text file may cite "the author" or "the user", or swear
#      (third-party licence texts and headers excepted).
#   4. As the pre-push hook (--pre-push, refs on stdin as git passes them): the same checks on the message of every commit
#      the push would publish.
set -e
R="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$R"
if [ "$1" = "--install" ]; then
	hooks="$(git rev-parse --git-common-dir)/hooks"
	printf '#!/usr/bin/env bash\nexec bash "$(git rev-parse --show-toplevel)/check-public.sh" --pre-push\n' > "$hooks/pre-push"
	chmod +x "$hooks/pre-push"
	echo "pre-push hook installed"
	exit 0
fi
[ -f local.env ] && while IFS= read -r line || [ -n "$line" ]; do
	case "$line" in PRIVATE_WORDS=*) export "PRIVATE_WORDS=${line#*=}" ;; esac
done < local.env
# the commits a push would publish: each ref's new commits not already on the remote
export AG_PUSH_MESSAGES=""
if [ "$1" = "--pre-push" ]; then
	AG_PUSH_MESSAGES="$(mktemp)"; trap 'rm -f "$AG_PUSH_MESSAGES"' EXIT
	zero=0000000000000000000000000000000000000000
	while read -r lref lsha rref rsha; do
		[ "$lsha" = "$zero" ] && continue   # (a deleted ref publishes nothing)
		if [ "$rsha" = "$zero" ]; then range=("$lsha" --not --remotes); else range=("$rsha..$lsha"); fi
		git log --format='--- commit %h%n%B' "${range[@]}" >> "$AG_PUSH_MESSAGES"
	done
fi

git ls-files -z | python -c '
import os, re, sys
files = [f for f in sys.stdin.buffer.read().decode("utf-8").split("\0") if f]
bad = []
private_path = re.compile(r"(^|/)\.claude/|^(BACKLOG\.md$|local\.env$|tools/(?!EspGen/|HallGen/)|config/Sound/|docs/images/|docs/SCREENSHOTS\.md$|snapshots/|release/|build/)|\.(wav|lip|fuz|xwm)$", re.I)
for f in files:
    if private_path.search(f):
        bad.append(f"private path is tracked: {f}")
words = [w.strip() for w in os.environ.get("PRIVATE_WORDS", "").split(",") if w.strip()]
if not words:
    bad.append("PRIVATE_WORDS is not set in local.env: the personal-word check cannot run")
leak = re.compile("|".join([r"C:[/\\]mods", r"C:[/\\]Users", r"/c/Users", r"C:[/\\]dev[/\\]", r"FUS v5", r"Librum"]
                           + [r"\b" + re.escape(w) + r"\b" for w in words]), re.I)
about = re.compile(r"\b(the author|the user)\b|\bfuck|\bshit\b|\bgoddamn", re.I)
third_party = ("LICENSE", "config/PrismaUI/views/AdventurersGuild/fonts/Cyrodiil-OFL.txt", "src/plugin/src/MagelightUI_API.h")
for f in files:
    if f in ("check-public.sh", "package-source.sh", "packaging/package.py"):
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
        elif f not in third_party and about.search(line):
            bad.append(f"{f}:{n}: not about the code: {line.strip()[:100]}")
msgs = os.environ.get("AG_PUSH_MESSAGES")
if msgs:
    commit = "?"
    for line in open(msgs, encoding="utf-8", errors="replace").read().splitlines():
        if line.startswith("--- commit "):
            commit = line[11:]
        elif leak.search(line):
            bad.append(f"commit {commit} message: {line.strip()[:100]}")
        elif about.search(line):
            bad.append(f"commit {commit} message, not about the code: {line.strip()[:100]}")
if bad:
    print("PUSH REFUSED - this would publish something private:", *bad, sep="\n  ")
    sys.exit(1)
print(f"check-public: {len(files)} tracked files, nothing private")
'
