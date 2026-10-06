# Changelog

## 1.2.1

**Trophies**
- The Guild now buys parts from hostile creatures added by other mods. An ingredient, hide or other animal part counts
  when a creature that starts fights carries or drops it; harmless wildlife adds nothing, and meat and fish are never
  trophies. A "creature" with an alchemist's pockets full of ingredients is carrying loot, and none of that counts.
  Merit follows the item's gold value, up to 5 each. Vanilla trophies are unchanged.
- `guild.json`, `modCreatureTrophies`: the gold-per-Merit rate, the cap, and a switch to turn this off.

## 1.2.0

**Guild Card**
- You now carry a physical Guild Card. Read it from your inventory anywhere in Skyrim to see your Guild Card page:
  rank, progress toward the next rank and career record, without a trip to a hold capital.
- The innkeeper hands it over when you register, and it is updated to your new rank at each promotion. Members from
  earlier versions receive theirs when they load their save.
- Read away from a counter, the card carries Field Notes: reports ready, quests in progress, trophies to sell, and
  a note when you are eligible for promotion.
- The first card is free. If you sell or lose it, ask the innkeeper at any Guild counter for a replacement (25 gold).
- Optional key to open the card (MCM, System page). None is set by default. In VR, VRIK's gesture
  menu offers "Adventurers Guild: Guild Card" as an action.

**Other**
- MCM, Debug page: the optional mods Adventurers Guild works with (Missives, The Notice Board, SkyrimNet) and
  whether each is Active, Inactive or Not Detected.
- SkyrimNet: NPCs know what each rank is trusted with, and about the guild card; an innkeeper can hand over a
  replacement card in conversation.

## 1.1.0

**Parties**
- A party can now have up to nine companions (it was four). The Party tab pages its list, and the Analysis chart shows
  everyone at once.
- The Party Bond armor bonus is a flat +20 while at least one member is with you. It was +10 for each member present.

**Fixes**
- Followers that another mod edits (for example Jenassa with Interesting NPCs installed) were not recognised as party
  members: no "With you", no Bond, no Affinities. Fixed. Existing saves are repaired when they load, and the log
  (`AdventurersGuild.log`) says how many saved entries were corrected.
- Dungeon notices no longer appear before you have joined the Guild.
- A dungeon's threat rank is now part of Appraisal, like the ranks on names and health bars: without Appraisal I a
  member is still told to report a cleared dungeon, but not its rank.

**Guild counter**
- The window is wider (1280 instead of 1080), and it scales down to fit a smaller screen.
- Buttons and tabs grow with their text, and nothing is shown below 90% of its size before it would be cut.

**Translations**
- The branch city names, the "[Rank X]" label on quest titles and a few more texts can now be translated.
- Accents on capital letters are no longer cut off on the Guild Card.
- Translators can test a language without changing the game's own: `[Debug] Language` in `AdventurersGuild.ini`.
- See `docs/TRANSLATING.md` ("Since 1.1.0") for the new keys.

## 1.0.1

- Licensing only: the plugin is GPL-3.0-or-later (it is built on CommonLibSSE-NG). The download includes the license
  text and notices. No functional changes.

## 1.0.0

- First release.
