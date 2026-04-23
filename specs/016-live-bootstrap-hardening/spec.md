# Feature Specification: Live Bootstrap Hardening

**Feature Branch**: `[016-live-bootstrap-hardening]`  
**Created**: 2026-04-23  
**Status**: Draft  
**Input**: User description: "Natural prepared live bootstrap is resource-starved before the first commander build. Callback relay diagnostics are not stable across long failure paths. tests/headless/behavioral-build.sh still uses the old env-var def-id path instead of runtime callback resolution."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start Bootstrap From a Viable Live State (Priority: P1)

As a maintainer running prepared live closeout, I want bootstrap to begin from a state that can actually support the first commander build so the run does not fail immediately because the environment has no practical resource path.

**Why this priority**: If the first commander build starts from a resource-starved state, every later provisioning step is blocked behind an invalid assumption about the prepared live scenario.

**Independent Test**: Can be fully tested by running prepared live closeout from the standard prepared scenario and confirming that the first commander build either starts successfully or fails early with an explicit bootstrap-readiness blocker instead of timing out later as if the fixture path were healthy.

**Acceptance Scenarios**:

1. **Given** prepared live closeout starts from a state with enough effective resources for the first commander build, **When** bootstrap begins, **Then** the workflow proceeds into natural commander-driven progression without reporting an immediate resource-starvation blocker.
2. **Given** prepared live closeout starts from a state that cannot support the first commander build, **When** bootstrap readiness is evaluated, **Then** the run reports an explicit bootstrap-readiness failure before relying on downstream build timeouts as the primary signal.
3. **Given** the standard prepared scenario cannot naturally satisfy the first commander build, **When** the workflow uses an approved maintainer-visible readiness path to make bootstrap viable, **Then** the run bundle records that readiness path explicitly.

---

### User Story 2 - Preserve Failure Diagnostics Through Long Bootstrap Failures (Priority: P2)

As a maintainer investigating a failed prepared live run, I want callback-derived diagnostics to remain available throughout long failure paths so I can still inspect what the live environment could do after bootstrap has already started going wrong.

**Why this priority**: Once bootstrap fails in a long-running way, unstable diagnostics leave the maintainer without trustworthy evidence for whether the failure was due to resource starvation, missing capability, or relay loss.

**Independent Test**: Can be fully tested by forcing a prepared live bootstrap failure that lasts beyond the first step and confirming that the final run bundle still contains callback-derived diagnostic evidence instead of losing it when relay reachability degrades.

**Acceptance Scenarios**:

1. **Given** bootstrap remains in a failed or blocked state for an extended period, **When** the maintainer reviews the finished run bundle, **Then** callback-derived diagnostics are still present for late-stage failure analysis.
2. **Given** callback reachability degrades after bootstrap has already started, **When** the workflow records failure evidence, **Then** previously required diagnostics remain available from the run bundle.
3. **Given** callback-derived diagnostics cannot be refreshed late in the run, **When** the workflow finishes, **Then** the run bundle makes clear whether diagnostics were preserved from earlier capture or were genuinely unavailable.

---

### User Story 3 - Keep Standalone Build Verification Aligned With Live Runtime Resolution (Priority: P3)

As a maintainer using the standalone build verification probe, I want it to resolve required build prerequisites from the live runtime instead of a manual injected identifier so the probe remains a trustworthy reproduction tool in the current environment.

**Why this priority**: A maintainer probe that still depends on manual injected identifiers no longer reflects how prepared live closeout resolves its prerequisites, so failures and reproductions diverge.

**Independent Test**: Can be fully tested by running the standalone build verification probe in a prepared live environment without manual def-id injection and confirming that it resolves its build prerequisite from the live runtime path used by the main workflow.

**Acceptance Scenarios**:

1. **Given** the standalone build verification probe runs in a prepared live environment with runtime callback resolution available, **When** it selects the build target prerequisite, **Then** it resolves that prerequisite from the live runtime without requiring a manual def-id environment override.
2. **Given** runtime callback resolution is unavailable to the standalone build verification probe, **When** the probe starts, **Then** it exits with an explicit runtime-resolution blocker rather than a stale manual override message.
3. **Given** the main prepared live workflow and the standalone build verification probe run against the same live environment, **When** both resolve the build prerequisite, **Then** they agree on the selected live prerequisite identity.

### Edge Cases

