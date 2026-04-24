# Non-Python Client Protobuf And Proxy Safety Design

Date: 2026-04-24

## Summary

Putting more structure in protobufs and more validation in the HighBar proxy is high leverage before adding non-Python clients. The Python client currently hides many sharp edges behind helpers and plugin-local conventions. Rust, Go, C#, F#, C++, or TypeScript clients will not inherit those safeguards unless the wire contract and proxy enforce them.

The goal should be:

1. Make invalid inputs hard to express in generated clients.
2. Reject malformed or unsafe batches before they reach the engine thread.
3. Return machine-readable diagnostics so non-Python clients can fix themselves.
4. Catch timing/order mistakes that are deterministic from the proxy's view.
5. Leave strategy policy in clients, while enforcing engine invariants in the proxy.

This will not make every bad AI impossible. It will make most integration bugs fail early with a useful reason instead of becoming silent in-game command churn.

## Current State

The current wire model has a good foundation:

- `AICommand` is a typed `oneof` over command arms.
- `CommandBatch` groups `1..N` commands for one `target_unit_id`.
- `SubmitCommands` is AI-role-only and protected by the session token.
- The proxy has `CommandValidator` that already catches:
  - empty `AICommand`
  - unit id drift between `CommandBatch.target_unit_id` and command-local `unit_id`
  - non-finite positions
  - positions outside map extents
  - unknown build def ids
  - `target_unit_id` not owned/live
- The command queue is bounded and reports `RESOURCE_EXHAUSTED`.
- A second AI command stream fails with `ALREADY_EXISTS`.

The largest gaps for non-Python clients are:

- `CommandAck` only has aggregate counters; it does not say which batch or field failed.
- Many fields are still raw integers or bitmasks.
- Build validation checks that a def id is known, but not yet that this builder can build that def.
- Timing/order mistakes are mostly left to client policy.
- Capabilities are discoverable only through callbacks and client conventions, not a single contract surface.
- Proto comments describe rules, but generated clients do not enforce comments.
- Privileged simulation controls such as pause, cheat resource/unit grants, and global game speed are mixed with or adjacent to normal AI command concepts. They need a separate authorization surface before broader client support.

## Design Principles

### Keep Protobuf As The Contract

Every language should be able to generate a client from `proto/highbar/*.proto` and understand the legal command surface without reading Python code.

### Make The Proxy Authoritative For Safety

Clients may be buggy or stale. The proxy should reject inputs that are structurally invalid, unsafe, not owned, not currently legal, or impossible for the target unit.

### Prefer Structured Errors Over Text

Human strings are useful in logs, but clients need stable enums, field paths, batch ids, command indexes, and retry hints.

### Separate Validation From Policy

The proxy should catch objective errors:

- unit is not owned
- command is stale
- options are invalid
- build target is impossible for builder
- command replaces an in-flight non-queued build too soon

The proxy should not decide whether a strategy is smart:

- whether an army mix is good
- whether a build order is optimal
- whether a scout should explore

### Make Safety Incremental

Do additive v1 improvements first. Save command-shape cleanup for `highbar.v2`.

### Separate AI Intent From Admin Control

Normal AI clients should express unit-level game intent: build, move, attack, repair, reclaim, toggle, and similar orders. They should not automatically gain authority to pause the simulation, enable cheats, create units, grant resources, or change global simulation speed.

Those controls are useful for testing, benchmarking, headless orchestration, and viewer tooling, but they affect the whole match and every connected client. They should live behind a separate gRPC admin/control channel with its own role, token scope, validation policy, audit log, and lifecycle checks.

## Proposed Architecture

```text
non-Python AI
  |
  | generated proto client
  v
HighBarProxy.SubmitCommands
  |
  | auth + AI stream ownership
  v
CommandValidator
  |
  | stateless validation
  | stateful validation
  | ordering/timing validation
  v
CommandQueue
  |
  | engine-thread drain
  v
CommandDispatch
  |
  | dispatch result + post-dispatch observation
  v
StateDelta / CommandAck / diagnostics
```

Privileged controls should use a sibling service:

