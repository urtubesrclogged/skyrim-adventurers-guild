# Builds Adventurers Guild. Usage: powershell -File build.ps1 [-Only esp|papyrus|dll|voice|lang] [-Configure]
#   esp     : tools/EspGen (AdventurersGuild.esp with the Missives integration, *.resolved.json, missives.json)
#   papyrus : Caprica -> build/papyrus
#   dll     : CMake/Ninja -> src/plugin/build/AdventurersGuild.dll
#   voice   : packs config/Sound (.wav + .lip) into build/Sound as .fuz
#   lang    : Interface/Translations/AdventurersGuild_ENGLISH.txt
# Paths to your tools and to Missives.esp come from local.env (copy local.env.example).
param([string]$Only = "", [switch]$Configure)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

$cfg = @{}
$envFile = Join-Path $root "local.env"
if (-not (Test-Path $envFile)) { throw "local.env not found: copy local.env.example to local.env and set your paths" }
foreach ($line in Get-Content $envFile) {
  if ($line -match '^\s*([A-Z_]+)\s*=\s*(.*?)\s*$') { $cfg[$Matches[1]] = $Matches[2] }
}
function Need([string]$key) { if (-not $cfg[$key]) { throw "local.env: $key is not set" }; return $cfg[$key] }
function NeedWin([string]$key) { return (Need $key).Replace('/', '\') }  # cmd / vcvars want backslashes

if (-not $Only -or $Only -eq "esp") {
  # AdventurersGuild.esp with the Missives integration (Missives.esp is read, not mastered), plus missives.json
  $env:SKYRIM_DATA = Need "SKYRIM_DATA"  # the vanilla masters EspGen resolves names against
  $env:MISSIVES_ADDONS = $cfg["MISSIVES_ADDONS"]   # optional: folders holding Missives add-on plugins (see local.env.example)
  dotnet run -c Release --project "$root\tools\EspGen" -- "$root\build\esp" "$root\config\SKSE\Plugins\AdventurersGuild" (Need "MISSIVES_ESP")
  if ($LASTEXITCODE -ne 0) { throw "EspGen failed" }
}

if (-not $Only -or $Only -eq "papyrus") {
  New-Item -ItemType Directory -Force "$root\build\papyrus" | Out-Null
  Push-Location "$root\src\papyrus"
  & (Need "CAPRICA") --game skyrim --import headers --import . --flags (Need "PAPYRUS_FLAGS") --output "$root\build\papyrus" AG_Native.psc AG_QuestHelper.psc AG_MCM.psc AG_SkyrimNet_Decorators.psc AG_SkyrimNetInit.psc AG_SkyrimNetActions.psc AG_TIF_GuildBusiness.psc
  $rc = $LASTEXITCODE
  Pop-Location
  if ($rc -ne 0) { throw "Caprica failed" }
}

if (-not $Only -or $Only -eq "dll") {
  $src   = "$root\src\plugin"
  $vc    = NeedWin "VCVARS"
  $cm    = NeedWin "CMAKE"
  $ninja = NeedWin "NINJA"
  $commonlib = Need "COMMONLIB_DIR"
  $vcpkg = Need "VCPKG_ROOT"
  $env:PATH += ";C:\Program Files (x86)\Microsoft Visual Studio\Installer"
  if ($Configure -or -not (Test-Path "$src\build\build.ninja")) {
    cmd /c "`"$vc`" >nul 2>&1 && `"$cm`" -S $src -B $src\build -G Ninja -DCMAKE_MAKE_PROGRAM=`"$ninja`" -DCMAKE_BUILD_TYPE=Release -DCOMMONLIB_DIR=`"$commonlib`" -DCMAKE_TOOLCHAIN_FILE=`"$vcpkg/scripts/buildsystems/vcpkg.cmake`" -DVCPKG_TARGET_TRIPLET=x64-windows-static-md 2>&1"
  }
  # 2>&1 inside cmd: Windows PowerShell turns any native stderr line (vcvars sometimes prints one) into a terminating
  # error even when the build succeeds; success is decided by the exit code below
  cmd /c "`"$vc`" >nul 2>&1 && `"$cm`" --build $src\build 2>&1"
  if ($LASTEXITCODE -ne 0) { throw "DLL build failed" }
}

if ((-not $Only -or $Only -eq "voice") -and (Test-Path "$root\tools\voicelines.py")) {
  # voiced lines ship as .fuz: packs every config/Sound .wav + .lip (the editable sources) into build/Sound (incremental).
  # The voice pipeline is not in the published source; without it this step is skipped (the .fuz are prebuilt assets).
  python "$root\tools\voicelines.py" --fuz
  if ($LASTEXITCODE -ne 0) { throw "fuz packing failed" }
}

# The generator is not in the published source; without it this step is skipped and the translation file in config/ is used as is.
if ((-not $Only -or $Only -eq "lang") -and (Test-Path "$root\tools\make_translations.py")) {
  # Interface/Translations/AdventurersGuild_ENGLISH.txt, generated from every Loc::T/F, t() and MCM key (tools/make_translations.py)
  python "$root\tools\make_translations.py"
  if ($LASTEXITCODE -ne 0) { throw "translation file generation failed" }
}
