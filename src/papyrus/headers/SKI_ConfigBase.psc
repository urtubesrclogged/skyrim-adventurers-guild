;/ Compile-time declarations only: SkyUI's SKI_ConfigBase (SkyUI 5 / SkyUI VR), trimmed to the members this mod's scripts
   call. Signatures checked against SkyUI VR 1.2.2's compiled script. The installed mod's own script is what runs; this
   mod does not ship it. /;
ScriptName SKI_ConfigBase Extends SKI_QuestBase Hidden

String Property ModName Auto
String[] Property Pages Auto
String Property CurrentPage Auto
Int Property LEFT_TO_RIGHT = 1 AutoReadOnly
Int Property TOP_TO_BOTTOM = 2 AutoReadOnly
Int Property OPTION_FLAG_NONE = 0 AutoReadOnly
Int Property OPTION_FLAG_DISABLED = 1 AutoReadOnly
Int Property OPTION_FLAG_WITH_UNMAP = 4 AutoReadOnly

Int Function GetVersion()
	Return 0
EndFunction

Event OnConfigInit()
EndEvent

Event OnConfigOpen()
EndEvent

Event OnConfigClose()
EndEvent

Event OnPageReset(String a_page)
EndEvent

; state-option events (the ...ST option functions route to these in the option's state)
Event OnSelectST()
EndEvent

Event OnDefaultST()
EndEvent

Event OnHighlightST()
EndEvent

Event OnSliderOpenST()
EndEvent

Event OnSliderAcceptST(Float a_value)
EndEvent

Event OnKeyMapChangeST(Int a_keyCode, String a_conflictControl, String a_conflictName)
EndEvent

Function SetCursorFillMode(Int a_fillMode)
EndFunction

Int Function AddHeaderOption(String a_text, Int a_flags = 0)
	Return 0
EndFunction

Int Function AddEmptyOption()
	Return 0
EndFunction

Function AddTextOptionST(String a_stateName, String a_text, String a_value, Int a_flags = 0)
EndFunction

Function AddToggleOptionST(String a_stateName, String a_text, Bool a_checked, Int a_flags = 0)
EndFunction

Function AddSliderOptionST(String a_stateName, String a_text, Float a_value, String a_formatString = "{0}", Int a_flags = 0)
EndFunction

Function AddKeyMapOptionST(String a_stateName, String a_text, Int a_keyCode, Int a_flags = 0)
EndFunction

Function SetKeyMapOptionValueST(Int a_keyCode, Bool a_noUpdate = False, String a_stateName = "")
EndFunction

Function SetToggleOptionValueST(Bool a_checked, Bool a_noUpdate = False, String a_stateName = "")
EndFunction

Function SetSliderOptionValueST(Float a_value, String a_formatString = "{0}", Bool a_noUpdate = False, String a_stateName = "")
EndFunction

Function SetSliderDialogStartValue(Float a_value)
EndFunction

Function SetSliderDialogDefaultValue(Float a_value)
EndFunction

Function SetSliderDialogRange(Float a_minValue, Float a_maxValue)
EndFunction

Function SetSliderDialogInterval(Float a_value)
EndFunction

Function SetInfoText(String a_text)
EndFunction

Function ForcePageReset()
EndFunction

Bool Function ShowMessage(String a_message, Bool a_withCancel = True, String a_acceptLabel = "$Accept", String a_cancelLabel = "$Cancel")
	Return False
EndFunction
