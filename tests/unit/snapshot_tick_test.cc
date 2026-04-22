// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — SnapshotTick scheduler unit tests (003-snapshot-arm-coverage T008).
//
// The scheduler is purely numeric — no CircuitAI, no I/O — so a fake
// frame clock (just an incrementing uint32) is sufficient to exercise
// every invariant from contracts/snapshot-tick.md §Scheduler behavior.
//
// Coverage (per contracts/snapshot-tick.md §Unit-test surface):
//   1. CadenceStability: at default config with under-cap load, emissions
//      fire every snapshot_cadence_frames frames for 300 frames.
//   2. HalvingOnOverCap: with own_units_count > max at frame 0, the
//      effective_cadence_frames doubles on each successive emission
//      (30 → 60 → 120 → 240 …).
//   3. SnapBackOnUnderCap: after a halving run, dropping under-cap
//      immediately snaps the NEXT cadence value back to base.
//   4. ForcedEmissionCoalescing: flipping pending_request multiple times
//      between ticks yields exactly one extra emission at the first
//      subsequent tick.
//   5. ZeroEmissionsWhileDisabled: if Pump() is not called (the module
//      short-circuits on Disabled), no emissions occur — this is
//      tested by ensuring the scheduler is stateless w.r.t. time.

#include "grpc/SnapshotTick.h"

#include <gtest/gtest.h>

#include <cstddef>
#include <cstdint>
#include <vector>

