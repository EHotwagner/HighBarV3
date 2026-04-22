# Data Model: Live Headless End-to-End

**Feature**: 002-live-headless-e2e
**Date**: 2026-04-21

The 002 spec introduces few new data entities and mostly refines the
ones 001 defined. This document records only the entities this
feature adds or changes — entities already specified by 001
(StateSnapshot, StateDelta, AuthToken, Subscriber ring, etc.) are
unchanged and are not duplicated here.

---

## 1. `UnitDamagedEvent` — widened payload

**Status**: field schema already present in `proto/highbar/events.proto`
lines 86–93; this feature makes the gateway actually populate the
four fields that are currently zero-valued.

**Fields** (unchanged proto):

| Field | Type | Source (after 002) | Current state (001) |
|---|---|---|---|
| `unit_id` | `int32` | `unit->GetId()` | populated |
| `attacker_id` | `optional int32` | `attacker->GetId()` if non-null | populated |
| `damage` | `float` | engine `EVENT_UNIT_DAMAGED.damage` | **zero — 002 populates** |
| `direction` | `Vector3` | engine `EVENT_UNIT_DAMAGED.dir` | **zero — 002 populates** |
| `weapon_def_id` | `int32` | engine `EVENT_UNIT_DAMAGED.weaponDefId` | **zero — 002 populates** |
| `is_paralyzer` | `bool` | engine `EVENT_UNIT_DAMAGED.paralyzer` | **false — 002 populates** |

**Validation rules**:

- `damage >= 0.0f`. Negative damage is an engine-side bug; the
  gateway logs a structured warning and clamps to 0 rather than
  propagating the negative.
- `weapon_def_id >= 0`. Unknown-weapon events (engine reports -1) are
  emitted verbatim — clients decide how to treat them.
- `direction` is the 3-vector the engine hands the event, not
  recomputed. A zero vector is legal when the engine reports
  unattributed damage with no direction.

**Source of truth**: The richer fields enter the gateway via the new
`CGrpcGatewayModule::OnUnitDamagedFull` entry point, called from the
one surgical edit in `src/circuit/CircuitAI.cpp::UnitDamaged`. See
research.md §R7.

**Why this matters for the rest of the feature**: The latency bench
(SC-005, Constitution V) measures `UnitDamaged → F# OnEvent` round
trip. With these fields zero, the bench is measuring something that
isn't semantically a damage event; a client could reasonably drop
such events as malformed, making the "true engine-event → client
round trip" property the constitution demands unverifiable.

---

## 2. `GatewayState` — runtime health state

**Status**: New enum; no proto representation. Consumed only inside
`CGrpcGatewayModule`.

**States** (monotonic transitions; no state is re-entered):

```
Healthy ──► Disabling ──► Disabled
```

| State | Meaning | Observable effects |
|---|---|---|
| `Healthy` | Normal operation. Accepts subscribers, serves deltas, dispatches commands. | Token file present, socket bound, no health file or health file contains `status=healthy`. |
| `Disabling` | Transition in progress on the engine thread. Set atomically at the start of `TransitionToDisabled`. | Between here and `Disabled`, incoming gRPC calls are rejected with `UNAVAILABLE`. |
| `Disabled` | Terminal for the match. All hooks are no-ops, engine + CircuitAI continue. | Socket unlinked, token file removed, health file present with `status=disabled`, `subsystem=<one-of>`, `reason=<code>`. |

**Transition trigger**: any caught exception in a gRPC handler, a
serializer, a transport I/O call, or a CircuitAI hook method.
Transition always runs on the engine thread (worker-thread faults
enqueue a transition request through the existing command queue).

**Transition side effects** (ordered — executed atomically from the
engine thread):

1. Write the structured `[hb-gateway] fault` log line (format in
   `contracts/gateway-fault.md`).
2. Close every active subscriber stream with gRPC status
   `UNAVAILABLE` and trailing metadata `highbar-fault-subsystem`
   + `highbar-fault-reason`.
3. Unlink the UDS socket (`unlink(socket_path_)`).
4. Remove `$writeDir/highbar.token`.
5. Write `$writeDir/highbar.health` (format: single JSON object, see
   contracts/gateway-fault.md).
