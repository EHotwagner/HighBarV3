// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — RingBuffer impl (T035).

#include "grpc/RingBuffer.h"

#include <algorithm>
#include <cassert>
#include <stdexcept>

namespace circuit::grpc {

RingBuffer::RingBuffer(std::size_t capacity)
	: capacity_(capacity), entries_(capacity) {
	if (capacity == 0) {
		throw std::invalid_argument("RingBuffer capacity must be > 0");
	}
}

void RingBuffer::Push(std::uint64_t seq,
                      std::shared_ptr<const std::string> payload) {
	std::lock_guard<std::mutex> lock(mutex_);
	if (head_seq_ != 0 && seq <= head_seq_) {
		throw std::invalid_argument(
			"RingBuffer::Push: seq must be strictly increasing");
	}
	entries_[head_] = RingEntry{seq, std::move(payload)};
	head_ = (head_ + 1) % capacity_;
	if (filled_ < capacity_) {
		++filled_;
	}
	head_seq_ = seq;
}

std::optional<std::vector<RingEntry>>
RingBuffer::GetFromSeq(std::uint64_t from_seq) const {
	std::lock_guard<std::mutex> lock(mutex_);
	if (filled_ == 0) {
		return std::nullopt;
	}
	// tail_seq = head_seq_ - filled_ + 1
	const std::uint64_t tail_seq = head_seq_ - (filled_ - 1);
	// Request is "give me entries newer than from_seq" — i.e.
	// [from_seq+1, head_seq_]. Valid iff from_seq >= tail_seq - 1
	// (we still hold the entry AFTER from_seq) AND from_seq <= head_seq_.
	if (from_seq + 1 < tail_seq) {
		return std::nullopt;  // too old
	}
	if (from_seq > head_seq_) {
		// Client thinks it's ahead of the server; treat as out of range
		// so it resets from fresh snapshot.
		return std::nullopt;
	}
	if (from_seq == head_seq_) {
		return std::vector<RingEntry>{};  // nothing newer, but still valid
	}

	std::vector<RingEntry> out;
	const std::size_t count =
		static_cast<std::size_t>(head_seq_ - from_seq);
	out.reserve(count);
	// Copy backward from head-1 until we have all entries newer than from_seq.
	// entries_[head_] is the next write slot; entries_[(head_ - 1 + cap) % cap]
	// is the newest.
	std::size_t idx = (head_ + capacity_ - 1) % capacity_;
	for (std::size_t i = 0; i < count; ++i) {
		out.push_back(entries_[idx]);
		idx = (idx + capacity_ - 1) % capacity_;
	}
	// Reverse so callers see oldest-first.
	std::reverse(out.begin(), out.end());
	return out;
}

std::uint64_t RingBuffer::HeadSeq() const {
	std::lock_guard<std::mutex> lock(mutex_);
	return head_seq_;
}

std::size_t RingBuffer::Size() const {
	std::lock_guard<std::mutex> lock(mutex_);
	return filled_;
}

}  // namespace circuit::grpc
