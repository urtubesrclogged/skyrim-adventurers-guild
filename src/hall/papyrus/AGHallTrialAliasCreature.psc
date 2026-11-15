; the trial's creature: its death moves the trial on
ScriptName AGHallTrialAliasCreature Extends ReferenceAlias Hidden

Event OnDeath(Actor akKiller)
	(GetOwningQuest() as AGHallTrialQuestScript).CreatureDied()
EndEvent
