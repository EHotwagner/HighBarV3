// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — US2 AI-move integration test (T070).
//
// Asserts: SubmitCommands{MoveTo} → CCircuitUnit::Cmd* dispatched
// within one frame; state stream reflects unit movement within 3
// frames of submission (SC-009).
//
// Blocked on the dlopen-driven mock-engine harness — same as
// tests/integration/observer_flow_test.cc (T051). When that harness
// lands, this test spins up a fake CCircuitAI with a single owned
// unit, boots HighBarService + CGrpcGatewayModule, issues a MoveTo
// via a test-internal gRPC client, then ticks OnFrameTick and
// asserts the unit's CmdMoveTo invocation and the resulting delta.

#include <gtest/gtest.h>

namespace {

TEST(AiMoveFlow, MoveToDispatchedWithinOneFrame) {
	GTEST_SKIP() << "requires dlopen mock-engine harness "
	             << "(tests/integration/README.md)";
}

TEST(AiMoveFlow, StateStreamReflectsMoveWithinThreeFrames) {
	GTEST_SKIP() << "requires dlopen mock-engine harness";
}

}  // namespace
