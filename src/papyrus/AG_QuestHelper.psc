ScriptName AG_QuestHelper Hidden
{Called by AdventurersGuild.dll through a Papyrus static call: quest objective display has no native
CommonLib equivalent.}

Function StartRegistrationQuest(Quest akQuest) Global
	If !akQuest || akQuest.IsCompleted()
		Return
	EndIf
	If !akQuest.IsRunning()
		akQuest.Start()
	EndIf
	akQuest.SetStage(10)
	akQuest.SetObjectiveDisplayed(10)
EndFunction

Function CompleteRegistrationQuest(Quest akQuest) Global
	If !akQuest || !akQuest.IsRunning()
		Return  ; registered without ever seeing a board notice: nothing to close
	EndIf
	akQuest.SetObjectiveCompleted(10)
	akQuest.SetStage(100)
EndFunction

; Missives' own "withdraw a posted, unaccepted missive" step (its board script does exactly this on a
; refresh: stage 0 -> SetStage(110)). Used to take down postings above the player's guild rank that
; were put up before the rank gate applied (e.g. on a save from before Adventurers Guild).
Function WithdrawMissive(Quest akQuest) Global
	If akQuest && akQuest.IsRunning() && akQuest.GetStage() == 0
		akQuest.SetStage(110)
	EndIf
EndFunction

; Take a posted missive from the guild counter exactly as if the player had picked its note off the board:
; the note moves from the board container into the player's inventory, and Missives' own note alias script
; (_M_AliasMissiveScript / _M_AliasMissiveDeliverScript, OnContainerChanged) accepts the quest. The board
; and the counter stay in sync because there is only one note.
Function AcceptMissive(Quest akQuest) Global
	If !akQuest || !akQuest.IsRunning() || akQuest.GetStage() != 0
		Return
	EndIf
	ReferenceAlias noteAlias = akQuest.GetAliasByName("Missive") as ReferenceAlias
	ReferenceAlias boardAlias = akQuest.GetAliasByName("MissiveBoard") as ReferenceAlias
	ObjectReference note = None
	If noteAlias
		note = noteAlias.GetReference()
	EndIf
	If !note
		Debug.Trace("AG_QuestHelper.AcceptMissive: " + akQuest + " has no Missive note")
		Return
	EndIf
	ObjectReference board = None
	If boardAlias
		board = boardAlias.GetReference()
	EndIf
	If board && board.GetItemCount(note) > 0
		board.RemoveItem(note, 1, true, Game.GetPlayer())
	Else
		Game.GetPlayer().AddItem(note, 1, true)
	EndIf
EndFunction

; The Notice Board SE: take a posted notice from the guild counter exactly as if the player had read it off the
; board. The note moves from the boards' shared container to the player, and the quest goes to stage 10, which is
; what the mod's own note script (manny_up_QuestNoteController.OnRead) does when the note is read at stage 0.
Function AcceptNotice(Quest akQuest, String asNoteAlias, ObjectReference akBoard) Global
	If !akQuest || !akQuest.IsRunning() || akQuest.GetStage() != 0
		Return
	EndIf
	ReferenceAlias noteAlias = akQuest.GetAliasByName(asNoteAlias) as ReferenceAlias
	ObjectReference note = None
	If noteAlias
		note = noteAlias.GetReference()
	EndIf
	If !note
		Debug.Trace("AG_QuestHelper.AcceptNotice: " + akQuest + " has no note in alias " + asNoteAlias)
		Return
	EndIf
	If akBoard && akBoard.GetItemCount(note) > 0
		akBoard.RemoveItem(note, 1, true, Game.GetPlayer())
	EndIf
	If akQuest.GetStage() == 0
		akQuest.SetStage(10)
	EndIf
EndFunction

; The Notice Board SE: take down a notice that is posted but was never taken (stage 0, its note still on the board).
; The note leaves the board the way the mod's own quests remove theirs (board.RemoveItem(note)), and the quest is
; stopped; the boards try to start it again each time one loads, and the rank condition decides whether it goes up.
Function WithdrawNotice(Quest akQuest, String asNoteAlias, ObjectReference akBoard) Global
	If !akQuest || !akQuest.IsRunning() || akQuest.GetStage() != 0
		Return
	EndIf
	ReferenceAlias noteAlias = akQuest.GetAliasByName(asNoteAlias) as ReferenceAlias
	ObjectReference note = None
	If noteAlias
		note = noteAlias.GetReference()
	EndIf
	If !note || !akBoard || akBoard.GetItemCount(note) < 1
		Return
	EndIf
	akBoard.RemoveItem(note, 1, true)
	akQuest.Stop()
EndFunction

; The Notice Board SE: what its board script does when a board's cell loads (manny_up_noticeboardScript.OnCellAttach),
; run when the guild counter opens, so a notice the player has just become eligible for is posted without a walk to
; a board first. A quest that cannot start (its own conditions, or the rank gate) simply stays stopped.
Function PostNotices(FormList akQuests) Global
	If !akQuests
		Return
	EndIf
	Int i = akQuests.GetSize()
	While i > 0
		i -= 1
		Quest q = akQuests.GetAt(i) as Quest
		If q && !q.IsRunning()
			q.Start()
		EndIf
	EndWhile
EndFunction

; Guild intel (counter > Services > Intel): put a dungeon's map marker on the map, as a rumour or a courier
; note would - visible, not fast-travelable until the player actually finds it.
Function RevealMarker(ObjectReference akMarker) Global
	If akMarker
		akMarker.AddToMap(false)
	EndIf
EndFunction
