// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — SPMC delta fan-out (T033).
//
// Engine thread publishes one serialized StateUpdate per frame.
// Each live SubscriberSlot receives a copy (by shared_ptr, so it's
// a ref-count bump, not a byte copy). Full ring → slot gets evicted
// with SlowConsumer reason; other slots unaffected (data-model §8).

#pragma once

#include "grpc/SubscriberSlot.h"

#include <cstdint>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

namespace circuit::grpc {

class Counters;

class DeltaBus {
public:
	// `counters` may be null (unit tests). When non-null, DeltaBus
	// bumps cumulative_dropped_subscribers / subscriber_count as
	// slots are evicted or added.
	explicit DeltaBus(Counters* counters = nullptr);

	// Producer side — engine thread.
	void Publish(std::shared_ptr<const std::string> payload);

	// Consumer side — called from a gRPC worker on subscribe. Returns
	// a SubscriberSlot handle; DeltaBus retains a weak reference for
	// fan-out. Slot lifetime is tied to the returned shared_ptr; the
	// worker destroys it on stream close.
	std::shared_ptr<SubscriberSlot> Subscribe();

	// Explicit unsubscribe. The worker calls this when the RPC closes
	// (client disconnect, eviction). After this returns, the slot is
	// guaranteed not to receive further TryPush calls.
	void Unsubscribe(const std::shared_ptr<SubscriberSlot>& slot);

	// Service-shutdown path. Evicts every currently-registered slot and
	// clears the registry so blocked StreamState pumps wake promptly and
	// no new publishes target torn-down subscribers.
	void EvictAll(EvictionReason reason);

	// Count of currently-live subscribers.
	std::size_t SubscriberCount() const;

private:
	Counters* counters_;
	mutable std::mutex mutex_;
	std::vector<std::weak_ptr<SubscriberSlot>> slots_;
};

}  // namespace circuit::grpc
