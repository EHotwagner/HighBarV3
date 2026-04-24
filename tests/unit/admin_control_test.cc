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

::highbar::v1::AdminAction TransferAction(std::uint64_t seq = 1) {
	::highbar::v1::AdminAction action;
	action.set_action_seq(seq);
	action.set_client_action_id(2000 + seq);
	action.mutable_unit_transfer()->set_unit_id(42);
	action.mutable_unit_transfer()->set_from_team_id(0);
	action.mutable_unit_transfer()->set_to_team_id(1);
	action.mutable_unit_transfer()->set_preserve_orders(true);
	action.set_reason("test transfer");
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

TEST(AdminController, AdvertisesTransferAndFixtureCapabilityMetadata) {
	circuit::grpc::AdminController controller(
		circuit::grpc::AdminController::Settings{
			.enabled = true,
			.cheats_allowed = true,
			.unit_transfer_enabled = true,
			.headless_fixture = true,
			.lease_ttl_frames = 90,
			.min_speed = 0.25f,
			.max_speed = 4.0f,
			.map_min_x = 0.0f,
			.map_min_z = 0.0f,
			.map_max_x = 8192.0f,
			.map_max_z = 8192.0f,
			.valid_team_ids = {0, 1},
			.valid_resource_ids = {0, 1},
			.valid_unit_def_ids = {1, 2},
			.live_unit_owners = {{42, 0}},
		});

	const auto caps = controller.Capabilities();
	EXPECT_TRUE(caps.enabled());
	EXPECT_TRUE(caps.unit_transfer_enabled());
	EXPECT_EQ(caps.min_speed(), 0.25f);
	EXPECT_EQ(caps.max_speed(), 4.0f);
	EXPECT_EQ(caps.valid_team_ids_size(), 2);
	EXPECT_EQ(caps.valid_resource_ids_size(), 2);
	EXPECT_EQ(caps.valid_unit_def_ids_size(), 2);
	EXPECT_EQ(caps.map_limits().max_x(), 8192.0f);
	bool found_transfer = false;
	for (const auto& action : caps.supported_actions()) {
		found_transfer = found_transfer || action == "unit_transfer";
	}
	EXPECT_TRUE(found_transfer);
}

TEST(AdminController, ValidatesUnitTransferAndInvalidTargets) {
	circuit::grpc::AdminController controller(
		circuit::grpc::AdminController::Settings{
			.enabled = true,
			.cheats_allowed = true,
			.unit_transfer_enabled = true,
			.headless_fixture = true,
			.lease_ttl_frames = 90,
			.min_speed = 0.1f,
			.max_speed = 10.0f,
			.map_min_x = 0.0f,
			.map_min_z = 0.0f,
			.map_max_x = 8192.0f,
			.map_max_z = 8192.0f,
			.valid_team_ids = {0, 1},
			.valid_resource_ids = {0, 1},
			.valid_unit_def_ids = {1, 2},
			.live_unit_owners = {{42, 0}},
		});

	EXPECT_EQ(controller.Validate(Operator(), TransferAction(5), 10, 20).status(),
	          ::highbar::v1::ADMIN_ACTION_ACCEPTED);

	auto unknown = TransferAction(6);
	unknown.mutable_unit_transfer()->set_unit_id(99);
	const auto unknown_result = controller.Validate(Operator(), unknown, 10, 20);
	EXPECT_EQ(unknown_result.status(),
	          ::highbar::v1::ADMIN_ACTION_REJECTED_INVALID_TARGET);
	EXPECT_EQ(unknown_result.issues(0).code(), ::highbar::v1::ADMIN_UNKNOWN_UNIT);

	auto mismatch = TransferAction(7);
	mismatch.mutable_unit_transfer()->set_from_team_id(1);
	const auto mismatch_result = controller.Validate(Operator(), mismatch, 10, 20);
	EXPECT_EQ(mismatch_result.status(),
	          ::highbar::v1::ADMIN_ACTION_REJECTED_INVALID_TARGET);
	EXPECT_EQ(mismatch_result.issues(0).code(),
	          ::highbar::v1::ADMIN_UNIT_OWNER_MISMATCH);
}

TEST(AdminController, RejectsInvalidResourceSpawnAndSpeedAgainstSettings) {
	circuit::grpc::AdminController controller(
		circuit::grpc::AdminController::Settings{
			.enabled = true,
			.cheats_allowed = true,
			.unit_transfer_enabled = true,
			.headless_fixture = true,
			.lease_ttl_frames = 90,
			.min_speed = 0.5f,
			.max_speed = 2.0f,
			.map_min_x = 0.0f,
			.map_min_z = 0.0f,
			.map_max_x = 1024.0f,
			.map_max_z = 1024.0f,
			.valid_team_ids = {0, 1},
			.valid_resource_ids = {0, 1},
			.valid_unit_def_ids = {10},
			.live_unit_owners = {},
		});

	::highbar::v1::AdminAction resource;
	resource.mutable_resource_grant()->set_team_id(9);
	resource.mutable_resource_grant()->set_resource_id(0);
	resource.mutable_resource_grant()->set_amount(100.0f);
	EXPECT_EQ(controller.Validate(Operator(), resource, 10, 20).status(),
	          ::highbar::v1::ADMIN_ACTION_REJECTED_INVALID_TARGET);

	::highbar::v1::AdminAction spawn;
	spawn.mutable_unit_spawn()->set_team_id(1);
	spawn.mutable_unit_spawn()->set_unit_def_id(10);
	spawn.mutable_unit_spawn()->mutable_position()->set_x(2048.0f);
	spawn.mutable_unit_spawn()->mutable_position()->set_z(2048.0f);
	EXPECT_EQ(controller.Validate(Operator(), spawn, 10, 20).status(),
	          ::highbar::v1::ADMIN_ACTION_REJECTED_INVALID_VALUE);

	::highbar::v1::AdminAction speed;
	speed.mutable_global_speed()->set_speed(3.0f);
	EXPECT_EQ(controller.Validate(Operator(), speed, 10, 20).status(),
	          ::highbar::v1::ADMIN_ACTION_REJECTED_INVALID_VALUE);
}

}  // namespace
