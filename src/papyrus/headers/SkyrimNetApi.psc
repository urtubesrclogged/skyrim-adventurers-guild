;/ Compile-time declarations only: SkyrimNet's SkyrimNetApi (optional; only called when SkyrimNet.esp is loaded), trimmed to the members this mod's scripts call.
   The installed mod's own script is what runs; this mod does not ship it. /;
Scriptname SkyrimNetApi Hidden

Int Function RegisterDecorator(String decoratorID, String sourceScript, String functionName) Global Native
Int Function RegisterPersistentEvent(String content, Actor originatorActor, Actor targetActor) Global Native
Int Function RegisterShortLivedEvent(String eventId, String eventType, String description, String data, Int ttlMs, Actor sourceActor, Actor targetActor) Global Native
