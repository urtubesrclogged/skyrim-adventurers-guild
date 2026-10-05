#pragma once

// What the two board integrations share (MissiveWatch for Missives, NoticeWatch for The Notice Board): the in-memory
// rank gate and label, and reading a posting's note the way the player would.
namespace AG::QuestBoard
{
	// Papyrus Quest.IsRunning(). NOT CommonLib's TESQuest::IsRunning(), which is only "not stopping" and is
	// true for every idle quest (it listed all 29 Whiterun missives as posted when 9 were running).
	inline bool Running(const RE::TESQuest* a_q) { return a_q && a_q->IsEnabled() && !a_q->IsStopping(); }

	inline RE::BGSBaseAlias* AliasNamed(RE::TESQuest* a_q, std::string_view a_name)
	{
		for (auto* a : a_q->aliases) {
			if (a && a->aliasName == a_name) return a;
		}
		return nullptr;
	}

	inline RE::TESObjectREFR* AliasRef(RE::TESQuest* a_q, std::string_view a_name)
	{
		auto* a = AliasNamed(a_q, a_name);
		return a ? a_q->GetAliasedRef(a->aliasID).get().get() : nullptr;
	}

	inline std::string StripRank(std::string a_s)
	{
		if (auto pos = a_s.rfind(" [Rank "); pos != std::string::npos) a_s.erase(pos);
		return a_s;
	}

	// " [Rank X]" after a quest's or a note's name, once.
	inline void Label(RE::TESFullName* a_named, char a_tier)
	{
		if (!a_named) return;
		const std::string_view cur = a_named->GetFullName();
		if (cur.contains("[Rank ")) return;  // already labeled
		a_named->fullName = std::format("{} [Rank {}]", cur, a_tier);
	}

	// "AG_PlayerRankGlobal >= rank" as the FIRST condition, so it is ANDed with the whole existing list (a leading
	// AND item forms its own group, whatever OR groups follow). Game heap (TESConditionItem redefines new).
	inline void Gate(RE::TESCondition* a_cond, RE::TESGlobal* a_rank, int a_min)
	{
		auto* item = new RE::TESConditionItem();
		item->data.object = RE::CONDITIONITEMOBJECT::kSelf;
		item->data.functionData.function = RE::FUNCTION_DATA::FunctionID::kGetGlobalValue;
		item->data.functionData.params[0] = a_rank;
		item->data.flags.opCode = RE::CONDITION_ITEM_DATA::OpCode::kGreaterThanOrEqualTo;
		item->data.flags.isOR = false;
		item->data.comparisonValue.f = static_cast<float>(a_min);
		item->next = a_cond->head;
		a_cond->head = item;
	}

	inline int Count(const RE::TESCondition* a_cond)
	{
		int n = 0;
		for (auto* i = a_cond ? a_cond->head : nullptr; i; i = i->next) ++n;
		return n;
	}

	// The quest's must-fill alias with the richest existing filter: non-Optional, conditioned. nullptr if it has none
	// (then the quest cannot be gated this way, and is left open to every rank).
	inline RE::BGSRefAlias* GateAlias(RE::TESQuest* a_q)
	{
		RE::BGSRefAlias* best = nullptr;
		for (auto* base : a_q->aliases) {
			if (!base || base->GetVMTypeID() != RE::BGSRefAlias::VMTYPEID) continue;
			auto* alias = static_cast<RE::BGSRefAlias*>(base);
			if (alias->flags.any(RE::BGSBaseAlias::FLAGS::kOptional) || !alias->conditions || !alias->conditions->head) continue;
			if (!best || Count(alias->conditions) > Count(best->conditions)) best = alias;
		}
		return best;
	}

	// The posting's own note title with its <Alias=...> tokens filled (e.g. "Slay the Giant at Bleakwind Basin"); the
	// quest's journal name if the note can't be read or is still unresolved. The rank label is removed.
	inline std::string NoteTitle(RE::TESQuest* a_q, std::string_view a_noteAlias)
	{
		std::string title;
		if (auto* note = AliasRef(a_q, a_noteAlias)) {
			if (const char* n = note->GetDisplayFullName(); n && *n) title = n;
		}
		if (title.empty() || title.find("<Alias") != std::string::npos) title = a_q->GetFullName();
		return StripRank(title);
	}

