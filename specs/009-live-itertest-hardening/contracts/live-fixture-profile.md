# Contract — Live Fixture Profile

**Feature**: [Live Itertesting Hardening](../spec.md)  
**Plan**: [plan.md](../plan.md)

This contract defines the minimum fixture-ready state the default bounded live Itertesting workflow must establish before directly verifiable command attempts begin.

## Required fields

| Field | Type | Semantics |
|-------|------|-----------|
| `profile_id` | string | Stable identifier for the active fixture profile. |
| `fixture_classes` | list | Required prerequisite classes the run must try to provision. |
| `supported_command_ids` | list | Commands expected to start from valid prerequisite state when provisioning succeeds. |
| `optional_fixture_classes` | list | Useful but non-mandatory fixture classes. |
| `provisioning_budget_seconds` | integer | Time budget for preparing the profile before dispatch. |
| `fallback_behavior` | enum | `classify_missing_fixture` or `interrupt_run`. |

## Rules

- The default live Itertesting entrypoint must use exactly one active fixture profile for a bounded run.
- Every command listed in `supported_command_ids` must map to one or more required fixture classes.
- When provisioning cannot satisfy a required fixture class, affected commands must be reported as missing-fixture outcomes rather than ordinary behavioral failures.
- The contract describes workflow expectations only; it does not require a new public API surface.
