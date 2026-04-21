// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — AI slot invariant unit test (T068).
//
// Verifies FR-011 / FR-012 at the TryClaimAiSlot / ReleaseAiSlot
// primitive level. The full SubmitCommands → ALREADY_EXISTS wire path
// is covered by tests/headless/us2-ai-coexist.sh against a live
// spring-headless match; this test locks down the atomic primitive
// that service layer relies on.
//
// Build: add_executable gated on find_package(GTest) same as
// delta_bus_test.

#include "grpc/HighBarService.h"
#include "grpc/AuthToken.h"
#include "grpc/Counters.h"

#include <gtest/gtest.h>

#include <atomic>
#include <thread>
#include <vector>

namespace {

using circuit::grpc::AuthToken;
using circuit::grpc::Counters;
using circuit::grpc::HighBarService;

// Construct a HighBarService without touching gRPC (no Bind called).
// HighBarService's ctor is cheap — just stores pointers — so this is
// fine for testing the slot primitives.
TEST(AiSlot, FirstClaimSucceedsSecondFails) {
	Counters counters;
	HighBarService svc(/*ai=*/nullptr, &counters, /*token=*/nullptr);

	EXPECT_TRUE(svc.TryClaimAiSlot());
	// Second claim while first held → must fail.
	EXPECT_FALSE(svc.TryClaimAiSlot());
}

TEST(AiSlot, ReleaseAllowsReclaim) {
	Counters counters;
	HighBarService svc(nullptr, &counters, nullptr);

	ASSERT_TRUE(svc.TryClaimAiSlot());
	svc.ReleaseAiSlot();
	// A subsequent AI client must be able to reclaim (FR-012).
	EXPECT_TRUE(svc.TryClaimAiSlot());
	svc.ReleaseAiSlot();
}

TEST(AiSlot, RacingClaimsAtMostOneWins) {
	Counters counters;
	HighBarService svc(nullptr, &counters, nullptr);

	constexpr int kThreads = 8;
	std::atomic<int> winners{0};
	std::vector<std::thread> ts;
	for (int i = 0; i < kThreads; ++i) {
		ts.emplace_back([&]() {
			if (svc.TryClaimAiSlot()) {
				++winners;
			}
		});
	}
	for (auto& t : ts) t.join();
	EXPECT_EQ(winners.load(), 1)
		<< "exactly one thread must win the AI-slot race";
}

TEST(AiSlot, ObserverCapIsIndependent) {
	// Observer reservations must not share state with the AI slot —
	// the single-AI invariant is orthogonal to the 4-observer cap.
	Counters counters;
	HighBarService svc(nullptr, &counters, nullptr);

	ASSERT_TRUE(svc.TryClaimAiSlot());
	for (int i = 0; i < 4; ++i) {
		EXPECT_TRUE(svc.TryReserveObserverSlot());
	}
	EXPECT_FALSE(svc.TryReserveObserverSlot())
		<< "observer cap is 4 regardless of AI state (FR-015a)";

	// AI slot independence confirmed: release observers without touching AI.
	for (int i = 0; i < 4; ++i) {
		svc.ReleaseObserverSlot();
	}
	// AI slot still held.
	EXPECT_FALSE(svc.TryClaimAiSlot());
	svc.ReleaseAiSlot();
}

}  // namespace
