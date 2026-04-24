// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — CommandValidator impl (T056).

#include "grpc/CommandValidator.h"

#include "grpc/CapabilityProvider.h"

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

namespace {

::highbar::v1::RetryHint RetryNever() {
	return ::highbar::v1::RETRY_NEVER;
}

std::string CommandArmName(const ::highbar::v1::AICommand& cmd) {
	using C = ::highbar::v1::AICommand;
	switch (cmd.command_case()) {
	case C::kMoveUnit: return "move_unit";
	case C::kPatrol: return "patrol";
	case C::kFight: return "fight";
	case C::kAttackArea: return "attack_area";
	case C::kStop: return "stop";
	case C::kWait: return "wait";
	case C::kBuildUnit: return "build_unit";
	case C::kRepair: return "repair";
	case C::kReclaimUnit: return "reclaim_unit";
	case C::kReclaimArea: return "reclaim_area";
	case C::kResurrectInArea: return "resurrect_in_area";
	case C::kSelfDestruct: return "self_destruct";
	case C::kSetWantedMaxSpeed: return "set_wanted_max_speed";
	case C::kSetFireState: return "set_fire_state";
	case C::kSetMoveState: return "set_move_state";
	case C::kPauseTeam: return "pause_team";
	case C::kGiveMe: return "give_me";
	case C::kGiveMeNewUnit: return "give_me_new_unit";
	default: return "unsupported";
	}
}

std::uint32_t CommandOptionsOf(const ::highbar::v1::AICommand& cmd) {
	using C = ::highbar::v1::AICommand;
	switch (cmd.command_case()) {
	case C::kBuildUnit: return cmd.build_unit().options();
	case C::kStop: return cmd.stop().options();
	case C::kWait: return cmd.wait().options();
	case C::kTimedWait: return cmd.timed_wait().options();
	case C::kSquadWait: return cmd.squad_wait().options();
	case C::kDeathWait: return cmd.death_wait().options();
	case C::kGatherWait: return cmd.gather_wait().options();
	case C::kMoveUnit: return cmd.move_unit().options();
	case C::kPatrol: return cmd.patrol().options();
	case C::kFight: return cmd.fight().options();
	case C::kAttack: return cmd.attack().options();
	case C::kAttackArea: return cmd.attack_area().options();
	case C::kGuard: return cmd.guard().options();
	case C::kRepair: return cmd.repair().options();
	case C::kReclaimUnit: return cmd.reclaim_unit().options();
	case C::kReclaimArea: return cmd.reclaim_area().options();
	case C::kReclaimInArea: return cmd.reclaim_in_area().options();
	case C::kReclaimFeature: return cmd.reclaim_feature().options();
	case C::kRestoreArea: return cmd.restore_area().options();
	case C::kResurrect: return cmd.resurrect().options();
	case C::kResurrectInArea: return cmd.resurrect_in_area().options();
	case C::kCapture: return cmd.capture().options();
	case C::kCaptureArea: return cmd.capture_area().options();
	case C::kSetBase: return cmd.set_base().options();
	case C::kSelfDestruct: return cmd.self_destruct().options();
	case C::kLoadUnits: return cmd.load_units().options();
	case C::kLoadUnitsArea: return cmd.load_units_area().options();
	case C::kLoadOnto: return cmd.load_onto().options();
	case C::kUnloadUnit: return cmd.unload_unit().options();
	case C::kUnloadUnitsArea: return cmd.unload_units_area().options();
	case C::kSetWantedMaxSpeed: return cmd.set_wanted_max_speed().options();
	case C::kStockpile: return cmd.stockpile().options();
	case C::kDgun: return cmd.dgun().options();
	case C::kCustom: return cmd.custom().options();
	case C::kSetOnOff: return cmd.set_on_off().options();
	case C::kSetRepeat: return cmd.set_repeat().options();
	case C::kSetMoveState: return cmd.set_move_state().options();
	case C::kSetFireState: return cmd.set_fire_state().options();
	case C::kSetTrajectory: return cmd.set_trajectory().options();
	case C::kSetAutoRepairLevel: return cmd.set_auto_repair_level().options();
	case C::kSetIdleMode: return cmd.set_idle_mode().options();
	default: return 0;
	}
}

void FillIssue(const ::highbar::v1::CommandBatch& batch,
               ::highbar::v1::CommandIssueCode code,
               std::uint32_t command_index,
               const std::string& field_path,
               const std::string& detail,
               ::highbar::v1::RetryHint retry_hint,
               ::highbar::v1::CommandIssue* issue) {
	if (issue == nullptr) return;
	issue->set_code(code);
	issue->set_command_index(command_index);
	issue->set_field_path(field_path);
	issue->set_detail(detail);
	issue->set_retry_hint(retry_hint);
	issue->set_batch_seq(batch.batch_seq());
	if (batch.has_client_command_id()) {
		issue->set_client_command_id(batch.client_command_id());
	}
}

void FillIssue(::highbar::v1::CommandIssueCode code,
               std::uint32_t command_index,
               const std::string& field_path,
               const std::string& detail,
               ::highbar::v1::RetryHint retry_hint,
               ::highbar::v1::CommandIssue* issue) {
	if (issue == nullptr) return;
	issue->set_code(code);
	issue->set_command_index(command_index);
	issue->set_field_path(field_path);
	issue->set_detail(detail);
	issue->set_retry_hint(retry_hint);
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
		std::uint32_t command_index,
		::highbar::v1::CommandIssue* issue,
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
		FillIssue(::highbar::v1::MISSING_TARGET_UNIT, command_index,
		          "commands[" + std::to_string(command_index) + "].unit_id",
		          *error, RetryNever(), issue);
		return false;
	}
	if (command_unit_id != batch_target_unit_id) {
		std::ostringstream os;
		os << "target_drift: batch target_unit_id " << batch_target_unit_id
		   << " disagrees with command unit_id " << command_unit_id;
		*error = os.str();
		FillIssue(::highbar::v1::TARGET_DRIFT, command_index,
		          "commands[" + std::to_string(command_index) + "].unit_id",
		          *error, RetryNever(), issue);
		return false;
	}
	return true;
}

