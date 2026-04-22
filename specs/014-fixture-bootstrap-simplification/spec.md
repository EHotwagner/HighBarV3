# Feature Specification: Fixture Bootstrap Simplification

**Feature Branch**: `[014-fixture-bootstrap-simplification]`  
**Created**: 2026-04-22  
**Status**: Draft  
**Input**: User description: "create specs to work on this feature, fixtures and simplify bootstrap"

## Clarifications

### Session 2026-04-22

- Q: Should 014 stay fixture-only, add richer classification only, or also repair the identified local helper parity gaps? → A: Expand 014 to include both richer classification/reporting and direct repair of the identified local helper parity gaps in this same feature.
- Q: Should `cmd-custom` remain generic, split by gadget family, split by exact command id, or leave scope? → A: Split `cmd-custom` by exact custom command id and require a mined command-id inventory as part of this feature.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Provision Shared Missing Fixtures (Priority: P1)

As a maintainer running the live Itertesting workflow, I want the bootstrap to prepare the specialized fixtures that are still missing so commands depending on those fixtures can be evaluated instead of being blocked before behavior is judged.

**Why this priority**: Missing fixtures are now the dominant closeout blocker after the command-channel runtime hardening. Until those fixtures exist, the workflow cannot meaningfully evaluate a large slice of direct commands.

**Independent Test**: Can be fully tested by running a prepared live closeout pass and confirming that commands tied to the newly supported fixture classes are no longer automatically reported as fixture-blocked, while commands with local helper parity gaps are surfaced separately from true fixture misses.

**Acceptance Scenarios**:

1. **Given** a prepared live run with a stable command channel, **When** the workflow needs a transport, payload, capturable target, restore target, wreck target, or custom target, **Then** it provisions a valid reusable fixture for that class before evaluating dependent commands.
2. **Given** a fixture-dependent command whose required fixture class was successfully prepared, **When** the command is exercised, **Then** the command is evaluated on live evidence instead of being blocked solely for missing setup.
3. **Given** a command whose local helper is currently stubbed or diverged from upstream support, **When** the workflow evaluates that command, **Then** the result distinguishes helper-parity failure from a missing live fixture.

---

### User Story 2 - Simplify Bootstrap Interpretation (Priority: P2)

As a maintainer reviewing closeout artifacts, I want one coherent bootstrap and fixture model so the workflow does not mix authoritative fixture classification with ad hoc simplified-bootstrap blocker rules or mislabel upstream/BAR command-semantic gates as fixture misses.

**Why this priority**: The current workflow still carries a separate simplified-bootstrap blocker path that can diverge from the declared fixture profile, which makes results harder to trust and maintain.

**Independent Test**: Can be tested by reviewing a generated run bundle and confirming that fixture availability, missing classes, affected commands, and upstream/BAR semantic-gate causes are all derived from one consistent interpretation model.

**Acceptance Scenarios**:

1. **Given** a command that depends on a specialized fixture class, **When** the maintainer reviews the run bundle, **Then** the bundle shows whether that class was planned, provisioned, missing, or refreshed using one authoritative interpretation path.
2. **Given** a fixture class that is not available in a run, **When** dependent commands are reported, **Then** only those commands are marked fixture-blocked and unrelated commands continue through normal evaluation.
3. **Given** a command is blocked because BAR Lua rewrites the target shape, omits the command for the chosen unit, requires a mod option that is not enabled, or resolves to a specific custom command id with different semantics, **When** the maintainer reviews the run bundle, **Then** that command is reported under a distinct upstream/BAR semantic-gate cause instead of as a generic fixture miss.
4. **Given** the workflow exercises a BAR custom command surface already identified in the mined inventory, **When** the maintainer reviews the run bundle, **Then** the artifact names the exact command id and owning gadget rather than only a generic `cmd-custom` bucket.

---

### User Story 3 - Preserve Trustworthy Closeout Results (Priority: P3)

