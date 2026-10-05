Scriptname AG_SkyrimNet_Decorators
{SkyrimNet decorator functions. Registered by AG_SkyrimNetInit; not attached to any form.}

; {{ guild_rank_of(actorUUID) }} -> {"status":"member","letter":"C","rank":2,"liaison":false}
; status is "member", "retired" or "none" (a hidden membership reads as none: the secret is kept).
String Function GetGuildRankOf(Actor akActor) Global
	If !akActor
		Return "{\"status\":\"none\",\"letter\":\"?\",\"rank\":-1,\"liaison\":false}"
	EndIf
	Int r = AG_Native.GetActorGuildRank(akActor)
	String status = AG_Native.GetActorGuildStatus(akActor)
	String letter = "?"
	If r >= 0
		letter = AG_Native.GetRankLetter(r)
	EndIf
	String liaison = "false"
	If AG_Native.IsGuildLiaison(akActor)
		liaison = "true"
	EndIf
	Return "{\"status\":\"" + status + "\",\"letter\":\"" + letter + "\",\"rank\":" + r + ",\"liaison\":" + liaison + "}"
EndFunction

; ag_join_status(actor) -> "can_join", or why not: member / retired / guard / child / guild_rep / invalid.
; The eligibility rule of AG_JoinAdventurersGuild (plain string); the DLL applies the same check when it runs.
String Function GetJoinStatusOf(Actor akActor) Global
	If !akActor
		Return "invalid"
	EndIf
	Return AG_Native.GetJoinStatus(akActor)
EndFunction

; {{ ag_party(actorUUID) }} -> the player's adventuring party and this actor's tie to one:
; {"party":true,"name":"Dragon's Bane","membersText":"Jenassa and Lydia","fallenText":"","bondTier":"Companions","days":3,
;  "dungeons":2,"missives":1,"greatBeasts":0,"renown":1,"renownWord":"talked about in the holds",
;  "member":true,"former":false,"memberOf":"Dragon's Bane","bond":"Companions"}   (member/former/bond: this actor's own)
String Function GetPartyOf(Actor akActor) Global
	Return AG_Native.GetPartyInfo(akActor)
EndFunction

; {{ threat_rank_of(actorUUID) }} -> {"letter":"B","rank":3}  (how dangerous this actor is, by level)
String Function GetThreatRankOf(Actor akActor) Global
	If !akActor
		Return "{\"letter\":\"?\",\"rank\":-1}"
	EndIf
	Int r = AG_Native.GetThreatRank(akActor)
	Return "{\"letter\":\"" + AG_Native.GetRankLetter(r) + "\",\"rank\":" + r + "}"
EndFunction

; {{ ag_player(player.UUID) }} -> the player's page of the Guild ledger (Guild::LedgerJson):
; {"registered":true,"rank":"C","merit":120,"reputation":540,"promotionReady":false,
;  "next":{"rank":"B","reputationShort":160,"levelShort":0},"reportsWaiting":{"count":2,...},
;  "missivesCompleted":{"E":3,...},"trophiesCarried":{"kinds":2,"merit":9},"appraisal":"II",...}
String Function GetPlayerLedger(Actor akActor) Global
	Return AG_Native.GetPlayerLedger()
EndFunction
