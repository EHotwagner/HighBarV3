# Contract: Contract Gate Matrix

**Feature**: [Command Contract Hardening Completion](../plan.md)

## Purpose

Define the completion-time gate behavior that must remain consistent across manifests, reports, Python regression tests, and the maintainer shell wrapper.

## Decision States

| Status | Meaning | Workflow effect |
|--------|---------|-----------------|
| `ready_for_itertesting` | No unresolved foundational blockers remain. | Normal improvement guidance may proceed. |
| `blocked_foundational` | One or more deterministic foundational blockers remain. | Improvement guidance is withheld and focused repros are shown. |
| `needs_pattern_review` | A foundational blocker exists but no deterministic repro is available. | Improvement guidance remains withheld and the run stops for explicit review. |

## Required Behaviors

1. The manifest, run report, and headless wrapper must agree on the gate status for the same run.
2. `blocked_foundational` and `needs_pattern_review` both prevent ordinary improvement guidance from being framed as the primary next action.
3. `ready_for_itertesting` clears blocker messaging and allows ordinary improvement output to continue.
4. `needs_pattern_review` must not silently degrade into `blocked_foundational` without the no-repro signal, or into `ready_for_itertesting`.
5. Blocked and review states must expose enough context for maintainers to know whether to rerun a focused repro or inspect a new pattern manually.

## Surface Expectations

- `manifest.json` records the machine-readable contract-health decision.
- `run-report.md` renders the blocker or ready state in maintainer-facing prose.
- `tests/headless/itertesting.sh` prints the stop-or-proceed outcome that matches the report and manifest.
