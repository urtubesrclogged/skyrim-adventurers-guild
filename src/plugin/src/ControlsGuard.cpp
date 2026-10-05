#include "ControlsGuard.h"

#include <chrono>
#include <mutex>
#include <thread>

namespace AG::ControlsGuard
{
	namespace
	{
		using UEFlag = RE::UserEvents::USER_EVENT_FLAG;
		constexpr std::uint32_t kRestorable = static_cast<std::uint32_t>(UEFlag::kMovement) | static_cast<std::uint32_t>(UEFlag::kLooking) |
		                                      static_cast<std::uint32_t>(UEFlag::kActivate) | static_cast<std::uint32_t>(UEFlag::kMenu) |
		                                      static_cast<std::uint32_t>(UEFlag::kFighting) | static_cast<std::uint32_t>(UEFlag::kSneaking) |
		                                      static_cast<std::uint32_t>(UEFlag::kMainFour) | static_cast<std::uint32_t>(UEFlag::kJumping);

		std::mutex    g_lock;
		int           g_visible = 0;
		int           g_kept = 0;  // times KeepOn had to act since the first panel appeared (logged when the last one goes)
		std::uint32_t g_before = 0;

		std::uint32_t Enabled()
		{
			auto* map = RE::ControlMap::GetSingleton();
			return map ? map->GetRuntimeData().enabledControls.underlying() : 0;
		}
	}

	void Shown()
	{
		std::lock_guard l(g_lock);
		if (g_visible++ == 0) {
			g_before = Enabled();
			g_kept = 0;
		}
	}

	void Hidden()
	{
		{
			std::lock_guard l(g_lock);
			if (g_visible == 0 || --g_visible > 0) return;
			if (g_kept) SKSE::log::info("ControlsGuard: kept player controls on {} time(s) while a notice was up", g_kept);
		}
		// PrismaUI hides on its own threads; give it a moment, then check on the game thread.
		std::thread([] {
			std::this_thread::sleep_for(std::chrono::milliseconds(300));
			SKSE::GetTaskInterface()->AddTask([] {
				auto* map = RE::ControlMap::GetSingleton();
				std::lock_guard l(g_lock);
				if (!map || g_visible > 0) return;  // one of our panels is up again: it will restore when it goes
				const auto lost = g_before & ~Enabled() & kRestorable;
				if (lost) {
					map->ToggleControls(static_cast<UEFlag>(lost), true, false);
					SKSE::log::info("ControlsGuard: player controls 0x{:X} were left off after a panel closed - turned back on (now 0x{:X})", lost, Enabled());
				}
			});
		}).detach();
	}

	void KeepOn()
	{
		auto* map = RE::ControlMap::GetSingleton();
		std::lock_guard l(g_lock);
		if (!map || g_visible == 0) return;
		const auto lost = g_before & ~Enabled() & kRestorable;
		if (lost) {
			map->ToggleControls(static_cast<UEFlag>(lost), true, false);
			++g_kept;
		}
	}
}
