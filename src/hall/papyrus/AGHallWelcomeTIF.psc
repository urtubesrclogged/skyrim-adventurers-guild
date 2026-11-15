;/ Merila's welcome: she welcomes the player to the hall on joining or on their first time in it. It plays once: the moment she begins it, Done is set and
   her ForceGreet package (conditioned on Done 0) stops, so walking off mid-welcome never brings her back to start again. /;
ScriptName AGHallWelcomeTIF Extends TopicInfo Hidden

GlobalVariable Property Done Auto   ; AGHallWelcomeDoneGlobal: 1 once the welcome has begun

Function Fragment_0(ObjectReference akSpeakerRef)
	Done.SetValue(1)
EndFunction
