Scriptname AGHallNative Native Hidden
{The Guild Hall's natives, in AdventurersGuild.dll (src/plugin/src/hall). Dump to Info and the Outdoor pair are for testing
over DevBench; Teammates, HallRef, HallWayOut and HallAnchor serve the hall's doors; HallStatus, HallRebuild and HallRemove the hall itself.}

; Writes the navmeshes of the loaded Tamriel cells within aiRadius cells of (aiCellX, aiCellY) to
; SKSE/AdventurersGuildHall/navmesh_<runtime>_<x>_<y>.json, on the game's main thread. Returns where it will write.
String Function Dump(Int aiCellX, Int aiCellY, Int aiRadius) Global Native

; The result of the last Dump: its checks, one line.
String Function LastDump() Global Native

; Which navmesh triangle is under the player: navmesh, its plugins, triangle, height.
String Function Here() Global Native

; The same for every follower in the loaded area.
String Function Followers() Global Native

; The player's living teammates in the loaded area and in a cell just left, wherever they stand (AGHallTravel.Travel).
Actor[] Function Teammates() Global Native

; The ambient conversation scenes (any plugin's quests started by the Actor Dialogue event) that have held one of akFolk for
; half a game hour, which such a scene never takes unless it waits on someone who left: the caller stops them.
Scene[] Function StuckScenes(Actor[] akFolk) Global Native

; Stitches the patch SKSE/AdventurersGuildHall/<asFile> (make_patch.py) into its navmesh, in memory only, after checking
; the navmesh is the one the patch was made for. On the game's main thread; LastDump() for the result.
String Function Inject(String asFile) Global Native

; Takes the patch out again (a cell reload also does).
String Function Revert() Global Native

; What the game's own lookup resolves at a point (navmesh, triangle, closest point, the navmeshes it
; considers), at the player, and the navmesh info map's entry for a navmesh (hex form ID).
String Function EngineAt(Float afX, Float afY, Float afZ) Global Native
String Function EngineHere() Global Native
String Function Info(String asNavmesh) Global Native

; The hall's outdoor navmesh (SKSE/Plugins/AdventurersGuild/Hall/outdoor/outdoor_nav.json): whether it is fitted, and what the fit did.
String Function Outdoor() Global Native
; Whether the fit adds the navmesh info map neighbours its links need (on by default; from the next fit).
String Function OutdoorInfoLinks(Bool abOn) Global Native

; The hall the DLL places and keeps (Data/SKSE/Plugins/AdventurersGuild/Hall/hall2.json; AG's co-save holds what it placed and hid).
String Function HallStatus() Global Native
; Take the hall down and place it again from the layout file now.
String Function HallRebuild() Global Native
; Take the hall, the refs it hid and the navmesh patches out of the world (for uninstalling).
String Function HallRemove() Global Native
; The piece the DLL placed for this record (the first, if the layout has more), or None. Placed pieces are persistent,
; so this answers from inside the hall too: an inside door's way out to its outside door.
ObjectReference Function HallRef(Form akBase) Global Native
; An inside door's way out when its outside door is not placed (a save that never built the hall): the foot of the stair
; that door's landing leads down to, on the land, facing the door: [x, y, z, angle]. Empty when the layout or the outdoor
; navmesh file has no answer (the player is told the door does not open).
Float[] Function HallWayOut(Form akDoorBase) Global Native
; The nearest persistent reference of Tamriel's to a point, to MoveTo with an offset: a cell that is not loaded holds no other.
ObjectReference Function HallAnchor(Float afX, Float afY) Global Native

; The outdoor navmesh's diagnostic: "status" (the swap, entry by entry) or "watch" (60 s of navmesh counts in the log), run
; on the main thread; "last" returns the latest result.
String Function OutdoorNav(String asStep) Global Native
