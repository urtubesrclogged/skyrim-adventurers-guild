; the player in Caralion's quest: each load, Vohd's level again
ScriptName AGHallCaralionAliasPlayer Extends ReferenceAlias Hidden

Event OnPlayerLoadGame()
	(GetOwningQuest() as AGHallCaralionQuestScript).GameLoaded()
EndEvent
