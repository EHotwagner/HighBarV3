// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — structured command diagnostics integration slice.

#include "grpc/CommandQueue.h"
#include "grpc/CommandValidator.h"

#include <gtest/gtest.h>

namespace {

::highbar::v1::CommandBatch MoveBatch(std::uint64_t seq) {
	::highbar::v1::CommandBatch batch;
	batch.set_batch_seq(seq);
	batch.set_target_unit_id(42);
	batch.set_client_command_id(9000 + seq);
	batch.set_based_on_frame(10);
	batch.set_based_on_state_seq(20);
	auto* move = batch.add_commands()->mutable_move_unit();
	move->set_unit_id(99);
	move->mutable_to_position()->set_x(1.0f);
	move->mutable_to_position()->set_y(0.0f);
	move->mutable_to_position()->set_z(1.0f);
	return batch;
}

TEST(CommandDiagnosticsIntegration, ValidateCommandBatchReturnsStructuredIssue) {
	circuit::grpc::CommandValidator validator(nullptr);
	const auto result = validator.ValidateBatch(MoveBatch(1));

	EXPECT_FALSE(result.ok);
	ASSERT_EQ(result.batch_result.issues_size(), 1);
	EXPECT_EQ(result.batch_result.issues(0).code(), ::highbar::v1::TARGET_DRIFT);
	EXPECT_EQ(result.batch_result.issues(0).client_command_id(), 9001u);
	EXPECT_EQ(result.batch_result.status(),
	          ::highbar::v1::COMMAND_BATCH_REJECTED_INVALID);
}

TEST(CommandDiagnosticsIntegration, SubmitQueueAcceptsWholeValidatedBatchOnly) {
	circuit::grpc::CommandQueue queue(nullptr, 1);
	std::vector<circuit::grpc::QueuedCommand> commands;
	circuit::grpc::QueuedCommand first;
	first.batch_seq = 1;
	first.command_index = 0;
	first.authoritative_target_unit_id = 42;
	first.command.mutable_stop()->set_unit_id(42);
	commands.push_back(first);
	circuit::grpc::QueuedCommand second = first;
	second.command_index = 1;
	commands.push_back(second);

	EXPECT_FALSE(queue.TryPushBatch(std::move(commands)));
	EXPECT_EQ(queue.Depth(), 0u);
}

}  // namespace
