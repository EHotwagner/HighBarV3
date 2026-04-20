// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — ValidateCommand unit tests (T067).
//
// Exercises data-model §4 validation rules. Full validation requires
// a live CCircuitAI + CCircuitUnit registry, which are only
// available through the dlopen-driven integration harness (see
// tests/integration/README.md — same blocker as T051/T052). The
// testable pure-logic surface here is PosInMap plus the validation
// error-code plumbing. Commit as GTEST_SKIP anchors so the file
// compiles against a GoogleTest-linked build and will light up when
// the mock-engine harness lands.

#include <gtest/gtest.h>

namespace {

TEST(CommandValidation, InvalidTargetUnitIdReturnsInvalidArgument) {
	GTEST_SKIP() << "requires mock CCircuitAI + teamUnits harness "
	             << "(tests/integration/README.md)";
}

TEST(CommandValidation, NonConstructibleBuildDefReturnsInvalidArgument) {
	GTEST_SKIP() << "requires mock CCircuitDef build-options graph";
}

TEST(CommandValidation, MoveToOutOfMapReturnsInvalidArgument) {
	GTEST_SKIP() << "requires AIFloat3::maxxpos/maxzpos initialization from "
	             << "CTerrainData; mock the terrain-manager construction in "
	             << "the integration harness";
}

TEST(CommandValidation, ValidCommandReturnsOk) {
	GTEST_SKIP() << "requires mock CCircuitAI harness";
}

}  // namespace
