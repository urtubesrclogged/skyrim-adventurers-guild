# Changelog

## 1.3.0

**Threat Ranks**
- Threat ranks now reflect how dangerous a creature is, not only its level
- Works for creatures added or changed by other mods
- Minimum ranks for giants, Dwarven Centurions, Draugr Deathlords and Dragon Priests

**Appraisal**
- Appraisal I reads adventurers, people, wildlife and dungeons
- Appraisal II reads creatures of legend (trolls, draugr, vampires, dragons, etc.)
- Appraisal III reads rank A and S threats
- Smaller Merit bonus on trophies

**Conduct**
- Bounties cost Reputation and put promotion on hold
- Abandoning a missive costs Reputation

**World Building and NPCs**
- Additional active adventurers (Sinmir, Mjoll, etc.)
- Wandering adventurers on the roads are Guild members
- Replacement Guild reps when an innkeeper dies (Ysolda, etc.)

**Trophies**
- The Guild buys parts from hostile creatures added by other mods

**Other**
- The Guild's notice is handed out when you use a Missives board, not when you walk past one
- MCM Debug page: recalculate rank from level
- SkyrimNet: updated lore and NPC bios
- Fixed the "register first" reminder repeating near a Missives board

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
