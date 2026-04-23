# Feature Specification: Live Bootstrap Hardening

**Feature Branch**: `[016-live-bootstrap-hardening]`  
**Created**: 2026-04-23  
**Status**: Draft  
**Input**: User description: "On this live runtime, nearly all callback categories are unsupported. Runtime prerequisite name resolution still works, but commander build-option diagnostics do not, and map metal-spot data is available only through the session-start map payload rather than the callback path."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start Bootstrap From a Viable Live State (Priority: P1)

As a maintainer running prepared live closeout, I want bootstrap to begin from a state that can actually support the first commander build so the run does not fail immediately because the environment has no practical resource path.

**Why this priority**: If the first commander build starts from a resource-starved state, every later provisioning step is blocked behind an invalid assumption about the prepared live scenario.

**Independent Test**: Can be fully tested by running prepared live closeout from the standard prepared scenario and confirming that the first commander build either starts successfully or fails early with an explicit bootstrap-readiness blocker instead of timing out later as if the fixture path were healthy.

**Acceptance Scenarios**:

1. **Given** prepared live closeout starts from a state with enough effective resources for the first commander build, **When** bootstrap begins, **Then** the workflow proceeds into natural commander-driven progression without reporting an immediate readiness blocker.
2. **Given** prepared live closeout starts from a state that cannot support the first commander build, **When** bootstrap readiness is evaluated, **Then** the run reports an explicit bootstrap-readiness failure before relying on downstream build timeouts as the primary signal.
3. **Given** the standard prepared scenario cannot naturally satisfy the first commander build, **When** the workflow uses an approved maintainer-visible readiness path to make bootstrap viable, **Then** the run bundle records that non-natural readiness path explicitly.

---

### User Story 2 - Make Runtime Capability Limits Explicit in Live Diagnostics (Priority: P2)

As a maintainer investigating a failed prepared live run, I want the diagnostic bundle to show which live inspection capabilities are actually supported and which are unavailable on this runtime so I can distinguish a real behavior failure from a missing runtime capability.

**Why this priority**: The current runtime only exposes a narrow inspection surface. If the workflow treats unsupported live inspection paths as ordinary diagnostic failures, maintainers lose trust in the report and misclassify the defect.

**Independent Test**: Can be fully tested by running prepared live closeout on a runtime with limited inspection support and confirming that the final report preserves successful prerequisite lookups, marks deeper unsupported diagnostics as capability-limited, and still uses the session-start map payload when available.

**Acceptance Scenarios**:

1. **Given** the live runtime supports prerequisite name resolution but not deeper unit, build-option, economy, or environment inspection, **When** diagnostics are collected, **Then** the run bundle records that distinction explicitly instead of reporting a generic callback failure.
2. **Given** deeper live inspection is unsupported but prerequisite name resolution succeeded earlier, **When** the workflow finishes, **Then** the run bundle preserves the successful early evidence rather than discarding it because later inspection could not continue.
3. **Given** callback-based map inspection is unavailable but the session-start map payload includes metal-spot data, **When** the workflow needs map-derived targeting or diagnostics, **Then** it uses the session-start map payload and does not report map data as unavailable.

---

### User Story 3 - Keep Standalone Build Verification Aligned With Supported Runtime Sources (Priority: P3)

As a maintainer using the standalone build verification probe, I want it to resolve prerequisites and map data through the same supported runtime sources as the main workflow so the probe remains a trustworthy reproduction tool in the current environment.

**Why this priority**: A standalone probe that assumes unsupported live inspection paths or manual injected identifiers will drift from the main workflow and stop being credible as a reproduction aid.

**Independent Test**: Can be fully tested by running the standalone build verification probe in a prepared live environment without manual prerequisite injection and confirming that it resolves the target definition from the live runtime, uses the session-start map payload for metal-spot targeting, and reports unsupported deeper diagnostics as capability limits rather than ambiguous failures.

**Acceptance Scenarios**:

1. **Given** the standalone build verification probe runs in a prepared live environment with supported prerequisite name-resolution capability, **When** it selects the build target prerequisite, **Then** it resolves that prerequisite from the live runtime without requiring a manual identifier override.
2. **Given** callback-based map inspection is unavailable but the session-start map payload contains metal spots, **When** the standalone probe chooses a build position, **Then** it uses the session-start map payload rather than failing on the unsupported callback path.
3. **Given** deeper commander or build-option inspection is unsupported on the live runtime, **When** the standalone probe records its outcome, **Then** it reports an explicit capability limitation rather than implying that the workflow itself lost correctness.

### Edge Cases

