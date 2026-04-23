# Tasks: Live Bootstrap Hardening

**Input**: Design documents from `/specs/016-live-bootstrap-hardening/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Include pytest and headless validation tasks because the feature spec defines independent test criteria for every user story and `quickstart.md` makes the validation loop part of feature completion.

**Organization**: Tasks are grouped by user story so each increment can be implemented and validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel once dependencies in the current phase are satisfied.
- **[Story]**: User story label for story-phase tasks only.
- Every task includes exact file paths.

## Phase 1: Setup (Shared Validation Scaffolding)

**Purpose**: Prepare the regression and maintainer validation surfaces used by all three stories.

- [ ] T001 Add canonical hardening metadata fixtures for bootstrap, capability, and probe outcomes in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`
- [ ] T002 [P] Add shared report and classifier fixture coverage for readiness, capability limits, and map-source output in `clients/python/tests/behavioral_coverage/test_itertesting_report.py` and `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`
- [ ] T003 [P] Add shared shell-level artifact assertions for hardening bundle output in `tests/headless/test_live_itertesting_hardening.sh` and `tests/headless/test_itertesting_campaign.sh`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the shared data model, manifest plumbing, and helper seams required before story work can begin.

**⚠️ CRITICAL**: No user story work should start until this phase is complete.

- [X] T004 Define `RuntimeCapabilityProfile` and `MapDataSourceDecision` in `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`
- [X] T005 Extend `ItertestingRun`, manifest serialization, and manifest loading for runtime capability and map-source records in `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`
- [ ] T006 [P] Add shared callback capability-profile and map-source helper scaffolding in `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [X] T007 [P] Add foundational metadata extraction for capability and map-source records in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T008 [P] Add base runtime capability and map-source report sections in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [X] T009 [P] Add foundational capability-limit classification vocabulary in `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`
- [X] T010 [P] Add manifest/report/classifier round-trip regressions for the new shared records in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`, `clients/python/tests/behavioral_coverage/test_itertesting_report.py`, and `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`

**Checkpoint**: The shared run-bundle schema, report sections, and helper seams are ready for user-story implementation.

---

## Phase 3: User Story 1 - Start Bootstrap From a Viable Live State (Priority: P1) 🎯 MVP

**Goal**: Ensure prepared live closeout either starts commander bootstrap from a viable state or fails immediately with an explicit readiness outcome.

**Independent Test**: Run prepared live closeout from the standard prepared scenario and confirm that the first commander build either proceeds naturally or the run stops with an explicit bootstrap-readiness blocker before a downstream build timeout becomes the primary signal.

### Tests for User Story 1

- [ ] T011 [P] [US1] Add starved-start and viable-start bootstrap regressions in `clients/python/tests/test_behavioral_registry.py` and `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`
- [ ] T012 [P] [US1] Add report and classifier assertions for `natural_ready`, `seeded_ready`, and `resource_starved` outcomes in `clients/python/tests/behavioral_coverage/test_itertesting_report.py` and `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`
- [ ] T013 [P] [US1] Add synthetic prepared-live assertions for explicit readiness blockers and seeded-readiness bundle evidence in `tests/headless/test_live_itertesting_hardening.sh`

### Implementation for User Story 1

- [ ] T014 [US1] Implement first-commander-step viability assessment and early resource-starvation blocking in `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [ ] T015 [US1] Implement the maintainer-visible explicit seed readiness path in `clients/python/highbar_client/behavioral_coverage/bootstrap.py` and `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [ ] T016 [US1] Persist bootstrap-readiness metadata and manifest shaping in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [ ] T017 [US1] Render bootstrap-readiness outcomes and blocker wording in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [ ] T018 [US1] Keep bootstrap-readiness blockers distinct from later behavior or transport failures in `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`
- [ ] T019 [US1] Surface bootstrap-readiness summaries in `tests/headless/itertesting.sh`

**Checkpoint**: User Story 1 is complete when prepared live closeout no longer treats a resource-starved opening state as an ordinary bootstrap timeout.

