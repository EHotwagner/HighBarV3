# Tasks: Build-Root Validation Completion

**Input**: Design documents from `/specs/012-build-root-validation/`  
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: This feature is a validation closeout workflow, so the core tasks intentionally include root `ctest`, pytest, headless reruns, and evidence verification tasks.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each closeout increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this belongs to (`[US1]`, `[US2]`, `[US3]`)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Closeout Inventory)

**Purpose**: Reconcile the active 012 closeout scope and standard command inventory before changing validation surfaces.

- [X] T001 Reconcile the 012 closeout command inventory in `specs/012-build-root-validation/quickstart.md`, `specs/011-contract-hardening-completion/quickstart.md`, and `tests/headless/README.md`
- [X] T002 [P] Baseline the unfinished 011 closeout work in `specs/011-contract-hardening-completion/tasks.md` and `specs/012-build-root-validation/plan.md`
- [X] T003 [P] Align the 012 contracts with the current closeout scope in `specs/012-build-root-validation/contracts/build-root-entrypoint.md`, `specs/012-build-root-validation/contracts/focused-rerun-matrix.md`, `specs/012-build-root-validation/contracts/environment-blocker-reporting.md`, and `specs/012-build-root-validation/contracts/completion-closeout-evidence.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Make the standard build-root and repo-root entrypoints deterministic before any story-specific reruns begin.

**Critical**: No user story work should start until this phase is complete.

- [ ] T004 Ensure the required root `ctest` targets remain discoverable from the standard build root in `CMakeLists.txt`
- [ ] T005 [P] Normalize build-root readiness and missing-target assertions in `tests/headless/test_command_contract_hardening.sh` and `tests/headless/test_live_itertesting_hardening.sh`
- [X] T006 [P] Normalize environment-versus-behavior blocker reporting in `tests/headless/itertesting.sh`, `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`, and `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [X] T007 Create a stable closeout evidence checklist in `specs/012-build-root-validation/quickstart.md` and `specs/012-build-root-validation/contracts/completion-closeout-evidence.md`

**Checkpoint**: Standard entrypoints, blocker vocabulary, and evidence expectations are consistent enough to start story-specific closeout work.

---

## Phase 3: User Story 1 - Run The Remaining Completion Checks From A Standard Build Root (Priority: P1)

**Goal**: Make the remaining 011 validation steps reachable from the standard build-root entrypoint with explicit pass, fail, or blocker outcomes.

**Independent Test**: Prepare the standard build root, run the documented discovery and focused C++ entrypoints, and confirm that required targets are visible and executable without ad hoc detours.

### Tests for User Story 1

- [ ] T008 [P] [US1] Add or tighten build-root discovery assertions in `tests/headless/test_command_contract_hardening.sh`
- [ ] T009 [P] [US1] Add or tighten build-root live-readiness assertions in `tests/headless/test_live_itertesting_hardening.sh`

### Implementation for User Story 1

- [ ] T010 [US1] Repair standard build-root discovery for `command_validation_test`, `ai_move_flow_test`, and `command_validation_perf_test` in `CMakeLists.txt`
- [X] T011 [US1] Align standard build-root instructions and blocker wording in `tests/headless/README.md` and `specs/011-contract-hardening-completion/quickstart.md`
- [X] T012 [US1] Record the standard build-root entrypoint and blocker expectations in `specs/012-build-root-validation/quickstart.md` and `specs/012-build-root-validation/contracts/build-root-entrypoint.md`
- [ ] T013 [US1] Run the standard build-root discovery and focused C++ checks documented in `specs/012-build-root-validation/quickstart.md` and reconcile any remaining mismatches in `tests/integration/ai_move_flow_test.cc` and `tests/unit/command_validation_perf_test.cc`

**Checkpoint**: Maintainers can reach the remaining C++ closeout checks from the standard build root and can tell when the environment is blocked before behavior is judged.

---

## Phase 4: User Story 2 - Complete The Final Hardening Reruns (Priority: P2)

**Goal**: Execute the remaining focused reruns, capture actionable evidence, and fix any exposed failures while keeping environment blockers distinct from behavior regressions.

**Independent Test**: Run the focused C++, Python, and headless reruns from the documented standard entrypoints and confirm that each required step produces an explicit outcome plus actionable evidence.

### Tests for User Story 2

