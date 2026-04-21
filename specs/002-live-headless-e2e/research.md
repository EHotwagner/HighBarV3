# Research: Live Headless End-to-End

**Feature**: 002-live-headless-e2e
**Date**: 2026-04-21
**Status**: Complete

This document records the research that resolves every technical
unknown raised by the plan's Technical Context and the spec's five
clarification questions. Format follows Spec Kit convention:
**Decision / Rationale / Alternatives considered**.

Ground truth for the "current state" statements below comes from a
direct survey of the 001-landed tree on 2026-04-21 — file paths and
line numbers are cited inline.

---

## R1. spring-headless binary pin

**Unknown**: FR-004 requires the build to record *which specific*
`spring-headless` release it was validated against and provide a
reproducible path. Nothing in the 001 tree pins this today — the
quickstart refers generically to `spring-headless matching BARb's
target commit`, and the reference path is only mentioned in the 002
spec's Assumptions section.

**Decision**: Pin the reference engine as
**`recoil_2025.06.19`** installed at
`$XDG_STATE_HOME/Beyond All Reason/engine/recoil_2025.06.19/spring-headless`
(default `$HOME/.local/state/...`). Record the pin in a checked-in
stanza: `data/config/spring-headless.pin` with fields `release_id`,
`sha256`, and an acquisition URL (BAR's engine CDN mirror). CMake
reads the stanza in a new `configure_file`-driven header so the plugin
can log the release it was built against on load. CI's self-hosted
runner provisioning script (see R2) consumes the same stanza to
hydrate the binary cache.

**Rationale**: `recoil_2025.06.19` is the release the reference host
already runs and is the concrete binary the spec's Assumption names.
A checked-in pin is the lightest-weight mechanism that satisfies
FR-004's reproducibility requirement without coupling the build to a
package manager that isn't in scope here. Tracking the SHA256 gives
the CI runbook-validation job something to compare against when it
hydrates the cache.

**Alternatives considered**:

- *Submodule the engine source.* Rejected: BAR's engine is a 400MB
  tree with its own build discipline; V3 is a plugin, not an engine
  fork. The constitution's fork discipline (principle I) explicitly
  contains only CircuitAI, not the engine.
- *Package engine via vcpkg or distro.* Rejected: `spring-headless`
  is not available via either channel and would require a custom
  port. Out of scope for this feature.
- *Leave the pin implicit (whatever the reference host has).*
  Rejected: the spec's entire premise is that "works on the reference
  host" must become "reproducible from a documented runbook"; implicit
  pins defeat that.

---

## R2. CI runner topology

**Unknown**: The spec's clarification answer commits to a hybrid
topology (GitHub-hosted for most jobs, self-hosted for headless +
bench). Mechanics of that split — runner labels, provisioning
scripts, asset caching — are unresolved. The 001 workflow at
`.github/workflows/ci.yml` runs every job on `ubuntu-22.04` and
relies on an optional `vars.SPRING_HEADLESS` for the engine-dependent
jobs (lines 122, 145).

**Decision**: Adopt a two-label split.

- Jobs `proto`, `cpp-build`, `cpp-unit-tests`, `fsharp`, `python`,
  `lint` run on `runs-on: ubuntu-22.04` (GitHub-hosted).
- Jobs `headless-acceptance`, `bench-latency`, `runbook-validation`
  run on `runs-on: [self-hosted, Linux, X64, bar-engine]` — the
  `bar-engine` label advertises availability of `spring-headless` and
  the cached BAR asset set.
- A runner missing either the binary pin from R1 or the asset cache
  *fails* its jobs loudly at startup (a pre-flight step asserts both);
  it does not silent-skip. This mirrors the constitution's
  "fail-closed on internal faults" posture.

Provisioning lives under a new `.github/runner-setup/` directory
containing: `install-spring-headless.sh` (consumes R1's pin stanza),
`hydrate-bar-assets.sh` (minimum asset set named and sourced from
BAR's asset CDN), `register-runner.sh` (GitHub runner registration
with the `bar-engine` label).

**Rationale**: Labels are GitHub's built-in mechanism for this
two-tier partitioning; they don't require a third-party scheduler.
Making the runner's pre-flight *assert* the assets (rather than
tolerate their absence) is what closes the "CI green because
everything skipped" failure mode that hid 001's integration gap. The
provisioning scripts are needed because no self-hosted runner exists
yet on the reference host (spec Assumption calls this out as in
scope).

**Alternatives considered**:

- *GitHub-hosted runners only, with `spring-headless` installed at
  runtime.* Rejected: `spring-headless` is ~200MB + asset cache
  easily 4GB. Fetching on every CI run is both slow and a reliability
  liability. A single hit on the BAR CDN outage would red the
  pipeline for unrelated reasons.
- *Matrix on multiple self-hosted runners.* Rejected: one runner is
  enough for this feature's concurrency (single-match,
  single-AI-slot). Matrix adds operational surface that isn't earned.
