# Feature Specification: Live Audit Evidence Refresh

**Feature Branch**: `[005-live-audit-evidence]`  
**Created**: 2026-04-22  
**Status**: Draft  
**Input**: User description: "wire the 004 scripts to the real headless topology, run them against the live server, and then update the audit rows from observed behavior rather than the current seed data."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Replace Seed Audit Rows With Live Evidence (Priority: P1)

A maintainer needs the audit workflow to connect to the real headless game environment, execute the audit scenarios, and update the audit deliverables from observed runtime behavior instead of prefilled seed rows.

**Why this priority**: The existing seed audit is useful for structure, but it does not prove that commands and RPCs behave correctly against the live environment. Replacing seed output with observed evidence is the minimum step needed to make the audit trustworthy.

**Independent Test**: A maintainer can run the audit workflow against a live headless environment and confirm that the main audit deliverable is updated from newly collected evidence rather than regenerated placeholder text.

**Acceptance Scenarios**:

1. **Given** a reachable headless environment, **When** a maintainer runs the primary audit workflow, **Then** the audit rows are refreshed from newly collected runtime observations.
2. **Given** a row classified as verified after a live run, **When** a reviewer inspects that row, **Then** the row cites evidence that came from the latest live run rather than a generic seed statement.
3. **Given** the live workflow cannot collect evidence for a row, **When** the run finishes, **Then** that row is clearly marked as unresolved, blocked, or broken rather than silently left with stale seed wording.

---

### User Story 2 - Reproduce Observed Behavior Row by Row (Priority: P1)

A reviewer needs each audit row and hypothesis entry to remain individually reproducible after the switch to live evidence, so they can verify that a specific command or RPC truly behaved as documented.

**Why this priority**: Live evidence only becomes actionable if reviewers can rerun and verify individual findings. Without row-level reproduction, the audit becomes a one-time report instead of an operational testing asset.

**Independent Test**: A reviewer can choose one verified row and one blocked or broken row, rerun their row-specific workflows against the live environment, and confirm that the observed outcomes match the recorded classification.

**Acceptance Scenarios**:

1. **Given** any verified row, **When** a reviewer runs that row's reproduction workflow, **Then** the workflow produces evidence consistent with the recorded outcome and updates or confirms the row accordingly.
2. **Given** any blocked or broken row, **When** a reviewer runs its hypothesis workflow, **Then** the workflow reports whether the named hypothesis is confirmed or falsified based on live observations.
3. **Given** a live rerun produces a different result than the current row classification, **When** the audit workflow completes, **Then** the row is updated to reflect the newly observed behavior and the change is made visible to reviewers.

---

### User Story 3 - Surface Live Run Drift and Partial Failures Transparently (Priority: P2)

A maintainer needs the audit system to show which findings were refreshed successfully, which failed due to environment or setup issues, and which changed behavior between runs, so the audit remains safe to trust during ongoing development.

**Why this priority**: Moving from seed data to live evidence introduces environment volatility. The audit must separate true behavioral findings from incomplete or unstable collection runs.

**Independent Test**: A maintainer can run the audit under a partially degraded or drifting environment and still receive a report that distinguishes refreshed rows, failed rows, and changed rows without masking uncertainty.

**Acceptance Scenarios**:

1. **Given** the live environment starts but some audit scenarios cannot complete, **When** the audit finishes, **Then** the output clearly identifies which rows were refreshed and which were not.
2. **Given** the same audit is run more than once, **When** outcomes differ between runs, **Then** the audit highlights the drift rather than overwriting prior uncertainty without explanation.
3. **Given** a prerequisite such as authentication, environment health, or match setup is missing, **When** a maintainer starts the live workflow, **Then** the workflow fails with a specific reason that explains why evidence could not be collected.

### Edge Cases

