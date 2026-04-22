# Phase 1 Data Model — Fixture Bootstrap Simplification

**Branch**: `014-fixture-bootstrap-simplification` | **Date**: 2026-04-22  
**Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

014 does not add external schemas or database tables. It formalizes the internal Itertesting bundle so fixture planning, provisioning, refresh, and blocker interpretation all come from one model.

---

## Entity: `LiveValidationSession`

The parent record for one prepared live Itertesting run. This remains the existing `ItertestingRun` plus its bundle under `reports/itertesting/<run-id>/`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Stable run identifier and artifact directory name. |
| `campaign_id` | string | yes | Parent closeout sequence identifier. |
| `setup_mode` | enum | yes | `natural`, `mixed`, or `cheat-assisted`. |
| `fixture_profile` | `LiveFixtureProfile` | yes | Static dependency surface for the run. |
| `fixture_provisioning` | `FixtureProvisioningResult` | yes | Dynamic provisioning result for the run. |
| `channel_health` | `ChannelHealthOutcome` | yes | Channel trustworthiness for the run. |
| `command_records` | array of `CommandVerificationRecord` | yes | One per tracked command. |
| `failure_classifications` | array of `FailureCauseClassification` | yes | Derived for unverified direct rows. |
| `contract_health_decision` | `ContractHealthDecision` | yes | Maintainer-facing stop/proceed decision. |

**Validation**:

- A 014 live-closeout run is not review-ready unless `fixture_profile`, `fixture_provisioning`, and `channel_health` are present together.
- The run bundle must let a maintainer answer both "which fixture classes were usable?" and "which commands were blocked because of them?" without consulting a second rule path.

---

## Entity: `CommandFixtureDependency`

The static requirement definition for one direct command. This is derived from `DEFAULT_LIVE_FIXTURE_CLASS_BY_COMMAND` in `bootstrap.py`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `command_id` | string | yes | Stable command identifier such as `cmd-load-units`. |
| `required_fixture_classes` | array of string | yes | Named classes required before behavior is judged. |
| `provisioning_strategy` | enum | yes | `baseline`, `shared-instance`, or `refreshable-shared-instance`. |
| `blocking_fallback` | enum | yes | `missing_fixture` or `transport_interruption_only_if_session_unhealthy`. |

**Validation**:

- Every direct `channel_a_command` in the live fixture profile must resolve to exactly one dependency record.
- No second hard-coded blocklist may exist outside this dependency model.

---

## Entity: `SharedFixtureInstance`

The reusable live object or target provisioned for a fixture class.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `instance_id` | string | yes | Stable per-run identifier. |
| `fixture_class` | string | yes | One of the named live fixture classes. |
| `backing_kind` | enum | yes | `unit`, `feature`, `area`, or `target-handle`. |
| `backing_id` | string | yes | Engine id or deterministic synthetic handle. |
| `usability_state` | enum | yes | `ready`, `consumed`, `destroyed`, `out_of_range`, `stale`, or `refresh_failed`. |
| `refresh_count` | integer | yes | Number of successful replacements or refreshes. |
| `last_ready_at` | timestamp \| null | yes | Last time the instance was known usable. |
| `replacement_of` | string \| null | no | Previous instance id when this is a replacement. |

**Validation**:

- `refresh_count` must increment only when a replacement or refresh succeeds.
- A class may have zero ready instances only if its class-level status is not `provisioned` or `refreshed`.

---

## Entity: `FixtureClassStatus`

The class-level status used by the run bundle and report.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `fixture_class` | string | yes | Named fixture class. |
| `status` | enum | yes | `planned`, `provisioned`, `refreshed`, `missing`, or `unusable`. |
| `planned_command_ids` | array of string | yes | Commands depending on the class in this profile. |
| `ready_instance_ids` | array of string | yes | Backing shared instances currently usable. |
| `last_transition_reason` | string | yes | Reviewer-facing reason for the latest status. |
| `affected_command_ids` | array of string | yes | Commands blocked when the class is missing or unusable. |
| `updated_at` | timestamp | yes | Last status change time. |

**Validation**:

