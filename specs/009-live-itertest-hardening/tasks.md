# Tasks: Live Itertesting Hardening

**Input**: Design documents from `/specs/009-live-itertest-hardening/`  
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Include pytest and live/headless validation tasks because the feature spec defines independent test criteria for each user story.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this belongs to (`[US1]`, `[US2]`, `[US3]`)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the live-hardening scaffolding in the existing Itertesting workflow

- [X] T001 Add live-hardening module scaffolding in `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`
- [X] T002 [P] Add live-hardening pytest scaffolding in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`, `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`, and `clients/python/tests/behavioral_coverage/test_itertesting_report.py`
- [X] T003 [P] Add headless validation scaffolding in `tests/headless/test_live_itertesting_hardening.sh`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core live-hardening infrastructure that MUST exist before any user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Define `LiveFixtureProfile`, `FixtureProvisioningResult`, `ChannelHealthOutcome`, `ArmVerificationRule`, and `FailureCauseClassification` fields in `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`
- [X] T005 [P] Implement shared failure-cause and verification-rule helpers in `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`
- [X] T006 [P] Add baseline channel-health and failure-cause report rendering in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [X] T007 [P] Add foundational classification/report tests in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py` and `clients/python/tests/behavioral_coverage/test_itertesting_report.py`
- [X] T008 Persist channel-health and fixture-provisioning records in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`

**Checkpoint**: Foundation ready - live fixture, channel-health, and failure-cause concepts are available to all user stories

---

## Phase 3: User Story 1 - Provision Valid Live Fixtures (Priority: P1) 🎯 MVP

**Goal**: Start default live Itertesting runs from a richer fixture-ready state so more directly verifiable commands reach meaningful attempt outcomes.

**Independent Test**: Run the default live Itertesting workflow with `HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0` and confirm more directly verifiable commands move out of pure precondition-blocked status, while any remaining prerequisite gaps are reported as explicit missing-fixture outcomes.

### Tests for User Story 1

- [X] T009 [P] [US1] Add fixture-profile and missing-fixture classification tests in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`
- [X] T010 [P] [US1] Add live fixture validation coverage in `tests/headless/test_live_itertesting_hardening.sh`

### Implementation for User Story 1

- [X] T011 [US1] Extend the default live fixture profile and prerequisite vocabulary in `clients/python/highbar_client/behavioral_coverage/bootstrap.py`
- [X] T012 [US1] Expand live bootstrap execution and missing-fixture classification in `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [X] T013 [US1] Update command input builders and prerequisite mappings in `clients/python/highbar_client/behavioral_coverage/registry.py`
- [X] T014 [US1] Harden the default live launch setup in `tests/headless/scripts/minimal.startscript` and `tests/headless/aicommand-behavioral-coverage.sh`
- [X] T015 [US1] Surface fixture provisioning results in Itertesting manifests and reports in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`

**Checkpoint**: User Story 1 should let the default live workflow attempt materially more directly verifiable commands from valid prerequisite state

---

## Phase 4: User Story 2 - Keep The Command Channel Alive (Priority: P2)

**Goal**: Keep the plugin command channel healthy through a bounded live run and classify transport degradation explicitly when it occurs.

**Independent Test**: Run the default live Itertesting workflow end to end and confirm it either completes without manual restart or exits with an explicit transport interruption outcome instead of silently turning later commands into generic failures.

### Tests for User Story 2

- [X] T016 [P] [US2] Add channel-health and transport-interruption tests in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py` and `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`
- [X] T017 [P] [US2] Add degraded-session wrapper validation in `tests/headless/test_live_itertesting_hardening.sh`

### Implementation for User Story 2

- [X] T018 [US2] Normalize plugin command channel failure detection in `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [X] T019 [US2] Implement run-level channel-health tracking and interruption outcomes in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T020 [US2] Update degraded-session retry and stop semantics in `tests/headless/itertesting.sh`
- [X] T021 [US2] Render channel-health outcomes and transport-specific failure causes in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`

**Checkpoint**: User Story 2 should make transport degradation explicit and keep healthy sessions from collapsing into false per-command failures

---

## Phase 5: User Story 3 - Tighten Arm-Specific Live Verification (Priority: P3)

**Goal**: Judge `fight`, `move_unit`, and `build_unit` with live evidence windows and predicates that match their real observable behavior.

**Independent Test**: Run live/headless verification for `cmd-move-unit`, `cmd-fight`, and `cmd-build-unit` and confirm the workflow classifies their outcomes from tuned evidence rules rather than avoidable generic timeout failures.

### Tests for User Story 3

- [X] T022 [P] [US3] Add tuned verification-rule tests for `cmd-move-unit`, `cmd-fight`, and `cmd-build-unit` in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`
- [X] T023 [P] [US3] Add targeted live evidence regression coverage in `tests/headless/test_live_itertesting_hardening.sh` and `tests/headless/audit/repro.sh`

### Implementation for User Story 3

