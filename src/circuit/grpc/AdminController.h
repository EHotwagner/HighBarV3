// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — admin validation, leases, and audit state.

#pragma once

#include "highbar/service.pb.h"

#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

namespace circuit::grpc {

struct AdminCaller {
	std::string identity;
	::highbar::v1::AdminRole role =
		::highbar::v1::ADMIN_ROLE_UNSPECIFIED;
};

class AdminController {
public:
	struct Settings {
		bool enabled = true;
		bool cheats_allowed = false;
		std::uint32_t lease_ttl_frames = 90;
	};

	AdminController();
	explicit AdminController(Settings settings);

	::highbar::v1::AdminCapabilitiesResponse Capabilities() const;
	::highbar::v1::AdminActionResult Validate(
		const AdminCaller& caller,
		const ::highbar::v1::AdminAction& action,
		std::uint32_t frame,
		std::uint64_t state_seq) const;
	::highbar::v1::AdminActionResult Execute(
		const AdminCaller& caller,
		const ::highbar::v1::AdminAction& action,
		std::uint32_t frame,
		std::uint64_t state_seq);
	void Heartbeat(const std::string& control,
	               const AdminCaller& caller,
	               std::uint32_t frame);
	void ExpireLeases(std::uint32_t frame);
	const std::vector<::highbar::v1::AdminAuditEvent>& AuditLog() const {
		return audit_log_;
	}

private:
	bool RoleCanExecute(::highbar::v1::AdminRole role) const;
	std::string ControlName(const ::highbar::v1::AdminAction& action) const;
	::highbar::v1::AdminActionResult Reject(
		const ::highbar::v1::AdminAction& action,
		::highbar::v1::AdminActionStatus status,
		::highbar::v1::AdminIssueCode code,
		const std::string& field_path,
		const std::string& detail,
		std::uint32_t frame,
		std::uint64_t state_seq,
		bool dry_run) const;
	void Audit(const AdminCaller& caller,
	           const ::highbar::v1::AdminAction& action,
	           const ::highbar::v1::AdminActionResult& result,
	           const std::string& control);

	Settings settings_;
	std::unordered_map<std::string, ::highbar::v1::AdminLease> leases_;
	std::vector<::highbar::v1::AdminAuditEvent> audit_log_;
	std::uint64_t next_audit_id_ = 1;
};

}  // namespace circuit::grpc
