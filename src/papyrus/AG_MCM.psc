; Adventurers Guild - Copyright (C) 2026 urtubesrclogged
; SPDX-License-Identifier: GPL-3.0-or-later (with the additional permissions in EXCEPTIONS.md). NO WARRANTY.
; Source and license: https://github.com/urtubesrclogged/skyrim-adventurers-guild

ScriptName AG_MCM Extends SKI_ConfigBase
{The Adventurers Guild MCM, written on SkyUI's own API (SkyUI 5 / SkyUI VR) - no MCM Helper. MCM Helper 1.6+ needs
SkyUI 6, which has no VR version, and every MCM Helper menu loses its pages there. Settings live in this script
(saved with the game) and are pushed into AdventurersGuild.dll on every load and every change.}

; ---- settings: the first time this script runs they start from AdventurersGuild.ini ([System], [Debug]), read by
; the DLL; from then on this script holds them and the ini is not consulted for this save ----
Bool bShowLabels = True
; before version 2 the three rank labels had a switch each; kept only so an older save can be carried over
Bool bShowGuild = True
Bool bShowThreat = True
Bool bShowLevel = True
Bool bLabelsCarriedOver = False
Bool bShowToast = True
Float fToastSeconds = 5.0
; Kept as "off" so that a game saved before 1.5.0, where this variable did not exist and so reads False, has the sounds ON.
Bool bToastSoundOff = False
; MCM > Audio > Notification sounds (version 6): 0 the Guild Drums, 1 Skyrim's own, 2 none. A game saved before it existed
; reads 0, the drums; one whose old switch was off is carried over to 2, once (bSoundSetCarried).
Int iSoundSet = 0
; MCM > Audio > Notification volume (1.5.0): -1 quieter, 0 default, 1 louder. A game saved before it existed reads 0.
Int iSoundVolume = 0
Bool bSoundSetCarried = False
; MCM > Audio (version 5), kept as "off" for the same reason: all three are ON in a game saved before they existed
Bool bGreetingsOff = False
Bool bInteractionsOff = False
Bool bRepLinesOff = False
Bool bFollowerCommentsOff = False
Bool bDetailedLog = False
; the key that opens the Guild Card: none until the player picks one (0 or less = none)
Int iCardKey = -1
Bool bRegistrationWasRunning = False
; the level of rank S (60..120). A new game takes the ini's (80); a save from before version 4 keeps 60, the levels
; it always had, and says so once
Int iSLevel = 60
Bool bSLevelSet = False

Int Function GetVersion()
	Return 6
EndFunction

Event OnConfigInit()
	SetPages()
	bShowLabels = AG_Native.GetShowGuildRank() || AG_Native.GetShowThreatRank() || AG_Native.GetShowLevelSuffix()
	bLabelsCarriedOver = True  ; a first install has nothing older to carry over
	bShowToast = AG_Native.GetShowRankUpToast()
	fToastSeconds = AG_Native.GetToastSeconds()
	iSoundSet = AG_Native.GetNoticeSoundSet()
	bSoundSetCarried = True
	iSoundVolume = AG_Native.GetNoticeVolume()
	bDetailedLog = AG_Native.GetDetailedLog()
	iSLevel = AG_Native.GetDefaultSLevel()
	bSLevelSet = True
	Apply()
	RegisterCardAction()
EndEvent

Event OnVersionUpdate(Int a_version)
	SetPages()
	; version 6: the notices' sounds are a choice of three. Sounds that had been turned off stay off. Once only.
	If !bSoundSetCarried
		bSoundSetCarried = True
		If bToastSoundOff
			iSoundSet = 2
		EndIf
		Apply()
	EndIf
	; version 2: one switch for all three labels - on if any of the old three was. Once only: a later version update
	; must not overwrite the player's choice with the old switches again.
	If !bLabelsCarriedOver
		bLabelsCarriedOver = True
		bShowLabels = bShowGuild || bShowThreat || bShowLevel
		Apply()
	EndIf
	; version 4: the level of rank S. A game already under way keeps the levels it had (S at 60). Once only.
	If !bSLevelSet
		bSLevelSet = True
		iSLevel = 60
		Apply()
		AG_Native.NoticeRankLevelsKept()
	EndIf
