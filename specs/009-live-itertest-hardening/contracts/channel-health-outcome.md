# Contract — Channel Health Outcome

**Feature**: [Live Itertesting Hardening](../spec.md)  
**Plan**: [plan.md](../plan.md)

This contract defines the canonical run-level status for plugin command channel health during a live Itertesting campaign.

## Shape

```json
{
  "run_id": "itertesting-20260422T101530Z",
  "status": "interrupted",
  "first_failure_stage": "dispatch",
  "failure_signal": "plugin command channel is not connected",
  "commands_attempted_before_failure": 14,
  "recovery_attempted": true,
  "finalized_at": "2026-04-22T10:16:04Z"
}
```

## Required fields

| Field | Type | Allowed values / semantics |
|-------|------|----------------------------|
| `run_id` | string | Parent live run id. |
| `status` | enum | `healthy`, `degraded`, `recovered`, `interrupted`. |
| `first_failure_stage` | enum | `startup`, `dispatch`, `verification`, `shutdown`, or omitted when healthy. |
| `failure_signal` | string | Canonical health signal used for report classification. |
| `commands_attempted_before_failure` | integer | Number of commands attempted before the health problem surfaced. |
| `recovery_attempted` | boolean | Whether deterministic recovery or wrapper retry was attempted. |
| `finalized_at` | timestamp | UTC time when status was finalized. |

## Rules

- `healthy` means the channel remained usable through scheduled attempts.
- `degraded` means the channel showed instability but the run still produced a usable terminal outcome.
- `recovered` means the workflow encountered degradation and resumed deterministically without manual restart.
- `interrupted` means transport degradation invalidated the remaining run and must be surfaced distinctly from per-command behavioral failure.
- Reviewer-facing reports must render channel-health outcome separately from command-level verification results.
