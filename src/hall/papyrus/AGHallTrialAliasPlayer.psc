; the player in a promotion trial: each load, the creature's level again (a base's data is not saved)
ScriptName AGHallTrialAliasPlayer Extends ReferenceAlias Hidden

Event OnPlayerLoadGame()
	(GetOwningQuest() as AGHallTrialQuestScript).GameLoaded()
EndEvent