EndEvent

Event OnGameReload()
	Parent.OnGameReload()
	Apply()
	RegisterCardAction()
EndEvent

; The mod event "AG_OpenGuildCard" opens (or closes) the Guild Card: any mod can send it. With VRIK installed it is
; also offered as a gesture action in VRIK's own MCM, since a VRIK gesture cannot press an arbitrary key.
Function RegisterCardAction()
	RegisterForModEvent("AG_OpenGuildCard", "OnOpenGuildCard")
	If Game.GetModByName("vrik.esp") != 255
		VRIK.VrikAddGestureAction("AG_OpenGuildCard", "Adventurers Guild: Guild Card")
	EndIf
EndFunction

; a plain Function: a mod event is dispatched by function name
Function OnOpenGuildCard(String asEvent, String asArg, Float afArg, Form akSender)
	AG_Native.ToggleGuildCard()
EndFunction

Function SetPages()
	Pages = new String[3]
	Pages[0] = "$AG_MCM_System"
	Pages[1] = "$AG_MCM_Audio"
	Pages[2] = "$AG_MCM_Debug"
EndFunction

; Pushes every setting into the DLL. Cheap and idempotent.
Function Apply()
	AG_Native.SetShowGuildRank(bShowLabels)
	AG_Native.SetShowThreatRank(bShowLabels)
	AG_Native.SetShowLevelSuffix(bShowLabels)
	AG_Native.SetShowRankUpToast(bShowToast)
	AG_Native.SetToastSeconds(fToastSeconds)
	AG_Native.SetNoticeSoundSet(iSoundSet)
	AG_Native.SetNoticeVolume(iSoundVolume)
	AG_Native.SetAudioOption(1, !bGreetingsOff)
	AG_Native.SetAudioOption(2, !bInteractionsOff)
	AG_Native.SetAudioOption(3, !bRepLinesOff)
	AG_Native.SetAudioOption(4, !bFollowerCommentsOff)
	AG_Native.SetDetailedLog(bDetailedLog)
	AG_Native.SetCardHotkey(iCardKey)
	If bSLevelSet
		AG_Native.SetSLevel(iSLevel)
	EndIf
EndFunction

