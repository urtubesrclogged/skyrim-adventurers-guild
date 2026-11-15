# Guild Hall NPCs: third-party work to credit

Carry these into the mod's THIRD_PARTY_NOTICES / ASSETS and the Nexus page when the NPCs ship.

- **Hair:** Vanilla hair remake by **jg1** (Nexus SE mod 63979, https://www.nexusmods.com/skyrimspecialedition/mods/63979).
  Shipped: `hair17` + `hairline17` (the day clerk) and `femaledarkelfhair04` + `femaledarkelfhair03_hairline` (the
  evening clerk), meshes and `.tri`, the non-physics version, copied from the SE test install (v1.0.2; 1.0.3 is out:
  re-copy from it before release). Under `meshes/AdventurersGuild/Hair/` with our own head-part records, so the mod's
  in-place replacement of vanilla hair is not repeated. The mod's permissions are read as
  allowing this; keep a copy of the permissions text with the release notes.
- **Tint fix:** Face Discoloration Fix by **Parapets** (Exit-9B, MIT, https://github.com/Exit-9B/Face-Discoloration-Fix):
  its addresses and byte patches, in AGFaceSpike's `tint.cpp`.
- **Method only, no code:** FollowerForge (SenjuWoo, MIT) for the RaceMenu Export Head route, kept as a fallback.
- **Refit (ours):** the twin buns (`femaledarkelfhair04` + its hairline) are refit from the Dark Elf head to the Breton head
  (refit_hair.py, positions written into copies of the originals by patch_verts.py); the remake's own files are unchanged
  in `hair_elf_original/`. Credit stays with jg1; the refit is a modification, so note it in the credits text.
- **Hair (shipped):** KS Hairdos SSE by **Kalilies and Stealthic** (Nexus SE 6817,
  https://www.nexusmods.com/skyrimspecialedition/mods/6817), v1.10: "You are free to use this mod for any follower and npc
  mods. This includes using it on npcs in quest mods, city overhauls etc. You can reupload if you keep the mod updated,
  link to this page and credit us." Shipped: **Sky275** (+ `Sky275Hl`, with KS's `straightscalpHUMAN` hairline) on the day
  clerk, **Aftershock** (+ `AftershockHl`) on the evening clerk and **Chignon** (+ `ChignonHl`) on the waitress, meshes, `.tri` and textures, under
  `meshes/` and `textures/AdventurersGuild/Hair/KS/`. The meshes' texture paths were rewritten to that folder by
  `retexture_nif.py`; nothing else in them changed. Credit the styles' original authors too: look each up in KS's own
  credits list (Ade, Alesso, Anto, ... Zauma; Hellosanta's textures) before release. "Keep the mod updated": re-copy
  from KS's current version before each release.
- The remake's four styles above are no longer worn by anyone (their records stay in the spike plugin, unused); drop
  them, and their credit, if they are still unused at release.
