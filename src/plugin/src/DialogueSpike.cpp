#include "DialogueSpike.h"

// TEMPORARY test harness for "Show Guild Card" (2026-10-10): can a plugin add a player choice to a vanilla
// conversation without overriding the vanilla line that lists the choices? The game reads an INFO's linked topics from
// the plugin file when the line is said and keeps the resulting choices in MenuTopicManager::dialogueList, so that list
// is the only place a choice can be added at runtime. Nothing here runs unless a script function below is called.
// Remove this file once the mechanism is settled (the real feature, or the ESP override, replaces it).
namespace AG::DialogueSpike
{
	namespace
	{
		using Dialogue = RE::MenuTopicManager::Dialogue;

		std::atomic<RE::FormID> g_armed{ 0 };      // a topic to add when the next line starts or ends
		std::atomic<int>        g_armedWhen{ 0 };  // 1 = as a line starts, 2 = as it ends
		std::atomic<int>        g_armedPlace{ 0 };

		struct Lock
		{
			explicit Lock(RE::MenuTopicManager* a_m) : m(a_m) { REX::W32::EnterCriticalSection(&m->criticalSection); }
			~Lock() { REX::W32::LeaveCriticalSection(&m->criticalSection); }
			RE::MenuTopicManager* m;
		};

		RE::FormID Id(const RE::TESForm* a_form) { return a_form ? a_form->GetFormID() : 0; }

		std::string DumpLocked(RE::MenuTopicManager* m)
		{
			std::string s = std::format("menuOpen={} greeting={} waiting={} root={:X} current={:X} last={:X} blocking={} topLevel={} selected={}",
				m->menuOpen, m->isGreetingPlayer, m->waitingToAdvance, Id(m->rootTopicInfo), Id(m->currentTopicInfo), Id(m->lastTopicInfo),
				m->blockingBranches.size(), m->topLevelBranches.size(), m->lastSelectedDialogue ? m->lastSelectedDialogue->topicText.c_str() : "-");
			if (!m->dialogueList) return s + "\n  (no choice list)";
			int n = 0;
			for (auto* d : *m->dialogueList) {
				if (!d) continue;
				int responses = 0;
				for (auto* r : d->responses)
					if (r) ++responses;
				s += std::format("\n  {}. \"{}\" topic={:X} info={:X} quest={:X} responses={} neverSaid={} u10={} u11={} u12={} u13={} u14={} u48={} u4A={} u4C={} u50={:X}", ++n,
					d->topicText.c_str() ? d->topicText.c_str() : "", Id(d->parentTopic), Id(d->parentTopicInfo), Id(d->parentQuest), responses, d->neverSaid, d->unk10, d->unk11,
					d->unk12, d->unk13, d->unk14, d->unk48, d->unk4A, d->unk4C, Id(d->unk50));
			}
			return s + std::format("\n  ({} choice(s))", n);
		}

		// a_place: 0 = first in the list, 1 = last
		std::string AddNow(RE::FormID a_topic, int a_place)
		{
			auto* m = RE::MenuTopicManager::GetSingleton();
			auto* topic = RE::TESForm::LookupByID<RE::TESTopic>(a_topic);
			if (!m) return "no dialogue manager";
			if (!topic) return std::format("{:X} is not a topic", a_topic);
			Lock lock(m);
			if (!m->dialogueList) return "no choice list (not in a conversation?)";
			auto speaker = m->speaker.get();
			auto* player = RE::PlayerCharacter::GetSingleton();
			RE::TESTopicInfo* info = nullptr;
			for (std::uint32_t i = 0; i < topic->numTopicInfos && !info; ++i)
				if (auto* t = topic->topicInfos[i]; t && t->objConditions.IsTrue(speaker.get(), player)) info = t;
			if (!info) return "no line of that topic passes its conditions for this speaker: the game would not offer it either";

			auto* d = static_cast<Dialogue*>(RE::malloc(sizeof(Dialogue)));
			if (!d) return "out of memory";
			std::memset(d, 0, sizeof(Dialogue));
			new (&d->topicText) RE::BSString(topic->GetFullName());
			d->parentTopic = topic;
			d->parentTopicInfo = info;
			d->parentQuest = topic->ownerQuest;
			d->neverSaid = !info->saidOnce;
			if (a_place == 0 || m->dialogueList->empty()) {
				m->dialogueList->push_front(d);
			} else {
				auto last = m->dialogueList->begin();
				for (auto it = m->dialogueList->begin(); it != m->dialogueList->end(); ++it) last = it;
				m->dialogueList->insert_after(last, d);
			}
			return std::format("added \"{}\" (line {:X}) {}\n{}", topic->GetFullName(), info->GetFormID(), a_place == 0 ? "first" : "last", DumpLocked(m));
		}
	}

	std::string Dump()
	{
		auto* m = RE::MenuTopicManager::GetSingleton();
		if (!m) return "no dialogue manager";
		Lock lock(m);
		return DumpLocked(m);
	}

	std::string Add(std::int32_t a_topic, std::int32_t a_place) { return AddNow(static_cast<RE::FormID>(a_topic), a_place); }

	std::string Arm(std::int32_t a_topic, std::int32_t a_when, std::int32_t a_place)
	{
		g_armedPlace = a_place;
		g_armedWhen = a_when;
		g_armed = static_cast<RE::FormID>(a_topic);
		return a_topic ? std::format("armed: {:X} is added as the next line {}", static_cast<RE::FormID>(a_topic), a_when == 2 ? "ends" : "starts") : "disarmed (lines are still logged until the game restarts)";
	}

	void OnInfo(bool a_begin, RE::FormID a_info)
	{
		static std::atomic<bool> watching{ false };
		const auto               topic = g_armed.load();
		if (topic) watching = true;
		if (!watching) return;
		SKSE::log::info("DialogueSpike: line {:X} {}\n{}", a_info, a_begin ? "starts" : "ends", Dump());
		if (topic && g_armedWhen == (a_begin ? 1 : 2)) {
			g_armed = 0;
			SKSE::log::info("DialogueSpike: {}", AddNow(topic, g_armedPlace));
		}
	}
}
