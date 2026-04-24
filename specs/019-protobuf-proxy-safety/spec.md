# Feature Specification: Non-Python Client Protobuf And Proxy Safety

**Feature Branch**: `019-protobuf-proxy-safety`  
**Created**: 2026-04-24  
**Status**: Draft  
**Input**: User description: "create specs for reports/2026-04-24-02h04min-non-python-client-protobuf-proxy-safety-design.md"

## Clarifications

### Session 2026-04-24

- Q: In strict mode, how should the proxy handle command submissions that omit the new correlation and/or state-basis fields? → A: Strict mode rejects submissions missing either correlation data or state-basis.
- Q: When a command batch contains a mix of valid commands and validation, conflict, stale, or capacity issues, should any commands be accepted? → A: Command batches are atomic: any validation, conflict, stale, or capacity issue rejects the entire batch.
- Q: How should conflicting admin controls such as pause or speed be resolved when another controller already owns that control? → A: Single-owner lease: conflicting admin actions are rejected until explicit release or heartbeat expiry.
- Q: What qualifies as a safe completion signal before a new immediate order may replace an in-flight command? → A: Safe completion means the proxy has observed the unit idle or released in a later state update.
- Q: What authorization model should the separate admin control surface use? → A: Admin actions require run-scoped role credentials configured for that match or test run.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Diagnose Invalid Client Commands (Priority: P1)

As a non-Python client developer, I need every rejected command submission to identify the failing batch, command, field, reason, and retry guidance so I can correct my client without reading Python helper behavior or interpreting logs.

**Why this priority**: This is the highest-value safety improvement because generated clients will otherwise see only aggregate rejection counts and cannot reliably self-correct.

**Independent Test**: Submit representative invalid command batches from a generated client and verify that each rejection returns a stable issue code, a precise location, a human-readable detail, and a retry hint.

**Acceptance Scenarios**:

1. **Given** a client submits a batch containing an empty command, **When** the proxy validates the batch, **Then** the batch is rejected with an issue that identifies the command index and empty-command reason.
2. **Given** a client submits a command for a target unit that differs from the batch target, **When** validation runs, **Then** the response identifies the target mismatch and the affected field.

---

### User Story 2 - Stop Unsafe Commands Before Simulation Impact (Priority: P1)

As a maintainer running live or headless scenarios, I need malformed, unsafe, unauthorized, stale, or impossible commands rejected before they can affect the simulation so integration bugs fail early and deterministically.

**Why this priority**: Shared proxy enforcement protects every current and future client and prevents language-specific helpers from being the only safety boundary.

**Independent Test**: Run validation and live dispatch scenarios for unsafe commands and verify they are rejected before simulation impact, or reported as dispatch failures if the world changes after initial acceptance.

**Acceptance Scenarios**:

1. **Given** a client commands a unit it does not own, **When** the command is submitted, **Then** the command is rejected before it reaches simulation execution.
2. **Given** a builder is asked to build a unit type it cannot construct, **When** validation checks current capabilities, **Then** the batch is rejected with a constructibility issue.
3. **Given** a target unit dies after acceptance but before execution, **When** dispatch is attempted, **Then** the system emits a dispatch result identifying that the accepted command could not be applied.
4. **Given** a client acts on stale world state, **When** the submission includes an outdated state basis, **Then** the response marks the command as stale and tells the client to retry from a fresh snapshot.

---

### User Story 3 - Separate Admin Controls From AI Intent (Priority: P2)

As an operator or test harness owner, I need pause, speed, cheat, lifecycle, and similar global controls handled through a separately authorized control surface so normal AI clients cannot accidentally or silently change the whole match.

**Why this priority**: Broader client support increases the risk that privileged test controls leak into normal strategy clients unless they have a distinct authorization and audit model.

**Independent Test**: Attempt privileged actions from normal AI credentials and from authorized operator credentials, then verify denial, acceptance, and audit outcomes match the run mode and role.

**Acceptance Scenarios**:

1. **Given** a normal AI client requests a global pause, **When** the request is submitted through the normal command path, **Then** it is rejected with a reason indicating that the action requires the admin control path.
2. **Given** an authorized test harness requests a resource grant in a run mode that allows cheats, **When** the action is validated and executed, **Then** the action is accepted and an audit event records who requested it, when, and why.
3. **Given** a natural verification run forbids cheats, **When** any client requests cheat-based unit or resource changes, **Then** the request is rejected before simulation impact and the rejection is auditable.

