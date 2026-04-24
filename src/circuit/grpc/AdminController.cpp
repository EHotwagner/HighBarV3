// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — admin validation, leases, and audit state.

#include "grpc/AdminController.h"

#include <cmath>

namespace circuit::grpc {

AdminController::AdminController()
	: AdminController(Settings{}) {}

AdminController::AdminController(Settings settings)
	: settings_(settings) {}

bool AdminController::RoleCanExecute(::highbar::v1::AdminRole role) const {
	return role == ::highbar::v1::ADMIN_ROLE_OPERATOR
	    || role == ::highbar::v1::ADMIN_ROLE_ADMIN
	    || role == ::highbar::v1::ADMIN_ROLE_TEST_HARNESS;
}

std::string AdminController::ControlName(
		const ::highbar::v1::AdminAction& action) const {
	using A = ::highbar::v1::AdminAction;
	switch (action.action_case()) {
	case A::kPause: return "pause";
	case A::kGlobalSpeed: return "global_speed";
	case A::kCheatPolicy: return "cheat_policy";
	case A::kResourceGrant: return "resource_grant";
	case A::kUnitSpawn: return "unit_spawn";
	case A::kLifecycle: return "lifecycle";
	default: return "unknown";
	}
}

::highbar::v1::AdminCapabilitiesResponse AdminController::Capabilities() const {
	::highbar::v1::AdminCapabilitiesResponse response;
	response.set_enabled(settings_.enabled);
	response.add_roles(::highbar::v1::ADMIN_ROLE_OPERATOR);
	response.add_roles(::highbar::v1::ADMIN_ROLE_ADMIN);
	response.add_roles(::highbar::v1::ADMIN_ROLE_TEST_HARNESS);
	response.add_supported_actions("pause");
	response.add_supported_actions("global_speed");
	response.add_supported_actions("cheat_policy");
	response.add_supported_actions("resource_grant");
	response.add_supported_actions("unit_spawn");
	response.add_supported_actions("lifecycle");
	response.add_feature_flags("admin_control_service");
	response.add_feature_flags("admin_leases");
	response.add_feature_flags("admin_audit_events");
	return response;
}

::highbar::v1::AdminActionResult AdminController::Reject(
		const ::highbar::v1::AdminAction& action,
		::highbar::v1::AdminActionStatus status,
		::highbar::v1::AdminIssueCode code,
		const std::string& field_path,
		const std::string& detail,
		std::uint32_t frame,
		std::uint64_t state_seq,
		bool dry_run) const {
	::highbar::v1::AdminActionResult result;
	result.set_action_seq(action.action_seq());
	result.set_client_action_id(action.client_action_id());
	result.set_status(status);
	result.set_frame(frame);
	result.set_state_seq(state_seq);
	result.set_dry_run(dry_run);
	auto* issue = result.add_issues();
	issue->set_code(code);
	issue->set_field_path(field_path);
	issue->set_detail(detail);
	issue->set_retry_hint(::highbar::v1::RETRY_NEVER);
	return result;
}

::highbar::v1::AdminActionResult AdminController::Validate(
		const AdminCaller& caller,
		const ::highbar::v1::AdminAction& action,
		std::uint32_t frame,
		std::uint64_t state_seq) const {
	if (!RoleCanExecute(caller.role)) {
		return Reject(action,
		              ::highbar::v1::ADMIN_ACTION_REJECTED_PERMISSION_DENIED,
		              ::highbar::v1::ADMIN_PERMISSION_DENIED,
		              "role", "admin action requires operator/admin/test-harness role",
		              frame, state_seq, true);
	}
	if (!settings_.enabled) {
		return Reject(action,
		              ::highbar::v1::ADMIN_ACTION_REJECTED_DISABLED,
		              ::highbar::v1::ADMIN_ACTION_DISABLED,
		              "action", "admin controls are disabled",
		              frame, state_seq, true);
	}
	if (action.action_case() == ::highbar::v1::AdminAction::kCheatPolicy
	    && !settings_.cheats_allowed) {
		return Reject(action,
		              ::highbar::v1::ADMIN_ACTION_REJECTED_RUN_MODE,
		              ::highbar::v1::ADMIN_RUN_MODE_FORBIDS_CHEATS,
		              "cheat_policy", "run mode forbids cheat controls",
		              frame, state_seq, true);
	}
	if (action.action_case() == ::highbar::v1::AdminAction::kGlobalSpeed
	    && (!std::isfinite(action.global_speed().speed())
	        || action.global_speed().speed() <= 0.0f
	        || action.global_speed().speed() > 10.0f)) {
		return Reject(action,
		              ::highbar::v1::ADMIN_ACTION_REJECTED_INVALID_VALUE,
		              ::highbar::v1::ADMIN_INVALID_SPEED_RANGE,
		              "global_speed.speed", "speed must be finite and in (0, 10]",
		              frame, state_seq, true);
	}
	if (action.based_on_frame() != 0 && action.based_on_frame() + 300 < frame) {
		return Reject(action,
		              ::highbar::v1::ADMIN_ACTION_REJECTED_STALE,
		              ::highbar::v1::ADMIN_STALE_SNAPSHOT_EPOCH,
		              "based_on_frame", "admin action basis is stale",
		              frame, state_seq, true);
	}
	const std::string control = ControlName(action);
	const auto lease_it = leases_.find(control);
	if (lease_it != leases_.end()
	    && lease_it->second.owner_client_id() != caller.identity
	    && action.conflict_policy()
	       != ::highbar::v1::ADMIN_CONFLICT_RELEASE_EXISTING_LEASE) {
		return Reject(action,
		              ::highbar::v1::ADMIN_ACTION_REJECTED_CONFLICT,
		              ::highbar::v1::ADMIN_CONTROL_CONFLICT,
		              "conflict_policy", "admin control is leased by another caller",
		              frame, state_seq, true);
	}

	::highbar::v1::AdminActionResult result;
	result.set_action_seq(action.action_seq());
	result.set_client_action_id(action.client_action_id());
	result.set_status(::highbar::v1::ADMIN_ACTION_ACCEPTED);
	result.set_frame(frame);
	result.set_state_seq(state_seq);
	result.set_dry_run(true);
	return result;
}

::highbar::v1::AdminActionResult AdminController::Execute(
		const AdminCaller& caller,
		const ::highbar::v1::AdminAction& action,
		std::uint32_t frame,
		std::uint64_t state_seq) {
	auto result = Validate(caller, action, frame, state_seq);
	result.set_dry_run(false);
	if (result.status() != ::highbar::v1::ADMIN_ACTION_ACCEPTED) {
		Audit(caller, action, result, ControlName(action));
		return result;
	}

	result.set_status(::highbar::v1::ADMIN_ACTION_EXECUTED);
	const std::string control = ControlName(action);
	if (control == "pause" || control == "global_speed") {
		auto* lease = &leases_[control];
		lease->set_control(control);
		lease->set_owner_client_id(caller.identity);
		lease->set_owner_role(caller.role);
		lease->set_acquired_frame(frame);
		lease->set_last_heartbeat_frame(frame);
		lease->set_expires_frame(frame + settings_.lease_ttl_frames);
		*result.mutable_lease() = *lease;
	}
	Audit(caller, action, result, control);
	return result;
}

void AdminController::Heartbeat(const std::string& control,
                                const AdminCaller& caller,
                                std::uint32_t frame) {
	auto it = leases_.find(control);
	if (it == leases_.end()) return;
	if (it->second.owner_client_id() != caller.identity) return;
	it->second.set_last_heartbeat_frame(frame);
	it->second.set_expires_frame(frame + settings_.lease_ttl_frames);
}

void AdminController::ExpireLeases(std::uint32_t frame) {
	for (auto it = leases_.begin(); it != leases_.end(); ) {
		if (it->second.expires_frame() != 0 && it->second.expires_frame() <= frame) {
			it = leases_.erase(it);
		} else {
			++it;
		}
	}
}

void AdminController::Audit(
		const AdminCaller& caller,
		const ::highbar::v1::AdminAction& action,
		const ::highbar::v1::AdminActionResult& result,
		const std::string& control) {
	::highbar::v1::AdminAuditEvent event;
	event.set_event_id(next_audit_id_++);
	event.set_caller_identity(caller.identity);
	event.set_role(::highbar::v1::AdminRole_Name(caller.role));
	event.set_action_type(control);
	event.set_frame(result.frame());
	event.set_state_seq(result.state_seq());
	event.set_result(::highbar::v1::AdminActionStatus_Name(result.status()));
	event.set_reason(action.reason());
	event.set_lease_control(control);
	event.set_run_mode(settings_.cheats_allowed ? "test" : "normal");
	audit_log_.push_back(std::move(event));
}

}  // namespace circuit::grpc
