# Contract: Command Capabilities And Dispatch

## Capability RPCs

Add AI-role command discovery RPCs to `HighBarProxy`:

```proto
rpc GetCommandSchema(CommandSchemaRequest) returns (CommandSchemaResponse);
rpc GetUnitCapabilities(UnitCapabilitiesRequest) returns (UnitCapabilitiesResponse);
rpc ValidateCommandBatch(CommandBatch) returns (CommandBatchResult);
```

Observers may receive schema-level read-only capability data if authorized by the existing state-read policy, but unit/action legality for command submission requires AI credentials.

## Command Schema Response

`CommandSchemaResponse` includes:

- `schema_version`
- `feature_flags`
- supported `AICommand` oneof arms
- valid option masks per command arm
- strictness mode and configured limits
- map extents
- resource identifiers
- known enum-like ranges for v1 raw integer fields
- queue capacity and current depth when visible to the caller

## Unit Capabilities Response

`UnitCapabilitiesResponse` includes:

- target `unit_id` and optional `generation`
- unit definition id and canonical name when available
- legal command arms for that unit
- build options for builders/factories
- custom command inventory with parameter count/range metadata
- current queue/busy state
- current order conflict state
- feature flags affecting validation

## Dispatch Event

Add `CommandDispatchEvent` to state deltas:

```proto
message CommandDispatchEvent {
  uint64 batch_seq = 1;
  uint64 client_command_id = 2;
  uint32 command_index = 3;
  uint32 target_unit_id = 4;
  CommandDispatchStatus status = 5;
  CommandIssue issue = 6;
  uint32 frame = 7;
}
```

`CommandDispatchStatus` values:

- `COMMAND_DISPATCH_APPLIED`
- `COMMAND_DISPATCH_SKIPPED_TARGET_MISSING`
- `COMMAND_DISPATCH_SKIPPED_TARGET_NOT_OWNED`
- `COMMAND_DISPATCH_SKIPPED_TARGET_DEAD`
- `COMMAND_DISPATCH_SKIPPED_CAPABILITY_CHANGED`
- `COMMAND_DISPATCH_SKIPPED_UNSUPPORTED_ARM`
- `COMMAND_DISPATCH_SKIPPED_ENGINE_NOT_READY`
- `COMMAND_DISPATCH_SKIPPED_UNKNOWN`

## Engine-Thread Rules

- Dispatch rechecks target existence, ownership, live state, command support, target existence, and builder/capability legality before calling engine APIs.
- Any failed recheck emits `CommandDispatchEvent` with an issue.
- Per-unit order tracker mutation occurs only on the engine thread.
- Worker threads never call `CCircuitUnit::Cmd*` or mutate CircuitAI state.

## Order Conflict Rules

- Immediate build or other long-running intent marks the unit busy.
- A later immediate order for the same unit is rejected when the unit remains busy unless `conflict_policy == REPLACE_CURRENT`.
- Safe completion means the proxy observed unit idle or release in a later state update.
- Queued command chains are accepted only when option bits and `conflict_policy` both express queue-after-current intent.

## Acceptance Criteria Mapping

- FR-010: order tracker and conflict policy.
- FR-012 and SC-004: dispatch events.
- FR-013: command schema and unit capabilities.
- SC-001 to SC-003: capability-backed validator fixtures.
