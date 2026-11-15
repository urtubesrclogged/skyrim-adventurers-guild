;/ Caralion's quest, The Golden Hand (plans/caralion-quest.md). Every stage is set here,
   from the aliases' events and the dialogue's fragments (AGHallCaralionTIF), never by stage fragments:
   10 started (AGHallCaralionWatchScript) - Caralion walks up to the player in the hall and complains (C1)
   20 the hall scene (Willem's contract W1, Caralion's last word C2)
   25 Willem's word (W3, his force-greet): "One troll head coming right up." (W3a) or walking away
      from it places Vohd; "Anything I should be worried about?" (W3q) answers and offers both again
   30 Vohd placed at the lair (AG_Native.PlaceInTamriel: no record in a vanilla cell) - objective 10, kill Vohd
   40 Vohd dead - objective 20, take his head
   50 the head taken: Caralion and his sellswords placed at the ambush spots, calm; he walks up (his force-greet, C4),
      the player's "Come and take it." gets his order to his men (C5), and the talk's end (or walking away) starts the
      fight. He is put at the player's level, and puts on whatever of his Cloudrest armor is
      still in his chest in room 5: only here, never before
   60 Caralion beaten (essential, so he yields from bleedout); his men stop with him; his force-greet (Q4). Walking away
      from it without choosing condemns him
   65 spared (he leaves Skyrim) / 66 condemned (no longer protected) - objective 30, the head to Willem
   70 back to Willem; 80 the ambush told (W2t); 100 the head handed in (W2): the Guild's contract paid /;
ScriptName AGHallCaralionQuestScript Extends Quest

ReferenceAlias Property CaralionAlias Auto
ReferenceAlias Property WillemAlias Auto
ReferenceAlias Property VohdAlias Auto
ReferenceAlias Property HeadAlias Auto
ReferenceAlias Property LairAlias Auto
ReferenceAlias[] Property SellswordAliases Auto
ReferenceAlias[] Property AmbushAliases Auto
ActorBase Property VohdBase Auto
ActorBase Property SellswordBase Auto
MiscObject Property HeadItem Auto
ObjectReference Property Anchor Auto
Faction Property GoldenHand Auto
Scene Property ChallengeScene Auto
Topic Property ShoutTopic Auto
Form Property XMarker Auto
GlobalVariable Property GoneGlobal Auto
Float[] Property LairSpot Auto
Float[] Property AmbushSpots Auto
Int Property LevelsAbovePlayer = 10 Auto
Armor[] Property CloudrestArmor Auto
ObjectReference Property CaralionChest Auto

Int VohdLevel = 0
Bool WalkAway = False
Bool Attacked = False
Bool Fought = False
Bool Gone = False
Actor CondemnedRef = None
Bool SceneStarted = False
Float WillemBy = 0.0

