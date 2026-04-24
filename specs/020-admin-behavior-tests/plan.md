# Implementation Plan: Comprehensive Admin Channel Behavioral Control

**Branch**: `020-admin-behavior-tests` | **Date**: 2026-04-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/020-admin-behavior-tests/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

This feature turns the admin channel from a mostly contract-level control surface into a behaviorally verified live-match tool. The implementation keeps `HighBarAdmin` as the privileged service from feature 019, adds the missing unit-ownership transfer action and any capability metadata needed to advertise it, executes all match mutations on the engine thread, and extends the Python/headless behavioral harness so each accepted pause, resume, speed, resource, spawn, transfer, rejection, lease, and capability scenario is proven against observed match state.

## Technical Context

**Language/Version**: C++17 for the gateway/admin controller and engine-thread execution, proto3 in `package highbar.v1`, Python 3.11+ for generated client helpers and behavioral harnesses, F#/.NET 8 for generated non-Python client compatibility, Bash for headless entry points.  
**Primary Dependencies**: `proto/highbar/{service,state,commands,common}.proto`, buf/protoc generated C++/C#/Python stubs, gRPC/Protobuf via vcpkg, `src/circuit/grpc/{AdminController,AdminService,HighBarService,CapabilityProvider,DeltaBus,Config,Counters}.*`, `src/circuit/module/GrpcGatewayModule.*`, Python helpers under `clients/python/highbar_client/`, behavioral coverage modules under `clients/python/highbar_client/behavioral_coverage/`, existing integration and headless harnesses under `tests/{unit,integration,headless}/`.  
**Storage**: No database. Runtime admin state stays in memory: role/caller metadata, active admin leases, frame/state basis, live match snapshots, audit events, and counters. Durable evidence is filesystem-backed under `build/reports/admin-behavior/` with per-action summaries, log pointers, and repeat-run artifacts.  
**Testing**: `buf lint proto`, `cd proto && buf generate`, C++ unit tests under `tests/unit/`, C++ integration tests under `tests/integration/`, Python pytest under `clients/python/tests/`, F# build/tests through `clients/fsharp/*.fsproj`, and live/headless validation through a new stable `tests/headless/admin-behavioral-control.sh` entry point.  
**Target Platform**: Linux x86_64 maintainer and CI environments running the Spring/BAR Skirmish AI plugin with loopback TCP or UDS gRPC transport and a prepared local BAR runtime.  
**Project Type**: Proto-first gRPC service and native plugin gateway with generated client libraries and headless behavioral test tooling.  
**Performance Goals**: Preserve Constitution V transport budget, p99 round-trip <= 500us on UDS and <= 1.5ms on loopback TCP. Complete the full admin behavioral suite in under 3 minutes on a prepared local environment. Observe each successful admin effect within 10 seconds.  
**Validation Baseline**: Feature 019 already added `HighBarAdmin`, admin role metadata, dry-run validation, execution results, capabilities, leases, and audit events. Existing schema covers pause, global speed, cheat policy, resource grant, unit spawn, and lifecycle actions. Unit ownership transfer is not yet represented in the admin proto. Existing behavioral coverage infrastructure proves AI command effects, but admin actions do not yet have comprehensive before/after state evidence.  
**Constraints**: All client-observable admin behavior must be in `.proto` files under `proto/highbar/`; generated C++, C#, and Python stubs must be regenerated together after proto changes; gRPC worker threads must not mutate CircuitAI or call engine callbacks; accepted admin mutations must be queued/drained on the gateway engine thread; invalid and unauthorized admin requests must be rejected before state mutation; pause/speed tests must restore normal play before continuing or exiting; unavailable local runtime prerequisites exit as setup failures, not behavioral regressions.  
**Scale/Scope**: Covers one controlled local live fixture, all currently supported mutating admin controls, one additive unit-transfer admin action, rejection cases for authorization, values, teams, unit definitions, positions, stale basis, and lease conflicts, capability discovery checks, repeatability across three consecutive prepared runs, and reviewable evidence artifacts. Excludes remote multiplayer, public production matches, a breaking `highbar.v2` redesign, and speculative Phase 3 per-module control.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version: **1.0.0** (`.specify/memory/constitution.md`).

