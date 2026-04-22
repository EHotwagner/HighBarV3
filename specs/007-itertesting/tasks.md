# Tasks: Itertesting

**Input**: Design documents from `/specs/007-itertesting/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Include pytest coverage for manifest/report/orchestration behavior and repo-local headless validation for the Itertesting CLI path because the spec requires independent test criteria for each story.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish Itertesting module and test scaffolding in the existing behavioral coverage package

- [X] T001 Create Itertesting module stubs in clients/python/highbar_client/behavioral_coverage/itertesting_runner.py, clients/python/highbar_client/behavioral_coverage/itertesting_report.py, and clients/python/highbar_client/behavioral_coverage/itertesting_types.py
- [X] T002 [P] Create Itertesting pytest scaffolding in clients/python/tests/behavioral_coverage/test_itertesting_runner.py and clients/python/tests/behavioral_coverage/test_itertesting_report.py
- [X] T003 [P] Add repo-local Itertesting launch coverage in tests/headless/test_itertesting_campaign.sh and tests/headless/itertesting.sh

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Define campaign, run, command-record, improvement-action, and comparison dataclasses plus manifest serialization helpers in clients/python/highbar_client/behavioral_coverage/itertesting_types.py
- [X] T005 [P] Implement UTC second-precision run-id generation, deterministic same-second collision suffixes, and report directory path helpers in clients/python/highbar_client/behavioral_coverage/itertesting_runner.py
- [X] T006 [P] Wire the `itertesting` subcommand, campaign arguments, and module dispatch in clients/python/highbar_client/behavioral_coverage/__init__.py and clients/python/highbar_client/behavioral_coverage/__main__.py
- [X] T007 Add foundational unit coverage for manifest validation, run-id collision handling, and CLI argument parsing in clients/python/tests/behavioral_coverage/test_itertesting_runner.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Grow Verified Command Coverage (Priority: P1) 🎯 MVP

**Goal**: Deliver one Itertesting run that records every tracked command, persists a timestamped run bundle (`manifest.json` and `run-report.md`), and summarizes directly observed verification evidence.

**Independent Test**: Run `python -m highbar_client.behavioral_coverage itertesting --reports-dir reports/itertesting --max-improvement-runs 0` and confirm the generated run bundle contains `manifest.json` plus `run-report.md`, covering every tracked command with concrete verification status and evidence summaries.

### Tests for User Story 1

- [X] T008 [P] [US1] Add manifest-shape, command-coverage, and dispatch-only-never-verifies tests in clients/python/tests/behavioral_coverage/test_itertesting_runner.py
- [X] T009 [P] [US1] Add markdown report rendering tests for coverage totals and unverified command sections in clients/python/tests/behavioral_coverage/test_itertesting_report.py

### Implementation for User Story 1

- [X] T010 [P] [US1] Implement command inventory expansion and per-command record initialization in clients/python/highbar_client/behavioral_coverage/itertesting_runner.py
- [X] T011 [US1] Implement single-run execution that classifies commands as verified, inconclusive, blocked, or failed from live behavioral evidence in clients/python/highbar_client/behavioral_coverage/itertesting_runner.py
- [X] T012 [P] [US1] Implement manifest.json writing and loading for one run in clients/python/highbar_client/behavioral_coverage/itertesting_runner.py
- [X] T013 [US1] Implement reviewer-facing `run-report.md` generation from manifest data in clients/python/highbar_client/behavioral_coverage/itertesting_report.py
- [X] T014 [US1] Connect the `itertesting` CLI flow to single-run execution and report emission in clients/python/highbar_client/behavioral_coverage/__init__.py
- [X] T015 [US1] Add the repo-local single-run wrapper for maintainers in tests/headless/itertesting.sh

**Checkpoint**: User Story 1 should produce a complete single-run Itertesting bundle that reviewers can inspect without raw logs

---

## Phase 4: User Story 2 - Iterate After Failures (Priority: P1)

**Goal**: Let Itertesting analyze unverified commands, record explicit improvements, and launch bounded follow-up runs that reference prior results.

**Independent Test**: Force an initial run with unverified commands, rerun Itertesting with `--max-improvement-runs 1`, and confirm the second run records previous-run comparison data plus concrete improvement actions instead of replaying the same unchanged attempt.

### Tests for User Story 2

- [X] T016 [P] [US2] Add retry-budget, stop-reason, and previous-run comparison tests in clients/python/tests/behavioral_coverage/test_itertesting_runner.py
- [X] T017 [P] [US2] Add report tests for improvement actions, coverage deltas, and stalled-versus-improved summaries in clients/python/tests/behavioral_coverage/test_itertesting_report.py

### Implementation for User Story 2

- [X] T018 [P] [US2] Implement per-command improvement planning for setup, target, evidence, timing, and exhausted cases in clients/python/highbar_client/behavioral_coverage/itertesting_runner.py
- [X] T019 [US2] Implement campaign orchestration that chains runs, applies retry budgets, and records campaign stop reasons in clients/python/highbar_client/behavioral_coverage/itertesting_runner.py
- [X] T020 [P] [US2] Implement previous-run comparison and run-summary aggregation in clients/python/highbar_client/behavioral_coverage/itertesting_types.py and clients/python/highbar_client/behavioral_coverage/itertesting_runner.py
- [X] T021 [US2] Extend markdown generation with cross-run comparison, newly verified, regressed, and next-improvement sections in clients/python/highbar_client/behavioral_coverage/itertesting_report.py
- [X] T022 [US2] Add a bounded campaign validation script that exercises chained Itertesting runs in tests/headless/test_itertesting_campaign.sh

**Checkpoint**: User Story 2 should support unattended bounded reruns with explicit improvement tracking and readable run-to-run progress

---

## Phase 5: User Story 3 - Use Supplemental Setup Tools (Priority: P2)

**Goal**: Support natural-first verification with explicit cheat-assisted escalation and separate reporting for commands that require supplemental setup.

**Independent Test**: Run Itertesting with `--allow-cheat-escalation --cheat-startscript tests/headless/scripts/cheats.startscript` and confirm the campaign escalates only after natural progress stalls, records cheat-backed setup actions, and separates cheat-assisted verified counts from natural ones.

### Tests for User Story 3

- [X] T023 [P] [US3] Add natural-first and cheat-escalation policy tests in clients/python/tests/behavioral_coverage/test_itertesting_runner.py
- [X] T024 [P] [US3] Add report tests for cheat-assisted labeling and split verification totals in clients/python/tests/behavioral_coverage/test_itertesting_report.py

### Implementation for User Story 3

- [X] T025 [P] [US3] Implement natural-first escalation rules and cheat-assisted setup action recording in clients/python/highbar_client/behavioral_coverage/itertesting_runner.py
- [X] T026 [US3] Add cheat startscript CLI options and setup-mode propagation in clients/python/highbar_client/behavioral_coverage/__init__.py and tests/headless/itertesting.sh
- [X] T027 [US3] Extend manifest/report serialization for setup mode, setup actions, and cheat-assisted verification totals in clients/python/highbar_client/behavioral_coverage/itertesting_types.py and clients/python/highbar_client/behavioral_coverage/itertesting_report.py
- [X] T028 [US3] Add headless cheat-escalation coverage for Itertesting in tests/headless/test_itertesting_campaign.sh

**Checkpoint**: User Story 3 should clearly disclose when supplemental setup was used and keep natural versus cheat-assisted verification separable

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final cleanup, quickstart alignment, and execution guidance across all stories

- [X] T029 [P] Document the maintainer workflow and expected artifact bundle in specs/007-itertesting/quickstart.md and tests/headless/README.md
- [X] T030 Verify the Itertesting CLI help text, command examples, and report locations in clients/python/highbar_client/behavioral_coverage/__init__.py and specs/007-itertesting/quickstart.md
- [X] T031 [P] Add regression coverage for malformed prior manifests and incomplete run bundles in clients/python/tests/behavioral_coverage/test_itertesting_runner.py

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational completion
- **User Story 2 (Phase 4)**: Depends on User Story 1 manifest/report flow being in place
- **User Story 3 (Phase 5)**: Depends on User Story 2 campaign orchestration and improvement planning
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Starts after Phase 2 and establishes the MVP single-run artifact flow
- **User Story 2 (P1)**: Starts after US1 because it extends the stored run state into bounded campaigns
- **User Story 3 (P2)**: Starts after US2 because cheat escalation depends on the campaign improvement loop and comparison state

### Within Each User Story

- Tests should be written before implementation and fail first
- Manifest and dataclass updates should land before runner/report integration that consumes them
- CLI wiring follows runner/report behavior, not the other way around
- Headless wrapper and validation scripts should run after the Python flow they exercise exists

### Parallel Opportunities

- `T002` and `T003` can run alongside `T001`
- `T005` and `T006` can run alongside each other after `T004`
- `T008` and `T009` can run in parallel for US1
- `T010` and `T012` can run in parallel before `T011`/`T013` integrate them
- `T016` and `T017` can run in parallel for US2
- `T018` and `T020` can run in parallel before `T019`/`T021`
- `T023` and `T024` can run in parallel for US3
- `T025` and `T027` can run in parallel before `T026`/`T028`
- `T029` and `T031` can run in parallel during polish

---

## Parallel Example: User Story 1

```bash
# Launch the US1 test tasks together:
Task: "Add manifest-shape and command-coverage tests in clients/python/tests/behavioral_coverage/test_itertesting_runner.py"
Task: "Add markdown report rendering tests for coverage totals and unverified command sections in clients/python/tests/behavioral_coverage/test_itertesting_report.py"

