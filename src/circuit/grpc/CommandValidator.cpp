// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — CommandValidator impl (T056).

#include "grpc/CommandValidator.h"

#include "CircuitAI.h"
#include "unit/CircuitDef.h"
#include "unit/CircuitUnit.h"

#include "AIFloat3.h"

#include <cmath>
#include <sstream>

namespace circuit::grpc {

namespace {

// Pull the "position" of a command for extents checking. Returns
// nullptr when the command arm has no position to validate. Only the
// arms with a 3D world-space target need checking; Lua, groups, and
// on/off toggles are position-free.
const ::highbar::v1::Vector3* PositionOf(
		const ::highbar::v1::AICommand& cmd) {
	using C = ::highbar::v1::AICommand;
	switch (cmd.command_case()) {
	case C::kDrawAddPoint:       return &cmd.draw_add_point().position();
	case C::kDrawRemovePoint:    return &cmd.draw_remove_point().position();
	case C::kSetLastPosMessage:  return &cmd.set_last_pos_message().position();
	case C::kGiveMeNewUnit:      return &cmd.give_me_new_unit().position();
	case C::kSetFigurePosition:  return &cmd.set_figure_position().position();
	case C::kDrawUnit:           return &cmd.draw_unit().position();
	case C::kBuildUnit:          return &cmd.build_unit().build_position();
	case C::kMoveUnit:           return &cmd.move_unit().to_position();
	case C::kPatrol:             return &cmd.patrol().to_position();
	case C::kFight:              return &cmd.fight().to_position();
	case C::kAttackArea:         return &cmd.attack_area().attack_position();
	case C::kReclaimArea:        return &cmd.reclaim_area().position();
	case C::kReclaimInArea:      return &cmd.reclaim_in_area().position();
	case C::kRestoreArea:        return &cmd.restore_area().position();
	case C::kResurrectInArea:    return &cmd.resurrect_in_area().position();
	case C::kCaptureArea:        return &cmd.capture_area().position();
	case C::kSetBase:            return &cmd.set_base().base_position();
	case C::kLoadUnitsArea:      return &cmd.load_units_area().position();
	case C::kUnloadUnit:         return &cmd.unload_unit().to_position();
	case C::kUnloadUnitsArea:    return &cmd.unload_units_area().to_position();
	default:                     return nullptr;
	}
}

}  // namespace

bool CommandValidator::TryCommandUnitId(const ::highbar::v1::AICommand& cmd,
                                        std::int32_t* unit_id) const {
	if (unit_id == nullptr) return false;
	using C = ::highbar::v1::AICommand;
	switch (cmd.command_case()) {
	case C::kBuildUnit:            *unit_id = cmd.build_unit().unit_id(); return true;
	case C::kStop:                 *unit_id = cmd.stop().unit_id(); return true;
	case C::kWait:                 *unit_id = cmd.wait().unit_id(); return true;
	case C::kTimedWait:            *unit_id = cmd.timed_wait().unit_id(); return true;
	case C::kSquadWait:            *unit_id = cmd.squad_wait().unit_id(); return true;
	case C::kDeathWait:            *unit_id = cmd.death_wait().unit_id(); return true;
	case C::kGatherWait:           *unit_id = cmd.gather_wait().unit_id(); return true;
	case C::kMoveUnit:             *unit_id = cmd.move_unit().unit_id(); return true;
	case C::kPatrol:               *unit_id = cmd.patrol().unit_id(); return true;
	case C::kFight:                *unit_id = cmd.fight().unit_id(); return true;
	case C::kAttack:               *unit_id = cmd.attack().unit_id(); return true;
	case C::kAttackArea:           *unit_id = cmd.attack_area().unit_id(); return true;
	case C::kGuard:                *unit_id = cmd.guard().unit_id(); return true;
	case C::kRepair:               *unit_id = cmd.repair().unit_id(); return true;
	case C::kReclaimUnit:          *unit_id = cmd.reclaim_unit().unit_id(); return true;
	case C::kReclaimArea:          *unit_id = cmd.reclaim_area().unit_id(); return true;
	case C::kReclaimInArea:        *unit_id = cmd.reclaim_in_area().unit_id(); return true;
	case C::kReclaimFeature:       *unit_id = cmd.reclaim_feature().unit_id(); return true;
	case C::kRestoreArea:          *unit_id = cmd.restore_area().unit_id(); return true;
	case C::kResurrect:            *unit_id = cmd.resurrect().unit_id(); return true;
	case C::kResurrectInArea:      *unit_id = cmd.resurrect_in_area().unit_id(); return true;
	case C::kCapture:              *unit_id = cmd.capture().unit_id(); return true;
	case C::kCaptureArea:          *unit_id = cmd.capture_area().unit_id(); return true;
	case C::kSetBase:              *unit_id = cmd.set_base().unit_id(); return true;
	case C::kSelfDestruct:         *unit_id = cmd.self_destruct().unit_id(); return true;
	case C::kLoadUnits:            *unit_id = cmd.load_units().unit_id(); return true;
	case C::kLoadUnitsArea:        *unit_id = cmd.load_units_area().unit_id(); return true;
	case C::kLoadOnto:             *unit_id = cmd.load_onto().unit_id(); return true;
	case C::kUnloadUnit:           *unit_id = cmd.unload_unit().unit_id(); return true;
	case C::kUnloadUnitsArea:      *unit_id = cmd.unload_units_area().unit_id(); return true;
	case C::kSetWantedMaxSpeed:    *unit_id = cmd.set_wanted_max_speed().unit_id(); return true;
	case C::kStockpile:            *unit_id = cmd.stockpile().unit_id(); return true;
	case C::kDgun:                 *unit_id = cmd.dgun().unit_id(); return true;
	case C::kCustom:               *unit_id = cmd.custom().unit_id(); return true;
	case C::kSetOnOff:             *unit_id = cmd.set_on_off().unit_id(); return true;
	case C::kSetRepeat:            *unit_id = cmd.set_repeat().unit_id(); return true;
	case C::kSetMoveState:         *unit_id = cmd.set_move_state().unit_id(); return true;
	case C::kSetFireState:         *unit_id = cmd.set_fire_state().unit_id(); return true;
	case C::kSetTrajectory:        *unit_id = cmd.set_trajectory().unit_id(); return true;
	case C::kSetAutoRepairLevel:   *unit_id = cmd.set_auto_repair_level().unit_id(); return true;
	case C::kSetIdleMode:          *unit_id = cmd.set_idle_mode().unit_id(); return true;
	case C::kGroupAddUnit:         *unit_id = cmd.group_add_unit().unit_id(); return true;
	case C::kGroupRemoveUnit:      *unit_id = cmd.group_remove_unit().unit_id(); return true;
	default:                       return false;
	}
}

bool CommandValidator::ValidateCommandTarget(
		const ::highbar::v1::AICommand& cmd,
		std::int32_t batch_target_unit_id,
		std::string* error) const {
	std::int32_t command_unit_id = 0;
	if (!TryCommandUnitId(cmd, &command_unit_id)) {
		return true;
	}
	if (command_unit_id <= 0) {
		std::ostringstream os;
		os << "unit-bound command missing unit_id for batch target "
		   << batch_target_unit_id;
		*error = os.str();
		return false;
	}
	if (command_unit_id != batch_target_unit_id) {
		std::ostringstream os;
		os << "target_drift: batch target_unit_id " << batch_target_unit_id
		   << " disagrees with command unit_id " << command_unit_id;
		*error = os.str();
		return false;
	}
	return true;
}

CommandValidator::CommandValidator(::circuit::CCircuitAI* ai) : ai_(ai) {}

bool CommandValidator::OwnsLiveUnit(std::int32_t unit_id) const {
	if (ai_ == nullptr) return false;
	if (unit_id <= 0) return false;
	auto* u = ai_->GetTeamUnit(unit_id);
	if (u == nullptr) return false;
	return !u->IsDead();
}

bool CommandValidator::InMapExtents(float x, float z) const {
	// AIFloat3::maxxpos / maxzpos are static globals populated by the
	// terrain manager on match init.
	return x >= 0.0f && z >= 0.0f
	    && x <= springai::AIFloat3::maxxpos
	    && z <= springai::AIFloat3::maxzpos;
}

bool CommandValidator::KnownBuildDef(std::int32_t def_id) const {
	if (ai_ == nullptr) return false;
	if (def_id <= 0) return false;
	return ai_->GetCircuitDefSafe(static_cast<CCircuitDef::Id>(def_id)) != nullptr;
}

bool CommandValidator::ValidateCommand(const ::highbar::v1::AICommand& cmd,
                                       std::string* error) const {
	if (cmd.command_case() == ::highbar::v1::AICommand::COMMAND_NOT_SET) {
		*error = "command batch contains an empty AICommand";
		return false;
	}
	// Position check first — cheapest, applies to ~20 arms.
	if (const auto* pos = PositionOf(cmd); pos != nullptr) {
		if (!std::isfinite(pos->x()) || !std::isfinite(pos->y())
		    || !std::isfinite(pos->z())) {
			*error = "position contains non-finite coordinate";
			return false;
		}
		if (!InMapExtents(pos->x(), pos->z())) {
			std::ostringstream os;
			os << "position out of map extents: x=" << pos->x()
			   << " z=" << pos->z();
			*error = os.str();
			return false;
		}
	}
	// Build def constructibility.
	if (cmd.command_case() == ::highbar::v1::AICommand::kBuildUnit) {
		const auto def_id = cmd.build_unit().to_build_unit_def_id();
		if (!KnownBuildDef(def_id)) {
			std::ostringstream os;
			os << "build.def_id unknown or non-constructible: " << def_id;
			*error = os.str();
			return false;
		}
	}
	return true;
}

ValidationResult CommandValidator::ValidateBatch(
		const ::highbar::v1::CommandBatch& batch) const {
	ValidationResult r;

	const auto batch_target = static_cast<std::int32_t>(batch.target_unit_id());

	// Enforce the batch-target contract and cheap semantic checks before
	// consulting runtime ownership. This keeps drift and malformed-shape
	// failures deterministic even in unit tests without a live AI.
	for (const auto& cmd : batch.commands()) {
		if (!ValidateCommandTarget(cmd, batch_target, &r.error)) {
			return r;  // ok == false, error set
		}
		if (!ValidateCommand(cmd, &r.error)) {
			return r;  // ok == false, error set
		}
	}

	// Batch target must resolve to a live owned unit.
	if (!OwnsLiveUnit(batch_target)) {
		std::ostringstream os;
		os << "target_unit_id " << batch.target_unit_id()
		   << " is not a live unit owned by this AI";
		r.error = os.str();
		return r;  // ok == false
	}

	r.ok = true;
	return r;
}

}  // namespace circuit::grpc
