# Feature Specification: Snapshot-grounded behavioral verification of AICommand arms

**Feature Branch**: `003-snapshot-arm-coverage`
**Created**: 2026-04-21
**Status**: Draft
**Input**: User description: "create specs from the deferred tasks and add behavioral tests for as many commands as possible. movement, build, attack… then create a quick macro build to create and test as many commands as possible. you MUST use actual snapshot gamedata to prove that unit was really created, building build, unit moved…"

## Background

Feature 002 shipped with all 66 AICommand arms wired into the dispatcher and an acceptance grid that proves commands reach the gateway and the gateway acks them. What 002 did **not** prove: that the engine actually *executed* those commands. The current `us2-ai-coexist.sh` checks `SubmitCommands ack=1` and `[cmd-ch] forwarding batch` — both **wire-side** signals. Whether the unit actually moved is unverified, because the delta stream only carries event-driven updates (UnitCreated, UnitDamaged, etc.) and the AI client never polls or diffs `StateSnapshot.own_units[].position`.

This feature closes that gap by introducing **behavioral verification**: every test pairs a command with a snapshot-diff predicate that proves the command had its expected side effect on engine state. It also picks up the 002 deferred backlog (T025 framerate harness, T044/T045 Lua widgets + per-arm coverage script, T068/T069 reproducibility runs) since those are the natural carriers for a behavioral-test suite.

## Clarifications

### Session 2026-04-21

- Q: Per-arm unit provisioning strategy — how does each arm's input-builder get its target unit? → A: **Two-phase bootstrap (no cheats required).** Phase 1 uses the commander to build a fixed prerequisite set (e.g., factory → ground unit, airpad → air unit, radar, mex, builder) to cover the capabilities needed by the 66 arms. Phase 2 iterates the arm registry and dispatches each arm against the appropriate Phase-1 unit (commander for commander-capable arms, factory output for factory arms, etc.). The prerequisite set is codified as a "bootstrap plan" the macro driver executes before the first verify-predicate runs; arms whose required capability is not in the bootstrap plan record `precondition_unmet` in the CSV. Baseline start-script stays cheats-off; the existing `SetGodMode`/cheats-arm skip path (Assumptions §6) is preserved.
- Q: Snapshot throttling behavior when `own_units.length > snapshot_max_units`? → A: **Halve the effective cadence** (e.g., double `snapshot_cadence_frames` — 30→60→120) until `own_units.length` drops back under the cap. Cadence remains predictable just coarser; no truncation, no skip. Default `snapshot_max_units` is raised from **500 → 1000** (tracked in `SnapshotTickConfig`).
- Q: Bit-for-bit reproducibility scope for the coverage CSV? → A: **Bit-exact only for reproducibility-critical columns** — `arm_name`, `dispatched`, `verified`, `error`. The `evidence` column (floating-point deltas, frame-timing strings) is **excluded** from the bit-for-bit check because engine float jitter makes bit-exact evidence unachievable and is not the feature's measurement of interest. The macro driver emits a **`verified_digest`** sidecar artifact — a stable hash (e.g., SHA-256) computed over a canonical serialization of the reproducibility-critical columns across all rows in `arm_name` sort order. US6 compares `verified_digest` values across the five runs; identical digests satisfy FR-012/SC-006.
- Q: Arm-dispatch failure isolation during the macro driver run? → A: **Bootstrap-state reset between arms.** After each arm's verify-predicate resolves (pass, fail, or timeout), the driver restores the Phase-1 bootstrap topology: for any capability unit missing from `own_units`, it reissues the corresponding bootstrap build order and waits (up to a per-capability timeout) for the snapshot to re-match the bootstrap manifest before dispatching the next arm. Budgeted at ~1–3s per arm. This keeps every arm dispatched against the same deterministic topology it would see if it ran first, protecting FR-012 reproducibility from destructive arms (SelfDestruct, Stop, long-range Move) cascading into later rows.
- Q: Python macro driver packaging & invocation? → A: **Extend the existing `clients/python/highbar_client` package** with a new `behavioral_coverage` submodule exposed as a module entry point. The shell wrapper `tests/headless/aicommand-behavioral-coverage.sh` invokes it via `uv run --project clients/python python -m highbar_client.behavioral_coverage`. No new lockfile, no new package — reuses the existing gRPC stubs (`highbar_client.highbar`), channel/session helpers, and `clients/python/pyproject.toml`. Any new Python-only deps (CSV hashing, etc.) land in that existing `pyproject.toml`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Move command verified by snapshot diff (Priority: P1)

