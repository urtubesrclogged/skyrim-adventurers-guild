// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "GuildCard.h"

#include "Counter.h"
#include "Dungeons.h"
#include "Guild.h"
#include "MemberCards.h"

#include <nlohmann/json.hpp>
#include "Loc.h"
#include "PrismaToast.h"
#include "RankCore.h"

#include <chrono>
#include <mutex>
#include <thread>

namespace AG::GuildCard
{
	namespace
	{
		constexpr const char* kPlugin = "AdventurersGuild.esp";
		RE::TESObjectBOOK*    g_card{ nullptr };
		std::atomic<bool>     g_opening{ false };
		std::atomic<bool>     g_issued{ false };  // the free first card has been handed over (co-save)
		std::mutex            g_sealLock;
		std::string           g_seal;             // which region's seal the card carries (co-save): "" = Skyrim's
		std::string g_issuedAt;  // the counter city that issued the card in hand; guarded by g_sealLock
		RE::TESGlobal*        g_gMissing{ nullptr };  // AG_CardMissingGlobal: 1 while a member carries no card (SkyrimNet eligibility)
		std::atomic<int>      g_hotkey{ -1 };     // SkyUI key code (DirectInput scan code; mouse 256+, gamepad 266+), <= 0 none

		// The menus a card can be read from. They pause the game or sit over the world; the card opens after them.
		constexpr std::string_view kUnder[]{ RE::BookMenu::MENU_NAME, RE::InventoryMenu::MENU_NAME, RE::ContainerMenu::MENU_NAME,
			RE::TweenMenu::MENU_NAME, RE::FavoritesMenu::MENU_NAME, RE::BarterMenu::MENU_NAME, RE::GiftMenu::MENU_NAME };

		// game thread
		void UpdateMissing()
		{
			auto* pc = RE::PlayerCharacter::GetSingleton();
			if (!g_gMissing || !g_card || !pc) return;
			g_gMissing->value = Guild::Registered() && !Guild::Dormant() && pc->GetItemCount(g_card) <= 0 ? 1.0f : 0.0f;
		}

		// the card entering or leaving the player's inventory (dropped, stored, sold, picked up, handed over)
		class CarrySink : public RE::BSTEventSink<RE::TESContainerChangedEvent>
		{
		public:
			static CarrySink* Get()
			{
				static CarrySink s;
				return &s;
			}

			RE::BSEventNotifyControl ProcessEvent(const RE::TESContainerChangedEvent* a_e, RE::BSTEventSource<RE::TESContainerChangedEvent>*) override
			{
				if (a_e && g_card && a_e->baseObj == g_card->GetFormID() && (a_e->oldContainer == 0x14 || a_e->newContainer == 0x14))
					SKSE::GetTaskInterface()->AddTask(UpdateMissing);
				return RE::BSEventNotifyControl::kContinue;
			}
		};

		bool AnyUnder()
		{
			auto* ui = RE::UI::GetSingleton();
			if (!ui) return false;
			for (auto name : kUnder)
				if (ui->IsMenuOpen(name)) return true;
			return false;
		}

		// Close what the card was read from, then open it: checked every 100 ms for up to 4 s (a menu closes over a
		// few frames, and the VR inventory takes longer). If the menus never go, nothing opens.
		std::mutex     g_memberLock;
		nlohmann::json g_memberToShow;  // set when the book being read is another adventurer's card

		void OpenWhenClear()
		{
			if (g_opening.exchange(true)) return;
			SKSE::GetTaskInterface()->AddTask([] {
				if (auto* q = RE::UIMessageQueue::GetSingleton())
					for (auto name : kUnder) q->AddMessage(name, RE::UI_MESSAGE_TYPE::kHide, nullptr);
			});
			std::thread([] {
				for (int i = 0; i < 40; ++i) {
					std::this_thread::sleep_for(std::chrono::milliseconds(100));
					std::atomic<int> state{ 0 };  // 1 clear, 2 still under a menu
					SKSE::GetTaskInterface()->AddTask([&state] { state = AnyUnder() ? 2 : 1; });
					for (int w = 0; w < 50 && state.load() == 0; ++w) std::this_thread::sleep_for(std::chrono::milliseconds(10));
					if (state.load() == 1) {
						SKSE::GetTaskInterface()->AddTask([] {
							nlohmann::json member;
							{
								std::lock_guard l(g_memberLock);
								member = std::move(g_memberToShow);
								g_memberToShow = nullptr;
							}
							if (member.is_null()) Counter::OpenCard();
							else Counter::OpenMemberCard(member);  // someone else's card: the page in its member view
						});
						break;
					}
				}
				g_opening = false;
			}).detach();
		}

