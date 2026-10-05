;/ Compile-time declarations only: the game's Form script, trimmed to the members this mod's scripts call.
   The game's own script is what runs. /;
ScriptName Form Hidden

Function RegisterForSingleUpdateGameTime(Float afInterval) native
Function UnregisterForUpdateGameTime() native

Event OnUpdateGameTime()
EndEvent
