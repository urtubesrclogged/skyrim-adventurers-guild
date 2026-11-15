# Guild Hall folk: SkyrimNet bios, lore and ranks

The SkyrimNet side of the hall's twelve NPCs. The lore will keep changing as 2.0 is built. Nothing here ships yet; it all goes in when the hall is folded into the mod.

## bios/

Shipped (2026-10-27) as config/SKSE/Plugins/SkyrimNet/external/adventurersguild.skyrimnet/prompts/characters/, named from
the merged plugin's references (each NPC's ID + 0x7800, its reference one above it: margot_belleau_001 ... caralion_of_cloudrest_043).
These files stay the source: edit here, then copy over.

One SkyrimNet character bio per NPC, named by its editor ID in the spike plugin (AGNpcSpike.esp). SkyrimNet finds a bio
by file name, `prompts/characters/<name>_<last three hex digits of the placed REFERENCE's form ID>.prompt` (not the
NPC record's: measured 2026-10-27, Hulda's base is 013BA3, her reference 01A66E, her bio hulda_66E.prompt) (name lower-case, words joined
with `_`, as the SkyrimNet bundles in the library do: `inigo_AE9.prompt`). The form IDs change when the NPCs move into the
hall's plugin, so the files are renamed at that point, from the final plugin, and go into the Guild's layer at
`config/SKSE/Plugins/SkyrimNet/external/adventurersguild.skyrimnet/prompts/characters/`.

| file | name | today's form ID |
|---|---|---|
| AGHallGuildMaster | Willem | 830 |
| AGHallClerkDay | Margot Belleau | 800 |
| AGHallClerkEvening | Nessa | 80E |
| AGHallAssistant | Merila Andalen | 832 |
| AGHallBarkeeper | Cassius Varro | 834 |
| AGHallCook | Old Henriette | 836 |
| AGHallServer | Brynja | 838 |
| AGHallResidentOrc | Ghrulek | 83A |
| AGHallResidentRanger | Ylva | 83C |
| AGHallResidentScout | Zhasim | 83E |
| AGHallResidentVeteran | Marius Crassus | 840 |
| AGHallResidentNoble | Caralion of Cloudrest | 842 |

Open: whether SkyrimNet reads `prompts/characters` from an external bundle (the library's bios bundles do it, e.g.
`skyrimnet.bios-dawn-of-skyrim`; no external bundle on FUS does). Check before integration; if not, they ship as their own
bios bundle beside the Guild's.

## The timeline every bio agrees with

- 4E 17: Titus Mede I, the year he takes the Ruby Throne, charters the Guild in the Imperial City.
- 4E 168: the Guild comes to Skyrim, under a charter from Titus Mede II in the year of his crowning (so
  the first company has six years of work before the war; the released 1.6 lore keeps 4E 170/171). High King Istlod grants it one hall, outside the hold capitals, on the road above
  Riverwood. A first company of about forty moves in. Henriette cooks; Marius is one of the veterans sent north; Willem,
  nineteen, signs on as an E-rank.
- 4E 171: the Great War begins.
- 4E 174: the Legion calls the Guild up as auxiliaries; the company marches out together.
- 4E 175: the Red Ring and the Concordat. Six come home, Willem and Marius among them. The hall is shut; Henriette keeps
  the kitchen key; the inn counters carry on.
- 4E 175-200: Willem rises to A-rank and, for the last ten years, petitions the Registrar-General to reopen the hall.
- 4E 200: Willem reopens the hall, partly with his own savings. The staff are hired over that year; the residents drift in.
- 4E 201: the game. The hall has been open about a year.

Willem is a retired A-rank. S stays out of reach: no one in the hall has it.

## Lore pack (tools/make_lore_pack.py), at integration

Keys stay the same (SkyrimNet syncs the pack by key); titles and text change.

**ag_basics** ("The Adventurers Guild"): replace the sentence about having no guildhall with:

