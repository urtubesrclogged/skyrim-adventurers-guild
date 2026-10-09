# Changelog

## 1.4.0

**World Building and NPCs**
- The Adventurers Guild now has a counter on Solstheim: Geldis Sadri at the Retching Netch in Raven Rock!
- With Missives - Worldspace Additions installed, the Raven Rock missive board is a Guild board too (new integration)
- Hundreds of new and reworked voiced lines for NPCs: Solstheim, the Dawnguard, housecarls, jarls, stewards, and many
  others all across Skyrim.
- Named adventurers who travel with you rise in rank as they level, and say so

**Balance Changes**
- Rank S is actually rare now. In a new game it starts at level 80, not 60, and level alone is no longer enough: only
  the oldest dragons, dragon priests and a few legends are S. Wildlife capped at B.
  - No more A-rank skeevers!
  - Other adventurers stop at A. Only you and your companions can be S
- Nobody loses a rank or gets the rug pulled. A playthrough already under way keeps its old levels (S at 60) until you
  change the new setting yourself or start a new game.
- Trophies earn less Merit across the board, the big game most of all (a dragon bone is 6, down from 15). Trophies
  from other mods' creatures pay 1 Merit per 25 gold of value, up to 4
- Guild training costs more Merit from rank C up. What you have already trained is untouched.

**New Guild Stuff**

*Intel*
- New Points of Interest tab: the Guild sells the whereabouts of Orc strongholds, standing stones, Daedric shrines,
  camps, landmarks, shipwrecks and more

*Services*
- New Guild Augments: a boon for the road that lasts a day, one at a time (carry more, better prices, faster skill
  gains, hardier, or a little more Health, Stamina and Magicka)

*Shop*
- Spell tomes one rank above your own can now be bought, at twice the Merit
- A lost Guild Card can be bought again on the counter's Guild Card tab, as well as by asking the rep

**Improvements & QoL**
- A new look for the Guild's papers: the Guild Card, missives, the party banner, the Field Notes and the promotion
  notice are aged parchment with torn edges, and the wax seal is larger
- A running Guild Augment shows on the Guild Card with the hours it has left
- New MCM setting, Level for rank S (60 to 120), for games that level far past 80 or scale their enemies up. The same
  levels apply to your promotions, threats, dungeons and other adventurers
- The Guild counter, Guild Card and notices now scale up on screens larger than 1080p (they were tiny at 4K)
- An empty Dungeons tab now says why: nothing in this hold at your rank
- Stendarr's Beacon and the Hall of the Vigilant are Points of Interest now, not dungeons
- Dawnstar's lines change once the nightmares end
- SkyrimNet: NPCs know what rank S means, and know about Guild Augments and tomes

**Fixes/Bugs**
- Places a quest has not yet put on the map are no longer sold as intel
- Followers who also work at an inn (Immersive Wenches and the like) no longer offer Guild dialogue while they travel
  with you
- "Jarl" is pronounced the way Skyrim says it in every voiced line
- A few voiced lines that opened with a distorted first word were re-recorded

## 1.3.1

**Fixes**
- Loading the game took far longer with 1.3.0 on large load orders (minutes on the biggest). The search for trophies
  from other mods' creatures is now quick and no longer happens while the game loads

## 1.3.0

**Threat Ranks Reworked**
- Threat ranks should now reflect how dangerous a creature is, not based only on its level
- Works for creatures added or changed by other mods (may not be perfect for some added creatures without deeper
  integration/awareness, but much improved over previous logic)
- No more E-rank giants!

**Appraisal**
- Each level of Appraisal now reads more of what is out there; what you cannot read yet shows as [?]
- Small nerf to Merit bonus on trophies

**Conduct**
- Having a bounty on you now costs you Reputation and can put promotion on hold (the Guild only cares what you do
  outside of the guild if you get caught and risk their relationships with the local jarls)
- Abandoning a missive costs you some Reputation now as well

**World Building and NPCs**
- Additional active adventurers (Sinmir, Mjoll, Annekke, etc.)
- Erik/Erik the Slayer guild integration
- Random adventurer encounters on the roads
- Inn Keeper Contingency Protocol (Nils might be the best guild rep now)

**Trophies**
- The Guild buys trophies from hostile creatures added by other mods

**Other**
- The Guild's notice is handed out when you use a Missives board, not when you walk past one and fixed the
  "register first" reminder repeating near a Missives board
- MCM Debug page: recalculate rank from level
- SkyrimNet: updated lore and NPC bios to match all other changes here

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