- [ ] T014 [P] [US2] Run the focused C++ and validator-overhead reruns from `specs/012-build-root-validation/quickstart.md` and inspect `build/reports/command-validation/validator-overhead.json`
- [X] T015 [P] [US2] Run the focused Python behavioral reruns from `specs/012-build-root-validation/quickstart.md` against `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`, `clients/python/tests/behavioral_coverage/test_live_row_repro.py`, `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`, and `clients/python/tests/behavioral_coverage/test_itertesting_report.py`
- [X] T016 [P] [US2] Run the focused headless reruns from `specs/012-build-root-validation/quickstart.md` using `tests/headless/test_command_contract_hardening.sh`, `tests/headless/test_live_itertesting_hardening.sh`, and `tests/headless/malformed-payload.sh`

### Implementation for User Story 2

- [ ] T017 [US2] Fix any C++ rerun failures exposed by T014 in `src/circuit/grpc/CommandValidator.cpp`, `src/circuit/grpc/CommandDispatch.cpp`, `src/circuit/module/GrpcGatewayModule.cpp`, `tests/integration/ai_move_flow_test.cc`, and `tests/unit/command_validation_perf_test.cc`
- [ ] T018 [US2] Fix any Python behavioral rerun failures exposed by T015 in `clients/python/highbar_client/behavioral_coverage/audit_runner.py`, `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`, `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`, `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`, `clients/python/tests/behavioral_coverage/test_live_row_repro.py`, `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`, and `clients/python/tests/behavioral_coverage/test_itertesting_report.py`
- [X] T019 [US2] Fix any headless or blocker-reporting failures exposed by T016 in `tests/headless/itertesting.sh`, `tests/headless/test_command_contract_hardening.sh`, `tests/headless/test_live_itertesting_hardening.sh`, and `tests/headless/malformed-payload.sh`
- [X] T020 [US2] Refresh focused-rerun outcome documentation and blocker interpretation in `specs/012-build-root-validation/contracts/focused-rerun-matrix.md`, `specs/012-build-root-validation/contracts/environment-blocker-reporting.md`, and `specs/012-build-root-validation/quickstart.md`

**Checkpoint**: Every remaining focused rerun yields pass, fail, or blocker outcomes, and any exposed failures are specific enough to drive the next fix.

---

## Phase 5: User Story 3 - Close 011 With A Repeatable Final Validation Pass (Priority: P3)

**Goal**: Rerun the full 011 completion workflow from standard entrypoints after fixes and produce the evidence bundle required to close the remaining 011 work.

**Independent Test**: Rerun the documented full completion workflow after the focused reruns are green, confirm the final pass completes from standard entrypoints, and verify the resulting evidence bundle against the closeout contract.

### Tests for User Story 3

- [X] T021 [P] [US3] Run the full documented completion workflow from `specs/011-contract-hardening-completion/quickstart.md` and `specs/012-build-root-validation/quickstart.md`, including `HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh`
- [X] T022 [P] [US3] Verify the latest successful full-suite evidence bundle by selecting the most recent `reports/itertesting/<run-id>/manifest.json`, `reports/itertesting/<run-id>/run-report.md`, and `reports/itertesting/<run-id>/campaign-stop-decision.json` produced by T021 and checking them with `build/reports/command-validation/validator-overhead.json` against `specs/012-build-root-validation/contracts/completion-closeout-evidence.md`

### Implementation for User Story 3

- [ ] T023 [US3] Fix any final full-suite blockers exposed by T021 in `tests/headless/itertesting.sh`, `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`, `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`, `src/circuit/grpc/CommandValidator.cpp`, and `src/circuit/module/GrpcGatewayModule.cpp`
- [ ] T024 [US3] Run the constitution-mandated transport latency microbench after transport-adjacent fixes in `tests/bench/bench_latency.py`, `tests/bench/latency-uds.sh`, and `tests/bench/latency-tcp.sh`
- [ ] T025 [US3] Re-run the final closeout suite and align final guidance in `specs/011-contract-hardening-completion/quickstart.md`, `specs/012-build-root-validation/quickstart.md`, and `tests/headless/README.md`
- [ ] T026 [US3] Record the final closure criteria and evidence expectations in `specs/012-build-root-validation/contracts/completion-closeout-evidence.md` and `specs/012-build-root-validation/quickstart.md`

**Checkpoint**: The full documented 011 completion workflow reruns from standard entrypoints with a reviewable evidence bundle and no unresolved blocker ambiguity.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Reconcile the final closeout artifacts and make the remaining 011/012 status easy to audit.

