# Tasks: BAR Live Run Viewer

**Input**: Design documents from `/specs/018-live-run-viewer/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Include pytest and headless validation tasks because the feature spec, contracts, and quickstart define explicit validation coverage for watch launch, attach-later selection, and watch-state reporting.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new watch-mode implementation seams and dedicated validation files referenced by the plan.

- [X] T001 Create the BNV watch orchestration module in `clients/python/highbar_client/behavioral_coverage/bnv_watch.py`
- [X] T002 Create the active watch registry module in `clients/python/highbar_client/behavioral_coverage/watch_registry.py`
- [X] T003 [P] Create watch profile and preflight test coverage scaffolding in `clients/python/tests/behavioral_coverage/test_bnv_watch.py`
- [X] T004 [P] Create attach-later registry test coverage scaffolding in `clients/python/tests/behavioral_coverage/test_watch_registry.py`
- [X] T005 [P] Create the dedicated live run viewer headless validation script in `tests/headless/test_live_run_viewer.sh`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the shared watch domain and runner plumbing that all user stories depend on.

**⚠️ CRITICAL**: No user story work should begin until this phase is complete.

- [X] T006 Extend the watch-related dataclasses and manifest serialization helpers in `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`
- [X] T007 Add watch CLI option parsing, reports-dir watch helpers, and common watch output plumbing in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`

**Checkpoint**: Shared watch entities and runner plumbing exist; user story implementation can proceed.

---

## Phase 3: User Story 1 - Watch a live run in BAR (Priority: P1) 🎯 MVP

**Goal**: Let a maintainer request watch mode for a compatible live Itertesting run and automatically launch BAR Native Game Viewer with the required spectator defaults.

**Independent Test**: Start a prepared live run with watch mode enabled and confirm the same run becomes viewable in BNV, while readiness failures abort before live execution and the normal bundle artifacts are still produced.

### Tests for User Story 1

- [X] T008 [P] [US1] Add watch profile parsing, environment resolution, and preflight failure tests in `clients/python/tests/behavioral_coverage/test_bnv_watch.py`
- [X] T009 [P] [US1] Add launch-time watch gating and run-failure policy coverage in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`
- [X] T010 [P] [US1] Add watch-status report rendering assertions in `clients/python/tests/behavioral_coverage/test_itertesting_report.py`

### Implementation for User Story 1

- [X] T011 [US1] Implement watch profile parsing, `HIGHBAR_BNV_BINARY` resolution, spectator defaults, and BNV launch command construction in `clients/python/highbar_client/behavioral_coverage/bnv_watch.py`
- [X] T012 [US1] Integrate launch-time watch preflight gating, BNV auto-launch, and bundle watch state updates in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T013 [US1] Render watch request, preflight result, and viewer access state in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [X] T014 [US1] Expose watch-mode environment passthrough for prepared live runs in `tests/headless/itertesting.sh`
- [X] T015 [US1] Implement watched-run happy-path and preflight-failure validation with a 30-second BNV availability assertion in `tests/headless/test_live_run_viewer.sh`

**Checkpoint**: User Story 1 should launch watched live runs with BNV defaults, fail early on readiness problems, and record the outcome in artifacts.

---

## Phase 4: User Story 2 - Open the correct active run after launch (Priority: P2)

**Goal**: Let maintainers attach BNV to an already active compatible run by explicit run reference, with auto-selection allowed only when exactly one compatible run exists.

**Independent Test**: Start multiple compatible live runs, attach by explicit run id and by single-active auto-selection, and confirm the viewer resolves the intended run without guessing.

### Tests for User Story 2

- [X] T016 [P] [US2] Add explicit-run, single-active, and ambiguous attach-later tests in `clients/python/tests/behavioral_coverage/test_watch_registry.py`
- [X] T017 [P] [US2] Add attach-later CLI coverage for explicit run ids and ambiguity failures in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`

### Implementation for User Story 2

- [X] T018 [US2] Implement active watch index persistence, attachability filtering, and selection summaries in `clients/python/highbar_client/behavioral_coverage/watch_registry.py`
- [X] T019 [US2] Add attach-later watch resolution, `--watch-run` handling, and single-active auto-selection logic in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T020 [US2] Extend attach-later headless validation for explicit selection and ambiguity rejection in `tests/headless/test_live_run_viewer.sh`

**Checkpoint**: User Story 2 should resolve the intended active run deterministically and reject ambiguous attach requests with explicit guidance.

---

## Phase 5: User Story 3 - Receive a clear reason when watching is unavailable (Priority: P3)

**Goal**: Make watch unavailability, expiry, and disconnect reasons explicit in stdout, bundle artifacts, and attach-later responses.

**Independent Test**: Request watch mode for incompatible, unavailable, expired, and disconnected cases and confirm each response reports a run-specific reason that remains visible in persisted artifacts.

### Tests for User Story 3

- [X] T021 [P] [US3] Add unavailable, expired, and disconnected watch-state coverage in `clients/python/tests/behavioral_coverage/test_bnv_watch.py`
- [X] T022 [P] [US3] Add expired and unavailable watch rendering assertions in `clients/python/tests/behavioral_coverage/test_itertesting_report.py`

