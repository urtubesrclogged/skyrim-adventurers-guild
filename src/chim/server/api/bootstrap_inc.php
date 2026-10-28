<?php
// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild
//
// Shared start of the API endpoints (not a hook name): HerikaServer's runtime and database, then our code.
error_reporting(E_ALL);
ini_set('display_errors', '0');

$enginePath = dirname(__DIR__, 3) . DIRECTORY_SEPARATOR;
require_once $enginePath . 'lib' . DIRECTORY_SEPARATOR . 'runtime_bootstrap.php';
chimRuntimeBootstrap($enginePath, [
    'load_general_settings' => false,
    'load_stt_connector' => false,
    'load_itt_connector' => false,
    'load_player_name' => false,
    'load_narrator' => false,
]);
$GLOBALS['db'] = $GLOBALS['db'] ?? new sql();

require_once dirname(__DIR__) . DIRECTORY_SEPARATOR . 'lib' . DIRECTORY_SEPARATOR . 'ag_chim.php';
