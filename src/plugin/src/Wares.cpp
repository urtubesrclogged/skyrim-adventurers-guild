// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "Wares.h"

#include "Guild.h"
#include "Loc.h"

#include <algorithm>
#include <fstream>
#include <map>
#include <mutex>
#include <random>
#include <vector>

namespace AG::Wares
{
	namespace
	{
		constexpr std::string_view kPlugin = "AdventurersGuild.esp";
		constexpr RE::FormID       kCurseAbility = 0xFE0;  // + index in wares.json "curses"
		constexpr RE::FormID       kCurseNote = 0xFF0;     // + 2 * index (weapon), + 1 for the worn one

		struct Kind
		{
			std::string       id;
			RE::TESLevItem*   list{ nullptr };
			int               weight{ 0 };
		};

		// one effect of a base enchantment, with the range vanilla's tiers of it span
		struct FamilyFx
		{
			RE::EffectSetting* fx{ nullptr };
			std::uint32_t      area{ 0 };
			float              magMin{ 0.0f }, magMax{ 0.0f };
			std::uint32_t      durMin{ 0 }, durMax{ 0 };
			float              costAtMax{ 0.0f };  // the strongest tier's cost, scaled for what we make
			bool               seen{ false };
			bool               measured{ false };  // found on a tier, not only on the base
		};

		struct Family
		{
			RE::EnchantmentItem*  base{ nullptr };
			bool                  weapon{ false };
			RE::BGSListForm*      worn{ nullptr };  // the slots it fits (armor); nullptr = any
			std::vector<FamilyFx> fx;
			int                   tiers{ 0 };
		};

		struct Tier
		{
			std::string id, name;
			int         rank{ -1 };
			float       strength{ 0.0f }, multiplier{ 1.0f };
			int         effects{ 1 };
			bool        curse{ false };
			int         charge{ 0 };
			int         merit{ 0 }, reputation{ 0 }, gold{ 0 };
		};

		struct Curse
		{
			std::string        id, name;
			RE::EffectSetting* fx{ nullptr };
			float              magnitude{ 0.0f };
			RE::SpellItem*     ability{ nullptr };
			RE::EffectSetting* noteWeapon{ nullptr };  // nothing but the curse's description, for a weapon's enchantment
			RE::EffectSetting* noteWorn{ nullptr };    // ... and for a worn one whose vanilla effect has no text
		};

		std::mutex                           g_lock;
		std::vector<Kind>                    g_kinds;
		std::vector<Family>                  g_families;
		std::vector<Tier>                    g_tiers;
		std::vector<Curse>                   g_curses;
		std::map<RE::FormID, int>            g_cursedWeapons;  // the created enchantment of a cursed weapon -> its curse
		std::mt19937                         g_rng{ std::random_device{}() };
		float                                g_resistCap{ 100.0f };

		// the tier names a translator sees: literal keys, so tools/make_translations.py finds them
		std::string TierName(const Tier& a_t)
		{
			if (a_t.id == "guild") return Loc::T("$AG_WareTier_guild", "Guild");
			if (a_t.id == "blessed") return Loc::T("$AG_WareTier_blessed", "Blessed");
			if (a_t.id == "cursed") return Loc::T("$AG_WareTier_cursed", "Cursed");
			if (a_t.id == "heroic") return Loc::T("$AG_WareTier_heroic", "Heroic");
			return a_t.name;
		}
		std::string TierDesc(const Tier& a_t)
		{
			if (a_t.id == "guild") return Loc::T("$AG_WareDesc_guild", "A piece of gear for your level, from the Guild's vaults, with a modest enchantment.");
			if (a_t.id == "blessed") return Loc::T("$AG_WareDesc_blessed", "A piece of gear for your level with a strong enchantment.");
			if (a_t.id == "cursed") return Loc::T("$AG_WareDesc_cursed", "An enchantment stronger than any you will find, and a curse that comes with it.");
			if (a_t.id == "heroic") return Loc::T("$AG_WareDesc_heroic", "A piece of gear for your level with two strong enchantments.");
			return {};
		}

		bool IsResist(RE::ActorValue a_av)
		{
			using AV = RE::ActorValue;
			return a_av == AV::kResistFire || a_av == AV::kResistFrost || a_av == AV::kResistShock || a_av == AV::kResistMagic || a_av == AV::kPoisonResist ||
			       a_av == AV::kResistDisease;
		}

