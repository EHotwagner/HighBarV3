# Tasks: Command Contract Hardening Completion

**Input**: Design documents from `/specs/011-contract-hardening-completion/`  
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Include C++ integration/unit/perf, Python pytest, and headless validation tasks because the spec explicitly requires runnable completion coverage and test-driven validation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this belongs to (`[US1]`, `[US2]`, `[US3]`)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the completion-suite command inventory and shared harness scaffolding.

- [X] T001 Define the completion-suite command inventory in `specs/011-contract-hardening-completion/quickstart.md`, `tests/headless/README.md`, and `specs/011-contract-hardening-completion/contracts/validation-suite.md`
- [X] T002 [P] Add shared C++/CTest completion scaffolding in `tests/integration/ai_move_flow_test.cc`, `tests/unit/command_validation_test.cc`, and `CMakeLists.txt`
- [X] T003 [P] Add shared Python/headless completion fixtures in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`, `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`, `tests/headless/test_command_contract_hardening.sh`, and `tests/headless/test_live_itertesting_hardening.sh`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the shared contract-health, repro, and wrapper primitives that every story depends on.

**Critical**: No user story work should start until this phase is complete.

- [X] T004 Extend completion metadata shapes and serialization in `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`, `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`, and `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [X] T005 [P] Centralize deterministic repro selection and pattern-review fallback helpers in `clients/python/highbar_client/behavioral_coverage/audit_runner.py` and `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`
- [X] T006 [P] Add reusable contract-hardening assertions and command helpers in `tests/unit/command_validation_test.cc`, `tests/integration/ai_move_flow_test.cc`, `tests/headless/test_command_contract_hardening.sh`, and `tests/headless/itertesting.sh`

**Checkpoint**: Shared completion models, repro plumbing, and wrapper helpers are ready for story-specific work.

---

## Phase 3: User Story 1 - Complete Contract Validation Coverage (Priority: P1)

**Goal**: Finish authoritative-target, malformed-payload, and inert-dispatch validation across the same integration and live workflows maintainers use.

**Independent Test**: Run the focused integration and headless suite for `ai_move_flow_test`, malformed payload rejection, and live inert-dispatch classification, and confirm authoritative target preservation plus correct blocker separation.

### Tests for User Story 1

- [X] T007 [P] [US1] Add authoritative-target drain coverage in `tests/integration/ai_move_flow_test.cc`
- [X] T008 [P] [US1] Add validator and malformed-payload regression coverage in `tests/unit/command_validation_test.cc` and `tests/headless/malformed-payload.sh`
- [X] T009 [P] [US1] Add inert-dispatch versus intentionally effect-free regression coverage in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`, `clients/python/tests/behavioral_coverage/test_itertesting_report.py`, and `tests/headless/test_live_itertesting_hardening.sh`

### Implementation for User Story 1

- [X] T010 [US1] Preserve normalized batch targets through engine-thread drain in `src/circuit/module/GrpcGatewayModule.cpp`, `src/circuit/grpc/CommandDispatch.h`, and `src/circuit/grpc/CommandDispatch.cpp`
- [X] T011 [US1] Complete malformed-batch rejection and validation-gap surfacing in `src/circuit/grpc/CommandValidator.h`, `src/circuit/grpc/CommandValidator.cpp`, and `src/circuit/grpc/HighBarService.cpp`
- [X] T012 [US1] Classify `inert_dispatch` and intentionally effect-free outcomes consistently in `src/circuit/grpc/CommandDispatch.cpp`, `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`, and `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T013 [US1] Render live blocker separation and expected signals in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py` and `tests/headless/test_command_contract_hardening.sh`

**Checkpoint**: User Story 1 is complete when maintainers can prove target preservation, malformed-payload rejection, and live inert-dispatch handling without relying on ad hoc commands.

---

## Phase 4: User Story 2 - Reproduce And Gate Remaining Blockers (Priority: P2)

**Goal**: Make every foundational blocker rerunnable when deterministic, and stop the workflow clearly when only pattern review is possible.

**Independent Test**: Run the Python and headless regression suite for deterministic repro routing, `needs_pattern_review` fallback handling, and blocked-versus-ready wrapper output, and confirm each outcome exposes the correct rerun path or stop state.

### Tests for User Story 2

- [X] T014 [P] [US2] Add deterministic repro routing coverage in `clients/python/tests/behavioral_coverage/test_live_row_repro.py` and `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`
- [X] T015 [P] [US2] Add `needs_pattern_review` gate coverage in `clients/python/tests/behavioral_coverage/test_itertesting_report.py`, `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`, and `tests/headless/test_command_contract_hardening.sh`
- [X] T016 [P] [US2] Add blocked-versus-ready wrapper coverage in `tests/headless/itertesting.sh` and `tests/headless/test_command_contract_hardening.sh`

### Implementation for User Story 2

- [X] T017 [US2] Map each foundational issue class to a focused repro entrypoint in `clients/python/highbar_client/behavioral_coverage/audit_runner.py`, `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`, and `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T018 [US2] Emit explicit `needs_pattern_review` fallback records in `clients/python/highbar_client/behavioral_coverage/audit_runner.py`, `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`, and `clients/python/highbar_client/behavioral_coverage/audit_report.py`
- [X] T019 [US2] Print blocked-versus-ready wrapper outcomes with linked repro context in `tests/headless/itertesting.sh`, `tests/headless/test_command_contract_hardening.sh`, and `tests/headless/README.md`

