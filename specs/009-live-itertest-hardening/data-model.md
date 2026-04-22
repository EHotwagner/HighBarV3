# Phase 1 Data Model — Live Itertesting Hardening

**Branch**: `009-live-itertest-hardening` | **Date**: 2026-04-22  
**Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

This feature extends the live Itertesting workflow without introducing a database or public API schema. All entities are workflow-backed records or design-time contracts consumed by the existing behavioral coverage and reporting surfaces.

---

## Entity: `LiveFixtureProfile`

Describes the prerequisite live state that the default bounded Itertesting run must establish before direct command attempts begin.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `profile_id` | string | yes | Stable identifier for the default live fixture profile. |
| `fixture_classes` | tuple<string> | yes | Required fixture classes such as commander, builder, hostile target, reclaim target, transport-capable unit, or resource baseline. |
| `supported_command_ids` | tuple<string> | yes | Direct commands expected to start from valid prerequisite state under this profile. |
| `optional_fixture_classes` | tuple<string> | no | Extra fixtures that improve attempt quality but are not mandatory for run start. |
| `provisioning_budget_seconds` | integer | yes | Time budget for preparing the live profile before command dispatch. |
| `fallback_behavior` | enum | yes | Expected behavior when a fixture class cannot be provisioned: `classify_missing_fixture` or `interrupt_run`. |

**Validation**:

- `supported_command_ids` must be a subset of the directly verifiable command inventory.
- `provisioning_budget_seconds` must be positive and bounded for unattended runs.
- `fallback_behavior` must never silently downgrade missing fixtures into ordinary behavioral failures.

---

## Entity: `FixtureProvisioningResult`

Run-scoped record of whether each required fixture class was successfully established.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Parent live run identifier. |
| `profile_id` | string | yes | Fixture profile used for the run. |
| `provisioned_fixture_classes` | tuple<string> | yes | Fixture classes confirmed present before command attempts. |
| `missing_fixture_classes` | tuple<string> | yes | Fixture classes not satisfied in time. |
| `affected_command_ids` | tuple<string> | yes | Commands blocked by the missing fixtures. |
| `completed_at` | timestamp | yes | UTC time when provisioning finished. |

**Validation**:

- `provisioned_fixture_classes` and `missing_fixture_classes` must be disjoint.
- Commands listed in `affected_command_ids` must map to at least one missing fixture class.

---

## Entity: `ChannelHealthOutcome`

Captures run-level status of the plugin command channel across a live Itertesting campaign.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Parent live run identifier. |
| `status` | enum | yes | `healthy`, `degraded`, `recovered`, `interrupted`. |
| `first_failure_stage` | enum | no | Where degradation first appeared: `startup`, `dispatch`, `verification`, or `shutdown`. |
| `failure_signal` | string | no | Canonical signal text or category used to classify the degradation. |
| `commands_attempted_before_failure` | integer | yes | Count of attempted commands before degradation. |
| `recovery_attempted` | boolean | yes | Whether the wrapper or runner initiated a deterministic retry/recovery step. |
| `finalized_at` | timestamp | yes | UTC time when health outcome was finalized. |

**Validation**:

- `status=healthy` requires `first_failure_stage` to be empty.
- `status=interrupted` requires a non-empty `failure_signal`.
- `commands_attempted_before_failure` must be non-negative and monotonically consistent with run summaries.

---

## Entity: `ArmVerificationRule`

Defines the live evidence strategy for a command whose real effect is not reliably captured by generic verification defaults.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `command_id` | string | yes | Stable command identifier. |
| `rule_mode` | enum | yes | `generic`, `movement_tuned`, `combat_tuned`, `construction_tuned`, or other named live rule category. |
| `expected_effect` | string | yes | Human-readable summary of the observable state change the rule looks for. |
| `evidence_window_shape` | string | yes | High-level timing window description, not implementation code. |
| `predicate_family` | string | yes | Predicate concept used to judge the effect, such as position delta, health delta, or unit-count/build-progress change. |
| `fallback_classification` | enum | yes | Cause category to use if expected evidence is still insufficient. |

**Validation**:

- Every directly verifiable command must resolve to exactly one rule.
- `fallback_classification` must be a valid `FailureCauseClassification`.
- Commands remaining on `generic` mode must have evidence that generic rules are sufficient.

---

## Entity: `FailureCauseClassification`

Canonical primary cause assigned to each non-verified directly verifiable command.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `command_id` | string | yes | Stable command identifier. |
| `run_id` | string | yes | Parent run identifier. |
| `primary_cause` | enum | yes | `missing_fixture`, `transport_interruption`, `predicate_or_evidence_gap`, `behavioral_failure`. |
| `supporting_detail` | string | yes | Reviewer-facing explanation for the chosen cause. |
| `source_scope` | enum | yes | `bootstrap`, `channel_health`, `verification_rule`, or `command_outcome`. |

**Validation**:

- Every non-verified directly verifiable command must have exactly one primary cause.
- `primary_cause=transport_interruption` requires a non-healthy `ChannelHealthOutcome`.
- `primary_cause=missing_fixture` requires the command to appear in `FixtureProvisioningResult.affected_command_ids`.

---

## Entity: `LiveHardeningSummary`

Run or campaign summary fields added to maintainers’ reviewer-facing outputs.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Parent run identifier. |
| `direct_commands_attempted` | integer | yes | Direct commands that reached a real attempt state. |
| `direct_commands_blocked_by_fixture` | integer | yes | Commands not attempted because fixture provisioning failed. |
| `transport_interrupted` | boolean | yes | Whether the run degraded due to channel failure. |
| `arm_rules_tuned_count` | integer | yes | Number of commands using non-generic live verification rules. |
| `manual_restart_required` | boolean | yes | Whether an operator had to restart coordinator or engine to finish the run. |

**Validation**:

- `direct_commands_attempted + direct_commands_blocked_by_fixture` must not exceed directly verifiable inventory.
- `manual_restart_required=false` is the expected steady-state path for successful reference runs.

---

## Relationships

```text
LiveFixtureProfile
└── FixtureProvisioningResult[]
    └── FailureCauseClassification[]

ChannelHealthOutcome
└── FailureCauseClassification[]

ArmVerificationRule[]
└── FailureCauseClassification[]

FixtureProvisioningResult + ChannelHealthOutcome + ArmVerificationRule[]
└── LiveHardeningSummary
```

This model keeps fixture readiness, transport survivability, and evidence quality as separate first-class concepts so reports can explain live failures without collapsing them into one ambiguous bucket.
