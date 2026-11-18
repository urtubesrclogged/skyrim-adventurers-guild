;/ The followers' contracts away from the hall (tools/hall-private/npcs/SCHEDULES.md "Away on contract"):
   Ghrulek, Ylva and Zhasim each go out on a contract for two days a week, leaving at 08:00 on their own weekday and coming back
   at 08:00 two days later, never two at once (Ghrulek Morndas, Ylva Middas, Zhasim Fredas; Sundas everyone is home).
   Nobody vanishes in front of the player: someone leaves or comes back only while the player is not in the hall's cells, or
   as the Sleep/Wait menu closes (the time passed unseen). A follower travelling with the player, one dead, or one in a fight
   stays; one who is not in the hall when the contract starts (left somewhere by the player) is not taken from there.
   While one is away their global is 1: the clerks answer "Have you seen ...?" and the absence idles play (away_dialogue.json).
   The weekday is the calendar's (AG_Native.DayOfWeek, 0 Sundas ... 6 Loredas), its hour the GameHour global.
   Each leaving, coming back, and staying because they travel with the player is written to the Papyrus log.
   The same timer frees the hall's people from ambient conversation scenes that never end (AGHallNative.StuckScenes): a scene
   whose partner left holds them for good, its packages in place of their schedule. /;
ScriptName AGHallAwayScript Extends Quest

Actor[] Property Folk Auto                 ; Ghrulek, Ylva, Zhasim
GlobalVariable[] Property AwayGlobals Auto  ; 1 while each is away
ObjectReference[] Property HomeMarkers Auto ; where each comes back to: their own bunk's marker
Int[] Property LeaveDays Auto              ; the weekday each leaves: 1 Morndas, 3 Middas, 5 Fredas
Cell[] Property HallCells Auto              ; the hall's cells: the main hall, the basement, the strongroom
GlobalVariable Property GameHour Auto
Actor[] Property HallFolk Auto             ; everyone who lives or works in the hall

Bool[] stayed                               ; told the log this contract that one stays with the player

Event OnInit()
	Listen()
EndEvent

Function Listen()
	RegisterForMenu("Sleep/Wait Menu")
	RegisterForSingleUpdateGameTime(0.25)
EndFunction

Event OnUpdateGameTime()
	FreeStuck()
	Check(False)
	RegisterForSingleUpdateGameTime(0.5)
EndEvent

Event OnMenuClose(String asMenuName)
	If asMenuName == "Sleep/Wait Menu"
		FreeStuck()
		Check(True)
	EndIf
EndEvent

Bool Function PlayerInHall()
	Cell here = Game.GetPlayer().GetParentCell()
	Int i = 0
	While i < HallCells.Length
		If here && here == HallCells[i]
			Return True
		EndIf
		i += 1
	EndWhile
	Return False
EndFunction

; away from Day 08:00 to Day + 2 at 08:00
Bool Function IsAway(Int aiDay, Float afHour, Int aiLeave)
	Int d = (aiDay - aiLeave + 7) % 7
	Return (d == 0 && afHour >= 8.0) || d == 1 || (d == 2 && afHour < 8.0)
EndFunction

Function FreeStuck()
	If !HallFolk
		Return
	EndIf
	Scene[] stuck = AGHallNative.StuckScenes(HallFolk)
	Int i = 0
	While i < stuck.Length
		Scene s = stuck[i]
		If s
			Quest q = s.GetOwningQuest()
			Debug.Trace("AGHallAway: stopped " + s + " of " + q + ", which held one of the hall's people past its time")
			s.Stop()
			If q && q.IsRunning()
				q.Stop()
			EndIf
		EndIf
		i += 1
	EndWhile
EndFunction

Function Check(Bool abUnseen)
	If !abUnseen && PlayerInHall()
		Return
	EndIf
	Int day = AG_Native.DayOfWeek()
	If day < 0
		Return
	EndIf
	Float hour = GameHour.GetValue()
	If !stayed
		stayed = new Bool[8]
	EndIf
	Int i = 0
	While i < Folk.Length
		Actor a = Folk[i]
		If a
			Bool away = IsAway(day, hour, LeaveDays[i])
			If away && AwayGlobals[i].GetValue() < 1
				If !a.IsDead() && !a.IsDisabled() && !a.IsPlayerTeammate() && !a.IsInCombat() && InHall(a)
					a.Disable()
					AwayGlobals[i].SetValue(1)
					Debug.Trace("AGHallAway: " + a.GetDisplayName() + " left on the contract")
				ElseIf a.IsPlayerTeammate() && !stayed[i]
					stayed[i] = True
					Debug.Trace("AGHallAway: " + a.GetDisplayName() + " stays: travelling with the player")
				EndIf
			ElseIf !away && AwayGlobals[i].GetValue() >= 1
				a.MoveTo(HomeMarkers[i])
				a.Enable()
				AwayGlobals[i].SetValue(0)
				Debug.Trace("AGHallAway: " + a.GetDisplayName() + " came back to the hall")
			ElseIf !away
				stayed[i] = False
			EndIf
		EndIf
		i += 1
	EndWhile
EndFunction

Bool Function InHall(Actor akWho)
	Cell c = akWho.GetParentCell()
	If !c
		Return True   ; in a cell that is not loaded, which is where the hall is while the player is away: nobody sees them go
	EndIf
	Int i = 0
	While i < HallCells.Length
		If c && c == HallCells[i]
			Return True
		EndIf
		i += 1
	EndWhile
	Return False
EndFunction
