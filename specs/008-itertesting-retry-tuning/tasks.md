# Tasks: Itertesting Retry Tuning

**Input**: Design documents from `/specs/008-itertesting-retry-tuning/`  
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Include pytest and headless campaign validation tasks because the feature spec defines independent test criteria for each user story.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare retry-tuning scaffolding in the existing Itertesting workflow

- [X] T001 Add retry-tuning module stubs in clients/python/highbar_client/behavioral_coverage/itertesting_retry_policy.py and clients/python/highbar_client/behavioral_coverage/itertesting_campaign.py
- [X] T002 [P] Add retry-tuning test scaffolding in clients/python/tests/behavioral_coverage/test_itertesting_runner.py and clients/python/tests/behavioral_coverage/test_itertesting_report.py
- [X] T003 [P] Add retry-tuning headless scenario scaffolding in tests/headless/test_itertesting_campaign.sh and tests/headless/itertesting.sh

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core governance infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Define RetryIntensityProfile, CampaignRetryPolicy, RunProgressSnapshot, and CampaignStopDecision models in clients/python/highbar_client/behavioral_coverage/itertesting_types.py
- [X] T005 [P] Implement retry policy normalization and hard-cap clamp helpers in clients/python/highbar_client/behavioral_coverage/itertesting_retry_policy.py
- [X] T006 [P] Wire retry-intensity and governance CLI options in clients/python/highbar_client/behavioral_coverage/__init__.py and clients/python/highbar_client/behavioral_coverage/__main__.py
- [X] T007 [P] Add foundational validation tests for profile parsing and cap clamping in clients/python/tests/behavioral_coverage/test_itertesting_runner.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Prevent Runaway Campaigns (Priority: P1) 🎯 MVP

**Goal**: Stop campaigns early when progress stalls, enforce the 10-run global cap, and always emit a clear stop reason.

**Independent Test**: Run a campaign with no meaningful coverage improvement and confirm Itertesting stops early with an explicit stop reason without exhausting a high configured retry budget.

### Tests for User Story 1

- [X] T008 [P] [US1] Add stall-detection and early-stop orchestration tests in clients/python/tests/behavioral_coverage/test_itertesting_runner.py
- [X] T009 [P] [US1] Add run-report stop-reason visibility tests in clients/python/tests/behavioral_coverage/test_itertesting_report.py

### Implementation for User Story 1

- [X] T010 [US1] Implement rolling-window stall detection and early-stop evaluation in clients/python/highbar_client/behavioral_coverage/itertesting_campaign.py
- [X] T011 [US1] Enforce non-bypassable global max of 10 improvement runs in clients/python/highbar_client/behavioral_coverage/itertesting_retry_policy.py and clients/python/highbar_client/behavioral_coverage/itertesting_runner.py
- [X] T012 [US1] Emit canonical stop-decision records for each completed campaign in clients/python/highbar_client/behavioral_coverage/itertesting_runner.py and clients/python/highbar_client/behavioral_coverage/itertesting_types.py
- [X] T013 [US1] Render configured-vs-effective retries and stop reason sections in clients/python/highbar_client/behavioral_coverage/itertesting_report.py
- [X] T014 [US1] Add stalled-campaign headless validation path in tests/headless/test_itertesting_campaign.sh

**Checkpoint**: US1 should terminate unproductive campaigns predictably and report exactly why each campaign stopped.

---

## Phase 4: User Story 2 - Tune Retry Intensity by Intent (Priority: P2)

**Goal**: Provide quick/standard/deep retry intensity modes with predictable envelopes, natural-first behavior, and runtime-aware governance.

**Independent Test**: Run three campaigns using quick, standard, and deep intensity and verify each follows expected retry envelope and stop behavior.

### Tests for User Story 2

- [X] T015 [P] [US2] Add quick/standard/deep envelope behavior tests in clients/python/tests/behavioral_coverage/test_itertesting_runner.py
- [X] T016 [P] [US2] Add disproportionate-intensity warning and runtime-governance report tests in clients/python/tests/behavioral_coverage/test_itertesting_report.py

### Implementation for User Story 2

- [X] T017 [US2] Implement profile catalog and policy derivation for quick/standard/deep in clients/python/highbar_client/behavioral_coverage/itertesting_retry_policy.py
- [X] T018 [US2] Apply profile-specific stall windows and minimum direct-gain thresholds in clients/python/highbar_client/behavioral_coverage/itertesting_campaign.py
- [X] T019 [US2] Implement natural-first escalation gating and optional cheat escalation handoff in clients/python/highbar_client/behavioral_coverage/itertesting_campaign.py and clients/python/highbar_client/behavioral_coverage/itertesting_runner.py
- [X] T020 [US2] Implement runtime target guardrail and 15-minute governance checks in clients/python/highbar_client/behavioral_coverage/itertesting_campaign.py and clients/python/highbar_client/behavioral_coverage/itertesting_runner.py
- [X] T021 [US2] Surface intensity profile, warning triggers, and runtime metrics in clients/python/highbar_client/behavioral_coverage/itertesting_report.py
- [X] T022 [US2] Update CLI and shell wrapper support for retry intensity arguments in clients/python/highbar_client/behavioral_coverage/__init__.py and tests/headless/itertesting.sh
- [X] T023 [US2] Add multi-profile headless campaign checks in tests/headless/test_itertesting_campaign.sh

**Checkpoint**: US2 should make campaign depth intentional and predictable without violating stall and runtime guardrails.

---

## Phase 5: User Story 3 - Keep Improvement Guidance Reusable (Priority: P3)