Event OnPageReset(String a_page)
	SetCursorFillMode(TOP_TO_BOTTOM)
	; "" is what SkyUI asks for when the mod is first selected, before a page is clicked: the System page is shown
	; then, so the menu does not open on an empty panel (it looked broken to a player; 1.4.3)
	If a_page == "" || a_page == Pages[0]
		AddHeaderOption("$AG_MCM_System_Labels_Header", OPTION_FLAG_NONE)
		AddToggleOptionST("Labels", "$AG_MCM_System_bShowLabels_Text", bShowLabels, OPTION_FLAG_NONE)
		AddEmptyOption()
		AddHeaderOption("$AG_MCM_System_Notices_Header", OPTION_FLAG_NONE)
		AddToggleOptionST("Toast", "$AG_MCM_System_bShowNotices_Text", bShowToast, OPTION_FLAG_NONE)
		AddSliderOptionST("ToastSeconds", "$AG_MCM_System_fNoticeSeconds_Text", fToastSeconds, "{0} s", OPTION_FLAG_NONE)
		AddEmptyOption()
		AddHeaderOption("$AG_MCM_System_Card_Header", OPTION_FLAG_NONE)
		AddKeyMapOptionST("CardKey", "$AG_MCM_System_iCardKey_Text", CardKeyShown(), OPTION_FLAG_WITH_UNMAP)
		; right-hand column: the level of rank S, and the level each rank then needs (read-only)
		SetCursorPosition(1)
		AddHeaderOption("$AG_MCM_System_Ranks_Header", OPTION_FLAG_NONE)
		AddSliderOptionST("SLevel", "$AG_MCM_System_iSLevel_Text", iSLevel, "{0}", OPTION_FLAG_NONE)
		AddEmptyOption()
		AddHeaderOption("$AG_MCM_System_RankLevels_Header", OPTION_FLAG_NONE)
		AddTextOption("$AG_MCM_System_RankD_Text", AG_Native.GetRankLevel(1), OPTION_FLAG_NONE)
		AddTextOption("$AG_MCM_System_RankC_Text", AG_Native.GetRankLevel(2), OPTION_FLAG_NONE)
		AddTextOption("$AG_MCM_System_RankB_Text", AG_Native.GetRankLevel(3), OPTION_FLAG_NONE)
		AddTextOption("$AG_MCM_System_RankA_Text", AG_Native.GetRankLevel(4), OPTION_FLAG_NONE)
		AddTextOption("$AG_MCM_System_RankS_Text", AG_Native.GetRankLevel(5), OPTION_FLAG_NONE)
	ElseIf a_page == Pages[1]
		AddHeaderOption("$AG_MCM_Audio_Sounds_Header", OPTION_FLAG_NONE)
		AddMenuOptionST("SoundSet", "$AG_MCM_Audio_iSoundSet_Text", SoundSetName(iSoundSet), OPTION_FLAG_NONE)
		AddMenuOptionST("SoundVolume", "$AG_MCM_Audio_iSoundVolume_Text", SoundVolumeNames()[iSoundVolume + 1], OPTION_FLAG_NONE)
		; the game's own sounds chosen, and another mod has replaced some of them: those notices are silent (one line for any number)
		If iSoundSet == 1 && AG_Native.GetSkyrimSoundsReplaced()
			AddTextOptionST("SoundsReplaced", "$AG_MCM_Audio_Replaced_Text", "", OPTION_FLAG_NONE)
		EndIf
		AddEmptyOption()
		AddHeaderOption("$AG_MCM_Audio_Voices_Header", OPTION_FLAG_NONE)
		AddToggleOptionST("Greetings", "$AG_MCM_Audio_bGreetings_Text", !bGreetingsOff, OPTION_FLAG_NONE)
		AddToggleOptionST("FollowerComments", "$AG_MCM_Audio_bFollowerComments_Text", !bFollowerCommentsOff, OPTION_FLAG_NONE)
		AddToggleOptionST("Interactions", "$AG_MCM_Audio_bInteractions_Text", !bInteractionsOff, OPTION_FLAG_NONE)
		AddToggleOptionST("RepLines", "$AG_MCM_Audio_bRepLines_Text", !bRepLinesOff, OPTION_FLAG_NONE)
	ElseIf a_page == Pages[2]
		AddHeaderOption("$AG_MCM_Debug_Log_Header", OPTION_FLAG_NONE)
		AddToggleOptionST("DetailedLog", "$AG_MCM_Debug_bDetailedLog_Text", bDetailedLog, OPTION_FLAG_NONE)
		AddEmptyOption()
		AddHeaderOption("$AG_MCM_Debug_Rank_Header", OPTION_FLAG_NONE)
		AddTextOptionST("RankReset", "$AG_MCM_Debug_RankReset_Text", "", OPTION_FLAG_NONE)
		AddEmptyOption()
		AddHeaderOption("$AG_MCM_Debug_Uninstall_Header", OPTION_FLAG_NONE)
		AddTextOptionST("Prepare", "$AG_MCM_Debug_Prepare_Text", "", OPTION_FLAG_NONE)
		AddTextOptionST("Cancel", "$AG_MCM_Debug_Cancel_Text", "", OPTION_FLAG_NONE)
		; right-hand column: the optional mods this one works with, and what the DLL found of each (read-only)
		SetCursorPosition(1)
		AddHeaderOption("$AG_MCM_Debug_Mods_Header", OPTION_FLAG_NONE)
		String[] names = AG_Native.GetIntegrationNames()
		String[] found = AG_Native.GetIntegrationStates()
		Int i = 0
		While i < names.Length && i < found.Length
			AddTextOption(names[i], found[i], OPTION_FLAG_NONE)
			i += 1
		EndWhile
	EndIf
