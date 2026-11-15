;/ A spouse agrees to live at the Guild Hall, in room 5 (plans/room5-home.md). As vanilla's own
   MoveSpouse does before it fills a new home, every one of RelationshipMarriageFIN's house aliases lets go, so the old
   home's packages stop; SpouseCurrentHome becomes the hall's own value, which the hall's spouse packages read (and which
   vanilla overwrites the day the spouse is moved to a house again, so those packages let go in turn). A spouse from
   outside goes into AGHallHomeQuest's alias (room 5 by night, the hall by day); one of the hall's own folk keeps their
   routine and only sleeps in room 5 (their own conditional sleep package). /;
ScriptName AG_TIF_HallHomeMove Extends TopicInfo Hidden

Quest Property MarriageFIN Auto
ReferenceAlias Property Spouse Auto
FormList Property HallFolk Auto
Int Property AtTheHall = 99 Auto

Function Fragment_0(ObjectReference akSpeakerRef)
	Actor who = akSpeakerRef as Actor
	RelationshipMarriageSpouseHouseScript homes = MarriageFIN as RelationshipMarriageSpouseHouseScript
	If homes.SolitudeHouse
		homes.SolitudeHouse.Clear()
	EndIf
	If homes.WindhelmHouse
		homes.WindhelmHouse.Clear()
	EndIf
	If homes.MarkarthHouse
		homes.MarkarthHouse.Clear()
	EndIf
	If homes.RiftenHouse
		homes.RiftenHouse.Clear()
	EndIf
	If homes.WhiterunHouse
		homes.WhiterunHouse.Clear()
	EndIf
	If homes.FalkreathHouse
		homes.FalkreathHouse.Clear()
	EndIf
	If homes.HjaalmarchHouse
		homes.HjaalmarchHouse.Clear()
	EndIf
	If homes.PaleHouse
		homes.PaleHouse.Clear()
	EndIf
	If homes.SpouseHouse
		homes.SpouseHouse.Clear()
	EndIf
	homes.SpouseCurrentHome = AtTheHall
	If !HallFolk.HasForm(who.GetActorBase())
		Spouse.ForceRefTo(who)
	EndIf
	who.EvaluatePackage()
EndFunction