; SkyrimNet (optional; all three inert without SkyrimNet.esp). (In testing: after the scene SkyrimNet
; had Willem answer Caralion on its own, so his force-greet never came; while its talk ran, SkyrimNet dropped the voice of
; Willem's word, "Dropping suppressed line".) For each scripted talk Caralion and Willem are in SkyrimNet's own blacklist
; faction (skyrimnet_filter_factions.yaml: "NPCs in these SkyrimNet factions are always ... blocked"), so it starts no
; talk of its own for them. (HoldPackages, the first try, left Caralion standing on his package: 6d56843, replaced.)
Faction Function NetBlacklist()
	If Game.GetModByName("SkyrimNet.esp") == 255
		Return None
	EndIf
	Return Game.GetFormFromFile(0x0012DB, "SkyrimNet.esp") as Faction   ; SkyrimNet_ActorBlacklistFaction
EndFunction

Function NetHold(Actor a)
	Faction f = NetBlacklist()
	If a && f
		a.AddToFaction(f)
		If SkyrimNetApi.IsHoldingPackages(a, "AdventurersGuild")   ; (a hold left by 6d56843)
			SkyrimNetApi.ReleaseHeldPackages(a, "AdventurersGuild")
		EndIf
	EndIf
EndFunction

Function NetRelease(Actor a)
	Faction f = NetBlacklist()
	If a && f
		a.RemoveFromFaction(f)
	EndIf
	; a hold left by 6d56843 on a save played with it
	If a && Game.GetModByName("SkyrimNet.esp") != 255 && SkyrimNetApi.IsHoldingPackages(a, "AdventurersGuild")
		SkyrimNetApi.ReleaseHeldPackages(a, "AdventurersGuild")
	EndIf
EndFunction

Function NetQuiet()
	If Game.GetModByName("SkyrimNet.esp") != 255
		SkyrimNetApi.PurgeDialogue(False)
	EndIf
EndFunction

Function Begin()
	SetStage(10)
	NetHold(CaralionAlias.GetActorRef())
	NetHold(WillemAlias.GetActorRef())
	CaralionAlias.GetActorRef().EvaluatePackage()
	Actor w = WillemAlias.GetActorRef()
	If w
		w.EvaluatePackage()   ; he follows Caralion from here (AGHallCaralionPkgWillemFollow), out of his bed or chair
		w.SheatheWeapon()     ; (he would come over mid-training, sword out)
	EndIf
EndFunction

; C1r said (its fragment): the scene once Willem is beside them (both must be ready and present),
; then Vohd once it ends. Caralion holds where he stands (stage 20); Willem has had his follow package since stage 10
Function Challenged()
	If GetStage() != 10
		Return
	EndIf
	SetStage(20)
	CaralionAlias.GetActorRef().EvaluatePackage()
	Actor w = WillemAlias.GetActorRef()
	If w
		w.EvaluatePackage()
	EndIf
	WillemBy = Utility.GetCurrentRealTime() + 25.0
	RegisterForSingleUpdate(0.5)
EndFunction

; Willem beside Caralion, in the same cell, free to speak
Bool Function WillemReady(Actor w, Actor c)
	Return w && c && !w.IsDead() && w.GetParentCell() == c.GetParentCell() && w.GetDistance(c) < 400.0 && !w.IsInCombat()
EndFunction

Event OnUpdate()
	Int stage = GetStage()
	If stage == 20 && !SceneStarted
		Actor w = WillemAlias.GetActorRef()
		Actor c = CaralionAlias.GetActorRef()
		If WillemReady(w, c) || Utility.GetCurrentRealTime() > WillemBy
			If w && c && !WillemReady(w, c)
				; 25 s and still not here (another cell, held up): he steps in beside Caralion, a pace to his side
				; (moved onto Caralion's own spot, he stood inside him)
				Float a = c.GetAngleZ() + 90.0
				w.MoveTo(c, 90.0 * Math.Sin(a), 90.0 * Math.Cos(a), 0.0, True)
				w.EvaluatePackage()
			EndIf
			If w
				w.SheatheWeapon()
			EndIf
			SceneStarted = True
			ChallengeScene.Start()
			RegisterForSingleUpdate(2.0)
		Else
			RegisterForSingleUpdate(0.5)
		EndIf
	ElseIf stage == 20
		If ChallengeScene.IsPlaying()
			RegisterForSingleUpdate(2.0)
		Else
			; the scene over: Willem turns to the player (his force-greet at 25); Caralion goes back to his day
			NetQuiet()
			SetStage(25)
			Actor w = WillemAlias.GetActorRef()
			If w
				w.EvaluatePackage()
			EndIf
			CaralionAlias.GetActorRef().EvaluatePackage()
		EndIf
	ElseIf stage == 25 && WalkAway
		Accepted()
	ElseIf stage == 50 && WalkAway
		Attack()
	ElseIf stage == 60 && WalkAway
		Condemned()
	ElseIf stage == 60
		; while he pleads, his men and the player's followers keep still (otherwise they fight on
		; while the player is held in the talk of his surrender)
		StandDown()
		If WalkAway
			RegisterForSingleUpdate(2.0)   ; the talk closed while this ran: the walk-away check keeps its 2 s (a spare lands first)
		Else
			RegisterForSingleUpdate(0.5)
		EndIf
	ElseIf CondemnedRef && !Fought
		; condemned: once the talk is closed and he is up from his bleedout, he fights on. Checked until he is in combat:
		; (he was not hostile until struck again) a StartCombat while the talk was still open
		; was dropped, and the old check never tried again
		If CondemnedRef.IsDead()
			Fought = True
		ElseIf CondemnedRef.IsInCombat()
			Fought = True
		Else
			If !CondemnedRef.IsBleedingOut() && !UI.IsMenuOpen("Dialogue Menu")
				CondemnedRef.SetActorValue("Aggression", 1)
				CondemnedRef.StartCombat(Game.GetPlayer())
			EndIf
			RegisterForSingleUpdate(1.0)
		EndIf
	ElseIf GetStageDone(65) && !Gone
		Leave()
	EndIf
EndEvent

Function PlaceVohd()
	If GetStage() >= 30
		Return
	EndIf
	ObjectReference lair = AG_Native.PlaceInTamriel(XMarker, LairSpot[0], LairSpot[1], LairSpot[2], LairSpot[3])
	LairAlias.ForceRefTo(lair)
	Actor v = Anchor.PlaceAtMe(VohdBase, 1, True, True) as Actor
	VohdAlias.ForceRefTo(v)
	ScaleVohd(v)
	ObjectReference h = Anchor.PlaceAtMe(HeadItem, 1, True, False)
	HeadAlias.ForceRefTo(h)
	v.AddItem(h, 1, True)
	v.MoveTo(lair)
	v.Enable()
	SetStage(30)
	SetObjectiveDisplayed(10)
EndFunction

; an elite at the player's level + 10, scaled from the troll's own values by that level against its own
Function ScaleVohd(Actor v)
	Int own = v.GetLevel()
	VohdLevel = Game.GetPlayer().GetLevel() + LevelsAbovePlayer
	If own < 1
		own = 1
	EndIf
	Float k = (VohdLevel as Float) / (own as Float)
	If k > 1.0
		v.SetActorValue("DamageResist", v.GetBaseActorValue("DamageResist") * k)
		v.SetActorValue("UnarmedDamage", v.GetBaseActorValue("UnarmedDamage") * k)
	EndIf
	; health on vanilla's boss curve at its level (the old x2.6 was far too easy: it gave 1,214 at
	; level 58, a level-36 creature's: vanilla's Draugr Deathlord boss has 2,310 at 45, about 50 a level)
	Float hp = 50.0 * (VohdLevel as Float)
	If hp > v.GetBaseActorValue("Health")
		v.SetActorValue("Health", hp)
	EndIf
	AG_Native.SetUniqueLevel(VohdBase, VohdLevel)
