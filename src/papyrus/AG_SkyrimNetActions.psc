; Adventurers Guild - Copyright (C) 2026 urtubesrclogged
; SPDX-License-Identifier: GPL-3.0-or-later (with the additional permissions in EXCEPTIONS.md). NO WARRANTY.
; Source and license: https://github.com/urtubesrclogged/skyrim-adventurers-guild

ScriptName AG_SkyrimNetActions Extends Quest
{SkyrimNet custom actions for the Adventurers Guild (external/adventurersguild.skyrimnet/actions/*.yaml). Attached to
AG_GuildDialogueQuest. Each is called with the speaking NPC; AdventurersGuild.dll applies the same fees and checks as
the innkeeper dialogue and refuses anyone who is not one of the nine Guild reps.}

Function OpenCounter_Execute(Actor akSpeaker)
	Debug.Trace("[AdventurersGuild] SkyrimNet action OpenCounter: " + AG_Native.ActionOpenCounter(akSpeaker))
EndFunction

Function Register_Execute(Actor akSpeaker)
	Debug.Trace("[AdventurersGuild] SkyrimNet action Register: " + AG_Native.ActionRegister(akSpeaker))
EndFunction

Function Promote_Execute(Actor akSpeaker)
	Debug.Trace("[AdventurersGuild] SkyrimNet action Promote: " + AG_Native.ActionPromote(akSpeaker))
EndFunction

Function Reports_Execute(Actor akSpeaker)
	Debug.Trace("[AdventurersGuild] SkyrimNet action Reports: " + AG_Native.ActionReports(akSpeaker))
EndFunction

; any NPC (not a rep) deciding to become an adventurer
Function Join_Execute(Actor akSpeaker)
	Debug.Trace("[AdventurersGuild] SkyrimNet action Join: " + AG_Native.ActionJoinGuild(akSpeaker))
EndFunction
