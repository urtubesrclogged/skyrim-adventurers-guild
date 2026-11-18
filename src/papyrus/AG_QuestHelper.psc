; Adventurers Guild - Copyright (C) 2026 urtubesrclogged
; SPDX-License-Identifier: GPL-3.0-or-later (with the additional permissions in EXCEPTIONS.md). NO WARRANTY.
; Source and license: https://github.com/urtubesrclogged/skyrim-adventurers-guild

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

; 2.0: objective 10 sends the player to an inn, 20 to the Guild Hall (registration the hall's alone, MCM > Guild Hall)
Function StartRegistrationQuestFor(Quest akQuest, Bool abHall) Global
	If !akQuest || akQuest.IsCompleted()
		Return
	EndIf
	If !akQuest.IsRunning()
		akQuest.Start()
	EndIf
	akQuest.SetStage(10)
	PointRegistrationQuest(akQuest, abHall)
EndFunction

; the setting changed while the quest runs: the objective that applies is shown, the other taken away
Function PointRegistrationQuest(Quest akQuest, Bool abHall) Global
	If !akQuest || !akQuest.IsRunning() || akQuest.IsCompleted()
		Return
	EndIf
	akQuest.SetObjectiveDisplayed(10, !abHall)
	akQuest.SetObjectiveDisplayed(20, abHall)
	MarkRegistrationHall(akQuest)
EndFunction

; objective 20 shown: the Guild Hall's map marker (made by the DLL with the hall installed) fills the HallMarker alias, the
; objective's target, and goes on the map as vanilla quests put a place there: seen, not yet for fast travel until the player
; discovers it. Called again after every load, so a marker made anew is the one pointed at.
Function MarkRegistrationHall(Quest akQuest) Global
	If !akQuest || !akQuest.IsRunning() || akQuest.IsCompleted() || !akQuest.IsObjectiveDisplayed(20)
		Return
	EndIf
	ObjectReference marker = AG_Native.HallMapMarker()
	If !marker
		Return
	EndIf
	ReferenceAlias target = akQuest.GetAliasByName("HallMarker") as ReferenceAlias
	If target && target.GetReference() != marker
		target.ForceRefTo(marker)
	EndIf
	If !marker.IsMapMarkerVisible()
		marker.AddToMap()
	EndIf
EndFunction

Function CompleteRegistrationQuest(Quest akQuest) Global
	If !akQuest || !akQuest.IsRunning()
		Return  ; registered without ever seeing a board notice: nothing to close
	EndIf
	If akQuest.IsObjectiveDisplayed(20)
		akQuest.SetObjectiveCompleted(20)
	Else
		akQuest.SetObjectiveCompleted(10)
	EndIf
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

; The Guild Hall posts the holds' work (2.0): its roll, chosen by the DLL (MissiveWatch.cpp, HallRoll), run as Missives' own
; board script runs it. akStops: posted and not taken, rolled down (stage 110). akStarts: started with the hall's Missives
; board loaded, so the note lands in it. Missives for the Good Guys makes its board alias optional and creates the note
; with the quest giver: with it installed (abGoodGuys), as its own board script does, the alias is pointed at the board
; and the note put into it.
Function HallRoll(Quest[] akStarts, Quest[] akStops, ObjectReference akBoard, Bool abGoodGuys) Global
	Int i = 0
	While i < akStops.Length
		If akStops[i] && akStops[i].IsRunning() && akStops[i].GetStage() == 0
			akStops[i].SetStage(110)
		EndIf
		i += 1
	EndWhile
	Int posted = 0
	Int failed = 0
	i = 0
	While i < akStarts.Length
		Quest q = akStarts[i]
		If q && !q.IsRunning()
			If q.Start()
				posted += 1
				ReferenceAlias boardAlias = q.GetAliasByName("MissiveBoard") as ReferenceAlias
				If boardAlias && !boardAlias.GetReference()
					boardAlias.ForceRefTo(akBoard)
				EndIf
				ReferenceAlias noteAlias = q.GetAliasByName("Missive") as ReferenceAlias
				ObjectReference note = None
				If noteAlias
					note = noteAlias.GetReference()
				EndIf
				If abGoodGuys && note && boardAlias && boardAlias.GetReference() == akBoard
					akBoard.AddItem(note, 1, true)
				EndIf
			Else
				failed += 1
			EndIf
		EndIf
		i += 1
	EndWhile
	Debug.Trace("AG_QuestHelper.HallRoll: " + posted + " posted, " + failed + " could not start, " + akStops.Length + " rolled down")
EndFunction

; Take a posted missive from the guild counter exactly as if the player had picked its note off the board:
; the note moves from the board container into the player's inventory, and Missives' own note alias script
; (_M_AliasMissiveScript / _M_AliasMissiveDeliverScript, OnContainerChanged) accepts the quest. The board
; and the counter stay in sync because there is only one note.
; aiPostedStage: the stage a posting waits at on the board - 0 for Missives, 10 for Monster Hunt Missives (1.5.0)
Function AcceptMissive(Quest akQuest, Int aiPostedStage = 0) Global
	If !akQuest || !akQuest.IsRunning() || akQuest.GetStage() != aiPostedStage
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

; A Jarl's bounty (the game's own BQ01-BQ04) taken from the guild counter: exactly what the innkeeper's and the
; steward's line does (TIF__00095123: GetOwningQuest().SetStage(10)). The stage gives the letter and the map marker.
Function AcceptBounty(Quest akQuest) Global
	If akQuest && akQuest.IsRunning() && akQuest.GetStage() < 10
		akQuest.SetStage(10)
	EndIf
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

