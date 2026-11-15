;/ The basement's archery practice (schedules.json "archery"): the bow is handed over only for the practice,
   so it never shows at the counter. Fragments of the practice package (a copy of
   Sky Haven's archery, which shoots with the weapon already in hand): on begin, a hunting bow and arrows, equipped; on
   end or change, both taken back. For trainees who carry no bow of their own: the end takes every bow and arrow of
   these kinds. /;
ScriptName PF_AGHallPracticeBow Extends Package Hidden

Weapon Property Bow Auto
Ammo Property Arrows Auto
Int Property ArrowCount = 24 Auto

; begin
Function Fragment_0(Actor akActor)
	If akActor.GetItemCount(Bow) == 0
		akActor.AddItem(Bow, 1, True)
		akActor.AddItem(Arrows, ArrowCount, True)
	EndIf
	akActor.EquipItem(Bow, False, True)
	akActor.EquipItem(Arrows, False, True)
EndFunction

; end, and change (a schedule handing over to the next package)
Function Fragment_1(Actor akActor)
	akActor.RemoveItem(Bow, akActor.GetItemCount(Bow), True)
	akActor.RemoveItem(Arrows, akActor.GetItemCount(Arrows), True)
EndFunction
