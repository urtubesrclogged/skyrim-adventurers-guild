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
		const auto sites = Find();
		LogBytes(sites, "before");  // the original bytes, kept in the log so each runtime's are on record

		std::error_code ec;
		const bool fdfFile = std::filesystem::exists("Data/SKSE/Plugins/FaceGenFixes.dll", ec);
		const bool fdfLoaded = GetModuleHandleW(L"FaceGenFixes.dll") != nullptr;
		const bool patched = Same(sites.tinc, kNop6) && Same(sites.tint, kNop2);
		if (fdfFile || fdfLoaded || patched) {
			g_tint = std::format("stepped aside: Face Discoloration Fix {}{}", fdfLoaded ? "loaded" : fdfFile ? "installed" : "",
				patched ? (fdfFile || fdfLoaded ? ", bytes already patched" : "bytes already patched") : "");
			SKSE::log::info("tint fix {}", g_tint);
			return;
		}

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
		const std::size_t room = ae ? 0x21 : 0x20;
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
