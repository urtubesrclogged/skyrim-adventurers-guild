; the player, for the load event: the watcher listens again and checks the leader board
ScriptName AGHallCaralionWatchPlayer Extends ReferenceAlias Hidden

Event OnPlayerLoadGame()
	(GetOwningQuest() as AGHallCaralionWatchScript).Listen()
EndEvent
