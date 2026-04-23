# Tasks: Live Bootstrap Hardening

**Input**: Design documents from `/specs/016-live-bootstrap-hardening/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Include pytest, synthetic headless validation, standalone probe validation, campaign validation, and prepared live rerun tasks because the specification defines independent test criteria for every user story and `quickstart.md` makes those validation loops mandatory.

**Organization**: Tasks are grouped by user story so each increment stays independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel when dependencies are already complete.
- **[Story]**: User story label for story-phase tasks only.
- Every task includes an exact file path.
- Any task touching `tests/headless/*` must keep edits surgical and preserve the existing maintainer workflow boundaries.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the existing regression and maintainer validation surfaces for 016-specific bootstrap, diagnostic-retention, and runtime-resolution work.

- [X] T001 Add shared bootstrap-readiness regression fixtures in `clients/python/tests/test_behavioral_registry.py` and `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`
- [X] T002 [P] Add shared report and classification assertions for readiness, callback retention, and runtime resolution in `clients/python/tests/behavioral_coverage/test_itertesting_report.py` and `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`
- [X] T003 [P] Add reusable hardening validation scaffolding in `tests/headless/test_live_itertesting_hardening.sh`, `tests/headless/test_itertesting_campaign.sh`, and `tests/headless/behavioral-build.sh`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the shared data model, bundle serialization, and helper plumbing that every story depends on.

**⚠️ CRITICAL**: No user story work should start until this phase is complete.

- [X] T004 Define `BootstrapReadinessAssessment`, `CallbackDiagnosticSnapshot`, `RuntimePrerequisiteResolutionRecord`, and `StandaloneBuildProbeOutcome` in `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`
- [X] T005 [P] Add shared bootstrap-readiness enums, first-step metadata, and seeded-readiness helper plumbing in `clients/python/highbar_client/behavioral_coverage/bootstrap.py` and `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [X] T006 [P] Add shared callback-diagnostic capture and preservation hooks in `clients/python/highbar_client/behavioral_coverage/__init__.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T007 [P] Add shared runtime prerequisite-resolution trace helpers around `_resolve_live_def_ids()` in `clients/python/highbar_client/behavioral_coverage/__init__.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T008 [P] Add foundational readiness, diagnostic-retention, and runtime-resolution rendering/classification hooks in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py` and `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`
- [X] T009 [P] Add foundational serialization and rendering regressions in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`, `clients/python/tests/behavioral_coverage/test_itertesting_report.py`, and `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`

**Checkpoint**: The shared run-bundle model, callback helper plumbing, and status rendering are ready for story work.

---

## Phase 3: User Story 1 - Start Bootstrap From a Viable Live State (Priority: P1) 🎯 MVP

**Goal**: Ensure prepared live closeout either starts commander bootstrap from a viable state or fails immediately with an explicit bootstrap-readiness outcome.

**Independent Test**: Run prepared live closeout from the standard prepared scenario and confirm that the first commander build either proceeds normally or the run stops with an explicit bootstrap-readiness blocker before a downstream build timeout becomes the primary signal.

### Tests for User Story 1

- [X] T010 [P] [US1] Add bootstrap-start viability and starved-start blocker regressions in `clients/python/tests/test_behavioral_registry.py` and `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`
- [X] T011 [P] [US1] Add report and classifier assertions for `natural_ready`, `seeded_ready`, and `resource_starved` outcomes in `clients/python/tests/behavioral_coverage/test_itertesting_report.py` and `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`
- [X] T012 [P] [US1] Add synthetic hardening assertions for explicit readiness blockers and seeded-readiness bundle evidence in `tests/headless/test_live_itertesting_hardening.sh`

### Implementation for User Story 1

- [X] T013 [US1] Implement first-step bootstrap readiness assessment and starved-start short-circuiting in `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [X] T014 [US1] Implement the maintainer-visible seeded-readiness path and provenance capture in `clients/python/highbar_client/behavioral_coverage/bootstrap.py` and `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [X] T015 [US1] Carry bootstrap-readiness outcomes into the Itertesting bundle in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`
- [X] T016 [US1] Render bootstrap-readiness sections and explicit blocker language in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [X] T017 [US1] Keep resource-starved readiness failures distinct from later command-behavior failures in `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`
- [X] T018 [US1] Update prepared live closeout summary output for readiness outcomes in `tests/headless/itertesting.sh`

**Checkpoint**: User Story 1 is complete when prepared live closeout no longer treats a resource-starved opening state as a natural bootstrap path.

---

## Phase 4: User Story 2 - Preserve Failure Diagnostics Through Long Bootstrap Failures (Priority: P2)

**Goal**: Preserve callback-derived diagnostic evidence across long bootstrap failures so the final run bundle still supports maintainer review.

**Independent Test**: Force a prepared live bootstrap failure that persists beyond the first step and confirm that the final run bundle still includes callback-derived diagnostic evidence, clearly marked as live, cached, or genuinely unavailable.

### Tests for User Story 2

- [X] T019 [P] [US2] Add cached-vs-live callback retention regressions in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py` and `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`
- [X] T020 [P] [US2] Add report-rendering regressions for preserved and missing callback diagnostics in `clients/python/tests/behavioral_coverage/test_itertesting_report.py`
- [X] T021 [P] [US2] Add synthetic long-failure assertions for retained callback evidence in `tests/headless/test_live_itertesting_hardening.sh` and `tests/headless/test_itertesting_campaign.sh`

### Implementation for User Story 2

- [X] T022 [US2] Capture early commander/bootstrap diagnostic snapshots and preserve them through long failure paths in `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [X] T023 [US2] Distinguish `live`, `cached`, and `missing` callback availability when late refresh fails in `clients/python/highbar_client/behavioral_coverage/__init__.py` and `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`
- [X] T024 [US2] Serialize preserved callback-diagnostic snapshots into the Itertesting bundle in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`
- [X] T025 [US2] Render callback-diagnostic retention state in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [X] T026 [US2] Expose retained callback evidence and relay-loss distinctions in prepared-run terminal output in `tests/headless/itertesting.sh`

**Checkpoint**: User Story 2 is complete when long bootstrap failures still leave trustworthy callback-derived evidence in the bundle and summary output.

---

## Phase 5: User Story 3 - Keep Standalone Build Verification Aligned With Live Runtime Resolution (Priority: P3)

**Goal**: Make the standalone build probe resolve prerequisites through the same runtime callback path used by prepared live closeout.

**Independent Test**: Run `tests/headless/behavioral-build.sh` in a prepared live environment without manual def-id injection and confirm that it resolves the build prerequisite via the runtime callback path or exits with an explicit runtime-resolution blocker that matches the main workflow’s recorded resolution state.

### Tests for User Story 3

- [X] T027 [P] [US3] Add runtime prerequisite-resolution regressions shared by live closeout and the standalone probe in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py` and `clients/python/tests/test_behavioral_registry.py`
- [X] T028 [P] [US3] Add report and classifier assertions for `resolved`, `missing`, and `relay_unavailable` prerequisite outcomes in `clients/python/tests/behavioral_coverage/test_itertesting_report.py` and `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`
- [X] T029 [P] [US3] Add headless probe validation assertions for callback-based prerequisite resolution in `tests/headless/test_live_itertesting_hardening.sh` and `tests/headless/test_itertesting_campaign.sh`

### Implementation for User Story 3

- [X] T030 [US3] Promote `_resolve_live_def_ids()` into the authoritative shared prerequisite-resolution path for live closeout in `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [X] T031 [US3] Record runtime prerequisite-resolution trace and consumer provenance in `clients/python/highbar_client/behavioral_coverage/itertesting_types.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T032 [US3] Serialize and emit `StandaloneBuildProbeOutcome` for runtime prerequisite resolution and dispatch status in `clients/python/highbar_client/behavioral_coverage/itertesting_types.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T033 [US3] Replace the `HIGHBAR_ARMMEX_DEF_ID` normal path with callback-based prerequisite resolution and explicit blockers in `tests/headless/behavioral-build.sh`
- [X] T034 [US3] Align standalone-probe failure messaging and bundle/report output with runtime-resolution states in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py` and `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`
- [X] T035 [US3] Update maintainer guidance for standalone probe/runtime-resolution agreement in `tests/headless/README.md` and `specs/016-live-bootstrap-hardening/quickstart.md`

**Checkpoint**: User Story 3 is complete when the standalone probe and main workflow agree on runtime prerequisite identity and no longer depend on the legacy env-var path.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Run the required validation loop, compare against the failing baseline, and close out maintainer-facing guidance.

- [X] T036 [P] Run the targeted pytest suite in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`, `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`, `clients/python/tests/behavioral_coverage/test_itertesting_report.py`, and `clients/python/tests/test_behavioral_registry.py`
- [X] T037 [P] Run synthetic hardening and campaign validation in `tests/headless/test_live_itertesting_hardening.sh` and `tests/headless/test_itertesting_campaign.sh`
- [ ] T038 Run standalone probe validation in `tests/headless/behavioral-build.sh`
- [X] T039 Run three prepared live closeout reruns via `tests/headless/itertesting.sh`
- [X] T040 [P] Verify fixture-provisioning timing stays within the existing 90-second budget using `reports/itertesting/<run-id>/manifest.json` and `tests/headless/itertesting.sh`
- [X] T041 [P] Verify channel-health remains healthy in prepared live validation bundles using `reports/itertesting/<run-id>/manifest.json` and `tests/headless/test_itertesting_campaign.sh`
- [X] T042 Compare `reports/itertesting/<run-id>/manifest.json`, `reports/itertesting/<run-id>/run-report.md`, and `reports/itertesting/<run-id>/campaign-stop-decision.json` against `reports/itertesting/itertesting-20260423T024247Z/run-report.md` and `specs/016-live-bootstrap-hardening/spec.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: No dependencies.
- **Phase 2**: Depends on Phase 1 and blocks all user stories.
- **Phase 3 (US1)**: Depends on Phase 2.
- **Phase 4 (US2)**: Depends on Phase 2 and is best validated after US1 establishes explicit bootstrap-readiness state.
- **Phase 5 (US3)**: Depends on Phase 2 and reuses the shared runtime-resolution helpers introduced there.
- **Phase 6**: Depends on the selected user stories being complete.

### User Story Dependencies

- **US1 (P1)**: No hard dependency on other stories once foundational work is done.
- **US2 (P2)**: Builds on the shared bundle and classification plumbing from Phase 2, and benefits from US1 readiness capture to anchor diagnostic stages.
- **US3 (P3)**: Builds on the shared runtime-resolution model from Phase 2 and should agree with the readiness path introduced in US1 when both target the same live prerequisite.

### Within Each User Story

- Write the story tests first and confirm they fail before implementation.
- Land shared model/helper changes before report or shell output that consumes them.
- Keep bundle serialization in place before adding report rendering or maintainer summary text.
- Run the story’s independent validation before moving to the next priority.

### Parallel Opportunities

- `T002` and `T003` can run in parallel after `T001`.
- `T005`, `T006`, `T007`, `T008`, and `T009` can run in parallel after `T004`.
- `T010`, `T011`, and `T012` can run in parallel.
- `T019`, `T020`, and `T021` can run in parallel.
- `T027`, `T028`, and `T029` can run in parallel.
- `T036`, `T037`, `T040`, and `T041` can run in parallel once implementation is complete.

---

## Parallel Example: User Story 1

```bash
Task: "Add bootstrap-start viability and starved-start blocker regressions in clients/python/tests/test_behavioral_registry.py and clients/python/tests/behavioral_coverage/test_itertesting_runner.py"
Task: "Add report and classifier assertions for natural_ready, seeded_ready, and resource_starved outcomes in clients/python/tests/behavioral_coverage/test_itertesting_report.py and clients/python/tests/behavioral_coverage/test_live_failure_classification.py"
Task: "Add synthetic hardening assertions for explicit readiness blockers and seeded-readiness bundle evidence in tests/headless/test_live_itertesting_hardening.sh"
```

---

## Parallel Example: User Story 2

```bash
Task: "Add cached-vs-live callback retention regressions in clients/python/tests/behavioral_coverage/test_itertesting_runner.py and clients/python/tests/behavioral_coverage/test_live_failure_classification.py"
Task: "Add report-rendering regressions for preserved and missing callback diagnostics in clients/python/tests/behavioral_coverage/test_itertesting_report.py"
Task: "Add synthetic long-failure assertions for retained callback evidence in tests/headless/test_live_itertesting_hardening.sh and tests/headless/test_itertesting_campaign.sh"
```

---

## Parallel Example: User Story 3

```bash
Task: "Add runtime prerequisite-resolution regressions shared by live closeout and the standalone probe in clients/python/tests/behavioral_coverage/test_itertesting_runner.py and clients/python/tests/test_behavioral_registry.py"
Task: "Add report and classifier assertions for resolved, missing, and relay_unavailable prerequisite outcomes in clients/python/tests/behavioral_coverage/test_itertesting_report.py and clients/python/tests/behavioral_coverage/test_live_failure_classification.py"
Task: "Add headless probe validation assertions for callback-based prerequisite resolution in tests/headless/test_live_itertesting_hardening.sh and tests/headless/test_itertesting_campaign.sh"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1).
3. Validate that prepared live closeout either starts from a viable state or emits an explicit readiness blocker before the first commander-build timeout dominates the failure.
4. Stop and review the run bundle before adding long-failure retention and standalone-probe alignment.

### Incremental Delivery

1. Ship US1 to replace implicit starved-start behavior with explicit readiness assessment and seeded-path provenance.
2. Ship US2 to preserve callback-derived diagnostics across long bootstrap failures.
3. Ship US3 to align the standalone build probe with the same runtime prerequisite-resolution model as the main workflow.
4. Finish with Phase 6 validation against the April 23, 2026 failure baseline.

### Parallel Team Strategy

1. One developer lands Phase 1 and Phase 2 shared model/plumbing changes.
2. After foundational completion:
   - Developer A: US1 bootstrap readiness and seeded-path reporting.
   - Developer B: US2 callback snapshot capture, retention, and report rendering.
   - Developer C: US3 standalone probe runtime resolution and maintainer guidance.
3. Rejoin for Phase 6 prepared live validation and artifact review.

---

## Notes

- Total tasks: 42
- Story task counts: US1 = 9, US2 = 8, US3 = 9
- Parallel opportunities identified: Setup, foundational helper/rendering work, and the test phases for each story
- Independent test criteria:
  - US1: Prepared live closeout starts naturally or fails early with an explicit readiness blocker.
  - US2: Long bootstrap failures retain callback-derived diagnostics in the final bundle.
  - US3: The standalone probe resolves prerequisites through runtime callbacks or reports an explicit runtime-resolution blocker without env-var injection.
- Suggested MVP scope: Phase 3 / US1 only
- Format validation: All tasks use the required checklist format with checkbox, task id, optional `[P]`, story label for story phases, and exact file paths
