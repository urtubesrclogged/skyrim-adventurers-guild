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
Bool bRegistrationWasRunning = False

Int Function GetVersion()
	Return 2
EndFunction

Event OnConfigInit()
	SetPages()
	bShowLabels = AG_Native.GetShowGuildRank() || AG_Native.GetShowThreatRank() || AG_Native.GetShowLevelSuffix()
	bLabelsCarriedOver = True  ; a first install has nothing older to carry over
	bShowToast = AG_Native.GetShowRankUpToast()
	fToastSeconds = AG_Native.GetToastSeconds()
	bDetailedLog = AG_Native.GetDetailedLog()
	Apply()
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
EndEvent

Event OnGameReload()
	Parent.OnGameReload()
	Apply()
EndEvent

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
	ElseIf a_page == Pages[1]
		AddHeaderOption("$AG_MCM_Debug_Log_Header", OPTION_FLAG_NONE)
		AddToggleOptionST("DetailedLog", "$AG_MCM_Debug_bDetailedLog_Text", bDetailedLog, OPTION_FLAG_NONE)
		AddEmptyOption()
		AddHeaderOption("$AG_MCM_Debug_Uninstall_Header", OPTION_FLAG_NONE)
		AddTextOptionST("Prepare", "$AG_MCM_Debug_Prepare_Text", "", OPTION_FLAG_NONE)
		AddTextOptionST("Cancel", "$AG_MCM_Debug_Cancel_Text", "", OPTION_FLAG_NONE)
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
