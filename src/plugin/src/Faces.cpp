// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "Faces.h"

#include <xbyak/xbyak.h>

#include <filesystem>
#include <span>
#include <unordered_map>

// THE TINT FIX
// Faces built at run time keep their skin tint: the method of Face Discoloration Fix by Parapets (Exit-9B,
// https://github.com/Exit-9B/Face-Discoloration-Fix, MIT), its addresses and patches unchanged. SE 1.5.97 from its
// 2021 VR-support commit (a8da345), AE and VR from its current source (9051804).
//
// The game reads an NPC's tint layers from the plugin and throws them away unless the NPC is the player; a face built
// at run time (no FaceGen files) then has no skin colour: the dark face. Four NOPs keep the tint layers, two more let
// the face builder use them, and a patch in InitializeAfterLoad skips NPCs whose tint data cannot be used (the mod's
// own guard against broken records, which keeping every NPC's tint layers would otherwise expose).
//
// Face Discoloration Fix: MIT License, Copyright (c) 2020-2023 Parapets. Permission notice: THIRD_PARTY_NOTICES.md.

// HIGH POLY HEAD
// High Poly Head's heads on our NPCs, when it is loaded. High Poly Head.esm adds a twin for every playable vanilla face,
// most brows and most beards, named "00KLH_" + the vanilla part's editor ID (measured 2026-10-26: 205 of its 218 head
// parts; all 39 playable faces, 31 of 35 brows, 45 of 52 beards; no hair). It edits no vanilla record, so an NPC only
// gets its head by naming it. At data load each of our NPCs gets the twin of its face, brows and beard, the face and
// brows taken from the race's defaults when the NPC names none. In memory only: nothing is written to the save, and a
// list without High Poly Head keeps the vanilla parts.

namespace
{
	const char* Runtime() { return REL::Module::IsVR() ? "VR" : REL::Module::IsAE() ? "AE" : "SE"; }
}

namespace
{
	constexpr std::array<std::uint8_t, 2> kNop2{ 0x66, 0x90 };
	constexpr std::array<std::uint8_t, 6> kNop6{ 0x66, 0x0F, 0x1F, 0x44, 0x00, 0x00 };
	constexpr std::array<std::uint8_t, 2> kJcc6ToJmp{ 0x90, 0xE9 };

	std::string g_tint = "not installed";

	std::uintptr_t Fn(std::uint64_t a_se, std::uint64_t a_ae, std::uint64_t a_vr)
	{
		return REL::VariantID(a_se, a_ae, a_vr).address();
	}

	std::string Hex(std::uintptr_t a_at, std::size_t a_n)
	{
		std::string s;
		for (std::size_t i = 0; i < a_n; ++i) s += std::format("{:02X}", reinterpret_cast<const std::uint8_t*>(a_at)[i]);
		return s;
	}

	bool Same(std::uintptr_t a_at, std::span<const std::uint8_t> a_bytes)
	{
		return std::memcmp(reinterpret_cast<const void*>(a_at), a_bytes.data(), a_bytes.size()) == 0;
	}

	bool CheckTint(RE::TESNPC* a_npc)
	{
		if (!a_npc->race) {
			SKSE::log::error("NPC '{}' ({:08X}) has no race", a_npc->GetName(), a_npc->GetFormID());
			return false;
		}
		return a_npc->tintLayers && !a_npc->tintLayers->empty();
	}

	struct Sites
	{
		std::uintptr_t tinc, tini, tias, tinv, init, tint, dataload;
	};

	Sites Find()
	{
		const auto read = Fn(24159, 24663, 0x36C150);   // TESNPC::ReadFromFileStream
		const auto after = Fn(24215, 24719, 0x3714D0);  // TESNPC::InitializeAfterLoad
		const auto finish = Fn(24272, 24787, 0x378240);  // TESNPC::FinishInit
		const auto gen = Fn(26259, 26838, 0x3E23D0);     // BSFaceGenDB::GenerateHeadPartModel
		if (REL::Module::IsAE())
			return { read + 0x43C, read + 0x972, read + 0x1637, read + 0x1A60, finish + 0x36, gen + 0x4D4, after + 0x73F };
		return { read + 0x2EB, read + 0x81A, read + 0x11E1, read + 0x1594, finish + 0x2E, gen + 0x3A4, after + 0x730 };
	}

	void LogBytes(const Sites& s, const char* a_when)
	{
		SKSE::log::info("tint sites {}: TINC {} TINI {} TIAS {} TINV {} init {} tint {} dataload {}", a_when,
			Hex(s.tinc, 6), Hex(s.tini, 6), Hex(s.tias, 6), Hex(s.tinv, 6), Hex(s.init, 6), Hex(s.tint, 2), Hex(s.dataload, 16));
	}