EndFunction

Function VohdDied()
	If GetStage() != 30
		Return
	EndIf
	SetObjectiveCompleted(10)
	SetObjectiveDisplayed(20)
	SetStage(40)
EndFunction

Function HeadTaken()
	If GetStage() >= 50
		Return
	EndIf
	If GetStage() < 40
		VohdDied()
	EndIf
	SetObjectiveCompleted(20)
	SetStage(50)
	Ambush()
EndFunction

; Caralion and his sellswords at the hall session's ambush spots (the player is at the lair, so their cells are loaded)
Function Ambush()
	Actor player = Game.GetPlayer()
	Int n = AmbushAliases.Length
	If n > 3
		n = 3
	EndIf
	ObjectReference[] spots = new ObjectReference[3]
	Int i = 0
	While i < n
		spots[i] = AG_Native.PlaceInTamriel(XMarker, AmbushSpots[i * 4], AmbushSpots[i * 4 + 1], AmbushSpots[i * 4 + 2], AmbushSpots[i * 4 + 3])
		AmbushAliases[i].ForceRefTo(spots[i])
		i += 1
	EndWhile
	Actor c = CaralionAlias.GetActorRef()
	c.MoveTo(spots[0])
	PutOnArmor(c)
	ScaleCaralion(c)
	; his men in place, not yet hostile: the fight starts when the talk ends (Attack)
	i = 0
	While i < SellswordAliases.Length
		Actor m = Anchor.PlaceAtMe(SellswordBase, 1, True, True) as Actor
		SellswordAliases[i].ForceRefTo(m)
		m.SetActorValue("Aggression", 0)   ; TG02's mercenary is very aggressive (2): it would attack before the talk
		m.MoveTo(spots[(i + 1) % n])
		m.Enable(True)
		i += 1
	EndWhile
	NetHold(c)
	c.EvaluatePackage()   ; his force-greet (C4): he walks up to the player
EndFunction

; C4's begin (AGHallCaralionTIF): the talk is open; its close without the reply starts the fight all the same
Function WatchAmbushTalk()
	NetQuiet()
	RegisterForMenu("Dialogue Menu")
EndFunction