		class Sink : public RE::BSTEventSink<RE::MenuOpenCloseEvent>
		{
		public:
			static Sink* Get()
			{
				static Sink s;
				return &s;
			}

			RE::BSEventNotifyControl ProcessEvent(const RE::MenuOpenCloseEvent* a_e, RE::BSTEventSource<RE::MenuOpenCloseEvent>*) override
			{
				if (!a_e || !a_e->opening || !g_card || a_e->menuName != RE::BookMenu::MENU_NAME) return RE::BSEventNotifyControl::kContinue;
				// which book: asked on the game thread, where the menu's target is set
				SKSE::GetTaskInterface()->AddTask([] {
					// another adventurer's card: which copy, by its item name (in the world, the reference's; in a menu, the
					// selected row's). A name this save has no record of is left to the book's own text.
					if (MemberCards::IsPersonal(RE::BookMenu::GetTargetForm())) {
						auto        ref = RE::BookMenu::GetTargetReference();
						const char* shown = ref ? ref->GetDisplayFullName() : nullptr;
						const auto  item = ref ? std::string(shown ? shown : "") : MemberCards::SelectedItemName();
						auto        member = MemberCards::CardFor(item);
						SKSE::log::info("GuildCard: \"{}\" is being read ({}) - {}", item, ref ? "where it lies" : "from a menu", member.is_null() ? "no record of it" : "shown");
						if (member.is_null()) return;
						if (ref)
							if (auto* pc = RE::PlayerCharacter::GetSingleton()) pc->PickUpObject(ref.get(), 1, false, true);  // as the player's own: read is also how it is taken
						{
							std::lock_guard l(g_memberLock);
							g_memberToShow = std::move(member);
						}
						OpenWhenClear();
						return;
					}
					if (RE::BookMenu::GetTargetForm() != g_card) return;
					if (!Guild::Registered() || Guild::Dormant()) return;  // the note's own text is shown instead
					// Read where it lies in the world: the Book Menu we are about to close is also where "Take" lives, so
					// the card is picked up as it is read (a card on the floor could otherwise be read but never taken).
					if (auto ref = RE::BookMenu::GetTargetReference(); ref)
						if (auto* pc = RE::PlayerCharacter::GetSingleton()) pc->PickUpObject(ref.get(), 1, false, true);
					OpenWhenClear();
				});
				return RE::BSEventNotifyControl::kContinue;
			}
		};
	}

	namespace
	{
		// SKSE's key codes for the gamepad (what SkyUI's key-map option stores)
		int PadKey(std::uint32_t a_id)
		{
			switch (a_id) {
			case 0x0001: return 266;  // D-pad up
			case 0x0002: return 267;
			case 0x0004: return 268;
			case 0x0008: return 269;
			case 0x0010: return 270;  // Start
			case 0x0020: return 271;  // Back
			case 0x0040: return 272;  // left thumb
			case 0x0080: return 273;
			case 0x0100: return 274;  // left shoulder
			case 0x0200: return 275;
			case 0x1000: return 276;  // A
			case 0x2000: return 277;
			case 0x4000: return 278;
			case 0x8000: return 279;
			case 0x0009: return 280;  // left trigger
			case 0x000A: return 281;
			default: return -1;
			}
		}

		// The key opens the card in the world, and closes it again. Never while another menu has the keyboard.
		void OnHotkey()
		{
			auto* ui = RE::UI::GetSingleton();
			if (!ui || !g_card) return;
			if (Counter::IsOpen()) {
				if (Counter::IsCardOnly()) Counter::Close();
				return;
			}
			if (ui->GameIsPaused() || ui->IsItemMenuOpen() || ui->IsApplicationMenuOpen() || ui->IsMenuOpen(RE::DialogueMenu::MENU_NAME) ||
				ui->IsMenuOpen(RE::CraftingMenu::MENU_NAME) || ui->IsMenuOpen(RE::Console::MENU_NAME)) {
				SKSE::log::info("GuildCard: open requested while a menu is up - ignored");
				return;
			}
			if (!Guild::Registered() || Guild::Dormant()) return;
			if (!Has()) {
				RE::SendHUDMessage::ShowHUDMessage(Loc::T("$AG_Card_NotCarried", "You are not carrying your guild card.").c_str());
				return;
			}
			Counter::OpenCard();
		}