As a maintainer, I want the richer fixture setup and parity repairs to improve coverage without reintroducing runtime instability or hiding genuinely unavailable fixtures behind vague behavior failures.

**Why this priority**: The runtime path is now stable enough to distinguish transport, fixture, evidence-gap, and behavior outcomes. Fixture work must preserve that clarity.

**Independent Test**: Can be tested by running repeated prepared live closeout passes and confirming that channel health remains stable while remaining unsupported fixtures continue to appear as explicit fixture blockers and repaired helper-parity surfaces no longer fail for obviously local stub reasons.

**Acceptance Scenarios**:

1. **Given** a prepared live run with newly provisioned fixture classes, **When** the workflow completes, **Then** the channel remains healthy and fixture provisioning is reported separately from command behavior.
2. **Given** a fixture cannot be created or refreshed during a run, **When** dependent commands are evaluated, **Then** they remain explicitly fixture-blocked rather than being mislabeled as transport failures or generic regressions.
3. **Given** a command still cannot be exercised because the local fork diverges from upstream or BAR Lua changes the effective command semantics, **When** the run completes, **Then** the workflow reports that cause distinctly and does not claim the failure was solved by fixture preparation alone.
4. **Given** the local helper parity surfaces for wanted speed, priority, fire-at-radar, manual fire, misc priority, and air strafe are repaired, **When** repeated prepared live closeout runs execute those commands, **Then** their outcomes no longer default to the previously stubbed local-helper failure mode.

### Edge Cases