EndEvent

; ---- System: rank labels (one switch for the three of them), Guild notices ----
State Labels
	Event OnSelectST()
		bShowLabels = !bShowLabels
		SetToggleOptionValueST(bShowLabels, False, "")
		Apply()
	EndEvent
	Event OnDefaultST()
		bShowLabels = True
		SetToggleOptionValueST(bShowLabels, False, "")
		Apply()
	EndEvent
	Event OnHighlightST()
		SetInfoText("$AG_MCM_System_bShowLabels_Help")
	EndEvent
EndState

State Greetings
	Event OnSelectST()
		bGreetingsOff = !bGreetingsOff
		SetToggleOptionValueST(!bGreetingsOff, False, "")
		Apply()
	EndEvent
	Event OnDefaultST()
		bGreetingsOff = False
		SetToggleOptionValueST(True, False, "")
		Apply()
	EndEvent
	Event OnHighlightST()
		SetInfoText("$AG_MCM_Audio_bGreetings_Help")
	EndEvent
EndState

State FollowerComments
	Event OnSelectST()
		bFollowerCommentsOff = !bFollowerCommentsOff
		SetToggleOptionValueST(!bFollowerCommentsOff, False, "")
		Apply()
	EndEvent
	Event OnDefaultST()
		bFollowerCommentsOff = False
		SetToggleOptionValueST(True, False, "")
		Apply()
	EndEvent
	Event OnHighlightST()
		SetInfoText("$AG_MCM_Audio_bFollowerComments_Help")
	EndEvent
EndState

State Interactions
	Event OnSelectST()
		bInteractionsOff = !bInteractionsOff
		SetToggleOptionValueST(!bInteractionsOff, False, "")
		Apply()
	EndEvent
	Event OnDefaultST()
		bInteractionsOff = False
		SetToggleOptionValueST(True, False, "")
		Apply()
	EndEvent
	Event OnHighlightST()
		SetInfoText("$AG_MCM_Audio_bInteractions_Help")
	EndEvent
EndState

State RepLines
	Event OnSelectST()
		bRepLinesOff = !bRepLinesOff
		SetToggleOptionValueST(!bRepLinesOff, False, "")
		Apply()
	EndEvent
	Event OnDefaultST()
		bRepLinesOff = False
		SetToggleOptionValueST(True, False, "")
		Apply()
	EndEvent
	Event OnHighlightST()
		SetInfoText("$AG_MCM_Audio_bRepLines_Help")
	EndEvent
EndState

String[] Function SoundSetNames()
	String[] names = new String[3]
	names[0] = "$AG_MCM_Audio_SoundSet_Drums"
	names[1] = "$AG_MCM_Audio_SoundSet_Skyrim"
	names[2] = "$AG_MCM_Audio_SoundSet_None"
	Return names
EndFunction

String Function SoundSetName(Int aiSet)
	Return SoundSetNames()[aiSet]
EndFunction

String[] Function SoundVolumeNames()
	String[] names = new String[3]
	names[0] = "$AG_MCM_Audio_SoundVolume_Quieter"
	names[1] = "$AG_MCM_Audio_SoundVolume_Default"
	names[2] = "$AG_MCM_Audio_SoundVolume_Louder"
	Return names
EndFunction

State SoundsReplaced
	Event OnHighlightST()
		SetInfoText("$AG_MCM_Audio_Replaced_Help")
	EndEvent
EndState

State SoundVolume
	Event OnMenuOpenST()
		SetMenuDialogOptions(SoundVolumeNames())
		SetMenuDialogStartIndex(iSoundVolume + 1)
		SetMenuDialogDefaultIndex(1)
	EndEvent
	Event OnMenuAcceptST(Int a_index)
		If a_index >= 0 && a_index <= 2
			iSoundVolume = a_index - 1
			SetMenuOptionValueST(SoundVolumeNames()[a_index], False, "")
			Apply()
		EndIf
	EndEvent
	Event OnDefaultST()
		iSoundVolume = 0
		SetMenuOptionValueST(SoundVolumeNames()[1], False, "")
		Apply()
	EndEvent
	Event OnHighlightST()
		SetInfoText("$AG_MCM_Audio_iSoundVolume_Help")
	EndEvent
