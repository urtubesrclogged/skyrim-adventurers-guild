;/ Compile-time declarations only: the game's Form script, trimmed to the members this mod's scripts call.
   The game's own script is what runs. /;
ScriptName Form Hidden

Function RegisterForSingleUpdate(Float afInterval) native
Function UnregisterForUpdate() native
Function RegisterForSingleUpdateGameTime(Float afInterval) native
Function UnregisterForUpdateGameTime() native

Event OnUpdate()
EndEvent

Event OnUpdateGameTime()
EndEvent

Function RegisterForModEvent(String eventName, String callbackName) Native
Int Function GetFormID() native
string Function GetWorldModelPath() native
