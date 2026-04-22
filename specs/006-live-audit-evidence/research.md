# Phase 0 Research — Live Audit Evidence Refresh

**Branch**: `006-live-audit-evidence` | **Date**: 2026-04-22
**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

The current 004 audit tooling already defines the artifact set and row-level interfaces, but inspection of `tests/headless/audit/*.sh`, `audit/*.md`, and `clients/python/highbar_client/behavioral_coverage/audit_runner.py` shows that the implementation is still static seed generation. The questions that matter for planning are therefore about the migration boundary: what becomes the source of truth, how partial runs publish safely, and how the current contracts survive the move to live evidence.

---

## 1. Source of truth for current evidence

**Decision**: Introduce a persisted live-run manifest under `build/reports/` and derive all checked-in audit deliverables from the latest completed manifest only.

**Rationale**: The spec clarification explicitly forbids carrying older evidence forward as current when a row fails in the latest run. A manifest-first design gives the renderer a single authoritative input, supports drift comparisons between manifests, and removes the current coupling where `audit_report.py` synthesizes reviewer output directly from static registry and citation metadata.

**Alternatives considered**:

- Render markdown directly from the live harness without an intermediate manifest: rejected. That would make partial-run recovery and drift comparison harder, and it would force every downstream view to re-parse raw logs.
- Keep the current static synthesis and merely swap in a few live snippets: rejected. It would still mix inferred and observed evidence in the same rows, which the clarified spec forbids.
- Carry forward older row evidence with a timestamp: rejected by clarification. Older runs can be retained for comparison, but not presented as current evidence.

---

## 2. Publish semantics for partial runs

**Decision**: Allow partial refresh publication, but require explicit freshness state at both deliverable and row granularity.

**Rationale**: The live topology can fail mid-run or expose environment-specific blockers. Throwing away all successful observations would reduce usefulness, while silently leaving stale rows would mislead reviewers. The correct middle ground is to publish what refreshed and mark everything else as `not refreshed live` or `partial`.

**Alternatives considered**:

- Fail the entire refresh if any row fails: rejected. Too brittle for headless integration work and contrary to the spec clarification.
- Publish partial output without row-level freshness markers: rejected. That would recreate the current trust problem, just with different wording.
- Update only successful rows and leave the rest unchanged: rejected. Reviewers must be able to tell which rows are stale in the current run.

---

## 3. Boundary between harness execution and markdown rendering

**Decision**: Keep `tests/headless/audit/*.sh` as the public execution entry points and move business logic into the Python behavioral coverage package, split into three stages: collect live observations, classify rows, then render checked-in markdown.

**Rationale**: The repo already advertises `repro.sh`, `hypothesis.sh`, `repro-stability.sh`, `phase2-macro-chain.sh`, and `run-all.sh` as the 004 entry points. Preserving those paths avoids churn for reviewers and future tasks, while Python remains the best place to encode row inventory, classification rules, and manifest rendering.

**Alternatives considered**:

- Rebuild the entire flow in Bash: rejected. Classification, manifest handling, and cross-artifact rendering are already Python-shaped problems.
- Collapse everything into Python entry points and remove the shell scripts: rejected. The existing headless test workflow is shell-oriented and already integrated with repo-local launch helpers.
- Leave classification in Bash and rendering in Python: rejected. It would split the core outcome logic across languages with no benefit.

---

## 4. Deliverable refresh strategy

**Decision**: Refresh all three 004 deliverables in one run from the same manifest: `audit/command-audit.md`, `audit/hypothesis-plan.md`, and `audit/v2-v3-ledger.md`.

**Rationale**: The clarifications resolved this explicitly. A single manifest-backed refresh keeps all linked row references, hypothesis entries, and ledger citations consistent. It also prevents a planner from treating the ledger as static prose while the command audit changes underneath it.

**Alternatives considered**:

- Refresh only `audit/command-audit.md`: rejected by clarification and would leave stale hypothesis/ledger links.
- Refresh command audit plus hypothesis plan, leaving ledger static: rejected. The spec requires the ledger to indicate where live proof is still missing.
- Maintain separate per-deliverable runs: rejected. That would introduce cross-run inconsistency and complicate freshness rules.

---

## 5. Drift detection model

**Decision**: Compare repeated completed manifests at the row level and surface drift as a first-class refresh outcome instead of overwriting it silently.

**Rationale**: The spec requires repeated runs to expose changed behavior. Manifest-to-manifest comparison is simpler and more auditable than diffing rendered markdown, because row identifiers, outcome buckets, evidence freshness, and deliverable status become structured fields instead of free-form text.

**Alternatives considered**:

- Diff the markdown files directly: rejected. Too fragile; text-only diffs would conflate cosmetic changes with behavioral drift.
- Track drift only for outcome bucket changes: rejected. Evidence freshness and deliverable status changes are also reviewer-relevant.
- Ignore drift unless a maintainer asks for it: rejected by the spec.

---

## 6. Save/Load and weakly proven RPCs

**Decision**: Treat existing seed-only RPC rows, especially `Save` and `Load`, as live refresh targets with explicit non-refreshed handling rather than pre-classified fixed rows.

**Rationale**: Current `audit/command-audit.md` and `audit/v2-v3-ledger.md` still present `Save` and `Load` as effectively fixed from service wiring alone. The feature’s purpose is to replace that source-based assumption with observed live behavior or a clear `not refreshed live` marker.

**Alternatives considered**:

- Preserve current RPC verdicts until someone writes a stronger test later: rejected. That is exactly the seed-data problem this feature is meant to remove.
- Remove weakly proven RPC rows from the deliverables: rejected. Scope remains all 74 rows.
- Classify any unrefreshed RPC as broken: rejected. Missing evidence is not automatically a dispatcher defect.

---

## 7. Agent context update

**Decision**: Update `AGENTS.md` manually to point the Speckit context marker at `specs/006-live-audit-evidence/plan.md`.

**Rationale**: The repo exposes the marker in `AGENTS.md`, but no dedicated update script exists in `.specify/scripts/`. Manual marker replacement is the minimal compliant change.

**Alternatives considered**:

- Leave the marker generic: rejected. The project instructions explicitly say to read the current plan for context.
- Invent a new helper script: rejected. Unnecessary for a single marker replacement.
