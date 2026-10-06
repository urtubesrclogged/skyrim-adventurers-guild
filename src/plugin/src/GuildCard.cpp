// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild

#include "GuildCard.h"

#include "Counter.h"
#include "Guild.h"
#include "Loc.h"
#include "RankCore.h"

#include <chrono>
#include <thread>

namespace AG::GuildCard
{
	namespace
	{
		constexpr const char* kPlugin = "AdventurersGuild.esp";
		RE::TESObjectBOOK*    g_card{ nullptr };
		std::atomic<bool>     g_opening{ false };
		std::atomic<bool>     g_issued{ false };  // the free first card has been handed over (co-save)
		std::atomic<int>      g_hotkey{ -1 };     // SkyUI key code (DirectInput scan code; mouse 256+, gamepad 266+), <= 0 none

		// The menus a card can be read from. They pause the game or sit over the world; the card opens after them.
		constexpr std::string_view kUnder[]{ RE::BookMenu::MENU_NAME, RE::InventoryMenu::MENU_NAME, RE::ContainerMenu::MENU_NAME,
			RE::TweenMenu::MENU_NAME, RE::FavoritesMenu::MENU_NAME, RE::BarterMenu::MENU_NAME, RE::GiftMenu::MENU_NAME };

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
						SKSE::GetTaskInterface()->AddTask([] { Counter::OpenCard(); });
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
				ui->IsMenuOpen(RE::CraftingMenu::MENU_NAME) || ui->IsMenuOpen(RE::Console::MENU_NAME))
				return;
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
		SKSE::log::info("GuildCard: watching for the card being read");
	}

	void Sync(bool a_announce)
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

	bool Has()
	{
		auto* pc = RE::PlayerCharacter::GetSingleton();
		return g_card && pc && pc->GetItemCount(g_card) > 0;
	}

	std::string Replace()
	{
		auto* pc = RE::PlayerCharacter::GetSingleton();
		if (!g_card || !pc || !Guild::Registered() || Guild::Dormant()) return {};
		if (Has()) return Loc::T("$AG_Card_HaveOne", "You already carry your guild card.");
		const int fee = Guild::CardFee();
		if (!Guild::PayGold(fee)) return Loc::F("$AG_Card_NoGold", "A replacement guild card costs {} gold.", fee);
		pc->AddObjectToContainer(g_card, nullptr, 1, nullptr);
		g_issued = true;
		SKSE::log::info("GuildCard: replacement issued for {} gold", fee);
		return Loc::T("$AG_Card_Replaced", "The Guild has issued you a new guild card.");
	}

	bool Issued() { return g_issued.load(); }
	void SetIssued(bool a_issued) { g_issued = a_issued; }
}
