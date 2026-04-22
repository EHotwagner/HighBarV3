# Phase 1 Data Model — Command Contract Hardening Completion

**Branch**: `011-contract-hardening-completion` | **Date**: 2026-04-22  
**Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

This feature does not add a new external API or persistence layer. The design artifacts are maintainer-facing workflow records that define what must be runnable, discoverable, and recorded before command contract hardening is considered complete.

---

## Entity: `ValidationSuiteStep`

One required command or target in the completion validation suite.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `step_id` | string | yes | Stable identifier such as `root-ctest-contract`, `malformed-payload`, or `validator-overhead`. |
| `layer` | enum | yes | `unit`, `integration`, `pytest`, `headless`, `ctest`, or `performance`. |
| `entrypoint` | string | yes | Repo-local command, script, or test target maintainers run directly. |
| `arguments` | tuple<string> | no | Minimal argument list required for the step. |
| `expected_result` | string | yes | Success signal or pass condition maintainers should verify. |
| `artifact_paths` | tuple<string> | no | Reports, manifests, or measurement files created by the step. |
| `required_for_completion` | boolean | yes | `true` for all steps in the final completion suite. |
| `root_ctest_discoverable` | boolean | yes | `true` when the step is a build-root runnable CTest target. |

**Validation**:

- Every required step must have one repo-local entrypoint and one explicit expected result.
- `root_ctest_discoverable=true` requires the entrypoint to be runnable via filtered root `ctest`.
- Completion cannot be declared if any required step is missing, skipped, failing, or undocumented.

---

## Entity: `FoundationalIssueRepro`

Focused rerun route or explicit fallback for a foundational issue class.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `issue_class` | enum | yes | `target_drift`, `validation_gap`, `inert_dispatch`, or `needs_pattern_review`. |
| `coverage_purpose` | enum | yes | `deterministic_confirmation`, `gate_fallback`, or `prevention_regression`. |
| `repro_kind` | enum | no | `unit`, `integration`, `pytest`, or `headless`; omitted only for explicit no-repro fallback. |
| `entrypoint` | string | no | Repo-local command or target. Required for deterministic classes. |
| `arguments` | tuple<string> | no | Minimal argument list for the repro. |
| `expected_signal` | string | yes | Concrete signal that proves the issue exists, stays fixed, or intentionally has no deterministic repro. |
| `independently_runnable` | boolean | yes | `true` for deterministic repros, `false` for pattern-review-only fallback. |
| `fallback_status` | enum | yes | `deterministic`, `pattern_review_required`, or `not_applicable`. |

**Validation**:

- Deterministic issue classes require `entrypoint`, `repro_kind`, and `independently_runnable=true`.
- `needs_pattern_review` requires `fallback_status=pattern_review_required` and no silent omission from manifests or reports.
- `expected_signal` must distinguish the foundational issue from ordinary Itertesting noise.

---

## Entity: `ContractGateCase`

Expected contract-health behavior for one blocked, ready, or no-repro workflow state.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `case_id` | string | yes | Stable identifier such as `blocked-foundational`, `ready-for-itertesting`, or `pattern-review-stop`. |
| `decision_status` | enum | yes | `blocked_foundational`, `ready_for_itertesting`, or `needs_pattern_review`. |
| `manifest_contract_status` | string | yes | Expected machine-readable state in `manifest.json`. |
| `report_guidance_mode` | enum | yes | `withheld`, `secondary_only`, or `normal`. |
| `wrapper_behavior` | enum | yes | `stop_with_blockers`, `proceed_normally`, or `stop_for_review`. |
| `required_surfaces` | tuple<string> | yes | Surfaces that must agree, e.g. `manifest`, `run-report`, `headless-wrapper`, `pytest`. |
| `blocking_repro_requirement` | enum | yes | `all_deterministic`, `allow_pattern_review`, or `none`. |

**Validation**:

- `blocked_foundational` and `needs_pattern_review` must withhold ordinary improvement guidance.
- `ready_for_itertesting` requires empty blocker output and normal wrapper progression.
- Any `allow_pattern_review` case must expose the no-repro state explicitly in both machine-readable and maintainer-facing outputs.

---

## Entity: `RootCTestDiscoveryTarget`

One BARb contract-hardening test target that must be visible from the engine build root.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `target_name` | string | yes | CTest target name such as `command_validation_test`, `ai_move_flow_test`, or `command_validation_perf_test`. |
| `source_file` | string | yes | Source file that produces the target. |
| `target_kind` | enum | yes | `unit`, `integration`, or `performance`. |
| `build_root_filter` | string | yes | Regex fragment maintainers use with `ctest -R`. |
| `bridge_source` | string | yes | The generated root-bridge mechanism responsible for discovery. |
| `expected_listing_state` | enum | yes | `visible`, `runnable`, or `required`. |

**Validation**:

- Every required discovery target must appear in `ctest -N` from the engine build root.
- `build_root_filter` must be stable enough for documentation and CI use.
- The bridge source must remain the root CMake/CTest path, not a custom side runner.

---

## Entity: `ValidatorPerformanceRecord`

Machine-readable measurement artifact for the hardened validator path.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `record_id` | string | yes | Stable identifier for the measurement run. |
| `measurement_entrypoint` | string | yes | Repo-local target or command that produced the measurement. |
| `batch_shape` | string | yes | Description of the representative command batch under test. |
| `sample_count` | integer | yes | Number of validation samples collected. |
| `median_us` | number | yes | Median validation time in microseconds. |
| `p95_us` | number | yes | p95 validation time in microseconds. |
| `p99_us` | number | yes | p99 validation time in microseconds. |
| `absolute_budget_us` | number | yes | Maximum allowed p99 latency for the hardened validator path. |
| `max_regression_percent` | number | yes | Maximum allowed slowdown versus the recorded baseline. |
| `budget_assessment` | enum | yes | `within_budget`, `review_required`, or `breach`. |
| `baseline_reference` | string | no | Prior run, control case, or transport-budget context used for comparison. |
| `artifact_path` | string | yes | Repo-local path to the emitted report file. |
| `recorded_at` | timestamp | yes | UTC completion time. |

**Validation**:

- `sample_count` must be positive and large enough to support percentile calculations.
- `artifact_path` must be created as part of the measurement step and referenced from the quickstart/validation docs.
- `budget_assessment=within_budget` requires `p99_us <= absolute_budget_us` and measured slowdown `<= max_regression_percent`.
- Any status other than `within_budget` must clearly explain the comparison basis in the artifact.

---

## Relationships

```text
ValidationSuiteStep[]
├── RootCTestDiscoveryTarget[]
├── FoundationalIssueRepro[]
└── ContractGateCase[]
    └── ValidatorPerformanceRecord
```

This model keeps completion criteria explicit: what must run, what must be discoverable, how blockers are rerun or escalated, and what performance evidence is recorded before the feature can close.
