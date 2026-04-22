# Contract — Retry Policy Profile

**Feature**: [Itertesting Retry Tuning](../spec.md)  
**Plan**: [plan.md](../plan.md)

This contract defines how retry intent is expressed and normalized before campaign execution.

## Input shape

```json
{
  "retry_intensity": "standard",
  "max_improvement_runs": 5,
  "runtime_target_minutes": 15,
  "allow_cheat_escalation": true,
  "natural_first": true
}
```

## Required fields

| Field | Type | Allowed values / semantics |
|-------|------|----------------------------|
| `retry_intensity` | enum | `quick`, `standard`, `deep`. |
| `max_improvement_runs` | integer | Maintainer-requested retry budget (>=0). |
| `runtime_target_minutes` | integer | Runtime governance target for successful campaigns (default 15). |
| `allow_cheat_escalation` | boolean | Enables escalation path after natural stalls. |
| `natural_first` | boolean | Default `true`; when true, natural attempts must be exhausted/stalled first. |

## Normalized output fields

| Field | Type | Semantics |
|-------|------|-----------|
| `configured_improvement_runs` | integer | Original requested value. |
| `effective_improvement_runs` | integer | `min(configured_improvement_runs, 10)`. |
| `global_cap_applied` | boolean | True when clamp changed requested value. |
| `stall_window_runs` | integer | Profile-derived window for no-gain detection. |
| `min_direct_gain_in_window` | integer | Profile-derived minimum gain to continue. |

## Rules

- `effective_improvement_runs` must never exceed 10.
- Invalid `retry_intensity` values fail validation before campaign start.
- `natural_first=true` means cheat-assisted verification cannot be the initial mode for commands unless an explicit override contract is present.
- Reports must surface both configured and effective retry values when clamping occurred.
