# Feature Specification: Itertesting Retry Tuning

**Feature Branch**: `008-itertesting-retry-tuning`  
**Created**: 2026-04-22  
**Status**: Draft  
**Input**: User description: "create specs to improve the itertest . maybe speed 100 is too much?"

## Clarifications

### Session 2026-04-22

- Q: What should Itertesting optimize first when maximizing verified commands? → A: Maximize naturally verified count first, then use cheat-assisted mode only after natural stalls.
- Q: Should Itertesting enforce a global hard cap on improvement runs even if a higher value is configured? → A: Yes, enforce a hard cap at 10 improvement runs.
- Q: What minimum verified command count should this feature target in live Itertesting campaigns? → A: Target at least 20 verified commands.
- Q: How should the “at least 20 verified commands” target treat non-directly-observable commands? → A: Measure target against directly verifiable commands and track non-observable commands separately.
- Q: What maximum wall-clock runtime should a successful campaign target? → A: Max 15 minutes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Prevent Runaway Campaigns (Priority: P1)

A maintainer starts Itertesting and expects the campaign to stop after meaningful attempts instead of burning time on large retry counts with no additional value.

**Why this priority**: Unbounded or overly large retry loops are the main operational pain and directly affect developer time.

**Independent Test**: Run a campaign with no meaningful coverage improvement opportunities and confirm it exits early with a clear stop reason before exhausting an overly large retry budget.

**Acceptance Scenarios**:

1. **Given** a campaign where no new command coverage is gained after repeated attempts, **When** Itertesting evaluates run-to-run progress, **Then** it stops early and reports that further retries were not useful.
2. **Given** a maintainer configures a high retry budget, **When** progress stalls, **Then** the campaign uses stall guardrails and does not consume the full configured budget.

---

### User Story 2 - Tune Retry Intensity by Intent (Priority: P2)

A maintainer can select a lightweight, standard, or deep retry intensity that matches the purpose of the run (quick validation vs deeper investigation).

**Why this priority**: Operators need predictable control over runtime/cost without manually guessing retry values each time.

**Independent Test**: Run three campaigns with different intensity settings and verify each follows the expected retry envelope and stop behavior.

**Acceptance Scenarios**:

1. **Given** a quick validation campaign, **When** the run is configured for low retry intensity, **Then** the campaign finishes in a small bounded number of iterations.
2. **Given** a deep investigation campaign, **When** higher intensity is selected, **Then** the campaign allows additional attempts but still enforces stall-based stopping.

---

### User Story 3 - Keep Improvement Guidance Reusable (Priority: P3)

A maintainer wants each campaign to build on prior improvement guidance so repeated campaigns can start from known best next actions.

**Why this priority**: Re-learning the same retry strategy wastes runs and slows coverage gains.

**Independent Test**: Run two campaigns back-to-back and verify the second campaign reuses saved improvement guidance from the first campaign.

**Acceptance Scenarios**:

1. **Given** prior campaign guidance exists for specific commands, **When** a new campaign starts, **Then** those instructions are loaded and applied as the initial retry guidance.
2. **Given** a command’s guidance changes after a new run, **When** results are saved, **Then** the instruction store records the new revision and status.

### Edge Cases

- What happens when the configured retry budget is extremely high but no progress is possible after the first run?
- How does the campaign behave when one run improves coverage and the next run regresses coverage?
- What happens when natural verification stalls but cheat-assisted escalation is disabled?
- How does the workflow report incomplete runs caused by live session interruptions?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Itertesting MUST apply conservative default retry behavior that avoids long unattended campaigns when progress is not being made.
- **FR-002**: Itertesting MUST allow maintainers to explicitly choose retry intensity levels for quick, standard, and deep campaigns.
- **FR-003**: Itertesting MUST stop early when run-to-run coverage progress has stalled according to defined guardrails, even if configured retry budget remains.
- **FR-004**: Itertesting MUST report a clear campaign stop reason for every campaign completion.
- **FR-005**: Itertesting MUST persist per-command improvement guidance in reusable instruction files and load them at the start of future campaigns.
- **FR-006**: Itertesting MUST prioritize maximizing naturally verified command coverage before attempting cheat-assisted escalation.
- **FR-007**: Itertesting MUST track and report natural and cheat-assisted verification progress separately when computing campaign outcomes.
- **FR-008**: Itertesting MUST surface warning feedback when configured retry intensity is likely disproportionate to observed improvement rate.
- **FR-009**: Itertesting MUST keep campaign behavior predictable by ensuring retry governance rules are applied consistently across all runs in the same campaign.
- **FR-010**: Itertesting MUST enforce a global maximum of 10 improvement runs per campaign even when a higher retry value is configured.
- **FR-011**: Itertesting MUST provide retry governance and improvement behavior that can achieve at least 20 verified commands in live campaigns under the reference environment assumptions.
- **FR-012**: Itertesting MUST compute primary coverage targets against the directly verifiable command subset while separately reporting non-directly-observable commands.
- **FR-013**: Itertesting MUST enforce campaign governance that keeps successful goal-reaching campaigns within a 15-minute wall-clock runtime target in the reference environment.

### Key Entities *(include if feature involves data)*

- **Campaign Retry Policy**: Maintainer-selected intensity and retry guardrails that determine allowed iterations and early-stop behavior.
- **Campaign Stop Decision**: Structured result describing why the campaign ended (budget exhausted, improvement achieved, or stalled).
- **Reusable Improvement Instruction**: Versioned command-level guidance reused across campaigns and updated as evidence changes.
- **Run Progress Snapshot**: Per-run summary used for run-to-run comparisons and stall detection.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of campaigns finish with an explicit stop reason that is visible in the run report.
- **SC-002**: In stalled campaigns, Itertesting stops before consuming more than 20% of a high configured retry budget once stall conditions are met.
- **SC-003**: Default retry behavior completes campaigns in a bounded number of iterations suitable for routine maintainer checks.
- **SC-004**: In back-to-back campaigns over the same command set, reusable instruction files are loaded and revised correctly for all commands with new guidance.
- **SC-005**: No campaign executes more than 10 improvement runs regardless of configured retry input.
- **SC-006**: Live Itertesting campaigns reach at least 20 verified commands when executed under the documented reference environment.
- **SC-007**: Coverage reports clearly separate directly verifiable command progress from non-directly-observable command tracking in 100% of campaign outputs.
- **SC-008**: In the reference environment, campaigns that achieve the 20-command target complete within 15 minutes in at least 90% of runs.

## Assumptions

- Maintainers continue to run Itertesting through the existing repo-local workflow and review generated report artifacts after each campaign.
- The command inventory remains stable during a single campaign execution window.
- Natural verification remains the default verification path, with cheat-assisted escalation treated as an explicit and separately tracked mode.
- A campaign may terminate early for live-environment interruptions, and this should be reported distinctly from normal stall/budget outcomes.
