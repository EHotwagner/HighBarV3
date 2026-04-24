# Implementation Plan: Non-Python Client Protobuf And Proxy Safety

**Branch**: `019-protobuf-proxy-safety` | **Date**: 2026-04-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/019-protobuf-proxy-safety/spec.md`

## Summary

This feature makes the HighBar gateway contract safer for generated non-Python clients by adding structured command diagnostics, explicit correlation and state-basis fields, dry-run validation, capability discovery, dispatch-failure visibility, and a separately authorized admin control surface. The technical approach is additive in `highbar.v1` where compatibility allows it: preserve existing `CommandAck` counters and current Python/F# client behavior during a warning-only rollout, then enable strict rejection for malformed, stale, conflicting, unauthorized, or unsafe command/admin submissions once conformance evidence is available.

## Technical Context

**Language/Version**: C++17 for the gateway module and proxy implementation, proto3 with `package highbar.v1`, Python 3.11+ for generated client/conformance fixtures, F#/.NET 8 for the existing non-Python client surface, Bash for headless wrappers.  
**Primary Dependencies**: `proto/highbar/{commands,service,state,common}.proto`, buf/protoc generated C++/C#/Python stubs, gRPC/Protobuf via vcpkg for C++, `src/circuit/grpc/{HighBarService,CommandValidator,CommandQueue,CommandDispatch,Config,Counters,DeltaBus,SchemaVersion}.*`, `src/circuit/module/GrpcGatewayModule.*`, Python client helpers under `clients/python/highbar_client/`, F# wrappers under `clients/fsharp/`, and the existing headless/integration test harness.  
**Storage**: No database. Runtime state is in-memory gateway/session state: per-stream batch sequence cache, per-unit order tracker, admin controller leases, queue capacity counters, and emitted state deltas. Durable evidence is filesystem-backed under existing reports/test artifacts, including conformance and warning-only rollout reports.  
**Testing**: `buf lint proto`, `cd proto && buf generate`, C++ unit tests under `tests/unit/`, integration tests under `tests/integration/`, Python pytest under `clients/python/tests/`, F# build/tests through `clients/fsharp/*.fsproj`, and headless validation through `tests/headless/*.sh`.  
**Target Platform**: Linux x86_64 maintainer and CI environments running the Spring/BAR Skirmish AI plugin, loopback TCP or UDS gRPC transport, and generated Python/F# clients.  
**Project Type**: Proto-first gRPC service and native plugin gateway with generated client libraries.  
**Performance Goals**: Preserve Constitution V transport budget, p99 round-trip <= 500us on UDS and <= 1.5ms on loopback TCP. Keep command validation overhead below the existing 100us p99 validator microbudget and avoid per-command allocations on the engine-thread dispatch path where practical.  
**Validation Baseline**: Current `SubmitCommands` validates batches with human-readable first-error strings, returns aggregate `CommandAck` counters only on stream completion, pushes commands one-by-one into a bounded queue, and can leave a partially queued batch if capacity is exhausted mid-batch. `commands.proto` carries broad V2-style raw integer fields, legacy pause/cheat arms, and no strict correlation/state-basis fields.  
**Constraints**: All client-observable interfaces must be expressed in `.proto` files; additive v1 schema changes must preserve field numbers and existing counters; generated C++, C#, and Python stubs must be regenerated together; gRPC worker threads must not mutate CircuitAI state or call engine APIs; admin actions must use run-scoped role credentials and engine-thread execution; strict mode rejects missing correlation or state basis, while rollout mode may warn without behavior change; command batches are atomic on validation, stale, conflict, and capacity failures.  
**Scale/Scope**: Covers normal AI command submission, command dry-run validation, capability discovery, dispatch result deltas, strict/warning-only validation modes, legacy AI-channel admin compatibility flags, separate admin validation/execution/capability RPCs, admin leases/audit events, and conformance evidence for Python plus at least one generated non-Python client. Excludes a breaking `highbar.v2` command-shape redesign except as documented follow-up direction.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version: **1.0.0** (`.specify/memory/constitution.md`).

| # | Principle | Plan status | Evidence / notes |
|---|---|---|---|
| I | Upstream Fork Discipline | PASS | Planned edits stay in V3-owned gateway, proto, clients, tests, docs, and config paths. Any unavoidable `CMakeLists.txt` change is limited to codegen/build wiring and must be called out in PRs. |
| II | Engine-Thread Supremacy | PASS | Worker-thread validation remains read-only or snapshot-derived. Queue drains, dispatch rechecks, order-tracker mutation, and admin engine actions execute on the gateway/engine thread. |
| III | Proto-First Contracts | PASS | New diagnostics, capabilities, dispatch events, and admin controls are defined in `proto/highbar/*.proto`; no side-channel JSON or string protocol is introduced for client-observable behavior. |
| IV | Phased Externalization | PASS | The work strengthens the external client contract while keeping existing Python/F# clients and compatibility mode during rollout. It does not remove builtin AI fallback or force Phase 3 per-module control. |
| V | Latency Budget as Shipping Gate | PASS | Validation is scoped to deterministic checks, warning/strict modes are configurable, and the existing validator perf test remains a shipping gate with added scenarios. |

**Initial gate result**: **PASS**

**Post-design re-evaluation**: **PASS**. Phase 1 keeps the design proto-first, isolates admin controls from AI intent, preserves engine-thread mutation rules, and uses additive v1 contracts plus rollout modes instead of a breaking rewrite.

## Project Structure

### Documentation (this feature)

```text
specs/019-protobuf-proxy-safety/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── command-diagnostics-and-validation.md
│   ├── command-capabilities-and-dispatch.md
│   ├── admin-control-service.md
│   └── conformance-and-rollout.md
└── tasks.md
```

### Source Code (repository root)

```text
proto/highbar/
├── commands.proto
├── service.proto
├── state.proto
└── common.proto

src/circuit/grpc/
├── HighBarService.{h,cpp}
├── CommandValidator.{h,cpp}
├── CommandQueue.{h,cpp}
├── CommandDispatch.{h,cpp}
├── OrderStateTracker.{h,cpp}
├── CapabilityProvider.{h,cpp}
├── AdminController.{h,cpp}
├── AdminService.{h,cpp}
├── Config.{h,cpp}
├── Counters.{h,cpp}
├── DeltaBus.{h,cpp}
└── SchemaVersion.h

src/circuit/module/
├── GrpcGatewayModule.{h,cpp}
└── CircuitAI.cpp

clients/python/highbar_client/
├── highbar/*_pb2*.py
├── commands.py
├── admin.py
└── ai_plugins.py

clients/fsharp/
├── HighBar.Proto.csproj
├── src/Commands.fs
├── src/Admin.fs
└── samples/AiClient/Program.fs

tests/
├── unit/
│   ├── command_validation_test.cc
│   ├── command_validation_perf_test.cc
│   └── command_queue_test.cc
├── integration/
│   └── cross_client_parity_test.sh
└── headless/
    ├── test_command_contract_hardening.sh
    └── protobuf-proxy-safety.sh
```

**Structure Decision**: Keep the implementation in the existing V3-owned gRPC gateway and proto contract. `commands.proto` owns command input shape, validation issues, retry hints, correlation/state-basis fields, and capability types. `service.proto` owns AI and admin RPC surfaces plus ack/admin result messages. `state.proto` owns dispatch/audit delta events. `CommandValidator` produces structured results for both dry-run and submit; `HighBarService` maps those results to RPC responses and strict/warning behavior; `CommandQueue` gains atomic batch capacity handling; `OrderStateTracker` owns per-unit conflict state; `CapabilityProvider` owns command and unit discovery; `AdminController` and `AdminService` own privileged validation, leases, and admin RPCs; `GrpcGatewayModule` and `CommandDispatch` own engine-thread rechecks, order tracking, dispatch events, and admin action execution.

## Phase 0 Research Summary

Phase 0 resolves the implementation choices behind the contract and rollout:

1. Use additive `highbar.v1` proto fields for diagnostics, correlation, dry-run validation, capabilities, dispatch events, and admin service scaffolding instead of starting with a breaking v2 redesign.
2. Preserve current aggregate `CommandAck` counters and add repeated per-batch results so existing clients remain compatible while generated clients get stable issue data.
3. Make batch handling atomic across validation, stale/conflict checks, and queue capacity by checking capacity before pushing any command from a batch.
4. Keep authoritative mutation and post-acceptance rechecks on the engine thread; worker-thread validation is preliminary and never calls `CCircuitUnit::Cmd*`.
5. Separate admin controls into a `HighBarAdmin` service with run-scoped role credentials, config/run-mode gates, leases for conflict-prone controls, and audit events.
6. Roll out strictness through warning-only mode and conformance fixtures before default strict rejection.

See [research.md](./research.md).

## Phase 1 Design Summary

Phase 1 models 019 as a shared validation contract plus two execution surfaces:

- `CommandBatch` gains client correlation, state basis, unit generation, and explicit conflict policy fields for strict-mode validation and retry correlation.
- `CommandBatchResult`, `CommandIssue`, `CommandIssueCode`, `RetryHint`, and `CommandBatchStatus` define stable command diagnostics while preserving existing ack counters.
- `CapabilityProfile` and related request/response types expose legal command arms, option masks, map/resource identifiers, queue state, schema version, feature flags, and unit-specific capabilities.
- `CommandDispatchEvent` closes the gap between accepted/enqueued commands and commands later skipped during engine-thread dispatch.
- `AdminAction`, `AdminActionResult`, `AdminIssue`, `AdminCapabilities`, `AdminLease`, and `AdminAuditEvent` define the separate privileged control surface.
- `ValidationMode` and rollout evidence records make warning-only, compatibility, and strict behavior explicit.

See [data-model.md](./data-model.md), [contracts/command-diagnostics-and-validation.md](./contracts/command-diagnostics-and-validation.md), [contracts/command-capabilities-and-dispatch.md](./contracts/command-capabilities-and-dispatch.md), [contracts/admin-control-service.md](./contracts/admin-control-service.md), and [contracts/conformance-and-rollout.md](./contracts/conformance-and-rollout.md).

## Complexity Tracking

No constitution violations or exception justifications are required.
