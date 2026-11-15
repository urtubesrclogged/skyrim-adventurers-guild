;/ Compile-time declarations only: the game's Game script, trimmed to the members this mod's scripts call.
   The game's own script is what runs. /;
ScriptName Game Hidden

Actor Function GetPlayer() native global
Actor Function FindClosestActorFromRef(ObjectReference arCenter, Float afRadius) native global