A developer or AI-author writes `SubmitCommands(MoveUnit(uid, target_pos))` and wants to know within seconds whether the engine actually moved the unit, not just whether the gateway accepted the batch. The test driver captures `StateSnapshot.own_units[uid].position` before sending the command, dispatches the move, captures another snapshot N frames later, and asserts the position vector changed by at least a configured minimum distance.

**Why this priority**: This is the smallest possible behavioral test and gates every other story. If snapshot-based diffing doesn't work for Move (the most common command), nothing else in this feature is buildable. Move also exercises the full client-mode loop end-to-end (external client → coordinator → plugin → engine → unit → snapshot → coordinator → external client).

**Independent Test**: Run `tests/headless/behavioral-move.sh`. It launches the live coordinator+plugin+spring topology, captures the commander's pre-move position from a snapshot, sends `MoveUnit(commander_id, +500x, 0z)`, waits N=120 frames (~4s), captures another snapshot, and exits 0 iff the commander's position-x grew by at least 100 elmos. Exits 1 on any verification failure with diagnostic output (before/after positions, frames elapsed, log tail).

**Acceptance Scenarios**:

1. **Given** a live match with a commander spawned at position (1024, 0, 1024), **When** an AI client sends `MoveUnit(commander_id, target=(1524, 0, 1024))` and waits 4 seconds, **Then** the next snapshot reports the commander at a position with `x ≥ 1124` (i.e. moved by at least 100 elmos toward the target).
2. **Given** the gateway has acked the move command, **When** the snapshot diff shows zero displacement, **Then** the test fails with output `move not executed: before=(1024,0,1024) after=(1024,0,1024)` and includes the engine log tail for diagnosis.
3. **Given** the commander is destroyed before the post-snapshot fires, **When** the verifier can't find `commander_id` in `own_units`, **Then** the test fails with output `target unit destroyed during test window` (a real failure, not a skip — race conditions are the test's job to surface).

---

### User Story 2 - Build command verified by snapshot diff (Priority: P1)

A developer wants to know whether `BuildUnit(builder_id, def_id, target_pos)` actually causes a new construction site to appear in `own_units` with `under_construction=true` and `build_progress` that advances over time. The test issues the command, then samples snapshots at 0/2/4 second offsets and asserts:
- a new `OwnUnit` with the expected `def_id` appears
- its `under_construction` flag is `true`
- its `build_progress` increases monotonically across the three samples

**Why this priority**: Build is the second-most-common AI primitive. It exercises a different state-mutation path (creates a new entity rather than mutating an existing one) and surfaces the `under_construction` / `build_progress` fields that no current test touches. P1 alongside Move because the two together cover the dominant patterns; if either snapshot-diffing technique fails, the macro driver can't be built.

**Independent Test**: Run `tests/headless/behavioral-build.sh`. Issues `BuildUnit(commander_id, def_id=<armmex>, target=<commander_pos + offset>)`, samples snapshots at t+1s/t+3s/t+5s, exits 0 iff (a) `own_units` count increased by exactly 1 in the t+1s sample, (b) the new unit's `under_construction=true` in t+1s, and (c) `build_progress` strictly increased between t+3s and t+5s.

**Acceptance Scenarios**:

1. **Given** a commander with available metal/energy, **When** the AI client issues `BuildUnit(commander_id, armmex, build_pos)` and waits 5 seconds, **Then** snapshots show `own_units.length` grew by 1, the new unit has `under_construction=true`, and `build_progress` rises across samples.
2. **Given** the build fails (e.g., obstructed terrain), **When** the t+5s snapshot still shows no new construction site, **Then** the test fails with `build not started: unit_count_delta=0 in 5s` and dumps the engine log tail.

---

### User Story 3 - Attack command verified by snapshot diff (Priority: P2)

A developer wants to know whether `AttackUnit(attacker_id, target_id)` actually causes the target's health to decrease. The test spawns or identifies an enemy in line-of-sight, captures the target's `health` from `EnemyUnit.health` in a snapshot, dispatches the attack, waits N seconds, and asserts target health decreased (or the target disappeared, indicating destruction).

