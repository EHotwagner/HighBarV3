# Tasks: Itertesting Channel Stability

**Input**: Design documents from `/specs/013-itertesting-channel-stability/`  
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Include pytest, synthetic headless validation, and prepared-environment live rerun tasks because the feature specification defines independent test criteria for every user story.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the existing Itertesting workflow for 013-specific lifecycle, fixture, and classification work.

- [X] T001 Add 013 live-closeout regression scaffolding in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py` and `tests/headless/test_live_itertesting_hardening.sh`
- [X] T002 [P] Add 013 classification/report test scaffolding in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py` and `clients/python/tests/behavioral_coverage/test_itertesting_report.py`
- [X] T003 [P] Add 013 artifact-inspection helper coverage in `tests/headless/itertesting.sh` and `tests/headless/test_live_itertesting_hardening.sh`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared lifecycle, fixture, and report infrastructure that MUST be complete before ANY user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Define or tighten 013 closeout record fields in `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`
- [X] T005 [P] Centralize required-vs-optional fixture mapping helpers in `clients/python/highbar_client/behavioral_coverage/bootstrap.py`
- [X] T006 [P] Centralize channel-failure signal and precedence helpers in `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`
- [X] T007 Wire shared live run serialization for `channel_health`, `fixture_profile`, `fixture_provisioning`, and `failure_classifications` in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T008 Render baseline fixture, channel-health, and failure-cause sections in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [X] T009 [P] Add foundational manifest/report serialization regressions in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py` and `clients/python/tests/behavioral_coverage/test_itertesting_report.py`

**Checkpoint**: Foundation ready. User story implementation can now begin.

---

## Phase 3: User Story 1 - Keep Live Validation Running (Priority: P1) 🎯 MVP

**Goal**: Keep the live Itertesting closeout workflow alive long enough to evaluate command outcomes, and emit a specific lifecycle blocker when it cannot.

**Independent Test**: Run the documented live closeout command in a prepared environment and confirm the session does not stop because the command channel disconnects during dispatch.

### Tests for User Story 1

- [X] T010 [P] [US1] Add prepared-live continuity and first-failure-stage regressions in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`
- [X] T011 [P] [US1] Add live wrapper retry and lifecycle-artifact checks in `tests/headless/test_live_itertesting_hardening.sh`
- [ ] T012 [P] [US1] Add command-channel lifecycle integration regression in `tests/integration/ai_move_flow_test.cc`
- [X] T013 [US1] Add readiness-gate regressions for interrupted and fixture-blocked runs in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py` and `clients/python/tests/behavioral_coverage/test_itertesting_report.py`

### Implementation for User Story 1

- [ ] T014 [US1] Harden command-channel close sequencing and lifecycle ownership in `src/circuit/grpc/HighBarService.cpp` and `src/circuit/module/GrpcGatewayModule.cpp`
- [ ] T015 [US1] Preserve queued command draining across live-session degradation in `src/circuit/grpc/CommandDispatch.cpp` and `src/circuit/grpc/CommandQueue.cpp`
- [X] T016 [US1] Record the first lifecycle failure stage, failure signal, and attempted-command count in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`
- [X] T017 [US1] Surface manifest-backed lifecycle diagnostics and retry decisions in `tests/headless/itertesting.sh`
- [X] T018 [US1] Render specific lifecycle blocker messaging in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [X] T019 [US1] Enforce `contract_health_decision` and `ready_for_itertesting` gating for interrupted or fixture-blocked runs in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`, `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`, and `tests/headless/itertesting.sh`

**Checkpoint**: User Story 1 should keep the live workflow running or report exactly what disconnected and when.

---

## Phase 4: User Story 2 - Cover Required Fixtures Before Judging Behavior (Priority: P2)

**Goal**: Ensure the live bootstrap provides required fixtures for the intended command surface, or explicitly marks commands as fixture-blocked before behavior is judged.

**Independent Test**: Run the live Itertesting workflow and confirm that commands needing specialized targets are either exercised with prepared fixtures or explicitly classified as fixture-blocked before transport or behavior is blamed.

### Tests for User Story 2

- [X] T020 [P] [US2] Add missing-fixture and affected-command classification regressions in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`
- [X] T021 [P] [US2] Add fixture-provisioning report-section and summary-count regressions in `clients/python/tests/behavioral_coverage/test_itertesting_report.py`

