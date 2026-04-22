# Tasks: Fixture Bootstrap Simplification

**Input**: Design documents from `/specs/014-fixture-bootstrap-simplification/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Include pytest, synthetic headless validation, campaign validation, and prepared live rerun tasks because the spec defines independent test criteria for every user story.

**Organization**: Tasks are grouped by user story so each increment stays independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel when dependencies are already complete.
- **[Story]**: User story label for story-phase tasks only.
- Every task includes an exact file path.
- Any task touching `tests/headless/*` must keep edits surgical and preserve Constitution I upstream-fork discipline.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the existing Itertesting test and wrapper surfaces for 014-specific fixture, semantic-gate, and inventory coverage.

- [X] T001 Add shared 014 regression builders for fixture provisioning and semantic-gate scenarios in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py` and `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`
- [X] T002 [P] Add shared report and intelligence assertions for 014 in `clients/python/tests/behavioral_coverage/test_itertesting_report.py` and `clients/python/tests/behavioral_coverage/test_upstream_fixture_intelligence.py`
- [X] T003 [P] Add reusable headless artifact checks for 014 in `tests/headless/test_live_itertesting_hardening.sh`, `tests/headless/test_itertesting_campaign.sh`, and `tests/headless/itertesting.sh`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the shared fixture-model, semantic-gate, and serialization plumbing required by every story.

**⚠️ CRITICAL**: No story work should start until this phase is complete.

- [X] T004 Define richer fixture provisioning and semantic-gate records in `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`
- [X] T005 [P] Centralize authoritative fixture dependency, planned-command, and class-status helpers in `clients/python/highbar_client/behavioral_coverage/bootstrap.py`
- [X] T006 [P] Add exact custom-command inventory and upstream intelligence accessors in `clients/python/highbar_client/behavioral_coverage/upstream_fixture_intelligence.py` and `clients/python/highbar_client/behavioral_coverage/registry.py`
- [X] T007 [P] Carry semantic-gate metadata through verification helpers in `clients/python/highbar_client/behavioral_coverage/predicates.py`, `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`, and `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T008 Serialize `class_statuses`, `shared_fixture_instances`, semantic-gate details, and aggregate fixture summaries in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T009 Render baseline fixture-status and semantic-gate sections in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [X] T010 [P] Add foundational serialization and intelligence regressions in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`, `clients/python/tests/behavioral_coverage/test_itertesting_report.py`, `clients/python/tests/behavioral_coverage/test_upstream_fixture_intelligence.py`, and `clients/python/tests/test_behavioral_registry.py`

**Checkpoint**: The authoritative fixture model, semantic-gate plumbing, and report serialization are ready for story work.

---

## Phase 3: User Story 1 - Provision Shared Missing Fixtures (Priority: P1) 🎯 MVP

**Goal**: Provision reusable live fixtures for the currently missing classes so dependent commands can advance to live evaluation instead of stopping at a generic fixture blocker.

**Independent Test**: Run a prepared closeout pass and confirm that commands tied to `transport_unit`, `payload_unit`, `capturable_target`, `restore_target`, `wreck_target`, and `custom_target` are no longer automatically fixture-blocked when those classes are successfully prepared, while true helper-parity gaps stay distinct.

### Tests for User Story 1

- [X] T011 [P] [US1] Add provisioning-success and affected-command regressions for the six missing fixture classes in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`
- [X] T012 [P] [US1] Add fixture-versus-helper-parity classification regressions in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`
- [X] T013 [P] [US1] Add synthetic hardening assertions for provisioned, refreshed, and still-missing fixture classes in `tests/headless/test_live_itertesting_hardening.sh`

### Implementation for User Story 1

- [X] T014 [US1] Expand live bootstrap provisioning for `transport_unit`, `payload_unit`, `capturable_target`, `restore_target`, `wreck_target`, and `custom_target` in `clients/python/highbar_client/behavioral_coverage/bootstrap.py`
- [X] T015 [US1] Implement reusable shared fixture instance creation, readiness tracking, and per-class affected-command expansion in `clients/python/highbar_client/behavioral_coverage/bootstrap.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`
- [X] T016 [US1] Route live bootstrap precondition checks through authoritative fixture dependencies in `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [X] T017 [US1] Attempt fixture refresh or replacement before blocking dependent commands in `clients/python/highbar_client/behavioral_coverage/bootstrap.py` and `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [X] T018 [US1] Persist per-class provisioned, refreshed, missing, and unusable fixture state in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [X] T019 [US1] Route fixture-ready commands back into normal live evaluation paths in `clients/python/highbar_client/behavioral_coverage/__init__.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`

**Checkpoint**: User Story 1 unlocks live evaluation for commands whose newly supported fixture classes are actually available.

---

## Phase 4: User Story 2 - Simplify Bootstrap Interpretation (Priority: P2)

**Goal**: Replace the duplicate simplified-bootstrap blocker path with one authoritative fixture and semantic-gate interpretation model, including exact BAR custom command ids.

**Independent Test**: Review a generated run bundle and confirm that fixture availability, missing classes, semantic-gate causes, and exact custom-command ids all come from one consistent interpretation path with no generic simplified-bootstrap blocker explanation remaining.

### Tests for User Story 2

- [X] T020 [P] [US2] Add exact custom-command inventory regressions for ids `32102`, `34571`, `34922`, `34923`, `34924`, `34925`, and `37382` in `clients/python/tests/behavioral_coverage/test_upstream_fixture_intelligence.py` and `clients/python/tests/test_behavioral_registry.py`
- [X] T021 [P] [US2] Add report and classification regressions for helper-parity, Lua rewrite, unit-shape, and mod-option gates in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py` and `clients/python/tests/behavioral_coverage/test_itertesting_report.py`
- [X] T022 [P] [US2] Add headless artifact assertions for exact custom-command ids and semantic-gate reporting in `tests/headless/test_live_itertesting_hardening.sh` and `tests/headless/itertesting.sh`

### Implementation for User Story 2

- [X] T023 [US2] Remove `_SIMPLIFIED_BOOTSTRAP_TARGET_MISSING_ARMS` and route precondition checks through authoritative fixture dependencies in `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [X] T024 [US2] Expand `clients/python/highbar_client/behavioral_coverage/upstream_fixture_intelligence.py` with the required BAR custom command ids, gadget owners, unit-eligibility rules, and evidence-channel expectations
- [X] T025 [US2] Split generic `cmd-custom` handling into exact command-id inventory entries and fixture-selection rules in `clients/python/highbar_client/behavioral_coverage/registry.py` and `clients/python/highbar_client/behavioral_coverage/bootstrap.py`
- [X] T026 [US2] Classify helper-parity gaps, Lua rewrites, unit-shape gates, and mod-option gates separately from missing fixtures in `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py` and `clients/python/highbar_client/behavioral_coverage/predicates.py`
- [X] T027 [US2] Surface exact custom command ids, owning gadgets, semantic-gate causes, and authoritative affected-command summaries in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [X] T028 [US2] Update maintainer wrapper output to expose authoritative fixture and semantic-gate summaries in `tests/headless/itertesting.sh`

**Checkpoint**: User Story 2 makes the run bundle the single authoritative review surface for fixture and semantic-gate interpretation.

---

## Phase 5: User Story 3 - Preserve Trustworthy Closeout Results (Priority: P3)

**Goal**: Preserve healthy closeout behavior while repairing the identified local helper parity gaps and keeping remaining unavailable surfaces explicitly classified.

**Independent Test**: Run repeated prepared closeout passes and confirm that channel health remains healthy while repaired helper surfaces stop defaulting to local-stub failures, and unresolved fixture or semantic-gate problems remain explicitly classified.

### Tests for User Story 3

- [X] T029 [P] [US3] Add regressions for repaired helper-parity surfaces and stable channel-health outcomes in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`, `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`, and `clients/python/tests/behavioral_coverage/test_upstream_fixture_intelligence.py`
- [X] T030 [P] [US3] Add synthetic and campaign assertions for manual-launch substitution, wanted-speed gating, attack rewrite classification, and refresh failures in `tests/headless/test_live_itertesting_hardening.sh` and `tests/headless/test_itertesting_campaign.sh`

### Implementation for User Story 3

- [X] T031 [US3] Repair `CmdWantedSpeed`, `CmdPriority`, `CmdMiscPriority`, and `CmdAirStrafe` helper dispatch in `src/circuit/unit/CircuitUnit.cpp`
- [X] T032 [US3] Repair `CmdFireAtRadar` and `CmdManualFire` helper dispatch, plus any required constants or comments, in `src/circuit/unit/CircuitUnit.cpp` and `src/circuit/unit/CircuitUnit.h`
- [X] T033 [US3] Adjust gRPC dispatch and live verification expectations for wanted-speed gating, manual-launch substitution, and attack or set-target rewrites in `src/circuit/grpc/CommandDispatch.cpp`, `clients/python/highbar_client/behavioral_coverage/predicates.py`, and `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`
- [X] T034 [P] [US3] Add integration coverage for repaired wanted-speed, manual-fire, and attack/set-target dispatch in `tests/integration/transport_parity_test.cc` and `tests/integration/README.md`
- [X] T035 [US3] Keep `channel_health` and `contract_health_decision` stable while repaired helper surfaces execute through richer fixture provisioning in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T036 [US3] Update run-bundle and maintainer-facing messaging for repaired helper surfaces versus remaining fixture blockers in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py` and `tests/headless/itertesting.sh`

**Checkpoint**: User Story 3 preserves trustworthy closeout interpretation while restoring the in-scope local helper surfaces.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, documentation, and closeout checks across all stories.

- [X] T037 [P] Update maintainer workflow guidance for fixture classes, exact custom ids, and semantic-gate review in `tests/headless/README.md` and `specs/014-fixture-bootstrap-simplification/quickstart.md`
- [X] T038 Run targeted pytest coverage in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`, `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`, `clients/python/tests/behavioral_coverage/test_itertesting_report.py`, `clients/python/tests/behavioral_coverage/test_upstream_fixture_intelligence.py`, and `clients/python/tests/test_behavioral_registry.py`
- [X] T039 Run synthetic live-hardening validation in `tests/headless/test_live_itertesting_hardening.sh`
- [X] T040 Run campaign artifact validation in `tests/headless/test_itertesting_campaign.sh`
- [X] T041 Run three prepared live closeout reruns via `tests/headless/itertesting.sh`
- [ ] T042 Count missing-fixture-blocked commands from `reports/itertesting/<run-id>/manifest.json` and `reports/itertesting/<run-id>/run-report.md` to confirm the total decreases from 11 to no more than 5
- [ ] T043 Compare prepared closeout duration from `tests/headless/itertesting.sh` output and `reports/itertesting/<run-id>/` artifacts against the recorded pre-014 baseline to confirm runtime stays within +10%

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: No dependencies.
- **Phase 2**: Depends on Phase 1 and blocks all user stories.
- **Phase 3 (US1)**: Depends on Phase 2.
- **Phase 4 (US2)**: Depends on Phase 2 and is simplest to land after US1 starts emitting richer fixture state.
- **Phase 5 (US3)**: Depends on Phase 2 and benefits from US1 and US2 plumbing, but remains independently testable.
- **Phase 6**: Depends on the selected user stories being complete.

### User Story Dependencies

- **US1 (P1)**: No hard dependency on other stories once foundational work is done.
- **US2 (P2)**: Depends on the shared fixture and semantic-gate model from Phase 2; best validated after US1.
- **US3 (P3)**: Depends on the shared fixture and semantic-gate model from Phase 2; best validated after US1 and US2.

### Within Each User Story

- Write the story tests first and confirm they fail before implementation.
- Land data-model or serialization changes before report or wrapper output that consumes them.
- Update live bootstrap behavior before tightening closeout interpretation that depends on the new fixture state.
- Run the story’s independent validation before moving to the next priority.

### Parallel Opportunities

- `T002` and `T003` can run in parallel after `T001`.
- `T005`, `T006`, `T007`, and `T010` can run in parallel after `T004`.
- `T011`, `T012`, and `T013` can run in parallel.
- `T020`, `T021`, and `T022` can run in parallel.
- `T029` and `T030` can run in parallel.
- `T037` can run in parallel with final validation once implementation is complete.

---

## Parallel Example: User Story 1

```bash
Task: "Add provisioning-success and affected-command regressions for the six missing fixture classes in clients/python/tests/behavioral_coverage/test_itertesting_runner.py"
Task: "Add fixture-versus-helper-parity classification regressions in clients/python/tests/behavioral_coverage/test_live_failure_classification.py"
Task: "Add synthetic hardening assertions for provisioned, refreshed, and still-missing fixture classes in tests/headless/test_live_itertesting_hardening.sh"
```

---

## Parallel Example: User Story 2

```bash
Task: "Add exact custom-command inventory regressions for ids 32102, 34571, 34922, 34923, 34924, 34925, and 37382 in clients/python/tests/behavioral_coverage/test_upstream_fixture_intelligence.py and clients/python/tests/test_behavioral_registry.py"
Task: "Add report and classification regressions for helper-parity, Lua rewrite, unit-shape, and mod-option gates in clients/python/tests/behavioral_coverage/test_live_failure_classification.py and clients/python/tests/behavioral_coverage/test_itertesting_report.py"
Task: "Add headless artifact assertions for exact custom-command ids and semantic-gate reporting in tests/headless/test_live_itertesting_hardening.sh and tests/headless/itertesting.sh"
```

---

## Parallel Example: User Story 3

```bash
Task: "Add regressions for repaired helper-parity surfaces and stable channel-health outcomes in clients/python/tests/behavioral_coverage/test_live_failure_classification.py, clients/python/tests/behavioral_coverage/test_itertesting_runner.py, and clients/python/tests/behavioral_coverage/test_upstream_fixture_intelligence.py"
Task: "Add synthetic and campaign assertions for manual-launch substitution, wanted-speed gating, attack rewrite classification, and refresh failures in tests/headless/test_live_itertesting_hardening.sh and tests/headless/test_itertesting_campaign.sh"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1).
3. Validate that the six currently missing fixture classes now unlock direct live evaluation when setup succeeds.
4. Stop and review the run bundle before landing semantic-gate expansion or helper-parity repairs.

### Incremental Delivery

1. Ship US1 to provision the missing shared fixtures and unlock more live coverage.
2. Ship US2 to unify fixture interpretation, add exact custom-command ids, and remove duplicate blocker logic.
3. Ship US3 to repair the in-scope helper parity gaps while preserving trustworthy closeout results.
4. Finish with Phase 6 validation and maintainer workflow updates.

### Parallel Team Strategy

1. One developer lands Phase 1 and Phase 2 shared fixture and semantic-gate plumbing.
2. After foundational completion:
   - Developer A: US1 provisioning and bootstrap changes.
   - Developer B: US2 classification, inventory, and reporting changes.
   - Developer C: US3 helper-parity repairs and closeout-stability work.
3. Rejoin for Phase 6 validation in the prepared live environment.

---

## Notes

- Total tasks: 43
- Story task counts: US1 = 9, US2 = 9, US3 = 8
- Suggested MVP scope: Phase 3 / US1 only
- All tasks use the required checklist format with checkbox, task id, optional `[P]`, optional story label, and exact file paths
