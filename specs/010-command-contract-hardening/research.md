# Phase 0 Research — Command Contract Hardening

**Branch**: `010-command-contract-hardening` | **Date**: 2026-04-22  
**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

The repository already contains the transport gateway, validator/dispatch split, Itertesting stop logic, and maintainer-facing reporting. This feature narrows scope to the foundational command contract seam that sits underneath those workflows: target invariants, validation depth, inert dispatch classification, deterministic repros, and the decision of whether Itertesting should proceed at all.

---

## 1. Authoritative dispatch-target model

**Decision**: Treat `CommandBatch.target_unit_id` as the authoritative single-target contract and reject any unit-bound command whose per-command `unit_id` is missing or disagrees with the batch target. Preserve the normalized target through queueing and engine-thread drain so runtime dispatch cannot silently choose a different unit than validation accepted.

**Rationale**: The proto documentation already says commands on different units must be sent in separate batches, but the current runtime still prefers per-command `unit_id` during `DrainCommandQueue`. That drift makes the contract incoherent, weakens validator guarantees, and forces maintainers to debug ambiguous outcomes. Enforcing the documented invariant is cheaper and safer than redefining the schema.

**Alternatives considered**:

- Keep the heterogeneous-batch escape hatch: rejected. It directly contradicts the documented `CommandBatch` contract and hides bugs until dispatch.
- Silently ignore per-command `unit_id` and trust only the batch target: rejected. It would avoid drift at runtime but still fail to tell clients that they sent an incoherent payload.
- Remove per-command unit ids from the proto now: rejected. That would be a breaking schema change for a problem that can be solved by stricter enforcement of the current contract.

---

## 2. Validation depth strategy

**Decision**: Expand validation from basic map-extents and build-def checks into a command-surface contract that rejects semantically invalid batches before enqueue. This includes target drift, non-finite or incomplete positional values, invalid target references, unsupported dispatch shapes, and other shallow-validation holes that currently pass through to ambiguous dispatch-time failures.

**Rationale**: `tests/headless/malformed-payload.sh` already proves the gateway benefits from synchronous rejection. The same principle should apply to incoherent targeting and known dispatcher preconditions. The validator should answer "is this a coherent batch for this command surface?" rather than merely "does this payload parse?"

**Alternatives considered**:

- Keep validation minimal and let dispatch discover errors later: rejected. That produces harder-to-triage failures and weakens the all-or-nothing batch guarantee.
- Push validation entirely into Python/Itertesting: rejected. Foundational contract defects must be rejected at the transport seam too, not only described after a run.
- Solve everything with new proto fields: rejected. Better validation and normalization should come first while the existing schema is still sufficient.

---

## 3. Foundational issue classification strategy

**Decision**: Add a dedicated foundational issue vocabulary for at least `target_drift`, `validation_gap`, and `inert_dispatch`, and keep those issues out of the ordinary Itertesting improvement bucket. A command may still have downstream evidence limitations, but the foundational blocker remains the primary maintainer-facing cause for the run.

**Rationale**: The spec explicitly separates contract blockers from setup/evidence/retry problems. Maintainers need to know whether they are fixing semantics, validator coverage, or an actually inert dispatcher path. Existing `missing_fixture` and `predicate_or_evidence_gap` reporting is useful, but it is not enough when the transport or dispatch contract itself is wrong.

**Alternatives considered**:

- Reuse the existing failure-cause vocabulary unchanged: rejected. It cannot clearly express the difference between a contract blocker and an ordinary live-workflow issue.
- Emit only free-form prose in reports: rejected. Reports need a stable issue class to support stop decisions, summaries, and repro routing.
- Allow multiple co-primary categories per command: rejected. That makes run gating and cross-run comparison noisier; the foundational issue should dominate when present.

---

## 4. Deterministic repro strategy

**Decision**: Pair each foundational issue class with a deterministic repro route anchored in existing repo-local test layers: C++ unit tests for validator invariants, C++ integration or headless tests for dispatch-path defects, and maintainer-facing report links to the exact entrypoint that confirms the issue independently from a full Itertesting campaign.

**Rationale**: The repo already has the right layers for focused confirmation. Validator defects are cheapest to prove in `tests/unit/command_validation_test.cc`; command-path defects can be exercised in integration/headless flows; Itertesting reports already know how to point maintainers at repro artifacts. Reusing those layers avoids inventing another diagnostics framework.

**Alternatives considered**:

- Broad campaign reruns only: rejected. Too slow and too noisy for foundational command-contract bugs.
- Headless-only repros for every issue: rejected. Some invariants are better proven in unit or integration tests.
- Manual issue writeups with no executable path: rejected. The feature requires deterministic confirmation, not just descriptions.

---

## 5. Contract-health gate strategy

**Decision**: Introduce a run-level contract-health decision that blocks normal Itertesting improvement output whenever foundational issues are present. Reports still retain downstream observations, but they are clearly secondary and withheld from "next improvement action" guidance until the blocker set is empty or explicitly resolved in a later run.

**Rationale**: This is the user-requested ordering: foundational command-contract repair first, Itertesting improvement second. The current workflow already emits stop decisions and report summaries; the missing piece is a gate that tells maintainers whether those downstream suggestions are actionable yet.

**Alternatives considered**:

- Always produce ordinary improvement guidance and let maintainers decide: rejected. It encourages wasted tuning work on structurally broken commands.
- Hard-stop the workflow without preserving downstream observations: rejected. Maintainers still benefit from seeing the surrounding run context, as long as it is clearly marked secondary.
- Move the gate outside Itertesting into a separate manual checklist: rejected. The decision belongs in the workflow output itself so it can be tracked per run.