; C5's end, or walking away from C4: the Golden Hand attacks
Function Attack()
	WalkAway = False
	If Attacked || GetStage() != 50
		Return
	EndIf
	Attacked = True
	NetRelease(CaralionAlias.GetActorRef())
	Actor player = Game.GetPlayer()
	GoldenHand.SetPlayerEnemy(True)
	Int i = 0
	While i < SellswordAliases.Length
		Actor m = SellswordAliases[i].GetActorRef()
		If m && !m.IsDead()
			m.SetActorValue("Aggression", 1)
			m.StartCombat(player)
		EndIf
		i += 1
	EndWhile
	CaralionAlias.GetActorRef().StartCombat(player)
EndFunction

; (he went down in a single hit, and was still far too easy after a first fix): his level is the player's by his
; record (the player-level multiplier, as vanilla's leveled uniques), so the game works out his spellsword's skills and
; health at it; the old run-time level change raised the number only (One-Handed 34 and 134 health at level 48). Here he
; takes healing potions for the fight, vanilla's best-by-level list
Function ScaleCaralion(Actor c)
	Form potions = Game.GetFormFromFile(0x065A45, "Skyrim.esm")   ; LItemPotionRestoreHealthBest
	If potions
		c.AddItem(potions, 3, True)
	EndIf
EndFunction

; his family's ebony plate, from his chest: each piece still there (one the player stole stays missing). Moved, not
; copied: spared, he leaves Skyrim wearing it; killed, it is on his body, his to loot. ("== None" on an array
; is a cast error in Papyrus; the pieces and the chest are looked up in this plugin when the properties are empty)
Function PutOnArmor(Actor c)
	Armor[] pieces = CloudrestArmor
	If !pieces || pieces.Length == 0
		pieces = new Armor[4]
		Int k = 0
		While k < 4
			pieces[k] = Game.GetFormFromFile(0x9600 + k, "AdventurersGuild - Guild Hall.esp") as Armor
			k += 1
		EndWhile
	EndIf
	ObjectReference chest = CaralionChest
	If !chest
		chest = Game.GetFormFromFile(0x0A19, "AdventurersGuild - Guild Hall.esp") as ObjectReference
	EndIf
	If !chest
		Return
	EndIf
	; (measured on a test save: the chest counted 0 of each piece until its contents were first touched,
	; then 1 more than added; a gold coin added and taken back made the game count what the chest holds)
	Form coin = Game.GetForm(0xF)
	chest.AddItem(coin, 1, True)
	chest.RemoveItem(coin, 1, True)
	Int i = 0
	While i < pieces.Length
		Armor a = pieces[i]
		If a && chest.GetItemCount(a) > 0
			chest.RemoveItem(a, 1, True, c)
			c.EquipItem(a, False, True)
		EndIf
		i += 1
	EndWhile
EndFunction

; Caralion's bleedout (he is protected until he yields): he yields, and his men with him
Function Yielded()
	If GetStage() != 50
		Return
	EndIf
	SetStage(60)
	GoldenHand.SetPlayerEnemy(False)
	StandDown()
	Actor c = CaralionAlias.GetActorRef()
	c.StopCombat()
	NetHold(c)
	c.EvaluatePackage()
	RegisterForSingleUpdate(0.5)   ; StandDown again every half second while he pleads (OnUpdate, stage 60)
EndFunction

; his men stop and the player's followers with them: once is not enough (a follower still swinging puts a man back in the
; fight, and he answers), so it is repeated while he pleads. Followers are found in the player's cell, as AGHallTravel's
; Travel finds them
Function StandDown()
	Actor player = Game.GetPlayer()
	Int i = 0
	While i < SellswordAliases.Length
		Actor m = SellswordAliases[i].GetActorRef()
		If m && !m.IsDead()
			m.SetActorValue("Aggression", 0)
			If m.IsInCombat()
				m.StopCombat()
			EndIf
		EndIf
		i += 1
	EndWhile
	Cell here = player.GetParentCell()
	If here
		Int count = here.GetNumRefs(62)   ; 62 = actors (ACHR)
		Int k = 0
		While k < count
			Actor a = here.GetNthRef(k, 62) as Actor
			If a && a != player && a.IsPlayerTeammate() && a.IsInCombat()
				a.StopCombat()
			EndIf
			k += 1
		EndWhile
	EndIf
	player.StopCombatAlarm()
EndFunction

; Q4's begin (AGHallCaralionTIF): the menu is open; its close without a choice condemns him. The check waits 2 s, so a
; spare or condemn fragment at the very end of the talk lands first (its own update then replaces this one)
Function WatchWalkAway()
	NetQuiet()
	RegisterForMenu("Dialogue Menu")
