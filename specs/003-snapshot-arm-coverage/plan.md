# Implementation Plan: Snapshot-grounded behavioral verification of AICommand arms

**Branch**: `003-snapshot-arm-coverage` | **Date**: 2026-04-21 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-snapshot-arm-coverage/spec.md`

## Summary

002 shipped the gateway, wired all 66 `AICommand` oneof arms into
`CommandDispatch.cpp`, and produced `aicommand-arm-coverage.csv` by
grepping dispatcher log lines for "forwarded / rejected". That coverage
number is a **wire-side** claim: it proves the gateway accepted the
batch and the dispatcher called a `CCircuitUnit::Cmd*` entry point. It
does not prove the engine actually *did* anything — whether the unit
moved, a construction site appeared, or a target took damage is still
unobserved. 002's deferred T025/T044/T045/T068/T069 exist precisely
because behavioral verification was punted out of that feature.

This plan closes that gap with one mechanical loop:

1. **Make `StateSnapshot` periodic.** The plugin has always been able
   to materialise a snapshot — it does so once in `HelloResponse`. This
   feature adds a frame-tick scheduler on the engine thread that emits
   `StateUpdate.payload.snapshot` every `snapshot_cadence_frames`
   frames (default 30 ≈ 1s at 30fps) when the gateway is `Healthy`
   (FR-001). An on-demand `RequestSnapshot` RPC (FR-006) is the test
   driver's escape hatch.

2. **Add three anchor per-command tests.** `behavioral-move.sh`,
   `behavioral-build.sh`, and `behavioral-attack.sh` each dispatch
   exactly one command, sample snapshots before and after, and assert
   the snapshot diff proves engine-side execution. These are the
   smallest-possible cases of the macro driver's loop; if they pass,
   the technique scales.

3. **Build the macro driver.** A new `behavioral_coverage` submodule
   inside the existing `clients/python/highbar_client` package
   (FR-013) holds a 66-row arm registry: each row binds an arm name
   to a `required_capability` tag, an input-builder lambda, and a
   verify-predicate. The driver executes a deterministic Phase-1
   **bootstrap plan** (commander builds factory/airpad/radar/mex/
   builder — enough capability coverage to provision Phase-2
   targets), then iterates the registry, dispatching each arm
   against its capability-provisioned target, running its
   verify-predicate, and performing a **bootstrap-state reset**
   between arms so destructive commands (SelfDestruct, long-range
   Move) don't cascade into later rows. Output: `build/reports/
   aicommand-behavioral-coverage.csv` (66 rows) + its
   `.digest` sidecar (SHA-256 over the four reproducibility-critical
   columns).

4. **Close 002's deferred backlog.** The five-run reproducibility
   script (US6) subsumes T068 (full-suite 5× pass) and T069
   (framerate p50 ±5%). The behavioral-coverage registry with per-arm
   verify-predicates subsumes T044/T045 for the wire-observable
   subset; Channel-C Lua-only arms remain deferred under their own
   follow-up tied to BAR Lua widgets (spec §Out of Scope). T025
   (framerate harness) is closed by US6's FR-009 p50 assertion.

Technical approach continues to track
[`docs/architecture.md`](../../docs/architecture.md). This feature
changes *no* architectural decisions — it exercises them. The
snapshot tick scheduler lands inside the existing
`CGrpcGatewayModule::OnFrameTick` → serialise → fan-out path that
the delta stream already uses; no new threads, no new locks, no new
transports. The `RequestSnapshot` RPC is one additional unary method
on `HighBarProxy`. The behavioral-coverage submodule is pure Python
on top of the existing `highbar_client.highbar` stubs.

## Technical Context

**Language/Version**: unchanged from 002 — C++20 for the plugin
(`libSkirmishAI.so`, BARb/CircuitAI fork), Python 3.11+ for the
macro driver (`clients/python/highbar_client`, grpcio). No F# work
in this feature (F# behavioral tests deferred, spec §Out of Scope).

**Primary Dependencies**: inherited — gRPC C++ + Protobuf + Abseil
(vcpkg manifest, baseline `256acc64012b23a13041d8705805e1f23b43a024`,
`vcpkg.json`); `grpcio` / `grpcio-tools` for Python; `buf` for
codegen. The pinned engine stays `recoil_2025.06.19`
(`data/config/spring-headless.pin`). One new Python-only transitive
dep is expected: `hashlib` is stdlib so SHA-256 comes free, but if
CSV canonicalization needs an ordered-key JSON or a deterministic
float-formatter, it lands in `clients/python/pyproject.toml` under
the existing `highbar_client` package (no separate package, no new
lockfile, per FR-013).

**Storage**: unchanged from 002 — ephemeral only. Per-session
`AuthToken` at `$writeDir/highbar.token` (mode 0600); bounded delta
ring buffer in process memory. This feature adds two new *artifact*
files emitted by the macro driver (not the plugin):
`build/reports/aicommand-behavioral-coverage.csv` and its
`.digest` sidecar. Both are build products; neither is checked in.

**Testing**: existing test taxonomy honored — `unit/` (GoogleTest),
`integration/` (`dlopen`-driven mock engine), `headless/` (real
`spring-headless`), `bench/` (UDS + TCP latency). This feature adds:

- One unit test for the snapshot-tick scheduler (fake frame clock,
  asserts emission cadence under normal load and under the halving
  rule when `own_units.length > snapshot_max_units`).
- Four new headless scripts: `behavioral-move.sh`,
  `behavioral-build.sh`, `behavioral-attack.sh`,
  `aicommand-behavioral-coverage.sh`, plus a
  `snapshot-tick.sh` that validates FR-001 cadence in isolation and
  a `behavioral-reproducibility.sh` that drives the macro driver
  five times and compares digests.
- No new integration tests — the mock engine does not produce the
  rich `own_units[]` the behavioral predicates need; the integration
  layer's role is the fault-surface tests 002 already owns.

**Target Platform**: unchanged — Linux x86_64 Ubuntu 22.04 reference
host (`bar-engine` self-hosted runner for headless + reproducibility
jobs, GitHub-hosted for unit + codegen + lint). The
five-run reproducibility script runs only on the self-hosted runner
(spec §Assumptions).

**Project Type**: same as 001/002 — forked C++ game plugin plus two
client libraries. No new top-level artifacts.

**Performance Goals**: two new gates added to the 001/002 set —

- **FR-001 cadence**: ≥ 25 snapshots in a 30s window at default
  config, max gap between snapshots ≤ 2s (SC-005 allows ≤5%
  framerate cost).
- **SC-003 wall-clock**: macro driver completes in ≤ 300s on the
  reference host (one match boot ~15s + bootstrap plan ≤ 90s + 66
  arms × [dispatch + verify ≤ 4s + reset ≤ 3s] ≈ 460s worst-case,
  trimmed by not-wire-observable/cheats/precondition rows).

The existing 001/002 budgets (p99 round-trip ≤ 500µs UDS / ≤ 1.5ms
loopback TCP, ≤ 5% framerate regression with four observers) must
hold with the snapshot tick enabled at default cadence (FR-011).

**Constraints**: all 001/002 constraints carry forward — engine-
thread supremacy for all mutations, bounded queues, schema-version
strict equality, ≤4 observers + 1 AI client, 108-byte UDS path
limit. This feature adds:

- **Engine-thread serialisation of snapshots.** The snapshot tick
  fires from `OnFrameTick` on the engine thread; the serialiser
  reuses the existing mutex/shared-lock discipline from the Hello
  path. gRPC workers still only fan out pre-built `StateUpdate`
  bytes.
- **Bounded RequestSnapshot rate.** `RequestSnapshot` coalesces
  to at most one extra snapshot per engine frame regardless of
  caller count (FR-006). Implementation: a single `pending_request`
  atomic flag the engine thread clears after each served snapshot.
- **Reproducibility discipline.** The digest (FR-004a) MUST be
  bit-for-bit stable across runs at the same gameseed; any
  non-determinism in the reproducibility-critical columns
  (`arm_name, dispatched, verified, error`) is a test bug that
  MUST be fixed in the Python driver, not papered over with retries
  or filtered out of the digest.

**Scale/Scope**: unchanged target host, ≤4 observers + 1 AI client,
30+ minute match runs. Scope additions are finite and named:

- One new plugin-side scheduler (`SnapshotTick` in
  `src/circuit/grpc/`, called from `OnFrameTick`).
- One new `HighBarProxy.RequestSnapshot` RPC (additive oneof-less
  unary; backward-compatible per Constitution III).
- One new `StateSnapshot.effective_cadence_frames` field (additive
  scalar; backward-compatible).
- One new Python submodule: `clients/python/highbar_client/
  behavioral_coverage/` with a 66-entry arm registry, a bootstrap
  manifest, a canonical CSV serialiser, and a CLI entry point.
- Six new headless scripts under `tests/headless/`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version: **1.0.0** (`.specify/memory/constitution.md`).

| # | Principle | Plan status | Evidence / notes |
|---|---|---|---|
| I | Upstream Fork Discipline | **PASS** | All new C++ code lands under the V3-reserved paths: the snapshot-tick scheduler in `src/circuit/grpc/SnapshotTick.{h,cpp}`, the `RequestSnapshot` handler in `src/circuit/grpc/HighBarService.cpp` (existing 002 file), the new proto fields in `proto/highbar/state.proto` and `proto/highbar/service.proto`. `CGrpcGatewayModule::OnFrameTick` gets one additional call site (`snapshot_tick_.Pump(frame)`) — the same surgical-edit shape 002 used for `DrainCommandQueue`. No edits to upstream-shared CircuitAI files beyond that already-justified module surface. No new top-level directories; the Python submodule lives inside the existing `clients/python/highbar_client` package per FR-013. |
| II | Engine-Thread Supremacy (NON-NEGOTIABLE) | **PASS** | The snapshot tick fires from `OnFrameTick` — engine thread, same call site that already drains the command queue. Snapshot serialisation reuses the existing `state_mutex_` shared-lock discipline (readers take shared, the engine-thread writer takes exclusive). `RequestSnapshot` RPC handlers on gRPC worker threads set a single atomic `pending_request_` flag; the engine thread observes it at the next `OnFrameTick` and emits one extra snapshot. No new threads, no new locks. The bootstrap-state reset is entirely client-side (Python macro driver) and interacts with the plugin only through the existing `SubmitCommands` → `DrainCommandQueue` engine-thread path. |
| III | Proto-First Contracts | **PASS** | Schema changes are strictly additive: (a) new `StateSnapshot.effective_cadence_frames uint32 = 8` (next free field number after 001's `static_map = 7`; backward-compatible — existing clients that ignore unknown fields see no change), (b) new `HighBarProxy.RequestSnapshot` RPC with a zero-field `RequestSnapshotRequest` and zero-field `RequestSnapshotResponse` (additive service method; v1 stubs regenerate cleanly). Schema version stays `1.0.0`; per Constitution III these additions satisfy "backward-compatible within a MINOR release." No new side-channel formats — the CSV and digest are test-artifact outputs, not client-observable wire surface (same carve-out 002 applied to `highbar.health` and the `[hb-gateway] fault` log line). `buf` codegen remains the sole source of generated code; all three client targets (C++, F#, Python) regenerate from the same `.proto` edits. |
| IV | Phased Externalization | **PASS** | This feature is pure validation instrumentation — it measures what 002 already delivered. No change to the phase model: Phase 1 stays the baseline (built-in BARb + additive gateway); Phase 2's `enable_builtin = false` path is unaffected by snapshot cadence (both paths produce the same `own_units[]`); Phase 3 remains out of scope. The bootstrap plan (FR-003a) runs in Phase 1 mode (built-in BARb active) because it needs the commander to auto-morph commands to issue; reproducibility (FR-012) is still deterministic because the gameseed is fixed. |
| V | Latency Budget as Shipping Gate | **PASS** | The snapshot tick interacts with the latency budget in two places, both measured by existing 002 benches: (a) serialisation cost per tick is bounded by `own_units.length` × fixed-cost-per-unit; the halving rule (FR-001 when `> snapshot_max_units`) caps the amortised per-frame cost regardless of unit count; (b) FR-011 forbids regressing on the existing `us1-observer.sh` / `us2-ai-coexist.sh` / latency benches with snapshot tick enabled. The unit test for the scheduler measures serialiser microseconds-per-unit; the headless `snapshot-tick.sh` re-runs `us1-framerate.sh`'s comparison and asserts ≤5% regression (SC-005). On the wire, `send_monotonic_ns` stamping already added in 002 (T062–T065) covers snapshots exactly as it covers deltas. |

**License & Compliance**: PASS. No new third-party dependencies. The
Python-only driver uses `grpcio`, `hashlib` (stdlib), and the existing
`highbar_client` package — all GPL-2.0-compatible or stdlib.

**Complexity Tracking**: *none expected*. The snapshot tick is a
single-call-site frame-driven pump; the bootstrap-state reset is a
per-arm guarded loop in Python; the digest is a one-line SHA-256
over a canonical CSV. No design deviates from the architecture doc
or a principle at plan-authoring time. If implementation surfaces an
unavoidable deviation (e.g., the engine thread can't afford the
serialiser on the same frame as the tick interval suggests), it
will be added here with a justification. The table is intentionally
empty.

**Initial gate result**: **PROCEED TO PHASE 0.**

**Post-design re-evaluation (to be filled after Phase 1 artifacts
land)**: deferred — the plan command completes with artifacts on
disk; the re-evaluation sentence is written by the tasks/implement
commands as the phase boundary is actually crossed. At plan-authoring
time no post-design delta is known.

## Project Structure

### Documentation (this feature)

```text
specs/003-snapshot-arm-coverage/
├── plan.md              # This file (/speckit.plan output)
├── research.md          # Phase 0 output — decisions on tick scheduler, bootstrap topology, digest canonicalization, threshold policy
├── data-model.md        # Phase 1 output — BehavioralTestCase, BootstrapPlan, SnapshotPair, VerificationOutcome, CoverageReport, SnapshotTickConfig
├── quickstart.md        # Phase 1 output — how a dev runs each of US1–US6 locally against the reference host
├── contracts/           # Phase 1 output — snapshot-tick proto delta, RequestSnapshot RPC, CSV + digest format, arm-registry schema, bootstrap-plan spec
└── tasks.md             # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (repository root)

