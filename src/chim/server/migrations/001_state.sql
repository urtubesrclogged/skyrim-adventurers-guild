-- Adventurers Guild for CHIM: the last state report from the game (and anything else keyed later). Not part of CHIM's
-- playthrough saves: it is the game's current state, sent again after every load.
CREATE SCHEMA IF NOT EXISTS plugins;

CREATE TABLE IF NOT EXISTS plugins.ag_chim (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
