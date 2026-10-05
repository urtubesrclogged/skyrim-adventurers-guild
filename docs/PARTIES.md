# Adventuring Parties — design (agreed 2026-09-28)

The player registers a party at any Adventurers Guild counter, leads it, and fills it with follower adventurers.
The Guild keeps a party ledger. Parties have their own measure, **Bond**, which grants a combat blessing.

## Rules
- **One active party at a time**, always led by the player. Founding it needs a registered player, a
  **fee** (guild.json `party.fee`, default 100 gold) and **at least one founding companion**: no party of one. The
  player picks the founders from the follower adventurers at their side and names it (typed; in VR through the
  headset keyboard).
- **Eligible to join:** a Guild member (any Adventurers kind "member", which every teammate becomes) who is an
  **active follower** (player teammate) and not already an active member. Size cap: `party.maxMembers`, default and hard maximum 4 companions (a party is at most 5 with the player), whatever a follower mod allows.
- **Remove:** any active member, following or not. They stay on the ledger as **former** (date left).
- **Death:** an active member who dies is recorded as **fallen** (date and place).
- **Disband:** behind a clear confirmation (a warning naming the party; the controller highlight starts on "Keep the
  Party"). The party stays on the ledger as **disbanded**; its active members become former. A new party can then be
  founded. Renaming is allowed while active.
- **Rejoining:** a former member added again becomes active again.

## Bond (the party's measure — never a letter, never in brackets)
Guild rank shows `(C)`, threat rank `[C]`; Bond is **named tiers with pips**, shown on the counter and in SkyrimNet
only, never on nameplates.

| Pips | Tier |
|---|---|
| ●○○○○ | Strangers |
| ●●○○○ | Companions |
| ●●●○○ | Comrades |
| ●●●●○ | Sworn |
| ●●●●● | Legend |

- **Per companion, then averaged.** Bond is between the player and each NPC, kept apart from any party: removing and
  re-adding someone, or founding a new party with the same companions, carries it over. It is earned only while they
  are an active member, through time and deeds together (days in the field at the player's side, shared kills and
  assists, dungeons cleared, missives completed while present). The party's Bond is the **mean over its active
  members**: party size is neither penalised nor rewarded, and a newcomer (Bond 0) lowers an established party's
  average until they earn their place. Former and fallen members do not count.
- **Needs company.** With no party member at the player's side, Bond is **dormant** (shown so on the counter) and
  grants nothing; it neither grows nor applies.
- **Blessing (combat only):** only while at least one member is at the player's side; on the player and every active
  member near the player (distance condition in the MGEF, no polling). Scales with the Bond tier and with how many
  members are present: modest regeneration / resistance. Guild privileges
  (missive rank, discounts) are deliberately NOT part of Bond.

## Party Traits (who is in the party; combat only)
Separate from Bond. Each trait's condition is asked of two groups, the player included in both:

- **The roster** - every active member, wherever they are - decides what is **eligible**: what the counter offers to
  select (**up to 3 selected**), and what a visit to the counter takes back. Every time the counter is opened, and after
  every roster change made there, each selected trait the roster no longer fits is unselected, silently: a member
  removed, a member who fell, the player cured of vampirism.
- **Those with the player right now** (alive, a player teammate - recruited, not dismissed - and 3D loaded; no
  distance test, so a follower who lags or fights up the road still counts, and one told to wait counts while she
  stays loaded) decide whether a selected trait is
  **active**. Away from the counter nothing is ever unselected: a selected trait goes inactive while those present do
  not fit it (a follower dismissed, a member far away) and active again by itself when they do, with a HUD line each
  way ("Affinity inactive: ..." / "Affinity active: ..."). An inactive trait keeps its slot. Two things soften this: a trait
  earned from the party's own record (In Their Memory, Nobody Left Behind) does not depend on who is present and is
  active whenever the roster fits it; and a trait goes inactive only after its condition has failed for 20 seconds, so
  followers catching up after a door or a fast travel do not flick it off and on. The words are fixed: selected / unselected for the player's pick, active / inactive for its effect.

So the roster is the gate, and presence only switches what the roster allows between active and inactive. A member's facts (race, sex,
vampire, werewolf, the factions the traits look at) are read from the actor whenever it can be reached and the last
reading is kept in the co-save, so a member who is not loaded still counts on the roster; a roster with a member who
has never been read unselects nothing.

Nothing is selected by default (Beast Buds alone takes over the slot of Creatures of the Night): a discovery - the first
time the roster fits a trait - shows a HUD message and a Guild record, a red count on the Party tab and the Affinity
sub-tab until the Affinity page is viewed, a "New" tag on its card, and the Party page says when a slot is open. Values live in guild.json.

