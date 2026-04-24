// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — admin execute/audit integration slice.

#include "grpc/AdminController.h"

#include <gtest/gtest.h>

namespace {

TEST(AdminControlIntegration, ExecuteRecordsAuditEvent) {
	circuit::grpc::AdminController controller(
		circuit::grpc::AdminController::Settings{
			.enabled = true,
			.cheats_allowed = true,
			.lease_ttl_frames = 30,
		});
	circuit::grpc::AdminCaller caller{"harness",
		::highbar::v1::ADMIN_ROLE_TEST_HARNESS};
	::highbar::v1::AdminAction action;
	action.set_action_seq(1);
	action.set_client_action_id(2);
	action.mutable_global_speed()->set_speed(1.5f);
	action.set_reason("integration smoke");

	const auto result = controller.Execute(caller, action, 100, 200);
	EXPECT_EQ(result.status(), ::highbar::v1::ADMIN_ACTION_EXECUTED);
	ASSERT_EQ(controller.AuditLog().size(), 1u);
	EXPECT_EQ(controller.AuditLog().front().caller_identity(), "harness");
	EXPECT_EQ(controller.AuditLog().front().action_type(), "global_speed");
}

}  // namespace
