// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — CommandDispatch impl (T057).

#include "grpc/CommandDispatch.h"
#include "grpc/Log.h"

#include "CircuitAI.h"
#include "unit/CircuitDef.h"
#include "unit/CircuitUnit.h"
#include "unit/enemy/EnemyInfo.h"

#include "AIFloat3.h"

#include <climits>

namespace circuit::grpc {

namespace {

springai::AIFloat3 ToFloat3(const ::highbar::v1::Vector3& v) {
	return springai::AIFloat3(v.x(), v.y(), v.z());
}

short OptionsOf(const ::highbar::v1::AICommand& cmd) {
	// Each unit-order command carries its own `options` uint32. For the
	// proto arms that don't (drawing/chat/Lua), callers don't hit this
	// helper anyway since they're skipped in the switch.
	using C = ::highbar::v1::AICommand;
	switch (cmd.command_case()) {
	case C::kBuildUnit:       return static_cast<short>(cmd.build_unit().options());
	case C::kStop:            return static_cast<short>(cmd.stop().options());
	case C::kWait:            return static_cast<short>(cmd.wait().options());
	case C::kTimedWait:       return static_cast<short>(cmd.timed_wait().options());
	case C::kMoveUnit:        return static_cast<short>(cmd.move_unit().options());
	case C::kPatrol:          return static_cast<short>(cmd.patrol().options());
	case C::kFight:           return static_cast<short>(cmd.fight().options());
	case C::kAttack:          return static_cast<short>(cmd.attack().options());
	case C::kAttackArea:      return static_cast<short>(cmd.attack_area().options());
	case C::kGuard:           return static_cast<short>(cmd.guard().options());
	case C::kRepair:          return static_cast<short>(cmd.repair().options());
	case C::kReclaimUnit:     return static_cast<short>(cmd.reclaim_unit().options());
	case C::kReclaimArea:     return static_cast<short>(cmd.reclaim_area().options());
	case C::kReclaimInArea:   return static_cast<short>(cmd.reclaim_in_area().options());
	case C::kReclaimFeature:  return static_cast<short>(cmd.reclaim_feature().options());
	case C::kResurrectInArea: return static_cast<short>(cmd.resurrect_in_area().options());
	case C::kSelfDestruct:    return static_cast<short>(cmd.self_destruct().options());
	case C::kDgun:            return static_cast<short>(cmd.dgun().options());
	case C::kSetWantedMaxSpeed: return static_cast<short>(cmd.set_wanted_max_speed().options());
	case C::kSetFireState:    return static_cast<short>(cmd.set_fire_state().options());
	case C::kSetMoveState:    return static_cast<short>(cmd.set_move_state().options());
	default:                  return 0;
	}
}

int TimeoutOf(const ::highbar::v1::AICommand& cmd) {
	using C = ::highbar::v1::AICommand;
	// Proto defaults timeout to 0; the Cmd* APIs want INT_MAX for
	// "no timeout". Map 0 → INT_MAX so F#/Python clients can leave
	// the field unset.
	int t = 0;
	switch (cmd.command_case()) {
	case C::kMoveUnit:        t = cmd.move_unit().timeout();        break;
	case C::kPatrol:          t = cmd.patrol().timeout();           break;
	case C::kFight:           t = cmd.fight().timeout();            break;
	case C::kAttack:          t = cmd.attack().timeout();           break;
	case C::kAttackArea:      t = cmd.attack_area().timeout();      break;
	case C::kRepair:          t = cmd.repair().timeout();           break;
	case C::kReclaimUnit:     t = cmd.reclaim_unit().timeout();     break;
	case C::kReclaimInArea:   t = cmd.reclaim_in_area().timeout();  break;
	case C::kResurrectInArea: t = cmd.resurrect_in_area().timeout(); break;
	case C::kBuildUnit:       t = cmd.build_unit().timeout();       break;
	case C::kDgun:            t = cmd.dgun().timeout();             break;
	default:                  t = 0;                                 break;
	}
	return t <= 0 ? INT_MAX : t;
}

}  // namespace

bool DispatchCommand(::circuit::CCircuitAI* ai,
                     ::circuit::CCircuitUnit* unit,
                     const ::highbar::v1::AICommand& cmd) {
	if (ai == nullptr || unit == nullptr) return false;

	using C = ::highbar::v1::AICommand;
	const short opts = OptionsOf(cmd);
	const int timeout = TimeoutOf(cmd);

	switch (cmd.command_case()) {
	case C::kMoveUnit:
		unit->CmdMoveTo(ToFloat3(cmd.move_unit().to_position()), opts, timeout);
		return true;

	case C::kPatrol:
		unit->CmdPatrolTo(ToFloat3(cmd.patrol().to_position()), opts, timeout);
		return true;

	case C::kFight:
		unit->CmdFightTo(ToFloat3(cmd.fight().to_position()), opts, timeout);
		return true;

	case C::kAttackArea:
		unit->CmdAttackGround(
			ToFloat3(cmd.attack_area().attack_position()), opts, timeout);
		return true;

	case C::kStop:
		unit->CmdStop(opts, timeout);
		return true;

	case C::kWait:
		unit->CmdWait(true);
		return true;

	case C::kBuildUnit: {
		auto* def = ai->GetCircuitDefSafe(
			static_cast<CCircuitDef::Id>(cmd.build_unit().to_build_unit_def_id()));
		if (def == nullptr) {
			LogError(ai, "CommandDispatch",
			         "build: unknown def_id (validated away — should not happen)");
			return false;
		}
		unit->CmdBuild(def, ToFloat3(cmd.build_unit().build_position()),
		               cmd.build_unit().facing(), opts, timeout);
		return true;
	}

	case C::kRepair: {
		const std::int32_t target_id = cmd.repair().repair_unit_id();
		auto* target = ai->GetFriendlyUnit(target_id);
		if (target == nullptr) return false;
		unit->CmdRepair(target, opts, timeout);
		return true;
	}

	case C::kReclaimUnit: {
		const std::int32_t target_id = cmd.reclaim_unit().reclaim_unit_id();
		auto* target = ai->GetFriendlyUnit(target_id);
		if (target == nullptr) return false;
		unit->CmdReclaimUnit(target, opts, timeout);
		return true;
	}

	case C::kReclaimInArea:
		unit->CmdReclaimInArea(
			ToFloat3(cmd.reclaim_in_area().position()),
			cmd.reclaim_in_area().radius(), opts, timeout);
		return true;

	case C::kResurrectInArea:
		unit->CmdResurrectInArea(
			ToFloat3(cmd.resurrect_in_area().position()),
			cmd.resurrect_in_area().radius(), opts, timeout);
		return true;

	case C::kSelfDestruct:
		unit->CmdSelfD(true);
		return true;

	case C::kSetWantedMaxSpeed:
		unit->CmdWantedSpeed(cmd.set_wanted_max_speed().wanted_max_speed());
		return true;

	case C::kSetFireState:
		unit->CmdSetFireState(
			static_cast<CCircuitDef::FireT>(cmd.set_fire_state().fire_state()));
		return true;

	case C::kSetMoveState:
		unit->CmdSetMoveState(
			static_cast<CCircuitDef::MoveT>(cmd.set_move_state().move_state()));
		return true;

	// Proto arms without a direct CCircuitUnit::Cmd* counterpart. The
	// drawing, chat, group, path, Lua, figure, cheat, and transport
	// commands route through springai::* helpers — wiring them is a
	// follow-up after US2 lands its core test.
	default:
		LogError(ai, "CommandDispatch",
		         "command arm not yet wired to engine (skipped)");
		return false;
	}
}

}  // namespace circuit::grpc