		// an effect's line on the item card: its own description with the numbers filled in, as the game shows it
		std::string Text(const RE::Effect& a_e)
		{
			std::string s = a_e.baseEffect ? std::string(a_e.baseEffect->magicItemDescription.c_str()) : std::string();
			const auto  put = [&](std::string_view a_tag, const std::string& a_v) {
				for (auto at = s.find(a_tag); at != std::string::npos; at = s.find(a_tag, at + a_v.size())) s.replace(at, a_tag.size(), a_v);
			};
			put("<mag>", std::format("{:.0f}", a_e.effectItem.magnitude));
			put("<dur>", std::to_string(a_e.effectItem.duration));
			return s;
		}

		template <class T = RE::TESForm>
		T* Resolve(const std::string& a_key)
		{
			const auto bar = a_key.find('|');
			if (bar == std::string::npos) return nullptr;
			auto*      dh = RE::TESDataHandler::GetSingleton();
			const auto id = static_cast<RE::FormID>(std::stoul(a_key.substr(bar + 1), nullptr, 16));
			auto*      form = dh ? dh->LookupForm(id, a_key.substr(0, bar)) : nullptr;
			return form ? form->As<T>() : nullptr;
		}

		std::string Name(const RE::TESForm* a_form)
		{
			const char* n = a_form ? a_form->GetName() : nullptr;
			return n && *n ? n : "?";
		}

		void AddFamily(const std::string& a_key, bool a_weapon)
		{
			auto* base = Resolve<RE::EnchantmentItem>(a_key);
			if (!base) {
				SKSE::log::warn("Wares: no base enchantment {}", a_key);
				return;
			}
			Family f{ base, a_weapon, base->data.wornRestrictions };
			for (auto* e : base->effects) {
				if (!e || !e->baseEffect) continue;
				// conditions belong to the record that owns them: one shared with a made enchantment would be freed twice
				if (e->conditions.head) {
					SKSE::log::info("Wares: {} skipped (its effects carry conditions)", a_key);
					return;
				}
				f.fx.push_back({ e->baseEffect, e->effectItem.area });
			}
			if (!f.fx.empty()) g_families.push_back(std::move(f));
		}

		// the masters a vanilla tier comes from. An enchantment overhaul adds tiers of its own under vanilla's bases (Librum:
		// Resist Magic up to 250, Carry Weight 200), and those would stretch "the strongest vanilla tier" far past vanilla;
		// a vanilla record keeps the values the load order gives it, so an overhaul's rebalance of vanilla still counts
		bool FromVanilla(const RE::TESForm* a_form)
		{
			const auto* file = a_form ? a_form->GetFile(0) : nullptr;
			if (!file) return false;
			const auto name = file->GetFilename();
			for (const auto v : { "Skyrim.esm", "Update.esm", "Dawnguard.esm", "HearthFires.esm", "Dragonborn.esm" }) {
				if (_stricmp(std::string(name).c_str(), v) == 0) return true;
			}
			return false;
		}

		// every vanilla tier of each base enchantment (EnchArmorFortifyHealth01..06 -> its base): the range a ware is placed in
		void MeasureTiers()
		{
			auto* dh = RE::TESDataHandler::GetSingleton();
			if (!dh) return;
			for (auto* ench : dh->GetFormArray<RE::EnchantmentItem>()) {
				if (!ench || !ench->data.baseEnchantment || !FromVanilla(ench)) continue;
				for (auto& f : g_families) {
					if (f.base != ench->data.baseEnchantment) continue;
					++f.tiers;
					for (std::size_t i = 0; i < f.fx.size() && i < ench->effects.size(); ++i) {
						auto* e = ench->effects[i];
						if (!e || e->baseEffect != f.fx[i].fx) continue;
						auto&       r = f.fx[i];
						const float m = e->effectItem.magnitude;
						const auto  d = e->effectItem.duration;
						r.measured = true;
						if (!r.seen) {
							r.magMin = r.magMax = m;
							r.durMin = r.durMax = d;
							r.costAtMax = e->cost;
							r.seen = true;
						} else {
							r.magMin = std::min(r.magMin, m);
							r.durMin = std::min(r.durMin, d);
							r.durMax = std::max(r.durMax, d);
							if (m >= r.magMax) {
								r.magMax = m;
								r.costAtMax = e->cost;
							}
						}
					}
				}
			}
			// an effect no tier carries (an overhaul replaced it on the tiers: the robes' Magicka regeneration) is dropped, and
			// so is one with nothing to scale; a family no tier names keeps the base's own numbers, which are all there is
			for (auto& f : g_families) {
				if (f.tiers == 0) continue;
				std::erase_if(f.fx, [](const FamilyFx& r) { return !r.measured || (r.magMax <= 0.0f && r.durMax == 0); });
			}
			std::erase_if(g_families, [](const Family& f) { return f.fx.empty(); });
			for (auto& f : g_families) {
				for (std::size_t i = 0; i < f.fx.size(); ++i) {
					auto& r = f.fx[i];
					if (r.seen || i >= f.base->effects.size()) continue;
					auto* e = f.base->effects[i];
					r.magMin = r.magMax = e->effectItem.magnitude;
					r.durMin = r.durMax = e->effectItem.duration;
					r.costAtMax = e->cost;
					r.seen = true;
				}
			}
		}

