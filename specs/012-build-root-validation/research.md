# Phase 0 Research — Build-Root Validation Completion

**Branch**: `012-build-root-validation` | **Date**: 2026-04-22  
**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

Feature 011 already finished the implementation and documentation work for command-contract hardening, but its task list still shows the closeout loop as incomplete: the focused reruns were not finished, any failures exposed by those reruns were not yet resolved, and the full completion suite was not rerun to green. Repository inspection shows the right command surfaces already exist; the remaining problem is operational closure from the standard build root.

---

## 1. Standard entrypoint strategy

**Decision**: Use the existing documented 011 entrypoints as the authoritative rerun surface: filtered root `ctest` from the standard engine build root for C++ and validator-overhead checks, plus the repo-root headless and Python commands already documented in `tests/headless/README.md` and `specs/011-contract-hardening-completion/quickstart.md`.

**Rationale**: The repository already exposes the required CTest bridge targets and maintainer shell wrappers. 012 is closure work, so introducing a new orchestration layer would add another surface to maintain without solving the actual problem, which is getting the standard validation environment ready and rerunning the documented suite.

**Alternatives considered**:

- Create a new one-shot wrapper for all remaining 011 checks: rejected. The standard entrypoints already exist and are the contract maintainers must trust.
- Continue using private local commands from the AI subdirectory: rejected. The feature spec explicitly requires the standard build-root validation path.
- Treat only repo-root shell wrappers as authoritative: rejected. Root `ctest` discovery is part of the required 011 closeout evidence.

---

## 2. Environment-readiness gate

**Decision**: Treat build-root readiness as an explicit prerequisite record rather than an implicit assumption. Missing root-discovered targets, absent `uv`, missing live-launch prerequisites, or exit-77 skips remain environment blockers that prevent completion, even when the underlying hardening code may already be correct.

**Rationale**: The unfinished value described in the 012 spec is not only behavior validation but also repeatability from a standard environment. The current headless wrappers already encode skip behavior for missing prerequisites; 012 needs to make that outcome visible as a blocker category instead of letting it blend into ordinary pass/fail noise.

**Alternatives considered**:

- Ignore environment-readiness and focus only on code failures: rejected. That would not solve the actual closeout gap.
- Downgrade skip outcomes to warnings: rejected. 011 and the 012 spec both require no-skip completion.
- Treat build-root readiness as out of scope because 011 already documented commands: rejected. The remaining work is specifically about making that documentation runnable in practice.

---

## 3. Focused rerun sequence

**Decision**: Preserve the remaining 011 closeout order exactly: run the focused C++ and Python reruns first, then run the headless completion steps and capture the validator artifact, then resolve any failures those reruns expose, and only then rerun the full documented completion workflow to green.

**Rationale**: The 011 task list already encodes the unfinished operational sequence in tasks `T028` through `T031`. Using the same progression keeps 012 aligned with the original completion logic and makes it clear that 012 closes the loop rather than redefining feature 011.

**Alternatives considered**:

- Skip straight to a full-suite rerun: rejected. Focused reruns are the fastest way to expose whether failures remain before spending headless time.
- Treat focused reruns as optional smoke checks: rejected. They are the unfinished portion of the original closeout plan.
- Declare completion when focused reruns pass without rerunning the full workflow: rejected. 011 closure still requires the end-to-end rerun from standard entrypoints.

---

## 4. Outcome and evidence model

**Decision**: Reuse the existing run artifacts as the closeout evidence bundle: `reports/itertesting/<run-id>/manifest.json`, `run-report.md`, and `campaign-stop-decision.json` for blocker and campaign state, plus `build/reports/command-validation/validator-overhead.json` for the performance gate.

**Rationale**: These artifacts already represent the maintainer-facing truth surfaces. 012 should define how to interpret them for closeout instead of inventing a second reporting path. That keeps the evidence set stable across focused reruns, failure triage, and the final rerun-to-green decision.

**Alternatives considered**:

- Create a separate closeout summary format: rejected. That would duplicate existing evidence and drift quickly.
- Rely only on shell stdout: rejected. Completion needs stable machine-readable records.
- Treat the validator artifact as informational only: rejected by Constitution V and the 011/012 specs.

---

## 5. Final closeout gate

**Decision**: Define 012 completion as a two-part gate: all remaining focused reruns must produce explicit outcomes, and after any required fixes, the full 011 completion workflow must rerun from the same standard entrypoints with no unresolved blockers or environment skips.

**Rationale**: The feature’s value is closure, not just diagnostics. A single partial rerun or one clean local attempt is insufficient because the project needs a repeatable standard workflow that future maintainers can use to confirm the same result.

**Alternatives considered**:

- Close 011 after any single successful focused rerun pass: rejected. That would leave the final rerun gap unresolved.
- Close 011 when environment blockers are documented but unresolved: rejected. The spec requires a working standard path, not just notes about why it failed.
- Make final reruns optional when validator-overhead already passed once: rejected. The closeout decision depends on the whole suite, not an isolated artifact.

---

## 6. Agent context update

**Decision**: Update `AGENTS.md` manually to point the Speckit marker at `specs/012-build-root-validation/plan.md`.

**Rationale**: The repo still exposes the marker in `AGENTS.md`, and `.specify/scripts/` contains no dedicated update helper. Manual marker replacement remains the smallest compliant change.

**Alternatives considered**:

- Leave the marker on 011: rejected. The active feature metadata now points at 012.
- Create a one-off helper script for a single marker swap: rejected. Unnecessary complexity.
