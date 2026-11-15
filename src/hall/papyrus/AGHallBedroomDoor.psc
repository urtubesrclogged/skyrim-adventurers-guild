Scriptname AGHallBedroomDoor extends ObjectReference
{A bedroom door of the hall's folk, closed only when its resident goes to sleep (closing every bedroom door behind everyone
was too much). By day nothing runs: the door stays as its people leave it.
While it stands open and the hall is loaded, the door looks at its Sleeper (npcgen names one per door: rooms 3-7 and the guild master's
bedroom); once they are lying down to sleep and the doorway is clear, it closes. A door the player opened is the player's (it stays
open until the player closes it): nothing runs on it until it is closed again. In the morning the sleeper
opens it on the way out and it stays open, as vanilla's.}

Actor Property Sleeper Auto
Float Property Doorway = 170.0 Auto       ; (from the hinge: the leaf's reach and the step either side of it)
Float Property Quick = 3.0 Auto           ; (seconds between looks just after someone opened it: they may be on their way to bed)
Int Property QuickLooks = 15 Auto         ; (about 45 seconds of quick looks, then the slow ones)
Float Property Slow = 30.0 Auto           ; (seconds between looks while it simply stands open)
Int Property MostWaits = 6 Auto           ; (someone else standing in the doorway: it closes anyway after this many looks)

Bool PlayerHasIt = False
Int Looks = 0
Int Waits = 0

Event OnOpen(ObjectReference akActionRef)
	PlayerHasIt = akActionRef == Game.GetPlayer()
	Looks = 0
	Waits = 0
	If PlayerHasIt
		UnregisterForUpdate()
	Else
		RegisterForSingleUpdate(Quick)
	EndIf
EndEvent

Event OnClose(ObjectReference akActionRef)
	PlayerHasIt = False
	UnregisterForUpdate()
EndEvent

Bool Function Asleep()
	; GetSleepState: 2 lying down to sleep, 3 asleep (0 awake, 1 wants to sleep, 4 waking)
	If !Sleeper || Sleeper.IsDead() || Sleeper.IsDisabled()
		Return False
	EndIf
	Int s = Sleeper.GetSleepState()
	Return s == 2 || s == 3
EndFunction

Event OnUpdate()
	If PlayerHasIt || GetOpenState() != 1 || !Is3DLoaded()
		Return
	EndIf
	Looks += 1
	If Asleep()
		Actor near = Game.FindClosestActorFromRef(self, Doorway)
		If near && near != Sleeper && Waits < MostWaits
			Waits += 1
		Else
			SetOpen(False)
			Return
		EndIf
	EndIf
	If Looks < QuickLooks
		RegisterForSingleUpdate(Quick)
	Else
		RegisterForSingleUpdate(Slow)
	EndIf
EndEvent

; the hall loaded again: a door left open is looked at again (its updates stop while the hall is unloaded)
Event OnCellAttach()
	If !PlayerHasIt && GetOpenState() == 1
		Looks = QuickLooks
		Waits = 0
		RegisterForSingleUpdate(Quick)
	EndIf
EndEvent

Event OnCellDetach()
	UnregisterForUpdate()
EndEvent