### Implementation for User Story 3

- [X] T023 [US3] Implement watch unavailability, expiry, and disconnect lifecycle transitions in `clients/python/highbar_client/behavioral_coverage/bnv_watch.py`
- [X] T024 [US3] Surface run-specific watch failure reasons consistently in stdout and bundle persistence in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T025 [US3] Expire completed sessions and preserve artifact pointers for diagnosis in `clients/python/highbar_client/behavioral_coverage/watch_registry.py`
- [X] T026 [US3] Extend headless validation for unavailable and expired watch requests, including a 10-second user-readable failure assertion, in `tests/headless/test_live_run_viewer.sh`

**Checkpoint**: User Story 3 should leave maintainers with a clear reason and artifact trail for every unavailable watch attempt.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Finalize maintainer-facing documentation and run the full validation matrix.

- [X] T027 [P] Update the maintainer watch workflow and command examples in `specs/018-live-run-viewer/quickstart.md`
- [X] T028 [P] Add non-watch workflow regression coverage in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`
- [X] T029 [P] Add BAR viewer prerequisite and watch profile guidance to `docs/local-env.md`
- [ ] T030 Run the live run viewer validation matrix from `specs/018-live-run-viewer/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1) has no dependencies and can start immediately.
- Foundational (Phase 2) depends on Setup and blocks all user story work until the shared types and runner seams exist.
- User Story phases depend on Foundational completion, then proceed in priority order for incremental delivery.
- Polish (Phase 6) depends on the user stories that are in scope being complete.

### User Story Dependencies

- User Story 1 (P1) starts after Phase 2 and delivers the MVP watch-at-launch workflow.
- User Story 2 (P2) depends on Phase 2 and reuses the watch artifacts created by User Story 1, but remains independently testable through attach-later flows.
- User Story 3 (P3) depends on Phase 2 and hardens the same watch seams with explicit lifecycle reasons, while remaining independently testable through failure and expiry cases.

### Within Each User Story

- Write the story tests first and confirm they fail before implementing the story.
- Implement the shared domain or registry logic before runner integration.
- Update headless validation after the Python behavior is in place.
- Do not move to the next story until the current story passes its independent test.

### Parallel Opportunities

- T003, T004, and T005 can run in parallel during Setup because they create separate test files.
- T008, T009, and T010 can run in parallel for User Story 1 because they target separate test files.
- T016 and T017 can run in parallel for User Story 2 because registry and runner attach-later coverage live in different files.
- T021 and T022 can run in parallel for User Story 3 because lifecycle assertions are split between unit and report tests.
- T027, T028, and T029 can run in parallel during Polish because they touch separate documentation and regression-test files.

---

## Parallel Example: User Story 1

```bash
Task: "T008 [US1] Add watch profile parsing, environment resolution, and preflight failure tests in clients/python/tests/behavioral_coverage/test_bnv_watch.py"
Task: "T009 [US1] Add launch-time watch gating and run-failure policy coverage in clients/python/tests/behavioral_coverage/test_itertesting_runner.py"
Task: "T010 [US1] Add watch-status report rendering assertions in clients/python/tests/behavioral_coverage/test_itertesting_report.py"
```

## Parallel Example: User Story 2

```bash
Task: "T016 [US2] Add explicit-run, single-active, and ambiguous attach-later tests in clients/python/tests/behavioral_coverage/test_watch_registry.py"
Task: "T017 [US2] Add attach-later CLI coverage for explicit run ids and ambiguity failures in clients/python/tests/behavioral_coverage/test_itertesting_runner.py"
```

## Parallel Example: User Story 3

```bash
Task: "T021 [US3] Add unavailable, expired, and disconnected watch-state coverage in clients/python/tests/behavioral_coverage/test_bnv_watch.py"
Task: "T022 [US3] Add expired and unavailable watch rendering assertions in clients/python/tests/behavioral_coverage/test_itertesting_report.py"
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 for User Story 1.
3. Run the User Story 1 independent test and the relevant quickstart validation.
4. Stop after User Story 1 if the goal is the minimum shippable watch-at-launch workflow.

### Incremental Delivery

1. Deliver User Story 1 to establish launch-time BNV watching.
2. Add User Story 2 to support deterministic attach-later selection.
3. Add User Story 3 to harden user-readable failure, expiry, and disconnect reporting.
4. Finish with Phase 6 documentation and validation updates.

### Parallel Team Strategy

1. One developer can own the shared types and runner plumbing in Phase 2.
2. After Phase 2, test work inside each story can proceed in parallel on separate files.
3. Documentation polish can run in parallel with final validation once implementation is stable.

---

## Notes

- All checklist items follow the required `- [ ] T### [P] [US#] Description with file path` format.
- `[P]` markers appear only on tasks that touch separate files with no incomplete dependency on each other.
- User story labels are present only on story-phase tasks.
- The MVP scope is Phase 3, User Story 1.
