# Tasks: Live Orchestration Refactor

**Input**: Design documents from `/specs/017-live-orchestration-refactor/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Include targeted pytest and headless validation tasks because the specification requires independently validating metadata collection, interpretation, and report rendering behavior.

**Organization**: Tasks are grouped by user story so each slice can be implemented and validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story label (`[US1]`, `[US2]`, `[US3]`)
- Every task includes the concrete repository path to change or validate

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new module and test surfaces the refactor will use.

- [X] T001 Create seam module scaffolds in `clients/python/highbar_client/behavioral_coverage/live_execution.py`, `clients/python/highbar_client/behavioral_coverage/metadata_records.py`, and `clients/python/highbar_client/behavioral_coverage/run_interpretation.py`
- [X] T002 [P] Create targeted test module scaffolds in `clients/python/tests/behavioral_coverage/test_live_execution.py` and `clients/python/tests/behavioral_coverage/test_metadata_records.py`
- [X] T003 [P] Add initial import/export wiring for the new seams in `clients/python/highbar_client/behavioral_coverage/__init__.py` and `clients/python/highbar_client/behavioral_coverage/__main__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish shared types, serialization, and policy primitives that every story depends on.

**⚠️ CRITICAL**: Complete this phase before beginning user-story implementation.

- [X] T004 Extend structured run dataclasses in `clients/python/highbar_client/behavioral_coverage/itertesting_types.py` with `LiveExecutionCapture`, `MetadataRecordEnvelope`, `MetadataInterpretationRule`, `RunModeEvidencePolicy`, `FixtureStateTransition`, `TransportAvailabilityDecision`, `InterpretationWarning`, and `RunInterpretationResult`
- [X] T005 [P] Implement metadata record parsing and round-trip helpers in `clients/python/highbar_client/behavioral_coverage/metadata_records.py`
- [X] T006 [P] Implement shared run-mode evidence policy defaults and transition helpers in `clients/python/highbar_client/behavioral_coverage/run_interpretation.py`
- [X] T007 Wire manifest serialization and deserialization for the new structured interpretation fields in `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`
- [X] T008 Add foundational regression coverage for metadata round-trips and policy defaults in `clients/python/tests/behavioral_coverage/test_metadata_records.py` and `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`

**Checkpoint**: Structured metadata and interpretation primitives are in place, and user-story work can proceed on top of them.

---

## Phase 3: User Story 1 - Trustworthy Live Failure Reporting (Priority: P1) 🎯 MVP

**Goal**: Make live bundles report only evidence that was actually established, with authoritative fixture and transport decisions for blocked or partial runs.

**Independent Test**: Trigger bootstrap-blocked and evidence-poor live scenarios and confirm the resulting bundle preserves metadata while reporting only explicitly supported fixture and transport availability.

### Tests for User Story 1

- [X] T009 [P] [US1] Add bootstrap-blocked and evidence-poor capture tests in `clients/python/tests/behavioral_coverage/test_live_execution.py`
- [X] T010 [P] [US1] Add latest-state-wins fixture and unknown-or-unproven transport regression tests in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`
- [X] T011 [P] [US1] Add blocker-classification regressions for authoritative fixture and transport decisions in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`

### Implementation for User Story 1

- [X] T012 [US1] Extract live bootstrap capture and metadata collection from `clients/python/highbar_client/behavioral_coverage/__init__.py` into `clients/python/highbar_client/behavioral_coverage/live_execution.py`
- [X] T013 [US1] Replace raw `__...__` metadata marker coupling with typed metadata envelopes in `clients/python/highbar_client/behavioral_coverage/__init__.py` and `clients/python/highbar_client/behavioral_coverage/metadata_records.py`
- [X] T014 [US1] Implement authoritative fixture and transport interpretation from transitions and run-mode policy in `clients/python/highbar_client/behavioral_coverage/run_interpretation.py`
- [X] T015 [US1] Update `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py` to consume `RunInterpretationResult` instead of rescanning metadata marker rows
- [X] T016 [US1] Update failure-cause synthesis to use authoritative fixture and transport decisions in `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`
- [X] T017 [US1] Extend bootstrap-blocked hardening assertions in `tests/headless/test_live_itertesting_hardening.sh`

