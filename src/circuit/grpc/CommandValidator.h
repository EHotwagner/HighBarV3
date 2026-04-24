// SPDX-License-Identifier: GPL-2.0-only
//
// HighBarV3 — server-side command validation (T056).
//
// Called from SubmitCommands on the gRPC worker thread, *before* the
// queue push. Validation is all-or-nothing per data-model §4: any
// rejection discards the whole CommandBatch without partial side
// effects. Failures map to INVALID_ARGUMENT; the string describes the
// first offending condition for client diagnostics.
//
// Threading: the validator only reads CircuitAI state (unit registry,
// unit defs, map extents). These reads race with engine-thread writes
// in principle, but the set we touch — team unit lookup by id, unit
// def constructibility, map bounds — is effectively append-only for
// the life of a match (destroyed units are marked dead, not removed).
// The engine-thread drain in T057 re-resolves the unit id before
// dispatch, so a worker seeing a stale live id still fails safely at
// the drain step if the unit died between validate and drain.

#pragma once

#include <cstdint>
#include <string>

#include "highbar/commands.pb.h"

namespace circuit {
class CCircuitAI;
}  // namespace circuit

namespace circuit::grpc {

struct CommandValidationSettings {
	::highbar::v1::ValidationMode mode =
		::highbar::v1::VALIDATION_MODE_COMPATIBILITY;
	std::uint32_t max_batch_commands = 64;
	bool require_correlation = false;
	bool require_state_basis = false;
	bool allow_legacy_ai_admin = true;
	bool reject_unsupported_arms = false;
};

struct ValidationResult {
	bool ok = false;
	std::string error;  // human-readable reason; empty when ok
	::highbar::v1::CommandBatchResult batch_result;
};

class CommandValidator {
public:
	explicit CommandValidator(
		::circuit::CCircuitAI* ai,
		CommandValidationSettings settings = CommandValidationSettings{});

	// Validate a single batch. On first failure returns {false, reason}
	// — the caller must NOT enqueue any command from this batch.
	ValidationResult ValidateBatch(const ::highbar::v1::CommandBatch& batch) const;

private:
	// Does this command bind to a specific unit? Returns true for
	// unit-bound arms and fills `unit_id`; game-wide arms return false.
	bool TryCommandUnitId(const ::highbar::v1::AICommand& cmd,
	                      std::int32_t* unit_id) const;

	// Enforce the authoritative batch-target contract for unit-bound
	// commands before the batch reaches the engine-thread queue.
	bool ValidateCommandTarget(const ::highbar::v1::AICommand& cmd,
	                           std::int32_t batch_target_unit_id,
	                           std::uint32_t command_index,
	                           ::highbar::v1::CommandIssue* issue,
	                           std::string* error) const;

	// Is `unit_id` a live unit owned by our team? Destroyed / enemy-owned
	// / never-existed → false.
	bool OwnsLiveUnit(std::int32_t unit_id) const;

	// Are (x, z) map-internal? y is vertical so we don't range-check it.
	bool InMapExtents(float x, float z) const;

	// Does our registry know a constructible def with this id?
	bool KnownBuildDef(std::int32_t def_id) const;

	// Inspect a single AICommand oneof arm. Fills `error` on failure.
	bool ValidateCommand(const ::highbar::v1::AICommand& cmd,
	                     std::uint32_t command_index,
	                     ::highbar::v1::CommandIssue* issue,
	                     std::string* error) const;

	::circuit::CCircuitAI* ai_;
	CommandValidationSettings settings_;
};

}  // namespace circuit::grpc