	const std::uint8_t* At(std::uintptr_t a_at) { return reinterpret_cast<const std::uint8_t*>(a_at); }

	// The data-load guard's room and where its jump lands, measured from the start of the room (Face Discoloration Fix's numbers)
	std::size_t GuardRoom() { return REL::Module::IsAE() ? 0x21 : 0x20; }
	std::size_t GuardTarget() { return REL::Module::IsAE() ? 0x10B : 0x106; }

	// The game's own code at the sites, as SE 1.5.97 and VR 1.4.15 both have it (logged on each). AE's bytes are not on record, so
	// on AE each site is checked by the instruction it must hold: the four tint-layer reads end in a jnz rel32, the init site is a
	// jz rel32, the tint site a jnz rel8, and the data-load room reads the NPC's tint list ([r15+260h]) and holds a jz rel32 to the
	// place the guard jumps to. The fixed offsets inside each function come from one game build; a build whose code moved fails here,
	// and the fix writes nothing, instead of writing into the wrong instructions.
	std::string Unexpected(const Sites& s)
	{
		if (!REL::Module::IsAE()) {
			constexpr std::array<std::uint8_t, 6> tinc{ 0x0F, 0x85, 0x98, 0x13, 0x00, 0x00 }, tini{ 0x0F, 0x85, 0x69, 0x0E, 0x00, 0x00 },
				tias{ 0x0F, 0x85, 0xA2, 0x04, 0x00, 0x00 }, tinv{ 0x0F, 0x85, 0xEF, 0x00, 0x00, 0x00 }, init{ 0x0F, 0x84, 0xB3, 0x00, 0x00, 0x00 };
			constexpr std::array<std::uint8_t, 2> tint{ 0x75, 0x1A };
			constexpr std::array<std::uint8_t, 16> load{ 0x49, 0x8B, 0x87, 0x60, 0x02, 0x00, 0x00, 0x48, 0x85, 0xC0, 0x0F, 0x84, 0xF6, 0x00, 0x00, 0x00 };
			if (!Same(s.tinc, tinc)) return "TINC";
			if (!Same(s.tini, tini)) return "TINI";
			if (!Same(s.tias, tias)) return "TIAS";
			if (!Same(s.tinv, tinv)) return "TINV";
			if (!Same(s.init, init)) return "init";
			if (!Same(s.tint, tint)) return "tint";
			if (!Same(s.dataload, load)) return "dataload";
			return {};
		}
		const auto jcc6 = [](std::uintptr_t a, std::uint8_t op) { return At(a)[0] == 0x0F && At(a)[1] == op; };
		if (!jcc6(s.tinc, 0x85)) return "TINC";
		if (!jcc6(s.tini, 0x85)) return "TINI";
		if (!jcc6(s.tias, 0x85)) return "TIAS";
		if (!jcc6(s.tinv, 0x85)) return "TINV";
		if (!jcc6(s.init, 0x84)) return "init";
		if (At(s.tint)[0] != 0x75) return "tint";
		constexpr std::array<std::uint8_t, 7> list{ 0x49, 0x8B, 0x87, 0x60, 0x02, 0x00, 0x00 };  // mov rax, [r15+260h]
		const auto* b = At(s.dataload);
		bool reads = false, jumps = false;
		for (std::size_t i = 0; i + list.size() <= GuardRoom(); ++i) reads |= std::memcmp(b + i, list.data(), list.size()) == 0;
		for (std::size_t i = 0; i + 6 <= GuardRoom(); ++i)
			if (b[i] == 0x0F && b[i + 1] == 0x84) {
				std::int32_t rel;
				std::memcpy(&rel, b + i + 2, 4);
				jumps |= static_cast<std::int64_t>(i) + 6 + rel == static_cast<std::int64_t>(GuardTarget());
			}
		return reads && jumps ? std::string{} : "dataload";
	}

	// already patched the way this fix patches (Face Discoloration Fix writes the same bytes)
	bool Patched(const Sites& s)
	{
		return Same(s.tinc, kNop6) && Same(s.tini, kNop6) && Same(s.tias, kNop6) && Same(s.tinv, kNop6) && Same(s.init, kJcc6ToJmp) &&
		       Same(s.tint, kNop2);
	}
}

namespace
{
	// the plugin the hall's people come from: the hall's own ("AdventurersGuild - Guild Hall.esp")
	constexpr std::array<std::string_view, 1> kOurs{ "AdventurersGuild - Guild Hall.esp" };
	constexpr std::string_view kHph = "High Poly Head.esm";
	constexpr std::string_view kPrefix = "00KLH_";

