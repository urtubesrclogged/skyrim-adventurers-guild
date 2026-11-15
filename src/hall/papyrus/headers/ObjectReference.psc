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
Function MoveTo(ObjectReference akTarget, Float afXOffset = 0.0, Float afYOffset = 0.0, Float afZOffset = 0.0, Bool abMatchRotation = True) native
Function Enable(Bool abFadeIn = False) native

; spike additions (signatures as in the game's ObjectReference.psc)
Function SetPosition(Float afX, Float afY, Float afZ) native
Function SetAngle(Float afXAngle, Float afYAngle, Float afZAngle) native
Function SetScale(Float afScale) native
Bool Function IsDisabled() native
Form Function GetBaseObject() native
Float Function GetPositionX() native
Float Function GetPositionY() native
Float Function GetPositionZ() native
Function Disable(Bool abFadeOut = False) native
Function Delete() native
Bool Function PlayGamebryoAnimation(String asAnimation, Bool abStartOver = False, Float afEaseInTime = 0.0) native
Event OnActivate(ObjectReference akActionRef)
EndEvent
Event OnLoad()
EndEvent
Event OnOpen(ObjectReference akActionRef)
EndEvent
Event OnClose(ObjectReference akActionRef)
EndEvent
Int Function GetOpenState() native
Function SetOpen(Bool abOpen = True) native
Function Lock(Bool abLock = True, Bool abAsOwner = False) native
Event OnCellAttach()
EndEvent
Event OnCellDetach()
EndEvent
Cell Function GetParentCell() native
Float Function GetAngleZ() native
Float Function GetWidth() native
Float Function GetLength() native
Float Function GetDistance(ObjectReference akOther) native
