# Tasks: Comprehensive Admin Channel Behavioral Control

**Input**: Design documents from `/home/developer/projects/HighBarV3/specs/020-admin-behavior-tests/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`
**Tests**: Required. This feature is a behavioral test suite and the specification requires proof for successful actions, rejected actions, evidence reports, capabilities, cleanup, and repeatability.
**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently after the shared foundation is complete.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and does not depend on another incomplete task in the same phase.
- **[Story]**: Required only for user-story phases.
- Every task includes exact repository paths.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the deterministic fixture, stable entry points, and Python module/test shells needed by all admin behavioral stories.

- [X] T001 Create deterministic admin fixture metadata with teams, resources, unit defs, spawn positions, transferable unit hints, observation tolerances, and repeat-run reset expectations in `tests/fixtures/admin_behavior/fixture.yaml`
- [X] T002 Create the admin behavioral Spring startscript for the fixture in `tests/headless/scripts/admin-behavior.startscript`
- [X] T003 [P] Create the stable headless wrapper skeleton with argument parsing and exit-code placeholders in `tests/headless/admin-behavioral-control.sh`
- [X] T004 [P] Create admin action and observation module skeletons in `clients/python/highbar_client/behavioral_coverage/admin_actions.py` and `clients/python/highbar_client/behavioral_coverage/admin_observations.py`
- [X] T005 [P] Create admin report module and unit-test shells in `clients/python/highbar_client/behavioral_coverage/admin_report.py`, `clients/python/tests/behavioral_coverage/test_admin_actions.py`, `clients/python/tests/behavioral_coverage/test_admin_observations.py`, and `clients/python/tests/behavioral_coverage/test_admin_report.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the proto contract, generated clients, validation context, and engine-thread execution path that all stories depend on.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Add `UnitTransferAction` and the `unit_transfer = 16` `AdminAction` oneof arm in `proto/highbar/service.proto`
- [X] T007 Add additive capability metadata for valid team ids, resource ids, unit def ids, map extents, speed bounds, and run-mode flags in `proto/highbar/service.proto`
- [X] T008 Regenerate generated stubs after the proto changes in `clients/python/highbar_client/highbar/service_pb2.py`, `clients/python/highbar_client/highbar/service_pb2_grpc.py`, `build/gen/highbar/service.pb.h`, `build/gen/highbar/service.grpc.pb.h`, and `build/gen/csharp/Service.cs`
- [X] T009 [P] Add Python helper coverage for transfer-capable admin actions in `clients/python/highbar_client/admin.py` and `clients/python/tests/test_admin.py`
- [X] T010 [P] Confirm F# generated-client compatibility for the expanded admin proto in `clients/fsharp/src/Admin.fs` and `clients/fsharp/HighBar.Proto.csproj`
- [X] T011 Add `unit_transfer` control naming, capability advertising, and audit action typing in `src/circuit/grpc/AdminController.cpp` and `src/circuit/grpc/AdminController.h`
- [X] T012 Add validation settings for speed bounds, fixture teams, resources, unit defs, map extents, live unit ownership, and stale basis checks in `src/circuit/grpc/AdminController.h` and `src/circuit/grpc/AdminController.cpp`
- [X] T013 Add an engine-thread admin execution queue and result handoff API in `src/circuit/module/GrpcGatewayModule.h` and `src/circuit/module/GrpcGatewayModule.cpp`
- [X] T014 Refactor `ExecuteAdminAction` to validate on the gRPC worker and accept successful mutations for gateway engine-thread execution in `src/circuit/grpc/AdminService.h`, `src/circuit/grpc/AdminService.cpp`, and `src/circuit/module/GrpcGatewayModule.cpp`
- [X] T015 Add shared Python dataclasses/enums for `AdminCaller`, `AdminBehaviorScenario`, `AdminObservation`, `AdminEvidenceRecord`, and `AdminBehaviorRun` in `clients/python/highbar_client/behavioral_coverage/admin_actions.py`

**Checkpoint**: Foundation ready - generated clients compile, admin transfer is represented in the wire contract, and accepted execution has an engine-thread path.

---

## Phase 3: User Story 1 - Prove Admin Actions Change the Running Match (Priority: P1) MVP

**Goal**: An operator can execute each supported admin action in a live local match and receive proof that the running match state changed as requested.

**Independent Test**: Start the controlled fixture, execute pause, resume, speed, resource grant, unit spawn, and unit transfer one at a time, then compare before/after state-stream evidence for each accepted action.

### Tests for User Story 1

Write these tests first and confirm they fail before implementation.

- [X] T016 [P] [US1] Add C++ unit tests for `unit_transfer` validation, capability exposure, and success-result shaping in `tests/unit/admin_control_test.cc`
- [X] T017 [P] [US1] Add C++ integration tests proving accepted admin execution is queued for engine-thread application and audited in `tests/integration/admin_control_test.cc`
- [X] T018 [P] [US1] Add Python tests for success scenario builders for pause, resume, speed, resource, spawn, and transfer in `clients/python/tests/behavioral_coverage/test_admin_actions.py`
- [X] T019 [P] [US1] Add Python tests for success observation predicates for stopped frames, resumed frames, speed tolerance, resource deltas, spawn position, and transfer ownership in `clients/python/tests/behavioral_coverage/test_admin_observations.py`

### Implementation for User Story 1

- [X] T020 [US1] Implement engine-thread handlers for pause, resume, global speed, resource grant, unit spawn, and unit transfer in `src/circuit/module/GrpcGatewayModule.cpp`
- [X] T021 [US1] Ensure state snapshots or deltas expose frame progression, team resources, unit definition, unit position, and unit owner data needed by observations in `proto/highbar/state.proto` and `src/circuit/grpc/DeltaBus.cpp`
- [X] T022 [US1] Implement success admin action builders and cleanup action builders in `clients/python/highbar_client/behavioral_coverage/admin_actions.py`
- [X] T023 [US1] Implement state-stream before/after collectors and action-specific success predicates in `clients/python/highbar_client/behavioral_coverage/admin_observations.py`
- [X] T024 [US1] Add the success scenario execution flow to the admin behavioral CLI in `clients/python/highbar_client/behavioral_coverage/__main__.py`
- [X] T025 [US1] Implement pause resume cleanup, normal-speed restoration, and lease release/expiry handling after success scenarios in `clients/python/highbar_client/behavioral_coverage/admin_actions.py`
- [X] T026 [US1] Wire the headless wrapper to launch the fixture, wait for gateway readiness, run the Python success scenarios, and pass through the suite exit code in `tests/headless/admin-behavioral-control.sh`

**Checkpoint**: User Story 1 is fully functional and independently testable with the success scenarios in the controlled live fixture.

---

## Phase 4: User Story 2 - Reject Unsafe or Invalid Admin Requests (Priority: P1)

**Goal**: Invalid, unauthorized, stale, or conflicting admin requests are rejected before they mutate match state.

**Independent Test**: Submit rejection scenarios in the controlled fixture and verify both the structured result and unchanged relevant match state.

### Tests for User Story 2

Write these tests first and confirm they fail before implementation.

- [X] T027 [P] [US2] Add C++ unit tests for unauthorized caller, invalid speed, invalid resource, invalid spawn, invalid transfer, stale basis, and lease conflict rejection in `tests/unit/admin_control_test.cc`
- [X] T028 [P] [US2] Add Python tests for rejection scenario builders and expected statuses in `clients/python/tests/behavioral_coverage/test_admin_actions.py`
- [X] T029 [P] [US2] Add Python tests for unchanged-state rejection predicates for speed, resources, units, ownership, and leases in `clients/python/tests/behavioral_coverage/test_admin_observations.py`

### Implementation for User Story 2

- [X] T030 [US2] Implement rejection validation for unauthorized roles, invalid speed, invalid resource grants, invalid spawns, invalid transfers, stale basis, and lease conflicts in `src/circuit/grpc/AdminController.cpp`
- [X] T031 [US2] Ensure rejected `ValidateAdminAction` and `ExecuteAdminAction` responses never enqueue engine-thread work in `src/circuit/grpc/AdminService.cpp` and `src/circuit/module/GrpcGatewayModule.cpp`
- [X] T032 [US2] Implement rejection scenario definitions for unauthorized, invalid speed, invalid resource, invalid spawn, invalid transfer, stale basis, and lease conflict cases in `clients/python/highbar_client/behavioral_coverage/admin_actions.py`
- [X] T033 [US2] Implement unchanged-state observation predicates and mutation-detection diagnostics in `clients/python/highbar_client/behavioral_coverage/admin_observations.py`
- [X] T034 [US2] Add lease-conflict setup, heartbeat, and cleanup behavior for rejection scenarios in `clients/python/highbar_client/behavioral_coverage/admin_actions.py`
- [X] T035 [US2] Add rejection scenario execution and failure classification to the admin behavioral CLI in `clients/python/highbar_client/behavioral_coverage/__main__.py`

**Checkpoint**: User Story 2 is independently testable and proves rejection behavior without relying on User Story 1 success assertions.

---

## Phase 5: User Story 3 - Make Behavioral Evidence Easy to Review (Priority: P2)

**Goal**: A developer can run one suite and review clear per-control evidence, prerequisite failures, logs, and cleanup status.

**Independent Test**: Run the suite and inspect `build/reports/admin-behavior/run-report.md`, `evidence.jsonl`, and `summary.csv` for complete pass/fail evidence.

### Tests for User Story 3

Write these tests first and confirm they fail before implementation.

- [X] T036 [P] [US3] Add Python tests for JSONL, CSV, Markdown report rendering, required fields, and failure details in `clients/python/tests/behavioral_coverage/test_admin_report.py`
- [X] T037 [US3] Add Python tests for prerequisite, behavioral, internal-error, cleanup, and repeatability exit classifications in `clients/python/tests/behavioral_coverage/test_admin_report.py`

### Implementation for User Story 3

- [X] T038 [US3] Implement `evidence.jsonl`, `summary.csv`, `run-report.md`, and repeat summary rendering in `clients/python/highbar_client/behavioral_coverage/admin_report.py`
- [X] T039 [US3] Implement prerequisite detection and exit `77` mapping for missing BAR runtime, missing token, disabled gateway, or missing fixture files in `tests/headless/admin-behavioral-control.sh`
- [X] T040 [US3] Copy or link engine and coordinator logs into `build/reports/admin-behavior/logs/` from `tests/headless/admin-behavioral-control.sh`
- [X] T041 [US3] Add CLI arguments for `--startscript`, `--output-dir`, `--timeout-seconds`, and `--repeat-index` in `clients/python/highbar_client/behavioral_coverage/__main__.py`
- [X] T042 [US3] Map evidence failures to `prerequisite_missing`, `permission_not_rejected`, `invalid_value_not_rejected`, `lease_conflict_not_rejected`, `effect_not_observed`, `unexpected_mutation`, `capability_mismatch`, `cleanup_failed`, and `internal_error` in `clients/python/highbar_client/behavioral_coverage/admin_report.py`
- [X] T043 [US3] Update the developer review workflow and expected artifacts in `specs/020-admin-behavior-tests/quickstart.md`

**Checkpoint**: User Story 3 produces reviewable durable evidence and distinguishes setup failures from behavioral regressions.

---

## Phase 6: User Story 4 - Discover Supported Admin Controls Consistently (Priority: P3)

**Goal**: Clients can query admin capabilities and only attempt controls that are advertised and executable in the current run mode.

**Independent Test**: Query capabilities in enabled and restricted modes, then verify advertised controls match execution or rejection behavior.

### Tests for User Story 4

Write these tests first and confirm they fail before implementation.

- [X] T044 [P] [US4] Add C++ unit tests for enabled, disabled, restricted, and transfer-capable admin capability responses in `tests/unit/admin_control_test.cc`
- [X] T045 [P] [US4] Add Python tests for capability matching, disabled-control handling, and advertised-but-not-executable failures in `clients/python/tests/behavioral_coverage/test_admin_actions.py`

### Implementation for User Story 4

- [X] T046 [US4] Populate capability metadata from runtime validation settings and fixture data in `src/circuit/grpc/AdminController.cpp` and `src/circuit/grpc/CapabilityProvider.cpp`
- [X] T047 [US4] Use `GetAdminCapabilities` to select executable scenarios and fail advertised-but-not-executable controls in `clients/python/highbar_client/behavioral_coverage/admin_actions.py`
- [X] T048 [US4] Implement disabled and restricted mode consistency checks in `clients/python/highbar_client/behavioral_coverage/admin_actions.py` and `clients/python/highbar_client/behavioral_coverage/admin_report.py`
- [X] T049 [US4] Verify generated Python and F# clients can read the expanded capability response in `clients/python/tests/test_admin.py` and `clients/fsharp/src/Admin.fs`

**Checkpoint**: User Story 4 is independently testable and capability discovery matches executable behavior.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, repeatability, validation commands, and cleanup across all stories.

- [X] T050 [P] Update admin client documentation for transfer, capabilities, and behavioral suite usage in `clients/python/README.md`
- [X] T051 [P] Update headless documentation for prerequisites, exit codes, reports, and repeatability in `tests/headless/README.md`
- [X] T052 Add three-run repeatability orchestration and leftover pause/speed/lease indicators in `tests/headless/admin-behavioral-control.sh` and `clients/python/highbar_client/behavioral_coverage/admin_report.py`
- [X] T053 Run proto lint and generation validation for `proto/highbar/service.proto` with `buf lint proto` and `cd proto && buf generate`
- [X] T054 Run C++ validation for `tests/unit/admin_control_test.cc` and `tests/integration/admin_control_test.cc` with `cmake --build build --target admin_control_test` and `ctest --test-dir build --output-on-failure -R 'admin_control|command_capabilities'`
- [X] T055 Run Python and F# validation for `clients/python/tests/` and `clients/fsharp/HighBar.Client.fsproj` with `uv run --project clients/python pytest clients/python/tests/test_admin.py clients/python/tests/behavioral_coverage/` and `dotnet build clients/fsharp/HighBar.Client.fsproj`
- [X] T056 Add repeat-run cleanup or fixture reset handling for resource grants, spawned units, and transferred ownership in `clients/python/highbar_client/behavioral_coverage/admin_actions.py` and `tests/headless/admin-behavioral-control.sh`
- [X] T057 Run latency budget validation for Constitution V with the existing UnitDamaged-to-F# callback microbench in `clients/fsharp/bench/Latency/Latency.fsproj` and `clients/fsharp/bench/Latency/Program.fs`, asserting p99 <= 500us on UDS and <= 1.5ms on loopback TCP
- [X] T058 Run the live admin behavioral suite and repeatability check for `tests/headless/admin-behavioral-control.sh`, storing evidence under `build/reports/admin-behavior/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion and blocks all user stories.
- **User Stories (Phase 3+)**: Depend on Foundational completion.
- **Polish (Phase 7)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **User Story 1 (P1)**: Start after Phase 2. This is the MVP.
- **User Story 2 (P1)**: Start after Phase 2. Can be implemented in parallel with US1 if validation and observation file ownership is coordinated.
- **User Story 3 (P2)**: Start after Phase 2; it can use synthetic records before US1/US2 are complete, then integrate real records.
- **User Story 4 (P3)**: Start after Phase 2; final capability matching should run after US1/US2 action behavior exists.

