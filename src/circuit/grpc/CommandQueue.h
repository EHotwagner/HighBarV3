// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — MPSC bounded command queue (T055).
//
// Multiple gRPC worker threads push accepted AICommands here; the
// engine thread drains the queue at the top of every frame tick
// (T057). Overflow returns synchronously so the wire side can reply
// RESOURCE_EXHAUSTED without ever dropping or reordering commands
// already in the queue (FR-012a, data-model §4).

#pragma once

#include "highbar/commands.pb.h"

#include <cstdint>
#include <mutex>
#include <queue>
#include <string>
#include <vector>

namespace circuit::grpc {

class Counters;

// Single entry: the command to dispatch plus the originating session
// for logging / per-session accounting. Commands are shallow-copied
// onto the queue so the caller's batch message can be freed once
// Push returns.
struct QueuedCommand {
	std::string session_id;
	::highbar::v1::AICommand command;
};

class CommandQueue {
public:
	// `counters` may be null for unit tests. `capacity` is the bounded
	// depth; defaults to 1024 per tasks.md T055.
	explicit CommandQueue(Counters* counters = nullptr,
	                      std::size_t capacity = 1024);

	// Attempt to enqueue. Returns true on success. On failure the queue
	// is already at capacity — the caller must report RESOURCE_EXHAUSTED
	// to the client without mutating state. Already-queued commands are
	// never dropped or reordered.
	bool TryPush(QueuedCommand cmd);

	// Engine-thread drain. Moves up to `max` entries into `out` and
	// returns the number actually moved. Called from OnFrameTick at the
	// top of every frame so throughput is bounded by engine frame rate.
	// Pass 0 to drain everything.
	std::size_t Drain(std::vector<QueuedCommand>* out,
	                  std::size_t max = 0);

	// Current depth. Cheap but approximate under concurrent access —
	// reflected into Counters::command_queue_depth atomically on every
	// push / drain.
	std::size_t Depth() const;

	std::size_t Capacity() const { return capacity_; }

private:
	Counters* counters_;
	const std::size_t capacity_;
	mutable std::mutex mutex_;
	std::queue<QueuedCommand> queue_;
};

}  // namespace circuit::grpc