; Another adventurer's guild card (MemberCards.cpp): one copy of the card item, carrying its own name, put in their
; inventory. A reference is made, renamed as a player renames an item, and moved in; the name stays with the item
; wherever it goes after that.
; The game keeps that same reference for the item, and puts it back in the world when the item is dropped - in the
; state it had when it went in. One that went in disabled comes back disabled: the dropped card could not be seen
; (found 2026-10-12). So it is made disabled (nothing appears at their feet), sent far below the ground, switched on
; there, and only then moved into the inventory.
Function GiveMemberCard(Actor akOwner, Form akCard, String asName) Global
	If !akOwner || !akCard
		Return
	EndIf
	ObjectReference card = akOwner.PlaceAtMe(akCard, 1, False, True)
	If !card
		Debug.Trace("AG_QuestHelper.GiveMemberCard: no card could be made for " + akOwner)
		Return
	EndIf
	If asName != ""
		card.SetDisplayName(asName, True)
	EndIf
	card.MoveTo(akOwner, 0.0, 0.0, -6000.0, False)
	card.Enable(False)
	akOwner.AddItem(card, 1, True)
	AG_Native.MemberCardGiven(akOwner)
EndFunction

; Hold stamps: the representative says her line for having stamped the card (no menu: she just says it).
Function SayLine(ObjectReference akSpeaker, Topic akTopic) Global
	If akSpeaker && akTopic
		akSpeaker.Say(akTopic)
	EndIf
EndFunction

; Guild intel (counter > Services > Intel): put a dungeon's map marker on the map, as a rumour or a courier
; note would - visible, not fast-travelable until the player actually finds it.
Function RevealMarker(ObjectReference akMarker) Global
	If akMarker
		akMarker.AddToMap(false)
	EndIf
EndFunction

; The Guild Hall's "A new bounty?" (2.0): the game's own way to start a quest for a place it chooses. akEvent is the
; hall's Story Manager keyword, whose node lists the hall's copies of the four bounty quests; akTown is a hold's capital,
; which their Location alias takes from the event. True when one started (the Story Manager picks which, as the game's
; own nodes do; a hold with no target left for any of them starts none).
Bool Function StartHallBounty(Keyword akEvent, Location akTown) Global
	If !akEvent || !akTown
		Return False
	EndIf
	Return akEvent.SendStoryEventAndWait(akTown)
EndFunction

; Prepare to Uninstall: a hall bounty still running would leave its hold marked as taken (BQActiveQuest) once the
; plugin is gone, and the game would never post a bounty there again. What its stage 200 does, without the reward.
Function StopHallBounty(Quest akQuest, Keyword akTaken) Global
	If !akQuest || !akQuest.IsRunning()
		Return
	EndIf
	LocationAlias hold = akQuest.GetAliasByName("Hold") as LocationAlias
	If hold && hold.GetLocation() && akTaken
		hold.GetLocation().SetKeywordData(akTaken, 0)
	EndIf
	akQuest.Stop()
EndFunction
