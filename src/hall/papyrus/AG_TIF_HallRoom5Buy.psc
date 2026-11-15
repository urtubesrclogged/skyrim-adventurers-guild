;/ Willem sells the player Caralion's old room once Caralion is gone: the reply the
   player reaches only with the gold on them. The gold goes to Willem, the player joins AGHallRoom5Faction (room 5's bed,
   chest and whatever Caralion left are owned by it), and his double bed passes to PlayerBedOwnership, as vanilla's home
   beds are owned, so a spouse who joins on marrying sleeps in it too (one double bed, Caralion's, from the start).
   His chest opens: whatever he left in it, his Cloudrest armor if he died before his quest, is
   the player's now, through the room's faction. /;
ScriptName AG_TIF_HallRoom5Buy Extends TopicInfo Hidden

MiscObject Property Gold Auto
Int Property Price = 1000 Auto
Faction Property Room5Faction Auto
ObjectReference Property Bed Auto
Faction Property PlayerBedOwnership Auto
ObjectReference Property Chest Auto

Function Fragment_0(ObjectReference akSpeakerRef)
	Actor player = Game.GetPlayer()
	player.RemoveItem(Gold, Price, False, akSpeakerRef)
	player.AddToFaction(Room5Faction)
	Bed.SetFactionOwner(PlayerBedOwnership)
	If Chest
		Chest.Lock(False)
	EndIf
EndFunction