**Checkpoint**: User Story 2 is complete when every blocker either links to a focused rerun command or stops the workflow with an explicit pattern-review requirement.

---

## Phase 5: User Story 3 - Make Final Validation Runnable From Standard Entry Points (Priority: P3)

**Goal**: Expose the remaining BARb validation from root `ctest`, record validator overhead with a budget verdict, and document the no-skip completion suite.

**Independent Test**: Run filtered root `ctest` for the BARb targets, run the validator-overhead measurement, and verify the documented completion entrypoints and no-skip rules from the standard commands.

### Tests for User Story 3

- [X] T020 [P] [US3] Add root-build discovery assertions for BARb contract targets in `tests/headless/test_command_contract_hardening.sh` and `tests/headless/test_live_itertesting_hardening.sh`
- [X] T021 [P] [US3] Add validator-overhead regression coverage and artifact checks in `tests/unit/command_validation_perf_test.cc` and `tests/bench/bench_latency.py`
- [X] T022 [P] [US3] Add no-skip completion-suite smoke coverage in `tests/headless/test_command_contract_hardening.sh` and `tests/headless/itertesting.sh`

### Implementation for User Story 3

- [X] T023 [US3] Expose `command_validation_test`, `ai_move_flow_test`, and `command_validation_perf_test` from root `ctest` in `CMakeLists.txt`
- [X] T024 [US3] Implement validator-overhead measurement and machine-readable record emission in `tests/unit/command_validation_perf_test.cc` and `build/reports/command-validation/validator-overhead.json`
- [X] T025 [US3] Record absolute and baseline-relative validator budget verdicts in `tests/unit/command_validation_perf_test.cc` and `tests/bench/bench_latency.py`
- [X] T026 [US3] Document the standard entrypoints and no-skip completion rules in `specs/011-contract-hardening-completion/quickstart.md`, `tests/headless/README.md`, `specs/011-contract-hardening-completion/contracts/root-ctest-discovery.md`, and `specs/011-contract-hardening-completion/contracts/validator-performance-record.md`

**Checkpoint**: User Story 3 is complete when maintainers can discover, run, and assess the finished validation set from the documented standard entry points.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Reconcile the final artifacts and rerun the documented suite to green.

- [X] T027 [P] Reconcile completion contracts and entity definitions in `specs/011-contract-hardening-completion/data-model.md`, `specs/011-contract-hardening-completion/contracts/validation-suite.md`, `specs/011-contract-hardening-completion/contracts/contract-gate-matrix.md`, `specs/011-contract-hardening-completion/contracts/foundational-repro-entrypoints.md`, `specs/011-contract-hardening-completion/contracts/root-ctest-discovery.md`, and `specs/011-contract-hardening-completion/contracts/validator-performance-record.md`
- [ ] T028 Run the focused C++ and Python completion checks from `specs/011-contract-hardening-completion/quickstart.md`
- [ ] T029 Run the headless completion suite and capture validator artifacts in `tests/headless/test_command_contract_hardening.sh`, `tests/headless/test_live_itertesting_hardening.sh`, `tests/headless/malformed-payload.sh`, `tests/headless/itertesting.sh`, and `build/reports/command-validation/validator-overhead.json`
- [ ] T030 Resolve any completion-suite failures uncovered by `T028` and `T029` in `src/circuit/grpc/CommandValidator.cpp`, `src/circuit/grpc/CommandDispatch.cpp`, `src/circuit/module/GrpcGatewayModule.cpp`, `clients/python/highbar_client/behavioral_coverage/audit_runner.py`, `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`, `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`, `tests/headless/test_command_contract_hardening.sh`, and `tests/headless/itertesting.sh`
- [ ] T031 Re-run the full completion suite after `T030` using `specs/011-contract-hardening-completion/quickstart.md`, `tests/headless/test_command_contract_hardening.sh`, `tests/headless/test_live_itertesting_hardening.sh`, `tests/headless/malformed-payload.sh`, `tests/headless/itertesting.sh`, and `build/reports/command-validation/validator-overhead.json`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies; start immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1 and blocks all user stories.
- **Phase 3 (US1)**: Depends on Phase 2.
- **Phase 4 (US2)**: Depends on Phase 2 and on US1 surfacing stable foundational issue records.
- **Phase 5 (US3)**: Depends on Phase 2 and on the completion-suite command surfaces from US1 so the documented standard entry points exercise the finished contract-validation flows.
- **Phase 6 (Polish)**: Depends on the user stories selected for delivery and ends with a full rerun to green after any fixes.

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on other user stories once foundational plumbing is complete.
- **User Story 2 (P2)**: Depends on US1 because repro routing attaches to the foundational blocker classes that US1 finishes validating.
- **User Story 3 (P3)**: Depends on Phase 2 and on the completion-suite command surfaces from US1; root `ctest` discovery and perf recording remain independently testable once those entrypoints exist.