**Why this priority**: Attack proves the cross-team mutation path. It's lower than Move/Build because it requires an enemy to be in LOS — a more brittle test setup that depends on map + start positions. Still P2 because attack-class arms are a meaningful fraction of the 66 (Attack, AttackArea, Guard, Patrol with engagement, etc.).

**Independent Test**: Run `tests/headless/behavioral-attack.sh`. Picks any visible `EnemyUnit` from the snapshot, records its `health`, issues `AttackUnit(commander_id, enemy_id)`, waits up to 15 seconds while sampling snapshots, exits 0 iff the target's health dropped by ≥1 hp at any sample point (or the target ID stopped appearing in `enemies_visible` AND a `UnitDestroyed` delta arrived for it).

**Acceptance Scenarios**:

1. **Given** an enemy unit visible at health=4500, **When** the commander attacks it for 15s, **Then** at least one snapshot shows the enemy at health < 4500 OR the enemy disappears from snapshots and a `UnitDestroyed`/`EnemyDestroyed` delta event was observed.
2. **Given** no enemies are in LOS, **When** the test starts, **Then** it exits 77 with `no enemy in LOS — test cannot proceed` rather than failing red.

---

### User Story 4 - Macro arm-coverage driver with side-effect verification (Priority: P1)

A developer runs one command and gets a CSV report scoring how many of the 66 AICommand arms have **proven engine-side effects**, not just gateway-side acks. The driver maintains an internal table mapping each arm to (a) an input builder that constructs a valid command for the current match state, and (b) a verify-predicate that reads `StateSnapshot` (or a delta event) and returns pass/fail. Arms whose side effects are not observable on the wire (e.g., draw-on-minimap, send-chat) are recorded as `not-wire-observable` and excluded from the success rate.

**Why this priority**: This is the headline deliverable. Move/Build/Attack are example anchors; the macro driver is what scales the technique to all 66 arms and produces the coverage metric the project leans on. P1 because without it the per-command tests are isolated proofs and the project still can't say "X% of our command surface is verified."

**Independent Test**: Run `tests/headless/aicommand-behavioral-coverage.sh`. It launches the live topology once, executes the bootstrap plan (commander builds factory/airpad/radar/mex/builder etc. to provision the capabilities the registry requires), then iterates the arm table — for each arm: dispatch the input batch against the appropriate bootstrap-provisioned unit, run the verify-predicate, then perform a bootstrap-state reset (reissue any missing capability unit and wait for the snapshot to re-match the bootstrap manifest) before moving to the next arm. The driver writes `build/reports/aicommand-behavioral-coverage.csv` (columns: `arm_name, category, dispatched, verified, evidence, error`) and its `.digest` sidecar. Exits 0 iff the verified-rate among wire-observable arms meets the configured threshold (default 50%, ratcheted upward as new arms are wired). Both artifacts are uploaded to CI alongside the existing `aicommand-arm-coverage.csv`.

**Acceptance Scenarios**:

1. **Given** the macro driver runs against a live match, **When** it completes, **Then** `aicommand-behavioral-coverage.csv` exists with exactly 66 rows, of which at least 3 (move_unit, build_unit, attack_unit) are marked `verified=true` with non-empty `evidence`.
2. **Given** the verified-rate among wire-observable arms is below the configured threshold, **When** the script exits, **Then** the exit code is 1 and the summary line `behavioral-coverage: <verified>/<wire-observable> below threshold <T>%` is printed.
3. **Given** an arm fails to verify because its input builder was wrong (not because the engine refused), **When** the failure is recorded, **Then** the `error` column distinguishes `dispatcher_rejected` from `effect_not_observed` so the dev can fix the test setup vs. file an engine bug.

---

### User Story 5 - Periodic snapshot tick (infrastructure) (Priority: P1)

For any of the above stories to work, the plugin must emit `StateSnapshot` payloads at a predictable cadence; today snapshots only ride along on the initial `HelloResponse`. This story adds a periodic snapshot tick controlled by a config option (default: every 30 frames ≈ 1 second at 30fps headless), with the existing delta stream continuing to ride between snapshots. The proto carries the necessary fields already (`StateUpdate.payload.snapshot`); only the engine-side scheduler is missing.

**Why this priority**: P1 because every behavioral test consumes snapshots. Without this, US1–US4 cannot exist as built; with this, they all become straightforward.

