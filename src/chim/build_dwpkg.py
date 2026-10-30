"""Adventurers Guild for CHIM: builds the server plugin package CHIM installs from the mod folder.

    python src/chim/build_dwpkg.py <version> <mod folder>

writes <mod folder>/CHIM/server-plugins/adventurersguild/<version>+<hash>.dwpkg (and removes older ones: CHIM's DLL
takes the newest file, not the highest version). The hash is of the payload, so a changed plugin is a new version and
CHIM installs it again; an unchanged one is left alone. Also writes <mod folder>/CHIM/adventurersguild_actions.csv from
actions.json: CHIM's DLL uploads every Data/CHIM/*_actions.csv when a save loads (CHIM Plugin/Misc.cpp).

A .dwpkg (HerikaServer docs/custom-plugins.md, lib/plugin_package_manager.php) is a ZIP: manifest.json (schema 4),
checksums.sha256 (SHA-256 of every other file) and the plugin under server/, installed to HerikaServer/ext/<name>/.

The lore comes from the SkyrimNet knowledge pack, so there is one source for both: its general entries (and the ones for
other mods) become Oghma entries under the topics in topics.json; the entries the pack gives only to some factions are
sent by faction (config/.../chim.json lists the factions the DLL reports). An entry that fits neither fails the build.
"""
import hashlib, io, json, os, re, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.join(ROOT, "src", "chim")
PACK = os.path.join(ROOT, "config", "SKSE", "Plugins", "SkyrimNet", "external", "adventurersguild.skyrimnet", "knowledge",
                    "adventurers_guild_lore.sknpack")
CHIM_JSON = os.path.join(ROOT, "config", "SKSE", "Plugins", "AdventurersGuild", "chim.json")
NAME = "adventurersguild"
# HerikaServer loads files with these names from every folder of ext/: our shared code must never be named like one
HOOKS = {"globals.php", "preprocessing.php", "prerequest.php", "context_pre.php", "context.php", "context_building.php", "prompts.php",
         "dialogue_prompt.php", "json_response_custom.php", "prepostrequest.php", "postrequest.php", "interact_actions.php",
         "functions.php"}
STAMP = (2026, 1, 1, 0, 0, 0)  # every entry's date: the same payload makes the same package


def lore():
    pack = json.load(open(PACK, encoding="utf-8"))["skyrimnet_knowledge_pack"]
    topics = json.load(open(os.path.join(HERE, "topics.json"), encoding="utf-8"))
    chim = json.load(open(CHIM_JSON, encoding="utf-8"))
    oghma, factions, bad = [], [], []
    for e in pack["entries"]:
        cond = e.get("condition_expr", "").strip()
        named = re.findall(r'"([^"]+)"', cond)
        if "faction" in cond:
            missing = [f for f in named if f not in chim["factions"]]
            if missing or not re.fullmatch(r'(\s*(or\s+)?(is_in_faction\(actorUUID, "[^"]+"\)|get_faction_rank\(actorUUID, "[^"]+"\) >= 0)\s*)+', cond):
                bad.append(f"{e['key']}: faction condition not understood or faction not in chim.json ({missing or cond})")
                continue
            factions.append({"key": e["key"], "factions": named, "importance": e.get("importance", 0.5), "text": e["content"]})
            continue
        plugin = ""
        if cond:
            if not re.fullmatch(r'is_plugin_loaded\("[^"]+"\)', cond) or named[0] not in chim["plugins"]:
                bad.append(f"{e['key']}: condition not understood or plugin not in chim.json ({cond})")
                continue
            plugin = named[0]
        t = topics["topics"].get(e["key"])
        if not t:
            bad.append(f"{e['key']}: no Oghma topic in src/chim/topics.json")
            continue
        oghma.append({"key": e["key"], "topic": t["topic"], "aliases": t["aliases"], "plugin": plugin, "text": e["content"]})
    if bad:
        sys.exit("knowledge pack entries CHIM cannot place:\n  " + "\n  ".join(bad))
    return {"pack": pack["version"], "guidelines": topics["guidelines"], "oghma": oghma, "factions": factions}


