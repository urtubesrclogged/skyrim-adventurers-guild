;/ Compile-time declarations only: CHIM's AIAgentFunctions (optional; only called by CHIM itself, through AGChim), trimmed
   to the members this mod's scripts call (CHIM AIAgent/Source/Scripts/AIAgentFunctions.psc). The installed mod's own
   script is what runs; this mod does not ship it. /;
Scriptname AIAgentFunctions Hidden

Int Function logMessageForActor(String a_msg, String type, String npc) Global Native
Actor Function getAgentByName(String npcName) Global Native