# Launch the US1 implementation tasks that touch different files:
Task: "Implement command inventory expansion and per-command record initialization in clients/python/highbar_client/behavioral_coverage/itertesting_runner.py"
Task: "Implement manifest.json writing and loading for one run in clients/python/highbar_client/behavioral_coverage/itertesting_runner.py"
```

---

## Parallel Example: User Story 2

```bash
# Launch the US2 test tasks together:
Task: "Add retry-budget, stop-reason, and previous-run comparison tests in clients/python/tests/behavioral_coverage/test_itertesting_runner.py"
Task: "Add report tests for improvement actions, coverage deltas, and stalled-versus-improved summaries in clients/python/tests/behavioral_coverage/test_itertesting_report.py"

# Launch the US2 implementation tasks that do not block each other immediately:
Task: "Implement per-command improvement planning for setup, target, evidence, timing, and exhausted cases in clients/python/highbar_client/behavioral_coverage/itertesting_runner.py"
Task: "Implement previous-run comparison and run-summary aggregation in clients/python/highbar_client/behavioral_coverage/itertesting_types.py and clients/python/highbar_client/behavioral_coverage/itertesting_runner.py"
```

---

## Parallel Example: User Story 3

```bash
# Launch the US3 test tasks together:
Task: "Add natural-first and cheat-escalation policy tests in clients/python/tests/behavioral_coverage/test_itertesting_runner.py"
Task: "Add report tests for cheat-assisted labeling and split verification totals in clients/python/tests/behavioral_coverage/test_itertesting_report.py"

