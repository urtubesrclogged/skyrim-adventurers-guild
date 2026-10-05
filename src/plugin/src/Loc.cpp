#include "Loc.h"

#include <mutex>
#include <unordered_map>

namespace AG::Loc
{
	namespace
	{
		std::mutex                                   g_lock;
		std::unordered_map<std::string, std::string> g_map;
		std::string                                  g_language{ "ENGLISH" };

		std::string Utf8(std::wstring_view a_w)
		{
			if (a_w.empty()) return {};
			const int n = WideCharToMultiByte(CP_UTF8, 0, a_w.data(), static_cast<int>(a_w.size()), nullptr, 0, nullptr, nullptr);
			std::string out(static_cast<std::size_t>(n), '\0');
			WideCharToMultiByte(CP_UTF8, 0, a_w.data(), static_cast<int>(a_w.size()), out.data(), n, nullptr, nullptr);
			return out;
		}

		// Through the game's file system, so the file may be loose or packed in a BSA like any interface file.
		bool Read(const std::string& a_language, std::unordered_map<std::string, std::string>& a_out)
		{
			const auto path = std::format("Interface\\Translations\\AdventurersGuild_{}.txt", a_language);
			RE::BSResourceNiBinaryStream stream{ path };
			if (!stream.good()) return false;
			std::wstring  all;
			wchar_t       buf[1024];
			std::uint64_t got = 0;
			do {
				stream.stream->DoRead(buf, sizeof(buf), got);
				all.append(buf, static_cast<std::size_t>(got / sizeof(wchar_t)));
			} while (got == sizeof(buf));
			if (all.empty() || all[0] != 0xFEFF) {
				SKSE::log::error("Loc: {} must be UTF-16 LE with a BOM (the Skyrim translation file format)", path);
				return false;
			}
			std::size_t pos = 1, lines = 0;
			while (pos < all.size()) {
				auto end = all.find(L'\n', pos);
				if (end == std::wstring::npos) end = all.size();
				std::wstring_view line(all.data() + pos, end - pos);
				pos = end + 1;
				if (!line.empty() && line.back() == L'\r') line.remove_suffix(1);
				if (line.size() < 3 || line[0] != L'$') continue;
				const auto tab = line.find(L'\t');
				if (tab == std::wstring_view::npos || tab < 2) continue;
				// "\n" in the file stands for a line break (the file itself is one entry per line)
				auto text = Utf8(line.substr(tab + 1));
				for (std::size_t i; (i = text.find("\\n")) != std::string::npos;) text.replace(i, 2, "\n");
				a_out[Utf8(line.substr(0, tab))] = std::move(text);
				++lines;
			}
			SKSE::log::info("Loc: {} strings from {}", lines, path);
			return true;
		}
	}

	void Load()
	{
		std::string language = "ENGLISH";
		if (auto* ini = RE::INISettingCollection::GetSingleton()) {
			if (auto* s = ini->GetSetting("sLanguage:General"); s && s->GetType() == RE::Setting::Type::kString && s->data.s && *s->data.s) language = s->data.s;
		}
		for (auto& c : language) c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
		std::unordered_map<std::string, std::string> map;
		// English first, the player's language over it: a partial translation still shows English for what it lacks
		Read("ENGLISH", map);
		if (language != "ENGLISH" && !Read(language, map)) SKSE::log::info("Loc: no {} translation; using English", language);
		std::lock_guard l(g_lock);
		g_map = std::move(map);
		g_language = language;
	}

	std::string T(std::string_view a_key, std::string_view a_english)
	{
		std::lock_guard l(g_lock);
		const auto it = g_map.find(std::string(a_key));
		return it != g_map.end() ? it->second : std::string(a_english);
	}

	nlohmann::json UiStrings()
	{
		std::lock_guard l(g_lock);
		auto j = nlohmann::json::object();
		for (auto& [k, v] : g_map)
			if (k.starts_with("$AG_UI_")) j[k] = v;
		return j;
	}

	std::string Language()
	{
		std::lock_guard l(g_lock);
		return g_language;
	}
}
