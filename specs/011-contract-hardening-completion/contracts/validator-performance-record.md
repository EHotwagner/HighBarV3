# Contract: Validator Performance Record

**Feature**: [Command Contract Hardening Completion](../plan.md)

## Purpose

Define the measurement artifact required to record the hot-path cost of the hardened validator checks.

## Required Record Fields

1. Measurement entrypoint used to generate the record.
2. Representative command-batch shape under test.
3. Sample count.
4. Median, p95, and p99 validation time in microseconds.
5. Absolute validator budget: `p99 <= 100µs`.
6. Maximum allowed regression versus baseline: `<= 10%`.
7. Comparison context or baseline reference.
8. Budget verdict: `within_budget`, `review_required`, or `breach`.
9. Stable artifact path under `build/reports/command-validation/`.

## Required Behaviors

1. The measurement is produced by a documented repo-local command, not by manual stopwatch timing.
2. The resulting artifact is machine-readable so later runs can compare results.
3. A passing verdict requires both `p99 <= 100µs` and `<= 10%` slowdown versus the recorded baseline.
4. The verdict explicitly states whether the hardened validator path remains acceptable against the project’s hot-path expectations.
5. A non-passing verdict must remain visible in the completion workflow and cannot be silently downgraded to informational output.

## Output Expectations

- Maintainers can inspect the artifact directly after running the perf target.
- The quickstart and validation docs point to the same command and artifact path.
- The record complements, rather than replaces, the broader transport latency benches.
