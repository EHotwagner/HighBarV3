# Feature Specification: Live Orchestration Refactor

**Feature Branch**: `017-live-orchestration-refactor`  
**Created**: 2026-04-23  
**Status**: Draft  
**Input**: User description: "Refactor the live bootstrap and Itertesting orchestration so responsibilities are split cleanly, metadata and fixture inference use structured seams instead of raw row coupling, and further fixes stop accumulating inside oversized orchestration files."

## Clarifications

### Session 2026-04-23

- Q: When a new metadata record type is collected but no interpretation rule exists yet, how should the workflow behave? → A: Preserve the record, emit a maintainer-visible warning, and block fully interpreted/successful classification until a rule is added.
- Q: When fixture evidence changes during a run, such as a fixture being observed first and later invalidated, which state should the final bundle treat as authoritative? → A: The latest explicit fixture state is authoritative for final availability, while earlier states remain as diagnostic history.
- Q: When a live run records bootstrap metadata but never reaches command-row evaluation, how should the bundle report transport availability? → A: Report transport as unknown or unproven unless explicit transport evidence was recorded.
- Q: For synthetic or skipped-live execution modes, how should the final bundle present fixture and transport status? → A: Mark fixture and transport status as mode-qualified non-live results, valid for the run mode but not counted as live evidence.
- Q: When explicit fixture evidence is missing, what should define whether a fixture is considered baseline-guaranteed for that run mode? → A: An explicit run-mode policy or contract defines which fixtures are baseline-guaranteed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trustworthy Live Failure Reporting (Priority: P1)

As a maintainer running live behavioral coverage, I want failed or blocked live runs to produce internally consistent bootstrap, fixture, and reporting outcomes so I can trust the bundle when deciding what to fix next.

**Why this priority**: The current workflow is most valuable when it narrows the real blocker quickly. Contradictory run artifacts waste investigation time and can send maintainers after the wrong problem.

**Independent Test**: Trigger a live run that stops before full fixture provisioning and confirm the resulting bundle reports only the evidence that the run actually established, while preserving bootstrap and capability metadata.

**Acceptance Scenarios**:

1. **Given** a live run that stops during bootstrap readiness assessment, **When** the run bundle is generated, **Then** the bootstrap status, fixture availability, and foundational blocker summary MUST agree with each other.
2. **Given** a live run that records bootstrap metadata but no downstream fixture evidence, **When** the report is rendered, **Then** it MUST not claim that unproven fixtures were provisioned.

---

### User Story 2 - Isolated Maintainer Changes (Priority: P2)

As a maintainer changing live bootstrap, metadata capture, or Itertesting synthesis, I want each responsibility to live behind a clear seam so I can make one class of change without accidentally breaking unrelated behavior.

**Why this priority**: The codebase is still functional, but too much behavior is concentrated in a small number of large files. That raises the cost and risk of every follow-up fix.

**Independent Test**: Modify one responsibility area, such as bootstrap-readiness interpretation or fixture inference, and verify that its dedicated tests pass without requiring unrelated execution-path edits.

**Acceptance Scenarios**:

1. **Given** a maintainer changes bootstrap-readiness interpretation, **When** they run the targeted validation for that responsibility, **Then** they can validate the change without depending on unrelated report-synthesis logic.
2. **Given** a maintainer changes run-bundle synthesis rules, **When** they inspect the refactored design, **Then** ownership boundaries clearly identify where execution, metadata extraction, and reporting decisions belong.

---

### User Story 3 - Faster Root-Cause Investigation (Priority: P3)

As a maintainer diagnosing a new live regression, I want the orchestration flow to map cleanly from live execution to recorded metadata to final report decisions so I can isolate the responsible layer quickly.

**Why this priority**: This workflow is used for repeated hardening. Faster diagnosis reduces churn and makes future work less likely to pile additional fixes into oversized files.

**Independent Test**: Review the refactored workflow documentation and run artifacts for a representative live failure and confirm that the execution layer, metadata layer, and synthesis layer can be traced separately.

**Acceptance Scenarios**:

1. **Given** a reported live blocker such as bootstrap starvation or transport interruption, **When** a maintainer traces the bundle evidence, **Then** they can determine which responsibility layer produced the decision without reverse-engineering unrelated orchestration code.
2. **Given** a new metadata record is added to the live workflow, **When** it is surfaced in the run bundle, **Then** its collection and interpretation paths are explicit and do not rely on hidden row-shape conventions.

### Edge Cases

- What happens when a live run emits metadata records but no command rows because bootstrap fails before command evaluation begins?
  The bundle preserves the recorded bootstrap metadata and reports transport availability as unknown or unproven unless explicit transport evidence was captured.
- How does the workflow behave when a fixture is partially observed, refreshed, or invalidated after bootstrap but before dependent commands are evaluated?
  The final bundle uses the latest explicit fixture state as authoritative for final availability while retaining earlier state changes as diagnostic history.