---

### User Story 4 - Discover Capabilities Before Submitting Commands (Priority: P3)

As a client implementer, I need a single discoverable description of legal command capabilities, resource identifiers, target limits, and validation rules so generated clients can adapt without hard-coding Python-specific conventions.

**Why this priority**: Capability discovery reduces integration mistakes, but it builds on the diagnostic and enforcement guarantees from the higher-priority stories.

**Independent Test**: Request capability information for a known unit and map state, then use it to validate both a legal command and an illegal command without changing simulation state.

**Acceptance Scenarios**:

1. **Given** a client requests current command capabilities, **When** the system responds, **Then** the response includes supported command types, legal options, map limits, resource identifiers, schema version, and feature flags.
2. **Given** a client dry-runs a command batch, **When** the batch is valid, **Then** the response confirms validity without enqueuing or dispatching the command.
3. **Given** a client dry-runs a command batch that uses an unsupported command type, **When** validation runs, **Then** the response identifies the unsupported command and no simulation state changes.

### Edge Cases

- Older clients submit commands without new correlation or state-basis fields; strict mode rejects these submissions, while compatibility or warning-only mode may report would-reject diagnostics without changing behavior.
- A client retries the same batch after a transient failure or reconnect.
- The command queue becomes full after part of a multi-command submission has been evaluated; the entire batch is rejected without partial enqueue or dispatch.
- A unit is valid during initial validation but dies, changes owner, or changes capability before execution.
- A client sends repeated immediate orders that would replace an in-flight build or other long-running intent before the proxy has observed the unit idle or released in a later state update.
- Two clients or tools attempt to control pause, speed, or another global admin setting at the same time; the active single-owner lease rejects conflicting actions until explicit release or heartbeat expiry.
- An admin controller disconnects while holding control of pause or speed; its lease expires after heartbeat loss and the expiry is auditable.
- A run mode disables cheats, but an authorized role attempts a cheat action anyway.
- A generated client sends an unknown option, enum-like value, resource id, unit definition, team id, or non-finite position.
- A compatibility mode allows legacy privileged commands, but strict mode is enabled for normal verification.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST return per-batch validation results for command submissions, while preserving existing aggregate acceptance and rejection counts for compatibility.
- **FR-002**: Each rejected batch or command MUST include a stable issue code, batch sequence or client correlation identifier, command index when applicable, affected field path when applicable, detail text, and retry guidance.
- **FR-003**: Clients MUST attach stable correlation data to command batches in strict mode so acknowledgements, dispatch results, logs, and state updates can be matched to the original client intent.
- **FR-004**: Clients MUST be able to validate a command batch without enqueuing, dispatching, or otherwise changing simulation state.
- **FR-005**: The system MUST reject command batches with no commands, too many commands, missing command intent, multiple command intents, missing required targets, invalid target identifiers, or target drift between the batch and command.
- **FR-006**: The system MUST reject malformed scalar values, including non-finite positions, out-of-range radii, invalid counts, invalid option masks, invalid enum-like values, overlong strings, and invalid text encoding.
- **FR-007**: The system MUST reject commands for units that are not live, not owned by the client, not currently known when visibility is required, or not capable of the requested action.
- **FR-008**: The system MUST reject build, repair, reclaim, capture, transport, toggle, stockpile, and custom commands when the target, capability, parameter count, or parameter range is not legal for the acting unit.
- **FR-009**: The system MUST reject strict-mode submissions that omit client-provided ordering or world-state basis, and MUST use those fields to detect stale or duplicate command submissions.
- **FR-010**: The system MUST prevent accidental replacement of an in-flight immediate order unless the client explicitly requests replacement or the proxy has observed the unit idle or released in a later state update.
- **FR-011**: The system MUST reject command batches atomically when any command has a validation issue, stale basis, conflict, or queue-capacity failure, and MUST distinguish those outcomes with separate machine-readable statuses.
- **FR-012**: The system MUST emit dispatch results when an accepted command cannot be applied later because simulation state changed before execution.
- **FR-013**: The system MUST expose discoverable command capabilities, including supported command types, legal options, unit build options, queue state, map limits, resource identifiers, schema version, and feature flags.
- **FR-014**: Privileged global controls MUST require a separate admin/operator authorization path using run-scoped role credentials configured for that match or test run, rather than the normal AI command path.
- **FR-015**: The admin control path MUST support capability discovery, dry-run validation, execution, and structured results for pause, speed, cheat, lifecycle, and future test-harness actions.
- **FR-016**: Admin actions MUST be rejected when the caller lacks the required role, the action is disabled by configuration, the run mode forbids the action, the action is stale, the target is invalid, or another controller owns an active single-owner lease for the conflicting control.
- **FR-017**: Every accepted or rejected admin action, explicit control release, and lease expiry MUST produce an audit record with caller credential identity for caller-initiated events, role, action type, frame or state reference, result, and reason.
- **FR-018**: Legacy privileged commands on the normal AI path MUST be allowed only through an explicit compatibility setting and MUST be rejected in strict mode with a clear admin-required issue code.
- **FR-019**: Maintainers MUST be able to run the new validation rules in a warning-only rollout mode before enabling strict rejection for updated clients.
- **FR-020**: The feature MUST include conformance evidence showing that generated clients outside the Python helper layer receive the same validation outcomes for the same command fixtures.

