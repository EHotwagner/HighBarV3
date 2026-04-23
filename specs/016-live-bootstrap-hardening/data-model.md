# Phase 1 Data Model — Live Bootstrap Hardening

**Branch**: `016-live-bootstrap-hardening` | **Date**: 2026-04-23  
**Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

016 does not add external schemas or database tables. It extends the existing prepared live Itertesting bundle so maintainers can see whether bootstrap began from a viable state, whether callback-derived diagnostics were preserved through failure, and whether both the main workflow and the standalone build probe resolved prerequisites through the same runtime callback path.

---

## Entity: `LiveValidationSession`

The parent record for one prepared live closeout run. This remains the existing `ItertestingRun` plus its bundle under `reports/itertesting/<run-id>/`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Stable run identifier and artifact directory name. |
| `fixture_provisioning` | `FixtureProvisioningResult` | yes | Existing class-level provisioning result. |
| `bootstrap_readiness` | `BootstrapReadinessAssessment` | yes | New readiness result recorded before or during bootstrap. |
| `callback_diagnostics` | array of `CallbackDiagnosticSnapshot` | yes | Preserved callback-derived evidence for the run. |
| `prerequisite_resolution` | array of `RuntimePrerequisiteResolutionRecord` | yes | Runtime def-name lookup trace for live prerequisites. |
| `command_records` | array of `CommandVerificationRecord` | yes | Existing per-command verification outcomes. |
| `failure_classifications` | array of `FailureCauseClassification` | yes | Existing cause summaries for unverified direct commands. |

**Validation**:

- A 016 run is not review-ready unless `bootstrap_readiness` explains whether the first commander build was naturally viable, explicitly seeded, or blocked before continuing.
- `callback_diagnostics` and `prerequisite_resolution` must agree with the failure detail and any standalone probe results attached to the same environment.

---

## Entity: `BootstrapReadinessAssessment`

The maintainer-facing decision about whether prepared live closeout can realistically start commander-driven bootstrap.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Parent run id. |
| `readiness_status` | enum | yes | `natural_ready`, `seeded_ready`, `resource_starved`, or `unknown`. |
| `readiness_path` | enum | yes | `prepared_state`, `explicit_seed`, or `unavailable`. |
| `first_required_step` | string | yes | First commander-built bootstrap step being validated, such as `armmex` or `armvp`. |
| `economy_summary` | string | yes | Reviewer-facing economy snapshot such as `metal/current-income-storage`. |
| `reason` | string | yes | Why the run was considered ready, seeded, or blocked. |
| `recorded_at` | timestamp | yes | When readiness was assessed. |

**Validation**:

- `resource_starved` must appear before the first commander-built timeout becomes the primary failure signal for that run.
- `seeded_ready` must never be reported without an explicit reason describing the non-natural readiness path.

---

## Entity: `CallbackDiagnosticSnapshot`

The preserved callback-derived evidence used for late failure review.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `snapshot_id` | string | yes | Stable per-run identifier. |
| `capture_stage` | enum | yes | `bootstrap_start`, `bootstrap_failure`, or `late_refresh`. |
| `availability_status` | enum | yes | `live`, `cached`, or `missing`. |
| `source` | enum | yes | `invoke_callback_live`, `preserved_earlier_capture`, or `not_available`. |
| `diagnostic_scope` | array of string | yes | Human-readable scope such as `commander_def`, `build_options`, `economy`, `prerequisite_resolution`. |
| `summary` | string | yes | Reviewer-facing description of the captured diagnostic state. |
| `captured_at` | timestamp | yes | When the snapshot was captured or preserved. |

**Validation**:

- A run with degraded late callback reachability must still retain at least one `live` or `cached` diagnostic snapshot if earlier capture succeeded.
- `missing` is only valid when no prior capture succeeded or the captured data is genuinely unusable.

---

## Entity: `RuntimePrerequisiteResolutionRecord`

The authoritative trace of how a live prerequisite name was resolved at runtime.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `prerequisite_name` | string | yes | Live prerequisite name such as `armmex`, `armvp`, or another bootstrap/build target. |
| `consumer` | enum | yes | `live_closeout` or `behavioral_build_probe`. |
| `callback_path` | string | yes | Callback route used for lookup, typically the bulk unit-def listing plus name resolution path. |
| `resolved_def_id` | integer \| null | no | Runtime def id when lookup succeeded. |
| `resolution_status` | enum | yes | `resolved`, `missing`, or `relay_unavailable`. |
| `reason` | string | yes | Reviewer-facing explanation of success or failure. |
| `recorded_at` | timestamp | yes | When the lookup result was captured. |

**Validation**:

- A prerequisite used by both `live_closeout` and `behavioral_build_probe` must resolve to the same `resolved_def_id` within the same environment or be reported as a mismatch.
- `relay_unavailable` must remain distinct from `missing` so maintainers can separate transport issues from lookup gaps.

---

## Entity: `StandaloneBuildProbeOutcome`

The maintainer-facing result from `tests/headless/behavioral-build.sh` once it uses runtime prerequisite resolution.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `probe_id` | string | yes | Stable probe execution identifier. |
| `prerequisite_name` | string | yes | The build target prerequisite being resolved, initially `armmex`. |
| `resolution_record` | `RuntimePrerequisiteResolutionRecord` | yes | The authoritative runtime lookup used by the probe. |
| `dispatch_result` | enum | yes | `verified`, `blocked`, `failed`, or `skipped`. |
| `failure_reason` | string \| null | no | Required when the probe is not verified. |
| `completed_at` | timestamp | yes | When the probe finished. |

**Validation**:

- `skipped` is not valid for the normal path merely because a manual def-id environment override was absent.
- Probe failures caused by runtime lookup must point to `resolution_record` rather than emitting a stale env-var message.

---

## Relationships

```text
LiveValidationSession
├── FixtureProvisioningResult
├── BootstrapReadinessAssessment
├── CallbackDiagnosticSnapshot[]
├── RuntimePrerequisiteResolutionRecord[]
├── CommandVerificationRecord[]
└── FailureCauseClassification[]

StandaloneBuildProbeOutcome
└── RuntimePrerequisiteResolutionRecord
```

016 keeps the 014/015 bundle structure intact while making bootstrap viability, diagnostic preservation, and runtime prerequisite resolution first-class review concepts instead of timing-dependent log fragments.
