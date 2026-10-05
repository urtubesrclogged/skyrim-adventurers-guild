; Adventurers Guild - Copyright (C) 2026 urtubesrclogged
; SPDX-License-Identifier: GPL-3.0-or-later (with the additional permissions in EXCEPTIONS.md). NO WARRANTY.
; Source and license: https://github.com/urtubesrclogged/skyrim-adventurers-guild

ScriptName AG_SkyrimNetInit Extends ReferenceAlias
{Optional SkyrimNet integration: registers the guild_rank_of / threat_rank_of decorators and turns guild
registration, promotions and Deeds of Skyrim unlocks into remembered SkyrimNet events. Attached to
AG_ConfigQuest's PlayerAlias, alongside SKI_PlayerLoadGameAlias. Fully inert without SkyrimNet.esp.}

Event OnInit()
	Utility.Wait(0.5)
	Initialize()
EndEvent

Event OnPlayerLoadGame()
	Initialize()
EndEvent

Function Initialize()
	If Game.GetModByName("SkyrimNet.esp") == 255
		Return
	EndIf
	Int a = SkyrimNetApi.RegisterDecorator("guild_rank_of", "AG_SkyrimNet_Decorators", "GetGuildRankOf")
	Int b = SkyrimNetApi.RegisterDecorator("threat_rank_of", "AG_SkyrimNet_Decorators", "GetThreatRankOf")
	Int c = SkyrimNetApi.RegisterDecorator("ag_player", "AG_SkyrimNet_Decorators", "GetPlayerLedger")
	Int d = SkyrimNetApi.RegisterDecorator("ag_join_status", "AG_SkyrimNet_Decorators", "GetJoinStatusOf")
	Int e = SkyrimNetApi.RegisterDecorator("ag_party", "AG_SkyrimNet_Decorators", "GetPartyOf")
	Debug.Trace("[AdventurersGuild] SkyrimNet decorators: guild_rank_of " + (a == 0) as String + ", threat_rank_of " + (b == 0) as String + ", ag_player " + (c == 0) as String + ", ag_join_status " + (d == 0) as String + ", ag_party " + (e == 0) as String)

	RegisterForModEvent("AG_Registered", "OnGuildRegistered")
	RegisterForModEvent("AG_RankChanged", "OnGuildRankChanged")
	RegisterForModEvent("DS_DeedUnlocked", "OnDeedUnlocked")
	RegisterForModEvent("AG_MissiveCompleted", "OnMissiveCompleted")
	RegisterForModEvent("AG_ReportsSubmitted", "OnReportsSubmitted")
	RegisterForModEvent("AG_DungeonCleared", "OnDungeonCleared")
	RegisterForModEvent("AG_NotableKill", "OnNotableKill")
	RegisterForModEvent("AG_TrophiesHandedIn", "OnTrophiesHandedIn")
	RegisterForModEvent("AG_IntelBought", "OnIntelBought")
	RegisterForModEvent("AG_AdventurerJoined", "OnAdventurerJoined")
	RegisterForModEvent("AG_PartyFounded", "OnPartyFounded")
	RegisterForModEvent("AG_PartyRenamed", "OnPartyRenamed")
	RegisterForModEvent("AG_PartyDisbanded", "OnPartyDisbanded")
	RegisterForModEvent("AG_PartyMemberJoined", "OnPartyMemberJoined")
	RegisterForModEvent("AG_PartyMemberLeft", "OnPartyMemberLeft")
	RegisterForModEvent("AG_PartyMemberFell", "OnPartyMemberFell")
	RegisterForModEvent("AG_PartyBondTier", "OnPartyBondTier")
EndFunction

; A plain Function, not an Event: RegisterForModEvent dispatches by (script, function) name, and
; Caprica only accepts new Events when they are native.
Function OnGuildRegistered(String eventName, String strArg, Float numArg, Form sender)
	If Game.GetModByName("SkyrimNet.esp") == 255
		Return
	EndIf
	Actor player = Game.GetPlayer()
	SkyrimNetApi.RegisterPersistentEvent(player.GetDisplayName() + " registered with the Adventurers Guild as " + RankPhrase(strArg) + " adventurer.", None, player)
EndFunction

Function OnGuildRankChanged(String eventName, String strArg, Float numArg, Form sender)
	If Game.GetModByName("SkyrimNet.esp") == 255
		Return
	EndIf
	Actor player = Game.GetPlayer()
	SkyrimNetApi.RegisterPersistentEvent(player.GetDisplayName() + " was promoted to " + strArg + "-rank by the Adventurers Guild.", None, player)
EndFunction

; strArg = deed id. Fired by DeedsOfSkyrim.dll on unlock (never fires without that mod installed).
Function OnDeedUnlocked(String eventName, String strArg, Float numArg, Form sender)
	If Game.GetModByName("SkyrimNet.esp") == 255
		Return
	EndIf
	String name = DS_Native.GetDeedName(strArg)
	If name == ""
		Return
	EndIf
	Actor player = Game.GetPlayer()
	String desc = DS_Native.GetDeedDescription(strArg)
	String msg = player.GetDisplayName() + " has accomplished the deed \"" + name + "\""
	If desc != ""
		msg += " (" + desc + ")"
	EndIf
	SkyrimNetApi.RegisterPersistentEvent(msg + ".", None, player)
EndFunction

; ---- Adventurers Guild activity (fired by AdventurersGuild.dll). numArg carries a rank index (0 = E) where one applies.

; "an A-rank", "a C-rank": how people say a rank (the Guild writes "Rank C" on paper; see the guidelines prompt)
String Function RankPhrase(String asLetter)
	If asLetter == "A" || asLetter == "E" || asLetter == "S"
		Return "an " + asLetter + "-rank"
	EndIf
	Return "a " + asLetter + "-rank"
EndFunction

String Function RankWord(Float afRank)
	Return AG_Native.GetRankLetter(afRank as Int)
EndFunction

Function Remember(String asText)
	If Game.GetModByName("SkyrimNet.esp") != 255
		Actor player = Game.GetPlayer()
		SkyrimNetApi.RegisterPersistentEvent(player.GetDisplayName() + " " + asText, None, player)
	EndIf
EndFunction

; A counter visit's small change: shown to nearby NPCs for ten minutes, not kept forever.
Function Mention(String asId, String asText)
	If Game.GetModByName("SkyrimNet.esp") != 255
		Actor player = Game.GetPlayer()
		SkyrimNetApi.RegisterShortLivedEvent("ag_" + asId, "adventurers_guild", player.GetDisplayName() + " " + asText, "", 600000, player, None)
	EndIf
EndFunction

Function OnMissiveCompleted(String eventName, String strArg, Float numArg, Form sender)
	Remember("completed " + RankPhrase(RankWord(numArg)) + " Guild Missive: " + strArg + ".")
EndFunction

Function OnReportsSubmitted(String eventName, String strArg, Float numArg, Form sender)
	Remember("handed in " + strArg + " at an Adventurers Guild counter.")
EndFunction

Function OnDungeonCleared(String eventName, String strArg, Float numArg, Form sender)
	Remember("cleared " + strArg + ", " + RankPhrase(RankWord(numArg)) + " dungeon, and can report it to the Adventurers Guild.")
EndFunction

Function OnNotableKill(String eventName, String strArg, Float numArg, Form sender)
	Remember("slew " + strArg + ", " + RankPhrase(RankWord(numArg)) + " foe.")
EndFunction

Function OnTrophiesHandedIn(String eventName, String strArg, Float numArg, Form sender)
	Mention("trophies", "sold " + strArg + " to the Adventurers Guild for " + (numArg as Int) + " Merit.")
EndFunction

; strArg = the NPC's name: they signed themselves up in a SkyrimNet conversation (AG_JoinAdventurersGuild)
Function OnAdventurerJoined(String eventName, String strArg, Float numArg, Form sender)
	If Game.GetModByName("SkyrimNet.esp") != 255
		Actor player = Game.GetPlayer()
		SkyrimNetApi.RegisterPersistentEvent(strArg + " joined the Adventurers Guild as " + RankPhrase(RankWord(numArg)) + " adventurer, after talking it over with " + player.GetDisplayName() + ".", None, player)
	EndIf
EndFunction

; ---- adventuring parties (AdventurersGuild.dll, Party.cpp). strArg: the party's or the member's name.
String Function PartyName()
	String n = AG_Native.GetPartyName()
	If n == ""
		Return "their party"
	EndIf
	Return n
EndFunction

Function OnPartyFounded(String eventName, String strArg, Float numArg, Form sender)
	Remember("registered an adventuring party with the Adventurers Guild: " + strArg + ".")
EndFunction

Function OnPartyRenamed(String eventName, String strArg, Float numArg, Form sender)
	Remember("renamed their adventuring party " + strArg + ".")
EndFunction

Function OnPartyDisbanded(String eventName, String strArg, Float numArg, Form sender)
	Remember("disbanded the adventuring party " + strArg + ".")
EndFunction

Function OnPartyMemberJoined(String eventName, String strArg, Float numArg, Form sender)
	If Game.GetModByName("SkyrimNet.esp") != 255
		SkyrimNetApi.RegisterPersistentEvent(strArg + " joined " + Game.GetPlayer().GetDisplayName() + "'s adventuring party, " + PartyName() + ".", None, Game.GetPlayer())
	EndIf
EndFunction

Function OnPartyMemberLeft(String eventName, String strArg, Float numArg, Form sender)
	If Game.GetModByName("SkyrimNet.esp") != 255
		SkyrimNetApi.RegisterPersistentEvent(strArg + " left " + Game.GetPlayer().GetDisplayName() + "'s adventuring party, " + PartyName() + ".", None, Game.GetPlayer())
	EndIf
EndFunction

; strArg = "Faendal fell at Bleak Falls Barrow" (or just "Faendal fell")
Function OnPartyMemberFell(String eventName, String strArg, Float numArg, Form sender)
	If Game.GetModByName("SkyrimNet.esp") != 255
		SkyrimNetApi.RegisterPersistentEvent(strArg + ", a member of " + Game.GetPlayer().GetDisplayName() + "'s adventuring party, " + PartyName() + ".", None, Game.GetPlayer())
	EndIf
EndFunction

; numArg = the Bond tier reached (1 Companions .. 4 Legend)
Function OnPartyBondTier(String eventName, String strArg, Float numArg, Form sender)
	String[] words = new String[5]
	words[1] = "Companions"
	words[2] = "Comrades"
	words[3] = "Sworn"
	words[4] = "Legend"
	Int t = numArg as Int
	If t >= 1 && t <= 4
		Remember("and their adventuring party " + strArg + " have grown close: their bond is now " + words[t] + ".")
	EndIf
EndFunction

Function OnIntelBought(String eventName, String strArg, Float numArg, Form sender)
	Mention("intel", "bought the Adventurers Guild's intel on " + strArg + " (" + RankPhrase(RankWord(numArg)) + " place).")
EndFunction