### Within Each User Story

- Write the listed tests first and confirm they fail before implementation.
- Finish shared models or helper updates before report, wrapper, or docs work that consumes them.
- Run each story’s independent test before moving to the next story.

### Parallel Opportunities

- `T002` and `T003` can run in parallel after `T001`.
- `T005` and `T006` can run in parallel after `T004`.
- `T007`, `T008`, and `T009` can run in parallel for US1.
- `T014`, `T015`, and `T016` can run in parallel for US2.
- `T020`, `T021`, and `T022` can run in parallel for US3.
- `T027` can run alongside the first validation pass in `T028`.
- `T031` runs after `T030` and serves as the final rerun-to-green gate.

---

## Parallel Example: User Story 1

```bash
Task: "Add authoritative-target drain coverage in tests/integration/ai_move_flow_test.cc"
Task: "Add validator and malformed-payload regression coverage in tests/unit/command_validation_test.cc and tests/headless/malformed-payload.sh"
Task: "Add inert-dispatch versus intentionally effect-free regression coverage in clients/python/tests/behavioral_coverage/test_live_failure_classification.py, clients/python/tests/behavioral_coverage/test_itertesting_report.py, and tests/headless/test_live_itertesting_hardening.sh"
```

---

## Parallel Example: User Story 2

```bash
Task: "Add deterministic repro routing coverage in clients/python/tests/behavioral_coverage/test_live_row_repro.py and clients/python/tests/behavioral_coverage/test_itertesting_runner.py"
Task: "Add needs_pattern_review gate coverage in clients/python/tests/behavioral_coverage/test_itertesting_report.py, clients/python/tests/behavioral_coverage/test_itertesting_runner.py, and tests/headless/test_command_contract_hardening.sh"
Task: "Add blocked-versus-ready wrapper coverage in tests/headless/itertesting.sh and tests/headless/test_command_contract_hardening.sh"
```

---

## Parallel Example: User Story 3

```bash
Task: "Add root-build discovery assertions for BARb contract targets in tests/headless/test_command_contract_hardening.sh and tests/headless/test_live_itertesting_hardening.sh"
Task: "Add validator-overhead regression coverage and artifact checks in tests/unit/command_validation_perf_test.cc and tests/bench/bench_latency.py"
Task: "Add no-skip completion-suite smoke coverage in tests/headless/test_command_contract_hardening.sh and tests/headless/itertesting.sh"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1).
3. Run the US1 integration, unit, Python, and headless checks.
4. Stop and confirm maintainers can validate the remaining contract behaviors from standard repo-local entry points.

### Incremental Delivery

1. Finish Setup and Foundational work.
2. Deliver US1 to complete the missing validation coverage.
3. Deliver US2 to make blocker repros and gate behavior actionable.
4. Deliver US3 to standardize root `ctest`, perf recording, and no-skip completion commands.
5. Finish with Phase 6 failure resolution and rerun-to-green validation.

### Parallel Team Strategy

1. One developer completes Phase 1 and Phase 2.
2. After the foundation is ready:
   - Developer A: US1 C++ validation and live blocker separation.
   - Developer B: US2 repro routing and wrapper/report gate behavior.
   - Developer C: US3 root `ctest`, perf measurement, and completion docs.
3. Rejoin for Phase 6 validation reruns, failure fixes, and the final rerun-to-green pass.

---

## Notes

- Every task uses the required checklist format with a task ID, optional `[P]`, optional story label, and explicit file paths.
- Setup, foundational, and polish tasks intentionally omit story labels.
- The suggested MVP scope is **User Story 1** because the feature is not meaningfully complete until the missing validation coverage is runnable.