	// What the engine prints for <Alias=Name> in this quest instance: the quest's own instance text table
	// (alias -> form whose name fills it) covers ref AND location aliases; the filled ref's name is a fallback.
	inline std::string AliasText(RE::TESQuest* a_q, const RE::BGSQuestInstanceText* a_inst, const std::string& a_name, bool a_baseName)
	{
		auto* alias = AliasNamed(a_q, a_name);
		if (!alias) return a_name;
		if (a_inst && !a_baseName) {
			for (auto& sd : a_inst->stringData) {
				if (sd.aliasID != alias->aliasID) continue;
				if (auto* f = RE::TESForm::LookupByID(sd.fullNameFormID); f && f->GetName() && *f->GetName()) return f->GetName();
			}
		}
		if (auto ref = a_q->GetAliasedRef(alias->aliasID).get()) {
			if (auto* base = ref->GetBaseObject(); a_baseName && base && base->GetName() && *base->GetName()) return base->GetName();
			if (const char* n = ref->GetDisplayFullName(); n && *n) return n;
		}
		return a_name;
	}

	// The note as the player would read it: its text with every <Alias...=X> filled in from the quest instance, book
	// markup removed, blank lines collapsed. Empty if the quest has no such note.
	inline std::string NoteText(RE::TESQuest* a_q, std::string_view a_noteAlias)
	{
		auto* noteAlias = AliasNamed(a_q, a_noteAlias);
		auto  note = noteAlias ? a_q->GetAliasedRef(noteAlias->aliasID).get() : nullptr;
		auto* book = note && note->GetBaseObject() ? note->GetBaseObject()->As<RE::TESObjectBOOK>() : nullptr;
		if (!book) return {};
		RE::BSString raw;
		book->GetDescription(raw, nullptr);

		// the instance of the quest text this note was stamped with (what the engine uses when it's read)
		std::uint32_t instId = a_q->currentInstanceID;
		if (auto* td = note->extraList.GetByType<RE::ExtraTextDisplayData>(); td && td->ownerQuest == a_q && td->ownerInstance.underlying() >= 0) {
			instId = static_cast<std::uint32_t>(td->ownerInstance.underlying());
		}
		const RE::BGSQuestInstanceText* inst = nullptr;
		for (auto* it : a_q->instanceData) {
			if (it && it->id == instId) inst = it;
		}

		// fill <Alias=X> / <Alias.BaseName=X> / <Alias.ShortName=X>, drop book markup (<font ...>, </font>, <p ...>)
		std::string text;
		const std::string src = raw.c_str() ? raw.c_str() : "";
		for (std::size_t i = 0; i < src.size();) {
			if (src[i] != '<') { text += src[i++]; continue; }
			const auto end = src.find('>', i);
			if (end == std::string::npos) { text += src.substr(i); break; }
			const std::string tag = src.substr(i + 1, end - i - 1);
			if (tag.starts_with("Alias=")) text += AliasText(a_q, inst, tag.substr(6), false);
			else if (tag.starts_with("Alias.BaseName=")) text += AliasText(a_q, inst, tag.substr(15), true);
			else if (tag.starts_with("Alias.") && tag.find('=') != std::string::npos) text += AliasText(a_q, inst, tag.substr(tag.find('=') + 1), false);
			else if (tag == "br" || tag == "br/" || tag == "p" || tag.starts_with("p ")) text += '\n';
			i = end + 1;
		}
		// tidy: trim each line, at most one blank line in a row, none at the ends
		std::string tidy;
		bool        blank = false;
		std::size_t pos = 0;
		while (pos <= text.size()) {
			auto nl = text.find('\n', pos);
			if (nl == std::string::npos) nl = text.size();
			auto line = text.substr(pos, nl - pos);
			const auto a = line.find_first_not_of(" \t\r");
			line = a == std::string::npos ? std::string{} : line.substr(a, line.find_last_not_of(" \t\r") - a + 1);
			if (line.empty()) {
				if (!tidy.empty() && !blank) tidy += '\n';
				blank = true;
			} else {
				tidy += line + '\n';
				blank = false;
			}
			pos = nl + 1;
		}
		while (!tidy.empty() && tidy.back() == '\n') tidy.pop_back();
		return tidy;
	}
}