- Prepared live closeout begins with effectively zero usable metal income even though the scenario nominally looks initialized.
- Bootstrap readiness is viable for the first build but collapses before later commander-driven progression completes.
- Callback-derived diagnostics are captured early, but the relay becomes unreachable before the run finishes.
- Callback-derived diagnostics were never captured before reachability degraded, and the run must distinguish that from ordinary late failure evidence.
- The standalone build verification probe runs in an environment where runtime callback resolution is present but returns no matching build prerequisite.
- The standalone build verification probe resolves a prerequisite that differs from a stale manually injected identifier used in older workflows.
- A maintainer-visible readiness path is used to make bootstrap viable; the run must not present that as ordinary natural progression.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Prepared live closeout MUST verify that the bootstrap starting state is viable for the first commander build before treating downstream fixture progression as naturally available.
- **FR-002**: If the prepared live starting state is not viable for the first commander build, the workflow MUST report an explicit bootstrap-readiness blocker instead of relying on later build timeouts as the primary diagnosis.
- **FR-003**: The workflow MUST provide a supported seeded bootstrap-readiness path that prevents the first commander build from starting in a resource-starved state.
- **FR-004**: If the seeded bootstrap-readiness path differs from ordinary natural progression, the run bundle MUST identify that difference explicitly.
- **FR-005**: Callback-derived diagnostics required for maintainer failure analysis MUST remain available for the full prepared live closeout window, either through continued reachability or preserved earlier capture.
- **FR-006**: Long bootstrap failure paths MUST continue to produce stable diagnostic evidence that distinguishes relay loss, capability absence, and ordinary bootstrap failure.
- **FR-007**: Loss of late callback reachability MUST NOT erase previously captured callback-derived diagnostics needed for run review.
- **FR-008**: The standalone build verification probe MUST resolve its required build prerequisite through the same runtime callback-resolution model used by prepared live closeout.
- **FR-009**: The standalone build verification probe MUST NOT require a manual def-id environment override as its normal prerequisite path.
- **FR-010**: If runtime callback resolution is unavailable or incomplete for the standalone build verification probe, the probe MUST fail with an explicit runtime-resolution blocker.
- **FR-011**: Prepared live closeout reporting MUST distinguish bootstrap-readiness blockers, callback-diagnostic availability failures, prerequisite-resolution failures, and command-behavior failures.
- **FR-012**: Hardening these three failure surfaces MUST NOT regress otherwise healthy prepared live closeout runs.

### Key Entities *(include if feature involves data)*

- **Bootstrap Readiness State**: The maintainer-visible determination of whether prepared live closeout can realistically begin commander-driven progression.
- **Seeded Bootstrap Readiness Path**: The explicit non-natural readiness state (`seeded_ready`) used to make the first commander build viable during prepared live validation when ordinary prepared-state readiness is insufficient.
- **Callback Diagnostic Snapshot**: The evidence captured from callback-derived inspection that supports failure classification during and after bootstrap.
- **Runtime Prerequisite Resolution**: The authoritative live process for determining the prerequisite identity required by a maintainer diagnostic or bootstrap step.
- **Standalone Build Verification Probe**: The maintainer-facing build diagnostic that must stay aligned with the runtime prerequisite-resolution model used by prepared live closeout.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In three consecutive prepared live validation runs, the first commander build is not blocked solely by an unclassified resource-starved starting state.
- **SC-002**: When prepared live closeout starts from a non-viable state, 100% of validation runs report a bootstrap-readiness blocker before the first commander-build timeout becomes the primary failure signal.
- **SC-003**: In validation runs that force long bootstrap failures, maintainers can review callback-derived diagnostic evidence in the final run bundle in 100% of cases.
- **SC-004**: The standalone build verification probe completes prerequisite resolution without manual def-id injection in 100% of prepared live environments where runtime callback resolution is available.
- **SC-005**: In validation runs where both the main workflow and the standalone build verification probe resolve the same build prerequisite, they agree on the live prerequisite identity in 100% of cases.
- **SC-006**: Three consecutive otherwise healthy prepared live validation runs complete without introducing a new callback-diagnostic availability blocker.

## Assumptions

- These defects are follow-up scope from the transport-provisioning work and should be solved without reopening unrelated fixture or command-behavior questions.
- Prepared live closeout remains the authoritative maintainer workflow for validating bootstrap and fixture availability.
- Runtime callback resolution is the authoritative source for live prerequisite identity whenever the environment exposes it.
- Any non-natural bootstrap-readiness path used to prevent initial resource starvation is acceptable only if it is explicit in maintainer reporting and remains bounded to prepared live validation.
