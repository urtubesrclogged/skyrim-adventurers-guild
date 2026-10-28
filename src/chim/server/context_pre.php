<?php
// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild
//
// HerikaServer hook, before the system prompt is built: what the speaker knows of the Adventurers Guild
// (lib/ag_chim.php, agChimInjectPrompt). Nothing when the game has sent no recent state, or CHIM lacks the API.

require_once __DIR__ . DIRECTORY_SEPARATOR . 'lib' . DIRECTORY_SEPARATOR . 'ag_chim.php';

try {
    agChimInjectPrompt();
} catch (Throwable $e) {
    if (class_exists('Logger')) {
        Logger::warn('[adventurersguild] prompt not added: ' . $e->getMessage());
    }
}
