# Phase 1 Data Model — Live Transport Provisioning

**Branch**: `015-live-transport-provisioning` | **Date**: 2026-04-22  
**Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

015 does not add external schemas or database tables. It specializes the 014 fixture/report model so `transport_unit` carries enough runtime detail to support discovery, natural provisioning, refresh, replacement, compatibility checks, and explicit fallback reporting inside the existing Itertesting bundle.

---

## Entity: `LiveValidationSession`

The parent record for one prepared live Itertesting run. This remains the existing `ItertestingRun` plus its bundle under `reports/itertesting/<run-id>/`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Stable run identifier and artifact directory name. |
| `campaign_id` | string | yes | Parent closeout sequence identifier. |
| `fixture_provisioning` | `FixtureProvisioningResult` | yes | Existing class-level provisioning result from 014. |
| `transport_provisioning` | `TransportProvisioningResult` | yes | Detailed transport lifecycle record for `transport_unit`. |
| `command_records` | array of `CommandVerificationRecord` | yes | One per tracked command. |
| `failure_classifications` | array of `FailureCauseClassification` | yes | Derived for unverified direct rows. |
| `contract_health_decision` | `ContractHealthDecision` | yes | Maintainer-facing stop/proceed decision. |

**Validation**:

- A 015 run is not review-ready unless `transport_provisioning` agrees with the `transport_unit` row in `fixture_provisioning.class_statuses`.
- The bundle must let a maintainer answer both "what transport was used?" and "which commands were still blocked because of transport?" from one artifact set.

---

## Entity: `SupportedTransportVariant`

The static definition of a live unit type that may satisfy `transport_unit`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `variant_id` | string | yes | Stable identifier such as `armatlas` or `armhvytrans`. |
| `def_name` | string | yes | Unit-def name used for runtime resolution. |
| `resolution_source` | enum | yes | `invoke_callback`, `preexisting_snapshot`, or `audit_reference`. |
| `provisioning_mode` | enum | yes | `reuse-only`, `natural-build`, or `fallback-spawn`. |
| `payload_rules` | array of string | yes | Reviewer-facing compatibility notes for supported payloads. |
| `priority` | integer | yes | Lower number means preferred candidate when multiple variants are valid. |

**Validation**:

- Each supported variant must resolve to a live `def_id` before natural or fallback provisioning uses it.
- The default candidate set must include at least two supported variants to satisfy SC-007.

---

## Entity: `TransportCandidate`

The concrete live unit instance being considered to satisfy `transport_unit`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `candidate_id` | string | yes | Stable per-run identifier. |
| `variant_id` | string | yes | References `SupportedTransportVariant`. |
| `unit_id` | integer | yes | Live engine unit id. |
| `provenance` | enum | yes | `preexisting`, `naturally_provisioned`, `refreshed`, `replaced`, or `fallback_provisioned`. |
| `readiness_state` | enum | yes | `ready`, `pending`, `lost`, `stale`, `incompatible`, or `refresh_failed`. |
| `payload_compatibility` | enum | yes | `compatible`, `incompatible`, or `not_checked`. |
| `discovered_at` | timestamp | yes | First time the candidate was seen. |
| `supersedes_candidate_id` | string \| null | no | Previous candidate when this is a replacement. |

**Validation**:

- Only candidates in `readiness_state=ready` and `payload_compatibility=compatible` may satisfy pending transport-dependent commands.
- A replacement candidate must preserve the causal chain by referencing the superseded candidate when one exists.

---

## Entity: `TransportLifecycleEvent`

The reviewer-facing transport event log for one run.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `event_id` | string | yes | Stable per-run event identifier. |
| `event_type` | enum | yes | `discovered`, `provision_started`, `provision_succeeded`, `refreshed`, `replaced`, `lost`, `fallback_used`, `compatibility_failed`, or `provision_failed`. |
| `candidate_id` | string \| null | no | Associated transport candidate if available. |
| `command_scope` | array of string | yes | Commands affected by the event. |
| `reason` | string | yes | Reviewer-facing explanation. |
| `recorded_at` | timestamp | yes | Event time. |

