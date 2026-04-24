// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — engine-thread order state tracker.

#include "grpc/OrderStateTracker.h"

#include <utility>

namespace circuit::grpc {

namespace {

void FillIssue(::highbar::v1::CommandIssueCode code,
               std::uint64_t batch_seq,
               std::uint64_t client_command_id,
               const char* field_path,
               const char* detail,
               ::highbar::v1::RetryHint retry_hint,
               ::highbar::v1::CommandIssue* issue) {
	issue->set_code(code);
	issue->set_batch_seq(batch_seq);
	issue->set_client_command_id(client_command_id);
	issue->set_field_path(field_path);
	issue->set_detail(detail);
	issue->set_retry_hint(retry_hint);
}

}  // namespace

OrderCheckResult OrderStateTracker::CheckAcceptedBatch(
		std::uint32_t unit_id,
		std::uint64_t batch_seq,
		std::uint64_t client_command_id,
		::highbar::v1::CommandConflictPolicy conflict_policy) const {
	OrderCheckResult result;
	const auto it = states_.find(unit_id);
	if (it == states_.end()) return result;

	const OrderState& state = it->second;
	if (batch_seq <= state.last_batch_seq) {
		result.ok = false;
		FillIssue(::highbar::v1::STALE_OR_DUPLICATE_BATCH_SEQ,
		          batch_seq, client_command_id, "batch_seq",
		          "batch_seq must increase per unit",
		          ::highbar::v1::RETRY_AFTER_NEXT_SNAPSHOT,
		          &result.issue);
		return result;
	}
	if (state.busy
	    && conflict_policy != ::highbar::v1::COMMAND_CONFLICT_REPLACE_CURRENT
	    && conflict_policy != ::highbar::v1::COMMAND_CONFLICT_QUEUE_AFTER_CURRENT) {
		result.ok = false;
		FillIssue(::highbar::v1::ORDER_CONFLICT,
		          batch_seq, client_command_id, "conflict_policy",
		          "unit has an active order",
		          ::highbar::v1::RETRY_AFTER_UNIT_IDLE,
		          &result.issue);
	}
	return result;
}

void OrderStateTracker::MarkAccepted(std::uint32_t unit_id,
                                     std::uint64_t batch_seq,
                                     std::uint64_t client_command_id,
                                     std::uint32_t frame,
                                     std::string intent_class) {
	auto& state = states_[unit_id];
	state.unit_id = unit_id;
	state.last_batch_seq = batch_seq;
	state.active_client_command_id = client_command_id;
	state.last_command_frame = frame;
	state.active_intent_class = std::move(intent_class);
	state.busy = true;
	state.released = false;
	if (state.generation == 0) state.generation = 1;
}

void OrderStateTracker::MarkIdle(std::uint32_t unit_id, std::uint32_t frame) {
	auto& state = states_[unit_id];
	state.unit_id = unit_id;
	state.last_command_frame = frame;
	state.busy = false;
	state.released = true;
	if (state.generation == 0) state.generation = 1;
}

void OrderStateTracker::MarkUnitRemoved(std::uint32_t unit_id,
                                        std::uint32_t frame) {
	auto& state = states_[unit_id];
	state.unit_id = unit_id;
	state.last_command_frame = frame;
	state.busy = false;
	state.released = true;
	++state.generation;
}

std::uint64_t OrderStateTracker::Generation(std::uint32_t unit_id) const {
	const auto it = states_.find(unit_id);
	return it == states_.end() ? 0 : it->second.generation;
}

std::optional<OrderState> OrderStateTracker::Get(std::uint32_t unit_id) const {
	const auto it = states_.find(unit_id);
	if (it == states_.end()) return std::nullopt;
	return it->second;
}

}  // namespace circuit::grpc
