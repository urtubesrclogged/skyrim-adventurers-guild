# Third-party notices

Adventurers Guild's own code is licensed under the GNU GPL version 3 or later, with the additional permissions in
EXCEPTIONS.md (see LICENSE). It builds on the following work by others.

## Included in this repository

| File | From | License / terms |
|---|---|---|
| `src/plugin/src/PrismaUI_API.h` | PrismaUI SKSE example plugin (PrismaUI-SKSE/example-skse-plugin, `src/PrismaUI_API.h`) | Distributed by its authors for modders to copy into their own projects ("For modders: Copy this file into your own project"). Unchanged apart from a provenance comment. |
| `src/plugin/src/MagelightUI_API.h` | [Magelight UI](https://github.com/Severause/MagelightUI) by Severause, `api/MagelightUI_API.h` at tag v1.8.0 (the header its documentation tells mods to vendor) | MIT (Copyright (c) 2026 Severause); the license text is below. Unchanged. Only used to talk to Magelight.dll when it is installed: the plugin has no build- or load-time dependency on it. |
| `src/papyrus/headers/*.psc` | Compile-time declarations of scripts from Skyrim, SkyUI (SKI_ConfigBase, SKI_QuestBase), SkyrimNet (SkyrimNetApi) and Deeds of Skyrim (DS_Native) | Function/type signatures only, trimmed to what this mod calls, so its scripts compile. No implementation is included; each mod's real scripts are what run. |
| `src/plugin/src/Faces.cpp` (the tint fix) | [Face Discoloration Fix](https://github.com/Exit-9B/Face-Discoloration-Fix) by Parapets: its patch addresses and byte patches, for faces built at run time (the Guild Hall's people ship no FaceGen files). The fix steps aside when Face Discoloration Fix itself is installed. | MIT (Copyright (c) 2020-2023 Parapets); the license text is below. |

### Face Discoloration Fix (MIT)

MIT License

Copyright (c) 2020-2023 Parapets

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

### Magelight UI API header (MIT)

MIT License

Copyright (c) 2026 Severause

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Shipped in the release (not in this repository)

| Files | From | License / terms |
|---|---|---|
| `meshes/` and `textures/AdventurersGuild/Hair/KS/` (the Guild Hall's people: Sky275, Aftershock and Chignon, with their hairlines) | [KS Hairdos SSE](https://www.nexusmods.com/skyrimspecialedition/mods/6817) by Kalilies and Stealthic, v1.10, and the original authors of each style (credited in KS Hairdos' own list) | KS Hairdos' permissions: "You are free to use this mod for any follower and npc mods. This includes using it on npcs in quest mods, city overhauls etc. You can reupload if you keep the mod updated, link to this page and credit us." The meshes' texture paths are rewritten to our folder; nothing else is changed. |
| `textures/AdventurersGuild/Hall2/` and `textures/AdventurersGuild/Board/` (the Guild Hall's and the Guild Board's wood, plaster, stone and metal) | [Vanilla Remastered (Ultimate) - Textures Upscaled and Reworked](https://www.nexusmods.com/skyrimspecialedition/mods/138164) by WaqasTopNotch: its colour maps (and a few of its normal maps), recoloured, resized and cropped | Its permissions: its assets may be used in other mods with credit, and not in mods that are sold. Nexus Mods tags it as AI-generated content. |
| `textures/AdventurersGuild/Hall2/` and `textures/AdventurersGuild/Board/` (the same surfaces' normal maps) | [The New Normal](https://www.nexusmods.com/skyrimspecialedition/mods/140662) 4.0.3 by Skytinerant: its normal maps, resized, with the specular rebuilt in their alpha | Its permissions: its assets may be used without asking as long as it is credited, not in mods that are sold, and its files may not be uploaded to other sites. Nexus Mods tags it as AI media. |

## Linked or used at build time (not included)

| Project | Used by | License |
|---|---|---|
| [CommonLibVR / CommonLibSSE-NG](https://github.com/alandtse/CommonLibVR) (alandtse, ng branch) | SKSE plugin (statically linked) | GPL-3.0-or-later WITH its Modding Exception and GPL-3.0 Linking Exception. This is why the plugin is GPL-3.0-or-later. |
| [spdlog](https://github.com/gabime/spdlog) | SKSE plugin (logging) | MIT |
| [fmt](https://github.com/fmtlib/fmt) | SKSE plugin | MIT |
| [nlohmann/json](https://github.com/nlohmann/json) | SKSE plugin (config, co-save) | MIT |
| [SimpleIni](https://github.com/brofield/simpleini) | SKSE plugin (INI) | MIT |
| [xbyak](https://github.com/herumi/xbyak), [rapidcsv](https://github.com/d99kris/rapidcsv), [toml11](https://github.com/ToruNiina/toml11), [DirectXMath](https://github.com/microsoft/DirectXMath), [DirectXTK](https://github.com/microsoft/DirectXTK) | CommonLib dependencies (vcpkg) | BSD-3-Clause / MIT |
| [OpenVR headers](https://github.com/ValveSoftware/openvr) (shipped with CommonLibVR) | SKSE plugin, VR keyboard | BSD-3-Clause |
| [Mutagen](https://github.com/Mutagen-Modding/Mutagen) (`Mutagen.Bethesda.Skyrim`, `Mutagen.Bethesda.FormKeys.SkyrimSE`) | `tools/EspGen` (builds AdventurersGuild.esp) | GPL-3.0. EspGen's own source is GPL-3.0-or-later like the rest of this repository. The generated .esp is not covered by Mutagen's license. |
| [Caprica](https://github.com/Orvid/Caprica) | Papyrus compiler (build) | MIT |
| [Cyrodiil](https://www.pixelsagas.com/) typeface by Neale Davidson (Pixel Sagas) | The name and rank at the head of the Guild Card, and the Guild Hall's sign | SIL Open Font License 1.1 (`fonts/Cyrodiil-OFL.txt` ships beside the font) |

## Runtime requirements (installed by the player, not redistributed)

SKSE / SKSE VR, Address Library for SKSE Plugins, PrismaUI or Magelight UI, SkyUI (or SkyUI VR) for the MCM, Missives (optional: rank-gated
Guild Missives), with Missives - Worldspace Additions, Missives - Voice and Quest Expansion (by jayserpa) and
Monster Hunt Missives (by sgtbham1, https://www.nexusmods.com/skyrimspecialedition/mods/186539) and Missives for the
Good Guys (by Lizzy of the Wildlander Team, https://www.nexusmods.com/skyrimspecialedition/mods/98373) and its sister mod
Missives for the Bad Guys (by the same author) as optional add-ons
to it, The Notice Board SE (optional: rank-gated Guild Notices), and optionally SkyrimNet, CHIM (Dwemer Dynamics; the Guild's CHIM server plugin in CHIM/server-plugins is our own code, written to CHIM's documented plugin API, with CHIM Injury Framework and CHIM Gore by Marcius3d, MIT, as working examples of it, and CHIM-BiSR as an example of its action bridge; no code is taken from them) and Deeds of Skyrim. Each is the work of its own authors and under its own terms.

`TESV_Papyrus_Flags.flg` is Bethesda's file from the Creation Kit; it is not included - point `PAPYRUS_FLAGS` in
`local.env` at your own copy.

The parchment of the counter's documents (`tex/skin/` in the release archive) is cut from Skyrim's own textures. Those
images are Bethesda's, are included only in the mod's release archive for use with the game, and are not part of
this repository or covered by its licence.

The Elder Scrolls V: Skyrim is (c) Bethesda Softworks / ZeniMax Media. This is an unofficial fan modification.
