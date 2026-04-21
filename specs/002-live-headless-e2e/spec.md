# Feature Specification: Live Headless End-to-End

**Feature Branch**: `002-live-headless-e2e`
**Created**: 2026-04-21
**Status**: Draft
**Input**: User description: "create specs to create a behaviorally fully functioning version, running against live headless servers."

## Clarifications

### Session 2026-04-21

- Q: Must every `AICommand` arm be wired to a live engine call (no deferral category), or may some arms return a distinct "deferred" error? → A: Every arm must be wired and behaviorally tested; no deferral category exists. All 66 arms (the count actually declared in `proto/highbar/commands.proto`) map to an observable engine effect. Malformed payloads still return `INVALID_ARGUMENT` per normal RPC validation.
- Q: What CI runner topology should the plan target for headless + latency gates? → A: Hybrid — GitHub-hosted runners for build, unit tests, Python pytest, codegen, and lint; a self-hosted runner with `spring-headless` + BAR asset cache for the headless acceptance suite and latency benches.
- Q: How is SC-008 (runbook validation for first-time users) measured? → A: Proxy — a CI job executes `BUILD.md` verbatim on a clean VM image and fails on the first step that does not match its documented output, plus at least one peer walkthrough on a clean VM before the feature is marked complete. No external recruit pool is required.
- Q: What happens if the gateway module faults mid-match (malformed frame, transient gRPC error, OOM during serialization)? → A: Exceptions caught at the module boundary; the gateway disables itself (drops clients, stops streaming, logs a structured `[hb-gateway]` fault event); the engine and the plugin's own AI logic continue uninterrupted. A disabled-gateway state must be observable to acceptance scripts and CI.

## User Scenarios & Testing *(mandatory)*

The HighBarV3 gRPC gateway (feature 001) landed with all 107 tasks marked
complete on master, but **nothing has been exercised end-to-end**. Every
acceptance script exits `skip` because the plugin binary has never been
built. Every latency claim is unverified. Documented gaps in the 001
implementation (Python client import bug, 51 of 66 `AICommand` arms
stubbed out, `UnitDamaged` payload not threaded to the gateway, unit
tests with no CMake target) remain open.

This feature closes those gaps so a maintainer can check out the branch,
run one command, and have a real BAR `spring-headless` match produce
proof that every Success Criterion in spec 001 is met with measured
numbers and no skips.

### User Story 1 — Plugin builds and loads into spring-headless (Priority: P1)

A maintainer checks out `master`, runs the project's documented build
command, and ends up with a working `libSkirmishAI.so` that
`spring-headless` can load as a BAR Skirmish AI without the engine
rejecting it, crashing, or falling back silently.

**Why this priority**: Every other story depends on this. Without a
loadable plugin, every downstream test continues to exit `skip`.

**Independent Test**: Run the build command. Launch
`spring-headless` with a minimal match script that selects HighBarV3 as
one AI slot. Confirm (a) the engine log reports the plugin loaded, (b)
the gateway emits its `[hb-gateway]` startup log line, (c) the engine
does not exit with an AI-slot failure.

**Acceptance Scenarios**:

1. **Given** a clean checkout of master on Linux x86_64 with the
   documented prerequisites installed, **When** the maintainer runs the
   project's build command, **Then** `libSkirmishAI.so` is produced
   under `build/` within 15 minutes.
2. **Given** the built plugin and a `spring-headless` binary, **When**
   the maintainer launches a BAR match with HighBarV3 selected,
   **Then** the engine log contains the gateway's startup log line and
   a bound Unix-domain socket is present on disk before the first game
   frame.

---

### User Story 2 — Observer integration test runs green (Priority: P1)

A maintainer runs the existing US1 observer acceptance script
(`tests/headless/us1-observer.sh`) and it produces `PASS` (not `skip`)
against a real `spring-headless` match, proving the end-to-end state
streaming path works.

**Why this priority**: US1 is the MVP of the 001 feature. A `PASS`
on this script empirically validates Success Criteria SC-001 (snapshot
within 2s) and SC-003 (framerate budget) that are currently unverified.

**Independent Test**: Launch a match with the built plugin. Run
`us1-observer.sh`. Confirm it exits 0, that the F# observer received at
least one `Snapshot` update within 2 seconds of connect, and that the
delta stream that follows has strictly monotonic sequence numbers over
a 30-second window.