This feature does not create new top-level source directories. Every
edit is to a file 001/002 already produced; every new file lands
under an existing subtree. The list below names every file this
feature edits or creates; lines are from the 002-landed tree as
surveyed on 2026-04-21.

```text
# Proto surface (Constitution III — additive, backward-compatible)
proto/highbar/state.proto                        # EDIT — add `uint32 effective_cadence_frames = 8` to
                                                 #        StateSnapshot. Field number is the next free
                                                 #        after 001's `static_map = 7`.
proto/highbar/service.proto                      # EDIT — add `rpc RequestSnapshot(RequestSnapshotRequest)
                                                 #        returns (RequestSnapshotResponse)` to
                                                 #        HighBarProxy. Define the two zero-field message
                                                 #        types in the same file.

# Plugin-side snapshot tick (FR-001, FR-006)
src/circuit/grpc/SnapshotTick.h                  # NEW — header for SnapshotTick scheduler (config struct,
                                                 #        Pump(frame) method, halving-cadence state).
src/circuit/grpc/SnapshotTick.cpp                # NEW — implementation. Emits snapshots at configured
                                                 #        cadence, doubles interval while
                                                 #        own_units.length > snapshot_max_units, sets
                                                 #        StateSnapshot.effective_cadence_frames on each
                                                 #        emission. Consumes the same serialiser the Hello
                                                 #        path uses.