6. Set `GatewayState = Disabled` with release semantics.

**Why the ordering matters**: Acceptance scripts (see
`tests/headless/gateway-fault.sh`) may check in any of three places
— socket presence, health file contents, stream trailers. If the
health file were written before the socket was unlinked, a script
that races between steps could see an inconsistent state. The
ordering above guarantees every externally-observable signal agrees.

**Validation rules**:

- No transition back to `Healthy` in the same match. A match that
  hits `Disabled` must end and be restarted. Simpler than a
  re-enabling state machine and matches the spec's intent (FR-023:
  "disabled for the remainder of the match").
- `subsystem` is one of `transport | serialization | dispatch |
  callback | handler`; no free-text subsystem names.
- `reason` is a short stable code (e.g. `oom`, `malformed-frame`,
  `rpc-internal`, `engine-callback-threw`), not free-text. The
  mapping from C++ exception types to reason codes is owned by
  `src/circuit/grpc/Log.cpp::LogFault`.

---

## 3. `AICommandArmCoverage` — per-arm acceptance report

**Status**: New build-time artifact. Not a runtime entity.

**Format**: CSV at `build/reports/aicommand-arm-coverage.csv`,
regenerated by the `aicommand-arm-coverage` CMake target each build.
One row per arm in the `AICommand` oneof from
`proto/highbar/commands.proto`.

**Columns**:

| Column | Description |
|---|---|
| `arm_name` | The proto oneof field name (e.g. `move_unit`, `patrol`, `draw_line`). |
| `arm_field_number` | The proto field number. Stable across builds once assigned. |
| `dispatcher_wired` | `true` if `src/circuit/grpc/CommandDispatch.cpp` has a `case` for this arm that calls a `springai::*` or `CCircuitUnit::Cmd*` entry; `false` otherwise. |
| `observability_channel` | `state-stream` \| `engine-log` \| `lua-widget`. See research.md §R3. |
| `covering_scripts` | Comma-separated list of `tests/headless/*.sh` basenames whose `# arm-covered:` header lists this arm. |
| `assertion_count` | Total number of distinct assertions across the covering scripts. |

**Validation rules** (enforced by the CMake target, which exits
non-zero on any violation):

- `dispatcher_wired = false` → build fails (FR-012).
- `covering_scripts` empty → build fails (FR-013).
- `observability_channel = lua-widget` → the named Lua widget file
  must exist under `tests/headless/widgets/` and be listed in
  `tests/headless/widgets/README.md`.

**Why CSV, not YAML/JSON**: Grep-ability from CI logs and from
commit messages. A waiver comment that references a specific arm
row is easier to audit than a structured document would be.

---

## 4. `SpringHeadlessPin` — reference engine binary pin

**Status**: New checked-in stanza at `data/config/spring-headless.pin`.
Consumed by CMake (for a generated-header) and by the CI runner
setup scripts.

**Format**: TOML, single table. Example:

```toml
[engine]
release_id = "recoil_2025.06.19"
sha256 = "<pinned hash>"
acquisition_url = "https://<BAR engine mirror>/recoil_2025.06.19/spring-headless"
install_path_relative = "Beyond All Reason/engine/recoil_2025.06.19"
```

**Fields**:

| Field | Type | Meaning |
|---|---|---|
| `release_id` | string | Human-readable release tag from BAR's engine repo. |
| `sha256` | string | SHA-256 of the installed `spring-headless` binary. |
| `acquisition_url` | string | Where a clean machine can fetch it. |
| `install_path_relative` | string | Path relative to `$XDG_STATE_HOME` (default `~/.local/state`) where the binary is expected. |

**Validation rules**:

- `sha256` is 64 hex chars, lower case. The CI runner-setup script
  re-computes and aborts on mismatch.
- `release_id` matches `recoil_[0-9]{4}\.[0-9]{2}\.[0-9]{2}`.
- The plugin logs both fields at startup (FR-003 observability).

