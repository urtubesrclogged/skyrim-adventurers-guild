# What is left of an earlier build (build.sh, before a build starts): every process whose command line names this checkout's build
# snapshot or its hall export, stopped; never this script's own caller or the caller's callers. Paths as build.sh passes them; matched
# without their drive, by forward slashes, in lower case, so C:\x, C:/x and Git Bash's /c/x are all found.
param([string]$snap, [string]$export)
function Bare([string]$p) { $p = $p.Replace([char]92, [char]47).ToLower(); if ($p -match '^[a-z]:/') { $p = $p.Substring(2) }; return $p }
$snap = Bare $snap; $export = Bare $export
$all = Get-CimInstance Win32_Process
$byId = @{}; foreach ($p in $all) { $byId[[int]$p.ProcessId] = $p }
$mine = @{}; $id = [int]$PID
while ($byId.ContainsKey($id) -and -not $mine.ContainsKey($id)) { $mine[$id] = 1; $id = [int]$byId[$id].ParentProcessId }
foreach ($p in $all) {
  if ($mine.ContainsKey([int]$p.ProcessId) -or -not $p.CommandLine) { continue }
  $c = $p.CommandLine.Replace([char]92, [char]47).ToLower()
  if ($c.Contains($snap) -or $c.Contains($export)) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue; "stopped leftover process $($p.ProcessId)" }
}
