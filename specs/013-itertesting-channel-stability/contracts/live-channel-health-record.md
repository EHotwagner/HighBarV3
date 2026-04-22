# Contract: Live Channel Health Record

**Feature**: [Itertesting Channel Stability](../plan.md)

## Purpose

Define the minimum machine-readable and reviewer-facing record that tells maintainers whether the command path stayed trustworthy during a live Itertesting run.

## Required Fields

| Field | Type | Meaning |
|-------|------|---------|
| `run_id` | string | Parent run identifier. |
| `status` | enum | `healthy`, `degraded`, `recovered`, or `interrupted`. |
| `first_failure_stage` | enum \| null | Earliest lifecycle stage where trust broke: `startup`, `dispatch`, `verification`, `shutdown`, or `null` when healthy. |
| `failure_signal` | string | Primary human-readable disconnect or lifecycle signal. |
| `commands_attempted_before_failure` | integer | Count of attempted rows before the first failure point. |
| `recovery_attempted` | boolean | Whether the workflow attempted to continue or restart. |
| `finalized_at` | timestamp | When the record was finalized. |

## Required Behaviors

1. Every live-closeout run must emit a `channel_health` block in `manifest.json`.
2. `run-report.md` must render a `## Channel Health` section using the same values.
3. When `status != healthy`, the record must identify the first failure stage instead of only reporting a generic disconnect.
4. When the first failure occurs during `dispatch`, later command outcomes must not be treated as clean behavior regressions unless other evidence proves they are independent of the interruption.
5. The wrapper and the report must agree on whether the run was transport-degraded enough to stop, retry, or continue.

## Wrapper Expectations

- `tests/headless/itertesting.sh` may retry a fresh live topology when the session degrades before meaningful direct coverage is achieved.
- A wrapper retry is a recovery tactic, not a reinterpretation of the failed run. The interrupted run still needs a truthful `channel_health` record.
- A run that exits without writing a new manifest after a disconnect is still a closeout failure.

## Review Expectations

- Maintainers can answer "what disconnected?" from `failure_signal`.
- Maintainers can answer "when did it stop being trustworthy?" from `first_failure_stage` and `commands_attempted_before_failure`.
- Three consecutive prepared-environment live reruns count toward success only when the record remains healthy or otherwise preserves trustworthy command evaluation for the intended surface.
