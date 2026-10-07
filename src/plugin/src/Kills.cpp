// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "Kills.h"
#include "Adventurers.h"
#include <chrono>
#include <thread>

#include "Guild.h"
#include "Party.h"
#include "RankCore.h"

namespace AG::Kills
{
	namespace
	{
		// Location ref types that mark a dungeon's boss: Skyrim.esm Boss, Dragonborn.esm DLC2Boss1.
		std::vector<RE::BGSLocationRefType*> g_boss;

		// TESDeathEvent fires twice per death (dying, then dead); credit the victim once.
		std::deque<RE::FormID> g_recent;

		// Last time the player's side (you, a follower, your summon) hit each foe, for assist credit when someone
		// else - a guard, a bystander, a fall - finishes it. Main thread only (hit and death events).
		using Clock = std::chrono::steady_clock;
		std::unordered_map<RE::FormID, Clock::time_point> g_lastHit;

		// A dungeon's boss. Vanilla also tags a settlement's owner (innkeeper, shopkeeper, jarl) with the same Boss
		// ref type for radiant quests, so it only counts inside a clearable location.
		bool IsBoss(RE::Actor* a_victim)
		{
			const auto* x = a_victim->extraList.GetByType<RE::ExtraLocationRefType>();
			if (!x || !x->locRefType || std::ranges::find(g_boss, x->locRefType) == g_boss.end()) return false;
			auto* loc = a_victim->GetCurrentLocation();
			return loc && (loc->HasKeywordString("LocTypeClearable") || loc->HasKeywordString("LocTypeDungeon"));
		}

		bool OnPlayerSide(RE::Actor* a_actor, RE::PlayerCharacter* a_pc)
		{
			return a_actor == a_pc || a_actor->IsPlayerTeammate();
		}

		// Share of the credit the killer earns the player: 1 for the player, followerShare for a follower or a
		// summon/reanimation commanded by the player's side, 0 for anyone else.
		float ShareFor(RE::Actor* a_killer, RE::PlayerCharacter* a_pc, float a_followerShare)
		{
			if (!a_killer) return 0.0f;
			if (a_killer == a_pc) return 1.0f;
			if (a_killer->IsPlayerTeammate()) return a_followerShare;
			if (a_killer->IsCommandedActor()) {
				const auto boss = a_killer->GetCommandingActor();
				if (boss && OnPlayerSide(boss.get(), a_pc)) return a_followerShare;
			}
			return 0.0f;
		}

		// the attacker counts as the player's side: you, a follower, or anything either of you commands
		bool PlayerSideAttacker(RE::Actor* a_attacker, RE::PlayerCharacter* a_pc)
		{
			return ShareFor(a_attacker, a_pc, 1.0f) > 0.0f;
		}

		// assistShare if the player's side hit a_victim within assistSeconds, else 0
		float AssistShare(RE::Actor* a_victim, const Guild::KillRewards& a_k)
		{
			const auto it = g_lastHit.find(a_victim->GetFormID());
			if (it == g_lastHit.end()) return 0.0f;
			const auto age = std::chrono::duration<float>(Clock::now() - it->second).count();
			return age <= a_k.assistSeconds ? a_k.assistShare : 0.0f;
		}

		// Reputation for a_victim at a_share of full credit; 0 and a reason when it does not count.
		float Value(RE::Actor* a_victim, float a_share, std::string& a_why)
		{
			auto* pc = RE::PlayerCharacter::GetSingleton();
			if (!a_victim || !pc || a_victim == pc) return a_why = "not a foe", 0.0f;
			if (a_victim->IsSummoned() || a_victim->IsCommandedActor()) return a_why = "summoned or reanimated", 0.0f;
			if (a_victim->IsPlayerTeammate()) return a_why = "an ally", 0.0f;
			if (!a_victim->IsHostileToActor(pc)) return a_why = "not hostile to you", 0.0f;
			const auto k = Guild::Kills();
			const int  rank = ThreatRank(a_victim);
			if (rank < 0 || rank >= kRankCount) return a_why = "no threat rank", 0.0f;
			// the biggest of: dungeon boss, or the race's engine size class (Large / Extra Large) - never multiplied together
			const bool boss = IsBoss(a_victim);
			float      mult = boss ? k.bossMultiplier : 1.0f;
			const char* size = "";
			if (auto* race = a_victim->GetRace()) {
				const auto rs = race->data.raceSize.get();
				if (rs == RE::RACE_SIZE::kExtraLarge && k.extraLargeMultiplier > mult) mult = k.extraLargeMultiplier, size = ", extra large";
				else if (rs == RE::RACE_SIZE::kLarge && k.largeMultiplier > mult) mult = k.largeMultiplier, size = ", large";
			}
			a_why = std::format("threat {}{}{}, x{}, share {}", Letter(rank), boss ? ", boss" : "", size, mult, a_share);
			return k.rep[rank] * mult * a_share;
		}