**Goal**: Persist per-command instruction revisions across campaigns and reuse them automatically at campaign start.

**Independent Test**: Run two back-to-back campaigns and verify the second campaign loads prior instruction files and records revised versions when guidance changes.

### Tests for User Story 3

- [X] T024 [P] [US3] Add instruction load/revision persistence tests in clients/python/tests/behavioral_coverage/test_itertesting_runner.py
- [X] T025 [P] [US3] Add report coverage tests for instruction revision/status output in clients/python/tests/behavioral_coverage/test_itertesting_report.py

### Implementation for User Story 3

- [X] T026 [US3] Implement instruction bootstrap loading from reports/itertesting/instructions/ in clients/python/highbar_client/behavioral_coverage/itertesting_runner.py
- [X] T027 [US3] Implement per-command instruction revision increments and status transitions in clients/python/highbar_client/behavioral_coverage/itertesting_types.py and clients/python/highbar_client/behavioral_coverage/itertesting_runner.py
- [X] T028 [US3] Persist updated instruction records with deterministic file naming in clients/python/highbar_client/behavioral_coverage/itertesting_runner.py
- [X] T029 [US3] Extend campaign summary/report output for reusable guidance updates in clients/python/highbar_client/behavioral_coverage/itertesting_report.py
- [X] T030 [US3] Add back-to-back campaign reuse validation in tests/headless/test_itertesting_campaign.sh

**Checkpoint**: US3 should carry forward command guidance and evolve it with explicit revision tracking.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final consistency, documentation, and regression coverage across all stories

- [X] T031 [P] Update quickstart command examples and expected outcomes in specs/008-itertesting-retry-tuning/quickstart.md
- [X] T032 [P] Align contract docs with implemented report and stop-decision fields in specs/008-itertesting-retry-tuning/contracts/campaign-report-summary.md and specs/008-itertesting-retry-tuning/contracts/campaign-stop-decision.md
- [X] T033 Run behavioral coverage pytest suite updates in clients/python/tests/behavioral_coverage/test_itertesting_runner.py and clients/python/tests/behavioral_coverage/test_itertesting_report.py
- [X] T034 Run headless retry-tuning validation script and capture outcomes in tests/headless/test_itertesting_campaign.sh and reports/itertesting/

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies, can begin immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1, blocks all user stories.
- **Phase 3 (US1)**: Depends on Phase 2.
- **Phase 4 (US2)**: Depends on Phase 2; may start after US1 baseline stop-decision plumbing is merged.
- **Phase 5 (US3)**: Depends on Phase 2; best sequenced after US1/US2 report structures stabilize.
- **Phase 6 (Polish)**: Depends on completion of selected user stories.

### User Story Dependencies

- **US1 (P1)**: No dependency on other user stories once foundational tasks are done.
- **US2 (P2)**: No hard dependency on US3; uses US1 campaign-stop and report sections as baseline.
- **US3 (P3)**: No hard dependency on US2; reuses foundational campaign/run models and reporting pipeline.

### Within Each User Story

- Write tests first and confirm they fail before implementation.
- Implement or update data models/contracts before orchestration wiring that consumes them.
- Update report rendering after campaign fields are produced.
- Run headless validation after Python-level behavior is passing.

### Parallel Opportunities

- `T002` and `T003` can run in parallel after `T001`.
- `T005`, `T006`, and `T007` can run in parallel after `T004`.
- US1 test tasks `T008` and `T009` can run in parallel.
- US2 test tasks `T015` and `T016` can run in parallel.
- US3 test tasks `T024` and `T025` can run in parallel.
- Polish tasks `T031` and `T032` can run in parallel.

---

## Parallel Example: User Story 1

```bash
Task: "Add stall-detection and early-stop orchestration tests in clients/python/tests/behavioral_coverage/test_itertesting_runner.py"
Task: "Add run-report stop-reason visibility tests in clients/python/tests/behavioral_coverage/test_itertesting_report.py"
```

---

## Parallel Example: User Story 2

```bash
Task: "Add quick/standard/deep envelope behavior tests in clients/python/tests/behavioral_coverage/test_itertesting_runner.py"
Task: "Add disproportionate-intensity warning and runtime-governance report tests in clients/python/tests/behavioral_coverage/test_itertesting_report.py"
```

---

## Parallel Example: User Story 3

```bash
Task: "Add instruction load/revision persistence tests in clients/python/tests/behavioral_coverage/test_itertesting_runner.py"
Task: "Add report coverage tests for instruction revision/status output in clients/python/tests/behavioral_coverage/test_itertesting_report.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Implement Phase 3 (US1) only.
3. Validate early-stop + hard-cap + stop-reason behavior.
4. Demo/deploy MVP.

### Incremental Delivery

1. Ship US1 to eliminate runaway campaigns.
2. Ship US2 to add operator-intent retry profiles and runtime governance.
3. Ship US3 to reuse and evolve improvement guidance.
4. Finish with Phase 6 polish tasks.

### Parallel Team Strategy

1. One developer finalizes Phase 1 and Phase 2.
2. After foundational completion:
   - Developer A: US1 orchestration and stop decision flow.
   - Developer B: US2 policy/governance and profile behavior.
   - Developer C: US3 instruction persistence and report enrichment.
3. Rejoin for Phase 6 validation and documentation.

---

## Notes

- All tasks use required checklist format with task ID and exact file path.
- Story tasks include required `[US1]`, `[US2]`, or `[US3]` labels.
- Setup, foundational, and polish tasks intentionally omit story labels.
- Suggested MVP scope is US1 (Phase 3).
