// ControlsWatch: a diagnostic SKSE plugin, not part of the mod. It logs every change of the player's enabled
// controls (ControlMap) with who made it: the native call stack as module+offset, and the Papyrus stacks that are
// executing on the calling thread. Built only on request (cmake --build ... --target ControlsWatch).
#include <spdlog/sinks/basic_file_sink.h>

#include <Windows.h>

#include <intrin.h>

namespace
{
	using UEFlag = RE::UserEvents::USER_EVENT_FLAG;

	std::string Flags(std::uint32_t a_bits)
	{
		static constexpr const char* names[] = { "Movement", "Looking", "Activate", "Menu", "Console", "POVSwitch", "Fighting", "Sneaking", "MainFour",
			"WheelZoom", "Jumping", "VATS" };
		std::string out;
		for (int i = 0; i < 12; ++i)
			if (a_bits & (1u << i)) out += (out.empty() ? "" : "|") + std::string(names[i]);
		return out.empty() ? "-" : out;
	}

	std::string Where(void* a_addr)
	{
		HMODULE mod = nullptr;
		if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, static_cast<LPCSTR>(a_addr), &mod) || !mod)
			return std::format("{:p}", a_addr);
		char path[MAX_PATH]{};
		GetModuleFileNameA(mod, path, MAX_PATH);
		const char* name = std::strrchr(path, '\\');
		return std::format("{}+{:X}", name ? name + 1 : path, reinterpret_cast<std::uintptr_t>(a_addr) - reinterpret_cast<std::uintptr_t>(mod));
	}

	void LogNativeStack()
	{
		void*      frames[48]{};
		const auto n = RtlCaptureStackBackTrace(1, 48, frames, nullptr);
		for (unsigned i = 0; i < n; ++i) SKSE::log::info("    #{:02} {}", i, Where(frames[i]));
	}

	// Papyrus stacks whose Stack* appears on this thread's native stack: the script that called the native.
	void LogPapyrusStacksImpl()
	{
		auto* vm = RE::BSScript::Internal::VirtualMachine::GetSingleton();
		if (!vm) return;
		const auto* tib = reinterpret_cast<NT_TIB*>(NtCurrentTeb());
		const auto  lo = reinterpret_cast<std::uintptr_t*>(_AddressOfReturnAddress());
		const auto  hi = reinterpret_cast<std::uintptr_t*>(tib->StackBase);
		int         shown = 0, total = 0;
		for (auto& [id, stack] : vm->allRunningStacks) {
			++total;
			auto* s = stack.get();
			if (!s) continue;
			bool onThread = false;
			for (auto* p = lo; p < hi; ++p)
				if (*p == reinterpret_cast<std::uintptr_t>(s)) {
					onThread = true;
					break;
				}
			if (!onThread) continue;
			++shown;
			SKSE::log::info("    papyrus stack {}:", id);
			int depth = 0;
			for (auto* f = s->top; f && depth < 12; f = f->previousFrame, ++depth) {
				auto* fn = f->owningFunction.get();
				SKSE::log::info("      {}.{}", fn ? fn->GetObjectTypeName().c_str() : "?", fn ? fn->GetName().c_str() : "?");
			}
		}
		SKSE::log::info("    papyrus: {} of {} running stacks are on this thread", shown, total);
	}

	void LogPapyrusFault() { SKSE::log::info("    papyrus: could not read the VM stacks (access fault)"); }

	void LogPapyrusStacks()
	{
		__try {
			LogPapyrusStacksImpl();
		} __except (EXCEPTION_EXECUTE_HANDLER) {
			LogPapyrusFault();
		}
	}

	void LogState(const char* a_when)
	{
		auto* map = RE::ControlMap::GetSingleton();
		if (!map) return;
		const auto& d = map->GetRuntimeData();
		SKSE::log::info("{}: enabled=0x{:X} [{}]  stored=0x{:X}", a_when, d.enabledControls.underlying(), Flags(d.enabledControls.underlying()),
			d.storedControls.underlying());
	}

	class Sink : public RE::BSTEventSink<RE::UserEventEnabled>
	{
	public:
		RE::BSEventNotifyControl ProcessEvent(const RE::UserEventEnabled* a_event, RE::BSTEventSource<RE::UserEventEnabled>*) override
		{
			if (!a_event) return RE::BSEventNotifyControl::kContinue;
			const auto now = a_event->newUserEventFlag.underlying(), old = a_event->oldUserEventFlag.underlying();
			if (now == old) return RE::BSEventNotifyControl::kContinue;
			auto*      map = RE::ControlMap::GetSingleton();
			const auto stored = map ? map->GetRuntimeData().storedControls.underlying() : 0;
			SKSE::log::info("CHANGE 0x{:X} -> 0x{:X}  off:[{}]  on:[{}]  stored=0x{:X}  thread {}", old, now, Flags(old & ~now & 0xFFF), Flags(now & ~old & 0xFFF),
				stored, GetCurrentThreadId());
			// the full picture only for the control this hunt is about, either direction
			if ((old ^ now) & static_cast<std::uint32_t>(UEFlag::kFighting)) {
				LogNativeStack();
				LogPapyrusStacks();
			}
			return RE::BSEventNotifyControl::kContinue;
		}
	};

	Sink g_sink;

	void OnMessage(SKSE::MessagingInterface::Message* a_msg)
	{
		switch (a_msg->type) {
		case SKSE::MessagingInterface::kDataLoaded:
			if (auto* map = RE::ControlMap::GetSingleton()) {
				map->AddEventSink(&g_sink);
				SKSE::log::info("listening for control changes");
			}
			LogState("data loaded");
			break;
		case SKSE::MessagingInterface::kPreLoadGame:
			LogState("before load");
			break;
		case SKSE::MessagingInterface::kPostLoadGame:
			LogState("after load");
			break;
		case SKSE::MessagingInterface::kSaveGame:
			LogState("on save");
			break;
		default:
			break;
		}
	}
}

SKSEPluginInfo(
	.Version = { 1, 0, 0, 0 },
	.Name = "ControlsWatch",
	.Author = "urtubesrclogged",
	.RuntimeCompatibility = SKSE::VersionIndependence::AddressLibrary)

SKSEPluginLoad(const SKSE::LoadInterface* a_skse)
{
	SKSE::Init(a_skse);
	if (auto path = SKSE::log::log_directory()) {
		*path /= "ControlsWatch.log";
		auto log = std::make_shared<spdlog::logger>("global", std::make_shared<spdlog::sinks::basic_file_sink_mt>(path->string(), true));
		spdlog::set_default_logger(std::move(log));
		spdlog::set_level(spdlog::level::info);
		spdlog::flush_on(spdlog::level::info);
	}
	SKSE::log::info("ControlsWatch loading");
	SKSE::GetMessagingInterface()->RegisterListener(OnMessage);
	return true;
}
