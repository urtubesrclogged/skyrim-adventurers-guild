# Third-party notices

Adventurers Guild's own code is MIT-licensed (see LICENSE). It builds on the following work by others.

## Included in this repository

| File | From | License / terms |
|---|---|---|
| `src/plugin/src/PrismaUI_API.h` | PrismaUI SKSE example plugin (PrismaUI-SKSE/example-skse-plugin, `src/PrismaUI_API.h`) | Distributed by its authors for modders to copy into their own projects ("For modders: Copy this file into your own project"). Unchanged apart from a provenance comment. |
| `src/papyrus/headers/*.psc` | Compile-time declarations of scripts from Skyrim, SkyUI (SKI_ConfigBase, SKI_QuestBase), SkyrimNet (SkyrimNetApi) and Deeds of Skyrim (DS_Native) | Function/type signatures only, trimmed to what this mod calls, so its scripts compile. No implementation is included; each mod's real scripts are what run. |

## Linked or used at build time (not included)

| Project | Used by | License |
|---|---|---|
| [CommonLibVR / CommonLibSSE-NG](https://github.com/alandtse/CommonLibVR) (alandtse, ng branch) | SKSE plugin | MIT |
| [spdlog](https://github.com/gabime/spdlog) | SKSE plugin (logging) | MIT |
| [fmt](https://github.com/fmtlib/fmt) | SKSE plugin | MIT |
| [nlohmann/json](https://github.com/nlohmann/json) | SKSE plugin (config, co-save) | MIT |
| [SimpleIni](https://github.com/brofield/simpleini) | SKSE plugin (INI) | MIT |
| [xbyak](https://github.com/herumi/xbyak), [rapidcsv](https://github.com/d99kris/rapidcsv), [toml11](https://github.com/ToruNiina/toml11), [DirectXMath](https://github.com/microsoft/DirectXMath), [DirectXTK](https://github.com/microsoft/DirectXTK) | CommonLib dependencies (vcpkg) | BSD-3-Clause / MIT |
| [OpenVR headers](https://github.com/ValveSoftware/openvr) (shipped with CommonLibVR) | SKSE plugin, VR keyboard | BSD-3-Clause |
| [Mutagen](https://github.com/Mutagen-Modding/Mutagen) (`Mutagen.Bethesda.Skyrim`, `Mutagen.Bethesda.FormKeys.SkyrimSE`) | `tools/EspGen` (builds AdventurersGuild.esp) | GPL-3.0. EspGen's own source is MIT; a compiled EspGen binary, which links Mutagen, may only be distributed under GPL-3.0. The generated .esp is not covered. |
| [Caprica](https://github.com/Orvid/Caprica) | Papyrus compiler (build) | MIT |

## Runtime requirements (installed by the player, not redistributed)

SKSE / SKSE VR, Address Library for SKSE Plugins, PrismaUI, SkyUI (or SkyUI VR) for the MCM, Missives (optional: rank-gated
Guild Missives), The Notice Board SE (optional: rank-gated Guild Notices),
and optionally SkyrimNet and Deeds of Skyrim. Each is the work of its own authors and under its own terms.

`TESV_Papyrus_Flags.flg` is Bethesda's file from the Creation Kit; it is not included - point `PAPYRUS_FLAGS` in
`local.env` at your own copy.

The Elder Scrolls V: Skyrim is (c) Bethesda Softworks / ZeniMax Media. This is an unofficial fan modification.