- *Skip the self-hosted runner, gate engine-dependent jobs behind a
  manual approval step.* Rejected: that is exactly the "skip silently"
  pattern FR-018 forbids.

---

## R3. `AICommand` arm count reconciliation

**Unknown**: The 001 plan and the initial draft of this spec both
cited a 97-arm target. A direct survey of the landed proto (both
HighBarV3 and HighBarV2 — the claimed source of the 001 count)
found exactly **66** oneof arms declared under `AICommand.command`.
The HighBarV2 proto tree does *not* contain an additional 31 arms
waiting to be transliterated — that premise was wrong. The
dispatcher (`src/circuit/grpc/CommandDispatch.cpp` lines 91–173)
wires 15 of those 66 and log-and-skips the remaining 51 at the
`default:` case (lines 175–183).

**Decision**: Pin this feature's scope to the real in-repo count of
**66 arms**. Spec FR-012/FR-013/SC-004 and plan Scope are updated
accordingly. No proto extension is required; the work is pure
dispatcher wiring (51 arms) plus per-arm acceptance coverage for all
66.

The "97" figure is retired from spec/plan/tasks. If future work
surfaces genuine proto gaps (e.g., new engine callbacks without a
corresponding proto arm), those are scoped into a separate feature
with its own clarification round — not folded into 002 after the
scope is pinned.

The schema-version string at the `Hello` handshake does not change.
Constitution III is satisfied trivially (no schema edits at the
oneof layer; only the `UnitDamagedEvent` populate-only widening).

**Rationale**: The earlier draft of this section argued that "97"
represented product intent and should override the in-repo count.
That argument depended on a factual claim (HighBarV2 has the missing
31) that does not hold up. Without that premise, "97" has no
anchor — committing to it would require designing 31 arms from
scratch, which is a much larger piece of work than "wire the
existing 51". The honest scope is 66.

Per-arm acceptance tests map each arm to one of three observability
channels:

1. **State-stream-observable** (movement, build, attack, repair,
   reclaim, etc.): the arm's effect appears as a `DeltaEvent` within
   3 engine frames.
2. **Engine-log side-channel** (chat, some drawing, some Lua calls):
   the arm causes a specific log line the acceptance script `grep`s
   from the engine's stdout (BAR's engine log is line-oriented and
   stable).
3. **Lua widget / in-memory hook** (draw markers, figures, some
   transport internals): the acceptance script attaches a BAR Lua
   widget that records a call record accessible via `InvokeCallback`;
   the script asserts on the record.

The mapping is recorded in
`contracts/aicommand-arm-map.md` (Phase 1 artifact).

**Alternatives considered**:

- *Keep the 97 commitment and design 31 new arms from scratch.*
  Rejected: the clarification that locked in "97" was predicated on
  the false belief that those arms already existed in HighBarV2.
  Once the premise fails, the commitment has no anchor — designing
  31 arms from scratch is a separate, larger piece of work.
- *Bump schema version and do a full `highbar.v2`.* Rejected:
  unnecessary. No schema changes at the oneof layer are in scope.

---

## R4. Gateway fault-capture pattern at the IModule boundary

**Unknown**: FR-023/FR-024 require the gateway to catch every
exception that escapes a gRPC handler, state serializer, transport
I/O call, or CircuitAI callback, transition to a disabled state, and
expose that state to acceptance scripts. The current
`src/circuit/module/GrpcGatewayModule.cpp` ctor (lines 63–106)
catches and rethrows; `OnFrameTick` (lines 288–317) has no
`try/catch`; no disabled state exists.

**Decision**: Implement fault capture as a uniform wrapper pattern.

- Add a `GatewayState` enum to `GrpcGatewayModule.h`:
  `Healthy` → `Disabling` → `Disabled` (one-way transition).
