# Phase 1 Data Model — Live Bootstrap Hardening

**Branch**: `016-live-bootstrap-hardening` | **Date**: 2026-04-23  
**Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

016 does not add a database or a new external wire schema. It extends the existing prepared live Itertesting bundle so maintainers can see whether bootstrap began from a viable state, which callback surfaces are actually supported on the current host, how prerequisite identities were resolved, and which map source each workflow used when callback-based map inspection is unavailable.

---

## Entity: `LiveValidationSession`

The parent record for one prepared live closeout run. This remains the existing `ItertestingRun` plus its bundle under `reports/itertesting/<run-id>/`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Stable run identifier and artifact directory name. |
| `fixture_provisioning` | `FixtureProvisioningResult` | yes | Existing class-level provisioning result. |
| `bootstrap_readiness` | `BootstrapReadinessAssessment` | yes | Maintainer-visible readiness result recorded before or during bootstrap. |
| `runtime_capability_profile` | `RuntimeCapabilityProfile` | yes | New capability summary describing which callback surfaces are usable on this host. |
| `callback_diagnostics` | array of `CallbackDiagnosticSnapshot` | yes | Preserved reviewer-facing diagnostic evidence. |
| `prerequisite_resolution` | array of `RuntimePrerequisiteResolutionRecord` | yes | Runtime def-name lookup trace for live prerequisites. |
| `map_source_decisions` | array of `MapDataSourceDecision` | yes | Which supported source each consumer used for map-derived targeting. |
| `command_records` | array of `CommandVerificationRecord` | yes | Existing per-command verification outcomes. |
| `failure_classifications` | array of `FailureCauseClassification` | yes | Existing cause summaries for unverified direct commands. |

**Validation**:

- A 016 run is not review-ready unless `bootstrap_readiness` explains whether the first commander build was naturally viable, explicitly seeded, or blocked before continuing.
- `runtime_capability_profile`, `prerequisite_resolution`, and `map_source_decisions` must agree with the narrative shown in `run-report.md`.

---

## Entity: `BootstrapReadinessAssessment`

The maintainer-facing decision about whether prepared live closeout can realistically start commander-driven bootstrap.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Parent run id. |
| `readiness_status` | enum | yes | `natural_ready`, `seeded_ready`, `resource_starved`, or `unknown`. |
| `readiness_path` | enum | yes | `prepared_state`, `explicit_seed`, or `unavailable`. |
| `first_required_step` | string | yes | First commander-built bootstrap step being validated, such as `armmex` or `armvp`. |
| `economy_summary` | string | yes | Reviewer-facing economy snapshot. |
| `reason` | string | yes | Why the run was considered ready, seeded, or blocked. |
| `recorded_at` | timestamp | yes | When readiness was assessed. |

**Validation**:

- `resource_starved` must appear before the first commander-built timeout becomes the primary failure signal for that run.
- `seeded_ready` must never be reported without an explicit reason describing the non-natural readiness path.

---

## Entity: `RuntimeCapabilityProfile`

The reportable summary of which live inspection surfaces are supported on the current host.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `profile_id` | string | yes | Stable identifier for the observed capability set. |
| `supported_callbacks` | array of integer | yes | Callback ids proven usable on this host, such as `47` and `40`. |
| `supported_scopes` | array of string | yes | Human-readable scopes such as `unit_def_lookup`, `unit_def_name`, `session_start_map`. |
| `unsupported_callback_groups` | array of string | yes | Reviewer-facing groups such as `unit`, `unitdef_except_name`, `map`, `economy`, `team_mod_cheat_info`. |
| `map_data_source_status` | enum | yes | `hello_static_map`, `callback_map`, or `missing`. |
| `notes` | string | yes | Summary of what the host can and cannot do. |
| `recorded_at` | timestamp | yes | When the capability profile was captured. |

**Validation**:

- A run must not report runtime prerequisite resolution as `resolved` unless the capability profile includes the lookup surfaces needed for that result.
- Map data must not be classified as missing if `map_data_source_status` is `hello_static_map`.

---

## Entity: `CallbackDiagnosticSnapshot`

