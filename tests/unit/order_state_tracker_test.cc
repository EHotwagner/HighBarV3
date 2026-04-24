// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — order state tracker unit tests.

#include "grpc/OrderStateTracker.h"

#include <gtest/gtest.h>

namespace {

TEST(OrderStateTracker, RejectsDuplicateOrStaleBatchSeq) {
	circuit::grpc::OrderStateTracker tracker;
	tracker.MarkAccepted(42, 10, 100, 30, "move");

	const auto result = tracker.CheckAcceptedBatch(
		42, 10, 101,
		::highbar::v1::COMMAND_CONFLICT_REPLACE_CURRENT);
	EXPECT_FALSE(result.ok);
	EXPECT_EQ(result.issue.code(), ::highbar::v1::STALE_OR_DUPLICATE_BATCH_SEQ);
	EXPECT_EQ(result.issue.field_path(), "batch_seq");
}

TEST(OrderStateTracker, RejectsBusyUnitWithoutReplacementPolicy) {
	circuit::grpc::OrderStateTracker tracker;
	tracker.MarkAccepted(42, 10, 100, 30, "move");

	const auto result = tracker.CheckAcceptedBatch(
		42, 11, 101,
		::highbar::v1::COMMAND_CONFLICT_POLICY_UNSPECIFIED);
	EXPECT_FALSE(result.ok);
	EXPECT_EQ(result.issue.code(), ::highbar::v1::ORDER_CONFLICT);
	EXPECT_EQ(result.issue.retry_hint(), ::highbar::v1::RETRY_AFTER_UNIT_IDLE);
}

TEST(OrderStateTracker, AllowsReplacementAndReleaseTransitions) {
	circuit::grpc::OrderStateTracker tracker;
	tracker.MarkAccepted(42, 10, 100, 30, "move");
	EXPECT_TRUE(tracker.CheckAcceptedBatch(
		42, 11, 101,
		::highbar::v1::COMMAND_CONFLICT_REPLACE_CURRENT).ok);

	tracker.MarkIdle(42, 35);
	const auto state = tracker.Get(42);
	ASSERT_TRUE(state.has_value());
	EXPECT_FALSE(state->busy);
	EXPECT_TRUE(state->released);

	tracker.MarkUnitRemoved(42, 36);
	EXPECT_GT(tracker.Generation(42), state->generation);
}

}  // namespace