CommandValidator::CommandValidator(::circuit::CCircuitAI* ai,
                                   CommandValidationSettings settings)
	: ai_(ai), settings_(settings) {}

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
                                       std::uint32_t command_index,
                                       ::highbar::v1::CommandIssue* issue,
                                       std::string* error) const {
	if (cmd.command_case() == ::highbar::v1::AICommand::COMMAND_NOT_SET) {
		*error = "command batch contains an empty AICommand";
		FillIssue(::highbar::v1::MISSING_COMMAND_INTENT, command_index,
		          "commands[" + std::to_string(command_index) + "]",
		          *error, RetryNever(), issue);
		return false;
	}
	if (!settings_.allow_legacy_ai_admin
	    && (cmd.command_case() == ::highbar::v1::AICommand::kPauseTeam
	        || cmd.command_case() == ::highbar::v1::AICommand::kGiveMe
	        || cmd.command_case() == ::highbar::v1::AICommand::kGiveMeNewUnit)) {
		*error = "AI command arm requires the HighBarAdmin service";
		FillIssue(::highbar::v1::COMMAND_REQUIRES_ADMIN_CHANNEL, command_index,
		          "commands[" + std::to_string(command_index) + "]",
		          *error, RetryNever(), issue);
		return false;
	}
	const std::string arm = CommandArmName(cmd);
	if ((settings_.reject_unsupported_arms
	     || settings_.mode == ::highbar::v1::VALIDATION_MODE_STRICT)
	    && !CapabilityProvider::IsSupportedCommandArm(arm)) {
		*error = "command arm is not dispatched by this gateway";
		FillIssue(::highbar::v1::COMMAND_ARM_NOT_DISPATCHED, command_index,
		          "commands[" + std::to_string(command_index) + "]",
		          *error, ::highbar::v1::RETRY_WITH_FRESH_CAPABILITIES, issue);
		return false;
	}
	const std::uint32_t valid_mask = CapabilityProvider::ValidOptionMaskFor(arm);
	const std::uint32_t options = CommandOptionsOf(cmd);
	if (valid_mask != 0 && (options & ~valid_mask) != 0) {
		*error = "command options contain invalid bits";
		FillIssue(::highbar::v1::INVALID_OPTION_BITS, command_index,
		          "commands[" + std::to_string(command_index) + "].options",
		          *error, RetryNever(), issue);
		return false;
	}
	if (cmd.command_case() == ::highbar::v1::AICommand::kSetMoveState) {
		const int value = cmd.set_move_state().move_state();
		if (value < 0 || value > 2) {
			*error = "move_state enum value out of range";
			FillIssue(::highbar::v1::INVALID_ENUM_VALUE, command_index,
			          "commands[" + std::to_string(command_index)
			          + "].set_move_state.move_state",
			          *error, RetryNever(), issue);
			return false;
		}
	}
	if (cmd.command_case() == ::highbar::v1::AICommand::kSetFireState) {
		const int value = cmd.set_fire_state().fire_state();
		if (value < 0 || value > 2) {
			*error = "fire_state enum value out of range";
			FillIssue(::highbar::v1::INVALID_ENUM_VALUE, command_index,
			          "commands[" + std::to_string(command_index)
			          + "].set_fire_state.fire_state",
			          *error, RetryNever(), issue);
			return false;
		}
	}
	// Position check first — cheapest, applies to ~20 arms.
	if (const auto* pos = PositionOf(cmd); pos != nullptr) {
		if (!std::isfinite(pos->x()) || !std::isfinite(pos->y())
		    || !std::isfinite(pos->z())) {
			*error = "position contains non-finite coordinate";
			FillIssue(::highbar::v1::POSITION_NON_FINITE, command_index,
			          "commands[" + std::to_string(command_index) + "].position",
			          *error, RetryNever(), issue);
			return false;
		}
		if (!InMapExtents(pos->x(), pos->z())) {
			std::ostringstream os;
			os << "position out of map extents: x=" << pos->x()
			   << " z=" << pos->z();
			*error = os.str();
			FillIssue(::highbar::v1::POSITION_OUT_OF_MAP, command_index,
			          "commands[" + std::to_string(command_index) + "].position",
			          *error, RetryNever(), issue);
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
			FillIssue(::highbar::v1::UNKNOWN_UNIT_DEF, command_index,
			          "commands[" + std::to_string(command_index)
			          + "].build_unit.to_build_unit_def_id",
			          *error, ::highbar::v1::RETRY_WITH_FRESH_CAPABILITIES, issue);
			return false;
		}
	}
	return true;
}