```text
operator / test harness / viewer bridge
  |
  | generated proto client with admin credentials
  v
HighBarAdmin.ControlService
  |
  | admin auth + capability policy + lifecycle checks
  v
AdminControlValidator
  |
  | pause/cheat/speed validation
  | mode guards
  | controller ownership checks
  v
Engine-thread admin action queue
  |
  v
AdminControlResult / audit event / state delta
```

This keeps the public AI command stream deterministic and strategy-focused while still allowing robust non-Python tooling to control test runs.

## Admin Control Channel

### Scope

The admin/control service should contain actions that affect the simulation globally or bypass normal gameplay constraints:

- pause and unpause
- global simulation speed controls, such as `setspeed`, `setminspeed`, and `setmaxspeed`
- cheat resource grants
- cheat unit creation
- explicit cheat enable/disable if the engine requires it
- benchmark or headless run controls that change lifecycle state
- future test-harness actions such as restart, resign, force team defeat, or scenario triggers

Unit-level speed limits are different. `set_wanted_max_speed` is a per-unit order and belongs in the normal AI command API. Global game speed belongs in the admin service.

### Proposed Service Shape

```proto
service HighBarAdmin {
  rpc GetAdminCapabilities(AdminCapabilitiesRequest) returns (AdminCapabilitiesResponse);
  rpc ValidateAdminAction(AdminAction) returns (AdminActionResult);
  rpc ExecuteAdminAction(AdminAction) returns (AdminActionResult);
}

message AdminAction {
  uint64 action_seq = 1;
  string client_action_id = 2;
  uint32 based_on_frame = 3;
  uint64 based_on_state_seq = 4;
  AdminConflictPolicy conflict_policy = 5;

  oneof action {
    SetPaused set_paused = 10;
    SetSimulationSpeed set_simulation_speed = 11;
    SetCheatPolicy set_cheat_policy = 12;
    GiveResource give_resource = 20;
    SpawnUnit spawn_unit = 21;
  }
}

message SetPaused {
  bool paused = 1;
  string reason = 2;
}

message SetSimulationSpeed {
  optional float speed = 1;
  optional float min_speed = 2;
  optional float max_speed = 3;
  string reason = 4;
}

message SetCheatPolicy {
  CheatPolicy policy = 1;
  string reason = 2;
}

message GiveResource {
  ResourceId resource = 1;
  float amount = 2;
  uint32 team_id = 3;
}

message SpawnUnit {
  uint32 unit_def_id = 1;
  Vector3 position = 2;
  uint32 team_id = 3;
}

enum CheatPolicy {
  CHEAT_POLICY_UNSPECIFIED = 0;
  CHEAT_POLICY_REJECT = 1;
  CHEAT_POLICY_REQUIRE_ALREADY_ENABLED = 2;
  CHEAT_POLICY_TEMP_ENABLE_FOR_ACTION = 3;
}

enum AdminConflictPolicy {
  ADMIN_CONFLICT_POLICY_UNSPECIFIED = 0;
  ADMIN_REJECT_IF_CONTROLLED = 1;
  ADMIN_TAKE_CONTROL = 2;
  ADMIN_ALLOW_SHARED = 3;
}
```

The existing `pause_team`, `give_me`, and `give_me_new_unit` command arms can remain for backward compatibility during a transition, but strict mode should reject them on the normal AI command channel unless explicitly allowed for legacy tests. New non-Python clients should use the admin service for these actions.

### Admin Authorization

Admin access should be separate from AI access:

- AI role can call `SubmitCommands`, `ValidateCommandBatch`, and read normal state.
- Observer role can read state but cannot mutate.
- Admin/operator role can pause, change speed, and run test controls.
- Test-harness role can use cheats only when the run mode allows cheats.

Recommended config:

```json
{
  "admin_control": {
    "enabled": true,
    "allow_pause": true,
    "allow_speed_control": true,
    "allow_cheats": false,
    "allow_legacy_ai_pause": false,
    "allow_legacy_ai_cheats": false,
    "controller_lease_frames": 300,
    "audit_all_actions": true
  }
}
```

Every admin action should produce an audit event with client id, role, action type, frame, result, and reason. This is valuable in BNV/headless reports because run-changing actions otherwise look like unexplained engine behavior.

### Admin Validation

The proxy should reject admin actions before they reach the engine when:

- the caller lacks the required role or token scope
- the action is disabled by config or run mode
- cheats are requested in a natural/non-cheat verification run
- the action is stale relative to `based_on_frame` / `based_on_state_seq`
- another admin controller currently owns pause or speed control and the conflict policy does not allow takeover
- speed values are non-finite, negative, or outside configured bounds
- min speed is greater than max speed
- resource amounts are non-finite, non-positive, or above configured test limits
- resource ids are unknown
- unit def ids are unknown
- spawn positions are non-finite or outside map bounds
- the target team id is invalid or not allowed for this admin role
- the engine is loading, shutting down, or not yet ready for that action

Admin result codes should be separate from unit command issue codes where useful:

- `ADMIN_PERMISSION_DENIED`
- `ADMIN_ACTION_DISABLED`
- `ADMIN_RUN_MODE_FORBIDS_CHEATS`
- `ADMIN_STALE_SNAPSHOT_EPOCH`
- `ADMIN_CONTROL_CONFLICT`
- `ADMIN_INVALID_SPEED`
- `ADMIN_INVALID_SPEED_RANGE`
- `ADMIN_INVALID_RESOURCE`
- `ADMIN_INVALID_AMOUNT`
- `ADMIN_UNKNOWN_UNIT_DEF`
- `ADMIN_POSITION_OUT_OF_MAP`
- `ADMIN_INVALID_TEAM`
- `ADMIN_ENGINE_NOT_READY`
- `ADMIN_ACTION_NOT_DISPATCHED`

The admin service should support `ValidateAdminAction` as a dry-run mirror of `ExecuteAdminAction`, just like `ValidateCommandBatch`.

## Protobuf Improvements

### Add Structured Diagnostics To `CommandAck`

Add fields without removing current counters:

```proto
message CommandAck {
  uint64 last_accepted_batch_seq = 1;
  uint64 batches_accepted = 2;
  uint64 batches_rejected_invalid = 3;
  uint64 batches_rejected_full = 4;

  repeated CommandBatchResult results = 10;
}

message CommandBatchResult {
  uint64 batch_seq = 1;
  CommandBatchStatus status = 2;
  repeated CommandIssue issues = 3;
  uint32 accepted_command_count = 4;
  uint32 queued_frame = 5;
}

enum CommandBatchStatus {
  COMMAND_BATCH_STATUS_UNSPECIFIED = 0;
  COMMAND_BATCH_ACCEPTED = 1;
  COMMAND_BATCH_REJECTED_INVALID = 2;
  COMMAND_BATCH_REJECTED_QUEUE_FULL = 3;
  COMMAND_BATCH_REJECTED_STALE = 4;
  COMMAND_BATCH_REJECTED_CONFLICT = 5;
  COMMAND_BATCH_PARTIALLY_QUEUED_BEFORE_QUEUE_FULL = 6;
}

message CommandIssue {
  CommandIssueCode code = 1;
  uint32 command_index = 2;
  string field_path = 3;
  string detail = 4;
  RetryHint retry_hint = 5;
}

enum RetryHint {
  RETRY_HINT_UNSPECIFIED = 0;
  RETRY_NEVER = 1;
  RETRY_AFTER_NEXT_SNAPSHOT = 2;
  RETRY_AFTER_UNIT_IDLE = 3;
  RETRY_AFTER_QUEUE_DRAINS = 4;
  RETRY_WITH_FRESH_CAPABILITIES = 5;
}
```

Example `CommandIssueCode` values:

- `EMPTY_COMMAND`
- `MISSING_TARGET_UNIT`
- `TARGET_UNIT_NOT_OWNED`
- `TARGET_UNIT_DEAD`
- `TARGET_DRIFT`
- `UNKNOWN_UNIT_DEF`
- `BUILDER_CANNOT_BUILD_DEF`
- `POSITION_NON_FINITE`
- `POSITION_OUT_OF_MAP`
- `INVALID_OPTION_BITS`
- `INVALID_ENUM_VALUE`
- `INVALID_TARGET_UNIT`
- `INVALID_TARGET_FEATURE`
- `QUEUE_FULL`
- `STALE_SNAPSHOT_EPOCH`
- `STALE_UNIT_GENERATION`
- `ORDER_CONFLICT`
- `NON_QUEUE_REPLACES_ACTIVE_ORDER`
- `COMMAND_ARM_NOT_DISPATCHED`
- `COMMAND_REQUIRES_ADMIN_CHANNEL`
- `LEGACY_AI_ADMIN_COMMAND_DISABLED`

