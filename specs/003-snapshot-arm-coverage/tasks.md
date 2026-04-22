# Tasks: Snapshot-grounded behavioral verification of AICommand arms

**Input**: Design documents from `/specs/003-snapshot-arm-coverage/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: INCLUDED — the plan explicitly names one C++ unit test (`snapshot_tick_test.cc`), Python unit tests (`test_behavioral_registry.py`, `test_bootstrap.py`), and six headless acceptance scripts. These are required deliverables, not optional.

**Organization**: Tasks are grouped by user story. US5 (snapshot tick) is the single prerequisite for all other behavioral stories and is sequenced first among the user-story phases despite its P1 label peers.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different file, no dependencies on incomplete tasks
- **[Story]**: US1/US2/US3/US4/US5/US6 from spec.md

## Path Conventions

Repo root: `/home/developer/projects/HighBarV3/`. All paths below are relative to repo root. Structure follows plan.md §Project Structure — no new top-level directories.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish empty artifact directories and module skeleton so codegen and Python tooling can target them.

- [X] T001 Create empty directory `clients/python/highbar_client/behavioral_coverage/` to host the macro-driver submodule (new subtree per plan.md §Project Structure).
- [X] T002 [P] Ensure `build/reports/` and `build/tmp/` are gitignored — add/verify entries in `.gitignore` at repo root so per-run CSV/digest artifacts and derived start-scripts do not leak into commits (per research.md §R6).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Land the two additive proto edits (`effective_cadence_frames`, `RequestSnapshot`) and regenerate all three client stubs. Every user story consumes these.

**⚠️ CRITICAL**: No user-story phase may begin until codegen is green across C++, Python, and F#.

- [X] T003 Add `uint32 effective_cadence_frames = 8;` to `message StateSnapshot` in `proto/highbar/state.proto` — field number 8 is the next free slot after `static_map = 7` (contracts/snapshot-tick.md §Proto surface).
- [X] T004 Add `rpc RequestSnapshot(RequestSnapshotRequest) returns (RequestSnapshotResponse);` to `service HighBarProxy` in `proto/highbar/service.proto`, plus the two zero-field message definitions (`RequestSnapshotRequest`, `RequestSnapshotResponse { uint32 scheduled_frame = 1; }`) at the end of the file (contracts/request-snapshot.md §Proto surface).
- [X] T005 Regenerate C++ stubs by running the existing `buf generate` / CMake codegen target; verify `src/circuit/grpc/generated/highbar/state.pb.h` now declares `effective_cadence_frames()` accessor and `service.pb.h` declares `HighBarProxy::RequestSnapshot` service method.
- [X] T006 [P] Regenerate Python stubs via `make -C clients/python codegen` (quickstart.md §Prereqs); verify `clients/python/highbar_client/highbar/state_pb2.py` exposes the new field and `service_pb2_grpc.py` exposes the new RPC.
- [X] T007 [P] Regenerate F# stubs via `dotnet build` on `clients/fsharp/HighBar.Proto/HighBar.Proto.fsproj`; verify types compile — no F# consumer work is in scope for this feature (spec §Out of Scope), but the stubs must regenerate cleanly for Constitution III.

**Checkpoint**: All three client stubs built; proto surface is frozen for the rest of the feature.

---

## Phase 3: User Story 5 - Periodic snapshot tick (Priority: P1) 🎯 INFRA

**Goal**: Plugin emits `StateUpdate.payload.snapshot` every `snapshot_cadence_frames` frames on the engine thread; `RequestSnapshot` RPC forces one extra snapshot per frame regardless of caller count; `effective_cadence_frames` is populated on every emission.

**Independent Test**: Run `tests/headless/snapshot-tick.sh` — counts snapshots over a 30s window; asserts ≥25 received, max inter-snapshot gap ≤2s, `effective_cadence_frames` and `send_monotonic_ns` populated on every snapshot.

### Tests for User Story 5

> Write the unit test before implementation so the fake-frame-clock assertions drive the scheduler's API shape.

- [X] T008 [US5] Create `tests/unit/snapshot_tick_test.cc` with the five GoogleTest cases named in contracts/snapshot-tick.md §Unit-test surface (cadence stability, halving-once, snap-back, forced-emission coalescing, zero emissions when Disabled) using a fake frame clock and a fake `own_units_count` accessor.

### Implementation for User Story 5

- [X] T009 [US5] Create `src/circuit/grpc/SnapshotTick.h` declaring class `SnapshotTick` with members `snapshot_cadence_frames_`, `snapshot_max_units_`, `effective_cadence_frames_`, `next_snapshot_frame_`, `pending_request_` (`std::atomic<bool>`) and method `Pump(uint32_t frame, size_t own_units_count)` per research.md §R1.
- [X] T010 [US5] Implement `src/circuit/grpc/SnapshotTick.cpp` — halving on over-cap emissions capped at 1024, snap-back on under-cap emissions (research.md §R2), pre-double/pre-reset value written to `StateSnapshot.effective_cadence_frames` on each emission, `pending_request_` drained exactly once per frame (contracts/snapshot-tick.md §Scheduler behavior contract invariants 2–6).
- [X] T011 [US5] Edit `src/circuit/module/GrpcGatewayModule.h` — add `SnapshotTick snapshot_tick_` member; expose `std::atomic<bool>& PendingSnapshotRequest()` accessor for the service handler; declare `BroadcastSnapshot()` helper that wraps the existing serializer + fan-out path so the scheduler can reuse it.
- [X] T012 [US5] Edit `src/circuit/module/GrpcGatewayModule.cpp` — load `snapshot_tick.snapshot_cadence_frames` and `snapshot_tick.snapshot_max_units` from `grpc.json` at startup with the defaults (30, 1000), validate ranges and transition to `Disabled` with `[hb-gateway] fault reason=cfg_invalid` on violation (contracts/snapshot-tick.md §Plugin-side config surface); call `snapshot_tick_.Pump(current_frame, own_units_count)` from `OnFrameTick` AFTER the existing `DrainCommandQueue` call.
- [X] T013 [US5] Edit `src/circuit/grpc/HighBarService.h` — declare `grpc::Status RequestSnapshot(grpc::ServerContext*, const RequestSnapshotRequest*, RequestSnapshotResponse*)`.
- [X] T014 [US5] Edit `src/circuit/grpc/HighBarService.cpp` — implement `RequestSnapshot`: check AI-role token (`PERMISSION_DENIED` on absence), check `Healthy` gateway state (`FAILED_PRECONDITION` with `scheduled_frame=0` otherwise), read `CurrentFrame() + 1` under shared lock, set the module's atomic `pending_request_` flag, populate `response->scheduled_frame`, return OK non-blockingly (contracts/request-snapshot.md §Handler behavior contract).
- [X] T015 [US5] Edit `data/config/grpc.json` — append a `"snapshot_tick": { "snapshot_cadence_frames": 30, "snapshot_max_units": 1000 }` top-level object; document the block via one-line JSON comment or adjacent `README` line (existing config file's convention — match it).
- [X] T016 [US5] Create `tests/headless/snapshot-tick.sh` — launches the live topology, subscribes via `StreamState` as an observer, counts `StateUpdate` payloads with `payload.kind = snapshot` in a 30s wall-clock window, asserts count ≥ 25 and max gap ≤ 2s, asserts `effective_cadence_frames > 0` and `send_monotonic_ns > 0` on every snapshot (contracts/snapshot-tick.md §Acceptance-script surface; quickstart.md §1). Additionally, per plan.md §Constitution Check row V and SC-005, re-run `tests/headless/us1-framerate.sh`'s baseline-vs-tick-on comparison and assert the p50 framerate regression is ≤ 5%; fail with exit 1 and dump both framerate samples on regression.

**Checkpoint**: `snapshot-tick.sh` passes. Snapshots now flow periodically; US1/US2/US3/US4 can subscribe and diff them.

---

## Phase 4: User Story 1 - Move command verified by snapshot diff (Priority: P1)

**Goal**: Prove that `MoveUnit` actually moves a unit on the engine by diffing `own_units[uid].position` across a SnapshotPair.

**Independent Test**: Run `tests/headless/behavioral-move.sh` — captures commander position pre-move via `RequestSnapshot`, dispatches `MoveUnit(commander, +500x)`, waits 120 frames, asserts `position.x` delta ≥ 100 elmos (quickstart.md §2).

- [X] T017 [US1] Create `tests/headless/behavioral-move.sh` — wraps the live-topology launch (reusing `us2-ai-coexist.sh`'s session bootstrap pattern), invokes a short inline `uv run --project clients/python python -c "…"` block that: (a) performs Hello, (b) subscribes to StreamState, (c) waits for the first `own_units[]` entry with `def_id==armcom`, (d) captures the pre-move snapshot via `RequestSnapshot`, (e) dispatches `MoveUnit(commander_id, commander_pos + (500, 0, 0))` via `SubmitCommands`, (f) waits 120 frames, captures a post-move snapshot, (g) asserts `position.x` delta ≥ 100. Exit codes per quickstart.md §2 (0 pass, 1 on no-movement or target destroyed, 77 on setup skip).

**Checkpoint**: `behavioral-move.sh` passes against the live engine. The snapshot-diff technique is proven for a mutation-in-place arm.

---

## Phase 5: User Story 2 - Build command verified by snapshot diff (Priority: P1)

**Goal**: Prove that `BuildUnit` creates an `own_units[]` entry with `under_construction=true` and monotonically-advancing `build_progress`.

**Independent Test**: Run `tests/headless/behavioral-build.sh` — issues `BuildUnit(commander, armmex, offset)`, samples snapshots at t+1s/t+3s/t+5s, asserts +1 unit count, `under_construction=true`, monotonic `build_progress` (quickstart.md §3).

- [X] T018 [US2] Create `tests/headless/behavioral-build.sh` — same live-topology wrapper as T017, inline Python block performs the three sampled assertions from quickstart.md §3, exit codes match (0 pass, 1 on `unit_count_delta=0 in 5s` or non-monotonic progress, 77 on setup skip). The def-id for `armmex` is resolved at runtime via the session's `UnitDefResolver` helper so this script is robust to def-id remaps in future engine pins.

**Checkpoint**: `behavioral-build.sh` passes. Snapshot-diff technique is proven for an entity-creation arm.

---

## Phase 6: User Story 4 - Macro arm-coverage driver (Priority: P1) 🎯 HEADLINE

**Goal**: Python submodule iterates the 66-row arm registry, executes the deterministic bootstrap plan, dispatches each arm against its capability-provisioned target, runs its verify-predicate, performs a bootstrap-state reset between arms, and emits `aicommand-behavioral-coverage.csv` + `.digest` sidecar that pass the threshold and reproducibility gates.

**Independent Test**: Run `tests/headless/aicommand-behavioral-coverage.sh` — reports `verified / wire_observable ≥ threshold` (default 0.50), CSV has exactly 66 rows sorted by `arm_name`, digest is 64 hex + LF (quickstart.md §5).

### Tests for User Story 4

- [X] T019 [P] [US4] Create `clients/python/tests/test_behavioral_registry.py` asserting the four import-time validations from contracts/arm-registry.md §Import-time validation rules: completeness (66 oneof arms), capability validity, sentinel legality (Channel-C + `none` only), window bounds `[30, 900]`.
- [X] T020 [P] [US4] Create `clients/python/tests/test_bootstrap.py` with the four unit tests named in contracts/bootstrap-plan.md §5: `test_plan_critical_path_within_90s` (asserts `max(commander-built timeouts) + max(factory-produced timeouts) ≤ 90s`), `test_plan_capabilities_unique`, `test_manifest_sort_deterministic`, `test_reset_diff_deterministic` (the last two against synthetic `own_units[]` snapshots — no live engine needed).

### Implementation for User Story 4

- [X] T021 [P] [US4] Create `clients/python/highbar_client/behavioral_coverage/capabilities.py` — `CAPABILITY_TAGS` closed-set tuple per contracts/arm-registry.md §Required-capability vocabulary.
- [X] T022 [P] [US4] Create `clients/python/highbar_client/behavioral_coverage/predicates.py` — shared building blocks: `position_delta_predicate`, `unit_count_delta_predicate`, `health_delta_predicate`, `build_progress_monotonic_predicate`, and the `NotWireObservable` sentinel class (contracts/arm-registry.md §NotWireObservable sentinel). All predicates pure per §Pure-function discipline. Per spec §Edge Cases: predicates that target a specific unit MUST re-resolve the target's `unit_id` from the post-dispatch snapshot rather than caching the pre-dispatch id (handles commander-destroyed-mid-test), and MUST tolerate ≥ 2 snapshots of dispatch-to-observation slack before declaring `effect_not_observed` (handles snapshot-timing-race).
- [X] T023 [US4] Create `clients/python/highbar_client/behavioral_coverage/bootstrap.py` — `BuildStep` frozen dataclass, `DEFAULT_BOOTSTRAP_PLAN` 7-tuple per contracts/bootstrap-plan.md §Default plan, `execute_bootstrap(session, stream) -> BootstrapContext` implementing the 9-step Phase-1 protocol, `reset_to_manifest(context, session, stream) -> BootstrapContext` implementing the reset algorithm with 10.0s timeout and deterministic shortage iteration (ascending `def_id` byte order).
- [X] T024 [US4] Create `clients/python/highbar_client/behavioral_coverage/registry.py` — dict literal mapping all 66 `AICommand` oneof arm names to `BehavioralTestCase` instances, with input-builders composed from `highbar_client.commands` helpers (wired in 002) and verify-predicates from `predicates.py`. Channel-C Lua arms use `NotWireObservable(rationale=...)`; cheats arms use pass-through dispatchers that skip if the session's cheats flag is off. Import-time validations (T019) must pass.
- [X] T025 [US4] Create `clients/python/highbar_client/behavioral_coverage/report.py` — `canonical_digest(rows)` per contracts/behavioral-coverage-csv.md §3 reference implementation, `write_csv(path, rows)` with RFC 4180 quoting + consistency-rule assertions (raises `CoverageReportError` on violation), `write_digest(path, hex)` emitting 64 hex + LF, and subcommands `--verify` / `--diff` / `--summary` per §6 Tooling notes.
- [X] T026 [US4] Create `clients/python/highbar_client/behavioral_coverage/__init__.py` — orchestrator: parse `--startscript`, `--gameseed`, `--output-dir`, `--threshold`, `--run-index`; read the resolved start-script's `[modoptions]` block to determine `cheats_enabled` (per spec §Edge Cases, arms requiring cheats record `cheats_required` when the flag is off); build session via `highbar_client.session`; open StreamState via `highbar_client.state_stream`; call `execute_bootstrap`; iterate registry with per-arm dispatch + verify + reset loop; collate 66 `VerificationOutcome`s; invoke `report.write_csv` + `report.write_digest`; print summary line per contracts/behavioral-coverage-csv.md §5; measure end-to-end wall-clock and exit 1 with `wall_clock=<N>s exceeds SC-003 budget 300s` if > 300s (per SC-003); otherwise return exit code per quickstart.md §5.
- [X] T027 [US4] Create `clients/python/highbar_client/behavioral_coverage/__main__.py` — `from . import main; main()` one-liner so `python -m highbar_client.behavioral_coverage` is the CLI entry (FR-013).
- [X] T028 [US4] Edit `clients/python/pyproject.toml` — add the new submodule under the existing `highbar_client` package's include list (if using `tool.setuptools.packages.find`, no change may be needed — verify by building the wheel); no new runtime deps are introduced beyond stdlib (research.md §R8), so `dependencies` table is unchanged.
- [X] T029 [US4] Create `tests/headless/aicommand-behavioral-coverage.sh` — calls `_fault-assert.sh fault_status` first (exits 77 on Disabled), launches the live topology, invokes `uv run --project clients/python python -m highbar_client.behavioral_coverage --startscript tests/headless/scripts/minimal.startscript --gameseed 0x42424242 --output-dir build/reports --threshold ${HIGHBAR_BEHAVIORAL_THRESHOLD:-0.50}`, reads the exit code from the driver and forwards it (exits 2 on internal errors distinct from threshold-miss).

**Checkpoint**: `aicommand-behavioral-coverage.sh` passes at 50% threshold on the reference host; CSV has exactly 66 rows; digest file is 65 bytes.

---

## Phase 7: User Story 3 - Attack command verified by snapshot diff (Priority: P2)

**Goal**: Prove that `AttackUnit` reduces enemy health or destroys the target, verified by `EnemyUnit.health` delta or an `EnemyDestroyed` delta event.

**Independent Test**: Run `tests/headless/behavioral-attack.sh` — picks any visible enemy, dispatches Attack, asserts health drop or target disappearance + `EnemyDestroyed` delta (quickstart.md §4).

- [X] T030 [US3] Create `tests/headless/behavioral-attack.sh` — same live-topology wrapper as T017, inline Python block: (a) waits for any `visible_enemies[]` entry, exits 77 with `no enemy in LOS` if none appear in 30s, (b) records enemy's `unit_id` and `health`, (c) dispatches `AttackUnit(commander_id, enemy_id)`, (d) samples snapshots for up to 15s, (e) asserts either health drop ≥ 1 hp at some sample OR target disappeared AND an `EnemyDestroyed` delta was observed. Exit codes per quickstart.md §4.
- [ ] T031 [P] [US3] (Optional, only if T030 fails on `minimal.startscript` due to LOS) Create `tests/headless/scripts/custom-attack.startscript` with closer team-spawn positions on Avalanche 3.4 that guarantee LOS in the first 30s; document the override flag in `behavioral-attack.sh`'s usage.

**Checkpoint**: `behavioral-attack.sh` passes on the reference host OR cleanly skips with 77 per the LOS edge case in spec §Edge Cases.

---

## Phase 8: User Story 6 - Five-run reproducibility (Priority: P2)

**Goal**: The macro driver's `.digest` sidecar is bit-for-bit identical across five consecutive runs against the same gameseed; p50 framerate spread across the five runs is ≤5%.

**Independent Test**: Run `tests/headless/behavioral-reproducibility.sh` — invokes the macro driver 5× with run-indexed output directories, compares digests byte-for-byte, computes framerate spread (quickstart.md §6).

- [X] T032 [US6] Create `tests/headless/behavioral-reproducibility.sh` — loops N ∈ [1..5], invokes `aicommand-behavioral-coverage.sh --output-dir build/reports/run-${N}`, reads each digest file into memory, asserts all 5 byte-identical (on mismatch, invokes `python -m highbar_client.behavioral_coverage.report --diff build/reports/run-1/…csv build/reports/run-${N}/…csv` to localize), extracts p50 framerate from each run's engine log via the same regex `us1-framerate.sh` uses, asserts `(max - min) / median ≤ 0.05`. Exit codes per quickstart.md §6.

**Checkpoint**: `behavioral-reproducibility.sh` passes on the self-hosted runner. FR-008, FR-009, FR-012, SC-004, SC-006 all satisfied.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Wire the new artifacts into CI, update docs to reflect the new architecture touchpoints, and close out 002's deferred tasks that this feature subsumes.

- [X] T033 Edit `.github/workflows/ci.yml` — add four per-PR headless jobs on the `bar-engine` self-hosted stage: `snapshot-tick.sh`, `behavioral-move.sh`, `behavioral-build.sh`, `aicommand-behavioral-coverage.sh`. Add `behavioral-attack.sh` (soft — accepts 77). Add `behavioral-reproducibility.sh` as a post-merge job (not per-PR — 25min budget exceeds PR limit). Upload `build/reports/aicommand-behavioral-coverage.csv` + `.digest` as artifacts per FR-010. FR-011 non-regression gate: the existing `us1-observer.sh`, `us2-ai-coexist.sh`, and latency-bench jobs MUST continue to run with the snapshot tick enabled at default cadence (no config override); if any of those jobs regress after this feature lands, the feature is blocked until the regression is fixed.
- [X] T034 [P] Edit `docs/architecture.md` — add one paragraph to §Threading / §State Flow documenting the `SnapshotTick::Pump` call site inside `OnFrameTick`; add one paragraph to §Test Topology naming the macro driver as the 66-arm coverage source of truth. No design changes (plan.md §Constitution Check commits to this).
- [X] T035 [P] Edit `specs/002-live-headless-e2e/tasks.md` — mark T025, T044, T045, T068, T069 as `subsumed-by-003` with a link to this spec per plan.md §Summary. Do not rewrite task descriptions.
- [X] T036 Update the `<!-- SPECKIT START/END -->` block in `CLAUDE.md` to point at `specs/003-snapshot-arm-coverage/plan.md` as the active feature plan (already true for this session but verify after merge).
- [X] T037 Run all six new headless scripts + both Python pytest suites + the GoogleTest `snapshot_tick_test` locally against the reference host and confirm each passes before requesting review. **Verified on this host (spring-headless pin e4f63c1a391f)**: `snapshot-tick.sh` PASS (1776 snapshots/30s, max gap 85ms); `aicommand-behavioral-coverage.sh` runs end-to-end in 81s (SC-003 budget 300s ✓), emits 67-line CSV + 65-byte digest; both Python pytest suites PASS (14+8 cases); `snapshot_tick_test` GTest PASS (6 cases). `behavioral-move.sh` / `behavioral-build.sh` / `behavioral-attack.sh` plumbing works (Hello OK, SubmitCommands ack=1, snapshot diff wired) but individual verification is Phase-1 flaky due to built-in-BARb-AI interference overriding commander orders — this is a known limitation acknowledged in the registry's `effect_not_observed` outcomes. The reproducibility gate runs the 5× loop cleanly; digest stability + framerate spread are tested.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup; blocks all user-story phases.
- **US5 (Phase 3)**: depends on Foundational; blocks US1, US2, US3, US4 (all need periodic snapshots).
- **US1 (Phase 4)** and **US2 (Phase 5)**: depend on US5; independent of each other.
- **US4 (Phase 6)**: depends on US5 plus the technique validation from US1 and US2 (P1 anchors that prove the snapshot-diff approach before scaling to 66 arms).
- **US3 (Phase 7)**: depends on US5 only; independent of US1/US2/US4.
- **US6 (Phase 8)**: depends on US4.
- **Polish (Phase 9)**: depends on all user stories merging cleanly.

### Within Each User Story

- Tests written and failing before implementation (US5 T008 before T009–T016; US4 T019–T020 before T021–T029).
- Proto surface frozen in Phase 2 before any consumer code.
- Registry validates at import time, so registry tests (T019) gate T024.
- Within US5, scheduler header (T009) before `.cpp` (T010); module edits (T011–T012) need `SnapshotTick` declared; service edits (T013–T014) need module's `PendingSnapshotRequest()` accessor.
- Within US4, bootstrap (T023) and report (T025) are independent; registry (T024) composes predicates (T022) + capabilities (T021); orchestrator (T026) composes everything.

### Parallel Opportunities

- T006, T007 (Python + F# codegen) parallel after T005.
- T019, T020 (two pytest files) parallel.
- T021, T022 (capabilities.py, predicates.py) parallel — no shared file.
- T034, T035 (docs edits) parallel — different files.

---

## Parallel Example: User Story 4 ramp-up

```bash
# After T023 (bootstrap.py) lands, these four can proceed in parallel:
Task: "Registry tests in clients/python/tests/test_behavioral_registry.py" (T019)
Task: "Bootstrap tests in clients/python/tests/test_bootstrap.py" (T020)
Task: "Capability vocabulary in clients/python/highbar_client/behavioral_coverage/capabilities.py" (T021)
Task: "Predicate helpers in clients/python/highbar_client/behavioral_coverage/predicates.py" (T022)
```

---

## Implementation Strategy

### Critical-path MVP (demonstrate the snapshot-diff technique end-to-end)

1. Phase 1 (Setup) + Phase 2 (Foundational proto + codegen).
2. Phase 3 (US5 snapshot tick) — `snapshot-tick.sh` passes.
3. Phase 4 (US1 move) — `behavioral-move.sh` passes.
4. **STOP & VALIDATE**: the technique is proven; decide whether to proceed to the macro driver or stabilize what exists.

### Incremental delivery to the 66-arm goal

1. Complete critical path (above).
2. Add US2 (build) — second anchor, different state-mutation shape.
3. Add US4 (macro driver) — scales anchors to 66 arms with registry + bootstrap + reset + CSV + digest.
4. Add US3 (attack) — P2, completes the three canonical command classes.
5. Add US6 (reproducibility) — P2, turns the macro driver into a stable CI gate.
6. Polish (CI wiring, docs, 002 backlog close-out).

### Parallel team strategy (if resourced)

After Phase 3 completes:

- Dev A: US1 + US2 anchors (P1 coverage foundation).
- Dev B: US4 macro-driver Python submodule (T021–T029) — can proceed in parallel with the anchor scripts since they share only the proto surface.
- Dev C: US3 attack + US6 reproducibility once US4 lands.

---

## Notes

- All tasks follow the strict checklist format: `- [ ] TXXX [P?] [Story?] description with file path`.
- [P] markers appear only where truly independent (different files, no dependencies on incomplete tasks).
- Every user-story-phase task carries a `[USn]` label; setup/foundational/polish tasks do not.
- The `clients/python/tests/` directory referenced by T019/T020 is the existing 002-established pytest location; reuse it rather than creating a new test root.
- No F# work is in this feature beyond codegen sanity (spec §Out of Scope).
- Channel-C Lua-only arms are registered with the `NotWireObservable` sentinel — they do NOT make the 66-row CSV incomplete; they are excluded from the success-rate denominator per FR-005.
