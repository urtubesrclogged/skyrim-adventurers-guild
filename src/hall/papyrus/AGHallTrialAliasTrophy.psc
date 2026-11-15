; the trial's trophy: taken by the player from the creature's body
ScriptName AGHallTrialAliasTrophy Extends ReferenceAlias Hidden

Event OnContainerChanged(ObjectReference akNewContainer, ObjectReference akOldContainer)
	If akNewContainer == Game.GetPlayer()
		(GetOwningQuest() as AGHallTrialQuestScript).TrophyTaken()
	EndIf
EndEvent