- [ ] T027 [P] Reconcile the 011 and 012 closeout notes in `specs/011-contract-hardening-completion/tasks.md`, `specs/012-build-root-validation/tasks.md`, and `specs/012-build-root-validation/plan.md`
- [X] T028 [P] Verify agent and workflow references remain aligned in `AGENTS.md`, `specs/012-build-root-validation/plan.md`, and `specs/012-build-root-validation/tasks.md`
- [X] T029 Run a final documentation-to-command consistency pass across `tests/headless/README.md`, `specs/011-contract-hardening-completion/quickstart.md`, and `specs/012-build-root-validation/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies; start immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1 and blocks all user stories.
- **Phase 3 (US1)**: Depends on Phase 2.
- **Phase 4 (US2)**: Depends on US1 exposing a working standard build-root rerun path.
- **Phase 5 (US3)**: Depends on US2 focused reruns and follow-up fixes.
- **Phase 6 (Polish)**: Depends on the desired user stories being complete and documented.

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on later stories once foundational entrypoint work is complete.
- **User Story 2 (P2)**: Depends on US1 because the focused reruns must be reachable from the standard build-root and repo-root entrypoints first.
- **User Story 3 (P3)**: Depends on US2 because the full rerun only makes sense after the focused reruns are green or their blockers are fixed.

### Within Each User Story

- Add or tighten the story’s explicit validation checks before relying on the related entrypoint behavior.
- Run the focused validation commands before making story-specific fixes.
- Resolve surfaced failures before updating closeout documentation to claim the story is complete.
- Re-run the same documented commands after fixes before moving to the next story.

### Parallel Opportunities

- `T002` and `T003` can run in parallel after `T001`.
- `T005` and `T006` can run in parallel after `T004`.
- `T008` and `T009` can run in parallel for US1.
- `T014`, `T015`, and `T016` can run in parallel for US2.
- `T021` and `T022` can run in parallel for US3 after the full rerun artifacts exist.
- `T027`, `T028`, and `T029` can run in parallel during final reconciliation.

---

## Parallel Example: User Story 1

```bash
Task: "Add or tighten build-root discovery assertions in tests/headless/test_command_contract_hardening.sh"
Task: "Add or tighten build-root live-readiness assertions in tests/headless/test_live_itertesting_hardening.sh"
```

---

## Parallel Example: User Story 2

```bash
Task: "Run the focused C++ and validator-overhead reruns from specs/012-build-root-validation/quickstart.md and inspect build/reports/command-validation/validator-overhead.json"
Task: "Run the focused Python behavioral reruns from specs/012-build-root-validation/quickstart.md against clients/python/tests/behavioral_coverage/"
Task: "Run the focused headless reruns from specs/012-build-root-validation/quickstart.md using tests/headless/test_command_contract_hardening.sh, tests/headless/test_live_itertesting_hardening.sh, and tests/headless/malformed-payload.sh"
```

---

## Parallel Example: User Story 3

```bash
Task: "Run the full documented completion workflow from specs/011-contract-hardening-completion/quickstart.md and specs/012-build-root-validation/quickstart.md"
Task: "Verify the final closeout evidence in build/reports/command-validation/validator-overhead.json and reports/itertesting/<run-id>/ against specs/012-build-root-validation/contracts/completion-closeout-evidence.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: User Story 1.
4. Stop and validate that the remaining C++ closeout checks are reachable from the standard build root with explicit blocker reporting.

### Incremental Delivery

1. Finish Setup and Foundational work.
2. Deliver US1 to restore the standard build-root rerun path.
3. Deliver US2 to run the focused reruns and fix any exposed failures.
4. Deliver US3 to rerun the full completion workflow and collect the final closure evidence.
5. Reconcile docs and workflow references in the Polish phase.

### Parallel Team Strategy

1. One developer handles Setup and Foundational alignment.
2. After Phase 2:
   - Developer A: US1 build-root discovery and standard entrypoint docs.
   - Developer B: US2 focused reruns, failure triage, and Python/headless fixes.
   - Developer C: US3 final rerun and evidence reconciliation once US2 is ready.
3. Rejoin for Phase 6 final audit and documentation cleanup.

---

## Notes

- All tasks use the required checklist format with task ID, optional `[P]`, optional story label, and explicit file paths.
- The task list stays intentionally close to the operational closeout work defined in 011 tasks `T028` through `T031`, but splits that work into independently testable user stories for feature 012.
- The suggested MVP scope is **User Story 1**, because the remaining workflow cannot progress until the standard build-root path is working again.
