// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — SnapshotTick implementation (003-snapshot-arm-coverage T010).
//
// See SnapshotTick.h for the contract. All arithmetic is over uint32;
// overflow is prevented by the kMaxEffectiveCadenceFrames cap.

#include "grpc/SnapshotTick.h"

namespace circuit::grpc {

SnapshotTick::SnapshotTick(const SnapshotTickConfig& cfg) {
	Configure(cfg);
}

void SnapshotTick::Configure(const SnapshotTickConfig& cfg) {
	snapshot_cadence_frames_ = cfg.snapshot_cadence_frames;
	snapshot_max_units_      = cfg.snapshot_max_units;
	effective_cadence_frames_ = cfg.snapshot_cadence_frames;
	next_snapshot_frame_     = cfg.snapshot_cadence_frames;
	configured_              = true;
}

SnapshotPumpResult SnapshotTick::Pump(std::uint32_t frame,
                                       std::size_t own_units_count) {
	SnapshotPumpResult out;

	// Drain the forced-request flag FIRST so the same tick can't both
	// skip the periodic emission and leave the flag dangling. The flag
	// is cleared via exchange to coalesce concurrent callers; all of
	// them observe the same `true→false` transition once.
	const bool forced = pending_request_.exchange(false,
	                                              std::memory_order_acq_rel);

	const bool cadence_due = (frame >= next_snapshot_frame_);

	if (!forced && !cadence_due) {
		return out;  // emit=false, cadence stays as-is
	}

	// Emit this frame. Stamp the cadence value IN EFFECT right now (the
	// pre-double / pre-reset value), then update effective_cadence_frames_
	// for the *next* emission based on the current over/under-cap state.
	out.emit   = true;
	out.forced = forced;
	out.effective_cadence_frames = effective_cadence_frames_;

	if (own_units_count > snapshot_max_units_) {
		// Over-cap: double the cadence for the next emission, capped at
		// kMaxEffectiveCadenceFrames so runaway unit counts can't starve
		// the stream entirely.
		std::uint32_t doubled = effective_cadence_frames_ * 2u;
		if (doubled < effective_cadence_frames_) {
			// Overflow guard (uint32 wrap).
			doubled = kMaxEffectiveCadenceFrames;
		}
		if (doubled > kMaxEffectiveCadenceFrames) {
			doubled = kMaxEffectiveCadenceFrames;
		}
		effective_cadence_frames_ = doubled;
	} else if (effective_cadence_frames_ > snapshot_cadence_frames_) {
		// Under-cap after prior over-cap period: snap back to base.
		// Asymmetric recovery per research.md §R2.
		effective_cadence_frames_ = snapshot_cadence_frames_;
	}
	// else: steady-state under-cap — leave effective_cadence_frames_ unchanged.

	// Schedule the next periodic emission. For forced emissions, the
	// next periodic tick is still `frame + effective_cadence_frames_`
	// (i.e., forced emissions do not shift the periodic schedule back).
	// Reading frame (not next_snapshot_frame_) ensures forced emissions
	// don't cause the next periodic tick to fire immediately.
	next_snapshot_frame_ = frame + effective_cadence_frames_;

	return out;
}

}  // namespace circuit::grpc