- Prepared live closeout begins with effectively zero usable metal income even though the scenario nominally looks initialized.
- The runtime supports only the narrow prerequisite name-resolution path and rejects most other live inspection requests.
- Early prerequisite lookup succeeds, but later deeper diagnostics are unavailable because the runtime never exposed those capabilities.
- Callback-based map inspection is unavailable and the session-start map payload is also missing or incomplete.
- The standalone build verification probe resolves the right prerequisite name but still cannot validate construction because the selected site is not buildable at dispatch time.
- The runtime capability surface changes between environments, and the reporting layer must not assume every host exposes the same diagnostics.
- A late transport loss happens after capability-limited diagnostics were already recorded, and the report must distinguish transport loss from unsupported runtime inspection.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Prepared live closeout MUST verify that the bootstrap starting state is viable for the first commander build before treating downstream fixture progression as naturally available.
- **FR-002**: If the prepared live starting state is not viable for the first commander build, the workflow MUST report an explicit bootstrap-readiness blocker instead of relying on later build timeouts as the primary diagnosis.
- **FR-003**: The workflow MUST provide a supported maintainer-visible readiness path that prevents the first commander build from starting in a resource-starved state when natural readiness is unavailable.
- **FR-004**: The live diagnostic bundle MUST record which runtime inspection capabilities are supported, which are unsupported, and which evidence sources remain usable despite those limits.
- **FR-005**: Runtime prerequisite name resolution MUST continue to work on hosts that expose only the narrow supported inspection surface required for definition enumeration and naming.
- **FR-006**: The workflow MUST preserve successful early prerequisite-resolution evidence even when later diagnostic steps are unavailable because the runtime does not support deeper inspection.
- **FR-007**: Commander, build-option, economy, and environment diagnostics that depend on unsupported runtime inspection capabilities MUST be reported as capability-limited rather than as generic workflow or transport failures.
- **FR-008**: When callback-based map inspection is unsupported but the session-start map payload includes metal-spot data, the workflow MUST use that payload as the authoritative source for map-derived targeting and diagnostics.
- **FR-009**: Unsupported callback-based map inspection alone MUST NOT cause the workflow to classify map data as unavailable if equivalent session-start map data is already present.
- **FR-010**: Prepared live closeout and the standalone build verification probe MUST share the same supported-source selection rules for prerequisite resolution, map-derived targeting, and capability-limited diagnostic reporting.
- **FR-011**: Reporting MUST distinguish bootstrap-readiness blockers, unsupported runtime inspection capability, late transport loss, missing session-start map data, prerequisite-resolution failure, and command-behavior failure.
- **FR-012**: Hardening for this callback-limited runtime MUST NOT regress otherwise healthy prepared live runs on hosts that expose a broader diagnostic surface.

### Key Entities *(include if feature involves data)*

- **Bootstrap Readiness State**: The maintainer-visible determination of whether prepared live closeout can realistically begin commander-driven progression.
- **Seeded Bootstrap Readiness Path**: The explicit non-natural readiness state used to make the first commander build viable during prepared live validation when ordinary prepared-state readiness is insufficient.
- **Runtime Capability Profile**: The reportable description of which live inspection paths are supported on the current host and which are unavailable.
- **Prerequisite Resolution Record**: The preserved evidence showing whether live prerequisite name resolution succeeded, failed, or was blocked by missing runtime capability.
- **Session-Start Map Payload**: The one-time map information available at session start that can still provide metal-spot data when callback-based map inspection is unsupported.
- **Standalone Build Verification Probe Outcome**: The maintainer-facing result of the build diagnostic, including prerequisite resolution status, map-data source, and any capability limitations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In three consecutive prepared live validation runs, the first commander build is not blocked solely by an unclassified resource-starved starting state.
- **SC-002**: In 100% of validation runs on callback-limited hosts, the diagnostic bundle distinguishes unsupported runtime inspection from ordinary workflow failure.
- **SC-003**: In 100% of validation runs where prerequisite name resolution succeeds before deeper inspection fails, the final report still includes the successful prerequisite-resolution evidence.
- **SC-004**: In 100% of prepared live environments where the session-start map payload includes metal spots, the standalone build verification probe completes map-derived targeting without requiring callback-based map inspection.
- **SC-005**: In 100% of prepared live environments where supported runtime prerequisite resolution is available, the main workflow and the standalone build verification probe agree on the resolved prerequisite identity.
- **SC-006**: Three consecutive otherwise healthy prepared live validation runs on broader-capability hosts complete without introducing a new capability-reporting or map-data regression.

## Assumptions

- Prepared live closeout remains the authoritative maintainer workflow for validating bootstrap readiness and live command behavior.
- The current target runtime exposes only a narrow live inspection surface for prerequisite definition lookup, while most deeper inspection categories are unsupported.
- Session-start map payload data remains available even when callback-based map inspection is unsupported, and that payload is sufficient for metal-spot targeting when present.
- Any maintainer-visible readiness path used to prevent initial resource starvation must stay explicit in reporting and bounded to prepared live validation.
- Hosts with broader inspection support must continue to benefit from richer diagnostics without being constrained to the callback-limited baseline.
