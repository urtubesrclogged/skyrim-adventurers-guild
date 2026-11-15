Scriptname AGHallBackOfficeDoor extends ObjectReference
{The guild's back office door: it is kept closed, as a staff-only room's door would be. The game never closes a door, so
when one of the staff opens this one it closes behind them. The door has no lock and no key (a follower walked through it
while it was locked): it is closed, never locked. A door the player opened is the player's: it stays open until the player
closes it, so nothing runs on it. (The bedroom doors briefly used this script too; they have AGHallBedroomDoor, closed
only at bedtime.)}

Float Property Pause = 2.0 Auto           ; (seconds between looks at the doorway)
Float Property Doorway = 170.0 Auto       ; (from the hinge: the leaf's reach and the step either side of it)
Int Property MostWaits = 6 Auto           ; (someone can stand near it all evening: it closes anyway after this many looks)

Bool PlayerHasIt = False
Int Waits = 0

Event OnOpen(ObjectReference akActionRef)
	PlayerHasIt = akActionRef == Game.GetPlayer()
	Waits = 0
	If PlayerHasIt
		UnregisterForUpdate()
	Else
		RegisterForSingleUpdate(Pause)
	EndIf
EndEvent

Event OnUpdate()
	If PlayerHasIt || GetOpenState() != 1
		Return
	EndIf
	Waits += 1
	If Waits < MostWaits && Game.FindClosestActorFromRef(self, Doorway)
		RegisterForSingleUpdate(Pause)
		Return
	EndIf
	SetOpen(False)
EndEvent

Event OnClose(ObjectReference akActionRef)
	PlayerHasIt = False
EndEvent

; an update that came due with the hall unloaded did nothing: the door is seen to when the hall is back
Event OnCellAttach()
	If !PlayerHasIt && GetOpenState() == 1
		Waits = 0
		RegisterForSingleUpdate(Pause)
	EndIf
EndEvent
