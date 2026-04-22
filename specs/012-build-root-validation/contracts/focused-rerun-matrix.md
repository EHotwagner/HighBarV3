# Contract: Focused Rerun Matrix

**Feature**: [Build-Root Validation Completion](../plan.md)

## Purpose

Define the remaining 011 reruns that must produce explicit outcomes before the final closeout pass.

## Required Reruns

| Rerun | Entrypoint | Primary evidence | Blocker type when unavailable |
|-------|------------|------------------|-------------------------------|
| Root C++ validation | `ctest --test-dir build --output-on-failure -R 'command_validation_test\|ai_move_flow_test'` | Test output plus build-root target visibility | `environment` |
| Python gate and repro validation | `uv run --project clients/python pytest ...` | Pytest result plus updated report logic | `environment` when tooling is unavailable, otherwise `behavior` |
| Headless blocker separation | `tests/headless/test_command_contract_hardening.sh` | Manifest/report contract-health output | `environment` when live prerequisites or script dependencies are unavailable |
| Live hardening rerun | `tests/headless/test_live_itertesting_hardening.sh` | Live fixture and channel-health validation output | `environment` when headless launch prerequisites are unavailable |
| Malformed-payload rerun | `tests/headless/malformed-payload.sh` | `INVALID_ARGUMENT` rejection and continued gateway health | `environment` only when the harness cannot start |
| Validator-overhead rerun | `ctest --test-dir build --output-on-failure -R 'command_validation_perf_test'` | `build/reports/command-validation/validator-overhead.json` | `environment` |
| Final full-suite closeout | Full documented 011 completion workflow | Complete evidence bundle from all required steps | `environment` or `behavior`, whichever remains unresolved |

## Required Behaviors

1. Every rerun above must yield `pass`, `fail`, or `blocked`.
2. `blocked` means prerequisites or discovery failed before behavior could be judged.
3. `fail` means the environment was ready and the hardening behavior or gate expectation still regressed.
4. No rerun may disappear into an undocumented skip or a silent omission from the closeout decision.
5. A live `blocked_foundational` campaign or interrupted command channel after startup is a closeout failure signal, not a successful completion run.