- [X] T024 [US3] Encode arm verification rule definitions and fallback cause mapping in `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py` and `clients/python/highbar_client/behavioral_coverage/hypotheses.py`
- [X] T025 [US3] Tune movement, combat, and construction predicate behavior in `clients/python/highbar_client/behavioral_coverage/predicates.py`
- [X] T026 [US3] Apply arm-specific live verification windows and rule selection in `clients/python/highbar_client/behavioral_coverage/registry.py` and `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [X] T027 [US3] Align audit/live outcome reporting for tuned arms in `clients/python/highbar_client/behavioral_coverage/audit_runner.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`

**Checkpoint**: User Story 3 should make the high-value live arms classify from their true observable effects rather than generic timeout defaults

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, documentation alignment, and regression coverage across all stories

- [X] T028 [P] Update maintainer workflow documentation in `tests/headless/README.md` and `specs/009-live-itertest-hardening/quickstart.md`
- [X] T029 [P] Run the behavioral-coverage pytest suite updates in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`, `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`, and `clients/python/tests/behavioral_coverage/test_itertesting_report.py`
- [X] T030 Run the end-to-end live hardening validation script in `tests/headless/test_live_itertesting_hardening.sh`
- [X] T031 Run targeted live repro validation for tuned arms with `tests/headless/audit/repro.sh` and capture outcomes in `reports/itertesting/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies, can begin immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1 and blocks all user stories.
- **Phase 3 (US1)**: Depends on Phase 2.
- **Phase 4 (US2)**: Depends on Phase 2 and benefits from US1 fixture improvements, but can begin once foundational channel-health plumbing exists.
- **Phase 5 (US3)**: Depends on Phase 2 and should follow US1/US2 so tuned predicates can build on richer fixtures and stable channel outcomes.
- **Phase 6 (Polish)**: Depends on completion of the selected user stories.

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on other user stories once foundational types and reporting hooks exist.
- **User Story 2 (P2)**: No hard dependency on US3; transport outcome tracking is independently valuable after the foundational phase.
- **User Story 3 (P3)**: Benefits from US1 and US2 because reliable fixtures and channel-health classification reduce false negatives before predicate tuning is evaluated.

### Within Each User Story

- Write tests first and confirm they fail before implementation.
- Update shared models/classification helpers before orchestration that consumes them.
- Change reports only after the runner emits the new fields.
- Run story-specific headless validation before moving to the next priority.

### Parallel Opportunities

- `T002` and `T003` can run in parallel after `T001`.
- `T005`, `T006`, and `T007` can run in parallel after `T004`.
- `T009` and `T010` can run in parallel for US1.
- `T016` and `T017` can run in parallel for US2.
- `T022` and `T023` can run in parallel for US3.
- `T028` and `T029` can run in parallel during polish.

---

## Parallel Example: User Story 1

```bash
Task: "Add fixture-profile and missing-fixture classification tests in clients/python/tests/behavioral_coverage/test_itertesting_runner.py"
Task: "Add live fixture validation coverage in tests/headless/test_live_itertesting_hardening.sh"
```

---

## Parallel Example: User Story 2

```bash
Task: "Add channel-health and transport-interruption tests in clients/python/tests/behavioral_coverage/test_itertesting_runner.py and clients/python/tests/behavioral_coverage/test_live_failure_classification.py"
Task: "Add degraded-session wrapper validation in tests/headless/test_live_itertesting_hardening.sh"
```

---

## Parallel Example: User Story 3

```bash
Task: "Add tuned verification-rule tests for cmd-move-unit, cmd-fight, and cmd-build-unit in clients/python/tests/behavioral_coverage/test_itertesting_runner.py"
Task: "Add targeted live evidence regression coverage in tests/headless/test_live_itertesting_hardening.sh and tests/headless/audit/repro.sh"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Implement Phase 3 (US1) only.
3. Validate the richer live fixture profile with `HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0`.
4. Stop and confirm more direct commands reach meaningful attempt state before expanding scope.

### Incremental Delivery

1. Ship US1 to increase the number of directly verifiable commands that can be attempted from valid prerequisite state.
2. Ship US2 to make command-channel degradation explicit and keep live sessions from producing false failure noise.
3. Ship US3 to improve outcome quality for `fight`, `move_unit`, and `build_unit`.
4. Finish with Phase 6 validation and documentation updates.

### Parallel Team Strategy

1. One developer completes Phase 1 and Phase 2.
2. After the foundation is ready:
   - Developer A: US1 fixture provisioning and report surfacing.
   - Developer B: US2 channel health and wrapper recovery behavior.
   - Developer C: US3 tuned verification rules and audit alignment.
3. Rejoin for polish, regression runs, and live repro validation.

---

## Notes

- All tasks follow the required checklist format with task ID, optional `[P]`, optional story label, and explicit file paths.
- Story phases map directly to the three user stories in `spec.md`.
- The suggested MVP scope is **User Story 1** because fixture readiness unlocks value for the rest of the live hardening work.
