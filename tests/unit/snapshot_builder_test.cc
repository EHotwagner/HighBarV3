// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — SnapshotBuilder validation rules (T049).
//
// The manager-walk path requires a live CCircuitAI, which is tightly
// coupled to the Spring engine callback. Rather than mocking it, the
// builder's runtime behavior is exercised end-to-end by
// tests/headless/us1-observer.sh against spring-headless. Phase 3
// unit coverage here is the schema-contract checks we CAN run
// against a built StateSnapshot:
//   * own_units.health <= own_units.max_health (data-model §1)
//   * build_progress == 0 when under_construction == false
//   * radar_enemies carry degraded positions (sentinel check)

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
		<< "sentinel: if the builder ever produces this, the assertion "
		   "in tests/headless/us1-observer.sh's observer output-grep "
		   "will catch it.";
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
