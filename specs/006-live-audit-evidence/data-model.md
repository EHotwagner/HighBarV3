# Phase 1 Data Model — Live Audit Evidence Refresh

**Branch**: `006-live-audit-evidence` | **Date**: 2026-04-22
**Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

This feature does not add databases or transport schemas. Its data model is the persisted live-run manifest and the in-memory structures used to regenerate the existing 004 markdown artifacts from observed behavior.

---

## Entity: `LiveAuditRun`

One completed or partial refresh attempt against the real headless topology.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Unique identifier for the refresh attempt, suitable for artifact filenames. |
| `started_at` | timestamp | yes | UTC start time of the run. |
| `completed_at` | timestamp \| null | yes | Null only for aborted runs captured for debugging; checked-in artifacts publish only from completed runs. |
| `engine_pin` | string | yes | Current engine pin used for the run. |
| `gametype_pin` | string | yes | Gametype actually exercised by the run. |
| `phase_mode` | enum | yes | `phase1`, `phase2`, or `mixed` for runs that include both attribution paths. |
| `topology_status` | enum | yes | `healthy`, `partial`, or `failed`. |
| `session_status` | enum | yes | `connected`, `partial`, or `failed`. |
| `row_results` | array of `ObservedRowResult` | yes | One attempted result per row touched by the run. |
| `deliverables` | array of `DeliverableRefreshStatus` | yes | One status per checked-in audit deliverable. |
| `summary` | `RefreshSummary` | yes | Reviewer-facing rollup derived from the row and deliverable states. |

**Validation**:

- Exactly one `LiveAuditRun` is selected as the latest completed source of current evidence.
- `phase_mode=mixed` is only allowed when the run includes Phase-1 refresh plus Phase-2 attribution checks.
- Checked-in artifact rendering is forbidden from incomplete runs with `completed_at=null`.

---

## Entity: `ObservedRowResult`

One row’s outcome within a specific `LiveAuditRun`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `row_id` | string | yes | Existing 004 row identifier such as `cmd-build-unit` or `rpc-hello`. |
| `kind` | enum | yes | `aicommand` or `rpc`. |
| `outcome_bucket` | string | yes | Existing 004 row bucket vocabulary, updated from live evidence. |
| `freshness_state` | enum | yes | `refreshed-live`, `not-refreshed-live`, or `drifted`. |
| `evidence_shape` | enum | yes | Snapshot diff, engine log, dispatch-only proof, or no observed evidence. |
| `evidence_excerpt` | markdown/text | no | Present only when refreshed live evidence was captured. |
| `hypothesis_class` | string \| null | no | Present when the row remains blocked or broken. |
| `repro_artifact` | path \| null | no | Path under `build/reports/` holding the detailed row repro or hypothesis output. |
| `failure_reason` | short string \| null | no | Required when `freshness_state=not-refreshed-live`. |
| `prior_run_delta` | short string \| null | no | Summary of what changed when `freshness_state=drifted`. |

**Validation**:

- Every checked-in audit row must have a corresponding `ObservedRowResult` in the selected manifest, even if its freshness state is `not-refreshed-live`.
- `freshness_state=refreshed-live` requires non-empty `evidence_excerpt` or an explicit dispatch-only reason.
- `freshness_state=not-refreshed-live` requires `failure_reason`.
- `freshness_state=drifted` requires `prior_run_delta`.

---

## Entity: `DeliverableRefreshStatus`

Refresh state for one checked-in audit deliverable.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `deliverable_name` | enum | yes | `command-audit`, `hypothesis-plan`, or `v2-v3-ledger`. |
| `status` | enum | yes | `refreshed`, `partial`, or `not-refreshed-live`. |
| `row_totals` | object | yes | Counts of refreshed, drifted, and not-refreshed rows contributing to the deliverable. |
| `blocking_reasons` | array of string | no | Reasons for `partial` or `not-refreshed-live` status. |
| `output_path` | path | yes | Checked-in file under `audit/`. |

**Validation**:

- Exactly three `DeliverableRefreshStatus` records exist in every manifest.
- `status=refreshed` requires zero not-refreshed rows relevant to that deliverable.
- `status=not-refreshed-live` requires at least one blocking reason.

---

## Entity: `RefreshSummary`

Reviewer-facing rollup emitted at the end of a run and mirrored into `audit/README.md`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Matches `LiveAuditRun.run_id`. |
| `verified_live_count` | integer | yes | Count of rows refreshed live and classified verified. |
| `blocked_count` | integer | yes | Count of rows currently blocked. |
| `broken_count` | integer | yes | Count of rows currently broken. |
| `not_refreshed_count` | integer | yes | Count of rows not refreshed in the latest run. |
| `drifted_count` | integer | yes | Count of rows whose current run differs from the previous completed run. |
| `deliverable_states` | map | yes | Short status per deliverable. |
| `top_failures` | array of string | no | Most important reasons the refresh was partial or incomplete. |

**Validation**:

- Counts reconcile with `ObservedRowResult` and `DeliverableRefreshStatus`.
- Summary must be derivable from the manifest with no hidden manual edits.

---

## Entity: `HistoricalComparison`

Structured comparison between the latest completed run and the previous completed run.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `previous_run_id` | string | yes | Prior completed run identifier. |
| `current_run_id` | string | yes | Latest completed run identifier. |
| `changed_rows` | array of string | yes | Row ids with bucket, freshness, or evidence changes. |
| `unchanged_rows` | integer | yes | Count for summary reporting. |
| `deliverable_changes` | array of string | yes | Deliverables whose status changed between runs. |

**Validation**:

- Comparison is optional when no previous completed run exists.
- When present, every `drifted` row in `ObservedRowResult` must appear in `changed_rows`.

---

## Relationships

```text
LiveAuditRun
├── row_results[] -> ObservedRowResult
├── deliverables[] -> DeliverableRefreshStatus
├── summary -> RefreshSummary
└── previous comparison -> HistoricalComparison
```

The existing 004 row inventory, hypothesis vocabulary, and ledger-pathology inventory remain inputs to classification and rendering. This feature adds freshness and run-selection state around them.
