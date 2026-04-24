// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — engine-thread order state tracker.

#pragma once

#include "highbar/commands.pb.h"

#include <cstdint>
#include <optional>
#include <string>
#include <unordered_map>

namespace circuit::grpc {

struct OrderState {
	std::uint32_t unit_id = 0;
	std::uint64_t generation = 0;
	std::uint32_t last_command_frame = 0;
	std::uint64_t last_batch_seq = 0;
	std::uint64_t active_client_command_id = 0;
	std::string active_intent_class;
	bool busy = false;
	bool released = true;
};

struct OrderCheckResult {
	bool ok = true;
	::highbar::v1::CommandIssue issue;
};

class OrderStateTracker {
public:
	OrderCheckResult CheckAcceptedBatch(
		std::uint32_t unit_id,
		std::uint64_t batch_seq,
		std::uint64_t client_command_id,
		::highbar::v1::CommandConflictPolicy conflict_policy) const;

	void MarkAccepted(std::uint32_t unit_id,
	                  std::uint64_t batch_seq,
	                  std::uint64_t client_command_id,
	                  std::uint32_t frame,
	                  std::string intent_class);
	void MarkIdle(std::uint32_t unit_id, std::uint32_t frame);
	void MarkUnitRemoved(std::uint32_t unit_id, std::uint32_t frame);

	std::uint64_t Generation(std::uint32_t unit_id) const;
	std::optional<OrderState> Get(std::uint32_t unit_id) const;

private:
	std::unordered_map<std::uint32_t, OrderState> states_;
};

}  // namespace circuit::grpc