### Add Client Correlation Fields

Generated clients need stable correlation across logs, acks, and state deltas:

```proto
message CommandBatch {
  uint64 batch_seq = 1;
  uint32 target_unit_id = 2;
  repeated AICommand commands = 3;
  optional CommandOptions batch_options = 4;

  uint64 client_command_id = 10;
  uint32 based_on_frame = 11;
  uint64 based_on_state_seq = 12;
  UnitGeneration target_generation = 13;
  CommandConflictPolicy conflict_policy = 14;
}

message UnitGeneration {
  uint32 unit_id = 1;
  uint32 generation = 2;
}

enum CommandConflictPolicy {
  COMMAND_CONFLICT_POLICY_UNSPECIFIED = 0;
  REPLACE_CURRENT = 1;
  QUEUE_AFTER_CURRENT = 2;
  REJECT_IF_BUSY = 3;
  REJECT_IF_DIFFERENT_INTENT = 4;
}
```

`based_on_frame` and `based_on_state_seq` let the proxy catch clients acting on old world state. `target_generation` protects against id reuse if the engine ever reuses unit ids. `conflict_policy` makes replacement explicit instead of accidentally replacing active orders.

### Replace Raw Integers With Enums Where Possible

Keep v1 numeric fields for compatibility, but add v2 typed fields later.

Candidates:

- `MoveState`
- `FireState`
- `Trajectory`
- `IdleMode`
- `ResourceId`
- `Facing`
- `PathType`
- `MessageZone`
- `CommandOptions` bit enum
- `CallbackId`

For v1, add validation of numeric ranges and invalid option masks. For v2, model these as enums.

### Add Capability RPCs

Non-Python clients should not have to learn capabilities piecemeal through callbacks.

```proto
rpc GetCommandSchema(CommandSchemaRequest) returns (CommandSchemaResponse);
rpc GetUnitCapabilities(UnitCapabilitiesRequest) returns (UnitCapabilitiesResponse);
rpc ValidateCommandBatch(CommandBatch) returns (CommandBatchResult);
```

Useful payloads:

- unit def id to canonical unit name
- unit def build options
- unit command queue state
- supported command arms for this proxy build
- valid option bits per command arm
- map extents
- resource ids
- custom command inventory
- current schema version and feature flags

`ValidateCommandBatch` should run the same validation path as `SubmitCommands` but not enqueue.

Admin capabilities should be discoverable separately through `HighBarAdmin.GetAdminCapabilities`. This prevents normal AI clients from inferring that privileged actions are part of their command contract just because the proxy binary knows how to dispatch them.

### Add Dispatch Results To State Deltas

`CommandAck` confirms enqueue, not actual engine dispatch. Non-Python clients need to know whether accepted commands were later skipped during engine-thread dispatch.

Add a delta event:

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

This closes the gap between "accepted by SubmitCommands" and "actually applied to engine."

## Proxy Validation Improvements

### Stateless Validation

These checks require only the proto payload:

- exactly one `AICommand.command` arm is set
- `CommandBatch.commands` is non-empty and under max batch length
- `batch_seq > 0`
- `target_unit_id > 0` for unit-bound batches
- command-local `unit_id` matches `CommandBatch.target_unit_id`
- all floats are finite
- all radii, timeouts, group ids, counts, and ids are in legal ranges
- strings are length-limited and valid UTF-8
- option bitmask contains only known bits
- enum-like int fields are in legal ranges
- command arms unsupported by the compiled proxy are rejected instead of silently skipped
- command arms that belong to the admin channel are rejected on `SubmitCommands` unless legacy compatibility explicitly allows them

### Runtime Validation

These checks require live proxy/engine state:

- target unit exists, is owned by this AI, and is not dead
- target enemy/unit/feature exists when required
- target unit is visible/known when the command requires visibility
- build def exists
- builder can build target def
- build target is not blocked by map extents or obvious placement invalidity
- transport commands target a compatible transport/cargo type
- stockpile/on-off/repeat commands target a unit that supports them
- repair/capture/reclaim target is valid for the command
- custom command id exists for that unit and has valid parameter count/range
- legacy pause/cheat command arms are allowed only when AI-channel admin compatibility is enabled for the current run mode

