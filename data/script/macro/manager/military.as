#include "../../define.as"
#include "../../unit.as"
#include "../../task.as"


namespace Military {

const float MACRO_DEFEND_POWER = 1000000.0f;

IUnitTask@ AiMakeTask(CCircuitUnit@ unit)
{
	return aiMilitaryMgr.Enqueue(TaskF::Defend(Task::FightType::ATTACK, MACRO_DEFEND_POWER));
}

void AiTaskAdded(IUnitTask@ task)
{
}

void AiTaskRemoved(IUnitTask@ task, bool done)
{
}

void AiUnitAdded(CCircuitUnit@ unit, Unit::UseAs usage)
{
}

void AiUnitRemoved(CCircuitUnit@ unit, Unit::UseAs usage)
{
}

void AiLoad(IStream& istream)
{
}

void AiSave(OStream& ostream)
{
}

void AiMakeDefence(int cluster, const AIFloat3& in pos)
{
	if ((ai.frame > 2 * MINUTE)
		|| (aiEconomyMgr.metal.income > 6.f)
		|| (aiEnemyMgr.mobileThreat > 0.f))
	{
		aiMilitaryMgr.DefaultMakeDefence(cluster, pos);
	}
}

}  // namespace Military