src/circuit/module/GrpcGatewayModule.h           # EDIT — add SnapshotTick member, wire config load from
src/circuit/module/GrpcGatewayModule.cpp         #        grpc.json, add RequestSnapshot plumbing (atomic
                                                 #        pending flag drained on OnFrameTick).
src/circuit/grpc/HighBarService.h                # EDIT — add RequestSnapshot RPC handler (enqueues the
src/circuit/grpc/HighBarService.cpp              #        pending flag; does not call the serialiser on
                                                 #        the worker thread). Coalesces concurrent
                                                 #        callers to one extra snapshot per frame.
data/config/grpc.json                            # EDIT — document + expose new keys
                                                 #        `snapshot_cadence_frames` (default 30) and
                                                 #        `snapshot_max_units` (default 1000) under a new
                                                 #        `snapshot_tick` object. Back-compat: missing
                                                 #        object → defaults.

# Python macro driver (FR-013 — new submodule inside existing package)
clients/python/highbar_client/behavioral_coverage/__init__.py       # NEW — module entry, CLI argparse, orchestrator.
clients/python/highbar_client/behavioral_coverage/__main__.py       # NEW — `python -m highbar_client.behavioral_coverage` entry.
clients/python/highbar_client/behavioral_coverage/registry.py       # NEW — 66-row arm registry: arm_name → (category, required_capability, input_builder, verify_predicate).
clients/python/highbar_client/behavioral_coverage/capabilities.py   # NEW — required_capability tag vocabulary (`commander`, `factory_ground`, `factory_air`, `builder`, `mex`, `radar`, `cloakable`, …).
clients/python/highbar_client/behavioral_coverage/bootstrap.py      # NEW — deterministic BootstrapPlan (ordered commander build orders, per-capability timeouts, manifest diff helper for FR-003b reset).
clients/python/highbar_client/behavioral_coverage/predicates.py     # NEW — shared verify-predicate building blocks (position-delta, unit-count-delta, health-delta, etc.).
clients/python/highbar_client/behavioral_coverage/report.py         # NEW — canonical CSV serialiser (ascending arm_name sort, UTF-8, LF), digest computer (SHA-256 over arm_name + dispatched + verified + error columns).
clients/python/pyproject.toml                                       # EDIT — register the behavioral_coverage submodule in `[project.entry-points]` or tool.setuptools.packages.find config if needed. Any new pip deps land here.