def payload(version_base):
    files = {}
    src = os.path.join(HERE, "server")
    for dp, _, fs in os.walk(src):
        for f in sorted(fs):
            rel = os.path.relpath(os.path.join(dp, f), src).replace("\\", "/")
            if "/" in rel and f in HOOKS:
                sys.exit(f"{rel}: a hook name below the plugin's root would be loaded by HerikaServer as a hook")
            files[rel] = open(os.path.join(dp, f), "rb").read()
    files["data/lore.json"] = (json.dumps(lore(), ensure_ascii=False, indent=1) + "\n").encode("utf-8")
    digest = hashlib.sha256(b"".join(k.encode() + b"\0" + v for k, v in sorted(files.items()))).hexdigest()[:8]
    version = f"{version_base}+{digest}"
    files["lib/ag_chim.php"] = files["lib/ag_chim.php"].replace(b"@AG_VERSION@", version.encode())
    return version, files


def actions_csv():
    """CHIM's custom action import (HerikaServer processor/import_files.php): one row per action, its code naming the
    Papyrus bridge (ExtCmd<script>_<action>, CHIM Plugin/Commands.cpp). Every code must have its rule in lib/ag_chim.php."""
    import csv
    src = json.load(open(os.path.join(HERE, "actions.json"), encoding="utf-8"))
    rules = open(os.path.join(HERE, "server", "lib", "ag_chim.php"), encoding="utf-8").read()
    meta = json.dumps({"dispatch": "plugin_command", "source": "adventurersguild", "integration": "adventurersguild",
                       "protocol": "extcmd_static_dispatch", "bridge_script": "AGChim", "bridge_entrypoint": "DispatchExternalCommand"},
                      separators=(",", ":"))
    params = json.dumps({"type": "object", "properties": {}, "required": []}, separators=(",", ":"))
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["code_name", "action_name", "description", "return_message", "available_to_npc", "available_to_followers",
                "available_to_narrator", "is_activated", "parameters_json", "metadata", "import_version"])
    for a in src["actions"]:
        if not re.fullmatch(r"ExtCmdAGChim_[A-Za-z]+", a["code"]) or f"'{a['code']}'" not in rules:
            sys.exit(f"{a['code']}: not an AGChim code, or no rule for it in server/lib/ag_chim.php")
        w.writerow([a["code"], a["name"], a["description"], a["returnMessage"], "true", "true", "false", "true", params, meta,
                    src["importVersion"]])
    return buf.getvalue().encode("utf-8")


def build(version_base, mod_dir):
    csv_data = actions_csv()
    os.makedirs(os.path.join(mod_dir, "CHIM"), exist_ok=True)
    with open(os.path.join(mod_dir, "CHIM", "adventurersguild_actions.csv"), "wb") as f:
        f.write(csv_data)
    version, files = payload(version_base)
    manifest = {"schema_version": 4, "name": NAME, "version": version,
                "description": "Adventurers Guild: the Guild's lore, ranks and record for CHIM's NPCs (sent by AdventurersGuild.dll).",
                "server": {"mutable_paths": []}}
    entries = [("manifest.json", (json.dumps(manifest, indent=2) + "\n").encode())] + [(f"server/{k}", v) for k, v in sorted(files.items())]
    entries.append(("checksums.sha256", "".join(f"{hashlib.sha256(d).hexdigest()}  {n}\n" for n, d in entries).encode()))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in entries:
            info = zipfile.ZipInfo(n, STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, d)
    out_dir = os.path.join(mod_dir, "CHIM", "server-plugins", NAME)
    os.makedirs(out_dir, exist_ok=True)
    for old in os.listdir(out_dir):
        if old != f"{version}.dwpkg":
            os.remove(os.path.join(out_dir, old))
    out = os.path.join(out_dir, f"{version}.dwpkg")
    with open(out, "wb") as f:
        f.write(buf.getvalue())
    return out, version


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    out, version = build(sys.argv[1], sys.argv[2])
    print(f"CHIM server plugin {version}: {out}")
