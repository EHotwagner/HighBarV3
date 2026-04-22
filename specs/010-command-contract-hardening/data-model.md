# Phase 1 Data Model — Command Contract Hardening

**Branch**: `010-command-contract-hardening` | **Date**: 2026-04-22  
**Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

This feature extends the existing gateway and Itertesting workflow without introducing a database or public API version change. All entities are transport-adjacent workflow records or maintainer-facing contracts consumed by the current gateway, reporting, and deterministic repro surfaces.

---

## Entity: `CommandContractIssue`

Maintainer-facing record describing a foundational command defect detected during validation, dispatch, or run classification.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `issue_id` | string | yes | Stable per-run identifier, typically derived from `run_id`, `command_id`, and issue class. |
| `run_id` | string | yes | Parent run identifier. |
| `command_id` | string | yes | Stable command identifier such as `cmd-move-unit`. |
| `issue_class` | enum | yes | At minimum `target_drift`, `validation_gap`, `inert_dispatch`; additional classes must remain foundational rather than downstream workflow noise. |
| `primary_cause` | string | yes | Short maintainer-facing description of the contract defect. |
| `evidence_summary` | string | yes | First concrete signal that triggered classification. |
| `source_scope` | enum | yes | `validator`, `queue_normalization`, `dispatcher`, `run_classification`, or `repro_followup`. |
| `blocks_improvement` | boolean | yes | Whether this issue makes normal Itertesting guidance non-actionable for the run. |
| `status` | enum | yes | `open`, `reproduced`, `resolved_in_later_run`, or `needs_new_pattern_review`. |

**Validation**:

- Every foundational issue must map to exactly one `command_id`, even if the root cause is run-level.
- `issue_class` must not be reused for ordinary setup/evidence gaps.
- `blocks_improvement=true` is required for unresolved foundational defects discovered in the same run.

---

## Entity: `DeterministicRepro`

Executable confirmation path linked to one `CommandContractIssue`.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `repro_id` | string | yes | Stable identifier for the repro route. |
| `issue_id` | string | yes | Parent foundational issue id. |
| `command_id` | string | yes | Command the repro is intended to confirm. |
| `repro_kind` | enum | yes | `unit`, `integration`, `headless`, `pytest`, or `audit`. |
| `entrypoint` | string | yes | Repo-local command or script path. |
| `arguments` | tuple<string> | no | Minimal argument list needed to reproduce the defect. |
| `expected_signal` | string | yes | Deterministic success condition proving the issue exists or has been fixed. |
| `artifact_path` | string | no | Optional report, log, or generated artifact path. |
| `independently_runnable` | boolean | yes | Must be true for spec compliance. |

**Validation**:

- Every `CommandContractIssue` should have one primary repro path unless the issue is marked `needs_new_pattern_review`.
- `entrypoint` must resolve to a repo-local executable test path or documented command.
- `expected_signal` must be specific enough to distinguish the foundational issue from unrelated run noise.

---

## Entity: `ContractHealthDecision`

Run-level decision on whether the command surface is coherent enough for normal Itertesting improvement behavior.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Parent run identifier. |
| `decision_status` | enum | yes | `ready_for_itertesting`, `blocked_foundational`, or `needs_pattern_review`. |
| `blocking_issue_ids` | tuple<string> | yes | Foundational issues keeping the run from normal improvement mode. |
| `summary_message` | string | yes | Maintainer-facing gate summary. |
| `stop_or_proceed` | enum | yes | `stop_for_repair`, `proceed_with_improvement`, or `proceed_but_flag_review`. |
| `recorded_at` | timestamp | yes | UTC time when the decision was finalized. |
| `resolved_issue_ids` | tuple<string> | no | Previously blocking issues that cleared in this run. |

**Validation**:

- `decision_status=blocked_foundational` requires at least one unresolved blocking issue.
- `decision_status=ready_for_itertesting` requires `blocking_issue_ids` to be empty.
- `stop_or_proceed` must align with `decision_status`.

---

## Entity: `ImprovementEligibility`

Run-scoped summary of whether ordinary Itertesting recommendations should be emitted or withheld.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `run_id` | string | yes | Parent run identifier. |
| `contract_health_status` | enum | yes | Mirrors `ContractHealthDecision.decision_status`. |
| `guidance_mode` | enum | yes | `withheld`, `secondary_only`, or `normal`. |
| `withheld_reason` | string | no | Required when guidance is not `normal`. |
| `visible_downstream_findings` | tuple<string> | yes | Secondary findings still shown to maintainers. |
| `normal_improvement_actions` | tuple<string> | yes | Empty when the gate is closed. |

**Validation**:

- `guidance_mode=normal` requires `contract_health_status=ready_for_itertesting`.
- `normal_improvement_actions` must be empty whenever `guidance_mode != normal`.
- `secondary_only` is the expected mode when foundational blockers exist but downstream observations are still preserved for context.

---

## Relationships

```text
CommandContractIssue[]
├── DeterministicRepro[]
└── ContractHealthDecision
    └── ImprovementEligibility
```

This model keeps foundational contract defects, focused confirmation routes, and normal Itertesting guidance separate so the workflow can stop for repair without hiding the evidence maintainers still need.