| Trait | Unlocks when | Effect |
|---|---|---|
| Creatures of the Night | at least 1 vampire or werewolf present | + damage at night (20:00-06:00; the MGEF's own GetCurrentTime condition) |
| Diversity Adversity | 4+ present, all different races (vampire races count as their base race) | + damage against Thalmor and Stormcloaks, always (whatever side the player took) |
| Battle Brothers | 3+ present, all male | + 5% damage |
| Shield Sisters | 3+ present, all female | + 5% physical damage resistance |
| Beast Buds | at least 1 vampire AND 1 werewolf present | a larger + damage at night; **replaces** Creatures of the Night (which is not offered while Beast Buds is) |
| Sworn to Carry | at least 1 housecarl present | + 25 carry weight |
| Kindred | 3+ present, all the same race (vampire races count as their base race) | + 5% magic resistance |
| Two Against the World | exactly 2 present: the player and one companion | + 5% damage, + 10% healing (health restored by healing spells and potions) |
| Coin-Bound | every companion present is a sellsword (PotentialHireling / CurrentHireling) | + 10% gold from the Adventurers Guild (dungeon-report gold; trophies pay Merit only; applied by the DLL on payout) |
| Nobody Left Behind | the party has 30+ days in the field and has never lost a member | + 10% healing, + 20 armor |
| In Their Memory | the party has lost a member (it replaces Nobody Left Behind for good) | + 5% damage |
| Study Group | 2+ present from the College of Winterhold (the player counts) | + 25% magicka regeneration |
| Unlikely Allies | a vampire and a Dawnguard member present (either may be the player) | + 10% damage against the undead and vampires |
| Honeymoon Adventure | your spouse (PlayerMarriedFaction) is present | + 30 health |

The Affinity sub-tab shows 8 traits per page (discovered first); traits 9+ live at FormIDs 0xC00+ (EspGen header).

Conditions are deliberately **stable facts** (race, sex, vampire/werewolf, factions, the party's own record), never things that
swing from moment to moment such as current skill levels.

Engine: the DLL re-evaluates the make-up on party changes, follow/unfollow and cell changes and sets one global per
trait; a single "Party Blessing" ability holds one MGEF per trait conditioned on its global and on distance to the
player (no polling). Faction targets use perk entry conditions. Open: detecting latent NPC werewolves (Aela, Farkas,
Vilkas are not flagged like vampires).

## Party Analysis (sub-tab)
- **Two radars side by side, 7 core strengths each** (every one of the 18 skill trees on exactly one axis):
  - Melee: One-Handed, Two-Handed (+ Unarmed with a skill mod). Ranged: Archery. Casting: Destruction,
    Conjuration. Defense: Heavy Armor, Light Armor, Block. Support: Restoration, Illusion, Alteration (+ Bard
    with a skill mod). Crafting: Smithing, Alchemy, Enchanting. Guile: Sneak, Lockpicking, Pickpocket, Speech.
  - **A member's score** on an axis = their **best** skill on it, 0-100. Nobody specialises in heavy and light armour
    at once, and a pure destruction mage is a strong caster however little conjuration they know, so the best skill is
    fairer than an average and axes with 1 or 4 skills stay comparable.
  - **Left, Members:** one ring per member (the player included, up to 5), showing how each contributes.
  - **Right, Party:** two rings: **strongest** (the best member's score on each axis) and **average** (the mean over
    the members shown).
  - **Toggle "Present Only"** (off by default), with a helper line beneath it ("Showing all members" / "Showing only
    present members"): both radars show only the player and the members present (as the blessing counts them).
  - Raw skill levels only: no equipment or other bonuses. Members not loaded use their skills as last seen (co-save).
- **Party stats**, counted from the Bond-tracking build on: days in the field together, kills together (dragons and
  bosses too), dungeons cleared and missives completed together, former members and the fallen.

## Counter: the Party tab
Sub-tabs, paged (VR: never scroll): Party | Recruit | Affinity | Analysis | History (fixed-width sub-tabs; controls for each view sit to their right).
- **Party:** banner (name, Bond pips + tier, founded, the live blessing), a one-line "Affinity: ✓ ..." summary,
  active members (guild rank, following or away) with Remove; Rename and Disband (red warning) buttons. With no party:
  the name (VR/SteamVR: a button that opens the headset keyboard through the DLL) and the founding members to pick.
- **Recruit:** eligible followers with Add (a returning companion shows the Bond they keep).
- **Affinity** (the Party Traits): all traits as a 2 x 4 grid. Discovered: effect, why the roster fits it ("Just you and Jenassa")
  or what it needs, and Select / Unselect (at most 3 selected; Select only for a trait the roster fits). A selected trait
  reads "selected · active" or "selected · inactive" (dashed border, "Inactive until they are at your side · ..."); the
  header counts both ("2 of 3 selected · 1 active"). Undiscovered: the name only, as a hint; condition and effect "???".
- **Analysis:** the two radars and the party's record.
- **History:** every former and fallen member of every party (✝ and where they fell), newest first, paged; each row
  names its party (and whether it was disbanded).

## SkyrimNet (built)
- **Renown** (guild.json `party.renown`): points from the party's record (3 per dungeon and missive, 5 per elite (boss or huge foe),
  0.2 per kill, 1 per day together). At 15 the party is "talked about in the holds": every NPC's view of the player then
  names the party, its members, its deeds and its fallen. At 60 it is "famous across Skyrim". Guild reps (the liaison
  block, with the full record) and the party's own members always know it.
- Decorator `ag_party(actor)`: the player's party (name, membersText, fallenText, bondTier, days, dungeons, missives,
  greatBeasts, renown) plus the actor's own tie (member / former, which party, their Bond with the player).
- Prompt 0026: the player's line (renown >= 1), a member's line (sworn member, Bond), a former member's line, and the
  reps' line. Guidelines 0511: one bullet on parties and Bond.
- Lore pack entries: ag_parties, ag_party_bond, ag_party_fame, ag_party_fallen.
- Persistent events: founded, member joined / left / fell (with the place), Bond tier reached, renamed, disbanded.
- Still to do: SkyrimNet actions (name the party at a rep; a follower joining or leaving when asked).

## Build order
1. Co-save ledger + lifecycle + DevBench natives (done). 2. Party tab (done). 3. Bond tracking + party stats +
Analysis sub-tab (done; tuning in guild.json party.bond). 4. Bond blessing + Party Traits (done; traits.json,
AG_PartyBlessing 0x8D0 with 22 effects, globals 0x8D1-0x8DA). 5. SkyrimNet.

## Open risks
- VR text entry: does focusing a PrismaUI `<input>` raise the SteamVR keyboard? Spike early; fallback is the DLL
  calling OpenVR `IVROverlay::ShowKeyboard` itself.
