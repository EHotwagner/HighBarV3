// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — transport parity test (T075).
//
// SC-008: identical end-to-end behavior on UDS and loopback TCP,
// modulo timing. The same scripted sequence (Hello → StreamState
// subscribe → SubmitCommands{MoveTo} → reconnect with resume_from_seq)
// runs against both transports; the resulting StateUpdate traces must
// be equal up to timing.
//
// Blocked on the dlopen mock-engine harness (tests/integration/README.md).
// Same harness gate as T051/T052/T070.

#include <gtest/gtest.h>

namespace {

TEST(TransportParity, UdsAndTcpProduceEquivalentStreams) {
	GTEST_SKIP() << "requires dlopen mock-engine harness";
}

TEST(TransportParity, NonLoopbackTcpBindRejectedAtStartup) {
	// Testable without the engine harness — HighBarService::Bind is a
	// pure function of endpoint + proto service registration. But it
	// still needs gRPC linked (ServerBuilder). Marked skip until the
	// integration fixture builds with vcpkg.
	GTEST_SKIP() << "requires gRPC-linked ServerBuilder fixture";
}

TEST(TransportParity, WantedSpeedDispatchParityAndSemanticGateExpectations) {
	GTEST_SKIP() << "requires dlopen mock-engine harness";
}

TEST(TransportParity, ManualLaunchAndDgunDispatchStayDistinct) {
	GTEST_SKIP() << "requires dlopen mock-engine harness";
}

TEST(TransportParity, AttackAndSetTargetRewriteSurfacesStayTransportEquivalent) {
	GTEST_SKIP() << "requires dlopen mock-engine harness";
}

}  // namespace