EndState

State SoundSet
	Event OnMenuOpenST()
		SetMenuDialogOptions(SoundSetNames())
		SetMenuDialogStartIndex(iSoundSet)
		SetMenuDialogDefaultIndex(0)
	EndEvent
	Event OnMenuAcceptST(Int a_index)
		If a_index >= 0 && a_index <= 2
			iSoundSet = a_index
			SetMenuOptionValueST(SoundSetName(iSoundSet), False, "")
			Apply()
			ForcePageReset()  ; the replaced-sounds warning shows for Skyrim only
		EndIf
	EndEvent
	Event OnDefaultST()
		iSoundSet = 0
		SetMenuOptionValueST(SoundSetName(iSoundSet), False, "")
		Apply()
	EndEvent
	Event OnHighlightST()
		SetInfoText("$AG_MCM_Audio_iSoundSet_Help")
	EndEvent
EndState

State Toast
	Event OnSelectST()
		bShowToast = !bShowToast
		SetToggleOptionValueST(bShowToast, False, "")
		Apply()
	EndEvent
	Event OnDefaultST()
		bShowToast = True
		SetToggleOptionValueST(bShowToast, False, "")
		Apply()
	EndEvent
	Event OnHighlightST()
		SetInfoText("$AG_MCM_System_bShowNotices_Help")
	EndEvent
EndState

; ---- System: the level of rank S. One table for the player's promotions and for every threat, dungeon and adventurer ----
State SLevel
	Event OnSliderOpenST()
		SetSliderDialogStartValue(iSLevel)
		SetSliderDialogDefaultValue(AG_Native.GetDefaultSLevel())
		SetSliderDialogRange(60.0, 120.0)
		SetSliderDialogInterval(10.0)
	EndEvent
	Event OnSliderAcceptST(Float a_value)
		iSLevel = a_value as Int
		Apply()
		ForcePageReset()  ; the five levels beneath it
	EndEvent
	Event OnDefaultST()
		iSLevel = AG_Native.GetDefaultSLevel()
		Apply()
		ForcePageReset()
	EndEvent
	Event OnHighlightST()
		SetInfoText("$AG_MCM_System_iSLevel_Help")
	EndEvent
EndState

State ToastSeconds
	Event OnSliderOpenST()
		SetSliderDialogStartValue(fToastSeconds)
		SetSliderDialogDefaultValue(5.0)
		SetSliderDialogRange(2.0, 15.0)
		SetSliderDialogInterval(1.0)
	EndEvent
	Event OnSliderAcceptST(Float a_value)
		fToastSeconds = a_value
		SetSliderOptionValueST(fToastSeconds, "{0} s", False, "")
		Apply()
	EndEvent
	Event OnDefaultST()
		fToastSeconds = 5.0
		SetSliderOptionValueST(fToastSeconds, "{0} s", False, "")
		Apply()
	EndEvent
	Event OnHighlightST()
		SetInfoText("$AG_MCM_System_fNoticeSeconds_Help")
	EndEvent
EndState

; ---- System: the key that opens the Guild Card. None by default, so it cannot collide with another mod's key;
; SkyUI reports a cleared key as -1. ----
Int Function CardKeyShown()
	If iCardKey > 0
		Return iCardKey
	EndIf
	Return -1
EndFunction

