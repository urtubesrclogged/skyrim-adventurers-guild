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
Bool bDetailedLog = False
; the key that opens the Guild Card: none until the player picks one (0 or less = none)
Int iCardKey = -1
Bool bRegistrationWasRunning = False
; the level of rank S (60..120). A new game takes the ini's (80); a save from before version 4 keeps 60, the levels
; it always had, and says so once
Int iSLevel = 60
Bool bSLevelSet = False

Int Function GetVersion()
	Return 4
EndFunction

Event OnConfigInit()
	SetPages()
	bShowLabels = AG_Native.GetShowGuildRank() || AG_Native.GetShowThreatRank() || AG_Native.GetShowLevelSuffix()
	bLabelsCarriedOver = True  ; a first install has nothing older to carry over
	bShowToast = AG_Native.GetShowRankUpToast()
	fToastSeconds = AG_Native.GetToastSeconds()
	bDetailedLog = AG_Native.GetDetailedLog()
	iSLevel = AG_Native.GetDefaultSLevel()
	bSLevelSet = True
	Apply()
	RegisterCardAction()
EndEvent

Event OnVersionUpdate(Int a_version)
	SetPages()
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
	Pages = new String[2]
	Pages[0] = "$AG_MCM_System"
	Pages[1] = "$AG_MCM_Debug"
EndFunction

; Pushes every setting into the DLL. Cheap and idempotent.
Function Apply()
	AG_Native.SetShowGuildRank(bShowLabels)
	AG_Native.SetShowThreatRank(bShowLabels)
	AG_Native.SetShowLevelSuffix(bShowLabels)
	AG_Native.SetShowRankUpToast(bShowToast)
	AG_Native.SetToastSeconds(fToastSeconds)
	AG_Native.SetDetailedLog(bDetailedLog)
	AG_Native.SetCardHotkey(iCardKey)
	If bSLevelSet
		AG_Native.SetSLevel(iSLevel)
	EndIf
EndFunction

Event OnPageReset(String a_page)
	SetCursorFillMode(TOP_TO_BOTTOM)
	If a_page == Pages[0]
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