**Checkpoint**: User Story 1 is complete when blocked or partial live runs produce internally consistent bootstrap, fixture, transport, and blocker outputs.

---

## Phase 4: User Story 2 - Isolated Maintainer Changes (Priority: P2)

**Goal**: Split execution, metadata, and interpretation responsibilities so maintainers can change one area without reopening unrelated orchestration logic.

**Independent Test**: Change a metadata-collection or interpretation rule and run only the dedicated seam tests to verify the change without touching unrelated report or campaign behavior.

### Tests for User Story 2

- [X] T018 [P] [US2] Add ownership-boundary tests for metadata collection responsibilities in `clients/python/tests/behavioral_coverage/test_metadata_records.py` and `clients/python/tests/behavioral_coverage/test_live_execution.py`
- [X] T019 [P] [US2] Add targeted interpretation-versus-rendering isolation regressions in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py` and `clients/python/tests/behavioral_coverage/test_itertesting_report.py`

### Implementation for User Story 2

- [X] T020 [US2] Move authoritative metadata record definitions and record-to-rule maps into `clients/python/highbar_client/behavioral_coverage/metadata_records.py`
- [X] T021 [US2] Split interpretation-only synthesis from campaign persistence logic between `clients/python/highbar_client/behavioral_coverage/run_interpretation.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T022 [US2] Reduce `clients/python/highbar_client/behavioral_coverage/__init__.py` to CLI and high-level orchestration flow while preserving the existing entry points in `clients/python/highbar_client/behavioral_coverage/__main__.py`
- [X] T023 [US2] Route prerequisite-resolution and map-source evidence through explicit seam helpers in `clients/python/highbar_client/behavioral_coverage/bootstrap.py` and `clients/python/highbar_client/behavioral_coverage/run_interpretation.py`

**Checkpoint**: User Story 2 is complete when execution, collection, interpretation, and rendering responsibilities can be changed and tested independently.

---

## Phase 5: User Story 3 - Faster Root-Cause Investigation (Priority: P3)

**Goal**: Preserve warnings and decision trace data so maintainers can identify which layer produced a final bundle decision without reverse-engineering oversized files.

**Independent Test**: Inspect a representative failure bundle and its targeted tests to confirm the execution layer, metadata layer, and interpretation layer are all traceable separately.

### Tests for User Story 3

