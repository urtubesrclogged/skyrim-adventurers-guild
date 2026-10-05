;/ Compile-time declarations only: the game's Spell script, trimmed to the members this mod's scripts call.
   The game's own script is what runs. /;
ScriptName Spell Extends Form Hidden

Int Function GetNumEffects() native
MagicEffect Function GetNthEffectMagicEffect(Int aiIndex) native
Float Function GetNthEffectMagnitude(Int aiIndex) native
Int Function GetNthEffectArea(Int aiIndex) native
Int Function GetNthEffectDuration(Int aiIndex) native
