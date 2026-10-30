<?php
// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild
//
// HerikaServer hook, while the actions for this line are gathered: the Guild's CHIM actions (CHIM/adventurersguild_actions.csv)
// only for the speaker they fit, as SkyrimNet's eligibility rules do (lib/ag_chim.php, agChimFilterActions).

require_once __DIR__ . DIRECTORY_SEPARATOR . 'lib' . DIRECTORY_SEPARATOR . 'ag_chim.php';

try {
    agChimFilterActions();
} catch (Throwable $e) {
    if (class_exists('Logger')) {
        Logger::warn('[adventurersguild] actions not filtered: ' . $e->getMessage());
    }
}
