;/ The fragments of the promotion trials' lines (AGHallTrialQuestScript has the logic). Willem's lines carry their own
   trial (Trial); the clerks' carry all five (Trials, D first), since their topic is the clerks' own:
   Ask    the clerk sends the player to Willem: the trial for the player's next rank starts
   Brief  Willem sets the trial (with his intro on the first): the creature placed
   NotYet Willem has no trial worthy of S before Dragon Rising
   HandIn Willem takes the trophy
   Done   the clerk updates the card: promoted /;
ScriptName AGHallTrialTIF Extends TopicInfo Hidden

Quest Property Trial Auto
Quest[] Property Trials Auto

AGHallTrialQuestScript Function T()
	Return Trial as AGHallTrialQuestScript
EndFunction

Function Fragment_Ask(ObjectReference akSpeakerRef)
	Int rank = AG_Native.GetGuildRank()   ; 0 E ... the next rank's trial is Trials[rank]
	If rank < 0 || rank >= Trials.Length
		Return
	EndIf
	AGHallTrialQuestScript q = Trials[rank] as AGHallTrialQuestScript
	If q
		q.Start()
		q.Begin()
	EndIf
EndFunction

Function Fragment_Brief(ObjectReference akSpeakerRef)
	T().Briefed()
EndFunction

Function Fragment_NotYet(ObjectReference akSpeakerRef)
	T().NotYet()
EndFunction

Function Fragment_HandIn(ObjectReference akSpeakerRef)
	T().HandedIn()
EndFunction

Function Fragment_Done(ObjectReference akSpeakerRef)
	Int i = 0
	While i < Trials.Length
		AGHallTrialQuestScript q = Trials[i] as AGHallTrialQuestScript
		If q && q.GetStage() == 50
			q.Promoted()
			Return
		EndIf
		i += 1
	EndWhile
EndFunction
