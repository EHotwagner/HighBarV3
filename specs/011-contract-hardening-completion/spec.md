# Feature Specification: Command Contract Hardening Completion

**Feature Branch**: `011-contract-hardening-completion`  
**Created**: 2026-04-22  
**Status**: Draft  
**Input**: User description: "create specs to What should be tested next Add and run ai_move_flow_test.cc coverage for authoritative target preservation through engine-thread drain. Add a true live test for inert_dispatch versus intentionally effect-free commands. Add blocked-vs-ready wrapper coverage and pattern-review/no-repro gate coverage in headless and Python tests. Add focused repro-entrypoint tests so each reported foundational issue can actually be rerun independently. Run tests/headless/malformed-payload.sh as part of the feature validation set. Measure hot-path latency impact of the new validator checks. Fix root ctest registration so BARb tests are visible from the engine build root. and RUN THE TESTS and improve/fix based on the result. this is part of the feature."

## Clarifications

### Session 2026-04-22

- Q: For the validator hot-path check, which acceptance rule should the spec require? → A: Require both: an absolute budget and a max regression vs baseline.
- Q: What exact validator hot-path budget should the spec require? → A: `p99 <= 100µs` and `<= 10%` regression vs baseline.
- Q: For `inert_dispatch` versus intentionally effect-free commands, what level of live validation should the spec require? → A: Require both: synthetic regression coverage and a real headless live validation run.
- Q: For this feature’s Definition of Done, how should environment-dependent skips be treated? → A: Completion requires all documented validation steps to pass; environment skips do not count as complete.
- Q: If the expanded completion suite finds failures, what must this feature do before it is considered done? → A: The feature must add the coverage, run it, and fix any failures blocking the documented completion suite.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Complete Contract Validation Coverage (Priority: P1)

As a maintainer, I need the remaining command-contract behaviors validated through integration and live workflows so I can trust that the feature works beyond narrow unit cases.

**Why this priority**: The feature is not complete until authoritative target preservation, malformed payload rejection, and live dispatch behavior are validated in the same workflows maintainers actually use to ship changes.

**Independent Test**: Can be fully tested by running the focused integration and headless validation suite, including the move-flow, malformed-payload, and live contract-hardening checks, and confirming that all expected contract blockers are surfaced with the correct behavior.

**Acceptance Scenarios**:

1. **Given** a coherent command batch that targets one live unit, **When** the batch is validated and drained through the engine-thread dispatch path, **Then** the authoritative batch target is preserved and the command reaches the intended unit without target reinterpretation.
2. **Given** a malformed or incoherent command batch, **When** the maintainer runs the repo’s malformed payload and contract-hardening validation workflows, **Then** the batch is rejected in the documented validation path and the failure is reported as a foundational blocker rather than an ordinary Itertesting issue.
3. **Given** a live workflow that includes both intentionally effect-free commands and genuinely inert dispatch defects, **When** the maintainer runs the synthetic regression coverage and the real headless live validation suite, **Then** intentionally effect-free commands are not reported as foundational defects and true inert dispatch failures are reported as blockers in both surfaces.

---

### User Story 2 - Reproduce And Gate Remaining Blockers (Priority: P2)

As a maintainer, I need every reported foundational issue to have a rerunnable confirmation path, and I need contract-health gating coverage that proves when the workflow should stop versus proceed.

**Why this priority**: A blocker report is only actionable if the maintainer can rerun it independently and if the gate behavior is stable for both blocked and ready states.

**Independent Test**: Can be fully tested by running Python, unit, and headless regression coverage for deterministic repro routing, pattern-review/no-repro fallback handling, and blocked-vs-ready campaign wrapper behavior.

**Acceptance Scenarios**:

1. **Given** a foundational issue reported by the workflow, **When** the maintainer follows the linked repro command, **Then** the same issue can be rerun independently from the original campaign.
2. **Given** a blocker state with no deterministic repro, **When** the maintainer inspects the workflow output, **Then** the run is clearly marked as blocked for pattern review and ordinary improvement guidance remains withheld.
3. **Given** one blocked campaign and one ready campaign, **When** the maintainer runs the wrapper workflows, **Then** the blocked campaign stops with linked blocker context and the ready campaign proceeds with normal improvement output.

---

### User Story 3 - Make Final Validation Runnable From Standard Entry Points (Priority: P3)

As a maintainer, I need the remaining contract-hardening tests discoverable from the normal build and validation entry points so I can run the feature’s validation set without custom one-off commands.

**Why this priority**: The feature is harder to maintain if validation only works from special-case paths or if performance changes are unmeasured against the project’s latency expectations.

**Independent Test**: Can be fully tested by running the filtered root `ctest` entry point for the BARb contract tests, the full contract-hardening validation set, and the validator hot-path measurement workflow from the documented commands.

**Acceptance Scenarios**:

