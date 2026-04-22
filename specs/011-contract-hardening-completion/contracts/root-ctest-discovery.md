# Contract: Root CTest Discovery

**Feature**: [Command Contract Hardening Completion](../plan.md)

## Purpose

Define which BARb contract-hardening targets must be discoverable and runnable from the standard engine build root.

## Required Targets

| Target | Source | Required root filter |
|--------|--------|----------------------|
| `command_validation_test` | `tests/unit/command_validation_test.cc` | `ctest --test-dir build -R command_validation_test` |
| `ai_move_flow_test` | `tests/integration/ai_move_flow_test.cc` | `ctest --test-dir build -R ai_move_flow_test` |
| `command_validation_perf_test` | `tests/unit/command_validation_perf_test.cc` | `ctest --test-dir build -R command_validation_perf_test` |

## Required Behaviors

1. `ctest -N` from the engine build root lists the required targets.
2. Maintainers do not need to `cd` into the AI binary subdirectory to run the completion suite.
3. The discovery path remains rooted in generated CMake/CTest bridge files, not a custom runner.
4. Filtered root execution must be stable enough for documentation and CI reuse.

## Non-Goals

- This contract does not require every repository test to be exposed from the build root.
- This contract does not replace existing headless shell entrypoints.
