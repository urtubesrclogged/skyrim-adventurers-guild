; Adventurers Guild - Copyright (C) 2026 urtubesrclogged
; SPDX-License-Identifier: GPL-3.0-or-later (with the additional permissions in EXCEPTIONS.md). NO WARRANTY.
; Source and license: https://github.com/urtubesrclogged/skyrim-adventurers-guild

ScriptName AG_Native Native Hidden
{Native bridge to AdventurersGuild.dll (SKSE). Rank 0..5 = E..S, -1 = none / not registered.
Guild rank = adventurers only (the player's is earned at the Guild). Threat rank = anything you fight.}

; ---- guild / ranks ----
Int Function GetGuildRank() Global Native                  ; player's earned guild rank, -1 if not registered
Bool Function IsRegistered() Global Native
Int Function GetMerit() Global Native                      ; spendable
Int Function GetReputation() Global Native                 ; guild standing (drives promotion; never spent)
Bool Function IsPromotionReady() Global Native
Int Function GetActorGuildRank(Actor akActor) Global Native     ; -1 if not an adventurer (or a hidden one)
String Function GetActorGuildStatus(Actor akActor) Global Native ; "member" / "retired" / "none"
Int Function GetThreatRank(Actor akActor) Global Native
String Function GetRankLetter(Int aiRank) Global Native
Int Function GetRankFromLevel(Int aiLevel) Global Native
Bool Function IsGuildLiaison(Actor akActor) Global Native  ; innkeeper and not a story exception (e.g. Delphine)
String Function GetPlayerLedger() Global Native            ; the player's ledger page as JSON (SkyrimNet ag_player)
; SkyrimNet actions (AG_SkyrimNetActions): a Guild rep doing guild business in an AI conversation. Same fees and
; checks as the dialogue; refused for anyone but one of the nine reps. Return a short status for the log.
String Function ActionOpenCounter(Actor akLiaison) Global Native
String Function ActionRegister(Actor akLiaison) Global Native
String Function ActionPromote(Actor akLiaison) Global Native
String Function ActionReports(Actor akLiaison) Global Native
; an NPC signing themselves up (AG_JoinAdventurersGuild): refused for members, retired adventurers, children, Guild reps
String Function ActionJoinGuild(Actor akActor) Global Native
String Function GetJoinStatus(Actor akActor) Global Native
; SkyrimNet ag_party(actor): the player's party (name, members, Bond, renown) and this actor's own tie to a party (JSON)
String Function GetPartyInfo(Actor akActor) Global Native
String Function GetPartyName() Global Native ; the player's active party, "" without one ; "can_join" or member/retired/guard/child/guild_rep/invalid
Function ReloadConfig() Global Native                      ; re-read guild.json, adventurers + ini

; uninstall (MCM "Debug" page)
Bool Function IsPreparedForUninstall() Global Native
String Function PrepareUninstall() Global Native           ; take back every ability/perk/item of ours; returns the report
String Function CancelUninstall() Global Native
String Function UninstallText(Int aiWhich) Global Native   ; 0 confirm, 1 already prepared, 2 nothing to cancel

; ---- MCM ----
Bool Function GetShowGuildRank() Global Native
Function SetShowGuildRank(Bool abOn) Global Native
Bool Function GetShowThreatRank() Global Native
Function SetShowThreatRank(Bool abOn) Global Native
Bool Function GetShowLevelSuffix() Global Native
Function SetShowLevelSuffix(Bool abOn) Global Native
String Function CardKeyConflictText(String asOther) Global Native ; "already used by ...: use it anyway?" in the game's language
Function ToggleGuildCard() Global Native                     ; opens the carried Guild Card in the world, or closes it
Function SetCardHotkey(Int aiKey) Global Native              ; key that opens the Guild Card (SkyUI key code; 0 or less = none)
Bool Function GetDetailedLog() Global Native                ; the detailed support log (each kill, each counter action)
Function SetDetailedLog(Bool abOn) Global Native
Bool Function GetShowRankUpToast() Global Native
Function SetShowRankUpToast(Bool abOn) Global Native
Float Function GetToastSeconds() Global Native               ; seconds a guild notice stays fully visible
Function SetToastSeconds(Float afSeconds) Global Native
Float Function GetMinorToastSeconds() Global Native          ; notices confirming something just done in a menu
Function SetMinorToastSeconds(Float afSeconds) Global Native

; ---- developer / testing ----
; For testing and for modders: they change the player's Guild standing or simulate events (cheat-level), and nothing
; in this mod calls them. Used with DevBench (Nexus SE 181326) or from other scripts. Players never see them.
String Function DebugDump() Global Native
; parties (DevBench): the ledger, and the lifecycle without the counter
String Function DebugPartyDump() Global Native
String Function DebugPartyFound(String asName, Actor akFounder) Global Native
String Function DebugPartyAdd(Actor akActor) Global Native
String Function DebugPartyRemove(Actor akActor) Global Native
String Function DebugPartyDisband() Global Native
Function DebugPartyBond(Actor akActor, Float afAmount) Global Native
String Function DebugDungeon() Global Native                ; current location / zone / threat rank / visited+reported
String Function DebugClearDungeon() Global Native           ; run the clear path for the current dungeon
Function DebugRegister() Global Native
Function DebugPromote() Global Native
Function DebugSetRank(Int aiRank) Global Native            ; -1 = unregister
Function DebugAddMerit(Int aiAmount) Global Native  ; Merit and Reputation
Function DebugAddRep(Int aiAmount) Global Native    ; Reputation only (as kills pay)
String Function DebugThreat() Global Native         ; threat-rank breakdown of actors near the player (also logged)
String Function DebugKill(Int aiFormId) Global Native  ; kill credit as if the player killed that actor
Function DebugReset() Global Native
Function DebugBoard() Global Native                        ; as if walking up to a Missives board
Function DebugCompleteMissive(String asFormId) Global Native
String Function DebugAdventurer(Actor akActor) Global Native
Function OpenCounter() Global Native                       ; the guild counter window (registered players)
String Function DebugLevelLabel(Int aiMode, Float afMargin) Global Native ; level-label fit: 0 auto, 1 shift, 2 shrink (-1 keeps); returns the measurements
String Function DebugLevelDump(Float afAvail) Global Native  ; the level strip's clips and bounds (call twice); afAvail > 0 forces the shrink room
Function DebugToast() Global Native                        ; shows a test notice (for checking the notice panel in VR)
Function DebugSetAppraisal(Int aiTier) Global Native       ; 0 = none, 1..3
Int Function GetAppraisalLevel() Global Native
Function DebugAddReport(String asTitle, Int aiGold, Int aiMerit) Global Native
Function SetNameMode(Int aiMode) Global Native
Int Function GetNameMode() Global Native
Function NameSiteAllow(Int aiRva, Bool abOn) Global Native
Function NameSiteReset() Global Native
String[] Function GetNameSites() Global Native
