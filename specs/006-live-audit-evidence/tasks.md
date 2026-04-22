# Tasks: Live Audit Evidence Refresh

**Input**: Design documents from `/specs/006-live-audit-evidence/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Include test and validation tasks because `spec.md` defines mandatory user-scenario testing and `quickstart.md` requires runnable refresh, repro, hypothesis, drift, and Phase-2 validation flows.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g. `US1`, `US2`, `US3`)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Align feature docs and repo-local entry points with the live-refresh implementation target

- [X] T001 Update feature workflow notes in tests/headless/audit/README.md for manifest-backed live refresh commands
- [X] T002 Update reviewer-facing refresh guidance in audit/README.md to describe live-run evidence instead of seeded 004 synthesis

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core manifest, freshness, and rendering infrastructure required before any user story can be completed

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 Define live refresh dataclasses and freshness enums in clients/python/highbar_client/behavioral_coverage/types.py
- [X] T003a Define canonical outcome-bucket and freshness-state vocabularies in clients/python/highbar_client/behavioral_coverage/types.py
- [X] T004 [P] Add manifest/report path helpers and run-id utilities in clients/python/highbar_client/behavioral_coverage/audit_inventory.py
- [X] T005 [P] Implement manifest serialization and latest-run selection helpers in clients/python/highbar_client/behavioral_coverage/audit_runner.py
- [X] T006 Extend clients/python/highbar_client/behavioral_coverage/audit_report.py to render artifacts from persisted manifest data instead of seed-only rows
- [X] T007 Add CLI plumbing in clients/python/highbar_client/behavioral_coverage/__main__.py and clients/python/highbar_client/behavioral_coverage/__init__.py for full refresh, row repro, hypothesis, and drift subcommands

**Checkpoint**: Manifest-backed refresh pipeline exists and user story work can build on stable shared contracts

---

## Phase 3: User Story 1 - Refresh Audit From Live Topology (Priority: P1) 🎯 MVP

**Goal**: Run the 004 audit workflow against the real headless topology and regenerate all three checked-in deliverables from the latest completed live run

**Independent Test**: Run `tests/headless/audit/run-all.sh` on the reference host and verify that `build/reports/` contains a completed manifest plus refreshed `audit/command-audit.md`, `audit/hypothesis-plan.md`, and `audit/v2-v3-ledger.md` sourced only from that run

### Tests for User Story 1

- [X] T008 [P] [US1] Add manifest contract coverage in clients/python/tests/behavioral_coverage/test_live_audit_manifest.py
- [X] T009 [P] [US1] Add artifact rendering coverage for freshness markers in clients/python/tests/behavioral_coverage/test_audit_report_live_refresh.py
- [X] T010 [US1] Add shell-level live refresh smoke coverage for tests/headless/audit/run-all.sh in tests/headless/audit/test_run_all.sh
- [X] T010a [US1] Add shell stdout summary coverage for tests/headless/audit/run-all.sh in tests/headless/audit/test_run_all.sh

### Implementation for User Story 1

- [X] T011 [P] [US1] Replace seeded row synthesis with live observation collection in clients/python/highbar_client/behavioral_coverage/audit_runner.py
- [X] T012 [P] [US1] Implement deliverable refresh-status aggregation and summary rollups in clients/python/highbar_client/behavioral_coverage/audit_runner.py
- [X] T013 [US1] Regenerate command audit rows with freshness state, live evidence, and failure reasons in clients/python/highbar_client/behavioral_coverage/audit_report.py
- [X] T013a [US1] Render unresolved rows distinctly from freshness markers in clients/python/highbar_client/behavioral_coverage/audit_report.py
- [X] T014 [US1] Regenerate hypothesis plan entries from latest live outcomes in clients/python/highbar_client/behavioral_coverage/audit_report.py and clients/python/highbar_client/behavioral_coverage/hypotheses.py
- [X] T015 [US1] Regenerate V2-vs-V3 ledger links and residual-risk text from live row outcomes in clients/python/highbar_client/behavioral_coverage/audit_report.py
- [X] T016 [US1] Wire tests/headless/audit/run-all.sh to launch the live refresh flow, persist the manifest under build/reports/, and rewrite checked-in audit artifacts
- [X] T016a [US1] Emit manifest-derived refresh summary to shell stdout in tests/headless/audit/run-all.sh and clients/python/highbar_client/behavioral_coverage/audit_report.py
- [X] T017 [US1] Update checked-in outputs in audit/command-audit.md, audit/hypothesis-plan.md, audit/v2-v3-ledger.md, and audit/README.md from a completed live refresh run

**Checkpoint**: User Story 1 delivers a manifest-backed full refresh from the live topology and produces reviewer-facing artifacts without manual row edits

---

## Phase 4: User Story 2 - Preserve Row-Level Reproduction (Priority: P1)

**Goal**: Keep each refreshed row individually reproducible or hypothesis-testable against the live server without rerunning the full audit

**Independent Test**: Run `tests/headless/audit/repro.sh` for one verified row and `tests/headless/audit/hypothesis.sh` for one blocked or broken row, then confirm the generated row reports match the latest manifest classification

### Tests for User Story 2

- [X] T018 [P] [US2] Add row repro command coverage in clients/python/tests/behavioral_coverage/test_live_row_repro.py
- [X] T019 [P] [US2] Add hypothesis execution coverage in clients/python/tests/behavioral_coverage/test_live_hypothesis.py
- [X] T020 [US2] Add shell-level regression coverage for tests/headless/audit/repro.sh and tests/headless/audit/hypothesis.sh in tests/headless/audit/test_row_workflows.sh

### Implementation for User Story 2

- [X] T021 [P] [US2] Implement manifest-aware row lookup, phase selection, and evidence extraction in clients/python/highbar_client/behavioral_coverage/audit_runner.py
- [X] T022 [P] [US2] Update row hypothesis ranking and live verdict text in clients/python/highbar_client/behavioral_coverage/hypotheses.py
- [X] T023 [US2] Rewrite tests/headless/audit/repro.sh to execute live row refreshes and emit row-specific reports under build/reports/
- [X] T024 [US2] Rewrite tests/headless/audit/hypothesis.sh to execute live hypothesis checks and persist verdict reports under build/reports/
- [X] T025 [US2] Update tests/headless/audit/def-id-resolver.py and tests/headless/audit/README.md to support row-specific live prerequisites and reviewer usage

**Checkpoint**: Reviewers can rerun individual verified, blocked, or broken rows and receive outputs that align with the current live manifest

---

## Phase 5: User Story 3 - Expose Partial Refreshes And Drift (Priority: P2)

**Goal**: Make incomplete refreshes, topology/session failures, and run-to-run behavior drift explicit to reviewers

**Independent Test**: Run the live audit under a partially degraded environment and then run `tests/headless/audit/repro-stability.sh`; verify the summary distinguishes refreshed versus not-refreshed rows and flags changed outcomes between completed runs

### Tests for User Story 3

- [X] T026 [P] [US3] Add partial-refresh and failure-reason coverage in clients/python/tests/behavioral_coverage/test_refresh_summary.py
- [X] T026a [P] [US3] Add unresolved-row rendering and summary coverage in clients/python/tests/behavioral_coverage/test_refresh_summary.py
- [X] T027 [P] [US3] Add historical comparison and drift detection coverage in clients/python/tests/behavioral_coverage/test_live_audit_drift.py
- [X] T028 [US3] Add shell-level regression coverage for tests/headless/audit/repro-stability.sh and tests/headless/audit/phase2-macro-chain.sh in tests/headless/audit/test_drift_and_phase2.sh
- [X] T028a [US3] Add shell-level summary assertions for partial and drifted runs in tests/headless/audit/test_drift_and_phase2.sh

### Implementation for User Story 3

- [X] T029 [P] [US3] Implement topology/session failure capture and partial-refresh row marking in clients/python/highbar_client/behavioral_coverage/audit_runner.py
- [X] T030 [P] [US3] Implement previous-manifest comparison and drift classification in clients/python/highbar_client/behavioral_coverage/audit_runner.py
- [X] T031 [US3] Render refresh summaries and deliverable-level partial status in clients/python/highbar_client/behavioral_coverage/audit_report.py and audit/README.md
- [X] T032 [US3] Rewrite tests/headless/audit/repro-stability.sh to compare completed manifests instead of diffing seeded markdown snapshots
- [X] T033 [US3] Update tests/headless/audit/phase2-macro-chain.sh to persist Phase-2 attribution evidence that can be linked from drifted or phase1_reissuance rows

**Checkpoint**: Reviewers can distinguish refreshed, partial, not-refreshed, and drifted results directly from the live refresh outputs

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, cleanup, and cross-artifact consistency

- [X] T034 [P] Validate quickstart commands and expected outcomes in specs/006-live-audit-evidence/quickstart.md against the finished scripts
- [X] T034a [P] Add timing and unattended-run validation notes in specs/006-live-audit-evidence/quickstart.md and tests/headless/audit/README.md
- [X] T035 Run end-to-end live refresh validation through tests/headless/audit/run-all.sh, tests/headless/audit/repro.sh, tests/headless/audit/hypothesis.sh, tests/headless/audit/repro-stability.sh, and tests/headless/audit/phase2-macro-chain.sh
- [X] T036 [P] Clean up stale seed wording and compatibility notes across audit/README.md, audit/command-audit.md, audit/hypothesis-plan.md, and audit/v2-v3-ledger.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup completion and blocks all story work
- **User Story 1 (Phase 3)**: Depends on Foundational completion
- **User Story 2 (Phase 4)**: Depends on Foundational completion and uses the live manifest flow delivered in US1
- **User Story 3 (Phase 5)**: Depends on Foundational completion and extends the manifest/run history introduced in US1
- **Polish (Phase 6)**: Depends on all target stories being complete

### User Story Dependencies

- **US1**: No dependency on other user stories; this is the MVP
- **US2**: Depends on US1 manifest-backed refresh outputs so row workflows can read current evidence
- **US3**: Depends on US1 completed-run manifests; can proceed in parallel with late US2 work once manifest persistence is stable

### Within Each User Story

- Tests should be written before implementation and should fail against the current seeded behavior
- Manifest/data structure changes precede rendering changes
- Python orchestration changes precede shell entry-point rewrites
- Checked-in `audit/` artifacts should be refreshed only after the implementation path is working end to end

### Parallel Opportunities

- T004 and T005 can run in parallel after T003 and T003a
- T008 and T009 can run in parallel before US1 implementation completes
- T011 and T012 can run in parallel within US1
- T018 and T019 can run in parallel before US2 implementation completes
- T021 and T022 can run in parallel within US2
- T026, T026a, and T027 can run in parallel before US3 implementation completes
- T029 and T030 can run in parallel within US3
- T034, T034a, and T036 can run in parallel during polish

---

## Parallel Example: User Story 1

```bash
# Launch US1 test work together:
Task: "Add manifest contract coverage in clients/python/tests/behavioral_coverage/test_live_audit_manifest.py"
Task: "Add artifact rendering coverage for freshness markers in clients/python/tests/behavioral_coverage/test_audit_report_live_refresh.py"