- A fixture class is provisioned initially but the underlying unit or target is consumed, destroyed, or moved out of usable range before a dependent command runs.
- A transport fixture exists without a valid payload unit, or a payload unit exists without a valid transport.
- A map or match state does not contain a valid capturable, restorable, or wreckable target at the moment the command needs it.
- A custom-target command requires a valid target object but not the same shape of target as capture, reclaim, or restore.
- A fixture refresh attempt times out mid-run and only a subset of dependent commands can still be exercised safely.
- A command exists upstream but the local helper remains stubbed, causing a fork-parity failure even when the live world fixture is present.
- BAR Lua inserts or rewrites a command only for specific unit classes, so the selected unit never receives the expected command descriptor or target shape.
- A command requires a BAR mod option such as `emprework`, and the run must distinguish an inactive mod-option gate from a missing fixture.
- A generic custom-command dispatch id maps to multiple BAR gadget-owned behaviors, and the workflow must determine the exact custom command id before it can classify fixtures, evidence, or semantic gates correctly.
- `cmd-attack` or `UNIT_SET_TARGET` is issued against a unit whose weapons carry `place_target_on_ground`, so BAR rewrites a unit-target command into map coordinates and the verifier must not expect unit-id targeting semantics.
- `CMD_WANTED_SPEED` is issued for a fixed-wing aircraft or with `emprework` disabled, so BAR accepts neither the movetype nor the mod-option context needed for wanted-speed behavior.
- `CMD_MANUALFIRE` is replaced by `MANUAL_LAUNCH` for manual-fire units that are not commanders, so the workflow must not treat commander DGun and non-commander manual launch as the same command surface.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The live closeout workflow MUST maintain one authoritative fixture model that maps each direct command to the fixture classes it requires.
- **FR-002**: The bootstrap workflow MUST provision reusable live fixtures for the currently missing fixture classes needed by the intended command surface: transport, payload, capturable target, restore target, wreck target, and custom target.
- **FR-003**: When a required fixture class is successfully provisioned, commands that depend on that class MUST be evaluated on live evidence instead of being blocked solely because the class was previously missing.
- **FR-004**: When a required fixture class cannot be provisioned or refreshed in a run, the workflow MUST classify only the affected commands as fixture-blocked and MUST identify the missing class by name.
- **FR-005**: The workflow MUST support fixture refresh or replacement when a previously provisioned fixture becomes unusable before later dependent commands run.
- **FR-006**: The bootstrap simplification work MUST remove duplicate or conflicting blocker rules so command interpretation comes from the authoritative fixture profile and provisioning result rather than from separate simplified-bootstrap exceptions.
- **FR-007**: The run bundle MUST expose the planned fixture classes, the provisioned fixture classes, the missing fixture classes, and the commands affected by each missing class.
- **FR-008**: Adding or refreshing fixture provisioning MUST NOT degrade command-channel health or reintroduce dispatch-time runtime failures during prepared live closeout runs.
- **FR-009**: Commands that still have no valid fixture in a run MUST remain explicitly distinguishable from evidence gaps, transport interruptions, and genuine behavior failures.
- **FR-010**: The workflow MUST distinguish true missing-fixture outcomes from non-fixture command-semantic gates, including local helper parity gaps, BAR Lua command insertion or rewrite constraints, and mod-option gates identified by the upstream fixture intelligence work.
- **FR-011**: This feature MUST repair the currently identified local helper parity gaps that upstream still supports for the live closeout surface: wanted speed, priority, fire-at-radar, manual fire, misc priority, and air strafe.
- **FR-012**: The run bundle MUST surface when a command is blocked because the chosen unit does not receive the relevant BAR command shape, because Lua rewrites the target contract, or because a required mod option is disabled.
- **FR-013**: `cmd-custom` and other generic command families MUST NOT remain classified as a single behaviorally meaningful surface once upstream metadata shows that multiple BAR gadget families own materially different command ids.
- **FR-014**: This feature MUST build and use a mined inventory of the exact BAR custom command ids relevant to the live closeout surface, including the owning gadget family, eligible unit shape, and expected evidence channel for each command id brought into scope.
- **FR-015**: `cmd-custom` classification, reporting, and testing MUST operate on exact custom command ids rather than a generic custom-target bucket.
- **FR-016**: The mined command inventory for this feature MUST include, at minimum, the currently identified BAR command ids and gadget owners that materially affect closeout classification: `MANUAL_LAUNCH` (`32102`, `cmd_manual_launch.lua`), `UNIT_SET_TARGET_NO_GROUND` (`34922`, `unit_target_on_the_move.lua`), `UNIT_SET_TARGET` (`34923`, `unit_target_on_the_move.lua`), `UNIT_CANCEL_TARGET` (`34924`, `unit_target_on_the_move.lua`), `UNIT_SET_TARGET_RECTANGLE` (`34925`, `unit_target_on_the_move.lua`), `PRIORITY` (`34571`, `unit_builder_priority.lua`), and `WANT_CLOAK` (`37382`, `unit_cloak.lua`).
- **FR-017**: Wanted-speed classification MUST account for the BAR `emprework` mod-option gate and the BAR movetype restriction that handles gunships and ground/sea movers but not fixed-wing aircraft.
- **FR-018**: Attack and set-target classification MUST account for BAR units whose weapons declare `place_target_on_ground`, because BAR rewrites those command descriptors and fallback unit-target orders into ground-coordinate targeting.
- **FR-019**: DGun and non-commander manual-fire validation MUST remain distinct surfaces: commander DGun stays commander-only, while non-commander manual-fire units must be classified against the BAR `MANUAL_LAUNCH` replacement command.

### Key Entities *(include if feature involves data)*