**Independent Test**: Run `tests/headless/snapshot-tick.sh`. Subscribes via `StreamState`, counts snapshots arriving in a 30-second window, exits 0 iff at least 25 snapshots arrived (allowing slack for the cadence) and each one has `OwnUnit.position` populated. Also asserts the `send_monotonic_ns` field is set on snapshots (for latency budget compatibility).

**Acceptance Scenarios**:

1. **Given** a 30-second observation window, **When** the test counts `StateUpdate` payloads with `payload.kind=snapshot`, **Then** the count is ≥25 and the cadence (max gap between snapshots) is ≤2 seconds.
2. **Given** snapshots are firing, **When** the per-frame Constitution V budget is measured against baseline (no snapshots), **Then** the framerate cost is ≤5% (snapshot serialization is bounded by `own_units.length` and the test match has ≤200 units).

---

### User Story 6 - Reproducibility (five-run consistency for the macro driver) (Priority: P2)

A developer wants confidence the verified-arm set is not flaky. The reproducibility script runs the macro driver five consecutive times with the same start-script and `gameseed`, and verifies that the set of arms marked `verified=true` is identical across all five runs (any arm that flips its verified status between runs is a flaky test that needs investigation). This subsumes 002 deferred tasks T068 (full-suite 5× pass) and T069 (framerate p50 within ±5%).

**Why this priority**: Reproducibility is a quality bar, not a feature gate. P2 because the macro driver itself is more valuable than the consistency proof; consistency without coverage is meaningless.

**Independent Test**: Run `tests/headless/behavioral-reproducibility.sh`. Invokes the macro driver 5×, compares the verified-arm sets, exits 0 iff (a) all five runs have identical verified sets, and (b) p50 framerate stays within ±5% across runs.

**Acceptance Scenarios**:

1. **Given** the macro driver runs five times with identical inputs, **When** the verified sets are compared, **Then** they are identical (zero arms flip).
2. **Given** the five runs report p50 framerates F1…F5, **When** the spread is computed, **Then** `(max(F)-min(F))/median(F) ≤ 0.05`.

---

### Edge Cases