**Acceptance Scenarios**:

1. **Given** a built plugin and a runnable engine, **When** the
   maintainer runs `us1-observer.sh`, **Then** the script exits 0, the
   observer logs at least one snapshot arm, and every subsequent delta
   arm has a strictly greater sequence number than the one before it.
2. **Given** the same environment, **When** the maintainer runs
   `us1-framerate.sh`, **Then** the measured framerate with four
   observers attached is at least 95 percent of the baseline framerate
   without observers.

---

### User Story 3 — AI command integration test runs green (Priority: P1)

A maintainer runs `tests/headless/us2-ai-coexist.sh` against a live
match, and an authenticated F# client successfully issues a `MoveTo`
command that the engine observably executes — the unit moves — while
the built-in AI continues to play its own units.

**Why this priority**: US2 is the core product feature of 001 — the
external AI path. Without a `PASS` here, "behaviorally fully
functioning" is not achieved regardless of how much code is on disk.
This story validates FR-006, FR-012, and FR-013.

**Independent Test**: Launch a match. Run `us2-ai-coexist.sh`.
Confirm (a) the F# client's `Hello` is accepted with an AI-slot claim,
(b) `SubmitCommands` returns a successful `CommandAck`, (c) the target
unit's position in the state stream changes within 3 engine frames of
command acceptance, (d) a second concurrent AI-role client receives
`ALREADY_EXISTS`, (e) the built-in AI's log lines continue appearing
throughout.

**Acceptance Scenarios**:

1. **Given** a live match with the plugin bound, **When** an
   authenticated F# client submits a `MoveTo` targeting a unit it owns,
   **Then** the engine moves the unit within 3 frames and the
   subsequent state stream reflects the new position.
2. **Given** an AI client already connected and actively streaming,
   **When** a second AI client attempts `Hello` with `role=AI`, **Then**
   the second client receives `ALREADY_EXISTS`.

---

### User Story 4 — Python client passes its own tests (Priority: P2)

A maintainer installs the Python client dev extras, runs `pytest` from
`clients/python/`, and every pure-unit test collects and passes. The
live-gateway tests are skipped cleanly when no gateway is present and
pass when the `HIGHBAR_UDS_PATH` and `HIGHBAR_TOKEN_PATH` environment
variables point at a running gateway.

**Why this priority**: A real import bug in the 001 implementation
blocks `tests/test_ai_role.py` from even being collected, because the
client modules import from a submodule path that the documented
codegen never produces. This must be fixed for FR-021 to be
credible.

**Independent Test**: Run `pytest` in `clients/python/` after running
the project's Python codegen step. Confirm 0 import errors, all
pure-unit tests pass, and live-gateway tests either skip (no gateway)
or pass (against a running gateway).

**Acceptance Scenarios**:

1. **Given** a clean virtualenv with dev extras installed and proto
   stubs freshly generated, **When** the maintainer runs `pytest`,
   **Then** both `test_observer.py` and `test_ai_role.py` collect
   without error and every pure-unit test passes.
2. **Given** the same environment with `HIGHBAR_UDS_PATH` and
   `HIGHBAR_TOKEN_PATH` pointed at a live gateway, **When** the
   maintainer runs `pytest`, **Then** the live-gateway tests pass,
   including `SubmitCommands` from the Python AI-role sample.

---

### User Story 5 — All 66 AI command arms wired and tested (Priority: P2)

An external AI developer writing against the F# or Python client can
issue any of the 66 `AICommand` arms and observe the engine execute
it. Every arm — unit orders, drawing, chat, Lua calls, stockpiling,
construction, self-destruct, and the rest — is backed by a real
`springai::*` engine call and exercised by at least one acceptance
test. No arm is "deferred" or "logged-and-skipped."

**Why this priority**: The 001 implementation logs-and-skips 51 of 66
arms inside the engine dispatcher. An external AI that happens to send
any of those receives a successful `CommandAck` even though nothing
happens — a silent failure mode that breaks FR-009's testability and
undermines FR-014's causal-ordering guarantee.

**Independent Test**: For each of the 66 `AICommand` arms, send one
batch from the Python client against a live match and verify an
observable engine effect via the state stream or a documented
side-channel (engine log line, Lua widget hook, map marker diff)
where the stream alone cannot observe the effect. No arm may produce
a successful ACK with no engine effect.

