// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — CommandQueue impl (T055).

#include "grpc/CommandQueue.h"
#include "grpc/Counters.h"

#include <algorithm>
#include <utility>
#include <vector>

namespace circuit::grpc {

CommandQueue::CommandQueue(Counters* counters, std::size_t capacity)
	: counters_(counters), capacity_(capacity) {}

bool CommandQueue::TryPush(QueuedCommand cmd) {
	std::lock_guard<std::mutex> lock(mutex_);
	if (queue_.size() >= capacity_) {
		return false;
	}
	queue_.push(std::move(cmd));
	if (counters_ != nullptr) {
		counters_->command_queue_depth.store(
			static_cast<std::uint32_t>(queue_.size()),
			std::memory_order_relaxed);
	}
	return true;
}

bool CommandQueue::TryPushBatch(std::vector<QueuedCommand> cmds) {
	std::lock_guard<std::mutex> lock(mutex_);
	if (cmds.size() > capacity_ - queue_.size()) {
		return false;
	}
	for (auto& cmd : cmds) {
		queue_.push(std::move(cmd));
	}
	if (counters_ != nullptr) {
		counters_->command_queue_depth.store(
			static_cast<std::uint32_t>(queue_.size()),
			std::memory_order_relaxed);
	}
	return true;
}

std::size_t CommandQueue::Drain(std::vector<QueuedCommand>* out,
                                std::size_t max) {
	if (out == nullptr) return 0;
	std::lock_guard<std::mutex> lock(mutex_);
	const std::size_t budget = (max == 0) ? queue_.size()
	                                      : std::min(max, queue_.size());
	out->reserve(out->size() + budget);
	for (std::size_t i = 0; i < budget; ++i) {
		out->push_back(std::move(queue_.front()));
		queue_.pop();
	}
	if (counters_ != nullptr) {
		counters_->command_queue_depth.store(
			static_cast<std::uint32_t>(queue_.size()),
			std::memory_order_relaxed);
	}
	return budget;
}

std::size_t CommandQueue::Depth() const {
	std::lock_guard<std::mutex> lock(mutex_);
	return queue_.size();
}

std::size_t CommandQueue::AvailableCapacity() const {
	std::lock_guard<std::mutex> lock(mutex_);
	return capacity_ - queue_.size();
}

}  // namespace circuit::grpc
