# Feature Specification: Comprehensive Admin Channel Behavioral Control

**Feature Branch**: `020-admin-behavior-tests`  
**Created**: 2026-04-24  
**Status**: Draft  
**Input**: User description: "create and behaviorally test a comprehensive admin channel"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Prove Admin Actions Change the Running Match (Priority: P1)

An operator can use the admin channel during a live local match and receive proof that each accepted action changes the actual match state, not just an acknowledgement.

**Why this priority**: The admin channel is only useful if accepted commands produce observable game effects. This is the core gap identified by current testing.

**Independent Test**: Start a controlled live match, run one admin action at a time, and compare observed match state before and after each action.

**Acceptance Scenarios**:

1. **Given** a live match with the admin channel enabled and an operator identity, **When** the operator pauses the match, **Then** the match stops advancing and the admin result reports success.
2. **Given** a paused live match, **When** the operator resumes the match, **Then** the match advances again and the admin result reports success.
3. **Given** a live match running at normal speed, **When** the operator changes the speed to a valid faster value, **Then** observed match progression reflects the new speed and the admin result reports success.
4. **Given** a live match with a known team resource balance, **When** the operator grants resources to that team, **Then** the team's observable resource balance increases by the requested amount within the allowed tolerance.
5. **Given** a live match with a known enemy team and a valid unit type, **When** the operator spawns an enemy unit at a valid map position, **Then** a new enemy unit of that type appears at the requested position within the allowed tolerance.
6. **Given** a live match with an existing unit controlled by one team, **When** the operator gives that unit to another team, **Then** the unit remains present and its ownership changes to the target team.

---

### User Story 2 - Reject Unsafe or Invalid Admin Requests (Priority: P1)

An operator or test harness can confirm that invalid, unauthorized, stale, or unsafe admin requests are rejected before they alter the match.

**Why this priority**: Admin controls are privileged. Rejections must be as behaviorally reliable as successful actions to prevent accidental or unauthorized match mutation.

**Independent Test**: Submit invalid and unauthorized requests in a controlled live match and verify both the structured result and unchanged match state.

**Acceptance Scenarios**:

1. **Given** a caller without an admin-capable role, **When** the caller requests any mutating admin action, **Then** the request is rejected and no match state changes.
2. **Given** a speed change outside the allowed range, **When** the operator submits it, **Then** the request is rejected and match speed remains unchanged.
3. **Given** a resource grant for an unknown resource or invalid amount, **When** the operator submits it, **Then** the request is rejected and team resources remain unchanged.
4. **Given** a unit spawn with an unknown unit type, invalid team, or off-map position, **When** the operator submits it, **Then** the request is rejected and no new unit appears.
5. **Given** an existing admin lease held by one caller, **When** a different caller submits a conflicting request without an allowed override, **Then** the request is rejected and the original lease remains effective.

---

### User Story 3 - Make Behavioral Evidence Easy to Review (Priority: P2)

A developer can run a single behavioral admin-channel test suite and get clear evidence for each control, including before/after observations and failure details.

**Why this priority**: The admin channel spans live match state and privileged operations. Failures need actionable evidence so regressions can be fixed without reconstructing the scenario manually.

**Independent Test**: Run the admin behavioral suite and review the generated result summary for each action category.

**Acceptance Scenarios**:

1. **Given** the behavioral suite completes successfully, **When** the developer reviews the result, **Then** each admin action category shows the request, expected observation, actual observation, and pass status.
2. **Given** any action fails or produces no observable state change, **When** the suite exits, **Then** the failure identifies the action, the expected state transition, the actual state observed, and where to find match logs.
3. **Given** a prerequisite such as the local game runtime is unavailable, **When** the suite starts, **Then** it exits with a clear prerequisite failure rather than reporting a behavioral regression.

---

### User Story 4 - Discover Supported Admin Controls Consistently (Priority: P3)

A client can discover which admin controls are available in the current run and only attempt controls that the run says it supports.

**Why this priority**: Discovery prevents client tools from assuming controls that are disabled or not supported in the current run mode.

**Independent Test**: Query capabilities for multiple run modes and verify advertised controls match executable behavior.

**Acceptance Scenarios**:

