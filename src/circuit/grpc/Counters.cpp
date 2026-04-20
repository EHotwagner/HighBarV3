// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — atomic runtime counters impl (T027).

#include "grpc/Counters.h"

#include <algorithm>

namespace circuit::grpc {

Counters::Counters() = default;

void Counters::RecordFrameFlushUs(std::uint64_t us) {
	std::lock_guard<std::mutex> lock(flush_mutex_);
	flush_samples_[flush_head_] = us;
	flush_head_ = (flush_head_ + 1) % kFlushBucketSize;
	if (flush_filled_ < kFlushBucketSize) {
		++flush_filled_;
	}
}

std::uint64_t Counters::FrameFlushP99Us() const {
	std::vector<std::uint64_t> snap;
	{
		std::lock_guard<std::mutex> lock(flush_mutex_);
		if (flush_filled_ == 0) {
			return 0;
		}
		snap.assign(flush_samples_.begin(),
		            flush_samples_.begin() + flush_filled_);
	}
	// 99th percentile. Index = ceil(0.99 * (n - 1)).
	const std::size_t k = static_cast<std::size_t>(
		0.99 * static_cast<double>(snap.size() - 1) + 0.5);
	std::nth_element(snap.begin(), snap.begin() + k, snap.end());
	return snap[k];
}

}  // namespace circuit::grpc
