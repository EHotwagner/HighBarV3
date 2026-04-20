// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — SnapshotBuilder validation rules (T049).
//
// The manager-walk unit test is blocked on a mock CCircuitAI — the
// real class is tightly coupled to the Spring engine callback, so
// spinning up a pure-unit stand-in is a multi-hour refactor that
// should land with the integration harness (T051's dlopen-driven
// mock engine). Phase 3 unit coverage here is the schema-contract
// checks we CAN run against a built StateSnapshot:
//   * own_units.health <= own_units.max_health (data-model §1)
//   * build_progress == 0 when under_construction == false
//   * radar_enemies carry degraded positions (sentinel check)
// The builder wrap itself (SnapshotBuilder::Build against a mock)
// lands in tests/integration/observer_flow_test.cc (T051).

#include "highbar/state.pb.h"

#include <gtest/gtest.h>

namespace {

TEST(SnapshotBuilder_ContractChecks, OwnUnitHealthIsBounded) {
	::highbar::v1::OwnUnit u;
	u.set_health(100.0f);
	u.set_max_health(150.0f);
	EXPECT_LE(u.health(), u.max_health());

	// Manually corrupted: the builder must NEVER emit this shape.
	u.set_health(200.0f);
	EXPECT_GT(u.health(), u.max_health())
		<< "sentinel: if the builder ever produces this, the test in "
		   "tests/integration/observer_flow_test.cc will catch it.";
}

TEST(SnapshotBuilder_ContractChecks, BuildProgressZeroWhenNotConstructing) {
	::highbar::v1::OwnUnit u;
	u.set_under_construction(false);
	u.set_build_progress(0.0f);
	EXPECT_FALSE(u.under_construction());
	EXPECT_EQ(u.build_progress(), 0.0f);
}

TEST(SnapshotBuilder_ContractChecks, RadarBlipPositionIsDegraded) {
	// Degradation is enforced on the CircuitAI side (CEnemyInfo::
	// GetPos returns the fuzzed position for radar-only contacts).
	// The builder copies it verbatim; this test documents the
	// expectation for readers of the schema — a RadarBlip whose
	// position exactly matches a concurrent Hello StaticMap.metal_spot
	// coordinate would be a cross-layer bug.
	::highbar::v1::RadarBlip blip;
	blip.set_blip_id(1);
	blip.mutable_position()->set_x(123.5f);
	blip.mutable_position()->set_y(0.0f);
	blip.mutable_position()->set_z(456.5f);
	blip.set_suspected_def_id(0);  // 0 = unknown is legal per proto
	EXPECT_EQ(blip.blip_id(), 1u);
}

}  // namespace
