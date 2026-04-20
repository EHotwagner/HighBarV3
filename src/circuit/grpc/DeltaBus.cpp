// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — DeltaBus impl (T033).

#include "grpc/DeltaBus.h"
#include "grpc/Counters.h"

namespace circuit::grpc {

DeltaBus::DeltaBus(Counters* counters) : counters_(counters) {}

void DeltaBus::Publish(std::shared_ptr<const std::string> payload) {
	// Snapshot live slots under the mutex, then publish outside the
	// mutex so a slow Pop (blocked on the ring's internal cv) can't
	// back-pressure the engine thread.
	std::vector<std::shared_ptr<SubscriberSlot>> live;
	{
		std::lock_guard<std::mutex> lock(mutex_);
		live.reserve(slots_.size());
		auto it = slots_.begin();
		while (it != slots_.end()) {
			if (auto sp = it->lock()) {
				if (sp->Eviction() == EvictionReason::kNone) {
					live.push_back(std::move(sp));
				}
				++it;
			} else {
				it = slots_.erase(it);  // expired weak_ptr; drop
			}
		}
	}

	for (auto& slot : live) {
		if (!slot->TryPush(payload)) {
			slot->Evict(EvictionReason::kSlowConsumer);
			if (counters_ != nullptr) {
				counters_->cumulative_dropped_subscribers.fetch_add(
					1, std::memory_order_relaxed);
			}
		}
	}
}

std::shared_ptr<SubscriberSlot> DeltaBus::Subscribe() {
	auto slot = std::make_shared<SubscriberSlot>();
	std::lock_guard<std::mutex> lock(mutex_);
	slots_.emplace_back(slot);
	if (counters_ != nullptr) {
		counters_->subscriber_count.fetch_add(1, std::memory_order_relaxed);
	}
	return slot;
}

void DeltaBus::Unsubscribe(const std::shared_ptr<SubscriberSlot>& slot) {
	if (!slot) return;
	slot->Evict(EvictionReason::kCanceled);  // idempotent if already evicted
	bool was_live = false;
	{
		std::lock_guard<std::mutex> lock(mutex_);
		for (auto it = slots_.begin(); it != slots_.end(); ) {
			auto sp = it->lock();
			if (!sp || sp.get() == slot.get()) {
				if (sp) was_live = true;
				it = slots_.erase(it);
			} else {
				++it;
			}
		}
	}
	if (was_live && counters_ != nullptr) {
		counters_->subscriber_count.fetch_sub(1, std::memory_order_relaxed);
	}
}

std::size_t DeltaBus::SubscriberCount() const {
	std::lock_guard<std::mutex> lock(mutex_);
	std::size_t n = 0;
	for (const auto& w : slots_) {
		if (auto sp = w.lock()) {
			if (sp->Eviction() == EvictionReason::kNone) ++n;
		}
	}
	return n;
}

}  // namespace circuit::grpc
