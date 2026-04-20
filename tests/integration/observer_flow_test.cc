// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — observer flow integration (T051).
//
// End-to-end test through a dlopen'd plugin + mock-engine harness:
//   * Observer connects via UDS.
//   * First StateUpdate arrives within 2s (SC-001).
//   * 60s of deltas land with strictly monotonic seq and no gaps.
//   * Disconnect does not disturb the plugin.
//
// STATUS: The dlopen-driven mock-engine harness doesn't exist yet;
// building it requires a minimal SSkirmishAICallback stand-in and a
// CCircuitAI test fixture. Both are multi-hour refactors that
// should happen in a dedicated integration-test harness PR.
// Placeholder here documents the expected contract so reviewers of
// future harness work know what this test must assert.

#include <gtest/gtest.h>

namespace {

TEST(ObserverFlow, FirstSnapshotWithinTwoSeconds_PLACEHOLDER) {
	GTEST_SKIP() << "blocked on mock-engine harness — see tests/integration/README.md";
}

TEST(ObserverFlow, SixtySecondsOfDeltasWithMonotonicSeq_PLACEHOLDER) {
	GTEST_SKIP() << "blocked on mock-engine harness — see tests/integration/README.md";
}

TEST(ObserverFlow, DisconnectDoesNotDisturbPlugin_PLACEHOLDER) {
	GTEST_SKIP() << "blocked on mock-engine harness — see tests/integration/README.md";
}

}  // namespace
