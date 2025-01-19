/*
 * SetupScript.cpp
 *
 *  Created on: Jan 18, 2025
 *      Author: rlcevg
 */

#include "script/SetupScript.h"
#include "script/ScriptManager.h"

#include "angelscript/add_on/scriptdictionary/scriptdictionary.h"

namespace circuit {

CSetupScript::CSetupScript(CScriptManager* scr)
		: IScript(scr)
{
}

CSetupScript::~CSetupScript()
{
}

CScriptDictionary* CSetupScript::GetModOptions(const CSetupData::ModOptions& modoptions)
{
	/*
	 * dictionary@ mo = aiSetupMgr.GetModOptions();
	 * if (mo.exists("chicken_queendifficulty"))
	 *     AiLog(string(mo["chicken_queendifficulty"]));
	 */
	CScriptDictionary* dict = CScriptDictionary::Create(script->GetEngine());
	int typeId = script->GetEngine()->GetTypeIdByDecl("string");
	for (const auto& kv : modoptions) {
		dict->Set(kv.first, (void*)&kv.second, typeId);
	}
	// Not holding reference to dict and no auto-handles, so
	// dict->Release() is in script's scope.
	return dict;
}

} /* namespace circuit */
