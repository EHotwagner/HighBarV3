# Contract — Campaign Stop Decision

**Feature**: [Itertesting Retry Tuning](../spec.md)  
**Plan**: [plan.md](../plan.md)

This contract defines the canonical campaign termination record. Every completed campaign must emit exactly one stop decision.

Artifact location: `reports/itertesting/<campaign-id>/campaign-stop-decision.json` and mirrored in the final run bundle as `stop-decision.json`.

## Shape

```json
{
  "decision_id": "stop-20260422T103200Z",
  "campaign_id": "campaign-20260422T101500Z",
  "final_run_id": "run-20260422T103152Z",
  "stop_reason": "stalled",
  "direct_verified_total": 18,
  "target_direct_verified": 20,
  "target_met": false,
  "runtime_elapsed_seconds": 862,
  "message": "No direct verified gain across the last 2 runs and no higher-confidence actions remained.",
  "created_at": "2026-04-22T10:32:00Z"
}
```

## Required fields

| Field | Type | Allowed values / semantics |
|-------|------|----------------------------|
| `decision_id` | string | Unique stop decision identifier. |
| `campaign_id` | string | Parent campaign id. |
| `final_run_id` | string | Run where stop was determined. |
| `stop_reason` | enum | `target_reached`, `stalled`, `budget_exhausted`, `runtime_guardrail`, `interrupted`. |
| `direct_verified_total` | integer | Final directly verifiable verified total. |
| `target_direct_verified` | integer | Required direct target (20 for this feature). |
| `target_met` | boolean | True when `direct_verified_total >= target_direct_verified`. |
| `runtime_elapsed_seconds` | integer | Campaign wall-clock elapsed at stop time. |
| `message` | string | Human-readable explanation included in reports. |
| `created_at` | timestamp | UTC emission time. |

## Rules

- `target_reached` requires `target_met=true`.
- `target_met=true` requires `direct_verified_total >= target_direct_verified`.
- A campaign may stop with `runtime_guardrail` even if retry budget remains.
- `interrupted` must be used when run termination is due to external interruption rather than stall/budget/target.
- Reviewer-facing reports must render this decision verbatim as the campaign stop reason section.