---

## Phase 4: User Story 2 - Make Runtime Capability Limits Explicit in Live Diagnostics (Priority: P2)

**Goal**: Record the host capability boundary explicitly, preserve usable prerequisite evidence, and use session-start map data when callback inspection is unavailable.

**Independent Test**: Run prepared live closeout on a callback-limited runtime and confirm that the final bundle preserves successful prerequisite lookup, marks deeper unsupported diagnostics as capability-limited, and records `HelloResponse.static_map` as the active map source when callback map inspection is unavailable.

### Tests for User Story 2

- [X] T020 [P] [US2] Add runtime capability-profile and preserved-prerequisite regressions in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`
- [X] T021 [P] [US2] Add report and classifier assertions for capability-limited diagnostics and map-source decisions in `clients/python/tests/behavioral_coverage/test_itertesting_report.py` and `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`
- [ ] T022 [P] [US2] Add callback-limited host and `static_map` sourcing assertions in `tests/headless/test_live_itertesting_hardening.sh` and `tests/headless/test_itertesting_campaign.sh`
- [X] T023 [P] [US2] Add missing-session-start-map regressions in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py` and `clients/python/tests/behavioral_coverage/test_itertesting_report.py`

### Implementation for User Story 2

- [X] T024 [US2] Capture supported callbacks, unsupported groups, and usable inspection scopes in `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [X] T025 [US2] Preserve successful prerequisite-resolution evidence across later capability-limited diagnostics in `clients/python/highbar_client/behavioral_coverage/__init__.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [ ] T026 [US2] Select `HelloResponse.static_map` as the authoritative fallback map source in `clients/python/highbar_client/behavioral_coverage/__init__.py` and `specs/002-live-headless-e2e/examples/coordinator.py`
- [X] T027 [US2] Serialize `RuntimeCapabilityProfile`, `CallbackDiagnosticSnapshot`, and `MapDataSourceDecision` into run bundles in `clients/python/highbar_client/behavioral_coverage/itertesting_types.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T028 [US2] Render runtime capability, map-source, and capability-limited diagnostic sections in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [X] T029 [US2] Classify and render `selected_source=missing` distinctly from unsupported callback inspection in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`, `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`, and `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`
- [X] T030 [US2] Classify unsupported callback groups separately from relay loss and command-behavior failure in `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`
- [X] T031 [US2] Emit capability-profile, callback-diagnostic, and map-source summaries from `tests/headless/itertesting.sh`

**Checkpoint**: User Story 2 is complete when callback-limited hosts produce bundles that clearly separate unsupported inspection from real workflow or transport failures.

---

## Phase 5: User Story 3 - Keep Standalone Build Verification Aligned With Supported Runtime Sources (Priority: P3)

**Goal**: Make the standalone build probe resolve prerequisites and map data through the same supported runtime sources as prepared live closeout.

**Independent Test**: Run `tests/headless/behavioral-build.sh` in a prepared live environment without manual prerequisite injection and confirm that it resolves the target definition from the runtime, uses session-start map data for targeting when needed, and reports unsupported deeper diagnostics as capability limits.

### Tests for User Story 3