- What happens when a new metadata record is introduced for live runs but no report-synthesis rule has been added yet?
  The workflow preserves the record, emits a maintainer-visible warning, and prevents the run from being classified as fully interpreted or successful until an explicit interpretation rule is added.
- How does the system handle synthetic or skipped-live runs that still need to produce valid manifests without pretending to have live evidence?
  The bundle reports fixture and transport status as mode-qualified non-live results that remain valid for the selected run mode but are not counted as established live evidence.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The live behavioral coverage workflow MUST separate live execution, metadata capture, and run-synthesis responsibilities into distinct, maintainable ownership boundaries.
- **FR-002**: The workflow MUST preserve all current maintainer-visible live outcomes required for diagnosis, including bootstrap readiness, capability limits, prerequisite resolution, map-source decisions, fixture availability, transport availability, and foundational blocker classification.
- **FR-003**: Run-bundle synthesis MUST consume recorded live metadata through an explicit interpretation layer rather than relying on incidental raw-row filtering or ordering assumptions.
- **FR-004**: A live run that stops before fixture provisioning completes MUST report only fixture availability that was explicitly supported by recorded evidence or defined as baseline-guaranteed by an explicit run-mode policy or contract.
- **FR-005**: The workflow MUST allow maintainers to validate bootstrap-readiness behavior, fixture inference behavior, and report-synthesis behavior through independently targeted tests.
- **FR-006**: The refactor MUST preserve existing external workflow entry points, run artifact formats, and maintainer-facing commands unless a change is explicitly documented as part of the feature.
- **FR-007**: The workflow MUST provide a clear ownership map for how live execution facts become metadata records and how metadata records become final manifest and report decisions.
- **FR-008**: Synthetic and skipped-live execution modes MUST continue to produce valid run bundles under the explicit run-mode policy.
- **FR-009**: When a new metadata record type is added, the workflow MUST provide one explicit place to define how that record is collected and one explicit place to define how it affects run interpretation.
- **FR-010**: The refactor MUST not reduce the current ability to diagnose live blockers such as bootstrap starvation, missing fixtures, transport interruption, or command-evidence gaps.
- **FR-011**: When a metadata record is collected without a defined interpretation rule, the workflow MUST preserve the record, emit a maintainer-visible warning, and prevent the run from being classified as fully interpreted or successful until that rule exists.
- **FR-012**: When fixture evidence changes during a run, the final bundle MUST use the latest explicit fixture state as authoritative for final availability and retain earlier state transitions as diagnostic history.
- **FR-013**: When a live run records bootstrap metadata but never reaches command-row evaluation, the bundle MUST report transport availability as unknown or unproven unless explicit transport evidence was recorded.
- **FR-014**: Synthetic and skipped-live execution modes MUST report fixture and transport status as mode-qualified non-live results that remain valid for that run mode without being counted as established live evidence.

### Key Entities *(include if feature involves data)*

- **Live Execution Responsibility**: The part of the workflow that interacts with a running session, gathers snapshots, performs bootstrap actions, and records raw live facts.
- **Metadata Record**: A structured diagnostic fact captured from a live or synthetic run, such as bootstrap readiness, runtime capability profile, prerequisite resolution, map-source decision, or standalone probe evidence.
- **Run Interpretation Responsibility**: The part of the workflow that converts recorded execution facts and metadata into fixture availability, transport availability, blocker classification, and report content.
- **Run Bundle**: The maintainer-facing manifest and report output that summarizes the run, its evidence, its blockers, and the resulting improvement guidance state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In bootstrap-blocked live runs, manifest and report outputs show zero contradictory fixture-availability claims in the targeted regression suite.
- **SC-002**: Maintainers can validate changes to bootstrap readiness, fixture inference, and run reporting through separate targeted test commands, with each command completing successfully without requiring unrelated responsibility changes.
- **SC-003**: For the representative failure modes covered by the regression suite, maintainers can identify the responsible workflow layer from the run bundle, decision trace, interpretation warnings, and targeted tests during the documented quickstart inspection workflow.
- **SC-004**: Adding or changing a metadata record type requires updates only in the defined collection and interpretation seams, rather than edits scattered across unrelated orchestration paths.

## Assumptions

- The refactor is primarily aimed at the current live behavioral coverage and Itertesting orchestration layers; the existing gateway and service structure remains in scope only for compatibility, not redesign.
- Existing maintainer commands, report locations, and manifest/report consumers must continue to work after the refactor.
- Current live-diagnostic concepts such as bootstrap readiness, fixture provisioning, transport provisioning, and capability profiles remain valid and should be preserved rather than replaced.
- The feature may reorganize responsibility boundaries and test ownership, but it is not intended to change the policy decisions already made by the current live-hardening features unless a current behavior is proven incorrect.
- Baseline-guaranteed fixture availability is defined by explicit per-mode policy or contract rather than inferred from incidental execution behavior.
