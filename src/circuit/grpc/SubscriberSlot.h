// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — per-subscriber fan-out slot (T034, data-model §8).
//
// Each observer session owns one SubscriberSlot. The engine thread
// is the sole producer (pushes the per-frame serialized StateUpdate).
// A gRPC worker thread is the sole consumer (pops and writes to the
// stream). Bounded ring of 8192 entries. If the ring is full and the
// engine thread tries to publish, the slot's eviction_reason is set
// to SLOW_CONSUMER; the worker notices on next pop and closes the
// client stream with RESOURCE_EXHAUSTED (FR-012a class).

#pragma once

#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <deque>
#include <memory>
#include <mutex>
#include <string>

namespace circuit::grpc {

enum class EvictionReason : std::uint8_t {
	kNone,
	kSlowConsumer,
	kCanceled,
	kFault,
};

class SubscriberSlot {
public:
	static constexpr std::size_t kDefaultCapacity = 8192;

	explicit SubscriberSlot(std::size_t capacity = kDefaultCapacity);

	// Producer-side (engine thread). Returns true on successful push,
	// false if the ring was full. A false return implies the slot
	// should be evicted; the caller (DeltaBus) sets eviction_reason
	// via SetEviction.
	bool TryPush(std::shared_ptr<const std::string> payload);

	// Consumer-side (gRPC worker). Blocks until either a payload is
	// available (out-param set, returns true) or the slot is evicted
	// (returns false; EvictionReason() reads the reason).
	// Returning false means "no more payloads — close the stream."
	bool BlockingPop(std::shared_ptr<const std::string>* out);

	// Explicit eviction. Wakes the consumer. Idempotent.
	void Evict(EvictionReason reason);

	EvictionReason Eviction() const {
		return eviction_.load(std::memory_order_acquire);
	}
	std::uint64_t DroppedCount() const {
		return dropped_.load(std::memory_order_relaxed);
	}
	std::size_t QueueDepth() const;

	// Optional session tag for logs; not used internally.
	void SetSessionId(std::string s) { session_id_ = std::move(s); }
	const std::string& SessionId() const { return session_id_; }

private:
	const std::size_t capacity_;
	mutable std::mutex mutex_;
	std::condition_variable cv_;
	std::deque<std::shared_ptr<const std::string>> queue_;
	std::atomic<EvictionReason> eviction_{EvictionReason::kNone};
	std::atomic<std::uint64_t> dropped_{0};
	std::string session_id_;
};

}  // namespace circuit::grpc
