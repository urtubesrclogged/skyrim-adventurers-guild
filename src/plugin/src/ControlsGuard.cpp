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
		bool          g_masked = false;      // the counter switched fighting off and owes it back
		bool          g_savedMasked = false; // the save being loaded was made in that state

		void SetFighting(bool a_on)
		{
			if (auto* map = RE::ControlMap::GetSingleton()) {
				auto& enabled = map->GetRuntimeData().enabledControls;
				if (a_on) enabled.set(UEFlag::kFighting);
				else enabled.reset(UEFlag::kFighting);
			}
		}

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

	void Mask()
	{
		if (!REL::Module::IsVR()) return;
		std::lock_guard l(g_lock);
		if (g_masked || !(Enabled() & static_cast<std::uint32_t>(UEFlag::kFighting))) return;  // already off: not ours to give back
		SetFighting(false);
		g_masked = true;
	}

	void Unmask()
	{
		std::lock_guard l(g_lock);
		if (!g_masked) return;
		g_masked = false;
		SetFighting(true);
	}

	bool Masked()
	{
		std::lock_guard l(g_lock);
		return g_masked;
	}

	void Saved(bool a_masked)
	{
		std::lock_guard l(g_lock);
		g_savedMasked = a_masked;
	}

	void OnGameLoaded()
	{
		std::lock_guard l(g_lock);
		g_masked = false;  // whatever was open before the load is gone
		if (!std::exchange(g_savedMasked, false)) return;
		if (!(Enabled() & static_cast<std::uint32_t>(UEFlag::kFighting))) {
			SetFighting(true);
			SKSE::log::info("ControlsGuard: this save was made with the guild counter open - fighting controls turned back on");
		}
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
