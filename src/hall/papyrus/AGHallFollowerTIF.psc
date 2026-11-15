;/ The three adventurers' follower choices, done as other follower mods do them: in the hall's own
   follower quest as Sofia, Inigo and Lucien keep theirs, so no dialogue mod that ties vanilla's follower lines to exact
   voice types can hide them. Each fragment does what vanilla's own line in that topic does (Skyrim.esm's TIF__ sources),
   through vanilla's follower quest, so Nether's Follower Framework and the like still take over. /;
ScriptName AGHallFollowerTIF Extends TopicInfo Hidden

Quest Property pDialogueFollower Auto
Faction Property DismissedFollowerFaction Auto
; their road helmet (it fills the gap in their outfits), worn only while following: on at recruiting,
; off and put away at dismissal, so they stay bareheaded in the hall as their outfits and Ghrulek's bio have it
Armor Property Helmet Auto

; "Follow me. I need your help." (vanilla TIF__000D8DE2 and kin)
Function Fragment_Recruit(ObjectReference akSpeakerRef)
	Actor who = akSpeakerRef as Actor
	(pDialogueFollower as DialogueFollowerScript).SetFollower(who)
	If Helmet && who
		If who.GetItemCount(Helmet) == 0
			who.AddItem(Helmet, 1, true)
		EndIf
		who.EquipItem(Helmet, false, true)
	EndIf
EndFunction

; "Follow me." after a wait (TIF__000D8DB3)
Function Fragment_Follow(ObjectReference akSpeakerRef)
	(pDialogueFollower as DialogueFollowerScript).FollowerFollow()
EndFunction

; "Wait here." (TIF__000D8E1C)
Function Fragment_Wait(ObjectReference akSpeakerRef)
	(pDialogueFollower as DialogueFollowerScript).FollowerWait()
EndFunction

; "I need to trade some things with you." (TIF__000D8DC1)
Function Fragment_Trade(ObjectReference akSpeakerRef)
	(akSpeakerRef as Actor).OpenInventory()
EndFunction

; "I need you to do something." (TIF__000D8DC6)
Function Fragment_FavorStart(ObjectReference akSpeakerRef)
	(akSpeakerRef as Actor).SetDoingFavor()
EndFunction

; "No. Never mind." out of the favor (TIF__000D8E18)
Function Fragment_FavorEnd(ObjectReference akSpeakerRef)
	(akSpeakerRef as Actor).SetDoingFavor(false)
EndFunction

; "It's time for us to part ways." (TIF__000D8DD4)
Function Fragment_Dismiss(ObjectReference akSpeakerRef)
	Actor who = akSpeakerRef as Actor
	If !who.IsInFaction(DismissedFollowerFaction)
		(pDialogueFollower as DialogueFollowerScript).DismissFollower(0, 0)
	EndIf
	If Helmet && who && who.GetItemCount(Helmet) > 0   ; the one helmet recruiting gave them, not one the player handed over
		who.UnequipItem(Helmet, false, true)
		who.RemoveItem(Helmet, 1, true)
	EndIf
EndFunction
