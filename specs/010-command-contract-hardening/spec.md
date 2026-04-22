# Feature Specification: Command Contract Hardening

**Feature Branch**: `[010-command-contract-hardening]`  
**Created**: 2026-04-22  
**Status**: Draft  
**Input**: User description: "the current bottleneck is the command-channel disconnect, not the tuned arm logic. If you want, I can inspect the latest coordinator/engine logs next and trace where the channel disconnect first appears. pipeline issues like batch target vs per-command unit drift, shallow validation, and commands that dispatch to no-ops. Itertesting can expose those, classify them, and produce better repros. It cannot make an incoherent command contract coherent.

So the split is:

- Yes: use Itertesting to improve coverage, evidence quality, repro quality, setup strategy, cheat-assisted scaffolding, and run-to-run learning.
- No: do not expect Itertesting to be the main mechanism for repairing protocol/dispatch semantics, schema mismatches, or inert command implementations.
The right order is:

1. Fix foundational command contract issues.
2. Use targeted deterministic tests for specific dispatcher/validator bugs."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Surface Foundational Contract Blockers (Priority: P1)

As a maintainer reviewing live command coverage, I want foundational command-contract defects to be separated from ordinary verification failures so I can fix the real blocker before spending time on Itertesting retries or tuning.

**Why this priority**: If contract defects are mixed into ordinary coverage failures, maintainers waste time tuning retries and evidence windows for commands that are structurally incapable of succeeding.

**Independent Test**: Run a campaign containing known contract defects and confirm the system reports them as foundational blockers rather than as ordinary retry candidates or coverage regressions.

**Acceptance Scenarios**:

1. **Given** a command whose batch target and per-command target disagree, **When** the campaign classifies the outcome, **Then** the result is recorded as a foundational contract issue rather than as a normal verification failure.
2. **Given** a command that passes shallow validation but dispatches to no meaningful effect, **When** the campaign finishes, **Then** the command is reported as an inert contract issue with a maintainer-facing explanation.

---

### User Story 2 - Produce Deterministic Repros For Contract Defects (Priority: P2)

As a maintainer diagnosing a command defect, I want a deterministic repro for each foundational contract issue so I can confirm the defect quickly and fix it with focused tests.

**Why this priority**: Once foundational blockers are identified, the fastest path to repair is a small deterministic reproduction rather than another broad campaign.

**Independent Test**: For each detected foundational issue class, generate a targeted repro and verify that a maintainer can rerun it independently from the broader campaign workflow.

**Acceptance Scenarios**:

1. **Given** a command classified with a foundational contract issue, **When** the maintainer requests a repro, **Then** the system provides a deterministic scenario tied to that issue class.
2. **Given** multiple commands that fail for different foundational reasons, **When** repros are generated, **Then** each repro remains focused on its own defect and does not depend on unrelated campaign context.

---

### User Story 3 - Gate Itertesting Behind Contract Health (Priority: P3)

As a maintainer using Itertesting for campaign improvement, I want Itertesting to focus on coverage, evidence, setup quality, and run-to-run learning only after foundational contract blockers are handled so campaign output remains actionable.

**Why this priority**: Itertesting is valuable for coverage improvement, but only after command semantics are coherent enough for retries and evidence tuning to matter.

**Independent Test**: Run one campaign with unresolved foundational blockers and one with no such blockers, and verify that the first stops with a contract-health decision while the second proceeds into normal Itertesting learning output.

**Acceptance Scenarios**:

1. **Given** unresolved foundational contract issues, **When** a maintainer starts Itertesting, **Then** the workflow records that the run is not ready for normal improvement-driven iteration.
2. **Given** a command set with no foundational contract blockers, **When** Itertesting runs, **Then** the workflow continues to produce ordinary coverage, evidence, setup, and learning outputs.

### Edge Cases

- What happens when a command intentionally has no observable effect and should not be treated as a defect?
- How does the system handle a command that exhibits both a foundational contract issue and an ordinary evidence gap in the same run?
- What happens when a contract issue only appears in batched dispatch and not in isolated single-command execution?
- How does the workflow respond when a deterministic repro cannot be generated from the available evidence for a newly observed issue pattern?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST distinguish foundational command-contract issues from ordinary Itertesting outcomes such as coverage gaps, evidence gaps, setup gaps, and retryable failures.
- **FR-002**: The system MUST classify at least the following foundational issue classes when observed: target drift between batch-level and command-level intent, shallow validation that allows invalid commands to proceed, and commands that dispatch but produce no meaningful effect.
- **FR-003**: The system MUST present foundational contract issues in maintainer-facing output with a primary cause category and supporting explanation.
- **FR-004**: The system MUST prevent unresolved foundational contract issues from being presented as normal Itertesting improvement opportunities.
- **FR-005**: The system MUST provide a contract-health decision for each run indicating whether Itertesting should proceed as a coverage-improvement workflow or stop for foundational repair.
- **FR-006**: The system MUST generate or reference a deterministic repro for each foundational contract issue that is classified.
- **FR-007**: The system MUST keep deterministic repros narrowly scoped to the specific defect they are intended to confirm.
- **FR-008**: The system MUST preserve the role of Itertesting for improving coverage, evidence quality, setup strategy, cheat-assisted scaffolding, and run-to-run learning after contract health is acceptable.
- **FR-009**: The system MUST ensure that commands classified with foundational contract issues remain visible in summaries until a subsequent run demonstrates that the blocker is resolved.
- **FR-010**: The system MUST allow maintainers to review foundational blockers separately from downstream campaign-quality findings in reports and stop decisions.
- **FR-011**: The system MUST ensure that targeted deterministic tests can be run independently from the broader campaign workflow.

### Key Entities *(include if feature involves data)*

- **Command Contract Issue**: A maintainer-facing record describing a foundational defect class, the affected command, the primary cause, and the evidence that triggered the classification.
- **Deterministic Repro**: A focused reproduction recipe or artifact linked to a specific command contract issue and intended to confirm the defect without running a full campaign.
- **Contract Health Decision**: A run-level outcome indicating whether foundational blockers are present and whether the workflow should proceed into normal Itertesting improvement behavior.
- **Itertesting Improvement Outcome**: A run result describing downstream quality signals such as coverage gains, evidence improvements, setup improvements, and learning recommendations once contract health is acceptable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a review of known defective commands, 100% of foundational contract issues are reported outside the ordinary Itertesting improvement bucket.
- **SC-002**: Maintainers can identify the primary blocker category for a defective command from the run output in under 10 minutes without inspecting unrelated campaign artifacts.
- **SC-003**: At least 90% of foundational contract issues detected in a run have an associated deterministic repro or clearly linked focused test path.
- **SC-004**: In validation runs that contain unresolved foundational blockers, the workflow prevents ordinary improvement guidance from being treated as the primary remediation path.
- **SC-005**: In validation runs without foundational blockers, Itertesting continues to emit ordinary coverage and learning output without being blocked by the contract-health gate.

## Assumptions

- The primary users are maintainers and reviewers diagnosing command behavior in an internal workflow rather than end users in a public product flow.
- Existing live campaign and reporting workflows remain in scope, but their role is narrowed so foundational contract repair happens before improvement-driven iteration.
- Recent issue patterns such as target drift, shallow validation, and inert dispatch behavior are representative enough to define the first set of foundational blocker categories.
- Deterministic repros may reference existing focused test paths where those already provide a stable confirmation route.
