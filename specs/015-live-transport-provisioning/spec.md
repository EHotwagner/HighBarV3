# Feature Specification: Live Transport Provisioning

**Feature Branch**: `[015-live-transport-provisioning]`  
**Created**: 2026-04-22  
**Status**: Draft  
**Input**: User description: "create specs for reports/014-transport-provisioning-status-2026-04-22.md"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Provision a Usable Transport Fixture (Priority: P1)

As a maintainer running prepared live Itertesting, I want the workflow to ensure a usable transport is available before transport-dependent commands are exercised so load and unload coverage is no longer blocked by a missing foundational fixture.

**Why this priority**: The latest validated run on 2026-04-22 reduced the foundational gap to one remaining real blocker: `transport_unit`. Until that fixture is available, the five transport-dependent commands cannot be judged on live behavior.

**Independent Test**: Can be fully tested by running a prepared live Itertesting closeout pass and confirming that transport-dependent commands proceed past the fixture gate when the environment can provide a valid transport.

**Acceptance Scenarios**:

1. **Given** transport-dependent commands are in scope and no usable transport is currently available, **When** the workflow prepares live fixtures, **Then** it provisions a usable transport before evaluating those commands.
2. **Given** a usable transport already exists in the live environment, **When** the workflow reaches transport-dependent commands, **Then** it reuses that transport instead of reporting the fixture as missing.
3. **Given** no usable transport can be obtained in the run environment, **When** transport-dependent commands are evaluated, **Then** only those commands are blocked and the missing fixture is reported explicitly as `transport_unit`.

---

### User Story 2 - Keep Transport Coverage Usable Throughout the Run (Priority: P2)

As a maintainer, I want the workflow to keep transport coverage usable even if the first transport is lost or an alternative supported transport type is the only one available so later load and unload commands remain trustworthy.

**Why this priority**: Transport coverage is not complete if the workflow only recognizes one narrow transport profile or if it fails after the first transport becomes unusable mid-run.

**Independent Test**: Can be tested by validating that the workflow accepts any supported transport variant present in the environment and can refresh or replace the fixture when the current transport becomes unusable.

**Acceptance Scenarios**:

1. **Given** the live environment offers more than one supported transport variant, **When** the workflow searches for or creates a transport fixture, **Then** any supported variant may satisfy `transport_unit`.
2. **Given** a previously usable transport is destroyed, consumed, or otherwise becomes unusable before later commands run, **When** additional transport-dependent commands remain, **Then** the workflow refreshes or replaces the transport fixture before continuing.
3. **Given** a transport is present but cannot actually carry the selected payload for the pending command, **When** the workflow prepares transport coverage, **Then** it must obtain a compatible transport-payload combination or block only the affected commands with an explicit transport-related reason.

---

### User Story 3 - Preserve Trustworthy Reporting and Run Stability (Priority: P3)

As a maintainer reviewing the run bundle, I want transport provisioning to appear in the existing closeout evidence with clear lifecycle reporting and without regressing channel stability so I can trust that the remaining blocker was actually removed instead of merely hidden.

**Why this priority**: The report shows the remaining issue is real transport provisioning, not misclassification. Closing it must preserve the channel health and reporting clarity already achieved by 014.

**Independent Test**: Can be tested by reviewing the run bundle from repeated prepared live runs and confirming that transport lifecycle status is visible while channel health remains healthy.

**Acceptance Scenarios**:

1. **Given** a prepared live run completes, **When** the maintainer reviews the run bundle, **Then** the bundle shows whether transport coverage was discovered, newly provisioned, refreshed, replaced, or still missing.
2. **Given** transport coverage is achieved during the run, **When** the workflow finishes, **Then** the run keeps healthy channel status and does not introduce a new transport-interruption blocker.
3. **Given** transport coverage still cannot be achieved, **When** the run bundle is reviewed, **Then** the report distinguishes transport fixture unavailability from payload availability, evidence gaps, and unrelated behavioral failures.

### Edge Cases

- A supported transport already exists before fixture preparation begins.
- The only available transport is a different supported variant than the one most commonly used in prior runs.
- A transport is created successfully but is destroyed or moves out of usable state before later unload commands execute.
- A transport exists but cannot carry the selected payload unit for the pending scenario.
- The environment can provide a payload fixture but not a transport fixture.
- The workflow spends time attempting transport preparation but must stop within the normal closeout budget if no usable transport can be obtained.
- An exceptional fallback path is used to provide transport coverage; the run bundle must make that visible instead of presenting it as ordinary provisioning.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The live Itertesting workflow MUST ensure a usable `transport_unit` fixture is available whenever transport-dependent commands are included in the intended command surface.
- **FR-002**: The workflow MUST first detect and reuse an already-usable transport fixture before concluding that transport coverage is missing.
- **FR-003**: When no usable transport is already available, the workflow MUST attempt to provision one through the ordinary live fixture path before classifying transport-dependent commands as blocked.
  Ordinary live fixture path means reuse of an already-live transport or creation through the existing client-mode coordinator and behavioral-coverage workflow using runtime unit-def resolution and normal command submission; it does not include cheat-assisted spawning or any exceptional fallback path.
