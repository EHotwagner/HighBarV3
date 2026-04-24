# Contract: Command Diagnostics And Validation

## Proto Surface

`CommandAck` preserves existing aggregate fields and adds:

```proto
repeated CommandBatchResult results = 10;
```

`CommandBatch` adds:

```proto
uint64 client_command_id = 10;
uint32 based_on_frame = 11;
uint64 based_on_state_seq = 12;
UnitGeneration target_generation = 13;
CommandConflictPolicy conflict_policy = 14;
```

Supporting types:

- `CommandBatchResult`
- `CommandBatchStatus`
- `CommandIssue`
- `CommandIssueCode`
- `RetryHint`
- `UnitGeneration`
- `CommandConflictPolicy`
- `ValidationMode`

## Submission Rules

- A batch is atomic. Any validation, stale, conflict, or capacity issue rejects the entire batch.
- Strict mode requires `client_command_id`, `based_on_frame`, and `based_on_state_seq`.
- `batch_seq` must be monotonic per AI command stream.
- `commands` must contain at least one command and no more than the configured maximum.
- Each `AICommand` must set exactly one oneof arm.
- Unit-bound command-local `unit_id` must match `CommandBatch.target_unit_id`.
- Legacy pause and cheat arms on the AI command path are rejected in strict mode unless explicit compatibility flags allow them.

## Result Semantics

`CommandBatchResult.status` values:

- `COMMAND_BATCH_ACCEPTED`
- `COMMAND_BATCH_REJECTED_INVALID`
- `COMMAND_BATCH_REJECTED_QUEUE_FULL`
- `COMMAND_BATCH_REJECTED_STALE`
- `COMMAND_BATCH_REJECTED_CONFLICT`
- `COMMAND_BATCH_ACCEPTED_WITH_WARNINGS`

When a batch is rejected, `accepted_command_count` is `0`.

When warning-only mode accepts a would-reject batch, `status` is `COMMAND_BATCH_ACCEPTED_WITH_WARNINGS`, `accepted_command_count` reflects the queued commands, and `issues` contains the strict-mode diagnostics.

## Issue Requirements

Every issue includes:

- Stable `CommandIssueCode`
- `command_index` when the problem is command-specific
- Proto `field_path` when the problem is field-specific
- Human-readable `detail`
- Stable `RetryHint`

Representative issue codes:

- `EMPTY_COMMAND`
- `TOO_MANY_COMMANDS`
- `MISSING_COMMAND_INTENT`
- `MULTIPLE_COMMAND_INTENTS`
- `MISSING_TARGET_UNIT`
- `TARGET_DRIFT`
- `TARGET_UNIT_NOT_OWNED`
- `TARGET_UNIT_DEAD`
- `UNKNOWN_UNIT_DEF`
- `BUILDER_CANNOT_BUILD_DEF`
- `POSITION_NON_FINITE`
- `POSITION_OUT_OF_MAP`
- `INVALID_OPTION_BITS`
- `INVALID_ENUM_VALUE`
- `INVALID_TARGET_UNIT`
- `INVALID_TARGET_FEATURE`
- `QUEUE_FULL`
- `STALE_OR_DUPLICATE_BATCH_SEQ`
- `STALE_SNAPSHOT_EPOCH`
- `STALE_UNIT_GENERATION`
- `ORDER_CONFLICT`
- `NON_QUEUE_REPLACES_ACTIVE_ORDER`
- `COMMAND_ARM_NOT_DISPATCHED`
- `COMMAND_REQUIRES_ADMIN_CHANNEL`
- `LEGACY_AI_ADMIN_COMMAND_DISABLED`

Retry hints:

- `RETRY_NEVER`
- `RETRY_AFTER_NEXT_SNAPSHOT`
- `RETRY_AFTER_UNIT_IDLE`
- `RETRY_AFTER_QUEUE_DRAINS`
- `RETRY_WITH_FRESH_CAPABILITIES`

## RPC Behavior

`SubmitCommands`:

- In compatibility and warning-only modes, may continue streaming after invalid batches when implementation supports per-batch results.
- In strict fail-fast mode, may close with the current gRPC status behavior, but the final response path must still preserve aggregate counters for successful stream completion.
- Queue capacity is checked before enqueueing any command from a batch.

`ValidateCommandBatch`:

- Runs the same validation path as `SubmitCommands`.
- Does not enqueue, dispatch, mutate order state, or change simulation state.
- Returns a single `CommandBatchResult`.

## Acceptance Criteria Mapping

- FR-001 to FR-002: `CommandAck.results`, `CommandBatchResult`, `CommandIssue`.
- FR-003 and FR-009: strict correlation and state-basis requirements.
- FR-004: `ValidateCommandBatch`.
- FR-005 to FR-008: structured validator issue codes.
- FR-010 to FR-011: conflict policy and atomic rejection.
- FR-018 to FR-019: AI-channel admin compatibility and warning-only mode.
