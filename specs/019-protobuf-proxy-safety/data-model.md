# Data Model: Non-Python Client Protobuf And Proxy Safety

## CommandBatch

Represents one atomic client submission for a single target unit.

**Fields**: `batch_seq`, `target_unit_id`, `commands[]`, `batch_options`, `client_command_id`, `based_on_frame`, `based_on_state_seq`, `target_generation`, `conflict_policy`.

**Validation**: In strict mode, `client_command_id`, `based_on_frame`, and `based_on_state_seq` are required. `batch_seq` is monotonic per AI command stream. `commands` is non-empty and no larger than the configured maximum. All unit-bound commands must match `target_unit_id`. Any validation, stale, conflict, or capacity issue rejects the whole batch.

**Relationships**: Contains one or more `CommandIntent` values. Produces one `CommandBatchResult`. May later produce one or more `CommandDispatchEvent` records.

## CommandIntent

Represents one `AICommand` oneof arm such as build, move, attack, repair, reclaim, transport, toggle, stop, or custom command.

**Fields**: Existing command-specific proto fields, including actor unit id, options, timeout, target ids, positions, counts, enum-like numeric values, and command parameters.

**Validation**: Exactly one oneof arm must be set. Floats must be finite. Positions must be inside map extents when required. Raw enum-like values and option masks must be in known ranges. Legacy AI-channel pause/cheat arms are rejected in strict mode unless compatibility explicitly allows them.

## ValidationResult

Atomic pre-dispatch outcome for a command batch.

**Fields**: `batch_seq`, `client_command_id`, `status`, `issues[]`, `accepted_command_count`, `queued_frame`, `mode`, `would_reject`.

**Statuses**: Accepted, rejected invalid, rejected stale, rejected conflict, rejected queue full, warning-only accepted with would-reject diagnostics.

**State transitions**: `pending` -> `accepted` or `rejected_*`. In warning-only mode, `pending` -> `accepted_with_warnings`.

## CommandIssue

Machine-readable diagnostic for a validation or dispatch problem.

**Fields**: `code`, `command_index`, `field_path`, `detail`, `retry_hint`, `batch_seq`, `client_command_id`.

**Validation**: `code` and `retry_hint` are stable enums. `field_path` uses proto field names and indexes where applicable, for example `commands[0].move_unit.to_position.x`. `detail` is human-readable and must not be the only structured signal.

## CommandDispatchEvent

State delta emitted after an accepted command reaches engine-thread dispatch.

**Fields**: `batch_seq`, `client_command_id`, `command_index`, `target_unit_id`, `status`, `issue`, `frame`.

**Statuses**: Applied, skipped target missing, skipped ownership changed, skipped capability changed, skipped unsupported arm, skipped engine not ready, skipped unknown.

**Timing rule**: Dispatch-time failures are visible to clients within one state update cycle after the failed execution attempt.

## CapabilityProfile

Discoverable description of the proxy command surface and live unit capability state.

**Fields**: `schema_version`, `feature_flags[]`, `supported_command_arms[]`, `valid_option_masks`, `map_limits`, `resource_ids`, `unit_def_build_options`, `unit_queue_state`, `custom_command_inventory`, `strictness_mode`, `max_batch_commands`, `queue_depth`, `queue_capacity`.

**Relationships**: Returned by command schema and unit capability RPCs. Referenced by retry hints such as `RETRY_WITH_FRESH_CAPABILITIES`.

## OrderState

Per-unit state used to prevent accidental immediate-order replacement.

**Fields**: `unit_id`, `generation`, `last_command_frame`, `last_batch_seq`, `active_intent_class`, `active_client_command_id`, `active_command_started_frame`, `queue_depth_estimate`, `last_idle_frame`, `released`.

**State transitions**: `idle` -> `busy` when an accepted immediate order starts. `busy` -> `released` after observed `UnitIdle`, `UnitDestroyed`, `UnitGiven`, `UnitCaptured`, explicit stop/cancel, or a conservative command-class timeout. A new immediate order while `busy` is rejected unless the client explicitly requests replacement.

## AdminAction

Privileged request affecting the global run or bypassing normal gameplay constraints.

**Fields**: `action_seq`, `client_action_id`, `based_on_frame`, `based_on_state_seq`, `conflict_policy`, action oneof for pause, simulation speed, cheat policy, resource grant, unit spawn, lifecycle/test-harness controls, and reason text.

**Validation**: Requires run-scoped role credentials. Rejected when disabled by config, forbidden by run mode, stale, invalid for engine lifecycle, invalid in target/resource/speed values, or conflicting with an active single-owner lease.

## AdminResult

Structured result for admin dry-run validation or execution.

**Fields**: `action_seq`, `client_action_id`, `status`, `issues[]`, `lease`, `frame`, `state_seq`, `dry_run`.

**Statuses**: Accepted, executed, rejected permission denied, rejected disabled, rejected run mode, rejected stale, rejected conflict, rejected invalid target/value, not dispatched.

## AdminLease

Single-owner control record for conflict-prone admin controls such as pause and global speed.

**Fields**: `control`, `owner_client_id`, `owner_role`, `acquired_frame`, `last_heartbeat_frame`, `expires_frame`, `released_frame`, `release_reason`.

**State transitions**: `none` -> `held`; `held` -> `released` by explicit release; `held` -> `expired` after heartbeat loss. Conflicting actions are rejected while another owner holds the lease unless the configured policy explicitly allows takeover.

## AdminAuditEvent

Durable audit record for every accepted/rejected admin action, explicit release, and lease expiry.

**Fields**: `event_id`, `caller_identity`, `role`, `action_type`, `frame`, `state_seq`, `result`, `reason`, `lease_control`, `run_mode`.

**Validation**: Caller identity is required for caller-initiated events. Lease expiry events identify the expired owner and expiry reason.

## ValidationMode

Configuration that selects rollout behavior.

**Fields**: `mode`, `strict`, `warning_only`, `allow_legacy_ai_pause`, `allow_legacy_ai_cheats`, `reject_unsupported_arms`, `reject_order_conflicts`, `max_state_age_frames`, `max_batch_commands`.

**State transitions**: Compatibility mode allows legacy behavior with diagnostics. Warning-only mode records would-reject events without changing simulation behavior. Strict mode rejects missing correlation/state-basis and all configured validation failures.

## ConformanceFixture

Language-neutral test input and expected result.

**Fields**: `fixture_id`, `encoded_command_batch` or `admin_action`, `client_language`, `expected_status`, `expected_issue_codes[]`, `expected_retry_hints[]`, `expected_field_paths[]`, `strictness_mode`.

**Validation**: Python and at least one generated non-Python client must produce equivalent validation outcomes for shared fixtures before strict mode becomes default.
