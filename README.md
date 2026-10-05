# Adventurers Guild

A fully fleshed-out adventurers guild for Skyrim, inspired by classic RPGs and isekai manga and anime. The Guild keeps
a counter in the inn of every hold capital: talk to the innkeeper, who represents the Guild, to get started.

Works in Skyrim VR and in regular Skyrim Special Edition.

## Main features

- **A Guild Counter at the inn of each of the nine hold capitals**: Guild Card, Quests, Trophies, Services, Party and
  Records, in one window that works with mouse, controller and VR lasers.
- **Your own Guild Card**: your rank, registration date, progress toward the next rank, and career stats.
- **Rank up from E to S**:
  - Registration comes with an assessment that places an experienced character as high as rank C, so the mod is safe
    to add in the middle of a playthrough.
  - Promotion is earned through Reputation and a minimum level (for example, rank D needs 100 Reputation and
    level 12), and is granted by the innkeeper for a small fee.
- **Appraisal**, a Guild skill bought at the counter in three levels: guild ranks on the names of fellow adventurers,
  threat ranks on enemy health bars and on dungeons, and better prices from merchants.
- **Two kinds of standing, tracked for you**:
  - **Reputation** is your name in the Guild. It is never spent, and promotion depends on it. Earned from kills
    (scaled by the foe's threat rank), dungeon reports and guild quests.
  - **Merit** is what the Guild owes you. It is spent on Guild Services. Earned from monster trophies, dungeon reports
    and guild quests.
- **Guild quests** from the boards or straight from the counter, each labelled with its rank and only offered once
  you have earned it:
  - Local Missives, with [Missives](https://www.nexusmods.com/skyrimspecialedition/mods/17576) installed.
  - Provincial Notices, with [The Notice Board](https://www.nexusmods.com/skyrimspecialedition/mods/3218) installed.
- **Reports**: hand in finished quests and cleared dungeons at any counter for gold, Merit and Reputation.
- **Trophies**: sell proof of your hunts to the Guild for Merit.
- **Guild Services**, paid for with Merit:
  - Intel that puts undiscovered dungeons on your map.
  - Guild Training: Vitality, Endurance and Arcana (permanent Health, Stamina and Magicka).
  - A Guild Library of skill books.
  - A Guild Shop of spell tomes and potions.
- **Adventuring parties**:
  - Found your own party, name it, choose up to four companions, and manage it as its leader.
  - Party Bond grows as you fight and travel together, and unlocks party bonuses.
  - 14 Affinities to discover, depending on who is in your party. Up to three can be selected at a time.
  - Party analysis, statistics, and a history of your deeds and of former and fallen members.
- **New dialogue**: nearly 500 voiced lines for vanilla NPCs, so the Guild sounds as if it had always been there.
- **SkyrimNet integration** (optional): NPCs know the Guild, its lore and its rules, know your rank and your party,
  and can play along.
- **Translatable**: all text is in a standard translation file (see [docs/TRANSLATING.md](docs/TRANSLATING.md)).

## Requirements

- [SKSE](https://skse.silverlock.org/)
- Address Library for SKSE Plugins (Special Edition) or VR Address Library (VR)
- [Prisma UI](https://www.nexusmods.com/skyrimspecialedition/mods/148718), for the guild counter and its notices
- Skyrim VR only: Skyrim VR ESL Support (the plugin is a light plugin)

## Optional, recommended

- [Missives](https://www.nexusmods.com/skyrimspecialedition/mods/17576) 2.03: guild quests in every hold. Works
  alongside other Missives patches; no patch is needed.
- [The Notice Board](https://www.nexusmods.com/skyrimspecialedition/mods/3218): more guild quests, shared across the
  province.
- SkyUI: the mod's settings menu (MCM), including the uninstall button.
- SkyrimNet: see above.

Each of these is detected when the game starts. Without one, its part of the mod is simply not there.

## Installation

Install the requirements, then install Adventurers Guild with your mod manager like any other mod. It is safe to add mid-playthrough.

## Uninstalling

In the mod's MCM, open Debug and press **Prepare to Uninstall**. This takes back every Guild ability, perk and party
bonus, removes Guild items and stops the Guild's quests, so nothing stays in your save. Then save, quit, and remove
the mod.

## Compatibility and known issues

- Tested on Skyrim VR 1.4.15 and Skyrim Special Edition 1.5.97. The same DLL is built for Anniversary Edition, which
  has not been tested yet.
- The mod edits no vanilla record, cell or NPC.
- Bounties and investigations from The Notice Board are posted at each hold's own board, so the guild counter may
  list fewer notices than the board outside. This is how that mod works.

## AI disclosure

Yup. I couldn't have made this mod without it.

## About this repository

This is the mod's source, published for transparency: the SKSE plugin is a DLL, so you can read exactly what it does.
Players should install the mod from its Nexus Mods page, not from here.

## What is where

| Path | What |
|---|---|
| `src/plugin/` | The SKSE plugin (C++23, CommonLibVR NG: one DLL for VR, SE and AE) |
| `src/papyrus/` | Papyrus scripts (MCM, quest helpers, SkyrimNet decorators and actions); `headers/` holds compile-time declarations only |
| `tools/EspGen/` | Generates `AdventurersGuild.esp` (ESL-flagged: a light plugin, so Skyrim VR needs Skyrim VR ESL Support) and the resolved config files with Mutagen (no hand-edited plugin) |
| `config/` | Everything the mod ships as data: JSON config, the counter and notice pages (PrismaUI), MCM, translations, SkyrimNet prompts and actions |
| `docs/` | `PARTIES.md` (party system design), `TRANSLATING.md` (for translators) |

## Building

Requirements: Visual Studio 2022 Build Tools (C++), CMake, Ninja, vcpkg, a
[CommonLibVR](https://github.com/alandtse/CommonLibVR) (ng branch) checkout, .NET 9 SDK, Python 3,
[Caprica](https://github.com/Orvid/Caprica), the Creation Kit's `TESV_Papyrus_Flags.flg`, and Missives 2.03
(`Missives.esp`: EspGen reads it to write `missives.json`; the plugin does not override any Missives record, the DLL
applies the rank gating in memory, so it works alongside other Missives patches).

1. Copy `local.env.example` to `local.env` and set the paths.
2. `powershell -File build.ps1` builds the plugin file, the scripts and the DLL (or `-Only esp|papyrus|dll`).
3. `bash deploy.sh` copies the result into your mod-manager folder (`MOD_DIR`); `bash package.sh` zips it.

Not in this repository:

- **The voice files.** They ship only in the mod's download on Nexus Mods. A copy built from this source is silent
  until the `Sound` folder from that download is copied over it.
- **The generators** for the translation file, the art and the voice lines. Their outputs that the mod needs
  (`config/Interface/Translations`, the textures under `config/PrismaUI`) are included as they are.

## License

- **Code**: MIT, see [LICENSE](LICENSE).
- **Assets** (art, voices, dialogue, lore and other text): all rights reserved with the permissions in
  [ASSETS.md](ASSETS.md).
- **Third-party code and dependencies**: see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Author: urtubesrclogged (Nexus Mods, GitHub, Discord).