	using Type = RE::BGSHeadPart::HeadPartType;

	std::string g_heads = "data not loaded yet";

	bool Ours(const RE::TESForm* a_form)
	{
		const auto* file = a_form ? a_form->GetFile(0) : nullptr;
		return file && std::ranges::find(kOurs, file->GetFilename()) != kOurs.end();
	}

	std::string Name(const RE::BGSHeadPart* a_part) { return a_part ? std::string(a_part->formEditorID.c_str()) : "-"; }

	const char* TypeName(Type a_type)
	{
		switch (a_type) {
		case Type::kFace: return "face";
		case Type::kEyes: return "eyes";
		case Type::kHair: return "hair";
		case Type::kFacialHair: return "beard";
		case Type::kScar: return "scar";
		case Type::kEyebrows: return "brows";
		default: return "misc";
		}
	}

	RE::BGSHeadPart* RaceDefault(RE::TESNPC* a_npc, Type a_type)
	{
		const auto* race = a_npc->race;
		const auto* face = race ? race->faceRelatedData[a_npc->IsFemale() ? 1 : 0] : nullptr;
		if (!face || !face->headParts) return nullptr;
		for (auto* p : *face->headParts)
			if (p && p->type.get() == a_type) return p;
		return nullptr;
	}
}

namespace AG::Faces
{
	void InstallTint()
	{
		// the original bytes, kept in the log so each runtime's are on record (other plugins may not have loaded yet)
		LogBytes(Find(), "at load");
		g_tint = "waiting for every SKSE plugin to load";
	}

	// After every SKSE plugin has loaded (Face Discoloration Fix patches inside its own load) and before the game reads any
	// plugin. What is in the game's code decides, not which files are installed: an installed Face Discoloration Fix built for
	// another game version patches nothing, and stepping aside for its file alone left the hall's people with dark faces.
	void ApplyTint()
	{
		const auto sites = Find();
		LogBytes(sites, "after every plugin loaded");
		const auto ver = REL::Module::get().version().string(".");
		std::error_code ec;
		const bool fdfFile = std::filesystem::exists("Data/SKSE/Plugins/FaceGenFixes.dll", ec);
		const bool fdfLoaded = GetModuleHandleW(L"FaceGenFixes.dll") != nullptr;
		const auto fdf = fdfLoaded ? "Face Discoloration Fix loaded" : fdfFile ? "Face Discoloration Fix installed, not loaded" : "Face Discoloration Fix not installed";

		if (Patched(sites)) {
			g_tint = std::format("stepped aside: the game is already patched ({}) on {} {}", fdf, Runtime(), ver);
			SKSE::log::info("tint fix {}", g_tint);
			return;
		}
		if (const auto site = Unexpected(sites); !site.empty()) {
			g_tint = std::format("NOT installed: the {} site does not hold the code the fix expects on {} {} ({}); nothing written. "
			                     "The Guild Hall's people will have dark faces",
				site, Runtime(), ver, fdf);
			SKSE::log::critical("tint fix {}", g_tint);
			return;
		}
		if (fdfFile || fdfLoaded) SKSE::log::warn("tint fix: {}, but the game is not patched: AG's own fix goes in", fdf);

		REL::safe_write(sites.tias, kNop6.data(), kNop6.size());
		REL::safe_write(sites.tinv, kNop6.data(), kNop6.size());
		REL::safe_write(sites.tinc, kNop6.data(), kNop6.size());
		REL::safe_write(sites.tini, kNop6.data(), kNop6.size());
		REL::safe_write(sites.init, kJcc6ToJmp.data(), kJcc6ToJmp.size());
		REL::safe_write(sites.tint, kNop2.data(), kNop2.size());

		const bool ae = REL::Module::IsAE();
		struct Patch : Xbyak::CodeGenerator
		{
			Patch(std::uintptr_t a_fn, bool a_ae)
			{
				Xbyak::Label start;
				L(start);
				mov(rcx, r15);
				mov(rax, a_fn);
				call(rax);
				test(al, al);
				if (a_ae) {
					jz(start.getAddress() + 0x10B);
					mov(r12d, esi);
					mov(rax, ptr[r15 + 0x260]);
				} else {
					jz(start.getAddress() + 0x106);
					mov(r12d, r14d);
				}
			}
		};
		Patch patch{ reinterpret_cast<std::uintptr_t>(&CheckTint), ae };
		patch.ready();
		const std::size_t room = GuardRoom();
		if (patch.getSize() > room) {
			g_tint = std::format("partly installed: the data-load guard is {} bytes, room for {}", patch.getSize(), room);
			SKSE::log::critical("tint fix {}", g_tint);
		} else {
			REL::safe_fill(sites.dataload, REL::NOP, room);
			REL::safe_write(sites.dataload, patch.getCode(), patch.getSize());
			g_tint = "installed";
		}
		LogBytes(sites, "after");
		SKSE::log::info("tint fix {} on {} {}", g_tint, Runtime(), REL::Module::get().version().string("."));
	}


