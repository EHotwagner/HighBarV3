# Feature Specification: BAR Live Run Viewer

**Feature Branch**: `018-live-run-viewer`  
**Created**: 2026-04-23  
**Status**: Draft  
**Input**: User description: "create the option to watch th run with the real game viewer of bar."

## Clarifications

### Session 2026-04-23

- Q: How should watch access be surfaced to the maintainer? → A: Automatically launch BAR's normal graphical game client directly, without going through a lobby, when watch mode is requested, with a comprehensive watch configuration and sensible defaults: windowed at 1920x1080 with mouse not captured.
- Q: Where should comprehensive watch-mode settings live? → A: Use one watch option plus an optional structured config reference or profile for detailed settings.
- Q: How should attach-later selection behave when no run reference is provided? → A: Auto-attach only when exactly one watchable run exists; otherwise require explicit run selection.
- Q: What should happen if BAR viewer launch fails for a requested watch? → A: Treat viewer launch failure as a run failure when watch mode was requested.
- Q: When should watch-mode readiness be validated? → A: Verify viewer prerequisites and launch readiness before the live run begins; abort before live execution if watch cannot be opened.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Watch a live run in BAR (Priority: P1)

As a maintainer running a live HighBar validation run, I want to open the same run in BAR's real game viewer so I can directly observe fixture setup, movement, combat, and failure conditions instead of relying only on logs and report artifacts.

**Why this priority**: Direct observation is the fastest way to understand why a live run passed, stalled, or failed, and it materially improves diagnosis during the existing maintainer review loop.

**Independent Test**: Launch a prepared live run with watch mode enabled and confirm the maintainer can see that exact run in BAR's viewer while the run still completes and produces its normal artifacts.

**Acceptance Scenarios**:

1. **Given** a viewer-capable live BAR environment, **When** the maintainer starts a run with watch mode enabled, **Then** the run becomes viewable in BAR's native game viewer as the same run being evaluated.
2. **Given** watch mode is requested, **When** BAR viewer prerequisites or launch readiness checks fail before start, **Then** the system aborts before live execution and reports the viewer-readiness failure for that run request.
3. **Given** a watched run is in progress, **When** the maintainer views it, **Then** the run continues to collect its normal evidence and finish under the same run identity.

---

### User Story 2 - Open the correct active run after launch (Priority: P2)

As a maintainer, I want to open a specific active run after it has already started so I can attach the BAR viewer from run context instead of only at launch time.

**Why this priority**: Maintainers may notice a suspicious run only after it is already underway, and they still need a reliable way to watch that exact run without ambiguity.

**Independent Test**: Start two compatible live runs, request viewing by explicit run reference and from a context with exactly one compatible active run, and confirm the viewer attaches to the intended run each time.

**Acceptance Scenarios**:

1. **Given** an active watchable run exists, **When** the maintainer requests to watch that run by its run reference, **Then** the system opens or presents access to the correct BAR viewer target for that run.
2. **Given** multiple active watchable runs exist, **When** the maintainer selects one run to watch, **Then** the viewer attaches to the selected run and not to another active run.

---

### User Story 3 - Receive a clear reason when watching is unavailable (Priority: P3)

As a maintainer, I want an explicit explanation when a run cannot be watched so I know whether the problem is the environment, the run mode, or the run's lifecycle state.

**Why this priority**: A failed or unsupported watch attempt should not create another diagnosis problem; the maintainer needs a clear next step instead of silent failure.

**Independent Test**: Attempt to watch incompatible runs and unavailable environments, then confirm each attempt returns a user-readable reason tied to the requested run.

**Acceptance Scenarios**:

1. **Given** a run that is not compatible with live viewing, **When** the maintainer requests watch mode, **Then** the system explains why live viewing is unavailable for that run.
2. **Given** a watched run has already ended before the viewer attaches, **When** the maintainer tries to open it, **Then** the system explains that live viewing has expired and points the maintainer to the remaining run artifacts.

### Edge Cases

