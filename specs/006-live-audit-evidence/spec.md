# Feature Specification: Live Audit Evidence Refresh

**Feature Branch**: `[006-live-audit-evidence]`  
**Created**: 2026-04-22  
**Status**: Draft  
**Input**: User description: "wire the 004 scripts to the real headless topology, run them against the live server, and then update the audit rows from observed behavior rather than the current seed data."

## Clarifications

### Session 2026-04-22

- Q: Which 004 deliverables must be refreshed from live behavior? → A: Refresh the full 004 audit set: command audit, hypothesis plan, and V2-vs-V3 ledger.
- Q: How should the refresh behave if some deliverables or rows cannot be updated live? → A: Publish partial refresh results, but clearly mark any deliverable or row that could not be refreshed live.
- Q: Should the refresh carry forward older evidence when the current live run fails for a row? → A: Only publish evidence from the latest completed live run, and mark any non-refreshed rows as not refreshed live.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Refresh Audit From Live Topology (Priority: P1)

 A maintainer needs the existing 004 audit workflow to run against the real headless topology and live server so the published 004 audit deliverables reflect observed behavior instead of seeded placeholder outcomes.

**Why this priority**: The audit is only trustworthy if it is grounded in what the live environment actually does. Running the existing workflow against the real topology is the minimum step needed to turn the audit from a scaffold into evidence.

**Independent Test**: A maintainer can start the live audit workflow against the headless environment and confirm that the command audit, hypothesis plan, and V2-versus-V3 ledger are regenerated from newly observed results rather than prior seed rows.

**Acceptance Scenarios**:

1. **Given** the live headless topology is reachable, **When** a maintainer runs the audit refresh workflow, **Then** the command audit, hypothesis plan, and V2-versus-V3 ledger are rebuilt from newly observed command and RPC behavior.
2. **Given** a row is marked verified after a live run, **When** a reviewer inspects that row, **Then** the row cites evidence from the latest completed live run instead of seed wording or older carried-forward evidence.
3. **Given** the workflow cannot observe behavior for a row, **When** the run completes, **Then** the row is clearly marked unresolved, blocked, broken, or not refreshed live rather than retaining stale seeded content.

---

### User Story 2 - Preserve Row-Level Reproduction (Priority: P1)

A reviewer needs each refreshed audit row to remain individually reproducible against the live server so specific findings can be rechecked without rerunning the entire audit.

**Why this priority**: Live evidence has limited value if reviewers cannot validate it row by row. Reproducibility keeps the audit actionable and prevents the refreshed output from becoming a one-time snapshot with no follow-up path.

**Independent Test**: A reviewer can choose one verified row and one blocked or broken row, run their row-specific workflows against the live server, and confirm that the recorded classifications match observed outcomes.

**Acceptance Scenarios**:

1. **Given** any verified row, **When** a reviewer runs its reproduction workflow, **Then** the workflow produces evidence consistent with the row's recorded outcome.
2. **Given** any blocked or broken row, **When** a reviewer runs its hypothesis workflow, **Then** the workflow reports whether the named explanation is supported by the latest observed behavior.
3. **Given** a rerun produces a different outcome than the current row classification, **When** the workflow finishes, **Then** the row is updated to reflect the newly observed behavior.

---

### User Story 3 - Expose Partial Refreshes And Drift (Priority: P2)

A maintainer needs the live audit process to show which deliverables and rows refreshed successfully, which failed due to environment issues, and which changed between runs so reviewers can trust the boundaries of the evidence.

**Why this priority**: Moving from seeded data to live evidence introduces environment variability. The refresh process must make incomplete coverage and behavioral drift explicit rather than implying false certainty.

**Independent Test**: A maintainer can run the live audit under a partially degraded environment and still receive a summary that separates refreshed findings, failed rows, and changed outcomes.

**Acceptance Scenarios**:

1. **Given** some live audit scenarios cannot complete, **When** the refresh run ends, **Then** the output identifies which deliverables and rows refreshed and which did not.
2. **Given** the audit is run more than once, **When** a row changes classification or evidence, **Then** the refresh highlights the drift instead of silently overwriting it.
3. **Given** a prerequisite for the live topology is missing, **When** a maintainer starts the workflow, **Then** the failure reason explains why live evidence could not be collected.

### Edge Cases