# Headless acceptance scripts (US1–US6)
tests/headless/snapshot-tick.sh                  # NEW — US5. Subscribes to StreamState, counts snapshot
                                                 #        payloads over 30s window, asserts cadence.
tests/headless/behavioral-move.sh                # NEW — US1. Single MoveUnit; snapshot diff on position.
tests/headless/behavioral-build.sh               # NEW — US2. Single BuildUnit; snapshot diff on
                                                 #        own_units.length + under_construction +
                                                 #        build_progress monotonicity.
tests/headless/behavioral-attack.sh              # NEW — US3. Single AttackUnit; snapshot diff on enemy
                                                 #        health, or EnemyDestroyed delta observation.
tests/headless/aicommand-behavioral-coverage.sh  # NEW — US4. Wraps `uv run --project clients/python python
                                                 #        -m highbar_client.behavioral_coverage` per FR-013.
                                                 #        Checks fault_status first (edge case), then runs
                                                 #        macro driver, then evaluates verified-rate against
                                                 #        HIGHBAR_BEHAVIORAL_THRESHOLD.
tests/headless/behavioral-reproducibility.sh     # NEW — US6. Invokes the coverage script 5× with the same
                                                 #        gameseed, diffs the five `.digest` files, asserts
                                                 #        identical; asserts p50 framerate spread ≤ 5%.