- **Engine never gets to playable frame**: The plugin's gateway can become healthy (heartbeats start) before the engine actually accepts player commands. Tests must wait for the first `OwnUnit` to appear in a snapshot before dispatching, not just for `[hb-gateway] startup`.
- **Commander destroyed mid-test**: Tests must reidentify their target unit from each fresh snapshot rather than caching a `unit_id` and assuming it remains valid. In the macro driver, destructive arms (e.g., `SelfDestruct`, suicidal `Move`) are absorbed by the FR-003b bootstrap-state reset that runs between every arm; subsequent arms always see the bootstrap topology.
- **Snapshot timing race**: A command dispatched at frame F may not be reflected in the snapshot at frame F+1 if the snapshot serializer ran before the command processor that frame. Verify-predicates must allow at least 2 snapshots of slack after dispatch.
- **Build site rejected by terrain**: If `BuildUnit` is dispatched on impassable terrain, no new unit appears. The test must distinguish `dispatcher_rejected` (gateway returns INVALID_ARGUMENT) from `effect_not_observed` (gateway acked but engine quietly rejected).
- **Macro driver run inside fault-disabled gateway**: If a prior test triggered a fault and the gateway is in `Disabled` state, all subsequent dispatches will fail. The macro driver must invoke `_fault-assert.sh::fault_status` at the top and exit 77 if not healthy.
- **Cheats arms in non-cheats match**: `SetGodMode`, `SetEnergyMex`, etc. require `cheats_enabled=true` in the start-script. The macro driver must read the start-script's cheats flag and skip those arms (record `not-wire-observable: cheats-required`) when cheats are off.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The plugin MUST emit `StateUpdate.payload.snapshot` payloads at a configurable cadence (default: every 30 engine frames) when the gateway is in `Healthy` state. Snapshots MUST populate `OwnUnit.position`, `OwnUnit.health`, `OwnUnit.under_construction`, `OwnUnit.build_progress`, and `EnemyUnit.health` for every unit in the team's snapshot at the moment of serialization. When `own_units.length > snapshot_max_units` the plugin MUST halve the effective tick rate (double the frame interval, e.g. 30→60→120) for that tick cycle and continue halving on each subsequent tick while the cap is exceeded; cadence returns to baseline as soon as the unit count drops back under the cap. The plugin MUST NOT skip snapshots entirely and MUST NOT truncate `own_units[]`. The degraded cadence MUST be surfaced to clients via a `StateSnapshot.effective_cadence_frames` field so test drivers can adapt their wait-windows deterministically.
- **FR-002**: Each behavioral test MUST express verification as a function `verify(snap_before, snap_after, dispatched_command) → (verified: bool, evidence: string)`. Evidence strings MUST be human-readable and include the specific delta (e.g., `position dx=503.2 dz=0.0`, `unit_count_delta=+1 new_def=armmex under_construction=true`).
- **FR-003**: The macro driver MUST maintain a registry mapping each of the 66 arm names to (a) an input-builder function that produces a valid `AICommand` given the current match state, (b) a verify-predicate as in FR-002, and (c) a `required_capability` tag (e.g., `commander`, `factory_ground`, `factory_air`, `builder`, `mex`, `radar`, `cloakable`). Arms with no wire-observable side effect (per FR-005 below) MUST register the sentinel `verify=not-wire-observable` and be excluded from the success-rate metric.
- **FR-003a**: The macro driver MUST execute a deterministic **bootstrap plan** before dispatching any arms under test. The bootstrap plan issues commander build orders that produce, at minimum, one instance of each `required_capability` tag registered by at least one wire-observable arm. The plan MUST complete (or time out) before Phase 2 dispatches begin. Arms whose `required_capability` is not produced by the bootstrap plan MUST record `precondition_unmet` in the CSV's `error` column (dispatched=false, verified=na) and be excluded from the success-rate denominator.
- **FR-003b**: Between each arm's verify-predicate resolution and the next arm's dispatch, the macro driver MUST perform a **bootstrap-state reset**: diff the current `own_units` against the bootstrap manifest, reissue bootstrap build orders for any missing capability unit, and block until the snapshot re-matches the manifest OR a per-reset timeout (default 10s) elapses. On reset timeout the driver MUST abort the remainder of the run and mark all undispatched arms with `error=bootstrap_reset_failed` (dispatched=false, verified=na); the run still emits a complete 66-row CSV and a digest. The reset sequence MUST be fully deterministic given the gameseed so FR-012 reproducibility holds regardless of which arm ran last.
- **FR-004**: The macro driver MUST output a CSV report at `build/reports/aicommand-behavioral-coverage.csv` with columns: `arm_name, category, dispatched (bool), verified (bool|na), evidence (string), error (string)`. The CSV MUST contain exactly 66 rows (one per arm), regardless of how many were dispatched in this run. Rows MUST be emitted in ascending `arm_name` (case-sensitive) sort order so that textual diffs are meaningful across runs.
- **FR-004a**: Alongside the CSV the macro driver MUST emit a sidecar digest artifact `build/reports/aicommand-behavioral-coverage.digest` containing a single SHA-256 hex string computed over a canonical serialization of the reproducibility-critical columns (`arm_name, dispatched, verified, error`) across all 66 rows in the same sort order as the CSV. The digest MUST NOT include the `category` or `evidence` columns. This digest is the authoritative input to the reproducibility check (FR-008/FR-012).
- **FR-005**: An arm is "wire-observable" iff its side effect is either (a) reflected in the next `StateSnapshot.own_units[]` / `enemies_visible[]` for any field, or (b) emitted as a `DeltaEvent` other than `unit_idle` or `command_finished`. Lua-only side effects (draw-on-minimap, in-game chat, custom widgets) are explicitly NOT wire-observable in this feature's scope; they are deferred to a follow-up that ships BAR Lua widgets and `InvokeCallback` plumbing.
- **FR-006**: The plugin MUST include a `RequestSnapshot` RPC on `HighBarProxy` that triggers an immediate out-of-cadence snapshot for the calling client's session. This is the test driver's escape hatch when it cannot afford to wait for the next periodic tick. The implementation MUST coalesce repeat requests (one extra snapshot per engine frame regardless of caller count) so a flood of requests cannot DoS the engine thread.
- **FR-007**: The acceptance script `tests/headless/aicommand-behavioral-coverage.sh` MUST exit 0 iff `verified_count / wire_observable_count >= threshold`, where `threshold` defaults to `0.50` and is overridable via env var `HIGHBAR_BEHAVIORAL_THRESHOLD`. CI MUST set the threshold to `0.50` initially and ratchet upward in subsequent commits as more arms gain verification.
- **FR-008**: The reproducibility script MUST run the macro driver five consecutive times with deterministic inputs (`gameseed = 0x42424242`), compare the `verified_digest` values emitted by each run (per FR-004a), and exit non-zero if any digest differs. On mismatch, the script MUST also surface a per-arm diff of the reproducibility-critical columns (`arm_name, dispatched, verified, error`) to localize the flaky arm(s).
- **FR-009**: The framerate reproducibility check (folded in from 002 T069) MUST capture p50 framerate from each of the five reproducibility runs and assert `(max - min) / median ≤ 0.05`.
- **FR-010**: The behavioral-coverage report MUST be uploaded as a CI artifact named `aicommand-behavioral-coverage.csv` (plus its `.digest` sidecar per FR-004a) from the `headless-acceptance` self-hosted job (002's existing `aicommand-arm-coverage.csv` artifact stays as-is — they answer different questions).
- **FR-013**: The macro driver MUST be implemented as a new `behavioral_coverage` submodule inside the existing `clients/python/highbar_client` package, reusing that package's gRPC stubs (`highbar_client.highbar`), channel helpers, and `pyproject.toml`. The shell wrapper `tests/headless/aicommand-behavioral-coverage.sh` MUST invoke it via `uv run --project clients/python python -m highbar_client.behavioral_coverage`. No separate Python package, lockfile, or virtualenv is introduced for this feature.
- **FR-011**: The plugin MUST NOT regress on any existing acceptance script when the snapshot tick is enabled at default cadence. `us1-observer.sh`, `us2-ai-coexist.sh`, and the latency benches MUST continue to pass with snapshot tick on.
- **FR-012**: The behavioral-coverage **digest** (FR-004a) MUST be bit-for-bit identical across runs of the macro driver against the same gameseed. The digest covers the reproducibility-critical columns (`arm_name, dispatched, verified, error`); the `evidence` column is explicitly excluded because engine floating-point jitter makes bit-exact evidence strings unachievable and is not the measurement of interest. Non-determinism in any of the critical columns is a test bug that MUST be fixed in the test, not papered over with retries.

### Key Entities

- **BehavioralTestCase**: One row in the macro driver's arm registry. Holds the arm name, category (Channel A/B/C from 002's contract), `required_capability` tag, input-builder function, verify-predicate, and a free-text rationale for arms registered as `not-wire-observable`.
- **BootstrapPlan**: An ordered list of commander build orders the macro driver issues in Phase 1 to provision the capability units that Phase 2 arms target. Each entry pairs a `def_id` with a `produces_capability` tag; the plan is deterministic (fixed order, fixed positions relative to commander spawn) so reproducibility guarantees (FR-008, FR-012) hold. Plan completion is determined by all expected capabilities appearing in `own_units` OR a per-capability build timeout.
- **SnapshotPair**: A pair of `StateSnapshot` instances captured at frames F and F+N (N configurable per test, default N=120 ≈ 4s at 30fps). The diff between them is the test's evidence.
- **VerificationOutcome**: Result of a verify-predicate. Carries `verified ∈ {true, false, na}`, `evidence` (human-readable string), and `error` (one of: empty, `dispatcher_rejected`, `effect_not_observed`, `target_unit_destroyed`, `cheats_required`, `precondition_unmet`).
- **CoverageReport**: The CSV at `build/reports/aicommand-behavioral-coverage.csv`. 66 rows (one per arm) sorted by `arm_name` ascending, columns as in FR-004, plus a header row. Paired with the sidecar digest `build/reports/aicommand-behavioral-coverage.digest` (FR-004a) which is the authoritative reproducibility input.
- **SnapshotTickConfig**: Plugin-side config exposed via the existing config file (`grpc.json` or equivalent). Fields: `snapshot_cadence_frames` (default 30), `snapshot_max_units` (default **1000**, beyond which the effective cadence is halved per FR-001 to stay within frame budget).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least three commands (`move_unit`, `build_unit`, `attack_unit`) are verified by snapshot diff in CI on every PR — i.e., the gateway-acked command is independently confirmed to have mutated engine state on the wire.
- **SC-002**: The macro driver reports `verified=true` for at least 50% of wire-observable arms on the first CI run after merge, with the threshold ratcheted upward by ≥5 percentage points per follow-up release until ≥80%.
- **SC-003**: The macro driver runs to completion in under 300 seconds on the reference host (one match boot ≈ 15s + bootstrap plan ≤ 90s + 66 arms × [dispatch + verify ≤ 4s + reset ≤ 3s] ≈ 460s worst-case, trimmed by not-wire-observable/cheats-skipped/precondition_unmet rows that incur no dispatch or reset). The bootstrap-plan phase alone MUST complete within 90 seconds or the driver fails fast with `bootstrap_timeout` before Phase 2 begins. Individual bootstrap-state resets MUST honor a 10s per-reset timeout (per FR-003b).
- **SC-004**: Five consecutive runs of the macro driver against the same gameseed produce identical verified-arm sets (zero flaky arms). Framerate p50 stays within ±5% across the five runs.
- **SC-005**: Enabling the periodic snapshot tick at default cadence (30 frames) costs no more than 5% of baseline framerate in the existing `us1-framerate.sh` two-match comparison.
- **SC-006**: The behavioral-coverage `verified_digest` (sidecar of the CSV, FR-004a) is bit-for-bit identical across the five reproducibility runs (any deviation is a test bug). The `evidence` column of the CSV is not required to be identical and is excluded from this check.
- **SC-007**: The 002 deferred backlog (T025, T044/T045, T068/T069) is closed by this feature's user stories: T025 by US6, T044/T045 by US4 (with the "deferred to a follow-up" carveout for Lua-only arms documented in FR-005), T068/T069 by US6.

