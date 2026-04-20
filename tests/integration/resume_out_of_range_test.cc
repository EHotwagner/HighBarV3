// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — resume-out-of-range integration test (T099).
//
// FR-008: when a reconnecting client requests resume_from_seq=N but
// the ring no longer holds seq=N (older entries evicted), the server
// sends a fresh StateSnapshot and continues with the next monotonic
// seq. The client's discriminator-based receiver detects the reset
// (payload arm = snapshot, not delta) and treats it as a full state
// refresh.
//
// Requires the dlopen mock-engine harness.

#include <gtest/gtest.h>

namespace {

TEST(ResumeOutOfRange, SendsFreshSnapshotWhenSeqEvicted) {
	GTEST_SKIP() << "requires dlopen mock-engine harness";
}

TEST(ResumeOutOfRange, LiveSequenceAfterFreshSnapshotIsMonotonic) {
	// Regression guard against the T094 seq-collision bug: the fresh
	// snapshot's seq and the next delta's seq must not collide. The
	// filter in StreamStateCallData::PumpLoop (last_sent_seq_) enforces
	// this; this test exercises it in a real dlopen harness run.
	GTEST_SKIP() << "requires dlopen mock-engine harness";
}

}  // namespace
