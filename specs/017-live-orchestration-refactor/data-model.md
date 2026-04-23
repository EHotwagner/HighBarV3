# Phase 1 Data Model — Live Orchestration Refactor

**Branch**: `017-live-orchestration-refactor` | **Date**: 2026-04-23  
**Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

017 does not add a database or a new external wire schema. It restructures the existing Itertesting bundle around explicit execution, metadata, and interpretation seams so maintainers can tell which layer recorded a fact, which rule interpreted it, and why the final fixture or transport decision was made.

---

## Entity: `LiveExecutionCapture`

The execution-layer handoff for one live, synthetic, or skipped-live run before bundle synthesis.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Stable run identifier and bundle directory name. |
| `setup_mode` | enum | yes | Existing run mode such as `natural`, `mixed`, or `cheat-assisted`. |
| `command_rows` | array of row objects | yes | Direct command outcomes only; metadata is no longer mixed into this list by convention. |
| `metadata_records` | array of `MetadataRecordEnvelope` | yes | Typed metadata captured during execution or attached from related probes. |
| `collection_notes` | array of string | no | Non-fatal collection observations such as fallback use or missing optional evidence. |
| `collected_at` | timestamp | yes | When the handoff became complete for interpretation. |

**Validation**:

- `command_rows` must not require marker-name filtering to distinguish them from metadata.
- Every metadata item used for bundle synthesis must be present in `metadata_records`, not discovered later by raw row scanning.

---

## Entity: `MetadataRecordEnvelope`

The canonical representation of one recorded metadata fact.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `record_type` | string | yes | Stable type id such as `bootstrap_readiness`, `runtime_capability_profile`, or `map_source_decision`. |
| `source_layer` | enum | yes | `live_execution`, `standalone_probe`, `run_mode_policy`, or another explicit producer. |
| `sequence_index` | integer | yes | Deterministic ordering within the capture. |
| `payload` | object | yes | Structured record data. |
| `recorded_at` | timestamp | yes | When the fact was observed or attached. |
| `interpretation_status` | enum | yes | `handled`, `warning`, or `unhandled`. |

**Validation**:

- Each `record_type` must have one authoritative collection definition.
- Unknown `record_type` values must still be preserved as envelopes and must not be dropped during serialization.

---

## Entity: `MetadataInterpretationRule`

The explicit rule that defines how one metadata record type affects bundle synthesis.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `record_type` | string | yes | Must match `MetadataRecordEnvelope.record_type`. |
| `consumer` | string | yes | Bundle concern affected, such as `bootstrap_readiness`, `fixture_authority`, or `transport_status`. |
| `required_fields` | array of string | yes | Minimum payload keys needed for normal interpretation. |
| `fallback_behavior` | enum | yes | `warning_only`, `preserve_and_block`, or another explicit strategy. |
| `warning_template` | string | no | Maintainer-visible warning text when interpretation cannot complete. |
| `owner_module` | string | yes | The one code location where this interpretation rule is defined. |

**Validation**:

- Every known `record_type` must map to exactly one interpretation rule.
- If no rule exists, the record becomes an `InterpretationWarning` and blocks full interpretation.

---

## Entity: `RunModeEvidencePolicy`

The explicit policy for how non-live or partially live modes affect final fixture and transport claims.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `setup_mode` | enum | yes | Parent run mode. |
| `baseline_guaranteed_fixtures` | array of string | yes | Fixture classes that the selected mode may treat as guaranteed without live proof. |
| `transport_default_status` | enum | yes | `unknown`, `unproven`, or `mode_qualified_non_live`. |
| `counts_as_live_evidence` | boolean | yes | Whether this mode can establish live evidence for success criteria. |
| `policy_reason` | string | yes | Maintainer-facing explanation of the policy. |

**Validation**:

- Synthetic and skipped-live modes must not upgrade fixture or transport results into live-proven states.
- Baseline guarantees must come from this policy, not from absent contradictory evidence.

---

## Entity: `FixtureStateTransition`

