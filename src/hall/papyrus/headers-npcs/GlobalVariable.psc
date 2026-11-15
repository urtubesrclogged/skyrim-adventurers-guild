ScriptName GlobalVariable Extends Form Native Hidden

Float Function GetValue() native
Function SetValue(Float afNewValue) native
Int Function GetValueInt()
	Return GetValue() as Int
EndFunction
Function SetValueInt(Int aiNewValue)
	SetValue(aiNewValue as Float)
EndFunction