**Acceptance Scenarios**:

1. **Given** a live match and an authenticated client, **When** the
   client submits any `AICommand` arm (any of the 66), **Then** the
   engine executes the order and the state stream or documented
   side-channel reflects the effect within 3 engine frames.
2. **Given** the same environment, **When** the client submits a
   malformed arm payload (missing a required field or out-of-range
   value), **Then** the response carries `INVALID_ARGUMENT` per normal
   RPC validation — distinct from "not wired," because no arm is
   unwired.

---

### User Story 6 — CI blocks regressions on the headless + latency gates (Priority: P2)

Every push to master and every pull request runs the full acceptance
suite against a real `spring-headless` match in a CI worker. Failures
in any headless script, pytest suite, dotnet build, or latency bench
block the merge. `skip` (exit 77) is never accepted silently on the CI
path — it is either upgraded to `PASS` or explicitly marked expected
with a short-lived waiver the maintainer has to remove.

**Why this priority**: Without this, the same "all green because all
skipped" failure mode that hid 001's integration gap can happen
again. CI is how "behaviorally fully functioning" stays true over time.

**Independent Test**: Push a commit that introduces a regression
(e.g., forces `us1-observer.sh` to fail by breaking schema version in
the Hello response). Confirm the CI run marks the pipeline failed and
the PR merge is blocked.

**Acceptance Scenarios**:

1. **Given** a pull request that regresses the observer acceptance
   script, **When** the CI pipeline runs, **Then** the pipeline is
   marked failed and the PR is blocked from merging.
2. **Given** a pull request that regresses the UDS latency bench past
   the 500µs p99 budget, **When** the CI pipeline runs, **Then** the
   bench job fails and the PR is blocked.
3. **Given** a CI run where `spring-headless` is unavailable in the
   runner environment, **When** the headless jobs would otherwise
   skip, **Then** the pipeline is marked failed unless the commit
   carries an explicit `ci-skip-reason:` footer the CI config requires.

---

### User Story 7 — Latency bench meets per-transport budgets with measured numbers (Priority: P3)

`tests/bench/latency-uds.sh` and `tests/bench/latency-tcp.sh` both
produce `PASS` with published p99 numbers below the Constitution V
budgets (500µs UDS, 1.5ms loopback TCP) on the reference Linux
x86_64 hardware described in the 001 plan. The measurement path uses a
true engine-event → F# client timestamp round trip, not a proxy metric.

**Why this priority**: SC-002 from the 001 spec is currently
aspirational. This story makes it a measured gate. The Constitution V
commitment only holds if the number exists and is reproducible.

**Independent Test**: Run both bench scripts against a live match on
the reference platform. Confirm both exit 0 and record p99 numbers
inside budget. Re-run five times and confirm the numbers are stable
within 20 percent run-to-run variance.

**Acceptance Scenarios**:

1. **Given** a live match on Linux x86_64 reference hardware, **When**
   the maintainer runs `latency-uds.sh`, **Then** the script exits 0
   and the published p99 is under 500µs.
2. **Given** the same environment configured for TCP transport,
   **When** the maintainer runs `latency-tcp.sh`, **Then** the script
   exits 0 and the published p99 is under 1.5ms.

---

### Edge Cases

- The reference Linux x86_64 host has a `spring-headless` binary
  installed, but CI runners may not. CI behavior when no binary is
  available is covered by US6.
- `grpcurl` may be absent on the reference host; acceptance scripts
  that probe RPCs directly need a bundled or documented substitute.
- vcpkg manifest resolution may fail on a host behind a restrictive
  firewall; the documented build path must record the vcpkg binary
  cache fallback.
- The BAR game assets (maps, unit defs) required to launch a
  `spring-headless` match are not part of this repo. The documented
  build must name the minimum asset set and where it comes from.
- A build that silently falls through to the `Protobuf/gRPC not found`
  warning branch produces a plugin that compiles but has no wire
  dependencies — the build must fail loudly in this case, not warn.
- Unit test binaries under `tests/unit/` have no CMake wiring; a pass
  of 100% of headless tests with no unit tests running is not an
  acceptable "green" state.
- 51 of the 66 `AICommand` arms currently declared in
  `proto/highbar/commands.proto` log-and-skip at the dispatcher. An
  authenticated client submitting one of these receives an ACK with
  no engine effect. This feature closes that path by wiring every arm
  to a real engine call; no deferral category is permitted. (The "97"
  figure occasionally cited from the 001 plan was aspirational and
  did not match the landed proto; this feature commits to the real
  in-repo count of 66.)
