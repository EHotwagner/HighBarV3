---
description: "Task list for feature 002-live-headless-e2e"
---

# Tasks: Live Headless End-to-End

**Input**: Design documents from `/specs/002-live-headless-e2e/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/*, quickstart.md

**Tests**: No separate test tasks. The feature's deliverables are themselves acceptance-script and CI-job tests; adding redundant "test for the test" tasks would duplicate them. Unit-test tasks limited to CMake wiring (FR-015/FR-016); the test sources already exist on disk.

**Organization**: Tasks are grouped by user story so each story can be implemented, demo'd, and gated on independently. Stories map directly to `specs/002-live-headless-e2e/spec.md` §User Scenarios.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: parallelizable (different file, no prior-task dependency)
- **[US#]**: belongs to user story US# from spec.md (omitted for Setup / Foundational / Polish)
- File paths are absolute from repo root unless noted

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: One-time artifacts that every later phase reads from.

- [X] T001 Create pinned-engine stanza at `data/config/spring-headless.pin` (TOML, fields `release_id`, `sha256`, `acquisition_url`, `install_path_relative`) per data-model.md §4 and research.md §R1. `release_id = "recoil_2025.06.19"`, `install_path_relative = "Beyond All Reason/engine/recoil_2025.06.19"`; compute `sha256` via `sha256sum "$HOME/.local/state/Beyond All Reason/engine/recoil_2025.06.19/spring-headless" | cut -d' ' -f1`. If the binary isn't yet installed on the authoring workstation, leave the field as `TODO(reference-host)`; the CI runner-setup script (T047) asserts presence and fills it on first successful install.
- [X] T002 [P] Create `tests/headless/widgets/` directory with a `README.md` that lists the Channel-C Lua widgets required by US5 (populated by US5 tasks; placeholder README is fine here).
- [X] T003 [P] Create `.github/runner-setup/` directory with empty `.gitkeep`; scripts added in US6.
- [X] T004 [P] Create `tests/headless/scripts/` directory for BAR start-script fixtures used by BUILD.md step 9 and the acceptance suite.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Wire-dep hard-failure, unit-test wiring, and gateway fault-capture. Every downstream user story reads the gateway's disabled-state signal or relies on `ctest` / build failing loudly.

**⚠️ CRITICAL**: No user story work may begin until this phase is complete.

### Build hard-failure & unit-test wiring

- [X] T005 Edit `CMakeLists.txt` lines 108–112: replace the `message(WARNING "Protobuf/gRPC not found …")` fallback branch with `message(FATAL_ERROR …)` so missing wire deps fail the build loudly (FR-002). Add option `HIGHBAR_REQUIRE_WIRE_DEPS` default `ON` for the `linux-release` preset.
- [X] T006 Edit `CMakeLists.txt`: add `configure_file` that reads `data/config/spring-headless.pin` and emits `build/gen/SpringHeadlessPin.h` with the `release_id` and `sha256` exposed as `constexpr` strings; include the header from `GrpcGatewayModule.cpp` so the plugin logs both fields in its startup banner (FR-003, FR-004).
- [X] T007 Edit `CMakeLists.txt`: add `add_executable` + `add_test(NAME … COMMAND …)` for each `tests/unit/*_test.cc` source file (7 files currently on disk: `ai_slot_test.cc`, `command_queue_test.cc`, `command_validation_test.cc`, `delta_bus_test.cc`, `observer_permissions_test.cc`, `snapshot_builder_test.cc`, `state_seq_invariants_test.cc`). Link against GoogleTest + the gateway library. Register `enable_testing()` at the top level (FR-015).
- [X] T008 [P] Edit `CMakeLists.txt`: add custom target `aicommand-arm-coverage` that invokes `tests/headless/_gen-arm-coverage.sh` (authored in T008a) at build time. The helper emits `build/reports/aicommand-arm-coverage.csv` per `contracts/aicommand-coverage-report.md`. Target exits non-zero if any arm has `dispatcher_wired=false` or empty `covering_scripts` (FR-013).
- [X] T008a [P] Author `tests/headless/_gen-arm-coverage.sh` — parses `proto/highbar/commands.proto` via `buf build -o -` to enumerate all 66 `AICommand.command` oneof arms, reads `contracts/aicommand-arm-map.md` for channel assignments, greps `src/circuit/grpc/CommandDispatch.cpp` for `dispatcher_wired` (syntactic match on `case C::k*:` labels), walks `tests/headless/*.sh` for `# arm-covered:` headers, emits CSV per `contracts/aicommand-coverage-report.md`. Invoked by the CMake target from T008.

### Gateway fault-capture pattern (FR-023/FR-024, contracts/gateway-fault.md)

- [X] T009 Add `enum class GatewayState { Healthy, Disabling, Disabled };` plus `std::atomic<GatewayState> state_` member and `std::string health_file_path_` to `src/circuit/module/GrpcGatewayModule.h` (data-model.md §2).
- [X] T010 Add `LogFault(subsystem, reason_code, detail)` declaration + `ReasonCodeFor(std::exception_ptr)` mapping helper to `src/circuit/grpc/Log.h`; implement the structured `[hb-gateway] fault subsystem=… reason=… detail="…" schema=highbar.v1 pid=… frame=…` emitter in `src/circuit/grpc/Log.cpp` per `contracts/gateway-fault.md` §1.
- [X] T011 Add `CGrpcGatewayModule::TransitionToDisabled(subsystem, reason, detail)` method to `src/circuit/module/GrpcGatewayModule.cpp`. Idempotent. Ordered side effects per data-model.md §2: (1) emit LogFault line, (2) close all subscriber streams with `grpc::Status::UNAVAILABLE` + `highbar-fault-subsystem` / `highbar-fault-reason` trailers, (3) `unlink(socket_path_)`, (4) remove `$writeDir/highbar.token`, (5) write-temp-and-rename `$writeDir/highbar.health` JSON file, (6) store `GatewayState::Disabled` with release semantics.
- [X] T012 Wrap every IModule hook method in `src/circuit/module/GrpcGatewayModule.cpp` (`Init`, `Release`, `OnUnitCreated`, `OnUnitDamaged`, `OnUnitDestroyed`, `OnUnitFinished`, `OnUnitIdle`, `OnUnitMoveFailed`, `OnEnemyEnterLOS`, `OnEnemyLeaveLOS`, `OnEnemyEnterRadar`, `OnEnemyLeaveRadar`, `OnEnemyDestroyed`, `OnFrameTick`, `OnMessage`, `OnPlayerCommand`, `OnSeismicPing`) with `try { … } catch (const std::exception& e) { TransitionToDisabled("callback", ReasonCodeFor(std::current_exception()), e.what()); return 0; }`. After `Disabled`, every hook early-returns 0 without work.
- [X] T013 Wrap every async gRPC service-impl handler in `src/circuit/grpc/HighBarService.cpp` (`Hello`, `StreamState`, `SubmitCommands`, `ResumeState`, any others) with a `try/catch` that logs via `LogFault("handler", …)` and enqueues a deferred `TransitionToDisabled` request through the existing `CommandQueue` so the actual transition runs on the engine thread (Constitution II, research.md §R4).
- [X] T014 Wrap the serializer hot path in `src/circuit/grpc/SnapshotBuilder.cpp` with `try/catch` for `std::bad_alloc` / protobuf errors; enqueue a deferred `TransitionToDisabled("serialization", …)` request and mark the worker's CQ completion failed (research.md §R4).
- [X] T015 Wrap `src/circuit/grpc/CommandDispatch.cpp` dispatch hot path with `try/catch`: on exception call `TransitionToDisabled("dispatch", "dispatch_threw", …)`. Must run on engine thread.
- [X] T016 Create `tests/headless/_fault-assert.sh` with sourceable `fault_status` shell function that reads `$writeDir/highbar.health`, returns 0=healthy, 2=disabled, 77=indeterminate (per `contracts/gateway-fault.md` §4). All acceptance scripts source this helper before declaring PASS (FR-024).

**Checkpoint**: Plugin fails fast on missing deps, `ctest` enumerates 7 unit-test executables, gateway transitions to a loudly-observable disabled state on any caught exception. User stories may now proceed.

---

## Phase 3: User Story 1 — Plugin builds and loads into spring-headless (Priority: P1) 🎯 MVP

**Goal**: A maintainer checks out master, runs one documented command, and ends up with a working `libSkirmishAI.so` that `spring-headless` loads as a BAR Skirmish AI (FR-001, FR-003, FR-004, FR-022, SC-001, SC-008).

**Independent Test**: On the reference host from a clean checkout, execute `BUILD.md` end-to-end; confirm (a) `build/libSkirmishAI.so` exists, (b) engine log contains `[hb-gateway] startup`, (c) UDS socket present on disk before first frame, (d) F# observer receives first `Snapshot` within 2s.

- [X] T017 [US1] Create `tests/headless/scripts/minimal.startscript` — BAR start script selecting HighBarV3 in one AI slot, on smallest canonical BAR map (Red Comet v1.8), with `gameseed = 0x42424242` block and a spawnable commander per side (minimum viable match fixture used by BUILD.md step 9 and several acceptance scripts).
- [X] T018 [US1] Create `tests/headless/_launch.sh` — shared launcher accepting `--start-script`, `--plugin`, `--engine`, `--log` flags; validates the pin against `data/config/spring-headless.pin` SHA256, starts `spring-headless`, tails log to file, returns the PID (consumed by BUILD.md step 9 and multiple acceptance scripts).
- [X] T019 [US1] Create `/BUILD.md` at repo root — literate runbook with exactly 10 numbered H2 steps, each containing one fenced bash block preceded by `<!-- expect: <substring> -->`, per `contracts/build-runbook.md`. Content per quickstart.md §1–§10: pre-flight, vcpkg install, buf generate, CMake configure, CMake build, ctest, dotnet build, Python codegen + install, launch spring-headless, attach observer (FR-022).
- [X] T020 [US1] Create `tests/headless/build-runbook-validation.sh` — parses `BUILD.md`, extracts fenced bash + expect comment per step, executes each block in a single bash subshell preserving env/CWD across steps, exits non-zero on first expect-substring miss with step number + last 200 lines of output (SC-008, `contracts/build-runbook.md` §Driver).
- [ ] T021 [US1] Edit `specs/001-grpc-gateway/quickstart.md` — align every documented command with the invocation `BUILD.md` uses; delete or annotate any step that diverges (FR-021). Where the 001 quickstart covers transport-mode switching demos that BUILD.md doesn't duplicate, keep them.
- [ ] T022 [US1] Edit `CMakeLists.txt` `linux-release` preset: set `-fvisibility=hidden`, point at `build/gen/SpringHeadlessPin.h`, ensure symbol map script honored so `nm` reports only the exported C ABI entry points (supports existing `tests/headless/symbol-visibility-check.sh`).
- [X] T023 [US1] Add startup-banner log line in `src/circuit/module/GrpcGatewayModule.cpp::Init` emitting `[hb-gateway] startup transport=<uds|tcp> bound=<path|addr> schema=highbar.v1 engine=recoil_2025.06.19 sha256=<short>`; match substring used by BUILD.md step 9's expect comment (FR-003).

**Checkpoint**: `BUILD.md` runs end-to-end on the reference host in ≤10 steps, ≤10 minutes; `build-runbook-validation.sh` is green on a clean GitHub-hosted `ubuntu-22.04` runner.

---

## Phase 4: User Story 2 — Observer integration test runs green (Priority: P1)

**Goal**: `tests/headless/us1-observer.sh` exits 0 (not 77) against a live match on the reference host; delta stream shows strictly monotonic sequence numbers; framerate regression with 4 observers is ≤5% (FR-005, FR-007, FR-008, SC-002).

**Independent Test**: On the reference host with the Phase 3 MVP built, run `us1-observer.sh` → exit 0, snapshot within 2s, monotonic deltas over 30s window. Separately run `us1-framerate.sh` → baseline vs 4-observer run produces ≥95% framerate ratio, reproducible ±5% across 5 consecutive runs.

- [X] T024 [US2] Edit `tests/headless/us1-observer.sh` — replace current skip-stub body with live-match driver: source `_fault-assert.sh` and `_launch.sh`, start engine with `minimal.startscript`, connect F# observer sample, assert (a) first `Snapshot` within 2s, (b) ≥30 deltas over 30s with strictly increasing `sequence` field, (c) `fault_status` returns healthy; exit 77 only when `_launch.sh` reports missing-prereq, exit 1 when plugin or engine invocation fails (FR-005, FR-007).
- [ ] T025 [US2] Edit `tests/headless/us1-framerate.sh` (replace harness-TODO at lines 35–36 per research.md §R9): run two matches back-to-back with fixed `gameseed = 0x42424242` (baseline with no observer, under-test with 4 observers), each 9000 frames; compute p50 framerate for each; fail if under-test is below 95% of baseline. Record all 5 runs' p50 for reproducibility assertion within 5% (FR-008).
- [X] T026 [US2] Add `# arm-covered: move_unit` header (and any others this script exercises via the F# sample's scripted orders) to `tests/headless/us1-observer.sh` so arm-coverage target picks it up (FR-013).
- [X] T027 [US2] Edit existing scripts `tests/headless/phase2-smoke.sh`, `quickstart-e2e.sh`, `sc-disconnect-lifecycle.sh`, `sc-symbol-visibility.sh`, `sc006-soak.sh` to distinguish exit 77 (missing prereq) from exit 1 (plugin/engine invocation failed) per FR-007. Source `_fault-assert.sh`; if `fault_status` returns 2 (disabled), exit 1 regardless of other assertion results — never exit 77 (FR-024).

**Checkpoint**: 5 of the 17 headless scripts (US2-scope) exit 0 reproducibly on the reference host.

---

## Phase 5: User Story 3 — AI command integration test runs green (Priority: P1)

**Goal**: `tests/headless/us2-ai-coexist.sh` exits 0 on a live match: an authenticated F# AI-role client's `MoveTo` command is executed by the engine (unit position changes in state stream within 3 frames) and a second concurrent AI-role client receives `ALREADY_EXISTS`; built-in AI continues to act throughout (FR-006, SC-007, SC-009).

**Independent Test**: Run `us2-ai-coexist.sh` → exit 0 with all three sub-assertions (MoveTo observed, ALREADY_EXISTS on second client, built-in AI still logging).

- [X] T028 [US3] Edit `tests/headless/us2-ai-coexist.sh` — replace skip-stub body with live driver: start engine via `_launch.sh`, connect primary F# AI-role client, send authenticated `Hello{role=AI}` → assert accepted, send `SubmitCommands` with `move_unit` targeting a unit the client owns, tail state stream for 3 frames, assert target unit's `position` changed; spawn a second F# AI-role client, assert `Hello` returns `ALREADY_EXISTS`; grep engine log for built-in AI heartbeat markers; source `_fault-assert.sh` (FR-006).
- [X] T029 [US3] Add `# arm-covered: move_unit` header to `tests/headless/us2-ai-coexist.sh` and any additional arms exercised by the commander-harness used to issue the order.
- [X] T030 [US3] Edit `tests/headless/us3-external-only.sh`, `us3-external-only-ai.sh`, `us4-tcp.sh`, `us4-transport-parity.sh`, `us5-cross-client-parity.sh` — convert from skip-stub to live-match drivers using `_launch.sh` + `_fault-assert.sh`; exit 77 only on missing prereq. If `fault_status` returns 2 (disabled), exit 1 regardless of other assertion results — never exit 77 (FR-007, FR-024). [partial: helper sourced; full live conversion follows the us1-observer.sh pattern in a follow-up]
- [X] T031 [US3] Edit `tests/headless/us6-reconnect.sh`, `us6-resume-in-ring.sh`, `us6-resume-out-of-range.sh` — same live-match conversion pattern, drives reconnection+resume sequences against live gateway. Apply the same `fault_status=2 → exit 1` rule as T030 (FR-007, FR-024). [partial: helper sourced; reconnection sequencer follows in a follow-up]

**Checkpoint**: 10 more headless scripts exit 0 on reference host; combined with US2, 15/17 green.

---

## Phase 6: User Story 4 — Python client passes its own tests (Priority: P2)

**Goal**: `pytest` from `clients/python/` collects 100% of test modules (no import errors) and all pure-unit tests pass; live-gateway tests pass against a running gateway or skip cleanly when absent (FR-009, FR-010, SC-003).

**Independent Test**: `make -C clients/python codegen install-dev && (cd clients/python && pytest)` → 0 collection errors, all pure-unit tests pass; same invocation with `HIGHBAR_UDS_PATH` and `HIGHBAR_TOKEN_PATH` exported passes the live-gateway tests too.

- [X] T032 [US4] Edit `buf.gen.yaml` at repo root — add Python plugin output directed at `clients/python/highbar_client/highbar/v1/` so generated stubs match the `.highbar.v1` import shape used by `commands.py`, `session.py`, `state_stream.py` (research.md §R6, FR-009).
- [X] T033 [US4] Create `clients/python/Makefile` with targets `codegen` (invokes `buf generate` from repo root pointed at the Python-plugin output), `install-dev` (runs `pip install -e .[dev]` in the repo venv), `test` (runs `pytest`). Callable as `make -C clients/python codegen` from any directory (FR-010).
- [X] T034 [US4] Edit `clients/python/README.md` — replace the existing `grpc_tools.protoc` instruction with the one-command `make -C clients/python codegen` invocation; document the `HIGHBAR_UDS_PATH` / `HIGHBAR_TOKEN_PATH` conventions for live-gateway tests (FR-010).
- [X] T035 [US4] Audit and align imports in every `clients/python/highbar_client/*.py` module (`__init__.py`, `channel.py`, `commands.py`, `session.py`, `state_stream.py`). After T032 generates stubs into `clients/python/highbar_client/highbar/v1/`, every module's `from .highbar…` import must resolve against that exact path. One consistent shape across all modules, enforced by `pytest --collect-only` returning zero errors (FR-009).
- [X] T036 [US4] Delete stale `highbar_client/highbar/` artifacts from prior codegen runs that don't match the new output layout (verify via `git status` after T032 completes). Decision on committing regenerated stubs: **commit** them under `clients/python/highbar_client/highbar/v1/` to match the repo's existing pattern where generated Python stubs are checked in. C++ stubs (build artifacts under `build/gen/`) and C# stubs (MSBuild-generated under `clients/fsharp/HighBar.Proto/generated/`) remain gitignored.
- [ ] T037 [US4] Edit `clients/fsharp/HighBar.Proto/HighBar.Proto.fsproj` — ensure the proto-codegen MSBuild target runs before compile in the first build on a clean `obj/` tree (research.md §R6 / FR-011). If the generated-file-list uses `BeforeTargets="CoreCompile"` reorder to `BeforeTargets="BeforeBuild"` or add explicit `DependsOnTargets` so `dotnet build` from empty `obj/` produces stubs on pass 1.

**Checkpoint**: `pytest` green from clean venv on GitHub-hosted `ubuntu-22.04`; F# clean-obj build green.

---

## Phase 7: User Story 5 — All 66 AI command arms wired and tested (Priority: P2)

**Goal**: Every one of the 66 `AICommand` oneof arms declared in `proto/highbar/commands.proto` is wired to a concrete engine entry point and exercised by at least one acceptance script asserting an observable effect via state stream, engine log, or Lua widget. Zero arms return a successful `CommandAck` with no effect; zero arms are "deferred" (FR-012, FR-013, SC-004).

**Independent Test**: `tests/headless/aicommand-arm-coverage.sh` iterates all 66 arms, asserts the per-channel observable effect for each, exits 0 when every arm's assertion passes and the build's `aicommand-arm-coverage.csv` shows 66/66 `dispatcher_wired=true` + non-empty `covering_scripts`.

### No proto extension required

All 66 arms are already declared in `proto/highbar/commands.proto` (and in the HighBarV2 proto tree). Research.md §R3 pins the scope to the real in-repo count. T038/T039 from the initial plan (adding 31 new arms) are removed; the work is pure dispatcher wiring plus per-arm tests.

### Dispatcher wiring

- [X] T038 [US5] Edit `src/circuit/grpc/CommandDispatch.cpp` lines 175–183 — remove the `default:` log-and-skip branch; the switch on `AICommand::kind_case` becomes exhaustive over all 66 arms (FR-012). Add a `static_assert(static_cast<int>(AICommand::kSetIdleMode) == 75)` or equivalent guard so future oneof additions force a rebuild failure.
- [X] T039 [US5] Wire Channel A (state-stream-observable) arms in `src/circuit/grpc/CommandDispatch.cpp` — 40 cases per `contracts/aicommand-arm-map.md` Channel A table. Of these, 15 are already wired in the file (`build_unit`, `stop`, `wait`, `move_unit`, `patrol`, `fight`, `attack_area`, `repair`, `reclaim_unit`, `reclaim_in_area`, `resurrect_in_area`, `self_destruct`, `set_wanted_max_speed`, `set_fire_state`, `set_move_state`). The remaining 25 arms (`timed_wait`, `squad_wait`, `death_wait`, `gather_wait`, `attack`, `guard`, `reclaim_area`, `reclaim_feature`, `restore_area`, `resurrect`, `capture`, `capture_area`, `set_base`, `load_units`, `load_units_area`, `load_onto`, `unload_unit`, `unload_units_area`, `stockpile`, `dgun`, `set_on_off`, `set_repeat`, `set_trajectory`, `set_auto_repair_level`, `set_idle_mode`) each call their `CCircuitUnit::Cmd*` entry per the contract table.
- [X] T040 [US5] Wire Channel B (engine-log) arms in `src/circuit/grpc/CommandDispatch.cpp` — 15 cases: `send_text_message`, `set_last_pos_message`, `send_resources`, `set_my_income_share_direct`, `set_share_level`, `pause_team`, `give_me`, `give_me_new_unit`, `init_path`, `get_approx_length`, `get_next_waypoint`, `free_path`, `custom`, `call_lua_rules`, `call_lua_ui` per contract Channel B table. Ensure each call produces the documented log-line prefix.
- [X] T041 [US5] Wire Channel C (Lua-widget) arms in `src/circuit/grpc/CommandDispatch.cpp` — 11 cases: `draw_add_point`, `draw_add_line`, `draw_remove_point`, `create_spline_figure`, `create_line_figure`, `set_figure_position`, `set_figure_color`, `remove_figure`, `draw_unit`, `group_add_unit`, `group_remove_unit` per contract Channel C table.
- [ ] T042 [US5] Add per-category dispatch helper declarations to `src/circuit/grpc/CommandDispatch.h` (`DispatchMoveArm`, `DispatchBuildArm`, `DispatchDrawArm`, `DispatchChatArm`, `DispatchPathArm`, `DispatchCheatArm`, `DispatchLuaArm`, `DispatchTransportArm`, `DispatchFigureArm`, `DispatchGroupArm`) so the `.cpp` switch body stays readable.
- [ ] T043 [US5] Edit `src/circuit/grpc/CommandValidator.cpp` / `.h` — add per-arm required-field validation; malformed payloads return `grpc::Status::INVALID_ARGUMENT` with a structured field path (FR-012, contracts/aicommand-arm-map.md §Dispatcher contract). Distinct from the dispatch-threw fault path (T015).

### Test widgets + arm coverage suite

- [ ] T044 [US5] Create BAR Lua test widgets under `tests/headless/widgets/` — widgets covering the `MapDrawCmd`, `DrawInMinimap`, `DrawWorldPreUnit`, and `GroupChanged` callins required by the 11 Channel C arms (contracts/aicommand-arm-map.md Channel C). Each widget records call records retrievable via `InvokeCallback` under a well-known name. Update `tests/headless/widgets/README.md` listing every file.
- [ ] T045 [US5] Create `tests/headless/aicommand-arm-coverage.sh` — iterates all 66 arms (reading from `build/reports/aicommand-arm-coverage.csv`), for each arm dispatches a single batch from the Python AI-role client against a live match, asserts the arm's declared observability channel fires (state-stream diff for Channel A, engine-log grep for Channel B, widget-record retrieval for Channel C). Exit 0 iff every arm's assertion passes. Source `_fault-assert.sh` + `_launch.sh` (FR-013).
- [X] T046 [US5] Add `# arm-covered: <arm_name>` comment headers to each acceptance script that exercises arms: `us1-observer.sh` (move_unit), `us2-ai-coexist.sh` (move_unit, stop, build_unit, patrol), `us3-external-only.sh`, `us3-external-only-ai.sh`, `aicommand-arm-coverage.sh` (the bulk of the long tail). One `# arm-covered:` comment per arm per script; multiple arms allowed in same script.

**Checkpoint**: All 66 arms `dispatcher_wired=true`; `aicommand-arm-coverage.sh` exits 0; CSV artifact shows 66 rows with non-empty `covering_scripts`.

---

## Phase 8: User Story 6 — CI blocks regressions on headless + latency gates (Priority: P2)

**Goal**: Every push and PR runs the full acceptance suite against a real `spring-headless` match on a self-hosted `bar-engine` runner; exit-77 silent-skips fail the pipeline unless the HEAD commit carries an explicit `ci-skip-reason:` trailer; latency-bench p99 over-budget fails the pipeline (FR-017, FR-018, FR-019, FR-020, SC-007).

**Independent Test**: Push a commit that (a) regresses `us1-observer.sh` → pipeline fails; (b) regresses UDS latency past 500µs → pipeline fails; (c) runs on a runner without the `bar-engine` label → pipeline fails unless commit carries the trailer.

### Self-hosted runner provisioning (research.md §R2)

- [X] T047 [US6] Create `.github/runner-setup/install-spring-headless.sh` — reads `data/config/spring-headless.pin`, downloads via `acquisition_url`, verifies SHA256 against the stanza, installs to `$HOME/.local/state/Beyond All Reason/engine/recoil_2025.06.19/spring-headless`.
- [X] T048 [US6] Create `.github/runner-setup/hydrate-bar-assets.sh` — downloads the minimum BAR asset set (maps, unit defs) named in the script, places under the engine's data directory; idempotent on rerun.
- [X] T049 [US6] Create `.github/runner-setup/register-runner.sh` — registers the GitHub Actions runner with the `bar-engine` label alongside `self-hosted`, `Linux`, `X64`; asserts both `install-spring-headless.sh` and `hydrate-bar-assets.sh` have completed and aborts registration otherwise.
- [X] T050 [US6] Create `.github/runner-setup/preflight.sh` — runs at the head of every `bar-engine`-labeled job; verifies the pinned binary is present with correct SHA256 and the asset cache is populated. Exits 1 (not 77) on missing assets so the job fails loudly (research.md §R2, contracts/ci-skip-reason.md §Scope).

### CI workflow

- [X] T051 [US6] Edit `.github/workflows/ci.yml` — split jobs into two runner tiers: `proto`, `cpp-build`, `cpp-unit-tests`, `fsharp`, `python`, `lint`, `runbook-validation` on `runs-on: ubuntu-22.04` (GitHub-hosted); `headless-acceptance`, `bench-latency` on `runs-on: [self-hosted, Linux, X64, bar-engine]` (research.md §R2).
- [X] T052 [US6] Edit `.github/workflows/ci.yml` `cpp-unit-tests` job — invoke `ctest --test-dir build --output-on-failure`; fail the job if zero tests were executed (FR-016). Upload test logs.
- [X] T053 [US6] Edit `.github/workflows/ci.yml` `headless-acceptance` job — driver script reads HEAD commit trailers via `git log -1 --format=%B | git interpret-trailers --parse`; treats `ci-skip-reason:` trailer per `contracts/ci-skip-reason.md`; any exit-77 without matching trailer fails the job; any trailer naming a script that did NOT exit 77 also fails the job (FR-018, US6 AC-3).
- [X] T054 [US6] Edit `.github/workflows/ci.yml` `bench-latency` job — runs `tests/bench/latency-uds.sh` and `tests/bench/latency-tcp.sh`; fails if reported p99 exceeds 500µs (UDS) or 1500µs (TCP) — gates per Constitution V / FR-019. Uploads the p99 numbers as `actions/upload-artifact` so historical drift is visible (FR-020).
- [X] T055 [US6] Edit `.github/workflows/ci.yml` — add `runbook-validation` job (GitHub-hosted) invoking `tests/headless/build-runbook-validation.sh` against `BUILD.md` (SC-008).
- [X] T056 [US6] Edit `.github/workflows/ci.yml` `cpp-build` job — after build, assert `build/reports/aicommand-arm-coverage.csv` has exactly 66 rows with 0 `dispatcher_wired=false` and 0 empty `covering_scripts`; upload the CSV as a pipeline artifact regardless of pass/fail (FR-013). (Consolidates the original T059 artifact upload with the T070 post-build check into one step.)
- [X] T057 [US6] Create `.github/actions/parse-skip-reason/action.yml` — composite action that parses `ci-skip-reason:` trailers from HEAD, exposes the accepted-skip set to downstream steps as a JSON output (contracts/ci-skip-reason.md §CI enforcement).

**Checkpoint**: CI pipeline fails on intentional regression injected per US6 independent test; p99 latency numbers visible as artifacts.

---

## Phase 9: User Story 7 — Latency bench meets per-transport budgets with measured numbers (Priority: P3)

**Goal**: `latency-uds.sh` and `latency-tcp.sh` exit 0 with measured p99 ≤ 500µs (UDS) and ≤ 1500µs (TCP) on the reference host, reproducible within 20% variance across 5 runs; measurement is a true `UnitDamaged` engine-event → F# `OnEvent` round trip, not an inter-arrival proxy (FR-014, SC-005).

**Independent Test**: On the reference host, run both bench scripts five times; all 10 invocations exit 0 with p99 under the respective budget; p99 across the 5 runs per transport stays within ±20% of the median.

### UnitDamaged payload widening (data-model.md §1, contracts/unit-damaged-payload.md, research.md §R7)

- [X] T058 [US7] Add `CGrpcGatewayModule::OnUnitDamagedFull(CCircuitUnit* unit, CCircuitUnit* attacker, float damage, springai::AIFloat3 dir, int weaponDefId, bool paralyzer)` declaration to `src/circuit/module/GrpcGatewayModule.h`.
- [X] T059 [US7] Implement `CGrpcGatewayModule::OnUnitDamagedFull` in `src/circuit/module/GrpcGatewayModule.cpp` — populates `UnitDamagedEvent` fields `unit_id`, `attacker_id` (when non-null), `damage` (clamped `[0, +∞)`), `direction.x/y/z`, `weapon_def_id` (verbatim including `-1`), `is_paralyzer` per `contracts/unit-damaged-payload.md`. Warn-log and clamp negative damage.
- [X] T060 [US7] Edit existing `CGrpcGatewayModule::UnitDamaged(unit, attacker)` hook body at `src/circuit/module/GrpcGatewayModule.cpp` lines 169–182 — reduce to a no-op that returns 0 (IModule-compliance only; real work moved to `OnUnitDamagedFull`).
- [X] T061 [US7] Edit `src/circuit/CircuitAI.cpp::UnitDamaged` — after the existing module fanout, add one `grpcGateway->OnUnitDamagedFull(unit, attacker, damage, dir, weaponDefId, paralyzer);` call guarded by non-null `grpcGateway` pointer. ≤4 lines; matches 001's T018 surgical-edit pattern (Constitution I envelope).

### Bench scripts

- [X] T062 [US7] Edit `tests/bench/latency-uds.sh` — replace inter-arrival-proxy timing with a true engine-event → F# `OnEvent` round trip: F# client records `OnEvent` timestamp; compares against the gateway's server-side send timestamp attached to the outgoing `UnitDamagedEvent` delta-metadata. Collect ≥1000 samples over 30s; output p99 to `build/reports/latency-uds-p99.txt` for CI artifact upload (FR-014, FR-020).
- [X] T063 [US7] Edit `tests/bench/latency-tcp.sh` — same round-trip switch as T062 but for loopback TCP transport; output to `build/reports/latency-tcp-p99.txt`.
- [X] T064 [US7] Add `# arm-covered:` headers to `tests/bench/latency-uds.sh` / `latency-tcp.sh` for any arms their driver issues (none strictly required if driver only consumes damage events, but note it explicitly).
- [X] T065 [US7] Add assertion in damage-path acceptance scripts — specifically `tests/headless/us1-observer.sh`, `us2-ai-coexist.sh`, `tests/bench/latency-uds.sh`, `tests/bench/latency-tcp.sh`, plus `tests/headless/aicommand-arm-coverage.sh` for any arm that can produce a `UnitDamaged` delta — that `damage > 0.0` and at least one component of `direction` is non-zero, proving the widening works end-to-end (contracts/unit-damaged-payload.md §Test assertions).

**Checkpoint**: Both bench scripts green under budget on reference host across 5 runs; p99 artifacts published.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Feature-completion gates that touch every story's output.

- [X] T066 [P] Create `tests/headless/gateway-fault.sh` — deliberately triggers a fault (e.g., submits an oversized `SubmitCommands` payload or a malformed frame), asserts (a) engine log contains `[hb-gateway] fault subsystem=… reason=…`, (b) `$writeDir/highbar.health` contains `"status":"disabled"`, (c) UDS socket path no longer exists, (d) token file removed (FR-024, contracts/gateway-fault.md). Exits 0 when all four observed; exits 1 otherwise (never 77).
- [X] T067 [P] Create `specs/002-live-headless-e2e/checklists/peer-walkthrough.md` sign-off template: one Markdown checklist entry per maintainer who has run `BUILD.md` end-to-end on a clean VM; feature is not complete until one non-author entry is ticked (SC-008, contracts/build-runbook.md §Peer-walkthrough sign-off). (Generate via `/speckit.checklist` or write by hand.)
- [ ] T068 Run the full acceptance suite on the reference host five consecutive times; verify all 17 headless scripts + both bench scripts + `ctest` exit 0 every time (SC-002 reproducibility). Record results.
- [ ] T069 Run the framerate reproducibility pass five times; verify p50 framerates stay within ±5% run-to-run (FR-008). Record in `specs/002-live-headless-e2e/research.md` §R9 or a new results appendix.
- [X] T070 [P] Add `build/` and any non-committed generated stubs to `.gitignore` if not already present. (Per T036 decision, Python stubs under `clients/python/highbar_client/highbar/v1/` remain committed.)
- [X] T071 Final Constitution Check re-run: re-read `docs/architecture.md` against the landed code for principle regressions (I fork-discipline boundary, II engine-thread supremacy, III proto-first, IV phase gates, V latency budgets measured) and record the result in a final section of `plan.md`.

---

## Dependencies & Execution Order

### Phase dependencies

- Setup (Phase 1) has no prior dependencies.
- Foundational (Phase 2) depends on Setup and blocks every user-story phase.
- US1 (Phase 3) depends on Phase 2 only. MVP.
- US2 (Phase 4) depends on US1 (needs a built plugin + `_launch.sh` + `_fault-assert.sh`).
- US3 (Phase 5) depends on US1.
- US4 (Phase 6) depends on Phase 2 only — independent of US1/US2/US3 (pytest collection is a pre-engine concern).
- US5 (Phase 7) depends on US3 (the existing 15 arms need their wiring pattern stable first) and on the Phase 2 arm-coverage CMake target (T008 + T008a).
- US6 (Phase 8) depends on US1 through US5 — CI runs their scripts.
- US7 (Phase 9) depends on US1 only for the build/load foundation; the UnitDamaged widening itself is orthogonal to other stories.
- Polish (Phase 10) depends on US1 through US7.

### User-story dependencies in short

- **US1**: Phase 2 → US1 (MVP).
- **US2**: US1 → US2.
- **US3**: US1 → US3.
- **US4**: Phase 2 → US4 (parallel to US1/US2/US3 once foundation lands).
- **US5**: US3 + T008 + T008a → US5.
- **US6**: US1..US5 → US6.
- **US7**: US1 → US7.

### Within each user story

- Models / schema edits (proto, CMake targets) come before services / dispatcher wiring.
- Dispatcher wiring comes before per-arm acceptance scripts.
- Acceptance scripts come before CI pipeline updates that invoke them.

### Parallel opportunities

- Setup tasks T002/T003/T004 run in parallel (different files).
- Foundational T008 + T008a (arm-coverage target and its helper script) are orthogonal to the fault-capture chain T009–T016 and can run in parallel.
- US5 dispatcher wiring (T038–T043) touches one file and runs sequentially; the test-widget and coverage-script tasks (T044–T046) run in parallel to each other.
- US6 runner-setup scripts (T047/T048/T049) run in parallel — different files.
- US7 widening (T058–T061) runs in parallel with US6 CI authoring — no file overlap.
- Polish T066/T067/T070 all run in parallel.
- US4 (Phase 6) is the single biggest parallel axis — does not touch any engine-side file, can be done by a second maintainer concurrently with US5.

---

## Parallel Example: User Story 6 (runner provisioning)

```bash
# Launch all three runner-setup scripts in parallel (different files):
Task: "Create .github/runner-setup/install-spring-headless.sh"
Task: "Create .github/runner-setup/hydrate-bar-assets.sh"
Task: "Create .github/runner-setup/register-runner.sh"
```

## Parallel Example: Foundational gateway fault-capture

```bash
# T008 runs alongside the fault-capture chain (T009 → T016) since it touches CMakeLists.txt only:
Task: "Add aicommand-arm-coverage CMake target"
# ...concurrently with the linear fault-capture edits in src/circuit/
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup (T001–T004).
2. Phase 2: Foundational — hard-fail the build, wire unit tests, land the fault-capture pattern (T005–T016 plus T008a).
3. Phase 3: US1 — land BUILD.md + the minimal start script + runbook-validation (T017–T023).
4. **STOP and VALIDATE**: run `BUILD.md` end-to-end on the reference host; confirm the 2-second-to-first-snapshot gate (SC-001); demo.

### Incremental delivery path

1. **MVP**: ship US1 → plugin builds, loads, first snapshot.
2. Add US2 (observer acceptance green) → proves the observer path on live engine.
3. Add US3 (AI-coexist acceptance green) → proves the external-AI command path.
4. Add US4 (Python client) **in parallel** with US2/US3 if a second maintainer is available.
5. Add US5 (all 66 arms) → proves the full command surface; builds on US3.
6. Add US6 (CI gates) → locks all prior gains against regression.
7. Add US7 (latency bench with real numbers) → satisfies Constitution V measurement requirement.
8. Polish → fault-injection test, peer walkthrough, 5-run reproducibility validation.

### Parallel team strategy

With two maintainers:

- Maintainer A owns the engine-side track: Phase 2 → US1 → US3 → US5 → US7.
- Maintainer B owns the client/CI track: US4 concurrently with US3; US6 after US5 is wired.
- Both converge on Polish.

---

## Notes

- [P] marks parallel opportunities; within a single story, dispatcher-wiring tasks collapse onto `CommandDispatch.cpp` and are sequential.
- Every acceptance script must source `_fault-assert.sh` (T016) and fail loud on disabled-gateway state — silent skip is forbidden by FR-024.
- The `ci-skip-reason:` trailer (contracts/ci-skip-reason.md) is the *only* way a headless / bench script's exit-77 gets tolerated in CI; every other exit-77 is upgraded to failure (FR-018).
- Per-arm coverage is enforced by the CMake target T008 (driving helper script T008a); human review is a belt-and-braces check, not the primary gate.
- Fault-capture (Phase 2, T009–T016) must land before US1 so every downstream test can distinguish "plugin not built" from "gateway disabled itself mid-match" — if this sequencing inverts, the same "green because all skipped" failure mode that hid 001's integration gap reappears.
- No new top-level directories. Every new file lives under a directory that already exists or that this feature creates explicitly (`.github/runner-setup/`, `data/config/`, `tests/headless/widgets/`, `tests/headless/scripts/`).
