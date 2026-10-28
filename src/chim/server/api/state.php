<?php
// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild
//
// POST from AdventurersGuild.dll whenever the Guild's state changes (and once after every load, with "hello": true,
// which also brings CHIM's Oghma up to date for this game). The body is the state as JSON; the answer is one line of
// text the DLL writes to its log the first time.
require_once __DIR__ . DIRECTORY_SEPARATOR . 'bootstrap_inc.php';

header('Content-Type: text/plain; charset=utf-8');
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    http_response_code(405);
    echo 'POST only';
    return;
}
$body = (string)file_get_contents('php://input', false, null, 0, 1048576);
$state = json_decode($body, true, 32, JSON_INVALID_UTF8_SUBSTITUTE);
if (!is_array($state) || (int)($state['v'] ?? 0) !== 1) {
    http_response_code(400);
    echo 'not an Adventurers Guild state report';
    return;
}
$hello = !empty($state['hello']);
unset($state['hello']);
if (!agChimSet('state', json_encode($state, JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE))) {
    http_response_code(500);
    echo 'state not stored (has the plugin\'s migration run?)';
    return;
}
$answer = 'Adventurers Guild ' . AG_CHIM_VERSION . ' on the CHIM server: state stored';
if ($hello) {
    $answer .= '; ' . agChimSyncOghma(is_array($state['plugins'] ?? null) ? $state['plugins'] : []);
}
echo $answer;
