;/ Compile-time declarations only: the game's ObjectReference script, trimmed to the members this mod's scripts call.
   The game's own script is what runs. /;
ScriptName ObjectReference Extends Form Hidden

Function AddItem(Form akItemToAdd, Int aiCount = 1, Bool abSilent = False) native
Int Function GetItemCount(Form akItem = None) native
Function RemoveItem(Form akItemToRemove, Int aiCount = 1, Bool abSilent = False, ObjectReference akOtherContainer = None) native
Function AddToMap(Bool abAllowFastTravel = False) native
Function Say(Topic akTopicToSay, Actor akActorToSpeakAs = None, Bool abSpeakInPlayersHead = False) native
ObjectReference Function PlaceAtMe(Form akFormToPlace, Int aiCount = 1, Bool abForcePersist = False, Bool abInitiallyDisabled = False) native
Bool Function SetDisplayName(String asName, Bool abForce = False) native
