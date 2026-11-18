Scriptname AGHallTravel extends Quest
{The Guild Hall's travel quest: AGHallDoor calls GoInTo, GoOut and GoOutVia, which move the player - and the followers
beside them - in and out of the hall. (The test tools of the hall's first builds were removed 2026-11-13: the DLL places
the hall.)}

Form Property MarkerBase Auto                 ; XMarkerHeading
Actor Property PlayerRef Auto

ObjectReference OutMarker                     ; where the player comes back out

; game yaw turns clockwise seen from above: a local (lx, ly) offset at angle a (degrees) -> world dx, dy
float Function RotX(float lx, float ly, float a)
	Return lx * Math.Cos(a) + ly * Math.Sin(a)
EndFunction

float Function RotY(float lx, float ly, float a)
	Return -lx * Math.Sin(a) + ly * Math.Cos(a)
EndFunction

Function Travel(ObjectReference akTarget)
	Actor[] found = AGHallNative.Teammates()
	Actor[] party = new Actor[16]
	int n = 0
	int k = 0
	String moved = ""
	String waiting = ""
	While k < found.Length && n < 16
		Actor a = found[k]
		If a && a.GetActorValue("WaitingForPlayer") <= 0.0
			party[n] = a
			n += 1
			moved += " " + a.GetDisplayName() + ";"
		ElseIf a
			waiting += " " + a.GetDisplayName() + ";"
		EndIf
		k += 1
	EndWhile
	PlayerRef.MoveTo(akTarget)
	float ang = akTarget.GetAngleZ()
	int j = 0
	While j < n
		float lx = 60.0
		If j % 2 == 0
			lx = -60.0
		EndIf
		float ly = 110.0 + 60.0 * (j / 2)
		party[j].MoveTo(akTarget, RotX(lx, ly, ang), RotY(lx, ly, ang), 0.0)
		j += 1
	EndWhile
	Debug.Trace("AGHallTravel: moved the player and " + n + " teammate(s) to " + akTarget + " (" + found.Length + " found; moved:" + moved + " waiting:" + waiting + ")")
EndFunction

Function GoInTo(ObjectReference akTarget)
	; the way back out is where the player came in (only an outside door calls this), facing away from the door: the
	; hall the DLL places has no exit of the first test build's kind (2026-10-25, the walkable interior behind the front door). A door
	; names its own target (a save could keep a shared landing point where an earlier build had put it)
	If !OutMarker
		OutMarker = PlayerRef.PlaceAtMe(MarkerBase, 1, true, false)
	EndIf
	OutMarker.MoveTo(PlayerRef)
	OutMarker.SetAngle(0.0, 0.0, PlayerRef.GetAngleZ() + 180.0)
	Travel(akTarget)
EndFunction

Function GoOut()
	If OutMarker
		Travel(OutMarker)
	EndIf
EndFunction

; out through the outside door of record akDoorBase (the one the DLL placed): 120 in front of it, facing away, whichever
; door the player came in by. The doors' outside is their local -y. None placed: as GoOut, and with no way back known either
; (a save that never built the hall, the player brought in by a teleport) by the foot of that door's stair: the hall is
; placed once its cells load round the player, and then they are moved on to its door.
Function GoOutVia(Form akDoorBase)
	ObjectReference d = AGHallNative.HallRef(akDoorBase)
	If !d && OutMarker
		GoOut()
		Return
	ElseIf !d
		If !ToStairFoot(akDoorBase)
			Return
		EndIf
		d = WaitForDoor(akDoorBase)
		If !d
			Return                                ; not placed in time: they stay on the land at the stair's foot
		EndIf
	EndIf
	; (the first exit by the back door turned them round to face it, later ones did not) the first
	; time, the marker comes from far off (the front door, where GoInTo left it), and the door's turn that MoveTo gave it
	; landed after our SetAngle: it moves now without taking the door's turn, and is turned before and after the move
	If !OutMarker
		OutMarker = d.PlaceAtMe(MarkerBase, 1, true, false)
	EndIf
	float a = d.GetAngleZ()
	OutMarker.SetAngle(0.0, 0.0, a + 180.0)
	OutMarker.MoveTo(d, RotX(0.0, -120.0, a), RotY(0.0, -120.0, a), 20.0, false)
	OutMarker.SetAngle(0.0, 0.0, a + 180.0)
	Travel(OutMarker)
EndFunction

; the foot of akDoorBase's stair, on the land, facing up it (the forecourt and steps are the hall's own pieces: nothing to stand
; on before it is placed). The marker gets there by an offset from a persistent reference: the cell is not loaded yet
bool Function ToStairFoot(Form akDoorBase)
	float[] f = AGHallNative.HallWayOut(akDoorBase)
	If f.Length < 4
		Return false
	EndIf
	ObjectReference anchor = AGHallNative.HallAnchor(f[0], f[1])
	If !anchor
		Return false
	EndIf
	If !OutMarker
		OutMarker = PlayerRef.PlaceAtMe(MarkerBase, 1, true, false)
	EndIf
	OutMarker.SetAngle(0.0, 0.0, f[3])
	OutMarker.MoveTo(anchor, f[0] - anchor.GetPositionX(), f[1] - anchor.GetPositionY(), f[2] + 50.0 - anchor.GetPositionZ(), false)
	OutMarker.SetAngle(0.0, 0.0, f[3])
	Travel(OutMarker)
	Return true
EndFunction

; the outside door, once the DLL has placed it and its model is in (up to 10 s of game time), or None
ObjectReference Function WaitForDoor(Form akDoorBase)
	int i = 0
	While i < 40
		ObjectReference d = AGHallNative.HallRef(akDoorBase)
		If d && d.Is3DLoaded()
			Utility.Wait(0.5)                     ; the stonework round it, placed in the same pass, settles too
			Return d
		EndIf
		Utility.Wait(0.25)
		i += 1
	EndWhile
	Debug.Trace("AGHallTravel: " + akDoorBase + " was not placed within 10 s of reaching its stair foot")
	Return None
EndFunction