### Dispatch-Time Validation

Some facts can change after the gRPC worker validates and before the engine thread drains the queue. The engine-thread drain must re-check:

- unit still exists and is owned
- unit is not dead/captured/given away
- command still applies to this unit def
- build options still allow the target
- target still exists if required
- command arm is wired to dispatch

If this fails, emit `CommandDispatchEvent` with structured reason.

## Timing And Order Errors The Proxy Can Catch

Yes, timing/order errors can be caught by the proxy. This is especially useful because they are common in real AI clients and hard to debug from client code alone.

### Catchable Now Or With Small Additions

| Error | Example | Proxy signal | Action |
|---|---|---|---|
| Non-monotonic `batch_seq` | client sends seq 42 then 41 | AI stream session state | reject with `STALE_OR_DUPLICATE_BATCH_SEQ` |
| Duplicate `batch_seq` | retry accidentally resubmits accepted batch | AI stream session state | idempotently ack same result or reject duplicate |
| Too-old world basis | command based on frame 100 when proxy is at 3000 | `based_on_frame` / `based_on_state_seq` | reject with `STALE_SNAPSHOT_EPOCH` |
| Queue flooding | client submits faster than engine drains | queue depth | `RESOURCE_EXHAUSTED`, retry after queue drains |
| Replacing active build unintentionally | commander receives immediate build every 30 frames | per-unit in-flight order tracker | reject with `NON_QUEUE_REPLACES_ACTIVE_ORDER` |
| Conflicting immediate orders in one batch | `build` then `move` with no queue option | command order validator | reject or require explicit `REPLACE_CURRENT` |
| Multiple non-queued batches for same unit in same frame | two clients or one client sends two immediate builds | per-frame target tracker | reject second as `ORDER_CONFLICT` |
| Queue flag missing | client intended queued build chain but omitted SHIFT | conflict policy + option bits | reject if `QUEUE_AFTER_CURRENT` without queue bit |
| Command targets stale unit | unit died between snapshot and submit | live unit registry | reject at submit or dispatch |
| Command targets reused unit id | old unit id now refers to a different unit | `UnitGeneration` | reject generation mismatch |
| Submit before Hello/session ready | client opens stream without role/session | service state/auth | `FAILED_PRECONDITION` or `PERMISSION_DENIED` |
| Second AI writer | two AI clients submit commands | AI slot | `ALREADY_EXISTS` |
| Save/load race | command submitted while load is in progress | lifecycle state | `FAILED_PRECONDITION` |
| Callback during shutdown | client calls callback after proxy closing | gateway lifecycle | `UNAVAILABLE` |
| Pause from normal AI channel | strategy client submits `pause_team` | admin-channel policy | reject with `COMMAND_REQUIRES_ADMIN_CHANNEL` |
| Cheat from normal AI channel | strategy client submits `give_me_new_unit` | admin-channel policy | reject with `COMMAND_REQUIRES_ADMIN_CHANNEL` |
| Cheat during natural verification | test client requests unit/resource grant | run mode | reject with `ADMIN_RUN_MODE_FORBIDS_CHEATS` |
| Speed change during benchmark | viewer changes global speed mid-run | admin lifecycle policy | reject or mark run non-comparable |
| Pause never resumed | admin pauses and disconnects | controller lease + watchdog | auto-release or fail run with audit event |
| Two controllers fight over speed | viewer and harness both set speed | admin controller lease | reject with `ADMIN_CONTROL_CONFLICT` |

### The Turtle1 Bug Class

The commander build churn is a perfect example:

- The client repeatedly sent immediate `build_unit` commands to the same commander.
- The engine interpreted each immediate build as replacing the current order.
- From the client's perspective each command looked valid.
- From the proxy's perspective the pattern is objectively suspicious:
  - same `target_unit_id`
  - same command class
  - immediate/non-queued options
  - recent prior build order has not produced idle or completion evidence

The proxy can catch this generically with a per-unit in-flight order tracker:

```text
on accepted immediate build:
  mark target_unit_id busy with intent class BUILD

on later immediate build for same target:
  if no UnitIdle / explicit cancel / timeout / completed order:
    reject unless conflict_policy == REPLACE_CURRENT

on queued build:
  allow if queue bit is set and batch policy says QUEUE_AFTER_CURRENT
```