> Its home in Skyrim is the Guild Hall on the road above Riverwood, the one hall the Guild keeps in the province, where
> its Guild Master grants promotions and its members eat, train and sleep between jobs. Every hold capital's inn keeps a
> Guild counter too, where the innkeeper signs up newcomers, buys the trophies of a good hunt and takes reports, and the
> Guild's jobs go up on the hold's missive board.

**ag_compromise**, retitled "Skyrim's Guild Hall":

> Each province has one central hall of the Adventurers Guild. When the Guild came to Skyrim in 4E 168, under a charter from Titus Mede II in the year of his crowning, the Jarls would
> grant no land inside their capitals to an Imperial-chartered guild, and the Companions claimed the cities' glory. High
> King Istlod settled it: one hall, outside the hold capitals, on the road above Riverwood, and a counter in each
> capital's inn. The hall's first company marched to the Great War as Legion auxiliaries and few came home; the hall stood
> shut for twenty-five years while the counters kept the Guild alive. Willem, a retired A-rank and one of the six who came
> back, reopened it in 4E 200.

**ag_dwindling**: "...against the Companions and without halls of its own" becomes "...against the Companions, and its
hall stood empty from the Great War until a year ago."

The registration change in the hall's backlog (players register at the hall, not the inns) will change ag_basics again.

**New: ag_hall_folk**, "Who's who at the Guild Hall". For those who have been there: Riverwood's people, Guild members,
the innkeepers who keep a counter, and the hall folk themselves (the targets are settled at integration, when the hall
has its own faction).

> The Guild Hall above Riverwood is run by its Guild Master, Willem, a scarred Nord and retired A-rank who came home from
> the Great War with the hall's first company and reopened the hall a year ago. Merila Andalen, a Dunmer, is his
> assistant and keeps the hall's records and library. Two Breton clerks keep the Guild counter: brisk Margot Belleau by
> day and young Nessa in the evening, and after midnight the barkeeper, Cassius Varro, an Imperial who hears every
> rumour, takes Guild business. Brynja, a Nord farm girl, serves the tavern, and Old Henriette, who cooked for the first
> company, runs the kitchen. Four members live in the attic: Ghrulek, a loud Orc warrior of C-rank; Ylva, a quiet B-rank
> ranger from the Pale; Zhasim, a Khajiit scout who stays D-rank on purpose; and Marius Crassus, the old company's
> sergeant, a retired A-rank. The best room belongs to Caralion of Cloudrest, a rich young Altmer of D-rank whom nobody
> likes and whose gold keeps the roof up.

## Ranks (config/SKSE/Plugins/AdventurersGuild/adventurers.json), at integration

Draft `named` entries (the registration dates are my proposal, from the timeline), in the file's own form (rank = the rank they start at; level is left to the NPC records). EspGen
resolves editor IDs against the vanilla masters today, so it needs the hall's plugin added before these resolve.

| npc | rank | registered | note (their SkyrimNet bio line) |
|---|---|---|---|
| Willem | A, retired | 4E 168 | Guild Master of the hall above Riverwood; a retired A-rank who reopened the hall |
| Marius Crassus | A, retired | 4E 168 | the first company's sergeant; retired, lives in the hall's attic |
| Ylva | B | 4E 193 | the hall's ranger; takes the monster hunts no one else will |
| Ghrulek | C | 4E 197 | Orc warrior, lives in the hall's attic; half his pay goes to his stronghold |
| Zhasim | D | 4E 196 | Khajiit scout; sells the Guild the whereabouts of places; stays D on purpose |
| Caralion of Cloudrest | D | 4E 200 | bought his rank with hired swords' deeds; most members know it |

How a "retired" rank with no retiredWhen location is expressed is for integration (adventurers.json's retirement today
is a location condition).

## Translations

The names go through the language file with the plugin. The bios and lore are English only, as the Guild's SkyrimNet
layer is today (its manifest lists `en`).
