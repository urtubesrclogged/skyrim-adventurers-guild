;/ Compile-time declarations only: the native API of Deeds of Skyrim (DeedsOfSkyrim.dll), trimmed to the two
   functions this mod calls. They only run when that mod fires its DS_DeedUnlocked event. /;
Scriptname DS_Native Native Hidden

String Function GetDeedName(String asId) Global Native          ; "" until accomplished
String Function GetDeedDescription(String asId) Global Native   ; "" until accomplished
