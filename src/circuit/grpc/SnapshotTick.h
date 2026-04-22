// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — SnapshotTick scheduler (003-snapshot-arm-coverage T009).
//
// Purely numeric frame-driven scheduler that decides when the plugin
// should emit a periodic StateSnapshot. Called from
// CGrpcGatewayModule::OnFrameTick on the engine thread; owns no
// CircuitAI state, no locks, no I/O. Uses an atomic<bool> for the
// RequestSnapshot RPC forced-emission flag (written by gRPC workers,
// read and drained by the engine thread).
//
// Behavior contract: contracts/snapshot-tick.md §Scheduler behavior.
// Research: research.md §R1 (call site) and §R2 (halving semantics).

#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>

namespace circuit::grpc {

struct SnapshotTickConfig {
	// Frames between periodic snapshots while own_units.length <=
	// snapshot_max_units. Default 30 (≈1s at 30fps headless).
	std::uint32_t snapshot_cadence_frames = 30;
	// Above this own_units.length, emissions double the effective
	// cadence (up to a 1024-frame cap) as a safety valve.
	std::uint32_t snapshot_max_units = 1000;
};

struct SnapshotPumpResult {
	// True if the caller should build + broadcast a snapshot this
	// frame; false otherwise (no-op, no serializer work).
	bool emit = false;
	// Cadence value to stamp on StateSnapshot.effective_cadence_frames
	// when `emit` is true. This is the pre-double, pre-reset value —
	// the interval in effect AT THIS emission. Zero when emit is false.
	std::uint32_t effective_cadence_frames = 0;
	// True if this emission was triggered by a RequestSnapshot RPC
	// (drains pending_request_) rather than by the periodic cadence.
	// Informational only — both kinds use the same serializer path.
	bool forced = false;
};

class SnapshotTick {
public:
	SnapshotTick() = default;
	explicit SnapshotTick(const SnapshotTickConfig& cfg);

	SnapshotTick(const SnapshotTick&) = delete;
	SnapshotTick& operator=(const SnapshotTick&) = delete;

	// Configure (or reconfigure) the scheduler. Must be called before
	// the first Pump() to honor snapshot_cadence_frames for the first
	// tick. Re-calling this resets next_snapshot_frame_ and
	// effective_cadence_frames_ to the new config.
	void Configure(const SnapshotTickConfig& cfg);

	// Pump one frame. Engine-thread only. Returns a decision: whether
	// to emit a snapshot now, the cadence value to stamp on it, and
	// whether the emission was forced by a pending RequestSnapshot RPC.
	//
	// Contract invariants (see contracts/snapshot-tick.md §Scheduler
	// behavior):
	//   1. Emission cadence: at steady state + under-cap, emissions fire
	//      every snapshot_cadence_frames frames.
	//   2. Halving on over-cap: effective_cadence_frames doubles for
	//      the NEXT emission (capped at 1024). Current emission carries
	//      the pre-double value.
	//   3. Snap-back on under-cap: if own_units_count <= max AND
	//      effective_cadence_frames_ > snapshot_cadence_frames, reset
	//      to base for the NEXT emission. Current emission carries the
	//      pre-reset value.
	//   4. Forced emission: if pending_request_ is set at the top of
	//      the frame, emit this frame regardless of cadence, clear the
	//      flag, and reschedule the next periodic emission at
	//      frame + effective_cadence_frames.
	SnapshotPumpResult Pump(std::uint32_t frame,
	                          std::size_t own_units_count);

	// Reference to the forced-emission atomic flag. gRPC worker threads
	// set this from the RequestSnapshot handler; Pump drains it exactly
	// once per frame regardless of caller count (FR-006 coalescing).
	std::atomic<bool>& PendingRequest() { return pending_request_; }

	// Read-only accessors for diagnostics and tests.
	std::uint32_t SnapshotCadenceFrames() const { return snapshot_cadence_frames_; }
	std::uint32_t SnapshotMaxUnits()      const { return snapshot_max_units_; }
	std::uint32_t EffectiveCadenceFrames() const { return effective_cadence_frames_; }
	std::uint32_t NextSnapshotFrame()      const { return next_snapshot_frame_; }

	// Cap on doubling under sustained over-cap load (research.md §R2).
	static constexpr std::uint32_t kMaxEffectiveCadenceFrames = 1024;

private:
	std::uint32_t snapshot_cadence_frames_ = 30;
	std::uint32_t snapshot_max_units_      = 1000;
	std::uint32_t effective_cadence_frames_ = 30;
	std::uint32_t next_snapshot_frame_     = 30;
	bool          configured_               = false;
	std::atomic<bool> pending_request_{false};
};

}  // namespace circuit::grpc