This does not require the proxy to understand turtle1. It enforces a general safety rule: accidental immediate replacement must be explicit.

### Timing Errors That Are Harder To Catch

Some timing issues are only partially catchable:

- A unit is moving and will be out of range by dispatch time.
- A target visible at submit time disappears before dispatch.
- A build placement is technically legal at submit time but blocked by a moving unit at execution.
- The client issues a strategically bad sequence that is still legal.

For these, the proxy can still help by emitting dispatch events and state deltas, but should not pretend validation is deterministic.

## Stateful Proxy Order Tracker

Add a small engine-thread-owned order tracker. The gRPC worker may perform preliminary checks, but authoritative mutation should happen on the engine thread or under a narrow lock.

State per unit:

```text
unit_id
generation
last_command_frame
last_batch_seq
active_intent_class
active_client_command_id
active_command_started_frame
queue_depth_estimate
last_idle_frame
```

Intent classes:

- `BUILD`
- `MOVE`
- `ATTACK`
- `REPAIR`
- `RECLAIM`
- `CAPTURE`
- `LOAD_TRANSPORT`
- `UNLOAD_TRANSPORT`
- `TOGGLE`
- `STOP`
- `UNKNOWN_CUSTOM`

Release signals:

- `UnitIdle`
- `CommandFinished` for command classes where engine semantics are known safe
- `UnitDestroyed`
- `UnitGiven`
- `UnitCaptured`
- `Stop`
- explicit `REPLACE_CURRENT`
- timeout based on command class

Important: do not treat all `CommandFinished` events as "builder is free." Some engines emit command-finished-like signals for acceptance, sub-command completion, or queue transitions. Build release should prefer `UnitIdle` or a conservative timeout unless a command id is known to mean final completion.

## Compatibility Plan

### Phase 1: v1 Additive Diagnostics

No command-shape breakage.

- Add `CommandBatchResult` and `CommandIssue` fields to `CommandAck`.
- Add issue enums and retry hints.
- Add stricter validator checks for:
  - empty command list
  - max command count
  - invalid option bits
  - enum-like ranges
  - unsupported command arms
  - build option constructibility
- Add `ValidateCommandBatch` dry-run RPC if schema-version policy allows a minor bump.
- Add tests that assert exact issue codes.

### Phase 2: v1 Stateful Safety

- Track per-stream `batch_seq`.
- Track per-unit in-flight immediate orders.
- Reject accidental immediate replacement unless `conflict_policy` or batch options explicitly allow it.
- Emit dispatch result deltas.
- Expose current queue depth and per-unit busy status through capabilities.

### Phase 2B: Admin Control Service

- Add `HighBarAdmin` as a separate gRPC service.
- Add `AdminAction`, `AdminActionResult`, admin issue codes, and admin capability discovery.
- Move new pause, global speed, and cheat controls to the admin service.
- Keep legacy AI-channel pause/cheat command arms only behind explicit compatibility flags.
- Add admin controller leases so viewer, harness, and operator tools do not fight over pause or speed.
- Audit every accepted and rejected admin action into reports.

### Phase 3: v2 Clean Command API

Create `highbar.v2` with stronger shapes:

- typed enums instead of raw ints
- explicit `UnitRef` and `UnitGeneration`
- command-specific options instead of one generic bitmask
- one `CommandTarget` model for units/features/positions
- result-bearing `SubmitCommands` that can acknowledge every batch without relying on stream EOF
- optional bidirectional command stream:
  - client sends commands
  - server streams acks/dispatch events as they happen

## Recommended Proto Direction For v2

The current V2-ported command catalog is broad but mechanically shaped around old engine wrappers. For non-Python clients, a cleaner API would be easier:

```proto
message UnitOrder {
  UnitRef actor = 1;
  CommandIntent intent = 2;
  CommandOptions options = 3;
  CommandConflictPolicy conflict_policy = 4;
}

message CommandIntent {
  oneof kind {
    BuildIntent build = 1;
    MoveIntent move = 2;
    AttackIntent attack = 3;
    RepairIntent repair = 4;
    ReclaimIntent reclaim = 5;
    GuardIntent guard = 6;
    StopIntent stop = 7;
    ToggleIntent toggle = 8;
    CustomIntent custom = 100;
  }
}
```