		class KeySink : public RE::BSTEventSink<RE::InputEvent*>
		{
		public:
			static KeySink* Get()
			{
				static KeySink s;
				return &s;
			}

			RE::BSEventNotifyControl ProcessEvent(RE::InputEvent* const* a_events, RE::BSTEventSource<RE::InputEvent*>*) override
			{
				const int key = g_hotkey.load();
				if (key <= 0) return RE::BSEventNotifyControl::kContinue;
				for (auto* e = a_events ? *a_events : nullptr; e; e = e->next) {
					const auto* b = e->AsButtonEvent();
					if (!b || !b->IsDown()) continue;
					int code = -1;
					switch (e->GetDevice()) {
					case RE::INPUT_DEVICE::kKeyboard: code = static_cast<int>(b->GetIDCode()); break;
					case RE::INPUT_DEVICE::kMouse: code = 256 + static_cast<int>(b->GetIDCode()); break;
					case RE::INPUT_DEVICE::kGamepad: code = PadKey(b->GetIDCode()); break;
					default: break;
					}
					if (code == key) SKSE::GetTaskInterface()->AddTask(OnHotkey);
				}
				return RE::BSEventNotifyControl::kContinue;
			}
		};
	}

	void SetHotkey(int a_key)
	{
		if (g_hotkey.exchange(a_key) != a_key) SKSE::log::info("GuildCard: hotkey {}", a_key > 0 ? std::to_string(a_key) : "none");
	}
	int Hotkey() { return g_hotkey.load(); }
	void Toggle()
	{
		SKSE::log::info("GuildCard: open/close requested by a mod event");
		SKSE::GetTaskInterface()->AddTask(OnHotkey);
	}

	void Install()
	{
		auto* dh = RE::TESDataHandler::GetSingleton();
		g_card = dh ? dh->LookupForm<RE::TESObjectBOOK>(0x81A, kPlugin) : nullptr;
		if (!g_card) {
			SKSE::log::error("GuildCard: AG_GuildCard (0x81A) not found in {} - no physical guild card", kPlugin);
			return;
		}
		if (auto* ui = RE::UI::GetSingleton()) ui->AddEventSink<RE::MenuOpenCloseEvent>(Sink::Get());
		if (auto* input = RE::BSInputDeviceManager::GetSingleton()) input->AddEventSink(KeySink::Get());
		g_gMissing = dh->LookupForm<RE::TESGlobal>(0x81E, kPlugin);
		if (auto* src = RE::ScriptEventSourceHolder::GetSingleton()) src->AddEventSink<RE::TESContainerChangedEvent>(CarrySink::Get());
		SKSE::log::info("GuildCard: watching for the card being read");
	}

	namespace
	{
		void SyncCard(bool a_announce);
	}

	void Sync(bool a_announce)
	{
		SyncCard(a_announce);
		UpdateMissing();  // also on every load, registration and promotion
	}

	namespace
	{
	void SyncCard(bool a_announce)
	{
		auto* pc = RE::PlayerCharacter::GetSingleton();
		if (!g_card || !pc || !Guild::Registered() || Guild::Dormant()) return;
		const int rank = Guild::Rank();
		if (rank >= 0) g_card->fullName = Loc::F("$AG_Item_GuildCardRank", "Adventurers Guild Card (Rank {})", Letter(rank));
		if (g_issued.exchange(true)) return;  // the free one has been given: a missing card is replaced by a liaison, for a fee
		if (pc->GetItemCount(g_card) > 0) return;
		pc->AddObjectToContainer(g_card, nullptr, 1, nullptr);
		SKSE::log::info("GuildCard: first card issued (rank {})", rank >= 0 ? Letter(rank) : '-');
		if (a_announce) RE::SendHUDMessage::ShowHUDMessage(Loc::T("$AG_Hud_CardIssued", "Guild card added. Read it to see your standing with the Guild.").c_str());
	}
	}

	bool Has()
	{
		auto* pc = RE::PlayerCharacter::GetSingleton();
		return g_card && pc && pc->GetItemCount(g_card) > 0;
	}

	void Stamp(const std::string& a_city)
	{
		std::lock_guard l(g_sealLock);
		g_seal = a_city == "Raven Rock" ? "morrowind" : "";
		g_issuedAt = a_city;
		SKSE::log::info("GuildCard: issued at {} - {} seal", a_city.empty() ? "an unnamed counter" : a_city, g_seal.empty() ? "Skyrim's" : "Morrowind's");
	}