		bool Fits(const Family& a_f, RE::TESBoundObject* a_item)
		{
			const bool weapon = a_item->Is(RE::FormType::Weapon);
			if (a_f.weapon != weapon) return false;
			if (weapon || !a_f.worn) return true;
			auto* kw = a_item->As<RE::BGSKeywordForm>();
			if (!kw) return false;
			for (auto* form : a_f.worn->forms) {
				if (auto* k = form ? form->As<RE::BGSKeyword>() : nullptr; k && kw->HasKeyword(k)) return true;
			}
			return false;
		}

		// a gear piece of this kind at the player's level, not enchanted already, with at least a_need families that fit it
		RE::TESBoundObject* RollItem(const Kind& a_kind, int a_need)
		{
			auto*         pc = RE::PlayerCharacter::GetSingleton();
			const auto    level = static_cast<std::uint16_t>(pc ? pc->GetLevel() : 1);
			for (int attempt = 0; attempt < 30; ++attempt) {
				RE::BSScrapArray<RE::CALCED_OBJECT> out;
				a_kind.list->CalculateCurrentFormList(level, 1, out, 0, true);
				if (out.empty()) continue;
				auto* form = out[std::uniform_int_distribution<std::size_t>(0, out.size() - 1)(g_rng)].form;
				auto* item = form ? form->As<RE::TESBoundObject>() : nullptr;
				if (!item || Name(item) == "?") continue;
				if (auto* w = item->As<RE::TESObjectWEAP>()) {
					if (w->formEnchanting || w->IsStaff() || w->IsBound()) continue;
				} else if (auto* a = item->As<RE::TESObjectARMO>()) {
					if (a->formEnchanting) continue;
				} else {
					continue;
				}
				const auto fit = std::ranges::count_if(g_families, [&](const Family& f) { return Fits(f, item); });
				if (fit >= a_need) return item;
			}
			return nullptr;
		}

		std::string Describe(const RE::Effect& a_e)
		{
			const auto name = Name(a_e.baseEffect);
			if (a_e.effectItem.magnitude > 0.0f && a_e.effectItem.duration > 0) return std::format("{} {:.0f} for {}s", name, a_e.effectItem.magnitude, a_e.effectItem.duration);
			if (a_e.effectItem.magnitude > 0.0f) return std::format("{} {:.0f}", name, a_e.effectItem.magnitude);
			if (a_e.effectItem.duration > 0) return std::format("{} for {}s", name, a_e.effectItem.duration);
			return name;
		}
	}

