# Phase 0 Research — Live Itertesting Hardening

**Branch**: `009-live-itertest-hardening` | **Date**: 2026-04-22  
**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

The repository already contains the live behavioral coverage driver, audit refresh workflow, and Itertesting retry-governance layer. This feature narrows scope to live-path hardening: richer fixtures, survivable command-channel behavior, and better arm-specific evidence decisions.

---

## 1. Fixture provisioning strategy

**Decision**: Extend the existing live bootstrap/startscript path into a richer fixture profile that provisions additional prerequisite classes for supported directly verifiable commands, while preserving deterministic “missing fixture” classification when a prerequisite still cannot be established.

**Rationale**: The current workflow already has a bootstrap model (`bootstrap.py`) and explicit simplified-bootstrap blocking in the live driver. Extending that path preserves one maintainer entrypoint and gives reports a clean boundary between “not attempted because fixture was missing” and “attempted but behavior/evidence failed.”

**Alternatives considered**:

- Add one-off manual setup scripts for each blocked command: rejected. Too brittle and incompatible with unattended Itertesting.
- Switch the default live path to cheats-first provisioning: rejected. The feature must harden the normal live path, not replace it with a different operating mode.
- Keep the current minimal bootstrap and rely only on retry guidance: rejected. Retry logic cannot recover commands that never start from valid prerequisites.

---

## 2. Command-channel survivability model

**Decision**: Model plugin command channel health as a run-level concern with explicit healthy/degraded/interrupted outcomes, and terminate or retry deterministically when the channel drops instead of allowing later commands to accumulate misleading per-arm failures.

**Rationale**: The current wrapper already detects `plugin command channel is not connected` and can retry a degraded live session. Elevating that concept into the planning model makes the classification explicit and prevents transport faults from being mistaken for command behavior defects.

**Alternatives considered**:

- Continue classifying disconnects only through free-form per-command error text: rejected. Reviewers cannot reliably separate infrastructure failure from command failure.
- Hide disconnects behind automatic restarts only: rejected. Recovery logic is useful, but the run report still needs an explicit transport outcome.
- Treat all disconnects as generic “failed” commands: rejected. Violates the feature’s requirement to distinguish transport interruption from behavioral failure.

---

## 3. Arm-specific verification rule strategy

**Decision**: Introduce explicit arm verification rules for timing- and predicate-sensitive live arms, starting with `fight`, `move_unit`, and `build_unit`, and ground those rules in the repo’s existing predicate primitives plus current audit hypotheses and targeted repro workflows.

**Rationale**: The project already encodes verification behavior in `predicates.py`, `registry.py`, and the live audit classification vocabulary. Reusing those concepts keeps the live path coherent with the audit workflow and avoids a separate, inconsistent definition of “verified.”

**Alternatives considered**:

- Keep a single generic verify window for all arms: rejected. The current failures show that live movement/combat/build behavior does not fit one generic timing model.
- Move all sensitive arms to a phase-2-only workflow: rejected. The default live Itertesting path still needs accurate first-pass judgments.
- Accept generic timeouts and rely on manual follow-up scripts: rejected. The feature is specifically about making the default live run more trustworthy.

---

## 4. Failure-cause classification vocabulary

**Decision**: Require one primary cause category for every non-verified directly verifiable command: `missing_fixture`, `transport_interruption`, `predicate_or_evidence_gap`, or `behavioral_failure`.

**Rationale**: Reports are only actionable if maintainers can immediately see whether a command failed because the live state was wrong, the transport died, the evidence rule was too weak, or the command truly failed to produce the expected effect.

**Alternatives considered**:

- Free-form failure notes only: rejected. Useful detail, but not enough for campaign-level triage.
- Multiple simultaneous categories per row: rejected. Harder to aggregate and compare across runs.
- No classification change beyond existing `blocked`/`failed`/`inconclusive`: rejected. Those statuses are too coarse for the live-hardening goals.

---

## 5. Validation strategy

**Decision**: Validate the feature through a layered mix of Python tests, repo-local headless wrappers, and targeted live repro scripts for the sensitive arms and transport cases.

**Rationale**: Fixture provisioning, channel survivability, and arm-specific evidence quality each fail differently. No single test type can validate all three. The repo already contains the right layers: pytest for orchestration logic, shell wrappers for workflow behavior, and targeted repros for arm-specific live evidence.

**Alternatives considered**:

- Manual report inspection only: rejected. Too slow and too easy to miss regressions.
- Pytest-only validation: rejected. Cannot prove live topology or command-channel behavior.
- Audit refresh only: rejected. Helpful for evidence classification, but insufficient as the sole regression gate for the maintainer workflow.
