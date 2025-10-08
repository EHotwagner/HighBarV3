/*
 * FactoryData.h
 *
 *  Created on: Dec 8, 2015
 *      Author: rlcevg
 */

#ifndef SRC_CIRCUIT_UNIT_FACTORYDATA_H_
#define SRC_CIRCUIT_UNIT_FACTORYDATA_H_

#include "unit/CircuitDef.h"

#include <unordered_map>

namespace circuit {

class CCircuitAI;

class CFactoryData {
public:
	CFactoryData();
	virtual ~CFactoryData();

	void InitFactoryDefs(CCircuitAI *circuit);

	CCircuitDef* GetFactoryToBuild(CCircuitAI* circuit, springai::AIFloat3 position = -RgtVector,
								   bool isStart = false, bool isReset = false);
	void AddFactory(const CCircuitDef* cdef);
	void DelFactory(const CCircuitDef* cdef);

	bool IsT1Factory(const CCircuitDef* cdef);

private:
	void ReadConfig(CCircuitAI* circuit);

	unsigned int choiceNum;
	unsigned int noAirNum = 0;
	struct SFactory {
		CCircuitDef::Id id;
		float startImp;  // importance[0]
		float switchImp;  // importance[1]
		int count;
		float mapSpeedPerc;
		bool isT1;  // FIXME: DEBUG Silly t1 detection
	};
	float airMapPerc = 0.f;
	float minOffset = 0.f;
	float lenOffset = 0.f;
	std::unordered_map<CCircuitDef::Id, SFactory> allFactories;

//	std::unordered_map<CCircuitDef::Id, std::unordered_set<CCircuitDef::Id>> factoryDefs;  // builder: set<factory>
};

} // namespace circuit

#endif // SRC_CIRCUIT_UNIT_FACTORYDATA_H_
