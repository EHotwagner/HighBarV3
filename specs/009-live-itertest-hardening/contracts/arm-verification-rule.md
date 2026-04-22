# Contract — Arm Verification Rule

**Feature**: [Live Itertesting Hardening](../spec.md)  
**Plan**: [plan.md](../plan.md)

This contract defines how directly verifiable live commands are assigned generic or tuned evidence rules.

## Required fields

| Field | Type | Semantics |
|-------|------|-----------|
| `command_id` | string | Stable command key such as `cmd-move-unit`. |
| `rule_mode` | enum | `generic`, `movement_tuned`, `combat_tuned`, `construction_tuned`, or another named rule family. |
| `expected_effect` | string | Human-readable description of the intended observable effect. |
| `evidence_window_shape` | string | Reviewer-facing description of when the effect should appear. |
| `predicate_family` | string | Predicate concept used to judge the effect. |
| `fallback_classification` | enum | Primary cause to use when the effect is still not observable. |

## Required initial coverage

The first tuned rule set for this feature must cover:

1. `cmd-move-unit`
2. `cmd-fight`
3. `cmd-build-unit`

## Rules

- Every directly verifiable command must resolve to exactly one verification rule.
- Commands named above must not rely solely on the generic live evidence window once this feature is complete.
- The rule contract is maintainer-facing and descriptive; it does not prescribe a particular implementation language or code shape.
- Any command left on `generic` mode must remain demonstrably reliable under that mode in regression validation.
