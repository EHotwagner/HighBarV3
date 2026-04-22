# Phase 1 Data Model — Build-Root Validation Completion

**Branch**: `012-build-root-validation` | **Date**: 2026-04-22  
**Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

This feature does not add a new public API or persistence layer. The design artifacts model the operational records maintainers need in order to finish the remaining 011 reruns from standard entrypoints and decide whether the feature is truly closed.

---

## Entity: `BuildRootValidationEnvironment`

The prepared validation context required before the remaining closeout reruns can begin.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `environment_id` | string | yes | Stable identifier such as `standard-build-root-linux`. |
| `build_root` | string | yes | Engine build directory used with root `ctest`. |
| `repo_root_entrypoints` | tuple<string> | yes | Repo-root scripts and Python commands required for the closeout workflow. |
| `required_targets` | tuple<string> | yes | Root-discovered CTest targets that must be visible from the build root. |
| `required_tools` | tuple<string> | yes | Tools such as `ctest`, `python3`, and `uv`. |
| `live_prerequisites_ready` | boolean | yes | Whether headless live-launch prerequisites are available. |
| `readiness_status` | enum | yes | `ready`, `blocked_environment`, or `misconfigured`. |
| `blocker_reasons` | tuple<string> | no | Concrete reasons the environment cannot yet run the remaining reruns. |

**Validation**:

- `readiness_status=ready` requires all required tools, entrypoints, and root-discovered targets to be present.
- Any missing target or tool must be surfaced in `blocker_reasons`, not inferred silently.
- A misconfigured environment does not count as a hardening failure until the standard entrypoints can actually run.

---

## Entity: `FocusedCompletionRerun`

One still-open rerun step needed to close the remaining 011 validation gap.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `rerun_id` | string | yes | Stable identifier such as `focused-cpp`, `focused-python`, `headless-suite`, or `final-full-suite`. |
| `stage` | enum | yes | `environment_check`, `focused_validation`, `failure_resolution`, or `final_closeout`. |
| `entrypoint` | string | yes | Standard build-root or repo-root command maintainers execute. |
| `expected_artifacts` | tuple<string> | no | Reports or records expected from the rerun. |
| `required_outcome` | enum | yes | `pass`, `fail`, or `blocked` depending on the observed result. |
| `blocker_classification` | enum | no | `environment`, `behavior`, or `none`. |
| `rerun_after_fix` | boolean | yes | Whether this step must be rerun after follow-up fixes. |
| `completion_critical` | boolean | yes | `true` for all steps that gate final 011 closeout. |

**Validation**:

- Focused reruns must use documented standard entrypoints only.
- `blocker_classification=environment` is valid only when prerequisites or discovery fail before behavior can be meaningfully judged.
- `rerun_after_fix=true` requires the same step to be repeated after any related failure is addressed.

---

## Entity: `CompletionOutcomeRecord`

The explicit result for one focused rerun or full-suite closeout pass.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `record_id` | string | yes | Stable identifier for the observed outcome. |
| `rerun_id` | string | yes | The `FocusedCompletionRerun` this record belongs to. |
| `outcome_status` | enum | yes | `passed`, `failed_behavior`, or `blocked_environment`. |
| `summary` | string | yes | Short maintainer-facing explanation of the result. |
| `artifact_paths` | tuple<string> | no | Manifest, report, stop-decision, or validator artifact paths tied to the outcome. |
| `requires_follow_up_fix` | boolean | yes | `true` when code or configuration work is needed before final closeout. |
| `next_action` | enum | yes | `fix_behavior`, `restore_environment`, `rerun_same_step`, or `advance_to_full_suite`. |

**Validation**:

- Every rerun must produce one explicit outcome record.
- `blocked_environment` must point at a concrete readiness issue, not a generic failure string.
- `advance_to_full_suite` is valid only after the focused reruns pass without unresolved blockers.

---

## Entity: `FinalCompletionPass`

The repeatable end-to-end rerun that closes the remaining 011 work.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `closeout_id` | string | yes | Stable identifier for the final rerun attempt. |
| `required_steps` | tuple<string> | yes | The full documented 011 completion command set. |
| `focused_records` | tuple<string> | yes | Outcome records that justify proceeding to the final rerun. |
| `final_status` | enum | yes | `complete`, `incomplete`, or `blocked`. |
| `evidence_bundle` | tuple<string> | yes | Paths to the artifacts that support the closeout decision. |
| `no_skip_enforced` | boolean | yes | Must be `true` for any successful closeout decision. |
| `closure_decision` | enum | yes | `close_011`, `fix_and_rerun`, or `restore_environment_and_rerun`. |

**Validation**:

- `final_status=complete` requires `no_skip_enforced=true` and no unresolved blockers in the evidence bundle.
- `closure_decision=close_011` requires the same standard entrypoints used in focused reruns to pass in the final rerun.
- Any blocked or incomplete result must preserve enough evidence for the next rerun attempt.

---

## Relationships

```text
BuildRootValidationEnvironment
└── FocusedCompletionRerun[]
    └── CompletionOutcomeRecord[]
        └── FinalCompletionPass
```

This model keeps the remaining work explicit: first prove the standard environment is ready, then run the open reruns, classify the outcome correctly, and only close 011 after the full documented workflow reruns cleanly.