- The headless topology starts but the audit cannot establish a usable live session.
- Some rows refresh successfully while others fail because the live server is only partially healthy.
- One or more audit deliverables fail to refresh, while the remaining deliverables complete from the same live run.
- A previously seeded row cannot be reproduced live and must be downgraded or marked stale.
- A row refreshed in an earlier run fails in the latest run and must be marked not refreshed live instead of carrying forward older evidence as current.
- A repeated live run changes the observed outcome for a row because of timing or environment drift.
- The live server accepts a workflow request but no observable evidence is produced for the targeted row.
- Parts of the audit that depend on save, load, or multi-client coordination remain unavailable in the live environment.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST run the existing 004 audit workflow against the real headless topology and live server rather than against seed-only inputs.
- **FR-002**: The system MUST refresh the full 004 audit set from observations gathered during the most recent live run, including the command audit, hypothesis plan, and V2-versus-V3 ledger.
- **FR-003**: The system MUST preserve row-level reproduction for verified findings so reviewers can rerun an individual row against the live server.
- **FR-004**: The system MUST preserve row-level hypothesis evaluation for blocked or broken findings so reviewers can test the named explanation against live behavior.
- **FR-005**: The system MUST distinguish freshly observed evidence from stale, missing, or unresolved evidence in each refreshed audit artifact.
- **FR-006**: The system MUST update a row's classification when the latest observed behavior differs from the prior recorded outcome.
- **FR-007**: The system MUST allow the refresh to publish partial results when some deliverables or rows fail, provided every non-refreshed deliverable or row is explicitly marked as not refreshed live.
- **FR-007a**: The system MUST report partial refresh failures explicitly, including which rows or deliverables were not refreshed and why.
- **FR-007b**: The system MUST treat the latest completed live run as the only source of current evidence and MUST NOT present older run evidence as current for rows that fail to refresh.
- **FR-008**: The system MUST surface live-topology and session-establishment failures with specific reasons before or during the refresh run.
- **FR-009**: The system MUST make outcome drift between repeated live runs visible to reviewers.
- **FR-010**: The system MUST ensure reviewer-facing audit guidance describes the live refresh workflow and does not present seed data as current evidence.
- **FR-011**: The system MUST refresh the V2-versus-V3 ledger alongside the command audit and hypothesis plan, tying each ledger entry to current live observations or explicitly indicating where live proof is still missing.
- **FR-012**: The system MUST end each refresh with a summary of which findings were verified live, which remained blocked, which became broken, and which still need follow-up.

### Key Entities *(include if feature involves data)*

- **Live Audit Run**: One execution of the audit refresh against the real headless topology, including prerequisites, observed outcomes, and run-level summary.
- **Observed Evidence Record**: The reviewer-visible evidence attached to a row from the latest live run.
- **Evidence Freshness State**: The indicator that a row is backed by the latest completed live run or is marked not refreshed live for the current run.
- **Audit Row Status**: The recorded classification of a command or RPC row after a live refresh, such as verified, blocked, broken, unresolved, or drifted.
- **Hypothesis Result**: The result of rerunning a blocked or broken row's explanatory workflow against the live environment.
- **Refresh Summary**: The run-level report of refreshed rows, failed rows, changed rows, and remaining follow-up work.
- **Deliverable Refresh Status**: The live-refresh state of each 004 audit deliverable, indicating refreshed, partially refreshed, or not refreshed live.

### Status Vocabulary

- **Outcome bucket**: The row classification after evaluation against the live environment. Allowed values are `verified`, `blocked`, `broken`, and `unresolved`.
- **Freshness state**: The indicator that describes whether the row reflects the latest completed live run. Allowed values are `refreshed-live`, `not-refreshed-live`, and `drifted`.
- **Combination rule**: Outcome bucket and freshness state are separate fields. A row may remain `unresolved` while also being `not-refreshed-live`, and reviewers must be able to distinguish those concepts in rendered artifacts and summaries.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A maintainer can run the live audit refresh and obtain updated command audit, hypothesis plan, and V2-versus-V3 ledger artifacts without manual row editing.
- **SC-002**: Reviewers can rerun at least one verified row and one blocked or broken row and obtain outcomes that match the refreshed artifacts.
- **SC-003**: Every row in the refreshed audit explicitly indicates whether its evidence came from the latest live run, remains unresolved, or was not refreshed.
- **SC-003a**: No row is presented as current live evidence unless it was refreshed during the latest completed live run.
- **SC-004**: When the live environment is degraded or incomplete, the refresh output identifies which findings were not refreshed and why.
- **SC-004a**: When a live run only refreshes part of the 004 audit set, reviewers can tell which deliverables completed, which were partial, and which were not refreshed live.
- **SC-005**: Repeated live refreshes make row-level behavior changes visible instead of silently replacing earlier results.

## Assumptions

- The existing 004 audit scripts and deliverables remain the starting point and will be upgraded rather than replaced wholesale.
- The live refresh updates the full 004 audit set in one pass rather than refreshing only a subset of the tracked deliverables.
- A usable live headless environment is available often enough to support repeated audit refresh runs, even if some scenarios remain flaky.
- Reviewers prefer explicit evidence freshness and uncertainty reporting over preserving earlier seed wording.
- Older live evidence may remain useful for historical comparison, but it is not treated as current evidence when the latest run fails to refresh a row.
- Rows that cannot yet be proven live should remain visible as unresolved or blocked findings rather than being removed.
- Deeper dispatcher or engine fixes discovered by the live refresh remain follow-up work outside this feature.