		void Credit(RE::Actor* a_victim, RE::Actor* a_killer)
		{
			auto* pc = RE::PlayerCharacter::GetSingleton();
			if (!a_victim || !pc || !Guild::Registered()) return;
			const auto k = Guild::Kills();
			float      share = ShareFor(a_killer, pc, k.followerShare);
			if (share <= 0.0f) share = AssistShare(a_victim, k);  // someone else finished what you fought
			if (share <= 0.0f) return;
			if (std::ranges::find(g_recent, a_victim->GetFormID()) != g_recent.end()) return;
			g_lastHit.erase(a_victim->GetFormID());
			g_recent.push_back(a_victim->GetFormID());
			if (g_recent.size() > 32) g_recent.pop_front();

			std::string why;
			const float rep = Value(a_victim, share, why);
			if (rep <= 0.0f) return;
			Guild::AddReputation(rep, std::format("killed {} ({})", a_victim->GetDisplayFullName(), why));
			auto* race = a_victim->GetRace();
			const bool huge = race && race->data.raceSize.get() == RE::RACE_SIZE::kExtraLarge;
			Party::OnKill(a_victim, a_killer, ThreatRank(a_victim), IsBoss(a_victim) || huge);
			Guild::CountKill(IsBoss(a_victim) || huge);
			if (IsBoss(a_victim) || huge) {
				const auto who = a_killer == RE::PlayerCharacter::GetSingleton() ? "" : " (with help)";
				Guild::Notify("AG_NotableKill", std::format("{}{}", a_victim->GetDisplayFullName(), who), static_cast<float>(ThreatRank(a_victim)));
			}
		}

		struct Sink final : RE::BSTEventSink<RE::TESDeathEvent>, RE::BSTEventSink<RE::TESHitEvent>
		{
			static Sink* Get()
			{
				static Sink s;
				return &s;
			}

			RE::BSEventNotifyControl ProcessEvent(const RE::TESDeathEvent* a_e, RE::BSTEventSource<RE::TESDeathEvent>*) override
			{
				if (!a_e || !a_e->actorDying) return RE::BSEventNotifyControl::kContinue;
				Party::OnDeath(a_e->actorDying->As<RE::Actor>());
				// an innkeeper who keeps a Guild counter: the game hands the inn to their backup from a script (a few
				// seconds), and whoever it is takes the counter over then
				if (auto* dead = a_e->actorDying->As<RE::Actor>(); dead && dead->GetActorBase() && Adventurers::IsLiaisonBase(dead->GetActorBase()->GetFormID())) {
					std::thread([] {
						for (int i = 0; i < 4; ++i) {  // at 3, 8, 15 and 30 s: the swap waits on the Papyrus VM
							std::this_thread::sleep_for(std::chrono::seconds(i == 0 ? 3 : i == 1 ? 5 : i == 2 ? 7 : 15));
							SKSE::GetTaskInterface()->AddTask([] { Guild::SyncSuccessors(); });
						}
					}).detach();
				}
				Credit(a_e->actorDying->As<RE::Actor>(), a_e->actorKiller ? a_e->actorKiller->As<RE::Actor>() : nullptr);
				return RE::BSEventNotifyControl::kContinue;
			}

			RE::BSEventNotifyControl ProcessEvent(const RE::TESHitEvent* a_e, RE::BSTEventSource<RE::TESHitEvent>*) override
			{
				if (!a_e || !a_e->target || !a_e->cause) return RE::BSEventNotifyControl::kContinue;
				auto* pc = RE::PlayerCharacter::GetSingleton();
				auto* attacker = a_e->cause->As<RE::Actor>();
				if (!pc || !attacker || !a_e->target->As<RE::Actor>() || !PlayerSideAttacker(attacker, pc)) return RE::BSEventNotifyControl::kContinue;
				const auto now = Clock::now();
				g_lastHit[a_e->target->GetFormID()] = now;
				if (g_lastHit.size() > 256) std::erase_if(g_lastHit, [&](auto& e) { return now - e.second > std::chrono::minutes(2); });
				return RE::BSEventNotifyControl::kContinue;
			}
		};
	}

	void Register()
	{
		g_boss.clear();
		if (auto* dh = RE::TESDataHandler::GetSingleton()) {
			if (auto* b = dh->LookupForm<RE::BGSLocationRefType>(0x0130F7, "Skyrim.esm")) g_boss.push_back(b);
			if (auto* b = dh->LookupForm<RE::BGSLocationRefType>(0x0206B5, "Dragonborn.esm")) g_boss.push_back(b);
		}
		RE::ScriptEventSourceHolder::GetSingleton()->AddEventSink<RE::TESDeathEvent>(Sink::Get());
		RE::ScriptEventSourceHolder::GetSingleton()->AddEventSink<RE::TESHitEvent>(Sink::Get());
		SKSE::log::info("Kills: watching deaths ({} boss ref types)", g_boss.size());
	}

	std::string DebugKill(RE::FormID a_ref)
	{
		auto* a = RE::TESForm::LookupByID<RE::Actor>(a_ref);
		if (!a) return std::format("{:08X} is not a loaded actor", a_ref);
		std::string why;
		const float rep = Value(a, 1.0f, why);
		if (rep > 0.0f) Guild::AddReputation(rep, std::format("debug kill {}", a->GetDisplayFullName()));
		return std::format("{} ({:08X}): {} Reputation - {}", a->GetDisplayFullName(), a_ref, rep, why);
	}

	std::string DebugThreat()
	{
		auto* pc = RE::PlayerCharacter::GetSingleton();
		auto* pl = RE::ProcessLists::GetSingleton();
		if (!pc || !pl) return "not in game";
		std::string out;
		for (auto& h : pl->highActorHandles) {
			const auto ptr = h.get();
			auto*      a = ptr.get();
			if (!a || a->GetPosition().GetDistance(pc->GetPosition()) > 8192.0f) continue;
			const auto t = ExplainThreat(a);
			const auto line = std::format("{:08X} {} lvl {} hp {:.0f} atk {:.0f} score {:.0f} {} -> {}{}{}", a->GetFormID(), a->GetDisplayFullName(), t.level,
				t.health, t.attack, t.score, LetterStr(t.byLevel), LetterStr(t.rank), t.why.empty() ? "" : " [" + t.why + "]", IsBoss(a) ? " BOSS" : "");
			SKSE::log::info("Threat: {}", line);
			out += line + "\n";
		}
		return out.empty() ? "no actors nearby" : out;
	}
}
