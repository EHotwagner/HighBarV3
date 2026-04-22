# Feature Specification: Live Itertesting Hardening

**Feature Branch**: `009-live-itertest-hardening`  
**Created**: 2026-04-22  
**Status**: Draft  
**Input**: User description: "strengthening the live bootstrap/startscript so more commands have valid fixtures, making the plugin command channel survive the whole run, tightening per-arm live predicates/timeouts for commands like fight, move_unit, and build_unit."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Provision Valid Live Fixtures (Priority: P1)

A maintainer can start the live Itertesting workflow and have materially more directly verifiable commands begin from valid prerequisite state instead of failing immediately because the bootstrap did not create the right units, targets, resources, or map context.

**Why this priority**: Fixture gaps are currently the largest source of avoidable non-attempts and block coverage growth before retry logic or evidence tuning can help.

**Independent Test**: Run the default live Itertesting workflow with bounded retries disabled and confirm that more directly verifiable commands move from precondition-blocked states into attempted outcomes with valid live evidence, inconclusive evidence, or genuine behavioral failures.

**Acceptance Scenarios**:

1. **Given** commands whose current live execution depends on missing units, targets, or resources, **When** the maintainer starts the live workflow, **Then** the run begins with a fixture state that satisfies the documented prerequisites for the supported command set.
2. **Given** a command whose prerequisite fixture still cannot be created in the reference environment, **When** the run completes, **Then** the report identifies the missing prerequisite class instead of treating the command as an unexplained timeout or transport failure.

---

### User Story 2 - Keep The Command Channel Alive (Priority: P2)

A maintainer can let a live Itertesting run finish without the plugin command channel dropping mid-run and turning many command outcomes into false failures.

**Why this priority**: Transport instability invalidates otherwise useful live runs and masks real command behavior behind infrastructure noise.

**Independent Test**: Run the default live Itertesting workflow end to end and confirm the command channel remains available for scheduled command attempts through normal completion or, if it degrades, the workflow exits with an explicit transport-level outcome instead of silently continuing with corrupted results.

**Acceptance Scenarios**:

1. **Given** a bounded live Itertesting run, **When** the maintainer executes the workflow, **Then** the plugin command channel stays available through the scheduled command attempt window and the campaign ends normally without requiring a manual restart.
2. **Given** the command channel degrades during a run, **When** the workflow evaluates run outcomes, **Then** it records a dedicated transport interruption outcome and avoids classifying unrelated commands as ordinary behavioral failures.

---

### User Story 3 - Tighten Arm-Specific Live Verification (Priority: P3)

A maintainer can trust that high-value arms such as `fight`, `move_unit`, and `build_unit` are judged with verification timing and predicates that match their real live behavior instead of generic windows that cause avoidable false negatives.

**Why this priority**: Once fixture readiness and transport stability improve, arm-specific evidence quality becomes the next major limiter on verified coverage.

**Independent Test**: Run live Itertesting against arms with known timing- or predicate-sensitive behavior and confirm those arms are classified from their real observable effects rather than generic timeout-driven failure.

**Acceptance Scenarios**:

1. **Given** an arm whose expected observable effect appears later or differently than the generic default, **When** the live workflow evaluates it, **Then** the command uses a verification rule that matches its expected live behavior.
2. **Given** a live run where `fight`, `move_unit`, or `build_unit` produces its expected observable effect, **When** the report is generated, **Then** that arm is marked verified or meaningfully inconclusive instead of failing under an avoidable generic timeout.

### Edge Cases