- Every IModule hook method (`OnUnitCreated`, `OnUnitDamaged`,
  `OnUnitDestroyed`, `OnFrameTick`, `OnEnemyEnterLOS`, etc.) gets
  a top-level `try { … } catch(const std::exception& e) {
  TransitionToDisabled("handler.<name>", e.what()); }` wrapper.
- `TransitionToDisabled(subsystem, reason)` is idempotent: logs the
  structured `[hb-gateway] fault` line (format in
  `contracts/gateway-fault.md`), closes all subscriber streams,
  unlinks the UDS socket, deletes `$writeDir/highbar.token`, writes
  a `$writeDir/highbar.health` file with `status=disabled` plus the
  originating subsystem and reason, and sets the state flag atomically.
  After transition, every hook is a no-op (returns 0).
- The gRPC async handlers run on worker threads, not the engine
  thread — they are wrapped at the service-impl level
  (`src/circuit/grpc/HighBarService.cpp`) with the same pattern, but
  the actual state transition is deferred to the next engine-thread
  frame via the existing command queue mechanism (Constitution II).
- Serialization code (`SnapshotBuilder.cpp`) runs under the shared
  lock from worker threads (per 001's design); its fault wrapper
  marks the worker's CQ completion as failed and enqueues a transition
  request to the engine thread.

**Rationale**: A single pattern applied uniformly is less
error-prone than per-callsite bespoke handling. Routing transitions
through the engine thread respects Constitution II without
compromise. Writing both a health file *and* unlinking the socket
gives acceptance scripts two orthogonal signals (file presence +
connect failure), so a test can't silently pass by probing only one.
The token-file removal ensures any surviving client retrying
`SubmitCommands` cannot succeed on a post-fault gateway.

**Alternatives considered**:

- *Crash the plugin on any internal fault.* Rejected: the spec
  explicitly forbids this — the engine and the plugin's own
  CircuitAI logic must continue.
- *Catch but continue running the gateway (no disabled state).*
  Rejected: for any non-trivial fault (corrupt state, OOM mid-
  serialization), continuing hides the root cause and produces
  cascading failures. Fail-loud-once beats fail-silently-forever.
- *Expose the disabled state via a new gRPC status endpoint.*
  Rejected: the fault might be in the transport layer itself, in
  which case the status endpoint is unreachable. A filesystem signal
  is resilient to that class of failure.

---

## R5. Runbook validation on clean VM (SC-008)

**Unknown**: The spec's Clarification Q3 fixes the measurement
method for SC-008 (a CI job executes `BUILD.md` verbatim on a clean
VM image plus one peer walkthrough). Implementation details — what
"clean VM", how "verbatim", how to diff output against documented
expectations — are unresolved.

**Decision**: Use a GitHub Actions job that runs on a fresh
`ubuntu-22.04` GitHub-hosted runner (each run gets a clean ephemeral
VM by definition). Represent `BUILD.md` as a literate runbook: each
numbered step is a fenced bash block with a `# expect: …` line that
pins the expected output substring. A small driver script
(`tests/headless/build-runbook-validation.sh`) parses the markdown,
runs each block, and fails if the block's actual output does not
contain the `expect:` substring.

The peer walkthrough is tracked as a pre-merge checklist item:
`specs/002-live-headless-e2e/checklists/peer-walkthrough.md` (to be
generated by `/speckit.checklist`). The feature is not complete
until one entry there is ticked.

**Rationale**: GitHub-hosted runners are already an ephemeral, clean
VM per job — no separate VM provisioning is needed. Parsing a
literate markdown document is lighter-weight than running the real
commands against a recorded transcript. The `# expect: …` convention
keeps the validation coupled to the document itself, so drift between
the doc and the scripts produces an immediate red pipeline.

**Alternatives considered**:

- *Use a dedicated VM image (Packer / QEMU / Vagrant).* Rejected: a
  GitHub-hosted runner already gives us clean-slate per-run, without
  the operational overhead of maintaining an image.
- *Freeform runbook, no CI check.* Rejected: explicitly the failure
  mode the spec's clarification addresses.
- *Full end-to-end: the validation job also launches the match.*
  Rejected: that is a job for the self-hosted runner
  (`headless-acceptance`); runbook validation is GitHub-hosted on the
  Build side, and its exit criterion is "BUILD.md produces a plugin
  binary and leaves the maintainer at the point where `us1-observer.sh`
  could run" — not running `us1-observer.sh` itself.

---

## R6. Python client import-path reconciliation

**Unknown**: `clients/python/highbar_client/commands.py` (lines 17–22),
`session.py` (line 21), and `state_stream.py` (line 18) all import
from `.highbar.v1` — a subpackage the documented codegen
(`clients/python/README.md` lines 13–17, using `grpc_tools.protoc
--python_out=highbar_client …`) does not produce; stubs land in
`.highbar` (no `v1`). `pytest` collection fails at `test_ai_role.py`
for that reason. There are two credible fix directions.

**Decision**: **Align the codegen to the imports**, not the other
way around. Extend the Python codegen step to emit the `v1`
subpackage by passing `--python_out=highbar_client/highbar/v1
--grpc_python_out=highbar_client/highbar/v1` along with adjustment
to proto `import` paths / `package` statements so the generated
files resolve each other correctly. Introduce a
`clients/python/codegen.sh` (or an equivalent `make` target) that
is callable from the repo root with a single command and runs as
part of the Python job in CI.

**Rationale**: The `.highbar.v1` import shape matches the `highbar.v1`
proto package statement and matches the F# client's namespace
(`HighBar.Proto.V1`), so the code is internally consistent with a
schema-versioned layout. The alternative — stripping `v1` from the
Python imports — breaks that consistency and leaves us with no place
to evolve when a future schema version arrives. The buf-based
workflow (the C++ and F# path) already uses versioned packages; the
Python path is the odd one out today, and it's cheaper to align it
once than to keep two shapes.

**Alternatives considered**:

- *Strip `.v1` from the Python imports.* Rejected for the
  consistency reason above.
- *Regenerate with `buf` instead of `grpc_tools`.* Rejected as
  out of scope here — the buf config is already used for C++/F#;
  migrating the Python codegen to buf is a larger change that would
  need its own spec/plan if we want the toolchain unified. It can
  happen later without breaking this feature's fix.

---

## R7. UnitDamaged richer signature routing

**Unknown**: FR-014 requires the gateway's `UnitDamaged` delta to
carry `damage`, `direction`, `weapon_def_id`, `is_paralyzer`. These
fields are already declared in `proto/highbar/events.proto` lines
86–93 but the gateway only populates `unit_id` and `attacker_id`
(`GrpcGatewayModule.cpp` lines 169–182). The limitation is at the
IModule interface: `IModule::UnitDamaged(unit, attacker)` does not
carry the richer signature. The richer signature lives on
`CCircuitAI::UnitDamaged(unit, attacker, damage, direction,
weaponDefId, paralyzer)`.

**Decision**: Add a bespoke entry point
`CGrpcGatewayModule::OnUnitDamagedFull(unit, attacker, damage, dir,
wdefId, paralyzer)` and call it from `CCircuitAI::UnitDamaged` after
the existing module fanout. The existing `IModule::UnitDamaged` hook
is kept as a no-op for safety (preserves IModule compliance for the
gateway), but the richer entry point is the one that populates the
delta. The edit to `CircuitAI.cpp` is ~4 lines and mirrors 001's
T018 pattern — the constitution's fork-discipline budget for
upstream-shared edits explicitly permits this shape.

**Rationale**: The alternative — broadening `IModule::UnitDamaged`
itself — would force a change visible to every module, not just the
gateway, and would break encapsulation. A bespoke per-module entry
point keeps the surface minimal and mirrors how CircuitAI already
exposes richer signatures where the base `IModule` interface is too
narrow.

**Alternatives considered**:

- *Broaden `IModule::UnitDamaged`.* Rejected above.
- *Compute `damage`/`direction`/`weapon` in the gateway by re-querying
  the engine after the hook.* Rejected: the values the engine
  delivered in the original event are the authoritative ones; any
  reconstructed value would diverge under simultaneous damage from
  multiple sources. Also: Constitution V's latency budget is measured
  from engine event → F# `OnEvent`; reconstructing would push
  serialization off the hot path and invalidate the measurement.

---

## R8. CI skip-reason footer grammar

**Unknown**: FR-018 requires the pipeline to fail on any
exit-77-skip unless the commit carries an explicit `ci-skip-reason:`
footer. The footer grammar and where the CI config reads it are
unresolved.

**Decision**: Recognize a single trailer on the HEAD commit
message (git-interpret-trailers form, case-insensitive key):

```
ci-skip-reason: <script-name> — <free-text justification>
```

Each line in the trailer names one headless script by its basename
(no directory). The CI driver reads the trailer via `git log -1
--format=%B | git interpret-trailers --parse`. Any script that exits
77 whose basename is not explicitly listed in the trailer set fails
the pipeline. The trailer expires per-commit — merging into master
does not preserve a waiver.

**Rationale**: Using `git interpret-trailers` is the same mechanism
the Linux kernel and Git itself use for commit metadata; it's
well-understood and robust to merge commits (trailers on the final
commit win). Per-script granularity means a partial outage (one
script's dependency missing) doesn't require waiving all of them,
and listing the script name explicitly in the commit message makes
the waiver grep-able in history.

**Alternatives considered**:

- *Blanket `[skip-ci]` tag.* Rejected: too coarse; it allows any
  script to silent-skip, defeating the purpose.
- *Waivers in a committed YAML file.* Rejected: waivers become
  stickier than the commit that introduced them, and the "short-lived"
  requirement in the spec's US6 description is harder to enforce.
- *Pipeline failure with manual-approval override.* Rejected:
  same pathology as the "GitHub-hosted only with manual approval"
  pattern under R2 — a human-in-the-loop waiver is exactly what the
  spec is trying to avoid.

---

## R9. Deterministic framerate bench (FR-008)

**Unknown**: `tests/headless/us1-framerate.sh` lines 35–36 mark the
harness TODO; no deterministic seed is in place. FR-008 requires a
deterministic seed and reproducibility within 5% variance run-to-run.

**Decision**: Use a fixed BAR start script with explicit
`gameseed = 0x42424242` (`game { gameseed = ... }` block). Use a
fixed map (`Red Comet v1.8`, the smallest canonical BAR map in the
reference asset cache). Run two matches per invocation — baseline
(no observer) and under-test (four observers) — each for a fixed
frame count (9000 frames ≈ 5 minutes at 30fps) and compare. Accept
the baseline if five consecutive runs on the reference host produce
p50 framerates within 5% of each other.

**Rationale**: BAR's engine accepts `gameseed` in the start script
and that's the standard way to pin RNG-driven unit-defs and AI
decisions. Five-run reproducibility within 5% is the gate the spec
calls out for "deterministic"; any smaller variance would require
us to model thermal / scheduler noise, which is out of scope.

**Alternatives considered**:

- *Synthetic frame generator (no engine run).* Rejected: FR-008 is
  about measuring a real match. A synthetic frame source would pass
  the number but miss any real regression.
- *Larger map / longer run.* Rejected: the 5-minute run is already
  slow to execute per CI pass; adding more doesn't improve the
  signal meaningfully.

---

## R10. AICommand coverage-report mechanization

**Unknown**: FR-013 requires an enumerable per-arm coverage report
(66 rows, each naming the arm, its test file, and the assertion).
Mechanics (who produces it, when, how it is consumed) were not
fixed in the spec.

**Decision**: Every acceptance script under `tests/headless/`
declares its per-arm assertions via a `# arm-covered: <arm_name>`
comment-line header. A CMake custom target
`aicommand-arm-coverage` walks all headless scripts, parses those
headers, enumerates every `AICommand` oneof arm from the proto
(via `buf`'s introspection), and emits a CSV report at
`build/reports/aicommand-arm-coverage.csv`. CI uploads the CSV as
a pipeline artifact and fails if any arm has zero covering scripts.

**Rationale**: Keeping the annotation on the acceptance script
itself — rather than in a separate coverage-manifest file — prevents
drift between what the script asserts and what the report claims it
covers. The CMake target is the right home because it already runs
codegen and has the proto introspection available.

**Alternatives considered**:

- *Manual coverage matrix in markdown.* Rejected: drifts fast, no
  enforcement.
- *Test-framework annotation (pytest mark / gtest label).* Rejected:
  most of the coverage lives in headless bash scripts, not pytest or
  gtest. A bash-script annotation is the lowest common denominator.

---

## All "NEEDS CLARIFICATION" items resolved

No unresolved clarifications remain in the plan. All decisions above
are actionable by `/speckit.tasks` and carry forward into the Phase 1
data-model, contracts, and quickstart artifacts.
