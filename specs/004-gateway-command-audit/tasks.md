# Tasks: Gateway Command Audit

**Input**: Design documents from `/specs/004-gateway-command-audit/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: This feature is validated through checked-in headless audit harnesses and reproduced evidence artifacts, so test/harness tasks are included for each user story.

**Organization**: Tasks are grouped by user story so each deliverable can be implemented and validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (`[US1]`, `[US2]`, `[US3]`, `[US4]`)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the repo scaffolding and checked-in harness entry points required by all audit work.

- [X] T001 Create the tracked audit documentation scaffold in `audit/README.md`, `audit/command-audit.md`, `audit/hypothesis-plan.md`, and `audit/v2-v3-ledger.md`
- [X] T002 Create the shared headless audit script directory with an index in `tests/headless/audit/README.md`
- [X] T003 [P] Add the cheats-enabled match variant in `tests/headless/scripts/cheats.startscript`
- [X] T004 [P] Add ignore rules for generated 004 audit artifacts in `.gitignore`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the shared Python metadata, inventory, and reporting layers that every story depends on.

**⚠️ CRITICAL**: No user story work should begin until this phase is complete.

- [X] T005 Extend shared audit enums and row dataclasses in `clients/python/highbar_client/behavioral_coverage/types.py`
- [X] T006 [P] Add command/RPC inventory extraction and citation mapping in `clients/python/highbar_client/behavioral_coverage/audit_inventory.py`
- [X] T007 [P] Add audit markdown rendering and contract validation in `clients/python/highbar_client/behavioral_coverage/audit_report.py`
- [X] T008 [P] Add hypothesis-class definitions and ranking helpers in `clients/python/highbar_client/behavioral_coverage/hypotheses.py`
- [X] T009 Add audit subcommands and artifact wiring in `clients/python/highbar_client/behavioral_coverage/__main__.py`

**Checkpoint**: Shared audit generation infrastructure exists and user-story implementation can proceed.

---

## Phase 3: User Story 1 - Audit Table Covering All Commands and RPCs (Priority: P1) 🎯 MVP

**Goal**: Produce one authoritative audit table with one row per AICommand arm and one row per service RPC, each backed by reproducible evidence or a falsifiable blocker hypothesis.

**Independent Test**: A reviewer can pick any `verified` row in `audit/command-audit.md`, run `tests/headless/audit/repro.sh <row-id>`, and reproduce the cited evidence against a fresh headless engine run.

### Tests for User Story 1

- [X] T010 [P] [US1] Add single-row reproduction harness in `tests/headless/audit/repro.sh`
- [X] T011 [P] [US1] Add per-row bootstrap and recipe selection in `clients/python/highbar_client/behavioral_coverage/audit_runner.py`
- [X] T012 [P] [US1] Add runtime def-id resolution helper for reproducible build/unit recipes in `tests/headless/audit/def-id-resolver.py`
- [X] T013 [P] [US1] Add duplicate-AI lockout, token-file cold-start, and Save/Load RPC repro assertions in `tests/headless/audit/repro.sh`

### Implementation for User Story 1

- [X] T014 [P] [US1] Extend `clients/python/highbar_client/behavioral_coverage/registry.py` with audit-specific channel and observability metadata for all 66 AICommand arms
- [X] T015 [P] [US1] Add RPC coverage metadata and dispatcher citations in `clients/python/highbar_client/behavioral_coverage/audit_inventory.py`
- [X] T016 [US1] Implement evidence collection, row classification, and edge-case handling for cheats, cross-team def rejection, sampler races, and gametype drift in `clients/python/highbar_client/behavioral_coverage/audit_runner.py`
- [X] T017 [US1] Emit and validate per-row reproduction recipes with explicit Phase-1 and Phase-2 labeling in `audit/command-audit.md`
- [X] T018 [US1] Generate the full audit table in `audit/command-audit.md`
- [X] T019 [US1] Add reviewer-facing reproduction guidance in `audit/README.md`

**Checkpoint**: `audit/command-audit.md` contains 74 rows with reproducible evidence paths and valid outcome buckets.

---

## Phase 4: User Story 2 - Hypothesis-Driven Test Plan for Unverified Arms (Priority: P1)

**Goal**: Turn every blocked, broken, or Phase-1-fragile arm into a ranked hypothesis entry with a concrete distinguishing test.

**Independent Test**: A maintainer can pick any entry in `audit/hypothesis-plan.md`, run `tests/headless/audit/hypothesis.sh <arm> <hypothesis-class>`, and get a binary confirmed/falsified result matching the predicted evidence shape.

### Tests for User Story 2

- [X] T020 [P] [US2] Add the hypothesis test harness in `tests/headless/audit/hypothesis.sh`
- [X] T021 [P] [US2] Add reproducibility drift runner in `tests/headless/audit/repro-stability.sh`

### Implementation for User Story 2

- [X] T022 [P] [US2] Implement per-class hypothesis execution flows in `clients/python/highbar_client/behavioral_coverage/audit_runner.py`
- [X] T023 [P] [US2] Add ranked hypothesis candidate generation in `clients/python/highbar_client/behavioral_coverage/hypotheses.py`
- [X] T024 [US2] Generate the hypothesis companion artifact in `audit/hypothesis-plan.md`
- [X] T025 [US2] Backfill `blocked` and `broken` rows in `audit/command-audit.md` with falsification links generated from `audit/hypothesis-plan.md`
- [X] T026 [US2] Record non-determinism notes and stability summaries in `audit/command-audit.md`

**Checkpoint**: Every unverified or Phase-1-fragile arm has a ranked hypothesis entry and a runnable distinguishing command.

---

## Phase 5: User Story 3 - V2-vs-V3 Problem Ledger (Priority: P2)

**Goal**: Produce a cross-linked ledger that ties each documented V2 pathology to its V3 fix or open finding, backed by source citations and runtime audit evidence.

**Independent Test**: A reviewer can open `audit/v2-v3-ledger.md`, verify the cited V2 and V3 source locations, then reproduce the referenced V3 audit row from `audit/command-audit.md`.

### Tests for User Story 3

- [X] T027 [P] [US3] Validate that every named V2 pathology from `specs/004-gateway-command-audit/spec.md` appears in `audit/v2-v3-ledger.md`

### Implementation for User Story 3

- [X] T028 [P] [US3] Add V2 pathology inventory and V3 runtime evidence cross-linking in `clients/python/highbar_client/behavioral_coverage/audit_inventory.py`
- [X] T029 [P] [US3] Add ledger markdown emission and validation in `clients/python/highbar_client/behavioral_coverage/audit_report.py`
- [X] T030 [US3] Capture the required V2 pathology excerpts and source ranges in `audit/v2-v3-ledger.md`
- [X] T031 [US3] Generate the completed comparison ledger in `audit/v2-v3-ledger.md`
- [X] T032 [US3] Add row-to-row backlinks between `audit/v2-v3-ledger.md` and `audit/command-audit.md`

**Checkpoint**: Every required V2 pathology is represented with a V3 citation and either a verified audit-row proof or an explicit open follow-up.

---

## Phase 6: User Story 4 - Phase-2 Dispatcher-Only Smoke Run (Priority: P3)

**Goal**: Re-run the macro chain with `enable_builtin=false` to determine whether Phase-1 ambient AI is masking dispatcher correctness.

**Independent Test**: A maintainer runs `tests/headless/audit/phase2-macro-chain.sh` and gets a per-step PASS/FAIL report that can be cited directly from the audit artifacts.

### Tests for User Story 4

- [X] T033 [P] [US4] Add the dispatcher-only smoke harness in `tests/headless/audit/phase2-macro-chain.sh`
- [X] T034 [P] [US4] Add Phase-2 launch toggles for the audit harness in `tests/headless/_launch.sh` and `tests/headless/phase2-smoke.sh`

### Implementation for User Story 4

- [X] T035 [P] [US4] Add the macro-chain scenario runner in `clients/python/highbar_client/behavioral_coverage/audit_runner.py`
- [X] T036 [US4] Generate the Phase-2 smoke report in `build/reports/004-phase2-smoke.md`
- [X] T037 [US4] Update `audit/command-audit.md` with Phase-2 attribution evidence for `phase1_reissuance` rows

**Checkpoint**: The audit can distinguish Phase-1 ambient-AI interference from genuine dispatcher defects using a checked-in Phase-2 smoke run.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, orchestration, and documentation cleanup across all stories.

- [X] T038 [P] Add an end-to-end audit orchestration wrapper in `tests/headless/audit/run-all.sh`
- [X] T039 [P] Add final artifact count and contract checks in `clients/python/highbar_client/behavioral_coverage/audit_report.py`
- [X] T040 Update reviewer instructions and example commands in `specs/004-gateway-command-audit/quickstart.md`
- [X] T041 Run the quickstart validation flow and record the final generated evidence references in `audit/README.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion; blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion; defines the MVP artifact.
- **User Story 2 (Phase 4)**: Depends on User Story 1's row inventory and evidence model.
- **User Story 3 (Phase 5)**: Depends on User Story 1's finalized audit rows and citations.
- **User Story 4 (Phase 6)**: Depends on Foundational completion and reuses User Story 1/2 harness infrastructure.
- **Polish (Phase 7)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Starts after Phase 2; no dependency on other user stories.
- **US2 (P1)**: Starts after US1 establishes row IDs, recipes, and outcome buckets.
- **US3 (P2)**: Starts after US1 establishes the runtime evidence rows it references.
- **US4 (P3)**: Starts after Phase 2; its output feeds back into US2/US1 row classification notes.