### Key Entities *(include if feature involves data)*

- **Command Batch**: A client-submitted group of one or more commands for a target unit, including ordering, correlation, command list, state basis required in strict mode, and conflict policy.
- **Command Intent**: A single unit-level action such as build, move, attack, repair, reclaim, transport, toggle, stop, or custom action.
- **Validation Result**: The atomic outcome for a batch before simulation impact, including accepted, rejected, stale, conflicted, or capacity-related status.
- **Command Issue**: A machine-readable diagnostic describing a specific validation or dispatch problem, its location, its human detail, and retry guidance.
- **Dispatch Result**: Evidence that an accepted command was applied or skipped during simulation execution, including any later failure reason.
- **Capability Profile**: The discoverable set of legal commands, options, identifiers, map limits, schema version, feature flags, and current unit capabilities available to a client.
- **Admin Action**: A privileged request authorized by run-scoped role credentials that affects the global run or bypasses normal gameplay constraints, such as pause, speed, cheat, lifecycle, or test-harness control; conflict-prone controls use a single-owner lease.
- **Admin Audit Event**: A durable record of an accepted or rejected admin action, explicit control release, or lease expiry, including caller credential identity for caller-initiated events, role, requested action, result, frame or state reference, and reason.
- **Order State**: Per-unit tracking of active intent, recent command ordering, observed idle or release state, and conflict state used to prevent accidental command replacement.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of covered malformed command fixtures identify the failing batch or command and return a stable issue code.
- **SC-002**: 95% of common client integration mistakes in the conformance suite include retry guidance that directs the client to never retry, retry from a fresh snapshot, retry after idle, or retry after queue capacity changes.
- **SC-003**: Unsafe command fixtures for wrong ownership, dead units, invalid positions, unsupported options, impossible builds, and stale state are rejected before simulation impact in all strict-mode validation runs.
- **SC-004**: Dispatch-time failures for accepted commands are visible to clients within one state update cycle after the failed execution attempt.
- **SC-005**: Normal AI credentials are denied 100% of privileged pause, speed, cheat, and lifecycle actions in strict mode.
- **SC-006**: Every admin action attempted during validation produces an audit record with enough information for a maintainer to identify caller, action, result, and reason in under 1 minute.
- **SC-007**: At least two independently generated client implementations produce equivalent validation outcomes for the shared fixture set before strict mode is enabled by default.
- **SC-008**: Warning-only rollout identifies would-reject events without changing simulation behavior, and maintainers can compare warning counts across at least three prepared live or headless runs.

## Assumptions

- The primary users are HighBar maintainers, non-Python client authors, test harness owners, and operator/viewer tooling authors.
- Existing Python clients and helpers remain supported during a compatibility period.
- The shared command contract is the authoritative source for generated clients; Python helper conventions are not considered sufficient documentation for non-Python clients.
- Strategy quality remains a client concern; proxy enforcement is limited to structural validity, authorization, safety, objective legality, ordering, and deterministic conflict checks.
- Strict rejection can be introduced incrementally after a warning-only period to reduce false positives for existing clients.
- Privileged controls are useful for tests and operations, but are outside normal AI strategy authority.