- **Fixture Class**: A named live prerequisite such as transport unit, payload unit, capturable target, restore target, wreck target, or custom target that one or more commands require before behavior can be judged.
- **Fixture Provisioning Result**: The per-run record of which fixture classes were planned, successfully provisioned, refreshed, missing, or unavailable for use.
- **Shared Fixture Instance**: A concrete reusable live object or target prepared for a fixture class and consumed by one or more dependent command evaluations.
- **Command Fixture Dependency**: The declared relationship between a direct command and the fixture classes that must be available for trustworthy evaluation.
- **Semantic Gate**: A non-fixture prerequisite that determines whether a command is behaviorally available, such as a local helper implementation, BAR Lua command insertion or rewrite behavior, unit-shape eligibility, or a required mod option.
- **Helper Parity Gap**: A case where upstream CircuitAI supports a command surface but the local fork has stubbed, commented out, or materially altered the helper used to emit it.
- **Custom Command Inventory Entry**: A mined record for one exact BAR custom command id, including its owning gadget or Lua family, insertion conditions, unit eligibility, target shape, and expected evidence channel.
- **Command Semantic Inventory**: The repo-local mined record set derived from the local fork, upstream CircuitAI, and BAR repositories that maps a command surface to helper parity status, custom command ids, Lua gates, unit-shape rules, and expected evidence channels.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Three consecutive prepared live closeout runs complete with healthy channel status and no transport-interruption blocker while the richer fixture workflow is enabled.
- **SC-002**: In a prepared live closeout run, commands tied to the six currently missing fixture classes are either evaluated beyond the fixture gate or explicitly blocked only by a named unavailable class, with no generic simplified-bootstrap blocker reason remaining.
- **SC-003**: In prepared live closeout runs, the number of direct commands blocked solely by missing fixtures decreases from the baseline of 11 to no more than 5.
- **SC-004**: Maintainers can determine from a single run bundle which specialized fixture classes were available, which were missing, and which commands were affected, without consulting separate bootstrap logic.
- **SC-005**: Fixture preparation and refresh keep the prepared live closeout workflow on the existing maintainer execution path, and total closeout duration does not exceed the pre-014 prepared-run baseline by more than 10%.
- **SC-006**: For commands covered by the upstream fixture intelligence report, maintainers can distinguish from a single run bundle whether an unverified result came from a missing fixture, a helper-parity gap, a BAR Lua command-shape gate, or a mod-option gate.
- **SC-007**: The explicitly identified local helper parity gaps for wanted speed, priority, fire-at-radar, manual fire, misc priority, and air strafe are either repaired or reported as intentionally deferred by a superseding clarified requirement before the feature is closed.
- **SC-008**: For every custom command id brought into 014 scope, the spec and run bundle identify the exact command id, owning BAR gadget family, unit eligibility rule, and expected verification evidence channel rather than treating all custom commands as one surface.
- **SC-009**: The in-scope semantic inventory recorded by 014 includes the exact BAR ids `32102`, `34571`, `34922`, `34923`, `34924`, `34925`, and `37382`, together with their owning gadgets, and those ids are reflected in classification or reporting expectations.
- **SC-010**: At least one prepared live or synthetic validation path demonstrates that a unit-target attack rewrite, a wanted-speed mod-option or movetype gate, and a manual-launch substitution are each classified under a distinct semantic-gate or parity cause rather than as missing fixtures.

## Assumptions

- The existing baseline fixture set remains available: commander, builder, hostile target, movement lane, resource baseline, and cloakable unit.
- The current stable command-channel behavior achieved by the recent runtime hardening must be preserved while fixture work is added.
- This feature remains maintainer-facing and scoped to the live Itertesting closeout workflow rather than creating a new external validation interface.
- Commands that are still genuinely unsupported by the available fixture surface should remain explicitly fixture-blocked rather than being forced into behavior evaluation.
- The run bundle under the existing Itertesting reporting workflow remains the authoritative review surface for fixture, channel, and closeout decisions.
- The repo-local upstream fixture intelligence findings are authoritative input for distinguishing fixture gaps from helper parity, BAR Lua command-shape, and mod-option gate causes within this feature.
- Incorporating the upstream findings into 014 requires local datamining of the relevant upstream repositories to build the custom-command inventory and semantic-gate evidence needed by this feature.
- Relevant upstream repositories for this feature are the local HighBarV3 fork, upstream `rlcevg/CircuitAI`, and upstream `beyond-all-reason/Beyond-All-Reason`, and the mined local clones of those repositories are considered valid feature inputs for spec, planning, and validation work.
