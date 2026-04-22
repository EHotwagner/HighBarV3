# Contract: Fixture Provisioning And Refresh

**Feature**: [Fixture Bootstrap Simplification](../plan.md)

## Purpose

Define how live Itertesting provisions reusable fixture instances, refreshes them when they become unusable, and reports per-class status in the run bundle.

## Required Record Shape

### `fixture_provisioning`

| Field | Meaning |
|-------|---------|
| `class_statuses` | One status row per planned fixture class. |
| `shared_fixture_instances` | Reusable prepared live objects or targets. |
| `provisioned_fixture_classes` | Aggregate list of currently usable classes. |
| `missing_fixture_classes` | Aggregate list of missing or unavailable classes. |
| `affected_command_ids` | Commands blocked because at least one required class is missing or unusable. |
| `completed_at` | Completion time for the provisioning evaluation. |

### `class_statuses[]`

| Field | Meaning |
|-------|---------|
| `fixture_class` | Named class such as `transport_unit`. |
| `status` | `planned`, `provisioned`, `refreshed`, `missing`, or `unusable`. |
| `planned_command_ids` | Commands that depend on the class. |
| `ready_instance_ids` | Currently usable backing instances. |
| `last_transition_reason` | Reviewer-facing reason for the current status. |
| `affected_command_ids` | Commands blocked if the class is not currently usable. |

## Required Behaviors

1. The workflow must provision reusable live fixtures for the six currently missing classes named in the spec when the environment can support them.
2. When a previously provisioned fixture becomes consumed, destroyed, or otherwise stale before a later command runs, the workflow must attempt refresh or replacement before classifying the dependent command as fixture-blocked.
3. Successful refresh must change the class status to `refreshed` and keep dependent commands eligible for live evaluation.
4. Failed refresh must preserve an explicit `missing` or `unusable` status and list only the affected commands.
5. `run-report.md` must render enough fixture status detail for maintainers to tell whether a class was never provisioned, provisioned successfully, or refreshed after becoming stale.

## Review Expectations

- Maintainers can see which shared fixtures were ready for transport, payload, capturable target, restore target, wreck target, and custom target classes.
- A refresh event explains why a later command remained evaluable instead of looking like a silent setup mutation.
- Commands unrelated to a missing class continue through normal evaluation.

## Non-Goals

- This contract does not require a separate debugging artifact outside the existing run bundle.
- This contract does not require cheat-assisted provisioning as the default path.