### Within Each User Story

- Tests first, and they should fail before implementation.
- Proto and generated clients before C++/Python code that references new fields.
- C++ validation before engine-thread execution handlers.
- Python scenario builders before CLI orchestration.
- Observations and reports before live-suite pass/fail gating.

---

## Parallel Opportunities

- Setup tasks T003, T004, and T005 can run in parallel after T001/T002 ownership is clear.
- Foundational tasks T009 and T010 can run in parallel after T006-T008.
- US1 tests T016-T019 can run in parallel.
- US2 tests T027-T029 can run in parallel.
- US3 report tests T036 and T037 share `clients/python/tests/behavioral_coverage/test_admin_report.py` and should run sequentially or be coordinated in one edit.
- US4 tests T044-T045 can run in parallel.
- Documentation tasks T050-T051 can run in parallel.

## Parallel Example: User Story 1

```bash
Task: "T016 [US1] Add C++ unit tests in tests/unit/admin_control_test.cc"
Task: "T017 [US1] Add C++ integration tests in tests/integration/admin_control_test.cc"
Task: "T018 [US1] Add Python action builder tests in clients/python/tests/behavioral_coverage/test_admin_actions.py"
Task: "T019 [US1] Add Python observation tests in clients/python/tests/behavioral_coverage/test_admin_observations.py"
```