EndFunction

Event OnMenuClose(String menuName)
	If menuName != "Dialogue Menu"
		Return
	EndIf
	UnregisterForMenu("Dialogue Menu")
	Int stage = GetStage()
	If stage == 60 || stage == 25 || stage == 50
		WalkAway = True
		RegisterForSingleUpdate(2.0)
	EndIf
EndEvent

; W3's begin (AGHallCaralionTIF): Willem's window is open; its close without "One troll head coming right up." starts the
; hunt all the same. The check waits 2 s, so W3a's fragment lands first
Function WatchWillemWord()
	NetQuiet()
	RegisterForMenu("Dialogue Menu")
EndFunction

; W3a's end, or walking away from Willem's word: Vohd placed, the hunt on (30)
Function Accepted()
	WalkAway = False
	If GetStage() != 25
		Return
	EndIf
	NetRelease(CaralionAlias.GetActorRef())
	NetRelease(WillemAlias.GetActorRef())
	PlaceVohd()
EndFunction

; the player's choice (AGHallCaralionTIF): spared, he leaves Skyrim for good; condemned, his protection lifts
Function Spared()
	WalkAway = False
	NetRelease(CaralionAlias.GetActorRef())
	SetStage(65)
	GoneGlobal.SetValue(1)
	AG_Native.LeaderBoardEndRival(2)
	ToWillem()
	RegisterForSingleUpdate(6.0)
EndFunction

Function Condemned()
	WalkAway = False
	If GetStage() >= 65
		Return
	EndIf
	SetStage(66)
	Actor c = CaralionAlias.GetActorRef()
	NetRelease(c)
	CaralionAlias.Clear()   ; no longer essential (the alias is optional, so it clears); his death ends the Golden Hand
	CondemnedRef = c
	c.SetActorValue("Aggression", 1)
	; his men fight on for him
	Actor player = Game.GetPlayer()
	GoldenHand.SetPlayerEnemy(True)
	Int i = 0
	While i < SellswordAliases.Length
		Actor m = SellswordAliases[i].GetActorRef()
		If m && !m.IsDead()
			m.SetActorValue("Aggression", 1)
			m.StartCombat(player)
		EndIf
		i += 1
	EndWhile
	ToWillem()
	RegisterForSingleUpdate(1.0)   ; he joins them once up from his bleedout (OnUpdate)
EndFunction

; spared: he and his men go, each disabled only once the player cannot see him (not vanishing
; in plain sight), checked every second until all are gone
Function Leave()
	Actor player = Game.GetPlayer()
	Bool left = True
	Actor c = CaralionAlias.GetActorRef()
	If c
		If c.IsEnabled() && (player.HasLOS(c) && player.GetDistance(c) < 4000.0)
			left = False
		Else
			CaralionAlias.Clear()
			c.Disable()
		EndIf
	EndIf
	Int i = 0
	While i < SellswordAliases.Length
		Actor m = SellswordAliases[i].GetActorRef()
		If m && !m.IsDead() && m.IsEnabled()
			If player.HasLOS(m) && player.GetDistance(m) < 4000.0
				left = False
			Else
				m.Disable()
			EndIf
		EndIf
		i += 1
	EndWhile
	If left
		Gone = True
	Else
		RegisterForSingleUpdate(1.0)
	EndIf
EndFunction

Function ToWillem()
	SetObjectiveDisplayed(30)
	SetStage(70)
EndFunction

Function Told()
	If GetStage() == 70
		SetStage(80)
	EndIf
EndFunction

Function HandedIn()
	Actor player = Game.GetPlayer()
	ObjectReference h = HeadAlias.GetReference()
	If h
		player.RemoveItem(h, 1, True)
	Else
		player.RemoveItem(HeadItem, 1, True)
	EndIf
	AG_Native.PayGuildContract(GetName())
	SetObjectiveCompleted(30)
	Int i = 0
	While i < SellswordAliases.Length
		Actor m = SellswordAliases[i].GetActorRef()
		If m
			m.Disable()
			m.Delete()
		EndIf
		i += 1
	EndWhile
	SetStage(100)
EndFunction

; each load: Vohd's level again (a base's data is not saved)
Function GameLoaded()
	Actor v = VohdAlias.GetActorRef()
	If VohdLevel > 0 && v && !v.IsDead()
		AG_Native.SetUniqueLevel(VohdBase, VohdLevel)
	EndIf
EndFunction
