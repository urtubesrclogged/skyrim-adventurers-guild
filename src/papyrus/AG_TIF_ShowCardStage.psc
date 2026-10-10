; Adventurers Guild - Copyright (C) 2026 urtubesrclogged
; SPDX-License-Identifier: GPL-3.0-or-later (with the additional permissions in EXCEPTIONS.md). NO WARRANTY.
; Source and license: https://github.com/urtubesrclogged/skyrim-adventurers-guild

;BEGIN FRAGMENT CODE - Do not edit anything between this and the end comment
;NEXT FRAGMENT INDEX 1
Scriptname AG_TIF_ShowCardStage Extends TopicInfo Hidden

;BEGIN FRAGMENT Fragment_0
Function Fragment_0(ObjectReference akSpeakerRef)
Actor akSpeaker = akSpeakerRef as Actor
;BEGIN CODE
TargetQuest.SetStage(Stage)
;END CODE
EndFunction
;END FRAGMENT

;END FRAGMENT CODE - Do not edit anything between this and the begin comment

; Show Guild Card: the line that lets the player through sets the stage vanilla's own Persuade success sets
; (the Treasury House: MS01 stage 50, as TIF__000D66BA does).
Quest Property TargetQuest Auto
Int Property Stage Auto
