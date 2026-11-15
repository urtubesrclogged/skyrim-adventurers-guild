# HallGen: the Guild Hall's generator

Builds the Guild Hall that ships with Adventurers Guild 2.0: its plugin (`AdventurersGuild - Guild Hall.esp`), its meshes and
textures, and its people. It is to the hall what `tools/EspGen` is to AG's own plugin.

## Build and deploy

```
bash build.sh                     # from AG's root: AG's build, the hall's build and every gate, then both to every test install
bash build.sh --no-deploy         # build and check only
bash build.sh --hall-only fus     # the hall alone, to one install
```

What `build.sh` does:
- **The last commit only.** It builds in `build/build-src`, a second checkout moved to HEAD, with the ignored inputs linked in.
  Uncommitted edits, yours or another session's, are never built. Commit, then build.
- **One at a time.** It takes the build lock (`lock.sh`); a second caller waits its turn, and the status page shows the queue.
  `deploy_hall.sh` takes the same lock when run on its own.
- **Only what changed.** AG and the hall are each rebuilt only if their committed files or their ignored inputs changed since
  their last good build; the hall is also rebuilt when AG's plugin changed. `--force` builds both.
- **Each install as soon as its game is closed.** MO2 locks an install's files while its game runs. Each install is checked
  against the build afterwards and stamped on the status page.
- **Stops on failure.** A failed build or gate stops before anything is deployed.

Every step reports to `build/status/index.html`; set `AG_SESSION` to name yourself there. The page also lists what each
install's last deploy brought: put `Test: <what to check in game>` lines in a commit message and they show there. Questions a
session needs answered go there too: `python tools/HallGen/status/status.py ask "<question>"`, and `resolve <n>`
once answered.

The steps on their own:

| | |
|---|---|
| `build_hall.sh` | export, the export's checks, meshes, plugin (NPCs merged in), scripts, every gate, into `build/hall` |
| `gates_all.sh` | every gate on an export; a failure not in `gates/accepted.tsv` stops the build |
| `deploy_hall.sh` | the built hall to the installs |
| `npcs/build_scripts.sh` | the hall folk's Papyrus, into `npcs/build/Scripts` |

## Settings

From AG's `local.env` (`env.sh`, `hallenv.py`): `HALL_INSTALLS` (the test installs: `name|its "Adventurers Guild 2.0" mod
folder|game exe`, separated by `;`), `BLENDER`, `TEXCONV`, `SKYRIM_DATA`, `CAPRICA`, `PAPYRUS_FLAGS` and the C++ toolchain
AG's own build uses. See `local.env.example`.

## What is not in the repository

`tools/hall-private` (ignored, as AG's other private tools are): the voice recordings and their takes; textures and meshes
made from the game's own files; the full Papyrus headers (the game's and SKSE's sources); third-party hair (see
`npcs/CREDITS.md`); research, drafts, plans and renders.

`tools/hall-private/prebuilt` holds the shipped textures and meshes that their own generators make, outside the hall's build:
`textures/make_hall_textures.py`'s upscaled copies, the paintings, the chains, the Guild Board (`board/`) and the leader board
(`leaderboard/`). `build_hall.sh` lays them into the build first. When one changes, run its generator and copy the result
there, at the path it ships at. `build/hall-work` (ignored): the export, the extracted data root the
meshes are built against, the mesh cache, the plugin's ID ledger, the gates' baseline and the logs.

The hall's history before it joined AG is archived outside the repository.
