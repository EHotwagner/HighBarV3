# Quickstart — Build-Root Validation Completion

**Branch**: `012-build-root-validation`  
**Plan**: [plan.md](./plan.md)

This quickstart defines the operational closeout workflow for the unfinished 011 completion work. Use the standard engine build root for `ctest`, use repo-root entrypoints for Python and headless runs, and treat any environment skip or missing target as a blocker rather than as a pass.

## Preconditions

1. Work from the repository root with a prepared engine build directory available at `build/`.
2. Ensure `ctest`, `python3`, and `uv` are installed and visible on `PATH`.
3. Ensure the headless BAR launch prerequisites required by `tests/headless/_launch.sh` are available before running live validation.
4. Review `specs/011-contract-hardening-completion/quickstart.md` and `tests/headless/README.md`; 012 closes the remaining open reruns from those same entrypoints.
5. The live headless wrappers prefer a Unix-socket coordinator endpoint and may fall back to loopback TCP if the local gRPC runtime cannot bind `unix:` endpoints.

## 1. Verify standard build-root readiness

```bash
ctest --test-dir build -N -R 'command_validation_test|ai_move_flow_test|command_validation_perf_test'
```

Expected behavior:

- The build root lists `command_validation_test`, `ai_move_flow_test`, and `command_validation_perf_test`.
- If any required target is missing, treat the result as an environment blocker and stop before judging hardening behavior.
- A partially stale build root still counts as blocked; for example, discovering only `command_validation_test` and `ai_move_flow_test` while `command_validation_perf_test` is absent does not satisfy closeout readiness.
- If the engine build cannot be reconfigured or rebuilt with the installed CMake/toolchain, record that as a build-root blocker rather than treating the missing target as a hardening pass.

## 2. Run the remaining focused reruns

```bash
ctest --test-dir build --output-on-failure -R 'command_validation_test|ai_move_flow_test'
uv run --project clients/python pytest \
  clients/python/tests/behavioral_coverage/test_live_failure_classification.py \
  clients/python/tests/behavioral_coverage/test_live_row_repro.py \
  clients/python/tests/behavioral_coverage/test_itertesting_runner.py \
  clients/python/tests/behavioral_coverage/test_itertesting_report.py
tests/headless/test_command_contract_hardening.sh
tests/headless/test_live_itertesting_hardening.sh
tests/headless/malformed-payload.sh
ctest --test-dir build --output-on-failure -R 'command_validation_perf_test'
```

Expected behavior:

- Each step produces an explicit pass, fail, or blocker outcome.
- `tests/headless/test_command_contract_hardening.sh` and `tests/headless/test_live_itertesting_hardening.sh` keep contract blockers separated from ordinary improvement guidance.
- `tests/headless/malformed-payload.sh` still returns `INVALID_ARGUMENT` without disabling the gateway.
- `command_validation_perf_test` writes `build/reports/command-validation/validator-overhead.json`.
- Exit-77 skips or missing live prerequisites are environment blockers, not acceptable completion results.

## 3. Inspect the closeout evidence

Review the latest artifacts after the focused reruns:

- `reports/itertesting/<run-id>/manifest.json`
- `reports/itertesting/<run-id>/run-report.md`
- `reports/itertesting/<run-id>/campaign-stop-decision.json`
- `build/reports/command-validation/validator-overhead.json`

Expected behavior:

- Environment blockers are distinguishable from behavior failures on first review.
- Any behavior failure is specific enough to guide the next fix before the final rerun.
- The validator artifact still reports the configured budget verdict.
- A live campaign that ends `blocked_foundational` with interrupted channel health remains a behavior blocker for closeout and must stay in scope until the rerun is green.

## 4. Resolve any exposed failures, then rerun the full workflow

After follow-up fixes or environment restoration, rerun the documented full completion flow from the same standard entrypoints:

```bash
ctest --test-dir build --output-on-failure -R 'command_validation_test|ai_move_flow_test|command_validation_perf_test'
uv run --project clients/python pytest \
  clients/python/tests/behavioral_coverage/test_live_failure_classification.py \
  clients/python/tests/behavioral_coverage/test_live_row_repro.py \
  clients/python/tests/behavioral_coverage/test_itertesting_runner.py \
  clients/python/tests/behavioral_coverage/test_itertesting_report.py
tests/headless/test_command_contract_hardening.sh
tests/headless/test_live_itertesting_hardening.sh
tests/headless/malformed-payload.sh
HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh
```

Expected behavior:

- The same standard entrypoints now complete without unresolved blockers.
- The headless wrapper either proceeds normally or emits an explicit blocker state; no required step is silently skipped.
- The evidence bundle is sufficient to decide whether the remaining 011 tasks can be closed.

## 5. Close 011 only after a clean final rerun

Do not treat the feature as complete until:

1. The focused reruns have explicit outcomes.
2. Any exposed failures or environment blockers have been resolved.
3. The full documented 011 completion workflow reruns from standard entrypoints with no unresolved blockers or skip-based gaps.
