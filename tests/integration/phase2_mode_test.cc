// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — Phase-2 mode integration test (T083).
//
// Asserts: with AIOptions.enable_builtin=false, the four built-in
// decision modules (military/builder/factory/economy) are NOT
// registered in CCircuitAI::modules, so their Update() / UnitCreated
// hooks never fire. The gateway module DOES run.
//
// A direct in-process check would use a mock CCircuitAI and count
// Update() calls on each manager. That requires the dlopen harness
// to build a minimal CCircuitAI instance.

#include <gtest/gtest.h>

namespace {

TEST(Phase2Mode, BuiltinModuleUpdateNotCalledWhenDisabled) {
	GTEST_SKIP() << "requires dlopen mock-engine harness "
	             << "(tests/integration/README.md)";
}

TEST(Phase2Mode, GatewayModuleStillRunsWhenBuiltinDisabled) {
	GTEST_SKIP() << "requires dlopen mock-engine harness";
}

TEST(Phase2Mode, ExternalCommandsStillDispatchedWhenBuiltinDisabled) {
	GTEST_SKIP() << "requires dlopen mock-engine harness";
}

}  // namespace
