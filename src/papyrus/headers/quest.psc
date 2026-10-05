;/ Compile-time declarations only: the game's Quest script, trimmed to the members this mod's scripts call.
   The game's own script is what runs. /;
ScriptName Quest Extends Form Hidden
bool Function IsCompleted() native
bool Function IsRunning() native
Function SetObjectiveCompleted(int aiObjective, bool abCompleted = true) native
Function SetObjectiveDisplayed(int aiObjective, bool abDisplayed = true, bool abForce = false) native
bool Function SetStage(int aiStage) native
bool Function Start() native
Function Stop() native
int Function GetStage() native

; SKSE
Alias Function GetAliasByName(string name) native
