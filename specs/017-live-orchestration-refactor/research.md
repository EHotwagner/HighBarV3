# Phase 0 Research — Live Orchestration Refactor

**Branch**: `017-live-orchestration-refactor` | **Date**: 2026-04-23  
**Plan**: [plan.md](./plan.md)

## Decision 1: Separate live execution metadata from command rows through a typed seam

**Decision**: Live execution should hand Itertesting a typed metadata collection alongside command rows instead of embedding maintainer metadata in `__...__` marker rows that later get rescanned by `itertesting_runner.py`.

**Rationale**:

- The current flow emits bootstrap and capability metadata through `_bootstrap_metadata_rows()` in `behavioral_coverage/__init__.py`, then reconstructs meaning later through `_metadata_rows()` and `_..._for_run()` helpers in `itertesting_runner.py`.
- That coupling depends on marker strings, row shape, and ordering assumptions that are easy to break during unrelated fixes.
- A typed seam makes FR-009 concrete: one place defines how a record is collected and one place defines how it is interpreted.

**Alternatives considered**:

- Keep marker rows and only add comments or naming conventions.  
  Rejected because the bug surface is structural, not documentation-only.
- Move all metadata collection and interpretation into `itertesting_runner.py`.  
  Rejected because it would make the already oversized runner own even more live execution detail.

## Decision 2: Preserve existing CLI commands and bundle artifacts while changing internal ownership

**Decision**: 017 should keep the current `python -m highbar_client.behavioral_coverage` surface, `tests/headless/*.sh` entry points, and `manifest.json` / `run-report.md` / `campaign-stop-decision.json` bundle layout, while refactoring only the internal ownership boundaries that produce them.

**Rationale**:

- FR-006 requires that maintainer-facing commands and artifact formats remain stable unless explicitly documented.
- The problem is maintainability and contradictory inference, not that the current bundle location or shell workflow is wrong.
- Preserving the outer workflow lets the feature focus on trustworthiness and isolation instead of forcing wrapper churn across the repository.

**Alternatives considered**:

- Introduce a new standalone orchestration command or bundle format.  
  Rejected because it would increase migration work without solving the core ownership problem.
- Delay the refactor until a larger transport or gateway redesign.  
  Rejected because the oversized Python files are already slowing routine live-hardening fixes.

## Decision 3: Make run-mode policy the authoritative source for baseline-guaranteed fixture and transport status

**Decision**: Fixture and transport availability that exists only because of run mode must be derived from an explicit run-mode policy, not from absence of contradictory live evidence.

**Rationale**:

- The clarified spec requires synthetic and skipped-live modes to remain valid without pretending they are live proof.
- The current workflow can fall back from "no evidence" to implied status, which is exactly how contradictory bundles become possible.
- An explicit policy object gives one place to define which fixtures are baseline-guaranteed and whether transport is live-proven, unknown, or mode-qualified non-live.

**Alternatives considered**:

- Continue inferring baseline state from missing rows.  
  Rejected because missing evidence is not proof and leads directly to false provisioning claims.
- Hardcode special cases in report rendering only.  
  Rejected because the authority must exist before report generation, not as a presentation patch.

## Decision 4: Use state transitions, not snapshots alone, to decide fixture and transport authority

**Decision**: The interpretation layer should synthesize fixture and transport availability from explicit state transitions, with the latest explicit state authoritative for final availability while earlier states remain preserved as diagnostic history.

**Rationale**:

- The spec explicitly says fixture evidence can change during a run and that the latest explicit state must win.
- Current inference logic in `itertesting_runner.py` mixes row detail parsing, fixture class summaries, and fallback heuristics, which makes refresh or invalidation behavior hard to audit.
- A transition model cleanly supports preexisting, provisioned, refreshed, invalidated, missing, unknown, and mode-qualified non-live outcomes without conflating them.

**Alternatives considered**:

- Keep only the final observed snapshot for each fixture class.  
  Rejected because it would discard the diagnostic history needed for root-cause investigation.
- Treat transport as a special case outside the shared state model.  
  Rejected because transport status is one of the most failure-prone fixture-derived decisions and needs the same authority rules.

## Decision 5: Unknown metadata must remain visible and block “fully interpreted” success

**Decision**: When a metadata record type is preserved without an interpretation rule, the bundle must emit a maintainer-visible warning and the run must not be classified as fully interpreted or successful until the rule exists.

**Rationale**:

- FR-011 makes this behavior mandatory, and it is central to preventing the refactor from quietly dropping new evidence.
- Preserving the record keeps future maintainers from losing the raw fact while still forcing an explicit interpretation decision.
- This rule also gives the targeted tests a concrete gate for new metadata additions: collection and interpretation must both be updated.

**Alternatives considered**:

- Ignore unknown metadata until a later cleanup.  
  Rejected because silent ignore recreates hidden coupling under a different name.
- Fail the entire run immediately at collection time.  
  Rejected because maintainers still need the recorded run evidence and should see the raw record in the bundle.

## Decision 6: Update `AGENTS.md` manually for the active plan context

**Decision**: Update the Speckit marker in `AGENTS.md` manually so it points to `specs/017-live-orchestration-refactor/plan.md`.

**Rationale**:

- The repository exposes the Speckit marker in `AGENTS.md`, but `.specify/scripts/` contains no dedicated agent-context update helper.
- Prior features in this repository already use manual marker replacement as the minimal compliant approach.

**Alternatives considered**:

- Leave `AGENTS.md` on `016`.  
  Rejected because the active planning context is now `017`.
- Add a new helper script as part of planning.  
  Rejected because that would expand scope beyond the feature documentation task.
