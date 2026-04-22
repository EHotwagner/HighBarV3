# Feature Specification: Build-Root Validation Completion

**Feature Branch**: `012-build-root-validation`  
**Created**: 2026-04-22  
**Status**: Draft  
**Input**: User description: "Create specs for the unfinished 011 completion work. The remaining gap is the final build-root rerun and completion validation work that could not be finished locally because the standard build-root validation environment was not ready and local validation mismatches prevented the remaining focused reruns from reaching the final checks. This is closure work that turns partial hardening into a runnable, repeatable completion suite."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run The Remaining Completion Checks From Standard Validation Entrypoints (Priority: P1)

As a maintainer, I need the remaining command-contract completion checks to run from the standard documented validation entrypoints so I can finish the 011 completion workflow without relying on ad hoc local workarounds.

**Why this priority**: The unfinished 011 work is blocked until maintainers can actually execute the final completion reruns from the standard validation environment.

**Independent Test**: This story is independently testable by preparing the standard build-root validation environment and confirming that the required completion checks can be discovered and executed through the documented build-root and repo-root entrypoints without environment-specific detours.

**Acceptance Scenarios**:

1. **Given** a properly prepared standard build-root validation environment, **When** the maintainer runs the required completion checks from the documented standard validation entrypoints, **Then** the remaining completion checks are discoverable and executable from those entrypoints.
2. **Given** a validation environment that previously stopped before the required checks could run, **When** the maintainer retries the documented completion flow, **Then** the flow reaches the required completion checks instead of failing early due to environment mismatch.
3. **Given** the remaining open completion work for 011, **When** the maintainer runs the standard build-root completion checks, **Then** the workflow yields explicit pass, fail, or blocker outcomes for those checks.

---

### User Story 2 - Complete The Final Hardening Reruns (Priority: P2)

As a maintainer, I need the remaining 011 completion reruns to execute successfully so I can verify whether any final fixes are still required before declaring command-contract hardening finished.

**Why this priority**: Once the validation environment is usable, the next highest-value outcome is completing the pending reruns and exposing any remaining failures in the documented completion workflow.

**Independent Test**: This story is independently testable by running the focused completion reruns, capturing their outputs, and confirming that any newly exposed failures are visible and actionable.

**Acceptance Scenarios**:

1. **Given** the focused completion reruns are available, **When** the maintainer runs them, **Then** the workflow records whether each remaining required validation step passes or fails.
2. **Given** the focused reruns expose one or more blocking failures, **When** the maintainer reviews the results, **Then** the failures are specific enough to guide the required follow-up fixes.
3. **Given** the focused reruns complete without blockers, **When** the maintainer reviews the results, **Then** the remaining 011 validation gap is reduced to the documented full-suite rerun.

---

### User Story 3 - Close 011 With A Repeatable Final Validation Pass (Priority: P3)

As a maintainer, I need the final 011 completion workflow to rerun cleanly after any fixes so I can prove that command-contract hardening is complete from standard project entrypoints.

**Why this priority**: The unfinished work only creates value when it closes 011 with a repeatable end-to-end validation result rather than another one-off local attempt.

**Independent Test**: This story is independently testable by rerunning the documented completion workflow after any required fixes and confirming that the final validation pass completes from standard entrypoints with all required results and artifacts.

**Acceptance Scenarios**:

1. **Given** any failures exposed by the focused reruns have been addressed, **When** the maintainer reruns the documented 011 completion workflow, **Then** the workflow completes from standard entrypoints and produces the required outcomes and artifacts.
2. **Given** the final rerun succeeds, **When** the maintainer reviews the results, **Then** the remaining 011 open tasks can be closed with evidence from the repeatable completion workflow.
3. **Given** the final rerun still exposes blockers, **When** the maintainer reviews the results, **Then** the workflow clearly shows that 011 is still incomplete and what must be resolved next.

### Edge Cases

- What happens when the standard build-root validation environment exists but still cannot reach the required completion checks?
- How does the workflow handle a validation environment that can run the completion checks but produces inconsistent results across reruns?
- What happens when the focused reruns pass but the final full-suite rerun still exposes a previously hidden blocker?
- How does the workflow report a blocker caused by validation-environment readiness rather than by hardening behavior itself?

If consecutive reruns produce inconsistent results, the workflow remains blocked until maintainers identify the variance source and reproduce a stable outcome from the same standard entrypoints.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a documented standard validation path for the remaining 011 completion checks, using build-root `ctest` for C++ validation and documented repo-root entrypoints for Python and headless validation.
- **FR-002**: The system MUST enable the remaining 011 focused completion reruns to execute from that documented standard validation path.
- **FR-003**: The system MUST allow maintainers to distinguish validation-environment blockers from hardening-behavior failures when running the remaining 011 completion checks.
- **FR-004**: The system MUST record explicit outcomes for the remaining focused completion reruns so maintainers can tell which required steps passed, failed, or remained blocked.
- **FR-005**: The system MUST keep any failures exposed by the focused reruns in scope until the documented completion workflow is rerun.
- **FR-006**: The system MUST support rerunning the documented 011 completion workflow after follow-up fixes without relying on private, one-off procedures.
- **FR-007**: The system MUST preserve the requirement that command-contract hardening is only considered complete after the documented completion workflow succeeds from standard entrypoints.
- **FR-008**: The system MUST ensure the final completion workflow produces the required validation outcomes and records needed to close the remaining 011 tasks.

### Key Entities *(include if feature involves data)*

- **Build-Root Validation Environment**: The standard project validation context used to discover and execute the remaining completion checks.
- **Focused Completion Rerun**: A rerun of the remaining pending 011 validation steps used to expose any final failures before the full-suite pass.
- **Environment Blocker**: A validation problem caused by entrypoint readiness or environment mismatch rather than by the hardening behavior under test.
- **Final Completion Pass**: The repeatable end-to-end validation result used to decide whether the remaining 011 tasks can be closed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Maintainers can run 100% of the remaining 011 focused completion reruns from the documented standard validation entrypoints.
- **SC-002**: The focused reruns produce explicit pass, fail, or blocker outcomes for every remaining required completion step instead of stopping silently before the checks begin.
- **SC-003**: Any validation-environment blocker encountered during the focused reruns is reported clearly enough that maintainers can distinguish it from a hardening-behavior failure on the first review.
- **SC-004**: After follow-up fixes, the documented 011 completion workflow can be rerun from standard entrypoints and yields all required validation results and artifacts needed to evaluate closure.
- **SC-005**: The remaining 011 open tasks can be closed only when the final rerun shows the documented completion workflow succeeding without unresolved blockers.

## Assumptions

- This feature is a follow-on closure feature for unfinished 011 work rather than a replacement for 011 itself.
- The intended users are maintainers who already rely on the project’s documented validation entrypoints to decide whether hardening work is complete.
- The main unfinished value is operational completion and repeatability, not new external behavior.
- The documented standard validation entrypoints are the correct authoritative surface for the remaining focused reruns.
- The final 011 closeout still depends on rerunning the documented completion workflow after any newly exposed failures are resolved.
