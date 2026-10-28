<?php
// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild
//
// Adventurers Guild for CHIM (1.6.0): what the people of Skyrim know of the Guild, in CHIM. Shared code of the server
// plugin; never a hook name (HerikaServer loads hook file names from every folder of ext/).
//
// AdventurersGuild.dll POSTs the Guild's state to api/state.php (the player's record and party, and the people near the
// player: their guild rank, bio line, party tie and the factions the lore depends on). From it:
//   - Oghma: the knowledge pack's general entries (and those of the other mods that are loaded), seeded into CHIM's own
//     Oghma, which brings one in when the talk names its topic;
//   - context_pre.php: the speaker's own standing, a counter keeper's view of the player's record, the lore only some
//     factions have, and a few rules when the talk is about the Guild.
// Memory events need nothing here: the DLL logs them as "info_guild" events, which CHIM keeps for the people nearby.

const AG_CHIM_VERSION = '@AG_VERSION@';     // filled in by src/chim/build_dwpkg.py
const AG_CHIM_TAG = 'adventurersguild';     // our Oghma rows (tags), so we never touch anyone else's
const AG_CHIM_FRESH = 600;                  // seconds a state report stays usable (the DLL sends one on every change)

function agChimDb()
{
    return $GLOBALS['db'] ?? null;
}

// Our one table (migrations/001_state.sql): key/value, the last state report and how old it is
function agChimGet(string $key): ?array
{
    $db = agChimDb();
    if (!$db) {
        return null;
    }
    try {
        $row = $db->fetchOne('SELECT value, EXTRACT(EPOCH FROM (NOW() - updated_at))::bigint AS age FROM plugins.ag_chim WHERE key = $1', [$key]);
    } catch (Throwable $e) {
        return null;
    }
    return $row ? ['value' => (string)$row['value'], 'age' => (int)$row['age']] : null;  // age in the database's own clock
}

