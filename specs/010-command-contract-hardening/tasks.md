# Tasks: Command Contract Hardening

**Input**: Design documents from `/specs/010-command-contract-hardening/`  
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Include C++ unit/integration, Python pytest, and headless validation tasks because the feature spec defines independent test criteria for each user story.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this belongs to (`[US1]`, `[US2]`, `[US3]`)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the gateway and Itertesting surfaces for command-contract hardening work

- [X] T001 Add command-contract hardening scaffolding in `src/circuit/grpc/CommandValidator.h`, `src/circuit/grpc/CommandValidator.cpp`, and `src/circuit/module/GrpcGatewayModule.cpp`
- [X] T002 [P] Add contract-health workflow scaffolding in `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`, `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`, `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`, and `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [X] T003 [P] Add contract-hardening regression harness scaffolding in `tests/unit/command_validation_test.cc`, `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`, `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`, `clients/python/tests/behavioral_coverage/test_itertesting_report.py`, and `tests/headless/test_command_contract_hardening.sh`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core contract-health models and transport plumbing that MUST exist before any user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Define `CommandContractIssue`, `DeterministicRepro`, `ContractHealthDecision`, and `ImprovementEligibility` in `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`
- [X] T005 [P] Implement foundational issue normalization and repro-selection helpers in `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py` and `clients/python/highbar_client/behavioral_coverage/audit_runner.py`
- [X] T006 [P] Add manifest and report serialization hooks for contract-health data in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [X] T007 [P] Introduce authoritative batch-target metadata plumbing in `src/circuit/grpc/CommandQueue.h`, `src/circuit/grpc/CoordinatorClient.cpp`, and `src/circuit/module/GrpcGatewayModule.cpp`
- [X] T008 [P] Add foundational regression coverage for contract-health models and queue metadata in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`, `clients/python/tests/behavioral_coverage/test_itertesting_report.py`, and `tests/unit/command_queue_test.cc`

**Checkpoint**: Foundation ready - gateway normalization and Itertesting contract-health records are available to all user stories

---

## Phase 3: User Story 1 - Surface Foundational Contract Blockers (Priority: P1) 🎯 MVP

**Goal**: Separate target drift, validation gaps, and inert dispatch defects from ordinary Itertesting failures so maintainers fix foundational blockers first.

**Independent Test**: Run a campaign containing known target-drift, shallow-validation, and inert-dispatch defects and confirm the workflow reports them as foundational blockers instead of normal retry or evidence failures.

### Tests for User Story 1

- [X] T009 [P] [US1] Add target-drift and shallow-validation rejection tests in `tests/unit/command_validation_test.cc`
- [ ] T010 [P] [US1] Add integration coverage for authoritative batch targeting and non-no-op dispatch behavior in `tests/integration/ai_move_flow_test.cc`
- [X] T011 [P] [US1] Add foundational-classification and blocker-report tests in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py` and `clients/python/tests/behavioral_coverage/test_itertesting_report.py`
- [X] T012 [P] [US1] Add end-to-end blocker separation coverage in `tests/headless/test_command_contract_hardening.sh`
- [X] T013 [P] [US1] Add regression coverage for intentionally effect-free commands in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`

### Implementation for User Story 1

- [X] T014 [US1] Enforce single-target batch drift rejection and deeper semantic validation in `src/circuit/grpc/CommandValidator.h` and `src/circuit/grpc/CommandValidator.cpp`
- [ ] T015 [US1] Preserve normalized authoritative targets during engine-thread drain in `src/circuit/module/GrpcGatewayModule.cpp` and `src/circuit/grpc/CommandDispatch.h`
- [ ] T016 [US1] Detect inert dispatcher and validation-gap outcomes in `src/circuit/grpc/CommandDispatch.cpp`, `src/circuit/module/GrpcGatewayModule.cpp`, and `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [ ] T017 [US1] Define explicit exemptions for intentionally effect-free commands while classifying `target_drift`, `validation_gap`, and `inert_dispatch` in `src/circuit/grpc/CommandDispatch.cpp`, `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`, and `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T018 [US1] Render dedicated foundational blocker sections with maintainer-facing explanations in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`

**Checkpoint**: User Story 1 should make foundational contract defects explicit before maintainers spend time on ordinary Itertesting tuning

---

## Phase 4: User Story 2 - Produce Deterministic Repros For Contract Defects (Priority: P2)

**Goal**: Link every foundational contract issue to a focused, independently runnable repro path so maintainers can confirm and fix defects quickly.

**Independent Test**: For each foundational issue class, generate a targeted repro and verify the repro can be rerun independently from the broader campaign workflow.

### Tests for User Story 2

- [ ] T019 [P] [US2] Add deterministic repro routing tests in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py` and `clients/python/tests/behavioral_coverage/test_live_row_repro.py`
- [X] T020 [P] [US2] Add no-repro fallback tests for newly observed foundational patterns in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py` and `clients/python/tests/behavioral_coverage/test_itertesting_report.py`
- [ ] T021 [P] [US2] Add focused validator and dispatch repro coverage in `tests/unit/command_validation_test.cc`, `tests/integration/ai_move_flow_test.cc`, and `tests/headless/test_command_contract_hardening.sh`

### Implementation for User Story 2

- [X] T022 [US2] Map foundational issue classes to independently runnable repro records in `clients/python/highbar_client/behavioral_coverage/audit_runner.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T023 [US2] Emit `needs_pattern_review` fallback records when no deterministic repro can be generated in `clients/python/highbar_client/behavioral_coverage/audit_runner.py`, `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`, and `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`
- [ ] T024 [US2] Add deterministic validator and dispatch repro entrypoints in `tests/unit/command_validation_test.cc`, `tests/integration/ai_move_flow_test.cc`, and `tests/headless/test_command_contract_hardening.sh`
- [X] T025 [US2] Attach repro commands, expected signals, artifact paths, and fallback status to manifest output in `clients/python/highbar_client/behavioral_coverage/itertesting_types.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [ ] T026 [US2] Surface per-issue repro instructions and pattern-review fallbacks in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py` and `clients/python/highbar_client/behavioral_coverage/audit_report.py`

