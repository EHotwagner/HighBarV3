// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — resume-in-ring integration test (T098).
//
// FR-007: when a reconnecting client requests resume_from_seq=N and N
// is still in the RingBuffer's window, the server replays the range
// [N+1 … head] before connecting the live SubscriberSlot. The client
// trace MUST be strictly monotonic and carry no gaps or duplicates
// (SC-005 invariants via resume_gap_check.cc).
//
// Requires the dlopen mock-engine harness (tests/integration/README.md).

#include <gtest/gtest.h>

namespace {

TEST(ResumeInRing, ReplaysExactRangeWithoutGapsOrDuplicates) {
	GTEST_SKIP() << "requires dlopen mock-engine harness";
}

TEST(ResumeInRing, FirstReplayedSeqEqualsResumePointPlusOne) {
	GTEST_SKIP() << "requires dlopen mock-engine harness";
}

}  // namespace
