; Caralion in his quest (essential from stage 10 until he yields): beaten at the ambush, he yields
ScriptName AGHallCaralionAliasCaralion Extends ReferenceAlias Hidden

Event OnEnterBleedout()
	(GetOwningQuest() as AGHallCaralionQuestScript).Yielded()
EndEvent
