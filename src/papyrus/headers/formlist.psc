;/ Compile-time declarations only: the game's FormList script, trimmed to the members this mod's scripts call.
   The game's own script is what runs. /;
ScriptName FormList Extends Form Hidden

Int Function GetSize() Native
Form Function GetAt(Int aiIndex) Native