**Why pinned here, not in `vcpkg.json`**: `vcpkg.json` pins C++
library versions; it doesn't have a slot for "runtime binary the
plugin is tested against". Keeping the engine pin in its own tiny
file matches the fork-discipline principle: it sits under `data/`,
which is already owned by V3, and touches no upstream-shared code.

---

## 5. `BuildRunbook` — top-level BUILD.md as a validated entity

**Status**: New file at `/BUILD.md`. Literate runbook format (see
research.md §R5).

**Structural invariants**:

- At most ten numbered steps from heading "## 1." through
  "## 10." (FR-022: "no more than 10 discrete documented steps").
- Every step contains exactly one fenced bash block tagged `bash`.
- Every fenced bash block is preceded (on the line immediately above
  the opening fence) by a `<!-- expect: <substring> -->` comment
  whose substring must appear in the block's stdout on a successful
  run.
- Any deviation from the above (≥11 steps, missing expect comment,
  expect substring not matched) fails `tests/headless/build-runbook-validation.sh`.

**Content contract** (what the ten steps achieve end-to-end):

1. Pre-flight: assert OS version, vcpkg presence, pinned
   `spring-headless`.
2. Submodule / vcpkg bootstrap.
3. `buf generate` for proto.
4. CMake configure with pinned toolchain.
5. CMake build (`libSkirmishAI.so` emitted under `build/`).
6. `ctest` for unit tests.
7. F# client restore + build.
8. Python client codegen + `pip install -e`.
9. Launch `spring-headless` with the minimal BAR start script.
10. Attach the F# observer and confirm one `Snapshot` arrives.

After step 10, the maintainer is at a state where
`tests/headless/us1-observer.sh` can run and report `PASS`.

**Relationship to the 001 quickstart**: `specs/001-grpc-gateway/quickstart.md`
is retained (it is the per-feature 001 design artifact) but edited in
this feature so every command it documents resolves to the same
invocation `BUILD.md` uses. Where they diverge, BUILD.md is the
source of truth.

---

## 6. `CISkipWaiver` — per-commit skip trailer

**Status**: New CI convention. No on-disk artifact beyond the commit
message itself.

**Format** (git-interpret-trailers):

```
ci-skip-reason: <script-basename> — <free-text justification>
```

**Fields**:

- `script-basename` is the `.sh` file basename, case-sensitive (e.g.
  `us1-framerate.sh`).
- `free-text justification` is any Unicode up to 200 chars. Longer
  justifications force a linked tracking issue.

**Validation rules**:

- Multiple trailers permitted per commit (one per skipped script).
- A trailer naming a script that did *not* exit 77 fails the CI run
  (stale waivers don't accumulate).
- Trailers are read from HEAD's commit message only; merge parents
  don't carry the waiver.
- The `cpp-build`, `fsharp`, `python`, and `proto` jobs do not
  accept this waiver — it applies only to `headless-acceptance` and
  `bench-latency`.

**Why on HEAD only**: An in-flight branch waives a script by
amending its tip; once the branch merges, the waiver is part of
history but carries no forward force. This matches the spec's
"short-lived waiver" intent directly.

---

## Relationships summary

```
BuildRunbook ──asserts──► SpringHeadlessPin (step 1 pre-flight)
             ──drives───► (CMake targets, F#/Python builds)

GatewayState ──writes───► health file + fault log line
             ──consumed by──► gateway-fault.sh (headless)

UnitDamagedEvent (widened) ──feeds──► latency-{uds,tcp}.sh
                                    ──feeds──► any acceptance script that
                                                checks damage semantics

AICommandArmCoverage ──checks──► CommandDispatch.cpp (dispatcher_wired)
                    ──checks──► tests/headless/*.sh (# arm-covered: headers)
                    ──asserts all 66 arms are wired and covered────

CISkipWaiver ──gates──► headless-acceptance / bench-latency exit-77 handling
```

No entity in this list carries persistent state across matches. All
are either per-build artifacts (coverage report), per-session runtime
state (GatewayState, UnitDamagedEvent), per-commit metadata
(CISkipWaiver), or long-lived repo files (pin, runbook).
