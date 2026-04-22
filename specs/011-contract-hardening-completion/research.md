# Phase 0 Research — Command Contract Hardening Completion

**Branch**: `011-contract-hardening-completion` | **Date**: 2026-04-22  
**Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

Feature 010 already defined the command-contract model and shipped most of the Python/report plumbing, but repository inspection shows the completion problem is now about finishing the remaining runnable seams: the placeholder `ai_move_flow_test.cc`, missing blocked-vs-ready wrapper coverage, incomplete repro entrypoints, validation-set documentation, build-root `ctest` discoverability, and explicit validator-overhead recording.

---

## 1. Authoritative target preservation coverage anchor

**Decision**: Finish `tests/integration/ai_move_flow_test.cc` as the primary authoritative-target preservation and engine-thread-drain coverage anchor, and keep it runnable from the engine build root through normal filtered `ctest`.

**Rationale**: The existing unit tests prove early rejection and queue metadata, but the remaining gap in feature 010 is the real engine-thread handoff. The repository already contains a placeholder `ai_move_flow_test.cc` and root `CMakeLists.txt` logic that enumerates integration targets through `ctest`; completion should use that seam instead of inventing a separate one-off harness.

**Alternatives considered**:

- Rely only on `tests/unit/command_validation_test.cc`: rejected. Unit coverage does not prove authoritative target preservation across queue drain and dispatch.
- Prove the behavior only in a headless script: rejected. That would make failures slower to isolate and harder to run from the normal build root.
- Introduce a brand-new bespoke integration runner: rejected. The existing `tests/integration/` plus root `ctest` bridge is already the correct maintainable surface.

---

## 2. Inert dispatch versus intentionally effect-free validation

**Decision**: Keep the distinction between `inert_dispatch` and intentionally effect-free commands as a dual-surface contract: synthetic Python/headless regression coverage proves the vocabulary and exemptions quickly, and a real headless live validation run proves the maintainer workflow does not collapse those cases in practice.

**Rationale**: `clients/python/tests/behavioral_coverage/test_live_failure_classification.py` already contains the intentionally effect-free exemption, and `tests/headless/test_command_contract_hardening.sh` already checks blocker separation. The clarified spec now requires both synthetic regression coverage and a real headless live run, so completion work needs to extend the current surfaces rather than treating the synthetic path as sufficient on its own.

**Alternatives considered**:

- Treat Python regression coverage as sufficient: rejected. The spec explicitly requires live validation behavior, not just in-memory classification.
- Treat any dispatch-only observation as `inert_dispatch`: rejected. Feature 010 already established that commands like `cmd-stop` and `cmd-wait` must stay exempt.
- Move the exemption into shell scripts only: rejected. The issue vocabulary still lives in Python manifests and reports, so Python must remain authoritative.

---

## 3. Contract-health gate coverage strategy

**Decision**: Validate blocked-vs-ready and pattern-review/no-repro behavior in both pytest and the maintainer shell wrapper, with the wrapper treated as part of the contract rather than an incidental consumer.

**Rationale**: The current repository already has the report/manifest logic and a shell wrapper that prints contract-health results. The remaining acceptance criteria depend on the wrapper stopping or proceeding correctly, so completion coverage has to assert both the Python source of truth and the repo-root shell entrypoint behavior.

**Alternatives considered**:

- Check only manifest and report rendering: rejected. Maintainers invoke `tests/headless/itertesting.sh`, and the wrapper behavior is part of the user-facing contract.
- Check only wrapper stdout: rejected. That would miss regressions in manifest/report serialization and gate-state semantics.
- Reframe pattern-review as a warning rather than a blocker: rejected. The existing issue vocabulary and spec both require ordinary improvement guidance to remain withheld.

---

## 4. Deterministic repro completion strategy

**Decision**: Require every deterministic foundational issue class to map to one focused rerun entrypoint, and require non-deterministic cases to surface an explicit `needs_pattern_review` blocker rather than silently omitting repro data.

