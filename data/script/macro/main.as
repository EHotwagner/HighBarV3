#include "manager/military.as"
#include "../dev/manager/builder.as"
#include "../dev/manager/factory.as"
#include "../dev/manager/economy.as"


namespace Main {

void AiMain()
{
	aiMilitaryMgr.quota.scout = 0;
	aiMilitaryMgr.quota.attack = Military::MACRO_DEFEND_POWER;
	aiMilitaryMgr.quota.raid.min = Military::MACRO_DEFEND_POWER;
	aiMilitaryMgr.quota.raid.avg = Military::MACRO_DEFEND_POWER;

	for (Id defId = 1, count = ai.GetDefCount(); defId <= count; ++defId) {
		CCircuitDef@ cdef = ai.GetCircuitDef(defId);
		if (cdef.costM >= 200.f && !cdef.IsMobile() && aiEconomyMgr.GetEnergyMake(cdef) > 1.f)
			cdef.AddAttribute(Unit::Attr::BASE.type);
	}

	array<string> names = {Factory::armalab, Factory::coralab, Factory::armavp, Factory::coravp,
		Factory::armaap, Factory::coraap, Factory::armasy, Factory::corasy};
	for (uint i = 0; i < names.length(); ++i)
		Factory::userData[ai.GetCircuitDef(names[i]).id].attr |= Factory::Attr::T2;
	names = {Factory::armshltx, Factory::corgant};
	for (uint i = 0; i < names.length(); ++i)
		Factory::userData[ai.GetCircuitDef(names[i]).id].attr |= Factory::Attr::T3;
}

void AiUpdate()
{
}

void AiLuaMessage(const string& in data)
{
	if (data.findLast("DISABLE_CONTROL:", 0) == 0)
		UnitControl(data.substr(16), false);
	else if (data.findLast("ENABLE_CONTROL:", 0) == 0)
		UnitControl(data.substr(15), true);
}

void AiMessage(const string& in data, int fromTeamId)
{
}

void AiUnitFinished(CCircuitUnit@ unit)
{
}

void AiUnitDestroyed(CCircuitUnit@ unit)
{
}

}  // namespace Main


void UnitControl(const string& in idList, bool isEnable)
{
	const array<string>@ ids = idList.split(",");
	for (uint i = 0; i < ids.length(); ++i)
		ai.UnitControl(parseInt(ids[i]), isEnable);
}
