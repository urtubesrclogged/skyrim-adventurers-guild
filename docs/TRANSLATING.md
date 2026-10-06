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
names live in `AdventurersGuild.esp`. Translate it with **xTranslator** as usual. The plugin is a light plugin (ESL-flagged) and not
localized (strings are embedded), which xTranslator handles directly. Dynamic String Distributor works as well: ship a
`SKSE/Plugins/DynamicStringDistributor/AdventurersGuild.esp/<name>.json` and the plugin file itself stays untouched. Its records keep fixed FormIDs between versions,
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

## Since 1.1.0

* **Room for your language.** The counter is wider, buttons and tabs grow with their text, and a label that still
  does not fit is tightened and shown slightly smaller (never below 90%) before it is ever cut. You should not need
  to shorten a translation to make it fit; if something is cut, please report it with a screenshot.
* **New keys**, all optional (English is shown for any you leave out):
  * `$AG_City_Whiterun`, `$AG_City_Solitude`, `$AG_City_Windhelm`, `$AG_City_Riften`, `$AG_City_Markarth`,
    `$AG_City_Falkreath`, `$AG_City_Morthal`, `$AG_City_Dawnstar`, `$AG_City_Winterhold`: the branch city shown on
    the counter ("Whiterun Branch").
  * `$AG_RankLabel` (`[Rank {}]`): the label added after quest and note names, e.g. `[Rang {}]`.
  * `$AG_MissivePrefix` (`Missive:`): set this to the prefix YOUR translation of Missives puts before its quest
    titles (e.g. `Missive :`), so the counter can leave it out of its lists.
  * `$AG_Title_GuildMissive`, `$AG_Title_GuildNotice`, `$AG_Party_AndOthers`, `$AG_Toast_ClearedReportPlain`.
* **Do not rely on spaces** at the start or end of a text: some editors remove them.
* **Testing without changing the game's language:** in `SKSE/Plugins/AdventurersGuild.ini`, under `[Debug]`, set
  `Language = FRENCH` (your language's name). Only this mod's text changes.

## For the mod author

`tools/make_translations.py` regenerates the English file from every `Loc::T`/`Loc::F` call in the DLL, `t()` and
`data-t` in the counter page, and `config/lang/mcm_english.json` (`build.ps1 -Only lang`). New player-facing text
must go through those, never as a bare string, or it cannot be translated.