- Some arms (chat, draw markers, Lua calls) have no state-stream-visible
  effect in a single-player vs-AI match. For these, the feature must
  designate a documented side-channel (engine log assertion, Lua widget
  hook, in-memory marker list) that the acceptance test can observe.
- The gateway module can fault at runtime (malformed client frame,
  transient gRPC error, OOM during snapshot serialization). Per
  FR-023, this disables the gateway but does not crash the engine or
  the plugin's own AI. Acceptance scripts must distinguish this from
  a healthy gateway and fail loudly.

## Requirements *(mandatory)*

### Functional Requirements

**Build & load**

- **FR-001**: A maintainer MUST be able to produce a working
  `libSkirmishAI.so` from a clean checkout of master on Linux x86_64
  by running a single documented command. The command MUST resolve all
  native dependencies (gRPC, Protobuf, Abseil) without manual
  intervention.
- **FR-002**: The build MUST fail loudly with a non-zero exit code and
  a specific error message if gRPC or Protobuf cannot be resolved. The
  existing `message(WARNING …)` fallback that produces a plugin with
  no wire dependencies MUST be removed or converted to a hard error.
- **FR-003**: The built plugin MUST load successfully into
  `spring-headless` as a BAR Skirmish AI and bind its configured
  transport before the first game frame is processed.
- **FR-004**: The documented build command MUST record which specific
  `spring-headless` release it was validated against and provide a
  reproducible path to that release (a known binary cache, a published
  URL, or a checked-in pointer to an engine fork commit).

**Integration test parity**

- **FR-005**: `tests/headless/us1-observer.sh` MUST exit 0 against a
  live match when the plugin is built and `spring-headless` is
  available. Skip (exit 77) due to missing prerequisites MUST be
  distinguishable from skip due to no plugin built.
- **FR-006**: `tests/headless/us2-ai-coexist.sh` MUST exit 0 against a
  live match, including the concurrent-AI-client race that exercises
  `ALREADY_EXISTS` per FR-011 of feature 001.
- **FR-007**: The full set of headless acceptance scripts (17 in
  total) MUST either exit 0 or exit 77-skip-with-reason. Exit codes 1
  or other non-zero non-77 values MUST be treated as failures.
- **FR-008**: The framerate regression check (`us1-framerate.sh`) MUST
  use a deterministic match seed so the measurement is reproducible
  run-to-run within 5 percent variance.

**Client fixes**

- **FR-009**: The Python client packages (`highbar_client.commands`,
  `highbar_client.session`, `highbar_client.state_stream`) MUST import
  from the submodule path that the documented codegen command
  produces. `pytest` MUST collect every test file without import
  errors.
- **FR-010**: The documented Python codegen MUST be reproducible from
  the project root by a single command, without manual `cd` steps or
  environment-specific path juggling.
- **FR-011**: The F# client MUST remain buildable from a clean `obj/`
  with no manual intervention (reproducing the first-build glitch
  observed in the 001 verification pass — where `HighBar.Proto` did
  not emit stubs until a second build — is a regression).

**Command surface**

- **FR-012**: The engine-side command dispatcher MUST wire every
  `AICommand` proto arm (all 66 declared in `proto/highbar/commands.proto`)
  to a `springai::*` callback that produces an observable engine
  effect or a documented side-channel signal (engine log line, Lua
  widget hook, map marker diff) where the state stream alone cannot
  observe the effect. No arm may return a successful `CommandAck`
  without a corresponding engine effect. The current "logged and
  silently accepted" path MUST be removed. Malformed arm payloads
  MUST return `INVALID_ARGUMENT` per normal RPC validation; this is
  distinct from "not wired," because no arm is unwired.
- **FR-013**: Every `AICommand` arm MUST be exercised by at least one
  acceptance-test scenario that submits the arm end-to-end from the F#
  or Python client against a live match and asserts the observable
  engine effect (state-stream diff or documented side-channel). The
  test suite's per-arm coverage MUST be enumerable: a report listing
  all 66 arms with their test file and assertion MUST be producible
  from the build.
