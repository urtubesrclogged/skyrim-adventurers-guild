;/ Compile-time declarations only: the game's Game script, trimmed to the members this mod's scripts call.
   The game's own script is what runs. /;
ScriptName Game Hidden

Actor Function GetPlayer() Global Native
Form Function GetFormFromFile(Int aiFormID, String asFilename) Global Native
Int Function GetModByName(String asName) Global Native
