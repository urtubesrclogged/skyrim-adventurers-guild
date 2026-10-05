;/ Compile-time declarations only: the game's Actor script, trimmed to the members this mod's scripts call.
   The game's own script is what runs. /;
ScriptName Actor Extends ObjectReference Hidden

Bool Function HasMagicEffect(MagicEffect akEffect) native
Bool Function HasSpell(Form akForm) native
Bool Function AddSpell(Spell akSpell, Bool abVerbose = True) native
Bool Function RemoveSpell(Spell akSpell) native
Bool Function DispelSpell(Spell akSpell) native
String Function GetDisplayName() native
bool Function IsInFaction(Faction akFaction) native