function agChimSet(string $key, string $value): bool
{
    $db = agChimDb();
    if (!$db) {
        return false;
    }
    try {
        $db->fetchOne('INSERT INTO plugins.ag_chim (key, value, updated_at) VALUES ($1, $2, NOW())
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW() RETURNING key', [$key, $value]);
        return true;
    } catch (Throwable $e) {
        return false;
    }
}

function agChimLore(): array
{
    static $lore = null;
    if ($lore === null) {
        $lore = json_decode((string)@file_get_contents(dirname(__DIR__) . '/data/lore.json'), true);
        if (!is_array($lore)) {
            $lore = [];
        }
    }
    return $lore;
}

// The last state report, if it is recent; one read per request
function agChimState(): ?array
{
    if (array_key_exists('AG_CHIM_STATE', $GLOBALS)) {
        return $GLOBALS['AG_CHIM_STATE'];
    }
    $GLOBALS['AG_CHIM_STATE'] = null;
    $row = agChimGet('state');
    if ($row && $row['age'] <= AG_CHIM_FRESH) {
        $state = json_decode($row['value'], true, 32, JSON_INVALID_UTF8_SUBSTITUTE);
        if (is_array($state)) {
            $GLOBALS['AG_CHIM_STATE'] = $state;
        }
    }
    return $GLOBALS['AG_CHIM_STATE'];
}

// ---------------------------------------------------------------------------------------------------------------------
// Oghma
// ---------------------------------------------------------------------------------------------------------------------

// Makes CHIM's Oghma hold exactly our entries for this game: the general ones and those of the other mods it has
// loaded. Only rows tagged as ours are written or removed; a topic someone else already owns is left alone. Oghma is
// kept per playthrough, so this runs on the first report after every load. Returns a one-line summary.
function agChimSyncOghma(array $plugins): string
{
    $db = agChimDb();
    if (!$db) {
        return 'no database';
    }
    $loaded = array_flip(array_map('strtolower', array_map('strval', $plugins)));
    $want = [];
    foreach (agChimLore()['oghma'] ?? [] as $e) {
        $needs = (string)($e['plugin'] ?? '');
        if ($needs === '' || isset($loaded[strtolower($needs)])) {
            $want[strtolower((string)$e['topic'])] = $e;
        }
    }
    $written = 0;
    $taken = 0;
    try {
        $ours = [];
        foreach ($db->fetchAll("SELECT topic FROM oghma WHERE tags = '" . AG_CHIM_TAG . "'") as $row) {
            $ours[(string)$row['topic']] = true;
        }
        foreach ($want as $topic => $e) {
            $row = $db->fetchOne('INSERT INTO oghma (topic, aliases, topic_desc, knowledge_class, topic_desc_basic, knowledge_class_basic, tags, category)
                VALUES ($1, $2, $3, \'\', \'\', \'\', $4, $5)
                ON CONFLICT (topic) DO UPDATE SET aliases = EXCLUDED.aliases, topic_desc = EXCLUDED.topic_desc
                WHERE oghma.tags = $4 AND (oghma.aliases IS DISTINCT FROM EXCLUDED.aliases OR oghma.topic_desc IS DISTINCT FROM EXCLUDED.topic_desc)
                RETURNING topic', [$topic, (string)($e['aliases'] ?? ''), (string)$e['text'], AG_CHIM_TAG, 'Adventurers Guild']);
            if ($row) {
                $db->fetchOne("UPDATE oghma SET native_vector =
                      setweight(to_tsvector('simple', coalesce(topic, '')), 'A')
                    || setweight(to_tsvector('simple', coalesce(aliases, '')), 'A')
                    || setweight(to_tsvector(coalesce(topic_desc, '')), 'B')
                    || setweight(to_tsvector(coalesce(topic_desc_basic, '')), 'C')
                    WHERE topic = $1 RETURNING topic", [$topic]);
                ++$written;
            } elseif (!isset($ours[$topic])) {
                $owner = $db->fetchOne('SELECT tags FROM oghma WHERE topic = $1', [$topic]);
                if ($owner && (string)$owner['tags'] !== AG_CHIM_TAG) {
                    ++$taken;
                }
            }
            unset($ours[$topic]);
        }
        foreach (array_keys($ours) as $topic) {  // ours, no longer wanted (a mod removed, an entry retired)
            $db->fetchOne('DELETE FROM oghma WHERE topic = $1 AND tags = $2 RETURNING topic', [$topic, AG_CHIM_TAG]);
        }
        $removed = count($ours);
    } catch (Throwable $e) {
        return 'Oghma not updated: ' . $e->getMessage();
    }
    return sprintf('Oghma: %d entries, %d written, %d removed%s', count($want), $written, $removed,
        $taken ? ", $taken topic(s) already used by another entry and left alone" : '');
}

// ---------------------------------------------------------------------------------------------------------------------
// The prompt
// ---------------------------------------------------------------------------------------------------------------------

// Is the talk about the Guild? The player's line (or the event being answered) and the topics Oghma picked for it.
function agChimTalkIsGuild(): bool
{
    $text = '';
    $request = $GLOBALS['gameRequest'] ?? null;
    if (is_array($request) && is_string($request[3] ?? null)) {
        $text = $request[3];
    }
    $text .= ' ' . (is_string($GLOBALS['OGHMA_HINT'] ?? null) ? $GLOBALS['OGHMA_HINT'] : '');
    return (bool)preg_match('/\b(adventur\w*|guild|missives?|bount(y|ies)|merit|guild card|promot\w*|\b[EDCBAS]-rank)\b/i', $text);
}

function agChimLetter(array $state, int $standing): string
{
    $letters = $state['letters'] ?? ['E', 'D', 'C', 'B', 'A', 'S'];
    return (string)($letters[$standing % 10] ?? '?');
}

// One line about a person's standing, as SkyrimNet's character_bio/0026_guild_rank.prompt puts it
function agChimStandingLine(array $state, array $who): string
{
    $s = (int)($who['standing'] ?? -1);
    if ($s >= 0 && $s <= 5) {
        return 'Adventurers Guild: ' . agChimLetter($state, $s) . '-rank adventurer (background; mention only when it is relevant)';
    }
    if ($s >= 10 && $s <= 15) {
        return 'Adventurers Guild: retired ' . agChimLetter($state, $s) . '-rank adventurer, set aside under the Guild\'s Neutrality Oath'
            . ' when they took up another service; still quietly proud of the old rank (background; mention only when it is relevant)';
    }
    return '';
}

// What a counter keeper (the Guild's liaison) knows of the player's record
function agChimRecordLines(array $state, string $player): array
{
    $led = $state['ledger'] ?? [];
    if (empty($led['registered'])) {
        return ["$player is not registered with the Adventurers Guild; registration is done at the Guild's counter for a fee of exactly "
            . (int)($led['registrationFee'] ?? 0) . ' gold (never quote any other amount)'];
    }
    $line = "The Guild's record of $player: " . ($led['rank'] ?? '?') . '-rank adventurer, ' . (int)($led['reputation'] ?? 0)
        . ' Reputation, ' . (int)($led['merit'] ?? 0) . ' Merit to spend';
    $next = $led['next'] ?? null;
    if (!empty($led['promotionReady']) && is_array($next)) {
        $line .= '; eligible for promotion to ' . ($next['rank'] ?? '?') . '-rank and only needs to ask at the counter and pay the '
            . (int)($led['promotionFee'] ?? 0) . ' gold promotion fee';
    } elseif (is_array($next)) {
        $line .= '; ' . ($next['rank'] ?? '?') . '-rank needs ' . (int)($next['reputationShort'] ?? 0) . ' more Reputation'
            . ((int)($next['levelShort'] ?? 0) > 0 ? ' and more seasoning in the field' : '');
    } else {
        $line .= '; the highest rank the Guild grants';
    }
    $lines = [$line];
    $appraisal = (string)($led['appraisal'] ?? 'none');
    $lines[] = "$player's Appraisal: " . ($appraisal === 'none' ? 'not learned (they cannot read ranks at all; the first level is sold at the counter for Merit)' : "level $appraisal of III");
    $party = $state['party'] ?? [];
    if (!empty($party['party'])) {
        $lines[] = "$player leads the adventuring party " . ($party['name'] ?? '') . ', registered with the Adventurers Guild: ' . ($party['membersText'] ?? '')
            . '; their bond is ' . ($party['bondTier'] ?? '') . ', ' . (int)($party['days'] ?? 0) . ' days on the road together, '
            . (int)($party['dungeons'] ?? 0) . ' dungeons and ' . (int)($party['missives'] ?? 0) . ' missives; the party is ' . ($party['renownWord'] ?? '')
            . (($party['fallenText'] ?? '') !== '' ? '; lost: ' . $party['fallenText'] : '');
    }
    if (isset($led['hasCard']) && !$led['hasCard']) {
        $lines[] = "$player no longer carries their guild card: a replacement at the counter costs exactly " . (int)($led['cardFee'] ?? 0) . ' gold (never quote any other amount)';
    }
    $waiting = $led['reportsWaiting'] ?? [];
    if ((int)($waiting['count'] ?? 0) > 0) {
        $lines[] = "$player has " . (int)$waiting['count'] . ' finished job(s) not yet reported to the Guild, worth ' . (int)($waiting['gold'] ?? 0) . ' gold, '
            . (int)($waiting['merit'] ?? 0) . ' Merit and ' . (int)($waiting['reputation'] ?? 0) . ' Reputation when handed in at a counter';
    }
    $bounty = $led['bounty'] ?? [];
    if ((int)($bounty['total'] ?? 0) > 0) {
        $lines[] = "$player has a price on their head (" . ($bounty['where'] ?? '') . "); while it stands the Guild hears no case for their promotion."
            . ' The counter can pay off all of it for ' . (int)($bounty['payTotal'] ?? 0) . " gold, the Guild's fee included, when $player asks";
    }
    if ((int)($led['trophiesCarried']['kinds'] ?? 0) > 0) {
        $lines[] = "$player carries monster trophies the Guild would buy, worth about " . (int)$led['trophiesCarried']['merit'] . ' Merit';
    }
    return $lines;
}

// The knowledge pack's entries for some factions only, for a speaker in one of them; at most two, the most important
function agChimFactionLore(array $factions): array
{
    if (!$factions) {
        return [];
    }
    $have = array_flip(array_map('strval', $factions));
    $hits = [];
    foreach (agChimLore()['factions'] ?? [] as $e) {
        foreach ($e['factions'] ?? [] as $f) {
            if (isset($have[(string)$f])) {
                $hits[] = $e;
                break;
            }
        }
    }
    usort($hits, static fn($a, $b) => ($b['importance'] ?? 0) <=> ($a['importance'] ?? 0));
    return array_map(static fn($e) => (string)$e['text'], array_slice($hits, 0, 2));
}

// The people CHIM says are here, with what we know of them
function agChimNearby(array $state): array
{
    $byName = [];
    foreach ($state['near'] ?? [] as $who) {
        if (is_array($who) && ($who['name'] ?? '') !== '') {
            $byName[(string)$who['name']] = $who;
        }
    }
    return $byName;
}

function agChimInjectPrompt(): void
{
    if (!function_exists('chimRegisterPromptInjection')) {
        return;
    }
    $state = agChimState();
    if (!$state) {
        return;
    }
    $speaker = (string)($GLOBALS['HERIKA_NAME'] ?? '');
    $player = (string)($GLOBALS['PLAYER_NAME'] ?? ($state['player'] ?? 'the player'));
    $near = agChimNearby($state);
    $me = $near[$speaker] ?? null;
    $guildTalk = agChimTalkIsGuild();

    // the speaker: their own standing, bio line and party, as SkyrimNet gives them
    $own = [];
    if ($me) {
        if (($line = agChimStandingLine($state, $me)) !== '') {
            $own[] = $line;
        }
        if (($me['note'] ?? '') !== '') {
            $own[] = (string)$me['note'];
        }
        $tie = (int)($me['tie'] ?? -1);
        $party = $state['party'] ?? [];
        if ($tie >= 0 && $tie <= 4 && !empty($party['party'])) {
            $own[] = "A sworn member of $player's adventuring party, " . ($party['name'] ?? '') . ' (its members: ' . ($party['membersText'] ?? '')
                . "); their bond with $player is " . ($party['bondWords'][$tie] ?? '') . '. Proud of the party and its name (background; mention only when it is relevant)';
        } elseif ($tie >= 10 && isset($party['parties'][$tie - 10])) {
            $own[] = "Once travelled with $player in the adventuring party " . $party['parties'][$tie - 10];
        }
        if (in_array('AG_GuildLiaisonFaction', $me['factions'] ?? [], true)) {
            $own[] = "Keeps this hold's Adventurers Guild counter as its licensed liaison: registration, trophies, reports, the Guild's services and cases for promotion";
            $own[] = "Knows the Guild's record of $player below, but raises it only when $player brings Guild business or asks about it; never brings it up unprompted while serving drinks or chatting";
            $own = array_merge($own, agChimRecordLines($state, $player));
        }
        if ($guildTalk) {
            $own = array_merge($own, agChimFactionLore($me['factions'] ?? []));
        }
    }
    if ($own) {
        chimRegisterPromptInjection('character_bottom', 'adventurersguild.standing', "\n- " . implode("\n- ", $own), 120);
    }

    // everyone here: who holds a guild rank (the player's is common knowledge once registered); and the rules, when
    // someone here holds one or the talk is about the Guild
    $ranks = [];
    $led = $state['ledger'] ?? [];
    if (!empty($led['registered'])) {
        $ranks[] = "$player (" . ($led['rank'] ?? '?') . '-rank)';
    }
    foreach ($near as $name => $who) {
        $s = (int)($who['standing'] ?? -1);
        if ($name !== $speaker && $s >= 0 && $s <= 5 && count($ranks) < 10) {
            $ranks[] = "$name (" . agChimLetter($state, $s) . '-rank)';
        }
    }
    $mine = $me && (int)($me['standing'] ?? -1) >= 0 && (int)($me['standing'] ?? -1) <= 15;
    if ($guildTalk || $mine || count($ranks) > (empty($led['registered']) ? 0 : 1)) {
        $text = (string)(agChimLore()['guidelines'] ?? '');
        if ($ranks) {
            $text .= "\nAdventurers Guild ranks of those here: " . implode(', ', $ranks) . '.';
        }
        if (trim($text) !== '') {
            chimRegisterPromptInjection('prompt_bottom', 'adventurersguild.rules', "\n\n<adventurers_guild>\n" . trim($text) . "\n</adventurers_guild>", 120);
        }
    }
}