	std::string IssuedAt()
	{
		std::lock_guard l(g_sealLock);
		return g_issuedAt;
	}

	void SetIssuedAt(const std::string& a_city)
	{
		std::lock_guard l(g_sealLock);
		g_issuedAt = a_city;
	}

	std::string Seal()
	{
		std::lock_guard l(g_sealLock);
		return g_seal;
	}

	void SetSeal(const std::string& a_seal)
	{
		std::lock_guard l(g_sealLock);
		g_seal = a_seal;
	}

	std::string Replace(const std::string& a_city)
	{
		auto* pc = RE::PlayerCharacter::GetSingleton();
		if (!g_card || !pc || !Guild::Registered() || Guild::Dormant()) return {};
		if (Has()) return Loc::T("$AG_Card_HaveOne", "You already carry your guild card.");
		const int fee = Guild::CardFee();
		if (!Guild::PayGold(fee)) return Loc::F("$AG_Card_NoGold", "A replacement guild card costs {} gold.", fee);
		pc->AddObjectToContainer(g_card, nullptr, 1, nullptr);
		g_issued = true;
		Stamp(a_city);   // a card reissued in another region carries that region's seal
		SetHoldStamps({});          // a new card is a blank one: its hold stamps are collected again, counter by counter
		CollectHoldStamp(a_city);   // ... starting with this counter's, if it is earned
		SKSE::log::info("GuildCard: replacement issued for {} gold", fee);
		return Loc::T("$AG_Card_Replaced", "The Guild has issued you a new guild card.");
	}

	namespace
	{
		std::vector<std::string> g_holdStamps;  // guarded by g_sealLock
		std::vector<std::string> g_everStamped; // guarded by g_sealLock
	}

	bool EverStamped(const std::string& a_city)
	{
		std::lock_guard l(g_sealLock);
		return std::find(g_everStamped.begin(), g_everStamped.end(), a_city) != g_everStamped.end();
	}

	std::vector<std::string> EverStampedList()
	{
		std::lock_guard l(g_sealLock);
		return g_everStamped;
	}

	void SetEverStamped(std::vector<std::string> a_cities)
	{
		std::lock_guard l(g_sealLock);
		g_everStamped = std::move(a_cities);
	}

	std::vector<std::string> HoldStamps()
	{
		std::lock_guard l(g_sealLock);
		return g_holdStamps;
	}

	void SetHoldStamps(std::vector<std::string> a_cities)
	{
		std::lock_guard l(g_sealLock);
		g_holdStamps = std::move(a_cities);
	}

	std::string StampFile(const std::string& a_city)
	{
		std::string out;
		for (const char c : a_city)
			if (std::isalnum(static_cast<unsigned char>(c))) out += static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
		return out;
	}

	bool CollectHoldStamp(const std::string& a_city)
	{
		if (a_city.empty() || !Guild::Registered() || Guild::Dormant() || !Has()) return false;  // no card in hand, nothing to stamp
		const int cleared = Dungeons::ClearedIn(a_city);
		if (cleared < Guild::StampDungeons()) return false;
		bool first = false;
		{
			std::lock_guard l(g_sealLock);
			if (std::find(g_holdStamps.begin(), g_holdStamps.end(), a_city) != g_holdStamps.end()) return false;
			g_holdStamps.push_back(a_city);
			first = std::find(g_everStamped.begin(), g_everStamped.end(), a_city) == g_everStamped.end();
			if (first) g_everStamped.push_back(a_city);
		}
		const auto city = Guild::CityName(a_city);
		Guild::Record(Loc::F("$AG_Log_Stamp", "Your guild card was stamped in {}.", city));
		PrismaToast::Show(Loc::T("$AG_Toast_StampAdded", "GUILD CARD STAMPED"), Loc::F("$AG_Toast_StampAddedSub", "{}'s hold stamp is on your card", city),
			"tex/skin/stamp_" + StampFile(a_city) + ".png");
		SKSE::log::info("GuildCard: stamped at {} ({} dungeon reports from the hold handed in, {} needed){}", a_city, cleared, Guild::StampDungeons(), first ? " - the first time for this hold" : "");
		Counter::Stamped(first);
		return true;
	}

	bool Issued() { return g_issued.load(); }
	void SetIssued(bool a_issued) { g_issued = a_issued; }
}
