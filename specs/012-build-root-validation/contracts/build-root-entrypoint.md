# Contract: Build-Root Entrypoint

**Feature**: [Build-Root Validation Completion](../plan.md)

## Purpose

Define the standard validation surfaces maintainers use to close the remaining 011 work without relying on ad hoc local procedures.

## Required Entrypoints

| Surface | Entrypoint | Required outcome |
|---------|------------|------------------|
| Root target discovery | `ctest --test-dir build -N -R 'command_validation_test\|ai_move_flow_test\|command_validation_perf_test'` | Required C++ and perf targets are visible from the standard build root. |
| Focused C++ reruns | `ctest --test-dir build --output-on-failure -R 'command_validation_test\|ai_move_flow_test'` | Remaining focused C++ validation steps execute from the build root. |
| Validator-overhead rerun | `ctest --test-dir build --output-on-failure -R 'command_validation_perf_test'` | The machine-readable validator artifact is regenerated from the build root. |
| Python behavioral reruns | `uv run --project clients/python pytest ...` | Behavioral-coverage gate and repro semantics rerun from the repo root. |
| Headless completion reruns | `tests/headless/test_command_contract_hardening.sh`, `tests/headless/test_live_itertesting_hardening.sh`, `tests/headless/malformed-payload.sh`, and `tests/headless/itertesting.sh` | Maintainer-facing closeout scripts run from the repo root and expose pass, fail, or blocker outcomes. |

## Required Behaviors

1. The build root is the authoritative C++ discovery and rerun surface.
2. Repo-root headless and Python entrypoints remain the authoritative closeout surface for live and report-driven behavior.
3. Maintainers must not need to `cd` into a private binary directory or use undocumented local commands to finish the workflow.
4. Missing required targets or unavailable prerequisites stop the workflow as environment blockers.
5. Partial discovery is still a blocker; listing `command_validation_test` and `ai_move_flow_test` without `command_validation_perf_test` does not satisfy the contract.