- `affected_command_ids` must be empty for `status` in `{planned, provisioned, refreshed}`.
- `status=missing` or `status=unusable` must list only commands whose dependency records include that class.
- The bundle must preserve aggregate `provisioned_fixture_classes`, `missing_fixture_classes`, and `affected_command_ids` derived from these status rows for backward-compatible report summaries.

---

## Entity: `FixtureProvisioningResult`

The dynamic per-run result that replaces ad hoc simplified-bootstrap blocker logic.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Parent run id. |
| `profile_id` | string | yes | References the active fixture profile. |
| `class_statuses` | array of `FixtureClassStatus` | yes | One entry per planned fixture class. |
| `shared_fixture_instances` | array of `SharedFixtureInstance` | no | Concrete reusable fixtures prepared during the run. |
| `provisioned_fixture_classes` | array of string | yes | Aggregate derived from class statuses. |
| `missing_fixture_classes` | array of string | yes | Aggregate derived from class statuses. |
| `affected_command_ids` | array of string | yes | Union of blocked commands across missing/unusable classes. |
| `completed_at` | timestamp | yes | When provisioning evaluation finished. |

**Validation**:

- `profile_id` must match the active `LiveFixtureProfile`.
- Every class in the profile must appear exactly once in `class_statuses`.
- A command may be fixture-blocked only if at least one missing or unusable class status names it in `affected_command_ids`.

---

## Entity: `CommandOutcomeRecord`

The per-command result remains the existing `CommandVerificationRecord` plus `FailureCauseClassification`.

### `CommandVerificationRecord`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `command_id` | string | yes | Stable command identifier. |
| `attempt_status` | enum | yes | `verified`, `inconclusive`, `blocked`, or `failed`. |
| `verification_mode` | enum | yes | `natural`, `cheat-assisted`, or `not-attempted`. |
| `evidence_kind` | enum | yes | `game-state`, `live-artifact`, `dispatch-only`, or `none`. |
| `verified` | boolean | yes | True only when direct evidence was observed. |
| `blocking_reason` | string \| null | no | Required for blocked or failed rows. |

### `FailureCauseClassification`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `command_id` | string | yes | Matches the command record. |
| `primary_cause` | enum | yes | `missing_fixture`, `transport_interruption`, `predicate_or_evidence_gap`, or `behavioral_failure`. |
| `supporting_detail` | string | yes | Reviewer-facing explanation. |
| `source_scope` | enum | yes | `bootstrap`, `channel_health`, `verification_rule`, or `command_outcome`. |

**Validation**:

- A row gets `missing_fixture` only when at least one fixture class status is `missing` or `unusable` for that command.
- A row gets `behavioral_failure` only when the session stayed healthy enough and all required classes were usable.
- The same command must not be blocked by a simplified-bootstrap-only rule once authoritative provisioning is present.

---

## Entity: `CloseoutDecisionRecord`

The run- and campaign-level readiness decision remains the existing `ContractHealthDecision` and `CampaignStopDecision`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `decision_status` | enum | yes | `ready_for_itertesting`, `blocked_foundational`, or `needs_pattern_review`. |
| `blocking_issue_ids` | array of string | yes | Includes fixture blockers when classes remain missing or unusable. |
| `summary_message` | string | yes | Maintainer-readable reason. |
| `stop_or_proceed` | enum | yes | `stop_for_repair`, `proceed_with_improvement`, or `proceed_but_flag_review`. |

**Validation**:

- Any run that still has intended-coverage commands blocked by missing or unusable fixture classes must not be `ready_for_itertesting`.
- Refresh failure for a class must keep dependent commands explicitly fixture-blocked instead of downgrading them into a generic evidence gap.

---

## Relationships

```text
LiveValidationSession
├── LiveFixtureProfile
├── FixtureProvisioningResult
│   ├── FixtureClassStatus[]
│   └── SharedFixtureInstance[]
├── CommandVerificationRecord[]
├── FailureCauseClassification[]
├── ChannelHealthOutcome
└── CloseoutDecisionRecord
```

014 makes fixture interpretation flow from one static dependency model plus one dynamic provisioning result, so bootstrap behavior, report output, and closeout gating stop disagreeing about why a command could not be judged.
