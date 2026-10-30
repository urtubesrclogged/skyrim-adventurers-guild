; Adventurers Guild - Copyright (C) 2026 urtubesrclogged
; SPDX-License-Identifier: GPL-3.0-or-later (with the additional permissions in EXCEPTIONS.md). NO WARRANTY.
; Source and license: https://github.com/urtubesrclogged/skyrim-adventurers-guild

ScriptName AGChim Hidden
{CHIM actions for the Adventurers Guild (1.6.0), the twin of AG_SkyrimNetActions. CHIM lists them from
Data/CHIM/adventurersguild_actions.csv; when an NPC uses one, CHIM's DLL calls the static DispatchExternalCommand of the
script named between "ExtCmd" and the first "_" of the action's code (CHIM Plugin/Commands.cpp), so this script's name
can have no underscore. The NPC comes by name: CHIM's own agent of that name. AdventurersGuild.dll runs the action with
the same fees and checks as the innkeeper dialogue, and the result goes back to CHIM ("funcret"), so the NPC answers
knowing it.}

Bool Function DispatchExternalCommand(String asNpcName, String asCommand, String asParameter) Global
	Actor npc = AIAgentFunctions.getAgentByName(asNpcName)
	String result = AG_Native.ChimAction(npc, asCommand)   ; "" when the command is not one of ours
	If result == ""
		Return False
	EndIf
	AIAgentFunctions.logMessageForActor("command@" + asCommand + "@" + asParameter + "@" + asNpcName + ": " + result, "funcret", asNpcName)
	Return True
EndFunction