**Checkpoint**: User Story 2 should let maintainers jump from a foundational issue directly into a small deterministic repro

---

## Phase 5: User Story 3 - Gate Itertesting Behind Contract Health (Priority: P3)

**Goal**: Allow normal Itertesting improvement output only when foundational contract blockers are absent, while preserving secondary findings for context.

**Independent Test**: Run one campaign with unresolved foundational blockers and one without blockers, then verify the first stops with a contract-health decision and the second proceeds with normal improvement guidance.

### Tests for User Story 3

- [X] T027 [P] [US3] Add contract-health decision and guidance-withholding tests in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py` and `clients/python/tests/behavioral_coverage/test_itertesting_report.py`
- [ ] T028 [P] [US3] Add blocked-vs-ready campaign wrapper coverage in `tests/headless/test_command_contract_hardening.sh` and `tests/headless/itertesting.sh`
- [ ] T029 [P] [US3] Add no-repro gate coverage for pattern-review blocker states in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`, `clients/python/tests/behavioral_coverage/test_itertesting_report.py`, and `tests/headless/test_command_contract_hardening.sh`

### Implementation for User Story 3

- [X] T030 [US3] Implement run-level `ContractHealthDecision` and `ImprovementEligibility` evaluation in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_campaign.py`
- [X] T031 [US3] Persist blocking issue visibility across runs and mark later resolutions in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`
- [X] T032 [US3] Withhold ordinary improvement actions while preserving secondary findings in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py` and `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`
- [X] T033 [US3] Gate normal improvement output when foundational issues fall back to pattern review without a deterministic repro in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [X] T034 [US3] Teach the headless Itertesting wrapper to stop on blocked contract health and print linked artifacts in `tests/headless/itertesting.sh` and `tests/headless/test_command_contract_hardening.sh`

**Checkpoint**: User Story 3 should keep Itertesting in improvement mode only when command semantics are coherent enough for those recommendations to matter

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final documentation, contract alignment, and regression validation across all stories

- [X] T035 [P] Update maintainer workflow docs in `specs/010-command-contract-hardening/quickstart.md` and `tests/headless/README.md`
- [X] T036 [P] Align implemented issue classes, gate states, repro fields, and pattern-review fallback behavior in `specs/010-command-contract-hardening/contracts/contract-health-decision.md`, `specs/010-command-contract-hardening/contracts/deterministic-repro.md`, `specs/010-command-contract-hardening/contracts/foundational-issue-classification.md`, and `specs/010-command-contract-hardening/data-model.md`
- [ ] T037 Run targeted regression suites for `tests/unit/command_validation_test.cc`, `tests/integration/ai_move_flow_test.cc`, `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`, `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`, and `clients/python/tests/behavioral_coverage/test_itertesting_report.py`
- [ ] T038 Run end-to-end contract-hardening validation in `tests/headless/test_command_contract_hardening.sh`, `tests/headless/malformed-payload.sh`, and `tests/headless/itertesting.sh`
- [ ] T039 Run the transport latency benchmark or existing microbench for gateway hot-path changes and record results against the constitution budget in `build/reports/` and `specs/010-command-contract-hardening/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies, can begin immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1 and blocks all user stories.
- **Phase 3 (US1)**: Depends on Phase 2.
- **Phase 4 (US2)**: Depends on Phase 2 and on US1 foundational issue emission so repro routing has stable blocker records to attach to.
- **Phase 5 (US3)**: Depends on Phase 2 and on US1 blocker classification; it benefits from US2 repro links but can begin once contract-health records are stable.
- **Phase 6 (Polish)**: Depends on completion of the selected user stories.

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on other user stories once the foundational transport and reporting hooks exist.
- **User Story 2 (P2)**: Depends on US1 because deterministic repros must attach to already-classified foundational issues.
- **User Story 3 (P3)**: Depends on US1 because the gate needs authoritative blocker classification; it benefits from US2 repro links for maintainer stop output.

