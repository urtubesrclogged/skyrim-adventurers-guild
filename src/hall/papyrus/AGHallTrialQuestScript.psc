;/ The promotion trials (tools/hall-private/plans/promotion-trial.md; npcs/trial_quests.json):
   five quests, Rank D Trial to Rank S Trial, each running this script with its own creature, spot and trophy. Every stage
   is set here, from the dialogue's fragments (AGHallTrialTIF) and the aliases' events, never by stage fragments:
   10 the clerk sends the player to Willem (Begin) - objective 10, speak to Willem
   15 Rank S only: Willem has no trial worthy of S until Dragon Rising is done (NotYet); objective 10 stays
   20 Willem's brief: the creature placed at its spot (AG_Native.PlaceInTamriel), its trophy in its inventory - objective 20
   30 the creature dead - objective 30, collect the trophy
   40 the trophy taken - objective 40, bring it to Willem
   50 Willem takes it (HandedIn) - objective 50, the card at the Guild Hall
   100 the clerk promotes (Promoted: AG_Native.TrialPromote, the promotion without a fee)
   While the creature is meant to be out there (20) and is gone without being killed (another mod, a cell reset), a new
   one is placed at the spot once the player comes near it (no "I lost it" line). Turning the
   MCM's Promotion Trials off stops a running trial (the DLL calls Cancel) and takes the creature and trophy away. /;
ScriptName AGHallTrialQuestScript Extends Quest

Int Property RankIndex Auto                 ; 1 D ... 5 S: the rank this trial is for
ActorBase Property CreatureBase Auto        ; our own unique copy of a vanilla creature
ActorBase Property HeadlessBase Auto        ; the hagraven's body once her head is taken (as vanilla's Glenmoril witches), else None
MiscObject Property TrophyItem Auto
Float Property ArmorAdd = 0.0 Auto          ; Damage Resist added at spawn
Float[] Property Spot Auto                  ; x, y, z, angle in Tamriel
ObjectReference Property Anchor Auto        ; under the hall's floor: where the creature is made, disabled, before it moves
Form Property XMarker Auto
GlobalVariable Property IntroGlobal Auto    ; 1 once Willem has explained the trials (his intro plays on the first only)
ReferenceAlias Property CreatureAlias Auto
ReferenceAlias Property TrophyAlias Auto
ReferenceAlias Property SpotAlias Auto

Float Property NearSpot = 6000.0 Auto       ; how near the player comes before a missing creature is placed again

Function Begin()
	If GetStage() >= 10
		Return
	EndIf
	SetStage(10)
	SetObjectiveDisplayed(10)
EndFunction

Function NotYet()
	If GetStage() == 10
		SetStage(15)
	EndIf
EndFunction

Function Briefed()
	Int s = GetStage()
	If s != 10 && s != 15
		Return
	EndIf
	IntroGlobal.SetValue(1)
	PlaceCreature()
	SetObjectiveCompleted(10)
	SetObjectiveDisplayed(20)
	SetStage(20)
	RegisterForSingleUpdate(10.0)
EndFunction

Function PlaceCreature()
	ObjectReference spotRef = SpotAlias.GetReference()
	If !spotRef
		spotRef = AG_Native.PlaceInTamriel(XMarker, Spot[0], Spot[1], Spot[2], Spot[3])
		SpotAlias.ForceRefTo(spotRef)
	EndIf
	SetLevel()
	Actor c = Anchor.PlaceAtMe(CreatureBase, 1, True, True) as Actor
	CreatureAlias.ForceRefTo(c)
	If ArmorAdd > 0.0
		c.ModActorValue("DamageResist", ArmorAdd)
	EndIf
	ObjectReference t = TrophyAlias.GetReference()
	If !t
		t = Anchor.PlaceAtMe(TrophyItem, 1, True, False)
		TrophyAlias.ForceRefTo(t)
	EndIf
	c.AddItem(t, 1, True)
	c.MoveTo(spotRef)
	c.Enable()
