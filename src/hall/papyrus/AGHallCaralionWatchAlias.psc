; Caralion, watched for his death (AGHallCaralionWatchScript)
ScriptName AGHallCaralionWatchAlias Extends ReferenceAlias Hidden

Event OnDeath(Actor akKiller)
	(GetOwningQuest() as AGHallCaralionWatchScript).CaralionDied()
EndEvent