	void Load()
	{
		std::lock_guard l(g_lock);
		g_kinds.clear();
		g_families.clear();
		g_tiers.clear();
		g_curses.clear();
		std::ifstream f("Data/SKSE/Plugins/AdventurersGuild/wares.json");
		if (!f) {
			SKSE::log::warn("Wares: wares.json missing");
			return;
		}
		const auto j = nlohmann::json::parse(f, nullptr, false, true);
		if (j.is_discarded() || !j.is_object()) {
			SKSE::log::error("Wares: wares.json is not valid JSON");
			return;
		}
		// an entry of the wrong type (or a bad FormID) throws; at data load that would take the game down, so it only
		// costs the wares
		try {
			for (auto& k : j.value("kinds", nlohmann::json::array())) {
				auto* list = Resolve<RE::TESLevItem>(k.value("list", ""));
				if (!list) {
					SKSE::log::warn("Wares: kind {} has no list", k.value("id", ""));
					continue;
				}
				g_kinds.push_back({ k.value("id", ""), list, std::max(0, k.value("weight", 1)) });
			}
			for (auto& key : j.value("armorFamilies", std::vector<std::string>{})) AddFamily(key, false);
			for (auto& key : j.value("weaponFamilies", std::vector<std::string>{})) AddFamily(key, true);
			MeasureTiers();
			for (auto& t : j.value("tiers", nlohmann::json::array())) {
				g_tiers.push_back({ t.value("id", ""), t.value("name", ""), t.value("rank", -1), t.value("strength", 0.0f), t.value("multiplier", 1.0f),
					std::max(1, t.value("effects", 1)), t.value("curse", false), std::max(0, t.value("charge", 0)),
					std::max(0, t.value("merit", 0)), std::max(0, t.value("reputation", 0)), std::max(0, t.value("gold", 0)) });
			}
			g_resistCap = j.value("resistCap", 100.0f);
			auto*      dh = RE::TESDataHandler::GetSingleton();
			RE::FormID id = kCurseAbility;
			for (auto& c : j.value("curses", nlohmann::json::array())) {
				Curse curse{ c.value("id", ""), c.value("name", ""), Resolve<RE::EffectSetting>(c.value("effect", "")), c.value("magnitude", 0.0f),
					dh ? dh->LookupForm<RE::SpellItem>(id, kPlugin) : nullptr };
				if (dh) {
					const auto n = kCurseNote + 2 * (id - kCurseAbility);
					curse.noteWeapon = dh->LookupForm<RE::EffectSetting>(n, kPlugin);
					curse.noteWorn = dh->LookupForm<RE::EffectSetting>(n + 1, kPlugin);
				}
				++id;
				if (!curse.fx || !curse.ability || !curse.noteWeapon || !curse.noteWorn) SKSE::log::warn("Wares: curse {} is missing its effect, ability or notes", curse.id);
				g_curses.push_back(std::move(curse));
			}
		} catch (const std::exception& e) {
			SKSE::log::error("Wares: wares.json could not be read ({}); no wares are offered", e.what());
			g_kinds.clear();
			g_families.clear();
			g_tiers.clear();
			g_curses.clear();
		}
		SKSE::log::info("Wares: {} kinds, {} enchantment families, {} tiers, {} curses", g_kinds.size(), g_families.size(), g_tiers.size(), g_curses.size());

		struct EquipSink : RE::BSTEventSink<RE::TESEquipEvent>
		{
			RE::BSEventNotifyControl ProcessEvent(const RE::TESEquipEvent* a_e, RE::BSTEventSource<RE::TESEquipEvent>*) override
			{
				if (a_e && a_e->actor && a_e->actor->IsPlayerRef()) {
					auto* form = RE::TESForm::LookupByID(a_e->baseObject);
					if (form && form->Is(RE::FormType::Weapon)) SKSE::GetTaskInterface()->AddTask([] { SyncCurses(); });
				}
				return RE::BSEventNotifyControl::kContinue;
			}
		};
		static EquipSink sink;
		static bool      registered = false;
		if (!registered) {
			if (auto* src = RE::ScriptEventSourceHolder::GetSingleton()) src->AddEventSink<RE::TESEquipEvent>(&sink);
			registered = true;
		}
	}

	void OnGameLoaded() { SyncCurses(); }

	nlohmann::json Saved()
	{
		std::lock_guard l(g_lock);
		auto            cursed = nlohmann::json::array();
		for (auto& [ench, curse] : g_cursedWeapons) cursed.push_back({ ench, curse });
		return { { "cursedWeapons", cursed } };
	}

	void Restore(const nlohmann::json& a_j)
	{
		std::lock_guard l(g_lock);
		g_cursedWeapons.clear();
		// value() throws on anything but an object, and this runs while a save loads: anything else is "no wares"
		if (!a_j.is_object()) return;
		const auto& list = a_j.find("cursedWeapons");
		if (list == a_j.end() || !list->is_array()) return;
		for (auto& p : *list) {
			if (p.is_array() && p.size() == 2 && p[0].is_number_unsigned() && p[1].is_number_integer()) g_cursedWeapons[p[0].get<RE::FormID>()] = p[1].get<int>();
		}
	}

