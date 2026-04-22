# Phase 1 Data Model — Itertesting Channel Stability

**Branch**: `013-itertesting-channel-stability` | **Date**: 2026-04-22  
**Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

013 does not introduce database tables or new transport schemas. Its data model formalizes how the existing Itertesting run bundle records whether a live session stayed trustworthy long enough to judge command behavior.

---

## Entity: `LiveValidationSession`

The end-to-end record for one prepared-environment live Itertesting run. This is represented by `ItertestingRun` plus its run bundle under `reports/itertesting/<run-id>/`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Stable run identifier and artifact directory name. |
| `campaign_id` | string | yes | Parent campaign or closeout sequence identifier. |
| `started_at` | timestamp | yes | UTC start time. |
| `completed_at` | timestamp \| null | yes | Null only for interrupted or otherwise incomplete runs kept for diagnosis. |
| `sequence_index` | integer | yes | Zero-based order inside the campaign. |
| `setup_mode` | enum | yes | `natural`, `mixed`, or `cheat-assisted`; used to interpret fixture coverage and direct evidence. |
| `summary` | `RunSummary` | yes | Aggregated outcome counts, including fixture-blocked totals and transport interruption totals. |
| `channel_health` | `ChannelHealthOutcome` \| null | no | Required for 013 live-closeout interpretation. |
| `fixture_profile` | `LiveFixtureProfile` \| null | no | Records the planned fixture surface for the run. |
| `fixture_provisioning` | `FixtureProvisioningResult` \| null | no | Records what the run actually had available. |
| `command_records` | array of `CommandVerificationRecord` | yes | One per tracked command. |
| `failure_classifications` | array of `FailureCauseClassification` | no | Derived per-command explanation for unverified direct rows. |
| `contract_health_decision` | `ContractHealthDecision` \| null | no | Maintainer-facing decision about whether ordinary improvement work may proceed. |

**Validation**:

- A 013 live-closeout run is not review-ready unless `channel_health`, `fixture_profile`, and `fixture_provisioning` are present.
- `completed_at` must be present for any run used toward the three-consecutive-reruns success gate.
- `summary.transport_interrupted=true` requires `channel_health.status` in `{degraded, recovered, interrupted}`.

---

## Entity: `ChannelHealthOutcome`

The lifecycle verdict for the command path during one live validation session.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Parent run id. |
| `status` | enum | yes | `healthy`, `degraded`, `recovered`, or `interrupted`. |
| `first_failure_stage` | enum \| null | yes | `startup`, `dispatch`, `verification`, `shutdown`, or `null` when healthy. |
| `failure_signal` | string | yes | Human-readable signal such as `plugin command channel is not connected`. |
| `commands_attempted_before_failure` | integer | yes | Count of attempted rows before the first lifecycle break. |
| `recovery_attempted` | boolean | yes | Whether the wrapper or workflow tried to continue or restart after the failure. |
| `finalized_at` | timestamp | yes | When the lifecycle verdict was written. |

**Validation**:

- `status=healthy` requires `first_failure_stage=null` and an empty `failure_signal`.
- `status!=healthy` requires a non-empty `failure_signal`.
- `commands_attempted_before_failure` must be less than or equal to the number of non-blocked command records in the run.

**State transitions**:

- Normal path: `healthy` for the full run.
- Degraded path: `healthy -> degraded -> recovered` when a lifecycle issue is detected and the session remains usable.
- Interrupted path: `healthy -> interrupted` when the session can no longer support trustworthy command evaluation.

---

## Entity: `FixtureProvisioningSurface`

The combination of the planned fixture profile and the run-specific provisioning result used to decide whether a command is fixture-blocked.

### `LiveFixtureProfile`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `profile_id` | string | yes | Stable profile identifier, currently `default-live-fixture-profile`. |
| `fixture_classes` | array of string | yes | Baseline fixture classes expected to exist. |
| `supported_command_ids` | array of string | yes | Direct command rows this profile supports. |
| `optional_fixture_classes` | array of string | no | Specialized fixture classes that may remain missing and block subsets of commands. |
| `provisioning_budget_seconds` | integer | yes | Expected bootstrap budget for fixture preparation. |
| `fallback_behavior` | enum | yes | `classify_missing_fixture` or `interrupt_run`. |