State CardKey
	Event OnKeyMapChangeST(Int a_keyCode, String a_conflictControl, String a_conflictName)
		If a_keyCode > 0 && a_conflictControl != ""
			String other = a_conflictControl
			If a_conflictName != ""
				other = a_conflictControl + " (" + a_conflictName + ")"
			EndIf
			If !ShowMessage(AG_Native.CardKeyConflictText(other), True, "$AG_MCM_Debug_Yes", "$AG_MCM_Debug_No")
				Return
			EndIf
		EndIf
		iCardKey = a_keyCode
		SetKeyMapOptionValueST(CardKeyShown(), False, "")
		Apply()
	EndEvent
	Event OnDefaultST()
		iCardKey = -1
		SetKeyMapOptionValueST(-1, False, "")
		Apply()
	EndEvent
	Event OnHighlightST()
		SetInfoText("$AG_MCM_System_iCardKey_Help")
	EndEvent
EndState

; ---- Debug: the detailed support log (each kill, each counter action) ----
State DetailedLog
	Event OnSelectST()
		bDetailedLog = !bDetailedLog
		SetToggleOptionValueST(bDetailedLog, False, "")
		Apply()
	EndEvent
	Event OnDefaultST()
		bDetailedLog = False
		SetToggleOptionValueST(bDetailedLog, False, "")
		Apply()
	EndEvent
	Event OnHighlightST()
		SetInfoText("$AG_MCM_Debug_bDetailedLog_Help")
	EndEvent
EndState

; ---- Debug, uninstalling: the DLL takes back every ability, perk and item of ours and stays dormant; here the Guild's
; quests stop, so its dialogue is gone too. Cancel restarts them (the registration quest only if it was running). ----
State Prepare
	Event OnSelectST()
		If AG_Native.IsPreparedForUninstall()
			ShowMessage(AG_Native.UninstallText(1), False, "$Accept", "$Cancel")
			Return
		EndIf
		If !ShowMessage(AG_Native.UninstallText(0), True, "$AG_MCM_Debug_Yes", "$AG_MCM_Debug_No")
			Return
		EndIf
		String report = AG_Native.PrepareUninstall()
		Quest reg = Game.GetFormFromFile(0x810, "AdventurersGuild.esp") as Quest
		bRegistrationWasRunning = reg && reg.IsRunning()
		SetGuildQuests(False)
		ShowMessage(report, False, "$Accept", "$Cancel")
	EndEvent
	Event OnHighlightST()
		SetInfoText("$AG_MCM_Debug_Prepare_Help")
	EndEvent
EndState

; ---- Debug: the guild rank your level alone gives, with the Reputation that rank starts at (the DLL words both
; messages, in the game's language) ----
State RankReset
	Event OnSelectST()
		If !AG_Native.IsRegistered()
			ShowMessage(AG_Native.RankResetText(), False, "$Accept", "$Cancel")
			Return
		EndIf
		If !ShowMessage(AG_Native.RankResetText(), True, "$Accept", "$Cancel")
			Return
		EndIf
		ShowMessage(AG_Native.RecalculateRank(), False, "$Accept", "$Cancel")
	EndEvent
	Event OnHighlightST()
		SetInfoText("$AG_MCM_Debug_RankReset_Help")
	EndEvent
EndState

State Cancel
	Event OnSelectST()
		If !AG_Native.IsPreparedForUninstall()
			ShowMessage(AG_Native.UninstallText(2), False, "$Accept", "$Cancel")
			Return
		EndIf
		String report = AG_Native.CancelUninstall()
		SetGuildQuests(True)
		ShowMessage(report, False, "$Accept", "$Cancel")
	EndEvent
	Event OnHighlightST()
		SetInfoText("$AG_MCM_Debug_Cancel_Help")
	EndEvent
EndState

; the Guild's dialogue at innkeepers (0x804), the world's greetings (0x8C0) and the registration quest (0x810)
Function SetGuildQuests(Bool abRunning)
	Int[] ids = new Int[3]
	ids[0] = 0x804
	ids[1] = 0x8C0
	ids[2] = 0x810
	Int i = 0
	While i < ids.Length
		Quest q = Game.GetFormFromFile(ids[i], "AdventurersGuild.esp") as Quest
		If q
			If !abRunning
				q.Stop()
			ElseIf ids[i] != 0x810 || bRegistrationWasRunning
				q.Start()
			EndIf
		EndIf
		i += 1
	EndWhile
EndFunction