- **FR-014**: The latency bench MUST measure the true engine-event →
  F# client round trip, not an inter-arrival proxy. The `UnitDamaged`
  payload fields (damage, direction, weapon) that the richer CCircuitAI
  signature carries MUST be threaded into the gateway's `DeltaEvent`
  so a timestamp can be attached server-side.

**Unit test wiring**

- **FR-015**: The C++ unit test sources under `tests/unit/` MUST be
  buildable and runnable from the project's CMake configuration. A
  `ctest` invocation MUST exercise every test file currently on disk
  and report pass/fail counts.
- **FR-016**: Unit test failures MUST block the CI pipeline. A green
  CI run with zero unit tests executed MUST NOT be possible.

**CI**

- **FR-017**: The CI configuration MUST execute the full headless
  acceptance suite against a real `spring-headless` binary on at least
  one worker on every push to master and every pull request. Headless
  acceptance scripts, latency benches, and any unit tests requiring
  the engine MUST target a runner class with `spring-headless` and the
  BAR asset cache available (a self-hosted runner in the default
  topology). Other jobs (build, Python pytest, F#/dotnet build,
  codegen, lint) MAY run on GitHub-hosted runners.
- **FR-018**: The CI configuration MUST fail the pipeline if any
  headless script exits 77-skip unless the commit carries an explicit
  `ci-skip-reason:` footer the CI config requires to be present for
  skips to be tolerated.
- **FR-019**: The CI configuration MUST fail the pipeline if either
  latency bench reports a p99 over its Constitution V budget.
- **FR-020**: The CI configuration MUST publish the p99 numbers from
  both latency benches as a visible build artifact, so regressions
  below the gate (e.g., p99 drifting from 300µs to 480µs, still under
  the 500µs budget) are observable historically.

**Documentation**

- **FR-021**: The `quickstart.md` in the 001 feature directory MUST be
  updated so every command it documents is verified by this feature
  and every step produces the claimed result. A CI job SHOULD execute
  quickstart.md steps in sequence and fail on any step that does not
  match its documented output.
- **FR-022**: The project MUST ship a top-level `BUILD.md` (or equivalent
  single-file runbook) that takes a maintainer from clean checkout to
  a running match with a live observer attached in no more than 10
  discrete documented steps.

**Runtime resilience**

- **FR-023**: The gateway module MUST catch any exception or error
  that escapes a gRPC handler, a state-serialization step, a transport
  I/O call, or a callback into the CircuitAI unit layer at the
  `CGrpcGatewayModule` boundary. An uncaught fault MUST NOT propagate
  to the engine, crash the `spring-headless` process, or halt the
  plugin's own AI logic. Instead, the gateway MUST transition to a
  disabled state: close active client streams, stop accepting new
  connections, and leave the plugin's AI logic running for the
  remainder of the match.
- **FR-024**: A disabled-gateway state MUST be observable to
  acceptance scripts and CI. The gateway MUST emit a structured
  `[hb-gateway] fault` log line naming the originating subsystem
  (transport / serialization / dispatch / callback) and a stable
  reason code, and MUST expose the disabled state through a mechanism
  the headless acceptance scripts can assert on (for example, the
  socket being removed or a documented health file flipping to a
  failed state). Any acceptance script that runs to completion with
  the gateway in disabled state MUST be treated as a failure, not a
  skip.

### Key Entities

- **Live headless match**: a `spring-headless` process launched with a
  BAR start script that selects HighBarV3 as one AI slot, on a map
  with at least one spawnable unit definition, running long enough
  (≥30 seconds) to exercise the gateway's delta stream.
- **Reference host**: the Linux x86_64 machine the build and bench
  commands were validated on. The specific kernel version,
  `spring-headless` release, vcpkg baseline, and dotnet SDK version
  are part of the entity's defining attributes — the commitment is
  reproducibility against this entity, not universal portability.
- **CI worker pool**: a two-tier runner set — (a) GitHub-hosted
  runners for build, unit tests, Python pytest, F#/dotnet build,
  codegen, and lint; (b) at least one self-hosted runner with the
  reference host's toolchain + a cached `spring-headless` binary + the
  minimum BAR asset set, targeted by the headless acceptance and
  latency-bench jobs via a runner label. Self-hosted workers that
  lack any of these assets cannot run the gated jobs and must be
  configured to fail the pipeline, not silent-skip.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A maintainer starting from a clean checkout on the
  reference host reaches a running `spring-headless` match with a live
  F# observer attached in under 10 minutes, following only the
  documented build and run steps.