	std::vector<Offer> Offers()
	{
		std::lock_guard    l(g_lock);
		std::vector<Offer> out;
		if (g_kinds.empty() || g_families.empty()) return out;
		for (int i = 0; i < static_cast<int>(g_tiers.size()); ++i) {
			auto& t = g_tiers[i];
			if (t.rank < 0) continue;  // not offered yet (Heroic: Hero status)
			out.push_back({ i, Loc::F("$AG_Ware_Offer", "{} Item", TierName(t)), TierDesc(t), t.rank, t.merit, t.reputation, t.gold });
		}
		return out;
	}

	std::optional<Made> Make(int a_tier, std::string& a_err)
	{
		auto* pc = RE::PlayerCharacter::GetSingleton();
		auto* mgr = RE::BGSCreatedObjectManager::GetSingleton();
		auto* changes = pc ? pc->GetInventoryChanges() : nullptr;
		if (!pc || !mgr || !changes) {
			a_err = "the game is not ready";
			return {};
		}
		std::unique_lock l(g_lock);
		if (a_tier < 0 || a_tier >= static_cast<int>(g_tiers.size()) || g_kinds.empty()) {
			a_err = "no such tier";
			return {};
		}
		const auto tier = g_tiers[a_tier];

		std::vector<int> weights;
		for (auto& k : g_kinds) weights.push_back(k.weight);
		const auto& kind = g_kinds[std::discrete_distribution<int>(weights.begin(), weights.end())(g_rng)];
		auto*       item = RollItem(kind, tier.effects);
		if (!item) {
			a_err = std::format("no {} could be rolled", kind.id);
			return {};
		}
		const bool weapon = item->Is(RE::FormType::Weapon);

		std::vector<const Family*> fits;
		for (auto& f : g_families) {
			if (Fits(f, item)) fits.push_back(&f);
		}
		std::ranges::shuffle(fits, g_rng);
		fits.resize(std::min<std::size_t>(fits.size(), tier.effects));

		RE::BSTArray<RE::Effect> effects;
		std::vector<std::string> said;
		for (auto* f : fits) {
			for (auto& r : f->fx) {
				RE::Effect e;
				e.baseEffect = r.fx;
				e.effectItem.area = r.area;
				const float s = tier.strength, m = tier.multiplier;
				if (r.magMax > 0.0f) {
					e.effectItem.magnitude = std::round((r.magMin + s * (r.magMax - r.magMin)) * m);
					if (IsResist(r.fx->data.primaryAV)) e.effectItem.magnitude = std::min(e.effectItem.magnitude, g_resistCap);  // past it, nothing
					e.effectItem.duration = r.durMax;
					e.cost = r.costAtMax * e.effectItem.magnitude / r.magMax;
				} else {  // no magnitude (paralysis, soul trap): the strength is in the duration
					e.effectItem.duration = static_cast<std::uint32_t>(std::lround((r.durMin + s * static_cast<float>(r.durMax - r.durMin)) * m));
					e.cost = r.costAtMax * (r.durMax ? static_cast<float>(e.effectItem.duration) / static_cast<float>(r.durMax) : 1.0f);
				}
				said.push_back(Describe(e));
				effects.push_back(e);
			}
		}
		int curse = -1;
		if (tier.curse && !g_curses.empty()) {
			curse = std::uniform_int_distribution<int>(0, static_cast<int>(g_curses.size()) - 1)(g_rng);
			auto& c = g_curses[curse];
			const auto note = [&](RE::EffectSetting* a_note) {  // the description's line; does nothing
				if (!a_note) return;
				RE::Effect e;
				e.baseEffect = a_note;
				e.effectItem.magnitude = c.magnitude;
				effects.push_back(e);
			};
			if (weapon) {
				note(c.noteWeapon);  // the curse itself is an ability while it is held (SyncCurses)
			} else if (c.fx) {  // worn: part of the enchantment, as on vanilla's Necromancer Amulet
				RE::Effect e;
				e.baseEffect = c.fx;
				e.effectItem.magnitude = c.magnitude;
				effects.push_back(e);
				if (c.fx->magicItemDescription.empty()) note(c.noteWorn);  // four of vanilla's have no text
			}
			said.push_back(std::format("curse {} ({} {:.0f})", c.name, Name(c.fx), c.magnitude));
		}
		if (effects.empty()) {
			a_err = std::format("no enchantment fits {}", Name(item));
			return {};
		}

		auto* ench = weapon ? mgr->AddWeaponEnchantment(effects) : mgr->AddArmorEnchantment(effects);
		if (!ench) {
			a_err = "the game made no enchantment";
			return {};
		}
		if (weapon && curse >= 0) g_cursedWeapons[ench->GetFormID()] = curse;
		const auto tierName = TierName(tier);
		const auto name = Loc::F("$AG_Ware_Name", "{} {}", tierName, Name(item));
		Made       made{ tierName, name };
		for (auto& e : effects) {
			const Curse* c = curse >= 0 ? &g_curses[curse] : nullptr;
			const bool  isCurse = c && (e.baseEffect == c->fx || e.baseEffect == c->noteWeapon || e.baseEffect == c->noteWorn);
			auto        text = Text(e);
			if (text.empty()) {
				if (isCurse) continue;  // a vanilla curse effect with no text: its note says it
				text = Describe(e);
			}
			made.lines.push_back({ std::move(text), isCurse });
		}
		l.unlock();

		pc->AddObjectToContainer(item, nullptr, 1, nullptr);
		auto* xl = changes->EnchantObject(item, nullptr, ench, static_cast<std::uint16_t>(weapon ? std::min(tier.charge, 0xFFFF) : 0));
		if (xl) xl->SetOverrideName(name.c_str());
		if (weapon && curse >= 0) SyncCurses();

		made.log = std::format("{} ({:08X}, enchantment {:08X}{}): ", name, item->GetFormID(), ench->GetFormID(), xl ? "" : ", NOT named: no extra list");
		for (std::size_t i = 0; i < said.size(); ++i) made.log += (i ? "; " : "") + said[i];
		SKSE::log::info("Wares: made {}", made.log);
		return made;
	}

