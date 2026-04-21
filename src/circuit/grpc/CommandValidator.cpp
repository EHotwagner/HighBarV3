// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — CommandValidator impl (T056).

#include "grpc/CommandValidator.h"

#include "CircuitAI.h"
#include "unit/CircuitDef.h"
#include "unit/CircuitUnit.h"

#include "AIFloat3.h"

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
	// Position check first — cheapest, applies to ~20 arms.
	if (const auto* pos = PositionOf(cmd); pos != nullptr) {
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

	// Batch target must resolve to a live owned unit.
	if (!OwnsLiveUnit(static_cast<std::int32_t>(batch.target_unit_id()))) {
		std::ostringstream os;
		os << "target_unit_id " << batch.target_unit_id()
		   << " is not a live unit owned by this AI";
		r.error = os.str();
		return r;  // ok == false
	}

	// Every command arm must pass its own checks (positions, build defs).
	for (const auto& cmd : batch.commands()) {
		if (!ValidateCommand(cmd, &r.error)) {
			return r;  // ok == false, error set
		}
	}

	r.ok = true;
	return r;
}

}  // namespace circuit::grpc
