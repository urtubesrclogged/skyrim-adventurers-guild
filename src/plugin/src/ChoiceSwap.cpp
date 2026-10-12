// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "ChoiceSwap.h"

#include "Adventurers.h"

#include <nlohmann/json.hpp>

#include <atomic>
#include <fstream>
#include <unordered_map>

// Show Guild Card without a single vanilla record in the plugin.
//
// The game builds the list of things the player can say by calling one routine once for every topic that is to be
// offered, from two places (one for the choices that follow a line, one for the top of a conversation). This file puts
// itself in front of those two calls: when the topic about to be offered is one of the vanilla choices the card stands
// in for (a gate guard's Persuade, the robber's Intimidate) and one of our replies would be said to this speaker, the
// topic of our own is offered in its place. Otherwise the call goes through untouched.
//
// What that buys over the first design (our replies added to the vanilla topic, which needs a copy of the topic record
// in the plugin): nothing of another mod's or of a translation is overridden, and the choice reads as ours.
//
// Credit: that the choice list is built this way, and where the two calls are, was learned from Dynamic Dialogue
// Replacer by KrisV-777 (GPL-3.0, https://github.com/KrisV-777/Dynamic-Dialogue-Replacer). The code here is our own.
namespace AG::ChoiceSwap
{
	namespace
	{
		constexpr std::string_view kPlugin = "AdventurersGuild.esp";

		// the routine's shape: the menu's manager, the topic to offer, the topic it follows, and one more value passed on as it came
		using Offer = std::int64_t(RE::MenuTopicManager*, RE::TESTopic*, RE::TESTopic*, std::uint64_t);

		std::unordered_map<RE::FormID, RE::TESTopic*> g_swaps;  // a vanilla choice -> the topic of ours offered in its place
		Offer*                                        g_game[2]{ nullptr, nullptr };
		std::atomic<int>                              g_said{ 0 };

		// Would the speaker have a reply of ours? A topic's lines each carry their own conditions (who, which rank, the card).
		bool HasReply(RE::TESTopic* a_ours, RE::TESObjectREFR* a_speaker)
		{
			auto* pc = RE::PlayerCharacter::GetSingleton();
			if (!a_ours || !a_speaker || !pc || !a_ours->topicInfos) return false;
			for (std::uint32_t i = 0; i < a_ours->numTopicInfos; ++i)
				if (auto* line = a_ours->topicInfos[i]; line && line->objConditions.IsTrue(a_speaker, pc)) return true;
			return false;
		}

		RE::TESTopic* Choose(RE::MenuTopicManager* a_menu, RE::TESTopic* a_topic)
		{
			if (!a_menu || !a_topic) return a_topic;
			const auto it = g_swaps.find(a_topic->GetFormID());
			if (it == g_swaps.end()) return a_topic;
			const auto speaker = a_menu->speaker.get();
			if (!HasReply(it->second, speaker.get())) return a_topic;
			if (g_said.fetch_add(1) < 10)
				SKSE::log::info("ChoiceSwap: {} is offered in place of {:08X} (speaker {:08X})", it->second->GetFormEditorID() ? it->second->GetFormEditorID() : "our topic",
					a_topic->GetFormID(), speaker ? speaker->GetFormID() : 0);
			return it->second;
		}

		// What the game would have to work with for a topic of ours: per reply, whether its conditions pass and how many
		// of its spoken parts have words (the game drops a choice whose reply has none). Only for the log.
		std::string Describe(RE::TESTopic* a_ours, RE::TESObjectREFR* a_speaker)
		{
			auto* pc = RE::PlayerCharacter::GetSingleton();
			std::string out = std::format("text \"{}\", quest {:08X}{}, {} replies", a_ours->GetFullName() ? a_ours->GetFullName() : "",
				a_ours->ownerQuest ? a_ours->ownerQuest->GetFormID() : 0, a_ours->ownerQuest && a_ours->ownerQuest->IsRunning() ? " (running)" : " (NOT running)", a_ours->numTopicInfos);
			for (std::uint32_t i = 0; i < a_ours->numTopicInfos && a_ours->topicInfos; ++i) {
				auto* line = a_ours->topicInfos[i];
				if (!line) continue;
				RE::TESTopicInfo::TESResponseList list{ nullptr };
				line->GetResponseList(&list);
				int parts = 0, worded = 0;
				for (auto* r = list.head; r; r = r->next) {
					++parts;
					if (!r->responseText.empty()) ++worded;
				}
				out += std::format("; {:08X}: conditions {}, {} part(s), {} with words, flags {:04X}, said once {}", line->GetFormID(),
					a_speaker && pc && line->objConditions.IsTrue(a_speaker, pc) ? "pass" : "fail", parts, worded,
					static_cast<unsigned>(line->data.flags.underlying()), line->saidOnce);
			}
			return out;
		}

		// Our topic is offered; if the game will not have it (it answers 0: nothing was added), the vanilla choice is
		// offered as it would have been, so a choice is never lost, and the log says what the game was given.
		// (Seen at the Riften gate, 2026-10-12: "(Persuade)" gone and nothing in its place.)
		std::int64_t Offered(int a_site, RE::MenuTopicManager* a_menu, RE::TESTopic* a_topic, RE::TESTopic* a_after, std::uint64_t a_more)
		{
			auto* ours = Choose(a_menu, a_topic);
			const auto added = g_game[a_site](a_menu, ours, a_after, a_more);
			if (ours == a_topic || added) return added;
			static std::atomic<int> said{ 0 };
			if (said.fetch_add(1) < 6)
				SKSE::log::warn("ChoiceSwap: the game would not list {} in place of {:08X} - the vanilla choice is offered instead. What it was given: {}",
					ours->GetFormEditorID() ? ours->GetFormEditorID() : "our topic", a_topic->GetFormID(), Describe(ours, a_menu ? a_menu->speaker.get().get() : nullptr));
			return g_game[a_site](a_menu, a_topic, a_after, a_more);
		}