### Within Each User Story

- Harness/test tasks precede artifact generation.
- Metadata and inventory tasks precede markdown emission.
- Markdown emission precedes cross-linking and final documentation cleanup.
- Phase-2 attribution evidence must exist before final `phase1_reissuance` notes are closed.

### Parallel Opportunities

- T003 and T004 can run in parallel during Setup.
- T006, T007, and T008 can run in parallel once T005 defines shared audit types.
- T010, T011, T012, and T013 can run in parallel for US1.
- T020 and T021 can run in parallel for US2.
- T028 and T029 can run in parallel for US3.
- T033, T034, and T035 can run in parallel for US4 after the foundational audit runner exists.
- T038 and T039 can run in parallel during Polish.

---

## Parallel Example: User Story 1

```bash
# Build the US1 harness pieces together:
Task: "Add single-row reproduction harness in tests/headless/audit/repro.sh"
Task: "Add per-row bootstrap and recipe selection in clients/python/highbar_client/behavioral_coverage/audit_runner.py"
Task: "Add runtime def-id resolution helper for reproducible build/unit recipes in tests/headless/audit/def-id-resolver.py"

# Build the inventory metadata together:
Task: "Extend clients/python/highbar_client/behavioral_coverage/registry.py with audit-specific channel and observability metadata for all 66 AICommand arms"
Task: "Add RPC coverage metadata and dispatcher citations in clients/python/highbar_client/behavioral_coverage/audit_inventory.py"
```