## Assumptions

- The existing `tests/headless/scripts/minimal.startscript` (Avalanche 3.4, two BARb teams) is acceptable as the baseline test match for all behavioral tests. If specific tests need a different map (e.g., for an attack scenario with guaranteed enemy LOS), they ship their own start-script under `tests/headless/scripts/`. The macro driver (US4) uses this start-script **without cheats** and provisions its target units via the Phase-1 bootstrap plan (FR-003a); cheats arms are still skipped per the existing cheats-flag path documented below.
- BAR's `CCircuitUnit::Cmd*` methods have observable effects within ≤2 seconds at 30fps headless — i.e., a snapshot taken 4 seconds after dispatch will reliably reflect the command's outcome (or definitive non-outcome). This is a working hypothesis to be confirmed in US1.
- The pinned BAR engine (`recoil_2025.06.19` per `data/config/spring-headless.pin`) emits the unit fields populated in `StateSnapshot` correctly. If a field is found to be unreliable (e.g., `build_progress` stale by one frame), the test ships a workaround in the verify-predicate, not a proto change.
- Snapshot tick is acceptable as a periodic push (vs. on-demand request) by default, mirroring the existing PushState pattern. The on-demand `RequestSnapshot` RPC (FR-006) is the escape hatch, not the primary mechanism.
- Lua-only arms (Channel C from 002's contract — draw, chat, message arms) are out of scope for this feature's behavioral verification. They remain on the deferred list and gain verification when 002's T044 BAR Lua widgets are written.
- `SetGodMode` and other cheats arms are tested only when the start-script enables cheats. The macro driver reads the start-script's cheats flag and skips those arms cleanly (recorded as `cheats_required` in the CSV) when cheats are off.
- The reproducibility runs (US6) execute on the bar-engine self-hosted runner, not on hosted CI. This matches the 002 topology — 5× live runs cannot fit in a hosted-runner time budget.
- The 002 deferred tasks not directly addressed by this feature (T021 docs alignment, T022 CMake symbol-visibility verification, T037 F# proto-codegen, T042/T043 CommandValidator refactor) remain on the deferred list under their original task IDs and are NOT promoted into this feature's scope.

## Out of Scope

- Verification of Channel C Lua-only arms (deferred — needs T044 widgets).
- Verification of arms that have no observable side effect on the wire even in principle (e.g., set-internal-flag arms). These are recorded as `not-wire-observable` and excluded from the success-rate metric, but no work is done in this feature to make them observable.
- F# client behavioral tests. The macro driver is Python-only for this feature and ships as a submodule of the existing `clients/python/highbar_client` package (FR-013); F# behavioral tests are a follow-up tied to the F# client's revival (002 T037).
- A new transport (gRPC-Web, named pipes). Snapshot tick + behavioral coverage work over the existing client-mode UDS / TCP transports.
- Multi-team behavioral coordination tests (e.g., "did the AI's attack provoke retaliation from another AI"). These are emergent-behavior tests, not command-verification tests, and belong in a separate feature.