This is less faithful to the raw engine API, but much safer for generated clients. Keep an escape hatch for raw/custom commands, but make typed intents the default.

## Test Strategy

### Proto Conformance Tests

For every supported language:

- serialize canonical command fixtures
- compare bytes or JSON representation
- run fixtures through `ValidateCommandBatch`
- assert identical issue codes

### Proxy Unit Tests

Add validator tests for:

- invalid option bits
- target drift
- missing command arm
- unsupported command arm
- non-monotonic batch seq
- stale frame/seq
- duplicate batch seq
- non-queued replacement of active build
- queue-after-current without queue option
- builder cannot build def
- target unit dead between validate and drain

### Headless Tests

Add live tests for:

- accepted build emits dispatch event
- repeated immediate build is rejected unless `REPLACE_CURRENT`
- queued build chain is accepted with queue option
- stale `based_on_state_seq` is rejected
- duplicate batch retry is idempotent or rejected consistently
- second AI writer remains `ALREADY_EXISTS`

## Operational Concerns

### Strictness Modes

Add config:

```json
{
  "command_validation": {
    "strict": true,
    "reject_unsupported_arms": true,
    "reject_order_conflicts": true,
    "max_state_age_frames": 300
  },
  "admin_control": {
    "enabled": true,
    "allow_pause": true,
    "allow_speed_control": true,
    "allow_cheats": false,
    "allow_legacy_ai_pause": false,
    "allow_legacy_ai_cheats": false,
    "controller_lease_frames": 300,
    "audit_all_actions": true
  }
}
```

Default should become strict for non-test runs once clients are updated.

Cheats should default to disabled outside explicit test harness modes. Global speed control can be allowed in headless tests, but benchmark reports should record every speed change or mark the run as non-comparable.

### Rollout Safety

Start by logging would-reject events without rejecting:

```text
[hb-validator] would_reject code=NON_QUEUE_REPLACES_ACTIVE_ORDER batch_seq=17 target=25947
```

Then flip to rejection after live reports are clean.

### Backward Compatibility

Current Python helpers can continue to work:

- if `conflict_policy` unset, infer old behavior initially
- warn when immediate replacement would be rejected in strict mode
- update Python helpers to set explicit policies

## Implementation Checklist

1. Add `CommandIssueCode`, `RetryHint`, `CommandIssue`, and `CommandBatchResult`.
2. Extend `CommandAck` with repeated results.
3. Preserve current aggregate counters.
4. Add exact validator issue codes instead of only strings.
5. Add invalid option and enum-range checks.
6. Add command-list size checks.
7. Add unsupported-arm rejection option.
8. Add build-option constructibility check per builder.
9. Add per-stream batch sequence tracker.
10. Add optional `based_on_frame` / `based_on_state_seq` stale-state checks.
11. Add per-unit in-flight order tracker.
12. Add `CommandDispatchEvent` deltas.
13. Add `ValidateCommandBatch` dry-run RPC.
14. Add capability RPCs.
15. Add `HighBarAdmin` gRPC service for pause, cheats, global speed, and future lifecycle controls.
16. Add admin role/token scopes independent from the AI command role.
17. Add `ValidateAdminAction` and structured `AdminActionResult` diagnostics.
18. Add proxy checks for admin action enablement, run mode, stale state, controller ownership, speed ranges, resource ids, unit defs, positions, and team ids.
19. Add audit events for accepted and rejected admin actions.
20. Gate legacy AI-channel pause/cheat arms with compatibility flags and return `COMMAND_REQUIRES_ADMIN_CHANNEL` when disabled.
21. Add conformance fixtures for Python plus one non-Python client first.

## Answer To "How Useful Would This Be?"

Very useful. It moves correctness from client-specific helper code into the shared contract. The result is:

- fewer language-specific bugs
- faster debugging
- safer experimentation with new clients
- clearer compatibility story
- less silent engine behavior
- fewer viewer-only discoveries like the turtle1 commander build churn

The highest-value first step is not a huge v2 redesign. It is structured validation results plus stricter proxy checks for command shape, target ownership, options, build capability, stale state, and accidental immediate order replacement.
