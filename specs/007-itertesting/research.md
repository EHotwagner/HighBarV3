# Phase 0 Research — Itertesting

**Branch**: `007-itertesting` | **Date**: 2026-04-22
**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

The current repository already has two relevant building blocks: the behavioral coverage driver under `clients/python/highbar_client/behavioral_coverage/` and the manifest-backed live audit workflow under `tests/headless/audit/` plus `audit_runner.py`. Itertesting should therefore reuse the same live-topology and evidence patterns while adding bounded campaign retries, explicit improvement tracking, and a dedicated report surface under `reports/itertesting/`.

---

## 1. Campaign boundary and reuse strategy

**Decision**: Build Itertesting as a new campaign orchestration layer inside `clients/python/highbar_client/behavioral_coverage/` that reuses the existing registry, predicates, bootstrap knowledge, and headless launch helpers.

**Rationale**: The current package already knows the tracked command inventory, command categories, and live verification mechanics. Reusing that layer keeps the command truth in one place and avoids a second drifting inventory for the same command set.

**Alternatives considered**:

- Build Itertesting as an unrelated standalone script tree: rejected. That would duplicate registry, evidence, and live-launch knowledge.
- Extend only the shell scripts and keep iteration logic in Bash: rejected. Improvement planning and per-command state are Python-shaped problems with structured data needs.
- Replace the existing behavioral coverage flow entirely: rejected. Itertesting is an additive bounded campaign workflow, not a full reset of the current harnesses.

---

## 2. Source of truth for per-run results

**Decision**: Persist one timestamped run manifest per run under `reports/itertesting/` and derive the human-readable run report from that manifest.

**Rationale**: The spec requires every run to be independently reviewable without raw engine logs and to support run-to-run comparison. A manifest-first design preserves machine-readable command outcomes, evidence references, improvement deltas, and campaign progress in a way that markdown alone cannot.

**Alternatives considered**:

- Emit markdown only: rejected. Hard to compare reliably and too lossy for automation.
- Reuse `build/reports/` as the primary durable Itertesting output: rejected. That area already hosts adjacent artifacts; the feature spec explicitly asks for `reports/itertesting/...`.
- Keep only the latest run and overwrite earlier ones: rejected. The spec requires comparison with previous runs.

---

## 3. Evidence standard for verification

**Decision**: A command is verified only when its run record references direct game-state evidence or a command-specific live artifact that can stand on its own in the report.

**Rationale**: The clarified spec explicitly forbids promotion from dispatcher acceptance, indirect inference, or manual judgment alone. The run manifest therefore needs a field that separates evidence-backed verification from merely dispatched or attempted outcomes.

**Alternatives considered**:

- Count dispatcher acceptance as verified for non-observable commands: rejected by clarification.
- Allow a prior verified run to carry a command forward as verified in later failed runs: rejected. Each run must report its own observed result.
- Collapse evidence detail into a short status string only: rejected. Reports must be independently reviewable without raw engine output.

---

## 4. Improvement planning model

**Decision**: For each unverified command, store a concrete next-step improvement action chosen from a bounded set such as setup change, target preparation, stronger evidence collection, execution timing change, or escalation to cheat-assisted setup.

**Rationale**: The feature is explicitly about evolving reruns rather than repeating the same weak attempt. A structured improvement vocabulary makes later tests and summaries checkable and keeps the retry logic from degrading into free-form notes.

**Alternatives considered**:

- Free-form narrative notes only: rejected. Too hard to validate and compare.
- Global per-run improvement note with no per-command granularity: rejected. Commands fail for different reasons.
- Unlimited autonomous mutation between runs: rejected. The feature needs a bounded, reviewable retry loop.

---

## 5. Natural versus cheat-assisted verification

**Decision**: Track setup mode explicitly per command and per run, default to natural attempts, and allow cheat-assisted escalation only after a command’s natural path stalls or when the maintainer opts in directly.

**Rationale**: The spec requires natural verification to be preferred and cheat-assisted outcomes to count only when clearly labeled. This means setup provenance must be part of the command record and surfaced in all summaries.

**Alternatives considered**:

- Mix natural and cheat-assisted verified counts together: rejected by clarification.
- Start every run in cheat-assisted mode to maximize coverage: rejected. It violates the priority rule and weakens evidence quality.
- Ban cheat-assisted verification entirely: rejected. The spec explicitly allows it to increase coverage reach.

---

## 6. Timestamp precision and collision handling

**Decision**: Use UTC timestamp names precise to the second as the primary run id, and append a deterministic numeric suffix when a second-level collision occurs.

**Rationale**: The spec requires names based on date/time to the second and separately requires collision prevention when two runs start within the same second. A suffix preserves the requested naming style while still making filenames unique.

**Alternatives considered**:

- Add millisecond precision instead of a suffix: rejected. It diverges from the explicit second-level naming requirement.
- Fail on same-second collisions: rejected by FR-014.
- Use random UUID names: rejected. They do not meet the requested reviewer-friendly timestamp naming convention.

---

## 7. Report surface and comparison output

**Decision**: Generate one markdown run report per run plus a campaign summary that compares the current run with the prior run and highlights verified gains, regressions, stalls, natural/cheat splits, and outstanding blockers.

**Rationale**: Maintainers need to review one run in isolation and also understand whether the campaign is improving. Splitting per-run review from cross-run comparison keeps both artifacts focused and readable.

**Alternatives considered**:

- One ever-growing markdown file for the whole campaign: rejected. It becomes hard to review and archive.
- Manifest comparison only with no human-readable summary: rejected. FR-013 requires reviewer-friendly reports.
- Per-command report files only: rejected. Maintainers need a run-level overview first.
