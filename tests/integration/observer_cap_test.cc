// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — observer cap enforcement (T052).
//
// With the plugin running, subscribe 4 observers via StreamState and
// assert a 5th attempt fails RESOURCE_EXHAUSTED (FR-015a, hard cap 4).
// The pre-existing 4 must remain connected and receiving deltas.
//
// Same harness blocker as observer_flow_test.cc (T051).

#include <gtest/gtest.h>

namespace {

TEST(ObserverCap, FifthSubscriberIsRejected_PLACEHOLDER) {
	GTEST_SKIP() << "blocked on mock-engine harness — see tests/integration/README.md";
}

TEST(ObserverCap, PreExistingFourUnaffectedByRejection_PLACEHOLDER) {
	GTEST_SKIP() << "blocked on mock-engine harness — see tests/integration/README.md";
}

}  // namespace
