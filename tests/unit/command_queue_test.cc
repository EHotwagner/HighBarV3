// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — CommandQueue unit test (T066).
//
// Verifies FR-012a:
//   1. Overflow returns RESOURCE_EXHAUSTED synchronously (TryPush → false)
//      without mutating the already-queued state.
//   2. No already-queued command is dropped or reordered when a later
//      push overflows.
//   3. Default capacity is 1024 (per tasks.md T055).
//   4. Drain is FIFO and updates Counters::command_queue_depth.
//
// Build: same CMake add_executable gating as the other tests/unit/
// files — add_executable(command_queue_test command_queue_test.cc)
// linking grpc/CommandQueue, grpc/Counters, GTest::gtest_main.

#include "grpc/CommandQueue.h"
#include "grpc/Counters.h"

#include <gtest/gtest.h>

#include <string>
#include <vector>

namespace {

using circuit::grpc::CommandQueue;
using circuit::grpc::Counters;
using circuit::grpc::QueuedCommand;

QueuedCommand MakeCommand(const std::string& session,
                          std::int32_t authoritative_target_unit_id,
                          std::int32_t unit_id) {
	QueuedCommand q;
	q.session_id = session;
	q.authoritative_target_unit_id = authoritative_target_unit_id;
	// Use MoveUnit as a convenient marker since it carries unit_id.
	auto* move = q.command.mutable_move_unit();
	move->set_unit_id(unit_id);
	return q;
}

TEST(CommandQueue, DefaultCapacityIs1024) {
	CommandQueue q;
	EXPECT_EQ(q.Capacity(), 1024u);
}

TEST(CommandQueue, FifoDrainPreservesOrder) {
	Counters c;
	CommandQueue q(&c, /*capacity=*/8);
	for (int i = 1; i <= 5; ++i) {
		ASSERT_TRUE(q.TryPush(MakeCommand("s1", i, i)));
	}
	EXPECT_EQ(q.Depth(), 5u);
	EXPECT_EQ(c.command_queue_depth.load(), 5u);

	std::vector<QueuedCommand> out;
	ASSERT_EQ(q.Drain(&out), 5u);
	ASSERT_EQ(out.size(), 5u);
	for (int i = 0; i < 5; ++i) {
		EXPECT_EQ(out[i].authoritative_target_unit_id, i + 1);
		EXPECT_EQ(out[i].command.move_unit().unit_id(), i + 1);
	}
	EXPECT_EQ(q.Depth(), 0u);
	EXPECT_EQ(c.command_queue_depth.load(), 0u);
}

TEST(CommandQueue, OverflowReturnsFalseSynchronously) {
	CommandQueue q(/*counters=*/nullptr, /*capacity=*/3);
	ASSERT_TRUE(q.TryPush(MakeCommand("s1", 1, 1)));
	ASSERT_TRUE(q.TryPush(MakeCommand("s1", 2, 2)));
	ASSERT_TRUE(q.TryPush(MakeCommand("s1", 3, 3)));

	// Fourth push must fail synchronously with false (caller maps to
	// RESOURCE_EXHAUSTED on the wire).
	EXPECT_FALSE(q.TryPush(MakeCommand("s1", 4, 4)));
	EXPECT_EQ(q.Depth(), 3u);
}

TEST(CommandQueue, OverflowDoesNotDropOrReorderQueued) {
	CommandQueue q(/*counters=*/nullptr, /*capacity=*/3);
	ASSERT_TRUE(q.TryPush(MakeCommand("s1", 10, 10)));
	ASSERT_TRUE(q.TryPush(MakeCommand("s1", 20, 20)));
	ASSERT_TRUE(q.TryPush(MakeCommand("s1", 30, 30)));

	// Several rejected pushes — must leave the queue untouched.
	for (int i = 0; i < 5; ++i) {
		EXPECT_FALSE(q.TryPush(MakeCommand("s1", 99, 99)));
	}

	std::vector<QueuedCommand> drained;
	ASSERT_EQ(q.Drain(&drained), 3u);
	ASSERT_EQ(drained.size(), 3u);
	EXPECT_EQ(drained[0].command.move_unit().unit_id(), 10);
	EXPECT_EQ(drained[1].command.move_unit().unit_id(), 20);
	EXPECT_EQ(drained[2].command.move_unit().unit_id(), 30);
	EXPECT_EQ(drained[0].authoritative_target_unit_id, 10);
	EXPECT_EQ(drained[1].authoritative_target_unit_id, 20);
	EXPECT_EQ(drained[2].authoritative_target_unit_id, 30);
}

TEST(CommandQueue, PartialDrainLeavesRemainder) {
	CommandQueue q(/*counters=*/nullptr, /*capacity=*/10);
	for (int i = 1; i <= 10; ++i) {
		ASSERT_TRUE(q.TryPush(MakeCommand("s1", i, i)));
	}
	std::vector<QueuedCommand> out;
	ASSERT_EQ(q.Drain(&out, /*max=*/4), 4u);
	EXPECT_EQ(q.Depth(), 6u);
	ASSERT_EQ(q.Drain(&out, /*max=*/0), 6u);
	EXPECT_EQ(q.Depth(), 0u);
	ASSERT_EQ(out.size(), 10u);
	for (int i = 0; i < 10; ++i) {
		EXPECT_EQ(out[i].command.move_unit().unit_id(), i + 1);
	}
}

TEST(CommandQueue, TryPushBatchIsAtomicWhenCapacityInsufficient) {
	CommandQueue q(/*counters=*/nullptr, /*capacity=*/3);
	ASSERT_TRUE(q.TryPush(MakeCommand("s1", 1, 1)));
	ASSERT_TRUE(q.TryPush(MakeCommand("s1", 2, 2)));

	std::vector<QueuedCommand> batch;
	batch.push_back(MakeCommand("s2", 10, 10));
	batch.push_back(MakeCommand("s2", 11, 11));

	EXPECT_FALSE(q.TryPushBatch(std::move(batch)));
	EXPECT_EQ(q.Depth(), 2u);

	std::vector<QueuedCommand> drained;
	ASSERT_EQ(q.Drain(&drained), 2u);
	ASSERT_EQ(drained.size(), 2u);
	EXPECT_EQ(drained[0].command.move_unit().unit_id(), 1);
	EXPECT_EQ(drained[1].command.move_unit().unit_id(), 2);
}

}  // namespace