ValidationResult CommandValidator::ValidateBatch(
		const ::highbar::v1::CommandBatch& batch) const {
	ValidationResult r;
	auto* batch_result = &r.batch_result;
	batch_result->set_batch_seq(batch.batch_seq());
	if (batch.has_client_command_id()) {
		batch_result->set_client_command_id(batch.client_command_id());
	}
	batch_result->set_mode(settings_.mode);

	const auto batch_target = static_cast<std::int32_t>(batch.target_unit_id());
	const auto reject = [&](::highbar::v1::CommandBatchStatus status,
	                        ::highbar::v1::CommandIssueCode code,
	                        std::uint32_t command_index,
	                        const std::string& field_path,
	                        const std::string& detail,
	                        ::highbar::v1::RetryHint retry_hint) {
		r.error = detail;
		batch_result->set_status(status);
		batch_result->set_accepted_command_count(0);
		FillIssue(batch, code, command_index, field_path, detail, retry_hint,
		          batch_result->add_issues());
		return r;
	};

	if (batch.commands_size() == 0) {
		return reject(::highbar::v1::COMMAND_BATCH_REJECTED_INVALID,
		              ::highbar::v1::EMPTY_COMMAND,
		              0,
		              "commands",
		              "command batch must contain at least one AICommand",
		              RetryNever());
	}
	if (settings_.max_batch_commands > 0
	    && static_cast<std::uint32_t>(batch.commands_size())
	       > settings_.max_batch_commands) {
		return reject(::highbar::v1::COMMAND_BATCH_REJECTED_INVALID,
		              ::highbar::v1::TOO_MANY_COMMANDS,
		              0,
		              "commands",
		              "command batch exceeds max_batch_commands",
		              RetryNever());
	}
	if (settings_.require_correlation && !batch.has_client_command_id()) {
		return reject(::highbar::v1::COMMAND_BATCH_REJECTED_INVALID,
		              ::highbar::v1::MISSING_CLIENT_COMMAND_ID,
		              0,
		              "client_command_id",
		              "strict validation requires client_command_id",
		              RetryNever());
	}
	if (settings_.require_state_basis
	    && (!batch.has_based_on_frame() || !batch.has_based_on_state_seq())) {
		return reject(::highbar::v1::COMMAND_BATCH_REJECTED_STALE,
		              ::highbar::v1::MISSING_STATE_BASIS,
		              0,
		              !batch.has_based_on_frame()
		              ? "based_on_frame"
		              : "based_on_state_seq",
		              "strict validation requires based_on_frame and based_on_state_seq",
		              ::highbar::v1::RETRY_AFTER_NEXT_SNAPSHOT);
	}

	// Enforce the batch-target contract and cheap semantic checks before
	// consulting runtime ownership. This keeps drift and malformed-shape
	// failures deterministic even in unit tests without a live AI.
	bool has_unit_bound_command = false;
	for (int i = 0; i < batch.commands_size(); ++i) {
		const auto& cmd = batch.commands(i);
		std::int32_t command_unit_id = 0;
		if (TryCommandUnitId(cmd, &command_unit_id)) {
			has_unit_bound_command = true;
		}
		::highbar::v1::CommandIssue issue;
		if (!ValidateCommandTarget(cmd, batch_target, static_cast<std::uint32_t>(i),
		                           &issue, &r.error)) {
			batch_result->set_status(::highbar::v1::COMMAND_BATCH_REJECTED_INVALID);
			batch_result->set_accepted_command_count(0);
			*batch_result->add_issues() = issue;
			batch_result->mutable_issues(batch_result->issues_size() - 1)
				->set_batch_seq(batch.batch_seq());
			if (batch.has_client_command_id()) {
				batch_result->mutable_issues(batch_result->issues_size() - 1)
					->set_client_command_id(batch.client_command_id());
			}
			return r;  // ok == false, error set
		}
		if (!ValidateCommand(cmd, static_cast<std::uint32_t>(i),
		                     &issue, &r.error)) {
			batch_result->set_status(::highbar::v1::COMMAND_BATCH_REJECTED_INVALID);
			batch_result->set_accepted_command_count(0);
			*batch_result->add_issues() = issue;
			batch_result->mutable_issues(batch_result->issues_size() - 1)
				->set_batch_seq(batch.batch_seq());
			if (batch.has_client_command_id()) {
				batch_result->mutable_issues(batch_result->issues_size() - 1)
					->set_client_command_id(batch.client_command_id());
			}
			return r;  // ok == false, error set
		}
	}

	// Batch target must resolve to a live owned unit.
	if (has_unit_bound_command && !OwnsLiveUnit(batch_target)) {
		std::ostringstream os;
		os << "target_unit_id " << batch.target_unit_id()
		   << " is not a live unit owned by this AI";
		r.error = os.str();
		batch_result->set_status(::highbar::v1::COMMAND_BATCH_REJECTED_INVALID);
		batch_result->set_accepted_command_count(0);
		FillIssue(batch, ::highbar::v1::TARGET_UNIT_NOT_OWNED, 0,
		          "target_unit_id", r.error,
		          ::highbar::v1::RETRY_AFTER_NEXT_SNAPSHOT,
		          batch_result->add_issues());
		return r;  // ok == false
	}

	r.ok = true;
	batch_result->set_status(::highbar::v1::COMMAND_BATCH_ACCEPTED);
	batch_result->set_accepted_command_count(
		static_cast<std::uint32_t>(batch.commands_size()));
	return r;
}

}  // namespace circuit::grpc
