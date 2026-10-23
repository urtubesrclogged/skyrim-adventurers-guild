// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#pragma once

#include <nlohmann/json.hpp>

// Player-facing text, translatable without touching code. Strings live in the standard Skyrim translation file
// Interface/Translations/AdventurersGuild_<LANGUAGE>.txt (UTF-16 LE with BOM, one "$KEY<TAB>text" per line; the
// language is Skyrim.ini's sLanguage). MCM Helper reads the same file for the MCM's "$" keys.
//
// Every call site carries its English text as the fallback, so the mod works with no translation file at all, and
// tools/make_translations.py generates AdventurersGuild_ENGLISH.txt from those call sites (a translator copies it to
// _FRENCH.txt etc. and translates the right-hand column). Text may use std::format placeholders: {} or {0}, {1}...
// (numbered ones let a translation reorder the arguments).
namespace AG::Loc
{
	void Load();  // at kDataLoaded: reads the player's language, falling back to ENGLISH

	// Translated text for a_key ("$AG_..."), or a_english when the file lacks it.
	std::string T(std::string_view a_key, std::string_view a_english);

	// T, then formatted. A translation whose placeholders don't fit the arguments falls back to the English.
	template <class... Args>
	std::string F(std::string_view a_key, std::string_view a_english, Args&&... a_args)
	{
		const auto text = T(a_key, a_english);
		try {
			return std::vformat(text, std::make_format_args(a_args...));
		} catch (const std::format_error&) {
			try {
				return std::vformat(a_english, std::make_format_args(a_args...));
			} catch (const std::format_error&) {
				return std::string(a_english);
			}
		}
	}

	// Every loaded "$AG_UI_..." string, for the PrismaUI views (window.agStrings); they keep their own English fallbacks.
	nlohmann::json UiStrings();
	std::string    Language();  // e.g. "ENGLISH"
}
