# Feature Specification: Itertesting

**Feature Branch**: `[007-itertesting]`  
**Created**: 2026-04-22  
**Status**: Draft  
**Input**: User description: "create an evolving iterating testsuite called itertesting where you try to get as many commands verified with behaviorally observed evidence such as gamedata. if it doesnt work improve on it and start a new run. dont forget there are also cheatcodes to give units. itertesting writes reports in reports/itertesting/.. using date/time to seconds for names."

## Clarifications

### Session 2026-04-22

- Q: What stopping rule should govern iterative reruns? → A: Stop after a configurable maximum number of improvement runs, even if some commands remain unverified.
- Q: What evidence standard is sufficient to mark a command verified? → A: Only direct game-state evidence or command-specific live artifacts can mark a command verified.
- Q: How should cheat-assisted verification be treated in final reporting? → A: Cheat-assisted verification counts, but must be labeled separately from natural verification.
- Q: How should the suite prioritize natural versus cheat-assisted verification? → A: Prioritize natural verification first, then use cheat-assisted verification when natural progress stalls.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Grow Verified Command Coverage (Priority: P1)

A maintainer can run Itertesting and receive a fresh report showing how many commands were behaviorally verified from observed game evidence in that run, along with which commands remain unverified.

**Why this priority**: The primary value is increasing the number of commands that have direct behavioral proof instead of indirect assumptions or dispatcher-only evidence.

**Independent Test**: Run Itertesting once against the current headless environment and confirm it produces a timestamped report that lists all tracked commands, their observed status, and the total number verified in that run.

**Acceptance Scenarios**:

1. **Given** a runnable headless environment, **When** a maintainer starts Itertesting, **Then** the suite records one run report containing the observed result for every tracked command.
2. **Given** commands that can already be behaviorally observed, **When** Itertesting completes a run, **Then** those commands are marked verified with concrete observed evidence from the game state or equivalent live evidence.

---

### User Story 2 - Iterate After Failures (Priority: P1)

A maintainer can let Itertesting adapt after a failed or inconclusive run so the next run improves setup, targeting, or evidence gathering instead of repeating the same weak attempt.

**Why this priority**: The user explicitly wants an evolving suite that improves itself between runs to maximize verified coverage over time.

**Independent Test**: Trigger a run where some commands fail to verify, then confirm Itertesting records what was inconclusive, defines a better next attempt, and starts a new run using the improved approach.

**Acceptance Scenarios**:

1. **Given** a run where commands remain blocked or inconclusive, **When** Itertesting finishes analyzing that run, **Then** it records the reason each command was not verified and proposes or applies an improved next-run strategy.
2. **Given** a previous run with unsuccessful verification attempts, **When** Itertesting starts a new run, **Then** the new run references the prior result and attempts a materially improved setup, evidence source, or execution path.

---

### User Story 3 - Use Supplemental Setup Tools (Priority: P2)

A maintainer can allow Itertesting to use supplemental setup aids such as cheat-based unit provisioning so commands that depend on rare units, targets, or map state can still be behaviorally verified.

**Why this priority**: Many commands stay blocked because the right unit mix or target state is missing; explicit support for cheat-based setup increases verification reach.

**Independent Test**: Select commands that require uncommon units or hard-to-reach preconditions, run Itertesting with cheat-enabled setup allowed, and confirm the run report shows those setup actions and their effect on verification outcomes.

**Acceptance Scenarios**:

1. **Given** a command that requires units or targets not normally present, **When** Itertesting is allowed to use supplemental setup actions, **Then** the run report records the setup action used and the resulting verification outcome.
2. **Given** a run that used cheat-based setup, **When** a maintainer reviews the report, **Then** it is clear which observed outcomes relied on supplemental setup and which did not.

---

### Edge Cases