namespace {

using ::circuit::grpc::SnapshotTick;
using ::circuit::grpc::SnapshotTickConfig;
using ::circuit::grpc::SnapshotPumpResult;

// Helper: run the scheduler across a closed frame range and collect
// every frame at which an emission fired, paired with the cadence
// value stamped at that emission.
struct EmissionEvent {
	std::uint32_t frame;
	std::uint32_t effective_cadence_frames;
	bool forced;
};

TEST(SnapshotTick, CadenceStabilityUnderCap) {
	SnapshotTick tick;
	tick.Configure({/*cadence=*/30, /*max=*/1000});

	// under-cap for 300 frames; start at frame 1 (next_snapshot_frame_
	// is initialized to 30, so first emission fires at frame 30).
	std::vector<EmissionEvent> emissions;
	for (std::uint32_t f = 1; f <= 300; ++f) {
		auto r = tick.Pump(f, /*own_units_count=*/100);
		if (r.emit) emissions.push_back({f, r.effective_cadence_frames, r.forced});
	}

	// Expect emissions at frames 30, 60, 90, …, 300 — exactly 10.
	ASSERT_EQ(emissions.size(), 10u);
	for (std::size_t i = 0; i < emissions.size(); ++i) {
		EXPECT_EQ(emissions[i].frame, 30u * (i + 1));
		EXPECT_EQ(emissions[i].effective_cadence_frames, 30u);
		EXPECT_FALSE(emissions[i].forced);
	}
}

TEST(SnapshotTick, HalvingOnOverCap) {
	SnapshotTick tick;
	tick.Configure({/*cadence=*/30, /*max=*/50});

	// own_units_count > max at every tick — effective cadence should
	// double on each emission. First emission at frame 30 carries the
	// pre-double value (30), next at 30+60=90 carries (60), next at
	// 90+120=210 carries (120), next at 210+240=450 carries (240), …
	std::vector<EmissionEvent> emissions;
	for (std::uint32_t f = 1; f <= 700; ++f) {
		auto r = tick.Pump(f, /*own_units_count=*/51);
		if (r.emit) emissions.push_back({f, r.effective_cadence_frames, r.forced});
	}

	ASSERT_GE(emissions.size(), 4u);
	EXPECT_EQ(emissions[0].frame, 30u);
	EXPECT_EQ(emissions[0].effective_cadence_frames, 30u);
	EXPECT_EQ(emissions[1].frame, 90u);
	EXPECT_EQ(emissions[1].effective_cadence_frames, 60u);
	EXPECT_EQ(emissions[2].frame, 210u);
	EXPECT_EQ(emissions[2].effective_cadence_frames, 120u);
	EXPECT_EQ(emissions[3].frame, 450u);
	EXPECT_EQ(emissions[3].effective_cadence_frames, 240u);
}

TEST(SnapshotTick, SnapBackOnUnderCap) {
	SnapshotTick tick;
	tick.Configure({/*cadence=*/30, /*max=*/50});

	// Drive the scheduler through a halving sequence under sustained
	// over-cap load, then drop under-cap and verify the first emission
	// after the drop stamps the *pre-reset* cadence and the emission
	// after that stamps the configured base (30). Exact frame numbers
	// depend on how many halvings have occurred — assert the semantic
	// invariant (pre-reset stamp > base; next stamp == base) rather
	// than baking in arithmetic.
	std::vector<EmissionEvent> emissions;
	// Run over-cap for enough frames to halve several times.
	for (std::uint32_t f = 1; f <= 2000; ++f) {
		auto r = tick.Pump(f, /*own_units_count=*/51);
		if (r.emit) emissions.push_back({f, r.effective_cadence_frames, r.forced});
	}
	const std::size_t over_cap_emission_count = emissions.size();
	const std::uint32_t pre_reset_cadence = tick.EffectiveCadenceFrames();
	ASSERT_GT(pre_reset_cadence, 30u)
		<< "precondition: expected sustained over-cap to have halved cadence above base";

	// Drop under-cap; run until two more emissions fire.
	for (std::uint32_t f = 2001; emissions.size() < over_cap_emission_count + 2 && f <= 10000; ++f) {
		auto r = tick.Pump(f, /*own_units_count=*/40);
		if (r.emit) emissions.push_back({f, r.effective_cadence_frames, r.forced});
	}
	ASSERT_GE(emissions.size(), over_cap_emission_count + 2u);

	// First emission after the drop carries the pre-reset cadence
	// (the interval that was in effect TO this emission).
	const auto& first_under = emissions[over_cap_emission_count];
	EXPECT_EQ(first_under.effective_cadence_frames, pre_reset_cadence)
		<< "first under-cap emission should stamp the pre-reset cadence";

	// Subsequent emission is at the snapped-back base cadence.
	const auto& second_under = emissions[over_cap_emission_count + 1];
	EXPECT_EQ(second_under.effective_cadence_frames, 30u)
		<< "second under-cap emission should stamp the snapped-back base cadence";

	// And the gap between them is exactly the base cadence.
	EXPECT_EQ(second_under.frame - first_under.frame, 30u);
}

TEST(SnapshotTick, ForcedEmissionCoalescing) {
	SnapshotTick tick;
	tick.Configure({/*cadence=*/30, /*max=*/1000});

	// Advance a few frames with no forced request — no emissions until
	// frame 30.
	for (std::uint32_t f = 1; f <= 9; ++f) {
		auto r = tick.Pump(f, /*own_units_count=*/100);
		EXPECT_FALSE(r.emit);
	}

	// Flip pending_request N times between frame 9 and frame 10 —
	// simulates N concurrent gRPC worker threads all calling
	// RequestSnapshot for the same frame.
	for (int i = 0; i < 16; ++i) {
		tick.PendingRequest().store(true, std::memory_order_release);
	}

	// Exactly ONE emission fires at frame 10 (forced). The next
	// periodic tick is scheduled at frame 10 + 30 = 40.
	auto r10 = tick.Pump(10, /*own_units_count=*/100);
	EXPECT_TRUE(r10.emit);
	EXPECT_TRUE(r10.forced);
	EXPECT_EQ(r10.effective_cadence_frames, 30u);

	// Flag is cleared after the first drain — subsequent ticks do not
	// fire until the periodic cadence is reached.
	EXPECT_FALSE(tick.PendingRequest().load(std::memory_order_acquire));

	// Frames 11..39: no emission.
	for (std::uint32_t f = 11; f <= 39; ++f) {
		auto r = tick.Pump(f, /*own_units_count=*/100);
		EXPECT_FALSE(r.emit) << "unexpected emission at frame " << f;
	}

	// Frame 40: periodic emission.
	auto r40 = tick.Pump(40, /*own_units_count=*/100);
	EXPECT_TRUE(r40.emit);
	EXPECT_FALSE(r40.forced);
	EXPECT_EQ(r40.effective_cadence_frames, 30u);
}

TEST(SnapshotTick, ZeroEmissionsWhenPumpNotCalled) {
	// Gateway-Disabled behavior: CGrpcGatewayModule short-circuits on
	// Disabled before calling Pump, so the scheduler observes no
	// frames. This test documents that the scheduler has no hidden
	// time source — if Pump isn't called, no emissions happen.
	SnapshotTick tick;
	tick.Configure({/*cadence=*/30, /*max=*/1000});

	// Set the pending flag to ensure even a forced request doesn't
	// self-fire without a Pump call.
	tick.PendingRequest().store(true, std::memory_order_release);

	// Scheduler state must remain at its initial values.
	EXPECT_EQ(tick.EffectiveCadenceFrames(), 30u);
	EXPECT_EQ(tick.NextSnapshotFrame(), 30u);
	EXPECT_TRUE(tick.PendingRequest().load(std::memory_order_acquire));

	// Once Pump is called (post-Healthy transition), the pending
	// request fires normally.
	auto r = tick.Pump(1, /*own_units_count=*/100);
	EXPECT_TRUE(r.emit);
	EXPECT_TRUE(r.forced);
}

TEST(SnapshotTick, OverCapCapsAtMaxEffectiveCadence) {
	// Sustained over-cap eventually pins effective_cadence_frames at
	// kMaxEffectiveCadenceFrames (1024) rather than overflowing.
	SnapshotTick tick;
	tick.Configure({/*cadence=*/30, /*max=*/50});

	std::uint32_t last_stamped = 0;
	for (std::uint32_t f = 1; f <= 100000; ++f) {
		auto r = tick.Pump(f, /*own_units_count=*/999);
		if (r.emit) last_stamped = r.effective_cadence_frames;
	}
	// Once pinned, every subsequent emission carries kMax.
	EXPECT_EQ(last_stamped, SnapshotTick::kMaxEffectiveCadenceFrames);
}

}  // namespace