1. **Given** admin controls are enabled, **When** a client asks for capabilities, **Then** the response lists the roles, controls, and feature flags that are actually executable in that run.
2. **Given** admin controls are disabled or restricted by run mode, **When** a client asks for capabilities, **Then** the response makes the restriction clear and mutating controls are rejected consistently.

### Edge Cases

- Admin action succeeds at the channel level but no matching state change is observed before the timeout.
- Pause stops frame progression, which can make follow-up checks time out unless resume behavior is handled explicitly.
- Speed changes may have small timing variance; tests must use tolerance windows rather than exact wall-clock equality.
- Resource names, team identifiers, unit types, and map positions may be unavailable or invalid for a selected fixture.
- Spawned or transferred units may appear one or more frames after the admin action result.
- A lease may expire during a long-running behavioral test and change conflict outcomes.
- The match runtime or viewer may be unavailable on a developer machine; this must be reported separately from action failure.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide admin controls for pause, resume, match speed, team resource grants, enemy unit spawning, and existing unit ownership transfer.
- **FR-002**: Every successful mutating admin action MUST produce an observable match-state change that corresponds to the requested action.
- **FR-003**: The system MUST report a successful admin action only after the action has been accepted for application to the running match.
- **FR-004**: The system MUST reject unauthorized admin callers before any match state changes.
- **FR-005**: The system MUST reject invalid action values, including out-of-range speed, invalid resource grants, invalid teams, invalid unit types, invalid positions, invalid unit transfer targets, from-team mismatches, unknown unit ids, and transfer requests disabled by the current run mode.
- **FR-006**: The system MUST preserve or update admin leases consistently so conflicting callers cannot silently override active controls.
- **FR-007**: The system MUST make admin capabilities discoverable for the current run, including whether each advertised control can actually be executed.
- **FR-008**: The system MUST record enough evidence for each admin action to compare the requested change, the response status, and the observed match-state result.
- **FR-009**: The behavioral suite MUST cover both successful and rejected admin actions for all supported mutating controls.
- **FR-010**: The behavioral suite MUST fail when an admin action reports success but the expected state change is not observed within the defined timeout.
- **FR-011**: The behavioral suite MUST distinguish prerequisite failures from behavioral failures.
- **FR-012**: The behavioral suite MUST leave the match in a usable state after pause and speed tests by resuming play and restoring a normal speed before continuing or exiting.

### Key Entities *(include if feature involves data)*

- **Admin Caller**: A client identity with a declared role used to decide whether privileged controls are allowed.
- **Admin Action**: A requested privileged operation such as pause, resume, speed change, resource grant, unit spawn, or unit transfer.
- **Admin Result**: The structured outcome of an admin action, including status, issues, lease details, and the match position associated with the result.
- **Admin Capability Set**: The controls, roles, and feature flags advertised for the current run.
- **Observed Match State**: The before/after evidence used to prove whether a requested admin action changed the running match.
- **Behavioral Evidence Record**: A per-action record containing request details, expected outcome, observed outcome, and relevant diagnostics.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a controlled local live match, 100% of supported admin controls produce the expected observable state change within 10 seconds of a successful action result.
- **SC-002**: 100% of invalid or unauthorized admin requests in the behavioral suite are rejected without any corresponding match-state mutation.
- **SC-003**: A developer can run the complete admin behavioral suite and receive a pass/fail summary for all action categories in under 3 minutes on a prepared local environment.
- **SC-004**: Every behavioral failure includes the action name, expected observation, actual observation, and log location.
- **SC-005**: Capability discovery matches executable behavior for all advertised admin controls in the tested run mode.
- **SC-006**: The suite can be repeated three times consecutively on the same prepared environment with no leftover pause, speed, lease, resource, or spawned-unit state causing false failures.

## Assumptions

- The first comprehensive version targets controlled local live matches rather than remote multiplayer or public production matches.
- The behavioral suite may use a fixed fixture map, known teams, known resources, and known unit types to keep expected observations deterministic.
- "Enemy units" means units owned by the opposing team in the fixture match.
- "Give units" means transferring an existing unit from one team to another, distinct from spawning a new unit.
- Valid speed, resource, unit, team, and map-position boundaries are defined by the current run's rules and advertised capabilities where available.
- The suite should treat unavailable local runtime prerequisites as setup failures, not product regressions.
