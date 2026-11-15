; Vohd: his death; the alias keeps his body for the head
ScriptName AGHallCaralionAliasVohd Extends ReferenceAlias Hidden

Event OnDeath(Actor akKiller)
	(GetOwningQuest() as AGHallCaralionQuestScript).VohdDied()
EndEvent
