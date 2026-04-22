# Phase 1 Data Model — Itertesting Retry Tuning

**Branch**: `008-itertesting-retry-tuning` | **Date**: 2026-04-22  
**Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

This feature extends Itertesting governance and reporting models without introducing database or proto schema changes. All entities are filesystem-backed records consumed by campaign orchestration and reviewer reports.

---

## Entity: `RetryIntensityProfile`

Named retry behavior envelope selected by maintainers.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `profile_name` | enum | yes | `quick`, `standard`, `deep`. |
| `configured_improvement_runs` | integer | yes | Requested budget from maintainer input. |
| `effective_improvement_runs` | integer | yes | Clamped value after global cap enforcement. |
| `stall_window_runs` | integer | yes | Number of recent runs evaluated for stall detection. |
| `min_direct_gain_in_window` | integer | yes | Minimum directly verifiable gain required to continue. |
| `allow_cheat_escalation` | boolean | yes | Whether escalation is permitted after natural stalls. |
| `runtime_target_minutes` | integer | yes | Profile runtime envelope used for warnings/governance. |

**Validation**:

- `effective_improvement_runs = min(configured_improvement_runs, 10)`.
- `stall_window_runs >= 1`.
- `min_direct_gain_in_window >= 0`.

---

## Entity: `CampaignRetryPolicy`

Campaign-level governance values derived from profile + fixed guardrails.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `campaign_id` | string | yes | Campaign identifier. |
| `selected_profile` | `RetryIntensityProfile` | yes | Active profile details. |
| `global_improvement_run_cap` | integer | yes | Always `10`. |
| `direct_target_min` | integer | yes | Always `20` for this feature. |
| `runtime_target_minutes` | integer | yes | Default `15` for successful target-reaching runs. |
| `natural_first` | boolean | yes | Default `true`; controls escalation ordering. |
| `warning_threshold_runs_without_gain` | integer | yes | Trigger point for disproportionate intensity warnings. |

**Validation**:

- `global_improvement_run_cap` must be immutable at `10`.
- `direct_target_min` must be immutable at `20` for feature acceptance.
- `natural_first=true` unless explicit operator override is provided.

---

## Entity: `RunProgressSnapshot`

Per-run progress snapshot used for stall detection and report summaries.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Timestamp-based run id. |
| `sequence_index` | integer | yes | Run order within campaign. |
| `duration_seconds` | integer | yes | Observed runtime for this run. |
| `direct_verified_natural` | integer | yes | Directly verifiable commands validated naturally. |
| `direct_verified_cheat_assisted` | integer | yes | Directly verifiable commands validated with cheat support. |
| `direct_unverified_total` | integer | yes | Remaining direct commands not verified. |
| `non_observable_tracked` | integer | yes | Non-directly-observable commands tracked separately. |
| `direct_gain_vs_previous` | integer | yes | Net direct verified delta against previous run. |
| `stall_detected` | boolean | yes | Result of windowed stall evaluation. |

**Validation**:

- `direct_verified_natural + direct_verified_cheat_assisted` equals total direct verified for that run.
- `direct_gain_vs_previous` is `0` for the first run.
- `stall_detected=true` only when evaluated window does not meet minimum gain.

---

## Entity: `CampaignStopDecision`

Machine-readable and reviewer-facing explanation for why campaign execution ended.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `decision_id` | string | yes | Unique decision identifier. |
| `campaign_id` | string | yes | Parent campaign reference. |
| `final_run_id` | string | yes | Run on which termination was decided. |
| `stop_reason` | enum | yes | `target_reached`, `stalled`, `budget_exhausted`, `runtime_guardrail`, `interrupted`. |
| `direct_verified_total` | integer | yes | Final directly verifiable verified total. |
| `target_met` | boolean | yes | Whether direct target (20) was achieved. |
| `message` | string | yes | Human-readable explanation emitted in reports/logs. |
| `created_at` | timestamp | yes | UTC time of decision emission. |

**Validation**:

- Every completed campaign must contain exactly one stop decision.
- `target_met=true` requires `direct_verified_total >= 20`.
- `stop_reason=target_reached` requires `target_met=true`.

---

## Entity: `ReusableImprovementInstruction`

Versioned per-command guidance reused across campaigns.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `command_id` | string | yes | Stable command key. |
| `revision` | integer | yes | Monotonic revision number. |
| `status` | enum | yes | `active`, `superseded`, `retired`. |
| `guidance` | string | yes | Concrete improvement action text. |
| `last_outcome` | enum | yes | `verified`, `inconclusive`, `blocked`, `failed`. |
| `last_run_id` | string | yes | Source run for latest update. |
| `updated_at` | timestamp | yes | UTC update time. |

**Validation**:

- Revisions must increment by one for each command update.
- `status=superseded` requires a higher active revision to exist.
- Every command that remains unverified after a run must have either updated guidance or explicit retirement rationale.

---

## Entity: `CoverageOutcomeSummary`

Campaign-level metrics emitted after each run and at campaign completion.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `campaign_id` | string | yes | Parent campaign id. |
| `run_id` | string | yes | Run producing this summary. |
| `direct_target` | integer | yes | `20` for this feature. |
| `direct_verified_total` | integer | yes | Sum of natural + cheat-assisted direct verified. |
| `direct_verified_natural` | integer | yes | Natural-only direct verified count. |
| `direct_verified_cheat_assisted` | integer | yes | Cheat-assisted direct verified count. |
| `non_observable_tracked` | integer | yes | Separate tracking count. |
| `runtime_elapsed_seconds` | integer | yes | Campaign elapsed wall-clock at summary point. |
| `disproportionate_intensity_warning` | boolean | yes | True when configured intensity exceeds observed gain need. |

**Validation**:

- `direct_verified_natural + direct_verified_cheat_assisted = direct_verified_total`.
- `runtime_elapsed_seconds` must be non-decreasing across run sequence.

---

## Relationships

```text
CampaignRetryPolicy
└── RunProgressSnapshot[]
    └── CoverageOutcomeSummary

CampaignRetryPolicy
└── ReusableImprovementInstruction[]

CampaignRetryPolicy
└── CampaignStopDecision (exactly one on completion)
```

This model extends the previous Itertesting design by making retry intent, stall governance, and runtime targets first-class entities.