---

## Parallel Example: User Story 2

```bash
# Run the reproducibility and hypothesis harness work together:
Task: "Add the hypothesis test harness in tests/headless/audit/hypothesis.sh"
Task: "Add reproducibility drift runner in tests/headless/audit/repro-stability.sh"

# Generate hypothesis metadata in parallel:
Task: "Implement per-class hypothesis execution flows in clients/python/highbar_client/behavioral_coverage/audit_runner.py"
Task: "Add ranked hypothesis candidate generation in clients/python/highbar_client/behavioral_coverage/hypotheses.py"
```

---

## Parallel Example: User Story 4

```bash
# Build the Phase-2 smoke infrastructure together:
Task: "Add the dispatcher-only smoke harness in tests/headless/audit/phase2-macro-chain.sh"
Task: "Add Phase-2 launch toggles for the audit harness in tests/headless/_launch.sh and tests/headless/phase2-smoke.sh"
Task: "Add the macro-chain scenario runner in clients/python/highbar_client/behavioral_coverage/audit_runner.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational audit metadata and generators.
3. Complete Phase 3: User Story 1 audit table and reproduction harness.
4. Validate that `audit/command-audit.md` contains all 74 rows and that at least one `verified` row reproduces end-to-end.

### Incremental Delivery

1. Ship US1 to establish the canonical audit table.
2. Add US2 to turn unverified rows into ranked, testable hypotheses.
3. Add US3 to close the V2-versus-V3 evidence loop using the US1 artifacts.
4. Add US4 to resolve the Phase-1-versus-Phase-2 attribution question for fragile arms.
5. Finish with Polish to provide one-command orchestration and final contract validation.
