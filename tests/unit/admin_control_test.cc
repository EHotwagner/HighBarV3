// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — admin controller unit tests.

#include "grpc/AdminController.h"

#include <gtest/gtest.h>

#include <string>
#include <utility>

namespace {

circuit::grpc::AdminCaller Operator(std::string id = "operator-a") {
	return {std::move(id), ::highbar::v1::ADMIN_ROLE_OPERATOR};
}

::highbar::v1::AdminAction PauseAction(std::uint64_t seq = 1) {
	::highbar::v1::AdminAction action;
	action.set_action_seq(seq);
	action.set_client_action_id(1000 + seq);
	action.mutable_pause()->set_paused(true);
	action.set_conflict_policy(::highbar::v1::ADMIN_CONFLICT_REJECT_IF_CONTROLLED);
	action.set_reason("test pause");
	return action;
}

TEST(AdminController, RejectsUnauthorizedCaller) {
	circuit::grpc::AdminController controller;
	circuit::grpc::AdminCaller caller{"observer",
		::highbar::v1::ADMIN_ROLE_OBSERVER};

	const auto result = controller.Validate(caller, PauseAction(), 10, 20);
	EXPECT_EQ(result.status(),
	          ::highbar::v1::ADMIN_ACTION_REJECTED_PERMISSION_DENIED);
	ASSERT_EQ(result.issues_size(), 1);
	EXPECT_EQ(result.issues(0).code(), ::highbar::v1::ADMIN_PERMISSION_DENIED);
}

TEST(AdminController, RejectsDisabledControlsAndInvalidSpeed) {
	circuit::grpc::AdminController disabled(
		circuit::grpc::AdminController::Settings{.enabled = false});
	EXPECT_EQ(disabled.Validate(Operator(), PauseAction(), 10, 20).status(),
	          ::highbar::v1::ADMIN_ACTION_REJECTED_DISABLED);

	circuit::grpc::AdminController controller;
	::highbar::v1::AdminAction speed;
	speed.set_action_seq(2);
	speed.mutable_global_speed()->set_speed(0.0f);
	const auto result = controller.Validate(Operator(), speed, 10, 20);
	EXPECT_EQ(result.status(),
	          ::highbar::v1::ADMIN_ACTION_REJECTED_INVALID_VALUE);
	EXPECT_EQ(result.issues(0).code(), ::highbar::v1::ADMIN_INVALID_SPEED_RANGE);
}

TEST(AdminController, ExecutesLeaseAndRejectsConflictingOwner) {
	circuit::grpc::AdminController controller;
	const auto first = controller.Execute(Operator("a"), PauseAction(1), 10, 20);
	EXPECT_EQ(first.status(), ::highbar::v1::ADMIN_ACTION_EXECUTED);
	EXPECT_EQ(first.lease().owner_client_id(), "a");
	EXPECT_EQ(controller.AuditLog().size(), 1u);

	const auto second = controller.Validate(Operator("b"), PauseAction(2), 11, 21);
	EXPECT_EQ(second.status(),
	          ::highbar::v1::ADMIN_ACTION_REJECTED_CONFLICT);
	EXPECT_EQ(second.issues(0).code(), ::highbar::v1::ADMIN_CONTROL_CONFLICT);
}

TEST(AdminController, RejectsStaleBasisAndForbiddenCheatMode) {
	circuit::grpc::AdminController controller;
	auto stale = PauseAction(3);
	stale.set_based_on_frame(1);
	EXPECT_EQ(controller.Validate(Operator(), stale, 400, 20).status(),
	          ::highbar::v1::ADMIN_ACTION_REJECTED_STALE);

	::highbar::v1::AdminAction cheat;
	cheat.set_action_seq(4);
	cheat.mutable_cheat_policy()->set_enabled(true);
	EXPECT_EQ(controller.Validate(Operator(), cheat, 10, 20).status(),
	          ::highbar::v1::ADMIN_ACTION_REJECTED_RUN_MODE);
}

}  // namespace
