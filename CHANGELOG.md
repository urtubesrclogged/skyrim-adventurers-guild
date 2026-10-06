# Changelog

## 1.2.0

**Guild Card**
- You now carry a physical Guild Card. Read it from your inventory anywhere in Skyrim to see your Guild Card page:
  rank, progress toward the next rank and career record, without a trip to a hold capital.
- The innkeeper hands it over when you register, and it is updated to your new rank at each promotion. Members from
  earlier versions receive theirs when they load their save.
- The first card is free. If you sell or lose it, ask the innkeeper at any Guild counter for a replacement (25 gold).
- Optional key to open the card (MCM, System page). None is set by default. In VR, VRIK's gesture
  menu offers "Adventurers Guild: Guild Card" as an action.

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
