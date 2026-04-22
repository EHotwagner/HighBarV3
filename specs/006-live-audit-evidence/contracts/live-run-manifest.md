# Contract — Live Run Manifest

**Applies to**: the persisted structured output written by the live refresh workflow under `build/reports/`.  
**Referenced from**: [data-model.md](../data-model.md) (`LiveAuditRun`, `ObservedRowResult`, `DeliverableRefreshStatus`, `RefreshSummary`).

## Purpose

The manifest is the only source of current evidence for checked-in audit regeneration. Markdown artifacts are rendered from the latest completed manifest only.

## Required sections

The manifest may be JSON, YAML, or another machine-readable format during implementation, but it must represent these logical sections:

1. Run metadata
2. Deliverable statuses
3. Row results
4. Optional historical comparison
5. Refresh summary

## Mandatory fields

| Field | Requirement |
|-------|-------------|
| `run_id` | Unique per refresh attempt and reused in artifact filenames. |
| `completed_at` | Required for any manifest used to regenerate checked-in markdown. |
| `deliverables` | Exactly three entries: command audit, hypothesis plan, V2-v3 ledger. |
| `row_results` | One entry for every tracked audit row, even if not refreshed live. |
| `summary` | Counts and deliverable states must reconcile with `row_results`. |

## Freshness rules

- A row may be marked `refreshed-live`, `not-refreshed-live`, or `drifted`.
- Older run evidence must not be promoted into the latest manifest as current evidence.
- Historical comparison data may reference older runs, but only as comparison, never as replacement evidence.

## File placement

Manifests must live under `build/reports/` and remain untracked build output.
