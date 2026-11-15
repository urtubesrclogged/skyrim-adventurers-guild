Scriptname AGHallDoor extends ObjectReference
{The Guild Hall's doors: activators, so the DLL can place the outside ones at run time. Outside it takes the player in,
inside it takes them out; AGHallTravel moves the player and their followers.}

AGHallTravel Property Travel Auto
bool Property Inside Auto
ObjectReference Property Target Auto   ; where an outside door leads (its landing point in the hall)
Form Property Outside Auto            ; an inside door's outside door (its record): out in front of that one. None: back to
                                      ; where the player came in (the hall's back door, 2026-10-26: two ways in and out)

; (the door's mesh carried its Open and Close sequences until 2026-11-01, and this played Close on every load and every use. The mesh has none now: blender/strip_door_anim.py)
Event OnActivate(ObjectReference akActionRef)
	If akActionRef != Travel.PlayerRef
		Return
	EndIf
	If Inside && Outside
		Travel.GoOutVia(Outside)
	ElseIf Inside
		Travel.GoOut()
	ElseIf Target
		Travel.GoInTo(Target)
	Else
		Debug.Trace("AGHallDoor: " + Self + " is an outside door with no Target: it leads nowhere")
	EndIf
EndEvent
