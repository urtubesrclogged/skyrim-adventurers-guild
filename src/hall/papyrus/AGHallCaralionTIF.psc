;/ The fragments of Caralion's quest's lines (AGHallCaralionQuestScript has the logic): C1's end starts the hall scene,
   Q4's begin watches for the player walking away (condemns him), Q4a spares him, Q4b condemns him, W2t tells Willem of the ambush, W2 hands Vohd's head in. /;
ScriptName AGHallCaralionTIF Extends TopicInfo Hidden

AGHallCaralionQuestScript Function Q()
	Return GetOwningQuest() as AGHallCaralionQuestScript
EndFunction

Function Fragment_C1(ObjectReference akSpeakerRef)
	Q().Challenged()
EndFunction

; C4's begin: the ambush talk; walking away from it starts the fight
Function Fragment_AmbushTalk(ObjectReference akSpeakerRef)
	Q().WatchAmbushTalk()
EndFunction

; C5's end: "Come and take it." answered with his order to his men
Function Fragment_Attack(ObjectReference akSpeakerRef)
	Q().Attack()
EndFunction

; W3's begin: Willem's word after the scene; walking away from it starts the hunt
Function Fragment_WillemWord(ObjectReference akSpeakerRef)
	Q().WatchWillemWord()
EndFunction

; W3a's end: "One troll head coming right up."
Function Fragment_Accepted(ObjectReference akSpeakerRef)
	Q().Accepted()
EndFunction

Function Fragment_Yield(ObjectReference akSpeakerRef)
	Q().WatchWalkAway()
EndFunction

Function Fragment_Spare(ObjectReference akSpeakerRef)
	Q().Spared()
EndFunction

Function Fragment_Condemn(ObjectReference akSpeakerRef)
	Q().Condemned()
EndFunction

Function Fragment_Told(ObjectReference akSpeakerRef)
	Q().Told()
EndFunction

Function Fragment_HandIn(ObjectReference akSpeakerRef)
	Q().HandedIn()
EndFunction