| # | Principle | Plan status | Evidence / notes |
|---|---|---|---|
| I | Upstream Fork Discipline | PASS | Planned edits stay in V3-owned proto, gateway, client, tests, reports, and docs paths. Any unavoidable build wiring in upstream-shared files must be minimal and called out in the PR. |
| II | Engine-Thread Supremacy | PASS | Validation and RPC metadata handling may run on gRPC workers, but pause, speed, resource, spawn, transfer, lease mutation, counters tied to execution, and audit emission for execution are applied through the gateway engine-thread path. |
| III | Proto-First Contracts | PASS | New transfer action, capability advertisement, result/evidence identifiers, and any additional observable fields are additive `highbar.v1` proto fields; reports consume proto-derived observations rather than side-channel command formats. |
| IV | Phased Externalization | PASS | The feature strengthens external admin/test control while preserving builtin AI fallback and current command behavior. It does not require external-client-only mode or Phase 3 module opt-outs. |
| V | Latency Budget as Shipping Gate | PASS | Behavioral evidence collection is test tooling. Runtime changes remain small admin-control additions and must keep existing latency bench gates intact. |

**Initial gate result**: **PASS**

**Post-design re-evaluation**: **PASS**. Phase 1 keeps the feature proto-first, additive, isolated to V3 paths, and engine-thread-safe. No constitution violations or exception justifications are required.

## Project Structure

### Documentation (this feature)

```text
specs/020-admin-behavior-tests/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── admin-behavioral-suite.md
│   ├── admin-control-contract-delta.md
│   └── admin-evidence-report.md
└── tasks.md
```

### Source Code (repository root)

```text
proto/highbar/
├── service.proto
├── state.proto
└── common.proto

src/circuit/grpc/
├── AdminController.{h,cpp}
├── AdminService.{h,cpp}
├── CapabilityProvider.{h,cpp}
├── Config.{h,cpp}
├── Counters.{h,cpp}
└── DeltaBus.{h,cpp}

src/circuit/module/
├── GrpcGatewayModule.{h,cpp}
└── CircuitAI.cpp

clients/python/highbar_client/
├── admin.py
├── highbar/*_pb2*.py
└── behavioral_coverage/
    ├── admin_actions.py
    ├── admin_observations.py
    ├── admin_report.py
    └── __main__.py

clients/python/tests/
├── test_admin.py
└── behavioral_coverage/
    ├── test_admin_actions.py
    ├── test_admin_observations.py
    └── test_admin_report.py

clients/fsharp/
├── HighBar.Proto.csproj
└── src/Admin.fs

tests/
├── unit/
│   └── admin_control_test.cc
├── integration/
│   └── admin_control_test.cc
├── headless/
│   ├── admin-behavioral-control.sh
│   └── scripts/admin-behavior.startscript
└── fixtures/
    └── admin_behavior/
        └── fixture.yaml
```

**Structure Decision**: Keep runtime implementation in the existing V3-owned admin/gateway modules and proto files. Reuse the Python behavioral coverage package for live orchestration and evidence rendering, but keep admin-specific actions, observation predicates, and reports in admin-named modules. Add a single headless wrapper as the stable developer/CI entry point and keep deterministic fixture metadata under `tests/fixtures/admin_behavior/`.

## Phase 0 Research Summary

Phase 0 resolves the implementation choices behind the behavioral suite:

1. Reuse `HighBarAdmin` from feature 019 and extend it additively with `UnitTransferAction` instead of introducing a second admin surface.
2. Use state-stream snapshots/deltas as the primary evidence source, with engine logs only as diagnostics for prerequisite or failure explanation.
3. Use a deterministic local fixture with known teams, resource ids, unit definitions, spawn positions, and an existing transferable unit.
4. Treat pause, resume, and speed as timing-sensitive observations with tolerance windows, cleanup actions, and normal-speed restoration.
5. Report prerequisite failures with exit 77 and behavioral failures with exit 1 so CI/developers can distinguish missing BAR runtime from regressions.
6. Keep capability discovery authoritative: tests execute only advertised controls and fail if advertised controls are not executable.

See [research.md](./research.md).

## Phase 1 Design Summary

Phase 1 models this feature as a live admin scenario suite plus durable evidence:

- `AdminBehaviorScenario` defines one success or rejection case, including action builder, caller role, fixture prerequisites, expected result, and expected observation.
- `AdminObservation` captures before/after snapshots, selected deltas, frame windows, tolerance values, and log pointers used to prove or disprove an effect.
- `AdminEvidenceRecord` renders the request, structured result, expected observation, actual observation, pass status, and diagnostics for each action category.
- `AdminBehaviorRun` aggregates scenario records, prerequisite status, capability profile, cleanup result, repeat index, and final exit classification.
- `UnitTransferAction` closes the contract gap for ownership transfer and is advertised through admin capabilities only when executable in the current run.

See [data-model.md](./data-model.md), [contracts/admin-control-contract-delta.md](./contracts/admin-control-contract-delta.md), [contracts/admin-behavioral-suite.md](./contracts/admin-behavioral-suite.md), [contracts/admin-evidence-report.md](./contracts/admin-evidence-report.md), and [quickstart.md](./quickstart.md).

## Complexity Tracking

No constitution violations or exception justifications are required.