# Launch the US3 implementation tasks that touch different concerns:
Task: "Implement natural-first escalation rules and cheat-assisted setup action recording in clients/python/highbar_client/behavioral_coverage/itertesting_runner.py"
Task: "Extend manifest/report serialization for setup mode, setup actions, and cheat-assisted verification totals in clients/python/highbar_client/behavioral_coverage/itertesting_types.py and clients/python/highbar_client/behavioral_coverage/itertesting_report.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. Validate a single Itertesting run and its report bundle under `reports/itertesting/`
5. Stop before campaign retries or cheat escalation work

### Incremental Delivery

1. Ship Setup + Foundational to establish the new CLI/module surface
2. Ship User Story 1 for one-run manifest/report generation
3. Ship User Story 2 for bounded retries and improvement tracking
4. Ship User Story 3 for cheat-assisted escalation and split reporting
5. Finish with documentation and malformed-artifact regression coverage

### Parallel Team Strategy

1. One developer completes Phase 1 and Phase 2
2. After foundation is stable:
   Developer A focuses on runner state/orchestration in `itertesting_runner.py`
   Developer B focuses on report rendering and manifest shape in `itertesting_report.py` and `itertesting_types.py`
   Developer C focuses on repo-local validation in `tests/headless/itertesting.sh` and `tests/headless/test_itertesting_campaign.sh`

---

## Notes

- All checklist entries use the required `- [ ] T### ...` format with exact file paths
- Story tasks are labeled `[US1]`, `[US2]`, or `[US3]`; setup/foundation/polish tasks intentionally omit story labels
- The MVP scope is User Story 1 only
- Tasks assume Itertesting remains inside the existing behavioral coverage package and headless shell workflow