		std::int64_t First(RE::MenuTopicManager* a_menu, RE::TESTopic* a_topic, RE::TESTopic* a_after, std::uint64_t a_more)
		{
			return Offered(0, a_menu, a_topic, a_after, a_more);
		}

		std::int64_t Second(RE::MenuTopicManager* a_menu, RE::TESTopic* a_topic, RE::TESTopic* a_after, std::uint64_t a_more)
		{
			return Offered(1, a_menu, a_topic, a_after, a_more);
		}

		RE::TESQuest* dh_quest()
		{
			auto* dh = RE::TESDataHandler::GetSingleton();
			return dh ? dh->LookupForm<RE::TESQuest>(0x8C0, kPlugin) : nullptr;  // AG_WorldDialogueQuest
		}

		// where a 5-byte call at a_site goes, or 0 when what is there is not such a call
		std::uintptr_t CallTarget(std::uintptr_t a_site)
		{
			const auto* p = reinterpret_cast<const std::uint8_t*>(a_site);
			if (p[0] != 0xE8) return 0;
			std::int32_t rel;
			std::memcpy(&rel, p + 1, 4);
			return a_site + 5 + static_cast<std::intptr_t>(rel);
		}
	}

	void Install()
	{
		// which vanilla choices, and which topics of ours: written by the plugin builder
		try {
			std::ifstream f("Data/SKSE/Plugins/AdventurersGuild/dialogue.resolved.json");
			if (!f) return;
			const auto j = nlohmann::json::parse(f, nullptr, true, true);
			auto*      dh = RE::TESDataHandler::GetSingleton();
			for (auto& s : j.value("choiceSwaps", nlohmann::json::array())) {
				auto* vanilla = Adventurers::FormOfKey(s.value("vanilla", ""));
				auto* ours = dh ? dh->LookupForm<RE::TESTopic>(static_cast<RE::FormID>(std::stoul(s.value("ours", "0"), nullptr, 16)), kPlugin) : nullptr;
				if (vanilla && vanilla->As<RE::TESTopic>() && ours) g_swaps[vanilla->GetFormID()] = ours;
				else SKSE::log::warn("ChoiceSwap: a pair does not resolve ({})", s.dump());
			}
		} catch (const std::exception& e) {
			SKSE::log::error("ChoiceSwap: dialogue.resolved.json error: {}", e.what());
			return;
		}
		if (g_swaps.empty()) return;

		// A topic of ours that stands in for a choice has no branch (nobody is to reach it any other way), and the game
		// gives a player topic its quest through its branch: these arrive with NO quest, whatever their record says.
		// The game will not list a topic without one (found at the Riften gate, 2026-10-12: the swap fired, the game
		// listed nothing, and the log line read "quest 00000000"). So the quest is set here: the world dialogue quest
		// they are written under. Their replies are evaluated, spoken and their voice files named by it.
		if (auto* quest = dh_quest()) {
			int set = 0;
			for (auto& [vanilla, ours] : g_swaps)
				if (!ours->ownerQuest) {
					ours->ownerQuest = quest;
					++set;
				}
			if (set) SKSE::log::info("ChoiceSwap: {} topic(s) given their quest ({})", set, quest->GetFormEditorID() ? quest->GetFormEditorID() : "the world dialogue quest");
		} else {
			SKSE::log::warn("ChoiceSwap: the world dialogue quest is not in {} - the Show Guild Card choices that stand in for a vanilla one are off", kPlugin);
			g_swaps.clear();
			return;
		}

		// The two places, by the game's function numbers (SE, AE) or its address (VR), and how far into each the call is.
		// Nothing is changed unless both are exactly what is expected: a direct call, and both to the same routine. On a
		// game version where that is not so, Show Guild Card's swapped choices are off and everything else is as it was.
		const std::uintptr_t site[2]{
			REL::Relocation<std::uintptr_t>{ REL::VariantID(34460, 35287, 0x05766F0) }.address() + REL::Relocate<std::ptrdiff_t>(0xFA, 0x154),
			REL::Relocation<std::uintptr_t>{ REL::VariantID(34477, 35304, 0x05778D0) }.address() + REL::Relocate<std::ptrdiff_t>(0x79, 0x6C),
		};
		const std::uintptr_t to[2]{ CallTarget(site[0]), CallTarget(site[1]) };
		if (!to[0] || to[0] != to[1]) {
			SKSE::log::warn("ChoiceSwap: this game version is not laid out as expected (calls go to {:X} and {:X}, relative to the game's base) - the Show Guild Card choices that stand in for a vanilla one are off; nothing else is affected",
				to[0] ? to[0] - REL::Module::get().base() : 0, to[1] ? to[1] - REL::Module::get().base() : 0);
			return;
		}
		auto& tr = SKSE::GetTrampoline();
		g_game[0] = reinterpret_cast<Offer*>(tr.write_call<5>(site[0], reinterpret_cast<std::uintptr_t>(&First)));
		g_game[1] = reinterpret_cast<Offer*>(tr.write_call<5>(site[1], reinterpret_cast<std::uintptr_t>(&Second)));
		SKSE::log::info("ChoiceSwap: {} vanilla choice(s) can be stood in for (the routine is at base+0x{:X})", g_swaps.size(), to[0] - REL::Module::get().base());
	}
}
