# Contract — Failure Cause Classification

**Feature**: [Live Itertesting Hardening](../spec.md)  
**Plan**: [plan.md](../plan.md)

This contract defines the canonical primary cause categories for non-verified directly verifiable commands in live Itertesting outputs.

## Allowed values

| Value | Meaning |
|-------|---------|
| `missing_fixture` | The run could not establish a prerequisite unit, target, resource state, or map context needed to attempt the command meaningfully. |
| `transport_interruption` | Plugin command channel instability invalidated the command outcome. |
| `predicate_or_evidence_gap` | The command may have had a live effect, but the active evidence rule could not verify it confidently. |
| `behavioral_failure` | The command was meaningfully attempted under valid prerequisites and did not produce the expected observable effect. |

## Rules

- Every non-verified directly verifiable command must have exactly one primary cause classification.
- The primary cause must be visible in the reviewer-facing run report or manifest summary.
- `transport_interruption` must only be used when the run-level channel-health contract records a non-healthy outcome.
- `missing_fixture` must only be used when the fixture profile did not satisfy a command prerequisite.
- Free-form supporting detail is allowed, but it must not replace the canonical category.
