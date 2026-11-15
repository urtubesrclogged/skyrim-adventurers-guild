Scriptname AGHallBoardRotate extends ObjectReference
{The guild board's postings rotate: three boards on one spot (the board session's variants A, B and C), one shown at a
time. The design is one a day; Hourly rotates them on the hour, for
testing. On a marker beside the board: the boards themselves are disabled in turn, and a disabled reference's
own events do not run.}

ObjectReference Property BoardA Auto
ObjectReference Property BoardB Auto
ObjectReference Property BoardC Auto
Bool Property Hourly = True Auto

Event OnCellAttach()
	Pick()
EndEvent

Event OnCellDetach()
	UnregisterForUpdateGameTime()
EndEvent

Event OnUpdateGameTime()
	Pick()
EndEvent

; the board for this hour (or day), and a single update at the next boundary (a hair after it)
Function Pick()
	Float t = Utility.GetCurrentGameTime()
	Float unit = t
	If Hourly
		unit = t * 24.0
	EndIf
	Int k = (unit as Int) % 3
	Show(BoardA, k == 0)
	Show(BoardB, k == 1)
	Show(BoardC, k == 2)
	Float left = 1.0 - (unit - (unit as Int)) + 0.01
	If !Hourly
		left = left * 24.0
	EndIf
	RegisterForSingleUpdateGameTime(left)
EndFunction

Function Show(ObjectReference r, Bool on)
	If !r
		Return
	EndIf
	If on
		r.Enable()
	Else
		r.Disable()
	EndIf
EndFunction
