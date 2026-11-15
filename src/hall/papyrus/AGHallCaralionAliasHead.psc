; Vohd's head: taken by the player, the ambush comes in
ScriptName AGHallCaralionAliasHead Extends ReferenceAlias Hidden

Event OnContainerChanged(ObjectReference akNewContainer, ObjectReference akOldContainer)
	If akNewContainer == Game.GetPlayer()
		(GetOwningQuest() as AGHallCaralionQuestScript).HeadTaken()
	EndIf
EndEvent