# Unit tests (FR-001 scheduler behavior under fake frame clock)
tests/unit/snapshot_tick_test.cc                 # NEW — asserts cadence at default config, asserts
                                                 #        halving when own_units > snapshot_max_units,
                                                 #        asserts effective_cadence_frames is populated.

# CI pipeline
.github/workflows/ci.yml                         # EDIT — add headless jobs for the 5 new scripts (three
                                                 #        P1 anchors + coverage + snapshot-tick) to the
                                                 #        existing self-hosted stage. Add
                                                 #        behavioral-reproducibility.sh as a post-merge job
                                                 #        (not per-PR — 5× runs exceed PR budget). Upload
                                                 #        build/reports/aicommand-behavioral-coverage.csv +
                                                 #        .digest as artifacts.

# Docs
docs/architecture.md                             # EDIT — one paragraph in §Threading / §State Flow
                                                 #        noting the new SnapshotTick call site; one
                                                 #        paragraph in §Test Topology naming the macro
                                                 #        driver as the 66-arm coverage source of truth.
                                                 #        No design changes.
specs/002-live-headless-e2e/tasks.md             # EDIT (light) — mark T025/T044/T045/T068/T069 as
                                                 #        subsumed-by-003, link to this spec. No task
                                                 #        content rewrite.
CLAUDE.md                                        # EDIT — update the <!-- SPECKIT START/END --> block to
                                                 #        point at specs/003-snapshot-arm-coverage/plan.md.
```

**Structure Decision**: This feature inherits 001/002's project
structure wholesale — no new top-level directories are introduced.
The biggest new subtree is
`clients/python/highbar_client/behavioral_coverage/`, which sits
inside an already-existing Python package per FR-013 (the
clarification's explicit direction: extend, don't fork). New C++
code lives under `src/circuit/grpc/` alongside the 002-era dispatcher
and coordinator. New acceptance scripts land in `tests/headless/`
next to the US1–US6 scripts 002 produced. This matches Constitution I
(fork discipline) exactly: we extend existing subtrees instead of
spreading V3 code into new ones.

## Complexity Tracking

*No Constitution Check violations at plan-authoring time.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *(none)*  | *(n/a)*    | *(n/a)*                             |
