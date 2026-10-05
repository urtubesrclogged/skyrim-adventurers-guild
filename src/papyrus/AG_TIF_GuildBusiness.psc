;BEGIN FRAGMENT CODE - Do not edit anything between this and the end comment
;NEXT FRAGMENT INDEX 1
Scriptname AG_TIF_GuildBusiness Extends TopicInfo Hidden

;BEGIN FRAGMENT Fragment_0
Function Fragment_0(ObjectReference akSpeakerRef)
Actor akSpeaker = akSpeakerRef as Actor
;BEGIN CODE
ShowBarterMenu(akSpeaker)
;END CODE
EndFunction
;END FRAGMENT

;END FRAGMENT CODE - Do not edit anything between this and the begin comment

; Opens the Adventurers Guild counter (the counter is this rep's "shop" of Guild services). It is named ShowBarterMenu
; on purpose: SkyrimNet only offers its AI a dialogue line as an action when the line's fragment calls a service
; function it recognises by name (showbartermenu = "Trade"), and a repeatable service is what this is. It never opens
; the vanilla barter menu. See KNOWLEDGEBASE.local.md, "SkyrimNet lists a dialogue line as an action only if...".
Function ShowBarterMenu(Actor akSpeaker)
	AG_Native.ActionOpenCounter(akSpeaker)
EndFunction
