# Phase 0 Research — Itertesting Retry Tuning

**Branch**: `008-itertesting-retry-tuning` | **Date**: 2026-04-22  
**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

The repository already contains an Itertesting planning baseline from feature `007-itertesting`. This feature narrows scope to retry governance and runtime tuning: tighter caps, explicit intensity intent, early stall stop, and measurable campaign outcomes.

---

## 1. Retry intensity profiles

**Decision**: Define three named profiles with deterministic defaults and allow overrides that are always clamped by a hard global maximum of 10 improvement runs.

- `quick`: short diagnostic envelope (low retry count, aggressive early stop)
- `standard`: balanced default envelope for routine campaign use
- `deep`: larger bounded envelope for investigation runs

**Rationale**: The spec requires maintainers to choose run intent explicitly without guessing raw retry values. Named profiles provide predictable behavior while preserving bounded runtime.

**Alternatives considered**:

- Expose only raw integer retry counts: rejected. Too easy to choose disproportionate values and recreate runaway campaigns.
- Fixed retry count for all runs: rejected. Maintainers need quick and deep modes for different goals.
- Unlimited deep profile: rejected by FR-010 global cap requirement.

---

## 2. Global hard cap enforcement

**Decision**: Apply an unconditional clamp `effective_improvement_runs = min(configured_runs, 10)` before campaign start and surface both requested and effective values in reports.

**Rationale**: FR-010 requires cap enforcement even when higher values are configured. Reporting both values avoids silent behavior surprises.

**Alternatives considered**:

- Warn but still honor higher configured values: rejected by FR-010.
- Fail the campaign on values above 10: rejected. Clamping is safer and less disruptive for existing automation.
- Cap per profile only: rejected. A global guarantee must supersede profile-specific settings.

---

## 3. Stall detection and early stop policy

**Decision**: Detect stalls on directly verifiable coverage progress over a rolling run window and stop early when the window shows no meaningful gain and no higher-confidence improvement action remains.

**Rationale**: The operational pain is long retry loops with no value. Windowed direct-progress checks prevent waste while still allowing one-off fluctuations.

**Alternatives considered**:

- Stop on first non-improving run: rejected. Too sensitive and likely to stop before a valid improvement attempt.
- Use only total verified count (including non-observable): rejected. Primary target must be tied to directly verifiable commands.
- Ignore improvement-action quality: rejected. Campaigns should continue only when a concrete next action exists.

---

## 4. Natural-first progression and cheat escalation

**Decision**: Keep natural verification as the default path and permit cheat-assisted mode only after natural stall criteria are met for relevant commands, unless maintainers explicitly override policy.

**Rationale**: Clarified priority requires maximizing natural evidence first; cheat-assisted mode remains a fallback to recover stuck commands.

**Alternatives considered**:

- Enable cheat mode from run 1 for maximum coverage speed: rejected by natural-first priority.
- Ban cheat escalation entirely: rejected. The feature explicitly allows cheat-assisted continuation after stalls.
- Escalate every unverified command after one miss: rejected. Too aggressive and weakens evidence quality.

---

## 5. Coverage accounting model

**Decision**: Maintain four distinct counters in campaign and run summaries:

1. directly verifiable natural verified
2. directly verifiable cheat-assisted verified
3. directly verifiable unverified (blocked/inconclusive/failed)
4. non-directly-observable tracked separately

Primary success and stall logic uses only the directly verifiable subset.

**Rationale**: FR-012 and success criteria require primary goal computation against directly observable commands while preserving visibility into non-observable inventory.

**Alternatives considered**:

- Single aggregate verified counter: rejected. Masks true progress quality and violates reporting requirements.
- Exclude non-observable commands from all reporting: rejected. They must still be tracked.
- Count non-observable toward the 20-command target: rejected by clarification.

---

## 6. Runtime governance for 15-minute target

**Decision**: Introduce campaign-level runtime governance that:

- stops immediately when direct verified count reaches 20,
- warns when selected intensity is likely disproportionate to recent gain rate,
- avoids launching another improvement run when remaining budgeted time cannot realistically satisfy one more attempt.

**Rationale**: FR-013 and SC-008 require a practical wall-clock envelope for successful campaigns. Runtime governance keeps campaigns predictable while preserving evidence quality.

**Alternatives considered**:

- Enforce only run-count limits: rejected. Count limits alone do not guarantee wall-clock behavior.
- Hard terminate exactly at 15:00 regardless of current run state: rejected. Can produce confusing partial evidence.
- Ignore runtime and rely on operator judgment: rejected. Feature is specifically about safe unattended execution.

---

## 7. Reusable instruction persistence

**Decision**: Persist per-command improvement instructions with revision metadata and prior outcome context under `reports/itertesting/instructions/`, then load them at campaign start as initial guidance.

**Rationale**: FR-005 requires run-to-run reuse; explicit revision tracking supports traceability when guidance changes.

**Alternatives considered**:

- Keep guidance in memory only for a single campaign: rejected. No cross-campaign reuse.
- One global free-form note file: rejected. Lacks command-level specificity and versionability.
- Overwrite guidance without revision markers: rejected. Prevents change auditing.