The diagnostic history item for one fixture class or transport-relevant resource.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `fixture_class` | string | yes | Named class such as `builder`, `transport_unit`, or `payload_unit`. |
| `state` | enum | yes | `planned`, `provisioned`, `refreshed`, `invalidated`, `missing`, `unknown`, or `mode_qualified_non_live`. |
| `observed_source` | string | yes | Collection source such as `live_execution` or `run_mode_policy`. |
| `detail` | string | yes | Reviewer-facing explanation of the state change. |
| `affected_commands` | array of string | yes | Commands whose availability depends on this fixture state. |
| `recorded_at` | timestamp | yes | When the state was recorded. |

**Validation**:

- The final availability decision for a fixture class must use the latest explicit transition.
- Earlier transitions remain preserved for diagnosis and must not be overwritten or discarded.

---

## Entity: `TransportAvailabilityDecision`

The authoritative final decision for transport availability in the run bundle.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `availability_status` | enum | yes | `available`, `missing`, `unproven`, `unknown`, or `mode_qualified_non_live`. |
| `explicit_evidence` | boolean | yes | Whether a transport claim is backed by observed run evidence. |
| `authoritative_transition` | `FixtureStateTransition` \| null | no | Latest transport-related transition when available. |
| `reason` | string | yes | Reviewer-facing explanation of the decision. |
| `diagnostic_history` | array of `FixtureStateTransition` | yes | Preserved transport timeline. |

**Validation**:

- A live run with bootstrap metadata but no command-row or transport evidence must resolve to `unknown` or `unproven`.
- Non-live mode qualification must remain visible instead of being reported as ordinary live availability.

---

## Entity: `InterpretationWarning`

The maintainer-visible signal that preserved evidence exists but interpretation is incomplete.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `warning_id` | string | yes | Stable bundle identifier. |
| `record_type` | string | yes | Related metadata type. |
| `severity` | enum | yes | `warning` or `blocking_warning`. |
| `message` | string | yes | Maintainer-visible explanation. |
| `blocks_full_interpretation` | boolean | yes | Whether the run may be considered fully interpreted. |
| `recorded_at` | timestamp | yes | When the warning was created. |

**Validation**:

- Unknown or partially handled metadata that affects bundle interpretation must create a blocking warning.
- Warning generation must preserve the original record instead of replacing it.

---

## Entity: `RunInterpretationResult`

The bundle-ready synthesis product that combines execution facts, metadata rules, and run-mode policy.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `bootstrap_readiness` | existing structured record | yes | Final bootstrap assessment. |
| `runtime_capability_profile` | existing structured record | yes | Final capability summary. |
| `prerequisite_resolution` | array | yes | Final prerequisite-resolution records. |
| `map_source_decisions` | array | yes | Final map-source decisions. |
| `fixture_transitions` | array of `FixtureStateTransition` | yes | Full fixture history. |
| `transport_decision` | `TransportAvailabilityDecision` | yes | Final transport authority. |
| `failure_classifications` | array | yes | Existing failure-cause summaries derived from authoritative decisions. |
| `interpretation_warnings` | array of `InterpretationWarning` | yes | Preserved interpretation gaps. |
| `decision_trace` | array of trace items | yes | Maps bundle decisions back to the responsible layer and rule. |
| `fully_interpreted` | boolean | yes | False when blocking warnings remain. |

**Validation**:

- `fully_interpreted` must be false whenever a blocking warning exists.
- Fixture, transport, blocker, and report conclusions must all be derived from this result rather than from repeated raw-row heuristics in later layers.

---

## Relationships

```text
LiveExecutionCapture
├── MetadataRecordEnvelope[]
└── command_rows[]

MetadataRecordEnvelope
└── MetadataInterpretationRule

RunModeEvidencePolicy
└── FixtureStateTransition[]

RunInterpretationResult
├── LiveExecutionCapture
├── RunModeEvidencePolicy
├── FixtureStateTransition[]
├── TransportAvailabilityDecision
└── InterpretationWarning[]
```

017 keeps the existing maintainer-visible bundle but makes its authority explicit: execution records facts, interpretation rules decide meaning, and warnings prevent silent success when meaning is incomplete.
