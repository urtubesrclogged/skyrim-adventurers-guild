#pragma once

// TEMPORARY test harness for "Show Guild Card": see DialogueSpike.cpp. Driven from script (AG_Native.DebugDialogue*).
namespace AG::DialogueSpike
{
	std::string Dump();                                                                  // the choices on offer right now
	std::string Add(std::int32_t a_topic, std::int32_t a_place);                         // add a topic as a choice now (0 first, 1 last)
	std::string Arm(std::int32_t a_topic, std::int32_t a_when, std::int32_t a_place);    // add it as the next line starts (1) or ends (2); 0 = disarm
	void        OnInfo(bool a_begin, RE::FormID a_info);                                 // from the dialogue event sink
}