The preserved diagnostic evidence used for late failure review. The existing snapshot record remains, but it now has to be interpreted alongside the runtime capability profile.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `snapshot_id` | string | yes | Stable per-run identifier. |
| `capture_stage` | enum | yes | `bootstrap_start`, `bootstrap_failure`, or `late_refresh`. |
| `availability_status` | enum | yes | `live`, `cached`, or `missing`. |
| `source` | enum | yes | `invoke_callback_live`, `preserved_earlier_capture`, or `not_available`. |
| `diagnostic_scope` | array of string | yes | Scope such as `commander_def`, `build_options`, `economy`, `prerequisite_resolution`. |
| `summary` | string | yes | Reviewer-facing explanation of what was captured and what was capability-limited. |
| `captured_at` | timestamp | yes | When the snapshot was captured or preserved. |

**Validation**:

- If a diagnostic scope depends on unsupported callbacks, the corresponding summary must describe a capability limit rather than a generic relay or workflow failure.
- Late transport loss must remain distinguishable from “unsupported on this host” when both appear in the same run.

---

## Entity: `RuntimePrerequisiteResolutionRecord`

The authoritative trace of how a live prerequisite name was resolved at runtime.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `prerequisite_name` | string | yes | Live prerequisite name such as `armmex`, `armvp`, or another bootstrap/build target. |
| `consumer` | enum | yes | `live_closeout` or `behavioral_build_probe`. |
| `callback_path` | string | yes | Callback route used for lookup, constrained to the supported bulk unit-def plus name-resolution path. |
| `resolved_def_id` | integer \| null | no | Runtime def id when lookup succeeded. |
| `resolution_status` | enum | yes | `resolved`, `missing`, or `relay_unavailable`. |
| `reason` | string | yes | Reviewer-facing explanation of success or failure. |
| `recorded_at` | timestamp | yes | When the lookup result was captured. |

**Validation**:

- A prerequisite used by both `live_closeout` and `behavioral_build_probe` must resolve to the same `resolved_def_id` within the same environment or be reported as a mismatch.
- `relay_unavailable` must remain distinct from `missing` so maintainers can separate transport failure from “supported callback path returned no matching name.”

---

## Entity: `MapDataSourceDecision`

The authoritative record of which source was used for map-derived targeting and diagnostics.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `consumer` | enum | yes | `live_closeout` or `behavioral_build_probe`. |
| `selected_source` | enum | yes | `hello_static_map`, `callback_map`, or `missing`. |
| `metal_spot_count` | integer | yes | Number of metal spots available from the chosen source. |
| `reason` | string | yes | Reviewer-facing explanation of why that source was selected. |
| `recorded_at` | timestamp | yes | When the selection was recorded. |

**Validation**:

- `callback_map` is not a valid selected source on the observed callback-limited host unless the capability profile explicitly marks map callbacks as supported.
- If `hello_static_map` has metal spots, `selected_source` must not be `missing`.

---

## Entity: `StandaloneBuildProbeOutcome`

The maintainer-facing result from `tests/headless/behavioral-build.sh`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `probe_id` | string | yes | Stable probe execution identifier. |
| `prerequisite_name` | string | yes | The build target prerequisite being resolved, initially `armmex`. |
| `resolution_record` | `RuntimePrerequisiteResolutionRecord` | yes | The authoritative runtime lookup used by the probe. |
| `map_source_decision` | `MapDataSourceDecision` | yes | Which source the probe used for build-position targeting. |
| `dispatch_result` | enum | yes | `verified`, `blocked`, `failed`, or `skipped`. |
| `failure_reason` | string \| null | no | Required when the probe is not verified. |
| `completed_at` | timestamp | yes | When the probe finished. |

**Validation**:

- `skipped` is not valid for the normal path merely because a manual def-id environment override was absent.
- Probe outcomes caused by unsupported deeper diagnostics must refer back to the capability profile rather than implying prerequisite-resolution failure.

---

## Relationships

```text
LiveValidationSession
├── FixtureProvisioningResult
├── BootstrapReadinessAssessment
├── RuntimeCapabilityProfile
├── CallbackDiagnosticSnapshot[]
├── RuntimePrerequisiteResolutionRecord[]
├── MapDataSourceDecision[]
├── CommandVerificationRecord[]
└── FailureCauseClassification[]

StandaloneBuildProbeOutcome
├── RuntimePrerequisiteResolutionRecord
└── MapDataSourceDecision
```

016 keeps the existing run-bundle structure intact while making callback capability limits and supported-source selection first-class review concepts instead of implicit assumptions.