	void SyncCurses()
	{
		auto* pc = RE::PlayerCharacter::GetSingleton();
		if (!pc) return;
		std::vector<bool> want;
		std::vector<RE::SpellItem*> abilities;
		{
			std::lock_guard l(g_lock);
			want.assign(g_curses.size(), false);
			for (auto& c : g_curses) abilities.push_back(c.ability);
			if (!Guild::Dormant()) {
				for (const bool left : { false, true }) {
					auto* entry = pc->GetEquippedEntryData(left);
					auto* ench = entry ? entry->GetEnchantment() : nullptr;
					if (!ench) continue;
					if (auto it = g_cursedWeapons.find(ench->GetFormID()); it != g_cursedWeapons.end() && it->second >= 0 && it->second < static_cast<int>(want.size()))
						want[it->second] = true;
				}
			}
		}
		for (std::size_t i = 0; i < abilities.size(); ++i) {
			if (!abilities[i]) continue;
			const bool has = pc->HasSpell(abilities[i]);
			if (want[i] && !has) pc->AddSpell(abilities[i]);
			else if (!want[i] && has) pc->RemoveSpell(abilities[i]);
		}
	}

	std::string DebugDump()
	{
		std::lock_guard l(g_lock);
		std::string     out = std::format("kinds={} families={} tiers={} curses={} cursedWeapons={}\n", g_kinds.size(), g_families.size(), g_tiers.size(), g_curses.size(), g_cursedWeapons.size());
		for (auto& f : g_families) {
			out += std::format("{:08X} {} {} tiers={}:", f.base->GetFormID(), f.weapon ? "weapon" : "armor", Name(f.base), f.tiers);
			for (auto& r : f.fx) out += std::format(" [{} mag {:.0f}-{:.0f} dur {}-{} cost {:.1f}]", Name(r.fx), r.magMin, r.magMax, r.durMin, r.durMax, r.costAtMax);
			out += "\n";
		}
		for (auto& [ench, curse] : g_cursedWeapons) out += std::format("cursed weapon enchantment {:08X} -> curse {}\n", ench, curse);
		return out;
	}
}