- [X] T024 [P] [US3] Add manifest and report regressions for interpretation warnings, `fully_interpreted`, and decision trace output in `clients/python/tests/behavioral_coverage/test_itertesting_report.py` and `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`
- [X] T025 [P] [US3] Add regression coverage for unhandled metadata blocking successful or improved run classification in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`
- [X] T026 [P] [US3] Add campaign artifact regression coverage for preserved warnings and traceability in `tests/headless/test_itertesting_campaign.sh`

### Implementation for User Story 3

- [X] T027 [US3] Serialize interpretation warnings, decision traces, `fully_interpreted`, and success-blocking interpretation state in `clients/python/highbar_client/behavioral_coverage/itertesting_types.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T028 [US3] Render maintainer-visible warning and layer-trace sections in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [X] T029 [US3] Surface layer ownership and traceability through prepared live bundle closeout in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py` and `tests/headless/itertesting.sh`
- [X] T030 [US3] Update bundle-inspection guidance with the traceability review workflow and inspection gate in `specs/017-live-orchestration-refactor/quickstart.md`

**Checkpoint**: User Story 3 is complete when representative bundles expose preserved warnings and enough traceability to identify the responsible layer quickly.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final verification, validation-loop cleanup, and closeout checks that span multiple stories.

- [X] T031 [P] Refresh validation references and acceptance wording in `specs/017-live-orchestration-refactor/contracts/live-orchestration-validation-suite.md` and `specs/017-live-orchestration-refactor/quickstart.md`
- [X] T032 [P] Update `AGENTS.md` to point at `specs/017-live-orchestration-refactor/plan.md` in `AGENTS.md`
- [X] T033 Run the targeted validation commands documented in `specs/017-live-orchestration-refactor/quickstart.md`
- [X] T034 [P] Inspect the latest bundle artifacts under `reports/itertesting/<run-id>/manifest.json`, `reports/itertesting/<run-id>/run-report.md`, and `reports/itertesting/<run-id>/campaign-stop-decision.json`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1: Setup**: No dependencies; start immediately.
- **Phase 2: Foundational**: Depends on Phase 1; blocks all user stories.
- **Phase 3: US1**: Depends on Phase 2; delivers the MVP bundle-authority slice.
- **Phase 4: US2**: Depends on Phase 2; safest after US1 because it restructures the same orchestration surfaces.
- **Phase 5: US3**: Depends on the interpreted bundle output from US1 and the seam split from US2.
- **Phase 6: Polish**: Depends on all implemented stories.

### User Story Dependencies

- **US1**: No story dependency beyond the shared foundations.
- **US2**: Depends on the structured metadata and interpretation primitives from Phase 2; coordinate carefully with US1 because both touch `__init__.py` and `itertesting_runner.py`.
- **US3**: Depends on authoritative interpreted bundle state from US1 and the explicit seam ownership from US2.

### Within Each User Story

- Write the listed regression tests before the corresponding implementation changes.
- Finish live execution and metadata capture changes before switching runner consumers to the new seams.
- Keep serialization updates aligned with report-rendering changes so bundles stay readable at each checkpoint.

### Parallel Opportunities

- `T002` and `T003` can run in parallel after `T001`.
- `T005` and `T006` can run in parallel after `T004`.
- `T009`, `T010`, and `T011` can run in parallel within US1.
- `T018` and `T019` can run in parallel within US2.
- `T024`, `T025`, and `T026` can run in parallel within US3.
- `T031` and `T034` can run in parallel once implementation is complete.

---

## Parallel Example: User Story 1

```bash
Task T009  Add bootstrap-blocked and evidence-poor capture tests in clients/python/tests/behavioral_coverage/test_live_execution.py
Task T010  Add latest-state-wins fixture and unknown-or-unproven transport regression tests in clients/python/tests/behavioral_coverage/test_itertesting_runner.py
Task T011  Add blocker-classification regressions in clients/python/tests/behavioral_coverage/test_live_failure_classification.py
```

## Parallel Example: User Story 2

```bash
Task T018  Add ownership-boundary tests in clients/python/tests/behavioral_coverage/test_metadata_records.py and clients/python/tests/behavioral_coverage/test_live_execution.py
Task T019  Add interpretation-versus-rendering isolation regressions in clients/python/tests/behavioral_coverage/test_itertesting_runner.py and clients/python/tests/behavioral_coverage/test_itertesting_report.py
```

## Parallel Example: User Story 3

```bash
Task T024  Add manifest/report traceability regressions in clients/python/tests/behavioral_coverage/test_itertesting_report.py and clients/python/tests/behavioral_coverage/test_itertesting_runner.py
Task T025  Add regression coverage for unhandled metadata blocking successful or improved run classification in clients/python/tests/behavioral_coverage/test_itertesting_runner.py
Task T026  Add campaign artifact traceability coverage in tests/headless/test_itertesting_campaign.sh
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational primitives.
3. Complete Phase 3: User Story 1.
4. Run the US1 pytest and hardening validations before expanding the refactor.

### Incremental Delivery

1. Land Setup + Foundational to establish the typed seams and serialization model.
2. Land US1 to make blocked and partial live bundles trustworthy.
3. Land US2 to isolate maintainer ownership boundaries without changing external commands.
4. Land US3 to expose warnings and layer traceability in bundles and reports.
5. Run Phase 6 validation and inspect fresh artifacts before closing the feature.

### Parallel Team Strategy

1. One developer handles shared foundations in `itertesting_types.py`, `metadata_records.py`, and `run_interpretation.py`.
2. After Phase 2, a second developer can prepare story-specific tests while the first lands execution and runner changes.
3. Delay concurrent edits to `clients/python/highbar_client/behavioral_coverage/__init__.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py` unless ownership is explicitly coordinated.

---

## Notes

- `[P]` tasks touch separate files or can be validated independently.
- Every user-story phase is scoped so it can be tested on its own.
- Keep maintainer-facing commands and bundle filenames stable throughout implementation.
- Do not treat missing evidence as proof of fixture or transport availability.
