;/ Compile-time declarations only: the game's Alias script, trimmed to the members this mod's scripts call.
   The game's own script is what runs. /;
ScriptName Alias Hidden

Quest Function GetOwningQuest() Native
Function RegisterForModEvent(String eventName, String callbackFunctionName) Native

Event OnInit()
EndEvent

Event OnPlayerLoadGame()
EndEvent
