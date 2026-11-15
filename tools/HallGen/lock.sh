# Sourced: one build or deploy at a time across every session. Every session builds into the same build/hall
# and deploys to the same installs, so two at once would mix their files. The lock is a folder (made atomically) holding who has it;
# a second caller waits its turn, listed in build/build.queue so the status page shows it, and takes over a lock whose holder died.
#   source lock.sh; build_lock "<what>"      (released when the script exits; BUILD_LOCK_HELD=1 tells a script build.sh runs not to wait)
_bl_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && { pwd -W 2>/dev/null || pwd; })"
BUILD_LOCK="$_bl_root/build/build.lock"; BUILD_QUEUE="$_bl_root/build/build.queue"
_bl_st() { python "$_bl_root/tools/HallGen/status/status.py" render > /dev/null 2>&1 || true; }
build_lock() {
  [ "${BUILD_LOCK_HELD:-}" = 1 ] && return 0
  local what="${1:-build}" me="${AG_SESSION:-$(basename "$PWD")}" waited=0 line
  mkdir -p "$_bl_root/build"
  # (2026-11-04: a session's shell sees only its own processes, so kill -0 on another session's pid always said "gone" and a waiter took the
  # lock from a live build: the NPC and leader board sessions' builds overlapped. The holder is known by its Windows process ID, which
  # tasklist sees from every session; a holder without one, or a lock not yet written, counts as alive: wait rather than take over)
  local wp; wp="$(cat /proc/$$/winpid 2>/dev/null || echo 0)"
  line="{\"who\": \"$me\", \"pid\": $$, \"winpid\": $wp, \"what\": \"$what\", \"t\": \"$(date '+%Y-%m-%d %H:%M:%S')\"}"
  until mkdir "$BUILD_LOCK" 2>/dev/null; do
    local hp; hp="$(python -c "import json,sys; print(json.load(open(sys.argv[1])).get('winpid', 0))" "$BUILD_LOCK/owner.json" 2>/dev/null || echo 0)"
    if [ "$hp" != 0 ] && ! tasklist //FI "PID eq $hp" //NH 2>/dev/null | grep -q " $hp "; then echo "build lock: its holder (Windows pid $hp) is gone; taking it over"; rm -rf "$BUILD_LOCK"; continue; fi
    if [ $waited -eq 0 ]; then echo "build lock held by $(cat "$BUILD_LOCK/owner.json" 2>/dev/null); waiting"; echo "$line" >> "$BUILD_QUEUE"; _bl_st; waited=1; fi
    sleep 15
  done
  echo "$line" > "$BUILD_LOCK/owner.json"
  [ -f "$BUILD_QUEUE" ] && { grep -v "\"pid\": $$," "$BUILD_QUEUE" > "$BUILD_QUEUE.tmp" || true; mv "$BUILD_QUEUE.tmp" "$BUILD_QUEUE"; }
  export BUILD_LOCK_HELD=1; _bl_st
}
build_unlock() {
  [ -f "$BUILD_LOCK/owner.json" ] && grep -q "\"pid\": $$," "$BUILD_LOCK/owner.json" && rm -rf "$BUILD_LOCK"
  [ -f "$BUILD_QUEUE" ] && { grep -v "\"pid\": $$," "$BUILD_QUEUE" > "$BUILD_QUEUE.tmp" || true; mv "$BUILD_QUEUE.tmp" "$BUILD_QUEUE"; }
  _bl_st; return 0
}