### Implementation for User Story 2

- [X] T022 [US2] Expand specialized live fixture provisioning coverage in `clients/python/highbar_client/behavioral_coverage/bootstrap.py`
- [X] T023 [US2] Persist provisioned fixture classes, missing fixture classes, and affected command ids in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`
- [X] T024 [US2] Classify fixture-blocked commands before behavioral failure in `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`
- [X] T025 [US2] Validate fixture-blocker output and affected-command reporting in `tests/headless/test_live_itertesting_hardening.sh` and `tests/headless/itertesting.sh`
- [X] T026 [US2] Render fixture-provisioning summaries for maintainers in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`

**Checkpoint**: User Story 2 should make missing fixtures explicit and keep incomplete setup from looking like a behavior regression.

---

## Phase 5: User Story 3 - Distinguish Transport Instability From Command Behavior (Priority: P3)

**Goal**: Keep transport-adjacent outcomes distinct from true command-behavior failures, especially for repeated reruns and commands such as `cmd-build-unit`.

**Independent Test**: Rerun the same live workflow and confirm that transport-adjacent failures are classified separately from true command-behavior regressions, especially for commands that previously oscillated between verified and failed outcomes.

### Tests for User Story 3

- [X] T027 [P] [US3] Add transport-versus-behavior precedence regressions for interrupted and healthy runs in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`
- [ ] T028 [P] [US3] Add repeated-rerun comparison and summary regressions for transport-adjacent outcomes in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`

### Implementation for User Story 3