# Launch US1 implementation work together:
Task: "Replace seeded row synthesis with live observation collection in clients/python/highbar_client/behavioral_coverage/audit_runner.py"
Task: "Implement deliverable refresh-status aggregation and summary rollups in clients/python/highbar_client/behavioral_coverage/audit_runner.py"
```

## Parallel Example: User Story 2

```bash
# Launch US2 test work together:
Task: "Add row repro command coverage in clients/python/tests/behavioral_coverage/test_live_row_repro.py"
Task: "Add hypothesis execution coverage in clients/python/tests/behavioral_coverage/test_live_hypothesis.py"

# Launch US2 implementation work together:
Task: "Implement manifest-aware row lookup, phase selection, and evidence extraction in clients/python/highbar_client/behavioral_coverage/audit_runner.py"
Task: "Update row hypothesis ranking and live verdict text in clients/python/highbar_client/behavioral_coverage/hypotheses.py"
```

## Parallel Example: User Story 3

```bash
# Launch US3 test work together:
Task: "Add partial-refresh and failure-reason coverage in clients/python/tests/behavioral_coverage/test_refresh_summary.py"
Task: "Add historical comparison and drift detection coverage in clients/python/tests/behavioral_coverage/test_live_audit_drift.py"

# Launch US3 implementation work together:
Task: "Implement topology/session failure capture and partial-refresh row marking in clients/python/highbar_client/behavioral_coverage/audit_runner.py"
Task: "Implement previous-manifest comparison and drift classification in clients/python/highbar_client/behavioral_coverage/audit_runner.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup
2. Complete Foundational manifest and rendering work
3. Complete User Story 1
4. Validate `tests/headless/audit/run-all.sh`
5. Refresh checked-in `audit/` artifacts from the latest completed live run

### Incremental Delivery

1. Establish manifest-backed refresh infrastructure
2. Deliver full live refresh generation for all three 004 artifacts
3. Add row-level repro and hypothesis reruns
4. Add partial-refresh reporting, drift detection, and Phase-2 attribution updates
5. Finish with quickstart and documentation validation

### Parallel Team Strategy

1. One developer completes foundational manifest contracts and CLI plumbing
2. A second developer can prepare US1 render tests while collection logic lands
3. After US1 stabilizes, one developer owns row workflows in `tests/headless/audit/*.sh` while another owns drift/summary logic in `clients/python/highbar_client/behavioral_coverage/`

---

## Notes

- All tasks follow the required checklist format with task ID, optional `[P]`, optional story label, and file path
- User stories are organized to keep each phase independently testable
- US1 is the suggested MVP scope because it establishes the live source of truth for every later workflow