### Within Each User Story

- Write the listed tests first and confirm they fail before implementation.
- Update shared C++ and Python models before orchestration or report code that consumes them.
- Preserve authoritative target handling before adding downstream issue classification that depends on it.
- Run story-specific headless validation before moving to the next priority.

### Parallel Opportunities

- `T002` and `T003` can run in parallel after `T001`.
- `T005`, `T006`, `T007`, and `T008` can run in parallel after `T004`.
- `T009`, `T010`, `T011`, `T012`, and `T013` can run in parallel for US1.
- `T019`, `T020`, and `T021` can run in parallel for US2.
- `T027`, `T028`, and `T029` can run in parallel for US3.
- `T035` and `T036` can run in parallel during polish.

---

## Parallel Example: User Story 1

```bash
Task: "Add target-drift and shallow-validation rejection tests in tests/unit/command_validation_test.cc"
Task: "Add integration coverage for authoritative batch targeting and non-no-op dispatch behavior in tests/integration/ai_move_flow_test.cc"
Task: "Add foundational-classification and blocker-report tests in clients/python/tests/behavioral_coverage/test_live_failure_classification.py and clients/python/tests/behavioral_coverage/test_itertesting_report.py"
Task: "Add end-to-end blocker separation coverage in tests/headless/test_command_contract_hardening.sh and tests/headless/malformed-payload.sh"
Task: "Add regression coverage for intentionally effect-free commands in clients/python/tests/behavioral_coverage/test_live_failure_classification.py and tests/unit/command_validation_test.cc"
```

---

## Parallel Example: User Story 2

```bash
Task: "Add deterministic repro routing tests in clients/python/tests/behavioral_coverage/test_itertesting_runner.py and clients/python/tests/behavioral_coverage/test_live_row_repro.py"
Task: "Add no-repro fallback tests for newly observed foundational patterns in clients/python/tests/behavioral_coverage/test_itertesting_runner.py and clients/python/tests/behavioral_coverage/test_itertesting_report.py"
Task: "Add focused validator and dispatch repro coverage in tests/unit/command_validation_test.cc, tests/integration/ai_move_flow_test.cc, and tests/headless/test_command_contract_hardening.sh"
```

---

## Parallel Example: User Story 3

```bash
Task: "Add contract-health decision and guidance-withholding tests in clients/python/tests/behavioral_coverage/test_itertesting_runner.py and clients/python/tests/behavioral_coverage/test_itertesting_report.py"
Task: "Add blocked-vs-ready campaign wrapper coverage in tests/headless/test_command_contract_hardening.sh and tests/headless/itertesting.sh"
Task: "Add no-repro gate coverage for pattern-review blocker states in clients/python/tests/behavioral_coverage/test_itertesting_runner.py, clients/python/tests/behavioral_coverage/test_itertesting_report.py, and tests/headless/test_command_contract_hardening.sh"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Implement Phase 3 (US1) only.
3. Validate US1 with unit, integration, and headless coverage for target drift, shallow validation, inert dispatch, and intentionally effect-free command exemptions.
4. Stop and confirm maintainers now see foundational defects before ordinary Itertesting guidance.

### Incremental Delivery

1. Ship US1 to make foundational command-contract defects explicit.
2. Ship US2 to attach deterministic repros to every foundational issue.
3. Ship US3 to gate improvement-driven Itertesting behind contract health.
4. Finish with Phase 6 validation and documentation updates.

### Parallel Team Strategy

1. One developer completes Phase 1 and Phase 2.
2. After the foundation is ready:
   - Developer A: US1 validator, dispatch, and foundational blocker reporting.
   - Developer B: US2 deterministic repro plumbing and focused repro entrypoints.
   - Developer C: US3 contract-health gate, report withholding, and wrapper behavior.
3. Rejoin for polish, regression runs, and quickstart validation.

---

## Notes

- All tasks use the required checklist format with task ID, optional `[P]`, optional story label, and explicit file paths.
- Setup, foundational, and polish tasks intentionally omit story labels.
- The suggested MVP scope is **User Story 1** because blocker classification has to exist before repro routing or contract-health gating becomes actionable.
