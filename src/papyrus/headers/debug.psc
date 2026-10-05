;/ Compile-time declarations only: the game's Debug script, trimmed to the members this mod's scripts call.
   The game's own script is what runs. /;
ScriptName Debug Hidden

Function Trace(String asTextToPrint, Int aiSeverity = 0) global native
Function Notification(String asNotificationText) global native
