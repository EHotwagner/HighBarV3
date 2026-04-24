// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — atomic runtime counters (T027).
//
// Engine-thread writes and gRPC-worker-thread reads use
// std::atomic<T> so snapshots via GetRuntimeCounters (T029) return
// a coherent view under atomic loads — no global lock, per
// data-model §10 invariants.

#pragma once

#include <array>
#include <atomic>
#include <cstdint>
#include <mutex>
#include <vector>

namespace circuit::grpc {

class Counters {
public:
	Counters();

	// --- Monotonic gauges / totals (atomic) --------------------------

	std::atomic<std::uint32_t> subscriber_count{0};
	std::atomic<std::uint64_t> cumulative_dropped_subscribers{0};
	std::atomic<std::uint32_t> command_queue_depth{0};
	std::atomic<std::uint64_t> command_submissions_rejected_resource_exhausted{0};
	std::atomic<std::uint64_t> command_submissions_rejected_invalid_argument{0};
	std::atomic<std::uint64_t> command_submissions_warning_only_would_reject{0};
	std::atomic<std::uint64_t> command_dispatch_failures{0};
	std::atomic<std::uint64_t> admin_actions_accepted{0};
	std::atomic<std::uint64_t> admin_actions_rejected{0};
	std::atomic<std::uint64_t> admin_audit_events{0};
	std::atomic<std::uint32_t> frames_since_bind{0};

	// --- Frame-flush p99 rolling bucket ------------------------------
	//
	// Engine thread records flush latencies via RecordFrameFlushUs().
	// gRPC workers read the current p99 via FrameFlushP99Us().
	// Implementation: 1024-entry ring of samples, protected by a tiny
	// spinlock (engine-thread writer never blocks on worker reads
	// beyond memcpy of the ring; reader computes p99 on a snapshot
	// copy).

	void RecordFrameFlushUs(std::uint64_t us);
	std::uint64_t FrameFlushP99Us() const;

private:
	static constexpr std::size_t kFlushBucketSize = 1024;
	mutable std::mutex flush_mutex_;
	std::array<std::uint64_t, kFlushBucketSize> flush_samples_{};
	std::size_t flush_head_ = 0;
	std::size_t flush_filled_ = 0;
};

}  // namespace circuit::grpc