1. **Given** the engine build root, **When** the maintainer runs a filtered `ctest` command for the BARb contract-hardening tests, **Then** the relevant tests are discovered and run from the root build directory.
2. **Given** the documented feature validation set, **When** the maintainer runs it end to end, **Then** the suite includes malformed payload validation, deterministic repro coverage, contract-health wrapper coverage, and the remaining integration/live checks.
3. **Given** the hardened validator path, **When** the maintainer runs the documented performance measurement, **Then** the resulting output shows whether validation overhead remains within the accepted hot-path budget, records the result with the feature artifacts, and a skipped measurement does not satisfy completion.

### Edge Cases

- What happens when root-level test discovery finds stale or missing engine-side test registrations even though BARb-local test files exist?
- How does the workflow handle a foundational issue that can be classified correctly but still lacks a deterministic repro command?
- What happens when a command is intentionally effect-free in live play but resembles a no-op dispatch from the outside?
- How does the validation set report a performance regression if correctness checks still pass?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide integration coverage for authoritative batch-target preservation through the engine-thread drain and dispatch path.
- **FR-002**: The system MUST include both synthetic regression coverage and a real headless live validation run that distinguish true inert dispatch defects from intentionally effect-free commands.
- **FR-003**: The system MUST include blocked-vs-ready contract-health gate coverage in both headless wrapper workflows and Python regression coverage.
- **FR-004**: The system MUST provide a rerunnable confirmation path for each foundational issue class that the workflow reports as deterministically reproducible.
- **FR-005**: The system MUST explicitly surface pattern-review blocker states when a foundational issue cannot be mapped to a deterministic repro.
- **FR-006**: The system MUST include malformed payload validation in the documented and executed feature validation set.
- **FR-007**: The system MUST allow BARb contract-hardening tests to be discovered and runnable from the standard engine build root entry point.
- **FR-009**: The system MUST update maintainer-facing documentation so the final contract-hardening validation set, repro paths, and performance-check workflow can be run without relying on tribal knowledge.
- **FR-010**: The system MUST measure and record validator hot-path overhead as part of the feature-completion validation workflow.
- **FR-011**: The validator hot-path check MUST enforce both an absolute performance budget and a maximum allowed regression versus a recorded baseline.
- **FR-012**: The validator hot-path check MUST pass only when the hardened path remains at or below `p99 <= 100µs` and no more than `10%` slower than the recorded baseline.
- **FR-013**: The feature MUST not be considered complete until every documented validation step in the completion suite has executed and passed in a properly provisioned environment; environment-dependent skips must be treated as incomplete validation, not a pass.
- **FR-014**: The feature MUST include the fixes required to make the documented completion suite pass when the newly added or expanded validation exposes failures that block completion.

### Key Entities *(include if feature involves data)*

- **Validation Suite**: The documented set of unit, integration, Python, headless, and performance checks required to declare command contract hardening complete.
- **Foundational Issue Repro**: A focused rerun path for a reported foundational issue, including deterministic commands when available and pattern-review fallback details when not.
- **Contract Health Run State**: The blocked or ready outcome for a workflow run, along with the evidence needed to explain why improvement guidance is withheld or allowed.
- **Validator Performance Record**: The captured measurement of command-batch validation overhead and its pass/fail status against the accepted budget.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Maintainers can run the full contract-hardening completion validation set from documented commands and finish with an unambiguous pass/fail result for each remaining gap.
- **SC-002**: Every foundational issue class reported by the workflow has either a rerunnable deterministic repro path or an explicit pattern-review blocker record with no silent fallthrough.
- **SC-003**: Root-level filtered test execution from the engine build directory discovers and runs the BARb contract-hardening tests needed for this feature.
- **SC-004**: Integration validation plus both synthetic and real headless live validation demonstrate that authoritative target preservation, malformed payload rejection, inert-dispatch detection, and intentionally effect-free command handling behave as specified.
- **SC-005**: Validator performance measurement produces a recorded result for the hardened path and clearly indicates both whether it stays at or below `p99 <= 100µs` and whether it remains within `10%` of the recorded baseline.
- **SC-006**: Feature completion is declared only after the full documented validation suite runs without environment skips, with each required step producing a pass result or recorded artifact as specified.
- **SC-007**: If the expanded completion suite initially exposes blocking failures, the feature closes only after those failures are fixed and the same suite is rerun to a passing result.

## Assumptions

- The follow-up work extends the already-shipped command contract hardening feature rather than redefining its contract model or wire schema.
- Existing maintainers will continue using the current engine-backed build tree, BARb-local tests, Python behavioral coverage suite, and headless scripts as the primary validation environment.
- The inert-dispatch completion check is not satisfied by synthetic coverage alone; it also requires a real headless live validation run.
- Performance validation can reuse an existing microbenchmark or lightweight measurement path rather than introducing a new benchmarking framework.
- A missing headless or performance prerequisite blocks completion for this feature instead of downgrading the corresponding validation step to an acceptable skip.
- The validator hot-path budget for this feature is `p99 <= 100µs` with a maximum allowed regression of `10%` versus the recorded baseline.
- This feature is a completion feature, so failures revealed by its added validation are in scope to fix when they block the documented completion suite.
- Root-level test discoverability is expected to work through the existing engine build and CTest structure instead of requiring a separate custom test runner.
