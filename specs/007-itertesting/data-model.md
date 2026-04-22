# Phase 1 Data Model — Itertesting

**Branch**: `007-itertesting` | **Date**: 2026-04-22
**Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

Itertesting does not introduce database or transport schema changes. Its data model is a set of filesystem-backed run and campaign records that coordinate repeated live verification attempts against the existing command inventory.

---

## Entity: `ItertestingCampaign`

One bounded verification campaign spanning one or more Itertesting runs.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `campaign_id` | string | yes | Stable identifier for the campaign root under `reports/itertesting/`. |
| `started_at` | timestamp | yes | UTC campaign start time. |
| `completed_at` | timestamp \| null | yes | Null while the campaign is still allowed to continue. |
| `max_improvement_runs` | integer | yes | Maintainer-configured stop budget from FR-016. |
| `natural_first` | boolean | yes | Default `true`; records whether cheat escalation requires stalled natural attempts. |
| `run_ids` | array of string | yes | Ordered list of associated Itertesting runs. |
| `final_status` | enum | yes | `improved`, `stalled`, `budget_exhausted`, or `aborted`. |
| `stop_reason` | string | yes | Reviewer-readable reason the campaign stopped. |

**Validation**:

- `run_ids` must contain at least one run.
- `completed_at` is required when `final_status` is not `aborted`.
- `len(run_ids) - 1` must not exceed `max_improvement_runs`.

---

## Entity: `ItertestingRun`

One full verification pass over the tracked command set.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Timestamp-to-second identifier, optionally suffixed for collisions. |
| `campaign_id` | string | yes | Parent campaign reference. |
| `started_at` | timestamp | yes | UTC start time. |
| `completed_at` | timestamp \| null | yes | Null only for interrupted/failed runs kept for diagnosis. |
| `sequence_index` | integer | yes | Zero-based run order within the campaign. |
| `engine_pin` | string | yes | Runtime engine pin actually exercised. |
| `gametype_pin` | string | yes | Gametype/version exercised. |
| `setup_mode` | enum | yes | `natural`, `mixed`, or `cheat-assisted` depending on the overall run profile. |
| `command_records` | array of `CommandVerificationRecord` | yes | One record for every tracked command. |
| `improvement_actions` | array of `ImprovementAction` | yes | Actions proposed or applied because some commands remained unverified. |
| `summary` | `RunSummary` | yes | Reviewer-facing aggregate metrics. |
| `previous_run_comparison` | `RunComparison` \| null | no | Present when there is a prior run in the campaign. |

**Validation**:

- Every tracked command must have exactly one `CommandVerificationRecord`.
- `sequence_index=0` must not include a prior comparison.
- `setup_mode=cheat-assisted` is only valid when the maintainer explicitly overrides natural-first or every attempted command uses cheat-backed setup.

---

## Entity: `CommandVerificationRecord`

The per-command outcome for one Itertesting run.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `command_id` | string | yes | Stable command identifier aligned with the existing command inventory. |
| `command_name` | string | yes | Human-readable arm/rpc name. |
| `category` | string | yes | Existing command grouping from the registry. |
| `attempt_status` | enum | yes | `verified`, `inconclusive`, `blocked`, or `failed`. |
| `verification_mode` | enum | yes | `natural`, `cheat-assisted`, or `not-attempted`. |
| `evidence_kind` | enum | yes | `game-state`, `live-artifact`, `dispatch-only`, or `none`. |
| `verified` | boolean | yes | `true` only when FR-003 / FR-003a are satisfied. |
| `evidence_summary` | string | no | Short reviewer-readable explanation of the observed proof. |
| `evidence_artifact_path` | path \| null | no | Optional path to a row-specific artifact. |
| `blocking_reason` | string \| null | no | Required when not verified. |
| `setup_actions` | array of string | no | Unit provisioning, target prep, or other setup actions used. |
| `improvement_state` | enum | yes | `none`, `candidate`, `applied`, or `exhausted`. |
| `improvement_note` | string | no | What changed or why no better action remains. |
| `source_run_id` | string | yes | Back-reference to the containing run. |

**Validation**:

- `verified=true` requires `attempt_status=verified` and `evidence_kind` in `{game-state, live-artifact}`.
- `verification_mode=cheat-assisted` requires at least one recorded cheat-backed setup action.
- Any non-verified record requires `blocking_reason`.
- `improvement_state=applied` or `candidate` requires a non-empty `improvement_note`.

---

## Entity: `ImprovementAction`

One concrete change proposed or applied to improve the next run.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `action_id` | string | yes | Stable per-campaign identifier. |
| `command_id` | string | yes | Command targeted by the action. |
| `action_type` | enum | yes | `setup-change`, `target-change`, `evidence-change`, `timing-change`, `cheat-escalation`, or `skip-no-better-action`. |
| `trigger_reason` | string | yes | Why the previous attempt was insufficient. |
| `applies_to_run_id` | string | yes | The run that should consume this change next. |
| `status` | enum | yes | `planned`, `applied`, `superseded`, or `rejected`. |
| `details` | string | yes | Reviewer-readable description of the concrete change. |

**Validation**:

- Each unverified command should have either a planned/applied action or an explicit `skip-no-better-action` record.
- `cheat-escalation` must not be created until natural attempts have stalled, unless the campaign override disables natural-first behavior.

---

## Entity: `RunSummary`

Aggregate metrics for one Itertesting run.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Matches the parent run id. |
| `tracked_commands` | integer | yes | Total commands covered by the run. |
| `verified_total` | integer | yes | Total verified commands. |
| `verified_natural` | integer | yes | Verified without cheat-backed setup. |
| `verified_cheat_assisted` | integer | yes | Verified with cheat-backed setup. |
| `inconclusive_total` | integer | yes | Commands attempted without sufficient evidence. |
| `blocked_total` | integer | yes | Commands blocked by setup, target, or observability issues. |
| `failed_total` | integer | yes | Commands that failed due to explicit runtime or logic failure. |
| `newly_verified` | array of string | yes | Commands newly verified relative to the prior run, if any. |
| `regressed` | array of string | yes | Commands previously verified but no longer verified. |
| `stalled` | array of string | yes | Commands still not improving despite retries. |

**Validation**:

- `verified_natural + verified_cheat_assisted = verified_total`.
- Totals must reconcile with the command records.

---

## Entity: `RunComparison`

Structured comparison between consecutive runs.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `previous_run_id` | string | yes | Prior run in the same campaign. |
| `current_run_id` | string | yes | Current run. |
| `coverage_delta` | integer | yes | Net change in total verified commands. |
| `natural_delta` | integer | yes | Net change in naturally verified commands. |
| `cheat_delta` | integer | yes | Net change in cheat-assisted verified commands. |
| `changed_commands` | array of string | yes | Commands whose verification record changed materially. |
| `improvement_actions_applied` | array of string | yes | Actions consumed by the current run. |
| `stall_detected` | boolean | yes | True when no meaningful improvement occurred. |

**Validation**:

- Present only when a prior run exists.
- `stall_detected=true` requires either zero positive coverage delta or explicit exhausted improvement state for remaining commands.

---

## Relationships

```text
ItertestingCampaign
└── ItertestingRun[]
    ├── CommandVerificationRecord[]
    ├── ImprovementAction[]
    ├── RunSummary
    └── RunComparison (optional)
```

The existing behavioral registry remains the source of tracked commands and categories. Itertesting adds campaign/run/improvement state around that inventory rather than replacing it.