EndFunction

; the creature's level is the rank's own (MCM > the S level moves B and A): a base's data is not saved, so again each load
Function SetLevel()
	AG_Native.SetUniqueLevel(CreatureBase, AG_Native.GetRankLevel(RankIndex))
EndFunction

Function GameLoaded()
	If GetStage() >= 20 && GetStage() < 100
		SetLevel()
	EndIf
	If GetStage() == 20
		RegisterForSingleUpdate(10.0)
	EndIf
EndFunction

Event OnUpdate()
	If GetStage() != 20
		Return
	EndIf
	Actor c = CreatureAlias.GetActorRef()
	If !c || c.IsDisabled() || c.IsDeleted()
		ObjectReference spotRef = SpotAlias.GetReference()
		If spotRef && Game.GetPlayer().GetDistance(spotRef) < NearSpot
			If c
				c.Delete()
			EndIf
			CreatureAlias.Clear()
			PlaceCreature()
		EndIf
	ElseIf c.IsDead()
		CreatureDied()
		Return
	EndIf
	RegisterForSingleUpdate(10.0)
EndEvent

Function CreatureDied()
	If GetStage() != 20
		Return
	EndIf
	SetObjectiveCompleted(20)
	SetObjectiveDisplayed(30)
	SetStage(30)
EndFunction

Function TrophyTaken()
	If GetStage() >= 40
		Return
	EndIf
	If GetStage() < 30
		CreatureDied()
	EndIf
	SetObjectiveCompleted(30)
	SetObjectiveDisplayed(40)
	SetStage(40)
	If HeadlessBase
		Headless()
	EndIf
EndFunction

; her body as vanilla's Glenmoril witches': the headless one in its place, with what she carried
Function Headless()
	Actor body = CreatureAlias.GetActorRef()
	If !body
		Return
	EndIf
	Actor h = body.PlaceAtMe(HeadlessBase, 1, False, True) as Actor
	If !h
		Return
	EndIf
	h.MoveTo(body)
	h.Enable()
	h.KillSilent()
	body.RemoveAllItems(h, False, True)
	CreatureAlias.Clear()
	body.Disable()
	body.Delete()
EndFunction

Function HandedIn()
	If GetStage() != 40
		Return
	EndIf
	ObjectReference t = TrophyAlias.GetReference()
	TrophyAlias.Clear()
	If t
		Game.GetPlayer().RemoveItem(t, 1, True)
	Else
		Game.GetPlayer().RemoveItem(TrophyItem, 1, True)
	EndIf
	SetObjectiveCompleted(40)
	SetObjectiveDisplayed(50)
	SetStage(50)
EndFunction

Function Promoted()
	If GetStage() != 50
		Return
	EndIf
	AG_Native.TrialPromote()
	SetObjectiveCompleted(50)
	SetStage(100)
	Tidy()
	Stop()
EndFunction

; what the trial put into the world: the spot's marker; a body is left to the game, as vanilla leaves its kills
Function Tidy()
	ObjectReference spotRef = SpotAlias.GetReference()
	SpotAlias.Clear()
	CreatureAlias.Clear()
	If spotRef
		spotRef.Delete()
	EndIf
EndFunction

; MCM > Promotion Trials off (the DLL calls this on a running trial): the trial ends, its creature (alive) and trophy go,
; and the player may promote at once
Function Cancel()
	Int s = GetStage()
	If s < 10 || s >= 100
		Return
	EndIf
	Actor c = CreatureAlias.GetActorRef()
	If c && !c.IsDead()
		c.Disable()
		c.Delete()
	EndIf
	ObjectReference t = TrophyAlias.GetReference()
	TrophyAlias.Clear()
	If t
		; carried by the player, or still in the creature (gone above), or loose where it fell
		Game.GetPlayer().RemoveItem(t, 1, True)
		t.Delete()
	EndIf
	Tidy()
	Stop()
EndFunction