- [ ] T032 [P] [US3] Add shared prerequisite-resolution and standalone-probe outcome regressions in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py` and `clients/python/tests/test_behavioral_registry.py`
- [X] T033 [P] [US3] Add report assertions for standalone probe map-source and capability-limit output in `clients/python/tests/behavioral_coverage/test_itertesting_report.py`
- [ ] T034 [P] [US3] Add standalone-probe validation assertions for runtime resolution without env-var injection in `tests/headless/test_live_itertesting_hardening.sh` and `tests/headless/test_itertesting_campaign.sh`

### Implementation for User Story 3

- [ ] T035 [US3] Align prerequisite resolution in `tests/headless/behavioral-build.sh` with the supported `CALLBACK_GET_UNIT_DEFS` and `CALLBACK_UNITDEF_GET_NAME` path used by `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [X] T036 [US3] Use session-start `static_map` and explicit map-source selection output in `tests/headless/behavioral-build.sh`
- [X] T037 [US3] Emit structured standalone probe outcome records with resolution, map-source, and capability-limit fields in `tests/headless/behavioral-build.sh`
- [X] T038 [US3] Load and render expanded standalone probe outcome fields in `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`, `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`, and `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [X] T039 [US3] Align standalone-probe failure wording with capability-limited runtime states in `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py` and `tests/headless/behavioral-build.sh`
- [X] T040 [US3] Update maintainer guidance for standalone probe and live workflow agreement in `tests/headless/README.md` and `specs/016-live-bootstrap-hardening/quickstart.md`

**Checkpoint**: User Story 3 is complete when the standalone probe and main workflow agree on prerequisite identity and map-source selection without relying on the legacy env-var path.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Run the required validation loop and confirm the final artifacts match the feature contracts.

- [ ] T041 [P] Add integration coverage for Hello/static_map relay and callback-path compatibility in `tests/integration/transport_parity_test.cc`
- [ ] T042 [P] Run the targeted pytest suite in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`, `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`, `clients/python/tests/behavioral_coverage/test_itertesting_report.py`, and `clients/python/tests/test_behavioral_registry.py`
- [ ] T043 [P] Run synthetic hardening and campaign validation in `tests/headless/test_live_itertesting_hardening.sh` and `tests/headless/test_itertesting_campaign.sh`
- [ ] T044 Run standalone probe validation in `tests/headless/behavioral-build.sh`
- [ ] T045 Run three prepared live closeout reruns through `tests/headless/itertesting.sh` and inspect `reports/itertesting/<run-id>/manifest.json`
- [ ] T046 Run broader-capability-host non-regression validation through `tests/headless/itertesting.sh` and inspect `reports/itertesting/<run-id>/manifest.json` and `reports/itertesting/<run-id>/run-report.md`
- [ ] T047 [P] Verify `reports/itertesting/<run-id>/manifest.json`, `reports/itertesting/<run-id>/run-report.md`, `reports/itertesting/<run-id>/campaign-stop-decision.json`, and `behavioral-build-outcome.json` agree on `bootstrap_readiness`, `runtime_capability_profile`, `map_source_decisions`, `prerequisite_resolution`, and standalone probe `dispatch_result`
- [ ] T048 [P] Verify the final validation evidence satisfies `FR-012` and `SC-006` against `specs/016-live-bootstrap-hardening/spec.md`, `specs/016-live-bootstrap-hardening/contracts/live-bootstrap-validation-suite.md`, and `specs/016-live-bootstrap-hardening/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: No dependencies.
- **Phase 2**: Depends on Phase 1 and blocks all user stories.
- **Phase 3 (US1)**: Depends on Phase 2.
- **Phase 4 (US2)**: Depends on Phase 2 and should build on the shared manifest/report seams from Phase 2.
- **Phase 5 (US3)**: Depends on Phase 4 because the standalone probe reuses the capability-profile and map-source rules established in US2.
- **Phase 6**: Depends on the user stories you intend to ship.

### User Story Dependencies

- **US1 (P1)**: No dependency on other user stories once foundational work is complete.
- **US2 (P2)**: No hard dependency on US1, but it benefits from US1 readiness metadata already being present in the bundle.
- **US3 (P3)**: Depends on the shared capability-profile and map-source rules from US2 so the standalone probe matches the main workflow.

### Within Each User Story

- Write the story tests first and confirm they fail before implementation.
- Land shared manifest/schema updates before report rendering that consumes them.
- Persist structured records before updating shell summaries or documentation.
- Validate each story independently before moving to the next priority.

### Parallel Opportunities

- `T002` and `T003` can run in parallel after `T001`.
- `T006`, `T007`, `T008`, `T009`, and `T010` can run in parallel after `T005`.
- `T011`, `T012`, and `T013` can run in parallel.
- `T020`, `T021`, `T022`, and `T023` can run in parallel.
- `T032`, `T033`, and `T034` can run in parallel.
- `T041`, `T042`, `T043`, and `T047` can run in parallel once implementation is complete.

---

## Parallel Example: User Story 1

```bash
Task: "Add starved-start and viable-start bootstrap regressions in clients/python/tests/test_behavioral_registry.py and clients/python/tests/behavioral_coverage/test_itertesting_runner.py"
Task: "Add report and classifier assertions for natural_ready, seeded_ready, and resource_starved outcomes in clients/python/tests/behavioral_coverage/test_itertesting_report.py and clients/python/tests/behavioral_coverage/test_live_failure_classification.py"
Task: "Add synthetic prepared-live assertions for explicit readiness blockers and seeded-readiness bundle evidence in tests/headless/test_live_itertesting_hardening.sh"
```

---

## Parallel Example: User Story 2

```bash
Task: "Add runtime capability-profile and preserved-prerequisite regressions in clients/python/tests/behavioral_coverage/test_itertesting_runner.py"
Task: "Add report and classifier assertions for capability-limited diagnostics and map-source decisions in clients/python/tests/behavioral_coverage/test_itertesting_report.py and clients/python/tests/behavioral_coverage/test_live_failure_classification.py"
Task: "Add callback-limited host and static_map sourcing assertions in tests/headless/test_live_itertesting_hardening.sh and tests/headless/test_itertesting_campaign.sh"
Task: "Add missing-session-start-map regressions in clients/python/tests/behavioral_coverage/test_itertesting_runner.py and clients/python/tests/behavioral_coverage/test_itertesting_report.py"
```

---

## Parallel Example: User Story 3

```bash
Task: "Add shared prerequisite-resolution and standalone-probe outcome regressions in clients/python/tests/behavioral_coverage/test_itertesting_runner.py and clients/python/tests/test_behavioral_registry.py"
Task: "Add report assertions for standalone probe map-source and capability-limit output in clients/python/tests/behavioral_coverage/test_itertesting_report.py"
Task: "Add standalone-probe validation assertions for runtime resolution without env-var injection in tests/headless/test_live_itertesting_hardening.sh and tests/headless/test_itertesting_campaign.sh"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1).
3. Validate that prepared live closeout either starts from a viable state or emits an explicit readiness blocker before the first commander-build timeout dominates the failure.
4. Stop and review the bundle before expanding capability-aware diagnostics.

