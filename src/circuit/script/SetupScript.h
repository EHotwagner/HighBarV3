/*
 * SetupScript.h
 *
 *  Created on: Jan 18, 2025
 *      Author: rlcevg
 */

#ifndef SRC_CIRCUIT_SCRIPT_SETUPSCRIPT_H_
#define SRC_CIRCUIT_SCRIPT_SETUPSCRIPT_H_

#include "script/Script.h"
#include "setup/SetupData.h"

class CScriptDictionary;

namespace circuit {

class CScriptManager;

class CSetupScript: public IScript {
public:
	CSetupScript(CScriptManager* scr);
	virtual ~CSetupScript();

	virtual bool Init() override { return true; }

	CScriptDictionary* GetModOptions(const CSetupData::ModOptions& modoptions);
};

} /* namespace circuit */

#endif /* SRC_CIRCUIT_SCRIPT_SETUPSCRIPT_H_ */
