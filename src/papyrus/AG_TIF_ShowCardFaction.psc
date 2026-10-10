; Adventurers Guild - Copyright (C) 2026 urtubesrclogged
; SPDX-License-Identifier: GPL-3.0-or-later (with the additional permissions in EXCEPTIONS.md). NO WARRANTY.
; Source and license: https://github.com/urtubesrclogged/skyrim-adventurers-guild

;BEGIN FRAGMENT CODE - Do not edit anything between this and the end comment
;NEXT FRAGMENT INDEX 1
Scriptname AG_TIF_ShowCardFaction Extends TopicInfo Hidden

;BEGIN FRAGMENT Fragment_0
Function Fragment_0(ObjectReference akSpeakerRef)
Actor akSpeaker = akSpeakerRef as Actor
;BEGIN CODE
Game.GetPlayer().AddToFaction(TargetFaction)
;END CODE
EndFunction
;END FRAGMENT

;END FRAGMENT CODE - Do not edit anything between this and the begin comment

; Show Guild Card: the line that accepts the player puts them in the faction vanilla's own acceptance does
; (the Orc strongholds: OrcFriendFaction, as QF_FavorOrcsIntro and QF_RelationshipOrcs do).
Faction Property TargetFaction Auto