## Parallel Example: User Story 2

```bash
Task: "T027 [US2] Add C++ rejection tests in tests/unit/admin_control_test.cc"
Task: "T028 [US2] Add Python rejection action tests in clients/python/tests/behavioral_coverage/test_admin_actions.py"
Task: "T029 [US2] Add unchanged-state observation tests in clients/python/tests/behavioral_coverage/test_admin_observations.py"
```

## Parallel Example: User Story 3

```bash
Task: "T036 [US3] Add report rendering tests in clients/python/tests/behavioral_coverage/test_admin_report.py"

# Then, in the same file after T036 lands:
Task: "T037 [US3] Add exit classification tests in clients/python/tests/behavioral_coverage/test_admin_report.py"
```

## Parallel Example: User Story 4

```bash
Task: "T044 [US4] Add C++ capability tests in tests/unit/admin_control_test.cc"
Task: "T045 [US4] Add Python capability matching tests in clients/python/tests/behavioral_coverage/test_admin_actions.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 for success-path behavioral proof.
3. Stop and validate US1 with the controlled fixture and `tests/headless/admin-behavioral-control.sh`.

### Incremental Delivery

1. Add US1 to prove successful live mutations.
2. Add US2 to prove rejected requests leave match state unchanged.
3. Add US3 to make evidence reviewable and CI-friendly.
4. Add US4 to align capability discovery with executable behavior.
5. Finish polish validation and three-run repeatability.

### Validation Gates

1. `buf lint proto`
2. `cd proto && buf generate`
3. `cmake --build build --target admin_control_test`
4. `ctest --test-dir build --output-on-failure -R 'admin_control|command_capabilities'`
5. `uv run --project clients/python pytest clients/python/tests/test_admin.py clients/python/tests/behavioral_coverage/`
6. `dotnet build clients/fsharp/HighBar.Client.fsproj`
7. Run the Constitution V latency microbench and confirm p99 <= 500us on UDS and <= 1.5ms on loopback TCP
8. `tests/headless/admin-behavioral-control.sh --startscript tests/headless/scripts/admin-behavior.startscript --output-dir build/reports/admin-behavior --timeout-seconds 10`

---

## Notes

- `[P]` tasks are parallelizable only when assigned without overlapping file edits.
- User Story 1 is the suggested MVP because it proves accepted admin actions change the live match.
- Pause and speed scenarios must always attempt cleanup before continuing or exiting.
- Missing local BAR/Spring prerequisites must exit `77`, not `1`.
- Rejections must be proven by both structured status and unchanged observed state.