**Rationale**: `audit_runner.py` already maps `target_drift`, `validation_gap`, and `inert_dispatch` to repo-local entrypoints, but feature 010 tasks still leave the focused coverage and no-repro surfaces incomplete. Completion work should finish those exact mappings and make the fallback state visible in tests, manifests, and reports.

**Alternatives considered**:

- Keep broad campaign reruns as the only repro path: rejected. That is too slow and noisy for foundational defects.
- Allow missing repros with no explicit blocker state: rejected. The spec requires maintainers to know whether a blocker is rerunnable or needs pattern review.
- Add a new external diagnostics service: rejected. The repo already has the right unit, integration, pytest, and headless seams.

---

## 5. Validation-suite completion

**Decision**: Treat `tests/headless/malformed-payload.sh` as a mandatory member of the final completion suite and define completion as a full no-skip validation set rather than a grab bag of ad hoc commands that may be partially skipped.

**Rationale**: The malformed-payload harness already exists and directly covers the transport-side requirement that incoherent commands fail synchronously without disabling the gateway. The clarified spec also makes environment-dependent skips insufficient for completion, so the completion suite should promote this harness from an available check to a required pass gate.

**Alternatives considered**:

- Leave malformed-payload coverage implicit inside broader headless runs: rejected. The spec explicitly asks for it in the documented and executed validation set.
- Fold malformed-payload checks into `test_command_contract_hardening.sh`: rejected. The current dedicated script already validates a different transport-seam guarantee and should remain independently runnable.
- Treat completion as documentation-only: rejected. The feature description explicitly includes running the tests and using the result to drive fixes.

---

## 6. Validator-overhead measurement strategy

**Decision**: Add a focused validator-overhead measurement target that records a machine-readable artifact under `build/reports/command-validation/`, and make it pass only when the hardened validator remains at or below `p99 <= 100µs` and within `10%` of the recorded baseline.

**Rationale**: The repository already contains `tests/bench/latency-uds.sh` and `tests/bench/latency-tcp.sh`, but those benches measure transport round-trip, not isolated validator cost. The clarified spec now sets both an absolute and baseline-relative validator budget, so the plan needs a targeted measurement artifact that can be run from the build tree and evaluated deterministically.

**Alternatives considered**:

- Use only `latency-uds.sh` and `latency-tcp.sh`: rejected. They are necessary context but insufficient to isolate validator overhead.
- Use an ad hoc local stopwatch and paste results into docs: rejected. Results need a reproducible command and stable artifact path.
- Skip explicit measurement because validation work is "small": rejected by Constitution V and the feature spec.

---

## 7. Root build discovery strategy

**Decision**: Use the existing root `CMakeLists.txt` bridge generation as the canonical BARb test-discovery mechanism and extend it so the contract-hardening targets needed for completion are all filterable from the engine build root.

**Rationale**: The current `CMakeLists.txt` already writes `CTestTestfile.cmake` bridge files and appends tests into a generated root include script. Completion should tighten that seam so maintainers can run the remaining contract-hardening tests through standard root `ctest` filters instead of walking into the AI subdirectory manually.

**Alternatives considered**:

- Ask maintainers to run tests only from the AI binary dir: rejected. The feature spec explicitly calls for the standard engine build root entry point.
- Replace the bridge with a custom shell wrapper: rejected. The repo already uses CTest as the build-root contract.
- Limit build-root discovery to unit tests: rejected. Integration and perf targets are part of the required completion set.

---

## 8. Agent context update

**Decision**: Update `AGENTS.md` manually to point the Speckit marker at `specs/011-contract-hardening-completion/plan.md`.

**Rationale**: The repo still exposes the marker in `AGENTS.md`, and `.specify/scripts/` still contains no dedicated agent-context update helper. Manual marker replacement remains the smallest compliant change.

**Alternatives considered**:

- Leave the marker pointing at feature 010: rejected. The project instructions explicitly route implementers through the current feature plan.
- Create a new helper script solely for this marker swap: rejected. Unnecessary for a one-line context update.
