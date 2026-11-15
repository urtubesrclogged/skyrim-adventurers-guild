;/ Cassius's and Brynja's "What have you got for sale?": their reply opens their shop when it ends,
   as vanilla's vendor lines do. /;
ScriptName AGHallBarterTIF Extends TopicInfo Hidden

Function Fragment_0(ObjectReference akSpeakerRef)
	Actor who = akSpeakerRef as Actor
	If who
		who.ShowBarterMenu()
	EndIf
EndFunction
