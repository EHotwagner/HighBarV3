// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — resume-history ring buffer (T035).
//
// Keeps the last N (config-driven, default 2048) serialized
// StateUpdate payloads keyed by monotonic `seq`. A client that
// reconnects with `resume_from_seq = N` and N is still in the ring
// gets `[N+1, head]` replayed before the live stream attaches.
// If N is out of range, the client falls back to a fresh snapshot
// with the next monotonic seq (research §5, FR-007, FR-008).

#pragma once

#include <cstdint>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <vector>

namespace circuit::grpc {

struct RingEntry {
	std::uint64_t seq;
	std::shared_ptr<const std::string> payload;
};

class RingBuffer {
public:
	explicit RingBuffer(std::size_t capacity);

	// Append a serialized StateUpdate. Called from the engine thread
	// only. `seq` must be strictly greater than the last pushed seq.
	void Push(std::uint64_t seq, std::shared_ptr<const std::string> payload);

	// Copy out [from_seq+1, head] if all those entries are still in
	// the ring. Returns nullopt if `from_seq` is out of range (either
	// too old — evicted — or ahead of head).
	std::optional<std::vector<RingEntry>> GetFromSeq(std::uint64_t from_seq) const;

	// Head seq (last pushed). 0 if nothing pushed yet.
	std::uint64_t HeadSeq() const;

	std::size_t Capacity() const { return capacity_; }
	std::size_t Size() const;

private:
	const std::size_t capacity_;
	mutable std::mutex mutex_;
	std::vector<RingEntry> entries_;  // capacity-sized, ring-indexed
	std::size_t head_ = 0;             // next write position
	std::size_t filled_ = 0;           // entries in [0, filled_) are live
	std::uint64_t head_seq_ = 0;       // highest seq pushed
};

}  // namespace circuit::grpc
