;/ Compile-time declarations only. /;
ScriptName ObjectReference Extends Form Hidden
Function AddItem(Form akItemToAdd, Int aiCount = 1, Bool abSilent = False) native
Int Function GetItemCount(Form akItem = None) native
Function RemoveItem(Form akItemToRemove, Int aiCount = 1, Bool abSilent = False, ObjectReference akOtherContainer = None) native
Function Enable(Bool abFadeIn = False) native
Function SetFactionOwner(Faction akFaction) native
Function Lock(Bool abLock = True, Bool abAsOwner = False) native