- The headless environment starts but the audit cannot establish a usable session, so no behavioral evidence can be collected.
- Some commands behave differently across runs because of ambient game-state variance, timing drift, or unstable setup conditions.
- A row previously marked from seed data cannot be reproduced live and must be downgraded or flagged as stale evidence.
- The environment allows a subset of RPC or command checks to complete while others fail due to startup, authorization, or scenario-precondition issues.
- A live rerun produces evidence that contradicts the current hypothesis classification for a row.
- Save, load, or multi-client coordination behaviors are unavailable or only partially wired in the live environment.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The audit workflow MUST execute against the real headless runtime environment and collect evidence from live behavior rather than generating generic seed-only output.
- **FR-002**: The system MUST refresh the main audit deliverables using evidence collected from the most recent live run.
- **FR-003**: The system MUST preserve row-level reproduction so a reviewer can rerun an individual verified row and compare the outcome to the recorded evidence.
- **FR-004**: The system MUST preserve row-level hypothesis evaluation so a reviewer can rerun an individual blocked or broken row and see whether the named hypothesis is confirmed or falsified.
- **FR-005**: The system MUST distinguish freshly observed evidence from stale, missing, or unresolved evidence in every audit deliverable.
- **FR-006**: The system MUST update row classifications when live observations differ from the previously recorded outcome.
- **FR-007**: The system MUST report partial failures explicitly, including which rows were not refreshed and why evidence collection did not complete.
- **FR-008**: The system MUST surface environment-health, session-establishment, and prerequisite failures before or during the run with specific failure reasons.
- **FR-009**: The system MUST identify outcome drift between repeated live runs rather than silently treating inconsistent results as stable.
- **FR-010**: The system MUST ensure reviewer-facing guidance matches the real live workflow and does not describe seed-only behavior as live evidence.
- **FR-011**: The system MUST keep the V2-versus-V3 ledger linked to audit findings that came from current live observations or explicitly identify where live proof is still missing.
- **FR-012**: The audit refresh process MUST leave maintainers with a clear summary of which findings were verified live, which remained blocked, which became broken, and which still need follow-up investigation.

### Key Entities *(include if feature involves data)*

- **Live Audit Run**: One full execution of the audit against the headless runtime, including prerequisites, observed evidence, row outcomes, and run-level summary.
- **Observed Evidence Record**: The specific runtime observation attached to a row, such as a behavioral state change, an authorization outcome, a session failure, or a reproducible blocker.
- **Audit Row Status**: The reviewer-facing classification of a single command or RPC after a live run, including verified, blocked, broken, unresolved, or drifted states.
- **Hypothesis Result**: The outcome of rerunning a row-specific explanatory test to determine whether the named explanation still matches observed behavior.
- **Refresh Summary**: The run-level summary that shows which rows were refreshed successfully, which failed to refresh, and which changed from their prior classification.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A maintainer can run the live audit workflow and obtain an updated audit summary without manual file editing.
- **SC-002**: Reviewers can rerun at least one verified row and one blocked or broken row and see outcomes that match the refreshed audit artifacts.
- **SC-003**: Every row in the refreshed audit explicitly indicates whether its evidence came from the latest live run, remains unresolved, or was not refreshed.
- **SC-004**: When the live environment is degraded or incomplete, the audit reports which findings were not refreshed and why, instead of presenting a falsely complete audit.
- **SC-005**: Repeated live runs make behavior changes visible by identifying rows whose outcomes drifted between runs.

## Assumptions

- The existing 004 audit deliverables, reproduction workflows, and hypothesis workflows remain the starting point for this feature and will be upgraded rather than replaced wholesale.
- A usable headless runtime environment is available on the reference host often enough to support repeated audit runs, even if some scenarios remain flaky or partially blocked.
- Reviewers care more about explicit evidence quality and freshness than about preserving prior seed wording.
- Rows that cannot yet be proven live should remain visible in the audit as unresolved or blocked findings rather than being removed from scope.
- This feature is limited to wiring the audit to live behavior and refreshing evidence; deeper dispatcher or engine fixes discovered by the live audit remain follow-up work.