- **FR-004**: The workflow MUST determine transport eligibility from the current run environment rather than assuming only one exact transport profile can satisfy `transport_unit`.
- **FR-005**: The workflow MUST treat any supported transport variant that can satisfy the intended load and unload behavior as valid coverage for `transport_unit`.
- **FR-006**: Before a transport-dependent command is evaluated, the workflow MUST confirm that the selected transport is alive, usable, and compatible with the selected payload for that command.
- **FR-007**: If a previously selected transport becomes unusable before later transport-dependent commands run, the workflow MUST refresh or replace the transport fixture before continuing with those commands.
- **FR-008**: If no usable transport can be discovered or provisioned after the workflow completes its transport preparation attempts, only the transport-dependent commands MUST be marked fixture-blocked, and the blocking fixture MUST be reported explicitly as `transport_unit`.
- **FR-009**: The run bundle MUST report the lifecycle of transport coverage, including whether the transport was preexisting, newly provisioned, refreshed, replaced, or still missing.
- **FR-010**: The run bundle MUST identify the exact commands affected by missing or unusable transport coverage.
- **FR-011**: Transport provisioning MUST preserve the existing separation between transport fixture failures, payload availability, evidence gaps, and behavioral failures.
- **FR-012**: Achieving transport coverage MUST NOT regress prepared live closeout channel health or introduce a new transport-interruption blocker in otherwise healthy runs.
- **FR-013**: If the workflow uses an exceptional or fallback path to obtain transport coverage, that path MUST be explicitly identified in the run bundle rather than reported as ordinary live provisioning.

### Key Entities *(include if feature involves data)*

- **Transport Fixture**: The reusable live transport capability required for `cmd-load-onto`, `cmd-load-units`, `cmd-load-units-area`, `cmd-unload-unit`, and `cmd-unload-units-area`.
- **Transport Candidate**: A preexisting or newly obtained live transport instance that may satisfy transport coverage if it is usable and compatible with the intended payload.
- **Transport Provisioning Result**: The per-run record showing whether transport coverage was discovered, provisioned, refreshed, replaced, missing, or obtained through an exceptional fallback.
- **Transport-Dependent Command Set**: The specific load and unload commands whose trustworthy evaluation depends on `transport_unit`.
- **Transport Lifecycle Event**: A reportable change in transport coverage state such as discovery, creation, refresh, replacement, loss, or failed acquisition.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Three consecutive prepared live Itertesting runs complete with healthy channel status and no transport-interruption blocker while transport provisioning is enabled.
- **SC-002**: In prepared live runs where the environment can supply a supported transport, the run bundle reports `transport_unit` as provisioned, refreshed, replaced, or preexisting rather than missing.
- **SC-003**: The five transport-dependent commands identified on 2026-04-22 (`cmd-load-onto`, `cmd-load-units`, `cmd-load-units-area`, `cmd-unload-unit`, `cmd-unload-units-area`) are no longer blocked solely by missing `transport_unit` in prepared live runs where transport coverage is achievable.
- **SC-004**: When transport coverage is not achievable, 100% of blocked transport-dependent commands are labeled with an explicit transport fixture cause, and no unrelated commands are added to that blocker set.
- **SC-005**: Maintainers can determine from a single run bundle whether transport coverage was discovered, newly provisioned, refreshed, replaced, or obtained through an exceptional fallback, without consulting separate bootstrap logic.
- **SC-006**: Prepared live closeout runtime with transport provisioning remains within 10% of the 2026-04-22 prepared-run baseline used for Feature 014 comparisons.
- **SC-007**: Validation demonstrates that at least two supported transport variants in the current game data can satisfy transport coverage when available in the run environment.

## Assumptions

- The payload fixture work completed under Feature 014 remains valid and does not need to be redesigned in this feature.
- The existing Itertesting run bundle remains the authoritative maintainer-facing surface for fixture and contract-health review.
- This feature is scoped to eliminating the remaining transport fixture blocker and does not expand to solve unrelated predicate or evidence-gap findings from the same runs.
- The prepared live workflow remains the primary path; any exceptional fallback used to obtain transport coverage is secondary and must stay explicit in reporting.
- The current live command registry already describes how transport-dependent commands should behave once a valid transport and payload are available.
