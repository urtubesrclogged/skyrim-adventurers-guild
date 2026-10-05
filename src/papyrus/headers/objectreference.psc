;/ Compile-time declarations only: the game's ObjectReference script, trimmed to the members this mod's scripts call.
   The game's own script is what runs. /;
ScriptName ObjectReference Extends Form Hidden

Function AddItem(Form akItemToAdd, Int aiCount = 1, Bool abSilent = False) native
Int Function GetItemCount(Form akItem = None) native
Function RemoveItem(Form akItemToRemove, Int aiCount = 1, Bool abSilent = False, ObjectReference akOtherContainer = None) native
Function AddToMap(Bool abAllowFastTravel = False) native
