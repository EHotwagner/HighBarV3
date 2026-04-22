# Contract: Environment Blocker Reporting

**Feature**: [Build-Root Validation Completion](../plan.md)

## Purpose

Ensure maintainers can distinguish standard-environment blockers from hardening-behavior failures during the remaining closeout reruns.

## Environment Blocker Conditions

| Condition | Required interpretation |
|-----------|-------------------------|
| Root `ctest -N` does not list a required target | Build-root discovery blocker |
| `uv` or other required tooling is missing | Repo-root tooling blocker |
| A headless script exits with skip semantics before behavior runs | Live-environment blocker |
| Launch prerequisites for `_launch.sh` are unavailable | Headless environment blocker |
| Validator artifact cannot be produced because the perf target cannot run | Build-root performance blocker |
| The engine build cannot be reconfigured or rebuilt with the installed CMake/toolchain | Build-root tooling blocker |

## Required Behaviors

1. Environment blockers are reported as blockers, not as passing results and not as ambiguous generic failures.
2. Behavior failures are reported separately once the standard entrypoint has actually run in a ready environment.
3. A blocker report must tell the maintainer what readiness condition failed first.
4. Blockers prevent 011 closure until the same standard entrypoint can be rerun successfully.

## Required Evidence Surfaces

- Build-root `ctest` output for missing or undiscoverable targets
- Headless wrapper output and exit status
- `reports/itertesting/<run-id>/manifest.json`
- `reports/itertesting/<run-id>/run-report.md`
- `reports/itertesting/<run-id>/campaign-stop-decision.json`
- `build/reports/command-validation/validator-overhead.json` when the perf step runs
