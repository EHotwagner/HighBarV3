# Quickstart — Command Contract Hardening Completion

**Branch**: `011-contract-hardening-completion`  
**Plan**: [plan.md](./plan.md)

This quickstart defines the completion validation set for the remaining command-contract hardening gaps: authoritative target preservation through engine-thread drain, inert-dispatch versus intentionally effect-free behavior, blocked-vs-ready and no-repro gate coverage, rerunnable foundational repros, malformed-payload resilience, root-build discovery, and validator-overhead recording.

Every step below is required for feature completion. A skipped required step leaves validation incomplete.

## Preconditions

1. Use the normal Linux reference environment for the gateway, Python behavioral coverage, and headless BAR workflows.
2. Have an engine build tree available so `ctest` can run from the standard build root.
3. Ensure Python dependencies and `uv` are available for the behavioral-coverage and headless scripts.
4. Configure any required headless engine prerequisites before running the shell harnesses.

## 1. Confirm build-root discovery and focused C++ coverage

```bash
ctest --test-dir build -N -R 'command_validation_test|ai_move_flow_test|command_validation_perf_test'
ctest --test-dir build --output-on-failure -R 'command_validation_test|ai_move_flow_test'
```

Expected behavior:

- The filtered listing from the engine build root shows the BARb contract-hardening targets.
- `command_validation_test` covers validator rejection and focused contract invariants.
- `ai_move_flow_test` proves authoritative target preservation through queue drain and dispatch.
- A missing or undiscoverable required target blocks completion rather than downgrading the step to an acceptable skip.

## 2. Run Python regression coverage for gate and repro behavior

```bash
uv run --project clients/python pytest \
  clients/python/tests/behavioral_coverage/test_live_failure_classification.py \
  clients/python/tests/behavioral_coverage/test_live_row_repro.py \
  clients/python/tests/behavioral_coverage/test_itertesting_runner.py \
  clients/python/tests/behavioral_coverage/test_itertesting_report.py
```

Expected behavior:

- Intentionally effect-free commands remain exempt from `inert_dispatch`.
- Deterministic repro routing stays attached to the correct foundational issue classes.
- Blocked, ready, and pattern-review gate states serialize and render consistently.

## 3. Run headless completion validation

```bash
tests/headless/test_command_contract_hardening.sh
tests/headless/test_live_itertesting_hardening.sh
tests/headless/malformed-payload.sh
HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh
```

Expected behavior:

- Contract blockers remain separated from ordinary improvement guidance.
- The live-hardening path covers both synthetic regression behavior and a real headless validation run for inert-dispatch versus intentionally effect-free commands.
- Malformed payloads fail with `INVALID_ARGUMENT` without disabling the gateway.
- The wrapper stops on blocked or pattern-review states and proceeds only when contract health is ready.
- A skipped headless step does not satisfy completion.

## 4. Follow the focused foundational repros

Use the linked repo-local repro command for each reported foundational issue:

- `target_drift` → filtered `ctest` on `command_validation_test`
- `validation_gap` → `tests/headless/malformed-payload.sh`
- `inert_dispatch` → `tests/headless/test_command_contract_hardening.sh`
- `needs_pattern_review` → no deterministic repro; follow the explicit review instructions in the manifest/report

Expected behavior:

- Deterministic issue classes can be rerun independently from the original campaign.
- Pattern-review-only blockers stay explicit and do not silently fall through to ordinary improvement work.

## 5. Record validator-overhead results

```bash
ctest --test-dir build --output-on-failure -R 'command_validation_perf_test'
```

Expected behavior:

- The measurement emits a machine-readable record under `build/reports/command-validation/`.
- The record includes percentile timings, the `p99 <= 100µs` absolute budget, the `<= 10%` regression budget versus baseline, and a clear verdict for the hardened validator path.
- Maintainers can review the artifact alongside the broader transport-budget context before closing the feature.