- **SC-002**: All 17 headless acceptance scripts exit 0 (not 77-skip)
  on the reference host. The run is reproducible: five consecutive
  runs produce the same pass set.
- **SC-003**: `pytest` from `clients/python/` collects 100% of test
  modules without import errors. Pure-unit tests pass; live-gateway
  tests pass when a gateway is provided.
- **SC-004**: Every `AICommand` arm (all 66 declared in the proto)
  produces an observable engine effect or a documented side-channel
  signal in at least one acceptance test. Zero arms produce a
  successful ACK with no engine effect, and zero arms return a
  "deferred" error — the deferral category does not exist. Malformed
  payloads return `INVALID_ARGUMENT` per normal RPC validation only.
- **SC-005**: UDS latency bench reports a p99 of 500µs or below on
  the reference host, measured across a 30-second sample of at least
  1000 round trips. TCP loopback latency bench reports 1.5ms or
  below under the same conditions.
- **SC-006**: Every C++ unit test file under `tests/unit/` is compiled
  and executed by a `ctest` invocation from the project's CMake build.
  Unit test execution is part of the CI pipeline.
- **SC-007**: A contributor who intentionally introduces a regression
  (breaking the schema version, forcing a headless script to fail,
  breaking the Python import again, or regressing latency past budget)
  sees the CI pipeline fail and cannot merge without fixing or
  explicitly waiving the failure.
- **SC-008**: The `BUILD.md` runbook is validated by a CI job that
  executes every documented step verbatim on a clean VM image matching
  the reference-host stanza and fails the pipeline if any step does
  not produce its documented output, and by at least one peer
  walkthrough on a clean VM that produces a running, observable
  gateway match in one sitting before the feature is marked complete.
  Silent drift between the runbook and the repo is caught by the CI
  job; wording / assumption gaps a script cannot detect are caught by
  the peer walkthrough.

## Assumptions

- Validation runs on the reference Linux x86_64 host the maintainer
  has available. The `spring-headless` at
  `/home/developer/.local/state/Beyond All Reason/engine/recoil_2025.06.19/spring-headless`
  is the canonical engine binary for this feature until the project
  documents a different one.
- vcpkg manifest mode with the existing `vcpkg.json` baseline is the
  dependency resolution strategy. No switch to distro packages or
  submodules is contemplated here.
- The CI platform is GitHub Actions, consistent with the `.github/workflows/ci.yml`
  scaffolded in feature 001 task T104. The runner topology is hybrid:
  GitHub-hosted runners for fast/non-engine jobs, and at least one
  self-hosted runner with the BAR engine + asset cache for the
  headless and latency-bench jobs. Provisioning the self-hosted
  runner (setup scripts, asset cache location, runner-label
  convention) is in scope for this feature if one is not already
  available.
- Extending `AICommand` coverage from 15 wired arms to the full 66
  declared in `proto/highbar/commands.proto` is an engine-side
  plumbing exercise. The necessary `springai::*` OOA callback surfaces
  exist in the CircuitAI base layer (per 001 task T057 notes); no
  upstream BARb patches are assumed.
- The `UnitDamaged` payload widening (FR-014) requires a surgical
  upstream-shared edit in `CCircuitAI`, scoped the same way 001's
  T018 was. This is within the Constitution I envelope.
- All six 001 user stories (US1–US6) and both transport modes (UDS,
  TCP) are in scope for live validation. None are deferred.
- Clients are validated against the BAR game domain (maps, unit defs,
  ownership model). Cross-game portability is not in scope.
- No new top-level or service-level proto messages are introduced by
  this feature, and no existing field numbers are reused or retyped.
  The existing `highbar.v1` schema is sufficient at the envelope
  layer — the `Hello` handshake version string stays at `highbar.v1`.
  All 66 `AICommand` oneof arms and their nested leaf-message types
  are already declared in `proto/highbar/commands.proto`; the feature
  wires them up in the dispatcher rather than adding to the schema.
  The one genuinely additive schema change is that the gateway starts
  populating four previously-zero-valued fields inside the existing
  `UnitDamagedEvent` message (damage, direction, weapon_def_id,
  is_paralyzer); this is populate-only, backward-compatible per
  Constitution III, and does not bump the schema version. See
  research.md §R3 for the full reconciliation.
