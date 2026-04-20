// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — MPSC bounded queue for AICommands awaiting the engine-
// thread drain (T055).
//
// Producers: gRPC worker threads running inside SubmitCommandsCallData.
// Consumer:  the engine thread, via CGrpcGatewayModule::OnFrameTick.
//
// Semantics (data-model §4, FR-012a):
//   - Push() returns synchronously with Status::kAccepted or
//     Status::kResourceExhausted; no blocking producers.
//   - Overflow never drops or reorders already-queued commands.
//   - Drain is consumer-only; removes all currently-queued commands
//     in FIFO order.
//   - The queue is owned by CGrpcGatewayModule; HighBarService gets a
//     non-owning pointer via SetUs2Handles (T058).

#pragma once

#include "highbar/commands.pb.h"

#include <cstdint>
#include <deque>
#include <mutex>
#include <string>
#include <vector>

namespace circuit::grpc {

struct QueuedCommand {
	std::string session_id;
	std::uint32_t target_unit_id = 0;
	::highbar::v1::AICommand command;
};

class CommandQueue {
public:
	enum class Status {
		kAccepted,
		kResourceExhausted,
	};

	// Default 1024 (tasks.md T055; research §8). Reader only grows with
	// ctor arg so tests can dial down the cap.
	explicit CommandQueue(std::size_t capacity = 1024);

	// Producer side. Thread-safe; never blocks on the consumer.
	Status Push(QueuedCommand cmd);

	// Consumer side. Engine thread only. Returns all currently-queued
	// commands in FIFO order and leaves the queue empty.
	std::vector<QueuedCommand> DrainAll();

	// Current depth. Atomic-snapshot; useful for the Counters surface.
	std::size_t Depth() const;

	std::size_t Capacity() const { return capacity_; }

private:
	const std::size_t capacity_;
	mutable std::mutex mutex_;
	std::deque<QueuedCommand> queue_;
};

}  // namespace circuit::grpc