- What happens when the live bootstrap can satisfy only part of the supported command set and some commands still lack prerequisite fixtures?
- What happens when the plugin command channel drops after some commands have already completed but before the remaining commands are attempted?
- How does the workflow classify commands whose observable effect occurs outside the default evidence window but still within a reasonable live run duration?
- What happens when one command mutates or destroys a shared fixture needed by a later command in the same run?
- How does the workflow report commands that remain non-directly-observable even after fixture and predicate hardening?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The live Itertesting workflow MUST prepare a fixture-ready starting state for the supported directly verifiable command set in the reference environment.
- **FR-002**: The live workflow MUST expand the default bootstrap/start scenario so more commands begin with valid units, targets, resources, and map context without manual operator intervention during the run.
- **FR-003**: The system MUST distinguish commands that were not attempted because prerequisite fixtures were unavailable from commands that were attempted and failed behaviorally.
- **FR-004**: The plugin command channel MUST remain usable for the full scheduled command attempt window of a normal bounded live run.
- **FR-005**: If the plugin command channel degrades, the workflow MUST record a dedicated transport interruption outcome and stop or recover deterministically rather than silently continuing with ambiguous results.
- **FR-006**: The system MUST NOT classify transport interruption as an ordinary timeout, missing fixture, or behavioral command failure.
- **FR-007**: The live workflow MUST support command-specific verification rules for arms whose observable behavior is not well represented by generic evidence timing or predicates.
- **FR-008**: Commands such as `fight`, `move_unit`, and `build_unit` MUST use live verification rules that reflect their expected effect timing and evidence shape in the reference environment.
- **FR-009**: Every non-verified directly verifiable command in a live run MUST be assigned one primary cause category: missing fixture, transport interruption, predicate or evidence gap, or genuine behavioral failure.
- **FR-010**: Campaign reports MUST make it clear whether a non-verified outcome came from fixture readiness, channel stability, or arm-specific evidence limitations.
- **FR-011**: Hardening changes MUST preserve compatibility with the existing maintainer entrypoint and bounded live campaign workflow.
- **FR-012**: The hardened workflow MUST increase the number of directly verifiable commands that can be validly attempted in the reference live environment without requiring manual mid-run restarts.
- **FR-013**: Commands that already verify reliably in the current live workflow MUST continue to verify unless the report identifies a newly introduced prerequisite or transport issue.
- **FR-014**: Campaign outputs MUST continue to separate natural verification, cheat-assisted setup, non-directly-observable commands, and transport-level failures instead of collapsing them into one unlabeled result.

### Key Entities *(include if feature involves data)*

- **Live Fixture Profile**: The prepared starting state for a live run, including the prerequisite units, targets, resources, and map conditions needed to attempt supported commands.
- **Channel Health Outcome**: The run-level status that describes whether the plugin command channel stayed healthy, degraded, recovered, or forced an interrupted result.
- **Arm Verification Rule**: The command-specific definition of what observable effect counts as verified, inconclusive, or failed for a live arm.
- **Failure Cause Classification**: The reviewer-facing reason assigned to each non-verified command so maintainers can tell fixture gaps, transport defects, evidence gaps, and real command failures apart.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the reference live environment, at least 20 directly verifiable commands begin from valid prerequisite state and are attempted in a default bounded campaign.
- **SC-002**: In at least 90% of reference bounded live campaigns, the plugin command channel remains available until scheduled command attempts complete or the campaign ends with an explicit transport interruption result.
- **SC-003**: For `fight`, `move_unit`, and `build_unit`, at least 80% of runs that produce the expected observable effect are classified as verified or meaningfully inconclusive rather than generic timeout failures.
- **SC-004**: 100% of non-verified directly verifiable command records identify one primary cause category from fixture readiness, transport interruption, predicate or evidence gap, or behavioral failure.
- **SC-005**: Maintainers can complete a default live Itertesting run without manual coordinator or engine restarts in at least 90% of reference runs.
- **SC-006**: Already-reliable live verified commands retain their prior verified status in 100% of regression validation runs unless a report explicitly attributes a new blocking cause.

## Assumptions

- The reference environment remains the existing live headless Itertesting workflow and its current command inventory.
- Existing retry governance, reporting structure, and cheat-escalation policy remain in place; this feature hardens the live path rather than redefining campaign governance.
- Some commands will remain non-directly-observable and are therefore out of scope for direct verification gains from this feature alone.
- Maintainers continue to expect unattended runs; manual mid-run intervention is considered a workflow failure rather than a supported operating mode.
- The feature is intended to improve prerequisite readiness, transport stability, and evidence accuracy for current commands, not to introduce new command families.
