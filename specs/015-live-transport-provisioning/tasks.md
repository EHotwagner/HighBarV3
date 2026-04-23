# Tasks: Live Transport Provisioning

**Input**: Design documents from `/specs/015-live-transport-provisioning/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Include pytest, synthetic headless validation, campaign validation, and prepared live rerun tasks because the spec defines independent test criteria for every user story and the quickstart requires them.

**Organization**: Tasks are grouped by user story so each increment stays independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel when dependencies are already complete.
- **[Story]**: User story label for story-phase tasks only.
- Every task includes an exact file path.
- Any task touching `tests/headless/*` must keep edits surgical and preserve Constitution I upstream-fork discipline.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the existing Itertesting regression and artifact-validation surfaces for 015-specific transport provisioning work.

- [X] T001 Add shared transport provisioning regression fixtures in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py` and `clients/python/tests/test_behavioral_registry.py`
- [X] T002 [P] Add shared transport reporting and blocker-classification assertions in `clients/python/tests/behavioral_coverage/test_itertesting_report.py` and `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`
- [X] T003 [P] Add reusable transport artifact checks in `tests/headless/test_live_itertesting_hardening.sh`, `tests/headless/test_itertesting_campaign.sh`, and `tests/headless/itertesting.sh`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the shared transport data model, callback plumbing, and serialization required before any story can land cleanly.

**⚠️ CRITICAL**: No user story work should start until this phase is complete.

- [X] T004 Define `TransportProvisioningResult`, `SupportedTransportVariant`, `TransportCandidate`, `TransportLifecycleEvent`, and `TransportCompatibilityCheck` in `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`
- [X] T005 [P] Add the authoritative transport-dependent command set, supported transport variant metadata, and status helpers in `clients/python/highbar_client/behavioral_coverage/bootstrap.py`
- [X] T006 [P] Add shared transport provisioning serialization and aggregate summary plumbing in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T007 [P] Add shared transport blocker and compatibility classification helpers in `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py` and `clients/python/highbar_client/behavioral_coverage/registry.py`
- [X] T008 Implement shared runtime transport def-resolution helpers and callback trace storage in `clients/python/highbar_client/behavioral_coverage/__init__.py` and `clients/python/highbar_client/behavioral_coverage/bootstrap.py`
- [X] T009 [P] Add foundational serialization and helper regressions in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`, `clients/python/tests/behavioral_coverage/test_itertesting_report.py`, and `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`

**Checkpoint**: The transport lifecycle model, callback plumbing, and bundle serialization are ready for story work.

---

## Phase 3: User Story 1 - Provision a Usable Transport Fixture (Priority: P1) 🎯 MVP

**Goal**: Ensure a usable transport is discovered or provisioned through the real client-mode workflow before transport-dependent commands are evaluated.

**Independent Test**: Run a prepared live Itertesting closeout pass and confirm that transport-dependent commands proceed past the fixture gate when the environment can provide a valid transport, while only those commands remain blocked when no usable transport can be obtained.

### Tests for User Story 1

- [ ] T010 [P] [US1] Add regressions for preexisting transport reuse and natural transport provisioning in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`
- [ ] T011 [P] [US1] Add regressions for transport-only blocker precision in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py` and `clients/python/tests/test_behavioral_registry.py`
- [ ] T012 [P] [US1] Add synthetic hardening assertions for discovered, provisioned, and still-missing `transport_unit` states in `tests/headless/test_live_itertesting_hardening.sh`

### Implementation for User Story 1

- [X] T013 [US1] Implement `InvokeCallback` forwarding on the maintainer live endpoint in `specs/002-live-headless-e2e/examples/coordinator.py`
- [X] T014 [US1] Populate runtime transport `def_id_by_name` resolution through the client-mode callback path in `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [ ] T015 [US1] Add preexisting transport discovery and reuse logic for `transport_unit` in `clients/python/highbar_client/behavioral_coverage/bootstrap.py` and `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [ ] T016 [US1] Implement ordinary live transport provisioning attempts before fixture-blocking transport commands in `clients/python/highbar_client/behavioral_coverage/bootstrap.py` and `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [ ] T017 [US1] Carry transport provisioning outcomes into fixture summaries, affected-command lists, and command gating in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`
- [ ] T018 [US1] Keep payload handling and non-transport command evaluation unchanged while transport-only blockers are emitted in `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`

**Checkpoint**: User Story 1 unlocks live evaluation for transport-dependent commands whenever the environment can supply a usable transport.

---

## Phase 4: User Story 2 - Keep Transport Coverage Usable Throughout the Run (Priority: P2)

**Goal**: Accept supported transport variants, validate transport-payload compatibility, and refresh or replace transport coverage when the first candidate becomes unusable.

**Independent Test**: Validate that the workflow accepts supported transport variants present in the environment and can refresh or replace the fixture when the current transport is lost or incompatible before later commands run.

### Tests for User Story 2

- [X] T019 [P] [US2] Add supported-variant recognition regressions for `armatlas` and `armhvytrans` in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py` and `clients/python/tests/test_behavioral_registry.py`
- [ ] T020 [P] [US2] Add refresh, replacement, and payload-compatibility regressions in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py` and `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`
- [ ] T021 [P] [US2] Add synthetic hardening assertions for refreshed, replaced, and payload-incompatible transport states in `tests/headless/test_live_itertesting_hardening.sh`

### Implementation for User Story 2

- [X] T022 [US2] Expand supported transport variant metadata, selection priority, and provisioning mode rules in `clients/python/highbar_client/behavioral_coverage/bootstrap.py`
- [X] T023 [US2] Replace the single transport health heuristic with supported-variant live discovery in `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [X] T024 [US2] Implement `TransportCandidate` lifecycle tracking and replacement chains in `clients/python/highbar_client/behavioral_coverage/itertesting_types.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T025 [US2] Add per-command transport-payload compatibility checks before load/unload evaluation in `clients/python/highbar_client/behavioral_coverage/registry.py` and `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [ ] T026 [US2] Refresh or replace lost, stale, or incompatible transport candidates before later transport-dependent commands in `clients/python/highbar_client/behavioral_coverage/bootstrap.py` and `clients/python/highbar_client/behavioral_coverage/__init__.py`
- [X] T027 [US2] Expand supported transport audit coverage for live review in `tests/headless/audit/def-id-resolver.py`

**Checkpoint**: User Story 2 keeps transport-dependent commands trustworthy even when the first transport is not the only valid variant or becomes unusable mid-run.

---

## Phase 5: User Story 3 - Preserve Trustworthy Reporting and Run Stability (Priority: P3)

**Goal**: Surface transport lifecycle detail in the existing run bundle while preserving healthy channel status and clear closeout decisions.

**Independent Test**: Review the run bundle from repeated prepared live runs and confirm that transport lifecycle status is visible, transport failures remain distinct from other causes, and channel health stays healthy while provisioning is enabled.

### Tests for User Story 3

- [X] T028 [P] [US3] Add report-rendering regressions for transport lifecycle, fallback visibility, and affected-command detail in `clients/python/tests/behavioral_coverage/test_itertesting_report.py`
- [ ] T029 [P] [US3] Add campaign and channel-health regressions for stable transport provisioning outcomes in `clients/python/tests/behavioral_coverage/test_itertesting_runner.py` and `tests/headless/test_itertesting_campaign.sh`
- [X] T030 [P] [US3] Add prepared-run artifact assertions for transport lifecycle summaries in `tests/headless/test_live_itertesting_hardening.sh` and `tests/headless/itertesting.sh`

### Implementation for User Story 3

- [X] T031 [US3] Serialize the transport resolution trace (`variant_id`, `callback_path`, `resolved_def_id`, `resolution_status`, `reason`) into `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py` and `clients/python/highbar_client/behavioral_coverage/itertesting_types.py`
- [X] T032 [US3] Render `transport_provisioning` lifecycle, candidate, and compatibility detail in `clients/python/highbar_client/behavioral_coverage/itertesting_report.py`
- [X] T033 [US3] Serialize transport lifecycle, fallback provenance, and affected-command detail into `manifest.json` and contract-health inputs in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py`
- [X] T034 [US3] Keep `missing_fixture`, `transport_interruption`, payload incompatibility, evidence gaps, and behavioral failures separated for transport commands in `clients/python/highbar_client/behavioral_coverage/live_failure_classification.py`
- [X] T035 [US3] Update maintainer wrapper summaries and artifact inspection output for transport lifecycle review in `tests/headless/itertesting.sh` and `tests/headless/README.md`
- [ ] T036 [US3] Preserve healthy closeout stop/proceed behavior while transport provisioning is enabled in `clients/python/highbar_client/behavioral_coverage/itertesting_runner.py` and `tests/headless/test_itertesting_campaign.sh`

**Checkpoint**: User Story 3 keeps the run bundle trustworthy and the prepared live closeout path stable while transport coverage is added.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, documentation, and baseline comparison across all stories.

- [ ] T037 Add transport/coordinator integration coverage for callback relay and transport provisioning handoff in `tests/integration/transport_parity_test.cc` and `tests/integration/README.md`
- [X] T038 [P] Update transport validation guidance and closeout expectations in `specs/015-live-transport-provisioning/quickstart.md`
- [X] T039 Run targeted pytest transport coverage in `clients/python/tests/behavioral_coverage/test_live_failure_classification.py`, `clients/python/tests/behavioral_coverage/test_itertesting_runner.py`, `clients/python/tests/behavioral_coverage/test_itertesting_report.py`, and `clients/python/tests/test_behavioral_registry.py`
- [X] T040 Run synthetic and campaign validation in `tests/headless/test_live_itertesting_hardening.sh` and `tests/headless/test_itertesting_campaign.sh`
- [ ] T041 Run three prepared live closeout reruns via `tests/headless/itertesting.sh`
- [ ] T042 Compare `reports/itertesting/<run-id>/manifest.json`, `reports/itertesting/<run-id>/run-report.md`, and `reports/itertesting/<run-id>/campaign-stop-decision.json` against `reports/2026-04-22-22h06min-014-transport-provisioning-status.md` to confirm SC-001 through SC-006
- [ ] T043 Confirm supported-variant evidence for `armatlas` and `armhvytrans` using `tests/headless/audit/def-id-resolver.py` and the latest `reports/itertesting/<run-id>/` artifacts to satisfy SC-007

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1**: No dependencies.
- **Phase 2**: Depends on Phase 1 and blocks all user stories.
- **Phase 3 (US1)**: Depends on Phase 2.
- **Phase 4 (US2)**: Depends on Phase 2 and builds most cleanly on top of US1 transport provisioning.
- **Phase 5 (US3)**: Depends on Phase 2 and is best validated after US1 and US2 lifecycle behavior exists.
- **Phase 6**: Depends on the selected user stories being complete.

### User Story Dependencies

- **US1 (P1)**: No hard dependency on other stories once foundational work is done.
- **US2 (P2)**: Extends US1 by broadening variant support and refresh/replacement behavior.
- **US3 (P3)**: Depends on US1 and US2 lifecycle outputs so reporting and stability checks have real transport events to render.

### Within Each User Story

- Write the story tests first and confirm they fail before implementation.
- Land lifecycle/data-model changes before report or wrapper output that consumes them.
- Add transport discovery/provisioning before tightening compatibility and replacement rules that assume a candidate exists.
- Run the story’s independent validation before moving to the next priority.

### Parallel Opportunities

- `T002` and `T003` can run in parallel after `T001`.
- `T005`, `T006`, `T007`, and `T009` can run in parallel after `T004`.
- `T010`, `T011`, and `T012` can run in parallel.
- `T019`, `T020`, and `T021` can run in parallel.
- `T028`, `T029`, and `T030` can run in parallel.
- `T038` can run in parallel with final validation once implementation is complete.

---

## Parallel Example: User Story 1

```bash
Task: "Add regressions for preexisting transport reuse and natural transport provisioning in clients/python/tests/behavioral_coverage/test_itertesting_runner.py"
Task: "Add regressions for transport-only blocker precision in clients/python/tests/behavioral_coverage/test_live_failure_classification.py and clients/python/tests/test_behavioral_registry.py"
Task: "Add synthetic hardening assertions for discovered, provisioned, and still-missing transport_unit states in tests/headless/test_live_itertesting_hardening.sh"
```

---

## Parallel Example: User Story 2

```bash
Task: "Add supported-variant recognition regressions for armatlas and armhvytrans in clients/python/tests/behavioral_coverage/test_itertesting_runner.py and clients/python/tests/test_behavioral_registry.py"
Task: "Add refresh, replacement, and payload-compatibility regressions in clients/python/tests/behavioral_coverage/test_live_failure_classification.py and clients/python/tests/behavioral_coverage/test_itertesting_runner.py"
Task: "Add synthetic hardening assertions for refreshed, replaced, and payload-incompatible transport states in tests/headless/test_live_itertesting_hardening.sh"
```

---

## Parallel Example: User Story 3

```bash
Task: "Add report-rendering regressions for transport lifecycle, fallback visibility, and affected-command detail in clients/python/tests/behavioral_coverage/test_itertesting_report.py"
Task: "Add campaign and channel-health regressions for stable transport provisioning outcomes in clients/python/tests/behavioral_coverage/test_itertesting_runner.py and tests/headless/test_itertesting_campaign.sh"
Task: "Add prepared-run artifact assertions for transport lifecycle summaries in tests/headless/test_live_itertesting_hardening.sh and tests/headless/itertesting.sh"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1).
3. Validate that transport-dependent commands proceed past the fixture gate when the environment can provide a usable transport.
4. Stop and review the run bundle before expanding variant, refresh, and reporting work.

### Incremental Delivery

1. Ship US1 to replace discovery-only transport handling with real reuse/provisioning.
2. Ship US2 to broaden variant support and keep transport coverage usable across the run.
3. Ship US3 to make lifecycle reporting explicit while preserving closeout stability.
4. Finish with Phase 6 validation against the 2026-04-22 baseline.

### Parallel Team Strategy

1. One developer lands Phase 1 and Phase 2 shared transport plumbing.
2. After foundational completion:
   - Developer A: US1 transport reuse, callback relay, and natural provisioning.
   - Developer B: US2 variant recognition, compatibility, and refresh/replacement.
   - Developer C: US3 reporting, wrapper summaries, and closeout-stability checks.
3. Rejoin for Phase 6 prepared live validation.

---

## Notes

- Total tasks: 43
- Story task counts: US1 = 9, US2 = 9, US3 = 9
- Parallel opportunities identified: Setup, foundational serialization/classification work, and the test phases for each story
- Suggested MVP scope: Phase 3 / US1 only
- All tasks use the required checklist format with checkbox, task id, optional `[P]`, story label for story phases, and exact file paths
