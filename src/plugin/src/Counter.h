#pragma once

// The guild counter: an interactive PrismaUI window opened from the innkeeper topic "I have guild
// business." (Guild Card, Reports to claim, Merit services, Records). Built on the Deeds of Skyrim menu
// pattern (Show + Focus, JS listeners), which is proven for VR clicks. A safe no-op without PrismaUI.
namespace AG::Counter
{
	void Install();            // at kDataLoaded
	void OpenAfterDialogue(std::string a_branch);  // opens once the Dialogue Menu closes; a_branch = the liaison's city
	std::string Branch();                           // city of the counter currently open ("" = none / debug)
	void Open();
	void Close();
	bool IsOpen();
	void Refresh();            // push fresh data if open (any thread)
	bool IsOpenComposite();   // VR runtime is OpenComposite rather than SteamVR (false outside VR)
	int  ViewOrder();          // PrismaUI order of the counter view (-1 if none), so a toast can sit above it
}
