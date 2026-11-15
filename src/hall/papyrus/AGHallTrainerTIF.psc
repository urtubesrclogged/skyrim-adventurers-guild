;/ Marius's training: the player picks a skill, and he trains it as vanilla's trainers do. Each
   skill's reply sets Skill (vanilla's CLAS skill index) and MaxLevel on his class through AG's DLL, then opens vanilla's
   training menu, so the price, the five sessions a level and the cap stay vanilla's. Members only (the topic's conditions). /;
ScriptName AGHallTrainerTIF Extends TopicInfo Hidden

Int Property Skill Auto
Int Property MaxLevel Auto

Function Fragment_0(ObjectReference akSpeakerRef)
	Actor who = akSpeakerRef as Actor
	If who && AG_Native.SetTrainerSkill(who, Skill, MaxLevel)
		Game.ShowTrainingMenu(who)
	EndIf
EndFunction
