# Contract: Completion Closeout Evidence

**Feature**: [Build-Root Validation Completion](../plan.md)

## Purpose

Define the evidence required to declare the remaining 011 completion work closed from standard entrypoints.

## Required Evidence Bundle

1. Root build discovery output showing the required CTest targets are visible.
2. Focused rerun outcomes for the remaining C++, Python, headless, and malformed-payload validation steps.
3. `build/reports/command-validation/validator-overhead.json` with its budget verdict.
4. Latest `reports/itertesting/<run-id>/manifest.json`.
5. Latest `reports/itertesting/<run-id>/run-report.md`.
6. Latest `reports/itertesting/<run-id>/campaign-stop-decision.json` when the campaign produces one.
7. Final full-suite rerun results from the same standard entrypoints used in the focused reruns.

## Required Behaviors

1. 011 may be closed only when the evidence bundle shows the final rerun completed without unresolved blockers or skip-based gaps.
2. A clean focused-rerun pass is necessary but not sufficient; the final full-suite rerun is still required.
3. If the focused reruns expose failures, those failures stay in scope until the full suite is rerun successfully after fixes.
4. The evidence bundle must remain reviewable by maintainers without consulting private local notes.
5. If the validator-overhead artifact is missing because the perf target is absent from the build root, that absence is itself part of the blocker evidence and prevents closure.
