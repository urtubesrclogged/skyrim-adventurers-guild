Scriptname AGHallBannerLock extends ObjectReference
{The guild's cloth banner in the tavern (2026-11-08). It is a moveable static, as vanilla's hanging city banners are, so a bump
could knock it off its bracket (2026-11-07: found fallen into the kitchen). Keyframed, nothing can push it; it still sways, the
sway being its mesh's own looping animation, not physics. It is only locked where it stands: nothing here moves it.}

Event OnLoad()
	SetMotionType(Motion_Keyframed, true)
EndEvent
