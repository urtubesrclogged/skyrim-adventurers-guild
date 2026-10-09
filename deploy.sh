#!/usr/bin/env bash
# Deploys Adventurers Guild build outputs into its MO2 mod folders (NOT overwrite/, which would shadow
# them). MO2 locks its files while the game runs, so this refuses to deploy then.
set -e
R="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$R/local.env" ] || { echo "local.env not found: copy local.env.example to local.env and set your paths" >&2; exit 1; }
while IFS= read -r line || [ -n "$line" ]; do   # KEY=VALUE lines (values may contain spaces); # comments skipped
	case "$line" in '#'*|'') continue ;; esac
	export "${line%%=*}=${line#*=}"
done < "$R/local.env"
# AG_MOD_DIR (environment) overrides local.env for one run, e.g. to stage a test build outside the mod manager
M="${AG_MOD_DIR:-${MOD_DIR:?local.env: MOD_DIR is not set}}"
GAME_EXE="${GAME_EXE:-SkyrimSE.exe}"
if tasklist 2>/dev/null | grep -qi "$GAME_EXE"; then
	echo "$GAME_EXE is running - close the game before deploying." >&2
	exit 1
fi
P="$M/SKSE/Plugins/AdventurersGuild"
mkdir -p "$P" "$M/Scripts" "$M/PrismaUI/views/AdventurersGuild"
# retired files from earlier builds (the MCM moved off MCM Helper onto SkyUI's own API in 1.11)
rm -f "$M/Scripts/AG_ConfigMenu.pex" "$M/MCM/Config/AdventurersGuild/config.json" "$M/MCM/Config/AdventurersGuild/settings.ini"
rmdir "$M/MCM/Config/AdventurersGuild" "$M/MCM/Config" "$M/MCM" 2>/dev/null || true
cp "$R/src/plugin/build/AdventurersGuild.dll"             "$M/SKSE/Plugins/AdventurersGuild.dll"
cp "$R/config/SKSE/Plugins/AdventurersGuild.ini"          "$M/SKSE/Plugins/AdventurersGuild.ini"
for f in guild.json adventurers.json trophies.json shop.json traits.json notices.json threat.json missives.addons.json; do
	cp "$R/config/SKSE/Plugins/AdventurersGuild/$f" "$P/$f"      # sources (documentation; the DLL reads guild.json directly)
done
cp "$R"/build/esp/*.resolved.json "$P/"
rm -f "$P/bounties.json" "$P/bounties.resolved.json" "$P/isekai_points.json"   # retired: bounties (kills pay Reputation directly), Isekai Hero points (shelved patch)
cp "$R/build/esp/missives.json" "$P/missives.json"              # Missives board quests (tier, hold) for MissiveWatch
cp "$R"/config/PrismaUI/views/AdventurersGuild/*.html "$M/PrismaUI/views/AdventurersGuild/"
mkdir -p "$M/PrismaUI/views/AdventurersGuild/tex" && cp "$R"/config/PrismaUI/views/AdventurersGuild/tex/*.png "$M/PrismaUI/views/AdventurersGuild/tex/"
cp "$R"/build/papyrus/AG_*.pex                             "$M/Scripts/"
# SkyrimNet 0.25+ content-library plugin (prompts + lore knowledge pack), shipped as an EXTERNAL layer: SkyrimNet
# registers external/<id>/ at start-up (MinLL/SkyrimNet-GamePlugin docs/modding/MIGRATING_TO_BETA25.md). library/ is
# only for hub/local installs (a mod-shipped folder there is "Ignoring unregistered store dir"). The pre-0.25 prompts/
# folder is no longer read, so old copies in either place are removed.
SN="$M/SKSE/Plugins/SkyrimNet"; rm -rf "$SN/prompts" "$SN/library" "$SN/external/adventurersguild.skyrimnet"
mkdir -p "$SN/external" && cp -r "$R/config/SKSE/Plugins/SkyrimNet/external/adventurersguild.skyrimnet" "$SN/external/"
cp "$R/build/esp/AdventurersGuild.esp" "$M/AdventurersGuild.esp"
# translations: the standard Skyrim file (DLL text, counter page, MCM); translators add _FRENCH.txt etc. beside it
mkdir -p "$M/Interface/Translations" && cp "$R/config/Interface/Translations/AdventurersGuild_ENGLISH.txt" "$M/Interface/Translations/"
mkdir -p "$M/SEQ" && cp "$R/build/esp/SEQ/AdventurersGuild.seq" "$M/SEQ/"
# voiced lines ship as .fuz: build.ps1 -Only voice packs config/Sound (.wav + .lip sources) into build/Sound
if [ -d "$R/build/Sound" ]; then rm -rf "$M/Sound" && mkdir -p "$M/Sound" && cp -r "$R/build/Sound/." "$M/Sound/"; fi   # .fuz only; replaces the old WAV + LIP set
[ -f "$M/meta.ini" ] || printf '[General]\nmodid=0\nnotes=Adventurers Guild. Requires Missives 2.03.\n' > "$M/meta.ini"   # MO2 bookkeeping only
echo "deployed"; find "$M" -type f | sed "s#$M/##" | sort