### `FixtureProvisioningResult`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Parent run id. |
| `profile_id` | string | yes | References the active fixture profile. |
| `provisioned_fixture_classes` | array of string | yes | Fixture classes actually present. |
| `missing_fixture_classes` | array of string | yes | Fixture classes absent at review time. |
| `affected_command_ids` | array of string | yes | Commands that become fixture-blocked because of the missing classes. |
| `completed_at` | timestamp | yes | When provisioning evaluation finished. |

**Validation**:

- `profile_id` must match the run’s `fixture_profile.profile_id`.
- Every `affected_command_id` must be in `fixture_profile.supported_command_ids`.
- Any command listed in `affected_command_ids` must have a `FailureCauseClassification.primary_cause` of `missing_fixture` unless the run became unhealthy before the command reached a usable evaluation point.

---

## Entity: `CommandOutcomeRecord`

The combination of per-command attempt data and its derived cause classification. This is represented by `CommandVerificationRecord` plus `FailureCauseClassification`.

### `CommandVerificationRecord`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `command_id` | string | yes | Stable command identifier such as `cmd-build-unit`. |
| `command_name` | string | yes | Human-readable command name. |
| `category` | string | yes | Existing registry category. |
| `attempt_status` | enum | yes | `verified`, `inconclusive`, `blocked`, or `failed`. |
| `verification_mode` | enum | yes | `natural`, `cheat-assisted`, or `not-attempted`. |
| `evidence_kind` | enum | yes | `game-state`, `live-artifact`, `dispatch-only`, or `none`. |
| `verified` | boolean | yes | True only when direct evidence was observed. |
| `blocking_reason` | string \| null | no | Required for non-verified rows. |
| `improvement_state` | enum | yes | `none`, `candidate`, `applied`, or `exhausted`. |
| `improvement_note` | string | no | Guidance or explanation for the next step. |
| `source_run_id` | string | yes | Parent run id. |

### `FailureCauseClassification`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `command_id` | string | yes | Matches the associated command record. |
| `run_id` | string | yes | Parent run id. |
| `primary_cause` | enum | yes | `missing_fixture`, `transport_interruption`, `predicate_or_evidence_gap`, or `behavioral_failure`. |
| `supporting_detail` | string | yes | Short reviewer-facing explanation. |
| `source_scope` | enum | yes | `bootstrap`, `channel_health`, `verification_rule`, or `command_outcome`. |

**Validation**:

- Direct verified rows should not receive a failure classification.
- `primary_cause=transport_interruption` requires `channel_health.status != healthy`.
- `primary_cause=missing_fixture` requires either the command to appear in `affected_command_ids` or the command’s required fixture classes to be absent from `provisioned_fixture_classes`.
- `primary_cause=behavioral_failure` is valid only when neither transport interruption nor missing fixtures provide a better explanation.

---

## Entity: `CloseoutDecisionRecord`

The maintainer-facing readiness decision for whether a run can be treated as trustworthy enough for normal Itertesting tuning.

This is represented by `ContractHealthDecision` for the run and `CampaignStopDecision` for the campaign.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `decision_status` | enum | yes | `ready_for_itertesting`, `blocked_foundational`, or `needs_pattern_review`. |
| `blocking_issue_ids` | array of string | yes | Foundational blocker identifiers, if any. |
| `summary_message` | string | yes | Maintainer-readable reason. |
| `stop_or_proceed` | enum | yes | `stop_for_repair`, `proceed_with_improvement`, or `proceed_but_flag_review`. |
| `recorded_at` | timestamp | yes | When the run-level decision was written. |
| `stop_reason` | enum | yes | Campaign-level reason such as `interrupted` or `foundational_blocked`. |
| `target_met` | boolean | yes | Whether the broader campaign target was met. |

**Validation**:

- A run with `channel_health.status=interrupted` during dispatch must not be treated as `ready_for_itertesting` unless later evidence proves the interruption did not invalidate command evaluation.
- A run with unresolved fixture blockers for intended coverage commands must not be treated as fully ready for normal tuning.
- Repeated reruns that show the same channel failure or fixture gap should preserve the same blocker interpretation even when only simulation speed changes between runs.

---

## Relationships

```text
LiveValidationSession
├── ChannelHealthOutcome
├── LiveFixtureProfile
├── FixtureProvisioningResult
├── CommandVerificationRecord[]
├── FailureCauseClassification[]
└── CloseoutDecisionRecord
```

The existing behavioral registry remains the source of tracked commands. 013 adds a stricter interpretation layer over the current run bundle so maintainers can tell whether a live session was stable enough to judge behavior.
