// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — SubscriberSlot impl (T034).

#include "grpc/SubscriberSlot.h"

namespace circuit::grpc {

SubscriberSlot::SubscriberSlot(std::size_t capacity) : capacity_(capacity) {}

bool SubscriberSlot::TryPush(std::shared_ptr<const std::string> payload) {
	{
		std::lock_guard<std::mutex> lock(mutex_);
		if (eviction_.load(std::memory_order_relaxed) != EvictionReason::kNone) {
			return false;  // already evicted; treat as dropped
		}
		if (queue_.size() >= capacity_) {
			dropped_.fetch_add(1, std::memory_order_relaxed);
			return false;
		}
		queue_.push_back(std::move(payload));
	}
	cv_.notify_one();
	return true;
}

bool SubscriberSlot::BlockingPop(std::shared_ptr<const std::string>* out) {
	std::unique_lock<std::mutex> lock(mutex_);
	cv_.wait(lock, [this] {
		return !queue_.empty()
		    || eviction_.load(std::memory_order_acquire) != EvictionReason::kNone;
	});
	if (!queue_.empty()) {
		*out = std::move(queue_.front());
		queue_.pop_front();
		return true;
	}
	return false;  // evicted + drained
}

void SubscriberSlot::Evict(EvictionReason reason) {
	EvictionReason expected = EvictionReason::kNone;
	if (eviction_.compare_exchange_strong(expected, reason)) {
		cv_.notify_all();
	}
}

std::size_t SubscriberSlot::QueueDepth() const {
	std::lock_guard<std::mutex> lock(mutex_);
	return queue_.size();
}

}  // namespace circuit::grpc