**Validation**:

- Events that block or unblock transport-dependent commands must name the affected commands explicitly.
- `fallback_used` must never appear without a corresponding reviewer-facing reason in the bundle.

---

## Entity: `TransportCompatibilityCheck`

The per-command gate that validates whether a transport candidate can be trusted for the next load/unload action.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `command_id` | string | yes | One of the five transport-dependent command ids. |
| `candidate_id` | string \| null | no | The candidate checked for this command. |
| `payload_unit_id` | integer \| null | no | Payload fixture paired with the check. |
| `result` | enum | yes | `compatible`, `candidate_missing`, `candidate_unusable`, or `payload_incompatible`. |
| `blocking_reason` | string \| null | no | Required when `result != compatible`. |
| `checked_at` | timestamp | yes | When the compatibility gate ran. |

**Validation**:

- Every evaluated transport-dependent command must have exactly one compatibility check.
- `payload_incompatible` must not degrade into a generic payload-missing reason if the payload fixture is otherwise present.

---

## Entity: `TransportProvisioningResult`

The detailed per-run record for how `transport_unit` was satisfied or why it remained blocked.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Parent run id. |
| `supported_variants` | array of `SupportedTransportVariant` | yes | Candidate transport types considered for this run. |
| `active_candidate_id` | string \| null | no | Candidate currently satisfying `transport_unit`, if any. |
| `candidates` | array of `TransportCandidate` | yes | All discovered or created candidates. |
| `lifecycle_events` | array of `TransportLifecycleEvent` | yes | Reviewer-facing transport history for the run. |
| `compatibility_checks` | array of `TransportCompatibilityCheck` | yes | Per-command transport gates. |
| `status` | enum | yes | `preexisting`, `provisioned`, `refreshed`, `replaced`, `fallback_provisioned`, `missing`, or `unusable`. |
| `affected_command_ids` | array of string | yes | Transport-dependent commands blocked by this result. |
| `completed_at` | timestamp | yes | When transport evaluation finished. |

**Validation**:

- `status` must agree with the `transport_unit` class status in `fixture_provisioning`.
- `affected_command_ids` must be limited to the five transport-dependent commands.
- `fallback_provisioned` must be visible as distinct from ordinary `provisioned`.

---

## Entity: `TransportCommandImpact`

The transport-specific blocker projection into the broader failure-classification and closeout model.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `command_id` | string | yes | Transport-dependent command id. |
| `transport_status` | enum | yes | Mirrors the relevant transport result for the command. |
| `primary_cause` | enum | yes | `missing_fixture`, `predicate_or_evidence_gap`, `behavioral_failure`, or `transport_interruption`. |
| `transport_detail` | string | yes | Exact reason tied to provisioning or compatibility. |
| `review_mode` | enum | yes | `ordinary`, `secondary_only`, or `blocked_foundational`. |

**Validation**:

- A transport-blocked command gets `primary_cause=missing_fixture` only when the session itself is otherwise healthy enough to trust the block.
- Unrelated commands must never inherit a transport blocker.

---

## Relationships

```text
LiveValidationSession
├── FixtureProvisioningResult
│   └── FixtureClassStatus[transport_unit]
├── TransportProvisioningResult
│   ├── SupportedTransportVariant[]
│   ├── TransportCandidate[]
│   ├── TransportLifecycleEvent[]
│   └── TransportCompatibilityCheck[]
├── CommandVerificationRecord[]
├── FailureCauseClassification[]
└── ContractHealthDecision
```

015 keeps the 014 bundle structure intact but gives `transport_unit` a real lifecycle model so discovery, provisioning, refresh, compatibility, and blocker reporting stop collapsing into one missing-fixture heuristic.