	void OnDataLoaded()
	{
		auto* dh = RE::TESDataHandler::GetSingleton();
		std::vector<RE::TESNPC*> ours;
		for (auto* npc : dh->GetFormArray<RE::TESNPC>())
			if (Ours(npc)) ours.push_back(npc);

		// Whether the tint fix worked, read from the records themselves: without it the game drops an NPC's tint layers as it
		// reads them, and a face built at run time comes out dark.
		int kept = 0;
		std::string each;
		for (auto* npc : ours) {
			const auto n = npc->tintLayers ? npc->tintLayers->size() : 0;
			kept += n > 0;
			const auto& q = npc->bodyTintColor;
			each += std::format("{}{} {} (skin {},{},{})", each.empty() ? "" : "; ", npc->GetName(), n, q.red, q.green, q.blue);
		}
		if (!ours.empty()) {
			if (kept) SKSE::log::info("tint layers kept by {} of {} hall NPC(s) (tint fix: {})", kept, ours.size(), g_tint);
			else SKSE::log::critical("tint layers kept by NONE of {} hall NPC(s): their faces will be dark (tint fix: {})", ours.size(), g_tint);
			SKSE::log::info("tint layers: {}", each);
		}

		if (!dh->LookupModByName(kHph)) {
			g_heads = std::format("High Poly Head not loaded: {} NPC(s) keep vanilla heads", ours.size());
			SKSE::log::info("heads: {}", g_heads);
			return;
		}

		std::unordered_map<std::string, RE::BGSHeadPart*> twins;
		for (auto* part : dh->GetFormArray<RE::BGSHeadPart>()) {
			const auto* file = part ? part->GetFile(0) : nullptr;
			const std::string_view ed = part ? part->formEditorID.c_str() : "";
			if (file && file->GetFilename() == kHph && ed.starts_with(kPrefix)) twins.emplace(ed.substr(kPrefix.size()), part);
		}

		int swapped = 0, missing = 0;
		for (auto* npc : ours) {
			std::vector<RE::BGSHeadPart*> parts(npc->headParts, npc->headParts + std::max<std::int8_t>(npc->numHeadParts, 0));
			std::string log;
			for (const auto type : { Type::kFace, Type::kEyebrows, Type::kFacialHair }) {
				auto it = std::ranges::find_if(parts, [&](auto* p) { return p && p->type.get() == type; });
				auto* cur = it != parts.end() ? *it : (type == Type::kFacialHair ? nullptr : RaceDefault(npc, type));
				if (!cur) continue;
				const auto twin = twins.find(Name(cur));
				if (twin == twins.end()) {
					++missing;
					log += std::format(" {} {} (no twin)", TypeName(type), Name(cur));
					continue;
				}
				if (it != parts.end()) *it = twin->second;
				else parts.push_back(twin->second);
				log += std::format(" {} {} -> {}", TypeName(type), Name(cur), Name(twin->second));
			}
			// a new array from the game's allocator: the old one stays where it is (the game may still hold it)
			auto* arr = RE::malloc<RE::BGSHeadPart*>(parts.size() * sizeof(RE::BGSHeadPart*));
			std::ranges::copy(parts, arr);
			npc->headParts = arr;
			npc->numHeadParts = static_cast<std::int8_t>(parts.size());
			++swapped;
			SKSE::log::info("heads: {:08X} {}:{}", npc->GetFormID(), npc->GetName(), log);
		}
		g_heads = std::format("High Poly Head loaded: {} NPC(s) given its heads, {} part(s) with no twin", swapped, missing);
		SKSE::log::info("heads: {}", g_heads);
	}


	std::string Status() { return std::format("tint fix: {} | heads: {}", g_tint, g_heads); }

	std::string Parts(RE::TESNPC* a_npc)
	{
		if (!a_npc) return "none";
		std::string s;
		for (std::int8_t i = 0; i < a_npc->numHeadParts; ++i)
			if (auto* p = a_npc->headParts[i]) s += std::format("{}{}={}", s.empty() ? "" : ", ", TypeName(p->type.get()), Name(p));
		for (const auto type : { Type::kFace, Type::kEyebrows })
			if (!a_npc->GetHeadPartByType(type))
				if (auto* d = RaceDefault(a_npc, type)) s += std::format(", {}={} (race default)", TypeName(type), Name(d));
		return s;
	}
}