- Watch mode is requested on a host that can execute live runs but does not have BAR's full game viewer available.
- BAR's viewer process fails to launch or initialize after watch mode was requested.
- BAR's viewer prerequisites fail validation before live execution starts.
- A run ends, crashes, or is cancelled before the viewer can attach.
- Multiple watchable runs are active at the same time and the maintainer must choose the correct one.
- Watch mode is requested for a skipped-live, synthetic, or otherwise non-live run that has no BAR viewer target.
- The viewer disconnects during a run but the run itself continues and still needs complete artifacts.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow a maintainer to opt into watch mode when starting a compatible live run.
- **FR-002**: The system MUST associate watch mode with the exact run identifier and any parent campaign context for the watched run.
- **FR-003**: The system MUST automatically launch BAR's real game viewer for a watch-enabled compatible live run in a non-controlling spectator context.
- **FR-004**: The system MUST preserve the existing run execution, evidence collection, and artifact generation behavior for watched runs except where watch mode explicitly requires BAR viewer launch as a gating condition.
- **FR-005**: The system MUST expose viewer availability status for each requested watched run, including whether viewing is pending, available, unavailable, or expired.
- **FR-006**: The system MUST let maintainers open or retrieve viewer access for an already active compatible run by explicit run reference.
- **FR-007**: The system MUST provide a user-readable reason when a requested run cannot be watched because of run mode, environment readiness, or run lifecycle state.
- **FR-008**: The system MUST record in user-facing run output whether watch mode was requested and whether viewer access became available.
- **FR-009**: The system MUST ensure that viewing a run does not grant control over the run or alter the run's in-game behavior beyond the explicit failure policy for required viewer launch.
- **FR-010**: The system MUST prevent ambiguity when multiple watchable runs are active by requiring or presenting enough run context for the maintainer to choose the correct run.
- **FR-011**: The system MUST provide a comprehensive watch-mode configuration surface with sensible defaults, including a default viewer launch of a 1920x1080 windowed spectator session with mouse capture disabled.
- **FR-012**: The system MUST keep the run launch flow to a single watch-mode option plus an optional structured configuration reference or profile for detailed viewer settings.
- **FR-013**: The system MUST auto-attach to an already active run only when exactly one compatible watchable run exists in context; otherwise it MUST require an explicit run selection or reference before launching the viewer.
- **FR-014**: If watch mode was requested and BAR's viewer cannot be launched for the targeted run, the system MUST mark the run as failed and record the viewer-launch reason in user-facing output and run artifacts.
- **FR-015**: If watch mode was requested, the system MUST validate BAR viewer prerequisites and launch readiness before live execution starts, and it MUST abort before live execution with a user-readable failure reason when readiness validation fails.

### Key Entities *(include if feature involves data)*

- **Watched Run Session**: A live run that has been marked as viewable, including its run identifier, campaign context, watch request state, lifecycle state, and viewer availability state.
- **Viewer Access Record**: The maintainer-facing watch details for one run, including whether viewer access is pending, available, unavailable, attached, or expired, plus the reason for the current state.
- **Watch Request**: A maintainer action asking to watch a specific run, including when the request was made, which run reference it targeted, whether the request relied on single-run auto-selection, and an optional structured viewer configuration reference or profile.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A maintainer can enable live viewing for a compatible run with no more than one additional option beyond the current run launch flow.
- **SC-002**: On prepared viewer-capable hosts, at least 95% of watch-enabled live runs expose working BAR viewer access within 30 seconds of run start.
- **SC-003**: 100% of watch requests for non-watchable runs return an explicit user-readable reason tied to the requested run within 10 seconds of the request.
- **SC-004**: In multi-run validation, maintainers attach to the intended active run in 100% of tested watch requests without cross-run attachment.
- **SC-005**: Launching a run without watch mode requires no additional operator steps compared with the current unattended workflow.

## Assumptions

- This feature is intended for maintainer-operated live validation workflows, not for player-facing public spectating.
- The first release covers observing active live runs; generating archival replay packages for older completed runs is out of scope.
- BAR's real game viewer is only available on hosts that already have the required BAR client assets and viewer prerequisites.
- Watch-mode requests are expected to perform viewer-readiness validation before any live execution begins.
- Existing run identifiers and run artifact directories remain the source of truth for run identity and diagnosis.
