// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — CommandQueue impl (T055).

#include "grpc/CommandQueue.h"

#include <utility>

namespace circuit::grpc {

CommandQueue::CommandQueue(std::size_t capacity)
	: capacity_(capacity == 0 ? 1 : capacity) {}

CommandQueue::Status CommandQueue::Push(QueuedCommand cmd) {
	std::lock_guard<std::mutex> lock(mutex_);
	if (queue_.size() >= capacity_) {
		return Status::kResourceExhausted;
	}
	queue_.emplace_back(std::move(cmd));
	return Status::kAccepted;
}

std::vector<QueuedCommand> CommandQueue::DrainAll() {
	std::vector<QueuedCommand> out;
	std::lock_guard<std::mutex> lock(mutex_);
	out.reserve(queue_.size());
	while (!queue_.empty()) {
		out.emplace_back(std::move(queue_.front()));
		queue_.pop_front();
	}
	return out;
}

std::size_t CommandQueue::Depth() const {
	std::lock_guard<std::mutex> lock(mutex_);
	return queue_.size();
}

}  // namespace circuit::grpc
