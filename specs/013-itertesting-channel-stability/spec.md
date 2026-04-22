# Feature Specification: Itertesting Channel Stability

**Feature Branch**: `[013-itertesting-channel-stability]`  
**Created**: 2026-04-22  
**Status**: Draft  
**Input**: User description: "fix  - The disconnect is likely tied to command-channel lifecycle or teardown after a small number of forwarded batches, not to overall simulation speed.
  - The fixture bootstrap is independently insufficient, so even with a stable channel the run would still be blocked on a subset of commands.
  - cmd-build-unit looks transport/timing-adjacent rather than a clean semantic regression, because the whole run collapses around the same channel
    interruption."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Keep Live Validation Running (Priority: P1)

A maintainer can run the live Itertesting closeout workflow without the validation session collapsing after only a few forwarded command batches.

**Why this priority**: The current failure mode stops the closeout workflow before maintainers can trust any command-level outcomes, so no later improvement work is dependable until the live validation session itself stays intact.

**Independent Test**: Can be fully tested by running the documented live Itertesting closeout command in a prepared environment and confirming the session does not stop because the command channel disconnects during dispatch.

**Acceptance Scenarios**:

1. **Given** a prepared live validation environment, **When** a maintainer runs the full live Itertesting closeout workflow, **Then** the session remains available long enough to evaluate command outcomes instead of stopping because the command channel disconnects during dispatch.
2. **Given** a live validation session that encounters a channel lifecycle problem, **When** the session stops, **Then** the maintainer receives a specific lifecycle outcome explaining what disconnected and when it happened.

---

### User Story 2 - Cover Required Fixtures Before Judging Behavior (Priority: P2)

A maintainer can rely on the live bootstrap to provide the fixtures needed for the intended validation surface, or to identify missing fixtures before commands are judged as behavioral failures.

**Why this priority**: Even a stable command channel will still produce blocked coverage if the live bootstrap does not prepare the required targets and unit classes for important command families.

**Independent Test**: Can be fully tested by running the live Itertesting workflow and confirming that commands needing specialized targets are either exercised with prepared fixtures or explicitly classified as fixture-blocked before transport or behavior is blamed.

**Acceptance Scenarios**:

1. **Given** a command that requires a specialized target or unit class, **When** the live validation workflow reaches that command, **Then** the run either provides the required fixture or records a specific fixture blocker instead of a generic failure.
2. **Given** a live validation summary, **When** a maintainer reviews the fixture section, **Then** it clearly lists which required fixture classes were provisioned, which were missing, and which commands were affected.

---

### User Story 3 - Distinguish Transport Instability From Command Behavior (Priority: P3)

A maintainer can tell whether a command such as `build_unit` failed because of transport instability or because the command behavior itself regressed.

**Why this priority**: Commands that fail during or immediately after channel collapse should not be treated as clean behavioral regressions, otherwise follow-up work will chase the wrong root cause.

**Independent Test**: Can be fully tested by rerunning the same live validation workflow and confirming that transport-adjacent failures are classified separately from true command-behavior regressions, especially for commands that previously oscillated between verified and failed outcomes.

**Acceptance Scenarios**:

1. **Given** a command outcome recorded during a transport interruption, **When** the maintainer reviews the validation evidence, **Then** the outcome is classified as transport-adjacent rather than as a clean command-behavior failure.
2. **Given** a command outcome recorded in a stable session, **When** the command fails to produce its expected effect, **Then** the maintainer receives a behavior-focused failure record instead of a transport-focused explanation.

### Edge Cases

- What happens when the command channel forwards some batches successfully and disconnects mid-session?
- How does the workflow behave when fixture coverage is only partially available for a command family?
- How are repeated reruns interpreted when a command alternates between verified, blocked, and timeout outcomes?
- What happens when the validation session is run at different simulation speeds but the underlying transport problem is unchanged?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The live validation workflow MUST keep the command channel available for the intended validation session or record a specific lifecycle blocker when that continuity is lost.
- **FR-002**: The validation evidence MUST identify the first point at which command-channel availability breaks down during a run.
- **FR-003**: The live bootstrap MUST provide the required fixture classes for the intended command coverage set or explicitly mark the affected commands as fixture-blocked before behavior is judged.
- **FR-004**: The workflow MUST distinguish fixture blockers from transport interruptions and from command-behavior failures in its evidence and closeout summaries.
- **FR-005**: The workflow MUST classify transport-adjacent command outcomes separately from clean behavioral regressions when a session is interrupted.
- **FR-006**: The workflow MUST preserve enough evidence for maintainers to compare repeated reruns of the same command and determine whether instability is transport-related or behavior-related.
- **FR-007**: A live closeout run MUST NOT be considered ready for normal Itertesting tuning when foundational blockers still prevent reliable command evaluation.
- **FR-008**: Changing simulation speed for a rerun via `HIGHBAR_STARTSCRIPT` pointing at a startscript variant with different `MinSpeed` and `MaxSpeed` values MUST NOT change the blocker interpretation when the same underlying command-channel interruption still occurs.

### Key Entities *(include if feature involves data)*

- **Live Validation Session**: A single end-to-end Itertesting run used to evaluate command outcomes, blocker state, and closeout readiness.
- **Command Channel Lifecycle Event**: A recorded state change showing when the command path becomes available, forwards work, degrades, or disconnects.
- **Fixture Provisioning Profile**: The set of targets, unit classes, and scenario resources made available to support live command evaluation.
- **Command Outcome Record**: The per-command result showing whether a command verified, failed, was blocked by missing fixtures, or was invalidated by transport instability.
- **Closeout Decision Record**: The summary decision that determines whether the run can continue into normal tuning or must stop for foundational repair.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a prepared validation environment, three consecutive live closeout reruns complete without stopping because the command channel disconnects during dispatch.
- **SC-002**: All commands in the intended live coverage surface are either exercised with the required fixtures or explicitly marked as fixture-blocked before command behavior is evaluated.
- **SC-003**: Commands affected by transport interruption are classified consistently as transport-adjacent across repeated reruns, with no ambiguous fallback to generic validation gaps.
- **SC-004**: Commands previously showing unstable outcomes, including `build_unit`, produce evidence that lets maintainers distinguish transport-related failure from behavior-related failure on first review.

## Assumptions

- Maintainers will continue to use the documented live Itertesting closeout workflow as the authoritative validation path.
- The existing live environment, map, and validation surface remain in scope; this feature improves reliability and interpretation rather than introducing a new workflow.
- Lua-only or otherwise non-observable commands remain outside direct live verification unless they already have accepted evidence rules.
- The goal is to make current closeout evidence trustworthy enough for maintainers to act on, not to expand the overall command catalog beyond the existing validation surface.
