# Translating the Adventurers Guild

Everything the player reads can be translated without touching code. A translation is a small patch mod with up to
three parts, all optional:

## 1. The interface text: one file

`Interface/Translations/AdventurersGuild_ENGLISH.txt` holds every line of the DLL's text (notices, HUD messages,
counter messages, Intel descriptions, rank labels), the guild counter window and the MCM.

1. Copy it to `AdventurersGuild_<LANGUAGE>.txt` in the same folder, where `<LANGUAGE>` is the game's language
   (Skyrim.ini `sLanguage`): `FRENCH`, `GERMAN`, `ITALIAN`, `SPANISH`, `POLISH`, `RUSSIAN`, `JAPANESE`, `CHINESE`...
2. Translate the text after the TAB on each line. Never change the `$AG_...` key before it.
3. Keep the placeholders: `{}` is filled in order; `{0}`, `{1}` by position, so you may reorder them
   (`Toward Rank {0}` -> `Vers le rang {0}`). `\n` is a line break.
4. Save as **UTF-16 LE with BOM** (the Skyrim translation file format; in Notepad++: Encoding > UCS-2 LE BOM).

Lines you leave out simply stay English, so a partial translation works. The game picks the file for its language
automatically; MCM Helper reads the same file for the mod's menu.

## 2. Dialogue, notes, quest and spell names: the plugin

Innkeeper and world dialogue, topic choices, the Guild Missive notes, the registration missive, Appraisal and training
names live in `AdventurersGuild.esp`. Translate it with **xTranslator** as usual. The plugin is not ESL-flagged and not
localized (strings are embedded), which xTranslator handles directly. Its records keep fixed FormIDs between versions,
so a saved xTranslator dictionary re-applies to updates.

## 3. Voices (optional)

Voice files are `Sound/Voice/AdventurersGuild.esp/<VoiceType>/<name>.fuz`. A translated voice pack ships files with
the same names. The names come from fixed dialogue FormIDs, so they stay stable between versions.

## Also translatable

* **Trophies other mods add** (`SKSE/Plugins/AdventurersGuild/trophies.json`, `byName`): `name` may be a list, so add
  your language's item name, e.g. `"name": ["Troll Hide", "Peau de troll"]`. Trophies matched against vanilla items
  need nothing: the game already names both in your language.
* **SkyrimNet lore** (`SKSE/Plugins/SkyrimNet/external/adventurersguild.skyrimnet/`): plain text, if you want the
  NPCs' background knowledge in your language (SkyrimNet's AI can answer in other languages regardless).

Item, book and spell names in the counter come from the game's own records and are already in your language.
Rank letters (E to S) are the same in every language.

## For the mod author

`tools/make_translations.py` regenerates the English file from every `Loc::T`/`Loc::F` call in the DLL, `t()` and
`data-t` in the counter page, and `config/lang/mcm_english.json` (`build.ps1 -Only lang`). New player-facing text
must go through those, never as a bare string, or it cannot be translated.
