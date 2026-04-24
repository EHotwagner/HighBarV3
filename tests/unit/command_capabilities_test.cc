// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — capability provider unit tests.

#include "grpc/CapabilityProvider.h"
#include "grpc/CommandQueue.h"
#include "grpc/SchemaVersion.h"

#include <gtest/gtest.h>

#include <algorithm>
#include <string>

namespace {

bool HasString(const google::protobuf::RepeatedPtrField<std::string>& values,
               const std::string& needle) {
	return std::find(values.begin(), values.end(), needle) != values.end();
}

TEST(CapabilityProvider, CommandSchemaListsDispatchableArmsAndQueueState) {
	circuit::grpc::CommandQueue queue(nullptr, 3);
	circuit::grpc::CapabilityProvider provider(nullptr, &queue);

	const auto schema = provider.CommandSchema();
	EXPECT_EQ(schema.schema_version(), ::highbar::v1::kSchemaVersion);
	EXPECT_TRUE(HasString(schema.feature_flags(), "command_capabilities"));
	EXPECT_TRUE(HasString(schema.supported_command_arms(), "move_unit"));
	EXPECT_TRUE(HasString(schema.supported_command_arms(), "build_unit"));
	EXPECT_TRUE(HasString(schema.supported_command_arms(), "set_fire_state"));
	EXPECT_EQ(schema.queue_depth(), 0u);
	EXPECT_EQ(schema.queue_capacity(), 3u);
	ASSERT_GT(schema.option_masks_size(), 0);
	EXPECT_GT(schema.map_limits().max_x(), schema.map_limits().min_x());
}

TEST(CapabilityProvider, UnitCapabilitiesMirrorGeneratedRequest) {
	circuit::grpc::CapabilityProvider provider(nullptr, nullptr);
	::highbar::v1::UnitCapabilitiesRequest request;
	request.set_unit_id(42);
	request.mutable_generation()->set_unit_id(42);
	request.mutable_generation()->set_generation(7);

	const auto caps = provider.UnitCapabilities(request);
	EXPECT_EQ(caps.unit_id(), 42u);
	EXPECT_EQ(caps.generation().generation(), 7u);
	EXPECT_TRUE(HasString(caps.legal_command_arms(), "stop"));
	EXPECT_TRUE(HasString(caps.feature_flags(), "protobuf_proxy_safety"));
}

TEST(CapabilityProvider, UnknownArmsHaveNoOptionMask) {
	EXPECT_TRUE(circuit::grpc::CapabilityProvider::IsSupportedCommandArm("move_unit"));
	EXPECT_FALSE(circuit::grpc::CapabilityProvider::IsSupportedCommandArm("pause_team"));
	EXPECT_EQ(circuit::grpc::CapabilityProvider::ValidOptionMaskFor("move_unit"), 0x7u);
	EXPECT_EQ(circuit::grpc::CapabilityProvider::ValidOptionMaskFor("pause_team"), 0u);
}

}  // namespace