### Incremental Delivery

1. Ship US1 to make bootstrap readiness explicit.
2. Ship US2 to make runtime capability limits, missing-map handling, and map-source selection explicit in the bundle.
3. Ship US3 to align the standalone build probe with the same supported runtime sources.
4. Finish with Phase 6 validation against the feature contracts and quickstart loop.

### Parallel Team Strategy

1. One developer handles Phase 1 and Phase 2 shared schema and report groundwork.
2. After foundational work is done:
   - Developer A: US1 bootstrap readiness and seeded-path handling.
   - Developer B: US2 capability-profile, callback-diagnostic, and map-source reporting.
   - Developer C: US3 standalone probe alignment and maintainer guidance.
3. Rejoin for Phase 6 validation and artifact review.

---

## Notes

- Total tasks: 48
- Story task counts: US1 = 9, US2 = 12, US3 = 9
- Parallel opportunities identified: setup validation work, foundational schema/report/classifier work, and the test phases for each user story
- Independent test criteria:
  - US1: Prepared live closeout starts naturally or fails early with an explicit readiness blocker.
  - US2: Callback-limited hosts preserve prerequisite evidence, expose capability limits, and distinguish session-start map data from truly missing map data.
  - US3: The standalone probe resolves prerequisites and selects map data from the same supported sources as prepared live closeout without relying on `HIGHBAR_ARMMEX_DEF_ID`.
- Suggested MVP scope: Phase 3 / US1 only
- Format validation: All tasks use the required checklist format with checkbox, task id, optional `[P]`, story label for story phases, and explicit file paths