- What happens when a run produces no new verified commands despite multiple improvement attempts?
- How does the suite behave when a command cannot be behaviorally observed with the current evidence sources even after setup improvements?
- What happens when a prior run report is missing, incomplete, or incompatible with the next run?
- How does the suite report commands that require cheat-based setup but still fail to produce observable evidence?
- What happens when two runs start within the same second and would otherwise collide on report naming?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide an evolving verification suite named Itertesting for tracked commands.
- **FR-002**: The system MUST execute commands in a live environment and classify each command based on behaviorally observed evidence from the run.
- **FR-003**: The system MUST treat direct game-state evidence or similarly concrete live evidence as the basis for marking a command verified.
- **FR-003a**: The system MUST NOT mark a command verified from dispatcher acceptance, indirect inference, or manual promotion alone.
- **FR-004**: The system MUST record the result for every tracked command in each run, including verified, inconclusive, blocked, or failed outcomes.
- **FR-005**: The system MUST preserve one timestamped run bundle per run under `reports/itertesting/`, including `manifest.json` and `run-report.md`, using date-and-time values precise to the second.
- **FR-006**: The system MUST make each run report distinguish newly verified commands from commands that remain unverified.
- **FR-007**: When a command is not verified, the system MUST record why the attempt failed or remained inconclusive.
- **FR-008**: The system MUST use the result of a prior run to improve the next run rather than repeating the same unsuccessful attempt unchanged.
- **FR-009**: The system MUST define and record what improvement was made between one run and the next for commands that were not previously verified.
- **FR-010**: The system MUST support supplemental setup actions, including cheat-based unit provisioning, when those actions are needed to reach meaningful command preconditions.
- **FR-011**: The system MUST record when supplemental setup actions were used and which command outcomes depended on them.
- **FR-011a**: The system MUST distinguish cheat-assisted verified commands from naturally verified commands in each run report and in run-to-run summaries.
- **FR-011b**: The system MUST prefer natural verification attempts before escalating to cheat-assisted setup for a command, unless a maintainer explicitly overrides that priority.
- **FR-012**: The system MUST allow a maintainer to compare one Itertesting run with earlier runs to see whether verified coverage improved, regressed, or stalled.
- **FR-013**: The system MUST ensure a run report can be reviewed independently without requiring a maintainer to inspect raw engine output.
- **FR-014**: The system MUST prevent report filename collisions when multiple runs occur close together.
- **FR-015**: The system MUST keep iterating until a run completes with no available improvement actions or until a maintainer-defined stopping condition is reached.
- **FR-016**: The system MUST support a configurable maximum number of improvement runs and stop automatically when that limit is reached, even if some commands remain unverified.

### Key Entities *(include if feature involves data)*

- **Itertesting Run**: One complete verification attempt across the tracked command set, including the run timestamp, command outcomes, evidence summary, and run-to-run improvement notes.
- **Command Verification Record**: The per-command result within a run, including observed outcome, evidence summary, blocking reason if unverified, and whether supplemental setup was used.
- **Improvement Action**: A recorded change made for a subsequent run, such as using a different setup path, better target preparation, stronger evidence collection, or supplemental provisioning.
- **Run Report**: The reviewer-facing artifact that summarizes one Itertesting run and makes its outcomes understandable without raw logs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A maintainer can start Itertesting and receive a timestamped run report covering 100% of tracked commands in a single unattended run.
- **SC-002**: For every unverified command in a run, 100% of records include an explicit blocking, failure, or inconclusive reason.
- **SC-002a**: 100% of commands marked verified in a run include direct game-state evidence or command-specific live artifacts in the report.
- **SC-003**: Maintainers can identify from the report alone whether total verified coverage improved, regressed, or remained unchanged between consecutive runs.
- **SC-003a**: Maintainers can identify from the report alone how many commands were verified naturally versus with cheat-assisted setup in each run.
- **SC-004**: When improvement actions are available, a follow-up run documents at least one concrete change in setup, evidence gathering, or execution approach relative to the prior run.
- **SC-004a**: When a command moves from natural attempts to cheat-assisted attempts, the report explains that the escalation occurred because natural progress stalled.
- **SC-005**: Reports from repeated runs can be stored without naming collisions even when runs are launched within the same minute.

## Assumptions

- The tracked command set initially aligns with the existing AI command inventory already used by the project’s behavioral verification work.
- Existing live audit and behavioral harnesses provide enough baseline environment control to support iterative verification expansion.
- Supplemental setup actions, including cheat-based provisioning, are acceptable for verification so long as their use is clearly disclosed in reports.
- Verified coverage is allowed to include both natural and cheat-assisted results, provided the two are not merged into one unlabeled count.
- The default optimization goal is to maximize natural verification first and use cheat-assisted verification as a secondary path when natural attempts stop yielding progress.
- Dispatcher acceptance on its own is not sufficient proof of behavioral success.
- Some commands may remain unverified for a period because the current environment still lacks sufficient observability or setup paths.
- The default operating mode is unattended execution bounded by a maintainer-configured retry budget rather than endless reruns.
- The Itertesting reports are intended for maintainers and reviewers who need concise evidence summaries rather than raw engine traces.
