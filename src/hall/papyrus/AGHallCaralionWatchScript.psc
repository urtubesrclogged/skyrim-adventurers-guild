;/ Starts Caralion's quest, and ends the Golden Hand when he dies (a start-game quest of its own):
   the quest starts once the player's party passes his on the leader board (AG's AG_LeaderBoard_PassedRival event, or
   AG_LB_PassedRival already set when this loads), if he lives. His death before it starts disbands his party
   (LeaderBoardEndRival 3: frozen, "disbanded"); after the player condemned him, it ends it as his fall (1). /;
ScriptName AGHallCaralionWatchScript Extends Quest

Quest Property CaralionQuest Auto
GlobalVariable Property PassedRival Auto
ReferenceAlias Property CaralionAlias Auto

Event OnInit()
	Listen()
EndEvent

Function Listen()
	RegisterForModEvent("AG_LeaderBoard_PassedRival", "OnPassedRival")
	TryStart()
EndFunction

Function OnPassedRival(String asEventName, String asArg, Float afNum, Form akSender)   ; (a mod event: SKSE calls it by name)
	TryStart()
EndFunction

Function TryStart()
	Actor c = CaralionAlias.GetActorRef()
	If PassedRival.GetValue() < 1 || !c || c.IsDead() || CaralionQuest.IsRunning() || CaralionQuest.IsCompleted()
		Return
	EndIf
	If CaralionQuest.Start()
		(CaralionQuest as AGHallCaralionQuestScript).Begin()
	EndIf
EndFunction

Function CaralionDied()
	If !CaralionQuest.IsRunning() && !CaralionQuest.IsCompleted()
		AG_Native.LeaderBoardEndRival(3)
	ElseIf CaralionQuest.GetStageDone(66)
		AG_Native.LeaderBoardEndRival(1)
	EndIf
EndFunction
