# Implementation Plan: gRPC Gateway for External AI & Observers

**Branch**: `001-grpc-gateway` | **Date**: 2026-04-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-grpc-gateway/spec.md`

## Summary

Fork BARb (CircuitAI, BAR-targeted Skirmish AI) and inject a new
`CGrpcGatewayModule : IModule` that exposes a gRPC server over a Unix
domain socket or loopback TCP. The module materializes a protobuf
`StateSnapshot` on subscription and publishes per-frame `StateDelta`s
(seq-numbered, ring-buffered) to up to four observers plus one
authenticated AI client. Commands submitted by the AI client are
deferred from gRPC worker threads to the engine thread via an MPSC
queue, then dispatched through CircuitAI's existing `CCircuitUnit::Cmd*`
APIs. Phase 1 leaves BARb's built-in modules active; Phase 2 (config
flag) lets the external client be the sole decision authority.

Technical approach is fully described in
[`docs/architecture.md`](../../docs/architecture.md); this plan turns
that design into a Constitution-gated, phase-ordered build plan and
derives the concrete research, data-model, and contract artifacts.

## Technical Context

**Language/Version**: C++20 (plugin, inherited from BARb/CircuitAI) · F#
on .NET 8 (F# client, ported from HighBarV2) · Python 3.11+ (new Python
client).
**Primary Dependencies**: gRPC C++ (vcpkg manifest, tracking the same
minor as `Grpc.Net.Client` on the F# side — see research.md) ·
Protobuf · Abseil (transitive via gRPC) · `Grpc.Net.Client` with
`SocketsHttpHandler`/`UnixDomainSocketEndPoint` (F#) · `grpcio` /
`grpcio-tools` (Python) · `buf` for code generation.
**Storage**: Ephemeral only. Per-session `AuthToken` written to
`$writeDir/highbar.token` (mode 0600) at plugin init; ring buffer of
2048 recent `StateUpdate`s in process memory; no on-disk persistence.
**Testing**: GoogleTest (C++ unit + `dlopen`-driven integration
harness) · BAR `spring-headless` (end-to-end, real engine) ·
`dotnet test` / xUnit (F# client) · `pytest` (Python client) ·
latency microbench alongside integration tests (`UnitDamaged` → F#
`OnEvent`).
**Target Platform**: Linux x86_64 (primary), matching BAR's engine
targets. Clients and the game run on the same host (Assumption in
spec). Ubuntu 22.04+ reference distro; gRPC pinned via vcpkg because
the distro package is too old.
**Project Type**: Native shared-library game plugin (`libSkirmishAI.so`)
plus two client libraries (F#/.NET and Python). Fork of an existing C++
codebase, not greenfield.
**Performance Goals** (from spec SC-002/SC-003 and Constitution V):
p99 round-trip ≤ 500µs UDS, ≤ 1.5ms loopback TCP; ≤ 5% framerate
regression with 4 observers attached; first snapshot delivered within
2s of subscribe.
**Constraints**: Engine-thread-only mutation (Constitution II,
NON-NEGOTIABLE) — all `Cmd*` calls and CircuitAI state writes on the
single engine callback thread. Bounded per-subscriber queue (8192) and
bounded command queue, both must fail synchronously on overflow. UDS
path ≤108 bytes. Max gRPC receive size bumped to 32MB (late-game
snapshots exceed 4MB default). Hard cap 4 concurrent observers.
Schema version strict-equality handshake. Fail-closed on internal
gateway faults (no silent degradation).
**Scale/Scope**: Single-match, single-host, single AI slot. ≤ 4
observer subscribers + 1 AI client concurrent. Match duration target:
30+ minutes without dropped/duplicated/out-of-order messages in ≥95%
of sessions (SC-006). Roughly 28 engine-event delta variants and 97
`AICommand` variants carried over from HighBarV2's proto tree.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version: **1.0.0** (`.specify/memory/constitution.md`).

| # | Principle | Plan status | Evidence / notes |
|---|---|---|---|
| I | Upstream Fork Discipline | **PASS** | All V3 code lives under the paths reserved by the constitution: `src/circuit/module/GrpcGatewayModule*`, `src/circuit/grpc/*`, `proto/highbar/*`, `clients/*`, `data/config/grpc.json`, `vcpkg.json`, `docs/*`. Upstream-shared edits are strictly scoped: ~3 lines in `src/circuit/CircuitAI.cpp::Init`, 1 line in `Release`, plus targeted `CMakeLists.txt` additions. Commit hygiene (V3 code separated from upstream-shared edits) is called out in `/speckit.tasks`. |
| II | Engine-Thread Supremacy (NON-NEGOTIABLE) | **PASS** | Design routes every `CCircuitUnit::Cmd*` call and CircuitAI manager write through the engine thread. gRPC workers deposit commands into an MPSC queue drained on the frame-update callback (FR-010). Snapshot serialization is the single read-side worker-thread exception, and uses a shared/exclusive lock with writers never blocking on gRPC I/O — matches the principle's carve-out verbatim. |
| III | Proto-First Contracts | **PASS** | Every client-observable interface lives under `proto/highbar/` (`service.proto`, `state.proto`, plus V2's `common.proto`, `events.proto`, `commands.proto`, `callbacks.proto`). Generated C++/C#/Python stubs are build artifacts via `buf` (`proto/buf.gen.yaml`). FR-022 / FR-022a make proto the sole contract and mandate a versioned strict-equality handshake (`Hello`). No side-channel formats, no ad-hoc JSON. |
| IV | Phased Externalization | **PASS** | Spec user stories map exactly onto the constitution's phase gates: US1+US2 = Phase 1 (built-in AI active, gateway additive); US3 = Phase 2 (config flag `enable_builtin=false`). Phase 3 per-module opt-out is explicitly out of scope for this feature (spec Assumptions). Delivery order is US1 → US2 → US4 → US3 → US5 → US6 (priority-ordered). |
| V | Latency Budget as Shipping Gate | **PASS** | SC-002 bakes the constitution's budget into the spec: ≤500µs p99 UDS, ≤1.5ms p99 loopback TCP, measured via `UnitDamaged` → F# `OnEvent`. Microbench ships alongside integration tests (Verification §5 in architecture doc). |

**License & Compliance**: PASS. All new deps (gRPC, Protobuf, Abseil
via vcpkg; `Grpc.Net.Client`, `grpcio`) are Apache-2.0 / BSD and
GPL-2.0-compatible. Clients sit behind the gRPC interface and do not
statically link plugin code, preserving "separate works" status.

**Complexity Tracking**: *none*. No principle deviations; the
architecture document is the authoritative shape and this plan
implements it directly. Complexity table intentionally left blank.

**Initial gate result**: **PROCEED TO PHASE 0.**

## Project Structure

### Documentation (this feature)

```text
specs/001-grpc-gateway/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── service.proto    # RPC surface sketch
│   ├── state.proto      # StateUpdate / snapshot / delta sketch
│   └── README.md        # Per-RPC contract notes
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (repository root)

HighBarV3 is a **fork of BARb**. The layout below lists only the
paths this feature adds or edits; the rest of the tree inherits from
upstream and is not reproduced here.

```text
# V3-additive (owned by this feature, per Constitution I)
src/circuit/module/
└── GrpcGatewayModule.{h,cpp}     # NEW — IModule impl: event handlers + command dispatch

src/circuit/grpc/                 # NEW — gRPC-specific code, isolated for clean upstream merges
├── HighBarService.{h,cpp}        #   grpc::Service async impl, CQ management
├── DeltaBus.{h,cpp}              #   SPMC fan-out, per-subscriber 8192 ring
├── SnapshotBuilder.{h,cpp}       #   CircuitAI managers → StateSnapshot
├── AuthInterceptor.{h,cpp}       #   AI-token gate for SubmitCommands/InvokeCallback
├── CommandQueue.{h,cpp}          #   MPSC, drained on engine-thread frame callback
└── RingBuffer.{h,cpp}            #   StateUpdate history for resume-from-seq

proto/highbar/                    # NEW — GPL-2.0 contract surface
├── common.proto                  #   ported from V2
├── events.proto                  #   ported from V2 (28 engine events)
├── commands.proto                #   ported from V2 (97 AICommands)
├── callbacks.proto               #   ported from V2 (becomes InvokeCallback body)
├── service.proto                 #   NEW — HighBarProxy RPC surface
└── state.proto                   #   NEW — StateSnapshot + StateDelta + StateUpdate envelope

proto/buf.gen.yaml                # NEW — buf codegen config (cpp, csharp, python)
proto/buf.yaml                    # NEW — buf lint/breaking config

clients/fsharp/                   # NEW — .NET 8 F# client (port from HighBarV2)
├── HighBar.Client.fsproj
├── src/
│   ├── Channel.fs                #   UDS + TCP endpoint construction
│   ├── Session.fs                #   Hello handshake, observer/AI roles
│   ├── StateStream.fs            #   StreamState consumer, resume-from-seq
│   └── Commands.fs               #   SubmitCommands wrapper, F#-ergonomic DU over AICommand
└── tests/
    └── HighBar.Client.Tests.fsproj

clients/python/                   # NEW — grpcio Python client
├── pyproject.toml
├── highbar_client/
│   ├── channel.py
│   ├── session.py
│   └── state_stream.py
└── tests/

data/config/grpc.json             # NEW — transport + token-path + ring-size config

vcpkg.json                        # NEW — manifest mode for grpc, protobuf, abseil
CMakeLists.txt                    # EDIT — find_package(gRPC/Protobuf), generated-code target,
                                  #        link with -fvisibility=hidden -Bsymbolic

# Upstream-shared edits (per Constitution I: surgical, justified)
src/circuit/CircuitAI.cpp         # EDIT — 3 lines in Init(), 1 in Release(): construct/register/destroy
                                  #        the gateway module after economyManager

# Tests
tests/
├── unit/                         # GoogleTest — synthetic event streams, DeltaBus stress,
│                                 #              second SubmitCommands → ALREADY_EXISTS,
│                                 #              observer InvokeCallback → PERMISSION_DENIED
├── integration/                  # dlopen-driven mock-engine harness — reconnect/resume,
│                                 #                                     reconnect/fresh,
│                                 #                                     multi-client (AI + 2 obs)
├── headless/                     # spring-headless scripts — Phase 1 + Phase 2 acceptance,
│                                 #                           60s smoke, framerate budget
└── bench/                        # latency microbench (UnitDamaged → F# OnEvent, p99 gate)
```

**Structure Decision**: This is a forked-codebase project with three
deliverable artifacts (plugin shared library, F# client library,
Python client library) and one contract (`proto/highbar/`). We do not
adopt the single-project, web-app, or mobile+API templates from the
plan boilerplate — the constitution prescribes the layout above, and
the architecture document names each file individually. Code paths
owned by V3 are kept under a small, merge-stable set of directories
(`src/circuit/module/GrpcGatewayModule*`, `src/circuit/grpc/*`,
`proto/highbar/`, `clients/*`) so that upstream BARb merges touch only
three files: `CircuitAI.cpp`, `CMakeLists.txt`, and — rarely — the
generated-code registration in `buf.gen.yaml`.

## Complexity Tracking

*No Constitution Check violations. Table intentionally empty.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *(none)*  | *(n/a)*    | *(n/a)*                             |