- [X] T029 [US3] Tighten precedence between transport interruption, missing fixture, predicate gaps, and behavioral failure in `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`
- [ ] T030 [US3] Preserve transport-adjacent classifications across rerun comparisons in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T031 [US3] Render transport-adjacent versus behavior-focused summaries in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [X] T032 [US3] Gate behavior-focused failure output on stable lifecycle and fixture evidence in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py` and `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`
- [X] T033 [US3] Add alternate-speed startscript coverage in `tests/headless/scripts/minimal-slow.startscript`, `specs/013-itertesting-channel-stability/quickstart.md`, and `specs/013-itertesting-channel-stability/contracts/transport-adjacent-failure-classification.md`

**Checkpoint**: User Story 3 should let maintainers tell whether a failure belongs to transport instability or to command behavior on first review.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final consistency, validation, and documentation across all stories.

- [X] T034 [P] Align 013 contract and validation docs with implemented fields in `specs/013-itertesting-channel-stability/contracts/live-channel-health-record.md`, `specs/013-itertesting-channel-stability/contracts/fixture-provisioning-and-blockers.md`, and `specs/013-itertesting-channel-stability/contracts/live-closeout-validation-suite.md`
- [X] T035 Run and stabilize Python regression coverage in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`, `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`, and `clients/python/tests/behavioral_coverage/test_itertesting_report.py`
- [X] T036 Run and stabilize synthetic live-hardening validation in `tests/headless/test_live_itertesting_hardening.sh` and `reports/itertesting/`
- [X] T037 Run Constitution V transport latency gates in `tests/bench/latency-uds.sh` and `tests/bench/latency-tcp.sh`
- [X] T038 Run three prepared live closeout reruns and inspect `manifest.json`, `run-report.md`, and `campaign-stop-decision.json` via `tests/headless/itertesting.sh` and `reports/itertesting/`
- [X] T039 Run alternate-speed confirmation via `HIGHBAR_STARTSCRIPT=tests/headless/scripts/minimal-slow.startscript tests/headless/itertesting.sh` and inspect `reports/itertesting/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies. Can begin immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1. Blocks all user stories.
- **Phase 3 (US1)**: Depends on Phase 2.
- **Phase 4 (US2)**: Depends on Phase 2. Best validated after US1 lifecycle fixes are merged, but should remain independently testable.
- **Phase 5 (US3)**: Depends on Phase 2. Best validated after US1 and US2 evidence fields stabilize, but should remain independently testable.
- **Phase 6 (Polish)**: Depends on completion of the selected user stories.

### User Story Dependencies

- **US1 (P1)**: No hard dependency on other stories once foundational tasks are complete.
- **US2 (P2)**: No hard dependency on US3. Uses shared fixture and report plumbing from Phase 2.
- **US3 (P3)**: No hard dependency on US2, but benefits from the stable lifecycle and fixture evidence produced by US1 and US2.

### Within Each User Story

- Write the story tests first and confirm they fail before implementation.
- Land shared model or helper changes before story-specific orchestration that consumes them.
- Update maintainer-facing report or wrapper output after the underlying manifest fields exist.
- Run the story’s independent validation before moving on to the next priority.

### Parallel Opportunities

- `T002` and `T003` can run in parallel after `T001`.
- `T005`, `T006`, and `T009` can run in parallel after `T004`.
- US1 test tasks `T010`, `T011`, and `T012` can run in parallel.
- US2 test tasks `T020` and `T021` can run in parallel.
- US3 test tasks `T027` and `T028` can run in parallel.
- Polish task `T034` can proceed alongside validation tasks once the user stories land.

---

## Parallel Example: User Story 1

```bash
Task: "Add prepared-live continuity and first-failure-stage regressions in clients/python/tests/behavioral_coverage/test_itertesting_runner.py"
Task: "Add live wrapper retry and lifecycle-artifact checks in tests/headless/test_live_itertesting_hardening.sh"
Task: "Add command-channel lifecycle integration regression in tests/integration/ai_move_flow_test.cc"
```

---

## Parallel Example: User Story 2

```bash
Task: "Add missing-fixture and affected-command classification regressions in clients/python/tests/behavioral_coverage/test_live_failure_classification.py"
Task: "Add fixture-provisioning report-section and summary-count regressions in clients/python/tests/behavioral_coverage/test_itertesting_report.py"
```

---

## Parallel Example: User Story 3

```bash
Task: "Add transport-versus-behavior precedence regressions for interrupted and healthy runs in clients/python/tests/behavioral_coverage/test_live_failure_classification.py"
Task: "Add repeated-rerun comparison and summary regressions for transport-adjacent outcomes in clients/python/tests/behavioral_coverage/test_itertesting_runner.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Implement Phase 3 (US1) only.
3. Validate that the live session stays up or emits specific lifecycle blockers.
4. Stop and review the live artifact bundle before expanding fixture or classification work.

### Incremental Delivery

1. Ship US1 to stabilize the live validation session and lifecycle reporting.
2. Ship US2 to make fixture blockers explicit.
3. Ship US3 to separate transport-adjacent outcomes from true behavior failures.
4. Finish with Phase 6 validation and documentation cleanup.

### Parallel Team Strategy

1. One developer lands Phase 1 and Phase 2 shared plumbing.
2. After foundational completion:
   - Developer A: US1 lifecycle continuity and wrapper reporting.
   - Developer B: US2 fixture provisioning and blocker classification.
   - Developer C: US3 rerun comparison and transport-adjacent summaries.
3. Rejoin for Phase 6 validation in the prepared live environment.

---

## Notes

- All tasks use the required checklist format with task ID and exact file path.
- Story tasks include the required `[US1]`, `[US2]`, or `[US3]` labels.
- Setup, foundational, and polish tasks intentionally omit story labels.
- Suggested MVP scope is US1 (Phase 3).
