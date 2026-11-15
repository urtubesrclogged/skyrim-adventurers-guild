// Adventurers Guild - Copyright (C) 2026 urtubesrclogged
// SPDX-License-Identifier: GPL-3.0-or-later
// Free software under the GNU GPL v3 or later, with the additional permissions in EXCEPTIONS.md. NO WARRANTY.
// See LICENSE and EXCEPTIONS.md at the repository root: https://github.com/urtubesrclogged/skyrim-adventurers-guild
#pragma once

// The Guild Hall's board (2.0): the work of every hold, read and taken where it hangs. A PrismaUI page of its own
// (board.html: the hall counter's list on the board's wood), opened by activating the board in the great hall. Its data
// is the hall counter's (GuildHall::CounterData) and its Take and Details are the counter's paths, so the two never
// disagree. Its postings rotate a day at a time: of the three arrangements the hall places on one spot, the day's one
// is enabled whenever the board loads (GuildBoard.cpp, Rotate).
namespace AG::GuildBoard
{
	void Install();  // at kDataLoaded: the view, and the board's activation
	void Open();     // also AG_Native.OpenGuildBoard()
	void Close();
	bool IsOpen();
	void Invoke(const std::string& a_script);  // into the page while it is open: the controller's buttons (Counter's pad reader)
}
