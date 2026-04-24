# Phase 0 Research: Non-Python Client Protobuf And Proxy Safety

## Additive v1 Contract First

**Decision**: Implement the first safety pass as additive `highbar.v1` fields, messages, enums, and RPCs. Reserve a breaking `highbar.v2` command-shape cleanup for a later feature.

**Rationale**: The current schema is already shipped into C++, Python, and F# surfaces. Additive proto3 fields let existing clients ignore new data while generated clients opt into diagnostics, correlation, dry-run validation, and capabilities. This also satisfies the constitution's backward-compatible minor-change rule.

**Alternatives considered**: Start `highbar.v2` immediately with typed command intents and enums. Rejected because it would combine safety enforcement with a broad migration and delay the high-value diagnostics needed by non-Python clients now.

## Structured Results In `CommandAck`

**Decision**: Preserve `last_accepted_batch_seq`, `batches_accepted`, `batches_rejected_invalid`, and `batches_rejected_full`; add `repeated CommandBatchResult results`.

**Rationale**: Current clients and samples consume the aggregate counters. Per-batch results provide stable issue codes, field paths, retry hints, and client correlation without breaking old codegen.

**Alternatives considered**: Return only gRPC status details for validation failures. Rejected because client-streaming `SubmitCommands` currently closes the stream on first failure and cannot report mixed batch diagnostics or warning-only would-reject evidence cleanly.

## Atomic Batch Capacity Handling

**Decision**: Treat capacity failures as whole-batch rejection by checking available queue capacity before pushing any command from a batch.

**Rationale**: The clarified spec requires atomic rejection for validation, stale, conflict, and capacity issues. The current push loop can enqueue earlier commands before a later command hits queue capacity; this must change before strict mode.

**Alternatives considered**: Keep partial enqueue and report `COMMAND_BATCH_PARTIALLY_QUEUED_BEFORE_QUEUE_FULL`. Rejected because the spec explicitly chooses atomic batches.

## Validation Placement

**Decision**: Split validation into worker-safe preliminary checks and engine-thread authoritative checks. Worker checks produce structured diagnostics but never mutate CircuitAI state. Engine-thread drain rechecks live ownership, target existence, capability, order-tracker conflicts, and admin actions before execution.

**Rationale**: This preserves Engine-Thread Supremacy while giving clients early deterministic failures. Dispatch events cover races after initial acceptance.

**Alternatives considered**: Move all validation to the worker thread for lower latency. Rejected because CircuitAI state mutation and callback APIs are not thread-safe, and some live facts are only safe to re-evaluate on the engine thread.

## Strict, Compatibility, And Warning Modes

**Decision**: Add config-driven validation modes: compatibility, warning-only, and strict. Strict mode rejects missing correlation or state-basis fields; warning-only records would-reject diagnostics without changing simulation behavior.

**Rationale**: Existing Python helpers and tests need a transition period. Warning-only reports let maintainers find false positives across prepared live/headless runs before strict rejection becomes default.

**Alternatives considered**: Enable strict rejection immediately. Rejected because current clients do not populate all new fields and would fail before conformance evidence exists.

## Explicit Correlation And State Basis

**Decision**: Add stable client correlation and basis fields to `CommandBatch`: `client_command_id`, `based_on_frame`, `based_on_state_seq`, `target_generation`, and `conflict_policy`.

**Rationale**: Generated clients need to match acks, logs, dispatch results, and state updates to original intent. State-basis fields let the proxy detect stale commands. Explicit conflict policy makes accidental immediate-order replacement detectable.

**Alternatives considered**: Infer correlation from `batch_seq` alone. Rejected because retries, reconnects, logs, dispatch events, and future multi-client tooling need an identifier that is client-owned and durable across surfaces.

## Capability Discovery

**Decision**: Add command schema and unit capability discovery RPCs on the AI service and admin capability discovery on a separate admin service.

**Rationale**: Non-Python generated clients should not need Python helper conventions to discover legal command arms, option masks, resource identifiers, map limits, build options, queue state, feature flags, and admin availability.

**Alternatives considered**: Document capabilities in comments only. Rejected because proto comments do not enforce behavior and are weakly surfaced in generated clients.

## Admin Control Separation

**Decision**: Introduce `HighBarAdmin` as a sibling service for pause, global speed, cheat, lifecycle, and future test-harness actions. Use run-scoped role credentials, config/run-mode gates, single-owner leases for conflicting controls, dry-run validation, execution results, and audit events.

**Rationale**: Normal AI clients should not gain global match authority through the unit-command path. Admin controls affect the whole run and need a different authorization and audit model.

**Alternatives considered**: Keep pause/cheat arms on `SubmitCommands` with stricter validation. Rejected because it keeps privileged run control adjacent to normal AI intent and makes generated clients infer that global controls are normal strategy commands.

## Dispatch Result Deltas

**Decision**: Add a `CommandDispatchEvent` state delta emitted when accepted commands are applied or skipped during engine-thread dispatch.

**Rationale**: `CommandAck` can only confirm validation/enqueue. Units can die, change ownership, lose capability, or become invalid before dispatch. Clients need a structured post-acceptance result within one state update cycle.

**Alternatives considered**: Log dispatch failures only. Rejected because logs are not a client-observable contract and cannot drive generated-client retry behavior.

## Conformance Evidence

**Decision**: Build fixture-driven conformance across Python and at least one generated non-Python client, using the same serialized command/admin fixtures and asserting identical result codes.

**Rationale**: The feature's purpose is language-neutral safety. Equivalent validation outcomes across generated clients are the evidence that the contract is not Python-helper-specific.

**Alternatives considered**: Unit-test the C++ validator only. Rejected because C++ tests do not prove generated client usability or cross-language schema behavior.
