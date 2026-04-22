# Contract: Validation Suite

**Feature**: [Command Contract Hardening Completion](../plan.md)

## Purpose

Define the required completion validation set and the entrypoints maintainers use to declare the remaining command-contract hardening work finished.

## Required Steps

| Step | Entrypoint | Required outcome |
|------|------------|------------------|
| Root C++ listing | `ctest --test-dir build -N -R 'command_validation_test\|ai_move_flow_test\|command_validation_perf_test'` | The required BARb targets are visible from the engine build root. |
| Focused C++ regressions | `ctest --test-dir build --output-on-failure -R 'command_validation_test\|ai_move_flow_test'` | Validator and authoritative-target integration coverage pass. |
| Python gate/repro regressions | `uv run --project clients/python pytest ...` | Classification, gate, and repro routing semantics pass in the behavioral-coverage suite. |
| Headless blocker separation | `tests/headless/test_command_contract_hardening.sh` | Foundational blockers remain separated from ordinary improvement guidance. |
| Live/tuned validation | `tests/headless/test_live_itertesting_hardening.sh` | Live fixture, channel-health, and tuned verification flows still pass, including the real headless inert-dispatch distinction required for completion. |
| Malformed payload resilience | `tests/headless/malformed-payload.sh` | Invalid payload is rejected synchronously without disabling the gateway. |
| Wrapper gate behavior | `HIGHBAR_ITERTESTING_MAX_IMPROVEMENT_RUNS=0 tests/headless/itertesting.sh` | Blocked and pattern-review states stop correctly; ready states proceed normally. |
| Validator-overhead measurement | `ctest --test-dir build --output-on-failure -R 'command_validation_perf_test'` | A recorded validator-overhead artifact is produced with a budget verdict. |

## Required Behaviors

1. Every step above is required for completion, and an environment-dependent skip leaves validation incomplete rather than counting as an acceptable pass.
2. The validation suite must remain runnable from documented repo-local commands, not private maintainer notes.
3. Root build discovery and validator-overhead recording are part of the suite, not optional extras.
4. Headless and Python surfaces must agree on contract-health and repro semantics.
5. If the expanded suite exposes blocking failures, completion requires fixing those failures and rerunning the same suite to green.

## Output Expectations

- Maintainers get an unambiguous pass/fail result for each step; any skip is explicitly incomplete.
- Report and manifest paths remain visible for blocked runs.
- Performance output lands in a stable build artifact location.
