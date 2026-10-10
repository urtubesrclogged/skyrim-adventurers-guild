#include "SteamVRAim.h"

#include <SimpleIni.h>
#include <Windows.h>
#include <openvr.h>

#include <atomic>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <string>
#include <thread>

namespace AG::SteamVRAim
{
	namespace
	{
		// What Prisma UI reads through the window property: an aim pose per hand in the standing universe, -Z the way the
		// hand points (OpenXR's /input/aim/pose convention), and whether each is usable this frame. The layout is the
		// interface between OpenComposite Unleashed and Prisma UI; it is matched here, not shared code.
		struct AimPoses
		{
			vr::HmdMatrix34_t matrix[2];  // [0] left, [1] right
			bool              valid[2];
		};
		AimPoses          g_poses{};   // lives as long as the game: Prisma UI keeps the pointer
		std::atomic<bool> g_published{ false };
		float             g_pitch = 0.0f;  // [VR] LaserPitch, degrees: tilts the ray down (+) or up (-) if a controller needs it

		vr::IVRSystem*       g_system = nullptr;
		vr::IVRRenderModels* g_models = nullptr;

		bool Contains(const char* a_module, std::string_view a_text)
		{
			char  path[MAX_PATH]{};
			auto* dll = GetModuleHandleA(a_module);
			if (!dll || !GetModuleFileNameA(dll, path, MAX_PATH)) return false;
			std::ifstream     f(path, std::ios::binary);
			const std::string bytes((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
			return bytes.find(a_text) != std::string::npos;
		}

		bool Interfaces()
		{
			if (g_system) return true;
			auto* dll = GetModuleHandleA("openvr_api.dll");
			using GetIface = void* (*)(const char*, vr::EVRInitError*);
			auto* get = dll ? reinterpret_cast<GetIface>(GetProcAddress(dll, "VR_GetGenericInterface")) : nullptr;
			if (!get) return false;
			vr::EVRInitError err = vr::VRInitError_None;
			auto*            sys = static_cast<vr::IVRSystem*>(get(vr::IVRSystem_Version, &err));
			if (!sys || err != vr::VRInitError_None) return false;
			g_models = static_cast<vr::IVRRenderModels*>(get(vr::IVRRenderModels_Version, &err));  // may be null: the grip pose is used then
			g_system = sys;
			return true;
		}

		vr::HmdMatrix34_t Mul(const vr::HmdMatrix34_t& a, const vr::HmdMatrix34_t& b)
		{
			vr::HmdMatrix34_t r{};
			for (int i = 0; i < 3; ++i) {
				for (int j = 0; j < 3; ++j) r.m[i][j] = a.m[i][0] * b.m[0][j] + a.m[i][1] * b.m[1][j] + a.m[i][2] * b.m[2][j];
				r.m[i][3] = a.m[i][0] * b.m[0][3] + a.m[i][1] * b.m[1][3] + a.m[i][2] * b.m[2][3] + a.m[i][3];
			}
			return r;
		}

		vr::HmdMatrix34_t PitchX(float a_degrees)  // a rotation about the hand's own X axis
		{
			const float       r = a_degrees * 3.14159265f / 180.0f, c = std::cos(r), s = std::sin(r);
			vr::HmdMatrix34_t m{};
			m.m[0][0] = 1.0f;
			m.m[1][1] = c;  m.m[1][2] = -s;
			m.m[2][1] = s;  m.m[2][2] = c;
			return m;
		}

		// Where the controller's "tip" is in the controller's own space: SteamVR's definition of where each model of
		// controller points from, the one its dashboard laser uses. False when the model has none (the raw pose is used).
		bool Tip(vr::TrackedDeviceIndex_t a_device, vr::HmdMatrix34_t& a_out)
		{
			if (!g_models) return false;
			char                    name[vr::k_unMaxPropertyStringSize]{};
			vr::ETrackedPropertyError perr = vr::TrackedProp_Success;
			g_system->GetStringTrackedDeviceProperty(a_device, vr::Prop_RenderModelName_String, name, sizeof(name), &perr);
			if (perr != vr::TrackedProp_Success || !name[0]) return false;
			vr::VRControllerState_t state{};
			g_system->GetControllerState(a_device, &state, sizeof(state));
			vr::RenderModel_ControllerMode_State_t mode{};
			vr::RenderModel_ComponentState_t       comp{};
			if (!g_models->GetComponentState(name, "tip", &state, &mode, &comp)) return false;
			a_out = comp.mTrackingToComponentLocal;
			return true;
		}

		BOOL CALLBACK Publish(HWND a_hwnd, LPARAM a_count)
		{
			DWORD pid = 0;
			GetWindowThreadProcessId(a_hwnd, &pid);
			if (pid != GetCurrentProcessId()) return TRUE;
			// Prisma UI reads the first visible window of the game it finds; every window of ours gets the property, so
			// whichever that is has it. One already there is somebody else's (OpenComposite): left alone.
			if (!GetPropW(a_hwnd, L"OC_AIM_POSES") && SetPropW(a_hwnd, L"OC_AIM_POSES", &g_poses)) ++*reinterpret_cast<int*>(a_count);
			return TRUE;
		}

		void Run()
		{
			using namespace std::chrono_literals;
			vr::HmdMatrix34_t tip[2]{};
			bool              hasTip[2]{};
			vr::TrackedDeviceIndex_t tipOf[2]{ vr::k_unTrackedDeviceIndexInvalid, vr::k_unTrackedDeviceIndexInvalid };
			int               tick = 0;
			bool              loggedHands = false;
			const auto        pitch = PitchX(-g_pitch);
			for (;; ++tick) {
				std::this_thread::sleep_for(5ms);
				if (!Interfaces()) {
					std::this_thread::sleep_for(500ms);
					continue;
				}
				if (tick % 400 == 0) {  // every two seconds: windows made since the last look
					int n = 0;
					EnumWindows(Publish, reinterpret_cast<LPARAM>(&n));
					if (n > 0 && !g_published.exchange(true)) SKSE::log::info("SteamVRAim: aim poses published for Prisma UI on {} window(s)", n);
				}
				vr::TrackedDevicePose_t poses[vr::k_unMaxTrackedDeviceCount];
				g_system->GetDeviceToAbsoluteTrackingPose(vr::TrackingUniverseStanding, 0.0f, poses, vr::k_unMaxTrackedDeviceCount);
				const vr::TrackedDeviceIndex_t hand[2]{ g_system->GetTrackedDeviceIndexForControllerRole(vr::TrackedControllerRole_LeftHand),
					g_system->GetTrackedDeviceIndexForControllerRole(vr::TrackedControllerRole_RightHand) };
				AimPoses next{};
				for (int h = 0; h < 2; ++h) {
					const auto d = hand[h];
					if (d == vr::k_unTrackedDeviceIndexInvalid || d >= vr::k_unMaxTrackedDeviceCount || !poses[d].bPoseIsValid || !poses[d].bDeviceIsConnected) continue;
					if (tipOf[h] != d || tick % 400 == 0) {  // a controller that woke up or was swapped, and now and then
						hasTip[h] = Tip(d, tip[h]);
						tipOf[h] = d;
					}
					auto m = poses[d].mDeviceToAbsoluteTracking;
					if (hasTip[h]) m = Mul(m, tip[h]);
					if (g_pitch != 0.0f) m = Mul(m, pitch);
					next.matrix[h] = m;
					next.valid[h] = true;
				}
				if (!loggedHands && (next.valid[0] || next.valid[1])) {
					loggedHands = true;
					SKSE::log::info("SteamVRAim: controllers tracked (left {}, right {}); pointing from {} / {}", next.valid[0] ? "yes" : "no", next.valid[1] ? "yes" : "no",
						hasTip[0] ? "the controller's tip" : "its grip pose", hasTip[1] ? "the controller's tip" : "its grip pose");
				}
				// Prisma UI reads this from its own thread. A pose caught half written is one frame of a slightly wrong ray;
				// the flags go last so a hand is never marked usable before its matrix is there.
				g_poses.matrix[0] = next.matrix[0];
				g_poses.matrix[1] = next.matrix[1];
				g_poses.valid[0] = next.valid[0];
				g_poses.valid[1] = next.valid[1];
			}
		}
	}

	void Install()
	{
		if (!REL::Module::IsVR()) return;
		CSimpleIniA ini;
		ini.SetUnicode();
		std::string mode = "auto";
		if (ini.LoadFile(L"Data\\SKSE\\Plugins\\AdventurersGuild.ini") >= 0) {
			mode = ini.GetValue("VR", "SteamVRLasers", "auto");
			g_pitch = static_cast<float>(ini.GetDoubleValue("VR", "LaserPitch", 0.0));
		}
		for (auto& c : mode) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
		if (mode == "off" || mode == "0") {
			SKSE::log::info("SteamVRAim: off ([VR] SteamVRLasers)");
			return;
		}
		if (Contains("openvr_api.dll", "OpenComposite") || Contains("openvr_api.dll", "opencomposite")) {
			SKSE::log::info("SteamVRAim: not needed (OpenComposite gives Prisma UI its aim poses)");
			return;
		}
		// Prisma UI 1.5.0 still points with SteamVR's poses on its own and is left as it is; the builds that dropped that
		// say so in a message of their own, which is how they are told apart (the DLL carries no version resource).
		const bool needs = Contains("PrismaUI.dll", "requires OpenComposite Unleashed");
		if (!needs && mode != "on" && mode != "1") {
			SKSE::log::info("SteamVRAim: not needed (this Prisma UI has its own SteamVR laser, or Prisma UI is not installed)");
			return;
		}
		SKSE::log::info("SteamVRAim: native SteamVR and a Prisma UI without a SteamVR laser - supplying the aim poses ourselves (pitch {:.1f})", g_pitch);
		std::thread(Run).detach();
	}
}
