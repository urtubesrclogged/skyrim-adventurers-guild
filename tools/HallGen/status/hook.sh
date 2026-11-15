# Sourced by a build or deploy script, so its run shows on the status page (status.py):
#   source "tools/HallGen/status/hook.sh"; status_step "<what>" ["<detail>"]
# records the start now and, by an EXIT trap, ok or fail by the script's exit code. A script with its own EXIT trap calls
# status_end first in it instead (it reads the exit code): trap 'status_end; its cleanup' EXIT. Nothing here ever stops the script.
_st_py="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/status.py"
status_end() {
  local rc=$?
  [ -n "${_st_what:-}" ] && python "$_st_py" event "$_st_what" "$([ $rc -eq 0 ] && echo ok || echo fail)" "exit $rc" > /dev/null 2>&1 || true
  return $rc
}
status_step() {
  _st_what="$1"
  python "$_st_py" event "$1" start "${2:-}" > /dev/null 2>&1 || true
  trap status_end EXIT
}
